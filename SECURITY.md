# Unspend Platform Security Documentation

## Overview
This document outlines the comprehensive security measures implemented in the Unspend invoice reconciliation platform to protect user data and ensure system integrity.

## Security Architecture

### 1. Authentication & Authorization

#### User Authentication
- **Password Hashing**: BCrypt with salt rounds (cost factor 12)
- **Password Requirements**:
  - Minimum 8 characters
  - Must contain uppercase, lowercase, numbers, and special characters
  - Prevents common passwords
- **Session Management**:
  - Secure session tokens (32 bytes, URL-safe)
  - 30-day session expiry with sliding window
  - Automatic session cleanup
  - Concurrent session limiting (3 per user)

#### API Authentication
- Bearer token authentication via Authorization header
- HTTP-only secure cookies for web sessions
- API key support for programmatic access
- Session validation on every request

### 2. Data Encryption

#### Encryption at Rest
- **Algorithm**: AES-256-GCM with Fernet
- **Key Management**: PBKDF2 key derivation (100,000 iterations)
- **Encrypted Data**:
  - User PII (names, emails, companies)
  - Contract and invoice sensitive fields
  - Uploaded documents
  - Database fields

#### Encryption in Transit
- HTTPS enforced in production
- TLS 1.2+ required
- HSTS header with preloading

### 3. Security Headers

#### Content Security Policy (CSP)
```
default-src 'self';
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' https://api.openai.com
```

#### Additional Headers
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-XSS-Protection: 1; mode=block` - XSS protection
- `Strict-Transport-Security: max-age=31536000` - Force HTTPS
- `Referrer-Policy: strict-origin-when-cross-origin` - Control referrer

### 4. CSRF Protection

- Double-submit cookie pattern
- CSRF tokens for state-changing operations
- 4-hour token lifetime
- Automatic token rotation
- SameSite cookie attribute

### 5. Input Validation & Sanitization

#### Request Validation
- Maximum request size: 10MB
- File upload size limit: 5MB
- Allowed file types: PDF, JPG, PNG
- SQL injection prevention
- XSS attack prevention
- XXE attack prevention

#### Data Sanitization
- HTML entity encoding
- SQL parameter binding
- Path traversal prevention
- Command injection prevention

### 6. Rate Limiting

#### Endpoint Categories
- **Authentication** (Strict): 10 req/min, 100 req/hour
- **API** (Standard): 30 req/min, 500 req/hour  
- **Public** (Relaxed): 60 req/min, 1000 req/hour

#### Protection Against
- Brute force attacks
- DDoS attempts
- API abuse
- Resource exhaustion

### 7. Audit Logging

#### Logged Events
- Authentication attempts (success/failure)
- Authorization decisions
- Data access and modifications
- Security events (CSRF failures, malicious requests)
- API usage patterns

#### Log Management
- Structured JSON logging
- 90-day retention
- Secure log storage
- Real-time alerting for security events

### 8. Secure Development Practices

#### Code Security
- Input validation on all endpoints
- Output encoding
- Parameterized queries
- Secure random number generation
- No hardcoded secrets

#### Dependencies
- Regular security updates
- Vulnerability scanning with Safety and Bandit
- License compliance checking
- Supply chain security

### 9. Data Protection & Privacy

#### GDPR Compliance
- User consent for data processing
- Right to access (data export)
- Right to erasure (account deletion)
- Data minimization
- Privacy by design

#### Data Retention
- User data: 365 days after last activity
- Logs: 90 days
- Backups: 30 days
- Secure deletion with overwriting

### 10. Incident Response

#### Security Monitoring
- Real-time threat detection
- Anomaly detection
- Failed authentication tracking
- Rate limit violations
- Malicious request patterns

#### Response Procedures
1. **Detection**: Automated alerts for security events
2. **Containment**: Automatic IP blocking, session invalidation
3. **Investigation**: Audit log analysis
4. **Recovery**: Data restoration from encrypted backups
5. **Lessons Learned**: Security posture improvement

## Security Configuration

### Environment Variables
```bash
# Required Security Environment Variables
SECRET_KEY=<strong-random-key>
ENCRYPTION_MASTER_KEY=<base64-encoded-32-byte-key>
JWT_SECRET_KEY=<strong-random-key>
SESSION_SECRET=<strong-random-key>

# Optional Security Settings
ENABLE_MFA=false
REQUIRE_HTTPS=true
MAX_LOGIN_ATTEMPTS=5
SESSION_TIMEOUT=3600
```

### Security Headers Configuration
See `security.config.json` for detailed configuration options.

## Security Best Practices for Users

### Password Security
- Use strong, unique passwords
- Enable MFA when available
- Don't share credentials
- Report suspicious activity

### Data Handling
- Only upload necessary documents
- Verify SSL certificate (https://)
- Log out when finished
- Keep software updated

## Security Testing

### Automated Testing
```bash
# Run security tests
python -m pytest backend/tests/test_security.py

# Static security analysis
bandit -r backend/

# Dependency vulnerability scan
safety check

# OWASP dependency check
dependency-check --scan .
```

### Manual Testing Checklist
- [ ] Authentication bypass attempts
- [ ] Session fixation tests
- [ ] CSRF token validation
- [ ] XSS payload testing
- [ ] SQL injection attempts
- [ ] File upload validation
- [ ] Rate limiting verification
- [ ] Encryption verification

## Vulnerability Reporting

### Responsible Disclosure
If you discover a security vulnerability:

1. **Do NOT** create a public issue
2. Email security@unspend.com with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
3. Allow 90 days for patching before public disclosure

### Security Acknowledgments
We maintain a hall of fame for security researchers who help improve our platform security.

## Compliance & Certifications

### Standards Compliance
- OWASP Top 10 mitigation
- PCI DSS guidelines (where applicable)
- GDPR compliance
- SOC 2 Type II (in progress)
- ISO 27001 (planned)

### Third-Party Audits
- Annual penetration testing
- Quarterly vulnerability assessments
- Continuous security monitoring

## Security Roadmap

### Planned Enhancements
1. **Q1 2025**:
   - Multi-factor authentication (MFA)
   - Hardware security key support
   - Advanced threat detection

2. **Q2 2025**:
   - Zero-trust architecture
   - End-to-end encryption
   - Blockchain audit trail

3. **Q3 2025**:
   - Homomorphic encryption
   - Quantum-resistant cryptography
   - AI-powered threat detection

## Contact

### Security Team
- Email: security@unspend.com
- Emergency: security-urgent@unspend.com
- PGP Key: [Available on request]

### Resources
- [Security Policy](security.config.json)
- [Infrastructure Guide](INFRASTRUCTURE.md)
- [API Documentation](API.md)

---

**Last Updated**: 2025-08-16
**Version**: 1.0.0
**Classification**: Public