"""
LLM Client for Unspend - Handles dual-model routing with strict JSON schemas
Enhanced with async processing, connection pooling, and advanced error handling
"""
import openai
import json
import asyncio
import time
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, ValidationError
import hashlib
from datetime import datetime, timedelta
import logging
from contextlib import asynccontextmanager
from functools import wraps
import threading
from dataclasses import dataclass, field
from cache_manager import create_cache_manager, MultiLayerCache

@dataclass
class LLMMetrics:
    """Track LLM performance metrics"""
    total_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    error_count: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

@dataclass 
class LLMRequest:
    """Structured LLM request"""
    model: str
    system: str
    user: str
    json_schema: Dict[str, Any]
    temperature: float = 0.0
    seed: Optional[int] = None
    max_tokens: int = 2000
    timeout: float = 30.0

class LLMConnectionPool:
    """Manage multiple OpenAI client connections for better throughput"""
    
    def __init__(self, api_key: str, pool_size: int = 3):
        self.api_key = api_key
        self.pool_size = pool_size
        self.clients = []
        self.available_clients = []
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            try:
                client = openai.OpenAI(api_key=self.api_key)
                self.clients.append(client)
                self.available_clients.append(client)
            except Exception as e:
                logging.error(f"Failed to initialize OpenAI client: {e}")
    
    @asynccontextmanager
    async def get_client(self):
        """Get an available client from the pool"""
        while True:
            with self.lock:
                if self.available_clients:
                    client = self.available_clients.pop()
                    break
            # Wait a bit if no clients available
            await asyncio.sleep(0.1)
        
        try:
            yield client
        finally:
            with self.lock:
                self.available_clients.append(client)

