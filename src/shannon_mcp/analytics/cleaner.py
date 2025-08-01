"""
Data Cleaner for Analytics Engine.

Handles cleanup and lifecycle management of analytics data.
"""

import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import re

from ..utils.logging import get_logger
from ..utils.errors import ShannonError

logger = get_logger(__name__)


class RetentionPolicy(str, Enum):
    """Data retention policies."""
    KEEP_ALL = "keep_all"
    KEEP_DAYS = "keep_days"
    KEEP_SIZE = "keep_size"
    KEEP_COUNT = "keep_count"


@dataclass
class CleanupPolicy:
    """Policy for cleaning up analytics data."""
    # Retention settings
    retention_policy: RetentionPolicy = RetentionPolicy.KEEP_DAYS
    retention_days: int = 90  # For KEEP_DAYS
    retention_size_mb: int = 1000  # For KEEP_SIZE
    retention_count: int = 100  # For KEEP_COUNT
    
    # Compression settings
    compress_after_days: int = 7
    
    # Archive settings
    archive_enabled: bool = True
    archive_path: Optional[Path] = None
    archive_after_days: int = 30
    
    # Cleanup schedule
    cleanup_interval_hours: int = 24
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "retention_policy": self.retention_policy.value,
            "retention_days": self.retention_days,
            "retention_size_mb": self.retention_size_mb,
            "retention_count": self.retention_count,
            "compress_after_days": self.compress_after_days,
            "archive_enabled": self.archive_enabled,
            "archive_path": str(self.archive_path) if self.archive_path else None,
            "archive_after_days": self.archive_after_days,
            "cleanup_interval_hours": self.cleanup_interval_hours
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CleanupPolicy":
        """Create from dictionary."""
        policy = cls()
        
        if "retention_policy" in data:
            policy.retention_policy = RetentionPolicy(data["retention_policy"])
        if "retention_days" in data:
            policy.retention_days = data["retention_days"]
        if "retention_size_mb" in data:
            policy.retention_size_mb = data["retention_size_mb"]
        if "retention_count" in data:
            policy.retention_count = data["retention_count"]
        if "compress_after_days" in data:
            policy.compress_after_days = data["compress_after_days"]
        if "archive_enabled" in data:
            policy.archive_enabled = data["archive_enabled"]
        if "archive_path" in data and data["archive_path"]:
            policy.archive_path = Path(data["archive_path"])
        if "archive_after_days" in data:
            policy.archive_after_days = data["archive_after_days"]
        if "cleanup_interval_hours" in data:
            policy.cleanup_interval_hours = data["cleanup_interval_hours"]
        
        return policy


