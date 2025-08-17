"""
REST API endpoints for Invoice Reconciliation Platform
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_restful import Api, Resource
from werkzeug.utils import secure_filename
from marshmallow import Schema, fields, ValidationError
import os
import uuid
import logging
from datetime import datetime
from functools import wraps

from services import (
    VendorService, ContractService, InvoiceService, ReconciliationService
)
from models import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
api = Api(app)

# Configuration
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 10485760))
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx'}

# Initialize database
init_db()

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ========== Validation Schemas ==========

class VendorSchema(Schema):
    """Schema for vendor validation"""
    name = fields.Str(required=True)
    legal_name = fields.Str()
    business_type = fields.Str()
    tax_id = fields.Str()
    address = fields.Str()
    contact_email = fields.Email()
    contact_phone = fields.Str()
    metadata = fields.Dict()


class ContractUploadSchema(Schema):
    """Schema for contract upload validation"""
    vendor_id = fields.Str()
    contract_number = fields.Str()
    title = fields.Str()


class InvoiceUploadSchema(Schema):
    """Schema for invoice upload validation"""
    vendor_id = fields.Str()
    invoice_number = fields.Str()


class ReconciliationSchema(Schema):
    """Schema for reconciliation request"""
    contract_id = fields.Str(required=True)
    invoice_id = fields.Str(required=True)


# ========== Utility Functions ==========

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def handle_errors(f):
    """Decorator to handle errors in API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            return {'error': 'Validation error', 'details': e.messages}, 400
        except Exception as e:
            logger.error(f"API error: {str(e)}")
            return {'error': 'Internal server error', 'message': str(e)}, 500
    return decorated_function


# ========== API Resources ==========

class HealthResource(Resource):
    """Health check endpoint"""
    def get(self):
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0'
        }


class VendorListResource(Resource):
    """Vendor list and creation"""
    
    @handle_errors
    def get(self):
        """Get list of vendors"""
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        search = request.args.get('search')
        
        vendor_service = VendorService()
        
        if search:
            vendors = vendor_service.search_vendors(search)
        else:
            vendors = vendor_service.list_vendors(active_only)
        
        return {
            'vendors': vendors,
            'count': len(vendors)
        }
    
    @handle_errors
    def post(self):
        """Create a new vendor"""
        schema = VendorSchema()
        vendor_data = schema.load(request.json)
        
        vendor_service = VendorService()
        result = vendor_service.create_vendor(
            vendor_data,
            created_by=request.headers.get('X-User-Id', 'api')
        )
        
        if result['success']:
            return result['vendor'], 201
        else:
            return {'error': result['message']}, 400


class VendorResource(Resource):
    """Individual vendor operations"""
    
    @handle_errors
    def get(self, vendor_id):
        """Get vendor details"""
        vendor_service = VendorService()
        vendor = vendor_service.get_vendor(vendor_id)
        
        if vendor:
            return vendor
        else:
            return {'error': 'Vendor not found'}, 404
    
    @handle_errors
    def put(self, vendor_id):
        """Update vendor"""
        schema = VendorSchema(partial=True)
        updates = schema.load(request.json)
        
        vendor_service = VendorService()
        result = vendor_service.update_vendor(
            vendor_id,
            updates,
            updated_by=request.headers.get('X-User-Id', 'api')
        )
        
        if result['success']:
            return result['vendor']
        else:
            return {'error': result['message']}, 400
    
    @handle_errors
    def delete(self, vendor_id):
        """Delete vendor (soft delete by setting status to inactive)"""
        vendor_service = VendorService()
        result = vendor_service.update_vendor(
            vendor_id,
            {'status': 'inactive'},
            updated_by=request.headers.get('X-User-Id', 'api')
        )
        
        if result['success']:
            return {'message': 'Vendor deleted successfully'}
        else:
            return {'error': result['message']}, 400


