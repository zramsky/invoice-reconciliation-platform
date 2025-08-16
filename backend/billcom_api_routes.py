"""
Bill.com API Routes for Unspend
Flask endpoints for Bill.com integration management
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from api_middleware import with_rate_limiting, with_error_handling, RateLimitRule
from billcom_integration import (
    BillcomConfig, BillcomAPIClient, BillcomSyncManager, 
    create_billcom_client, create_billcom_sync_manager,
    BillcomSyncStatus, BillcomResourceType
)
from database import Database
import os

# Create Blueprint
billcom_bp = Blueprint('billcom', __name__, url_prefix='/api/billcom')

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiting rules for Bill.com operations
BILLCOM_RATE_LIMIT = RateLimitRule(
    requests_per_minute=30,  # Lower limit for external API operations
    requests_per_hour=300,
    requests_per_day=2000,
    burst_allowance=5
)

def create_billcom_blueprint(database_instance):
    """Factory function to create Bill.com blueprint with database instance"""
    
    # Store database instance for use in routes
    billcom_bp.database = database_instance
    
    return billcom_bp

def get_billcom_config() -> BillcomConfig:
    """Get Bill.com configuration from environment variables"""
    return BillcomConfig(
        username=os.getenv('BILLCOM_USERNAME', ''),
        password=os.getenv('BILLCOM_PASSWORD', ''),
        organization_id=os.getenv('BILLCOM_ORG_ID', ''),
        dev_key=os.getenv('BILLCOM_DEV_KEY', ''),
        is_sandbox=os.getenv('BILLCOM_SANDBOX', 'true').lower() == 'true'
    )

@billcom_bp.route('/config', methods=['GET'])
@with_error_handling
@with_rate_limiting(RateLimitRule(requests_per_minute=60))
def get_config():
    """Get Bill.com integration configuration status"""
    config = get_billcom_config()
    
    # Don't expose sensitive data
    config_status = {
        "configured": bool(config.username and config.password and config.organization_id and config.dev_key),
        "is_sandbox": config.is_sandbox,
        "username": config.username[:3] + "***" if config.username else "",
        "organization_id": config.organization_id[:8] + "***" if config.organization_id else ""
    }
    
    return jsonify({
        "success": True,
        "config": config_status,
        "timestamp": datetime.now().isoformat()
    })

@billcom_bp.route('/config', methods=['POST'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def update_config():
    """Update Bill.com integration configuration"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No configuration data provided"}), 400
    
    # Validate required fields
    required_fields = ['username', 'password', 'organization_id', 'dev_key']
    missing_fields = [field for field in required_fields if not data.get(field)]
    
    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "missing_fields": missing_fields
        }), 400
    
    # In a production environment, these would be stored securely
    # For now, this endpoint validates the configuration
    config = BillcomConfig(
        username=data['username'],
        password=data['password'],
        organization_id=data['organization_id'],
        dev_key=data['dev_key'],
        is_sandbox=data.get('is_sandbox', True)
    )
    
    # Test the configuration by attempting authentication
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        
        # Run authentication test in asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        auth_success = loop.run_until_complete(client.authenticate())
        loop.close()
        
        if auth_success:
            return jsonify({
                "success": True,
                "message": "Bill.com configuration validated successfully",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "error": "Authentication failed",
                "message": "Invalid credentials or configuration"
            }), 401
            
    except Exception as e:
        logger.error(f"Config validation error: {e}")
        return jsonify({
            "error": "Configuration validation failed",
            "message": str(e)
        }), 500

@billcom_bp.route('/test-connection', methods=['POST'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def test_connection():
    """Test Bill.com API connection"""
    config = get_billcom_config()
    
    if not (config.username and config.password and config.organization_id and config.dev_key):
        return jsonify({
            "error": "Bill.com integration not configured",
            "message": "Please configure Bill.com credentials first"
        }), 400
    
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        
        # Test authentication
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_time = datetime.now()
        auth_success = loop.run_until_complete(client.authenticate())
        response_time = (datetime.now() - start_time).total_seconds()
        loop.close()
        
        if auth_success:
            return jsonify({
                "success": True,
                "connection_status": "connected",
                "response_time_ms": round(response_time * 1000, 2),
                "timestamp": datetime.now().isoformat(),
                "session_expires": client.session.expires_at.isoformat() if client.session.expires_at else None
            })
        else:
            return jsonify({
                "success": False,
                "connection_status": "failed",
                "message": "Authentication failed"
            }), 401
            
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            "success": False,
            "connection_status": "error",
            "message": str(e)
        }), 500

