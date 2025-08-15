import openai
import json
import re
from datetime import datetime

class AIAnalyzer:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key) if api_key else None
    
    def extract_contract_details(self, contract_text):
        """Extract key details from contract using GPT"""
        prompt = f"""
        Analyze the following contract text and extract key information in JSON format.
        
        Contract Text:
        {contract_text[:4000]}
        
        IMPORTANT INSTRUCTIONS:
        1. For vendor_name: Find the actual company/vendor name providing services (NOT the client). Look for company names with suffixes like Inc, LLC, Corp, Ltd, Company. The vendor is the party PROVIDING services.
        2. For business_type: Determine what type of services the vendor provides based on the contract context.
        3. For service_description: Provide a brief 1-2 sentence description of what services the vendor will provide.
        
        Extract the following information:
        - vendor_name (the service provider company name, e.g., "Acme Technologies Inc")
        - business_type (e.g., "Technology Services", "Consulting Services", "Marketing Services")
        - service_description (brief description of services being provided)
        - contract_number
        - start_date
        - end_date
        - payment_terms
        - total_value
        - billing_frequency
        - items (list of items/services with descriptions and prices)
        - special_conditions
        
        Return ONLY valid JSON without any markdown formatting or backticks.
        """
        
        try:
            if not self.client:
                return self._fallback_extraction(contract_text, "contract")
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a contract analysis expert specializing in vendor identification and service classification. Extract the vendor/supplier name (the party PROVIDING services), not the client name. Return only valid JSON without markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            result = response.choices[0].message.content
            return json.loads(result)
        except Exception as e:
            print(f"AI extraction error: {str(e)}")
            return self._fallback_extraction(contract_text, "contract")
    
    def extract_invoice_details(self, invoice_text):
        """Extract key details from invoice using GPT"""
        prompt = f"""
        Analyze the following invoice text and extract key information in JSON format:
        
        Invoice Text:
        {invoice_text[:3000]}
        
        Extract the following information:
        - vendor_name
        - invoice_number
        - invoice_date
        - due_date
        - total_amount
        - subtotal
        - tax_amount
        - items (list with description, quantity, unit_price, total)
        - payment_terms
        - reference_contract_number (if mentioned)
        
        Return ONLY valid JSON without any markdown formatting.
        """
        
        try:
            if not self.client:
                return self._fallback_extraction(invoice_text, "invoice")
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an invoice analysis expert. Extract information accurately and return only JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            result = response.choices[0].message.content
            return json.loads(result)
        except Exception as e:
            print(f"AI extraction error: {str(e)}")
            return self._fallback_extraction(invoice_text, "invoice")
    
    def _fallback_extraction(self, text, doc_type):
        """Fallback extraction using regex patterns"""
        extracted = {}
        
        amount_pattern = r'\$?[\d,]+\.?\d*'
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        
        amounts = re.findall(amount_pattern, text)
        dates = re.findall(date_pattern, text)
        
        if doc_type == "invoice":
            extracted = {
                "vendor_name": "Unknown",
                "invoice_number": re.search(r'Invoice\s*#?\s*(\w+)', text, re.I),
                "invoice_date": dates[0] if dates else None,
                "total_amount": amounts[0] if amounts else "0",
                "items": []
            }
        else:
            extracted = {
                "vendor_name": "Unknown",
                "business_type": "General Services",
                "service_description": "Services as per contract",
                "contract_number": re.search(r'Contract\s*#?\s*(\w+)', text, re.I),
                "total_value": amounts[0] if amounts else "0",
                "items": []
            }
        
        return extracted
    
    def compare_documents(self, contract_details, invoice_details):
        """Compare contract and invoice for discrepancies"""
        discrepancies = []
        warnings = []
        matches = []
        
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
        
        if invoice_details.get('reference_contract_number'):
            if invoice_details['reference_contract_number'] != contract_details.get('contract_number'):
                warnings.append({
                    "field": "Contract Reference",
                    "message": f"Invoice references contract {invoice_details['reference_contract_number']}, but provided contract is {contract_details.get('contract_number')}",
                    "severity": "MEDIUM"
                })
        
        contract_items = contract_details.get('items', [])
        invoice_items = invoice_details.get('items', [])
        
        if len(invoice_items) > len(contract_items):
            warnings.append({
                "field": "Items Count",
                "message": f"Invoice has {len(invoice_items)} items, contract has {len(contract_items)} items",
                "severity": "MEDIUM"
            })
        
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