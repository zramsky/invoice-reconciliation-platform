#!/bin/bash

# Unspend Platform Automated Backup Scheduler
# Manages scheduled backups using cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_LOG="$SCRIPT_DIR/logs/scheduler.log"

# Create log directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$BACKUP_LOG"
    echo "$1"
}

# Function to run backup
run_backup() {
    local backup_type=$1
    log_message "Starting $backup_type backup..."
    
    cd "$PROJECT_ROOT"
    python3 backup_system/backup_manager.py backup --type "$backup_type"
    
    if [ $? -eq 0 ]; then
        log_message "✅ $backup_type backup completed successfully"
        
        # Send success notification (optional)
        if [ -n "$SLACK_WEBHOOK" ]; then
            curl -X POST "$SLACK_WEBHOOK" \
                -H 'Content-Type: application/json' \
                -d "{\"text\":\"✅ Unspend $backup_type backup completed successfully\"}" \
                2>/dev/null
        fi
    else
        log_message "❌ $backup_type backup failed"
        
        # Send failure notification
        if [ -n "$SLACK_WEBHOOK" ]; then
            curl -X POST "$SLACK_WEBHOOK" \
                -H 'Content-Type: application/json' \
                -d "{\"text\":\"❌ ALERT: Unspend $backup_type backup failed!\"}" \
                2>/dev/null
        fi
    fi
}

# Function to setup cron jobs
setup_cron() {
    log_message "Setting up backup cron jobs..."
    
    # Create cron entries
    CRON_ENTRIES="
# Unspend Backup Schedule
# Hourly snapshot backups (keep 24)
0 * * * * $SCRIPT_DIR/backup_scheduler.sh hourly
# Daily incremental backups at 2 AM (keep 7)
0 2 * * * $SCRIPT_DIR/backup_scheduler.sh daily
# Weekly full backups on Sunday at 3 AM (keep 4)
0 3 * * 0 $SCRIPT_DIR/backup_scheduler.sh weekly
# Monthly full backups on 1st at 4 AM (keep 12)
0 4 1 * * $SCRIPT_DIR/backup_scheduler.sh monthly
# Quarterly DR test on 1st of Jan/Apr/Jul/Oct at 5 AM
0 5 1 1,4,7,10 * $SCRIPT_DIR/backup_scheduler.sh test
"
    
    # Add to crontab
    (crontab -l 2>/dev/null | grep -v "Unspend Backup Schedule" | grep -v "backup_scheduler.sh"; echo "$CRON_ENTRIES") | crontab -
    
    log_message "✅ Cron jobs configured"
    echo "Cron schedule:"
    crontab -l | grep "backup_scheduler.sh"
}

# Function to remove cron jobs
remove_cron() {
    log_message "Removing backup cron jobs..."
    crontab -l 2>/dev/null | grep -v "backup_scheduler.sh" | crontab -
    log_message "✅ Cron jobs removed"
}

# Function to sync to offsite storage
sync_offsite() {
    log_message "Syncing backups to offsite storage..."
    
    # S3 sync (requires AWS CLI)
    if command -v aws &> /dev/null && [ -n "$AWS_S3_BUCKET" ]; then
        aws s3 sync "$SCRIPT_DIR/../backups" "s3://$AWS_S3_BUCKET/backups/" \
            --exclude "*.log" \
            --exclude "backup_metadata.db" \
            --storage-class GLACIER_IR
        
        if [ $? -eq 0 ]; then
            log_message "✅ Synced to S3: $AWS_S3_BUCKET"
        else
            log_message "❌ S3 sync failed"
        fi
    fi
    
    # Google Drive sync (requires rclone)
    if command -v rclone &> /dev/null && [ -n "$GDRIVE_REMOTE" ]; then
        rclone sync "$SCRIPT_DIR/../backups" "$GDRIVE_REMOTE:unspend-backups" \
            --exclude "*.log" \
            --exclude "backup_metadata.db"
        
        if [ $? -eq 0 ]; then
            log_message "✅ Synced to Google Drive"
        else
            log_message "❌ Google Drive sync failed"
        fi
    fi
    
    # rsync to remote server
    if [ -n "$REMOTE_BACKUP_HOST" ]; then
        rsync -avz --delete \
            --exclude="*.log" \
            --exclude="backup_metadata.db" \
            "$SCRIPT_DIR/../backups/" \
            "$REMOTE_BACKUP_USER@$REMOTE_BACKUP_HOST:$REMOTE_BACKUP_PATH/"
        
        if [ $? -eq 0 ]; then
            log_message "✅ Synced to remote: $REMOTE_BACKUP_HOST"
        else
            log_message "❌ Remote sync failed"
        fi
    fi
}

# Function to run DR test
run_dr_test() {
    log_message "Starting disaster recovery test..."
    
    cd "$PROJECT_ROOT"
    python3 disaster_recovery/dr_orchestrator.py test
    
    if [ $? -eq 0 ]; then
        log_message "✅ DR test passed"
    else
        log_message "❌ DR test failed - immediate attention required!"
        
        # Send urgent notification
        if [ -n "$SLACK_WEBHOOK" ]; then
            curl -X POST "$SLACK_WEBHOOK" \
                -H 'Content-Type: application/json' \
                -d "{\"text\":\"🚨 URGENT: Unspend DR test failed! Review immediately.\"}" \
                2>/dev/null
        fi
    fi
}

# Function to show backup status
show_status() {
    echo "📊 Unspend Backup Status"
    echo "========================"
    
    cd "$PROJECT_ROOT"
    python3 backup_system/backup_manager.py list | tail -20
    
    echo ""
    echo "📅 Scheduled Jobs:"
    crontab -l 2>/dev/null | grep "backup_scheduler.sh" || echo "No jobs scheduled"
    
    echo ""
    echo "💾 Disk Usage:"
    du -sh "$SCRIPT_DIR/../backups" 2>/dev/null || echo "No backups found"
    
    echo ""
    echo "📝 Recent Logs:"
    tail -5 "$BACKUP_LOG" 2>/dev/null || echo "No logs found"
}

# Main script logic
case "$1" in
    hourly)
        run_backup "snapshot"
        ;;
    daily)
        run_backup "incremental"
        sync_offsite
        ;;
    weekly)
        run_backup "full"
        sync_offsite
        ;;
    monthly)
        run_backup "full"
        sync_offsite
        # Also run cleanup
        cd "$PROJECT_ROOT"
        python3 -c "from backup_system.backup_manager import BackupManager; BackupManager()._cleanup_old_backups()"
        ;;
    test)
        run_dr_test
        ;;
    setup)
        setup_cron
        ;;
    remove)
        remove_cron
        ;;
    sync)
        sync_offsite
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {hourly|daily|weekly|monthly|test|setup|remove|sync|status}"
        echo ""
        echo "Commands:"
        echo "  hourly   - Run hourly snapshot backup"
        echo "  daily    - Run daily incremental backup"
        echo "  weekly   - Run weekly full backup"
        echo "  monthly  - Run monthly full backup with cleanup"
        echo "  test     - Run disaster recovery test"
        echo "  setup    - Setup cron jobs for automated backups"
        echo "  remove   - Remove cron jobs"
        echo "  sync     - Sync backups to offsite storage"
        echo "  status   - Show backup status and schedule"
        exit 1
        ;;
esac

exit 0