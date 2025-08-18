#!/usr/bin/env python3
"""
Railway-specific Flask app that definitely works
"""
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import json
import uuid

app = Flask(__name__)
CORS(app, origins=["*"])

# In-memory vendor storage
vendors = {
    "demo-1": {
        "id": "demo-1",
        "name": "Demo Vendor",
        "business_description": "Test vendor",
        "status": "active",
        "created_at": datetime.now().isoformat()
    }
}

@app.route('/')
def home():
    return jsonify({
        "service": "Invoice Reconciliation Backend", 
        "status": "running",
        "platform": "Railway",
        "version": "1.0",
        "endpoints": {
            "ping": "/api/ping",
            "vendors": "/api/vendors"
        }
    })

@app.route('/health')
@app.route('/api/ping') 
@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "healthy"
    })

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    return jsonify(list(vendors.values()))

@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    try:
        data = request.get_json() or {}
        vendor_name = data.get('name') or data.get('vendor_name')
        
        if not vendor_name:
            return jsonify({"error": "name required"}), 400
            
        vendor_id = str(uuid.uuid4())[:8]
        vendor = {
            "id": vendor_id,
            "name": vendor_name,
            "business_description": data.get('business_description', ''),
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        
        vendors[vendor_id] = vendor
        return jsonify({"message": "success", "vendor": vendor}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>')
def get_vendor(vendor_id):
    if vendor_id not in vendors:
        return jsonify({"error": "not found"}), 404
    return jsonify(vendors[vendor_id])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Flask app on port {port}")
    print(f"Debug mode: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False
    )