class ContractListResource(Resource):
    """Contract list and upload"""
    
    @handle_errors
    def get(self):
        """Get list of contracts"""
        vendor_id = request.args.get('vendor_id')
        
        contract_service = ContractService()
        contracts = contract_service.list_contracts(vendor_id)
        
        return {
            'contracts': contracts,
            'count': len(contracts)
        }
    
    @handle_errors
    def post(self):
        """Upload and process a contract document"""
        if 'file' not in request.files:
            return {'error': 'No file provided'}, 400
        
        file = request.files['file']
        if file.filename == '':
            return {'error': 'No file selected'}, 400
        
        if not allowed_file(file.filename):
            return {'error': 'Invalid file type'}, 400
        
        # Parse form data
        vendor_id = request.form.get('vendor_id')
        
        # Save file
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{file_id}_{filename}')
        file.save(file_path)
        
        # Process contract
        contract_service = ContractService()
        result = contract_service.process_contract_document(file_path, vendor_id)
        
        if result['success']:
            return result, 201
        else:
            return {'error': result['message']}, 400


class ContractResource(Resource):
    """Individual contract operations"""
    
    @handle_errors
    def get(self, contract_id):
        """Get contract details"""
        contract_service = ContractService()
        contract = contract_service.get_contract(contract_id)
        
        if contract:
            return contract
        else:
            return {'error': 'Contract not found'}, 404


class InvoiceListResource(Resource):
    """Invoice list and upload"""
    
    @handle_errors
    def get(self):
        """Get list of invoices"""
        vendor_id = request.args.get('vendor_id')
        status = request.args.get('status')
        
        invoice_service = InvoiceService()
        invoices = invoice_service.list_invoices(vendor_id, status)
        
        return {
            'invoices': invoices,
            'count': len(invoices)
        }
    
    @handle_errors
    def post(self):
        """Upload and process an invoice document"""
        if 'file' not in request.files:
            return {'error': 'No file provided'}, 400
        
        file = request.files['file']
        if file.filename == '':
            return {'error': 'No file selected'}, 400
        
        if not allowed_file(file.filename):
            return {'error': 'Invalid file type'}, 400
        
        # Parse form data
        vendor_id = request.form.get('vendor_id')
        
        # Save file
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{file_id}_{filename}')
        file.save(file_path)
        
        # Process invoice
        invoice_service = InvoiceService()
        result = invoice_service.process_invoice_document(file_path, vendor_id)
        
        if result['success']:
            return result, 201
        else:
            return {'error': result['message']}, 400


class InvoiceResource(Resource):
    """Individual invoice operations"""
    
    @handle_errors
    def get(self, invoice_id):
        """Get invoice details"""
        invoice_service = InvoiceService()
        invoice = invoice_service.get_invoice(invoice_id)
        
        if invoice:
            return invoice
        else:
            return {'error': 'Invoice not found'}, 404


class ReconciliationResource(Resource):
    """Reconciliation operations"""
    
    @handle_errors
    def post(self):
        """Perform reconciliation between contract and invoice"""
        schema = ReconciliationSchema()
        data = schema.load(request.json)
        
        reconciliation_service = ReconciliationService()
        result = reconciliation_service.reconcile_contract_invoice(
            data['contract_id'],
            data['invoice_id'],
            performed_by=request.headers.get('X-User-Id', 'api')
        )
        
        if result['success']:
            return result['reconciliation'], 201
        else:
            return {'error': result['message']}, 400
    
    @handle_errors
    def get(self):
        """Get reconciliation history"""
        vendor_id = request.args.get('vendor_id')
        limit = int(request.args.get('limit', 10))
        failed_only = request.args.get('failed_only', 'false').lower() == 'true'
        
        reconciliation_service = ReconciliationService()
        
        if failed_only:
            reconciliations = reconciliation_service.get_failed_reconciliations(vendor_id)
        else:
            reconciliations = reconciliation_service.get_reconciliation_history(vendor_id, limit)
        
        return {
            'reconciliations': reconciliations,
            'count': len(reconciliations)
        }


