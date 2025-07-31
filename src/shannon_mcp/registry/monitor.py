"""
Resource Monitor for Process Registry.

Monitors system and process resource usage.
"""

import asyncio
import psutil
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics

from ..utils.logging import get_logger
from ..utils.errors import ShannonError
from .storage import RegistryStorage, ProcessEntry, ProcessStatus
from .tracker import ProcessTracker

logger = get_logger(__name__)


class ResourceType(str, Enum):
    """Types of resources to monitor."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    FILE_HANDLES = "file_handles"
    THREADS = "threads"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ResourceStats:
    """Resource usage statistics."""
    timestamp: datetime
    resource_type: ResourceType
    
    # Current values
    current_value: float
    current_percent: Optional[float] = None
    
    # Historical stats
    avg_1min: Optional[float] = None
    avg_5min: Optional[float] = None
    avg_15min: Optional[float] = None
    
    # Peaks
    peak_value: Optional[float] = None
    peak_time: Optional[datetime] = None
    
    # Additional metrics
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "resource_type": self.resource_type.value,
            "current_value": self.current_value,
            "current_percent": self.current_percent,
            "averages": {
                "1min": self.avg_1min,
                "5min": self.avg_5min,
                "15min": self.avg_15min
            },
            "peak": {
                "value": self.peak_value,
                "time": self.peak_time.isoformat() if self.peak_time else None
            },
            "metadata": self.metadata
        }


@dataclass
class ResourceAlert:
    """Resource usage alert."""
    timestamp: datetime
    severity: AlertSeverity
    resource_type: ResourceType
    process_id: Optional[int]
    session_id: Optional[str]
    
    message: str
    current_value: float
    threshold_value: float
    
    # Alert context
    duration_seconds: Optional[float] = None
    previous_alerts: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "resource_type": self.resource_type.value,
            "process_id": self.process_id,
            "session_id": self.session_id,
            "message": self.message,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "duration_seconds": self.duration_seconds,
            "previous_alerts": self.previous_alerts
        }


class ResourceMonitor:
    """Monitors resource usage for processes and system."""
    
    def __init__(
        self,
        storage: RegistryStorage,
        tracker: ProcessTracker
    ):
        """
        Initialize resource monitor.
        
        Args:
            storage: Registry storage instance
            tracker: Process tracker instance
        """
        self.storage = storage
        self.tracker = tracker
        
        # Monitoring configuration
        self.sample_interval_seconds = 5
        self.history_size = 180  # 15 minutes at 5s intervals
        
        # Resource thresholds
        self.thresholds = {
            ResourceType.CPU: {
                AlertSeverity.WARNING: 70.0,
                AlertSeverity.CRITICAL: 90.0,
                AlertSeverity.EMERGENCY: 95.0
            },
            ResourceType.MEMORY: {
                AlertSeverity.WARNING: 2048,  # 2GB
                AlertSeverity.CRITICAL: 4096,  # 4GB
                AlertSeverity.EMERGENCY: 8192  # 8GB
            },
            ResourceType.FILE_HANDLES: {
                AlertSeverity.WARNING: 500,
                AlertSeverity.CRITICAL: 1000,
                AlertSeverity.EMERGENCY: 2000
            },
            ResourceType.THREADS: {
                AlertSeverity.WARNING: 50,
                AlertSeverity.CRITICAL: 100,
                AlertSeverity.EMERGENCY: 200
            }
        }
        
        # Historical data
        self._system_history: Dict[ResourceType, deque] = {
            res_type: deque(maxlen=self.history_size)
            for res_type in ResourceType
        }
        self._process_history: Dict[int, Dict[ResourceType, deque]] = {}
        
        # Alert tracking
        self._active_alerts: Dict[str, ResourceAlert] = {}
        self._alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        
        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Resource monitoring already running")
            return
        
        self._stop_event.clear()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Started resource monitoring with {self.sample_interval_seconds}s interval")
    
    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        if not self._monitoring_task:
            return
        
        self._stop_event.set()
        
        try:
            await asyncio.wait_for(self._monitoring_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Monitoring task didn't stop gracefully, cancelling")
            self._monitoring_task.cancel()
        
        logger.info("Stopped resource monitoring")
    
    def add_alert_callback(
        self,
        callback: Callable[[ResourceAlert], None]
    ) -> None:
        """
        Add alert callback.
        
        Args:
            callback: Function to call on alerts
        """
        self._alert_callbacks.append(callback)
    
    async def get_system_stats(self) -> Dict[ResourceType, ResourceStats]:
        """
        Get current system resource statistics.
        
        Returns:
            Dict of resource stats by type
        """
        stats = {}
        now = datetime.now(timezone.utc)
        
        # CPU stats
        cpu_percent = psutil.cpu_percent(interval=1)
        stats[ResourceType.CPU] = ResourceStats(
            timestamp=now,
            resource_type=ResourceType.CPU,
            current_value=cpu_percent,
            current_percent=cpu_percent,
            metadata={
                "cpu_count": psutil.cpu_count(),
                "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            }
        )
        
        # Memory stats
        memory = psutil.virtual_memory()
        stats[ResourceType.MEMORY] = ResourceStats(
            timestamp=now,
            resource_type=ResourceType.MEMORY,
            current_value=memory.used / (1024 * 1024),  # MB
            current_percent=memory.percent,
            metadata={
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "swap_percent": psutil.swap_memory().percent
            }
        )
        
        # Disk I/O stats
        disk_io = psutil.disk_io_counters()
        if disk_io:
            stats[ResourceType.DISK_IO] = ResourceStats(
                timestamp=now,
                resource_type=ResourceType.DISK_IO,
                current_value=(disk_io.read_bytes + disk_io.write_bytes) / (1024 * 1024),
                metadata={
                    "read_mb": disk_io.read_bytes / (1024 * 1024),
                    "write_mb": disk_io.write_bytes / (1024 * 1024),
                    "read_count": disk_io.read_count,
                    "write_count": disk_io.write_count
                }
            )
        
        # Network I/O stats
        net_io = psutil.net_io_counters()
        if net_io:
            stats[ResourceType.NETWORK_IO] = ResourceStats(
                timestamp=now,
                resource_type=ResourceType.NETWORK_IO,
                current_value=(net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024),
                metadata={
                    "sent_mb": net_io.bytes_sent / (1024 * 1024),
                    "recv_mb": net_io.bytes_recv / (1024 * 1024),
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                }
            )
        
        # Add historical averages
        for res_type, stat in stats.items():
            self._add_historical_stats(stat, self._system_history[res_type])
        
        return stats
    
    async def get_process_stats(
        self,
        pid: int
    ) -> Optional[Dict[ResourceType, ResourceStats]]:
        """
        Get resource statistics for a process.
        
        Args:
            pid: Process ID
            
        Returns:
            Dict of resource stats by type, or None if process not found
        """
        try:
            process = psutil.Process(pid)
            stats = {}
            now = datetime.now(timezone.utc)
            
            with process.oneshot():
                # CPU stats
                cpu_percent = process.cpu_percent()
                stats[ResourceType.CPU] = ResourceStats(
                    timestamp=now,
                    resource_type=ResourceType.CPU,
                    current_value=cpu_percent,
                    current_percent=cpu_percent,
                    metadata={
                        "cpu_num": process.cpu_num() if hasattr(process, 'cpu_num') else None
                    }
                )
                
                # Memory stats
                memory = process.memory_info()
                memory_percent = process.memory_percent()
                stats[ResourceType.MEMORY] = ResourceStats(
                    timestamp=now,
                    resource_type=ResourceType.MEMORY,
                    current_value=memory.rss / (1024 * 1024),  # MB
                    current_percent=memory_percent,
                    metadata={
                        "vms_mb": memory.vms / (1024 * 1024),
                        "shared_mb": getattr(memory, 'shared', 0) / (1024 * 1024)
                    }
                )
                
                # File handles
                try:
                    open_files = len(process.open_files())
                    stats[ResourceType.FILE_HANDLES] = ResourceStats(
                        timestamp=now,
                        resource_type=ResourceType.FILE_HANDLES,
                        current_value=open_files
                    )
                except (psutil.AccessDenied, AttributeError):
                    pass
                
                # Threads
                stats[ResourceType.THREADS] = ResourceStats(
                    timestamp=now,
                    resource_type=ResourceType.THREADS,
                    current_value=process.num_threads()
                )
                
                # Disk I/O (if available)
                try:
                    io_counters = process.io_counters()
                    stats[ResourceType.DISK_IO] = ResourceStats(
                        timestamp=now,
                        resource_type=ResourceType.DISK_IO,
                        current_value=(io_counters.read_bytes + io_counters.write_bytes) / (1024 * 1024),
                        metadata={
                            "read_mb": io_counters.read_bytes / (1024 * 1024),
                            "write_mb": io_counters.write_bytes / (1024 * 1024)
                        }
                    )
                except (psutil.AccessDenied, AttributeError):
                    pass
            
            # Add historical averages
            if pid in self._process_history:
                for res_type, stat in stats.items():
                    if res_type in self._process_history[pid]:
                        self._add_historical_stats(
                            stat,
                            self._process_history[pid][res_type]
                        )
            
            return stats
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    async def get_session_stats(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get aggregated resource statistics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Aggregated statistics
        """
        processes = await self.storage.get_session_processes(session_id)
        
        total_stats = {
            "session_id": session_id,
            "process_count": len(processes),
            "total_cpu_percent": 0.0,
            "total_memory_mb": 0.0,
            "total_threads": 0,
            "total_file_handles": 0,
            "processes": []
        }
        
        for entry in processes:
            stats = await self.get_process_stats(entry.pid)
            if stats:
                # Aggregate totals
                total_stats["total_cpu_percent"] += stats[ResourceType.CPU].current_value
                total_stats["total_memory_mb"] += stats[ResourceType.MEMORY].current_value
                
                if ResourceType.THREADS in stats:
                    total_stats["total_threads"] += stats[ResourceType.THREADS].current_value
                
                if ResourceType.FILE_HANDLES in stats:
                    total_stats["total_file_handles"] += stats[ResourceType.FILE_HANDLES].current_value
                
                # Add process info
                total_stats["processes"].append({
                    "pid": entry.pid,
                    "command": entry.command,
                    "cpu_percent": stats[ResourceType.CPU].current_value,
                    "memory_mb": stats[ResourceType.MEMORY].current_value
                })
        
        return total_stats
    
    async def check_alerts(self) -> List[ResourceAlert]:
        """
        Check for resource alerts.
        
        Returns:
            List of new alerts
        """
        new_alerts = []
        
        # Check system alerts
        system_stats = await self.get_system_stats()
        for res_type, stats in system_stats.items():
            if res_type in self.thresholds:
                alert = self._check_threshold(
                    stats, None, None, self.thresholds[res_type]
                )
                if alert:
                    new_alerts.append(alert)
        
        # Check process alerts
        processes = await self.storage.get_all_processes(
            status=ProcessStatus.RUNNING,
            host=self.tracker.hostname
        )
        
        for entry in processes:
            process_stats = await self.get_process_stats(entry.pid)
            if process_stats:
                for res_type, stats in process_stats.items():
                    if res_type in self.thresholds:
                        alert = self._check_threshold(
                            stats, entry.pid, entry.session_id,
                            self.thresholds[res_type]
                        )
                        if alert:
                            new_alerts.append(alert)
        
        # Fire callbacks for new alerts
        for alert in new_alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
        
        return new_alerts
    
    def _check_threshold(
        self,
        stats: ResourceStats,
        pid: Optional[int],
        session_id: Optional[str],
        thresholds: Dict[AlertSeverity, float]
    ) -> Optional[ResourceAlert]:
        """Check if stats exceed thresholds."""
        # Find highest severity threshold exceeded
        triggered_severity = None
        threshold_value = None
        
        for severity in [
            AlertSeverity.EMERGENCY,
            AlertSeverity.CRITICAL,
            AlertSeverity.WARNING
        ]:
            if severity in thresholds:
                if stats.current_value >= thresholds[severity]:
                    triggered_severity = severity
                    threshold_value = thresholds[severity]
                    break
        
        if not triggered_severity:
            # Clear any existing alert
            alert_key = f"{stats.resource_type}_{pid or 'system'}"
            if alert_key in self._active_alerts:
                del self._active_alerts[alert_key]
            return None
        
        # Check if this is a new or escalated alert
        alert_key = f"{stats.resource_type}_{pid or 'system'}"
        existing_alert = self._active_alerts.get(alert_key)
        
        if existing_alert and existing_alert.severity == triggered_severity:
            # Same severity, update duration
            existing_alert.duration_seconds = (
                datetime.now(timezone.utc) - existing_alert.timestamp
            ).total_seconds()
            return None  # Not a new alert
        
        # Create new alert
        if pid:
            message = (
                f"Process {pid} {stats.resource_type.value} usage "
                f"({stats.current_value:.1f}) exceeds {triggered_severity.value} "
                f"threshold ({threshold_value})"
            )
        else:
            message = (
                f"System {stats.resource_type.value} usage "
                f"({stats.current_value:.1f}) exceeds {triggered_severity.value} "
                f"threshold ({threshold_value})"
            )
        
        alert = ResourceAlert(
            timestamp=datetime.now(timezone.utc),
            severity=triggered_severity,
            resource_type=stats.resource_type,
            process_id=pid,
            session_id=session_id,
            message=message,
            current_value=stats.current_value,
            threshold_value=threshold_value,
            previous_alerts=existing_alert.previous_alerts + 1 if existing_alert else 0
        )
        
        self._active_alerts[alert_key] = alert
        return alert
    
    def _add_historical_stats(
        self,
        stats: ResourceStats,
        history: deque
    ) -> None:
        """Add historical statistics to stats object."""
        if not history:
            return
        
        now = datetime.now(timezone.utc)
        
        # Filter samples by time window
        samples_1min = []
        samples_5min = []
        samples_15min = []
        
        for sample in history:
            age = (now - sample['timestamp']).total_seconds()
            
            if age <= 60:
                samples_1min.append(sample['value'])
            if age <= 300:
                samples_5min.append(sample['value'])
            if age <= 900:
                samples_15min.append(sample['value'])
        
        # Calculate averages
        if samples_1min:
            stats.avg_1min = statistics.mean(samples_1min)
        if samples_5min:
            stats.avg_5min = statistics.mean(samples_5min)
        if samples_15min:
            stats.avg_15min = statistics.mean(samples_15min)
        
        # Find peak
        if history:
            peak_sample = max(history, key=lambda x: x['value'])
            stats.peak_value = peak_sample['value']
            stats.peak_time = peak_sample['timestamp']
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                # Collect system stats
                system_stats = await self.get_system_stats()
                
                # Store history
                for res_type, stats in system_stats.items():
                    self._system_history[res_type].append({
                        'timestamp': stats.timestamp,
                        'value': stats.current_value
                    })
                
                # Collect process stats
                processes = await self.storage.get_all_processes(
                    status=ProcessStatus.RUNNING,
                    host=self.tracker.hostname
                )
                
                for entry in processes:
                    process_stats = await self.get_process_stats(entry.pid)
                    if process_stats:
                        # Initialize history if needed
                        if entry.pid not in self._process_history:
                            self._process_history[entry.pid] = {
                                res_type: deque(maxlen=self.history_size)
                                for res_type in ResourceType
                            }
                        
                        # Store history
                        for res_type, stats in process_stats.items():
                            self._process_history[entry.pid][res_type].append({
                                'timestamp': stats.timestamp,
                                'value': stats.current_value
                            })
                        
                        # Update storage with latest resource usage
                        await self.storage.update_process_resources(
                            pid=entry.pid,
                            host=entry.host,
                            cpu_percent=process_stats[ResourceType.CPU].current_value,
                            memory_mb=process_stats[ResourceType.MEMORY].current_value,
                            disk_read_mb=process_stats.get(
                                ResourceType.DISK_IO, ResourceStats(
                                    datetime.now(timezone.utc), ResourceType.DISK_IO, 0
                                )
                            ).metadata.get('read_mb'),
                            disk_write_mb=process_stats.get(
                                ResourceType.DISK_IO, ResourceStats(
                                    datetime.now(timezone.utc), ResourceType.DISK_IO, 0
                                )
                            ).metadata.get('write_mb')
                        )
                
                # Clean up old process history
                current_pids = {p.pid for p in processes}
                dead_pids = set(self._process_history.keys()) - current_pids
                for pid in dead_pids:
                    del self._process_history[pid]
                
                # Check for alerts
                await self.check_alerts()
                
                # Wait for next iteration
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.sample_interval_seconds
                )
                
            except asyncio.TimeoutError:
                # Expected timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)