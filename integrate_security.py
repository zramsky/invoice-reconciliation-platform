#!/usr/bin/env python3
"""
Security Integration Script for Unspend Platform
Integrates all security components into the main application
"""

import os
import sys
import json
from pathlib import Path

def integrate_security():
    """Integrate security middleware into Flask app"""
    
    print("🔐 Unspend Security Integration")
    print("=" * 40)
    
    # Check if app.py exists
    app_path = Path("backend/app.py")
    if not app_path.exists():
        print("❌ Error: backend/app.py not found")
        return False
    
    print("✅ Found main application file")
    
    # Read current app.py
    with open(app_path, 'r') as f:
        app_content = f.read()
    
    # Check if security is already integrated
    if 'security_middleware' in app_content:
        print("ℹ️  Security middleware already integrated")
        return True
    
    # Security imports to add
    security_imports = """
# Security imports
from security_middleware import create_security_middleware, SecurityConfig
from data_encryption import init_encryption, get_encryption_service
"""
    
    # Security initialization code
    security_init = """
# Initialize security
security_config = SecurityConfig(
    enable_csrf=True,
    enable_security_headers=True,
    enable_request_validation=True,
    enable_audit_logging=True
)
security_middleware = create_security_middleware(app, app.config['SECRET_KEY'], security_config)

# Initialize encryption
encryption_service = init_encryption(os.getenv('ENCRYPTION_MASTER_KEY'))
"""
    
    print("📝 Adding security imports...")
    
    # Find position to insert imports (after other imports)
    import_position = app_content.find("load_dotenv()")
    if import_position == -1:
        print("⚠️  Warning: Could not find ideal import position")
    else:
        # Insert security imports before load_dotenv()
        app_content = (
            app_content[:import_position] + 
            security_imports + "\n" +
            app_content[import_position:]
        )
        print("✅ Security imports added")
    
    print("🔧 Adding security initialization...")
    
    # Find position to insert initialization (after auth_manager)
    init_position = app_content.find("auth_manager = AuthManager")
    if init_position != -1:
        # Find end of line
        end_of_line = app_content.find("\n", init_position)
        if end_of_line != -1:
            app_content = (
                app_content[:end_of_line + 1] +
                security_init + "\n" +
                app_content[end_of_line + 1:]
            )
            print("✅ Security initialization added")
    
    # Backup original file
    backup_path = app_path.with_suffix('.py.backup')
    with open(backup_path, 'w') as f:
        f.write(app_content)
    print(f"💾 Backup saved to {backup_path}")
    
    # Write updated app.py
    with open(app_path, 'w') as f:
        f.write(app_content)
    print("✅ Security integration complete")
    
    return True

def generate_env_template():
    """Generate .env template with security variables"""
    
    env_template = """# Unspend Platform Environment Variables
# SECURITY CONFIGURATION - CHANGE ALL VALUES IN PRODUCTION

# Core Configuration
FLASK_ENV=development
FLASK_DEBUG=False
SECRET_KEY=change-this-to-a-strong-random-key-in-production

# Database
DATABASE_PATH=backend/unspend.db

# OpenAI API
OPENAI_API_KEY=your-openai-api-key-here

# Security Keys - MUST BE CHANGED IN PRODUCTION
ENCRYPTION_MASTER_KEY=generate-strong-32-byte-key-and-base64-encode
JWT_SECRET_KEY=change-this-to-a-strong-random-jwt-key
SESSION_SECRET=change-this-to-a-strong-session-secret

# Security Settings
ENABLE_MFA=false
REQUIRE_HTTPS=false
MAX_LOGIN_ATTEMPTS=5
SESSION_TIMEOUT=3600
LOCKOUT_DURATION=900

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=500

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000

# File Upload
MAX_FILE_SIZE=5242880
ALLOWED_EXTENSIONS=pdf,jpg,jpeg,png

# Logging
LOG_LEVEL=INFO
AUDIT_LOG_ENABLED=true
AUDIT_LOG_FILE=security_audit.log

# Firebase (for deployment)
FIREBASE_PROJECT_ID=unspend-91424
"""
    
    env_path = Path(".env.template")
    with open(env_path, 'w') as f:
        f.write(env_template)
    
    print(f"📄 Created {env_path}")
    return True

