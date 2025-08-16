# Unspend - AI-Powered Invoice Reconciliation Platform

**Contract and invoice reconciliation for nursing homes and healthcare organizations**

Cut waste. Keep the signal.

## 🎯 Overview

Unspend is a production-ready invoice reconciliation platform that automatically processes contracts and invoices, extracts structured data, reconciles invoice lines to contract terms, flags issues with evidence, and provides insights into upcoming spend and renewals through a clean dashboard.

### Key Features

- **🤖 Tiered LLM Architecture**: Small models for extraction, large models for complex reconciliation
- **📊 Deterministic Reconciliation**: Rules-based matching before expensive LLM calls
- **🎯 Strict JSON Schemas**: Pydantic validation with confidence scoring
- **💾 Smart Caching**: Database-backed LLM response caching
- **📈 Quality Gates**: Automatic flagging of low-confidence extractions
- **🔍 Audit Trails**: Complete processing history and changes
- **⚡ Modern UI**: Real-time dashboard with drag-and-drop upload

## 🏗️ Architecture

### LLM Routing Strategy
- **Small Model** (gpt-4o-mini): First-pass extraction with auto-escalation
- **Large Model** (gpt-4o): Complex reconciliation and low-confidence cases
- **Temperature 0**: For extraction consistency
- **Temperature 0.2**: For reconciliation review creativity

### Processing Pipeline
1. **Document Upload** → OCR/Text Extraction → Normalization
2. **Small Model Extraction** → Confidence Check → Escalation (if needed)
3. **Deterministic Matching** → Rule Validation → Flag Generation
4. **LLM Review** (if flags present) → Final Results
5. **Database Storage** → Audit Trail → Dashboard Update

### Reconciliation Rules
- Vendor exact match + alias table
- Contract date validation
- Line matching: exact code → description similarity → unit/price tolerance
- Overpay detection, quantity variance, out-of-scope items
- Cap exceeded, price escalation, service date validation
- Duplicate invoice detection

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key
- Tesseract OCR (for image processing)

### Installation

1. **Clone and setup**:
```bash
git checkout yomi-development
cd invoice-reconciliation-platform
pip install -r requirements.txt
```

2. **Set environment variables**:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

3. **Test the system**:
```bash
python3 test_system.py
```

4. **Start the application**:
```bash
python3 backend/app.py
```

5. **Access the dashboard**:
```
http://localhost:5000/dashboard
```

## 📡 API Endpoints

### Core Processing
- `POST /api/contracts` - Upload and extract contract data
- `POST /api/invoices` - Upload and extract invoice data  
- `POST /api/reconcile` - Run reconciliation between contract and invoice
- `GET /api/dashboard` - Get dashboard statistics and recent activity

### Quality & Monitoring
- `GET /api/quality/review` - Get low-confidence extractions for review
- `PUT /api/quality/update/{type}/{id}` - Update extraction after human review
- `GET /api/audit/trail` - Get audit trail with filtering
- `GET /api/cache/stats` - Get LLM cache performance statistics
- `POST /api/cache/cleanup` - Clean up old cache entries

### Legacy Support
- `POST /api/upload` - Legacy upload both files
- `POST /api/process/{session_id}` - Legacy processing endpoint

## 📋 Data Schemas

### Contract Schema
```json
{
  "vendor": {"value": "Acme Corp", "confidence": 0.95},
  "service_category": {"value": "IT Services", "confidence": 0.90},
  "start_date": {"value": "2024-01-01", "confidence": 0.95},
  "end_date": {"value": "2024-12-31", "confidence": 0.95},
  "auto_renew": {"value": true, "confidence": 0.80},
  "renewal_notice_days": {"value": 30, "confidence": 0.75},
  "price_escalation": {"value": {"type": "fixed_pct", "amount": 3.0}, "confidence": 0.85},
  "cap_total": {"value": 50000.0, "confidence": 0.90},
  "allowed_fees": {"value": ["service_fee"], "confidence": 0.80},
  "terms": [
    {
      "item_code": {"value": "SRV-001", "confidence": 0.95},
      "item_desc": {"value": "Monthly IT Support", "confidence": 0.90},
      "unit": {"value": "month", "confidence": 0.95},
      "price": {"value": 1000.0, "confidence": 0.95},
      "min_qty": {"value": 1, "confidence": 0.80},
      "max_qty": {"value": 12, "confidence": 0.80},
      "effective_start": {"value": "2024-01-01", "confidence": 0.90},
      "effective_end": {"value": "2024-12-31", "confidence": 0.90}
    }
  ],
  "notes": "Additional contract details"
}
```

### Invoice Schema
```json
{
  "vendor": {"value": "Acme Corp", "confidence": 0.95},
  "invoice_no": {"value": "INV-2024-001", "confidence": 0.98},
  "invoice_date": {"value": "2024-01-15", "confidence": 0.95},
  "due_date": {"value": "2024-02-15", "confidence": 0.90},
  "lines": [
    {
      "item_code": {"value": "SRV-001", "confidence": 0.95},
      "item_desc": {"value": "Monthly IT Support", "confidence": 0.90},
      "unit": {"value": "month", "confidence": 0.95},
      "qty": {"value": 1, "confidence": 0.98},
      "unit_price": {"value": 1000.0, "confidence": 0.98},
      "line_total": {"value": 1000.0, "confidence": 0.98},
      "service_period_start": {"value": "2024-01-01", "confidence": 0.85},
      "service_period_end": {"value": "2024-01-31", "confidence": 0.85}
    }
  ],
  "notes": "Additional invoice details"
}
```

