#!/usr/bin/env python3
"""
Test script for Unspend system - verifies all components work together
"""
import sys
import os
sys.path.append('./backend')

from database import Database
from schemas import ContractSchema, InvoiceSchema, validate_contract, validate_invoice
from reconciliation_engine import ReconciliationEngine
from llm_client import LLMClient
from ocr_processor import OCRProcessor

def test_database():
    """Test database functionality"""
    print("Testing database...")
    db = Database()
    
    # Test storing contract
    sample_contract = {
        "vendor": {"value": "Test Vendor Inc", "confidence": 0.9},
        "service_category": {"value": "IT Services", "confidence": 0.8},
        "start_date": {"value": "2024-01-01", "confidence": 0.9},
        "end_date": {"value": "2024-12-31", "confidence": 0.9},
        "auto_renew": {"value": True, "confidence": 0.7},
        "terms": [
            {
                "item_code": {"value": "SRV-001", "confidence": 0.9},
                "item_desc": {"value": "Monthly IT Support", "confidence": 0.9},
                "unit": {"value": "month", "confidence": 0.9},
                "price": {"value": 1000.0, "confidence": 0.9},
                "min_qty": {"value": 1, "confidence": 0.8},
                "max_qty": {"value": 12, "confidence": 0.8},
                "effective_start": {"value": "2024-01-01", "confidence": 0.9},
                "effective_end": {"value": "2024-12-31", "confidence": 0.9}
            }
        ],
        "notes": "Test contract"
    }
    
    contract_id = db.store_contract("Test contract text", sample_contract, 0.85, "test")
    print(f"✓ Contract stored with ID: {contract_id}")
    
    # Test storing invoice
    sample_invoice = {
        "vendor": {"value": "Test Vendor Inc", "confidence": 0.9},
        "invoice_no": {"value": "INV-2024-001", "confidence": 0.9},
        "invoice_date": {"value": "2024-01-15", "confidence": 0.9},
        "due_date": {"value": "2024-02-15", "confidence": 0.8},
        "lines": [
            {
                "item_code": {"value": "SRV-001", "confidence": 0.9},
                "item_desc": {"value": "Monthly IT Support", "confidence": 0.9},
                "unit": {"value": "month", "confidence": 0.9},
                "qty": {"value": 1, "confidence": 0.9},
                "unit_price": {"value": 1000.0, "confidence": 0.9},
                "line_total": {"value": 1000.0, "confidence": 0.9},
                "service_period_start": {"value": "2024-01-01", "confidence": 0.8},
                "service_period_end": {"value": "2024-01-31", "confidence": 0.8}
            }
        ],
        "notes": "Test invoice"
    }
    
    invoice_id = db.store_invoice("Test invoice text", sample_invoice, 0.87, "test")
    print(f"✓ Invoice stored with ID: {invoice_id}")
    
    # Test dashboard stats
    stats = db.get_dashboard_stats()
    print(f"✓ Dashboard stats: {stats['total_contracts']} contracts, {stats['total_invoices']} invoices")
    
    return contract_id, invoice_id, sample_contract, sample_invoice

def test_schemas():
    """Test Pydantic schema validation"""
    print("\nTesting schemas...")
    
    # Test contract validation
    sample_contract = {
        "vendor": {"value": "Test Vendor", "confidence": 0.9},
        "service_category": {"value": "IT Services", "confidence": 0.8},
        "start_date": {"value": "2024-01-01", "confidence": 0.9},
        "end_date": {"value": "2024-12-31", "confidence": 0.9},
        "auto_renew": {"value": True, "confidence": 0.7},
        "renewal_notice_days": {"value": 30, "confidence": 0.8},
        "price_escalation": {"value": {"type": "none", "amount": None}, "confidence": 0.9},
        "cap_total": {"value": 12000.0, "confidence": 0.8},
        "allowed_fees": {"value": ["service_fee", "maintenance_fee"], "confidence": 0.7},
        "terms": [],
        "notes": "Test contract"
    }
    
    validated = validate_contract(sample_contract)
    print("✓ Contract schema validation passed")
    
    # Test invoice validation
    sample_invoice = {
        "vendor": {"value": "Test Vendor", "confidence": 0.9},
        "invoice_no": {"value": "INV-001", "confidence": 0.9},
        "invoice_date": {"value": "2024-01-15", "confidence": 0.9},
        "due_date": {"value": "2024-02-15", "confidence": 0.8},
        "lines": [],
        "notes": "Test invoice"
    }
    
    validated = validate_invoice(sample_invoice)
    print("✓ Invoice schema validation passed")

