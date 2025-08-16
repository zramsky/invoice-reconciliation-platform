"""
Advanced Caching Manager for Unspend
Implements Redis-like functionality with multiple cache layers
"""
import json
import time
import threading
import hashlib
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import sqlite3
import pickle
import zlib
import logging

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: Optional[int] = None  # seconds
    compressed: bool = False
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl

    def touch(self):
        """Update access metadata"""
        self.last_accessed = datetime.now()
        self.access_count += 1

class CacheBackend(ABC):
    """Abstract cache backend"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        pass
    
    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        pass

class MemoryCache(CacheBackend):
    """In-memory cache with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.data: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.current_memory = 0
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str) -> Optional[CacheEntry]:
        with self.lock:
            entry = self.data.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                return entry
            elif entry:
                # Remove expired entry
                self._remove_entry(key)
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self.lock:
            # Serialize value to calculate size
            serialized = pickle.dumps(value)
            size = len(serialized)
            
            # Compress if large
            compressed = False
            if size > 1024:  # Compress if > 1KB
                compressed_data = zlib.compress(serialized)
                if len(compressed_data) < size * 0.8:  # Only if significant compression
                    serialized = compressed_data
                    compressed = True
                    size = len(compressed_data)
            
            # Check if we need to evict
            self._ensure_capacity(size)
            
            # Remove existing entry if it exists
            if key in self.data:
                self._remove_entry(key)
            
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=serialized,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                ttl=ttl,
                compressed=compressed,
                size_bytes=size
            )
            
            self.data[key] = entry
            self.current_memory += size
            return True
    
    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.data:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self) -> bool:
        with self.lock:
            self.data.clear()
            self.current_memory = 0
            return True
    
    def keys(self, pattern: str = "*") -> List[str]:
        with self.lock:
            if pattern == "*":
                return list(self.data.keys())
            # Simple pattern matching (could be enhanced)
            import fnmatch
            return [k for k in self.data.keys() if fnmatch.fnmatch(k, pattern)]
    
    def _remove_entry(self, key: str):
        """Remove entry and update memory tracking"""
        if key in self.data:
            self.current_memory -= self.data[key].size_bytes
            del self.data[key]
    
    def _ensure_capacity(self, new_size: int):
        """Ensure we have capacity for new entry"""
        # Check memory limit
        while (self.current_memory + new_size > self.max_memory_bytes and 
               len(self.data) > 0):
            self._evict_lru()
        
        # Check count limit
        while len(self.data) >= self.max_size and len(self.data) > 0:
            self._evict_lru()
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if not self.data:
            return
        
        # Find LRU entry
        lru_key = min(self.data.keys(), 
                     key=lambda k: self.data[k].last_accessed)
        self._remove_entry(lru_key)
        self.logger.debug(f"Evicted LRU cache entry: {lru_key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_accesses = sum(entry.access_count for entry in self.data.values())
            return {
                "entries": len(self.data),
                "memory_mb": round(self.current_memory / (1024 * 1024), 2),
                "total_accesses": total_accesses,
                "compressed_entries": sum(1 for e in self.data.values() if e.compressed)
            }

class PersistentCache(CacheBackend):
    """SQLite-based persistent cache"""
    
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at TIMESTAMP,
                    last_accessed TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    ttl INTEGER,
                    compressed BOOLEAN DEFAULT 0,
                    size_bytes INTEGER
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)")
            conn.commit()
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get(self, key: str) -> Optional[CacheEntry]:
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM cache_entries WHERE key = ?", (key,)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        entry = self._row_to_entry(row)
                        if entry.is_expired():
                            self.delete(key)
                            return None
                        
                        # Update access metadata
                        conn.execute(
                            "UPDATE cache_entries SET last_accessed = ?, access_count = access_count + 1 WHERE key = ?",
                            (datetime.now(), key)
                        )
                        conn.commit()
                        entry.touch()
                        return entry
            except Exception as e:
                self.logger.error(f"Cache get error: {e}")
                return None
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self.lock:
            try:
                # Serialize and optionally compress
                serialized = pickle.dumps(value)
                size = len(serialized)
                compressed = False
                
                if size > 1024:
                    compressed_data = zlib.compress(serialized)
                    if len(compressed_data) < size * 0.8:
                        serialized = compressed_data
                        compressed = True
                        size = len(compressed_data)
                
                with self._get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries 
                        (key, value, created_at, last_accessed, ttl, compressed, size_bytes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key, serialized, datetime.now(), datetime.now(),
                        ttl, compressed, size
                    ))
                    conn.commit()
                return True
            except Exception as e:
                self.logger.error(f"Cache set error: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                self.logger.error(f"Cache delete error: {e}")
                return False
    
    def clear(self) -> bool:
        with self.lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM cache_entries")
                    conn.commit()
                return True
            except Exception as e:
                self.logger.error(f"Cache clear error: {e}")
                return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        with self.lock:
            try:
                with self._get_connection() as conn:
                    if pattern == "*":
                        cursor = conn.execute("SELECT key FROM cache_entries")
                    else:
                        # SQLite GLOB pattern
                        cursor = conn.execute("SELECT key FROM cache_entries WHERE key GLOB ?", (pattern,))
                    return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                self.logger.error(f"Cache keys error: {e}")
                return []
    
    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        with self.lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        DELETE FROM cache_entries 
                        WHERE ttl IS NOT NULL 
                        AND (julianday('now') - julianday(created_at)) * 86400 > ttl
                    """)
                    conn.commit()
                    return cursor.rowcount
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}")
                return 0
    
    def _row_to_entry(self, row) -> CacheEntry:
        """Convert database row to CacheEntry"""
        # Deserialize value
        value = row['value']
        if row['compressed']:
            value = zlib.decompress(value)
        value = pickle.loads(value)
        
        return CacheEntry(
            key=row['key'],
            value=value,
            created_at=datetime.fromisoformat(row['created_at']),
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            access_count=row['access_count'],
            ttl=row['ttl'],
            compressed=bool(row['compressed']),
            size_bytes=row['size_bytes']
        )

class MultiLayerCache:
    """Multi-layer cache with L1 (memory) and L2 (persistent) layers"""
    
    def __init__(self, memory_cache: MemoryCache, persistent_cache: PersistentCache):
        self.l1_cache = memory_cache  # Fast memory cache
        self.l2_cache = persistent_cache  # Persistent cache
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.l1_hits = 0
        self.l2_hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value with L1 -> L2 fallback"""
        # Try L1 first
        entry = self.l1_cache.get(key)
        if entry:
            self.l1_hits += 1
            value = entry.value
            if entry.compressed:
                value = zlib.decompress(value)
            return pickle.loads(value)
        
        # Try L2
        entry = self.l2_cache.get(key)
        if entry:
            self.l2_hits += 1
            # Promote to L1
            self.l1_cache.set(key, entry.value, entry.ttl)
            return entry.value
        
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
            persist: bool = True) -> bool:
        """Set value in both layers"""
        # Always set in L1
        l1_success = self.l1_cache.set(key, value, ttl)
        
        # Optionally set in L2
        l2_success = True
        if persist:
            l2_success = self.l2_cache.set(key, value, ttl)
        
        return l1_success and l2_success
    
    def delete(self, key: str) -> bool:
        """Delete from both layers"""
        l1_success = self.l1_cache.delete(key)
        l2_success = self.l2_cache.delete(key)
        return l1_success or l2_success
    
    def clear(self) -> bool:
        """Clear both layers"""
        l1_success = self.l1_cache.clear()
        l2_success = self.l2_cache.clear()
        return l1_success and l2_success
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        total_requests = self.l1_hits + self.l2_hits + self.misses
        l1_stats = self.l1_cache.get_stats()
        
        return {
            "total_requests": total_requests,
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "misses": self.misses,
            "l1_hit_rate": self.l1_hits / max(1, total_requests),
            "l2_hit_rate": self.l2_hits / max(1, total_requests),
            "overall_hit_rate": (self.l1_hits + self.l2_hits) / max(1, total_requests),
            "l1_cache": l1_stats
        }
    
    def maintenance(self):
        """Perform cache maintenance"""
        # Cleanup expired entries in L2
        expired_count = self.l2_cache.cleanup_expired()
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired cache entries")

# Factory function for easy setup
def create_cache_manager(
    memory_max_size: int = 1000,
    memory_max_mb: int = 100,
    persistent_db: str = "cache.db"
) -> MultiLayerCache:
    """Create a configured multi-layer cache manager"""
    memory_cache = MemoryCache(memory_max_size, memory_max_mb)
    persistent_cache = PersistentCache(persistent_db)
    return MultiLayerCache(memory_cache, persistent_cache)