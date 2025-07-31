"""
Process Registry Manager for Shannon MCP Server.

This module provides system-wide process tracking and management with:
- Process lifecycle tracking
- PID management and validation
- Resource monitoring
- Cleanup routines
- Cross-platform process management
"""

import asyncio
import os
import signal
import psutil
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import structlog

from .base import BaseManager, ManagerConfig, HealthStatus
from ..utils.config import get_config
from ..utils.errors import (
    SystemError, ValidationError, ConfigurationError,
    handle_errors, error_context, ErrorRecovery
)
from ..utils.notifications import emit, EventCategory, EventPriority, event_handler
from ..utils.shutdown import track_request_lifetime, register_shutdown_handler, ShutdownPhase
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.process")


class ProcessStatus(Enum):
    """Process lifecycle status."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping" 
    STOPPED = "stopped"
    ORPHANED = "orphaned"
    FAILED = "failed"


class ProcessType(Enum):
    """Type of process being tracked."""
    SESSION = "session"        # Claude Code session process
    SERVER = "server"          # MCP server process
    WORKER = "worker"          # Background worker process
    AGENT = "agent"            # AI agent process
    HOOK = "hook"              # Hook execution process
    UTILITY = "utility"        # Utility/maintenance process


@dataclass
class ProcessPIDInfo:
    """Detailed PID information for tracking and validation."""
    pid: int
    ppid: Optional[int] = None  # Parent PID
    creation_time: Optional[datetime] = None
    command_line: str = ""
    executable_path: str = ""
    platform_info: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_psutil(cls, proc: psutil.Process) -> 'ProcessPIDInfo':
        """Create PID info from psutil process."""
        try:
            pid_info = cls(pid=proc.pid)
            
            # Get process info safely
            try:
                pid_info.ppid = proc.ppid()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            try:
                pid_info.creation_time = datetime.fromtimestamp(proc.create_time())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            try:
                pid_info.command_line = ' '.join(proc.cmdline())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            try:
                pid_info.executable_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            # Platform-specific info
            try:
                pid_info.platform_info = {
                    "username": proc.username(),
                    "status": proc.status(),
                    "nice": proc.nice(),
                    "num_threads": proc.num_threads()
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
            return pid_info
            
        except Exception:
            # Return minimal info if everything fails
            return cls(pid=proc.pid)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "creation_time": self.creation_time.isoformat() if self.creation_time else None,
            "command_line": self.command_line,
            "executable_path": self.executable_path,
            "platform_info": self.platform_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessPIDInfo':
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            ppid=data.get("ppid"),
            creation_time=datetime.fromisoformat(data["creation_time"]) if data.get("creation_time") else None,
            command_line=data.get("command_line", ""),
            executable_path=data.get("executable_path", ""),
            platform_info=data.get("platform_info", {})
        )


@dataclass
class PIDEvent:
    """PID lifecycle event for audit trail."""
    id: str
    pid: int
    event_type: str  # "created", "terminated", "orphaned", "reused", "collision", "validated"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    process_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Generate event ID if not provided."""
        if not self.id:
            self.id = f"pid_event_{uuid.uuid4().hex[:12]}"


@dataclass
class ProcessConstraints:
    """Resource and security constraints for process validation."""
    max_memory_mb: Optional[int] = None
    max_cpu_percent: Optional[float] = None
    max_file_descriptors: Optional[int] = None
    max_connections: Optional[int] = None
    allowed_users: Optional[List[str]] = None
    allowed_groups: Optional[List[str]] = None
    allowed_working_dirs: Optional[List[str]] = None
    blocked_executables: Optional[List[str]] = None
    required_capabilities: Optional[List[str]] = None
    max_child_processes: Optional[int] = None
    max_uptime_hours: Optional[float] = None


@dataclass
class ProcessValidationResult:
    """Result of process validation."""
    process_id: str
    pid: int
    is_valid: bool
    validation_time: datetime = field(default_factory=datetime.utcnow)
    
    # Validation category results
    integrity_valid: bool = True
    resource_valid: bool = True
    security_valid: bool = True
    lifecycle_valid: bool = True
    
    # Detailed findings
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, category: str, message: str):
        """Add validation error."""
        self.errors.append(f"[{category}] {message}")
        self.is_valid = False
        
        # Update category validity
        if category.lower() in ["integrity", "process"]:
            self.integrity_valid = False
        elif category.lower() in ["resource", "memory", "cpu"]:
            self.resource_valid = False
        elif category.lower() in ["security", "permission", "user"]:
            self.security_valid = False
        elif category.lower() in ["lifecycle", "state", "parent"]:
            self.lifecycle_valid = False
    
    def add_warning(self, category: str, message: str):
        """Add validation warning."""
        self.warnings.append(f"[{category}] {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "process_id": self.process_id,
            "pid": self.pid,
            "is_valid": self.is_valid,
            "validation_time": self.validation_time.isoformat(),
            "integrity_valid": self.integrity_valid,
            "resource_valid": self.resource_valid,
            "security_valid": self.security_valid,
            "lifecycle_valid": self.lifecycle_valid,
            "warnings": self.warnings,
            "errors": self.errors,
            "metrics": self.metrics
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "pid": self.pid,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "process_id": self.process_id,
            "details": self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PIDEvent':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            pid=data["pid"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            process_id=data.get("process_id"),
            details=data.get("details", {})
        )


@dataclass
class ResourceLimits:
    """Resource usage limits and thresholds."""
    max_cpu_percent: float = 90.0
    max_memory_mb: float = 1024.0  # 1GB default
    max_file_descriptors: int = 1024
    max_threads: int = 100
    max_connections: int = 100
    max_disk_io_mb_per_sec: float = 100.0
    
    # Alert thresholds (percentage of max)
    cpu_alert_threshold: float = 0.8  # 80% of max
    memory_alert_threshold: float = 0.8  # 80% of max
    fd_alert_threshold: float = 0.8  # 80% of max
    
    def is_cpu_exceeded(self, cpu_percent: float) -> bool:
        """Check if CPU usage exceeds limit."""
        return cpu_percent > self.max_cpu_percent
    
    def is_memory_exceeded(self, memory_mb: float) -> bool:
        """Check if memory usage exceeds limit."""
        return memory_mb > self.max_memory_mb
    
    def is_fd_exceeded(self, fd_count: int) -> bool:
        """Check if file descriptor count exceeds limit."""
        return fd_count > self.max_file_descriptors
    
    def should_alert_cpu(self, cpu_percent: float) -> bool:
        """Check if CPU usage should trigger alert."""
        return cpu_percent > (self.max_cpu_percent * self.cpu_alert_threshold)
    
    def should_alert_memory(self, memory_mb: float) -> bool:
        """Check if memory usage should trigger alert."""
        return memory_mb > (self.max_memory_mb * self.memory_alert_threshold)


@dataclass
class ProcessResourceHistory:
    """Historical resource usage tracking."""
    cpu_history: List[float] = field(default_factory=list)
    memory_history: List[float] = field(default_factory=list)
    timestamp_history: List[datetime] = field(default_factory=list)
    max_history_size: int = 100  # Keep last 100 measurements
    
    def add_measurement(self, cpu_percent: float, memory_mb: float) -> None:
        """Add a resource measurement."""
        now = datetime.utcnow()
        
        self.cpu_history.append(cpu_percent)
        self.memory_history.append(memory_mb)
        self.timestamp_history.append(now)
        
        # Trim history if too large
        if len(self.cpu_history) > self.max_history_size:
            self.cpu_history.pop(0)
            self.memory_history.pop(0)
            self.timestamp_history.pop(0)
    
    def get_cpu_trend(self) -> str:
        """Get CPU usage trend."""
        if len(self.cpu_history) < 3:
            return "insufficient_data"
        
        recent = sum(self.cpu_history[-3:]) / 3
        older = sum(self.cpu_history[-6:-3]) / 3 if len(self.cpu_history) >= 6 else recent
        
        if recent > older * 1.1:
            return "increasing"
        elif recent < older * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def get_average_cpu(self, last_n: int = 10) -> float:
        """Get average CPU usage over last N measurements."""
        if not self.cpu_history:
            return 0.0
        recent_measurements = self.cpu_history[-last_n:]
        return sum(recent_measurements) / len(recent_measurements)
    
    def get_peak_memory(self) -> float:
        """Get peak memory usage."""
        return max(self.memory_history) if self.memory_history else 0.0


