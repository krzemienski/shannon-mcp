"""
Session caching system for Shannon MCP Server.

This module provides advanced caching with:
- LRU eviction policy
- TTL support
- Persistence to disk
- Memory management
- Cache statistics
- Async operations
"""

import asyncio
from typing import Optional, Dict, Any, List, TypeVar, Generic, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import json
import pickle
import aiofiles
from pathlib import Path
import structlog
import weakref

from ..utils.logging import get_logger
from ..utils.errors import CacheError, ValidationError

logger = get_logger("shannon-mcp.cache")

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Single cache entry with metadata."""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def touch(self) -> None:
        """Update access time and count."""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LRUCache(Generic[T]):
    """LRU cache with TTL support."""
    
    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        default_ttl: Optional[timedelta] = None,
        eviction_callback: Optional[Callable[[str, T], None]] = None
    ):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            max_memory_mb: Maximum memory usage in MB
            default_ttl: Default time-to-live for entries
            eviction_callback: Callback when entry is evicted
        """
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.eviction_callback = eviction_callback
        
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def get(self, key: str) -> Optional[T]:
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
            if entry.is_expired():
                await self._remove_entry(key, expired=True)
                self._stats.misses += 1
                return None
            
            # Update LRU order
            self._cache.move_to_end(key)
            entry.touch()
            
            self._stats.hits += 1
            return entry.value
    
    async def put(
        self,
        key: str,
        value: T,
        ttl: Optional[timedelta] = None,
        size_bytes: Optional[int] = None
    ) -> None:
        """
        Put value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live (overrides default)
            size_bytes: Size of value in bytes
        """
        async with self._lock:
            # Calculate size if not provided
            if size_bytes is None:
                size_bytes = self._estimate_size(value)
            
            # Check if we need to evict
            await self._ensure_space(size_bytes)
            
            # Create entry
            ttl = ttl or self.default_ttl
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + ttl
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size_bytes=size_bytes
            )
            
            # Update cache
            if key in self._cache:
                # Remove old entry size
                old_entry = self._cache[key]
                self._stats.total_size_bytes -= old_entry.size_bytes
            else:
                self._stats.entry_count += 1
            
            self._cache[key] = entry
            self._stats.total_size_bytes += size_bytes
            
            # Move to end (most recent)
            self._cache.move_to_end(key)
    
    async def remove(self, key: str) -> bool:
        """
        Remove entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            return await self._remove_entry(key)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            # Call eviction callbacks
            if self.eviction_callback:
                for key, entry in self._cache.items():
                    try:
                        self.eviction_callback(key, entry.value)
                    except Exception as e:
                        logger.error(
                            "eviction_callback_error",
                            key=key,
                            error=str(e)
                        )
            
            self._cache.clear()
            self._stats = CacheStats()
    
    async def _remove_entry(
        self,
        key: str,
        expired: bool = False,
        evicted: bool = False
    ) -> bool:
        """Remove single entry."""
        if key not in self._cache:
            return False
        
        entry = self._cache.pop(key)
        self._stats.total_size_bytes -= entry.size_bytes
        self._stats.entry_count -= 1
        
        if expired:
            self._stats.expirations += 1
        elif evicted:
            self._stats.evictions += 1
        
        # Call eviction callback
        if self.eviction_callback:
            try:
                self.eviction_callback(key, entry.value)
            except Exception as e:
                logger.error(
                    "eviction_callback_error",
                    key=key,
                    error=str(e)
                )
        
        return True
    
    async def _ensure_space(self, needed_bytes: int) -> None:
        """Ensure space for new entry by evicting if needed."""
        # Check entry count
        while len(self._cache) >= self.max_size:
            # Evict least recently used
            key = next(iter(self._cache))
            await self._remove_entry(key, evicted=True)
        
        # Check memory usage
        while self._stats.total_size_bytes + needed_bytes > self.max_memory_bytes:
            if not self._cache:
                raise CacheError(
                    f"Cannot fit entry of {needed_bytes} bytes in cache"
                )
            
            # Evict least recently used
            key = next(iter(self._cache))
            await self._remove_entry(key, evicted=True)
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate size of value in bytes."""
        try:
            # Try pickle for size estimation
            return len(pickle.dumps(value))
        except:
            # Fallback to rough estimation
            return len(str(value))
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                await self._remove_entry(key, expired=True)
            
            return len(expired_keys)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def start_cleanup_task(self, interval: float = 60.0) -> None:
        """Start periodic cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    count = await self.cleanup_expired()
                    if count > 0:
                        logger.debug(
                            "cleaned_expired_entries",
                            count=count
                        )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(
                        "cleanup_task_error",
                        error=str(e)
                    )
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self) -> None:
        """Stop cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


