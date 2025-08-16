"""
Data Export & Reporting System for Unspend
Handles CSV/PDF generation for reconciliation reports, vendor performance, renewals, and audit trails
"""
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from flask import Blueprint, request, jsonify, g, Response, make_response
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from api_middleware import with_error_handling, with_rate_limiting, RateLimitRule
from auth_system import require_auth

# Rate limiting for export operations (more restrictive due to resource usage)
EXPORT_RATE_LIMIT = RateLimitRule(requests_per_minute=10, requests_per_hour=50, requests_per_day=200)

def create_reporting_blueprint(database):
    """Create reporting and export blueprint"""
    reporting_bp = Blueprint('reporting', __name__, url_prefix='/api/reports')
    
    @reporting_bp.route('/reconciliations/export', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(EXPORT_RATE_LIMIT)
    @require_auth
    def export_reconciliation_report():
        """Export reconciliation report as CSV or PDF"""
        try:
            # Get query parameters
            format_type = request.args.get('format', 'csv').lower()
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            vendor_id = request.args.get('vendor_id', type=int)
            user_id = g.current_user.id  # Always filter by current user
            
            if format_type not in ['csv', 'pdf']:
                return jsonify({"error": "Format must be 'csv' or 'pdf'"}), 400
            
            # Get reconciliation data
            report_data = database.get_reconciliation_report_data(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                vendor_id=vendor_id
            )
            
            if format_type == 'csv':
                return _generate_reconciliation_csv(report_data, start_date, end_date)
            else:
                return _generate_reconciliation_pdf(report_data, start_date, end_date)
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @reporting_bp.route('/vendors/performance/export', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(EXPORT_RATE_LIMIT)
    @require_auth
    def export_vendor_performance_report():
        """Export vendor performance report as CSV or PDF"""
        try:
            format_type = request.args.get('format', 'csv').lower()
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            vendor_id = request.args.get('vendor_id', type=int)
            
            if format_type not in ['csv', 'pdf']:
                return jsonify({"error": "Format must be 'csv' or 'pdf'"}), 400
            
            # Get vendor performance data
            report_data = database.get_vendor_performance_report_data(
                vendor_id=vendor_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if format_type == 'csv':
                return _generate_vendor_performance_csv(report_data, start_date, end_date)
            else:
                return _generate_vendor_performance_pdf(report_data, start_date, end_date)
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @reporting_bp.route('/renewals/export', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(EXPORT_RATE_LIMIT)
    @require_auth
    def export_contract_renewal_report():
        """Export contract renewal report as CSV or PDF"""
        try:
            format_type = request.args.get('format', 'csv').lower()
            days_ahead = request.args.get('days_ahead', 365, type=int)
            vendor_id = request.args.get('vendor_id', type=int)
            
            if format_type not in ['csv', 'pdf']:
                return jsonify({"error": "Format must be 'csv' or 'pdf'"}), 400
            
            # Get renewal data
            report_data = database.get_contract_renewal_report_data(
                days_ahead=days_ahead,
                vendor_id=vendor_id
            )
            
            if format_type == 'csv':
                return _generate_renewal_csv(report_data, days_ahead)
            else:
                return _generate_renewal_pdf(report_data, days_ahead)
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @reporting_bp.route('/audit-trail/export', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(EXPORT_RATE_LIMIT)
    @require_auth
    def export_audit_trail_report():
        """Export audit trail report as CSV (compliance focused)"""
        try:
            format_type = request.args.get('format', 'csv').lower()
            table_name = request.args.get('table_name')
            operation = request.args.get('operation')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            limit = min(request.args.get('limit', 1000, type=int), 10000)
            
            if format_type not in ['csv', 'pdf']:
                return jsonify({"error": "Format must be 'csv' or 'pdf'"}), 400
            
            # Get audit trail data
            report_data = database.get_audit_trail_report_data(
                table_name=table_name,
                operation=operation,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            
            if format_type == 'csv':
                return _generate_audit_trail_csv(report_data, start_date, end_date)
            else:
                return _generate_audit_trail_pdf(report_data, start_date, end_date)
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @reporting_bp.route('/summary', methods=['GET'])
    @with_error_handling
    @with_rate_limiting(EXPORT_RATE_LIMIT)
    @require_auth
    def get_reporting_summary():
        """Get summary data for all available reports"""
        try:
            user_id = g.current_user.id
            
            # Get counts for each report type
            reconciliation_count = len(database.get_reconciliation_report_data(user_id=user_id))
            vendor_count = len(database.get_vendor_performance_report_data())
            renewal_count = len(database.get_contract_renewal_report_data(days_ahead=90))
            audit_count = len(database.get_audit_trail_report_data(limit=100))
            
            return jsonify({
                "success": True,
                "summary": {
                    "available_reports": {
                        "reconciliations": {
                            "total_records": reconciliation_count,
                            "export_formats": ["csv", "pdf"],
                            "filters": ["start_date", "end_date", "vendor_id"]
                        },
                        "vendor_performance": {
                            "total_records": vendor_count,
                            "export_formats": ["csv", "pdf"],
                            "filters": ["start_date", "end_date", "vendor_id"]
                        },
                        "contract_renewals": {
                            "total_records": renewal_count,
                            "export_formats": ["csv", "pdf"],
                            "filters": ["days_ahead", "vendor_id"]
                        },
                        "audit_trail": {
                            "total_records": audit_count,
                            "export_formats": ["csv", "pdf"],
                            "filters": ["table_name", "operation", "start_date", "end_date", "limit"]
                        }
                    },
                    "rate_limits": {
                        "requests_per_minute": EXPORT_RATE_LIMIT.requests_per_minute,
                        "requests_per_hour": EXPORT_RATE_LIMIT.requests_per_hour,
                        "requests_per_day": EXPORT_RATE_LIMIT.requests_per_day
                    }
                }
            })
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # CSV Generation Functions
    
    def _generate_reconciliation_csv(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate CSV for reconciliation report"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Reconciliation ID', 'Date', 'Method', 'Flags Count', 'Status',
            'Vendor Name', 'Vendor Industry', 'Contract ID', 'Contract Confidence',
            'Invoice ID', 'Invoice Confidence', 'Contract Value', 'Invoice Amount',
            'Payment Terms', 'Service Category'
        ])
        
        # Data rows
        for item in data:
            contract_data = item['contract']['data']
            invoice_data = item['invoice']['data']
            vendor = item['vendor']
            
            writer.writerow([
                item['reconciliation_id'],
                item['reconciliation_date'],
                item['reconciliation_method'],
                item['flags_count'],
                'Success' if item['flags_count'] == 0 else 'Has Issues',
                vendor['name'] if vendor else 'Unknown',
                vendor['industry'] if vendor else '',
                item['contract']['id'],
                f"{item['contract']['confidence']:.2f}",
                item['invoice']['id'], 
                f"{item['invoice']['confidence']:.2f}",
                contract_data.get('cap_total', {}).get('value', ''),
                invoice_data.get('total_amount', {}).get('value', ''),
                contract_data.get('payment_terms', {}).get('value', ''),
                contract_data.get('service_category', {}).get('value', '')
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=reconciliation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
    
    def _generate_vendor_performance_csv(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate CSV for vendor performance report"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Vendor ID', 'Vendor Name', 'Industry', 'Contact Email', 'Payment Terms',
            'Period Start', 'Period End', 'Total Contracts', 'Total Invoices',
            'Total Reconciliations', 'Successful Reconciliations', 'Success Rate %',
            'Total Flags', 'Avg Processing Time', 'Avg Confidence Score', 'Total Amount',
            'Total Aliases', 'Total Renewals'
        ])
        
        # Data rows
        for item in data:
            success_rate = 0
            if item['total_reconciliations'] and item['total_reconciliations'] > 0:
                success_rate = (item['successful_reconciliations'] / item['total_reconciliations']) * 100
            
            writer.writerow([
                item['vendor_id'],
                item['display_name'],
                item['industry'] or '',
                item['contact_email'] or '',
                item['payment_terms'] or '',
                item['period_start'] or '',
                item['period_end'] or '',
                item['total_contracts'] or 0,
                item['total_invoices'] or 0,
                item['total_reconciliations'] or 0,
                item['successful_reconciliations'] or 0,
                f"{success_rate:.1f}%",
                item['total_flags'] or 0,
                f"{item['avg_processing_time'] or 0:.2f}s",
                f"{item['avg_confidence_score'] or 0:.2f}",
                f"${item['total_amount'] or 0:.2f}",
                item['total_aliases'] or 0,
                item['total_renewals'] or 0
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=vendor_performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
    
    def _generate_renewal_csv(data: List[Dict], days_ahead: int) -> Response:
        """Generate CSV for contract renewal report"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Renewal ID', 'Vendor Name', 'Vendor Contact', 'Contract Start', 'Contract End',
            'Days Until End', 'Auto Renew', 'Notice Days', 'Status', 'Next Review',
            'Contract Value', 'Service Category', 'Renewal Notes'
        ])
        
        # Data rows
        for item in data:
            contract_data = item['contract']['data']
            vendor = item['vendor']
            
            writer.writerow([
                item['renewal_id'],
                vendor['name'],
                vendor['contact_email'] or '',
                item['start_date'],
                item['end_date'],
                item['days_until_end'],
                'Yes' if item['auto_renew'] else 'No',
                item['renewal_notice_days'],
                item['renewal_status'],
                item['next_review_date'] or '',
                contract_data.get('cap_total', {}).get('value', ''),
                contract_data.get('service_category', {}).get('value', ''),
                item['renewal_notes'] or ''
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=contract_renewals_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
    
    def _generate_audit_trail_csv(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate CSV for audit trail report"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Audit ID', 'Timestamp', 'Operation', 'Table Name', 'Record ID',
            'User ID', 'Changes Summary'
        ])
        
        # Data rows
        for item in data:
            changes_summary = json.dumps(item['changes']) if item['changes'] else ''
            
            writer.writerow([
                item['audit_id'],
                item['timestamp'],
                item['operation'],
                item['table_name'],
                item['record_id'],
                item['user_id'],
                changes_summary
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=audit_trail_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
    
    # PDF Generation Functions (simplified - would need full reportlab implementation)
    
    def _generate_reconciliation_pdf(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate PDF for reconciliation report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title = Paragraph(f"Reconciliation Report", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Summary info
        period_info = f"Period: {start_date or 'All'} to {end_date or 'All'}"
        elements.append(Paragraph(period_info, styles['Normal']))
        elements.append(Paragraph(f"Total Records: {len(data)}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Table data
        table_data = [['ID', 'Date', 'Vendor', 'Flags', 'Status']]
        for item in data[:50]:  # Limit to first 50 for PDF
            vendor_name = item['vendor']['name'] if item['vendor'] else 'Unknown'
            status = 'Success' if item['flags_count'] == 0 else 'Issues'
            table_data.append([
                str(item['reconciliation_id']),
                item['reconciliation_date'][:10],  # Date only
                vendor_name[:20],  # Truncate long names
                str(item['flags_count']),
                status
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        buffer.seek(0)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reconciliation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        return response
    
    def _generate_vendor_performance_pdf(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate simplified PDF for vendor performance report"""
        # Similar structure to reconciliation PDF but with vendor-specific data
        # Implementation would follow same pattern as above
        return jsonify({"message": "PDF generation for vendor performance will be implemented"}), 501
    
    def _generate_renewal_pdf(data: List[Dict], days_ahead: int) -> Response:
        """Generate simplified PDF for renewal report"""
        # Similar structure to reconciliation PDF but with renewal-specific data
        return jsonify({"message": "PDF generation for renewals will be implemented"}), 501
    
    def _generate_audit_trail_pdf(data: List[Dict], start_date: str, end_date: str) -> Response:
        """Generate simplified PDF for audit trail report"""
        # Similar structure to reconciliation PDF but with audit-specific data
        return jsonify({"message": "PDF generation for audit trail will be implemented"}), 501
    
    return reporting_bp