#!/usr/bin/env python3
"""
Production Readiness Checker for Unspend Platform
Checks for critical security issues before deployment
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Tuple

class ProductionChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
        
    def check_environment(self) -> bool:
        """Check environment variables"""
        print("🔍 Checking environment configuration...")
        
        required_vars = [
            'SECRET_KEY',
            'ENCRYPTION_MASTER_KEY', 
            'FLASK_ENV',
            'DATABASE_URL'
        ]
        
        for var in required_vars:
            value = os.environ.get(var)
            if not value:
                self.issues.append(f"❌ Missing required environment variable: {var}")
            elif var == 'SECRET_KEY' and value == 'dev-secret-key-change-in-production':
                self.issues.append(f"❌ {var} is using default development value!")
            elif var == 'FLASK_ENV' and value != 'production':
                self.warnings.append(f"⚠️  FLASK_ENV is '{value}', not 'production'")
            else:
                self.passed.append(f"✅ {var} is set")
        
        # Check security settings
        if os.environ.get('SECURE_COOKIES', 'False').lower() != 'true':
            self.issues.append("❌ SECURE_COOKIES is not enabled")
        else:
            self.passed.append("✅ SECURE_COOKIES is enabled")
            
        if os.environ.get('REQUIRE_HTTPS', 'False').lower() != 'true':
            self.issues.append("❌ REQUIRE_HTTPS is not enabled")
        else:
            self.passed.append("✅ REQUIRE_HTTPS is enabled")
        
        return len(self.issues) == 0
    
    def check_code_security(self) -> bool:
        """Check for hardcoded security issues"""
        print("🔍 Checking code for security issues...")
        
        app_file = Path('backend/app.py')
        if app_file.exists():
            content = app_file.read_text()
            
            # Check for insecure cookie settings
            if 'secure=False' in content:
                self.issues.append("❌ Found 'secure=False' in cookie settings (backend/app.py)")
            
            # Check for debug mode
            if 'debug=True' in content:
                self.issues.append("❌ Found 'debug=True' in app.run() (backend/app.py)")
            
            # Check for hardcoded secrets
            if 'dev-secret-key-change-in-production' in content:
                self.warnings.append("⚠️  Default secret key found in code")
        
        return True
    
    def check_database(self) -> bool:
        """Check database configuration"""
        print("🔍 Checking database configuration...")
        
        db_url = os.environ.get('DATABASE_URL', '')
        
        if 'sqlite' in db_url.lower():
            self.warnings.append("⚠️  Using SQLite - not recommended for production")
        elif 'postgresql' in db_url.lower():
            self.passed.append("✅ Using PostgreSQL for production")
        
        return True
    
    def check_ssl_certificates(self) -> bool:
        """Check SSL configuration"""
        print("🔍 Checking SSL/TLS configuration...")
        
        # Check for certificate files
        cert_files = ['ssl/cert.pem', 'ssl/key.pem', 'nginx/ssl/']
        
        for cert_path in cert_files:
            if Path(cert_path).exists():
                self.passed.append(f"✅ Found SSL files at {cert_path}")
                return True
        
        self.warnings.append("⚠️  No SSL certificates found - ensure HTTPS is configured at load balancer")
        return True
    
    def check_dependencies(self) -> bool:
        """Check for vulnerable dependencies"""
        print("🔍 Checking dependencies...")
        
        try:
            import subprocess
            
            # Check with safety
            result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.warnings.append("⚠️  Some dependencies may have vulnerabilities")
            else:
                self.passed.append("✅ No known vulnerabilities in dependencies")
        except:
            self.warnings.append("⚠️  Could not check dependencies (install 'safety')")
        
        return True
    
    def check_backup_configuration(self) -> bool:
        """Check backup and DR configuration"""
        print("🔍 Checking backup configuration...")
        
        backup_dir = Path('backups')
        if backup_dir.exists():
            self.passed.append("✅ Backup directory exists")
        else:
            self.warnings.append("⚠️  Backup directory not found")
        
        # Check for backup encryption key
        if os.environ.get('BACKUP_ENCRYPTION_KEY'):
            self.passed.append("✅ Backup encryption key is set")
        else:
            self.warnings.append("⚠️  Backup encryption key not set")
        
        return True
    
    def generate_report(self) -> bool:
        """Generate production readiness report"""
        print("\n" + "="*60)
        print("📊 PRODUCTION READINESS REPORT")
        print("="*60)
        
        # Show passed checks
        if self.passed:
            print("\n✅ PASSED CHECKS:")
            for item in self.passed:
                print(f"  {item}")
        
        # Show warnings
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        # Show critical issues
        if self.issues:
            print("\n❌ CRITICAL ISSUES (Must fix before production):")
            for issue in self.issues:
                print(f"  {issue}")
        
        # Final verdict
        print("\n" + "="*60)
        if self.issues:
            print("🚫 PRODUCTION READINESS: FAILED")
            print("   Fix all critical issues before deploying to production!")
            return False
        elif self.warnings:
            print("⚠️  PRODUCTION READINESS: PASSED WITH WARNINGS")
            print("   Review warnings and ensure they are acceptable for your use case.")
            return True
        else:
            print("✅ PRODUCTION READINESS: PASSED")
            print("   All checks passed! Ready for production deployment.")
            return True
    
    def run_all_checks(self) -> bool:
        """Run all production readiness checks"""
        print("🚀 Starting Production Readiness Check...\n")
        
        # Run all checks
        self.check_environment()
        self.check_code_security()
        self.check_database()
        self.check_ssl_certificates()
        self.check_dependencies()
        self.check_backup_configuration()
        
        # Generate report
        return self.generate_report()

def main():
    """Main entry point"""
    checker = ProductionChecker()
    
    # Load production environment if available
    env_file = Path('.env.production')
    if env_file.exists():
        print("📄 Loading .env.production file...")
        from dotenv import load_dotenv
        load_dotenv('.env.production')
    
    # Run checks
    if checker.run_all_checks():
        sys.exit(0)  # Success
    else:
        print("\n📋 Next Steps:")
        print("1. Review PRODUCTION_FIXES_REQUIRED.md for detailed fixes")
        print("2. Set required environment variables in .env.production")
        print("3. Fix critical code issues identified above")
        print("4. Run this check again before deployment")
        sys.exit(1)  # Failure

if __name__ == "__main__":
    main()