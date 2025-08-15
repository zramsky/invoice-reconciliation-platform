"""
LLM Client for Unspend - Handles dual-model routing with strict JSON schemas
"""
import openai
import json
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, ValidationError
import hashlib
from datetime import datetime

class LLMClient:
    def __init__(self, small_model: str = "gpt-4o-mini", large_model: str = "gpt-4o"):
        """
        Initialize LLM client with small and large models
        
        Args:
            small_model: Fast, cheap model for initial extraction
            large_model: More capable model for escalation and reconciliation
        """
        self.small_model = small_model
        self.large_model = large_model
        self.client = None
        self.cache = {}  # Simple in-memory cache for development
        
    def set_api_key(self, api_key: str):
        """Set OpenAI API key"""
        self.client = openai.OpenAI(api_key=api_key)
    
    def call(self, 
             model: str, 
             system: str, 
             user: str, 
             json_schema: Dict[str, Any],
             temperature: float = 0.0,
             seed: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
        """
        Make LLM call with strict JSON response and auto-repair
        
        Returns:
            Tuple of (parsed_json, success_flag)
        """
        if not self.client:
            raise ValueError("API key not set. Call set_api_key() first.")
        
        # Check cache
        cache_key = hashlib.md5(f"{model}_{system}_{user}_{temperature}_{seed}".encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key], True
        
        # Prepare messages
        messages = [
            {"role": "system", "content": f"{system}\n\nIMPORTANT: Return ONLY valid JSON matching this schema. No markdown, no explanations."},
            {"role": "user", "content": user}
        ]
        
        # Add schema to user message
        schema_prompt = f"\n\nReturn JSON matching this exact schema:\n{json.dumps(json_schema, indent=2)}"
        messages[1]["content"] += schema_prompt
        
        try:
            # First attempt
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=2000,
                seed=seed
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean up response (remove markdown if present)
            if result_text.startswith("```json"):
                result_text = result_text.replace("```json", "").replace("```", "").strip()
            elif result_text.startswith("```"):
                result_text = result_text.replace("```", "").strip()
            
            # Parse JSON
            try:
                parsed_json = json.loads(result_text)
                self.cache[cache_key] = parsed_json
                return parsed_json, True
            except json.JSONDecodeError as e:
                # Auto-repair attempt
                repair_prompt = f"""
                The following JSON is invalid: {result_text}
                
                Error: {str(e)}
                
                Please fix this JSON to match the required schema exactly:
                {json.dumps(json_schema, indent=2)}
                
                Return ONLY the corrected JSON, no explanations.
                """
                
                repair_response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a JSON repair expert. Fix invalid JSON and return only valid JSON."},
                        {"role": "user", "content": repair_prompt}
                    ],
                    temperature=0.0,
                    max_tokens=2000
                )
                
                repaired_text = repair_response.choices[0].message.content.strip()
                if repaired_text.startswith("```json"):
                    repaired_text = repaired_text.replace("```json", "").replace("```", "").strip()
                elif repaired_text.startswith("```"):
                    repaired_text = repaired_text.replace("```", "").strip()
                
                try:
                    parsed_json = json.loads(repaired_text)
                    self.cache[cache_key] = parsed_json
                    return parsed_json, True
                except json.JSONDecodeError:
                    return {}, False
                    
        except Exception as e:
            print(f"LLM call failed: {str(e)}")
            return {}, False
    
    def extract_contract(self, text_or_pages: str) -> Tuple[Dict[str, Any], bool]:
        """
        Extract contract details using small model, escalate if needed
        """
        contract_schema = {
            "vendor": {"value": "", "confidence": 0.0},
            "service_category": {"value": "", "confidence": 0.0},
            "start_date": {"value": "", "confidence": 0.0},
            "end_date": {"value": "", "confidence": 0.0},
            "auto_renew": {"value": None, "confidence": 0.0},
            "renewal_notice_days": {"value": None, "confidence": 0.0},
            "price_escalation": {"value": {"type": "none", "amount": None}, "confidence": 0.0},
            "cap_total": {"value": None, "confidence": 0.0},
            "allowed_fees": {"value": [], "confidence": 0.0},
            "terms": [
                {
                    "item_code": {"value": "", "confidence": 0.0},
                    "item_desc": {"value": "", "confidence": 0.0},
                    "unit": {"value": "", "confidence": 0.0},
                    "price": {"value": None, "confidence": 0.0},
                    "min_qty": {"value": None, "confidence": 0.0},
                    "max_qty": {"value": None, "confidence": 0.0},
                    "effective_start": {"value": "", "confidence": 0.0},
                    "effective_end": {"value": "", "confidence": 0.0}
                }
            ],
            "notes": ""
        }
        
        system_prompt = """You are an extraction engine for contracts. Think step by step privately. Return only JSON that matches the schema. If a field is not explicitly present, return null and explain briefly in notes. Include a confidence from 0 to 1 for every field.

Process exactly one document. Do not infer from any other document. Read line by line, then summarize fields. If a field is not explicitly present, return null and explain briefly in notes. Perform all arithmetic step by step internally, but only return the final numbers and a short evidence block. Never guess vendor names or prices. If ambiguous, return null with a reason and low confidence."""
        
        user_prompt = f"""Return ContractSchema as strict JSON for the following text. Do not invent values. Dates must be ISO format (YYYY-MM-DD). Money must be numbers. Units must be normalized. If scanned pages are noisy, prefer clearly stated tables or schedules. 

Text: {text_or_pages[:6000]}"""
        
        # First pass with small model
        result, success = self.call(
            model=self.small_model,
            system=system_prompt,
            user=user_prompt,
            json_schema=contract_schema,
            temperature=0.0,
            seed=42
        )
        
        if not success:
            return {}, False
        
        # Check if escalation is needed
        needs_escalation = self._needs_escalation(result)
        
        if needs_escalation:
            # Retry with large model
            result, success = self.call(
                model=self.large_model,
                system=system_prompt,
                user=user_prompt,
                json_schema=contract_schema,
                temperature=0.0,
                seed=42
            )
        
        return result, success
    
    def extract_invoice(self, text_or_pages: str) -> Tuple[Dict[str, Any], bool]:
        """
        Extract invoice details using small model, escalate if needed
        """
        invoice_schema = {
            "vendor": {"value": "", "confidence": 0.0},
            "invoice_no": {"value": "", "confidence": 0.0},
            "invoice_date": {"value": "", "confidence": 0.0},
            "due_date": {"value": "", "confidence": 0.0},
            "lines": [
                {
                    "item_code": {"value": "", "confidence": 0.0},
                    "item_desc": {"value": "", "confidence": 0.0},
                    "unit": {"value": "", "confidence": 0.0},
                    "qty": {"value": None, "confidence": 0.0},
                    "unit_price": {"value": None, "confidence": 0.0},
                    "line_total": {"value": None, "confidence": 0.0},
                    "service_period_start": {"value": "", "confidence": 0.0},
                    "service_period_end": {"value": "", "confidence": 0.0}
                }
            ],
            "notes": ""
        }
        
        system_prompt = """You are an extraction engine for invoices. Think step by step privately. Return only JSON that matches the schema. If a field is not explicitly present, return null and explain briefly in notes. Include a confidence from 0 to 1 for every field.

Process exactly one document. Do not infer from any other document. Read line by line, then summarize fields. If a field is not explicitly present, return null and explain briefly in notes. Perform all arithmetic step by step internally, but only return the final numbers and a short evidence block. Never guess vendor names or prices. If ambiguous, return null with a reason and low confidence."""
        
        user_prompt = f"""Return InvoiceSchema as strict JSON for the following text. Do not invent values. Compute line_total as qty times unit_price if missing. Dates must be ISO format (YYYY-MM-DD).

Text: {text_or_pages[:6000]}"""
        
        # First pass with small model
        result, success = self.call(
            model=self.small_model,
            system=system_prompt,
            user=user_prompt,
            json_schema=invoice_schema,
            temperature=0.0,
            seed=42
        )
        
        if not success:
            return {}, False
        
        # Check if escalation is needed
        needs_escalation = self._needs_escalation(result)
        
        if needs_escalation:
            # Retry with large model
            result, success = self.call(
                model=self.large_model,
                system=system_prompt,
                user=user_prompt,
                json_schema=invoice_schema,
                temperature=0.0,
                seed=42
            )
        
        return result, success
    
    def reconcile_review(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Perform reconciliation review using large model
        """
        reconciliation_schema = {
            "matches": [
                {
                    "invoice_line_index": 0,
                    "contract_term_index": 0,
                    "match_method": "code",
                    "confidence": 0.0
                }
            ],
            "flags": [
                {
                    "type": "overpay_per_unit",
                    "severity": "error",
                    "summary": "",
                    "evidence": {
                        "contract_price": None,
                        "invoice_price": None,
                        "delta": None,
                        "clause_reference": "",
                        "service_dates": {
                            "invoice_start": "",
                            "invoice_end": "",
                            "contract_start": "",
                            "contract_end": ""
                        }
                    }
                }
            ],
            "next_payment_preview": {
                "period_start": "",
                "period_end": "",
                "items": [
                    {
                        "item_code": "",
                        "expected_qty": None,
                        "expected_unit_price": None,
                        "expected_total": None
                    }
                ],
                "subtotal": None,
                "taxes": None,
                "total": None,
                "assumptions": []
            }
        }
        
        system_prompt = """You are a reconciliation checker. Think step by step privately. Return only JSON that matches ReconciliationResult. Verify math and dates. Each flag must include a short evidence block that cites the exact numbers and any clause text provided. If you cannot justify a flag, remove it and note why in a hidden notes field."""
        
        user_prompt = f"""Given ContractSchema, InvoiceSchema, and preliminary matches, produce ReconciliationResult. Respect contract dates, caps, and escalation. If a price should be escalated, compute expected price. If a line is out of scope, say so plainly. 

Payload: {json.dumps(payload, indent=2)}"""
        
        result, success = self.call(
            model=self.large_model,
            system=system_prompt,
            user=user_prompt,
            json_schema=reconciliation_schema,
            temperature=0.2,
            seed=42
        )
        
        return result, success
    
    def _needs_escalation(self, result: Dict[str, Any]) -> bool:
        """
        Determine if result needs escalation to large model
        """
        # Check for low confidence in required fields
        required_fields = ['vendor', 'invoice_no'] if 'invoice_no' in result else ['vendor', 'service_category']
        
        for field in required_fields:
            if field in result and isinstance(result[field], dict):
                confidence = result[field].get('confidence', 0.0)
                if confidence < 0.7:
                    return True
        
        # Check for math mismatches in invoice lines
        if 'lines' in result:
            for line in result['lines']:
                if isinstance(line, dict):
                    qty = line.get('qty', {}).get('value')
                    unit_price = line.get('unit_price', {}).get('value')
                    line_total = line.get('line_total', {}).get('value')
                    
                    if qty and unit_price and line_total:
                        expected_total = float(qty) * float(unit_price)
                        if abs(expected_total - float(line_total)) > 0.01:
                            return True
        
        return False