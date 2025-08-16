from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

from ocr_processor import OCRProcessor
from ai_analyzer import AIAnalyzer
from llm_client import LLMClient
from reconciliation_engine import ReconciliationEngine
from database import Database
from schemas import validate_contract, validate_invoice, validate_reconciliation
from api_middleware import (
    with_rate_limiting, with_error_handling, RateLimitRule,
    create_api_middleware, request_logger, error_handler
)
from batch_processor import (
    BatchProcessor, BatchJob, BatchRequest, JobPriority,
    create_document_processors
)
from auth_system import AuthManager, require_auth, optional_auth
from vendor_management import create_vendor_blueprint
from reporting_system import create_reporting_blueprint
from billcom_api_routes import create_billcom_blueprint

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 10485760))

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

ocr_processor = OCRProcessor()
database = Database()
api_key = os.getenv('OPENAI_API_KEY')
ai_analyzer = AIAnalyzer(api_key) if api_key else None  # Legacy analyzer for fallback
llm_client = LLMClient()
reconciliation_engine = ReconciliationEngine(database)
if api_key:
    llm_client.set_api_key(api_key)
    llm_client.set_database(database)  # Enable database caching

# Initialize API middleware
api_middleware = create_api_middleware()

# Initialize authentication
auth_manager = AuthManager(database, os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'))

# Initialize batch processor
batch_processor = BatchProcessor(max_workers=4, max_concurrent_jobs=20)
create_document_processors(batch_processor, llm_client, ocr_processor, reconciliation_engine)
batch_processor.start()

# Register vendor management blueprint
vendor_bp = create_vendor_blueprint(database)
app.register_blueprint(vendor_bp)

# Register reporting system blueprint
reporting_bp = create_reporting_blueprint(database)
app.register_blueprint(reporting_bp)

# Register Bill.com integration blueprint
billcom_bp = create_billcom_blueprint(database)
app.register_blueprint(billcom_bp)

reconciliation_sessions = {}

# Configure different rate limits for different endpoint types
STRICT_RATE_LIMIT = RateLimitRule(requests_per_minute=10, requests_per_hour=100, requests_per_day=500)
STANDARD_RATE_LIMIT = RateLimitRule(requests_per_minute=30, requests_per_hour=500, requests_per_day=2000)
RELAXED_RATE_LIMIT = RateLimitRule(requests_per_minute=60, requests_per_hour=1000, requests_per_day=5000)

@app.before_request
def before_request():
    """Set up request context"""
    g.auth_manager = auth_manager

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        company = data.get('company', '').strip()
        
        if not email or not password or not full_name:
            return jsonify({"error": "Email, password, and full name are required"}), 400
        
        result = auth_manager.register_user(email, password, full_name, company)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "user_id": result['user_id']
            }), 201
        else:
            return jsonify({"error": result['error']}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and create session"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        
        ip_address = request.environ.get('REMOTE_ADDR')
        user_agent = request.headers.get('User-Agent')
        
        result = auth_manager.login_user(email, password, ip_address, user_agent)
        
        if result['success']:
            response = jsonify({
                "success": True,
                "user": result['user'],
                "expires_at": result['expires_at']
            })
            
            # Set session token as HTTP-only cookie
            response.set_cookie(
                'session_token',
                result['session_token'],
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite='Lax',
                max_age=30*24*60*60  # 30 days
            )
            
            return response, 200
        else:
            return jsonify({"error": result['error']}), 401
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@with_error_handling
@require_auth
def logout():
    """Logout user and invalidate session"""
    try:
        session_token = request.headers.get('Authorization')
        if session_token and session_token.startswith('Bearer '):
            session_token = session_token[7:]
        else:
            session_token = request.cookies.get('session_token')
        
        if session_token:
            auth_manager.logout_user(session_token)
        
        response = jsonify({"success": True, "message": "Logged out successfully"})
        response.set_cookie('session_token', '', expires=0)
        
        return response, 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/profile', methods=['GET'])
@with_error_handling
@require_auth
def get_profile():
    """Get current user profile"""
    try:
        user = g.current_user
        
        # Get user data summary
        data_summary = auth_manager.get_user_data_summary(user.id)
        
        return jsonify({
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "company": user.company,
                "subscription_tier": user.subscription_tier,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            },
            "data_summary": data_summary
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/validate', methods=['GET'])
@optional_auth
def validate_session():
    """Validate current session"""
    try:
        if g.current_user:
            return jsonify({
                "valid": True,
                "user": {
                    "id": g.current_user.id,
                    "email": g.current_user.email,
                    "full_name": g.current_user.full_name,
                    "company": g.current_user.company,
                    "subscription_tier": g.current_user.subscription_tier
                }
            }), 200
        else:
            return jsonify({"valid": False}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API Versioning - Version 2 (Enhanced) endpoints
@app.route('/api/v2/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])  # Default to v2
@with_error_handling
@with_rate_limiting(RELAXED_RATE_LIMIT)
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "api_version": "v2",
        "features": ["llm_optimization", "advanced_caching", "rate_limiting", "batch_processing"]
    })

# V1 endpoints for backward compatibility
@app.route('/api/v1/health', methods=['GET'])
@with_error_handling
@with_rate_limiting(RELAXED_RATE_LIMIT)
def health_check_v1():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "api_version": "v1"
    })

