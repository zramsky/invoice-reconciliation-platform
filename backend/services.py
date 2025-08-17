"""
Service layer for business logic
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import os
import shutil
from repositories import (
    VendorRepository, ContractRepository, InvoiceRepository,
    ReconciliationRepository, ReconciliationSessionRepository,
    AuditLogRepository
)
from models import get_session
from ocr_processor import OCRProcessor
from ai_analyzer import AIAnalyzer
import logging

logger = logging.getLogger(__name__)


class VendorService:
    """Service for vendor management"""
    
    def __init__(self):
        self.session = get_session()
        self.vendor_repo = VendorRepository(self.session)
        self.audit_repo = AuditLogRepository(self.session)
    
    def create_vendor(self, vendor_data: dict, created_by: str = 'system') -> dict:
        """Create a new vendor"""
        try:
            # Check if vendor already exists
            existing = self.vendor_repo.find_by_name(vendor_data.get('name'))
            if existing:
                return {
                    'success': False,
                    'message': f"Vendor with name '{vendor_data['name']}' already exists",
                    'vendor_id': existing.id
                }
            
            vendor = self.vendor_repo.create(**vendor_data)
            
            # Log the action
            self.audit_repo.log_action(
                entity_type='vendor',
                entity_id=vendor.id,
                action='create',
                changes=vendor_data,
                performed_by=created_by
            )
            
            return {
                'success': True,
                'vendor': self._vendor_to_dict(vendor)
            }
        except Exception as e:
            logger.error(f"Error creating vendor: {str(e)}")
            self.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
        finally:
            self.session.close()
    
    def update_vendor(self, vendor_id: str, updates: dict, updated_by: str = 'system') -> dict:
        """Update vendor information"""
        try:
            vendor = self.vendor_repo.update(vendor_id, **updates)
            if not vendor:
                return {
                    'success': False,
                    'message': 'Vendor not found'
                }
            
            # Log the action
            self.audit_repo.log_action(
                entity_type='vendor',
                entity_id=vendor_id,
                action='update',
                changes=updates,
                performed_by=updated_by
            )
            
            return {
                'success': True,
                'vendor': self._vendor_to_dict(vendor)
            }
        except Exception as e:
            logger.error(f"Error updating vendor: {str(e)}")
            self.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
        finally:
            self.session.close()
    
    def get_vendor(self, vendor_id: str) -> Optional[dict]:
        """Get vendor details"""
        try:
            vendor = self.vendor_repo.get_vendor_with_contracts(vendor_id)
            if vendor:
                return self._vendor_to_dict(vendor, include_contracts=True)
            return None
        finally:
            self.session.close()
    
    def list_vendors(self, active_only: bool = True) -> List[dict]:
        """List all vendors"""
        try:
            if active_only:
                vendors = self.vendor_repo.get_active_vendors()
            else:
                vendors = self.vendor_repo.get_all()
            
            return [self._vendor_to_dict(v) for v in vendors]
        finally:
            self.session.close()
    
    def search_vendors(self, search_term: str) -> List[dict]:
        """Search vendors"""
        try:
            vendors = self.vendor_repo.search_vendors(search_term)
            return [self._vendor_to_dict(v) for v in vendors]
        finally:
            self.session.close()
    
    def _vendor_to_dict(self, vendor, include_contracts: bool = False) -> dict:
        """Convert vendor object to dictionary"""
        vendor_dict = {
            'id': vendor.id,
            'name': vendor.name,
            'legal_name': vendor.legal_name,
            'business_type': vendor.business_type,
            'tax_id': vendor.tax_id,
            'address': vendor.address,
            'contact_email': vendor.contact_email,
            'contact_phone': vendor.contact_phone,
            'status': vendor.status,
            'created_at': vendor.created_at.isoformat() if vendor.created_at else None,
            'updated_at': vendor.updated_at.isoformat() if vendor.updated_at else None,
            'metadata': vendor.metadata
        }
        
        if include_contracts and vendor.contracts:
            vendor_dict['contracts'] = [
                {
                    'id': c.id,
                    'contract_number': c.contract_number,
                    'title': c.title,
                    'status': c.status,
                    'total_value': c.total_value,
                    'start_date': c.start_date.isoformat() if c.start_date else None,
                    'end_date': c.end_date.isoformat() if c.end_date else None
                }
                for c in vendor.contracts
            ]
        
        return vendor_dict


class ContractService:
    """Service for contract management"""
    
    def __init__(self):
        self.session = get_session()
        self.contract_repo = ContractRepository(self.session)
        self.vendor_repo = VendorRepository(self.session)
        self.audit_repo = AuditLogRepository(self.session)
        self.ocr_processor = OCRProcessor()
        self.ai_analyzer = AIAnalyzer(os.getenv('OPENAI_API_KEY'))
    
    def process_contract_document(
        self, 
        file_path: str, 
        vendor_id: Optional[str] = None
    ) -> dict:
        """Process a contract document and extract information"""
        try:
            # Extract text using OCR
            contract_text = self.ocr_processor.process_document(file_path)
            
            # Extract details using AI
            contract_details = self.ai_analyzer.extract_contract_details(contract_text)
            
            # If vendor_id not provided, try to find or create vendor
            if not vendor_id:
                vendor_name = contract_details.get('vendor_name')
                if vendor_name:
                    vendor = self.vendor_repo.find_by_name(vendor_name)
                    if not vendor:
                        # Create new vendor
                        vendor = self.vendor_repo.create(
                            name=vendor_name,
                            business_type=contract_details.get('business_type'),
                            metadata={'auto_created': True}
                        )
                    vendor_id = vendor.id
            
            # Prepare contract data
            contract_data = {
                'vendor_id': vendor_id,
                'contract_number': contract_details.get('contract_number'),
                'title': contract_details.get('service_description'),
                'description': contract_details.get('service_description'),
                'total_value': self._parse_amount(contract_details.get('total_value')),
                'payment_terms': contract_details.get('payment_terms'),
                'billing_frequency': contract_details.get('billing_frequency'),
                'original_file_path': file_path,
                'extracted_text': contract_text[:5000],  # Store first 5000 chars
                'ai_analysis': contract_details,
                'status': 'active'
            }
            
            # Parse dates
            if contract_details.get('start_date'):
                contract_data['start_date'] = self._parse_date(contract_details['start_date'])
            if contract_details.get('end_date'):
                contract_data['end_date'] = self._parse_date(contract_details['end_date'])
            
            # Extract line items
            line_items = []
            if contract_details.get('items'):
                for item in contract_details['items']:
                    line_items.append({
                        'description': item.get('description'),
                        'quantity': item.get('quantity', 1),
                        'unit_price': self._parse_amount(item.get('price')),
                        'total_price': self._parse_amount(item.get('total'))
                    })
            
            # Create contract with line items
            contract = self.contract_repo.create_with_line_items(contract_data, line_items)
            
            # Log the action
            self.audit_repo.log_action(
                entity_type='contract',
                entity_id=contract.id,
                action='create',
                changes={'source': 'document_processing'},
                performed_by='system'
            )
            
            return {
                'success': True,
                'contract': self._contract_to_dict(contract),
                'extracted_details': contract_details
            }
            
        except Exception as e:
            logger.error(f"Error processing contract document: {str(e)}")
            self.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
        finally:
            self.session.close()
    
    def get_contract(self, contract_id: str) -> Optional[dict]:
        """Get contract details"""
        try:
            contract = self.contract_repo.get_by_id(contract_id)
            if contract:
                return self._contract_to_dict(contract)
            return None
        finally:
            self.session.close()
    
    def list_contracts(self, vendor_id: Optional[str] = None) -> List[dict]:
        """List contracts"""
        try:
            contracts = self.contract_repo.get_active_contracts(vendor_id)
            return [self._contract_to_dict(c) for c in contracts]
        finally:
            self.session.close()
    
    def get_expiring_contracts(self, days: int = 30) -> List[dict]:
        """Get contracts expiring soon"""
        try:
            contracts = self.contract_repo.get_expiring_contracts(days)
            return [self._contract_to_dict(c) for c in contracts]
        finally:
            self.session.close()
    
    def _contract_to_dict(self, contract) -> dict:
        """Convert contract object to dictionary"""
        return {
            'id': contract.id,
            'vendor_id': contract.vendor_id,
            'vendor_name': contract.vendor.name if contract.vendor else None,
            'contract_number': contract.contract_number,
            'title': contract.title,
            'description': contract.description,
            'start_date': contract.start_date.isoformat() if contract.start_date else None,
            'end_date': contract.end_date.isoformat() if contract.end_date else None,
            'total_value': contract.total_value,
            'payment_terms': contract.payment_terms,
            'billing_frequency': contract.billing_frequency,
            'status': contract.status,
            'ai_analysis': contract.ai_analysis,
            'created_at': contract.created_at.isoformat() if contract.created_at else None,
            'line_items': [
                {
                    'id': item.id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                }
                for item in contract.line_items
            ] if contract.line_items else []
        }
    
    def _parse_amount(self, amount_str) -> float:
        """Parse amount string to float"""
        if not amount_str:
            return 0.0
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        amount_str = str(amount_str).replace('$', '').replace(',', '')
        try:
            return float(amount_str)
        except:
            return 0.0
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        
        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%m-%d-%Y',
            '%d-%m-%Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None


class InvoiceService:
    """Service for invoice management"""
    
    def __init__(self):
        self.session = get_session()
        self.invoice_repo = InvoiceRepository(self.session)
        self.vendor_repo = VendorRepository(self.session)
        self.contract_repo = ContractRepository(self.session)
        self.audit_repo = AuditLogRepository(self.session)
        self.ocr_processor = OCRProcessor()
        self.ai_analyzer = AIAnalyzer(os.getenv('OPENAI_API_KEY'))
    
    def process_invoice_document(
        self, 
        file_path: str,
        vendor_id: Optional[str] = None
    ) -> dict:
        """Process an invoice document and extract information"""
        try:
            # Extract text using OCR
            invoice_text = self.ocr_processor.process_document(file_path)
            
            # Extract details using AI
            invoice_details = self.ai_analyzer.extract_invoice_details(invoice_text)
            
            # If vendor_id not provided, try to find vendor
            if not vendor_id:
                vendor_name = invoice_details.get('vendor_name')
                if vendor_name:
                    vendor = self.vendor_repo.find_by_name(vendor_name)
                    if vendor:
                        vendor_id = vendor.id
            
            # Prepare invoice data
            invoice_data = {
                'vendor_id': vendor_id,
                'invoice_number': invoice_details.get('invoice_number'),
                'subtotal': self._parse_amount(invoice_details.get('subtotal')),
                'tax_amount': self._parse_amount(invoice_details.get('tax_amount')),
                'total_amount': self._parse_amount(invoice_details.get('total_amount')),
                'reference_contract_number': invoice_details.get('reference_contract_number'),
                'original_file_path': file_path,
                'extracted_text': invoice_text[:5000],
                'ai_analysis': invoice_details,
                'status': 'pending'
            }
            
            # Parse dates
            if invoice_details.get('invoice_date'):
                invoice_data['invoice_date'] = self._parse_date(invoice_details['invoice_date'])
            if invoice_details.get('due_date'):
                invoice_data['due_date'] = self._parse_date(invoice_details['due_date'])
            
            # Extract line items
            line_items = []
            if invoice_details.get('items'):
                for item in invoice_details['items']:
                    line_items.append({
                        'description': item.get('description'),
                        'quantity': item.get('quantity', 1),
                        'unit_price': self._parse_amount(item.get('unit_price')),
                        'total_price': self._parse_amount(item.get('total'))
                    })
            
            # Create invoice with line items
            invoice = self.invoice_repo.create_with_line_items(invoice_data, line_items)
            
            # Log the action
            self.audit_repo.log_action(
                entity_type='invoice',
                entity_id=invoice.id,
                action='create',
                changes={'source': 'document_processing'},
                performed_by='system'
            )
            
            return {
                'success': True,
                'invoice': self._invoice_to_dict(invoice),
                'extracted_details': invoice_details
            }
            
        except Exception as e:
            logger.error(f"Error processing invoice document: {str(e)}")
            self.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
        finally:
            self.session.close()
    
    def get_invoice(self, invoice_id: str) -> Optional[dict]:
        """Get invoice details"""
        try:
            invoice = self.invoice_repo.get_by_id(invoice_id)
            if invoice:
                return self._invoice_to_dict(invoice)
            return None
        finally:
            self.session.close()
    
    def list_invoices(self, vendor_id: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
        """List invoices"""
        try:
            if status == 'pending':
                invoices = self.invoice_repo.get_pending_invoices(vendor_id)
            elif status == 'overdue':
                invoices = self.invoice_repo.get_overdue_invoices()
            else:
                filters = {}
                if vendor_id:
                    filters['vendor_id'] = vendor_id
                if status:
                    filters['status'] = status
                invoices = self.invoice_repo.search(filters)
            
            return [self._invoice_to_dict(i) for i in invoices]
        finally:
            self.session.close()
    
    def _invoice_to_dict(self, invoice) -> dict:
        """Convert invoice object to dictionary"""
        return {
            'id': invoice.id,
            'vendor_id': invoice.vendor_id,
            'vendor_name': invoice.vendor.name if invoice.vendor else None,
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
            'payment_date': invoice.payment_date.isoformat() if invoice.payment_date else None,
            'subtotal': invoice.subtotal,
            'tax_amount': invoice.tax_amount,
            'total_amount': invoice.total_amount,
            'status': invoice.status,
            'reference_contract_number': invoice.reference_contract_number,
            'ai_analysis': invoice.ai_analysis,
            'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
            'line_items': [
                {
                    'id': item.id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                }
                for item in invoice.line_items
            ] if invoice.line_items else []
        }
    
    def _parse_amount(self, amount_str) -> float:
        """Parse amount string to float"""
        if not amount_str:
            return 0.0
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        amount_str = str(amount_str).replace('$', '').replace(',', '')
        try:
            return float(amount_str)
        except:
            return 0.0
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        
        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%m-%d-%Y',
            '%d-%m-%Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None


class ReconciliationService:
    """Service for reconciliation operations"""
    
    def __init__(self):
        self.session = get_session()
        self.reconciliation_repo = ReconciliationRepository(self.session)
        self.contract_repo = ContractRepository(self.session)
        self.invoice_repo = InvoiceRepository(self.session)
        self.audit_repo = AuditLogRepository(self.session)
        self.ai_analyzer = AIAnalyzer(os.getenv('OPENAI_API_KEY'))
    
    def reconcile_contract_invoice(
        self,
        contract_id: str,
        invoice_id: str,
        performed_by: str = 'system'
    ) -> dict:
        """Reconcile a contract with an invoice"""
        try:
            # Get contract and invoice
            contract = self.contract_repo.get_by_id(contract_id)
            invoice = self.invoice_repo.get_by_id(invoice_id)
            
            if not contract or not invoice:
                return {
                    'success': False,
                    'message': 'Contract or invoice not found'
                }
            
            # Perform reconciliation
            contract_details = contract.ai_analysis or {}
            invoice_details = invoice.ai_analysis or {}
            
            comparison_results = self.ai_analyzer.compare_documents(
                contract_details,
                invoice_details
            )
            
            # Create reconciliation record
            reconciliation = self.reconciliation_repo.create_reconciliation_record(
                vendor_id=contract.vendor_id,
                contract_id=contract_id,
                invoice_id=invoice_id,
                comparison_results=comparison_results,
                performed_by=performed_by
            )
            
            # Log the action
            self.audit_repo.log_action(
                entity_type='reconciliation',
                entity_id=reconciliation.id,
                action='create',
                changes={
                    'contract_id': contract_id,
                    'invoice_id': invoice_id,
                    'status': reconciliation.status
                },
                performed_by=performed_by
            )
            
            return {
                'success': True,
                'reconciliation': self._reconciliation_to_dict(reconciliation)
            }
            
        except Exception as e:
            logger.error(f"Error performing reconciliation: {str(e)}")
            self.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
        finally:
            self.session.close()
    
    def get_reconciliation_history(
        self,
        vendor_id: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """Get reconciliation history"""
        try:
            if vendor_id:
                reconciliations = self.reconciliation_repo.get_vendor_reconciliation_history(vendor_id)
            else:
                reconciliations = self.reconciliation_repo.get_recent_reconciliations(limit)
            
            return [self._reconciliation_to_dict(r) for r in reconciliations]
        finally:
            self.session.close()
    
    def get_failed_reconciliations(self, vendor_id: Optional[str] = None) -> List[dict]:
        """Get failed reconciliations"""
        try:
            reconciliations = self.reconciliation_repo.get_failed_reconciliations(vendor_id)
            return [self._reconciliation_to_dict(r) for r in reconciliations]
        finally:
            self.session.close()
    
    def _reconciliation_to_dict(self, reconciliation) -> dict:
        """Convert reconciliation object to dictionary"""
        return {
            'id': reconciliation.id,
            'vendor_id': reconciliation.vendor_id,
            'vendor_name': reconciliation.vendor.name if reconciliation.vendor else None,
            'contract_id': reconciliation.contract_id,
            'contract_number': reconciliation.contract.contract_number if reconciliation.contract else None,
            'invoice_id': reconciliation.invoice_id,
            'invoice_number': reconciliation.invoice.invoice_number if reconciliation.invoice else None,
            'status': reconciliation.status,
            'discrepancy_count': reconciliation.discrepancy_count,
            'warning_count': reconciliation.warning_count,
            'match_count': reconciliation.match_count,
            'discrepancies': reconciliation.discrepancies,
            'warnings': reconciliation.warnings,
            'matches': reconciliation.matches,
            'summary': reconciliation.summary,
            'performed_at': reconciliation.performed_at.isoformat() if reconciliation.performed_at else None,
            'performed_by': reconciliation.performed_by
        }