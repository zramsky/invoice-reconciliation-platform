"""
Simple database layer for Unspend - stores processed documents and audit trails
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str = "unspend.db"):
        self.db_path = db_path
        self.init_tables()
    
    def init_tables(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Contracts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_hash TEXT UNIQUE NOT NULL,
                    raw_text TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    extraction_confidence REAL DEFAULT 0.0,
                    extraction_method TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Invoices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_hash TEXT UNIQUE NOT NULL,
                    raw_text TEXT NOT NULL,
                    extracted_json TEXT NOT NULL,
                    extraction_confidence REAL DEFAULT 0.0,
                    extraction_method TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Reconciliations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER,
                    invoice_id INTEGER,
                    reconciliation_json TEXT NOT NULL,
                    method TEXT DEFAULT 'unknown',
                    flags_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES contracts (id),
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
                )
            """)
            
            # Audit trails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_trails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    record_id INTEGER,
                    changes_json TEXT,
                    user_id TEXT DEFAULT 'system',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # LLM calls cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    model TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1
                )
            """)
            
            # Vendor management tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    industry TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    address TEXT,
                    tax_id TEXT,
                    payment_terms TEXT,
                    preferred_payment_method TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Vendor aliases table for business name variations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendor_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_id INTEGER NOT NULL,
                    alias_name TEXT NOT NULL,
                    confidence_score REAL DEFAULT 1.0,
                    auto_generated BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vendor_id) REFERENCES vendors (id) ON DELETE CASCADE,
                    UNIQUE(vendor_id, alias_name)
                )
            """)
            
            # Contract renewals tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contract_renewals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    vendor_id INTEGER NOT NULL,
                    current_start_date TEXT NOT NULL,
                    current_end_date TEXT NOT NULL,
                    auto_renew BOOLEAN DEFAULT FALSE,
                    renewal_notice_days INTEGER DEFAULT 30,
                    renewal_status TEXT DEFAULT 'pending',
                    notification_sent_at TIMESTAMP,
                    next_review_date TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contract_id) REFERENCES contracts (id) ON DELETE CASCADE,
                    FOREIGN KEY (vendor_id) REFERENCES vendors (id) ON DELETE CASCADE
                )
            """)
            
            # Vendor performance metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendor_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_id INTEGER NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    total_contracts INTEGER DEFAULT 0,
                    total_invoices INTEGER DEFAULT 0,
                    total_reconciliations INTEGER DEFAULT 0,
                    successful_reconciliations INTEGER DEFAULT 0,
                    total_flags INTEGER DEFAULT 0,
                    avg_processing_time REAL DEFAULT 0.0,
                    avg_confidence_score REAL DEFAULT 0.0,
                    total_amount REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vendor_id) REFERENCES vendors (id) ON DELETE CASCADE,
                    UNIQUE(vendor_id, period_start, period_end)
                )
            """)
            
            # Create performance indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contracts_hash ON contracts(text_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contracts_confidence ON contracts(extraction_confidence)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contracts_created ON contracts(created_at)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_hash ON invoices(text_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_confidence ON invoices(extraction_confidence)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(created_at)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reconciliations_flags ON reconciliations(flags_count)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reconciliations_created ON reconciliations(created_at)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_trails(operation)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_trails(table_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_trails(timestamp)")
            
            # Vendor management indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendors_canonical ON vendors(canonical_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendors_status ON vendors(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendor_aliases_name ON vendor_aliases(alias_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contract_renewals_end_date ON contract_renewals(current_end_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contract_renewals_status ON contract_renewals(renewal_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendor_performance_period ON vendor_performance(period_start, period_end)")
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def _compute_text_hash(self, text: str) -> str:
        """Compute SHA-256 hash of text for deduplication"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def store_contract(self, raw_text: str, extracted_json: Dict[str, Any], 
                      confidence: float = 0.0, method: str = 'unknown') -> int:
        """Store contract with extracted data"""
        text_hash = self._compute_text_hash(raw_text)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute("SELECT id FROM contracts WHERE text_hash = ?", (text_hash,))
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']
            
            # Insert new contract
            cursor.execute("""
                INSERT INTO contracts (text_hash, raw_text, extracted_json, 
                                     extraction_confidence, extraction_method)
                VALUES (?, ?, ?, ?, ?)
            """, (text_hash, raw_text, json.dumps(extracted_json), confidence, method))
            
            contract_id = cursor.lastrowid
            
            # Audit trail
            self._audit_log(conn, 'INSERT', 'contracts', contract_id, {
                'text_length': len(raw_text),
                'confidence': confidence,
                'method': method
            })
            
            conn.commit()
            return contract_id
    
    def store_invoice(self, raw_text: str, extracted_json: Dict[str, Any], 
                     confidence: float = 0.0, method: str = 'unknown') -> int:
        """Store invoice with extracted data"""
        text_hash = self._compute_text_hash(raw_text)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute("SELECT id FROM invoices WHERE text_hash = ?", (text_hash,))
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']
            
            # Insert new invoice
            cursor.execute("""
                INSERT INTO invoices (text_hash, raw_text, extracted_json, 
                                    extraction_confidence, extraction_method)
                VALUES (?, ?, ?, ?, ?)
            """, (text_hash, raw_text, json.dumps(extracted_json), confidence, method))
            
            invoice_id = cursor.lastrowid
            
            # Audit trail
            self._audit_log(conn, 'INSERT', 'invoices', invoice_id, {
                'text_length': len(raw_text),
                'confidence': confidence,
                'method': method
            })
            
            conn.commit()
            return invoice_id
    
    def store_reconciliation(self, contract_id: int, invoice_id: int, 
                           reconciliation_result: Dict[str, Any], method: str = 'unknown') -> int:
        """Store reconciliation result"""
        flags_count = len(reconciliation_result.get('flags', []))
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO reconciliations (contract_id, invoice_id, reconciliation_json, 
                                           method, flags_count)
                VALUES (?, ?, ?, ?, ?)
            """, (contract_id, invoice_id, json.dumps(reconciliation_result), method, flags_count))
            
            reconciliation_id = cursor.lastrowid
            
            # Audit trail
            self._audit_log(conn, 'INSERT', 'reconciliations', reconciliation_id, {
                'contract_id': contract_id,
                'invoice_id': invoice_id,
                'flags_count': flags_count,
                'method': method
            })
            
            conn.commit()
            return reconciliation_id
    
    def get_contract(self, contract_id: int) -> Optional[Dict[str, Any]]:
        """Get contract by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'text_hash': row['text_hash'],
                    'raw_text': row['raw_text'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence'],
                    'extraction_method': row['extraction_method'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            return None
    
    def get_invoice(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Get invoice by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'text_hash': row['text_hash'],
                    'raw_text': row['raw_text'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence'],
                    'extraction_method': row['extraction_method'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            return None
    
    def get_contract_by_hash(self, text_hash: str) -> Optional[Dict[str, Any]]:
        """Get contract by text hash"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contracts WHERE text_hash = ?", (text_hash,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence']
                }
            return None
    
    def get_invoice_by_hash(self, text_hash: str) -> Optional[Dict[str, Any]]:
        """Get invoice by text hash"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE text_hash = ?", (text_hash,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'extracted_json': json.loads(row['extracted_json']),
                    'extraction_confidence': row['extraction_confidence']
                }
            return None
    
    def cache_llm_response(self, cache_key: str, model: str, prompt_hash: str, 
                          response: Dict[str, Any]) -> None:
        """Cache LLM response"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Try to insert, update access count if exists
            cursor.execute("""
                INSERT OR REPLACE INTO llm_cache (cache_key, model, prompt_hash, 
                                                 response_json, access_count)
                VALUES (?, ?, ?, ?, 
                       COALESCE((SELECT access_count + 1 FROM llm_cache WHERE cache_key = ?), 1))
            """, (cache_key, model, prompt_hash, json.dumps(response), cache_key))
            
            conn.commit()
    
    def get_cached_llm_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached LLM response"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT response_json FROM llm_cache 
                WHERE cache_key = ? AND created_at > datetime('now', '-7 days')
            """, (cache_key,))
            
            row = cursor.fetchone()
            if row:
                # Update access count
                cursor.execute("""
                    UPDATE llm_cache SET access_count = access_count + 1 
                    WHERE cache_key = ?
                """, (cache_key,))
                conn.commit()
                
                return json.loads(row['response_json'])
            return None
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count contracts
            cursor.execute("SELECT COUNT(*) as count FROM contracts")
            contracts_count = cursor.fetchone()['count']
            
            # Count invoices
            cursor.execute("SELECT COUNT(*) as count FROM invoices")
            invoices_count = cursor.fetchone()['count']
            
            # Count reconciliations
            cursor.execute("SELECT COUNT(*) as count FROM reconciliations")
            reconciliations_count = cursor.fetchone()['count']
            
            # Count flags by severity
            cursor.execute("""
                SELECT COUNT(*) as error_flags FROM reconciliations 
                WHERE flags_count > 0
            """)
            error_flags_count = cursor.fetchone()['error_flags']
            
            # Cache stats
            cursor.execute("SELECT COUNT(*) as count, SUM(access_count) as total_hits FROM llm_cache")
            cache_row = cursor.fetchone()
            cache_entries = cache_row['count']
            cache_hits = cache_row['total_hits'] or 0
            
            # Recent reconciliations with flags
            cursor.execute("""
                SELECT r.id, r.flags_count, r.created_at, r.method,
                       c.extracted_json as contract_json,
                       i.extracted_json as invoice_json
                FROM reconciliations r
                JOIN contracts c ON r.contract_id = c.id
                JOIN invoices i ON r.invoice_id = i.id
                WHERE r.flags_count > 0
                ORDER BY r.created_at DESC
                LIMIT 10
            """)
            
            recent_flags = []
            for row in cursor.fetchall():
                contract_data = json.loads(row['contract_json'])
                invoice_data = json.loads(row['invoice_json'])
                
                recent_flags.append({
                    'reconciliation_id': row['id'],
                    'flags_count': row['flags_count'],
                    'created_at': row['created_at'],
                    'method': row['method'],
                    'vendor': contract_data.get('vendor', {}).get('value', 'Unknown'),
                    'invoice_no': invoice_data.get('invoice_no', {}).get('value', 'Unknown')
                })
            
            return {
                'total_contracts': contracts_count,
                'total_invoices': invoices_count,
                'total_reconciliations': reconciliations_count,
                'total_exceptions': error_flags_count,
                'cache_entries': cache_entries,
                'cache_hits': cache_hits,
                'recent_flags': recent_flags
            }
    
    def get_vendor_count(self) -> int:
        """Get total vendor count"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM vendors")
            return cursor.fetchone()['count']
    
    def store_billcom_vendor(self, vendor_data: Dict[str, Any]) -> int:
        """Store vendor data from Bill.com sync"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if vendor already exists
            cursor.execute(
                "SELECT id FROM vendors WHERE canonical_name = ?",
                (vendor_data.get('canonical_name'),)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing vendor
                cursor.execute("""
                    UPDATE vendors SET
                        display_name = ?,
                        contact_email = ?,
                        contact_phone = ?,
                        address = ?,
                        tax_id = ?,
                        notes = ?,
                        status = ?,
                        external_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    vendor_data.get('display_name'),
                    vendor_data.get('contact_email'),
                    vendor_data.get('contact_phone'),
                    vendor_data.get('address'),
                    vendor_data.get('tax_id'),
                    vendor_data.get('notes'),
                    vendor_data.get('status', 'active'),
                    vendor_data.get('external_id'),
                    existing['id']
                ))
                conn.commit()
                return existing['id']
            else:
                # Create new vendor
                cursor.execute("""
                    INSERT INTO vendors (
                        canonical_name, display_name, contact_email, contact_phone,
                        address, tax_id, notes, status, external_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vendor_data.get('canonical_name'),
                    vendor_data.get('display_name'),
                    vendor_data.get('contact_email'),
                    vendor_data.get('contact_phone'),
                    vendor_data.get('address'),
                    vendor_data.get('tax_id'),
                    vendor_data.get('notes'),
                    vendor_data.get('status', 'active'),
                    vendor_data.get('external_id')
                ))
                conn.commit()
                return cursor.lastrowid
    
    def store_billcom_invoice(self, invoice_data: Dict[str, Any]) -> int:
        """Store invoice data from Bill.com sync"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create a synthetic text hash for Bill.com invoices
            invoice_text = f"Bill.com Invoice: {invoice_data.get('invoice_number', '')} - {invoice_data.get('vendor_name', '')} - ${invoice_data.get('total_amount', 0)}"
            text_hash = hashlib.md5(invoice_text.encode()).hexdigest()
            
            # Check if invoice already exists
            cursor.execute(
                "SELECT id FROM invoices WHERE text_hash = ?",
                (text_hash,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing invoice
                cursor.execute("""
                    UPDATE invoices SET
                        raw_text = ?,
                        extracted_json = ?,
                        extraction_confidence = 1.0,
                        extraction_method = 'billcom_api',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    invoice_text,
                    json.dumps(invoice_data),
                    existing['id']
                ))
                conn.commit()
                return existing['id']
            else:
                # Create new invoice
                cursor.execute("""
                    INSERT INTO invoices (
                        text_hash, raw_text, extracted_json,
                        extraction_confidence, extraction_method
                    ) VALUES (?, ?, ?, 1.0, 'billcom_api')
                """, (
                    text_hash,
                    invoice_text,
                    json.dumps(invoice_data)
                ))
                conn.commit()
                return cursor.lastrowid
    
    def get_billcom_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get Bill.com sync history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get vendors synced from Bill.com
            cursor.execute("""
                SELECT 'vendor' as type, id, display_name as name, 
                       created_at, updated_at, external_id
                FROM vendors
                WHERE external_id IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'type': row['type'],
                    'id': row['id'],
                    'name': row['name'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'external_id': row['external_id']
                })
            
            return results
    
    def get_billcom_vendor_count(self) -> int:
        """Get count of vendors synced from Bill.com"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM vendors WHERE external_id IS NOT NULL")
            return cursor.fetchone()['count']
    
    def get_low_confidence_extractions(self, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Get extractions with low confidence for review"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            results = []
            
            # Low confidence contracts
            cursor.execute("""
                SELECT 'contract' as type, id, extraction_confidence, created_at,
                       extracted_json
                FROM contracts 
                WHERE extraction_confidence < ?
                ORDER BY created_at DESC
            """, (threshold,))
            
            for row in cursor.fetchall():
                extracted = json.loads(row['extracted_json'])
                results.append({
                    'type': row['type'],
                    'id': row['id'],
                    'confidence': row['extraction_confidence'],
                    'created_at': row['created_at'],
                    'vendor': extracted.get('vendor', {}).get('value', 'Unknown')
                })
            
            # Low confidence invoices
            cursor.execute("""
                SELECT 'invoice' as type, id, extraction_confidence, created_at,
                       extracted_json
                FROM invoices 
                WHERE extraction_confidence < ?
                ORDER BY created_at DESC
            """, (threshold,))
            
            for row in cursor.fetchall():
                extracted = json.loads(row['extracted_json'])
                results.append({
                    'type': row['type'],
                    'id': row['id'],
                    'confidence': row['extraction_confidence'],
                    'created_at': row['created_at'],
                    'vendor': extracted.get('vendor', {}).get('value', 'Unknown'),
                    'invoice_no': extracted.get('invoice_no', {}).get('value', 'Unknown')
                })
            
            return sorted(results, key=lambda x: x['created_at'], reverse=True)
    
    def _audit_log(self, conn, operation: str, table_name: str, record_id: int, 
                  changes: Dict[str, Any], user_id: str = 'system'):
        """Add audit log entry"""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_trails (operation, table_name, record_id, changes_json, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (operation, table_name, record_id, json.dumps(changes), user_id))
    
    def cleanup_old_cache(self, days: int = 7):
        """Clean up old cache entries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM llm_cache 
                WHERE created_at < datetime('now', '-{} days')
            """.format(days))
            
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
    
    # Vendor Management Methods
    
    def create_vendor(self, canonical_name: str, display_name: str, **kwargs) -> int:
        """Create a new vendor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if vendor already exists
            cursor.execute("SELECT id FROM vendors WHERE canonical_name = ?", (canonical_name,))
            existing = cursor.fetchone()
            if existing:
                return existing['id']
            
            # Insert new vendor
            cursor.execute("""
                INSERT INTO vendors (canonical_name, display_name, industry, contact_email, 
                                   contact_phone, address, tax_id, payment_terms, 
                                   preferred_payment_method, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                canonical_name, display_name, 
                kwargs.get('industry'), kwargs.get('contact_email'),
                kwargs.get('contact_phone'), kwargs.get('address'),
                kwargs.get('tax_id'), kwargs.get('payment_terms'),
                kwargs.get('preferred_payment_method'), kwargs.get('notes'),
                kwargs.get('status', 'active')
            ))
            
            vendor_id = cursor.lastrowid
            
            # Audit trail
            self._audit_log(conn, 'INSERT', 'vendors', vendor_id, {
                'canonical_name': canonical_name,
                'display_name': display_name
            })
            
            conn.commit()
            return vendor_id
    
    def get_vendor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get vendor by canonical name or alias"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Try canonical name first
            cursor.execute("""
                SELECT * FROM vendors WHERE canonical_name = ? OR display_name = ?
            """, (name, name))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            
            # Try aliases
            cursor.execute("""
                SELECT v.* FROM vendors v
                JOIN vendor_aliases va ON v.id = va.vendor_id
                WHERE va.alias_name = ?
            """, (name,))
            row = cursor.fetchone()
            
            return dict(row) if row else None
    
    def add_vendor_alias(self, vendor_id: int, alias_name: str, confidence_score: float = 1.0, 
                        auto_generated: bool = False) -> bool:
        """Add alias for a vendor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO vendor_aliases (vendor_id, alias_name, confidence_score, auto_generated)
                    VALUES (?, ?, ?, ?)
                """, (vendor_id, alias_name, confidence_score, auto_generated))
                
                self._audit_log(conn, 'INSERT', 'vendor_aliases', cursor.lastrowid, {
                    'vendor_id': vendor_id,
                    'alias_name': alias_name,
                    'auto_generated': auto_generated
                })
                
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_vendor_aliases(self, vendor_id: int) -> List[Dict[str, Any]]:
        """Get all aliases for a vendor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM vendor_aliases WHERE vendor_id = ? ORDER BY confidence_score DESC
            """, (vendor_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def create_contract_renewal(self, contract_id: int, vendor_id: int, 
                              start_date: str, end_date: str, **kwargs) -> int:
        """Create contract renewal tracking record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO contract_renewals (contract_id, vendor_id, current_start_date, 
                                             current_end_date, auto_renew, renewal_notice_days,
                                             renewal_status, next_review_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contract_id, vendor_id, start_date, end_date,
                kwargs.get('auto_renew', False), kwargs.get('renewal_notice_days', 30),
                kwargs.get('renewal_status', 'pending'), kwargs.get('next_review_date'),
                kwargs.get('notes')
            ))
            
            renewal_id = cursor.lastrowid
            
            self._audit_log(conn, 'INSERT', 'contract_renewals', renewal_id, {
                'contract_id': contract_id,
                'vendor_id': vendor_id,
                'end_date': end_date
            })
            
            conn.commit()
            return renewal_id
    
    def get_upcoming_renewals(self, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Get contracts requiring renewal attention"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cr.*, v.display_name as vendor_name, v.contact_email,
                       c.extracted_json as contract_data
                FROM contract_renewals cr
                JOIN vendors v ON cr.vendor_id = v.id
                JOIN contracts c ON cr.contract_id = c.id
                WHERE cr.current_end_date <= date('now', '+{} days')
                AND cr.renewal_status IN ('pending', 'notified')
                ORDER BY cr.current_end_date ASC
            """.format(days_ahead))
            
            renewals = []
            for row in cursor.fetchall():
                contract_data = json.loads(row['contract_data'])
                renewal_dict = dict(row)
                renewal_dict['contract_data'] = contract_data
                renewals.append(renewal_dict)
            
            return renewals
    
    def update_vendor_performance(self, vendor_id: int, period_start: str, period_end: str,
                                 metrics: Dict[str, Any]) -> bool:
        """Update vendor performance metrics for a period"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO vendor_performance 
                (vendor_id, period_start, period_end, total_contracts, total_invoices,
                 total_reconciliations, successful_reconciliations, total_flags,
                 avg_processing_time, avg_confidence_score, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vendor_id, period_start, period_end,
                metrics.get('total_contracts', 0), metrics.get('total_invoices', 0),
                metrics.get('total_reconciliations', 0), metrics.get('successful_reconciliations', 0),
                metrics.get('total_flags', 0), metrics.get('avg_processing_time', 0.0),
                metrics.get('avg_confidence_score', 0.0), metrics.get('total_amount', 0.0)
            ))
            
            conn.commit()
            return True
    
    def get_vendor_performance(self, vendor_id: int, months: int = 12) -> List[Dict[str, Any]]:
        """Get vendor performance history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM vendor_performance 
                WHERE vendor_id = ? 
                AND period_start >= date('now', '-{} months')
                ORDER BY period_start DESC
            """.format(months), (vendor_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_vendor_analytics(self, vendor_id: int) -> Dict[str, Any]:
        """Get comprehensive vendor analytics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Basic vendor info
            cursor.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
            vendor = dict(cursor.fetchone() or {})
            
            # Contract count and reconciliation stats
            cursor.execute("""
                SELECT COUNT(DISTINCT c.id) as contract_count,
                       COUNT(DISTINCT i.id) as invoice_count,
                       COUNT(DISTINCT r.id) as reconciliation_count,
                       AVG(c.extraction_confidence) as avg_contract_confidence,
                       AVG(i.extraction_confidence) as avg_invoice_confidence,
                       SUM(r.flags_count) as total_flags
                FROM vendors v
                LEFT JOIN contracts c ON JSON_EXTRACT(c.extracted_json, '$.vendor.value') = v.canonical_name
                LEFT JOIN invoices i ON JSON_EXTRACT(i.extracted_json, '$.vendor.value') = v.canonical_name
                LEFT JOIN reconciliations r ON (r.contract_id = c.id OR r.invoice_id = i.id)
                WHERE v.id = ?
            """, (vendor_id,))
            
            stats = dict(cursor.fetchone() or {})
            
            # Recent performance
            performance_history = self.get_vendor_performance(vendor_id, 6)
            
            return {
                'vendor': vendor,
                'stats': stats,
                'performance_history': performance_history,
                'aliases': self.get_vendor_aliases(vendor_id)
            }
    
    def list_vendors(self, status: str = 'active', limit: int = 100) -> List[Dict[str, Any]]:
        """List all vendors with basic stats"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if status == 'all':
                where_clause = ""
                params = ()
            else:
                where_clause = "WHERE status = ?"
                params = (status,)
            
            cursor.execute(f"""
                SELECT v.*,
                       COUNT(DISTINCT va.id) as alias_count,
                       COUNT(DISTINCT cr.id) as renewal_count
                FROM vendors v
                LEFT JOIN vendor_aliases va ON v.id = va.vendor_id
                LEFT JOIN contract_renewals cr ON v.id = cr.vendor_id
                {where_clause}
                GROUP BY v.id
                ORDER BY v.display_name
                LIMIT ?
            """, params + (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Reporting and Export Methods
    
    def get_reconciliation_report_data(self, user_id: Optional[int] = None, 
                                     start_date: Optional[str] = None, 
                                     end_date: Optional[str] = None,
                                     vendor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get comprehensive reconciliation data for reporting"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build dynamic query based on filters
            where_conditions = []
            params = []
            
            if start_date:
                where_conditions.append("r.created_at >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("r.created_at <= ?")
                params.append(end_date)
            
            if vendor_id:
                where_conditions.append("v.id = ?")
                params.append(vendor_id)
            
            # Add user filter if provided (for user-specific data)
            user_join = ""
            if user_id:
                user_join = """
                    LEFT JOIN user_contracts uc ON c.id = uc.contract_id
                    LEFT JOIN user_invoices ui ON i.id = ui.invoice_id
                """
                where_conditions.append("(uc.user_id = ? OR ui.user_id = ?)")
                params.extend([user_id, user_id])
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            cursor.execute(f"""
                SELECT 
                    r.id as reconciliation_id,
                    r.created_at as reconciliation_date,
                    r.method as reconciliation_method,
                    r.flags_count,
                    r.reconciliation_json,
                    c.id as contract_id,
                    c.extracted_json as contract_data,
                    c.extraction_confidence as contract_confidence,
                    i.id as invoice_id,
                    i.extracted_json as invoice_data,
                    i.extraction_confidence as invoice_confidence,
                    v.id as vendor_id,
                    v.display_name as vendor_name,
                    v.canonical_name as vendor_canonical,
                    v.industry as vendor_industry
                FROM reconciliations r
                JOIN contracts c ON r.contract_id = c.id
                JOIN invoices i ON r.invoice_id = i.id
                LEFT JOIN vendors v ON JSON_EXTRACT(c.extracted_json, '$.vendor.value') = v.canonical_name
                    OR JSON_EXTRACT(i.extracted_json, '$.vendor.value') = v.canonical_name
                {user_join}
                WHERE {where_clause}
                ORDER BY r.created_at DESC
            """, params)
            
            results = []
            for row in cursor.fetchall():
                contract_data = json.loads(row['contract_data'])
                invoice_data = json.loads(row['invoice_data'])
                reconciliation_data = json.loads(row['reconciliation_json'])
                
                results.append({
                    'reconciliation_id': row['reconciliation_id'],
                    'reconciliation_date': row['reconciliation_date'],
                    'reconciliation_method': row['reconciliation_method'],
                    'flags_count': row['flags_count'],
                    'reconciliation_result': reconciliation_data,
                    'contract': {
                        'id': row['contract_id'],
                        'data': contract_data,
                        'confidence': row['contract_confidence']
                    },
                    'invoice': {
                        'id': row['invoice_id'],
                        'data': invoice_data,
                        'confidence': row['invoice_confidence']
                    },
                    'vendor': {
                        'id': row['vendor_id'],
                        'name': row['vendor_name'],
                        'canonical_name': row['vendor_canonical'],
                        'industry': row['vendor_industry']
                    } if row['vendor_id'] else None
                })
            
            return results
    
    def get_vendor_performance_report_data(self, vendor_id: Optional[int] = None,
                                         start_date: Optional[str] = None,
                                         end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get vendor performance data for reporting"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_conditions = ["v.status = 'active'"]
            params = []
            
            if vendor_id:
                where_conditions.append("v.id = ?")
                params.append(vendor_id)
            
            if start_date:
                where_conditions.append("vp.period_start >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("vp.period_end <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT 
                    v.id as vendor_id,
                    v.display_name,
                    v.canonical_name,
                    v.industry,
                    v.contact_email,
                    v.payment_terms,
                    vp.period_start,
                    vp.period_end,
                    vp.total_contracts,
                    vp.total_invoices,
                    vp.total_reconciliations,
                    vp.successful_reconciliations,
                    vp.total_flags,
                    vp.avg_processing_time,
                    vp.avg_confidence_score,
                    vp.total_amount,
                    COUNT(DISTINCT va.id) as total_aliases,
                    COUNT(DISTINCT cr.id) as total_renewals
                FROM vendors v
                LEFT JOIN vendor_performance vp ON v.id = vp.vendor_id
                LEFT JOIN vendor_aliases va ON v.id = va.vendor_id
                LEFT JOIN contract_renewals cr ON v.id = cr.vendor_id
                WHERE {where_clause}
                GROUP BY v.id, vp.id
                ORDER BY v.display_name, vp.period_start DESC
            """, params)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_contract_renewal_report_data(self, days_ahead: int = 365,
                                       vendor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get contract renewal data for reporting"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_conditions = [f"cr.current_end_date <= date('now', '+{days_ahead} days')"]
            params = []
            
            if vendor_id:
                where_conditions.append("cr.vendor_id = ?")
                params.append(vendor_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT 
                    cr.id as renewal_id,
                    cr.current_start_date,
                    cr.current_end_date,
                    cr.auto_renew,
                    cr.renewal_notice_days,
                    cr.renewal_status,
                    cr.notification_sent_at,
                    cr.next_review_date,
                    cr.notes as renewal_notes,
                    cr.created_at as renewal_created,
                    v.id as vendor_id,
                    v.display_name as vendor_name,
                    v.canonical_name as vendor_canonical,
                    v.industry as vendor_industry,
                    v.contact_email as vendor_contact,
                    c.id as contract_id,
                    c.extracted_json as contract_data,
                    c.extraction_confidence as contract_confidence,
                    CAST(julianday(cr.current_end_date) - julianday('now') AS INTEGER) as days_until_end
                FROM contract_renewals cr
                JOIN vendors v ON cr.vendor_id = v.id
                JOIN contracts c ON cr.contract_id = c.id
                WHERE {where_clause}
                ORDER BY cr.current_end_date ASC, v.display_name
            """, params)
            
            results = []
            for row in cursor.fetchall():
                contract_data = json.loads(row['contract_data'])
                
                results.append({
                    'renewal_id': row['renewal_id'],
                    'start_date': row['current_start_date'],
                    'end_date': row['current_end_date'],
                    'days_until_end': row['days_until_end'],
                    'auto_renew': bool(row['auto_renew']),
                    'renewal_notice_days': row['renewal_notice_days'],
                    'renewal_status': row['renewal_status'],
                    'notification_sent_at': row['notification_sent_at'],
                    'next_review_date': row['next_review_date'],
                    'renewal_notes': row['renewal_notes'],
                    'renewal_created': row['renewal_created'],
                    'vendor': {
                        'id': row['vendor_id'],
                        'name': row['vendor_name'],
                        'canonical_name': row['vendor_canonical'],
                        'industry': row['vendor_industry'],
                        'contact_email': row['vendor_contact']
                    },
                    'contract': {
                        'id': row['contract_id'],
                        'data': contract_data,
                        'confidence': row['contract_confidence']
                    }
                })
            
            return results
    
    def get_audit_trail_report_data(self, table_name: Optional[str] = None,
                                  operation: Optional[str] = None,
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None,
                                  limit: int = 1000) -> List[Dict[str, Any]]:
        """Get audit trail data for compliance reporting"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_conditions = []
            params = []
            
            if table_name:
                where_conditions.append("table_name = ?")
                params.append(table_name)
            
            if operation:
                where_conditions.append("operation = ?")
                params.append(operation)
            
            if start_date:
                where_conditions.append("timestamp >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("timestamp <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            cursor.execute(f"""
                SELECT 
                    id,
                    operation,
                    table_name,
                    record_id,
                    changes_json,
                    user_id,
                    timestamp
                FROM audit_trails
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                changes_data = json.loads(row['changes_json']) if row['changes_json'] else {}
                
                results.append({
                    'audit_id': row['id'],
                    'operation': row['operation'],
                    'table_name': row['table_name'],
                    'record_id': row['record_id'],
                    'changes': changes_data,
                    'user_id': row['user_id'],
                    'timestamp': row['timestamp']
                })
            
            return results