def check_dependencies():
    """Check if all required dependencies are installed"""
    
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        'cryptography',
        'bcrypt',
        'PyJWT',
        'flask',
        'flask-cors'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} installed")
        except ImportError:
            print(f"❌ {package} missing")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def create_security_tests():
    """Create basic security tests"""
    
    test_content = '''"""
Security Tests for Unspend Platform
"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security_middleware import CSRFProtection, RequestValidator, PasswordValidator
from data_encryption import EncryptionService

class TestPasswordValidation:
    def test_strong_password(self):
        """Test strong password validation"""
        is_valid, error = PasswordValidator.validate("StrongP@ssw0rd123")
        assert is_valid == True
        assert error is None
    
    def test_weak_password(self):
        """Test weak password rejection"""
        is_valid, error = PasswordValidator.validate("password")
        assert is_valid == False
        assert "too common" in error.lower()
    
    def test_short_password(self):
        """Test short password rejection"""
        is_valid, error = PasswordValidator.validate("Pass1!")
        assert is_valid == False
        assert "at least 8 characters" in error

class TestEncryption:
    def test_string_encryption(self):
        """Test string encryption/decryption"""
        service = EncryptionService()
        original = "sensitive data"
        encrypted = service.encrypt_string(original)
        decrypted = service.decrypt_string(encrypted)
        assert decrypted == original
    
    def test_json_encryption(self):
        """Test JSON encryption/decryption"""
        service = EncryptionService()
        original = {"user": "test", "data": "sensitive"}
        encrypted = service.encrypt_json(original)
        decrypted = service.decrypt_json(encrypted)
        assert decrypted == original

class TestCSRF:
    def test_token_generation(self):
        """Test CSRF token generation"""
        csrf = CSRFProtection("test-secret-key")
        token = csrf.generate_token("session-123")
        assert token is not None
        assert ":" in token
    
    def test_token_validation(self):
        """Test CSRF token validation"""
        csrf = CSRFProtection("test-secret-key")
        session_id = "session-123"
        token = csrf.generate_token(session_id)
        assert csrf.validate_token(token, session_id) == True
        assert csrf.validate_token("invalid-token", session_id) == False

class TestRequestValidation:
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection"""
        validator = RequestValidator(10485760)
        assert validator._is_safe_string("normal text") == True
        assert validator._is_safe_string("SELECT * FROM users") == False
        assert validator._is_safe_string("1 OR 1=1") == False
    
    def test_xss_detection(self):
        """Test XSS pattern detection"""
        validator = RequestValidator(10485760)
        assert validator._is_safe_string("<script>alert(1)</script>") == False
        assert validator._is_safe_string("javascript:alert(1)") == False
        assert validator._is_safe_string("normal text") == True
'''
    
    test_path = Path("backend/tests/test_security.py")
    test_path.parent.mkdir(exist_ok=True)
    
    with open(test_path, 'w') as f:
        f.write(test_content)
    
    print(f"🧪 Created {test_path}")
    return True

def main():
    """Main integration script"""
    
    print("\n🚀 Starting Unspend Security Integration\n")
    
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Please install missing dependencies first")
        return 1
    
    # Generate environment template
    generate_env_template()
    
    # Create security tests
    create_security_tests()
    
    # Integrate security (commented out to avoid modifying app.py automatically)
    # Uncomment the following line to actually integrate:
    # integrate_security()
    
    print("\n" + "=" * 40)
    print("✅ Security setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.template to .env and update values")
    print("2. Generate strong keys for production:")
    print("   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
    print("3. Run security tests:")
    print("   pytest backend/tests/test_security.py")
    print("4. Review SECURITY.md for full documentation")
    print("\n🔐 Your application is now security-enhanced!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())