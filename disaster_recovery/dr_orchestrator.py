#!/usr/bin/env python3
"""
Disaster Recovery Orchestrator for Unspend Platform
Manages failover, recovery procedures, and business continuity
"""

import os
import sys
import time
import json
import sqlite3
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging
import threading
import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backup_system.backup_manager import BackupManager, BackupType

class DisasterType(Enum):
    """Types of disasters"""
    DATABASE_CORRUPTION = "database_corruption"
    DATA_LOSS = "data_loss"
    RANSOMWARE = "ransomware"
    HARDWARE_FAILURE = "hardware_failure"
    HUMAN_ERROR = "human_error"
    NATURAL_DISASTER = "natural_disaster"
    CYBER_ATTACK = "cyber_attack"

class RecoveryStrategy(Enum):
    """Recovery strategies"""
    RESTORE_LATEST = "restore_latest"
    POINT_IN_TIME = "point_in_time"
    FAILOVER = "failover"
    REBUILD = "rebuild"
    PARTIAL_RESTORE = "partial_restore"

@dataclass
class RecoveryPoint:
    """Recovery point objective"""
    timestamp: datetime
    backup_id: str
    data_loss_minutes: int
    confidence_score: float

@dataclass
class RecoveryPlan:
    """Disaster recovery plan"""
    disaster_type: DisasterType
    strategy: RecoveryStrategy
    recovery_point: RecoveryPoint
    estimated_rto_minutes: int  # Recovery Time Objective
    estimated_rpo_minutes: int  # Recovery Point Objective
    steps: List[str]
    risks: List[str]

