"""
Pydantic schemas for Unspend - Strict validation for LLM outputs
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from enum import Enum

class ConfidenceField(BaseModel):
    """Base field with confidence scoring"""
    value: Optional[Union[str, int, float, bool, Dict[str, Any]]] = None
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")

class PriceEscalationType(str, Enum):
    FIXED_PCT = "fixed_pct"
    CPI = "cpi"
    NONE = "none"

class PriceEscalation(BaseModel):
    type: PriceEscalationType
    amount: Optional[float] = None

class ContractTerm(BaseModel):
    item_code: ConfidenceField
    item_desc: ConfidenceField
    unit: ConfidenceField
    price: ConfidenceField
    min_qty: ConfidenceField
    max_qty: ConfidenceField
    effective_start: ConfidenceField
    effective_end: ConfidenceField

class ContractSchema(BaseModel):
    vendor: ConfidenceField
    service_category: ConfidenceField
    start_date: ConfidenceField
    end_date: ConfidenceField
    auto_renew: ConfidenceField
    renewal_notice_days: ConfidenceField
    price_escalation: ConfidenceField
    cap_total: ConfidenceField
    allowed_fees: ConfidenceField
    terms: List[ContractTerm] = []
    notes: str = ""

    @validator('terms')
    def validate_terms(cls, v):
        if not isinstance(v, list):
            return []
        return v

class InvoiceLine(BaseModel):
    item_code: ConfidenceField
    item_desc: ConfidenceField
    unit: ConfidenceField
    qty: ConfidenceField
    unit_price: ConfidenceField
    line_total: ConfidenceField
    service_period_start: ConfidenceField
    service_period_end: ConfidenceField

class InvoiceSchema(BaseModel):
    vendor: ConfidenceField
    invoice_no: ConfidenceField
    invoice_date: ConfidenceField
    due_date: ConfidenceField
    lines: List[InvoiceLine] = []
    notes: str = ""

    @validator('lines')
    def validate_lines(cls, v):
        if not isinstance(v, list):
            return []
        return v

class MatchMethodType(str, Enum):
    CODE = "code"
    DESCRIPTION = "description"
    UNIT_PRICE_TOLERANCE = "unit_price_tolerance"

class Match(BaseModel):
    invoice_line_index: int
    contract_term_index: int
    match_method: MatchMethodType
    confidence: float = Field(ge=0.0, le=1.0)

class FlagType(str, Enum):
    OVERPAY_PER_UNIT = "overpay_per_unit"
    QUANTITY_VARIANCE = "quantity_variance"
    OUT_OF_SCOPE = "out_of_scope"
    CAP_EXCEEDED = "cap_exceeded"
    DATE_VARIANCE = "date_variance"
    ESCALATION_ERROR = "escalation_error"
    DUPLICATE_INVOICE = "duplicate_invoice"

class SeverityType(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

class ServiceDates(BaseModel):
    invoice_start: str = ""
    invoice_end: str = ""
    contract_start: str = ""
    contract_end: str = ""

class FlagEvidence(BaseModel):
    contract_price: Optional[float] = None
    invoice_price: Optional[float] = None
    delta: Optional[float] = None
    clause_reference: str = ""
    service_dates: ServiceDates = ServiceDates()

class Flag(BaseModel):
    type: FlagType
    severity: SeverityType
    summary: str
    evidence: FlagEvidence

class PaymentItem(BaseModel):
    item_code: str
    expected_qty: Optional[float] = None
    expected_unit_price: Optional[float] = None
    expected_total: Optional[float] = None

class NextPaymentPreview(BaseModel):
    period_start: str = ""
    period_end: str = ""
    items: List[PaymentItem] = []
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    total: Optional[float] = None
    assumptions: List[str] = []

class ReconciliationResult(BaseModel):
    matches: List[Match] = []
    flags: List[Flag] = []
    next_payment_preview: NextPaymentPreview = NextPaymentPreview()

    class Config:
        # Allow extra fields for future extensibility
        extra = "allow"

# Validation helpers
def validate_contract(data: Dict[str, Any]) -> ContractSchema:
    """Validate contract data against schema"""
    try:
        return ContractSchema(**data)
    except Exception as e:
        raise ValueError(f"Contract validation failed: {str(e)}")

def validate_invoice(data: Dict[str, Any]) -> InvoiceSchema:
    """Validate invoice data against schema"""
    try:
        return InvoiceSchema(**data)
    except Exception as e:
        raise ValueError(f"Invoice validation failed: {str(e)}")

def validate_reconciliation(data: Dict[str, Any]) -> ReconciliationResult:
    """Validate reconciliation result against schema"""
    try:
        return ReconciliationResult(**data)
    except Exception as e:
        raise ValueError(f"Reconciliation validation failed: {str(e)}")