"""
Bill.com API Integration for Unspend
Handles authentication, vendor sync, invoice sync, and bill management
"""
import requests
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import asyncio
import aiohttp
from contextlib import asynccontextmanager

class BillcomSyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class BillcomResourceType(str, Enum):
    VENDOR = "vendor"
    INVOICE = "invoice"
    BILL = "bill"
    PAYMENT = "payment"

@dataclass
class BillcomConfig:
    """Bill.com API configuration"""
    base_url: str = "https://api.bill.com/api/v3"
    sandbox_url: str = "https://api-sandbox.bill.com/api/v3"
    username: str = ""
    password: str = ""
    organization_id: str = ""
    dev_key: str = ""
    is_sandbox: bool = True
    session_timeout: int = 35 * 60  # 35 minutes in seconds

@dataclass
class BillcomSession:
    """Bill.com session management"""
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=35))
    is_valid: bool = False

@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    resource_type: BillcomResourceType
    processed_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    data: List[Dict[str, Any]] = field(default_factory=list)
    sync_duration: float = 0.0

class BillcomAPIClient:
    """Bill.com API client with session management and error handling"""
    
    def __init__(self, config: BillcomConfig, database=None):
        self.config = config
        self.database = database
        self.session = BillcomSession()
        self.logger = logging.getLogger(__name__)
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 1 second between requests
        
    async def authenticate(self) -> bool:
        """Authenticate with Bill.com API and obtain session"""
        try:
            auth_data = {
                "userName": self.config.username,
                "password": self.config.password,
                "organizationId": self.config.organization_id,
                "devKey": self.config.dev_key
            }
            
            url = f"{self._get_base_url()}/login"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=auth_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('response_status') == 0:  # Success
                            self.session.session_id = result['response_data']['sessionId']
                            self.session.created_at = datetime.now()
                            self.session.expires_at = datetime.now() + timedelta(seconds=self.config.session_timeout)
                            self.session.is_valid = True
                            
                            self.logger.info("Successfully authenticated with Bill.com API")
                            return True
                        else:
                            self.logger.error(f"Authentication failed: {result.get('response_message')}")
                            return False
                    else:
                        self.logger.error(f"HTTP error during authentication: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def _get_base_url(self) -> str:
        """Get the appropriate base URL based on sandbox setting"""
        return self.config.sandbox_url if self.config.is_sandbox else self.config.base_url
    
    async def _ensure_valid_session(self) -> bool:
        """Ensure we have a valid session, refresh if needed"""
        if not self.session.is_valid or datetime.now() >= self.session.expires_at:
            return await self.authenticate()
        return True
    
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Tuple[bool, Dict]:
        """Make authenticated request to Bill.com API with rate limiting"""
        if not await self._ensure_valid_session():
            return False, {"error": "Authentication failed"}
        
        # Rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last_request)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        url = f"{self._get_base_url()}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "sessionId": self.session.session_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, json=data, headers=headers) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get('response_status') == 0:
                        return True, result.get('response_data', {})
                    else:
                        error_msg = result.get('response_message', f'HTTP {response.status}')
                        self.logger.error(f"API request failed: {error_msg}")
                        return False, {"error": error_msg}
                        
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return False, {"error": str(e)}
    
    async def get_vendors(self, max_results: int = 999) -> SyncResult:
        """Fetch vendors from Bill.com"""
        start_time = time.time()
        result = SyncResult(success=False, resource_type=BillcomResourceType.VENDOR)
        
        try:
            success, data = await self._make_request("POST", "Crud/Read/Vendor.json", {
                "start": 0,
                "max": max_results,
                "filters": [{"field": "isActive", "op": "=", "value": "1"}]
            })
            
            if success:
                vendors = data.get('Vendor', [])
                result.success = True
                result.processed_count = len(vendors)
                result.data = vendors
                
                self.logger.info(f"Successfully fetched {len(vendors)} vendors from Bill.com")
            else:
                result.errors.append(data.get('error', 'Unknown error'))
                
        except Exception as e:
            result.errors.append(str(e))
            self.logger.error(f"Error fetching vendors: {e}")
        
        result.sync_duration = time.time() - start_time
        return result
    
    async def get_bills(self, start_date: str = None, end_date: str = None, max_results: int = 999) -> SyncResult:
        """Fetch bills (invoices) from Bill.com"""
        start_time = time.time()
        result = SyncResult(success=False, resource_type=BillcomResourceType.BILL)
        
        try:
            # Build filters for date range if provided
            filters = [{"field": "isActive", "op": "=", "value": "1"}]
            
            if start_date:
                filters.append({"field": "invoiceDate", "op": ">=", "value": start_date})
            if end_date:
                filters.append({"field": "invoiceDate", "op": "<=", "value": end_date})
            
            success, data = await self._make_request("POST", "Crud/Read/Bill.json", {
                "start": 0,
                "max": max_results,
                "filters": filters
            })
            
            if success:
                bills = data.get('Bill', [])
                result.success = True
                result.processed_count = len(bills)
                result.data = bills
                
                self.logger.info(f"Successfully fetched {len(bills)} bills from Bill.com")
            else:
                result.errors.append(data.get('error', 'Unknown error'))
                
        except Exception as e:
            result.errors.append(str(e))
            self.logger.error(f"Error fetching bills: {e}")
        
        result.sync_duration = time.time() - start_time
        return result
    
    async def get_invoices(self, start_date: str = None, end_date: str = None, max_results: int = 999) -> SyncResult:
        """Fetch AR invoices from Bill.com"""
        start_time = time.time()
        result = SyncResult(success=False, resource_type=BillcomResourceType.INVOICE)
        
        try:
            filters = [{"field": "isActive", "op": "=", "value": "1"}]
            
            if start_date:
                filters.append({"field": "invoiceDate", "op": ">=", "value": start_date})
            if end_date:
                filters.append({"field": "invoiceDate", "op": "<=", "value": end_date})
            
            success, data = await self._make_request("POST", "Crud/Read/Invoice.json", {
                "start": 0,
                "max": max_results,
                "filters": filters
            })
            
            if success:
                invoices = data.get('Invoice', [])
                result.success = True
                result.processed_count = len(invoices)
                result.data = invoices
                
                self.logger.info(f"Successfully fetched {len(invoices)} invoices from Bill.com")
            else:
                result.errors.append(data.get('error', 'Unknown error'))
                
        except Exception as e:
            result.errors.append(str(e))
            self.logger.error(f"Error fetching invoices: {e}")
        
        result.sync_duration = time.time() - start_time
        return result
    
    def normalize_vendor_data(self, billcom_vendor: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Bill.com vendor format to Unspend vendor format"""
        return {
            "external_id": billcom_vendor.get("id"),
            "canonical_name": billcom_vendor.get("name", "").lower().strip(),
            "display_name": billcom_vendor.get("name", ""),
            "contact_email": billcom_vendor.get("email"),
            "contact_phone": billcom_vendor.get("phone"),
            "address": self._format_address(billcom_vendor),
            "tax_id": billcom_vendor.get("taxId"),
            "payment_terms": billcom_vendor.get("paymentTerms"),
            "notes": f"Synced from Bill.com on {datetime.now().isoformat()}",
            "status": "active" if billcom_vendor.get("isActive") == "1" else "inactive",
            "billcom_data": billcom_vendor  # Store original for reference
        }
    
    def normalize_bill_data(self, billcom_bill: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Bill.com bill format to Unspend invoice format"""
        return {
            "external_id": billcom_bill.get("id"),
            "invoice_number": billcom_bill.get("invoiceNumber"),
            "vendor_name": billcom_bill.get("vendorName"),
            "vendor_id": billcom_bill.get("vendorId"),
            "invoice_date": billcom_bill.get("invoiceDate"),
            "due_date": billcom_bill.get("dueDate"),
            "total_amount": float(billcom_bill.get("amount", 0)),
            "status": billcom_bill.get("approvalStatus"),
            "description": billcom_bill.get("description"),
            "billcom_data": billcom_bill
        }
    
    def _format_address(self, vendor_data: Dict[str, Any]) -> str:
        """Format vendor address from Bill.com data"""
        address_parts = []
        
        if vendor_data.get("address1"):
            address_parts.append(vendor_data["address1"])
        if vendor_data.get("address2"):
            address_parts.append(vendor_data["address2"])
        if vendor_data.get("city"):
            address_parts.append(vendor_data["city"])
        if vendor_data.get("state"):
            address_parts.append(vendor_data["state"])
        if vendor_data.get("zip"):
            address_parts.append(vendor_data["zip"])
        
        return ", ".join(address_parts)

class BillcomSyncManager:
    """Manages synchronization between Unspend and Bill.com"""
    
    def __init__(self, api_client: BillcomAPIClient, database):
        self.api_client = api_client
        self.database = database
        self.logger = logging.getLogger(__name__)
    
    async def sync_vendors(self) -> SyncResult:
        """Sync vendors from Bill.com to Unspend"""
        self.logger.info("Starting vendor sync from Bill.com")
        
        # Fetch vendors from Bill.com
        billcom_result = await self.api_client.get_vendors()
        
        if not billcom_result.success:
            return billcom_result
        
        # Process each vendor
        processed_count = 0
        error_count = 0
        errors = []
        
        for billcom_vendor in billcom_result.data:
            try:
                # Normalize vendor data
                vendor_data = self.api_client.normalize_vendor_data(billcom_vendor)
                
                # Store vendor data using the new database method
                vendor_id = self.database.store_billcom_vendor(vendor_data)
                self.logger.info(f"Processed vendor from Bill.com: {vendor_data['display_name']} (ID: {vendor_id})")
                
                processed_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Error processing vendor {billcom_vendor.get('name', 'Unknown')}: {e}")
                self.logger.error(f"Error processing vendor: {e}")
        
        # Return sync result
        sync_result = SyncResult(
            success=(error_count == 0),
            resource_type=BillcomResourceType.VENDOR,
            processed_count=processed_count,
            error_count=error_count,
            errors=errors,
            sync_duration=billcom_result.sync_duration
        )
        
        self.logger.info(f"Vendor sync completed: {processed_count} processed, {error_count} errors")
        return sync_result
    
    async def sync_bills(self, days_back: int = 30) -> SyncResult:
        """Sync bills from Bill.com to Unspend"""
        self.logger.info(f"Starting bill sync from Bill.com (last {days_back} days)")
        
        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        # Fetch bills from Bill.com
        billcom_result = await self.api_client.get_bills(start_date, end_date)
        
        if not billcom_result.success:
            return billcom_result
        
        # Process each bill
        processed_count = 0
        error_count = 0
        errors = []
        
        for billcom_bill in billcom_result.data:
            try:
                # Normalize bill data
                bill_data = self.api_client.normalize_bill_data(billcom_bill)
                
                # Store bill data using the new database method
                invoice_id = self.database.store_billcom_invoice(bill_data)
                self.logger.info(f"Processed bill from Bill.com: {bill_data['invoice_number']} (ID: {invoice_id})")
                
                processed_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Error processing bill {billcom_bill.get('invoiceNumber', 'Unknown')}: {e}")
                self.logger.error(f"Error processing bill: {e}")
        
        sync_result = SyncResult(
            success=(error_count == 0),
            resource_type=BillcomResourceType.BILL,
            processed_count=processed_count,
            error_count=error_count,
            errors=errors,
            sync_duration=billcom_result.sync_duration
        )
        
        self.logger.info(f"Bill sync completed: {processed_count} processed, {error_count} errors")
        return sync_result
    

def create_billcom_client(config: BillcomConfig, database) -> BillcomAPIClient:
    """Factory function to create Bill.com API client"""
    return BillcomAPIClient(config, database)

def create_billcom_sync_manager(api_client: BillcomAPIClient, database) -> BillcomSyncManager:
    """Factory function to create Bill.com sync manager"""
    return BillcomSyncManager(api_client, database)