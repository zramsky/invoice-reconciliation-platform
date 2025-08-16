"""
API Middleware for Unspend - Error handling, rate limiting, and request/response logging
"""
import time
import json
import logging
import traceback
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
from flask import request, jsonify, g
import hashlib

@dataclass
class RateLimitRule:
    """Rate limiting rule configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_allowance: int = 10  # Allow short bursts

@dataclass
class ClientMetrics:
    """Track metrics per client"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_request: Optional[datetime] = None
    avg_response_time: float = 0.0
    rate_limit_violations: int = 0

class RateLimiter:
    """Advanced rate limiter with multiple time windows"""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: {
                'minute': deque(),
                'hour': deque(),
                'day': deque(),
                'burst': deque()
            }
        )
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def is_allowed(self, client_id: str, rule: RateLimitRule) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed under rate limits"""
        with self.lock:
            now = time.time()
            client_queues = self.clients[client_id]
            
            # Clean old entries
            self._cleanup_old_entries(client_queues, now)
            
            # Check limits
            violations = []
            
            # Check burst limit (last 10 seconds)
            if len(client_queues['burst']) >= rule.burst_allowance:
                violations.append('burst_limit_exceeded')
            
            # Check minute limit
            if len(client_queues['minute']) >= rule.requests_per_minute:
                violations.append('minute_limit_exceeded')
            
            # Check hour limit
            if len(client_queues['hour']) >= rule.requests_per_hour:
                violations.append('hour_limit_exceeded')
            
            # Check day limit
            if len(client_queues['day']) >= rule.requests_per_day:
                violations.append('day_limit_exceeded')
            
            if violations:
                return False, {
                    'violations': violations,
                    'retry_after': self._calculate_retry_after(client_queues, rule),
                    'current_usage': {
                        'minute': len(client_queues['minute']),
                        'hour': len(client_queues['hour']),
                        'day': len(client_queues['day'])
                    }
                }
            
            # Record the request
            for queue in client_queues.values():
                queue.append(now)
            
            return True, {
                'current_usage': {
                    'minute': len(client_queues['minute']),
                    'hour': len(client_queues['hour']),
                    'day': len(client_queues['day'])
                }
            }
    
    def _cleanup_old_entries(self, queues: Dict[str, deque], now: float):
        """Remove old entries from rate limit queues"""
        # Burst window (10 seconds)
        while queues['burst'] and now - queues['burst'][0] > 10:
            queues['burst'].popleft()
        
        # Minute window
        while queues['minute'] and now - queues['minute'][0] > 60:
            queues['minute'].popleft()
        
        # Hour window
        while queues['hour'] and now - queues['hour'][0] > 3600:
            queues['hour'].popleft()
        
        # Day window
        while queues['day'] and now - queues['day'][0] > 86400:
            queues['day'].popleft()
    
    def _calculate_retry_after(self, queues: Dict[str, deque], rule: RateLimitRule) -> int:
        """Calculate how long client should wait before retrying"""
        now = time.time()
        
        # Find the earliest time when a limit would be lifted
        retry_times = []
        
        if len(queues['minute']) >= rule.requests_per_minute and queues['minute']:
            retry_times.append(queues['minute'][0] + 60)
        
        if len(queues['hour']) >= rule.requests_per_hour and queues['hour']:
            retry_times.append(queues['hour'][0] + 3600)
        
        if retry_times:
            return max(1, int(min(retry_times) - now))
        
        return 60  # Default 1 minute

class APIErrorHandler:
    """Centralized error handling for API endpoints"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_counts = defaultdict(int)
        self.lock = threading.RLock()
    
    def handle_error(self, error: Exception, endpoint: str = None) -> tuple[Dict[str, Any], int]:
        """Handle API errors and return appropriate response"""
        with self.lock:
            error_type = type(error).__name__
            self.error_counts[error_type] += 1
        
        # Log the error
        self.logger.error(f"API Error in {endpoint}: {error}", exc_info=True)
        
        # Determine response based on error type
        if isinstance(error, ValueError):
            return {
                "error": "Invalid input",
                "message": str(error),
                "error_type": "validation_error",
                "timestamp": datetime.now().isoformat()
            }, 400
        
        elif isinstance(error, FileNotFoundError):
            return {
                "error": "Resource not found",
                "message": "The requested resource could not be found",
                "error_type": "not_found",
                "timestamp": datetime.now().isoformat()
            }, 404
        
        elif isinstance(error, PermissionError):
            return {
                "error": "Access denied",
                "message": "Insufficient permissions to access this resource",
                "error_type": "permission_error",
                "timestamp": datetime.now().isoformat()
            }, 403
        
        elif isinstance(error, TimeoutError):
            return {
                "error": "Request timeout",
                "message": "The request took too long to process",
                "error_type": "timeout_error",
                "timestamp": datetime.now().isoformat()
            }, 504
        
        else:
            # Generic server error
            return {
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "error_type": "internal_error",
                "error_id": hashlib.md5(str(error).encode()).hexdigest()[:8],
                "timestamp": datetime.now().isoformat()
            }, 500
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        with self.lock:
            return dict(self.error_counts)

