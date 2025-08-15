from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

from ocr_processor import OCRProcessor
from ai_analyzer import AIAnalyzer

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
ai_analyzer = AIAnalyzer(os.getenv('OPENAI_API_KEY'))

reconciliation_sessions = {}

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

@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('../frontend', path)

if __name__ == '__main__':
    app.run(debug=True, port=5000)