### Reconciliation Result Schema
```json
{
  "matches": [
    {
      "invoice_line_index": 0,
      "contract_term_index": 0,
      "match_method": "code",
      "confidence": 1.0
    }
  ],
  "flags": [
    {
      "type": "overpay_per_unit",
      "severity": "error",
      "summary": "Unit price $1050.00 exceeds contract price $1000.00",
      "evidence": {
        "contract_price": 1000.0,
        "invoice_price": 1050.0,
        "delta": 50.0,
        "clause_reference": "Section 3.1",
        "service_dates": {
          "invoice_start": "2024-01-01",
          "invoice_end": "2024-01-31",
          "contract_start": "2024-01-01",
          "contract_end": "2024-12-31"
        }
      }
    }
  ],
  "next_payment_preview": {
    "period_start": "2024-02-01",
    "period_end": "2024-02-29",
    "items": [
      {
        "item_code": "SRV-001",
        "expected_qty": 1,
        "expected_unit_price": 1000.0,
        "expected_total": 1000.0
      }
    ],
    "subtotal": 1000.0,
    "taxes": 100.0,
    "total": 1100.0,
    "assumptions": ["Based on current contract terms", "Assumes monthly billing cycle"]
  }
}
```

## 🎨 Dashboard Features

### Main Dashboard (`/dashboard`)
- **Real-time Stats**: Contracts, invoices, reconciliations, exceptions
- **Recent Flags**: Latest reconciliation issues requiring attention
- **Low Confidence**: Extractions needing human review
- **Drag & Drop Upload**: Process documents instantly
- **Auto-refresh**: Updates every 30 seconds

### Quality Gates
- Confidence threshold: 0.7 (configurable)
- Automatic escalation for low-confidence extractions
- Math validation for invoice line totals
- Required field validation

### Caching Strategy
- Database-backed LLM response cache (7-day retention)
- Text hash-based document deduplication
- In-memory fallback cache
- Cache hit rate monitoring

## 🔧 Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your-openai-api-key

# Optional
UPLOAD_FOLDER=uploads
PROCESSED_FOLDER=processed
MAX_FILE_SIZE=10485760
```

### Database
- SQLite by default (`unspend.db`)
- Configurable via `Database()` constructor
- Auto-migration on startup

### Models
- Small: `gpt-4o-mini` (configurable in `LLMClient`)
- Large: `gpt-4o` (configurable in `LLMClient`)

## 🧪 Testing

Run the comprehensive test suite:
```bash
python3 test_system.py
```

Tests validate:
- ✅ Database operations and schema creation
- ✅ Pydantic schema validation
- ✅ Reconciliation engine logic
- ✅ OCR text normalization
- ✅ LLM client configuration

## 📁 Project Structure

```
invoice-reconciliation-platform/
├── backend/
│   ├── app.py                 # Flask application
│   ├── llm_client.py         # Tiered LLM routing
│   ├── reconciliation_engine.py # Deterministic rules
│   ├── database.py           # SQLite persistence
│   ├── schemas.py            # Pydantic validation
│   ├── ocr_processor.py      # Document processing
│   └── ai_analyzer.py        # Legacy analyzer
├── frontend/
│   ├── dashboard.html        # Modern dashboard UI
│   └── index.html           # Original UI
├── requirements.txt          # Python dependencies
├── test_system.py           # Comprehensive tests
└── UNSPEND_README.md        # This documentation
```

## 🚀 Production Deployment

### Performance Considerations
- Use Redis for LLM response caching in production
- Configure PostgreSQL for enterprise database needs
- Implement rate limiting for API endpoints
- Set up monitoring with OpenTelemetry

### Security Best Practices
- Store API keys in secure vaults (not environment variables)
- Implement proper authentication and authorization
- Enable HTTPS/TLS for all endpoints
- Regular security audits and dependency updates

### Scaling
- Horizontal scaling with load balancers
- Separate background processing for large documents
- Queue-based processing for high volume
- CDN for frontend assets

## 📊 Monitoring & Analytics

### Key Metrics
- **Processing Volume**: Documents per day/hour
- **Accuracy Rates**: Confidence score distributions
- **Flag Types**: Most common reconciliation issues
- **Performance**: Processing time per document
- **Cache Efficiency**: Hit rates and response times

### Alerts
- Low confidence extraction spikes
- Processing failures
- High error flag rates
- Performance degradation

## 🤝 Contributing

1. Work on feature branches from `yomi-development`
2. Follow the existing code style and patterns
3. Add tests for new functionality
4. Update documentation as needed
5. Create pull requests for review

## 📜 License

MIT License - see LICENSE file for details

## 🆘 Support

For questions or issues:
1. Check the test suite: `python3 test_system.py`
2. Review the dashboard for system status
3. Check API endpoints manually
4. Review audit trails for processing history

---

**Built with ❤️ for healthcare organizations fighting invoice reconciliation complexity.**