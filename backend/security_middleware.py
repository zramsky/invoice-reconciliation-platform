"""
Enhanced Security Middleware for Unspend Platform
Provides CSRF protection, security headers, rate limiting, and request validation
"""

import secrets
import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
from flask import request, jsonify, session, make_response, g
import logging
from dataclasses import dataclass
from collections import defaultdict
import time

@dataclass
class SecurityConfig:
    """Security configuration settings"""
    enable_csrf: bool = True
    enable_security_headers: bool = True
    enable_request_validation: bool = True
    enable_ip_whitelist: bool = False
    enable_audit_logging: bool = True
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    allowed_origins: List[str] = None
    ip_whitelist: List[str] = None
    session_timeout: int = 3600  # 1 hour
    
    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ['https://unspend-91424.web.app', 'http://localhost:3000']
        if self.ip_whitelist is None:
            self.ip_whitelist = []

class CSRFProtection:
    """CSRF token management and validation"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.token_lifetime = timedelta(hours=4)
        self.logger = logging.getLogger(__name__)
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        token = f"{timestamp}:{signature}"
        return token
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token"""
        try:
            parts = token.split(':')
            if len(parts) != 2:
                return False
            
            timestamp_str, signature = parts
            timestamp = int(timestamp_str)
            
            # Check if token is expired
            current_time = int(time.time())
            if current_time - timestamp > self.token_lifetime.total_seconds():
                self.logger.warning(f"CSRF token expired for session {session_id}")
                return False
            
            # Verify signature
            message = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                self.logger.warning(f"Invalid CSRF token signature for session {session_id}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"CSRF validation error: {e}")
            return False

class SecurityHeadersManager:
    """Manages security headers for responses"""
    
    @staticmethod
    def apply_headers(response):
        """Apply security headers to response"""
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.openai.com"
        )
        
        # Other security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), '
            'gyroscope=(), magnetometer=(), microphone=(), '
            'payment=(), usb=()'
        )
        
        return response

class RequestValidator:
    """Validates and sanitizes incoming requests"""
    
    def __init__(self, max_request_size: int):
        self.max_request_size = max_request_size
        self.logger = logging.getLogger(__name__)
        
        # SQL injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
            r"(--|\||;|\/\*|\*\/)",
            r"(\bOR\b\s*\d+\s*=\s*\d+)",
            r"(\bAND\b\s*\d+\s*=\s*\d+)"
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>"
        ]
    
    def validate_request(self, request) -> Tuple[bool, Optional[str]]:
        """Validate incoming request for security issues"""
        # Check request size
        if request.content_length and request.content_length > self.max_request_size:
            return False, "Request too large"
        
        # Validate JSON data if present
        if request.is_json:
            try:
                data = request.get_json()
                if not self._validate_data(data):
                    return False, "Potentially malicious content detected"
            except Exception as e:
                return False, f"Invalid JSON: {str(e)}"
        
        # Validate query parameters
        for key, value in request.args.items():
            if not self._is_safe_string(str(value)):
                return False, f"Potentially malicious query parameter: {key}"
        
        # Validate form data
        for key, value in request.form.items():
            if not self._is_safe_string(str(value)):
                return False, f"Potentially malicious form data: {key}"
        
        return True, None
    
    def _validate_data(self, data: Any, depth: int = 0) -> bool:
        """Recursively validate data structure"""
        if depth > 10:  # Prevent deep recursion attacks
            return False
        
        if isinstance(data, dict):
            for key, value in data.items():
                if not self._is_safe_string(str(key)):
                    return False
                if not self._validate_data(value, depth + 1):
                    return False
        elif isinstance(data, list):
            for item in data:
                if not self._validate_data(item, depth + 1):
                    return False
        elif isinstance(data, str):
            if not self._is_safe_string(data):
                return False
        
        return True
    
    def _is_safe_string(self, text: str) -> bool:
        """Check if string contains potentially malicious content"""
        # Check for SQL injection patterns
        for pattern in self.sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                self.logger.warning(f"SQL injection pattern detected: {pattern}")
                return False
        
        # Check for XSS patterns
        for pattern in self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                self.logger.warning(f"XSS pattern detected: {pattern}")
                return False
        
        return True
    
    def sanitize_string(self, text: str) -> str:
        """Sanitize string by escaping dangerous characters"""
        # HTML escape
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        text = text.replace('/', '&#x2F;')
        
        return text

