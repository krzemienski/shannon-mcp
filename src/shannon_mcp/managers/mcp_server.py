"""
MCP Server Manager for Shannon MCP Server.

This module manages Model Context Protocol (MCP) server connections with:
- STDIO transport support
- SSE transport support
- Connection pooling
- Server discovery
- Health monitoring
- Configuration import
"""

import asyncio
import json
import os
import tempfile
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import subprocess
import structlog
import aiohttp
from urllib.parse import urlparse
import uuid
import weakref

from ..managers.base import BaseManager, ManagerConfig, HealthStatus
from ..utils.config import MCPConfig
from ..utils.errors import (
    SystemError, ValidationError, ConfigurationError,
    handle_errors, error_context
)
from ..utils.notifications import emit, EventCategory, EventPriority, event_handler
from ..utils.logging import get_logger
from ..transport import TransportManager, StdioTransport, SSETransport, ConnectionState as TransportConnectionState


logger = get_logger("shannon-mcp.mcp-server")


class TransportType(Enum):
    """MCP transport types."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    WEBSOCKET = "websocket"


class ConnectionState(Enum):
    """Connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    
    @classmethod
    def from_transport_state(cls, transport_state: TransportConnectionState) -> 'ConnectionState':
        """Convert transport connection state to manager connection state."""
        mapping = {
            TransportConnectionState.DISCONNECTED: cls.DISCONNECTED,
            TransportConnectionState.CONNECTING: cls.CONNECTING,
            TransportConnectionState.CONNECTED: cls.CONNECTED,
            TransportConnectionState.CLOSING: cls.DISCONNECTED,
            TransportConnectionState.CLOSED: cls.DISCONNECTED,
            TransportConnectionState.ERROR: cls.ERROR
        }
        return mapping.get(transport_state, cls.ERROR)


@dataclass
class MCPServer:
    """MCP server configuration."""
    id: str
    name: str
    transport: TransportType
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    endpoint: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 60
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "transport": self.transport.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "endpoint": self.endpoint,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "health_check_interval": self.health_check_interval,
            "enabled": self.enabled,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPServer':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            transport=TransportType(data["transport"]),
            command=data.get("command"),
            args=data.get("args", []),
            env=data.get("env", {}),
            endpoint=data.get("endpoint"),
            timeout=data.get("timeout", 30),
            retry_count=data.get("retry_count", 3),
            retry_delay=data.get("retry_delay", 1.0),
            health_check_interval=data.get("health_check_interval", 60),
            enabled=data.get("enabled", True),
            config=data.get("config", {}),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.utcnow().isoformat()))
        )


@dataclass
class Connection:
    """Active MCP server connection."""
    server_id: str
    state: ConnectionState
    transport_name: str
    process: Optional[asyncio.subprocess.Process] = None
    session: Optional[aiohttp.ClientSession] = None
    last_ping: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    connected_at: Optional[datetime] = None
    reconnect_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_healthy(self, health_timeout: int = 30) -> bool:
        """Check if connection is healthy."""
        if self.state != ConnectionState.CONNECTED:
            return False
        
        if self.last_ping is None:
            return True  # No ping yet, assume healthy
        
        timeout_threshold = datetime.utcnow() - timedelta(seconds=health_timeout)
        return self.last_ping > timeout_threshold