@dataclass
class ProcessMetrics:
    """Process resource usage metrics with comprehensive monitoring."""
    # Basic metrics
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    file_descriptors: int = 0
    threads: int = 0
    
    # Extended metrics
    memory_vms_mb: float = 0.0  # Virtual memory size
    memory_shared_mb: float = 0.0  # Shared memory
    network_connections: int = 0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    disk_io_mb_per_sec: float = 0.0
    open_files: int = 0
    
    # Context switches and system calls
    ctx_switches_voluntary: int = 0
    ctx_switches_involuntary: int = 0
    
    # Timestamps
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    last_disk_io_time: Optional[datetime] = None
    
    # Historical tracking
    history: ProcessResourceHistory = field(default_factory=ProcessResourceHistory)
    
    # Resource limits
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    
    # Alert tracking
    alert_count: int = 0
    last_alert_time: Optional[datetime] = None
    
    def update_from_psutil(self, proc: psutil.Process) -> None:
        """Update metrics from psutil process with comprehensive data collection."""
        try:
            now = datetime.utcnow()
            
            # Basic metrics
            self.cpu_percent = proc.cpu_percent()
            memory_info = proc.memory_info()
            self.memory_mb = memory_info.rss / 1024 / 1024
            self.memory_vms_mb = memory_info.vms / 1024 / 1024
            
            # Memory details (platform-dependent)
            try:
                memory_full_info = proc.memory_full_info()
                if hasattr(memory_full_info, 'shared'):
                    self.memory_shared_mb = memory_full_info.shared / 1024 / 1024
            except (AttributeError, psutil.AccessDenied):
                pass
            
            # File descriptors and threads
            self.file_descriptors = proc.num_fds() if hasattr(proc, 'num_fds') else 0
            self.threads = proc.num_threads()
            
            # Network connections
            try:
                connections = proc.connections()
                self.network_connections = len(connections)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Disk I/O
            try:
                io_counters = proc.io_counters()
                if io_counters:
                    # Calculate I/O rate if we have previous measurement
                    if self.last_disk_io_time:
                        time_delta = (now - self.last_disk_io_time).total_seconds()
                        if time_delta > 0:
                            read_delta = (io_counters.read_bytes / 1024 / 1024) - self.disk_read_mb
                            write_delta = (io_counters.write_bytes / 1024 / 1024) - self.disk_write_mb
                            self.disk_io_mb_per_sec = (read_delta + write_delta) / time_delta
                    
                    self.disk_read_mb = io_counters.read_bytes / 1024 / 1024
                    self.disk_write_mb = io_counters.write_bytes / 1024 / 1024
                    self.last_disk_io_time = now
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Open files
            try:
                open_files = proc.open_files()
                self.open_files = len(open_files)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Context switches
            try:
                ctx_switches = proc.num_ctx_switches()
                if ctx_switches:
                    self.ctx_switches_voluntary = ctx_switches.voluntary
                    self.ctx_switches_involuntary = ctx_switches.involuntary
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # Update history
            self.history.add_measurement(self.cpu_percent, self.memory_mb)
            
            # Update timestamp
            self.last_updated = now
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def check_resource_limits(self) -> List[str]:
        """Check if any resource limits are exceeded.
        
        Returns:
            List of violated limit descriptions
        """
        violations = []
        
        if self.limits.is_cpu_exceeded(self.cpu_percent):
            violations.append(f"CPU usage {self.cpu_percent:.1f}% exceeds limit {self.limits.max_cpu_percent:.1f}%")
        
        if self.limits.is_memory_exceeded(self.memory_mb):
            violations.append(f"Memory usage {self.memory_mb:.1f}MB exceeds limit {self.limits.max_memory_mb:.1f}MB")
        
        if self.limits.is_fd_exceeded(self.file_descriptors):
            violations.append(f"File descriptors {self.file_descriptors} exceeds limit {self.limits.max_file_descriptors}")
        
        if self.threads > self.limits.max_threads:
            violations.append(f"Thread count {self.threads} exceeds limit {self.limits.max_threads}")
        
        if self.network_connections > self.limits.max_connections:
            violations.append(f"Network connections {self.network_connections} exceeds limit {self.limits.max_connections}")
        
        if self.disk_io_mb_per_sec > self.limits.max_disk_io_mb_per_sec:
            violations.append(f"Disk I/O {self.disk_io_mb_per_sec:.1f}MB/s exceeds limit {self.limits.max_disk_io_mb_per_sec:.1f}MB/s")
        
        return violations
    
    def should_trigger_alerts(self) -> List[str]:
        """Check if resource usage should trigger alerts.
        
        Returns:
            List of alert conditions
        """
        alerts = []
        
        if self.limits.should_alert_cpu(self.cpu_percent):
            alerts.append(f"CPU usage {self.cpu_percent:.1f}% approaching limit")
        
        if self.limits.should_alert_memory(self.memory_mb):
            alerts.append(f"Memory usage {self.memory_mb:.1f}MB approaching limit")
        
        if self.file_descriptors > (self.limits.max_file_descriptors * self.limits.fd_alert_threshold):
            alerts.append(f"File descriptor usage {self.file_descriptors} approaching limit")
        
        return alerts
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get comprehensive resource usage summary."""
        return {
            "cpu": {
                "current_percent": self.cpu_percent,
                "trend": self.history.get_cpu_trend(),
                "average_10min": self.history.get_average_cpu(),
                "limit": self.limits.max_cpu_percent
            },
            "memory": {
                "rss_mb": self.memory_mb,
                "vms_mb": self.memory_vms_mb,
                "shared_mb": self.memory_shared_mb,
                "peak_mb": self.history.get_peak_memory(),
                "limit_mb": self.limits.max_memory_mb
            },
            "io": {
                "file_descriptors": self.file_descriptors,
                "open_files": self.open_files,
                "network_connections": self.network_connections,
                "disk_read_mb": self.disk_read_mb,
                "disk_write_mb": self.disk_write_mb,
                "disk_io_rate_mb_per_sec": self.disk_io_mb_per_sec
            },
            "system": {
                "threads": self.threads,
                "ctx_switches_voluntary": self.ctx_switches_voluntary,
                "ctx_switches_involuntary": self.ctx_switches_involuntary
            },
            "alerts": {
                "alert_count": self.alert_count,
                "last_alert": self.last_alert_time.isoformat() if self.last_alert_time else None
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with comprehensive metrics."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "memory_vms_mb": self.memory_vms_mb,
            "memory_shared_mb": self.memory_shared_mb,
            "file_descriptors": self.file_descriptors,
            "threads": self.threads,
            "network_connections": self.network_connections,
            "disk_read_mb": self.disk_read_mb,
            "disk_write_mb": self.disk_write_mb,
            "disk_io_mb_per_sec": self.disk_io_mb_per_sec,
            "open_files": self.open_files,
            "ctx_switches_voluntary": self.ctx_switches_voluntary,
            "ctx_switches_involuntary": self.ctx_switches_involuntary,
            "start_time": self.start_time.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "resource_summary": self.get_resource_summary(),
            "violations": self.check_resource_limits(),
            "alert_triggers": self.should_trigger_alerts()
        }


@dataclass 
class ProcessRecord:
    """Process registry record."""
    process_id: str
    pid: int
    process_type: ProcessType
    parent_process_id: Optional[str] = None
    session_id: Optional[str] = None
    binary_path: Optional[str] = None
    command_line: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None
    status: ProcessStatus = ProcessStatus.STARTING
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: ProcessMetrics = field(default_factory=ProcessMetrics)
    pid_info: Optional[ProcessPIDInfo] = None  # Enhanced PID tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize process ID if not provided."""
        if not self.process_id:
            self.process_id = f"proc_{uuid.uuid4().hex[:12]}"
    
    def update_heartbeat(self) -> None:
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow()
        self.updated_at = self.last_heartbeat
    
    def is_alive(self) -> bool:
        """Check if process is still alive."""
        try:
            # Check if PID exists and is accessible
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def get_psutil_process(self) -> Optional[psutil.Process]:
        """Get psutil process object."""
        try:
            return psutil.Process(self.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "process_id": self.process_id,
            "pid": self.pid,
            "process_type": self.process_type.value,
            "parent_process_id": self.parent_process_id,
            "session_id": self.session_id,
            "binary_path": self.binary_path,
            "command_line": self.command_line,
            "start_time": self.start_time.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "status": self.status.value,
            "metadata": self.metadata,
            "metrics": self.metrics.to_dict(),
            "pid_info": self.pid_info.to_dict() if self.pid_info else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessRecord':
        """Create from dictionary."""
        metrics_data = data.get("metrics", {})
        metrics = ProcessMetrics(
            cpu_percent=metrics_data.get("cpu_percent", 0.0),
            memory_mb=metrics_data.get("memory_mb", 0.0),
            file_descriptors=metrics_data.get("file_descriptors", 0),
            threads=metrics_data.get("threads", 0),
            start_time=datetime.fromisoformat(metrics_data.get("start_time", datetime.utcnow().isoformat())),
            last_updated=datetime.fromisoformat(metrics_data.get("last_updated", datetime.utcnow().isoformat()))
        )
        
        # Parse PID info if available
        pid_info = None
        if data.get("pid_info"):
            pid_info = ProcessPIDInfo.from_dict(data["pid_info"])
        
        return cls(
            process_id=data["process_id"],
            pid=data["pid"],
            process_type=ProcessType(data["process_type"]),
            parent_process_id=data.get("parent_process_id"),
            session_id=data.get("session_id"),
            binary_path=data.get("binary_path"),
            command_line=data.get("command_line"),
            start_time=datetime.fromisoformat(data["start_time"]),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]) if data.get("last_heartbeat") else None,
            status=ProcessStatus(data["status"]),
            metadata=data.get("metadata", {}),
            metrics=metrics,
            pid_info=pid_info,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


