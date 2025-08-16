"""
Vendor Management API endpoints for Unspend
Handles vendor CRUD, aliases, performance analytics, and contract renewals
"""
from flask import Blueprint, request, jsonify, g
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timedelta
from api_middleware import with_error_handling, with_rate_limiting, RateLimitRule
from auth_system import require_auth, optional_auth

# Rate limiting rules for vendor management
VENDOR_RATE_LIMIT = RateLimitRule(requests_per_minute=30, requests_per_hour=200, requests_per_day=1000)

def create_vendor_blueprint(database):
    """Create vendor management blueprint with database dependency injection"""
    vendor_bp = Blueprint('vendor', __name__, url_prefix='/api/vendors')
    
    @vendor_bp.route('/', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def list_vendors():
        """List all vendors with basic stats"""
        try:
            status = request.args.get('status', 'active')
            limit = min(int(request.args.get('limit', 100)), 500)
            
            vendors = database.list_vendors(status=status, limit=limit)
            
            return jsonify({
                "success": True,
                "vendors": vendors,
                "total_count": len(vendors),
                "filters": {"status": status, "limit": limit}
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/', methods=['POST'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def create_vendor():
        """Create a new vendor"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body required"}), 400
            
            canonical_name = data.get('canonical_name', '').strip()
            display_name = data.get('display_name', '').strip()
            
            if not canonical_name or not display_name:
                return jsonify({"error": "canonical_name and display_name are required"}), 400
            
            # Create vendor with optional fields
            vendor_id = database.create_vendor(
                canonical_name=canonical_name,
                display_name=display_name,
                industry=data.get('industry'),
                contact_email=data.get('contact_email'),
                contact_phone=data.get('contact_phone'),
                address=data.get('address'),
                tax_id=data.get('tax_id'),
                payment_terms=data.get('payment_terms'),
                preferred_payment_method=data.get('preferred_payment_method'),
                notes=data.get('notes'),
                status=data.get('status', 'active')
            )
            
            return jsonify({
                "success": True,
                "vendor_id": vendor_id,
                "message": f"Vendor '{display_name}' created successfully"
            }), 201
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def get_vendor_details(vendor_id):
        """Get detailed vendor information including analytics"""
        try:
            analytics = database.get_vendor_analytics(vendor_id)
            
            if not analytics.get('vendor'):
                return jsonify({"error": "Vendor not found"}), 404
            
            return jsonify({
                "success": True,
                "vendor_analytics": analytics
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>/aliases', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def get_vendor_aliases(vendor_id):
        """Get all aliases for a vendor"""
        try:
            aliases = database.get_vendor_aliases(vendor_id)
            
            return jsonify({
                "success": True,
                "vendor_id": vendor_id,
                "aliases": aliases,
                "total_count": len(aliases)
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>/aliases', methods=['POST'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def add_vendor_alias(vendor_id):
        """Add a new alias for a vendor"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body required"}), 400
            
            alias_name = data.get('alias_name', '').strip()
            if not alias_name:
                return jsonify({"error": "alias_name is required"}), 400
            
            confidence_score = float(data.get('confidence_score', 1.0))
            auto_generated = data.get('auto_generated', False)
            
            success = database.add_vendor_alias(
                vendor_id=vendor_id,
                alias_name=alias_name,
                confidence_score=confidence_score,
                auto_generated=auto_generated
            )
            
            if success:
                return jsonify({
                    "success": True,
                    "message": f"Alias '{alias_name}' added to vendor {vendor_id}"
                }), 201
            else:
                return jsonify({"error": "Alias already exists for this vendor"}), 409
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>/performance', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def get_vendor_performance(vendor_id):
        """Get vendor performance history"""
        try:
            months = int(request.args.get('months', 12))
            performance_history = database.get_vendor_performance(vendor_id, months)
            
            return jsonify({
                "success": True,
                "vendor_id": vendor_id,
                "performance_history": performance_history,
                "period_months": months
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>/performance', methods=['POST'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def update_vendor_performance(vendor_id):
        """Update vendor performance metrics for a period"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body required"}), 400
            
            period_start = data.get('period_start')
            period_end = data.get('period_end')
            metrics = data.get('metrics', {})
            
            if not period_start or not period_end:
                return jsonify({"error": "period_start and period_end are required"}), 400
            
            success = database.update_vendor_performance(
                vendor_id=vendor_id,
                period_start=period_start,
                period_end=period_end,
                metrics=metrics
            )
            
            if success:
                return jsonify({
                    "success": True,
                    "message": f"Performance metrics updated for vendor {vendor_id}"
                })
            else:
                return jsonify({"error": "Failed to update performance metrics"}), 500
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/renewals', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def get_upcoming_renewals():
        """Get upcoming contract renewals"""
        try:
            days_ahead = int(request.args.get('days_ahead', 90))
            renewals = database.get_upcoming_renewals(days_ahead)
            
            return jsonify({
                "success": True,
                "upcoming_renewals": renewals,
                "total_count": len(renewals),
                "days_ahead": days_ahead
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/<int:vendor_id>/renewals', methods=['POST'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def create_contract_renewal(vendor_id):
        """Create contract renewal tracking for a vendor"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body required"}), 400
            
            contract_id = data.get('contract_id')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if not all([contract_id, start_date, end_date]):
                return jsonify({"error": "contract_id, start_date, and end_date are required"}), 400
            
            renewal_id = database.create_contract_renewal(
                contract_id=contract_id,
                vendor_id=vendor_id,
                start_date=start_date,
                end_date=end_date,
                auto_renew=data.get('auto_renew', False),
                renewal_notice_days=data.get('renewal_notice_days', 30),
                renewal_status=data.get('renewal_status', 'pending'),
                next_review_date=data.get('next_review_date'),
                notes=data.get('notes')
            )
            
            return jsonify({
                "success": True,
                "renewal_id": renewal_id,
                "message": f"Contract renewal tracking created for vendor {vendor_id}"
            }), 201
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/search', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def search_vendors():
        """Search vendors by name (including aliases)"""
        try:
            query = request.args.get('q', '').strip()
            
            if not query:
                return jsonify({"error": "Search query 'q' parameter is required"}), 400
            
            vendor = database.get_vendor_by_name(query)
            
            if vendor:
                return jsonify({
                    "success": True,
                    "vendor": vendor,
                    "found": True
                })
            else:
                return jsonify({
                    "success": True,
                    "vendor": None,
                    "found": False,
                    "message": f"No vendor found matching '{query}'"
                })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @vendor_bp.route('/analytics', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(VENDOR_RATE_LIMIT)
    @require_auth
    def get_vendor_analytics_summary():
        """Get aggregated vendor analytics for dashboard"""
        try:
            # Get top vendors by activity
            vendors = database.list_vendors(status='active', limit=50)
            
            # Calculate summary metrics
            total_vendors = len(vendors)
            vendors_with_aliases = len([v for v in vendors if v['alias_count'] > 0])
            vendors_with_renewals = len([v for v in vendors if v['renewal_count'] > 0])
            
            # Get upcoming renewals count
            upcoming_renewals = database.get_upcoming_renewals(30)
            critical_renewals = len([r for r in upcoming_renewals if r['renewal_status'] == 'pending'])
            
            return jsonify({
                "success": True,
                "vendor_summary": {
                    "total_vendors": total_vendors,
                    "vendors_with_aliases": vendors_with_aliases,
                    "vendors_with_renewals": vendors_with_renewals,
                    "upcoming_renewals_30_days": len(upcoming_renewals),
                    "critical_renewals": critical_renewals
                },
                "top_vendors": vendors[:10]  # Top 10 for dashboard
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return vendor_bp