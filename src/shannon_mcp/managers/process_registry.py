"""
Process Registry Manager for Shannon MCP Server.

Manages system-wide registration of MCP sessions across multiple processes.
"""

import asyncio
import json
import os
import psutil
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from pathlib import Path
import socket
import fcntl

from .base import BaseManager, ManagerConfig, ManagerError
from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.managers.process_registry")


@dataclass
class ProcessInfo:
    """Information about a registered process."""
    pid: int
    name: str
    command: str
    created_at: datetime
    port: Optional[int] = None
    socket_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "pid": self.pid,
            "name": self.name,
            "command": self.command,
            "created_at": self.created_at.isoformat(),
            "port": self.port,
            "socket_path": self.socket_path,
            "metadata": self.metadata
        }


@dataclass
class RegisteredSession:
    """Information about a registered MCP session."""
    session_id: str
    process_info: ProcessInfo
    client_info: Dict[str, Any]
    status: str
    registered_at: datetime
    last_seen: datetime
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "session_id": self.session_id,
            "process": self.process_info.to_dict(),
            "client_info": self.client_info,
            "status": self.status,
            "registered_at": self.registered_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "tags": self.tags
        }


@dataclass
class ProcessRegistryConfig(ManagerConfig):
    """Configuration for process registry manager."""
    registry_path: str = "/tmp/shannon-mcp-registry"
    cleanup_interval: int = 60  # seconds
    stale_threshold: int = 300  # seconds
    enable_discovery: bool = True
    discovery_port_range: tuple = (50000, 51000)
    enable_ipc: bool = True
    ipc_socket_dir: str = "/tmp/shannon-mcp-sockets"


