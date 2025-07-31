"""
Process Tracker for Process Registry.

Tracks and manages process lifecycle across the system.
"""

import os
import asyncio
import psutil
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
import json

from ..utils.logging import get_logger
from ..utils.errors import ShannonError
from .storage import RegistryStorage, ProcessEntry, ProcessStatus

logger = get_logger(__name__)


@dataclass
class ProcessInfo:
    """Detailed process information."""
    pid: int
    name: str
    cmdline: List[str]
    create_time: datetime
    status: str
    username: str
    
    # Resource usage
    cpu_percent: float
    memory_info: Dict[str, int]
    io_counters: Optional[Dict[str, int]]
    num_threads: int
    
    # Network connections
    connections: List[Dict[str, Any]]
    
    # Open files
    open_files: List[str]
    
    # Environment
    environ: Dict[str, str]
    cwd: Optional[str]
    
    @classmethod
    def from_psutil(cls, process: psutil.Process) -> "ProcessInfo":
        """Create from psutil Process object."""
        try:
            # Get process info with timeout
            with process.oneshot():
                info = process.as_dict(attrs=[
                    'pid', 'name', 'cmdline', 'create_time', 'status',
                    'username', 'cpu_percent', 'memory_info', 'io_counters',
                    'num_threads', 'connections', 'open_files', 'environ', 'cwd'
                ])
            
            # Convert create_time to datetime
            create_time = datetime.fromtimestamp(
                info['create_time'],
                tz=timezone.utc
            )
            
            # Convert memory_info to dict
            memory_dict = {}
            if info.get('memory_info'):
                mem = info['memory_info']
                memory_dict = {
                    'rss': mem.rss,
                    'vms': mem.vms,
                    'shared': getattr(mem, 'shared', 0),
                    'text': getattr(mem, 'text', 0),
                    'data': getattr(mem, 'data', 0)
                }
            
            # Convert io_counters to dict
            io_dict = None
            if info.get('io_counters'):
                io = info['io_counters']
                io_dict = {
                    'read_count': io.read_count,
                    'write_count': io.write_count,
                    'read_bytes': io.read_bytes,
                    'write_bytes': io.write_bytes
                }
            
            # Convert connections to list of dicts
            connections = []
            for conn in info.get('connections', []):
                connections.append({
                    'fd': conn.fd,
                    'family': conn.family,
                    'type': conn.type,
                    'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                    'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                    'status': conn.status
                })
            
            return cls(
                pid=info['pid'],
                name=info['name'],
                cmdline=info.get('cmdline', []),
                create_time=create_time,
                status=info['status'],
                username=info.get('username', ''),
                cpu_percent=info.get('cpu_percent', 0.0),
                memory_info=memory_dict,
                io_counters=io_dict,
                num_threads=info.get('num_threads', 1),
                connections=connections,
                open_files=info.get('open_files', []),
                environ=info.get('environ', {}),
                cwd=info.get('cwd')
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            raise ShannonError(f"Failed to get process info: {e}")


class ProcessTracker:
    """Tracks system processes and Claude sessions."""
    
    def __init__(self, storage: RegistryStorage):
        """
        Initialize process tracker.
        
        Args:
            storage: Registry storage instance
        """
        self.storage = storage
        self.hostname = os.uname().nodename
        
        # Track known PIDs
        self._tracked_pids: Set[int] = set()
        self._tracking_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start_tracking(self, interval_seconds: int = 30) -> None:
        """
        Start background process tracking.
        
        Args:
            interval_seconds: Tracking interval
        """
        if self._tracking_task and not self._tracking_task.done():
            logger.warning("Process tracking already running")
            return
        
        self._stop_event.clear()
        self._tracking_task = asyncio.create_task(
            self._tracking_loop(interval_seconds)
        )
        logger.info(f"Started process tracking with {interval_seconds}s interval")
    
    async def stop_tracking(self) -> None:
        """Stop background process tracking."""
        if not self._tracking_task:
            return
        
        self._stop_event.set()
        
        try:
            await asyncio.wait_for(self._tracking_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Tracking task didn't stop gracefully, cancelling")
            self._tracking_task.cancel()
        
        logger.info("Stopped process tracking")
    
    async def track_process(
        self,
        pid: int,
        session_id: str,
        project_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessEntry:
        """
        Start tracking a specific process.
        
        Args:
            pid: Process ID to track
            session_id: Associated session ID
            project_path: Optional project path
            metadata: Optional metadata
            
        Returns:
            Process entry
        """
        try:
            # Get process info
            process = psutil.Process(pid)
            info = ProcessInfo.from_psutil(process)
            
            # Create process entry
            entry = ProcessEntry(
                pid=pid,
                session_id=session_id,
                project_path=project_path,
                command=info.name,
                args=info.cmdline[1:] if len(info.cmdline) > 1 else [],
                env=info.environ,
                status=self._map_status(info.status),
                started_at=info.create_time,
                last_seen=datetime.now(timezone.utc),
                host=self.hostname,
                port=self._extract_port(info.connections),
                user=info.username,
                metadata=metadata or {},
                cpu_percent=info.cpu_percent,
                memory_mb=info.memory_info.get('rss', 0) / (1024 * 1024)
            )
            
            # Register in storage
            await self.storage.register_process(entry)
            
            # Add to tracked PIDs
            self._tracked_pids.add(pid)
            
            logger.info(f"Started tracking process {pid} for session {session_id}")
            return entry
            
        except Exception as e:
            raise ShannonError(f"Failed to track process {pid}: {e}")
    
    async def untrack_process(self, pid: int) -> None:
        """
        Stop tracking a process.
        
        Args:
            pid: Process ID
        """
        if pid in self._tracked_pids:
            self._tracked_pids.remove(pid)
            
        await self.storage.remove_process(pid, self.hostname)
        logger.info(f"Stopped tracking process {pid}")
    
    async def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """
        Get detailed process information.
        
        Args:
            pid: Process ID
            
        Returns:
            Process info if found
        """
        try:
            process = psutil.Process(pid)
            return ProcessInfo.from_psutil(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    async def find_claude_processes(self) -> List[ProcessInfo]:
        """
        Find all Claude Code processes on the system.
        
        Returns:
            List of Claude process info
        """
        claude_processes = []
        
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a Claude process
                if self._is_claude_process(process):
                    info = ProcessInfo.from_psutil(process)
                    claude_processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return claude_processes
    
    async def validate_tracked_processes(self) -> Dict[str, List[int]]:
        """
        Validate all tracked processes.
        
        Returns:
            Dict with 'alive' and 'dead' process lists
        """
        alive = []
        dead = []
        
        # Get all processes from storage
        processes = await self.storage.get_all_processes(host=self.hostname)
        
        for entry in processes:
            if psutil.pid_exists(entry.pid):
                # Check if it's still the same process
                try:
                    process = psutil.Process(entry.pid)
                    create_time = datetime.fromtimestamp(
                        process.create_time(),
                        tz=timezone.utc
                    )
                    
                    # Compare creation times to ensure it's the same process
                    if abs((create_time - entry.started_at).total_seconds()) < 1:
                        alive.append(entry.pid)
                    else:
                        # Different process with same PID
                        dead.append(entry.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    dead.append(entry.pid)
            else:
                dead.append(entry.pid)
        
        # Update status for dead processes
        for pid in dead:
            await self.storage.update_process_status(
                pid, self.hostname, ProcessStatus.STOPPED
            )
        
        return {'alive': alive, 'dead': dead}
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system-wide process statistics.
        
        Returns:
            System statistics
        """
        # CPU stats
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory stats
        memory = psutil.virtual_memory()
        
        # Disk stats
        disk = psutil.disk_usage('/')
        
        # Process counts
        total_processes = len(psutil.pids())
        
        # Claude processes
        claude_processes = await self.find_claude_processes()
        
        # Tracked processes
        tracked = await self.storage.get_all_processes(host=self.hostname)
        active_tracked = [p for p in tracked if p.status == ProcessStatus.RUNNING]
        
        return {
            'system': {
                'hostname': self.hostname,
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
                'total_processes': total_processes
            },
            'claude': {
                'total_instances': len(claude_processes),
                'instances': [
                    {
                        'pid': p.pid,
                        'name': p.name,
                        'cpu_percent': p.cpu_percent,
                        'memory_mb': p.memory_info.get('rss', 0) / (1024 * 1024)
                    }
                    for p in claude_processes
                ]
            },
            'tracked': {
                'total': len(tracked),
                'active': len(active_tracked),
                'by_status': {
                    status.value: len([p for p in tracked if p.status == status])
                    for status in ProcessStatus
                }
            }
        }
    
    def _is_claude_process(self, process: psutil.Process) -> bool:
        """Check if a process is Claude Code."""
        try:
            name = process.info.get('name', '').lower()
            cmdline = process.info.get('cmdline', [])
            
            # Check process name
            if 'claude' in name:
                return True
            
            # Check command line
            if cmdline:
                cmd_str = ' '.join(cmdline).lower()
                if 'claude' in cmd_str or 'claude-code' in cmd_str:
                    return True
            
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _map_status(self, psutil_status: str) -> ProcessStatus:
        """Map psutil status to ProcessStatus."""
        mapping = {
            psutil.STATUS_RUNNING: ProcessStatus.RUNNING,
            psutil.STATUS_SLEEPING: ProcessStatus.IDLE,
            psutil.STATUS_DISK_SLEEP: ProcessStatus.BUSY,
            psutil.STATUS_STOPPED: ProcessStatus.STOPPED,
            psutil.STATUS_ZOMBIE: ProcessStatus.ZOMBIE,
            psutil.STATUS_DEAD: ProcessStatus.STOPPED,
        }
        
        return mapping.get(psutil_status, ProcessStatus.RUNNING)
    
    def _extract_port(self, connections: List[Dict[str, Any]]) -> Optional[int]:
        """Extract listening port from connections."""
        for conn in connections:
            if conn.get('status') == 'LISTEN' and conn.get('laddr'):
                # Parse port from address
                laddr = conn['laddr']
                if isinstance(laddr, str) and ':' in laddr:
                    try:
                        return int(laddr.split(':')[-1])
                    except ValueError:
                        pass
        return None
    
    async def _tracking_loop(self, interval: int) -> None:
        """Background tracking loop."""
        while not self._stop_event.is_set():
            try:
                # Update tracked processes
                await self._update_tracked_processes()
                
                # Validate processes
                validation = await self.validate_tracked_processes()
                if validation['dead']:
                    logger.info(f"Found {len(validation['dead'])} dead processes")
                
                # Clean up stale entries
                stale_count = await self.storage.cleanup_stale_processes(
                    stale_threshold_seconds=interval * 10  # 10x interval
                )
                
                # Wait for next iteration
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval
                )
                
            except asyncio.TimeoutError:
                # Expected timeout - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _update_tracked_processes(self) -> None:
        """Update resource usage for tracked processes."""
        for pid in list(self._tracked_pids):
            try:
                process = psutil.Process(pid)
                
                # Get resource usage
                with process.oneshot():
                    cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    
                    # Try to get I/O counters (may not be available)
                    io_counters = None
                    try:
                        io_counters = process.io_counters()
                    except (psutil.AccessDenied, AttributeError):
                        pass
                
                # Calculate disk I/O in MB
                disk_read_mb = None
                disk_write_mb = None
                if io_counters:
                    disk_read_mb = io_counters.read_bytes / (1024 * 1024)
                    disk_write_mb = io_counters.write_bytes / (1024 * 1024)
                
                # Update in storage
                await self.storage.update_process_resources(
                    pid=pid,
                    host=self.hostname,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_info.rss / (1024 * 1024),
                    disk_read_mb=disk_read_mb,
                    disk_write_mb=disk_write_mb
                )
                
                # Update status based on CPU usage
                if cpu_percent > 50:
                    status = ProcessStatus.BUSY
                elif cpu_percent > 0:
                    status = ProcessStatus.RUNNING
                else:
                    status = ProcessStatus.IDLE
                
                await self.storage.update_process_status(
                    pid, self.hostname, status
                )
                
            except psutil.NoSuchProcess:
                # Process no longer exists
                self._tracked_pids.remove(pid)
                await self.storage.update_process_status(
                    pid, self.hostname, ProcessStatus.STOPPED
                )
            except Exception as e:
                logger.warning(f"Failed to update process {pid}: {e}")