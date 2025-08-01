"""
Registry Cleaner for Process Registry.

Provides cleanup and maintenance routines for the process registry.
"""

import asyncio
import psutil
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum

from ..utils.logging import get_logger
from ..utils.errors import ShannonError
from .storage import RegistryStorage, ProcessEntry, ProcessStatus
from .validator import ProcessValidator, ValidationStatus

logger = get_logger(__name__)


@dataclass
class CleanupStats:
    """Statistics from cleanup operation."""
    started_at: datetime
    completed_at: datetime
    
    # Process cleanup
    processes_checked: int = 0
    processes_removed: int = 0
    zombies_killed: int = 0
    orphans_registered: int = 0
    
    # Storage cleanup
    stale_entries_removed: int = 0
    history_entries_purged: int = 0
    messages_expired: int = 0
    
    # Resource recovery
    memory_freed_mb: float = 0
    disk_space_freed_mb: float = 0
    
    # Errors encountered
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def duration_seconds(self) -> float:
        """Get cleanup duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "processes": {
                "checked": self.processes_checked,
                "removed": self.processes_removed,
                "zombies_killed": self.zombies_killed,
                "orphans_registered": self.orphans_registered
            },
            "storage": {
                "stale_entries": self.stale_entries_removed,
                "history_purged": self.history_entries_purged,
                "messages_expired": self.messages_expired
            },
            "resources": {
                "memory_freed_mb": self.memory_freed_mb,
                "disk_freed_mb": self.disk_space_freed_mb
            },
            "errors": self.errors
        }


class RegistryCleaner:
    """Cleans up stale processes and registry data."""
    
    def __init__(
        self,
        storage: RegistryStorage,
        validator: ProcessValidator
    ):
        """
        Initialize cleaner.
        
        Args:
            storage: Registry storage instance
            validator: Process validator instance
        """
        self.storage = storage
        self.validator = validator
        
        # Cleanup configuration
        self.stale_process_hours = 24
        self.history_retention_days = 30
        self.message_retention_hours = 24
        self.zombie_grace_minutes = 10
        
        # Background task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start_periodic_cleanup(
        self,
        interval_hours: int = 1
    ) -> None:
        """
        Start periodic cleanup task.
        
        Args:
            interval_hours: Cleanup interval in hours
        """
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return
        
        self._stop_event.clear()
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(interval_hours * 3600)
        )
        logger.info(f"Started periodic cleanup with {interval_hours}h interval")
    
    async def stop_periodic_cleanup(self) -> None:
        """Stop periodic cleanup task."""
        if not self._cleanup_task:
            return
        
        self._stop_event.set()
        
        try:
            await asyncio.wait_for(self._cleanup_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Cleanup task didn't stop gracefully, cancelling")
            self._cleanup_task.cancel()
        
        logger.info("Stopped periodic cleanup")
    
    async def cleanup_now(
        self,
        deep_clean: bool = False
    ) -> CleanupStats:
        """
        Perform cleanup immediately.
        
        Args:
            deep_clean: Whether to perform deep cleaning
            
        Returns:
            Cleanup statistics
        """
        stats = CleanupStats(
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)  # Will update
        )
        
        logger.info(f"Starting registry cleanup (deep_clean={deep_clean})")
        
        try:
            # Clean up processes
            await self._cleanup_processes(stats)
            
            # Clean up orphaned processes
            await self._cleanup_orphans(stats)
            
            # Clean up storage
            await self._cleanup_storage(stats, deep_clean)
            
            # Clean up system resources if deep clean
            if deep_clean:
                await self._cleanup_system_resources(stats)
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            stats.errors.append(str(e))
        
        stats.completed_at = datetime.now(timezone.utc)
        
        logger.info(
            f"Cleanup completed in {stats.duration_seconds:.1f}s: "
            f"{stats.processes_removed} processes removed, "
            f"{stats.zombies_killed} zombies killed, "
            f"{stats.stale_entries_removed} stale entries removed"
        )
        
        return stats
    
    async def _cleanup_processes(self, stats: CleanupStats) -> None:
        """Clean up invalid processes."""
        # Validate all processes
        validation_results = await self.validator.validate_all_processes(
            fix_issues=False  # We'll handle fixes ourselves
        )
        
        stats.processes_checked = sum(
            len(results) for results in validation_results.values()
        )
        
        # Handle each validation status
        for status, results in validation_results.items():
            if status == ValidationStatus.VALID:
                continue
                
            for result in results:
                try:
                    if status == ValidationStatus.MISSING:
                        # Remove missing processes
                        await self.storage.remove_process(
                            result.pid, result.host
                        )
                        stats.processes_removed += 1
                        
                    elif status == ValidationStatus.HIJACKED:
                        # Remove hijacked PIDs
                        await self.storage.remove_process(
                            result.pid, result.host
                        )
                        stats.processes_removed += 1
                        
                    elif status == ValidationStatus.ZOMBIE:
                        # Try to kill zombies
                        if await self._kill_zombie(result.pid):
                            stats.zombies_killed += 1
                        await self.storage.remove_process(
                            result.pid, result.host
                        )
                        stats.processes_removed += 1
                        
                    elif status == ValidationStatus.STALE:
                        # Check if truly stale
                        if await self._is_truly_stale(result):
                            await self.storage.remove_process(
                                result.pid, result.host
                            )
                            stats.processes_removed += 1
                            
                except Exception as e:
                    logger.error(
                        f"Failed to clean up {status} process {result.pid}: {e}"
                    )
                    stats.errors.append(f"Process {result.pid}: {e}")
    
    async def _cleanup_orphans(self, stats: CleanupStats) -> None:
        """Register orphaned Claude processes."""
        try:
            orphans = await self.validator.find_orphaned_processes()
            
            for orphan in orphans:
                try:
                    # Try to determine session from command line
                    session_id = self._extract_session_id(orphan.cmdline)
                    if not session_id:
                        session_id = f"orphan_{orphan.pid}"
                    
                    # Register the orphan
                    entry = ProcessEntry(
                        pid=orphan.pid,
                        session_id=session_id,
                        project_path=orphan.cwd,
                        command=orphan.name,
                        args=orphan.cmdline[1:] if len(orphan.cmdline) > 1 else [],
                        env=orphan.environ,
                        status=ProcessStatus.RUNNING,
                        started_at=orphan.create_time,
                        last_seen=datetime.now(timezone.utc),
                        host=self.validator.hostname,
                        port=None,
                        user=orphan.username,
                        metadata={"orphan": True},
                        cpu_percent=orphan.cpu_percent,
                        memory_mb=orphan.memory_info.get('rss', 0) / (1024 * 1024)
                    )
                    
                    await self.storage.register_process(entry)
                    stats.orphans_registered += 1
                    
                    logger.info(f"Registered orphan process {orphan.pid}")
                    
                except Exception as e:
                    logger.error(f"Failed to register orphan {orphan.pid}: {e}")
                    stats.errors.append(f"Orphan {orphan.pid}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to find orphans: {e}")
            stats.errors.append(f"Orphan search: {e}")
    
    async def _cleanup_storage(
        self,
        stats: CleanupStats,
        deep_clean: bool
    ) -> None:
        """Clean up storage data."""
        try:
            # Clean up stale processes
            threshold_seconds = self.stale_process_hours * 3600
            removed = await self.storage.cleanup_stale_processes(threshold_seconds)
            stats.stale_entries_removed += removed
            
            # Clean up expired messages
            expired = await self.storage.cleanup_expired_messages()
            stats.messages_expired += expired
            
            # Clean up old history if deep clean
            if deep_clean:
                purged = await self._purge_old_history()
                stats.history_entries_purged += purged
                
        except Exception as e:
            logger.error(f"Storage cleanup error: {e}")
            stats.errors.append(f"Storage: {e}")
    
    async def _cleanup_system_resources(self, stats: CleanupStats) -> None:
        """Clean up system resources."""
        try:
            # Get initial memory usage
            initial_memory = psutil.virtual_memory()
            
            # Force garbage collection in Python
            import gc
            gc.collect()
            
            # Clear system caches if possible (Linux only)
            if hasattr(os, 'sync'):
                os.sync()
            
            # Calculate freed memory
            final_memory = psutil.virtual_memory()
            memory_freed = (initial_memory.used - final_memory.used) / (1024 * 1024)
            if memory_freed > 0:
                stats.memory_freed_mb = memory_freed
                
        except Exception as e:
            logger.error(f"System resource cleanup error: {e}")
            stats.errors.append(f"System resources: {e}")
    
    async def _kill_zombie(self, pid: int) -> bool:
        """Try to kill a zombie process."""
        try:
            process = psutil.Process(pid)
            
            # Try to get parent
            ppid = process.ppid()
            if ppid > 0:
                # Signal parent to reap child
                parent = psutil.Process(ppid)
                parent.send_signal(psutil.signal.SIGCHLD)
                await asyncio.sleep(0.1)
                
                # Check if still zombie
                if process.is_running() and process.status() == psutil.STATUS_ZOMBIE:
                    # Try harder - kill parent
                    logger.warning(f"Killing parent {ppid} to clean zombie {pid}")
                    parent.kill()
                    return True
            
            # Try to kill zombie directly
            process.kill()
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            logger.error(f"Failed to kill zombie {pid}: {e}")
            return False
    
    async def _is_truly_stale(self, result) -> bool:
        """Check if a stale process is truly dead."""
        try:
            # Try to communicate with the process
            process = psutil.Process(result.pid)
            
            # Check if it responds to signals
            process.send_signal(0)  # Null signal
            
            # If we get here, process exists but isn't updating
            # Check CPU usage
            cpu = process.cpu_percent(interval=1.0)
            if cpu > 0:
                # Process is active, just not updating registry
                return False
            
            # Process exists but is idle and not updating
            return True
            
        except psutil.NoSuchProcess:
            return True
        except Exception:
            # Can't determine, assume stale
            return True
    
    def _extract_session_id(self, cmdline: List[str]) -> Optional[str]:
        """Try to extract session ID from command line."""
        # Look for session ID patterns in command line
        for i, arg in enumerate(cmdline):
            if arg in ['--session', '--session-id', '-s']:
                if i + 1 < len(cmdline):
                    return cmdline[i + 1]
            elif arg.startswith('--session='):
                return arg.split('=', 1)[1]
            elif arg.startswith('--session-id='):
                return arg.split('=', 1)[1]
        
        # Look for session ID in arguments
        cmd_str = ' '.join(cmdline)
        if 'session_' in cmd_str:
            # Extract session ID pattern
            import re
            match = re.search(r'session_[a-f0-9-]+', cmd_str)
            if match:
                return match.group(0)
        
        return None
    
    async def _purge_old_history(self) -> int:
        """Purge old history entries."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.history_retention_days
        )
        
        # This would need to be implemented in storage
        # For now, return 0
        return 0
    
    async def _cleanup_loop(self, interval: float) -> None:
        """Background cleanup loop."""
        while not self._stop_event.is_set():
            try:
                # Perform cleanup
                stats = await self.cleanup_now(deep_clean=False)
                
                # Log if there were significant cleanups
                if stats.processes_removed > 0 or stats.errors:
                    logger.info(f"Periodic cleanup: {stats.to_dict()}")
                
                # Wait for next iteration
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval
                )
                
            except asyncio.TimeoutError:
                # Expected timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)