"""
Centralized Configuration Management for Unspend Platform
This file provides configuration without modifying existing code
"""

import os
from typing import Optional

class Config:
    """Base configuration - inherits from environment"""
    
    # Core Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Security Settings
    SECURE_COOKIES = os.environ.get('SECURE_COOKIES', 'False').lower() == 'true'
    REQUIRE_HTTPS = os.environ.get('REQUIRE_HTTPS', 'False').lower() == 'true'
    SESSION_COOKIE_SECURE = SECURE_COOKIES
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict' if SECURE_COOKIES else 'Lax'
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///backend/unspend.db')
    DATABASE_POOL_SIZE = int(os.environ.get('DATABASE_POOL_SIZE', '10'))
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # File Upload
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '5242880'))  # 5MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    PROCESSED_FOLDER = os.environ.get('PROCESSED_FOLDER', 'processed')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    @classmethod
    def init_app(cls, app):
        """Initialize Flask app with configuration"""
        # This method can be called to configure the app without modifying app.py
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SECURE_COOKIES = False
    REQUIRE_HTTPS = False
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SECURE_COOKIES = True
    REQUIRE_HTTPS = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    LOG_LEVEL = 'WARNING'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SECURE_COOKIES = False
    DATABASE_URL = 'sqlite:///test.db'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(env: Optional[str] = None) -> Config:
    """Get configuration based on environment"""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])