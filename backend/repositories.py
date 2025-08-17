"""
Repository layer for database operations
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from models import (
    Vendor, Contract, Invoice, Reconciliation, 
    ContractLineItem, InvoiceLineItem, ReconciliationSession,
    AuditLog
)
import json


class BaseRepository:
    """Base repository with common CRUD operations"""
    
    def __init__(self, session: Session, model):
        self.session = session
        self.model = model
    
    def create(self, **kwargs) -> Any:
        """Create a new entity"""
        entity = self.model(**kwargs)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
    
    def get_by_id(self, entity_id: str) -> Optional[Any]:
        """Get entity by ID"""
        return self.session.query(self.model).filter(
            self.model.id == entity_id
        ).first()
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        """Get all entities with pagination"""
        return self.session.query(self.model).limit(limit).offset(offset).all()
    
    def update(self, entity_id: str, **kwargs) -> Optional[Any]:
        """Update an entity"""
        entity = self.get_by_id(entity_id)
        if entity:
            for key, value in kwargs.items():
                setattr(entity, key, value)
            entity.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(entity)
        return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete an entity"""
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.commit()
            return True
        return False
    
    def search(self, filters: Dict[str, Any], limit: int = 100) -> List[Any]:
        """Search with filters"""
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.limit(limit).all()


class VendorRepository(BaseRepository):
    """Repository for Vendor operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, Vendor)
    
    def find_by_name(self, name: str) -> Optional[Vendor]:
        """Find vendor by name (case-insensitive)"""
        return self.session.query(Vendor).filter(
            Vendor.name.ilike(f'%{name}%')
        ).first()
    
    def get_active_vendors(self) -> List[Vendor]:
        """Get all active vendors"""
        return self.session.query(Vendor).filter(
            Vendor.status == 'active'
        ).order_by(Vendor.name).all()
    
    def get_vendor_with_contracts(self, vendor_id: str) -> Optional[Vendor]:
        """Get vendor with all contracts"""
        return self.session.query(Vendor).filter(
            Vendor.id == vendor_id
        ).first()
    
    def search_vendors(self, search_term: str) -> List[Vendor]:
        """Search vendors by name or legal name"""
        search_pattern = f'%{search_term}%'
        return self.session.query(Vendor).filter(
            or_(
                Vendor.name.ilike(search_pattern),
                Vendor.legal_name.ilike(search_pattern),
                Vendor.tax_id.ilike(search_pattern)
            )
        ).all()


class ContractRepository(BaseRepository):
    """Repository for Contract operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, Contract)
    
    def find_by_contract_number(self, contract_number: str) -> Optional[Contract]:
        """Find contract by contract number"""
        return self.session.query(Contract).filter(
            Contract.contract_number == contract_number
        ).first()
    
    def get_active_contracts(self, vendor_id: Optional[str] = None) -> List[Contract]:
        """Get active contracts, optionally filtered by vendor"""
        query = self.session.query(Contract).filter(
            Contract.status == 'active'
        )
        if vendor_id:
            query = query.filter(Contract.vendor_id == vendor_id)
        return query.all()
    
    def get_expiring_contracts(self, days: int = 30) -> List[Contract]:
        """Get contracts expiring within specified days"""
        expiry_date = datetime.utcnow() + timedelta(days=days)
        return self.session.query(Contract).filter(
            and_(
                Contract.end_date <= expiry_date,
                Contract.end_date >= datetime.utcnow(),
                Contract.status == 'active'
            )
        ).all()
    
    def create_with_line_items(self, contract_data: dict, line_items: List[dict]) -> Contract:
        """Create contract with line items"""
        contract = Contract(**contract_data)
        self.session.add(contract)
        
        for item_data in line_items:
            item = ContractLineItem(contract_id=contract.id, **item_data)
            self.session.add(item)
        
        self.session.commit()
        self.session.refresh(contract)
        return contract