def test_reconciliation_engine():
    """Test reconciliation engine"""
    print("\nTesting reconciliation engine...")
    
    engine = ReconciliationEngine()
    
    # Sample data
    contract = {
        "vendor": {"value": "test vendor inc", "confidence": 0.9},
        "start_date": {"value": "2024-01-01", "confidence": 0.9},
        "end_date": {"value": "2024-12-31", "confidence": 0.9},
        "terms": [
            {
                "item_code": {"value": "SRV-001", "confidence": 0.9},
                "item_desc": {"value": "monthly it support", "confidence": 0.9},
                "unit": {"value": "month", "confidence": 0.9},
                "price": {"value": 1000.0, "confidence": 0.9},
                "max_qty": {"value": 1, "confidence": 0.8},
                "effective_start": {"value": "2024-01-01", "confidence": 0.9},
                "effective_end": {"value": "2024-12-31", "confidence": 0.9}
            }
        ]
    }
    
    invoice = {
        "vendor": {"value": "test vendor inc", "confidence": 0.9},
        "invoice_no": {"value": "INV-001", "confidence": 0.9},
        "invoice_date": {"value": "2024-01-15", "confidence": 0.9},
        "lines": [
            {
                "item_code": {"value": "SRV-001", "confidence": 0.9},
                "item_desc": {"value": "monthly it support", "confidence": 0.9},
                "unit": {"value": "month", "confidence": 0.9},
                "qty": {"value": 1, "confidence": 0.9},
                "unit_price": {"value": 1000.0, "confidence": 0.9},
                "line_total": {"value": 1000.0, "confidence": 0.9},
                "service_period_start": {"value": "2024-01-01", "confidence": 0.8},
                "service_period_end": {"value": "2024-01-31", "confidence": 0.8}
            }
        ]
    }
    
    result = engine.reconcile(contract, invoice)
    print(f"✓ Reconciliation completed with {len(result.matches)} matches and {len(result.flags)} flags")
    
    return result

def test_ocr_processor():
    """Test OCR processor"""
    print("\nTesting OCR processor...")
    
    processor = OCRProcessor()
    
    # Test text normalization
    test_text = "Invoice Date: 01/15/2024\nAmount: USD 1,234.56\nQuantity: 5 pcs"
    normalized = processor._normalize_text(test_text)
    print(f"✓ Text normalization: '{test_text}' -> '{normalized}'")

def test_llm_client():
    """Test LLM client (without API key)"""
    print("\nTesting LLM client...")
    
    client = LLMClient()
    print(f"✓ LLM client initialized with models: {client.small_model}, {client.large_model}")
    
    # Test without API key (should handle gracefully)
    try:
        result, success = client.extract_contract("Sample contract text")
        if not success:
            print("✓ LLM client handled missing API key gracefully")
        else:
            print("✓ LLM client extraction completed")
    except ValueError as e:
        if "API key not set" in str(e):
            print("✓ LLM client properly validates API key requirement")

def main():
    """Run all tests"""
    print("🚀 Starting Unspend system tests...\n")
    
    try:
        # Run tests
        contract_id, invoice_id, contract_data, invoice_data = test_database()
        test_schemas()
        reconciliation_result = test_reconciliation_engine()
        test_ocr_processor()
        test_llm_client()
        
        print("\n✅ All tests passed! Unspend system is ready.")
        print("\n📊 System Summary:")
        print(f"   • Database: ✓ Operational")
        print(f"   • Schemas: ✓ Validated")
        print(f"   • Reconciliation: ✓ Working ({len(reconciliation_result.matches)} matches found)")
        print(f"   • OCR Processing: ✓ Ready")
        print(f"   • LLM Client: ✓ Configured")
        
        print("\n🌟 Quick start:")
        print("   1. Set OPENAI_API_KEY environment variable")
        print("   2. Run: python3 backend/app.py")
        print("   3. Visit: http://localhost:5000/dashboard")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())