class DisasterRecoveryOrchestrator:
    """Main disaster recovery orchestration system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.backup_manager = BackupManager()
        self.logger = self._setup_logging()
        
        # Recovery metrics
        self.rto_target = self.config.get('rto_minutes', 60)  # 1 hour default
        self.rpo_target = self.config.get('rpo_minutes', 30)  # 30 minutes default
        
        # Initialize recovery database
        self.recovery_db = Path('disaster_recovery/recovery_history.db')
        self.recovery_db.parent.mkdir(exist_ok=True)
        self._init_recovery_db()
        
        # Health check endpoints
        self.health_checks = self.config.get('health_checks', {})
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load DR configuration"""
        default_config = {
            'rto_minutes': 60,  # Recovery Time Objective
            'rpo_minutes': 30,  # Recovery Point Objective
            'auto_failover': False,
            'notification_enabled': True,
            'notification_webhook': None,
            'backup_locations': [
                'backups/',
                '/mnt/nas/backups/',
                's3://unspend-backups/'
            ],
            'health_checks': {
                'database': 'backend/unspend.db',
                'api': 'http://localhost:5000/api/health',
                'frontend': 'http://localhost:3000'
            },
            'recovery_test_schedule': 'monthly',
            'dr_site': {
                'enabled': False,
                'url': 'https://dr.unspend.com',
                'sync_interval_minutes': 15
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _setup_logging(self) -> logging.Logger:
        """Set up DR logging"""
        log_dir = Path('disaster_recovery/logs')
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger('dr_orchestrator')
        logger.setLevel(logging.INFO)
        
        # File handler
        log_file = log_dir / f'dr_{datetime.now().strftime("%Y%m%d")}.log'
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _init_recovery_db(self):
        """Initialize recovery history database"""
        conn = sqlite3.connect(self.recovery_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_events (
                event_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                disaster_type TEXT NOT NULL,
                recovery_strategy TEXT NOT NULL,
                backup_id TEXT,
                recovery_started TIMESTAMP,
                recovery_completed TIMESTAMP,
                success BOOLEAN,
                data_loss_minutes INTEGER,
                downtime_minutes INTEGER,
                error_message TEXT,
                notes TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_tests (
                test_id TEXT PRIMARY KEY,
                test_date TIMESTAMP NOT NULL,
                test_type TEXT NOT NULL,
                backup_id TEXT NOT NULL,
                restore_success BOOLEAN NOT NULL,
                verification_success BOOLEAN,
                duration_minutes INTEGER,
                issues_found TEXT,
                recommendations TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def detect_disaster(self) -> Optional[DisasterType]:
        """Detect if a disaster has occurred"""
        self.logger.info("Running disaster detection...")
        
        # Check database integrity
        if not self._check_database_integrity():
            return DisasterType.DATABASE_CORRUPTION
        
        # Check for data loss
        if self._detect_data_loss():
            return DisasterType.DATA_LOSS
        
        # Check for ransomware indicators
        if self._detect_ransomware():
            return DisasterType.RANSOMWARE
        
        # Check system health
        if not self._check_system_health():
            return DisasterType.HARDWARE_FAILURE
        
        return None
    
    def create_recovery_plan(self, disaster_type: DisasterType) -> RecoveryPlan:
        """Create a recovery plan based on disaster type"""
        self.logger.info(f"Creating recovery plan for: {disaster_type.value}")
        
        # Determine recovery strategy
        strategy = self._determine_strategy(disaster_type)
        
        # Find best recovery point
        recovery_point = self._find_recovery_point(disaster_type)
        
        # Calculate RTO/RPO
        rto, rpo = self._calculate_recovery_objectives(disaster_type, strategy)
        
        # Generate recovery steps
        steps = self._generate_recovery_steps(disaster_type, strategy)
        
        # Identify risks
        risks = self._identify_risks(disaster_type, strategy)
        
        plan = RecoveryPlan(
            disaster_type=disaster_type,
            strategy=strategy,
            recovery_point=recovery_point,
            estimated_rto_minutes=rto,
            estimated_rpo_minutes=rpo,
            steps=steps,
            risks=risks
        )
        
        self.logger.info(f"Recovery plan created - RTO: {rto} min, RPO: {rpo} min")
        return plan
    
    def execute_recovery(self, plan: RecoveryPlan) -> bool:
        """Execute disaster recovery plan"""
        event_id = self._generate_event_id()
        self.logger.info(f"Starting recovery execution: {event_id}")
        
        # Log recovery start
        self._log_recovery_start(event_id, plan)
        
        # Send notification
        self._send_notification(f"Disaster recovery initiated: {plan.disaster_type.value}")
        
        recovery_start = datetime.now()
        success = True
        error_message = None
        
        try:
            # Execute recovery steps
            for i, step in enumerate(plan.steps, 1):
                self.logger.info(f"Step {i}/{len(plan.steps)}: {step}")
                
                if "backup" in step.lower():
                    success = self._restore_from_backup(plan.recovery_point.backup_id)
                elif "database" in step.lower():
                    success = self._recover_database()
                elif "verify" in step.lower():
                    success = self._verify_recovery()
                elif "failover" in step.lower():
                    success = self._execute_failover()
                
                if not success:
                    raise Exception(f"Step failed: {step}")
            
            # Verify system health
            if not self._verify_system_health():
                raise Exception("System health check failed after recovery")
            
            recovery_end = datetime.now()
            downtime_minutes = int((recovery_end - recovery_start).total_seconds() / 60)
            
            self.logger.info(f"Recovery completed successfully in {downtime_minutes} minutes")
            
            # Log recovery completion
            self._log_recovery_completion(
                event_id,
                success=True,
                downtime_minutes=downtime_minutes,
                data_loss_minutes=plan.recovery_point.data_loss_minutes
            )
            
            # Send success notification
            self._send_notification(
                f"Recovery successful - Downtime: {downtime_minutes} min, "
                f"Data loss: {plan.recovery_point.data_loss_minutes} min"
            )
            
            return True
            
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Recovery failed: {error_message}")
            
            # Log failure
            recovery_end = datetime.now()
            downtime_minutes = int((recovery_end - recovery_start).total_seconds() / 60)
            
            self._log_recovery_completion(
                event_id,
                success=False,
                downtime_minutes=downtime_minutes,
                error_message=error_message
            )
            
            # Send failure notification
            self._send_notification(f"Recovery FAILED: {error_message}")
            
            return False
    
    def test_recovery(self, backup_id: Optional[str] = None) -> bool:
        """Test disaster recovery procedures"""
        test_id = self._generate_test_id()
        self.logger.info(f"Starting recovery test: {test_id}")
        
        test_start = datetime.now()
        
        # Select backup for testing
        if not backup_id:
            backups = self.backup_manager.list_backups()
            if not backups:
                self.logger.error("No backups available for testing")
                return False
            backup_id = backups[0]['backup_id']  # Use latest
        
        # Create test environment
        test_path = Path('disaster_recovery/test') / test_id
        test_path.mkdir(parents=True, exist_ok=True)
        
        issues = []
        recommendations = []
        
        try:
            # Test backup restoration
            self.logger.info("Testing backup restoration...")
            if not self.backup_manager.restore_backup(backup_id, str(test_path)):
                issues.append("Backup restoration failed")
                recommendations.append("Verify backup integrity and encryption keys")
                raise Exception("Backup restoration failed")
            
            # Test database recovery
            self.logger.info("Testing database recovery...")
            test_db = test_path / 'backend/unspend.db'
            if test_db.exists():
                if not self._verify_database(str(test_db)):
                    issues.append("Database verification failed")
                    recommendations.append("Check database consistency and schema")
            
            # Test data integrity
            self.logger.info("Testing data integrity...")
            if not self._verify_data_integrity(test_path):
                issues.append("Data integrity check failed")
                recommendations.append("Review backup process and exclusion patterns")
            
            # Calculate test duration
            test_end = datetime.now()
            duration_minutes = int((test_end - test_start).total_seconds() / 60)
            
            # Check against RTO
            if duration_minutes > self.rto_target:
                issues.append(f"Recovery time ({duration_minutes} min) exceeds RTO ({self.rto_target} min)")
                recommendations.append("Optimize recovery procedures or adjust RTO target")
            
            # Log test results
            self._log_recovery_test(
                test_id=test_id,
                backup_id=backup_id,
                success=len(issues) == 0,
                duration_minutes=duration_minutes,
                issues=issues,
                recommendations=recommendations
            )
            
            # Clean up test environment
            shutil.rmtree(test_path)
            
            if issues:
                self.logger.warning(f"Recovery test completed with issues: {issues}")
            else:
                self.logger.info(f"Recovery test completed successfully in {duration_minutes} minutes")
            
            return len(issues) == 0
            
        except Exception as e:
            self.logger.error(f"Recovery test failed: {e}")
            
            # Log failure
            test_end = datetime.now()
            duration_minutes = int((test_end - test_start).total_seconds() / 60)
            
            self._log_recovery_test(
                test_id=test_id,
                backup_id=backup_id,
                success=False,
                duration_minutes=duration_minutes,
                issues=issues + [str(e)],
                recommendations=recommendations
            )
            
            # Clean up
            if test_path.exists():
                shutil.rmtree(test_path)
            
            return False
    
    def _check_database_integrity(self) -> bool:
        """Check database integrity"""
        db_path = Path(self.health_checks.get('database', 'backend/unspend.db'))
        
        if not db_path.exists():
            self.logger.error(f"Database not found: {db_path}")
            return False
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            conn.close()
            
            if result and result[0] == 'ok':
                return True
            else:
                self.logger.error(f"Database integrity check failed: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Database integrity check error: {e}")
            return False
    
    def _detect_data_loss(self) -> bool:
        """Detect potential data loss"""
        # Check for missing files
        critical_files = [
            'backend/unspend.db',
            'backend/app.py',
            'frontend/index.html'
        ]
        
        for file_path in critical_files:
            if not Path(file_path).exists():
                self.logger.error(f"Critical file missing: {file_path}")
                return True
        
        return False
    
    def _detect_ransomware(self) -> bool:
        """Detect ransomware indicators"""
        # Check for encrypted file extensions
        ransomware_extensions = ['.locked', '.enc', '.encrypted', '.crypto', '.oops']
        
        for ext in ransomware_extensions:
            files = list(Path('.').rglob(f'*{ext}'))
            if files:
                self.logger.warning(f"Potential ransomware detected: {len(files)} files with {ext}")
                return True
        
        # Check for ransom notes
        ransom_patterns = ['readme.txt', 'how_to_decrypt.txt', 'restore_files.txt']
        for pattern in ransom_patterns:
            if list(Path('.').rglob(pattern)):
                self.logger.warning(f"Potential ransom note detected: {pattern}")
                return True
        
        return False
    
    def _check_system_health(self) -> bool:
        """Check overall system health"""
        # Check API health
        api_url = self.health_checks.get('api')
        if api_url:
            try:
                response = requests.get(api_url, timeout=5)
                if response.status_code != 200:
                    self.logger.error(f"API health check failed: {response.status_code}")
                    return False
            except Exception as e:
                self.logger.error(f"API health check error: {e}")
                return False
        
        return True
    
    def _determine_strategy(self, disaster_type: DisasterType) -> RecoveryStrategy:
        """Determine recovery strategy based on disaster type"""
        strategies = {
            DisasterType.DATABASE_CORRUPTION: RecoveryStrategy.RESTORE_LATEST,
            DisasterType.DATA_LOSS: RecoveryStrategy.POINT_IN_TIME,
            DisasterType.RANSOMWARE: RecoveryStrategy.POINT_IN_TIME,
            DisasterType.HARDWARE_FAILURE: RecoveryStrategy.FAILOVER,
            DisasterType.HUMAN_ERROR: RecoveryStrategy.POINT_IN_TIME,
            DisasterType.NATURAL_DISASTER: RecoveryStrategy.FAILOVER,
            DisasterType.CYBER_ATTACK: RecoveryStrategy.REBUILD
        }
        
        return strategies.get(disaster_type, RecoveryStrategy.RESTORE_LATEST)
    
    def _find_recovery_point(self, disaster_type: DisasterType) -> RecoveryPoint:
        """Find best recovery point"""
        backups = self.backup_manager.list_backups()
        
        if not backups:
            raise Exception("No backups available for recovery")
        
        # For ransomware, find backup before infection
        if disaster_type == DisasterType.RANSOMWARE:
            # Look for backup at least 24 hours old
            cutoff = datetime.now() - timedelta(hours=24)
            for backup in backups:
                if datetime.fromisoformat(backup['timestamp']) < cutoff:
                    data_loss = int((datetime.now() - 
                                   datetime.fromisoformat(backup['timestamp'])).total_seconds() / 60)
                    return RecoveryPoint(
                        timestamp=datetime.fromisoformat(backup['timestamp']),
                        backup_id=backup['backup_id'],
                        data_loss_minutes=data_loss,
                        confidence_score=0.9
                    )
        
        # For other disasters, use latest verified backup
        for backup in backups:
            if backup['status'] in ['completed', 'verified']:
                data_loss = int((datetime.now() - 
                               datetime.fromisoformat(backup['timestamp'])).total_seconds() / 60)
                return RecoveryPoint(
                    timestamp=datetime.fromisoformat(backup['timestamp']),
                    backup_id=backup['backup_id'],
                    data_loss_minutes=data_loss,
                    confidence_score=1.0 if backup['status'] == 'verified' else 0.8
                )
        
        raise Exception("No suitable recovery point found")
    
    def _calculate_recovery_objectives(self, disaster_type: DisasterType, 
                                      strategy: RecoveryStrategy) -> Tuple[int, int]:
        """Calculate RTO and RPO"""
        # Base estimates
        base_rto = {
            RecoveryStrategy.RESTORE_LATEST: 30,
            RecoveryStrategy.POINT_IN_TIME: 45,
            RecoveryStrategy.FAILOVER: 15,
            RecoveryStrategy.REBUILD: 120,
            RecoveryStrategy.PARTIAL_RESTORE: 60
        }
        
        # Disaster type modifiers
        disaster_modifier = {
            DisasterType.DATABASE_CORRUPTION: 1.0,
            DisasterType.DATA_LOSS: 1.2,
            DisasterType.RANSOMWARE: 2.0,
            DisasterType.HARDWARE_FAILURE: 1.5,
            DisasterType.HUMAN_ERROR: 1.0,
            DisasterType.NATURAL_DISASTER: 3.0,
            DisasterType.CYBER_ATTACK: 2.5
        }
        
        rto = int(base_rto.get(strategy, 60) * disaster_modifier.get(disaster_type, 1.0))
        rpo = 30  # Default 30 minutes based on backup frequency
        
        return rto, rpo
    
    def _generate_recovery_steps(self, disaster_type: DisasterType, 
                                strategy: RecoveryStrategy) -> List[str]:
        """Generate recovery steps"""
        steps = []
        
        # Common initial steps
        steps.append("Initiate incident response team notification")
        steps.append("Document current system state")
        
        # Strategy-specific steps
        if strategy == RecoveryStrategy.RESTORE_LATEST:
            steps.extend([
                "Identify latest verified backup",
                "Prepare recovery environment",
                "Restore backup to recovery location",
                "Verify database integrity",
                "Verify application functionality",
                "Switch traffic to recovered system"
            ])
        elif strategy == RecoveryStrategy.POINT_IN_TIME:
            steps.extend([
                "Identify target recovery point",
                "Validate backup integrity",
                "Restore to isolated environment",
                "Apply transaction logs if available",
                "Verify data consistency",
                "Test critical functions",
                "Perform cutover"
            ])
        elif strategy == RecoveryStrategy.FAILOVER:
            steps.extend([
                "Verify DR site availability",
                "Sync latest data to DR site",
                "Update DNS records",
                "Redirect traffic to DR site",
                "Verify service availability",
                "Monitor performance"
            ])
        
        # Common final steps
        steps.append("Verify system functionality")
        steps.append("Document recovery process")
        steps.append("Notify stakeholders of recovery completion")
        
        return steps
    
    def _identify_risks(self, disaster_type: DisasterType, 
                       strategy: RecoveryStrategy) -> List[str]:
        """Identify recovery risks"""
        risks = []
        
        # Common risks
        risks.append("Potential data loss between backup and disaster")
        risks.append("Extended downtime if recovery fails")
        
        # Disaster-specific risks
        if disaster_type == DisasterType.RANSOMWARE:
            risks.append("Backup may be infected")
            risks.append("Attacker may still have access")
        elif disaster_type == DisasterType.HARDWARE_FAILURE:
            risks.append("Replacement hardware may not be available")
            risks.append("Performance degradation on alternate hardware")
        
        # Strategy-specific risks
        if strategy == RecoveryStrategy.FAILOVER:
            risks.append("DR site may not have full capacity")
            risks.append("Network latency may impact performance")
        elif strategy == RecoveryStrategy.REBUILD:
            risks.append("Configuration drift from documentation")
            risks.append("Missing dependencies or libraries")
        
        return risks
    
    def _restore_from_backup(self, backup_id: str) -> bool:
        """Restore from backup"""
        try:
            # Create recovery directory
            recovery_path = Path('disaster_recovery/recovery') / datetime.now().strftime('%Y%m%d_%H%M%S')
            recovery_path.mkdir(parents=True, exist_ok=True)
            
            # Restore backup
            if not self.backup_manager.restore_backup(backup_id, str(recovery_path)):
                return False
            
            # Move restored files to production
            # This is simplified - in production, would need careful orchestration
            self.logger.info("Moving restored files to production...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Restore from backup failed: {e}")
            return False
    
    def _recover_database(self) -> bool:
        """Recover database"""
        try:
            db_path = Path('backend/unspend.db')
            
            # Check if database exists
            if not db_path.exists():
                self.logger.error("Database file not found")
                return False
            
            # Run recovery commands
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Vacuum to rebuild database
            cursor.execute("VACUUM")
            
            # Reindex
            cursor.execute("REINDEX")
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Database recovery failed: {e}")
            return False
    
    def _verify_recovery(self) -> bool:
        """Verify recovery success"""
        # Check critical files exist
        critical_files = [
            'backend/unspend.db',
            'backend/app.py',
            'frontend/index.html'
        ]
        
        for file_path in critical_files:
            if not Path(file_path).exists():
                self.logger.error(f"Critical file missing after recovery: {file_path}")
                return False
        
        # Check database integrity
        if not self._check_database_integrity():
            return False
        
        # Check system health
        if not self._check_system_health():
            return False
        
        return True
    
    def _execute_failover(self) -> bool:
        """Execute failover to DR site"""
        if not self.config.get('dr_site', {}).get('enabled'):
            self.logger.error("DR site not configured")
            return False
        
        try:
            dr_url = self.config['dr_site']['url']
            
            # In production, would update DNS, load balancer, etc.
            self.logger.info(f"Failing over to DR site: {dr_url}")
            
            # Verify DR site is accessible
            response = requests.get(f"{dr_url}/api/health", timeout=10)
            if response.status_code != 200:
                self.logger.error(f"DR site health check failed: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failover failed: {e}")
            return False
    
    def _verify_system_health(self) -> bool:
        """Verify system health after recovery"""
        return self._check_system_health() and self._check_database_integrity()
    
    def _verify_database(self, db_path: str) -> bool:
        """Verify database file"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            if not tables:
                self.logger.error("No tables found in database")
                return False
            
            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            conn.close()
            
            return result and result[0] == 'ok'
            
        except Exception as e:
            self.logger.error(f"Database verification failed: {e}")
            return False
    
    def _verify_data_integrity(self, path: Path) -> bool:
        """Verify data integrity of restored files"""
        # Check for expected directories
        expected_dirs = ['backend', 'frontend']
        
        for dir_name in expected_dirs:
            if not (path / dir_name).exists():
                self.logger.error(f"Expected directory missing: {dir_name}")
                return False
        
        return True
    
    def _send_notification(self, message: str):
        """Send notification about DR event"""
        if not self.config.get('notification_enabled'):
            return
        
        self.logger.info(f"Notification: {message}")
        
        # Send to webhook if configured
        webhook_url = self.config.get('notification_webhook')
        if webhook_url:
            try:
                payload = {
                    'text': f"[Unspend DR] {message}",
                    'timestamp': datetime.now().isoformat()
                }
                requests.post(webhook_url, json=payload, timeout=5)
            except Exception as e:
                self.logger.error(f"Failed to send notification: {e}")
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"dr_event_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    def _generate_test_id(self) -> str:
        """Generate unique test ID"""
        return f"dr_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    def _log_recovery_start(self, event_id: str, plan: RecoveryPlan):
        """Log recovery start"""
        conn = sqlite3.connect(self.recovery_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO recovery_events (
                event_id, timestamp, disaster_type, recovery_strategy,
                backup_id, recovery_started
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            datetime.now(),
            plan.disaster_type.value,
            plan.strategy.value,
            plan.recovery_point.backup_id,
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
    
    def _log_recovery_completion(self, event_id: str, success: bool, 
                                downtime_minutes: int, data_loss_minutes: int = 0,
                                error_message: Optional[str] = None):
        """Log recovery completion"""
        conn = sqlite3.connect(self.recovery_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE recovery_events
            SET recovery_completed = ?, success = ?, data_loss_minutes = ?,
                downtime_minutes = ?, error_message = ?
            WHERE event_id = ?
        """, (
            datetime.now(),
            success,
            data_loss_minutes,
            downtime_minutes,
            error_message,
            event_id
        ))
        
        conn.commit()
        conn.close()
    
    def _log_recovery_test(self, test_id: str, backup_id: str, success: bool,
                          duration_minutes: int, issues: List[str],
                          recommendations: List[str]):
        """Log recovery test results"""
        conn = sqlite3.connect(self.recovery_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO recovery_tests (
                test_id, test_date, test_type, backup_id, restore_success,
                verification_success, duration_minutes, issues_found, recommendations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id,
            datetime.now(),
            'full_recovery',
            backup_id,
            success,
            success,  # Same as restore for now
            duration_minutes,
            json.dumps(issues),
            json.dumps(recommendations)
        ))
        
        conn.commit()
        conn.close()

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Unspend Disaster Recovery')
    parser.add_argument('action', choices=['detect', 'plan', 'execute', 'test'],
                       help='DR action to perform')
    parser.add_argument('--disaster-type', 
                       choices=['database_corruption', 'data_loss', 'ransomware',
                               'hardware_failure', 'human_error'],
                       help='Type of disaster')
    parser.add_argument('--backup-id', help='Backup ID for testing')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    orchestrator = DisasterRecoveryOrchestrator(args.config)
    
    if args.action == 'detect':
        disaster = orchestrator.detect_disaster()
        if disaster:
            print(f"⚠️  Disaster detected: {disaster.value}")
            sys.exit(1)
        else:
            print("✅ No disasters detected")
    
    elif args.action == 'plan':
        if not args.disaster_type:
            print("❌ --disaster-type required for planning")
            sys.exit(1)
        
        disaster_type = DisasterType[args.disaster_type.upper()]
        plan = orchestrator.create_recovery_plan(disaster_type)
        
        print(f"\n📋 Recovery Plan for {disaster_type.value}")
        print(f"Strategy: {plan.strategy.value}")
        print(f"RTO: {plan.estimated_rto_minutes} minutes")
        print(f"RPO: {plan.estimated_rpo_minutes} minutes")
        print(f"Data Loss: {plan.recovery_point.data_loss_minutes} minutes")
        print("\nSteps:")
        for i, step in enumerate(plan.steps, 1):
            print(f"  {i}. {step}")
        print("\nRisks:")
        for risk in plan.risks:
            print(f"  ⚠️  {risk}")
    
    elif args.action == 'execute':
        if not args.disaster_type:
            # Try to detect disaster
            disaster = orchestrator.detect_disaster()
            if not disaster:
                print("❌ No disaster detected and --disaster-type not specified")
                sys.exit(1)
        else:
            disaster = DisasterType[args.disaster_type.upper()]
        
        plan = orchestrator.create_recovery_plan(disaster)
        
        print(f"🚨 Executing recovery for: {disaster.value}")
        if orchestrator.execute_recovery(plan):
            print("✅ Recovery completed successfully")
        else:
            print("❌ Recovery failed")
            sys.exit(1)
    
    elif args.action == 'test':
        print("🧪 Starting recovery test...")
        if orchestrator.test_recovery(args.backup_id):
            print("✅ Recovery test passed")
        else:
            print("❌ Recovery test failed")
            sys.exit(1)