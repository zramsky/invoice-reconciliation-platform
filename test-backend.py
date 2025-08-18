#!/usr/bin/env python3
"""
Simple Flask backend for testing file storage and serving
Minimal dependencies version for testing contract file functionality
"""

import os
import json
import uuid
from datetime import datetime
import mimetypes

try:
    from flask import Flask, request, jsonify, send_file, send_from_directory
    from flask_cors import CORS
    from werkzeug.utils import secure_filename
except ImportError:
    print("Missing dependencies. Installing Flask...")
    os.system("pip3 install --break-system-packages Flask flask-cors")
    from flask import Flask, request, jsonify, send_file, send_from_directory
    from flask_cors import CORS
    from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
VENDORS_FOLDER = os.path.join(UPLOAD_FOLDER, 'vendors')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx', 'txt'}

# Create directories
os.makedirs(VENDORS_FOLDER, exist_ok=True)

# In-memory storage for testing
vendors_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return jsonify({
        "message": "Invoice Reconciliation Platform Backend",
        "status": "running",
        "endpoints": {
            "create_vendor": "POST /api/vendors",
            "list_vendors": "GET /api/vendors", 
            "get_vendor": "GET /api/vendors/<id>",
            "view_contract": "GET /api/vendors/<id>/contract",
            "download_contract": "GET /api/vendors/<id>/contract/download"
        }
    })

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

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
        vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
        os.makedirs(vendor_folder, exist_ok=True)
        
        contract_file_path = None
        contract_filename = None
        
        # Handle contract file upload
        if 'contract_file' in request.files:
            contract_file = request.files['contract_file']
            if contract_file and contract_file.filename and allowed_file(contract_file.filename):
                contract_filename = secure_filename(contract_file.filename)
                contract_file_path = os.path.join(vendor_folder, contract_filename)
                contract_file.save(contract_file_path)
                print(f"✅ Contract file saved: {contract_file_path}")
        
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
        print(f"✅ Vendor created: {vendor_name} (ID: {vendor_id})")
        
        return jsonify({
            "vendor_id": vendor_id,
            "message": "Vendor created successfully",
            "vendor_data": vendor_data
        })
    
    except Exception as e:
        print(f"❌ Error creating vendor: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors', methods=['GET'])
def list_vendors():
    """List all vendors"""
    try:
        vendors_list = []
        
        # Load vendors from filesystem if not in memory
        if os.path.exists(VENDORS_FOLDER):
            for vendor_id in os.listdir(VENDORS_FOLDER):
                vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
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
        vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
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
        vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
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
        
        print(f"📄 Serving contract: {contract_file_path} ({mime_type})")
        
        return send_file(
            contract_file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=vendor_data.get('contract_filename', 'contract')
        )
    
    except Exception as e:
        print(f"❌ Error serving contract: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>/contract/download', methods=['GET'])
def download_vendor_contract(vendor_id):
    """Download vendor contract file"""
    try:
        # Get vendor data
        vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
        vendor_json_path = os.path.join(vendor_folder, 'vendor_data.json')
        
        if not os.path.exists(vendor_json_path):
            return jsonify({"error": "Vendor not found"}), 404
        
        with open(vendor_json_path, 'r') as f:
            vendor_data = json.load(f)
        
        contract_file_path = vendor_data.get('contract_file_path')
        if not contract_file_path or not os.path.exists(contract_file_path):
            return jsonify({"error": "Contract file not found"}), 404
        
        print(f"⬇️ Downloading contract: {contract_file_path}")
        
        return send_file(
            contract_file_path,
            as_attachment=True,
            download_name=vendor_data.get('contract_filename', 'contract')
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve frontend files
@app.route('/<path:filename>')
def serve_frontend(filename):
    return send_from_directory('../frontend', filename)

@app.route('/index.html')
@app.route('/frontend/')
def serve_index():
    return send_from_directory('../frontend', 'index.html')

if __name__ == '__main__':
    print("🚀 Starting Invoice Reconciliation Platform Test Backend...")
    print("📁 Upload folder:", VENDORS_FOLDER)
    print("🌐 Backend URL: http://localhost:5001")
    print("🎯 Frontend URL: http://localhost:5001/index.html")
    print("📖 API Documentation: http://localhost:5001")
    print("\n✨ Ready to test file storage!")
    
    app.run(debug=True, host='0.0.0.0', port=5001)