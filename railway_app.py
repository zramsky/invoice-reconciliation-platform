#!/usr/bin/env python3
"""
Railway-optimized version of the Invoice Reconciliation Platform Backend
Simplified for reliable deployment
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Simple in-memory storage for Railway deployment
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
        "status": "active"
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
        "contract_content": "DEMO CONTRACT\n\nContract Date: August 17, 2025\nVendor: Test Services Inc\nService: Premium Testing Services\n\nThis is a demo contract file to test the platform functionality.\n\nTERMS:\n1. Service delivery weekly\n2. Monthly reconciliation process\n3. Standard payment terms\n\nSigned: Test Services Inc"
    }
}

@app.route('/')
def index():
    return jsonify({
        "service": "Invoice Reconciliation Platform Backend",
        "status": "running",
        "version": "2.0.1-railway",
        "platform": "Railway Deployment",
        "startup_time": datetime.now().isoformat(),
        "endpoints": {
            "health": "/api/health",
            "ping": "/api/ping",
            "vendors": "/api/vendors"
        },
        "demo_vendors": len(vendors_storage)
    })

@app.route('/api/ping')
def ping():
    """Ultra-fast health check for Railway"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "vendors": len(vendors_storage),
        "platform": "Railway",
        "database": "In-memory (Railway deployment)"
    })

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors"""
    return jsonify(list(vendors_storage.values()))

@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    """Create a new vendor"""
    try:
        data = request.get_json() or {}
        vendor_name = data.get('vendor_name') or request.form.get('vendor_name')
        
        if not vendor_name:
            return jsonify({"error": "vendor_name is required"}), 400

        vendor_id = str(uuid.uuid4())
        
        vendor_data = {
            "id": vendor_id,
            "name": vendor_name,
            "business_description": data.get('business_description', ''),
            "effective_date": data.get('effective_date', ''),
            "renewal_date": data.get('renewal_date', ''),
            "reconciliation_summary": data.get('reconciliation_summary', ''),
            "upload_date": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)