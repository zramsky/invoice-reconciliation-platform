# 🚨 CRITICAL Production Fixes Required

## Overview
This document lists critical security and configuration fixes needed before production deployment. These fixes require code changes in files owned by different instances.

## 🔴 CRITICAL Security Fixes (Must fix before production)

### 1. Cookie Security Settings
**File**: `backend/app.py` (Lines 149-152, 165-168)
**Owner**: Backend Instance
**Current Issue**:
```python
secure=False,  # Set to True in production with HTTPS
samesite='Lax'
```
**Required Fix**:
```python
secure=os.getenv('SECURE_COOKIES', 'False').lower() == 'true',
samesite='Strict' if os.getenv('FLASK_ENV') == 'production' else 'Lax'
```

### 2. Secret Key Management
**File**: `backend/app.py` (Line 55)
**Owner**: Backend Instance
**Current Issue**:
```python
auth_manager = AuthManager(database, os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'))
```
**Required Fix**:
```python
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError("SECRET_KEY must be set in production")
    secret_key = 'dev-secret-key'  # Only for development
auth_manager = AuthManager(database, secret_key)
```

### 3. Debug Mode
**File**: `backend/app.py` (Line 1103)
**Owner**: Backend Instance
**Current Issue**:
```python
app.run(debug=True, port=5000)
```
**Required Fix**:
```python
debug_mode = os.getenv('FLASK_ENV') != 'production'
app.run(debug=debug_mode, port=5000)
```

## 🟡 HIGH Priority Fixes

### 1. Database Migration
**Current**: SQLite
**Required**: PostgreSQL for production
**Action**: 
- Install PostgreSQL adapter: `pip install psycopg2-binary`
- Use DATABASE_URL from environment

### 2. Session Storage
**File**: `backend/app.py` (Line 70)
**Current Issue**:
```python
reconciliation_sessions = {}  # In-memory storage
```
**Required Fix**: Use Redis for session storage
```python
import redis
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
```

### 3. HTTPS Enforcement
**Action**: Add HTTPS redirect middleware
```python
@app.before_request
def force_https():
    if os.getenv('REQUIRE_HTTPS') == 'True' and not request.is_secure:
        return redirect(request.url.replace('http://', 'https://'))
```

## 🟢 MEDIUM Priority Fixes

### 1. File Upload Validation
- Add content-type validation
- Add virus scanning
- Implement file size limits properly

### 2. Error Information Disclosure
- Hide stack traces in production
- Use generic error messages

### 3. Logging Configuration
- Centralize logging
- Add log rotation
- Implement structured logging

## 📋 Production Deployment Checklist

### Environment Variables (Required)
```bash
# These MUST be set in production
export FLASK_ENV=production
export SECRET_KEY=<generate-strong-key>
export ENCRYPTION_MASTER_KEY=<generate-strong-key>
export SECURE_COOKIES=True
export REQUIRE_HTTPS=True
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://...
```

### Pre-deployment Steps
1. [ ] Set all required environment variables
2. [ ] Run security audit: `python -m pytest tests/test_security.py`
3. [ ] Run database migrations
4. [ ] Configure SSL certificates
5. [ ] Set up monitoring and alerting
6. [ ] Configure backup automation
7. [ ] Test disaster recovery procedure
8. [ ] Load test the application
9. [ ] Security scan with OWASP ZAP
10. [ ] Review and update firewall rules

### Post-deployment Verification
1. [ ] Verify HTTPS is enforced
2. [ ] Check secure cookies are set
3. [ ] Confirm debug mode is disabled
4. [ ] Test rate limiting is active
5. [ ] Verify backups are running
6. [ ] Check monitoring is receiving data
7. [ ] Test error handling (no stack traces)
8. [ ] Verify audit logging is working

## 🛠️ Helper Scripts

### Generate Secret Keys
```bash
# Generate SECRET_KEY
python -c 'import secrets; print(secrets.token_hex(32))'

# Generate ENCRYPTION_MASTER_KEY
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

### Test Production Configuration
```bash
# Set production environment
export FLASK_ENV=production
source .env.production

# Run configuration test
python -c "from config.app_config import get_config; c = get_config('production'); print('Secure cookies:', c.SECURE_COOKIES); print('HTTPS required:', c.REQUIRE_HTTPS)"
```

## ⚠️ WARNING

**DO NOT DEPLOY TO PRODUCTION** until all CRITICAL fixes are implemented. The application currently has security vulnerabilities that could expose user data.

## 📞 Support

If you need help implementing these fixes:
1. Consult with the instance owner for each file
2. Test all changes in staging first
3. Run the full test suite after changes
4. Document any deviations from this guide

---

**Document Created**: 2025-08-16
**Last Updated**: 2025-08-16
**Status**: AWAITING FIXES
**Production Ready**: ❌ NO