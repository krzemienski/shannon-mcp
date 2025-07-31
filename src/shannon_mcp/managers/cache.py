"""
Session cache management for Shannon MCP Server.

This module provides session caching with:
- LRU cache implementation
- Session expiration
- Persistence support
- Memory management
- Cache statistics
"""

import asyncio
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, field
import json
import pickle
import structlog
from pathlib import Path

from ..utils.logging import get_logger
from ..utils.errors import CacheError, handle_errors
from ..utils.notifications import emit, EventCategory

logger = get_logger("shannon-mcp.cache")


@dataclass
class CacheEntry:
    """Single cache entry."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: Optional[int] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds
    
    def touch(self):
        """Update last accessed time."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""
    total_entries: int = 0
    total_size_bytes: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LRUCache:
    """Least Recently Used cache implementation."""
    
    def __init__(
        self,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100MB
        default_ttl: Optional[int] = 3600,  # 1 hour
        persistence_path: Optional[Path] = None
    ):
        """
        Initialize LRU cache.
        
        Args:
            max_entries: Maximum number of entries
            max_size_bytes: Maximum cache size in bytes
            default_ttl: Default TTL in seconds
            persistence_path: Optional path for persistence
        """
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes
        self.default_ttl = default_ttl
        self.persistence_path = persistence_path
        
        # OrderedDict maintains insertion order for LRU
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._persist_task: Optional[asyncio.Task] = None
    
    async def initialize(self) -> None:
        """Initialize cache and start background tasks."""
        # Load persisted cache if available
        if self.persistence_path:
            await self._load_persisted()
        
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        if self.persistence_path:
            self._persist_task = asyncio.create_task(self._periodic_persist())
        
        logger.info(
            "cache_initialized",
            max_entries=self.max_entries,
            max_size_mb=self.max_size_bytes / 1024 / 1024,
            persistence_enabled=bool(self.persistence_path)
        )
    
    async def shutdown(self) -> None:
        """Shutdown cache and save state."""
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._persist_task:
            self._persist_task.cancel()
        
        # Final persistence
        if self.persistence_path:
            await self._save_persisted()
        
        logger.info("cache_shutdown", stats=self.get_stats())
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            # Check expiration
            if entry.is_expired:
                self._stats.expirations += 1
                del self._cache[key]
                self._stats.total_entries -= 1
                self._stats.total_size_bytes -= entry.size_bytes
                return None
            
            # Update LRU order
            self._cache.move_to_end(key)
            entry.touch()
            
            self._stats.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        # Calculate size
        try:
            size_bytes = len(pickle.dumps(value))
        except:
            # Fallback for non-pickleable objects
            size_bytes = len(str(value).encode())
        
        async with self._lock:
            # Check if key exists
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.total_size_bytes -= old_entry.size_bytes
            
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                ttl_seconds=ttl or self.default_ttl
            )
            
            # Add to cache
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Update stats
            self._stats.total_entries = len(self._cache)
            self._stats.total_size_bytes += size_bytes
            
            # Evict if necessary
            await self._evict_if_needed()
    
    async def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            del self._cache[key]
            
            self._stats.total_entries -= 1
            self._stats.total_size_bytes -= entry.size_bytes
            
            return True
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._stats.total_entries = 0
            self._stats.total_size_bytes = 0
            self._stats.evictions += len(self._cache)
    
    async def _evict_if_needed(self) -> None:
        """Evict entries if cache limits exceeded."""
        evicted = 0
        
        # Evict by entry count
        while len(self._cache) > self.max_entries:
            # Remove least recently used
            key, entry = self._cache.popitem(last=False)
            self._stats.total_size_bytes -= entry.size_bytes
            evicted += 1
        
        # Evict by size
        while self._stats.total_size_bytes > self.max_size_bytes:
            if not self._cache:
                break
            key, entry = self._cache.popitem(last=False)
            self._stats.total_size_bytes -= entry.size_bytes
            evicted += 1
        
        if evicted > 0:
            self._stats.evictions += evicted
            self._stats.total_entries = len(self._cache)
            
            logger.info(
                "cache_eviction",
                evicted_count=evicted,
                remaining_entries=self._stats.total_entries,
                size_mb=self._stats.total_size_bytes / 1024 / 1024
            )
    
    async def _cleanup_expired(self) -> None:
        """Background task to clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                async with self._lock:
                    expired_keys = []
                    
                    for key, entry in self._cache.items():
                        if entry.is_expired:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        entry = self._cache[key]
                        del self._cache[key]
                        self._stats.total_entries -= 1
                        self._stats.total_size_bytes -= entry.size_bytes
                        self._stats.expirations += 1
                    
                    if expired_keys:
                        logger.info(
                            "expired_entries_cleaned",
                            count=len(expired_keys)
                        )
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_error", error=str(e))
    
    async def _periodic_persist(self) -> None:
        """Background task to persist cache periodically."""
        while True:
            try:
                await asyncio.sleep(300)  # Save every 5 minutes
                await self._save_persisted()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("persist_error", error=str(e))
    
    async def _save_persisted(self) -> None:
        """Save cache to disk."""
        if not self.persistence_path:
            return
        
        try:
            # Create directory if needed
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data
            data = {
                "version": 1,
                "timestamp": datetime.utcnow().isoformat(),
                "stats": {
                    "hits": self._stats.hits,
                    "misses": self._stats.misses,
                    "evictions": self._stats.evictions,
                    "expirations": self._stats.expirations
                },
                "entries": {}
            }
            
            # Add non-expired entries
            async with self._lock:
                for key, entry in self._cache.items():
                    if not entry.is_expired:
                        try:
                            # Try to serialize value
                            data["entries"][key] = {
                                "value": pickle.dumps(entry.value).hex(),
                                "created_at": entry.created_at.isoformat(),
                                "last_accessed": entry.last_accessed.isoformat(),
                                "access_count": entry.access_count,
                                "size_bytes": entry.size_bytes,
                                "ttl_seconds": entry.ttl_seconds
                            }
                        except:
                            # Skip non-serializable entries
                            logger.warning(
                                "skip_non_serializable",
                                key=key
                            )
            
            # Write atomically
            temp_path = self.persistence_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f)
            temp_path.replace(self.persistence_path)
            
            logger.info(
                "cache_persisted",
                entries=len(data["entries"]),
                path=str(self.persistence_path)
            )
            
        except Exception as e:
            logger.error(
                "persist_save_error",
                error=str(e),
                path=str(self.persistence_path)
            )
    
    async def _load_persisted(self) -> None:
        """Load cache from disk."""
        if not self.persistence_path or not self.persistence_path.exists():
            return
        
        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)
            
            # Check version
            if data.get("version") != 1:
                logger.warning("unsupported_cache_version", version=data.get("version"))
                return
            
            # Restore stats
            stats = data.get("stats", {})
            self._stats.hits = stats.get("hits", 0)
            self._stats.misses = stats.get("misses", 0)
            self._stats.evictions = stats.get("evictions", 0)
            self._stats.expirations = stats.get("expirations", 0)
            
            # Restore entries
            loaded = 0
            for key, entry_data in data.get("entries", {}).items():
                try:
                    # Deserialize value
                    value = pickle.loads(bytes.fromhex(entry_data["value"]))
                    
                    # Create entry
                    entry = CacheEntry(
                        key=key,
                        value=value,
                        created_at=datetime.fromisoformat(entry_data["created_at"]),
                        last_accessed=datetime.fromisoformat(entry_data["last_accessed"]),
                        access_count=entry_data["access_count"],
                        size_bytes=entry_data["size_bytes"],
                        ttl_seconds=entry_data.get("ttl_seconds")
                    )
                    
                    # Skip if expired
                    if not entry.is_expired:
                        self._cache[key] = entry
                        self._stats.total_entries += 1
                        self._stats.total_size_bytes += entry.size_bytes
                        loaded += 1
                        
                except Exception as e:
                    logger.warning(
                        "skip_corrupted_entry",
                        key=key,
                        error=str(e)
                    )
            
            logger.info(
                "cache_loaded",
                loaded=loaded,
                path=str(self.persistence_path)
            )
            
        except Exception as e:
            logger.error(
                "persist_load_error",
                error=str(e),
                path=str(self.persistence_path)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_entries": self._stats.total_entries,
            "total_size_mb": self._stats.total_size_bytes / 1024 / 1024,
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": self._stats.hit_rate,
            "evictions": self._stats.evictions,
            "expirations": self._stats.expirations,
            "max_entries": self.max_entries,
            "max_size_mb": self.max_size_bytes / 1024 / 1024
        }
    
    def get_entry_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all entries."""
        stats = []
        
        for key, entry in self._cache.items():
            stats.append({
                "key": key,
                "size_bytes": entry.size_bytes,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
                "access_count": entry.access_count,
                "age_seconds": (datetime.utcnow() - entry.created_at).total_seconds(),
                "is_expired": entry.is_expired
            })
        
        return sorted(stats, key=lambda x: x["last_accessed"], reverse=True)