class LLMClient:
    def __init__(self, small_model: str = "gpt-4o-mini", large_model: str = "gpt-4o", pool_size: int = 3):
        """
        Initialize enhanced LLM client with connection pooling and metrics
        
        Args:
            small_model: Fast, cheap model for initial extraction
            large_model: More capable model for escalation and reconciliation
            pool_size: Number of concurrent OpenAI connections to maintain
        """
        self.small_model = small_model
        self.large_model = large_model
        self.pool_size = pool_size
        self.connection_pool = None
        self.client = None  # Legacy single client for backwards compatibility
        self.cache = {}  # Legacy in-memory cache for backwards compatibility
        self.database = None  # Will be set via set_database()
        self.cache_manager = create_cache_manager()  # Advanced multi-layer cache
        self.metrics = LLMMetrics()
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting
        self.rate_limit_requests = 60  # requests per minute
        self.rate_limit_window = 60  # seconds
        self.request_times = []
        
        # Token counting for cost tracking
        self.token_costs = {
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},  # per 1K tokens
            "gpt-4o": {"input": 0.0025, "output": 0.01}
        }
        
    def set_api_key(self, api_key: str):
        """Set OpenAI API key and initialize connection pool"""
        try:
            self.client = openai.OpenAI(api_key=api_key)
            self.connection_pool = LLMConnectionPool(api_key, self.pool_size)
            self.logger.info(f"Initialized LLM client with {self.pool_size} connections")
        except Exception as e:
            self.logger.error(f"OpenAI client initialization failed: {e}")
            self.client = None
            self.connection_pool = None
    
    def set_database(self, database):
        """Set database for caching"""
        self.database = database
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = time.time()
        # Clean old requests outside the window
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_window]
        
        if len(self.request_times) >= self.rate_limit_requests:
            return False
        
        self.request_times.append(now)
        return True
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost for API call"""
        if model not in self.token_costs:
            return 0.0
        
        costs = self.token_costs[model]
        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (completion_tokens / 1000) * costs["output"]
        return input_cost + output_cost
    
    def _update_metrics(self, response_time: float, tokens: int, cost: float, is_cache_hit: bool, is_error: bool = False):
        """Update performance metrics"""
        self.metrics.total_calls += 1
        if is_cache_hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
        
        if is_error:
            self.metrics.error_count += 1
        else:
            self.metrics.total_tokens += tokens
            self.metrics.total_cost += cost
            
            # Update rolling average response time
            if self.metrics.total_calls > 1:
                self.metrics.avg_response_time = (
                    (self.metrics.avg_response_time * (self.metrics.total_calls - 1) + response_time) / 
                    self.metrics.total_calls
                )
            else:
                self.metrics.avg_response_time = response_time
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        cache_hit_rate = self.metrics.cache_hits / max(1, self.metrics.total_calls)
        error_rate = self.metrics.error_count / max(1, self.metrics.total_calls)
        
        return {
            "total_calls": self.metrics.total_calls,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "error_rate": round(error_rate, 3),
            "total_tokens": self.metrics.total_tokens,
            "total_cost": round(self.metrics.total_cost, 4),
            "avg_response_time": round(self.metrics.avg_response_time, 2),
            "uptime_hours": (datetime.now() - self.metrics.last_reset).total_seconds() / 3600
        }
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics = LLMMetrics()
        self.logger.info("LLM metrics reset")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        cache_stats = self.cache_manager.get_stats()
        return {
            "advanced_cache": cache_stats,
            "legacy_cache_size": len(self.cache),
            "database_cache_enabled": self.database is not None
        }
    
    def clear_cache(self, pattern: str = "*") -> bool:
        """Clear cache entries matching pattern"""
        try:
            if pattern == "*":
                self.cache_manager.clear()
                self.cache.clear()
                if self.database:
                    # Clear database cache if method exists
                    if hasattr(self.database, 'clear_cache'):
                        self.database.clear_cache()
                return True
            else:
                # Clear specific patterns (not implemented in legacy caches)
                return False
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")
            return False
    
    def cache_maintenance(self):
        """Perform cache maintenance tasks"""
        try:
            self.cache_manager.maintenance()
            self.logger.info("Cache maintenance completed")
        except Exception as e:
            self.logger.error(f"Cache maintenance error: {e}")
    
    def preload_cache(self, common_requests: List[LLMRequest]):
        """Preload cache with common requests for better performance"""
        async def _preload():
            for request in common_requests:
                try:
                    await self.call_async(request)
                    self.logger.debug(f"Preloaded cache for model: {request.model}")
                except Exception as e:
                    self.logger.warning(f"Failed to preload cache: {e}")
        
        # Run preloading in background
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_preload())
        except RuntimeError:
            # No event loop running, skip preloading
            self.logger.warning("No event loop available for cache preloading")
    
    async def call_async(self, request: LLMRequest) -> Tuple[Dict[str, Any], bool]:
        """
        Async LLM call with connection pooling and enhanced error handling
        """
        if not self.connection_pool:
            return await self._call_sync_fallback(request)
        
        start_time = time.time()
        
        # Check rate limits
        if not self._check_rate_limit():
            self.logger.warning("Rate limit exceeded, waiting...")
            await asyncio.sleep(1)
            if not self._check_rate_limit():
                self._update_metrics(0, 0, 0, False, True)
                raise Exception("Rate limit exceeded")
        
        # Check cache first
        cache_key = self._generate_cache_key(request)
        cached_response = await self._get_cached_response(cache_key)
        if cached_response:
            response_time = time.time() - start_time
            self._update_metrics(response_time, 0, 0, True)
            return cached_response, True
        
        # Make API call with connection pool
        try:
            async with self.connection_pool.get_client() as client:
                response = await self._make_api_call(client, request)
                
                if response:
                    # Cache successful response
                    await self._cache_response(cache_key, request, response)
                    
                    # Update metrics
                    response_time = time.time() - start_time
                    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                    cost = self._calculate_cost(
                        request.model, 
                        response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                        response.usage.completion_tokens if hasattr(response, 'usage') else 0
                    )
                    self._update_metrics(response_time, tokens, cost, False)
                    
                    return self._parse_response(response), True
                
        except Exception as e:
            self.logger.error(f"Async API call failed: {e}")
            response_time = time.time() - start_time
            self._update_metrics(response_time, 0, 0, False, True)
            
        return {}, False
    
    def _generate_cache_key(self, request: LLMRequest) -> str:
        """Generate cache key for request"""
        return hashlib.md5(
            f"{request.model}_{request.system}_{request.user}_{request.temperature}_{request.seed}".encode()
        ).hexdigest()
    
    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response async with multi-layer cache"""
        # Try advanced cache manager first
        cached_response = self.cache_manager.get(cache_key)
        if cached_response:
            return cached_response
        
        # Fallback to database cache for backwards compatibility
        if self.database:
            cached_response = self.database.get_cached_llm_response(cache_key)
            if cached_response:
                # Promote to cache manager
                self.cache_manager.set(cache_key, cached_response, ttl=3600)  # 1 hour TTL
                return cached_response
        
        # Final fallback to legacy in-memory cache
        return self.cache.get(cache_key)
    
    async def _cache_response(self, cache_key: str, request: LLMRequest, response: Dict[str, Any]):
        """Cache response async with advanced caching"""
        # Cache in advanced cache manager with appropriate TTL
        cache_ttl = 3600  # 1 hour default
        if "extract" in request.system.lower():
            cache_ttl = 86400  # 24 hours for extractions (more stable)
        elif "reconcile" in request.system.lower():
            cache_ttl = 1800   # 30 minutes for reconciliation (more dynamic)
        
        self.cache_manager.set(cache_key, response, ttl=cache_ttl)
        
        # Also cache in legacy systems for backwards compatibility
        self.cache[cache_key] = response
        if self.database:
            prompt_hash = hashlib.md5(f"{request.system}_{request.user}".encode()).hexdigest()
            self.database.cache_llm_response(cache_key, request.model, prompt_hash, response)
    
    async def _make_api_call(self, client, request: LLMRequest):
        """Make actual API call async"""
        messages = [
            {"role": "system", "content": f"{request.system}\n\nIMPORTANT: Return ONLY valid JSON matching this schema. No markdown, no explanations."},
            {"role": "user", "content": f"{request.user}\n\nReturn JSON matching this exact schema:\n{json.dumps(request.json_schema, indent=2)}"}
        ]
        
        try:
            response = client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                seed=request.seed,
                timeout=request.timeout
            )
            return response
        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {e}")
            return None
    
    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse and clean API response"""
        result_text = response.choices[0].message.content.strip()
        
        # Clean up response (remove markdown if present)
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"):
            result_text = result_text.replace("```", "").strip()
        
        try:
            return json.loads(result_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return {}
    
    async def _call_sync_fallback(self, request: LLMRequest) -> Tuple[Dict[str, Any], bool]:
        """Fallback to synchronous call when connection pool unavailable"""
        return self.call(
            request.model, request.system, request.user, 
            request.json_schema, request.temperature, request.seed
        )
    
    def call(self, 
             model: str, 
             system: str, 
             user: str, 
             json_schema: Dict[str, Any],
             temperature: float = 0.0,
             seed: Optional[int] = None) -> Tuple[Dict[str, Any], bool]:
        """
        Legacy synchronous LLM call with strict JSON response and auto-repair
        Maintained for backwards compatibility
        
        Returns:
            Tuple of (parsed_json, success_flag)
        """
        if not self.client:
            raise ValueError("API key not set. Call set_api_key() first.")
        
        # Check cache (database first, then in-memory)
        cache_key = hashlib.md5(f"{model}_{system}_{user}_{temperature}_{seed}".encode()).hexdigest()
        
        # Try database cache first
        if self.database:
            cached_response = self.database.get_cached_llm_response(cache_key)
            if cached_response:
                return cached_response, True
        
        # Fallback to in-memory cache
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
                
                # Cache in both places
                self.cache[cache_key] = parsed_json
                if self.database:
                    prompt_hash = hashlib.md5(f"{system}_{user}".encode()).hexdigest()
                    self.database.cache_llm_response(cache_key, model, prompt_hash, parsed_json)
                
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
                    
                    # Cache repaired result
                    self.cache[cache_key] = parsed_json
                    if self.database:
                        prompt_hash = hashlib.md5(f"{system}_{user}".encode()).hexdigest()
                        self.database.cache_llm_response(cache_key, model, prompt_hash, parsed_json)
                    
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