class InvoiceRepository(BaseRepository):
    """Repository for Invoice operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, Invoice)
    
    def find_by_invoice_number(self, invoice_number: str) -> Optional[Invoice]:
        """Find invoice by invoice number"""
        return self.session.query(Invoice).filter(
            Invoice.invoice_number == invoice_number
        ).first()
    
    def get_pending_invoices(self, vendor_id: Optional[str] = None) -> List[Invoice]:
        """Get pending invoices"""
        query = self.session.query(Invoice).filter(
            Invoice.status == 'pending'
        )
        if vendor_id:
            query = query.filter(Invoice.vendor_id == vendor_id)
        return query.order_by(Invoice.due_date).all()
    
    def get_overdue_invoices(self) -> List[Invoice]:
        """Get overdue invoices"""
        return self.session.query(Invoice).filter(
            and_(
                Invoice.due_date < datetime.utcnow(),
                Invoice.status.in_(['pending', 'overdue'])
            )
        ).all()
    
    def create_with_line_items(self, invoice_data: dict, line_items: List[dict]) -> Invoice:
        """Create invoice with line items"""
        invoice = Invoice(**invoice_data)
        self.session.add(invoice)
        
        for item_data in line_items:
            item = InvoiceLineItem(invoice_id=invoice.id, **item_data)
            self.session.add(item)
        
        self.session.commit()
        self.session.refresh(invoice)
        return invoice
    
    def get_invoices_by_contract(self, contract_number: str) -> List[Invoice]:
        """Get all invoices referencing a contract"""
        return self.session.query(Invoice).filter(
            Invoice.reference_contract_number == contract_number
        ).all()


class ReconciliationRepository(BaseRepository):
    """Repository for Reconciliation operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, Reconciliation)
    
    def get_recent_reconciliations(self, limit: int = 10) -> List[Reconciliation]:
        """Get recent reconciliations"""
        return self.session.query(Reconciliation).order_by(
            desc(Reconciliation.performed_at)
        ).limit(limit).all()
    
    def get_failed_reconciliations(self, vendor_id: Optional[str] = None) -> List[Reconciliation]:
        """Get failed reconciliations"""
        query = self.session.query(Reconciliation).filter(
            Reconciliation.status == 'failed'
        )
        if vendor_id:
            query = query.filter(Reconciliation.vendor_id == vendor_id)
        return query.order_by(desc(Reconciliation.performed_at)).all()
    
    def get_vendor_reconciliation_history(self, vendor_id: str) -> List[Reconciliation]:
        """Get reconciliation history for a vendor"""
        return self.session.query(Reconciliation).filter(
            Reconciliation.vendor_id == vendor_id
        ).order_by(desc(Reconciliation.performed_at)).all()
    
    def create_reconciliation_record(
        self, 
        vendor_id: str,
        contract_id: str,
        invoice_id: str,
        comparison_results: dict,
        performed_by: str = 'system'
    ) -> Reconciliation:
        """Create a reconciliation record from comparison results"""
        reconciliation = Reconciliation(
            vendor_id=vendor_id,
            contract_id=contract_id,
            invoice_id=invoice_id,
            status=comparison_results['summary']['reconciliation_status'].lower(),
            discrepancy_count=comparison_results['summary']['total_discrepancies'],
            warning_count=comparison_results['summary']['total_warnings'],
            match_count=comparison_results['summary']['total_matches'],
            discrepancies=comparison_results['discrepancies'],
            warnings=comparison_results['warnings'],
            matches=comparison_results['matches'],
            summary=comparison_results['summary'],
            performed_by=performed_by
        )
        self.session.add(reconciliation)
        self.session.commit()
        self.session.refresh(reconciliation)
        return reconciliation


class ReconciliationSessionRepository(BaseRepository):
    """Repository for temporary reconciliation sessions"""
    
    def __init__(self, session: Session):
        super().__init__(session, ReconciliationSession)
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        expired_sessions = self.session.query(ReconciliationSession).filter(
            ReconciliationSession.expires_at < datetime.utcnow()
        ).all()
        
        count = len(expired_sessions)
        for session in expired_sessions:
            self.session.delete(session)
        
        self.session.commit()
        return count
    
    def create_session(self, contract_path: str, invoice_path: str) -> ReconciliationSession:
        """Create a new reconciliation session"""
        session = ReconciliationSession(
            contract_file_path=contract_path,
            invoice_file_path=invoice_path,
            status='uploaded',
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session


class AuditLogRepository(BaseRepository):
    """Repository for audit logs"""
    
    def __init__(self, session: Session):
        super().__init__(session, AuditLog)
    
    def log_action(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        changes: dict = None,
        performed_by: str = 'system',
        ip_address: str = None
    ) -> AuditLog:
        """Log an action"""
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            performed_by=performed_by,
            ip_address=ip_address
        )
        self.session.add(log)
        self.session.commit()
        return log
    
    def get_entity_history(self, entity_type: str, entity_id: str) -> List[AuditLog]:
        """Get audit history for an entity"""
        return self.session.query(AuditLog).filter(
            and_(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id
            )
        ).order_by(desc(AuditLog.performed_at)).all()