class QuickReconcileResource(Resource):
    """Quick reconciliation by uploading both files"""
    
    @handle_errors
    def post(self):
        """Upload contract and invoice for immediate reconciliation"""
        if 'contract' not in request.files or 'invoice' not in request.files:
            return {'error': 'Both contract and invoice files are required'}, 400
        
        contract_file = request.files['contract']
        invoice_file = request.files['invoice']
        
        if not (allowed_file(contract_file.filename) and allowed_file(invoice_file.filename)):
            return {'error': 'Invalid file types'}, 400
        
        # Save files
        contract_id = str(uuid.uuid4())
        invoice_id = str(uuid.uuid4())
        
        contract_filename = secure_filename(contract_file.filename)
        invoice_filename = secure_filename(invoice_file.filename)
        
        contract_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{contract_id}_{contract_filename}')
        invoice_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{invoice_id}_{invoice_filename}')
        
        contract_file.save(contract_path)
        invoice_file.save(invoice_path)
        
        # Process documents
        contract_service = ContractService()
        invoice_service = InvoiceService()
        reconciliation_service = ReconciliationService()
        
        # Process contract
        contract_result = contract_service.process_contract_document(contract_path)
        if not contract_result['success']:
            return {'error': f"Contract processing failed: {contract_result['message']}"}, 400
        
        # Process invoice
        invoice_result = invoice_service.process_invoice_document(
            invoice_path,
            vendor_id=contract_result['contract']['vendor_id']
        )
        if not invoice_result['success']:
            return {'error': f"Invoice processing failed: {invoice_result['message']}"}, 400
        
        # Perform reconciliation
        reconciliation_result = reconciliation_service.reconcile_contract_invoice(
            contract_result['contract']['id'],
            invoice_result['invoice']['id'],
            performed_by=request.headers.get('X-User-Id', 'api')
        )
        
        if reconciliation_result['success']:
            return {
                'contract': contract_result['contract'],
                'invoice': invoice_result['invoice'],
                'reconciliation': reconciliation_result['reconciliation']
            }, 201
        else:
            return {'error': f"Reconciliation failed: {reconciliation_result['message']}"}, 400


class ExpiringContractsResource(Resource):
    """Get contracts expiring soon"""
    
    @handle_errors
    def get(self):
        """Get contracts expiring within specified days"""
        days = int(request.args.get('days', 30))
        
        contract_service = ContractService()
        contracts = contract_service.get_expiring_contracts(days)
        
        return {
            'contracts': contracts,
            'count': len(contracts),
            'days_ahead': days
        }


class DashboardStatsResource(Resource):
    """Dashboard statistics"""
    
    @handle_errors
    def get(self):
        """Get dashboard statistics"""
        vendor_service = VendorService()
        contract_service = ContractService()
        invoice_service = InvoiceService()
        reconciliation_service = ReconciliationService()
        
        vendors = vendor_service.list_vendors()
        contracts = contract_service.list_contracts()
        pending_invoices = invoice_service.list_invoices(status='pending')
        overdue_invoices = invoice_service.list_invoices(status='overdue')
        recent_reconciliations = reconciliation_service.get_reconciliation_history(limit=5)
        failed_reconciliations = reconciliation_service.get_failed_reconciliations()
        
        return {
            'stats': {
                'total_vendors': len(vendors),
                'active_contracts': len(contracts),
                'pending_invoices': len(pending_invoices),
                'overdue_invoices': len(overdue_invoices),
                'failed_reconciliations': len(failed_reconciliations)
            },
            'recent_activity': {
                'reconciliations': recent_reconciliations[:5]
            }
        }


# ========== Register API Routes ==========

# Health check
api.add_resource(HealthResource, '/api/v2/health')

# Vendor endpoints
api.add_resource(VendorListResource, '/api/v2/vendors')
api.add_resource(VendorResource, '/api/v2/vendors/<string:vendor_id>')

# Contract endpoints
api.add_resource(ContractListResource, '/api/v2/contracts')
api.add_resource(ContractResource, '/api/v2/contracts/<string:contract_id>')
api.add_resource(ExpiringContractsResource, '/api/v2/contracts/expiring')

# Invoice endpoints
api.add_resource(InvoiceListResource, '/api/v2/invoices')
api.add_resource(InvoiceResource, '/api/v2/invoices/<string:invoice_id>')

# Reconciliation endpoints
api.add_resource(ReconciliationResource, '/api/v2/reconciliations')
api.add_resource(QuickReconcileResource, '/api/v2/reconcile/quick')

# Dashboard
api.add_resource(DashboardStatsResource, '/api/v2/dashboard/stats')


# ========== Static File Serving (for frontend) ==========

@app.route('/')
def serve_frontend():
    """Serve the frontend"""
    return send_from_directory('../frontend', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('../frontend', path)


# ========== Error Handlers ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Running on port 5001 to avoid conflict with existing app