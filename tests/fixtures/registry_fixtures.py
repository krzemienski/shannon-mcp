"""
Process Registry test fixtures.
"""

import psutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import random
import uuid
import json

from shannon_mcp.registry.storage import ProcessStatus


class RegistryFixtures:
    """Fixtures for Process Registry testing."""
    
    @staticmethod
    def create_mock_process_info(
        pid: Optional[int] = None,
        name: str = "claude",
        status: str = "running"
    ) -> Dict[str, Any]:
        """Create mock process information."""
        if not pid:
            pid = random.randint(1000, 99999)
        
        now = datetime.now(timezone.utc)
        create_time = now - timedelta(seconds=random.randint(10, 3600))
        
        return {
            "pid": pid,
            "name": name,
            "cmdline": [name, "--session", f"session_{uuid.uuid4().hex[:12]}"],
            "create_time": create_time.timestamp(),
            "status": status,
            "username": f"user_{random.randint(1000, 9999)}",
            "cpu_percent": round(random.uniform(0, 50), 2),
            "memory_info": {
                "rss": random.randint(50, 500) * 1024 * 1024,  # RSS in bytes
                "vms": random.randint(100, 1000) * 1024 * 1024,  # VMS in bytes
            },
            "num_threads": random.randint(1, 20),
            "open_files": random.randint(5, 50),
            "connections": random.randint(0, 10)
        }
    
    @staticmethod
    def create_process_entry(
        pid: Optional[int] = None,
        session_id: Optional[str] = None,
        status: ProcessStatus = ProcessStatus.RUNNING,
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a process registry entry."""
        if not pid:
            pid = random.randint(1000, 99999)
        
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        if not project_path:
            project_path = f"/home/user/project_{uuid.uuid4().hex[:6]}"
        
        now = datetime.now(timezone.utc)
        
        entry = {
            "pid": pid,
            "session_id": session_id,
            "project_path": project_path,
            "command": "claude",
            "args": ["--session", session_id, "--model", "claude-3-opus"],
            "env": {
                "CLAUDE_API_KEY": "test-key",
                "CLAUDE_SESSION_ID": session_id,
                "PATH": "/usr/local/bin:/usr/bin:/bin"
            },
            "status": status.value,
            "started_at": now.isoformat(),
            "last_seen": now.isoformat(),
            "host": f"host-{uuid.uuid4().hex[:6]}",
            "port": random.randint(30000, 40000) if status == ProcessStatus.RUNNING else None,
            "user": f"user_{random.randint(1000, 9999)}",
            "metadata": {
                "version": "1.0.0",
                "platform": "linux"
            }
        }
        
        # Add resource metrics for running processes
        if status == ProcessStatus.RUNNING:
            entry.update({
                "cpu_percent": round(random.uniform(0, 50), 2),
                "memory_mb": round(random.uniform(50, 500), 2),
                "disk_read_mb": round(random.uniform(0, 100), 2),
                "disk_write_mb": round(random.uniform(0, 50), 2),
                "open_files": random.randint(5, 50),
                "num_threads": random.randint(1, 20)
            })
        
        return entry
    
    @staticmethod
    def create_zombie_process() -> Dict[str, Any]:
        """Create a zombie process entry."""
        entry = RegistryFixtures.create_process_entry(
            status=ProcessStatus.ZOMBIE
        )
        
        # Zombies have minimal resource usage
        entry.update({
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "disk_read_mb": 0.0,
            "disk_write_mb": 0.0,
            "zombie_since": datetime.now(timezone.utc).isoformat()
        })
        
        return entry
    
    @staticmethod
    def create_stale_process() -> Dict[str, Any]:
        """Create a stale process entry."""
        entry = RegistryFixtures.create_process_entry(
            status=ProcessStatus.RUNNING
        )
        
        # Make it stale by setting last_seen to old timestamp
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        entry["last_seen"] = stale_time.isoformat()
        entry["stale_detected"] = datetime.now(timezone.utc).isoformat()
        
        return entry
    
    @staticmethod
    def create_registry_database(
        db_path: Path,
        process_count: int = 10
    ) -> List[Dict[str, Any]]:
        """Create a mock registry database."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        processes = []
        
        # Create various process states
        for i in range(process_count):
            if i % 5 == 0:
                # Create zombie
                process = RegistryFixtures.create_zombie_process()
            elif i % 4 == 0:
                # Create stale
                process = RegistryFixtures.create_stale_process()
            elif i % 3 == 0:
                # Create terminated
                process = RegistryFixtures.create_process_entry(
                    status=ProcessStatus.TERMINATED
                )
            else:
                # Create running
                process = RegistryFixtures.create_process_entry(
                    status=ProcessStatus.RUNNING
                )
            
            processes.append(process)
        
        # Save to file
        db_content = {
            "version": "1.0.0",
            "processes": processes,
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_processes": len(processes),
                "hosts": list(set(p["host"] for p in processes))
            }
        }
        
        db_path.write_text(json.dumps(db_content, indent=2))
        
        return processes
    
    @staticmethod
    def create_resource_alert(
        pid: int,
        alert_type: str = "cpu"
    ) -> Dict[str, Any]:
        """Create a resource alert."""
        alerts = {
            "cpu": {
                "type": "high_cpu_usage",
                "metric": "cpu_percent",
                "value": 95.5,
                "threshold": 80.0,
                "message": "CPU usage exceeds 80% threshold"
            },
            "memory": {
                "type": "high_memory_usage",
                "metric": "memory_percent",
                "value": 88.2,
                "threshold": 75.0,
                "message": "Memory usage exceeds 75% threshold"
            },
            "disk": {
                "type": "high_disk_io",
                "metric": "disk_write_mb_per_sec",
                "value": 125.0,
                "threshold": 100.0,
                "message": "Disk write rate exceeds 100 MB/s"
            },
            "files": {
                "type": "too_many_open_files",
                "metric": "open_files",
                "value": 950,
                "threshold": 900,
                "message": "Open files approaching system limit"
            }
        }
        
        alert = alerts.get(alert_type, alerts["cpu"])
        
        return {
            "pid": pid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert": alert,
            "severity": "warning" if alert["value"] < alert["threshold"] * 1.2 else "critical"
        }
    
    @staticmethod
    def create_cleanup_report(
        cleaned_pids: List[int],
        failed_pids: List[int]
    ) -> Dict[str, Any]:
        """Create a cleanup operation report."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "cleanup",
            "summary": {
                "total_processed": len(cleaned_pids) + len(failed_pids),
                "successfully_cleaned": len(cleaned_pids),
                "failed": len(failed_pids)
            },
            "cleaned_pids": cleaned_pids,
            "failed_pids": failed_pids,
            "duration_seconds": round(random.uniform(0.5, 5.0), 2)
        }
    
    @staticmethod
    def create_cross_session_message(
        from_pid: int,
        to_session: str,
        message_type: str = "notification"
    ) -> Dict[str, Any]:
        """Create a cross-session message."""
        message_types = {
            "notification": {
                "type": "notification",
                "content": "Task completed successfully",
                "priority": "info"
            },
            "command": {
                "type": "command",
                "content": "refresh_agents",
                "priority": "high"
            },
            "data": {
                "type": "data",
                "content": {"key": "value", "items": [1, 2, 3]},
                "priority": "normal"
            }
        }
        
        msg = message_types.get(message_type, message_types["notification"])
        
        return {
            "id": str(uuid.uuid4()),
            "from_pid": from_pid,
            "to_session": to_session,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": msg,
            "delivered": False,
            "ttl_seconds": 300
        }
    
    @staticmethod
    def create_mock_psutil_process(info: Dict[str, Any]):
        """Create a mock psutil.Process object."""
        class MockProcess:
            def __init__(self, data):
                self._data = data
            
            def pid(self):
                return self._data["pid"]
            
            def name(self):
                return self._data["name"]
            
            def cmdline(self):
                return self._data["cmdline"]
            
            def create_time(self):
                return self._data["create_time"]
            
            def status(self):
                return self._data["status"]
            
            def username(self):
                return self._data["username"]
            
            def cpu_percent(self, interval=None):
                return self._data["cpu_percent"]
            
            def memory_info(self):
                class MemInfo:
                    def __init__(self, data):
                        self.rss = data["rss"]
                        self.vms = data["vms"]
                return MemInfo(self._data["memory_info"])
            
            def num_threads(self):
                return self._data["num_threads"]
            
            def is_running(self):
                return self._data["status"] == "running"
        
        return MockProcess(info)