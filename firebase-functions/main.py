import json
import os
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, storage
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import openai
import tempfile
import uuid
from datetime import datetime
import io

# Initialize Firebase Admin
initialize_app()

# Configure CORS
cors_options = options.CorsOptions(
    cors_origins="*",
    cors_methods=["POST", "GET", "OPTIONS"],
)

class OCRProcessor:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def extract_text_from_pdf(self, pdf_bytes):
        """Extract text from PDF bytes using OCR"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file_path = tmp_file.name
            
            images = convert_from_path(tmp_file_path, dpi=300)
            os.unlink(tmp_file_path)
            
            full_text = ""
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image, lang='eng')
                full_text += f"\n--- Page {i+1} ---\n{text}"
            
            return full_text.strip()
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def extract_text_from_image(self, image_bytes):
        """Extract text from image bytes using OCR"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")

class AIAnalyzer:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    def extract_contract_details(self, contract_text):
        """Extract key details from contract using GPT"""
        prompt = f"""
        Analyze the following contract text and extract key information in JSON format:
        
        Contract Text:
        {contract_text[:3000]}
        
        Extract: vendor_name, contract_number, start_date, end_date, payment_terms, 
        total_value, billing_frequency, items, special_conditions
        
        Return ONLY valid JSON.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract information and return only JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}
    
    def extract_invoice_details(self, invoice_text):
        """Extract key details from invoice using GPT"""
        prompt = f"""
        Analyze the following invoice text and extract key information in JSON format:
        
        Invoice Text:
        {invoice_text[:3000]}
        
        Extract: vendor_name, invoice_number, invoice_date, due_date, total_amount,
        subtotal, tax_amount, items, payment_terms, reference_contract_number
        
        Return ONLY valid JSON.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract information and return only JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}
    
    def compare_documents(self, contract_details, invoice_details):
        """Compare contract and invoice for discrepancies"""
        discrepancies = []
        warnings = []
        matches = []
        
        # Vendor name comparison
        if contract_details.get('vendor_name', '').lower() != invoice_details.get('vendor_name', '').lower():
            if contract_details.get('vendor_name') and invoice_details.get('vendor_name'):
                discrepancies.append({
                    "field": "Vendor Name",
                    "contract_value": contract_details.get('vendor_name'),
                    "invoice_value": invoice_details.get('vendor_name'),
                    "severity": "HIGH"
                })
        else:
            matches.append("Vendor Name")
        
        # Amount comparison
        contract_total = self._parse_amount(contract_details.get('total_value', '0'))
        invoice_total = self._parse_amount(invoice_details.get('total_amount', '0'))
        
        if contract_total and invoice_total:
            if abs(contract_total - invoice_total) > 0.01:
                discrepancies.append({
                    "field": "Total Amount",
                    "contract_value": f"${contract_total:,.2f}",
                    "invoice_value": f"${invoice_total:,.2f}",
                    "difference": f"${abs(contract_total - invoice_total):,.2f}",
                    "severity": "HIGH"
                })
            else:
                matches.append("Total Amount")
        
        return {
            "discrepancies": discrepancies,
            "warnings": warnings,
            "matches": matches,
            "summary": {
                "total_discrepancies": len(discrepancies),
                "total_warnings": len(warnings),
                "total_matches": len(matches),
                "reconciliation_status": "PASSED" if len(discrepancies) == 0 else "FAILED"
            }
        }
    
    def _parse_amount(self, amount_str):
        """Parse amount string to float"""
        if not amount_str:
            return 0
        amount_str = str(amount_str).replace('$', '').replace(',', '')
        try:
            return float(amount_str)
        except:
            return 0

# Initialize processors
ocr_processor = OCRProcessor()
ai_analyzer = AIAnalyzer()

@https_fn.on_request(cors=cors_options)
def api(req: https_fn.Request) -> https_fn.Response:
    """Main API endpoint for Firebase Functions"""
    
    path = req.path
    
    if path == "/api/health":
        return https_fn.Response(json.dumps({
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }), headers={"Content-Type": "application/json"})
    
    elif path == "/api/process" and req.method == "POST":
        try:
            # Get file data from request
            data = req.get_json()
            
            if not data or 'contract_data' not in data or 'invoice_data' not in data:
                return https_fn.Response(json.dumps({
                    "error": "Missing contract or invoice data"
                }), status=400, headers={"Content-Type": "application/json"})
            
            # Process documents
            contract_text = ocr_processor.extract_text_from_pdf(
                data['contract_data'].encode('latin-1')
            )
            invoice_text = ocr_processor.extract_text_from_pdf(
                data['invoice_data'].encode('latin-1')
            )
            
            # Extract details
            contract_details = ai_analyzer.extract_contract_details(contract_text)
            invoice_details = ai_analyzer.extract_invoice_details(invoice_text)
            
            # Compare documents
            comparison_results = ai_analyzer.compare_documents(
                contract_details, 
                invoice_details
            )
            
            return https_fn.Response(json.dumps({
                "status": "completed",
                "results": {
                    "contract_details": contract_details,
                    "invoice_details": invoice_details,
                    "comparison": comparison_results,
                    "processed_at": datetime.now().isoformat()
                }
            }), headers={"Content-Type": "application/json"})
            
        except Exception as e:
            return https_fn.Response(json.dumps({
                "error": str(e)
            }), status=500, headers={"Content-Type": "application/json"})
    
    else:
        return https_fn.Response(json.dumps({
            "error": "Endpoint not found"
        }), status=404, headers={"Content-Type": "application/json"})