class MCPServerManager(BaseManager[MCPServer]):
    """Manages MCP server connections and discovery."""
    
    def __init__(self, config: MCPConfig):
        """Initialize MCP server manager."""
        manager_config = ManagerConfig(
            name="mcp_server_manager",
            db_path=None,  # Disable database to prevent initialization hangs
            enable_notifications=False,  # Disable notifications
            custom_config=config.dict()
        )
        super().__init__(manager_config)
        
        self.mcp_config = config
        self._servers: Dict[str, MCPServer] = {}
        self._connections: Dict[str, Connection] = {}
        self._discovery_cache: Dict[str, List[MCPServer]] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        
        # Connection pools
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        
        # Transport manager
        self._transport_manager = TransportManager()
    
    async def _initialize(self) -> None:
        """Initialize MCP server manager."""
        logger.info("initializing_mcp_server_manager")

        # Create HTTP session (lightweight)
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.mcp_config.connection_timeout)
        )

        # Register message handlers (lightweight)
        self._register_message_handlers()

        # Defer server loading to prevent blocking
        logger.info("mcp_server_loading_deferred", reason="prevent_init_blocking")
    
    async def _start(self) -> None:
        """Start MCP server manager."""
        # Start health monitoring
        self._tasks.append(
            asyncio.create_task(self._health_monitor_loop())
        )
        
        # Auto-connect enabled servers
        for server in self._servers.values():
            if server.enabled:
                try:
                    await self.connect_server(server.id)
                except Exception as e:
                    logger.error(
                        "auto_connect_failed",
                        server_id=server.id,
                        error=str(e)
                    )
    
    async def _stop(self) -> None:
        """Stop MCP server manager."""
        # Disconnect all servers
        for server_id in list(self._connections.keys()):
            await self.disconnect_server(server_id)
        
        # Stop health check tasks
        for task in self._health_check_tasks.values():
            task.cancel()
        self._health_check_tasks.clear()
        
        # Close HTTP session
        if self._http_session:
            await self._http_session.close()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        total_servers = len(self._servers)
        connected_servers = sum(
            1 for conn in self._connections.values()
            if conn.state == ConnectionState.CONNECTED
        )
        
        error_connections = sum(
            1 for conn in self._connections.values()
            if conn.state == ConnectionState.ERROR
        )
        
        return {
            "total_servers": total_servers,
            "connected_servers": connected_servers,
            "error_connections": error_connections,
            "discovery_cache_size": len(self._discovery_cache),
            "active_health_checks": len(self._health_check_tasks)
        }
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        # MCP servers table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                transport TEXT NOT NULL,
                command TEXT,
                args TEXT,
                env TEXT,
                endpoint TEXT,
                timeout INTEGER DEFAULT 30,
                retry_count INTEGER DEFAULT 3,
                retry_delay REAL DEFAULT 1.0,
                health_check_interval INTEGER DEFAULT 60,
                enabled BOOLEAN DEFAULT 1,
                config TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mcp_servers_transport 
            ON mcp_servers(transport)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mcp_servers_enabled 
            ON mcp_servers(enabled)
        """)
        
        # Connection history table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT NOT NULL,
                state TEXT NOT NULL,
                connected_at TEXT,
                disconnected_at TEXT,
                error_message TEXT,
                duration_seconds REAL,
                FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_mcp_connections_server 
            ON mcp_connections(server_id)
        """)
        
        # Server discovery cache
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_discovery_cache (
                source TEXT NOT NULL,
                servers TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (source)
            )
        """)
    
    async def add_server(self, server: MCPServer) -> None:
        """
        Add a new MCP server.
        
        Args:
            server: MCP server configuration
            
        Raises:
            ValidationError: If server is invalid
            SystemError: If add fails
        """
        with error_context("mcp_server_manager", "add_server", server_id=server.id):
            # Validate server
            if not server.name:
                raise ValidationError("name", server.name, "Server name is required")
            
            if server.transport == TransportType.STDIO and not server.command:
                raise ValidationError("command", server.command, "STDIO transport requires command")
            
            if server.transport in (TransportType.SSE, TransportType.HTTP) and not server.endpoint:
                raise ValidationError("endpoint", server.endpoint, f"{server.transport.value} transport requires endpoint")
            
            # Check for duplicates
            if server.id in self._servers:
                raise ValidationError("id", server.id, "Server already exists")
            
            # Save to database
            await self._save_server(server)
            
            # Add to registry
            self._servers[server.id] = server
            
            # Create connection lock
            self._connection_locks[server.id] = asyncio.Lock()
            
            # Emit event
            await emit(
                "mcp_server_added",
                EventCategory.MCP,
                {
                    "server_id": server.id,
                    "name": server.name,
                    "transport": server.transport.value
                }
            )
            
            logger.info(
                "mcp_server_added",
                server_id=server.id,
                name=server.name,
                transport=server.transport.value
            )
    
    async def remove_server(self, server_id: str) -> bool:
        """
        Remove an MCP server.
        
        Args:
            server_id: Server ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if server_id not in self._servers:
            return False
        
        with error_context("mcp_server_manager", "remove_server", server_id=server_id):
            # Disconnect if connected
            if server_id in self._connections:
                await self.disconnect_server(server_id)
            
            # Remove from database
            await self.db.execute("""
                DELETE FROM mcp_servers WHERE id = ?
            """, (server_id,))
            await self.db.commit()
            
            # Remove from registry
            server = self._servers.pop(server_id)
            
            # Clean up
            self._connection_locks.pop(server_id, None)
            
            # Stop health check task
            if server_id in self._health_check_tasks:
                self._health_check_tasks[server_id].cancel()
                del self._health_check_tasks[server_id]
            
            # Emit event
            await emit(
                "mcp_server_removed",
                EventCategory.MCP,
                {
                    "server_id": server_id,
                    "name": server.name
                }
            )
            
            logger.info(
                "mcp_server_removed",
                server_id=server_id,
                name=server.name
            )
            
            return True
    
    async def get_server(self, server_id: str) -> Optional[MCPServer]:
        """Get server by ID."""
        return self._servers.get(server_id)
    
    async def list_servers(
        self,
        transport: Optional[TransportType] = None,
        enabled_only: bool = False
    ) -> List[MCPServer]:
        """
        List MCP servers.
        
        Args:
            transport: Filter by transport type
            enabled_only: Only return enabled servers
            
        Returns:
            List of servers
        """
        servers = list(self._servers.values())
        
        if transport:
            servers = [s for s in servers if s.transport == transport]
        
        if enabled_only:
            servers = [s for s in servers if s.enabled]
        
        return servers
    
    async def connect_server(self, server_id: str) -> Connection:
        """
        Connect to an MCP server.
        
        Args:
            server_id: Server ID to connect to
            
        Returns:
            Active connection
            
        Raises:
            ValidationError: If server not found
            SystemError: If connection fails
        """
        server = self._servers.get(server_id)
        if not server:
            raise ValidationError("server_id", server_id, "Server not found")
        
        if not server.enabled:
            raise ValidationError("server_id", server_id, "Server is disabled")
        
        # Check for existing connection
        if server_id in self._connections:
            connection = self._connections[server_id]
            if connection.state == ConnectionState.CONNECTED:
                return connection
        
        # Get connection lock
        async with self._connection_locks[server_id]:
            with error_context("mcp_server_manager", "connect_server", server_id=server_id):
                # Create transport based on type
                transport_name = f"{server.name}_{server.id}"
                
                if server.transport == TransportType.STDIO:
                    transport = await self._transport_manager.add_process_stdio_transport(
                        name=transport_name,
                        command=server.command,
                        args=server.args,
                        env=server.env
                    )
                elif server.transport == TransportType.SSE:
                    transport = await self._transport_manager.add_sse_transport(
                        name=transport_name,
                        base_url=server.endpoint,
                        headers={"Authorization": f"Bearer {server.config.get('api_key', '')}"}  
                        if server.config.get('api_key') else None
                    )
                elif server.transport == TransportType.HTTP:
                    # Use SSE transport for HTTP (with different config)
                    transport = await self._transport_manager.add_sse_transport(
                        name=transport_name,
                        base_url=server.endpoint,
                        endpoint="",  # HTTP uses base URL directly
                        headers={"Authorization": f"Bearer {server.config.get('api_key', '')}"}  
                        if server.config.get('api_key') else None
                    )
                else:
                    raise SystemError(f"Unsupported transport: {server.transport}")
                
                # Create connection object
                connection = Connection(
                    server_id=server_id,
                    state=ConnectionState.CONNECTING,
                    transport_name=transport_name
                )
                
                self._connections[server_id] = connection
                
                try:
                    # Connect transport
                    await self._transport_manager.connect(transport_name)
                    
                    # Mark as connected
                    connection.state = ConnectionState.CONNECTED
                    connection.connected_at = datetime.utcnow()
                    connection.error_count = 0
                    connection.reconnect_attempts = 0
                    
                    # Start health check
                    self._health_check_tasks[server_id] = asyncio.create_task(
                        self._health_check_loop(server_id)
                    )
                    
                    # Log connection
                    await self._log_connection(server_id, ConnectionState.CONNECTED)
                    
                    # Emit event
                    await emit(
                        "mcp_server_connected",
                        EventCategory.MCP,
                        {
                            "server_id": server_id,
                            "transport": server.transport.value
                        },
                        priority=EventPriority.HIGH
                    )
                    
                    logger.info(
                        "mcp_server_connected",
                        server_id=server_id,
                        transport=server.transport.value
                    )
                    
                    return connection
                    
                except Exception as e:
                    # Mark as error
                    connection.state = ConnectionState.ERROR
                    connection.last_error = str(e)
                    connection.error_count += 1
                    
                    # Log connection error
                    await self._log_connection(server_id, ConnectionState.ERROR, str(e))
                    
                    # Emit event
                    await emit(
                        "mcp_server_connection_failed",
                        EventCategory.MCP,
                        {
                            "server_id": server_id,
                            "error": str(e)
                        },
                        priority=EventPriority.HIGH
                    )
                    
                    logger.error(
                        "mcp_server_connection_failed",
                        server_id=server_id,
                        error=str(e)
                    )
                    
                    raise
    
    async def disconnect_server(self, server_id: str) -> bool:
        """
        Disconnect from an MCP server.
        
        Args:
            server_id: Server ID to disconnect from
            
        Returns:
            True if disconnected, False if not connected
        """
        if server_id not in self._connections:
            return False
        
        async with self._connection_locks.get(server_id, asyncio.Lock()):
            connection = self._connections[server_id]
            
            # Stop health check
            if server_id in self._health_check_tasks:
                self._health_check_tasks[server_id].cancel()
                del self._health_check_tasks[server_id]
            
            # Disconnect transport
            try:
                await self._transport_manager.disconnect(connection.transport_name)
                await self._transport_manager.remove_transport(connection.transport_name)
                
            except Exception as e:
                logger.error(
                    "disconnect_error",
                    server_id=server_id,
                    error=str(e)
                )
            
            # Calculate duration
            duration = None
            if connection.connected_at:
                duration = (datetime.utcnow() - connection.connected_at).total_seconds()
            
            # Log disconnection
            await self._log_connection(
                server_id,
                ConnectionState.DISCONNECTED,
                duration_seconds=duration
            )
            
            # Remove connection
            del self._connections[server_id]
            
            # Emit event
            await emit(
                "mcp_server_disconnected",
                EventCategory.MCP,
                {
                    "server_id": server_id,
                    "duration": duration
                }
            )
            
            logger.info(
                "mcp_server_disconnected",
                server_id=server_id,
                duration=duration
            )
            
            return True
    
    async def get_connection(self, server_id: str) -> Optional[Connection]:
        """Get active connection for server."""
        return self._connections.get(server_id)
    
    async def list_connections(self) -> List[Connection]:
        """List all active connections."""
        return list(self._connections.values())
    
    
    async def discover_servers(self, source: str = "local") -> List[MCPServer]:
        """
        Discover MCP servers from various sources.
        
        Args:
            source: Discovery source (local, github, etc.)
            
        Returns:
            List of discovered servers
        """
        # Check cache first
        if source in self._discovery_cache:
            return self._discovery_cache[source]
        
        discovered = []
        
        try:
            if source == "local":
                discovered = await self._discover_local_servers()
            elif source == "claude_config":
                discovered = await self._discover_claude_config_servers()
            elif source.startswith("github:"):
                org_repo = source[7:]  # Remove "github:" prefix
                discovered = await self._discover_github_servers(org_repo)
            
            # Cache results
            self._discovery_cache[source] = discovered
            
            # Save to database cache
            await self._save_discovery_cache(source, discovered)
            
            logger.info(
                "servers_discovered",
                source=source,
                count=len(discovered)
            )
            
        except Exception as e:
            logger.error(
                "discovery_failed",
                source=source,
                error=str(e)
            )
        
        return discovered
    
    def _register_message_handlers(self) -> None:
        """Register transport message handlers."""
        # Register common handlers
        self._transport_manager.on_message("ping", self._handle_ping)
        self._transport_manager.on_message("notification", self._handle_notification)
        self._transport_manager.on_message("tools/list", self._handle_tools_list)
        self._transport_manager.on_message("resources/list", self._handle_resources_list)
        self._transport_manager.on_message("prompts/list", self._handle_prompts_list)
    
    async def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True, "timestamp": datetime.utcnow().isoformat()}
    
    async def _handle_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notification from server."""
        await emit(
            "mcp_server_notification",
            EventCategory.MCP,
            params
        )
        return {"acknowledged": True}
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools list request."""
        # This would be implemented based on the server's capabilities
        return {"tools": []}
    
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources list request."""
        # This would be implemented based on the server's capabilities
        return {"resources": []}
    
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts list request."""
        # This would be implemented based on the server's capabilities
        return {"prompts": []}
    
    async def send_request(
        self,
        server_id: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Send JSON-RPC request to MCP server."""
        connection = self._connections.get(server_id)
        if not connection or connection.state != ConnectionState.CONNECTED:
            raise ValidationError("server_id", server_id, "Server not connected")
        
        server = self._servers[server_id]
        request_timeout = timeout or server.timeout
        
        try:
            # Use transport manager to send request
            return await self._transport_manager.request(
                method=method,
                params=params,
                transport=connection.transport_name,
                timeout=request_timeout
            )
        except Exception as e:
            connection.error_count += 1
            connection.last_error = str(e)
            
            logger.error(
                "request_failed",
                server_id=server_id,
                method=method,
                error=str(e)
            )
            
            raise SystemError(f"Request failed: {e}") from e
    
    # Health monitoring
    
    async def _health_check_loop(self, server_id: str) -> None:
        """Health check loop for a server."""
        server = self._servers[server_id]
        
        while server_id in self._connections:
            try:
                await asyncio.sleep(server.health_check_interval)
                
                if server_id not in self._connections:
                    break
                
                connection = self._connections[server_id]
                
                # Perform health check
                try:
                    await self._ping_connection(connection)
                    connection.last_ping = datetime.utcnow()
                    
                    # Reset error count on successful ping
                    if connection.error_count > 0:
                        connection.error_count = 0
                        logger.info(
                            "server_recovered",
                            server_id=server_id
                        )
                
                except Exception as e:
                    connection.error_count += 1
                    connection.last_error = str(e)
                    
                    logger.warning(
                        "health_check_failed",
                        server_id=server_id,
                        error_count=connection.error_count,
                        error=str(e)
                    )
                    
                    # Reconnect if too many errors
                    if connection.error_count >= server.retry_count:
                        logger.error(
                            "server_unhealthy",
                            server_id=server_id,
                            error_count=connection.error_count
                        )
                        
                        # Attempt reconnection
                        try:
                            await self.disconnect_server(server_id)
                            await asyncio.sleep(server.retry_delay)
                            await self.connect_server(server_id)
                        except Exception as reconnect_error:
                            logger.error(
                                "reconnection_failed",
                                server_id=server_id,
                                error=str(reconnect_error)
                            )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "health_check_error",
                    server_id=server_id,
                    error=str(e)
                )
    
    async def _ping_connection(self, connection: Connection) -> None:
        """Ping a connection to check health."""
        try:
            # Use standard ping method through transport
            await self._transport_manager.request(
                method="ping",
                transport=connection.transport_name,
                timeout=5.0
            )
        except Exception as e:
            raise SystemError(f"Ping failed: {e}") from e
    
    # Discovery methods
    
    async def _discover_local_servers(self) -> List[MCPServer]:
        """Discover servers from local installations."""
        discovered = []
        
        # Check common installation paths
        search_paths = [
            Path.home() / ".local" / "bin",
            Path("/usr/local/bin"),
            Path("/opt/mcp-servers"),
        ]
        
        for path in search_paths:
            if path.exists():
                for executable in path.glob("mcp-*"):
                    if executable.is_file() and executable.stat().st_mode & 0o111:
                        server = MCPServer(
                            id=f"local_{executable.stem}",
                            name=executable.stem.replace("mcp-", "").replace("-", " ").title(),
                            transport=TransportType.STDIO,
                            command=str(executable)
                        )
                        discovered.append(server)
        
        return discovered
    
    async def _discover_claude_config_servers(self) -> List[MCPServer]:
        """Discover servers from Claude configuration."""
        discovered = []
        
        # Check Claude config locations
        config_paths = [
            Path.home() / ".config" / "claude" / "mcp_servers.json",
            Path.home() / ".claude" / "mcp_servers.json",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                    
                    for server_name, server_config in config.get("mcpServers", {}).items():
                        server = MCPServer(
                            id=f"claude_{server_name}",
                            name=server_name,
                            transport=TransportType.STDIO,
                            command=server_config.get("command"),
                            args=server_config.get("args", []),
                            env=server_config.get("env", {})
                        )
                        discovered.append(server)
                        
                except Exception as e:
                    logger.error(
                        "claude_config_parse_error",
                        path=str(config_path),
                        error=str(e)
                    )
        
        return discovered
    
    async def _discover_github_servers(self, org_repo: str) -> List[MCPServer]:
        """Discover servers from GitHub repository."""
        discovered = []
        
        try:
            url = f"https://api.github.com/repos/{org_repo}/contents/servers"
            
            async with self._http_session.get(url) as resp:
                if resp.status == 200:
                    files = await resp.json()
                    
                    for file in files:
                        if file["name"].endswith(".json"):
                            # Fetch server definition
                            async with self._http_session.get(file["download_url"]) as file_resp:
                                if file_resp.status == 200:
                                    server_def = await file_resp.json()
                                    
                                    server = MCPServer(
                                        id=f"github_{file['name'][:-5]}",
                                        name=server_def.get("name", file["name"][:-5]),
                                        transport=TransportType(server_def.get("transport", "stdio")),
                                        command=server_def.get("command"),
                                        args=server_def.get("args", []),
                                        env=server_def.get("env", {}),
                                        endpoint=server_def.get("endpoint")
                                    )
                                    discovered.append(server)
        
        except Exception as e:
            logger.error(
                "github_discovery_error",
                org_repo=org_repo,
                error=str(e)
            )
        
        return discovered
    
    # Monitoring loops
    
    async def _health_monitor_loop(self) -> None:
        """Main health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check for unhealthy connections
                unhealthy = []
                for server_id, connection in self._connections.items():
                    if not connection.is_healthy():
                        unhealthy.append(server_id)
                
                if unhealthy:
                    logger.warning(
                        "unhealthy_connections",
                        count=len(unhealthy),
                        servers=unhealthy
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_monitor_error", error=str(e))
    
    async def _auto_discovery_loop(self) -> None:
        """Auto-discovery loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Discover every hour
                
                # Discover from all sources
                sources = ["local", "claude_config"]
                
                for source in sources:
                    try:
                        await self.discover_servers(source)
                    except Exception as e:
                        logger.error(
                            "auto_discovery_error",
                            source=source,
                            error=str(e)
                        )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("auto_discovery_loop_error", error=str(e))
    
    # Database operations
    
    async def _load_servers(self) -> None:
        """Load servers from database."""
        cursor = await self.db.execute("""
            SELECT id, name, transport, command, args, env, endpoint,
                   timeout, retry_count, retry_delay, health_check_interval,
                   enabled, config, created_at, updated_at
            FROM mcp_servers
        """)
        
        rows = await cursor.fetchall()
        
        for row in rows:
            server = MCPServer(
                id=row[0],
                name=row[1],
                transport=TransportType(row[2]),
                command=row[3],
                args=json.loads(row[4]) if row[4] else [],
                env=json.loads(row[5]) if row[5] else {},
                endpoint=row[6],
                timeout=row[7],
                retry_count=row[8],
                retry_delay=row[9],
                health_check_interval=row[10],
                enabled=bool(row[11]),
                config=json.loads(row[12]) if row[12] else {},
                created_at=datetime.fromisoformat(row[13]),
                updated_at=datetime.fromisoformat(row[14])
            )
            
            self._servers[server.id] = server
            self._connection_locks[server.id] = asyncio.Lock()
        
        logger.info("servers_loaded", count=len(self._servers))
    
    async def _save_server(self, server: MCPServer) -> None:
        """Save server to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO mcp_servers 
            (id, name, transport, command, args, env, endpoint,
             timeout, retry_count, retry_delay, health_check_interval,
             enabled, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            server.id,
            server.name,
            server.transport.value,
            server.command,
            json.dumps(server.args),
            json.dumps(server.env),
            server.endpoint,
            server.timeout,
            server.retry_count,
            server.retry_delay,
            server.health_check_interval,
            server.enabled,
            json.dumps(server.config),
            server.created_at.isoformat(),
            server.updated_at.isoformat()
        ))
        await self.db.commit()
    
    async def _log_connection(
        self,
        server_id: str,
        state: ConnectionState,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> None:
        """Log connection event."""
        await self.db.execute("""
            INSERT INTO mcp_connections 
            (server_id, state, connected_at, disconnected_at, error_message, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            server_id,
            state.value,
            datetime.utcnow().isoformat() if state == ConnectionState.CONNECTED else None,
            datetime.utcnow().isoformat() if state == ConnectionState.DISCONNECTED else None,
            error_message,
            duration_seconds
        ))
        await self.db.commit()
    
    async def _save_discovery_cache(self, source: str, servers: List[MCPServer]) -> None:
        """Save discovery cache to database."""
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        await self.db.execute("""
            INSERT OR REPLACE INTO mcp_discovery_cache 
            (source, servers, discovered_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (
            source,
            json.dumps([s.to_dict() for s in servers]),
            datetime.utcnow().isoformat(),
            expires_at.isoformat()
        ))
        await self.db.commit()


# Export public API
__all__ = [
    'MCPServerManager',
    'MCPServer',
    'Connection',
    'TransportType',
    'ConnectionState',
]