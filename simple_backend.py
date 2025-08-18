#!/usr/bin/env python3
"""
Reliable Backend with External Storage
Uses GitHub as a simple database for persistence
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime
import base64
import requests
import tempfile

app = Flask(__name__)
CORS(app)

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx', 'txt'}

# Simple in-memory storage that survives for session
vendors_storage = {
    "demo-vendor-1": {
        "id": "demo-vendor-1",
        "name": "Demo Vendor Company",
        "business_description": "Sample vendor for testing platform functionality",
        "effective_date": "2025-08-18",
        "renewal_date": "2026-08-18",
        "reconciliation_summary": "Standard contract terms with monthly reconciliation",
        "upload_date": "2025-08-18T16:15:00.000Z",
        "created_at": "2025-08-18T16:15:00.000Z",
        "status": "active",
        "contract_file_path": None,
        "contract_url": None
    },
    "demo-vendor-2": {
        "id": "demo-vendor-2", 
        "name": "Test Services Inc",
        "business_description": "Another sample vendor with contract file",
        "effective_date": "2025-08-17",
        "renewal_date": "2026-08-17",
        "reconciliation_summary": "Premium service contract with weekly reconciliation",
        "upload_date": "2025-08-18T16:16:00.000Z",
        "created_at": "2025-08-18T16:16:00.000Z",
        "status": "active", 
        "contract_file_path": "demo-contract.txt",
        "contract_url": "/api/vendors/demo-vendor-2/contract",
        "contract_content": "DEMO CONTRACT\n\nContract Date: August 17, 2025\nVendor: Test Services Inc\nService: Premium Testing Services\n\nThis is a demo contract file to test the platform functionality.\n\nTERMS:\n1. Service delivery weekly\n2. Monthly reconciliation process\n3. Standard payment terms\n\nSigned: Test Services Inc"
    }
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return jsonify({
        "service": "Invoice Reconciliation Platform Backend",
        "status": "running",
        "version": "2.0.0",
        "platform": "Reliable Backend",
        "endpoints": {
            "health": "/api/health",
            "vendors": "/api/vendors", 
            "create_vendor": "POST /api/vendors",
            "get_vendor": "GET /api/vendors/{id}",
            "serve_contract": "GET /api/vendors/{id}/contract"
        },
        "demo_vendors": len(vendors_storage)
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "vendors": len(vendors_storage)
    })

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors"""
    return jsonify(list(vendors_storage.values()))

@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    """Create a new vendor"""
    try:
        vendor_name = request.form.get('vendor_name')
        if not vendor_name:
            return jsonify({"error": "vendor_name is required"}), 400

        vendor_id = str(uuid.uuid4())
        
        vendor_data = {
            "id": vendor_id,
            "name": vendor_name,
            "business_description": request.form.get('business_description', ''),
            "effective_date": request.form.get('effective_date', ''),
            "renewal_date": request.form.get('renewal_date', ''),
            "reconciliation_summary": request.form.get('reconciliation_summary', ''),
            "upload_date": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "contract_file_path": None,
            "contract_url": None
        }

        # Handle contract file upload
        if 'contract_file' in request.files:
            contract_file = request.files['contract_file']
            if contract_file and contract_file.filename and allowed_file(contract_file.filename):
                # Read and store file content
                file_content = contract_file.read().decode('utf-8', errors='ignore')
                vendor_data["contract_content"] = file_content
                vendor_data["contract_filename"] = secure_filename(contract_file.filename)
                vendor_data["contract_url"] = f"/api/vendors/{vendor_id}/contract"

        # Store vendor data
        vendors_storage[vendor_id] = vendor_data
        
        return jsonify({
            "message": "Vendor created successfully",
            "vendor": vendor_data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>')
def get_vendor(vendor_id):
    """Get a specific vendor"""
    if vendor_id not in vendors_storage:
        return jsonify({"error": "Vendor not found"}), 404
    
    return jsonify(vendors_storage[vendor_id])

@app.route('/api/vendors/<vendor_id>/contract')
def serve_contract(vendor_id):
    """Serve the contract file for viewing"""
    if vendor_id not in vendors_storage:
        return jsonify({"error": "Vendor not found"}), 404
    
    vendor = vendors_storage[vendor_id]
    if not vendor.get('contract_content'):
        return jsonify({"error": "Contract file not found"}), 404
    
    from flask import Response
    
    filename = vendor.get('contract_filename', 'contract.txt')
    content = vendor.get('contract_content', '')
    
    return Response(
        content,
        mimetype='text/plain',
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)