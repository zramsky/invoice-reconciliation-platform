from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
from dotenv import load_dotenv
import uuid
from datetime import datetime
import base64
import mimetypes

from ocr_processor import OCRProcessor
from ai_analyzer import AIAnalyzer

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['PROCESSED_FOLDER'] = os.getenv('PROCESSED_FOLDER', 'processed')
app.config['VENDORS_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'vendors')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 10485760))

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
os.makedirs(app.config['VENDORS_FOLDER'], exist_ok=True)

ocr_processor = OCRProcessor()
ai_analyzer = AIAnalyzer(os.getenv('OPENAI_API_KEY'))

reconciliation_sessions = {}
vendors_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/upload', methods=['POST'])
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
        contract_details = ai_analyzer.extract_contract_details(contract_text)
        invoice_details = ai_analyzer.extract_invoice_details(invoice_text)
        
        session['status'] = 'comparing'
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

# Vendor Management Endpoints

@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    """Create a new vendor with contract file"""
    try:
        vendor_name = request.form.get('vendor_name')
        business_description = request.form.get('business_description', '')
        effective_date = request.form.get('effective_date')
        renewal_date = request.form.get('renewal_date')
        reconciliation_summary = request.form.get('reconciliation_summary', '')
        
        if not vendor_name:
            return jsonify({"error": "Vendor name is required"}), 400
        
        vendor_id = str(uuid.uuid4())
        vendor_folder = os.path.join(app.config['VENDORS_FOLDER'], vendor_id)
        os.makedirs(vendor_folder, exist_ok=True)
        
        contract_file_path = None
        contract_filename = None
        
        # Handle contract file upload
        if 'contract_file' in request.files:
            contract_file = request.files['contract_file']
            if contract_file and allowed_file(contract_file.filename):
                contract_filename = secure_filename(contract_file.filename)
                contract_file_path = os.path.join(vendor_folder, contract_filename)
                contract_file.save(contract_file_path)
        
        vendor_data = {
            "id": vendor_id,
            "vendor_name": vendor_name,
            "business_description": business_description,
            "effective_date": effective_date,
            "renewal_date": renewal_date,
            "reconciliation_summary": reconciliation_summary,
            "contract_filename": contract_filename,
            "contract_file_path": contract_file_path,
            "upload_date": datetime.now().isoformat(),
            "status": "Active",
            "created_at": datetime.now().isoformat()
        }
        
        # Save vendor data to JSON file
        vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
        with open(vendor_json_path, 'w') as f:
            json.dump(vendor_data, f, indent=2)
        
        vendors_storage[vendor_id] = vendor_data
        
        return jsonify({
            "vendor_id": vendor_id,
            "message": "Vendor created successfully",
            "vendor_data": vendor_data
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors', methods=['GET'])
def list_vendors():
    """List all vendors"""
    try:
        vendors_list = []
        
        # Load vendors from filesystem if not in memory
        if os.path.exists(app.config['VENDORS_FOLDER']):
            for vendor_id in os.listdir(app.config['VENDORS_FOLDER']):
                vendor_folder = os.path.join(app.config['VENDORS_FOLDER'], vendor_id)
                vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
                
                if os.path.isfile(vendor_json_path):
                    try:
                        with open(vendor_json_path, 'r') as f:
                            vendor_data = json.load(f)
                            vendors_storage[vendor_id] = vendor_data
                            vendors_list.append(vendor_data)
                    except (json.JSONDecodeError, FileNotFoundError):
                        continue
        
        return jsonify({"vendors": vendors_list})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>', methods=['GET'])
def get_vendor(vendor_id):
    """Get specific vendor details"""
    try:
        # Try to load from memory first
        if vendor_id in vendors_storage:
            return jsonify({"vendor": vendors_storage[vendor_id]})
        
        # Load from filesystem
        vendor_folder = os.path.join(app.config['VENDORS_FOLDER'], vendor_id)
        vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
        
        if not os.path.exists(vendor_json_path):
            return jsonify({"error": "Vendor not found"}), 404
        
        with open(vendor_json_path, 'r') as f:
            vendor_data = json.load(f)
            vendors_storage[vendor_id] = vendor_data
            return jsonify({"vendor": vendor_data})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>/contract', methods=['GET'])
def get_vendor_contract(vendor_id):
    """Serve vendor contract file"""
    try:
        # Get vendor data
        vendor_folder = os.path.join(app.config['VENDORS_FOLDER'], vendor_id)
        vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
        
        if not os.path.exists(vendor_json_path):
            return jsonify({"error": "Vendor not found"}), 404
        
        with open(vendor_json_path, 'r') as f:
            vendor_data = json.load(f)
        
        contract_file_path = vendor_data.get('contract_file_path')
        if not contract_file_path or not os.path.exists(contract_file_path):
            return jsonify({"error": "Contract file not found"}), 404
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(contract_file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        return send_file(
            contract_file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=vendor_data.get('contract_filename', 'contract')
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>/contract/download', methods=['GET'])
def download_vendor_contract(vendor_id):
    """Download vendor contract file"""
    try:
        # Get vendor data
        vendor_folder = os.path.join(app.config['VENDORS_FOLDER'], vendor_id)
        vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
        
        if not os.path.exists(vendor_json_path):
            return jsonify({"error": "Vendor not found"}), 404
        
        with open(vendor_json_path, 'r') as f:
            vendor_data = json.load(f)
        
        contract_file_path = vendor_data.get('contract_file_path')
        if not contract_file_path or not os.path.exists(contract_file_path):
            return jsonify({"error": "Contract file not found"}), 404
        
        return send_file(
            contract_file_path,
            as_attachment=True,
            download_name=vendor_data.get('contract_filename', 'contract')
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('../frontend', path)

if __name__ == '__main__':
    app.run(debug=True, port=5000)