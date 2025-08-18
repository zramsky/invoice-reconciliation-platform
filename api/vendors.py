from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime
import tempfile

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration for Vercel serverless
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'doc', 'docx', 'txt'}

# In-memory storage for serverless (you'd use a database in production)
vendors_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

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

        # Handle file upload (simplified for serverless)
        if 'contract_file' in request.files:
            contract_file = request.files['contract_file']
            if contract_file and contract_file.filename and allowed_file(contract_file.filename):
                # Store file content in vendor data (base64 encoded for simplicity)
                import base64
                file_content = base64.b64encode(contract_file.read()).decode('utf-8')
                vendor_data["contract_file_content"] = file_content
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
    if not vendor.get('contract_file_content'):
        return jsonify({"error": "Contract file not found"}), 404
    
    # Decode base64 content and serve
    import base64
    from io import BytesIO
    from flask import Response
    
    file_content = base64.b64decode(vendor['contract_file_content'])
    filename = vendor.get('contract_filename', 'contract.txt')
    
    # Determine content type
    if filename.lower().endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        mimetype = 'image/jpeg'
    else:
        mimetype = 'text/plain'
    
    return Response(
        file_content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

# Vercel serverless function entry point
def handler(request):
    return app(request.environ, lambda status, headers: None)

if __name__ == '__main__':
    app.run(debug=True)