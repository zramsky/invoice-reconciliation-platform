"""
Deterministic reconciliation engine for Unspend
Handles matching, rules validation, and flag generation
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from schemas import (
    ContractSchema, InvoiceSchema, Match, Flag, FlagType, SeverityType,
    FlagEvidence, ServiceDates, NextPaymentPreview, PaymentItem,
    ReconciliationResult, MatchMethodType
)

class ReconciliationEngine:
    def __init__(self, database=None):
        self.vendor_aliases = {}  # Will store vendor name aliases
        self.processed_invoices = []  # For duplicate detection
        self.database = database  # For vendor auto-discovery
        
    def reconcile(self, contract: Dict[str, Any], invoice: Dict[str, Any]) -> ReconciliationResult:
        """
        Main reconciliation function - runs deterministic matching and rules
        """
        # Step 1: Vendor matching
        vendor_match = self._match_vendor(contract, invoice)
        if not vendor_match:
            return ReconciliationResult(
                flags=[Flag(
                    type=FlagType.OUT_OF_SCOPE,
                    severity=SeverityType.ERROR,
                    summary="Vendor mismatch - invoice and contract are from different vendors",
                    evidence=FlagEvidence()
                )]
            )
        
        # Step 2: Contract selection by dates
        if not self._is_contract_active(contract, invoice):
            return ReconciliationResult(
                flags=[Flag(
                    type=FlagType.DATE_VARIANCE,
                    severity=SeverityType.ERROR,
                    summary="Invoice date is outside contract term",
                    evidence=FlagEvidence(
                        service_dates=ServiceDates(
                            invoice_start=invoice.get('invoice_date', {}).get('value', ''),
                            contract_start=contract.get('start_date', {}).get('value', ''),
                            contract_end=contract.get('end_date', {}).get('value', '')
                        )
                    )
                )]
            )
        
        # Step 3: Line matching
        matches = self._match_lines(contract, invoice)
        
        # Step 4: Rules validation
        flags = self._validate_rules(contract, invoice, matches)
        
        # Step 5: Generate next payment preview
        next_payment = self._generate_payment_preview(contract, invoice, matches)
        
        return ReconciliationResult(
            matches=matches,
            flags=flags,
            next_payment_preview=next_payment
        )
    
    def _match_vendor(self, contract: Dict[str, Any], invoice: Dict[str, Any]) -> bool:
        """Match vendors using exact match then alias table"""
        contract_vendor = contract.get('vendor', {}).get('value', '').lower().strip()
        invoice_vendor = invoice.get('vendor', {}).get('value', '').lower().strip()
        
        if not contract_vendor or not invoice_vendor:
            return False
        
        # Exact match
        if contract_vendor == invoice_vendor:
            self._auto_discover_vendor(contract_vendor, contract, invoice)
            return True
        
        # Database alias lookup if available
        if self.database:
            contract_vendor_record = self.database.get_vendor_by_name(contract_vendor)
            invoice_vendor_record = self.database.get_vendor_by_name(invoice_vendor)
            
            if contract_vendor_record and invoice_vendor_record:
                if contract_vendor_record['id'] == invoice_vendor_record['id']:
                    return True
        
        # Alias table lookup (legacy)
        if contract_vendor in self.vendor_aliases:
            aliases = self.vendor_aliases[contract_vendor]
            if invoice_vendor in [alias.lower() for alias in aliases]:
                return True
        
        # Fuzzy match using common business name patterns
        contract_clean = self._clean_business_name(contract_vendor)
        invoice_clean = self._clean_business_name(invoice_vendor)
        
        if contract_clean == invoice_clean:
            self._auto_discover_vendor(contract_vendor, contract, invoice)
            # Auto-create alias if fuzzy match succeeds
            self._auto_create_alias(contract_vendor, invoice_vendor)
            return True
        
        return False
    
    def _auto_discover_vendor(self, vendor_name: str, contract: Dict[str, Any], invoice: Dict[str, Any]):
        """Auto-discover and create vendor record if not exists"""
        if not self.database:
            return
        
        try:
            # Check if vendor already exists
            existing_vendor = self.database.get_vendor_by_name(vendor_name)
            if existing_vendor:
                return existing_vendor['id']
            
            # Extract vendor information from contract/invoice
            vendor_info = self._extract_vendor_info(vendor_name, contract, invoice)
            
            # Create new vendor
            vendor_id = self.database.create_vendor(
                canonical_name=vendor_name,
                display_name=vendor_info.get('display_name', vendor_name.title()),
                industry=vendor_info.get('industry'),
                contact_email=vendor_info.get('contact_email'),
                notes=f"Auto-discovered from reconciliation on {datetime.now().isoformat()}"
            )
            
            return vendor_id
        except Exception:
            # Fail silently for auto-discovery
            pass
    
    def _extract_vendor_info(self, vendor_name: str, contract: Dict[str, Any], invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional vendor information from documents"""
        vendor_info = {'display_name': vendor_name.title()}
        
        # Try to extract contact email from invoice
        if 'contact_email' in invoice:
            vendor_info['contact_email'] = invoice['contact_email'].get('value')
        
        # Try to extract service category as industry from contract
        if 'service_category' in contract:
            vendor_info['industry'] = contract['service_category'].get('value')
        
        return vendor_info
    
    def _auto_create_alias(self, canonical_name: str, alias_name: str):
        """Auto-create vendor alias when fuzzy match succeeds"""
        if not self.database or canonical_name == alias_name:
            return
        
        try:
            vendor = self.database.get_vendor_by_name(canonical_name)
            if vendor:
                self.database.add_vendor_alias(
                    vendor_id=vendor['id'],
                    alias_name=alias_name,
                    confidence_score=0.8,  # Lower confidence for auto-generated
                    auto_generated=True
                )
        except Exception:
            # Fail silently for auto-alias creation
            pass
    
    def _clean_business_name(self, name: str) -> str:
        """Clean business name for fuzzy matching"""
        # Remove common business suffixes
        suffixes = ['inc', 'llc', 'corp', 'ltd', 'company', 'co', 'incorporated']
        name_lower = name.lower()
        
        for suffix in suffixes:
            patterns = [f' {suffix}', f' {suffix}.', f', {suffix}', f', {suffix}.']
            for pattern in patterns:
                name_lower = name_lower.replace(pattern, '')
        
        # Remove extra whitespace and punctuation
        name_lower = re.sub(r'[^\w\s]', '', name_lower)
        name_lower = re.sub(r'\s+', ' ', name_lower).strip()
        
        return name_lower
    
    def _is_contract_active(self, contract: Dict[str, Any], invoice: Dict[str, Any]) -> bool:
        """Check if contract is active for invoice date"""
        try:
            invoice_date_str = invoice.get('invoice_date', {}).get('value', '')
            contract_start_str = contract.get('start_date', {}).get('value', '')
            contract_end_str = contract.get('end_date', {}).get('value', '')
            
            if not all([invoice_date_str, contract_start_str, contract_end_str]):
                return True  # If dates missing, don't fail on this rule
            
            invoice_date = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00'))
            contract_start = datetime.fromisoformat(contract_start_str.replace('Z', '+00:00'))
            contract_end = datetime.fromisoformat(contract_end_str.replace('Z', '+00:00'))
            
            return contract_start <= invoice_date <= contract_end
        except:
            return True  # If date parsing fails, don't fail on this rule
    
    def _match_lines(self, contract: Dict[str, Any], invoice: Dict[str, Any]) -> List[Match]:
        """Match invoice lines to contract terms using priority order"""
        matches = []
        contract_terms = contract.get('terms', [])
        invoice_lines = invoice.get('lines', [])
        
        used_contract_indices = set()
        
        for inv_idx, invoice_line in enumerate(invoice_lines):
            best_match = None
            best_confidence = 0.0
            best_method = None
            
            for cont_idx, contract_term in enumerate(contract_terms):
                if cont_idx in used_contract_indices:
                    continue
                
                # Priority 1: Exact item code match
                inv_code = invoice_line.get('item_code', {}).get('value', '').strip()
                cont_code = contract_term.get('item_code', {}).get('value', '').strip()
                
                if inv_code and cont_code and inv_code.lower() == cont_code.lower():
                    best_match = cont_idx
                    best_confidence = 1.0
                    best_method = MatchMethodType.CODE
                    break
                
                # Priority 2: Description similarity
                inv_desc = invoice_line.get('item_desc', {}).get('value', '')
                cont_desc = contract_term.get('item_desc', {}).get('value', '')
                
                if inv_desc and cont_desc:
                    similarity = self._compute_description_similarity(inv_desc, cont_desc)
                    if similarity > 0.8 and similarity > best_confidence:
                        best_match = cont_idx
                        best_confidence = similarity
                        best_method = MatchMethodType.DESCRIPTION
                
                # Priority 3: Unit and price tolerance
                if not best_match or best_confidence < 0.7:
                    unit_price_match = self._check_unit_price_tolerance(invoice_line, contract_term)
                    if unit_price_match and unit_price_match > best_confidence:
                        best_match = cont_idx
                        best_confidence = unit_price_match
                        best_method = MatchMethodType.UNIT_PRICE_TOLERANCE
            
            if best_match is not None and best_confidence >= 0.6:
                matches.append(Match(
                    invoice_line_index=inv_idx,
                    contract_term_index=best_match,
                    match_method=best_method,
                    confidence=best_confidence
                ))
                used_contract_indices.add(best_match)
        
        return matches
    
    def _compute_description_similarity(self, desc1: str, desc2: str) -> float:
        """Compute cosine similarity between normalized descriptions"""
        try:
            # Normalize descriptions
            desc1_norm = self._normalize_description(desc1)
            desc2_norm = self._normalize_description(desc2)
            
            if not desc1_norm or not desc2_norm:
                return 0.0
            
            # Use TF-IDF vectorization and cosine similarity
            vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform([desc1_norm, desc2_norm])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return float(similarity)
        except:
            return 0.0
    
    def _normalize_description(self, description: str) -> str:
        """Normalize description for similarity comparison"""
        if not description:
            return ""
        
        # Convert to lowercase
        desc = description.lower()
        
        # Remove common noise words specific to invoices/contracts
        noise_words = ['service', 'services', 'fee', 'fees', 'charge', 'charges', 'monthly', 'annual']
        for word in noise_words:
            desc = re.sub(rf'\b{word}\b', '', desc)
        
        # Remove punctuation and normalize whitespace
        desc = re.sub(r'[^\w\s]', ' ', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        return desc
    
    def _check_unit_price_tolerance(self, invoice_line: Dict[str, Any], contract_term: Dict[str, Any]) -> float:
        """Check if unit price is within tolerance"""
        try:
            inv_price = invoice_line.get('unit_price', {}).get('value')
            cont_price = contract_term.get('price', {}).get('value')
            inv_unit = invoice_line.get('unit', {}).get('value', '').lower()
            cont_unit = contract_term.get('unit', {}).get('value', '').lower()
            
            if not all([inv_price, cont_price, inv_unit, cont_unit]):
                return 0.0
            
            # Units must match
            if inv_unit != cont_unit:
                return 0.0
            
            # Price tolerance of 5%
            price_diff = abs(float(inv_price) - float(cont_price))
            tolerance = 0.05 * float(cont_price)
            
            if price_diff <= tolerance:
                return 0.8  # Good confidence for price match
            
            return 0.0
        except:
            return 0.0
    
    def _validate_rules(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                       matches: List[Match]) -> List[Flag]:
        """Validate all reconciliation rules"""
        flags = []
        
        # Rule 1: Overpay per unit
        flags.extend(self._check_overpay_per_unit(contract, invoice, matches))
        
        # Rule 2: Quantity variance beyond allowed max
        flags.extend(self._check_quantity_variance(contract, invoice, matches))
        
        # Rule 3: Out of scope lines
        flags.extend(self._check_out_of_scope(contract, invoice, matches))
        
        # Rule 4: Cap exceeded
        flags.extend(self._check_cap_exceeded(contract, invoice))
        
        # Rule 5: Price escalation missing or incorrect
        flags.extend(self._check_price_escalation(contract, invoice, matches))
        
        # Rule 6: Service dates outside term
        flags.extend(self._check_service_dates(contract, invoice, matches))
        
        # Rule 7: Duplicate invoice
        flags.extend(self._check_duplicate_invoice(invoice))
        
        return flags
    
    def _check_overpay_per_unit(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                               matches: List[Match]) -> List[Flag]:
        """Check for overpayment per unit"""
        flags = []
        contract_terms = contract.get('terms', [])
        invoice_lines = invoice.get('lines', [])
        
        for match in matches:
            try:
                inv_line = invoice_lines[match.invoice_line_index]
                cont_term = contract_terms[match.contract_term_index]
                
                inv_price = float(inv_line.get('unit_price', {}).get('value', 0))
                cont_price = float(cont_term.get('price', {}).get('value', 0))
                
                if inv_price > cont_price * 1.01:  # Allow 1% tolerance for rounding
                    delta = inv_price - cont_price
                    flags.append(Flag(
                        type=FlagType.OVERPAY_PER_UNIT,
                        severity=SeverityType.ERROR,
                        summary=f"Unit price ${inv_price:.2f} exceeds contract price ${cont_price:.2f}",
                        evidence=FlagEvidence(
                            contract_price=cont_price,
                            invoice_price=inv_price,
                            delta=delta
                        )
                    ))
            except (ValueError, IndexError, KeyError):
                continue
        
        return flags
    
    def _check_quantity_variance(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                                matches: List[Match]) -> List[Flag]:
        """Check for quantity variance beyond allowed max"""
        flags = []
        contract_terms = contract.get('terms', [])
        invoice_lines = invoice.get('lines', [])
        
        for match in matches:
            try:
                inv_line = invoice_lines[match.invoice_line_index]
                cont_term = contract_terms[match.contract_term_index]
                
                inv_qty = float(inv_line.get('qty', {}).get('value', 0))
                max_qty = cont_term.get('max_qty', {}).get('value')
                
                if max_qty and inv_qty > float(max_qty):
                    flags.append(Flag(
                        type=FlagType.QUANTITY_VARIANCE,
                        severity=SeverityType.WARN,
                        summary=f"Quantity {inv_qty} exceeds maximum allowed {max_qty}",
                        evidence=FlagEvidence()
                    ))
            except (ValueError, IndexError, KeyError):
                continue
        
        return flags
    
    def _check_out_of_scope(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                           matches: List[Match]) -> List[Flag]:
        """Check for out of scope invoice lines"""
        flags = []
        invoice_lines = invoice.get('lines', [])
        matched_line_indices = {match.invoice_line_index for match in matches}
        
        for idx, line in enumerate(invoice_lines):
            if idx not in matched_line_indices:
                item_desc = line.get('item_desc', {}).get('value', 'Unknown item')
                flags.append(Flag(
                    type=FlagType.OUT_OF_SCOPE,
                    severity=SeverityType.ERROR,
                    summary=f"Invoice line '{item_desc}' not found in contract terms",
                    evidence=FlagEvidence()
                ))
        
        return flags
    
    def _check_cap_exceeded(self, contract: Dict[str, Any], invoice: Dict[str, Any]) -> List[Flag]:
        """Check if contract cap is exceeded"""
        flags = []
        cap_total = contract.get('cap_total', {}).get('value')
        
        if not cap_total:
            return flags
        
        try:
            # Calculate total invoice amount
            invoice_total = 0
            for line in invoice.get('lines', []):
                line_total = line.get('line_total', {}).get('value', 0)
                invoice_total += float(line_total) if line_total else 0
            
            # For now, just check this invoice against cap
            # In production, this would check cumulative spend
            if invoice_total > float(cap_total):
                flags.append(Flag(
                    type=FlagType.CAP_EXCEEDED,
                    severity=SeverityType.ERROR,
                    summary=f"Invoice total ${invoice_total:.2f} exceeds contract cap ${float(cap_total):.2f}",
                    evidence=FlagEvidence(
                        contract_price=float(cap_total),
                        invoice_price=invoice_total,
                        delta=invoice_total - float(cap_total)
                    )
                ))
        except (ValueError, KeyError):
            pass
        
        return flags
    
    def _check_price_escalation(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                               matches: List[Match]) -> List[Flag]:
        """Check for missing or incorrect price escalation"""
        flags = []
        escalation = contract.get('price_escalation', {}).get('value', {})
        
        if not escalation or escalation.get('type') == 'none':
            return flags
        
        # This is a simplified check - in production would need historical data
        # to compute expected escalated prices
        
        return flags
    
    def _check_service_dates(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                            matches: List[Match]) -> List[Flag]:
        """Check if service dates are within contract term"""
        flags = []
        contract_terms = contract.get('terms', [])
        invoice_lines = invoice.get('lines', [])
        
        for match in matches:
            try:
                inv_line = invoice_lines[match.invoice_line_index]
                cont_term = contract_terms[match.contract_term_index]
                
                inv_start = inv_line.get('service_period_start', {}).get('value')
                inv_end = inv_line.get('service_period_end', {}).get('value')
                cont_start = cont_term.get('effective_start', {}).get('value')
                cont_end = cont_term.get('effective_end', {}).get('value')
                
                if all([inv_start, inv_end, cont_start, cont_end]):
                    inv_start_dt = datetime.fromisoformat(inv_start.replace('Z', '+00:00'))
                    inv_end_dt = datetime.fromisoformat(inv_end.replace('Z', '+00:00'))
                    cont_start_dt = datetime.fromisoformat(cont_start.replace('Z', '+00:00'))
                    cont_end_dt = datetime.fromisoformat(cont_end.replace('Z', '+00:00'))
                    
                    if not (cont_start_dt <= inv_start_dt <= cont_end_dt and 
                           cont_start_dt <= inv_end_dt <= cont_end_dt):
                        flags.append(Flag(
                            type=FlagType.DATE_VARIANCE,
                            severity=SeverityType.WARN,
                            summary="Service period is outside contract term effective dates",
                            evidence=FlagEvidence(
                                service_dates=ServiceDates(
                                    invoice_start=inv_start,
                                    invoice_end=inv_end,
                                    contract_start=cont_start,
                                    contract_end=cont_end
                                )
                            )
                        ))
            except (ValueError, IndexError, KeyError):
                continue
        
        return flags
    
    def _check_duplicate_invoice(self, invoice: Dict[str, Any]) -> List[Flag]:
        """Check for duplicate invoices"""
        flags = []
        vendor = invoice.get('vendor', {}).get('value', '')
        invoice_no = invoice.get('invoice_no', {}).get('value', '')
        invoice_date = invoice.get('invoice_date', {}).get('value', '')
        
        # Calculate total amount
        total_amount = 0
        try:
            for line in invoice.get('lines', []):
                line_total = line.get('line_total', {}).get('value', 0)
                total_amount += float(line_total) if line_total else 0
        except (ValueError, KeyError):
            total_amount = 0
        
        # Check against processed invoices
        invoice_key = f"{vendor}_{invoice_no}_{total_amount:.2f}"
        
        for processed in self.processed_invoices:
            if processed == invoice_key:
                flags.append(Flag(
                    type=FlagType.DUPLICATE_INVOICE,
                    severity=SeverityType.ERROR,
                    summary=f"Duplicate invoice detected: {invoice_no} from {vendor}",
                    evidence=FlagEvidence()
                ))
                break
        
        # Add to processed list
        self.processed_invoices.append(invoice_key)
        
        return flags
    
    def _generate_payment_preview(self, contract: Dict[str, Any], invoice: Dict[str, Any], 
                                 matches: List[Match]) -> NextPaymentPreview:
        """Generate next payment preview based on contract terms"""
        try:
            # Calculate next period dates (simplified - assume monthly billing)
            invoice_date_str = invoice.get('invoice_date', {}).get('value', '')
            if invoice_date_str:
                current_date = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00'))
                next_period_start = current_date + timedelta(days=30)
                next_period_end = next_period_start + timedelta(days=30)
            else:
                next_period_start = datetime.now()
                next_period_end = next_period_start + timedelta(days=30)
            
            # Generate expected items based on matches
            items = []
            subtotal = 0
            contract_terms = contract.get('terms', [])
            
            for match in matches:
                try:
                    cont_term = contract_terms[match.contract_term_index]
                    item_code = cont_term.get('item_code', {}).get('value', '')
                    price = float(cont_term.get('price', {}).get('value', 0))
                    # Assume same quantity as current invoice for simplicity
                    qty = 1  # Could be derived from historical patterns
                    
                    item_total = price * qty
                    subtotal += item_total
                    
                    items.append(PaymentItem(
                        item_code=item_code,
                        expected_qty=qty,
                        expected_unit_price=price,
                        expected_total=item_total
                    ))
                except (ValueError, IndexError, KeyError):
                    continue
            
            # Calculate taxes (simplified - assume 10%)
            taxes = subtotal * 0.1
            total = subtotal + taxes
            
            return NextPaymentPreview(
                period_start=next_period_start.strftime('%Y-%m-%d'),
                period_end=next_period_end.strftime('%Y-%m-%d'),
                items=items,
                subtotal=subtotal,
                taxes=taxes,
                total=total,
                assumptions=[
                    "Based on current contract terms",
                    "Assumes monthly billing cycle",
                    "Estimated 10% tax rate",
                    "Quantities based on historical patterns"
                ]
            )
        except Exception:
            return NextPaymentPreview()
    
    def add_vendor_alias(self, primary_name: str, aliases: List[str]):
        """Add vendor name aliases for better matching"""
        self.vendor_aliases[primary_name.lower()] = [alias.lower() for alias in aliases]