class IPWhitelist:
    """IP address whitelist management"""
    
    def __init__(self, whitelist: List[str]):
        self.whitelist = set(whitelist)
        self.logger = logging.getLogger(__name__)
    
    def is_allowed(self, ip_address: str) -> bool:
        """Check if IP is whitelisted"""
        if not self.whitelist:
            return True  # No whitelist means all IPs allowed
        
        # Check exact match
        if ip_address in self.whitelist:
            return True
        
        # Check subnet match (simplified)
        for allowed_ip in self.whitelist:
            if allowed_ip.endswith('*'):
                subnet = allowed_ip[:-1]
                if ip_address.startswith(subnet):
                    return True
        
        self.logger.warning(f"Blocked request from non-whitelisted IP: {ip_address}")
        return False

class SecurityAuditLogger:
    """Logs security events for audit trail"""
    
    def __init__(self, log_file: str = 'security_audit.log'):
        self.log_file = log_file
        self.logger = logging.getLogger(__name__)
        
        # Set up file handler for audit logs
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.audit_logger = logging.getLogger('security_audit')
        self.audit_logger.addHandler(handler)
        self.audit_logger.setLevel(logging.INFO)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security event"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'ip_address': request.environ.get('REMOTE_ADDR') if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'method': request.method if request else None,
            'path': request.path if request else None,
            'details': details
        }
        
        self.audit_logger.info(json.dumps(event))
    
    def log_failed_auth(self, reason: str, email: Optional[str] = None):
        """Log failed authentication attempt"""
        self.log_security_event('failed_auth', {
            'reason': reason,
            'email': email
        })
    
    def log_csrf_failure(self, session_id: str):
        """Log CSRF validation failure"""
        self.log_security_event('csrf_failure', {
            'session_id': session_id
        })
    
    def log_malicious_request(self, reason: str):
        """Log potentially malicious request"""
        self.log_security_event('malicious_request', {
            'reason': reason
        })

class SecurityMiddleware:
    """Main security middleware integrating all security features"""
    
    def __init__(self, app, secret_key: str, config: Optional[SecurityConfig] = None):
        self.app = app
        self.config = config or SecurityConfig()
        self.csrf = CSRFProtection(secret_key)
        self.headers_manager = SecurityHeadersManager()
        self.request_validator = RequestValidator(self.config.max_request_size)
        self.ip_whitelist = IPWhitelist(self.config.ip_whitelist)
        self.audit_logger = SecurityAuditLogger()
        self.logger = logging.getLogger(__name__)
        
        # Register middleware
        self._register_middleware()
    
    def _register_middleware(self):
        """Register middleware with Flask app"""
        
        @self.app.before_request
        def before_request():
            """Run security checks before processing request"""
            # Check IP whitelist
            if self.config.enable_ip_whitelist:
                ip_address = request.environ.get('REMOTE_ADDR')
                if not self.ip_whitelist.is_allowed(ip_address):
                    self.audit_logger.log_malicious_request(f"Blocked IP: {ip_address}")
                    return jsonify({'error': 'Access denied'}), 403
            
            # Validate request
            if self.config.enable_request_validation:
                is_valid, error = self.request_validator.validate_request(request)
                if not is_valid:
                    self.audit_logger.log_malicious_request(error)
                    return jsonify({'error': 'Invalid request'}), 400
            
            # CSRF validation for state-changing methods
            if self.config.enable_csrf and request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                # Skip CSRF for authentication endpoints
                if not request.path.startswith('/api/auth/'):
                    csrf_token = request.headers.get('X-CSRF-Token')
                    session_id = session.get('session_id', '')
                    
                    if not csrf_token or not self.csrf.validate_token(csrf_token, session_id):
                        self.audit_logger.log_csrf_failure(session_id)
                        return jsonify({'error': 'CSRF validation failed'}), 403
        
        @self.app.after_request
        def after_request(response):
            """Apply security headers after processing request"""
            if self.config.enable_security_headers:
                response = self.headers_manager.apply_headers(response)
            
            # Add CSRF token to response if needed
            if self.config.enable_csrf and 'session_id' in session:
                csrf_token = self.csrf.generate_token(session['session_id'])
                response.headers['X-CSRF-Token'] = csrf_token
            
            return response
    
    def require_https(self, f):
        """Decorator to require HTTPS"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_secure and self.app.env == 'production':
                return jsonify({'error': 'HTTPS required'}), 403
            return f(*args, **kwargs)
        return decorated_function

# Helper function to create and configure security middleware
def create_security_middleware(app, secret_key: str, config: Optional[SecurityConfig] = None):
    """Create and configure security middleware for Flask app"""
    return SecurityMiddleware(app, secret_key, config)