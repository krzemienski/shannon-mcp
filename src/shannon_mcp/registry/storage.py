"""
Registry Storage for Process Registry.

Provides persistent storage for process information using SQLite.
"""

import asyncio
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os

from ..utils.logging import get_logger
from ..utils.errors import ShannonError

logger = get_logger(__name__)


class ProcessStatus(str, Enum):
    """Status of a registered process."""
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    ZOMBIE = "zombie"


@dataclass
class ProcessEntry:
    """A registered process entry."""
    pid: int
    session_id: str
    project_path: Optional[str]
    command: str
    args: List[str]
    env: Dict[str, str]
    status: ProcessStatus
    started_at: datetime
    last_seen: datetime
    host: str
    port: Optional[int]
    user: Optional[str]
    metadata: Dict[str, Any]
    
    # Resource usage
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    disk_read_mb: Optional[float] = None
    disk_write_mb: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "pid": self.pid,
            "session_id": self.session_id,
            "project_path": self.project_path,
            "command": self.command,
            "args": json.dumps(self.args),
            "env": json.dumps(self.env),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "metadata": json.dumps(self.metadata),
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "disk_read_mb": self.disk_read_mb,
            "disk_write_mb": self.disk_write_mb
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessEntry":
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            session_id=data["session_id"],
            project_path=data.get("project_path"),
            command=data["command"],
            args=json.loads(data["args"]) if isinstance(data["args"], str) else data["args"],
            env=json.loads(data["env"]) if isinstance(data["env"], str) else data["env"],
            status=ProcessStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            host=data["host"],
            port=data.get("port"),
            user=data.get("user"),
            metadata=json.loads(data["metadata"]) if isinstance(data["metadata"], str) else data["metadata"],
            cpu_percent=data.get("cpu_percent"),
            memory_mb=data.get("memory_mb"),
            disk_read_mb=data.get("disk_read_mb"),
            disk_write_mb=data.get("disk_write_mb")
        )