@app.route('/api/upload', methods=['POST'])
@optional_auth
def upload_files():
    """Upload contract and invoice files for reconciliation"""
    try:
        if 'contract' not in request.files or 'invoice' not in request.files:
            return jsonify({"error": "Both contract and invoice files are required"}), 400
        
        contract_file = request.files['contract']
        invoice_file = request.files['invoice']
        
        if not contract_file or not invoice_file:
            return jsonify({"error": "Both files must be selected"}), 400
        
        if not (allowed_file(contract_file.filename) and allowed_file(invoice_file.filename)):
            return jsonify({"error": "Invalid file type. Allowed: PDF, PNG, JPG, JPEG, TIFF, BMP"}), 400
        
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        contract_filename = secure_filename(contract_file.filename)
        invoice_filename = secure_filename(invoice_file.filename)
        
        contract_path = os.path.join(session_folder, f"contract_{contract_filename}")
        invoice_path = os.path.join(session_folder, f"invoice_{invoice_filename}")
        
        contract_file.save(contract_path)
        invoice_file.save(invoice_path)
        
        reconciliation_sessions[session_id] = {
            "contract_path": contract_path,
            "invoice_path": invoice_path,
            "status": "uploaded",
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify({
            "session_id": session_id,
            "message": "Files uploaded successfully",
            "status": "ready_for_processing"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/process/<session_id>', methods=['POST'])
@optional_auth
def process_reconciliation(session_id):
    """Process uploaded files for reconciliation"""
    try:
        if session_id not in reconciliation_sessions:
            return jsonify({"error": "Invalid session ID"}), 404
        
        session = reconciliation_sessions[session_id]
        
        session['status'] = 'processing_ocr'
        contract_text = ocr_processor.process_document(session['contract_path'])
        invoice_text = ocr_processor.process_document(session['invoice_path'])
        
        session['status'] = 'extracting_details'
        
        # Use new LLMClient for extraction
        contract_details, contract_success = llm_client.extract_contract(contract_text)
        invoice_details, invoice_success = llm_client.extract_invoice(invoice_text)
        
        # Fallback to old analyzer if LLM client fails
        if not contract_success:
            contract_details = ai_analyzer.extract_contract_details(contract_text)
        if not invoice_success:
            invoice_details = ai_analyzer.extract_invoice_details(invoice_text)
        
        session['status'] = 'comparing'
        
        # Use new reconciliation if both extractions succeeded
        if contract_success and invoice_success:
            # Run deterministic reconciliation first
            reconciliation_result = reconciliation_engine.reconcile(contract_details, invoice_details)
            
            # If any flags require LLM review, run reconciliation review
            needs_llm_review = any(flag.severity.value == "error" for flag in reconciliation_result.flags)
            
            if needs_llm_review:
                payload = {
                    "contract": contract_details,
                    "invoice": invoice_details,
                    "matches": [match.dict() for match in reconciliation_result.matches]
                }
                llm_review, review_success = llm_client.reconcile_review(payload)
                if review_success:
                    # Merge LLM review with deterministic results
                    comparison_results = {
                        "deterministic": reconciliation_result.dict(),
                        "llm_review": llm_review,
                        "method": "hybrid"
                    }
                else:
                    comparison_results = reconciliation_result.dict()
            else:
                comparison_results = reconciliation_result.dict()
        else:
            # Use legacy comparison
            comparison_results = ai_analyzer.compare_documents(contract_details, invoice_details)
        
        session['status'] = 'completed'
        session['results'] = {
            "contract_details": contract_details,
            "invoice_details": invoice_details,
            "comparison": comparison_results,
            "processed_at": datetime.now().isoformat()
        }
        
        return jsonify({
            "session_id": session_id,
            "status": "completed",
            "results": session['results']
        })
    
    except Exception as e:
        if session_id in reconciliation_sessions:
            reconciliation_sessions[session_id]['status'] = 'error'
            reconciliation_sessions[session_id]['error'] = str(e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/results/<session_id>', methods=['GET'])
def get_results(session_id):
    """Get reconciliation results for a session"""
    if session_id not in reconciliation_sessions:
        return jsonify({"error": "Invalid session ID"}), 404
    
    session = reconciliation_sessions[session_id]
    
    if session['status'] != 'completed':
        return jsonify({
            "session_id": session_id,
            "status": session['status'],
            "message": "Processing not yet completed"
        })
    
    return jsonify({
        "session_id": session_id,
        "status": session['status'],
        "results": session.get('results', {})
    })

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all reconciliation sessions"""
    sessions_list = []
    for session_id, session in reconciliation_sessions.items():
        sessions_list.append({
            "session_id": session_id,
            "status": session['status'],
            "timestamp": session.get('timestamp'),
            "has_results": 'results' in session
        })
    
    return jsonify({"sessions": sessions_list})

# New Unspend API endpoints for testing

@app.route('/api/contracts', methods=['POST'])
@with_error_handling
@with_rate_limiting(STANDARD_RATE_LIMIT)
@require_auth
def upload_contract():
    """Upload and parse contract using new LLM client"""
    try:
        if 'contract' not in request.files:
            return jsonify({"error": "Contract file is required"}), 400
        
        contract_file = request.files['contract']
        if not contract_file or not allowed_file(contract_file.filename):
            return jsonify({"error": "Invalid contract file"}), 400
        
        # Save file
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        filename = secure_filename(contract_file.filename)
        file_path = os.path.join(session_folder, f"contract_{filename}")
        contract_file.save(file_path)
        
        # Process with OCR
        contract_text = ocr_processor.process_document(file_path)
        
        # Check if already processed (by text hash)
        import hashlib
        text_hash = hashlib.sha256(contract_text.encode('utf-8')).hexdigest()
        cached_contract = database.get_contract_by_hash(text_hash)
        
        if cached_contract:
            return jsonify({
                "session_id": session_id,
                "success": True,
                "contract_details": cached_contract['extracted_json'],
                "raw_text_length": len(contract_text),
                "extraction_method": "cached",
                "confidence": cached_contract['extraction_confidence']
            })
        
        # Extract with LLM
        contract_details, success = llm_client.extract_contract(contract_text)
        
        # Calculate confidence score
        confidence = 0.0
        if success and contract_details:
            confidence_sum = 0
            confidence_count = 0
            for field, data in contract_details.items():
                if isinstance(data, dict) and 'confidence' in data:
                    confidence_sum += data['confidence']
                    confidence_count += 1
            confidence = confidence_sum / confidence_count if confidence_count > 0 else 0.0
        
        # Store in database
        if success:
            contract_id = database.store_contract(
                contract_text, 
                contract_details, 
                confidence, 
                "llm_client"
            )
            
            # Link contract to authenticated user
            auth_manager.link_contract_to_user(g.current_user.id, contract_id)
        
        return jsonify({
            "session_id": session_id,
            "success": success,
            "contract_details": contract_details,
            "raw_text_length": len(contract_text),
            "extraction_method": "llm_client" if success else "failed",
            "confidence": confidence
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/invoices', methods=['POST'])
@with_error_handling
@with_rate_limiting(STANDARD_RATE_LIMIT)
@require_auth
def upload_invoice():
    """Upload and parse invoice using new LLM client"""
    try:
        if 'invoice' not in request.files:
            return jsonify({"error": "Invoice file is required"}), 400
        
        invoice_file = request.files['invoice']
        if not invoice_file or not allowed_file(invoice_file.filename):
            return jsonify({"error": "Invalid invoice file"}), 400
        
        # Save file
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        filename = secure_filename(invoice_file.filename)
        file_path = os.path.join(session_folder, f"invoice_{filename}")
        invoice_file.save(file_path)
        
        # Process with OCR
        invoice_text = ocr_processor.process_document(file_path)
        
        # Check if already processed (by text hash)
        import hashlib
        text_hash = hashlib.sha256(invoice_text.encode('utf-8')).hexdigest()
        cached_invoice = database.get_invoice_by_hash(text_hash)
        
        if cached_invoice:
            return jsonify({
                "session_id": session_id,
                "success": True,
                "invoice_details": cached_invoice['extracted_json'],
                "raw_text_length": len(invoice_text),
                "extraction_method": "cached",
                "confidence": cached_invoice['extraction_confidence']
            })
        
        # Extract with LLM
        invoice_details, success = llm_client.extract_invoice(invoice_text)
        
        # Calculate confidence score
        confidence = 0.0
        if success and invoice_details:
            confidence_sum = 0
            confidence_count = 0
            for field, data in invoice_details.items():
                if isinstance(data, dict) and 'confidence' in data:
                    confidence_sum += data['confidence']
                    confidence_count += 1
            confidence = confidence_sum / confidence_count if confidence_count > 0 else 0.0
        
        # Store in database
        if success:
            invoice_id = database.store_invoice(
                invoice_text, 
                invoice_details, 
                confidence, 
                "llm_client"
            )
            
            # Link invoice to authenticated user
            auth_manager.link_invoice_to_user(g.current_user.id, invoice_id)
        
        return jsonify({
            "session_id": session_id,
            "success": success,
            "invoice_details": invoice_details,
            "raw_text_length": len(invoice_text),
            "extraction_method": "llm_client" if success else "failed",
            "confidence": confidence
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reconcile', methods=['POST'])
@with_error_handling
@with_rate_limiting(STRICT_RATE_LIMIT)
@require_auth
def reconcile_documents():
    """Run reconciliation between contract and invoice"""
    try:
        data = request.get_json()
        
        if not data or 'contract' not in data or 'invoice' not in data:
            return jsonify({"error": "Both contract and invoice data required"}), 400
        
        # Validate inputs
        try:
            contract_validated = validate_contract(data['contract'])
            invoice_validated = validate_invoice(data['invoice'])
        except ValueError as e:
            return jsonify({"error": f"Validation failed: {str(e)}"}), 400
        
        # Run deterministic reconciliation first
        reconciliation_result = reconciliation_engine.reconcile(data['contract'], data['invoice'])
        
        # Check if LLM review is needed for complex cases
        needs_llm_review = any(flag.severity.value == "error" for flag in reconciliation_result.flags)
        
        llm_review = None
        if needs_llm_review:
            payload = {
                "contract": data['contract'],
                "invoice": data['invoice'],
                "matches": [match.dict() for match in reconciliation_result.matches]
            }
            llm_review, llm_success = llm_client.reconcile_review(payload)
        
        # Combine results
        final_result = {
            "deterministic": reconciliation_result.dict(),
            "llm_review": llm_review if needs_llm_review else None,
            "method": "hybrid" if needs_llm_review else "deterministic"
        }
        
        return jsonify({
            "success": True,
            "reconciliation": final_result,
            "validation_passed": True
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/data', methods=['GET'])
@with_error_handling
@require_auth
def get_user_data():
    """Get all data belonging to the authenticated user"""
    try:
        user_id = g.current_user.id
        
        # Get user's contracts
        with database.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get user contracts with details
            cursor.execute("""
                SELECT c.id, c.raw_text, c.extracted_json, c.extraction_confidence, 
                       c.extraction_method, c.created_at
                FROM contracts c
                JOIN user_contracts uc ON c.id = uc.contract_id
                WHERE uc.user_id = ?
                ORDER BY c.created_at DESC
            """, (user_id,))
            
            user_contracts = []
            for row in cursor.fetchall():
                user_contracts.append({
                    'id': row['id'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence'],
                    'extraction_method': row['extraction_method'],
                    'created_at': row['created_at'],
                    'text_length': len(row['raw_text'])
                })
            
            # Get user invoices with details
            cursor.execute("""
                SELECT i.id, i.raw_text, i.extracted_json, i.extraction_confidence,
                       i.extraction_method, i.created_at
                FROM invoices i
                JOIN user_invoices ui ON i.id = ui.invoice_id
                WHERE ui.user_id = ?
                ORDER BY i.created_at DESC
            """, (user_id,))
            
            user_invoices = []
            for row in cursor.fetchall():
                user_invoices.append({
                    'id': row['id'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence'],
                    'extraction_method': row['extraction_method'],
                    'created_at': row['created_at'],
                    'text_length': len(row['raw_text'])
                })
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "contracts": user_contracts,
            "invoices": user_invoices,
            "summary": {
                "total_contracts": len(user_contracts),
                "total_invoices": len(user_invoices)
            }
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard', methods=['GET'])
@optional_auth
def dashboard():
    """Dashboard data for exceptions, next payments, renewals"""
    try:
        # Get real stats from database
        stats = database.get_dashboard_stats()
        
        # Get low confidence extractions for review
        low_confidence = database.get_low_confidence_extractions()
        
        # If user is authenticated, get their personal data summary
        user_data_summary = None
        if g.current_user:
            user_data_summary = auth_manager.get_user_data_summary(g.current_user.id)
        
        dashboard_data = {
            "total_contracts": stats['total_contracts'],
            "total_invoices": stats['total_invoices'],
            "total_reconciliations": stats['total_reconciliations'],
            "total_exceptions": stats['total_exceptions'],
            "next_payments": [],  # TODO: Calculate from active contracts
            "upcoming_renewals": [],  # TODO: Calculate from contract end dates
            "recent_flags": stats['recent_flags'],
            "low_confidence_extractions": low_confidence[:10],
            "llm_stats": {
                "cache_entries": stats['cache_entries'],
                "cache_hits": stats['cache_hits'],
                "small_model": llm_client.small_model,
                "large_model": llm_client.large_model
            },
            "legacy_sessions": len(reconciliation_sessions),
            "user_data": user_data_summary,
            "authenticated": g.current_user is not None
        }
        
        return jsonify(dashboard_data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/quality/review', methods=['GET'])
def get_quality_review():
    """Get items requiring human review due to quality gates"""
    try:
        threshold = float(request.args.get('threshold', 0.7))
        low_confidence = database.get_low_confidence_extractions(threshold)
        
        # Add quality gate recommendations
        for item in low_confidence:
            item['review_reason'] = 'Low confidence score'
            item['recommended_action'] = 'Manual review and correction'
            if item['confidence'] < 0.5:
                item['priority'] = 'high'
            elif item['confidence'] < 0.7:
                item['priority'] = 'medium'
            else:
                item['priority'] = 'low'
        
        return jsonify({
            "items_for_review": low_confidence,
            "total_count": len(low_confidence),
            "threshold": threshold
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/quality/update/<item_type>/<int:item_id>', methods=['PUT'])
def update_extraction(item_type, item_id):
    """Update extraction after human review"""
    try:
        data = request.get_json()
        
        if item_type not in ['contract', 'invoice']:
            return jsonify({"error": "Invalid item type"}), 400
        
        # TODO: Implement update logic with validation
        # For now, just log the update attempt
        return jsonify({
            "success": True,
            "message": f"Updated {item_type} {item_id}",
            "updated_fields": list(data.keys()) if data else []
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit/trail', methods=['GET'])
def get_audit_trail():
    """Get audit trail with optional filtering"""
    try:
        # Get query parameters
        table_name = request.args.get('table')
        operation = request.args.get('operation')
        limit = int(request.args.get('limit', 100))
        
        # For now, return a simple response
        # TODO: Implement full audit trail query from database
        return jsonify({
            "audit_entries": [],
            "filters": {
                "table_name": table_name,
                "operation": operation,
                "limit": limit
            },
            "total_count": 0
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get detailed cache statistics"""
    try:
        stats = database.get_dashboard_stats()
        
        return jsonify({
            "cache_entries": stats.get('cache_entries', 0),
            "cache_hits": stats.get('cache_hits', 0),
            "hit_rate": stats.get('cache_hits', 0) / max(stats.get('cache_entries', 1), 1),
            "memory_cache_size": len(llm_client.cache) if llm_client.cache else 0,
            "models": {
                "small": llm_client.small_model,
                "large": llm_client.large_model
            }
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Clean up old cache entries"""
    try:
        days = int(request.args.get('days', 7))
        deleted_count = database.cleanup_old_cache(days)
        
        return jsonify({
            "success": True,
            "deleted_entries": deleted_count,
            "retention_days": days
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test/upload', methods=['POST'])
def test_upload():
    """Test endpoint for validating file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400
        
        # Just validate, don't process
        return jsonify({
            "success": True,
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(file.read()),
            "message": "File validation successful"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
@with_error_handling
@with_rate_limiting(RELAXED_RATE_LIMIT)
def get_api_metrics():
    """Get comprehensive API metrics including LLM performance"""
    try:
        client_id = request.args.get('client_id')
        
        # Get request metrics
        request_metrics = request_logger.get_metrics(client_id)
        
        # Get LLM metrics
        llm_metrics = llm_client.get_metrics()
        
        # Get cache metrics
        cache_metrics = llm_client.get_cache_stats()
        
        # Get error statistics
        error_stats = error_handler.get_error_stats()
        
        return jsonify({
            "request_metrics": request_metrics,
            "llm_performance": llm_metrics,
            "cache_performance": cache_metrics,
            "error_statistics": error_stats,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/cache/clear', methods=['POST'])
@with_error_handling
@with_rate_limiting(RateLimitRule(requests_per_minute=5, requests_per_hour=20))
def clear_cache():
    """Admin endpoint to clear caches"""
    try:
        pattern = request.args.get('pattern', '*')
        
        # Clear LLM cache
        cache_cleared = llm_client.clear_cache(pattern)
        
        # Perform cache maintenance
        llm_client.cache_maintenance()
        
        return jsonify({
            "success": cache_cleared,
            "pattern": pattern,
            "message": f"Cache cleared with pattern: {pattern}",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/metrics/reset', methods=['POST'])
@with_error_handling
@with_rate_limiting(RateLimitRule(requests_per_minute=2, requests_per_hour=10))
def reset_metrics():
    """Admin endpoint to reset performance metrics"""
    try:
        # Reset LLM metrics
        llm_client.reset_metrics()
        
        return jsonify({
            "success": True,
            "message": "Performance metrics reset",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/batch/submit', methods=['POST'])
@with_error_handling
@with_rate_limiting(STANDARD_RATE_LIMIT)
def submit_batch_job():
    """Submit a batch processing job"""
    try:
        data = request.get_json()
        job_type = data.get('job_type')
        input_data = data.get('input_data', {})
        priority = data.get('priority', 'normal')
        
        # Convert priority string to enum
        priority_map = {
            'low': JobPriority.LOW,
            'normal': JobPriority.NORMAL,
            'high': JobPriority.HIGH,
            'urgent': JobPriority.URGENT
        }
        job_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)
        
        # Submit job
        job_id = batch_processor.submit_job(job_type, input_data, job_priority)
        
        return jsonify({
            "success": True,
            "job_id": job_id,
            "status": "submitted",
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/batch/status/<job_id>', methods=['GET'])
@with_error_handling
@with_rate_limiting(RELAXED_RATE_LIMIT)
def get_batch_job_status(job_id):
    """Get status of a batch job"""
    try:
        status_info = batch_processor.get_job_status(job_id)
        
        if not status_info:
            return jsonify({"error": "Job not found"}), 404
        
        return jsonify({
            "success": True,
            **status_info,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/batch/stats', methods=['GET'])
@with_error_handling
@with_rate_limiting(RELAXED_RATE_LIMIT)
def get_batch_processor_stats():
    """Get batch processor statistics"""
    try:
        stats = batch_processor.get_stats()
        
        return jsonify({
            "success": True,
            "batch_processor_stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/batch/upload', methods=['POST'])
@with_error_handling
@with_rate_limiting(STANDARD_RATE_LIMIT)
def batch_upload_documents():
    """Upload multiple documents for batch processing"""
    try:
        # Check if files were uploaded
        if not request.files:
            return jsonify({"error": "No files uploaded"}), 400
        
        submitted_jobs = []
        
        for file_key, file in request.files.items():
            if file and allowed_file(file.filename):
                # Save file
                session_id = str(uuid.uuid4())
                session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
                os.makedirs(session_folder, exist_ok=True)
                
                filename = secure_filename(file.filename)
                file_path = os.path.join(session_folder, filename)
                file.save(file_path)
                
                # Determine job type based on file key or name
                if 'contract' in file_key.lower() or 'contract' in filename.lower():
                    job_type = 'extract_contract'
                elif 'invoice' in file_key.lower() or 'invoice' in filename.lower():
                    job_type = 'extract_invoice'
                else:
                    # Default to contract extraction
                    job_type = 'extract_contract'
                
                # Submit to batch processor
                job_id = batch_processor.submit_job(
                    job_type,
                    {'file_path': file_path, 'filename': filename},
                    JobPriority.NORMAL
                )
                
                submitted_jobs.append({
                    'job_id': job_id,
                    'job_type': job_type,
                    'filename': filename,
                    'file_key': file_key
                })
        
        return jsonify({
            "success": True,
            "submitted_jobs": submitted_jobs,
            "total_jobs": len(submitted_jobs),
            "message": f"Submitted {len(submitted_jobs)} documents for batch processing",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/login')
def serve_login():
    return send_from_directory('../frontend', 'login.html')

@app.route('/signup')
def serve_signup():
    return send_from_directory('../frontend', 'signup.html')

@app.route('/dashboard')
def serve_dashboard():
    return send_from_directory('../frontend', 'dashboard-protected.html')

@app.route('/vendors')
def serve_vendor_management():
    return send_from_directory('../frontend', 'vendor-management.html')

@app.route('/reports')
def serve_reports():
    return send_from_directory('../frontend', 'reports.html')

@app.route('/billcom-integration')
def serve_billcom_integration():
    return send_from_directory('../frontend', 'billcom-integration.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('../frontend', path)

if __name__ == '__main__':
    app.run(debug=True, port=5001)