class ProcessRegistryManager(BaseManager[RegisteredSession]):
    """Manages system-wide registration of MCP sessions."""
    
    def __init__(self, config: ProcessRegistryConfig):
        """Initialize process registry manager."""
        super().__init__(config)
        self.config: ProcessRegistryConfig = config
        self._registry: Dict[str, RegisteredSession] = {}
        self._process_sessions: Dict[int, Set[str]] = {}
        self._lock_file: Optional[int] = None
        self._discovery_socket: Optional[socket.socket] = None
        self._ipc_sockets: Dict[str, socket.socket] = {}
    
    async def _initialize(self) -> None:
        """Initialize process registry manager."""
        logger.info("Initializing process registry manager")
        
        # Create registry directory
        Path(self.config.registry_path).mkdir(parents=True, exist_ok=True)
        
        # Create IPC socket directory
        if self.config.enable_ipc:
            Path(self.config.ipc_socket_dir).mkdir(parents=True, exist_ok=True)
        
        # Acquire registry lock
        await self._acquire_registry_lock()
        
        # Load existing registry
        await self._load_registry()
        
        # Start discovery service
        if self.config.enable_discovery:
            await self._start_discovery_service()
    
    async def _start(self) -> None:
        """Start process registry operations."""
        logger.info("Starting process registry manager")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _stop(self) -> None:
        """Stop process registry operations."""
        logger.info("Stopping process registry manager")
        
        # Cancel tasks
        for task in ['_cleanup_task', '_heartbeat_task']:
            if hasattr(self, task):
                getattr(self, task).cancel()
        
        # Close discovery socket
        if self._discovery_socket:
            self._discovery_socket.close()
        
        # Close IPC sockets
        for sock in self._ipc_sockets.values():
            sock.close()
        
        # Release registry lock
        await self._release_registry_lock()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Check process registry health."""
        # Check for stale processes
        stale_count = 0
        now = datetime.now(timezone.utc)
        for session in self._registry.values():
            if (now - session.last_seen).total_seconds() > self.config.stale_threshold:
                stale_count += 1
        
        return {
            "healthy": True,
            "registered_sessions": len(self._registry),
            "unique_processes": len(self._process_sessions),
            "stale_sessions": stale_count,
            "discovery_enabled": self.config.enable_discovery,
            "ipc_enabled": self.config.enable_ipc
        }
    
    async def _create_schema(self) -> None:
        """Create database schema for process registry."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS process_registry (
                session_id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                command TEXT NOT NULL,
                process_created_at TIMESTAMP NOT NULL,
                port INTEGER,
                socket_path TEXT,
                process_metadata TEXT,
                client_info TEXT,
                status TEXT NOT NULL,
                registered_at TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                tags TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_registry_pid 
            ON process_registry(pid)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_registry_status 
            ON process_registry(status)
        """)
    
    async def register_session(
        self,
        session_id: str,
        client_info: Dict[str, Any],
        port: Optional[int] = None,
        socket_path: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> RegisteredSession:
        """Register a new MCP session."""
        # Get current process info
        pid = os.getpid()
        process = psutil.Process(pid)
        
        process_info = ProcessInfo(
            pid=pid,
            name=process.name(),
            command=' '.join(process.cmdline()),
            created_at=datetime.fromtimestamp(process.create_time(), timezone.utc),
            port=port,
            socket_path=socket_path,
            metadata={
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "num_threads": process.num_threads()
            }
        )
        
        # Create registered session
        session = RegisteredSession(
            session_id=session_id,
            process_info=process_info,
            client_info=client_info,
            status="active",
            registered_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            tags=tags or []
        )
        
        # Store in registry
        self._registry[session_id] = session
        
        # Track by process
        if pid not in self._process_sessions:
            self._process_sessions[pid] = set()
        self._process_sessions[pid].add(session_id)
        
        # Persist to registry file
        await self._persist_registry()
        
        # Persist to database
        if self.db:
            await self._persist_session(session)
        
        # Announce via discovery
        if self.config.enable_discovery:
            await self._announce_session(session)
        
        logger.info(f"Registered session {session_id} from process {pid}")
        return session
    
    async def unregister_session(self, session_id: str) -> None:
        """Unregister an MCP session."""
        session = self._registry.get(session_id)
        if not session:
            return
        
        # Remove from registry
        del self._registry[session_id]
        
        # Remove from process tracking
        pid = session.process_info.pid
        if pid in self._process_sessions:
            self._process_sessions[pid].discard(session_id)
            if not self._process_sessions[pid]:
                del self._process_sessions[pid]
        
        # Update registry file
        await self._persist_registry()
        
        # Remove from database
        if self.db:
            await self.db.execute(
                "DELETE FROM process_registry WHERE session_id = ?",
                (session_id,)
            )
            await self.db.commit()
        
        logger.info(f"Unregistered session {session_id}")
    
    async def update_session_status(
        self,
        session_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update session status."""
        session = self._registry.get(session_id)
        if not session:
            raise ManagerError(f"Session {session_id} not found")
        
        session.status = status
        session.last_seen = datetime.now(timezone.utc)
        
        if metadata:
            session.process_info.metadata.update(metadata)
        
        # Update registry file
        await self._persist_registry()
        
        # Update database
        if self.db:
            await self._update_session_db(session)
    
    async def heartbeat(self, session_id: str) -> None:
        """Update session heartbeat."""
        session = self._registry.get(session_id)
        if session:
            session.last_seen = datetime.now(timezone.utc)
    
    async def list_sessions(
        self,
        process_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[RegisteredSession]:
        """List registered sessions."""
        sessions = list(self._registry.values())
        
        if process_id:
            sessions = [s for s in sessions if s.process_info.pid == process_id]
        
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        return sessions
    
    async def discover_sessions(self) -> List[RegisteredSession]:
        """Discover MCP sessions on the system."""
        discovered = []
        
        # Scan for known MCP processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'shannon-mcp' in cmdline or 'claude-code' in cmdline:
                    # Check if already registered
                    if proc.info['pid'] not in self._process_sessions:
                        # Try to connect and get info
                        session_info = await self._probe_process(proc.info['pid'])
                        if session_info:
                            discovered.append(session_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return discovered
    
    async def send_message(
        self,
        session_id: str,
        message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send IPC message to a session."""
        if not self.config.enable_ipc:
            raise ManagerError("IPC is disabled")
        
        session = self._registry.get(session_id)
        if not session:
            raise ManagerError(f"Session {session_id} not found")
        
        if not session.process_info.socket_path:
            raise ManagerError(f"Session {session_id} has no IPC socket")
        
        # Connect to session socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(session.process_info.socket_path)
            
            # Send message
            data = json.dumps(message).encode()
            sock.sendall(len(data).to_bytes(4, 'big') + data)
            
            # Receive response
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None
            
            length = int.from_bytes(length_bytes, 'big')
            response_data = sock.recv(length)
            
            return json.loads(response_data.decode())
            
        finally:
            sock.close()
    
    async def cleanup_stale_sessions(self) -> int:
        """Clean up stale sessions."""
        now = datetime.now(timezone.utc)
        threshold = timedelta(seconds=self.config.stale_threshold)
        
        stale_sessions = []
        for session_id, session in self._registry.items():
            # Check if process still exists
            if not psutil.pid_exists(session.process_info.pid):
                stale_sessions.append(session_id)
                continue
            
            # Check last seen time
            if now - session.last_seen > threshold:
                stale_sessions.append(session_id)
        
        # Remove stale sessions
        for session_id in stale_sessions:
            await self.unregister_session(session_id)
        
        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale sessions")
        
        return len(stale_sessions)
    
    # Private helper methods
    
    async def _acquire_registry_lock(self) -> None:
        """Acquire exclusive lock on registry."""
        lock_path = Path(self.config.registry_path) / ".lock"
        self._lock_file = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)
        
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            os.close(self._lock_file)
            raise ManagerError("Another registry instance is running")
    
    async def _release_registry_lock(self) -> None:
        """Release registry lock."""
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            os.close(self._lock_file)
            self._lock_file = None
    
    async def _load_registry(self) -> None:
        """Load registry from file."""
        registry_file = Path(self.config.registry_path) / "registry.json"
        
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                
                for session_data in data.get('sessions', []):
                    # Reconstruct objects
                    process_info = ProcessInfo(
                        pid=session_data['process']['pid'],
                        name=session_data['process']['name'],
                        command=session_data['process']['command'],
                        created_at=datetime.fromisoformat(session_data['process']['created_at']),
                        port=session_data['process'].get('port'),
                        socket_path=session_data['process'].get('socket_path'),
                        metadata=session_data['process'].get('metadata', {})
                    )
                    
                    session = RegisteredSession(
                        session_id=session_data['session_id'],
                        process_info=process_info,
                        client_info=session_data['client_info'],
                        status=session_data['status'],
                        registered_at=datetime.fromisoformat(session_data['registered_at']),
                        last_seen=datetime.fromisoformat(session_data['last_seen']),
                        tags=session_data.get('tags', [])
                    )
                    
                    # Verify process still exists
                    if psutil.pid_exists(process_info.pid):
                        self._registry[session.session_id] = session
                        
                        if process_info.pid not in self._process_sessions:
                            self._process_sessions[process_info.pid] = set()
                        self._process_sessions[process_info.pid].add(session.session_id)
                
                logger.info(f"Loaded {len(self._registry)} sessions from registry")
                
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
    
    async def _persist_registry(self) -> None:
        """Persist registry to file."""
        registry_file = Path(self.config.registry_path) / "registry.json"
        
        data = {
            'version': '1.0',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'sessions': [session.to_dict() for session in self._registry.values()]
        }
        
        # Write atomically
        temp_file = registry_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        temp_file.replace(registry_file)
    
    async def _start_discovery_service(self) -> None:
        """Start UDP discovery service."""
        self._discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Find available port in range
        for port in range(*self.config.discovery_port_range):
            try:
                self._discovery_socket.bind(('0.0.0.0', port))
                self._discovery_port = port
                logger.info(f"Discovery service listening on port {port}")
                break
            except OSError:
                continue
        else:
            raise ManagerError("No available discovery port")
        
        # Start listening task
        asyncio.create_task(self._discovery_listener())
    
    async def _discovery_listener(self) -> None:
        """Listen for discovery requests."""
        while True:
            try:
                data, addr = await asyncio.get_event_loop().sock_recvfrom(
                    self._discovery_socket, 1024
                )
                
                message = json.loads(data.decode())
                if message.get('type') == 'discover':
                    # Send response with our sessions
                    response = {
                        'type': 'announce',
                        'sessions': [s.to_dict() for s in self._registry.values()]
                    }
                    
                    await asyncio.get_event_loop().sock_sendto(
                        self._discovery_socket,
                        json.dumps(response).encode(),
                        addr
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery listener error: {e}")
    
    async def _announce_session(self, session: RegisteredSession) -> None:
        """Announce session via discovery."""
        announcement = {
            'type': 'announce',
            'session': session.to_dict()
        }
        
        # Broadcast to discovery port range
        for port in range(*self.config.discovery_port_range):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(
                    json.dumps(announcement).encode(),
                    ('255.255.255.255', port)
                )
                sock.close()
            except:
                pass
    
    async def _probe_process(self, pid: int) -> Optional[RegisteredSession]:
        """Probe a process to get session info."""
        # Try common IPC methods
        # This would be implemented based on the actual IPC mechanism
        return None
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up stale sessions."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self.cleanup_stale_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeats."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Update our own sessions
                pid = os.getpid()
                if pid in self._process_sessions:
                    for session_id in self._process_sessions[pid]:
                        await self.heartbeat(session_id)
                
                await self._persist_registry()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _persist_session(self, session: RegisteredSession) -> None:
        """Persist session to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO process_registry (
                session_id, pid, process_name, command, process_created_at,
                port, socket_path, process_metadata, client_info, status,
                registered_at, last_seen, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.process_info.pid,
            session.process_info.name,
            session.process_info.command,
            session.process_info.created_at.isoformat(),
            session.process_info.port,
            session.process_info.socket_path,
            json.dumps(session.process_info.metadata),
            json.dumps(session.client_info),
            session.status,
            session.registered_at.isoformat(),
            session.last_seen.isoformat(),
            json.dumps(session.tags)
        ))
        await self.db.commit()
    
    async def _update_session_db(self, session: RegisteredSession) -> None:
        """Update session in database."""
        await self.db.execute("""
            UPDATE process_registry SET
                status = ?, last_seen = ?, process_metadata = ?
            WHERE session_id = ?
        """, (
            session.status,
            session.last_seen.isoformat(),
            json.dumps(session.process_info.metadata),
            session.session_id
        ))
        await self.db.commit()