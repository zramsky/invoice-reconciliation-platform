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
from database import get_db, init_db
from monitoring import get_monitor, get_profiler, create_monitoring_middleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Add monitoring middleware
app = create_monitoring_middleware(app)

# Load environment variables safely
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'not-configured')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '10485760'))  # 10MB default

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx', 'txt'}

# Initialize database on startup
try:
    init_db()
    database = get_db()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    database = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return jsonify({
        "service": "Invoice Reconciliation Platform Backend",
        "status": "running",
        "version": "2.0.1",
        "platform": "Reliable Backend",
        "startup_time": datetime.now().isoformat(),
        "endpoints": {
            "health": "/api/health",
            "ping": "/api/ping",
            "vendors": "/api/vendors", 
            "create_vendor": "POST /api/vendors",
            "get_vendor": "GET /api/vendors/{id}",
            "serve_contract": "GET /api/vendors/{id}/contract"
        },
        "database_status": database.get_health_stats() if database else {"connected": False, "error": "Database not initialized"}
    })

@app.route('/api/ping')
def ping():
    """Ultra-fast health check for load balancing"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/monitor/health')
def monitor_health():
    """Comprehensive health monitoring endpoint"""
    monitor = get_monitor()
    
    return jsonify({
        "service": monitor.get_health_report(),
        "database": monitor.check_database_health(),
        "dependencies": monitor.check_external_dependencies()
    })

@app.route('/api/monitor/performance')
def monitor_performance():
    """Performance monitoring endpoint"""
    profiler = get_profiler()
    monitor = get_monitor()
    
    return jsonify({
        "endpoints": profiler.get_endpoint_report(),
        "overall": monitor.get_health_report()["metrics"]
    })

@app.route('/api/health')
def health_check():
    db_stats = database.get_health_stats() if database else {"connected": False, "total_vendors": 0}
    
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "vendors": db_stats.get("total_vendors", 0),
        "database": db_stats,
        "config": {
            "openai_configured": OPENAI_API_KEY != 'not-configured' and not OPENAI_API_KEY.startswith('your_'),
            "upload_folder": UPLOAD_FOLDER,
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "database_type": db_stats.get("database_type", "none")
        }
    })

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors"""
    try:
        if not database:
            return jsonify({"error": "Database not available"}), 500
        
        vendors = database.get_all_vendors()
        return jsonify(vendors)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch vendors: {str(e)}"}), 500

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

        # Store vendor data in database
        if not database:
            return jsonify({"error": "Database not available"}), 500
        
        vendor = database.create_vendor(vendor_data)
        
        return jsonify({
            "message": "Vendor created successfully",
            "vendor": vendor
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vendors/<vendor_id>')
def get_vendor(vendor_id):
    """Get a specific vendor"""
    try:
        if not database:
            return jsonify({"error": "Database not available"}), 500
        
        vendor = database.get_vendor(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404
        
        return jsonify(vendor)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch vendor: {str(e)}"}), 500

@app.route('/api/vendors/<vendor_id>/contract')
def serve_contract(vendor_id):
    """Serve the contract file for viewing"""
    try:
        if not database:
            return jsonify({"error": "Database not available"}), 500
        
        vendor = database.get_vendor(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404
        
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
    except Exception as e:
        return jsonify({"error": f"Failed to serve contract: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)