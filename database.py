#!/usr/bin/env python3
"""
Database models and connection management for Invoice Reconciliation Platform
Supports both SQLite (development) and PostgreSQL (production)
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# Try to import PostgreSQL support, fallback to SQLite
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

import sqlite3
from sqlite3 import Row

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Unified database manager supporting both PostgreSQL and SQLite"""
    
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        self.use_postgres = POSTGRES_AVAILABLE and self.db_url and self.db_url.startswith('postgresql')
        
        if self.use_postgres:
            logger.info("Using PostgreSQL database")
            self.connection = None
            self._connect_postgres()
        else:
            logger.info("Using SQLite database (development mode)")
            self.db_path = os.environ.get('SQLITE_DB', 'invoices.db')
            self.connection = None
            self._connect_sqlite()
        
        self._create_tables()
    
    def _connect_postgres(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                self.db_url,
                cursor_factory=RealDictCursor
            )
            self.connection.autocommit = True
            logger.info("Connected to PostgreSQL successfully")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def _connect_sqlite(self):
        """Connect to SQLite database"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = Row  # Enable dict-like access
            logger.info(f"Connected to SQLite database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        vendors_table_sql = """
        CREATE TABLE IF NOT EXISTS vendors (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            business_description TEXT,
            effective_date DATE,
            renewal_date DATE,
            reconciliation_summary TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(50) DEFAULT 'active',
            contract_filename VARCHAR(500),
            contract_content TEXT,
            contract_file_path VARCHAR(500),
            metadata JSON
        );
        """
        
        # Create indexes for better performance
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_vendors_status ON vendors(status);",
            "CREATE INDEX IF NOT EXISTS idx_vendors_created_at ON vendors(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_vendors_name ON vendors(name);"
        ]
        
        try:
            cursor = self.connection.cursor()
            
            # Create main table
            if self.use_postgres:
                # PostgreSQL-specific adjustments
                vendors_table_sql = vendors_table_sql.replace('JSON', 'JSONB')
            
            cursor.execute(vendors_table_sql)
            
            # Create indexes
            for index_sql in indexes_sql:
                cursor.execute(index_sql)
            
            if not self.use_postgres:
                self.connection.commit()
            
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
        finally:
            cursor.close()
    
    def create_vendor(self, vendor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new vendor in the database"""
        try:
            cursor = self.connection.cursor()
            
            # Prepare the data
            vendor_id = vendor_data.get('id')
            now = datetime.now().isoformat()
            
            insert_sql = """
            INSERT INTO vendors (
                id, name, business_description, effective_date, renewal_date,
                reconciliation_summary, upload_date, created_at, updated_at,
                status, contract_filename, contract_content, contract_file_path, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING *;
            """ if self.use_postgres else """
            INSERT INTO vendors (
                id, name, business_description, effective_date, renewal_date,
                reconciliation_summary, upload_date, created_at, updated_at,
                status, contract_filename, contract_content, contract_file_path, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );
            """
            
            values = (
                vendor_id,
                vendor_data.get('name'),
                vendor_data.get('business_description'),
                vendor_data.get('effective_date'),
                vendor_data.get('renewal_date'),
                vendor_data.get('reconciliation_summary'),
                vendor_data.get('upload_date', now),
                vendor_data.get('created_at', now),
                now,  # updated_at
                vendor_data.get('status', 'active'),
                vendor_data.get('contract_filename'),
                vendor_data.get('contract_content'),
                vendor_data.get('contract_file_path'),
                json.dumps(vendor_data.get('metadata', {}))
            )
            
            cursor.execute(insert_sql, values)
            
            if self.use_postgres:
                result = cursor.fetchone()
                vendor = dict(result) if result else vendor_data
            else:
                self.connection.commit()
                vendor = self.get_vendor(vendor_id)
            
            logger.info(f"Created vendor: {vendor_id}")
            return vendor
            
        except Exception as e:
            logger.error(f"Failed to create vendor: {e}")
            raise
        finally:
            cursor.close()
    
    def get_vendor(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        """Get a vendor by ID"""
        try:
            cursor = self.connection.cursor()
            
            select_sql = "SELECT * FROM vendors WHERE id = %s;" if self.use_postgres else "SELECT * FROM vendors WHERE id = ?;"
            cursor.execute(select_sql, (vendor_id,))
            
            result = cursor.fetchone()
            if result:
                vendor = dict(result)
                # Parse JSON metadata
                if vendor.get('metadata'):
                    try:
                        vendor['metadata'] = json.loads(vendor['metadata'])
                    except:
                        vendor['metadata'] = {}
                return vendor
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get vendor {vendor_id}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_all_vendors(self) -> List[Dict[str, Any]]:
        """Get all vendors"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("SELECT * FROM vendors ORDER BY created_at DESC;")
            
            results = cursor.fetchall()
            vendors = []
            
            for result in results:
                vendor = dict(result)
                # Parse JSON metadata
                if vendor.get('metadata'):
                    try:
                        vendor['metadata'] = json.loads(vendor['metadata'])
                    except:
                        vendor['metadata'] = {}
                vendors.append(vendor)
            
            return vendors
            
        except Exception as e:
            logger.error(f"Failed to get vendors: {e}")
            raise
        finally:
            cursor.close()
    
    def update_vendor(self, vendor_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a vendor"""
        try:
            cursor = self.connection.cursor()
            
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key == 'metadata':
                    value = json.dumps(value)
                set_clauses.append(f"{key} = %s" if self.use_postgres else f"{key} = ?")
                values.append(value)
            
            # Add updated_at
            set_clauses.append("updated_at = %s" if self.use_postgres else "updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(vendor_id)
            
            update_sql = f"""
            UPDATE vendors 
            SET {', '.join(set_clauses)}
            WHERE id = %s
            """ if self.use_postgres else f"""
            UPDATE vendors 
            SET {', '.join(set_clauses)}
            WHERE id = ?
            """
            
            cursor.execute(update_sql, values)
            
            if not self.use_postgres:
                self.connection.commit()
            
            return self.get_vendor(vendor_id)
            
        except Exception as e:
            logger.error(f"Failed to update vendor {vendor_id}: {e}")
            raise
        finally:
            cursor.close()
    
    def delete_vendor(self, vendor_id: str) -> bool:
        """Delete a vendor"""
        try:
            cursor = self.connection.cursor()
            
            delete_sql = "DELETE FROM vendors WHERE id = %s;" if self.use_postgres else "DELETE FROM vendors WHERE id = ?;"
            cursor.execute(delete_sql, (vendor_id,))
            
            if not self.use_postgres:
                self.connection.commit()
            
            logger.info(f"Deleted vendor: {vendor_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vendor {vendor_id}: {e}")
            return False
        finally:
            cursor.close()
    
    def get_health_stats(self) -> Dict[str, Any]:
        """Get database health and statistics"""
        try:
            cursor = self.connection.cursor()
            
            # Get basic stats
            cursor.execute("SELECT COUNT(*) as total_vendors FROM vendors;")
            total_vendors = cursor.fetchone()[0] if not self.use_postgres else cursor.fetchone()['total_vendors']
            
            cursor.execute("SELECT COUNT(*) as active_vendors FROM vendors WHERE status = 'active';")
            active_vendors = cursor.fetchone()[0] if not self.use_postgres else cursor.fetchone()['active_vendors']
            
            return {
                "database_type": "PostgreSQL" if self.use_postgres else "SQLite",
                "connected": True,
                "total_vendors": total_vendors,
                "active_vendors": active_vendors,
                "last_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get health stats: {e}")
            return {
                "database_type": "PostgreSQL" if self.use_postgres else "SQLite",
                "connected": False,
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }
        finally:
            cursor.close()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

# Global database instance
db = None

def get_db() -> DatabaseManager:
    """Get database instance (singleton pattern)"""
    global db
    if db is None:
        db = DatabaseManager()
    return db

def init_db():
    """Initialize database with demo data"""
    database = get_db()
    
    # Check if we already have data
    vendors = database.get_all_vendors()
    if len(vendors) > 0:
        logger.info(f"Database already has {len(vendors)} vendors")
        return
    
    # Create demo vendors
    demo_vendors = [
        {
            "id": "demo-vendor-1",
            "name": "Demo Vendor Company",
            "business_description": "Sample vendor for testing platform functionality",
            "effective_date": "2025-08-18",
            "renewal_date": "2026-08-18",
            "reconciliation_summary": "Standard contract terms with monthly reconciliation",
            "status": "active"
        },
        {
            "id": "demo-vendor-2",
            "name": "Test Services Inc",
            "business_description": "Another sample vendor with contract file",
            "effective_date": "2025-08-17",
            "renewal_date": "2026-08-17",
            "reconciliation_summary": "Premium service contract with weekly reconciliation",
            "status": "active",
            "contract_filename": "demo-contract.txt",
            "contract_content": "DEMO CONTRACT\\n\\nContract Date: August 17, 2025\\nVendor: Test Services Inc\\nService: Premium Testing Services\\n\\nThis is a demo contract file to test the platform functionality.\\n\\nTERMS:\\n1. Service delivery weekly\\n2. Monthly reconciliation process\\n3. Standard payment terms\\n\\nSigned: Test Services Inc"
        }
    ]
    
    for vendor_data in demo_vendors:
        try:
            database.create_vendor(vendor_data)
        except Exception as e:
            logger.error(f"Failed to create demo vendor {vendor_data['id']}: {e}")
    
    logger.info("Demo data initialized successfully")

if __name__ == "__main__":
    # Initialize database and create demo data
    init_db()
    print("Database initialized successfully!")