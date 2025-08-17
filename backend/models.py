"""
Database models for Invoice Reconciliation Platform
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON, Boolean, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid
import os

Base = declarative_base()

class Vendor(Base):
    """Vendor model for storing vendor information"""
    __tablename__ = 'vendors'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    business_type = Column(String(100))
    tax_id = Column(String(50))
    address = Column(Text)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    status = Column(String(50), default='active')  # active, inactive, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)  # Store additional vendor info
    
    # Relationships
    contracts = relationship("Contract", back_populates="vendor", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="vendor", cascade="all, delete-orphan")
    reconciliations = relationship("Reconciliation", back_populates="vendor")


class Contract(Base):
    """Contract model for storing contract details"""
    __tablename__ = 'contracts'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id = Column(String(36), ForeignKey('vendors.id'), nullable=False)
    contract_number = Column(String(100), unique=True)
    title = Column(String(255))
    description = Column(Text)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    total_value = Column(Float)
    payment_terms = Column(String(255))
    billing_frequency = Column(String(50))  # monthly, quarterly, annual, one-time
    status = Column(String(50), default='active')  # draft, active, expired, terminated
    
    # Document storage
    original_file_path = Column(String(500))
    extracted_text = Column(Text)
    ai_analysis = Column(JSON)  # Store AI extracted details
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="contracts")
    line_items = relationship("ContractLineItem", back_populates="contract", cascade="all, delete-orphan")
    reconciliations = relationship("Reconciliation", back_populates="contract")


class ContractLineItem(Base):
    """Line items within a contract"""
    __tablename__ = 'contract_line_items'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String(36), ForeignKey('contracts.id'), nullable=False)
    item_code = Column(String(50))
    description = Column(Text)
    quantity = Column(Float)
    unit_price = Column(Float)
    total_price = Column(Float)
    
    # Relationships
    contract = relationship("Contract", back_populates="line_items")


class Invoice(Base):
    """Invoice model for storing invoice details"""
    __tablename__ = 'invoices'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id = Column(String(36), ForeignKey('vendors.id'), nullable=False)
    invoice_number = Column(String(100), unique=True)
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    payment_date = Column(DateTime)
    subtotal = Column(Float)
    tax_amount = Column(Float)
    total_amount = Column(Float)
    status = Column(String(50), default='pending')  # pending, paid, overdue, cancelled
    reference_contract_number = Column(String(100))
    
    # Document storage
    original_file_path = Column(String(500))
    extracted_text = Column(Text)
    ai_analysis = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    reconciliations = relationship("Reconciliation", back_populates="invoice")


class InvoiceLineItem(Base):
    """Line items within an invoice"""
    __tablename__ = 'invoice_line_items'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey('invoices.id'), nullable=False)
    item_code = Column(String(50))
    description = Column(Text)
    quantity = Column(Float)
    unit_price = Column(Float)
    total_price = Column(Float)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")


class Reconciliation(Base):
    """Reconciliation records between contracts and invoices"""
    __tablename__ = 'reconciliations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id = Column(String(36), ForeignKey('vendors.id'))
    contract_id = Column(String(36), ForeignKey('contracts.id'))
    invoice_id = Column(String(36), ForeignKey('invoices.id'))
    
    status = Column(String(50))  # passed, failed, warning, pending
    discrepancy_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    match_count = Column(Integer, default=0)
    
    # Detailed results
    discrepancies = Column(JSON)
    warnings = Column(JSON)
    matches = Column(JSON)
    summary = Column(JSON)
    
    performed_at = Column(DateTime, default=datetime.utcnow)
    performed_by = Column(String(255))  # User who initiated
    
    # Relationships
    vendor = relationship("Vendor", back_populates="reconciliations")
    contract = relationship("Contract", back_populates="reconciliations")
    invoice = relationship("Invoice", back_populates="reconciliations")


class ReconciliationSession(Base):
    """Temporary session for file uploads and processing"""
    __tablename__ = 'reconciliation_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_file_path = Column(String(500))
    invoice_file_path = Column(String(500))
    status = Column(String(50), default='uploaded')  # uploaded, processing, completed, error
    error_message = Column(Text)
    results = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Auto-cleanup old sessions


class AuditLog(Base):
    """Audit trail for all system activities"""
    __tablename__ = 'audit_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50))  # vendor, contract, invoice, reconciliation
    entity_id = Column(String(36))
    action = Column(String(50))  # create, update, delete, reconcile
    changes = Column(JSON)
    performed_by = Column(String(255))
    performed_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))


# Database initialization
def init_db(database_url=None):
    """Initialize the database"""
    if not database_url:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///reconciliation.db')
    
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()


def get_session():
    """Get database session"""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///reconciliation.db')
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)
    return Session()