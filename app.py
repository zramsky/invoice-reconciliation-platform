#!/usr/bin/env python3
"""
Simplified Flask backend for deployment
Vendor management system without heavy OCR/AI dependencies
"""

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
VENDORS_FOLDER = os.path.join(UPLOAD_FOLDER, 'vendors')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx', 'txt'}

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VENDORS_FOLDER, exist_ok=True)

# In-memory storage for vendors (use database in production)
vendors_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "Invoice Reconciliation Platform Backend",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "vendors": "/api/vendors",
            "create_vendor": "POST /api/vendors",
            "get_vendor": "GET /api/vendors/{id}",
            "serve_contract": "GET /api/vendors/{id}/contract",
            "download_contract": "GET /api/vendors/{id}/contract/download"
        }
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors"""
    return jsonify(list(vendors_storage.values()))

@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    """Create a new vendor with contract file"""
    try:
        vendor_name = request.form.get('vendor_name')
        if not vendor_name:
            return jsonify({"error": "vendor_name is required"}), 400

        # Generate unique vendor ID
        vendor_id = str(uuid.uuid4())
        
        # Create vendor directory
        vendor_folder = os.path.join(VENDORS_FOLDER, vendor_id)
        os.makedirs(vendor_folder, exist_ok=True)
        
        vendor_data = {
            "id": vendor_id,
            "name": vendor_name,
            "created_at": datetime.now().isoformat(),
            "contract_file_path": None,
            "contract_url": None
        }

        # Handle contract file upload
        if 'contract_file' in request.files:
            contract_file = request.files['contract_file']
            if contract_file and contract_file.filename and allowed_file(contract_file.filename):
                contract_filename = secure_filename(contract_file.filename)
                contract_file_path = os.path.join(vendor_folder, contract_filename)
                contract_file.save(contract_file_path)
                
                # Store relative path for serving
                vendor_data["contract_file_path"] = contract_file_path
                vendor_data["contract_url"] = f"/api/vendors/{vendor_id}/contract"

        # Save vendor data
        vendors_storage[vendor_id] = vendor_data
        
        return jsonify({
            "message": "Vendor created successfully",
            "vendor": vendor_data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>', methods=['GET'])
def get_vendor(vendor_id):
    """Get a specific vendor"""
    if vendor_id not in vendors_storage:
        return jsonify({"error": "Vendor not found"}), 404
    
    return jsonify(vendors_storage[vendor_id])

@app.route('/api/vendors/<vendor_id>/contract', methods=['GET'])
def serve_contract(vendor_id):
    """Serve the contract file for viewing"""
    if vendor_id not in vendors_storage:
        return jsonify({"error": "Vendor not found"}), 404
    
    vendor = vendors_storage[vendor_id]
    if not vendor.get('contract_file_path') or not os.path.exists(vendor['contract_file_path']):
        return jsonify({"error": "Contract file not found"}), 404
    
    return send_file(vendor['contract_file_path'])

@app.route('/api/vendors/<vendor_id>/contract/download', methods=['GET'])
def download_contract(vendor_id):
    """Download the contract file"""
    if vendor_id not in vendors_storage:
        return jsonify({"error": "Vendor not found"}), 404
    
    vendor = vendors_storage[vendor_id]
    if not vendor.get('contract_file_path') or not os.path.exists(vendor['contract_file_path']):
        return jsonify({"error": "Contract file not found"}), 404
    
    return send_file(vendor['contract_file_path'], as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)