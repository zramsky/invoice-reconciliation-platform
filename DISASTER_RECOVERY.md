# Unspend Platform Disaster Recovery Plan

## Executive Summary

This document outlines the comprehensive disaster recovery (DR) and business continuity plan for the Unspend invoice reconciliation platform. It defines procedures for backup, recovery, and system restoration to minimize data loss and downtime.

## Key Metrics

### Recovery Objectives
- **RTO (Recovery Time Objective)**: 60 minutes
- **RPO (Recovery Point Objective)**: 30 minutes
- **MTTR (Mean Time To Recovery)**: 45 minutes
- **Data Retention**: 30 days standard, 365 days for compliance

### Service Level Agreements
- **Availability Target**: 99.9% (8.76 hours downtime/year)
- **Backup Success Rate**: >99%
- **Recovery Test Frequency**: Quarterly
- **Maximum Data Loss**: 30 minutes

## Backup Strategy

### Backup Schedule

| Type | Frequency | Retention | Storage Location |
|------|-----------|-----------|------------------|
| Snapshot | Hourly | 24 hours | Local + Cache |
| Incremental | Daily @ 2 AM | 7 days | Local + Offsite |
| Full | Weekly (Sunday @ 3 AM) | 4 weeks | Local + Offsite |
| Archive | Monthly (1st @ 4 AM) | 12 months | Offsite + Cold Storage |

### Backup Components
- **Database**: SQLite database with all user data
- **User Documents**: Uploaded contracts and invoices
- **Configuration**: Application settings and secrets
- **Code**: Application source code (via Git)
- **Logs**: Audit and security logs

### Encryption & Security
- **Algorithm**: AES-256-GCM
- **Key Management**: Master key with PBKDF2 derivation
- **Verification**: SHA-256 checksums
- **Access Control**: Role-based with audit logging

## Disaster Scenarios

### 1. Database Corruption
**Detection**: Integrity check failures, query errors
**Strategy**: Restore from latest verified backup
**RTO**: 30 minutes
**RPO**: Up to 30 minutes

### 2. Data Loss
**Detection**: Missing files, accidental deletion
**Strategy**: Point-in-time recovery
**RTO**: 45 minutes
**RPO**: Up to last backup

### 3. Ransomware Attack
**Detection**: Encrypted files, ransom notes
**Strategy**: Restore from pre-infection backup (24+ hours old)
**RTO**: 120 minutes
**RPO**: 24-48 hours

### 4. Hardware Failure
**Detection**: System unavailable, disk errors
**Strategy**: Failover to DR site
**RTO**: 15 minutes
**RPO**: 15 minutes

### 5. Natural Disaster
**Detection**: Site unavailable
**Strategy**: Full failover to DR site
**RTO**: 60 minutes
**RPO**: 30 minutes

## Recovery Procedures

### Quick Recovery Guide

#### Step 1: Assess the Situation
```bash
# Check system health
python disaster_recovery/dr_orchestrator.py detect

# List available backups
python backup_system/backup_manager.py list
```

#### Step 2: Create Recovery Plan
```bash
# Generate recovery plan
python disaster_recovery/dr_orchestrator.py plan --disaster-type [type]
```

#### Step 3: Execute Recovery
```bash
# Automated recovery
python disaster_recovery/dr_orchestrator.py execute --disaster-type [type]

# OR Manual recovery
python backup_system/backup_manager.py restore --backup-id [id]
```

#### Step 4: Verify Recovery
```bash
# Verify system health
curl http://localhost:5000/api/health

# Check database integrity
sqlite3 backend/unspend.db "PRAGMA integrity_check"
```

### Detailed Recovery Procedures

#### Database Recovery
1. Stop application services
2. Backup corrupted database (for analysis)
3. Restore database from backup:
   ```bash
   python backup_system/backup_manager.py restore --backup-id [latest] --restore-path /tmp/recovery
   cp /tmp/recovery/backend/unspend.db backend/unspend.db
   ```
4. Verify database integrity
5. Restart services
6. Test critical functions

#### Full System Recovery
1. Provision new infrastructure (if needed)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   npm install
   ```
3. Restore from backup:
   ```bash
   python backup_system/backup_manager.py restore --backup-id [id]
   ```
4. Update configuration
5. Restore database
6. Verify file permissions
7. Start services
8. Run health checks

#### Failover to DR Site
1. Verify DR site availability
2. Sync latest data:
   ```bash
   ./backup_system/backup_scheduler.sh sync
   ```
3. Update DNS records
4. Redirect traffic to DR site
5. Monitor performance
6. Plan failback

## Testing Procedures

### Quarterly DR Test
```bash
# Automated test
python disaster_recovery/dr_orchestrator.py test