class ProcessManager(BaseManager[ProcessRecord]):
    """Manages system-wide process registry."""
    
    def __init__(self):
        """Initialize process manager."""
        config = get_config()
        manager_config = ManagerConfig(
            name="process_manager",
            db_path=Path.home() / ".shannon-mcp" / "process_registry.db",
            custom_config={}
        )
        super().__init__(manager_config)
        
        # In-memory process registry
        self._processes: Dict[str, ProcessRecord] = {}
        self._pid_to_process_id: Dict[int, str] = {}
        self._registry_lock = asyncio.Lock()
        
        # Enhanced PID tracking
        self._pid_events: List[PIDEvent] = []  # In-memory PID event buffer
        self._pid_audit_lock = asyncio.Lock()
        
        # PID file directory
        self._pid_dir = Path.home() / ".shannon-mcp" / "pids"
        self._pid_dir.mkdir(parents=True, exist_ok=True)
        
        # Cleanup scheduling
        self._last_cleanup = datetime.utcnow()
        self._cleanup_interval = 3600   # 1 hour between comprehensive cleanups
        
        # Monitoring settings
        self._monitoring_interval = 30.0  # seconds
        self._heartbeat_timeout = 300.0   # 5 minutes
        self._cleanup_age = 3600.0        # 1 hour for stopped processes
        
        # Register shutdown handler
        register_shutdown_handler(
            "process_manager",
            self._shutdown_processes,
            phase=ShutdownPhase.STOP_WORKERS,
            timeout=30.0
        )
    
    async def _initialize(self) -> None:
        """Initialize process manager."""
        logger.info("initializing_process_manager")
        
        # Clean up stale PID files on startup
        await self._cleanup_stale_pid_files()
        
        # Load active processes from database
        await self._load_active_processes()
        
        # Validate loaded processes
        await self._validate_loaded_processes()
    
    async def _start(self) -> None:
        """Start process manager operations."""
        # Start process monitoring
        self._tasks.append(
            asyncio.create_task(self._monitor_processes())
        )
        
        # Start resource monitoring
        self._tasks.append(
            asyncio.create_task(self._monitor_resources())
        )
    
    async def _stop(self) -> None:
        """Stop process manager operations."""
        # Gracefully terminate tracked processes
        await self._shutdown_processes()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        total_processes = len(self._processes)
        running_processes = sum(
            1 for p in self._processes.values() 
            if p.status == ProcessStatus.RUNNING
        )
        orphaned_processes = sum(
            1 for p in self._processes.values()
            if p.status == ProcessStatus.ORPHANED
        )
        
        # Check system resource usage
        system_cpu = psutil.cpu_percent()
        system_memory = psutil.virtual_memory().percent
        
        return {
            "total_processes": total_processes,
            "running_processes": running_processes,
            "orphaned_processes": orphaned_processes,
            "system_cpu_percent": system_cpu,
            "system_memory_percent": system_memory,
            "pid_files": len(list(self._pid_dir.glob("*.pid"))),
            "monitoring_active": not self._stop_event.is_set(),
            "pid_tracking_enabled": True,
            "pid_audit_events": await self._count_pid_events()
        }
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS process_registry (
                process_id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                process_type TEXT NOT NULL,
                parent_process_id TEXT,
                session_id TEXT,
                binary_path TEXT,
                command_line TEXT,
                start_time TEXT NOT NULL,
                last_heartbeat TEXT,
                status TEXT NOT NULL,
                metadata TEXT,
                metrics TEXT,
                pid_info TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create PID audit trail table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS pid_audit_trail (
                id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                process_id TEXT,
                details TEXT
            )
        """)
        
        # Create indexes for performance
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_registry_pid 
            ON process_registry(pid)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_registry_status 
            ON process_registry(status)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_registry_type 
            ON process_registry(process_type)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_registry_session 
            ON process_registry(session_id)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_process_registry_heartbeat 
            ON process_registry(last_heartbeat)
        """)
        
        # Create indexes for PID audit trail
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pid_audit_pid 
            ON pid_audit_trail(pid)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pid_audit_timestamp 
            ON pid_audit_trail(timestamp)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pid_audit_event_type 
            ON pid_audit_trail(event_type)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pid_audit_process_id 
            ON pid_audit_trail(process_id)
        """)
        
        # Create validation results table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                id TEXT PRIMARY KEY,
                process_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                is_valid BOOLEAN NOT NULL,
                validation_time TEXT NOT NULL,
                integrity_valid BOOLEAN NOT NULL,
                resource_valid BOOLEAN NOT NULL,
                security_valid BOOLEAN NOT NULL,
                lifecycle_valid BOOLEAN NOT NULL,
                warnings TEXT,
                errors TEXT,
                metrics TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (process_id) REFERENCES process_registry(process_id)
            )
        """)
        
        # Create indexes for validation results
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_results_process_id 
            ON validation_results(process_id)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_results_pid 
            ON validation_results(pid)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_results_validation_time 
            ON validation_results(validation_time)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_validation_results_is_valid 
            ON validation_results(is_valid)
        """)
    
    @track_request_lifetime
    async def register_process(
        self,
        pid: int,
        process_type: ProcessType,
        binary_path: Optional[str] = None,
        command_line: Optional[str] = None,
        session_id: Optional[str] = None,
        parent_process_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessRecord:
        """
        Register a new process in the registry.
        
        Args:
            pid: Process ID
            process_type: Type of process
            binary_path: Path to binary
            command_line: Full command line
            session_id: Associated session ID
            parent_process_id: Parent process ID
            metadata: Additional metadata
            
        Returns:
            Process record
            
        Raises:
            ValidationError: If process validation fails
            SystemError: If registration fails
        """
        async with self._registry_lock:
            # Validate PID
            if not self._validate_pid(pid):
                raise ValidationError("pid", pid, "Process not found or not accessible")
            
            # Enhanced PID collision detection
            if pid in self._pid_to_process_id:
                existing_process_id = self._pid_to_process_id[pid]
                existing_record = self._processes.get(existing_process_id)
                if existing_record and existing_record.is_alive():
                    # Check for PID reuse by comparing metadata
                    if await self._detect_pid_reuse(pid):
                        # PID has been reused, resolve collision
                        await self._resolve_pid_collision(pid, existing_process_id)
                    else:
                        logger.warning(
                            "process_already_registered",
                            pid=pid,
                            existing_process_id=existing_process_id
                        )
                        return existing_record
            
            with error_context("process_manager", "register_process", pid=pid):
                # Get detailed PID information for tracking
                pid_info = await self._get_detailed_pid_info(pid)
                
                # Create process record
                process_record = ProcessRecord(
                    process_id="",  # Will be auto-generated
                    pid=pid,
                    process_type=process_type,
                    parent_process_id=parent_process_id,
                    session_id=session_id,
                    binary_path=binary_path,
                    command_line=command_line,
                    metadata=metadata or {},
                    status=ProcessStatus.STARTING,
                    pid_info=pid_info  # Enhanced PID tracking
                )
                
                # Update metrics from psutil
                psutil_proc = process_record.get_psutil_process()
                if psutil_proc:
                    process_record.metrics.update_from_psutil(psutil_proc)
                    process_record.status = ProcessStatus.RUNNING
                
                # Store in memory
                self._processes[process_record.process_id] = process_record
                self._pid_to_process_id[pid] = process_record.process_id
                
                # Log PID event
                await self._log_pid_event(
                    pid, "created",
                    process_id=process_record.process_id,
                    details={
                        "process_type": process_type.value,
                        "binary_path": binary_path or "unknown",
                        "command_line": command_line or "unknown"
                    }
                )
                
                # Save to database
                await self._save_process(process_record)
                
                # Create PID file
                await self._create_pid_file(process_record)
                
                # Emit event
                await emit(
                    "process_registered",
                    EventCategory.SYSTEM,
                    {
                        "process_id": process_record.process_id,
                        "pid": pid,
                        "process_type": process_type.value
                    },
                    priority=EventPriority.MEDIUM
                )
                
                logger.info(
                    "process_registered",
                    process_id=process_record.process_id,
                    pid=pid,
                    process_type=process_type.value
                )
                
                return process_record
    
    async def unregister_process(self, process_id: str) -> None:
        """
        Unregister a process from the registry.
        
        Args:
            process_id: Process ID to unregister
            
        Raises:
            ValidationError: If process not found
        """
        async with self._registry_lock:
            process_record = self._processes.get(process_id)
            if not process_record:
                raise ValidationError("process_id", process_id, "Process not found")
            
            with error_context("process_manager", "unregister_process", process_id=process_id):
                # Update status to stopped
                process_record.status = ProcessStatus.STOPPED
                process_record.updated_at = datetime.utcnow()
                
                # Remove from memory
                self._processes.pop(process_id, None)
                self._pid_to_process_id.pop(process_record.pid, None)
                
                # Update database
                await self._save_process(process_record)
                
                # Clean up PID file
                await self._remove_pid_file(process_record)
                
                # Emit event
                await emit(
                    "process_unregistered",
                    EventCategory.SYSTEM,
                    {
                        "process_id": process_id,
                        "pid": process_record.pid
                    }
                )
                
                logger.info(
                    "process_unregistered",
                    process_id=process_id,
                    pid=process_record.pid
                )
    
    async def get_process(self, process_id: str) -> Optional[ProcessRecord]:
        """Get process by ID."""
        return self._processes.get(process_id)
    
    async def get_process_by_pid(self, pid: int) -> Optional[ProcessRecord]:
        """Get process by PID."""
        process_id = self._pid_to_process_id.get(pid)
        if process_id:
            return self._processes.get(process_id)
        return None
    
    async def list_processes(
        self,
        process_type: Optional[ProcessType] = None,
        status: Optional[ProcessStatus] = None,
        session_id: Optional[str] = None
    ) -> List[ProcessRecord]:
        """
        List processes with optional filtering.
        
        Args:
            process_type: Filter by process type
            status: Filter by status
            session_id: Filter by session ID
            
        Returns:
            List of process records
        """
        processes = list(self._processes.values())
        
        if process_type:
            processes = [p for p in processes if p.process_type == process_type]
        
        if status:
            processes = [p for p in processes if p.status == status]
        
        if session_id:
            processes = [p for p in processes if p.session_id == session_id]
        
        # Sort by creation time, newest first
        processes.sort(key=lambda p: p.created_at, reverse=True)
        
        return processes
    
    async def update_heartbeat(self, process_id: str) -> None:
        """
        Update process heartbeat.
        
        Args:
            process_id: Process ID
            
        Raises:
            ValidationError: If process not found
        """
        process_record = self._processes.get(process_id)
        if not process_record:
            raise ValidationError("process_id", process_id, "Process not found")
        
        process_record.update_heartbeat()
        
        # Update database periodically (not every heartbeat for performance)
        now = datetime.utcnow()
        if not hasattr(process_record, '_last_db_update') or \
           (now - getattr(process_record, '_last_db_update', now)).total_seconds() > 60:
            await self._save_process(process_record)
            setattr(process_record, '_last_db_update', now)
    
    async def terminate_process(
        self,
        process_id: str,
        force: bool = False,
        timeout: float = 10.0
    ) -> None:
        """
        Terminate a process gracefully or forcefully.
        
        Args:
            process_id: Process ID
            force: Force termination with SIGKILL
            timeout: Timeout for graceful termination
            
        Raises:
            ValidationError: If process not found
            SystemError: If termination fails
        """
        process_record = self._processes.get(process_id)
        if not process_record:
            raise ValidationError("process_id", process_id, "Process not found")
        
        if not process_record.is_alive():
            logger.warning(
                "process_already_dead",
                process_id=process_id,
                pid=process_record.pid
            )
            process_record.status = ProcessStatus.STOPPED
            await self._save_process(process_record)
            return
        
        with error_context("process_manager", "terminate_process", process_id=process_id):
            process_record.status = ProcessStatus.STOPPING
            await self._save_process(process_record)
            
            try:
                if force:
                    # Force kill
                    if os.name == 'nt':
                        os.kill(process_record.pid, signal.SIGTERM)
                    else:
                        os.killpg(os.getpgid(process_record.pid), signal.SIGKILL)
                else:
                    # Graceful termination
                    if os.name == 'nt':
                        os.kill(process_record.pid, signal.SIGTERM)
                    else:
                        os.killpg(os.getpgid(process_record.pid), signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    for _ in range(int(timeout * 10)):  # Check every 100ms
                        if not process_record.is_alive():
                            break
                        await asyncio.sleep(0.1)
                    else:
                        # Force kill after timeout
                        logger.warning(
                            "graceful_termination_timeout",
                            process_id=process_id,
                            pid=process_record.pid
                        )
                        if os.name == 'nt':
                            os.kill(process_record.pid, signal.SIGTERM)
                        else:
                            os.killpg(os.getpgid(process_record.pid), signal.SIGKILL)
                
                process_record.status = ProcessStatus.STOPPED
                await self._save_process(process_record)
                
                # Emit event
                await emit(
                    "process_terminated",
                    EventCategory.SYSTEM,
                    {
                        "process_id": process_id,
                        "pid": process_record.pid,
                        "force": force
                    }
                )
                
                logger.info(
                    "process_terminated",
                    process_id=process_id,
                    pid=process_record.pid,
                    force=force
                )
                
            except (OSError, ProcessLookupError) as e:
                logger.error(
                    "process_termination_failed",
                    process_id=process_id,
                    pid=process_record.pid,
                    error=str(e)
                )
                raise SystemError(f"Failed to terminate process {process_record.pid}: {e}") from e
    
    # Helper methods
    
    def _validate_pid(self, pid: int) -> bool:
        """Validate if PID exists and is accessible."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    async def _save_process(self, process_record: ProcessRecord) -> None:
        """Save process record to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO process_registry 
            (process_id, pid, process_type, parent_process_id, session_id,
             binary_path, command_line, start_time, last_heartbeat, status,
             metadata, metrics, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            process_record.process_id,
            process_record.pid,
            process_record.process_type.value,
            process_record.parent_process_id,
            process_record.session_id,
            process_record.binary_path,
            process_record.command_line,
            process_record.start_time.isoformat(),
            process_record.last_heartbeat.isoformat() if process_record.last_heartbeat else None,
            process_record.status.value,
            json.dumps(process_record.metadata),
            json.dumps(process_record.metrics.to_dict()),
            process_record.created_at.isoformat(),
            process_record.updated_at.isoformat()
        ))
        await self.db.commit()
    
    async def _load_active_processes(self) -> None:
        """Load active processes from database."""
        async with self.db.execute("""
            SELECT * FROM process_registry 
            WHERE status IN ('starting', 'running', 'stopping')
        """) as cursor:
            rows = await cursor.fetchall()
            
            for row in rows:
                try:
                    # Convert row to dict
                    process_data = {
                        "process_id": row[0],
                        "pid": row[1],
                        "process_type": row[2],
                        "parent_process_id": row[3],
                        "session_id": row[4],
                        "binary_path": row[5],
                        "command_line": row[6],
                        "start_time": row[7],
                        "last_heartbeat": row[8],
                        "status": row[9],
                        "metadata": json.loads(row[10]) if row[10] else {},
                        "metrics": json.loads(row[11]) if row[11] else {},
                        "created_at": row[12],
                        "updated_at": row[13]
                    }
                    
                    # Create process record
                    process_record = ProcessRecord.from_dict(process_data)
                    
                    # Store in memory
                    self._processes[process_record.process_id] = process_record
                    self._pid_to_process_id[process_record.pid] = process_record.process_id
                    
                except Exception as e:
                    logger.error(
                        "failed_to_load_process",
                        process_id=row[0] if len(row) > 0 else "unknown",
                        error=str(e)
                    )
        
        logger.info(
            "processes_loaded_from_database",
            count=len(self._processes)
        )
    
    async def _validate_loaded_processes(self) -> None:
        """Validate loaded processes and mark orphaned ones."""
        orphaned_count = 0
        
        for process_record in list(self._processes.values()):
            if not process_record.is_alive():
                logger.warning(
                    "orphaned_process_detected",
                    process_id=process_record.process_id,
                    pid=process_record.pid
                )
                process_record.status = ProcessStatus.ORPHANED
                await self._save_process(process_record)
                orphaned_count += 1
        
        if orphaned_count > 0:
            logger.info(
                "orphaned_processes_detected",
                count=orphaned_count
            )
    
    async def _create_pid_file(self, process_record: ProcessRecord) -> None:
        """Create PID file for process."""
        pid_file = self._pid_dir / f"{process_record.process_id}.pid"
        
        try:
            with pid_file.open('w') as f:
                json.dump({
                    "process_id": process_record.process_id,
                    "pid": process_record.pid,
                    "process_type": process_record.process_type.value,
                    "created_at": process_record.created_at.isoformat()
                }, f, indent=2)
                
            logger.debug(
                "pid_file_created",
                process_id=process_record.process_id,
                pid_file=str(pid_file)
            )
        except Exception as e:
            logger.error(
                "pid_file_creation_failed",
                process_id=process_record.process_id,
                pid_file=str(pid_file),
                error=str(e)
            )
    
    async def _remove_pid_file(self, process_record: ProcessRecord) -> None:
        """Remove PID file for process."""
        pid_file = self._pid_dir / f"{process_record.process_id}.pid"
        
        try:
            if pid_file.exists():
                pid_file.unlink()
                logger.debug(
                    "pid_file_removed",
                    process_id=process_record.process_id,
                    pid_file=str(pid_file)
                )
        except Exception as e:
            logger.error(
                "pid_file_removal_failed",
                process_id=process_record.process_id,
                pid_file=str(pid_file),
                error=str(e)
            )
    
    async def _cleanup_stale_pid_files(self) -> None:
        """Clean up stale PID files on startup."""
        if not self._pid_dir.exists():
            return
        
        cleaned_count = 0
        
        for pid_file in self._pid_dir.glob("*.pid"):
            try:
                with pid_file.open('r') as f:
                    data = json.load(f)
                
                pid = data.get("pid")
                if pid and not self._validate_pid(pid):
                    # Process is dead, remove stale PID file
                    pid_file.unlink()
                    cleaned_count += 1
                    logger.debug(
                        "stale_pid_file_removed",
                        pid_file=str(pid_file),
                        pid=pid
                    )
                    
            except Exception as e:
                # Invalid PID file, remove it
                try:
                    pid_file.unlink()
                    cleaned_count += 1
                    logger.debug(
                        "invalid_pid_file_removed",
                        pid_file=str(pid_file),
                        error=str(e)
                    )
                except:
                    pass
        
        if cleaned_count > 0:
            logger.info(
                "stale_pid_files_cleaned",
                count=cleaned_count
            )
    
    # Monitoring methods
    
    async def _monitor_processes(self) -> None:
        """Monitor process health and status."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self._monitoring_interval)
                
                if self._stop_event.is_set():
                    break
                
                now = datetime.utcnow()
                
                # Check for dead processes
                dead_processes = []
                orphaned_processes = []
                stale_processes = []
                
                for process_id, process_record in list(self._processes.items()):
                    # Check if process is still alive
                    if not process_record.is_alive():
                        if process_record.status in (ProcessStatus.RUNNING, ProcessStatus.STARTING):
                            # Process died unexpectedly
                            process_record.status = ProcessStatus.ORPHANED
                            orphaned_processes.append(process_record)
                        elif process_record.status == ProcessStatus.STOPPING:
                            # Process completed shutdown
                            process_record.status = ProcessStatus.STOPPED
                            dead_processes.append(process_record)
                    
                    # Check for stale heartbeat
                    if (process_record.last_heartbeat and 
                        (now - process_record.last_heartbeat).total_seconds() > self._heartbeat_timeout):
                        logger.warning(
                            "process_heartbeat_stale",
                            process_id=process_id,
                            pid=process_record.pid,
                            last_heartbeat=process_record.last_heartbeat.isoformat()
                        )
                    
                    # Check for old stopped processes
                    if (process_record.status in (ProcessStatus.STOPPED, ProcessStatus.FAILED) and
                        (now - process_record.updated_at).total_seconds() > self._cleanup_age):
                        stale_processes.append(process_record)
                
                # Handle dead processes
                for process_record in dead_processes:
                    logger.info(
                        "process_completed_shutdown",
                        process_id=process_record.process_id,
                        pid=process_record.pid
                    )
                    await self._save_process(process_record)
                
                # Handle orphaned processes
                for process_record in orphaned_processes:
                    logger.warning(
                        "process_orphaned",
                        process_id=process_record.process_id,
                        pid=process_record.pid
                    )
                    await self._save_process(process_record)
                    
                    # Emit orphaned process event
                    await emit(
                        "process_orphaned",
                        EventCategory.SYSTEM,
                        {
                            "process_id": process_record.process_id,
                            "pid": process_record.pid,
                            "process_type": process_record.process_type.value
                        },
                        priority=EventPriority.HIGH
                    )
                
                # Clean up stale processes
                for process_record in stale_processes:
                    logger.debug(
                        "cleaning_stale_process",
                        process_id=process_record.process_id,
                        pid=process_record.pid
                    )
                    self._processes.pop(process_record.process_id, None)
                    self._pid_to_process_id.pop(process_record.pid, None)
                    await self._remove_pid_file(process_record)
                
                # Run comprehensive cleanup periodically
                if (now - self._last_cleanup).total_seconds() >= self._cleanup_interval:
                    logger.info("running_scheduled_cleanup")
                    try:
                        cleanup_stats = await self.run_comprehensive_cleanup()
                        self._last_cleanup = now
                        
                        # Log cleanup summary
                        if any(cleanup_stats.values()):
                            logger.info(
                                "scheduled_cleanup_completed",
                                **cleanup_stats
                            )
                    except Exception as cleanup_error:
                        logger.error(
                            "scheduled_cleanup_failed",
                            error=str(cleanup_error)
                        )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "process_monitoring_error",
                    error=str(e),
                    exc_info=True
                )
    
    async def _monitor_resources(self) -> None:
        """Monitor resource usage of tracked processes with comprehensive validation."""
        # Configurable monitoring intervals
        config = get_config()
        monitoring_interval = getattr(config, 'process_monitoring_interval', 60.0)  # Default 60 seconds
        resource_validation_interval = getattr(config, 'resource_validation_interval', 300.0)  # Default 5 minutes
        
        last_validation_time = datetime.utcnow()
        
        logger.info(
            "resource_monitoring_started",
            monitoring_interval=monitoring_interval,
            validation_interval=resource_validation_interval
        )
        
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(monitoring_interval)
                
                if self._stop_event.is_set():
                    break
                
                now = datetime.utcnow()
                
                # Comprehensive resource monitoring
                await self._collect_comprehensive_metrics()
                
                # Periodic resource validation and enforcement
                if (now - last_validation_time).total_seconds() >= resource_validation_interval:
                    await self._validate_and_enforce_resource_limits()
                    last_validation_time = now
                
                # Log aggregate system statistics
                await self._log_system_resource_summary()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "resource_monitoring_error",
                    error=str(e),
                    exc_info=True
                )
    
    async def _collect_comprehensive_metrics(self) -> None:
        """Collect comprehensive resource metrics for all tracked processes."""
        collection_start = datetime.utcnow()
        successful_collections = 0
        failed_collections = 0
        
        # Process processes in batches for performance
        batch_size = 50  # Process up to 50 processes at once
        process_items = list(self._processes.items())
        
        for i in range(0, len(process_items), batch_size):
            batch = process_items[i:i + batch_size]
            
            # Collect metrics for batch
            for process_id, process_record in batch:
                try:
                    if process_record.status == ProcessStatus.RUNNING:
                        psutil_proc = process_record.get_psutil_process()
                        if psutil_proc:
                            # Update comprehensive metrics
                            process_record.metrics.update_from_psutil(psutil_proc)
                            successful_collections += 1
                            
                            # Check for immediate alerts (critical violations)
                            violations = process_record.metrics.check_resource_limits()
                            if violations:
                                await self._handle_resource_violations(process_id, process_record, violations)
                            
                            # Check for alert thresholds
                            alerts = process_record.metrics.should_trigger_alerts()
                            if alerts:
                                await self._handle_resource_alerts(process_id, process_record, alerts)
                        else:
                            # Process no longer accessible, mark as orphaned
                            process_record.status = ProcessStatus.ORPHANED
                            failed_collections += 1
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    failed_collections += 1
                    logger.debug(
                        "process_metrics_collection_failed",
                        process_id=process_id,
                        pid=process_record.pid,
                        error=str(e)
                    )
                except Exception as e:
                    failed_collections += 1
                    logger.error(
                        "process_metrics_collection_error",
                        process_id=process_id,
                        pid=process_record.pid,
                        error=str(e)
                    )
            
            # Yield control between batches to prevent blocking
            if not self._stop_event.is_set():
                await asyncio.sleep(0.1)
        
        collection_duration = (datetime.utcnow() - collection_start).total_seconds()
        
        logger.debug(
            "resource_metrics_collection_completed",
            successful_collections=successful_collections,
            failed_collections=failed_collections,
            total_processes=len(self._processes),
            collection_duration_seconds=collection_duration
        )
    
    async def _handle_resource_violations(
        self,
        process_id: str,
        process_record: ProcessRecord,
        violations: List[str]
    ) -> None:
        """Handle processes that exceed resource limits."""
        logger.warning(
            "resource_limits_exceeded",
            process_id=process_id,
            pid=process_record.pid,
            violations=violations,
            metrics_summary=process_record.metrics.get_resource_summary()
        )
        
        # Emit violation event
        await emit(
            "process_resource_violation",
            EventCategory.PROCESS,
            {
                "process_id": process_id,
                "pid": process_record.pid,
                "violations": violations,
                "metrics": process_record.metrics.get_resource_summary()
            },
            priority=EventPriority.HIGH
        )
        
        # Update audit trail
        await self._add_audit_event(
            process_id=process_id,
            event_type="resource_violation",
            details={
                "violations": violations,
                "metrics_snapshot": process_record.metrics.get_resource_summary()
            }
        )
        
        # Determine action based on violation severity
        critical_violations = [v for v in violations if "exceeds limit" in v]
        
        if critical_violations:
            # For critical violations, consider process termination
            await self._handle_critical_resource_violations(process_id, process_record, critical_violations)
        
        # Update process validation results
        await self._update_process_validation_result(
            process_id,
            "resource_limits",
            False,
            f"Resource violations: {'; '.join(violations)}"
        )
    
    async def _handle_critical_resource_violations(
        self,
        process_id: str,
        process_record: ProcessRecord,
        violations: List[str]
    ) -> None:
        """Handle critical resource violations that may require termination."""
        config = get_config()
        auto_terminate_violators = getattr(config, 'auto_terminate_resource_violators', False)
        
        if auto_terminate_violators:
            logger.error(
                "terminating_process_for_resource_violations",
                process_id=process_id,
                pid=process_record.pid,
                violations=violations
            )
            
            try:
                # Attempt graceful termination first
                await self.terminate_process(process_id, force=False, timeout=10.0)
                
                # Emit termination event
                await emit(
                    "process_terminated_resource_violation",
                    EventCategory.PROCESS,
                    {
                        "process_id": process_id,
                        "pid": process_record.pid,
                        "violations": violations,
                        "action": "terminated"
                    },
                    priority=EventPriority.CRITICAL
                )
                
            except Exception as e:
                logger.error(
                    "process_termination_failed",
                    process_id=process_id,
                    pid=process_record.pid,
                    error=str(e)
                )
        else:
            logger.warning(
                "critical_resource_violation_detected",
                process_id=process_id,
                pid=process_record.pid,
                violations=violations,
                note="auto_termination_disabled"
            )
    
    async def _handle_resource_alerts(
        self,
        process_id: str,
        process_record: ProcessRecord,
        alerts: List[str]
    ) -> None:
        """Handle resource usage alerts."""
        # Throttle alerts to prevent spam
        now = datetime.utcnow()
        if (process_record.metrics.last_alert_time and 
            (now - process_record.metrics.last_alert_time).total_seconds() < 300):  # 5 minutes
            return
        
        process_record.metrics.alert_count += 1
        process_record.metrics.last_alert_time = now
        
        logger.info(
            "resource_usage_alert",
            process_id=process_id,
            pid=process_record.pid,
            alerts=alerts,
            alert_count=process_record.metrics.alert_count
        )
        
        # Emit alert event
        await emit(
            "process_resource_alert",
            EventCategory.PROCESS,
            {
                "process_id": process_id,
                "pid": process_record.pid,
                "alerts": alerts,
                "alert_count": process_record.metrics.alert_count,
                "metrics": process_record.metrics.get_resource_summary()
            },
            priority=EventPriority.MEDIUM
        )
    
    async def _validate_and_enforce_resource_limits(self) -> None:
        """Validate resource usage across all processes and enforce limits."""
        validation_start = datetime.utcnow()
        
        # Collect system-wide resource statistics
        total_processes = len([p for p in self._processes.values() if p.status == ProcessStatus.RUNNING])
        system_metrics = await self._collect_system_wide_metrics()
        
        # Check system-wide resource usage
        await self._validate_system_resource_limits(system_metrics)
        
        # Run comprehensive validation for processes that haven't been validated recently
        validation_tasks = []
        for process_id, process_record in self._processes.items():
            if process_record.status == ProcessStatus.RUNNING:
                # Check if process needs validation
                last_validation = await self._get_last_validation_time(process_id, "resource_comprehensive")
                
                if not last_validation or (validation_start - last_validation).total_seconds() > 1800:  # 30 minutes
                    validation_tasks.append(
                        self._comprehensive_process_resource_validation(process_id, process_record)
                    )
        
        if validation_tasks:
            # Run validations in parallel, but limit concurrency
            semaphore = asyncio.Semaphore(10)  # Max 10 concurrent validations
            
            async def bounded_validation(task):
                async with semaphore:
                    return await task
            
            bounded_tasks = [bounded_validation(task) for task in validation_tasks]
            results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
            
            # Log validation results
            successful_validations = sum(1 for r in results if r is True)
            failed_validations = sum(1 for r in results if isinstance(r, Exception))
            
            logger.info(
                "resource_validation_completed",
                total_validations=len(validation_tasks),
                successful=successful_validations,
                failed=failed_validations,
                duration_seconds=(datetime.utcnow() - validation_start).total_seconds()
            )
    
    async def _collect_system_wide_metrics(self) -> Dict[str, Any]:
        """Collect system-wide resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1.0)
            cpu_count = psutil.cpu_count()
            
            # Memory usage
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk usage
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network usage
            network_io = psutil.net_io_counters()
            
            # Process counts
            running_processes = len([p for p in self._processes.values() if p.status == ProcessStatus.RUNNING])
            total_processes = len(self._processes)
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                "memory": {
                    "total_mb": memory.total / 1024 / 1024,
                    "available_mb": memory.available / 1024 / 1024,
                    "used_mb": memory.used / 1024 / 1024,
                    "percent": memory.percent,
                    "swap_total_mb": swap.total / 1024 / 1024,
                    "swap_used_mb": swap.used / 1024 / 1024,
                    "swap_percent": swap.percent
                },
                "disk": {
                    "total_gb": disk_usage.total / 1024 / 1024 / 1024,
                    "used_gb": disk_usage.used / 1024 / 1024 / 1024,
                    "free_gb": disk_usage.free / 1024 / 1024 / 1024,
                    "percent": (disk_usage.used / disk_usage.total) * 100,
                    "read_mb": disk_io.read_bytes / 1024 / 1024 if disk_io else 0,
                    "write_mb": disk_io.write_bytes / 1024 / 1024 if disk_io else 0
                },
                "network": {
                    "bytes_sent_mb": network_io.bytes_sent / 1024 / 1024 if network_io else 0,
                    "bytes_recv_mb": network_io.bytes_recv / 1024 / 1024 if network_io else 0,
                    "packets_sent": network_io.packets_sent if network_io else 0,
                    "packets_recv": network_io.packets_recv if network_io else 0
                },
                "processes": {
                    "shannon_running": running_processes,
                    "shannon_total": total_processes,
                    "system_total": len(psutil.pids())
                }
            }
            
        except Exception as e:
            logger.error(
                "system_metrics_collection_failed",
                error=str(e)
            )
            return {}
    
    async def _validate_system_resource_limits(self, system_metrics: Dict[str, Any]) -> None:
        """Validate system-wide resource limits."""
        config = get_config()
        system_limits = getattr(config, 'system_resource_limits', {})
        
        violations = []
        
        # Check system CPU usage
        max_system_cpu = system_limits.get('max_cpu_percent', 95.0)
        if system_metrics.get('cpu', {}).get('percent', 0) > max_system_cpu:
            violations.append(f"System CPU usage {system_metrics['cpu']['percent']:.1f}% exceeds limit {max_system_cpu:.1f}%")
        
        # Check system memory usage
        max_system_memory = system_limits.get('max_memory_percent', 90.0)
        memory_percent = system_metrics.get('memory', {}).get('percent', 0)
        if memory_percent > max_system_memory:
            violations.append(f"System memory usage {memory_percent:.1f}% exceeds limit {max_system_memory:.1f}%")
        
        # Check disk usage
        max_disk_usage = system_limits.get('max_disk_percent', 85.0)
        disk_percent = system_metrics.get('disk', {}).get('percent', 0)
        if disk_percent > max_disk_usage:
            violations.append(f"System disk usage {disk_percent:.1f}% exceeds limit {max_disk_usage:.1f}%")
        
        if violations:
            logger.warning(
                "system_resource_limits_exceeded",
                violations=violations,
                system_metrics=system_metrics
            )
            
            # Emit system violation event
            await emit(
                "system_resource_violation",
                EventCategory.SYSTEM,
                {
                    "violations": violations,
                    "system_metrics": system_metrics
                },
                priority=EventPriority.HIGH
            )
    
    async def _comprehensive_process_resource_validation(
        self,
        process_id: str,
        process_record: ProcessRecord
    ) -> bool:
        """Perform comprehensive resource validation for a single process."""
        try:
            validation_start = datetime.utcnow()
            
            # Get current metrics
            psutil_proc = process_record.get_psutil_process()
            if not psutil_proc:
                await self._update_process_validation_result(
                    process_id,
                    "resource_comprehensive",
                    False,
                    "Process not accessible for validation"
                )
                return False
            
            # Update metrics
            process_record.metrics.update_from_psutil(psutil_proc)
            
            # Check all resource limits
            violations = process_record.metrics.check_resource_limits()
            alerts = process_record.metrics.should_trigger_alerts()
            
            # Analyze resource trends
            cpu_trend = process_record.metrics.history.get_cpu_trend()
            avg_cpu = process_record.metrics.history.get_average_cpu()
            peak_memory = process_record.metrics.history.get_peak_memory()
            
            # Determine validation result
            validation_passed = len(violations) == 0
            
            # Create detailed validation result
            validation_details = {
                "violations": violations,
                "alerts": alerts,
                "trends": {
                    "cpu_trend": cpu_trend,
                    "average_cpu_10min": avg_cpu,
                    "peak_memory_mb": peak_memory
                },
                "metrics_snapshot": process_record.metrics.get_resource_summary(),
                "validation_duration_ms": (datetime.utcnow() - validation_start).total_seconds() * 1000
            }
            
            # Update validation result
            await self._update_process_validation_result(
                process_id,
                "resource_comprehensive",
                validation_passed,
                f"Comprehensive resource validation: {len(violations)} violations, {len(alerts)} alerts",
                validation_details
            )
            
            # Handle violations if any
            if violations:
                await self._handle_resource_violations(process_id, process_record, violations)
            
            return validation_passed
            
        except Exception as e:
            logger.error(
                "comprehensive_resource_validation_failed",
                process_id=process_id,
                error=str(e)
            )
            
            await self._update_process_validation_result(
                process_id,
                "resource_comprehensive",
                False,
                f"Validation failed: {str(e)}"
            )
            
            return False
    
    async def _log_system_resource_summary(self) -> None:
        """Log comprehensive system resource usage summary."""
        try:
            # Collect process-level statistics
            running_processes = [p for p in self._processes.values() if p.status == ProcessStatus.RUNNING]
            
            if not running_processes:
                return
            
            total_cpu = sum(p.metrics.cpu_percent for p in running_processes)
            total_memory = sum(p.metrics.memory_mb for p in running_processes)
            total_file_descriptors = sum(p.metrics.file_descriptors for p in running_processes)
            total_threads = sum(p.metrics.threads for p in running_processes)
            total_connections = sum(p.metrics.network_connections for p in running_processes)
            
            # Calculate averages
            process_count = len(running_processes)
            avg_cpu = total_cpu / process_count if process_count > 0 else 0
            avg_memory = total_memory / process_count if process_count > 0 else 0
            
            # Count processes with violations and alerts
            processes_with_violations = sum(1 for p in running_processes if p.metrics.check_resource_limits())
            processes_with_alerts = sum(1 for p in running_processes if p.metrics.should_trigger_alerts())
            
            # Get system metrics
            system_metrics = await self._collect_system_wide_metrics()
            
            logger.info(
                "comprehensive_resource_summary",
                shannon_processes={
                    "count": process_count,
                    "total_cpu_percent": total_cpu,
                    "avg_cpu_percent": avg_cpu,
                    "total_memory_mb": total_memory,
                    "avg_memory_mb": avg_memory,
                    "total_file_descriptors": total_file_descriptors,
                    "total_threads": total_threads,
                    "total_connections": total_connections,
                    "processes_with_violations": processes_with_violations,
                    "processes_with_alerts": processes_with_alerts
                },
                system_resources=system_metrics
            )
            
        except Exception as e:
            logger.error(
                "resource_summary_logging_failed",
                error=str(e)
            )
    
    async def _shutdown_processes(self) -> None:
        """Shutdown all tracked processes."""
        logger.info(
            "shutting_down_processes",
            count=len(self._processes)
        )
        
        # Terminate all running processes
        terminate_tasks = []
        for process_id, process_record in list(self._processes.items()):
            if process_record.status in (ProcessStatus.RUNNING, ProcessStatus.STARTING):
                terminate_tasks.append(
                    self.terminate_process(process_id, force=False, timeout=5.0)
                )
        
        if terminate_tasks:
            # Wait for graceful termination
            results = await asyncio.gather(*terminate_tasks, return_exceptions=True)
            
            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "process_shutdown_failed",
                        task_index=i,
                        error=str(result)
                    )
    
    # Enhanced PID Tracking Methods (Task 12.2)
    
    async def _get_detailed_pid_info(self, pid: int) -> Optional[ProcessPIDInfo]:
        """Get detailed PID information using psutil.
        
        Args:
            pid: Process ID to inspect
            
        Returns:
            Detailed PID information or None if process not found
        """
        try:
            process = psutil.Process(pid)
            
            # Get basic process info
            info = ProcessPIDInfo(
                pid=pid,
                ppid=process.ppid(),
                creation_time=datetime.fromtimestamp(process.create_time()),
                command_line=" ".join(process.cmdline()),
                executable_path=process.exe()
            )
            
            # Add platform-specific information
            platform_info = {
                "name": process.name(),
                "status": process.status(),
                "username": process.username(),
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "num_threads": process.num_threads(),
                "cwd": process.cwd() if hasattr(process, 'cwd') else None
            }
            
            # Add file descriptors count (Unix-like systems)
            try:
                platform_info["num_fds"] = process.num_fds()
            except (AttributeError, psutil.AccessDenied):
                pass
            
            # Add connections count
            try:
                platform_info["num_connections"] = len(process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            info.platform_info = platform_info
            return info
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        except Exception as e:
            logger.warning(
                "failed_to_get_pid_info",
                pid=pid,
                error=str(e)
            )
            return None
    
    async def _validate_pid_with_metadata(self, pid: int, expected_info: Optional[ProcessPIDInfo] = None) -> bool:
        """Validate PID with metadata comparison.
        
        Args:
            pid: Process ID to validate
            expected_info: Expected process information for comparison
            
        Returns:
            True if PID is valid and matches expected info
        """
        current_info = await self._get_detailed_pid_info(pid)
        
        if not current_info:
            return False
        
        if not expected_info:
            return True  # PID exists, no specific validation required
        
        # Compare critical fields for PID reuse detection
        if current_info.creation_time != expected_info.creation_time:
            await self._log_pid_event(
                pid, "reused", 
                details={
                    "expected_creation": expected_info.creation_time.isoformat(),
                    "actual_creation": current_info.creation_time.isoformat()
                }
            )
            return False
        
        if current_info.ppid != expected_info.ppid:
            logger.warning(
                "pid_parent_changed",
                pid=pid,
                expected_ppid=expected_info.ppid,
                actual_ppid=current_info.ppid  
            )
        
        return True
    
    async def _detect_pid_reuse(self, pid: int) -> bool:
        """Detect if a PID has been reused by comparing with stored metadata.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if PID reuse is detected
        """
        # Get stored PID info from database
        cursor = await self.db.execute(
            "SELECT pid_info FROM process_registry WHERE pid = ? ORDER BY created_at DESC LIMIT 1",
            (pid,)
        )
        row = await cursor.fetchone()
        
        if not row or not row[0]:
            return False  # No stored info to compare
        
        try:
            stored_info_dict = json.loads(row[0])
            stored_info = ProcessPIDInfo(
                pid=stored_info_dict["pid"],
                ppid=stored_info_dict.get("ppid"),
                creation_time=datetime.fromisoformat(stored_info_dict["creation_time"]) if stored_info_dict.get("creation_time") else None,
                command_line=stored_info_dict.get("command_line", ""),
                executable_path=stored_info_dict.get("executable_path", ""),
                platform_info=stored_info_dict.get("platform_info", {})
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("failed_to_parse_stored_pid_info", pid=pid, error=str(e))
            return False
        
        # Compare with current PID info
        current_info = await self._get_detailed_pid_info(pid)
        if not current_info:
            return True  # PID no longer exists, likely reused
        
        # Check creation time - most reliable indicator of PID reuse
        if stored_info.creation_time and current_info.creation_time:
            if current_info.creation_time != stored_info.creation_time:
                await self._log_pid_event(
                    pid, "reused",
                    details={
                        "stored_creation": stored_info.creation_time.isoformat(),
                        "current_creation": current_info.creation_time.isoformat(),
                        "stored_command": stored_info.command_line,
                        "current_command": current_info.command_line
                    }
                )
                return True
        
        return False
    
    async def _log_pid_event(self, pid: int, event_type: str, process_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> str:
        """Log a PID-related event to the audit trail.
        
        Args:
            pid: Process ID
            event_type: Event type (created, terminated, orphaned, reused, collision)
            process_id: Associated process record ID
            details: Additional event details
            
        Returns:
            Event ID
        """
        event = PIDEvent(
            id=f"pid_event_{uuid.uuid4().hex[:12]}",
            pid=pid,
            event_type=event_type,
            process_id=process_id,
            details=details or {}
        )
        
        await self.db.execute("""
            INSERT INTO pid_audit_trail 
            (id, pid, event_type, timestamp, process_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.id,
            event.pid,
            event.event_type,
            event.timestamp.isoformat(),
            event.process_id,
            json.dumps(event.details)
        ))
        await self.db.commit()
        
        logger.info(
            "pid_event_logged",
            event_id=event.id,
            pid=pid,
            event_type=event_type,
            process_id=process_id
        )
        
        return event.id
    
    async def _resolve_pid_collision(self, pid: int, new_process_id: str) -> bool:
        """Resolve PID collision by updating existing records.
        
        Args:
            pid: Colliding PID
            new_process_id: New process record ID
            
        Returns:
            True if collision was resolved successfully
        """
        try:
            # Find existing process record with this PID
            cursor = await self.db.execute(
                "SELECT process_id, status FROM process_registry WHERE pid = ? AND status IN ('running', 'starting')",
                (pid,)
            )
            existing_records = await cursor.fetchall()
            
            if not existing_records:
                return True  # No collision to resolve
            
            # Mark existing records as terminated due to PID reuse
            for record in existing_records:
                existing_id, existing_status = record
                
                await self.db.execute("""
                    UPDATE process_registry 
                    SET status = 'terminated', 
                        updated_at = ?,
                        metadata = json_set(COALESCE(metadata, '{}'), '$.termination_reason', 'pid_reused')
                    WHERE process_id = ?
                """, (datetime.utcnow().isoformat(), existing_id))
                
                # Log the collision event
                await self._log_pid_event(
                    pid, "collision",
                    details={
                        "existing_process_id": existing_id,
                        "new_process_id": new_process_id,
                        "previous_status": existing_status
                    }
                )
                
                logger.warning(
                    "pid_collision_resolved",
                    pid=pid,
                    existing_process_id=existing_id,
                    new_process_id=new_process_id
                )
            
            await self.db.commit()
            return True
            
        except Exception as e:
            logger.error(
                "failed_to_resolve_pid_collision",
                pid=pid,
                new_process_id=new_process_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def _count_pid_events(self) -> int:
        """Count total PID audit events."""
        cursor = await self.db.execute("SELECT COUNT(*) FROM pid_audit_trail")
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    # Process Validation Methods
    
    async def validate_process_integrity(
        self,
        process_id: str,
        result: ProcessValidationResult
    ) -> None:
        """
        Validate process integrity and existence.
        
        Checks:
        - Process still exists and matches PID
        - Command line and executable haven't changed
        - Creation time matches (detects PID reuse)
        - Parent process relationship is valid
        """
        try:
            process_record = self._processes.get(process_id)
            if not process_record:
                result.add_error("integrity", f"Process record not found: {process_id}")
                return
            
            # Check if process still exists
            try:
                proc = psutil.Process(process_record.pid)
                
                # Verify PID hasn't been reused
                current_pid_info = await self._get_detailed_pid_info(process_record.pid)
                if current_pid_info and process_record.pid_info:
                    if current_pid_info.creation_time != process_record.pid_info.creation_time:
                        result.add_error("integrity", f"PID {process_record.pid} has been reused")
                        await self._log_pid_event(
                            process_record.pid,
                            "reused", 
                            process_id,
                            {"old_creation_time": process_record.pid_info.creation_time.isoformat() if process_record.pid_info.creation_time else None,
                             "new_creation_time": current_pid_info.creation_time.isoformat() if current_pid_info.creation_time else None}
                        )
                        return
                
                # Verify command line matches
                if (process_record.pid_info and process_record.pid_info.command_line and 
                    current_pid_info and current_pid_info.command_line):
                    if process_record.pid_info.command_line != current_pid_info.command_line:
                        result.add_warning("integrity", 
                                         f"Command line mismatch for PID {process_record.pid}")
                
                # Verify executable path
                if (process_record.pid_info and process_record.pid_info.executable_path and
                    current_pid_info and current_pid_info.executable_path):
                    if process_record.pid_info.executable_path != current_pid_info.executable_path:
                        result.add_warning("integrity", 
                                         f"Executable path changed for PID {process_record.pid}")
                
                # Check parent process relationship
                if current_pid_info and current_pid_info.ppid:
                    try:
                        parent_proc = psutil.Process(current_pid_info.ppid)
                        result.metrics["parent_pid"] = current_pid_info.ppid
                        result.metrics["parent_status"] = parent_proc.status()
                    except psutil.NoSuchProcess:
                        result.add_warning("integrity", f"Parent process {current_pid_info.ppid} no longer exists")
                
                result.metrics["process_status"] = proc.status()
                result.metrics["process_threads"] = proc.num_threads()
                
            except psutil.NoSuchProcess:
                result.add_error("integrity", f"Process {process_record.pid} no longer exists")
                # Mark as orphaned
                process_record.status = ProcessStatus.ORPHANED
                await self._log_pid_event(process_record.pid, "orphaned", process_id)
                
        except Exception as e:
            result.add_error("integrity", f"Integrity validation failed: {e}")
    
    async def validate_resource_constraints(
        self,
        process_id: str,
        constraints: ProcessConstraints,
        result: ProcessValidationResult
    ) -> None:
        """
        Validate process resource usage against constraints.
        
        Checks:
        - Memory usage within limits
        - CPU usage patterns
        - File descriptor usage
        - Network connections
        - Child process count
        """
        try:
            process_record = self._processes.get(process_id)
            if not process_record:
                result.add_error("resource", f"Process record not found: {process_id}")
                return
            
            try:
                proc = psutil.Process(process_record.pid)
                
                # Memory validation
                if constraints.max_memory_mb:
                    memory_mb = proc.memory_info().rss / 1024 / 1024
                    result.metrics["memory_mb"] = memory_mb
                    if memory_mb > constraints.max_memory_mb:
                        result.add_error("resource", 
                                       f"Memory usage {memory_mb:.1f}MB exceeds limit {constraints.max_memory_mb}MB")
                
                # CPU validation
                if constraints.max_cpu_percent:
                    cpu_percent = proc.cpu_percent(interval=1.0)
                    result.metrics["cpu_percent"] = cpu_percent
                    if cpu_percent > constraints.max_cpu_percent:
                        result.add_error("resource", 
                                       f"CPU usage {cpu_percent:.1f}% exceeds limit {constraints.max_cpu_percent}%")
                
                # File descriptor validation
                if constraints.max_file_descriptors and hasattr(proc, 'num_fds'):
                    try:
                        fd_count = proc.num_fds()
                        result.metrics["file_descriptors"] = fd_count
                        if fd_count > constraints.max_file_descriptors:
                            result.add_error("resource", 
                                           f"File descriptor count {fd_count} exceeds limit {constraints.max_file_descriptors}")
                    except (psutil.AccessDenied, AttributeError):
                        result.add_warning("resource", "Cannot access file descriptor count")
                
                # Network connections validation
                if constraints.max_connections:
                    try:
                        connections = proc.connections()
                        conn_count = len(connections)
                        result.metrics["connections"] = conn_count
                        if conn_count > constraints.max_connections:
                            result.add_error("resource", 
                                           f"Connection count {conn_count} exceeds limit {constraints.max_connections}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("resource", "Cannot access network connections")
                
                # Child process validation
                if constraints.max_child_processes:
                    try:
                        children = proc.children(recursive=True)
                        child_count = len(children)
                        result.metrics["child_processes"] = child_count
                        if child_count > constraints.max_child_processes:
                            result.add_error("resource", 
                                           f"Child process count {child_count} exceeds limit {constraints.max_child_processes}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("resource", "Cannot access child processes")
                
                # Uptime validation
                if constraints.max_uptime_hours:
                    try:
                        create_time = datetime.fromtimestamp(proc.create_time())
                        uptime_hours = (datetime.utcnow() - create_time).total_seconds() / 3600
                        result.metrics["uptime_hours"] = uptime_hours
                        if uptime_hours > constraints.max_uptime_hours:
                            result.add_warning("resource", 
                                             f"Process uptime {uptime_hours:.1f}h exceeds recommended limit {constraints.max_uptime_hours}h")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("resource", "Cannot access process creation time")
                
            except psutil.NoSuchProcess:
                result.add_error("resource", f"Process {process_record.pid} no longer exists")
                
        except Exception as e:
            result.add_error("resource", f"Resource validation failed: {e}")
    
    async def validate_security_policies(
        self,
        process_id: str,
        constraints: ProcessConstraints,
        result: ProcessValidationResult
    ) -> None:
        """
        Validate process security policies and permissions.
        
        Checks:
        - User/group permissions
        - Working directory restrictions
        - Executable path validation
        - Environment variable checks
        """
        try:
            process_record = self._processes.get(process_id)
            if not process_record:
                result.add_error("security", f"Process record not found: {process_id}")
                return
            
            try:
                proc = psutil.Process(process_record.pid)
                
                # User validation
                if constraints.allowed_users:
                    try:
                        username = proc.username()
                        result.metrics["username"] = username
                        if username not in constraints.allowed_users:
                            result.add_error("security", 
                                           f"Process running as unauthorized user: {username}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("security", "Cannot access process username")
                
                # Working directory validation
                if constraints.allowed_working_dirs:
                    try:
                        cwd = proc.cwd()
                        result.metrics["working_dir"] = cwd
                        allowed = any(cwd.startswith(allowed_dir) for allowed_dir in constraints.allowed_working_dirs)
                        if not allowed:
                            result.add_error("security", 
                                           f"Process running in unauthorized directory: {cwd}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("security", "Cannot access working directory")
                
                # Executable path validation
                if constraints.blocked_executables:
                    try:
                        exe_path = proc.exe()
                        result.metrics["executable"] = exe_path
                        for blocked_exe in constraints.blocked_executables:
                            if blocked_exe in exe_path or exe_path.endswith(blocked_exe):
                                result.add_error("security", 
                                               f"Process using blocked executable: {exe_path}")
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("security", "Cannot access executable path")
                
                # Environment variable validation
                try:
                    environ = proc.environ()
                    suspicious_vars = ["LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES"]
                    for var in suspicious_vars:
                        if var in environ:
                            result.add_warning("security", 
                                             f"Suspicious environment variable detected: {var}")
                    
                    result.metrics["env_var_count"] = len(environ)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    result.add_warning("security", "Cannot access environment variables")
                
                # Process capabilities (Linux only)
                if hasattr(proc, 'uids') and os.name == 'posix':
                    try:
                        uids = proc.uids()
                        if uids.effective == 0:  # Running as root
                            if not constraints.allowed_users or 'root' not in constraints.allowed_users:
                                result.add_warning("security", "Process running with root privileges")
                        result.metrics["effective_uid"] = uids.effective
                        result.metrics["real_uid"] = uids.real
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        result.add_warning("security", "Cannot access process UIDs")
                
            except psutil.NoSuchProcess:
                result.add_error("security", f"Process {process_record.pid} no longer exists")
                
        except Exception as e:
            result.add_error("security", f"Security validation failed: {e}")
    
    async def validate_process_lifecycle(
        self,
        process_id: str,
        result: ProcessValidationResult
    ) -> None:
        """
        Validate process lifecycle and state consistency.
        
        Checks:
        - Process state consistency
        - Zombie process detection
        - Parent-child relationships
        - Process tree integrity
        """
        try:
            process_record = self._processes.get(process_id)
            if not process_record:
                result.add_error("lifecycle", f"Process record not found: {process_id}")
                return
            
            try:
                proc = psutil.Process(process_record.pid)
                
                # Process status validation
                proc_status = proc.status()
                result.metrics["psutil_status"] = proc_status
                result.metrics["registry_status"] = process_record.status.value
                
                # Check for zombie processes
                if proc_status == psutil.STATUS_ZOMBIE:
                    result.add_error("lifecycle", f"Process {process_record.pid} is a zombie")
                
                # Check status consistency
                if (process_record.status == ProcessStatus.RUNNING and 
                    proc_status not in [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING, psutil.STATUS_IDLE]):
                    result.add_warning("lifecycle", 
                                     f"Status mismatch: registry={process_record.status.value}, actual={proc_status}")
                
                # Parent process validation
                try:
                    ppid = proc.ppid()
                    if ppid > 0:
                        parent_proc = psutil.Process(ppid)
                        result.metrics["parent_status"] = parent_proc.status()
                        
                        # Check if parent is init (process was orphaned)
                        if ppid == 1 and process_record.pid_info and process_record.pid_info.ppid != 1:
                            result.add_warning("lifecycle", 
                                             f"Process appears to be orphaned (parent is init)")
                except psutil.NoSuchProcess:
                    result.add_warning("lifecycle", "Parent process no longer exists")
                
                # Child process validation
                try:
                    children = proc.children()
                    child_pids = [child.pid for child in children]
                    result.metrics["child_pids"] = child_pids
                    result.metrics["child_count"] = len(child_pids)
                    
                    # Check for excessive child processes
                    if len(child_pids) > 50:  # Arbitrary threshold
                        result.add_warning("lifecycle", 
                                         f"Process has {len(child_pids)} child processes")
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    result.add_warning("lifecycle", "Cannot access child processes")
                
                # Process creation time validation
                try:
                    create_time = datetime.fromtimestamp(proc.create_time())
                    age_seconds = (datetime.utcnow() - create_time).total_seconds()
                    result.metrics["age_seconds"] = age_seconds
                    
                    # Check for very old processes that might be stuck
                    if age_seconds > 86400:  # 24 hours
                        result.add_warning("lifecycle", 
                                         f"Process is very old ({age_seconds/3600:.1f} hours)")
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    result.add_warning("lifecycle", "Cannot access process creation time")
                
            except psutil.NoSuchProcess:
                result.add_error("lifecycle", f"Process {process_record.pid} no longer exists")
                # Update status to orphaned
                process_record.status = ProcessStatus.ORPHANED
                await self._log_pid_event(process_record.pid, "orphaned", process_id)
                
        except Exception as e:
            result.add_error("lifecycle", f"Lifecycle validation failed: {e}")
    
    async def run_comprehensive_validation(
        self,
        process_id: str,
        constraints: Optional[ProcessConstraints] = None
    ) -> ProcessValidationResult:
        """
        Run comprehensive process validation.
        
        Args:
            process_id: Process to validate
            constraints: Resource and security constraints
            
        Returns:
            Validation result with all checks
        """
        process_record = self._processes.get(process_id)
        if not process_record:
            raise ValidationError("process_id", process_id, "Process not found")
        
        # Initialize validation result
        result = ProcessValidationResult(
            process_id=process_id,
            pid=process_record.pid,
            is_valid=True
        )
        
        try:
            # Run all validation categories
            await self.validate_process_integrity(process_id, result)
            
            if constraints:
                await self.validate_resource_constraints(process_id, constraints, result)
                await self.validate_security_policies(process_id, constraints, result)
            
            await self.validate_process_lifecycle(process_id, result)
            
            # Log validation event
            await self._log_pid_event(
                process_record.pid,
                "validated",
                process_id,
                {
                    "is_valid": result.is_valid,
                    "error_count": len(result.errors),
                    "warning_count": len(result.warnings)
                }
            )
            
            # Store validation result in database
            await self._save_validation_result(result)
            
            logger.info(
                "process_validation_completed",
                process_id=process_id,
                pid=process_record.pid,
                is_valid=result.is_valid,
                errors=len(result.errors),
                warnings=len(result.warnings)
            )
            
            return result
            
        except Exception as e:
            result.add_error("validation", f"Validation framework error: {e}")
            logger.error(
                "process_validation_failed",
                process_id=process_id,
                error=str(e),
                exc_info=True
            )
            return result
    
    async def _save_validation_result(self, result: ProcessValidationResult) -> None:
        """Save validation result to database."""
        try:
            await self.db.execute("""
                INSERT INTO validation_results 
                (process_id, pid, is_valid, validation_time, integrity_valid, 
                 resource_valid, security_valid, lifecycle_valid, 
                 warnings, errors, metrics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.process_id,
                result.pid,
                result.is_valid,
                result.validation_time.isoformat(),
                result.integrity_valid,
                result.resource_valid,
                result.security_valid,
                result.lifecycle_valid,
                json.dumps(result.warnings),
                json.dumps(result.errors),
                json.dumps(result.metrics)
            ))
            await self.db.commit()
        except Exception as e:
            logger.error("failed_to_save_validation_result", error=str(e))

    # Cleanup Operations
    
    async def cleanup_stale_processes(self, max_age_hours: int = 24) -> int:
        """
        Clean up processes that haven't had a heartbeat in the specified time.
        
        Args:
            max_age_hours: Maximum age in hours for last heartbeat
            
        Returns:
            Number of processes cleaned up
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
            
            # Get stale processes
            cursor = await self.db.execute("""
                SELECT process_id, pid, last_heartbeat 
                FROM process_registry 
                WHERE last_heartbeat < ? OR last_heartbeat IS NULL
            """, (cutoff_time,))
            
            stale_processes = await cursor.fetchall()
            cleanup_count = 0
            
            for process_id, pid, last_heartbeat in stale_processes:
                # Check if process is actually dead
                try:
                    if pid and psutil.pid_exists(pid):
                        # Process still exists, update heartbeat
                        await self.update_heartbeat(process_id)
                        continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
                # Remove stale process
                await self.db.execute("""
                    DELETE FROM process_registry WHERE process_id = ?
                """, (process_id,))
                
                # Log cleanup
                await self._log_pid_event(
                    pid or 0,
                    PIDEventType.CLEANUP,
                    process_id,
                    {"reason": "stale_heartbeat", "last_heartbeat": last_heartbeat}
                )
                
                cleanup_count += 1
                
                logger.info(
                    "cleaned_up_stale_process",
                    process_id=process_id,
                    pid=pid,
                    last_heartbeat=last_heartbeat
                )
            
            await self.db.commit()
            
            logger.info(
                "cleanup_stale_processes_completed",
                cleaned_up=cleanup_count,
                max_age_hours=max_age_hours
            )
            
            return cleanup_count
            
        except Exception as e:
            logger.error("cleanup_stale_processes_failed", error=str(e))
            return 0
    
    async def cleanup_orphaned_pids(self) -> int:
        """
        Clean up PID records where the actual process no longer exists.
        
        Returns:
            Number of orphaned PIDs cleaned up
        """
        try:
            # Get all registered PIDs
            cursor = await self.db.execute("""
                SELECT DISTINCT pid FROM process_registry WHERE pid IS NOT NULL
            """)
            
            registered_pids = [row[0] for row in await cursor.fetchall()]
            cleanup_count = 0
            
            for pid in registered_pids:
                try:
                    if not psutil.pid_exists(pid):
                        # PID no longer exists, remove all records
                        await self.db.execute("""
                            DELETE FROM process_registry WHERE pid = ?
                        """, (pid,))
                        
                        # Log cleanup
                        await self._log_pid_event(
                            pid,
                            PIDEventType.CLEANUP,
                            None,
                            {"reason": "orphaned_pid"}
                        )
                        
                        cleanup_count += 1
                        
                        logger.info("cleaned_up_orphaned_pid", pid=pid)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # PID definitely doesn't exist
                    await self.db.execute("""
                        DELETE FROM process_registry WHERE pid = ?
                    """, (pid,))
                    
                    cleanup_count += 1
                    logger.info("cleaned_up_orphaned_pid", pid=pid)
            
            await self.db.commit()
            
            logger.info(
                "cleanup_orphaned_pids_completed",
                cleaned_up=cleanup_count
            )
            
            return cleanup_count
            
        except Exception as e:
            logger.error("cleanup_orphaned_pids_failed", error=str(e))
            return 0
    
    async def cleanup_old_validation_results(self, retention_days: int = 30) -> int:
        """
        Clean up old validation results based on retention policy.
        
        Args:
            retention_days: Number of days to retain validation results
            
        Returns:
            Number of validation results cleaned up
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
            
            # Count old validation results
            cursor = await self.db.execute("""
                SELECT COUNT(*) FROM validation_results WHERE validation_time < ?
            """, (cutoff_time,))
            
            count_result = await cursor.fetchone()
            old_count = count_result[0] if count_result else 0
            
            if old_count > 0:
                # Delete old validation results
                await self.db.execute("""
                    DELETE FROM validation_results WHERE validation_time < ?
                """, (cutoff_time,))
                
                await self.db.commit()
                
                logger.info(
                    "cleanup_old_validation_results_completed",
                    cleaned_up=old_count,
                    retention_days=retention_days
                )
            
            return old_count
            
        except Exception as e:
            logger.error("cleanup_old_validation_results_failed", error=str(e))
            return 0
    
    async def cleanup_old_audit_trail(self, retention_days: int = 90) -> int:
        """
        Clean up old audit trail entries.
        
        Args:
            retention_days: Number of days to retain audit trail
            
        Returns:
            Number of audit trail entries cleaned up
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
            
            # Count old audit entries
            cursor = await self.db.execute("""
                SELECT COUNT(*) FROM pid_audit_trail WHERE timestamp < ?
            """, (cutoff_time,))
            
            count_result = await cursor.fetchone()
            old_count = count_result[0] if count_result else 0
            
            if old_count > 0:
                # Delete old audit entries
                await self.db.execute("""
                    DELETE FROM pid_audit_trail WHERE timestamp < ?
                """, (cutoff_time,))
                
                await self.db.commit()
                
                logger.info(
                    "cleanup_old_audit_trail_completed",
                    cleaned_up=old_count,
                    retention_days=retention_days
                )
            
            return old_count
            
        except Exception as e:
            logger.error("cleanup_old_audit_trail_failed", error=str(e))
            return 0
    
    async def perform_database_maintenance(self) -> bool:
        """
        Perform database maintenance operations.
        
        Returns:
            True if maintenance completed successfully
        """
        try:
            # Get database statistics before maintenance
            cursor = await self.db.execute("PRAGMA page_count")
            page_count_before = (await cursor.fetchone())[0]
            
            cursor = await self.db.execute("PRAGMA freelist_count")
            freelist_count_before = (await cursor.fetchone())[0]
            
            # Vacuum database to reclaim space
            await self.db.execute("VACUUM")
            
            # Analyze tables to update statistics
            await self.db.execute("ANALYZE")
            
            # Get statistics after maintenance
            cursor = await self.db.execute("PRAGMA page_count")
            page_count_after = (await cursor.fetchone())[0]
            
            cursor = await self.db.execute("PRAGMA freelist_count")
            freelist_count_after = (await cursor.fetchone())[0]
            
            pages_reclaimed = page_count_before - page_count_after
            freelist_reduced = freelist_count_before - freelist_count_after
            
            logger.info(
                "database_maintenance_completed",
                pages_reclaimed=pages_reclaimed,
                freelist_reduced=freelist_reduced,
                page_count_before=page_count_before,
                page_count_after=page_count_after
            )
            
            return True
            
        except Exception as e:
            logger.error("database_maintenance_failed", error=str(e))
            return False
    
    async def run_comprehensive_cleanup(
        self,
        stale_process_hours: int = 24,
        validation_retention_days: int = 30,
        audit_retention_days: int = 90,
        perform_db_maintenance: bool = True
    ) -> Dict[str, int]:
        """
        Run comprehensive cleanup operations.
        
        Args:
            stale_process_hours: Hours before considering process stale
            validation_retention_days: Days to retain validation results
            audit_retention_days: Days to retain audit trail
            perform_db_maintenance: Whether to perform database maintenance
            
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            "stale_processes": 0,
            "orphaned_pids": 0,
            "old_validation_results": 0,
            "old_audit_entries": 0,
            "database_maintenance": False
        }
        
        start_time = datetime.utcnow()
        
        logger.info("starting_comprehensive_cleanup")
        
        try:
            # Cleanup stale processes
            cleanup_stats["stale_processes"] = await self.cleanup_stale_processes(stale_process_hours)
            
            # Cleanup orphaned PIDs
            cleanup_stats["orphaned_pids"] = await self.cleanup_orphaned_pids()
            
            # Cleanup old validation results
            cleanup_stats["old_validation_results"] = await self.cleanup_old_validation_results(validation_retention_days)
            
            # Cleanup old audit trail
            cleanup_stats["old_audit_entries"] = await self.cleanup_old_audit_trail(audit_retention_days)
            
            # Perform database maintenance
            if perform_db_maintenance:
                cleanup_stats["database_maintenance"] = await self.perform_database_maintenance()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(
                "comprehensive_cleanup_completed",
                duration_seconds=duration,
                **cleanup_stats
            )
            
            # Emit cleanup event
            await emit(
                "process_cleanup_completed",
                EventCategory.SYSTEM,
                {
                    "cleanup_stats": cleanup_stats,
                    "duration_seconds": duration
                },
                priority=EventPriority.LOW
            )
            
            return cleanup_stats
            
        except Exception as e:
            logger.error("comprehensive_cleanup_failed", error=str(e))
            return cleanup_stats


# Export public API
__all__ = [
    'ProcessManager',
    'ProcessRecord',
    'ProcessStatus',
    'ProcessType', 
    'ProcessMetrics',
    'ProcessPIDInfo',
    'PIDEvent',
    'ProcessConstraints',
    'ProcessValidationResult',
]