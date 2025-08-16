"""
Data Encryption Service for Unspend Platform
Handles encryption of sensitive user data and documents
"""

import os
import base64
import json
import hashlib
from typing import Any, Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import logging

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self, master_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Use provided key or generate new one
        if master_key:
            self.master_key = master_key.encode() if isinstance(master_key, str) else master_key
        else:
            # Try to load from environment or generate new
            env_key = os.getenv('ENCRYPTION_MASTER_KEY')
            if env_key:
                self.master_key = env_key.encode()
            else:
                self.master_key = Fernet.generate_key()
                self.logger.warning("Generated new encryption key - save this: " + self.master_key.decode())
        
        # Initialize Fernet cipher
        self.fernet = Fernet(self.master_key)
        
        # Create database encryption key (derived from master)
        self.db_key = self._derive_key(self.master_key, b'database_encryption_salt')
        self.db_fernet = Fernet(self.db_key)
    
    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        """Derive encryption key from password and salt"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt_string(self, data: str) -> str:
        """Encrypt a string"""
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"String encryption error: {e}")
            raise
    
    def decrypt_string(self, encrypted_data: str) -> str:
        """Decrypt a string"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"String decryption error: {e}")
            raise
    
    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """Encrypt JSON data"""
        try:
            json_str = json.dumps(data)
            return self.encrypt_string(json_str)
        except Exception as e:
            self.logger.error(f"JSON encryption error: {e}")
            raise
    
    def decrypt_json(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt JSON data"""
        try:
            json_str = self.decrypt_string(encrypted_data)
            return json.loads(json_str)
        except Exception as e:
            self.logger.error(f"JSON decryption error: {e}")
            raise
    
    def encrypt_file(self, file_data: bytes) -> bytes:
        """Encrypt file data"""
        try:
            return self.fernet.encrypt(file_data)
        except Exception as e:
            self.logger.error(f"File encryption error: {e}")
            raise
    
    def decrypt_file(self, encrypted_data: bytes) -> bytes:
        """Decrypt file data"""
        try:
            return self.fernet.decrypt(encrypted_data)
        except Exception as e:
            self.logger.error(f"File decryption error: {e}")
            raise
    
    def encrypt_database_field(self, data: str) -> str:
        """Encrypt data for database storage"""
        try:
            encrypted = self.db_fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"Database field encryption error: {e}")
            raise
    
    def decrypt_database_field(self, encrypted_data: str) -> str:
        """Decrypt data from database"""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.db_fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"Database field decryption error: {e}")
            raise
    
    def hash_data(self, data: str) -> str:
        """Create SHA-256 hash of data (one-way)"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_hash(self, data: str, hash_value: str) -> bool:
        """Verify data against hash"""
        return self.hash_data(data) == hash_value

class SecureDocumentStorage:
    """Secure storage for user documents"""
    
    def __init__(self, encryption_service: EncryptionService, storage_path: str = 'secure_storage'):
        self.encryption = encryption_service
        self.storage_path = storage_path
        self.logger = logging.getLogger(__name__)
        
        # Create secure storage directory
        os.makedirs(storage_path, exist_ok=True)
        
        # Set restrictive permissions (Unix-like systems)
        try:
            os.chmod(storage_path, 0o700)  # Only owner can read/write/execute
        except:
            pass  # Windows doesn't support chmod
    
    def store_document(self, user_id: str, document_id: str, document_data: bytes, metadata: Dict[str, Any]) -> str:
        """Store encrypted document"""
        try:
            # Encrypt document
            encrypted_data = self.encryption.encrypt_file(document_data)
            
            # Encrypt metadata
            encrypted_metadata = self.encryption.encrypt_json(metadata)
            
            # Create user directory
            user_dir = os.path.join(self.storage_path, self._hash_user_id(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Generate secure filename
            filename = self._generate_filename(document_id)
            file_path = os.path.join(user_dir, filename)
            
            # Store encrypted document
            with open(file_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Store encrypted metadata
            metadata_path = file_path + '.meta'
            with open(metadata_path, 'w') as f:
                f.write(encrypted_metadata)
            
            self.logger.info(f"Document stored securely: {document_id}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Document storage error: {e}")
            raise
    
    def retrieve_document(self, user_id: str, document_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """Retrieve and decrypt document"""
        try:
            # Get file path
            user_dir = os.path.join(self.storage_path, self._hash_user_id(user_id))
            filename = self._generate_filename(document_id)
            file_path = os.path.join(user_dir, filename)
            
            # Read encrypted document
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Read encrypted metadata
            metadata_path = file_path + '.meta'
            with open(metadata_path, 'r') as f:
                encrypted_metadata = f.read()
            
            # Decrypt document
            document_data = self.encryption.decrypt_file(encrypted_data)
            
            # Decrypt metadata
            metadata = self.encryption.decrypt_json(encrypted_metadata)
            
            self.logger.info(f"Document retrieved: {document_id}")
            return document_data, metadata
            
        except Exception as e:
            self.logger.error(f"Document retrieval error: {e}")
            raise
    
    def delete_document(self, user_id: str, document_id: str) -> bool:
        """Securely delete document"""
        try:
            # Get file path
            user_dir = os.path.join(self.storage_path, self._hash_user_id(user_id))
            filename = self._generate_filename(document_id)
            file_path = os.path.join(user_dir, filename)
            metadata_path = file_path + '.meta'
            
            # Securely overwrite file before deletion
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size))  # Overwrite with random data
                os.remove(file_path)
            
            # Remove metadata
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            
            self.logger.info(f"Document deleted: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Document deletion error: {e}")
            return False
    
    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for directory name"""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]
    
    def _generate_filename(self, document_id: str) -> str:
        """Generate secure filename"""
        return hashlib.sha256(document_id.encode()).hexdigest() + '.enc'

class EncryptedDatabase:
    """Database wrapper with automatic field encryption"""
    
    def __init__(self, database, encryption_service: EncryptionService):
        self.database = database
        self.encryption = encryption_service
        self.logger = logging.getLogger(__name__)
        
        # Fields to encrypt
        self.encrypted_fields = {
            'contracts': ['vendor_name', 'contract_number', 'amount'],
            'invoices': ['vendor_name', 'invoice_number', 'amount'],
            'users': ['full_name', 'company', 'email']
        }
    
    def encrypt_row(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt specified fields in a row"""
        encrypted_row = row.copy()
        
        if table in self.encrypted_fields:
            for field in self.encrypted_fields[table]:
                if field in encrypted_row and encrypted_row[field]:
                    try:
                        # Convert to string if needed
                        value = str(encrypted_row[field])
                        encrypted_row[field] = self.encryption.encrypt_database_field(value)
                    except Exception as e:
                        self.logger.error(f"Failed to encrypt {field}: {e}")
        
        return encrypted_row
    
    def decrypt_row(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt specified fields in a row"""
        decrypted_row = row.copy()
        
        if table in self.encrypted_fields:
            for field in self.encrypted_fields[table]:
                if field in decrypted_row and decrypted_row[field]:
                    try:
                        decrypted_row[field] = self.encryption.decrypt_database_field(decrypted_row[field])
                    except Exception as e:
                        self.logger.error(f"Failed to decrypt {field}: {e}")
                        # Keep original value if decryption fails
        
        return decrypted_row

class PIIRedactor:
    """Redact personally identifiable information"""
    
    @staticmethod
    def redact_email(email: str) -> str:
        """Redact email address"""
        if '@' in email:
            parts = email.split('@')
            username = parts[0]
            domain = parts[1]
            
            if len(username) > 2:
                redacted_username = username[0] + '*' * (len(username) - 2) + username[-1]
            else:
                redacted_username = '*' * len(username)
            
            return f"{redacted_username}@{domain}"
        return email
    
    @staticmethod
    def redact_phone(phone: str) -> str:
        """Redact phone number"""
        # Keep only last 4 digits
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) >= 4:
            return '*' * (len(digits) - 4) + digits[-4:]
        return '*' * len(digits)
    
    @staticmethod
    def redact_ssn(ssn: str) -> str:
        """Redact SSN"""
        digits = ''.join(filter(str.isdigit, ssn))
        if len(digits) >= 4:
            return '*' * (len(digits) - 4) + digits[-4:]
        return '*' * len(digits)
    
    @staticmethod
    def redact_credit_card(cc: str) -> str:
        """Redact credit card number"""
        digits = ''.join(filter(str.isdigit, cc))
        if len(digits) >= 4:
            return '*' * (len(digits) - 4) + digits[-4:]
        return '*' * len(digits)
    
    @staticmethod
    def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields in dictionary"""
        redacted = data.copy()
        
        sensitive_fields = {
            'email': PIIRedactor.redact_email,
            'phone': PIIRedactor.redact_phone,
            'ssn': PIIRedactor.redact_ssn,
            'credit_card': PIIRedactor.redact_credit_card,
            'card_number': PIIRedactor.redact_credit_card
        }
        
        for field, redactor in sensitive_fields.items():
            if field in redacted and redacted[field]:
                redacted[field] = redactor(str(redacted[field]))
        
        return redacted

# Initialize global encryption service
encryption_service = None

def init_encryption(master_key: Optional[str] = None):
    """Initialize global encryption service"""
    global encryption_service
    encryption_service = EncryptionService(master_key)
    return encryption_service

def get_encryption_service() -> EncryptionService:
    """Get global encryption service"""
    global encryption_service
    if not encryption_service:
        encryption_service = init_encryption()
    return encryption_service