class SessionCache:
    """Specialized cache for sessions with persistence."""
    
    def __init__(
        self,
        max_sessions: int = 100,
        max_size_mb: int = 500,
        session_ttl: int = 3600,
        persistence_dir: Path = None
    ):
        """
        Initialize session cache.
        
        Args:
            max_sessions: Maximum cached sessions
            max_size_mb: Maximum cache size in MB
            session_ttl: Session time-to-live in seconds
            persistence_dir: Directory for cache persistence
        """
        self.persistence_dir = persistence_dir or (Path.home() / ".shannon-mcp" / "session_cache")
        self.persist_on_eviction = True
        
        # Create cache with eviction callback
        self._cache = LRUCache[Dict[str, Any]](
            max_size=max_sessions,
            max_memory_mb=max_size_mb,
            default_ttl=timedelta(seconds=session_ttl),
            eviction_callback=self._on_eviction if self.persist_on_eviction else None
        )
        
        # Ensure cache directory exists
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize cache and start cleanup task."""
        await self._cache.start_cleanup_task(interval=300.0)  # Every 5 minutes
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session from cache or disk.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data or None
        """
        # Try memory cache first
        session_data = await self._cache.get(session_id)
        if session_data is not None:
            return session_data
        
        # Try loading from disk
        session_file = self.persistence_dir / f"{session_id}.json"
        if session_file.exists():
            try:
                async with aiofiles.open(session_file, 'r') as f:
                    content = await f.read()
                    session_data = json.loads(content)
                
                # Put back in memory cache
                await self._cache.put(session_id, session_data)
                
                logger.debug(
                    "session_loaded_from_disk",
                    session_id=session_id
                )
                
                return session_data
                
            except Exception as e:
                logger.error(
                    "session_load_error",
                    session_id=session_id,
                    error=str(e)
                )
        
        return None
    
    async def put_session(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        persist: bool = False
    ) -> None:
        """
        Put session in cache.
        
        Args:
            session_id: Session ID
            session_data: Session data
            persist: Persist to disk immediately
        """
        await self._cache.put(session_id, session_data)
        
        if persist:
            await self._persist_session(session_id, session_data)
    
    async def cache_session(
        self,
        session: Any,  # Would be Session type but avoiding circular import
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache a session object.
        
        Args:
            session: Session object
            ttl: Time-to-live in seconds
        """
        session_data = session.to_dict()
        if hasattr(session, 'binary') and session.binary:
            session_data["binary"] = session.binary.to_dict()
        
        ttl_delta = timedelta(seconds=ttl) if ttl else None
        await self._cache.put(session.id, session_data, ttl=ttl_delta)
    
    async def remove_session(self, session_id: str) -> bool:
        """
        Remove session from cache and disk.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if removed
        """
        # Remove from memory
        removed = await self._cache.remove(session_id)
        
        # Remove from disk
        session_file = self.persistence_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            removed = True
        
        return removed
    
    async def list_sessions(
        self,
        include_disk: bool = True
    ) -> List[str]:
        """
        List all session IDs.
        
        Args:
            include_disk: Include sessions on disk
            
        Returns:
            List of session IDs
        """
        # Get memory cache sessions
        session_ids = set()
        async with self._cache._lock:
            session_ids.update(self._cache._cache.keys())
        
        # Add disk sessions
        if include_disk:
            for session_file in self.persistence_dir.glob("*.json"):
                session_id = session_file.stem
                session_ids.add(session_id)
        
        return sorted(session_ids)
    
    async def _persist_session(
        self,
        session_id: str,
        session_data: Dict[str, Any]
    ) -> None:
        """Persist session to disk."""
        session_file = self.persistence_dir / f"{session_id}.json"
        
        try:
            # Write to temporary file first
            temp_file = session_file.with_suffix('.tmp')
            
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(session_data, indent=2))
            
            # Atomic rename
            temp_file.rename(session_file)
            
            logger.debug(
                "session_persisted",
                session_id=session_id,
                file=str(session_file)
            )
            
        except Exception as e:
            logger.error(
                "session_persist_error",
                session_id=session_id,
                error=str(e)
            )
            raise CacheError(f"Failed to persist session: {e}")
    
    def _on_eviction(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Handle session eviction."""
        # Persist to disk synchronously (called from async context)
        asyncio.create_task(self._persist_session(session_id, session_data))
        
        logger.debug(
            "session_evicted",
            session_id=session_id,
            persist=self.persist_on_eviction
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self._cache.get_stats()
        return {
            "entries": stats.entry_count,
            "hit_rate": stats.hit_rate,
            "size_mb": stats.total_size_bytes / (1024 * 1024),
            "hits": stats.hits,
            "misses": stats.misses,
            "evictions": stats.evictions,
            "expirations": stats.expirations
        }
    
    async def shutdown(self) -> None:
        """Shutdown cache and cleanup."""
        await self._cache.stop_cleanup_task()
        await self._cache.clear()
    
    async def cleanup(self) -> None:
        """Clean up old sessions from disk."""
        now = datetime.utcnow()
        cleaned_count = 0
        
        for session_file in self.persistence_dir.glob("*.json"):
            try:
                # Check file age
                mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                age = now - mtime
                
                # Remove if older than 7 days
                if age > timedelta(days=7):
                    session_file.unlink()
                    cleaned_count += 1
                    
            except Exception as e:
                logger.error(
                    "cleanup_error",
                    file=str(session_file),
                    error=str(e)
                )
        
        if cleaned_count > 0:
            logger.info(
                "disk_cleanup_complete",
                cleaned_count=cleaned_count
            )
        
        return cleaned_count


# Export public API
__all__ = [
    'LRUCache',
    'SessionCache',
    'CacheEntry',
    'CacheStats',
    'CacheError'
]