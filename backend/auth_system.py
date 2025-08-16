"""
User Authentication and Session Management for Unspend
Handles user accounts, login/logout, and data persistence per user
"""
import bcrypt
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sqlite3
import json
import logging
from functools import wraps
from flask import request, jsonify, session, g
import secrets

@dataclass
class User:
    """User model"""
    id: str
    email: str
    password_hash: str
    full_name: str
    company: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    subscription_tier: str = "free"  # free, pro, enterprise
    api_key: Optional[str] = None

class AuthManager:
    """Handles user authentication and session management"""
    
    def __init__(self, database, secret_key: str):
        self.database = database
        self.secret_key = secret_key
        self.logger = logging.getLogger(__name__)
        self.init_auth_tables()
    
    def init_auth_tables(self):
        """Initialize authentication tables"""
        with self.database.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    company TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    subscription_tier TEXT DEFAULT 'free',
                    api_key TEXT UNIQUE
                )
            """)
            
            # User sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # User data tables - link existing data to users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    contract_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (contract_id) REFERENCES contracts (id),
                    UNIQUE(user_id, contract_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    invoice_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id),
                    UNIQUE(user_id, invoice_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_reconciliations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    reconciliation_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (reconciliation_id) REFERENCES reconciliations (id),
                    UNIQUE(user_id, reconciliation_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_contracts ON user_contracts(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_invoices ON user_invoices(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_reconciliations ON user_reconciliations(user_id)")
            
            conn.commit()
    
    def register_user(self, email: str, password: str, full_name: str, company: str = "") -> Dict[str, Any]:
        """Register a new user"""
        try:
            # Validate email format
            if not self._is_valid_email(email):
                return {"success": False, "error": "Invalid email format"}
            
            # Check if user already exists
            if self.get_user_by_email(email):
                return {"success": False, "error": "User already exists"}
            
            # Validate password strength
            if not self._is_strong_password(password):
                return {"success": False, "error": "Password must be at least 8 characters with uppercase, lowercase, and number"}
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Generate user ID and API key
            user_id = str(uuid.uuid4())
            api_key = self._generate_api_key()
            
            # Create user
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (id, email, password_hash, full_name, company, api_key)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, email.lower(), password_hash, full_name, company, api_key))
                conn.commit()
            
            self.logger.info(f"New user registered: {email}")
            
            return {
                "success": True,
                "user_id": user_id,
                "message": "User registered successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return {"success": False, "error": "Registration failed"}
    
    def login_user(self, email: str, password: str, ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Login user and create session"""
        try:
            # Get user
            user = self.get_user_by_email(email)
            if not user or not user.is_active:
                return {"success": False, "error": "Invalid credentials"}
            
            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return {"success": False, "error": "Invalid credentials"}
            
            # Create session
            session_token = self._generate_session_token()
            session_id = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(days=30)  # 30-day session
            
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean up old sessions for this user
                cursor.execute("DELETE FROM user_sessions WHERE user_id = ? AND expires_at < ?", 
                             (user.id, datetime.now()))
                
                # Create new session
                cursor.execute("""
                    INSERT INTO user_sessions (id, user_id, session_token, expires_at, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, user.id, session_token, expires_at, ip_address, user_agent))
                
                # Update last login
                cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", 
                             (datetime.now(), user.id))
                
                conn.commit()
            
            self.logger.info(f"User logged in: {email}")
            
            return {
                "success": True,
                "session_token": session_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "company": user.company,
                    "subscription_tier": user.subscription_tier,
                    "api_key": user.api_key
                },
                "expires_at": expires_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return {"success": False, "error": "Login failed"}
    
    def logout_user(self, session_token: str) -> bool:
        """Logout user and invalidate session"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Logout error: {e}")
            return False
    
    def validate_session(self, session_token: str) -> Optional[User]:
        """Validate session token and return user"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get session and user
                cursor.execute("""
                    SELECT u.*, s.expires_at, s.id as session_id
                    FROM users u
                    JOIN user_sessions s ON u.id = s.user_id
                    WHERE s.session_token = ? AND s.expires_at > ? AND u.is_active = 1
                """, (session_token, datetime.now()))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Update last accessed
                cursor.execute("UPDATE user_sessions SET last_accessed = ? WHERE id = ?", 
                             (datetime.now(), row['session_id']))
                conn.commit()
                
                return User(
                    id=row['id'],
                    email=row['email'],
                    password_hash=row['password_hash'],
                    full_name=row['full_name'],
                    company=row['company'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
                    is_active=bool(row['is_active']),
                    subscription_tier=row['subscription_tier'],
                    api_key=row['api_key']
                )
                
        except Exception as e:
            self.logger.error(f"Session validation error: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row['id'],
                        email=row['email'],
                        password_hash=row['password_hash'],
                        full_name=row['full_name'],
                        company=row['company'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
                        is_active=bool(row['is_active']),
                        subscription_tier=row['subscription_tier'],
                        api_key=row['api_key']
                    )
        except Exception as e:
            self.logger.error(f"Get user error: {e}")
        
        return None
    
    def link_contract_to_user(self, user_id: str, contract_id: int):
        """Link a contract to a user"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO user_contracts (user_id, contract_id)
                    VALUES (?, ?)
                """, (user_id, contract_id))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Link contract error: {e}")
    
    def link_invoice_to_user(self, user_id: str, invoice_id: int):
        """Link an invoice to a user"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO user_invoices (user_id, invoice_id)
                    VALUES (?, ?)
                """, (user_id, invoice_id))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Link invoice error: {e}")
    
    def get_user_data_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of user's data"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count contracts
                cursor.execute("SELECT COUNT(*) as count FROM user_contracts WHERE user_id = ?", (user_id,))
                contracts_count = cursor.fetchone()['count']
                
                # Count invoices
                cursor.execute("SELECT COUNT(*) as count FROM user_invoices WHERE user_id = ?", (user_id,))
                invoices_count = cursor.fetchone()['count']
                
                # Count reconciliations
                cursor.execute("SELECT COUNT(*) as count FROM user_reconciliations WHERE user_id = ?", (user_id,))
                reconciliations_count = cursor.fetchone()['count']
                
                return {
                    "contracts": contracts_count,
                    "invoices": invoices_count,
                    "reconciliations": reconciliations_count
                }
        except Exception as e:
            self.logger.error(f"Get user data summary error: {e}")
            return {"contracts": 0, "invoices": 0, "reconciliations": 0}
    
    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _is_strong_password(self, password: str) -> bool:
        """Check password strength"""
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        return has_upper and has_lower and has_digit
    
    def _generate_session_token(self) -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    def _generate_api_key(self) -> str:
        """Generate API key for user"""
        return f"unspend_{secrets.token_urlsafe(24)}"

# Authentication decorators
def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for session token in header or cookie
        session_token = request.headers.get('Authorization')
        if session_token and session_token.startswith('Bearer '):
            session_token = session_token[7:]  # Remove 'Bearer ' prefix
        else:
            session_token = request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({"error": "Authentication required"}), 401
        
        # Validate session
        user = g.auth_manager.validate_session(session_token)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401
        
        # Add user to request context
        g.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function

def optional_auth(f):
    """Decorator for optional authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.headers.get('Authorization')
        if session_token and session_token.startswith('Bearer '):
            session_token = session_token[7:]
        else:
            session_token = request.cookies.get('session_token')
        
        g.current_user = None
        if session_token:
            user = g.auth_manager.validate_session(session_token)
            if user:
                g.current_user = user
        
        return f(*args, **kwargs)
    
    return decorated_function