@billcom_bp.route('/sync/vendors', methods=['POST'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def sync_vendors():
    """Sync vendors from Bill.com to Unspend"""
    config = get_billcom_config()
    
    if not (config.username and config.password and config.organization_id and config.dev_key):
        return jsonify({
            "error": "Bill.com integration not configured"
        }), 400
    
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        sync_manager = create_billcom_sync_manager(client, database)
        
        # Run sync in asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sync_result = loop.run_until_complete(sync_manager.sync_vendors())
        loop.close()
        
        return jsonify({
            "success": sync_result.success,
            "resource_type": sync_result.resource_type,
            "processed_count": sync_result.processed_count,
            "error_count": sync_result.error_count,
            "errors": sync_result.errors,
            "sync_duration_ms": round(sync_result.sync_duration * 1000, 2),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Vendor sync error: {e}")
        return jsonify({
            "success": False,
            "error": "Vendor sync failed",
            "message": str(e)
        }), 500

@billcom_bp.route('/sync/bills', methods=['POST'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def sync_bills():
    """Sync bills from Bill.com to Unspend"""
    config = get_billcom_config()
    data = request.get_json() or {}
    
    if not (config.username and config.password and config.organization_id and config.dev_key):
        return jsonify({
            "error": "Bill.com integration not configured"
        }), 400
    
    # Get date range from request
    days_back = data.get('days_back', 30)
    
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        sync_manager = create_billcom_sync_manager(client, database)
        
        # Run sync in asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sync_result = loop.run_until_complete(sync_manager.sync_bills(days_back))
        loop.close()
        
        return jsonify({
            "success": sync_result.success,
            "resource_type": sync_result.resource_type,
            "processed_count": sync_result.processed_count,
            "error_count": sync_result.error_count,
            "errors": sync_result.errors,
            "sync_duration_ms": round(sync_result.sync_duration * 1000, 2),
            "days_back": days_back,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Bills sync error: {e}")
        return jsonify({
            "success": False,
            "error": "Bills sync failed",
            "message": str(e)
        }), 500

@billcom_bp.route('/sync/status', methods=['GET'])
@with_error_handling
@with_rate_limiting(RateLimitRule(requests_per_minute=120))
def get_sync_status():
    """Get Bill.com sync status and history"""
    try:
        database = billcom_bp.database
        
        # Get sync history from database
        sync_history = database.get_billcom_sync_history()
        
        # Get basic statistics
        vendor_count = database.get_vendor_count()
        billcom_vendor_count = database.get_billcom_vendor_count()
        
        return jsonify({
            "success": True,
            "sync_history": sync_history,
            "statistics": {
                "total_vendors": vendor_count,
                "billcom_vendors": billcom_vendor_count,
                "last_vendor_sync": sync_history[0]['updated_at'] if sync_history else None,
                "last_bills_sync": None  # Could be enhanced to track bill sync times
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Sync status error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get sync status",
            "message": str(e)
        }), 500

@billcom_bp.route('/vendors', methods=['GET'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def get_billcom_vendors():
    """Fetch vendors directly from Bill.com API"""
    config = get_billcom_config()
    
    if not (config.username and config.password and config.organization_id and config.dev_key):
        return jsonify({
            "error": "Bill.com integration not configured"
        }), 400
    
    max_results = request.args.get('max_results', 100, type=int)
    max_results = min(max_results, 999)  # Cap at API limit
    
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        
        # Fetch vendors from Bill.com
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(client.get_vendors(max_results))
        loop.close()
        
        if result.success:
            return jsonify({
                "success": True,
                "vendors": result.data,
                "count": result.processed_count,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to fetch vendors from Bill.com",
                "errors": result.errors
            }), 500
            
    except Exception as e:
        logger.error(f"Bill.com vendors fetch error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch vendors",
            "message": str(e)
        }), 500

@billcom_bp.route('/bills', methods=['GET'])
@with_error_handling
@with_rate_limiting(BILLCOM_RATE_LIMIT)
def get_billcom_bills():
    """Fetch bills directly from Bill.com API"""
    config = get_billcom_config()
    
    if not (config.username and config.password and config.organization_id and config.dev_key):
        return jsonify({
            "error": "Bill.com integration not configured"
        }), 400
    
    # Get query parameters
    days_back = request.args.get('days_back', 30, type=int)
    max_results = request.args.get('max_results', 100, type=int)
    max_results = min(max_results, 999)  # Cap at API limit
    
    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    try:
        database = billcom_bp.database
        client = create_billcom_client(config, database)
        
        # Fetch bills from Bill.com
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(client.get_bills(start_date, end_date, max_results))
        loop.close()
        
        if result.success:
            return jsonify({
                "success": True,
                "bills": result.data,
                "count": result.processed_count,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "days_back": days_back
                },
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to fetch bills from Bill.com",
                "errors": result.errors
            }), 500
            
    except Exception as e:
        logger.error(f"Bill.com bills fetch error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to fetch bills",
            "message": str(e)
        }), 500

# Error handlers for the blueprint
@billcom_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested Bill.com API endpoint does not exist"
    }), 404

@billcom_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "An error occurred while processing your Bill.com request"
    }), 500