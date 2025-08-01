"""
Process Validator for Process Registry.

Validates process state and integrity.
"""

import os
import asyncio
import psutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logging import get_logger
from ..utils.errors import ShannonError
from .storage import RegistryStorage, ProcessEntry, ProcessStatus
from .tracker import ProcessTracker, ProcessInfo

logger = get_logger(__name__)


class ValidationStatus(str, Enum):
    """Process validation status."""
    VALID = "valid"
    STALE = "stale"
    ZOMBIE = "zombie"
    HIJACKED = "hijacked"  # PID reused by different process
    MISSING = "missing"
    UNHEALTHY = "unhealthy"
    RESOURCE_EXCEEDED = "resource_exceeded"


@dataclass
class ValidationResult:
    """Result of process validation."""
    pid: int
    host: str
    status: ValidationStatus
    process_status: Optional[ProcessStatus]
    reason: str
    details: Dict[str, Any]
    recommended_action: Optional[str]
    
    @property
    def is_valid(self) -> bool:
        """Check if process is valid."""
        return self.status == ValidationStatus.VALID


class ProcessValidator:
    """Validates process health and integrity."""
    
    def __init__(
        self,
        storage: RegistryStorage,
        tracker: ProcessTracker
    ):
        """
        Initialize validator.
        
        Args:
            storage: Registry storage instance
            tracker: Process tracker instance
        """
        self.storage = storage
        self.tracker = tracker
        self.hostname = os.uname().nodename
        
        # Validation thresholds
        self.stale_threshold_seconds = 300  # 5 minutes
        self.cpu_threshold_percent = 90.0
        self.memory_threshold_mb = 4096  # 4GB
        self.zombie_threshold_seconds = 600  # 10 minutes
        
    async def validate_process(
        self,
        entry: ProcessEntry
    ) -> ValidationResult:
        """
        Validate a single process.
        
        Args:
            entry: Process entry to validate
            
        Returns:
            Validation result
        """
        # Check if process exists
        if not psutil.pid_exists(entry.pid):
            return ValidationResult(
                pid=entry.pid,
                host=entry.host,
                status=ValidationStatus.MISSING,
                process_status=ProcessStatus.STOPPED,
                reason="Process no longer exists",
                details={"last_seen": entry.last_seen.isoformat()},
                recommended_action="remove_from_registry"
            )
        
        try:
            # Get current process info
            process = psutil.Process(entry.pid)
            info = ProcessInfo.from_psutil(process)
            
            # Check if it's the same process (not PID reuse)
            if not self._is_same_process(entry, info):
                return ValidationResult(
                    pid=entry.pid,
                    host=entry.host,
                    status=ValidationStatus.HIJACKED,
                    process_status=ProcessStatus.STOPPED,
                    reason="PID has been reused by a different process",
                    details={
                        "original_command": entry.command,
                        "current_command": info.name,
                        "original_start": entry.started_at.isoformat(),
                        "current_start": info.create_time.isoformat()
                    },
                    recommended_action="remove_from_registry"
                )
            
            # Check if process is zombie
            if info.status == psutil.STATUS_ZOMBIE:
                zombie_duration = (
                    datetime.now(timezone.utc) - entry.last_seen
                ).total_seconds()
                
                if zombie_duration > self.zombie_threshold_seconds:
                    return ValidationResult(
                        pid=entry.pid,
                        host=entry.host,
                        status=ValidationStatus.ZOMBIE,
                        process_status=ProcessStatus.ZOMBIE,
                        reason=f"Process has been zombie for {zombie_duration:.0f}s",
                        details={
                            "zombie_since": entry.last_seen.isoformat(),
                            "parent_pid": process.ppid()
                        },
                        recommended_action="kill_and_remove"
                    )
            
            # Check if process is stale (not updated recently)
            stale_duration = (
                datetime.now(timezone.utc) - entry.last_seen
            ).total_seconds()
            
            if stale_duration > self.stale_threshold_seconds:
                return ValidationResult(
                    pid=entry.pid,
                    host=entry.host,
                    status=ValidationStatus.STALE,
                    process_status=entry.status,
                    reason=f"Process not updated for {stale_duration:.0f}s",
                    details={
                        "last_seen": entry.last_seen.isoformat(),
                        "threshold_seconds": self.stale_threshold_seconds
                    },
                    recommended_action="refresh_tracking"
                )
            
            # Check resource usage
            resource_issues = []
            
            if info.cpu_percent > self.cpu_threshold_percent:
                resource_issues.append(
                    f"High CPU usage: {info.cpu_percent:.1f}%"
                )
            
            memory_mb = info.memory_info.get('rss', 0) / (1024 * 1024)
            if memory_mb > self.memory_threshold_mb:
                resource_issues.append(
                    f"High memory usage: {memory_mb:.0f}MB"
                )
            
            if resource_issues:
                return ValidationResult(
                    pid=entry.pid,
                    host=entry.host,
                    status=ValidationStatus.RESOURCE_EXCEEDED,
                    process_status=ProcessStatus.BUSY,
                    reason="; ".join(resource_issues),
                    details={
                        "cpu_percent": info.cpu_percent,
                        "memory_mb": memory_mb,
                        "cpu_threshold": self.cpu_threshold_percent,
                        "memory_threshold_mb": self.memory_threshold_mb
                    },
                    recommended_action="monitor_closely"
                )
            
            # Check process health indicators
            health_issues = []
            
            # Check for excessive file handles
            if len(info.open_files) > 1000:
                health_issues.append(
                    f"Excessive open files: {len(info.open_files)}"
                )
            
            # Check for excessive connections
            if len(info.connections) > 100:
                health_issues.append(
                    f"Excessive connections: {len(info.connections)}"
                )
            
            # Check for excessive threads
            if info.num_threads > 100:
                health_issues.append(
                    f"Excessive threads: {info.num_threads}"
                )
            
            if health_issues:
                return ValidationResult(
                    pid=entry.pid,
                    host=entry.host,
                    status=ValidationStatus.UNHEALTHY,
                    process_status=entry.status,
                    reason="; ".join(health_issues),
                    details={
                        "open_files": len(info.open_files),
                        "connections": len(info.connections),
                        "threads": info.num_threads
                    },
                    recommended_action="investigate_health"
                )
            
            # Process is valid
            return ValidationResult(
                pid=entry.pid,
                host=entry.host,
                status=ValidationStatus.VALID,
                process_status=self._determine_status(info),
                reason="Process is healthy and running normally",
                details={
                    "cpu_percent": info.cpu_percent,
                    "memory_mb": memory_mb,
                    "uptime_seconds": (
                        datetime.now(timezone.utc) - info.create_time
                    ).total_seconds()
                },
                recommended_action=None
            )
            
        except psutil.NoSuchProcess:
            return ValidationResult(
                pid=entry.pid,
                host=entry.host,
                status=ValidationStatus.MISSING,
                process_status=ProcessStatus.STOPPED,
                reason="Process disappeared during validation",
                details={},
                recommended_action="remove_from_registry"
            )
        except psutil.AccessDenied:
            return ValidationResult(
                pid=entry.pid,
                host=entry.host,
                status=ValidationStatus.VALID,
                process_status=entry.status,
                reason="Access denied to process (likely running)",
                details={"note": "Process exists but cannot access details"},
                recommended_action=None
            )
        except Exception as e:
            logger.error(f"Validation error for PID {entry.pid}: {e}")
            return ValidationResult(
                pid=entry.pid,
                host=entry.host,
                status=ValidationStatus.UNHEALTHY,
                process_status=entry.status,
                reason=f"Validation error: {str(e)}",
                details={"error": str(e)},
                recommended_action="manual_check"
            )
    
    async def validate_all_processes(
        self,
        fix_issues: bool = False
    ) -> Dict[str, List[ValidationResult]]:
        """
        Validate all processes in the registry.
        
        Args:
            fix_issues: Whether to automatically fix issues
            
        Returns:
            Dict categorizing validation results by status
        """
        # Get all processes for this host
        processes = await self.storage.get_all_processes(host=self.hostname)
        
        results = {
            status.value: []
            for status in ValidationStatus
        }
        
        for entry in processes:
            result = await self.validate_process(entry)
            results[result.status.value].append(result)
            
            # Apply fixes if requested
            if fix_issues:
                await self._apply_fix(result)
        
        # Log summary
        total = len(processes)
        valid = len(results[ValidationStatus.VALID.value])
        logger.info(
            f"Validated {total} processes: {valid} valid, "
            f"{total - valid} with issues"
        )
        
        return results
    
    async def validate_session(
        self,
        session_id: str
    ) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate all processes in a session.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            Tuple of (all_valid, results)
        """
        processes = await self.storage.get_session_processes(session_id)
        results = []
        
        for entry in processes:
            result = await self.validate_process(entry)
            results.append(result)
        
        all_valid = all(r.is_valid for r in results)
        return all_valid, results
    
    async def check_port_conflicts(self) -> List[Dict[str, Any]]:
        """
        Check for port conflicts between processes.
        
        Returns:
            List of conflict details
        """
        conflicts = []
        port_map: Dict[int, List[ProcessEntry]] = {}
        
        # Get all running processes
        processes = await self.storage.get_all_processes(
            status=ProcessStatus.RUNNING
        )
        
        # Build port map
        for entry in processes:
            if entry.port:
                if entry.port not in port_map:
                    port_map[entry.port] = []
                port_map[entry.port].append(entry)
        
        # Find conflicts
        for port, entries in port_map.items():
            if len(entries) > 1:
                conflicts.append({
                    'port': port,
                    'processes': [
                        {
                            'pid': e.pid,
                            'host': e.host,
                            'session_id': e.session_id,
                            'command': e.command
                        }
                        for e in entries
                    ]
                })
        
        return conflicts
    
    async def find_orphaned_processes(self) -> List[ProcessInfo]:
        """
        Find Claude processes not in the registry.
        
        Returns:
            List of orphaned process info
        """
        # Get all Claude processes
        all_claude = await self.tracker.find_claude_processes()
        
        # Get registered PIDs
        registered = await self.storage.get_all_processes(host=self.hostname)
        registered_pids = {p.pid for p in registered}
        
        # Find orphans
        orphans = [
            p for p in all_claude
            if p.pid not in registered_pids
        ]
        
        if orphans:
            logger.warning(f"Found {len(orphans)} orphaned Claude processes")
        
        return orphans
    
    def _is_same_process(
        self,
        entry: ProcessEntry,
        info: ProcessInfo
    ) -> bool:
        """Check if process info matches registry entry."""
        # Compare creation times (within 1 second tolerance)
        time_diff = abs(
            (info.create_time - entry.started_at).total_seconds()
        )
        if time_diff > 1:
            return False
        
        # Compare command names
        if entry.command.lower() not in info.name.lower():
            # Check cmdline as fallback
            if entry.command not in ' '.join(info.cmdline):
                return False
        
        return True
    
    def _determine_status(self, info: ProcessInfo) -> ProcessStatus:
        """Determine process status from info."""
        if info.status == psutil.STATUS_ZOMBIE:
            return ProcessStatus.ZOMBIE
        elif info.status in [psutil.STATUS_STOPPED, psutil.STATUS_DEAD]:
            return ProcessStatus.STOPPED
        elif info.cpu_percent > 50:
            return ProcessStatus.BUSY
        elif info.cpu_percent > 0:
            return ProcessStatus.RUNNING
        else:
            return ProcessStatus.IDLE
    
    async def _apply_fix(self, result: ValidationResult) -> None:
        """Apply recommended fix for validation result."""
        if not result.recommended_action:
            return
        
        try:
            if result.recommended_action == "remove_from_registry":
                await self.storage.remove_process(result.pid, result.host)
                logger.info(f"Removed {result.status} process {result.pid}")
                
            elif result.recommended_action == "kill_and_remove":
                try:
                    process = psutil.Process(result.pid)
                    process.kill()
                    await asyncio.sleep(1)  # Wait for termination
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
                await self.storage.remove_process(result.pid, result.host)
                logger.info(f"Killed and removed zombie process {result.pid}")
                
            elif result.recommended_action == "refresh_tracking":
                # Re-track the process
                entry = await self.storage.get_process(result.pid, result.host)
                if entry:
                    await self.tracker.track_process(
                        result.pid,
                        entry.session_id,
                        entry.project_path,
                        entry.metadata
                    )
                    logger.info(f"Refreshed tracking for stale process {result.pid}")
                    
            elif result.recommended_action == "monitor_closely":
                # Add monitoring flag to metadata
                await self.storage.update_process_status(
                    result.pid,
                    result.host,
                    result.process_status or ProcessStatus.BUSY,
                    {"monitoring": "high_resource_usage"}
                )
                
        except Exception as e:
            logger.error(f"Failed to apply fix for {result.pid}: {e}")