class DataCleaner:
    """Cleans up old analytics data according to retention policies."""
    
    def __init__(
        self,
        base_path: Path,
        policy: Optional[CleanupPolicy] = None
    ):
        """
        Initialize data cleaner.
        
        Args:
            base_path: Base directory for analytics
            policy: Cleanup policy to use
        """
        self.base_path = Path(base_path)
        self.metrics_dir = self.base_path / "metrics"
        self.policy = policy or CleanupPolicy()
        
        # Background task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return
            
        self._stop_event.clear()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started analytics cleanup task")
        
    async def stop(self) -> None:
        """Stop background cleanup task."""
        if not self._cleanup_task:
            return
            
        self._stop_event.set()
        
        try:
            await asyncio.wait_for(self._cleanup_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Cleanup task didn't stop gracefully, cancelling")
            self._cleanup_task.cancel()
            
        logger.info("Stopped analytics cleanup task")
        
    async def cleanup_now(self) -> Dict[str, Any]:
        """
        Perform cleanup immediately.
        
        Returns:
            Cleanup statistics
        """
        stats = {
            "files_deleted": 0,
            "files_compressed": 0,
            "files_archived": 0,
            "bytes_freed": 0,
            "errors": []
        }
        
        try:
            # Compress old files
            compress_stats = await self._compress_old_files()
            stats["files_compressed"] = compress_stats["compressed"]
            stats["bytes_freed"] += compress_stats["bytes_saved"]
            
            # Archive old files
            if self.policy.archive_enabled:
                archive_stats = await self._archive_old_files()
                stats["files_archived"] = archive_stats["archived"]
            
            # Apply retention policy
            retention_stats = await self._apply_retention_policy()
            stats["files_deleted"] = retention_stats["deleted"]
            stats["bytes_freed"] += retention_stats["bytes_freed"]
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            stats["errors"].append(str(e))
            
        logger.info(
            f"Cleanup complete: {stats['files_deleted']} deleted, "
            f"{stats['files_compressed']} compressed, "
            f"{stats['files_archived']} archived, "
            f"{stats['bytes_freed']:,} bytes freed"
        )
        
        return stats
        
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        interval = self.policy.cleanup_interval_hours * 3600
        
        while not self._stop_event.is_set():
            try:
                # Perform cleanup
                await self.cleanup_now()
                
                # Wait for next cleanup
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval
                )
            except asyncio.TimeoutError:
                # Timeout is expected - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)
                
    async def _compress_old_files(self) -> Dict[str, Any]:
        """Compress files older than threshold."""
        import gzip
        import aiofiles
        
        stats = {"compressed": 0, "bytes_saved": 0}
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policy.compress_after_days)
        
        # Find uncompressed files
        for file_path in self.metrics_dir.glob("metrics_*.jsonl"):
            try:
                # Check file age
                mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.utc
                )
                
                if mtime < cutoff:
                    # Compress file
                    original_size = file_path.stat().st_size
                    compressed_path = file_path.with_suffix('.jsonl.gz')
                    
                    async with aiofiles.open(file_path, 'rb') as f_in:
                        content = await f_in.read()
                        
                    async with aiofiles.open(compressed_path, 'wb') as f_out:
                        compressed = gzip.compress(content, compresslevel=6)
                        await f_out.write(compressed)
                    
                    # Remove original
                    file_path.unlink()
                    
                    compressed_size = compressed_path.stat().st_size
                    stats["compressed"] += 1
                    stats["bytes_saved"] += original_size - compressed_size
                    
                    logger.debug(f"Compressed {file_path.name} ({original_size} -> {compressed_size} bytes)")
                    
            except Exception as e:
                logger.error(f"Failed to compress {file_path}: {e}")
                
        return stats
        
    async def _archive_old_files(self) -> Dict[str, Any]:
        """Archive files older than threshold."""
        import shutil
        
        stats = {"archived": 0}
        
        if not self.policy.archive_path:
            # Default archive path
            self.policy.archive_path = self.base_path / "archive"
            
        # Ensure archive directory exists
        self.policy.archive_path.mkdir(parents=True, exist_ok=True)
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.policy.archive_after_days)
        
        # Find files to archive
        for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
            for file_path in self.metrics_dir.glob(pattern):
                try:
                    # Check file age
                    mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime,
                        tz=timezone.utc
                    )
                    
                    if mtime < cutoff:
                        # Move to archive
                        archive_dest = self.policy.archive_path / file_path.name
                        shutil.move(str(file_path), str(archive_dest))
                        stats["archived"] += 1
                        
                        logger.debug(f"Archived {file_path.name}")
                        
                except Exception as e:
                    logger.error(f"Failed to archive {file_path}: {e}")
                    
        return stats
        
    async def _apply_retention_policy(self) -> Dict[str, Any]:
        """Apply retention policy to delete old files."""
        stats = {"deleted": 0, "bytes_freed": 0}
        
        if self.policy.retention_policy == RetentionPolicy.KEEP_ALL:
            return stats
            
        # Get all metrics files
        files = []
        for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
            files.extend(self.metrics_dir.glob(pattern))
            if self.policy.archive_enabled and self.policy.archive_path:
                files.extend(self.policy.archive_path.glob(pattern))
        
        # Sort by modification time (newest first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        if self.policy.retention_policy == RetentionPolicy.KEEP_DAYS:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.policy.retention_days)
            
            for file_path in files:
                try:
                    mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime,
                        tz=timezone.utc
                    )
                    
                    if mtime < cutoff:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        stats["deleted"] += 1
                        stats["bytes_freed"] += size
                        logger.debug(f"Deleted {file_path.name} (age: {(datetime.now(timezone.utc) - mtime).days} days)")
                        
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")
                    
        elif self.policy.retention_policy == RetentionPolicy.KEEP_SIZE:
            total_size = 0
            size_limit = self.policy.retention_size_mb * 1024 * 1024
            
            for file_path in files:
                try:
                    size = file_path.stat().st_size
                    total_size += size
                    
                    if total_size > size_limit:
                        file_path.unlink()
                        stats["deleted"] += 1
                        stats["bytes_freed"] += size
                        logger.debug(f"Deleted {file_path.name} (total size exceeded)")
                        
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")
                    
        elif self.policy.retention_policy == RetentionPolicy.KEEP_COUNT:
            # Keep only the newest N files
            for file_path in files[self.policy.retention_count:]:
                try:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    stats["deleted"] += 1
                    stats["bytes_freed"] += size
                    logger.debug(f"Deleted {file_path.name} (count exceeded)")
                    
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")
                    
        return stats
        
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get current storage statistics."""
        stats = {
            "total_files": 0,
            "uncompressed_files": 0,
            "compressed_files": 0,
            "archived_files": 0,
            "total_size_bytes": 0,
            "uncompressed_size_bytes": 0,
            "compressed_size_bytes": 0,
            "archived_size_bytes": 0,
            "oldest_file": None,
            "newest_file": None
        }
        
        oldest_time = None
        newest_time = None
        
        # Analyze metrics directory
        for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
            for file_path in self.metrics_dir.glob(pattern):
                stats["total_files"] += 1
                size = file_path.stat().st_size
                stats["total_size_bytes"] += size
                
                if file_path.suffix == '.gz':
                    stats["compressed_files"] += 1
                    stats["compressed_size_bytes"] += size
                else:
                    stats["uncompressed_files"] += 1
                    stats["uncompressed_size_bytes"] += size
                
                # Track oldest/newest
                mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.utc
                )
                
                if oldest_time is None or mtime < oldest_time:
                    oldest_time = mtime
                    stats["oldest_file"] = file_path.name
                    
                if newest_time is None or mtime > newest_time:
                    newest_time = mtime
                    stats["newest_file"] = file_path.name
        
        # Analyze archive directory
        if self.policy.archive_enabled and self.policy.archive_path and self.policy.archive_path.exists():
            for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
                for file_path in self.policy.archive_path.glob(pattern):
                    stats["archived_files"] += 1
                    stats["archived_size_bytes"] += file_path.stat().st_size
        
        return stats