# Manual test checklist
- [ ] Create test backup
- [ ] Restore to isolated environment
- [ ] Verify database integrity
- [ ] Test user authentication
- [ ] Verify document access
- [ ] Check API endpoints
- [ ] Validate data consistency
- [ ] Document issues found
- [ ] Update procedures
```

### Test Schedule
- **Monthly**: Backup verification
- **Quarterly**: Full DR test
- **Semi-annually**: Failover test
- **Annually**: Complete DR drill

## Automation

### Setup Automated Backups
```bash
# Configure environment
export AWS_S3_BUCKET=unspend-backups
export SLACK_WEBHOOK=https://hooks.slack.com/services/xxx

# Setup cron jobs
./backup_system/backup_scheduler.sh setup

# Verify schedule
./backup_system/backup_scheduler.sh status
```

### Monitoring
- Backup success/failure notifications
- Storage capacity alerts
- Recovery test reminders
- Expiration warnings

## Communication Plan

### Incident Response Team

| Role | Primary | Backup | Contact |
|------|---------|--------|---------|
| Incident Commander | CTO | VP Engineering | On-call phone |
| Technical Lead | DevOps Lead | Sr. Engineer | Slack/Phone |
| Communications | Product Manager | CEO | Email/Slack |
| Customer Support | Support Lead | Account Manager | Support system |

### Notification Templates

#### Initial Alert
```
🚨 INCIDENT DETECTED
Type: [Disaster Type]
Severity: [Critical/High/Medium]
Impact: [User Impact]
Status: Recovery initiated
ETA: [RTO estimate]
```

#### Progress Update
```
📊 RECOVERY UPDATE
Progress: [Step X of Y]
Completed: [Actions taken]
Current: [Current action]
ETA: [Updated estimate]
```

#### Resolution
```
✅ INCIDENT RESOLVED
Duration: [Downtime]
Data Loss: [RPO actual]
Root Cause: [Brief description]
Next Steps: [Follow-up actions]
```

## Offsite Storage

### Primary: AWS S3
- **Bucket**: unspend-backups
- **Region**: us-west-2
- **Replication**: Cross-region to us-east-1
- **Lifecycle**: Glacier after 30 days

### Secondary: Google Drive
- **Account**: backup@unspend.com
- **Folder**: /unspend-backups
- **Sync**: Daily via rclone

### Tertiary: Physical
- **Location**: Bank safety deposit box
- **Media**: Encrypted USB drives
- **Rotation**: Monthly

## Recovery Tools

### Required Tools
```bash
# Install recovery tools
pip install -r requirements.txt
apt-get install sqlite3 rsync
npm install -g firebase-tools

# AWS CLI (for S3)
pip install awscli
aws configure

# rclone (for cloud sync)
curl https://rclone.org/install.sh | sudo bash
rclone config
```

### Recovery Scripts
- `backup_manager.py` - Backup creation and restoration
- `dr_orchestrator.py` - Disaster recovery automation
- `backup_scheduler.sh` - Scheduled backup management

## Compliance & Audit

### Regulatory Requirements
- **GDPR**: Data portability, right to erasure
- **SOC 2**: Backup controls, recovery testing
- **HIPAA**: Encryption, audit trails (if applicable)

### Audit Trail
- All backup operations logged
- Recovery events tracked
- Test results documented
- Access control enforced

### Documentation
- DR plan reviewed quarterly
- Procedures updated after tests
- Contact list verified monthly
- Runbooks maintained

## Improvement Process

### Post-Incident Review
1. Timeline reconstruction
2. Root cause analysis
3. Impact assessment
4. Lessons learned
5. Action items
6. Procedure updates

### Metrics Tracking
- Backup success rate
- Recovery test results
- Actual vs. target RTO/RPO
- Incident frequency
- Time to detection

### Continuous Improvement
- Quarterly DR plan review
- Annual third-party audit
- Technology updates
- Process optimization

## Appendices

### A. Contact Information
```
Emergency Contacts:
- On-call: +1-xxx-xxx-xxxx
- Escalation: +1-xxx-xxx-xxxx
- AWS Support: [Account #]
- Firebase Support: [Project ID]
```

### B. Configuration Files
- `backup_config.json` - Backup settings
- `dr_config.json` - DR configuration
- `.env.backup` - Environment variables

### C. Vendor Information
- **AWS**: Account ID, support tier
- **Google Cloud**: Project ID
- **Firebase**: Project: unspend-91424

### D. Recovery Checklist
```
Pre-Recovery:
□ Assess disaster type
□ Notify incident team
□ Document current state
□ Identify recovery point

Recovery:
□ Execute recovery plan
□ Restore from backup
□ Verify data integrity
□ Test critical functions

Post-Recovery:
□ Document actual RTO/RPO
□ Conduct post-mortem
□ Update procedures
□ Schedule follow-up test
```

---

**Document Version**: 1.0.0
**Last Updated**: 2025-08-16
**Next Review**: 2025-02-16
**Owner**: Infrastructure Team
**Classification**: Confidential