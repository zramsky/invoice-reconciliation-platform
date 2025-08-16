#!/usr/bin/env python3
"""
Comprehensive Backup Manager for Unspend Platform
Handles automated backups, encryption, verification, and restoration
"""

import os
import sys
import sqlite3
import json
import hashlib
import shutil
import tarfile
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from data_encryption import EncryptionService

class BackupType(Enum):
    """Types of backups"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"

class BackupStatus(Enum):
    """Backup status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    CORRUPTED = "corrupted"

@dataclass
class BackupMetadata:
    """Metadata for a backup"""
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size_bytes: int
    checksum: str
    encrypted: bool
    compression: str
    source_files: List[str]
    status: BackupStatus
    verification_date: Optional[datetime] = None
    restore_tested: bool = False
    retention_days: int = 30

class BackupManager:
    """Main backup management system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.backup_dir = Path(self.config.get('backup_dir', 'backups'))
        self.backup_dir.mkdir(exist_ok=True)
        
        # Set up logging
        self.logger = self._setup_logging()
        
        # Initialize encryption if enabled
        self.encryption = None
        if self.config.get('encrypt_backups', True):
            encryption_key = os.getenv('BACKUP_ENCRYPTION_KEY')
            if encryption_key:
                self.encryption = EncryptionService(encryption_key)
                self.logger.info("Backup encryption enabled")
            else:
                self.logger.warning("Backup encryption key not found - backups will not be encrypted")
        
        # Backup metadata database
        self.metadata_db = self.backup_dir / 'backup_metadata.db'
        self._init_metadata_db()
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load backup configuration"""
        default_config = {
            'backup_dir': 'backups',
            'retention_days': 30,
            'max_backups': 30,
            'compress_backups': True,
            'encrypt_backups': True,
            'verify_after_backup': True,
            'offsite_enabled': False,
            'backup_schedule': {
                'full': 'weekly',  # weekly, daily, monthly
                'incremental': 'daily',
                'snapshot': 'hourly'
            },
            'paths_to_backup': [
                'backend/unspend.db',
                'backend/uploads',
                'backend/processed',
                'secure_storage'
            ],
            'exclude_patterns': [
                '*.pyc',
                '__pycache__',
                '*.log',
                'node_modules',
                '.git'
            ]
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _setup_logging(self) -> logging.Logger:
        """Set up backup logging"""
        log_dir = self.backup_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger('backup_manager')
        logger.setLevel(logging.INFO)
        
        # File handler
        log_file = log_dir / f'backup_{datetime.now().strftime("%Y%m%d")}.log'
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _init_metadata_db(self):
        """Initialize backup metadata database"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                backup_id TEXT PRIMARY KEY,
                backup_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                size_bytes INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                encrypted BOOLEAN NOT NULL,
                compression TEXT,
                source_files TEXT NOT NULL,
                status TEXT NOT NULL,
                verification_date TIMESTAMP,
                restore_tested BOOLEAN DEFAULT FALSE,
                retention_days INTEGER DEFAULT 30,
                backup_path TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restore_history (
                restore_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                restore_timestamp TIMESTAMP NOT NULL,
                restore_path TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                FOREIGN KEY (backup_id) REFERENCES backups (backup_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_backup(self, backup_type: BackupType = BackupType.FULL) -> Optional[str]:
        """Create a backup"""
        backup_id = self._generate_backup_id()
        self.logger.info(f"Starting {backup_type.value} backup: {backup_id}")
        
        try:
            # Create backup directory
            backup_path = self.backup_dir / backup_type.value / backup_id
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Collect files to backup
            files_to_backup = self._collect_files_to_backup(backup_type)
            
            if not files_to_backup:
                self.logger.warning("No files to backup")
                return None
            
            # Create backup archive
            archive_path = self._create_archive(backup_path, files_to_backup)
            
            # Compress if enabled
            if self.config.get('compress_backups', True):
                archive_path = self._compress_archive(archive_path)
            
            # Encrypt if enabled
            if self.encryption:
                archive_path = self._encrypt_backup(archive_path)
            
            # Calculate checksum
            checksum = self._calculate_checksum(archive_path)
            
            # Get file size
            size_bytes = archive_path.stat().st_size
            
            # Create metadata
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=backup_type,
                timestamp=datetime.now(),
                size_bytes=size_bytes,
                checksum=checksum,
                encrypted=bool(self.encryption),
                compression='gzip' if self.config.get('compress_backups') else None,
                source_files=files_to_backup,
                status=BackupStatus.COMPLETED,
                retention_days=self.config.get('retention_days', 30)
            )
            
            # Save metadata
            self._save_metadata(metadata, str(archive_path))
            
            # Verify backup if enabled
            if self.config.get('verify_after_backup', True):
                if self.verify_backup(backup_id):
                    metadata.status = BackupStatus.VERIFIED
                    metadata.verification_date = datetime.now()
                    self._update_metadata(metadata)
            
            self.logger.info(f"Backup completed successfully: {backup_id}")
            self.logger.info(f"Size: {size_bytes / 1024 / 1024:.2f} MB")
            
            # Clean up old backups
            self._cleanup_old_backups()
            
            return backup_id
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            self._update_backup_status(backup_id, BackupStatus.FAILED)
            return None
    
    def _collect_files_to_backup(self, backup_type: BackupType) -> List[str]:
        """Collect files to backup based on type"""
        files = []
        
        for path_pattern in self.config.get('paths_to_backup', []):
            path = Path(path_pattern)
            
            if path.exists():
                if path.is_file():
                    files.append(str(path))
                elif path.is_dir():
                    # Recursively add all files in directory
                    for file_path in path.rglob('*'):
                        if file_path.is_file():
                            # Check if file should be excluded
                            if not self._should_exclude(file_path):
                                files.append(str(file_path))
        
        # For incremental backup, only include modified files
        if backup_type == BackupType.INCREMENTAL:
            last_backup = self._get_last_backup_time()
            if last_backup:
                files = [f for f in files if Path(f).stat().st_mtime > last_backup.timestamp()]
        
        return files
    
    def _should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded from backup"""
        exclude_patterns = self.config.get('exclude_patterns', [])
        
        for pattern in exclude_patterns:
            if file_path.match(pattern):
                return True
        
        return False
    
    def _create_archive(self, backup_path: Path, files: List[str]) -> Path:
        """Create tar archive of files"""
        archive_path = backup_path / 'backup.tar'
        
        with tarfile.open(archive_path, 'w') as tar:
            for file_path in files:
                tar.add(file_path, arcname=file_path)
                self.logger.debug(f"Added to archive: {file_path}")
        
        return archive_path
    
    def _compress_archive(self, archive_path: Path) -> Path:
        """Compress archive with gzip"""
        compressed_path = archive_path.with_suffix('.tar.gz')
        
        with open(archive_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove uncompressed archive
        archive_path.unlink()
        
        return compressed_path
    
    def _encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file"""
        encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
        
        with open(backup_path, 'rb') as f:
            data = f.read()
        
        encrypted_data = self.encryption.encrypt_file(data)
        
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Remove unencrypted file
        backup_path.unlink()
        
        return encrypted_path
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity"""
        self.logger.info(f"Verifying backup: {backup_id}")
        
        metadata = self._get_metadata(backup_id)
        if not metadata:
            self.logger.error(f"Backup metadata not found: {backup_id}")
            return False
        
        backup_path = self._get_backup_path(backup_id)
        if not backup_path or not backup_path.exists():
            self.logger.error(f"Backup file not found: {backup_id}")
            return False
        
        # Verify checksum
        current_checksum = self._calculate_checksum(backup_path)
        if current_checksum != metadata['checksum']:
            self.logger.error(f"Checksum mismatch for backup: {backup_id}")
            self._update_backup_status(backup_id, BackupStatus.CORRUPTED)
            return False
        
        # Verify file can be read
        try:
            # If encrypted, try to decrypt
            if metadata['encrypted'] and self.encryption:
                with open(backup_path, 'rb') as f:
                    encrypted_data = f.read()
                self.encryption.decrypt_file(encrypted_data)
            
            self.logger.info(f"Backup verified successfully: {backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup verification failed: {e}")
            self._update_backup_status(backup_id, BackupStatus.CORRUPTED)
            return False
    
    def restore_backup(self, backup_id: str, restore_path: Optional[str] = None) -> bool:
        """Restore a backup"""
        restore_id = self._generate_restore_id()
        self.logger.info(f"Starting restore: {restore_id} from backup: {backup_id}")
        
        try:
            metadata = self._get_metadata(backup_id)
            if not metadata:
                raise ValueError(f"Backup not found: {backup_id}")
            
            backup_path = self._get_backup_path(backup_id)
            if not backup_path or not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_id}")
            
            # Verify backup before restore
            if not self.verify_backup(backup_id):
                raise ValueError(f"Backup verification failed: {backup_id}")
            
            # Set restore path
            if not restore_path:
                restore_path = Path('restore') / restore_id
            else:
                restore_path = Path(restore_path)
            
            restore_path.mkdir(parents=True, exist_ok=True)
            
            # Copy backup file to temp location
            temp_file = restore_path / 'temp_backup'
            shutil.copy2(backup_path, temp_file)
            
            # Decrypt if needed
            if metadata['encrypted'] and self.encryption:
                with open(temp_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self.encryption.decrypt_file(encrypted_data)
                temp_file = temp_file.with_suffix('')
                with open(temp_file, 'wb') as f:
                    f.write(decrypted_data)
            
            # Decompress if needed
            if metadata['compression'] == 'gzip':
                decompressed_file = temp_file.with_suffix('.tar')
                with gzip.open(temp_file, 'rb') as f_in:
                    with open(decompressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                temp_file.unlink()
                temp_file = decompressed_file
            
            # Extract archive
            with tarfile.open(temp_file, 'r') as tar:
                tar.extractall(restore_path)
            
            # Clean up temp file
            temp_file.unlink()
            
            # Log restore
            self._log_restore(restore_id, backup_id, str(restore_path), True, None)
            
            self.logger.info(f"Restore completed successfully: {restore_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            self._log_restore(restore_id, backup_id, str(restore_path), False, str(e))
            return False
    
    def list_backups(self, backup_type: Optional[BackupType] = None) -> List[Dict]:
        """List all backups"""
        conn = sqlite3.connect(self.metadata_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if backup_type:
            cursor.execute(
                "SELECT * FROM backups WHERE backup_type = ? ORDER BY timestamp DESC",
                (backup_type.value,)
            )
        else:
            cursor.execute("SELECT * FROM backups ORDER BY timestamp DESC")
        
        backups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return backups
    
    def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        self.logger.info("Starting backup cleanup")
        
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        # Get expired backups
        cutoff_date = datetime.now() - timedelta(days=self.config.get('retention_days', 30))
        cursor.execute(
            "SELECT backup_id, backup_path FROM backups WHERE timestamp < ?",
            (cutoff_date,)
        )
        
        expired_backups = cursor.fetchall()
        
        for backup_id, backup_path in expired_backups:
            try:
                # Delete backup file
                if Path(backup_path).exists():
                    Path(backup_path).unlink()
                    # Remove parent directory if empty
                    Path(backup_path).parent.rmdir()
                
                # Delete metadata
                cursor.execute("DELETE FROM backups WHERE backup_id = ?", (backup_id,))
                
                self.logger.info(f"Deleted expired backup: {backup_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to delete backup {backup_id}: {e}")
        
        conn.commit()
        conn.close()
        
        # Also enforce max backups limit
        self._enforce_max_backups()
    
    def _enforce_max_backups(self):
        """Enforce maximum number of backups"""
        max_backups = self.config.get('max_backups', 30)
        
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        # Count current backups
        cursor.execute("SELECT COUNT(*) FROM backups")
        count = cursor.fetchone()[0]
        
        if count > max_backups:
            # Delete oldest backups
            cursor.execute("""
                DELETE FROM backups 
                WHERE backup_id IN (
                    SELECT backup_id FROM backups 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                )
            """, (count - max_backups,))
            
            conn.commit()
        
        conn.close()
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        return f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    def _generate_restore_id(self) -> str:
        """Generate unique restore ID"""
        return f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    def _save_metadata(self, metadata: BackupMetadata, backup_path: str):
        """Save backup metadata to database"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO backups (
                backup_id, backup_type, timestamp, size_bytes, checksum,
                encrypted, compression, source_files, status, verification_date,
                restore_tested, retention_days, backup_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata.backup_id,
            metadata.backup_type.value,
            metadata.timestamp,
            metadata.size_bytes,
            metadata.checksum,
            metadata.encrypted,
            metadata.compression,
            json.dumps(metadata.source_files),
            metadata.status.value,
            metadata.verification_date,
            metadata.restore_tested,
            metadata.retention_days,
            backup_path
        ))
        
        conn.commit()
        conn.close()
    
    def _update_metadata(self, metadata: BackupMetadata):
        """Update backup metadata"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE backups 
            SET status = ?, verification_date = ?, restore_tested = ?
            WHERE backup_id = ?
        """, (
            metadata.status.value,
            metadata.verification_date,
            metadata.restore_tested,
            metadata.backup_id
        ))
        
        conn.commit()
        conn.close()
    
    def _get_metadata(self, backup_id: str) -> Optional[Dict]:
        """Get backup metadata"""
        conn = sqlite3.connect(self.metadata_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM backups WHERE backup_id = ?", (backup_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        return dict(row) if row else None
    
    def _get_backup_path(self, backup_id: str) -> Optional[Path]:
        """Get backup file path"""
        metadata = self._get_metadata(backup_id)
        if metadata and 'backup_path' in metadata:
            return Path(metadata['backup_path'])
        return None
    
    def _update_backup_status(self, backup_id: str, status: BackupStatus):
        """Update backup status"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE backups SET status = ? WHERE backup_id = ?",
            (status.value, backup_id)
        )
        
        conn.commit()
        conn.close()
    
    def _get_last_backup_time(self) -> Optional[datetime]:
        """Get timestamp of last successful backup"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(timestamp) FROM backups 
            WHERE status IN (?, ?)
        """, (BackupStatus.COMPLETED.value, BackupStatus.VERIFIED.value))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return datetime.fromisoformat(result[0])
        return None
    
    def _log_restore(self, restore_id: str, backup_id: str, restore_path: str, 
                     success: bool, error_message: Optional[str]):
        """Log restore operation"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO restore_history (
                restore_id, backup_id, restore_timestamp, restore_path,
                success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            restore_id,
            backup_id,
            datetime.now(),
            restore_path,
            success,
            error_message
        ))
        
        conn.commit()
        conn.close()

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Unspend Backup Manager')
    parser.add_argument('action', choices=['backup', 'restore', 'list', 'verify'],
                       help='Action to perform')
    parser.add_argument('--type', choices=['full', 'incremental', 'differential', 'snapshot'],
                       default='full', help='Backup type')
    parser.add_argument('--backup-id', help='Backup ID for restore/verify')
    parser.add_argument('--restore-path', help='Path to restore backup to')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    manager = BackupManager(args.config)
    
    if args.action == 'backup':
        backup_type = BackupType[args.type.upper()]
        backup_id = manager.create_backup(backup_type)
        if backup_id:
            print(f"✅ Backup created: {backup_id}")
        else:
            print("❌ Backup failed")
            sys.exit(1)
    
    elif args.action == 'restore':
        if not args.backup_id:
            print("❌ --backup-id required for restore")
            sys.exit(1)
        
        if manager.restore_backup(args.backup_id, args.restore_path):
            print(f"✅ Backup restored: {args.backup_id}")
        else:
            print("❌ Restore failed")
            sys.exit(1)
    
    elif args.action == 'list':
        backups = manager.list_backups()
        if backups:
            print("\n📦 Available Backups:")
            print("-" * 80)
            for backup in backups:
                size_mb = backup['size_bytes'] / 1024 / 1024
                print(f"ID: {backup['backup_id']}")
                print(f"  Type: {backup['backup_type']}")
                print(f"  Date: {backup['timestamp']}")
                print(f"  Size: {size_mb:.2f} MB")
                print(f"  Status: {backup['status']}")
                print(f"  Encrypted: {backup['encrypted']}")
                print("-" * 80)
        else:
            print("No backups found")
    
    elif args.action == 'verify':
        if not args.backup_id:
            print("❌ --backup-id required for verify")
            sys.exit(1)
        
        if manager.verify_backup(args.backup_id):
            print(f"✅ Backup verified: {args.backup_id}")
        else:
            print("❌ Verification failed")
            sys.exit(1)