class RequestLogger:
    """Request and response logging with metrics"""
    
    def __init__(self, max_log_entries: int = 10000):
        self.max_log_entries = max_log_entries
        self.request_logs = deque(maxlen=max_log_entries)
        self.client_metrics: Dict[str, ClientMetrics] = defaultdict(ClientMetrics)
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def log_request(self, request_data: Dict[str, Any], response_data: Dict[str, Any], 
                   response_time: float, status_code: int, client_id: str):
        """Log request/response with metrics"""
        with self.lock:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'client_id': client_id,
                'method': request_data.get('method'),
                'endpoint': request_data.get('endpoint'),
                'request_size': len(json.dumps(request_data.get('body', {}), default=str)),
                'response_size': len(json.dumps(response_data, default=str)),
                'response_time_ms': round(response_time * 1000, 2),
                'status_code': status_code,
                'user_agent': request_data.get('user_agent'),
                'ip_address': request_data.get('ip_address')
            }
            
            self.request_logs.append(log_entry)
            
            # Update client metrics
            metrics = self.client_metrics[client_id]
            metrics.total_requests += 1
            metrics.last_request = datetime.now()
            
            if status_code < 400:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
            
            # Update rolling average response time
            if metrics.total_requests > 1:
                metrics.avg_response_time = (
                    (metrics.avg_response_time * (metrics.total_requests - 1) + response_time) / 
                    metrics.total_requests
                )
            else:
                metrics.avg_response_time = response_time
    
    def get_metrics(self, client_id: str = None) -> Dict[str, Any]:
        """Get request metrics"""
        with self.lock:
            if client_id:
                metrics = self.client_metrics.get(client_id, ClientMetrics())
                return {
                    'total_requests': metrics.total_requests,
                    'successful_requests': metrics.successful_requests,
                    'failed_requests': metrics.failed_requests,
                    'success_rate': metrics.successful_requests / max(1, metrics.total_requests),
                    'avg_response_time': round(metrics.avg_response_time, 3),
                    'last_request': metrics.last_request.isoformat() if metrics.last_request else None
                }
            else:
                # Aggregate metrics
                total_requests = sum(m.total_requests for m in self.client_metrics.values())
                successful_requests = sum(m.successful_requests for m in self.client_metrics.values())
                
                return {
                    'total_clients': len(self.client_metrics),
                    'total_requests': total_requests,
                    'successful_requests': successful_requests,
                    'failed_requests': total_requests - successful_requests,
                    'success_rate': successful_requests / max(1, total_requests),
                    'total_log_entries': len(self.request_logs)
                }

# Global instances
rate_limiter = RateLimiter()
error_handler = APIErrorHandler()
request_logger = RequestLogger()

def get_client_id() -> str:
    """Extract client ID from request"""
    # Use API key if available, otherwise use IP address
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return hashlib.md5(api_key.encode()).hexdigest()[:16]
    
    # Fallback to IP address
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ['REMOTE_ADDR'])
    return hashlib.md5(ip.encode()).hexdigest()[:16]

def with_rate_limiting(rule: RateLimitRule = None):
    """Decorator for rate limiting endpoints"""
    if rule is None:
        rule = RateLimitRule()
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_id = get_client_id()
            allowed, info = rate_limiter.is_allowed(client_id, rule)
            
            if not allowed:
                request_logger.client_metrics[client_id].rate_limit_violations += 1
                response = {
                    "error": "Rate limit exceeded",
                    "violations": info['violations'],
                    "retry_after": info['retry_after'],
                    "current_usage": info['current_usage']
                }
                return jsonify(response), 429
            
            # Add rate limit info to response headers
            g.rate_limit_info = info['current_usage']
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def with_error_handling(f):
    """Decorator for centralized error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        client_id = get_client_id()
        
        request_data = {
            'method': request.method,
            'endpoint': request.endpoint,
            'body': request.get_json() if request.is_json else {},
            'user_agent': request.headers.get('User-Agent'),
            'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ['REMOTE_ADDR'])
        }
        
        try:
            response = f(*args, **kwargs)
            response_time = time.time() - start_time
            
            # Handle different response types
            from flask import Response
            if isinstance(response, Response):
                status_code = response.status_code
                response_data = response.get_json() if hasattr(response, 'get_json') and response.get_json() else {"success": True}
            elif isinstance(response, tuple):
                response_data, status_code = response[0], response[1] if len(response) > 1 else 200
            else:
                response_data = response
                status_code = 200
            
            # Log successful request
            request_logger.log_request(request_data, response_data, response_time, status_code, client_id)
            
            # Add metrics headers if available
            if hasattr(g, 'rate_limit_info'):
                from flask import make_response, Response
                
                if isinstance(response, tuple):
                    # Convert to Flask response object to add headers
                    flask_response = make_response(jsonify(response_data), status_code)
                    flask_response.headers['X-RateLimit-Remaining-Minute'] = str(60 - g.rate_limit_info['minute'])
                    flask_response.headers['X-RateLimit-Remaining-Hour'] = str(1000 - g.rate_limit_info['hour'])
                    return flask_response
                elif isinstance(response, Response):
                    # Response is already a Flask Response object, add headers directly
                    response.headers['X-RateLimit-Remaining-Minute'] = str(60 - g.rate_limit_info['minute'])
                    response.headers['X-RateLimit-Remaining-Hour'] = str(1000 - g.rate_limit_info['hour'])
                    return response
            
            return response
            
        except Exception as e:
            response_time = time.time() - start_time
            error_response, status_code = error_handler.handle_error(e, request.endpoint)
            
            # Log failed request
            request_logger.log_request(request_data, error_response, response_time, status_code, client_id)
            
            return jsonify(error_response), status_code
    
    return decorated_function

def create_api_middleware():
    """Factory function to create API middleware instances"""
    return {
        'rate_limiter': rate_limiter,
        'error_handler': error_handler,
        'request_logger': request_logger
    }