class RegistryStorage:
    """Storage backend for the process registry."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize registry storage.
        
        Args:
            db_path: Path to SQLite database (defaults to ~/.claude/registry.db)
        """
        if db_path is None:
            db_path = Path.home() / ".claude" / "registry.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize database and create tables."""
        async with self._lock:
            self._db = await aiosqlite.connect(
                self.db_path,
                timeout=30.0
            )
            
            # Enable WAL mode for concurrent access
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA synchronous=NORMAL")
            
            # Create processes table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS processes (
                    pid INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    project_path TEXT,
                    command TEXT NOT NULL,
                    args TEXT NOT NULL,
                    env TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER,
                    user TEXT,
                    metadata TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_mb REAL,
                    disk_read_mb REAL,
                    disk_write_mb REAL,
                    PRIMARY KEY (pid, host),
                    CHECK (status IN ('starting', 'running', 'idle', 'busy', 
                                     'stopping', 'stopped', 'crashed', 'zombie'))
                )
            """)
            
            # Create indices
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processes_session 
                ON processes(session_id)
            """)
            
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processes_status 
                ON processes(status)
            """)
            
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processes_project 
                ON processes(project_path)
            """)
            
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processes_last_seen 
                ON processes(last_seen)
            """)
            
            # Create history table for tracking changes
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS process_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pid INTEGER NOT NULL,
                    host TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    details TEXT,
                    CHECK (event_type IN ('registered', 'status_changed', 
                                         'updated', 'removed'))
                )
            """)
            
            # Create cross-session communication table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_session TEXT NOT NULL,
                    to_session TEXT,
                    message_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    expires_at TEXT
                )
            """)
            
            await self._db.commit()
            
        logger.info(f"Initialized process registry database at {self.db_path}")
    
    async def register_process(self, entry: ProcessEntry) -> None:
        """
        Register a new process.
        
        Args:
            entry: Process entry to register
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            # Check if process already exists
            cursor = await self._db.execute(
                "SELECT pid FROM processes WHERE pid = ? AND host = ?",
                (entry.pid, entry.host)
            )
            existing = await cursor.fetchone()
            
            if existing:
                # Update existing entry
                await self._update_process(entry)
            else:
                # Insert new entry
                data = entry.to_dict()
                
                await self._db.execute("""
                    INSERT INTO processes (
                        pid, session_id, project_path, command, args, env,
                        status, started_at, last_seen, host, port, user,
                        metadata, cpu_percent, memory_mb, disk_read_mb, disk_write_mb
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["pid"], data["session_id"], data["project_path"],
                    data["command"], data["args"], data["env"], data["status"],
                    data["started_at"], data["last_seen"], data["host"],
                    data["port"], data["user"], data["metadata"],
                    data["cpu_percent"], data["memory_mb"],
                    data["disk_read_mb"], data["disk_write_mb"]
                ))
                
                # Record in history
                await self._record_history(
                    entry.pid, entry.host, entry.session_id,
                    "registered", None, entry.status.value,
                    f"Process registered: {entry.command}"
                )
                
            await self._db.commit()
            
            logger.debug(f"Registered process {entry.pid} on {entry.host}")
    
    async def get_process(self, pid: int, host: Optional[str] = None) -> Optional[ProcessEntry]:
        """
        Get a process by PID.
        
        Args:
            pid: Process ID
            host: Optional host filter
            
        Returns:
            Process entry if found
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            if host:
                cursor = await self._db.execute(
                    "SELECT * FROM processes WHERE pid = ? AND host = ?",
                    (pid, host)
                )
            else:
                # Get from current host
                cursor = await self._db.execute(
                    "SELECT * FROM processes WHERE pid = ? AND host = ?",
                    (pid, os.uname().nodename)
                )
            
            row = await cursor.fetchone()
            
            if row:
                # Convert row to dict
                columns = [desc[0] for desc in cursor.description]
                data = dict(zip(columns, row))
                return ProcessEntry.from_dict(data)
            
            return None
    
    async def get_session_processes(
        self,
        session_id: str,
        status: Optional[ProcessStatus] = None
    ) -> List[ProcessEntry]:
        """
        Get all processes for a session.
        
        Args:
            session_id: Session ID
            status: Optional status filter
            
        Returns:
            List of process entries
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            if status:
                cursor = await self._db.execute(
                    "SELECT * FROM processes WHERE session_id = ? AND status = ?",
                    (session_id, status.value)
                )
            else:
                cursor = await self._db.execute(
                    "SELECT * FROM processes WHERE session_id = ?",
                    (session_id,)
                )
            
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            processes = []
            for row in rows:
                data = dict(zip(columns, row))
                processes.append(ProcessEntry.from_dict(data))
            
            return processes
    
    async def get_all_processes(
        self,
        status: Optional[ProcessStatus] = None,
        host: Optional[str] = None
    ) -> List[ProcessEntry]:
        """
        Get all registered processes.
        
        Args:
            status: Optional status filter
            host: Optional host filter
            
        Returns:
            List of process entries
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            query = "SELECT * FROM processes WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            if host:
                query += " AND host = ?"
                params.append(host)
            
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            processes = []
            for row in rows:
                data = dict(zip(columns, row))
                processes.append(ProcessEntry.from_dict(data))
            
            return processes
    
    async def update_process_status(
        self,
        pid: int,
        host: str,
        status: ProcessStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update process status.
        
        Args:
            pid: Process ID
            host: Process host
            status: New status
            metadata: Optional metadata update
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            # Get current status
            cursor = await self._db.execute(
                "SELECT status, session_id FROM processes WHERE pid = ? AND host = ?",
                (pid, host)
            )
            row = await cursor.fetchone()
            
            if not row:
                logger.warning(f"Process {pid} on {host} not found")
                return
            
            old_status, session_id = row
            
            # Update status and last_seen
            if metadata:
                await self._db.execute("""
                    UPDATE processes 
                    SET status = ?, last_seen = ?, metadata = ?
                    WHERE pid = ? AND host = ?
                """, (
                    status.value,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(metadata),
                    pid,
                    host
                ))
            else:
                await self._db.execute("""
                    UPDATE processes 
                    SET status = ?, last_seen = ?
                    WHERE pid = ? AND host = ?
                """, (
                    status.value,
                    datetime.now(timezone.utc).isoformat(),
                    pid,
                    host
                ))
            
            # Record in history
            if old_status != status.value:
                await self._record_history(
                    pid, host, session_id,
                    "status_changed", old_status, status.value,
                    f"Status changed from {old_status} to {status.value}"
                )
            
            await self._db.commit()
            
            logger.debug(f"Updated process {pid} on {host} to status {status}")
    
    async def update_process_resources(
        self,
        pid: int,
        host: str,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        disk_read_mb: Optional[float] = None,
        disk_write_mb: Optional[float] = None
    ) -> None:
        """
        Update process resource usage.
        
        Args:
            pid: Process ID
            host: Process host
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in MB
            disk_read_mb: Disk read in MB
            disk_write_mb: Disk write in MB
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            # Build update query
            updates = ["last_seen = ?"]
            params = [datetime.now(timezone.utc).isoformat()]
            
            if cpu_percent is not None:
                updates.append("cpu_percent = ?")
                params.append(cpu_percent)
            
            if memory_mb is not None:
                updates.append("memory_mb = ?")
                params.append(memory_mb)
            
            if disk_read_mb is not None:
                updates.append("disk_read_mb = ?")
                params.append(disk_read_mb)
            
            if disk_write_mb is not None:
                updates.append("disk_write_mb = ?")
                params.append(disk_write_mb)
            
            params.extend([pid, host])
            
            await self._db.execute(f"""
                UPDATE processes 
                SET {', '.join(updates)}
                WHERE pid = ? AND host = ?
            """, params)
            
            await self._db.commit()
    
    async def remove_process(self, pid: int, host: str) -> None:
        """
        Remove a process from the registry.
        
        Args:
            pid: Process ID
            host: Process host
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            # Get process info for history
            cursor = await self._db.execute(
                "SELECT session_id, status FROM processes WHERE pid = ? AND host = ?",
                (pid, host)
            )
            row = await cursor.fetchone()
            
            if row:
                session_id, status = row
                
                # Delete process
                await self._db.execute(
                    "DELETE FROM processes WHERE pid = ? AND host = ?",
                    (pid, host)
                )
                
                # Record in history
                await self._record_history(
                    pid, host, session_id,
                    "removed", status, None,
                    "Process removed from registry"
                )
                
                await self._db.commit()
                
                logger.debug(f"Removed process {pid} on {host}")
    
    async def cleanup_stale_processes(self, stale_threshold_seconds: int = 300) -> int:
        """
        Remove processes that haven't been seen recently.
        
        Args:
            stale_threshold_seconds: Seconds before considering process stale
            
        Returns:
            Number of processes removed
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            threshold = datetime.now(timezone.utc).timestamp() - stale_threshold_seconds
            threshold_time = datetime.fromtimestamp(threshold, tz=timezone.utc).isoformat()
            
            # Find stale processes
            cursor = await self._db.execute(
                "SELECT pid, host, session_id, status FROM processes WHERE last_seen < ?",
                (threshold_time,)
            )
            stale_processes = await cursor.fetchall()
            
            # Remove them
            for pid, host, session_id, status in stale_processes:
                await self._record_history(
                    pid, host, session_id,
                    "removed", status, None,
                    f"Stale process (not seen for {stale_threshold_seconds}s)"
                )
            
            await self._db.execute(
                "DELETE FROM processes WHERE last_seen < ?",
                (threshold_time,)
            )
            
            await self._db.commit()
            
            count = len(stale_processes)
            if count > 0:
                logger.info(f"Cleaned up {count} stale processes")
            
            return count
    
    async def send_message(
        self,
        from_session: str,
        to_session: Optional[str],
        message_type: str,
        payload: Dict[str, Any],
        ttl_seconds: int = 3600
    ) -> int:
        """
        Send a message between sessions.
        
        Args:
            from_session: Sender session ID
            to_session: Recipient session ID (None for broadcast)
            message_type: Type of message
            payload: Message payload
            ttl_seconds: Time to live in seconds
            
        Returns:
            Message ID
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            now = datetime.now(timezone.utc)
            expires_at = now.timestamp() + ttl_seconds
            
            cursor = await self._db.execute("""
                INSERT INTO messages (
                    from_session, to_session, message_type, payload,
                    created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                from_session,
                to_session,
                message_type,
                json.dumps(payload),
                now.isoformat(),
                datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
            ))
            
            await self._db.commit()
            
            return cursor.lastrowid
    
    async def get_messages(
        self,
        session_id: str,
        unread_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a session.
        
        Args:
            session_id: Session ID
            unread_only: Only return unread messages
            
        Returns:
            List of messages
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            now = datetime.now(timezone.utc).isoformat()
            
            # Get messages for this session or broadcast messages
            if unread_only:
                cursor = await self._db.execute("""
                    SELECT * FROM messages 
                    WHERE (to_session = ? OR to_session IS NULL)
                    AND read_at IS NULL
                    AND expires_at > ?
                    ORDER BY created_at
                """, (session_id, now))
            else:
                cursor = await self._db.execute("""
                    SELECT * FROM messages 
                    WHERE (to_session = ? OR to_session IS NULL)
                    AND expires_at > ?
                    ORDER BY created_at
                """, (session_id, now))
            
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            messages = []
            message_ids = []
            
            for row in rows:
                data = dict(zip(columns, row))
                data["payload"] = json.loads(data["payload"])
                messages.append(data)
                message_ids.append(data["id"])
            
            # Mark messages as read
            if unread_only and message_ids:
                placeholders = ','.join('?' * len(message_ids))
                await self._db.execute(f"""
                    UPDATE messages 
                    SET read_at = ?
                    WHERE id IN ({placeholders})
                """, [now] + message_ids)
                
                await self._db.commit()
            
            return messages
    
    async def cleanup_expired_messages(self) -> int:
        """
        Clean up expired messages.
        
        Returns:
            Number of messages removed
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            now = datetime.now(timezone.utc).isoformat()
            
            cursor = await self._db.execute(
                "DELETE FROM messages WHERE expires_at < ?",
                (now,)
            )
            
            await self._db.commit()
            
            return cursor.rowcount
    
    async def get_process_history(
        self,
        pid: Optional[int] = None,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get process history.
        
        Args:
            pid: Optional PID filter
            session_id: Optional session filter
            limit: Maximum entries to return
            
        Returns:
            List of history entries
        """
        async with self._lock:
            if not self._db:
                raise ShannonError("Registry storage not initialized")
            
            query = "SELECT * FROM process_history WHERE 1=1"
            params = []
            
            if pid:
                query += " AND pid = ?"
                params.append(pid)
            
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            
            query += " ORDER BY event_time DESC LIMIT ?"
            params.append(limit)
            
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            history = []
            for row in rows:
                data = dict(zip(columns, row))
                if data.get("details"):
                    try:
                        data["details"] = json.loads(data["details"])
                    except:
                        pass
                history.append(data)
            
            return history
    
    async def _update_process(self, entry: ProcessEntry) -> None:
        """Update an existing process entry."""
        data = entry.to_dict()
        
        await self._db.execute("""
            UPDATE processes SET
                session_id = ?, project_path = ?, command = ?, args = ?,
                env = ?, status = ?, last_seen = ?, port = ?, user = ?,
                metadata = ?, cpu_percent = ?, memory_mb = ?,
                disk_read_mb = ?, disk_write_mb = ?
            WHERE pid = ? AND host = ?
        """, (
            data["session_id"], data["project_path"], data["command"],
            data["args"], data["env"], data["status"], data["last_seen"],
            data["port"], data["user"], data["metadata"],
            data["cpu_percent"], data["memory_mb"],
            data["disk_read_mb"], data["disk_write_mb"],
            data["pid"], data["host"]
        ))
        
        # Record update in history
        await self._record_history(
            entry.pid, entry.host, entry.session_id,
            "updated", None, None,
            "Process information updated"
        )
    
    async def _record_history(
        self,
        pid: int,
        host: str,
        session_id: str,
        event_type: str,
        old_status: Optional[str],
        new_status: Optional[str],
        details: Optional[str]
    ) -> None:
        """Record an event in process history."""
        await self._db.execute("""
            INSERT INTO process_history (
                pid, host, session_id, event_type, event_time,
                old_status, new_status, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, host, session_id, event_type,
            datetime.now(timezone.utc).isoformat(),
            old_status, new_status, details
        ))
    
    async def close(self) -> None:
        """Close database connection."""
        async with self._lock:
            if self._db:
                await self._db.close()
                self._db = None
                logger.debug("Closed registry database connection")