class SessionCache(LRUCache):
    """Specialized cache for sessions with additional features."""
    
    def __init__(
        self,
        max_sessions: int = 100,
        max_size_mb: int = 500,
        session_ttl: int = 3600,
        persistence_dir: Optional[Path] = None
    ):
        """
        Initialize session cache.
        
        Args:
            max_sessions: Maximum number of cached sessions
            max_size_mb: Maximum cache size in MB
            session_ttl: Session TTL in seconds
            persistence_dir: Directory for persistence
        """
        persistence_path = None
        if persistence_dir:
            persistence_path = persistence_dir / "session_cache.json"
        
        super().__init__(
            max_entries=max_sessions,
            max_size_bytes=max_size_mb * 1024 * 1024,
            default_ttl=session_ttl,
            persistence_path=persistence_path
        )
        
        self.persistence_dir = persistence_dir
    
    async def get_session(self, session_id: str):
        """Get session from cache."""
        session = await self.get(session_id)
        
        if session:
            logger.debug(
                "session_cache_hit",
                session_id=session_id
            )
            
            # Emit cache hit event
            await emit(
                "session_cache_hit",
                EventCategory.SESSION,
                {"session_id": session_id}
            )
        else:
            logger.debug(
                "session_cache_miss",
                session_id=session_id
            )
        
        return session
    
    async def cache_session(self, session, ttl: Optional[int] = None) -> None:
        """Cache a session."""
        await self.set(session.id, session, ttl)
        
        logger.info(
            "session_cached",
            session_id=session.id,
            state=session.state.value,
            ttl=ttl or self.default_ttl
        )
        
        # Emit cache event
        await emit(
            "session_cached",
            EventCategory.SESSION,
            {
                "session_id": session.id,
                "ttl": ttl or self.default_ttl
            }
        )
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Remove session from cache."""
        removed = await self.delete(session_id)
        
        if removed:
            logger.info(
                "session_invalidated",
                session_id=session_id
            )
            
            # Emit invalidation event
            await emit(
                "session_cache_invalidated",
                EventCategory.SESSION,
                {"session_id": session_id}
            )
        
        return removed
    
    async def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        active = []
        
        async with self._lock:
            for key, entry in self._cache.items():
                if not entry.is_expired:
                    session = entry.value
                    if hasattr(session, 'state') and session.state.value in ['ready', 'running']:
                        active.append(key)
        
        return active
    
    async def cleanup_stale_sessions(self) -> int:
        """Clean up stale sessions."""
        cleaned = 0
        
        async with self._lock:
            stale_keys = []
            
            for key, entry in self._cache.items():
                session = entry.value
                if hasattr(session, 'state'):
                    # Remove failed or timed out sessions
                    if session.state.value in ['failed', 'timeout']:
                        age = (datetime.utcnow() - entry.created_at).total_seconds()
                        if age > 300:  # 5 minutes
                            stale_keys.append(key)
            
            for key in stale_keys:
                del self._cache[key]
                cleaned += 1
            
            self._stats.total_entries = len(self._cache)
        
        if cleaned > 0:
            logger.info(
                "stale_sessions_cleaned",
                count=cleaned
            )
        
        return cleaned


# Export public API
__all__ = ['LRUCache', 'SessionCache', 'CacheEntry', 'CacheStats']