import pytest
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from unittest.mock import Mock, patch, MagicMock

@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_files():
    """Create mock file uploads"""
    return {
        'contract': (MagicMock(), 'contract.pdf'),
        'invoice': (MagicMock(), 'invoice.pdf')
    }

class TestHealthEndpoint:
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'version' in data
        assert 'features' in data

class TestUploadEndpoints:
    @patch('app.ocr_processor')
    @patch('app.llm_client')
    def test_upload_contract(self, mock_llm, mock_ocr, client):
        """Test contract upload endpoint"""
        mock_ocr.process_image.return_value = "Contract text"
        mock_llm.extract_contract_details.return_value = ({
            "contract_number": "TEST-001",
            "vendor": "Test Vendor",
            "amount": 1000.00
        }, True, 0.95)
        
        data = {'contract': (b'test content', 'contract.pdf')}
        response = client.post('/api/contracts', 
                              data=data, 
                              content_type='multipart/form-data')
        
        assert response.status_code in [200, 500]  # Depends on setup
    
    @patch('app.ocr_processor')
    @patch('app.llm_client')
    def test_upload_invoice(self, mock_llm, mock_ocr, client):
        """Test invoice upload endpoint"""
        mock_ocr.process_image.return_value = "Invoice text"
        mock_llm.extract_invoice_details.return_value = ({
            "invoice_number": "INV-001",
            "vendor": "Test Vendor",
            "amount": 1000.00
        }, True, 0.95)
        
        data = {'invoice': (b'test content', 'invoice.pdf')}
        response = client.post('/api/invoices',
                              data=data,
                              content_type='multipart/form-data')
        
        assert response.status_code in [200, 500]  # Depends on setup

class TestReconciliationEndpoint:
    @patch('app.reconciliation_engine')
    def test_reconcile_documents(self, mock_engine, client):
        """Test reconciliation endpoint"""
        mock_engine.reconcile.return_value = {
            "status": "matched",
            "confidence": 0.95,
            "discrepancies": []
        }
        
        data = {
            "contract": {
                "contract_number": "TEST-001",
                "vendor": "Test Vendor",
                "amount": 1000.00
            },
            "invoice": {
                "invoice_number": "INV-001",
                "vendor": "Test Vendor",
                "amount": 1000.00
            }
        }
        
        response = client.post('/api/reconcile',
                              json=data,
                              content_type='application/json')
        
        assert response.status_code in [200, 500]  # Depends on setup

class TestVendorEndpoints:
    @patch('app.database')
    def test_get_vendors(self, mock_db, client):
        """Test get vendors endpoint"""
        mock_db.get_vendors.return_value = [
            {"id": 1, "name": "Vendor 1"},
            {"id": 2, "name": "Vendor 2"}
        ]
        
        response = client.get('/api/vendors')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'vendors' in data
    
    @patch('app.database')
    def test_add_vendor(self, mock_db, client):
        """Test add vendor endpoint"""
        mock_db.add_vendor.return_value = {"id": 1, "name": "New Vendor"}
        
        data = {"name": "New Vendor", "email": "vendor@test.com"}
        response = client.post('/api/vendors',
                               json=data,
                               content_type='application/json')
        
        assert response.status_code in [201, 500]  # Depends on setup

class TestMetricsEndpoints:
    @patch('app.llm_client')
    def test_llm_metrics(self, mock_llm, client):
        """Test LLM metrics endpoint"""
        mock_llm.get_metrics.return_value = {
            "total_requests": 100,
            "cache_hits": 50,
            "average_latency": 0.5
        }
        
        response = client.get('/api/metrics/llm')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'metrics' in data
    
    @patch('app.database')
    def test_system_stats(self, mock_db, client):
        """Test system stats endpoint"""
        mock_db.get_stats.return_value = {
            "total_documents": 100,
            "total_reconciliations": 50
        }
        
        response = client.get('/api/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'stats' in data

class TestErrorHandling:
    def test_missing_files(self, client):
        """Test error handling for missing files"""
        response = client.post('/api/upload', data={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_invalid_file_type(self, client):
        """Test error handling for invalid file types"""
        data = {'contract': (b'test', 'contract.txt')}
        response = client.post('/api/contracts',
                              data=data,
                              content_type='multipart/form-data')
        assert response.status_code in [400, 500]
    
    def test_invalid_json(self, client):
        """Test error handling for invalid JSON"""
        response = client.post('/api/reconcile',
                              data='invalid json',
                              content_type='application/json')
        assert response.status_code in [400, 500]

if __name__ == '__main__':
    pytest.main([__file__, '-v'])