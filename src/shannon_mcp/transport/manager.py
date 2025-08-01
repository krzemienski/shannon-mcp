"""Transport connection manager for MCP protocol"""

import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
from contextlib import asynccontextmanager

from .base import Transport, TransportError, ConnectionState
from .stdio import StdioTransport
from .process_stdio import ProcessStdioTransport
from .sse import SSETransport
from ..utils.logging import get_logger
from ..utils.notifications import EventBus, EventCategory, EventPriority, emit

logger = get_logger(__name__)


class TransportManager:
    """Manages transport connections and routing
    
    Supports multiple simultaneous transport connections and
    provides unified interface for message handling.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._transports: Dict[str, Transport] = {}
        self._primary_transport: Optional[str] = None
        self._message_handlers: Dict[str, Callable] = {}
        self._event_bus = event_bus or EventBus()
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "total_errors": 0
        }
        
    async def add_stdio_transport(self, name: str = "stdio", **kwargs) -> StdioTransport:
        """Add a STDIO transport"""
        if name in self._transports:
            raise TransportError(f"Transport '{name}' already exists")
            
        transport = StdioTransport(name=name, **kwargs)
        await self._register_transport(name, transport)
        return transport
        
    async def add_process_stdio_transport(self, name: str, command: str, 
                                        args: Optional[List[str]] = None,
                                        env: Optional[Dict[str, str]] = None,
                                        cwd: Optional[str] = None) -> ProcessStdioTransport:
        """Add a process-based STDIO transport"""
        if name in self._transports:
            raise TransportError(f"Transport '{name}' already exists")
            
        transport = ProcessStdioTransport(
            command=command, 
            args=args, 
            env=env, 
            cwd=cwd, 
            name=name
        )
        await self._register_transport(name, transport)
        return transport
        
    async def add_sse_transport(self, name: str, base_url: str, **kwargs) -> SSETransport:
        """Add an SSE transport"""
        if name in self._transports:
            raise TransportError(f"Transport '{name}' already exists")
            
        transport = SSETransport(base_url=base_url, name=name, **kwargs)
        await self._register_transport(name, transport)
        return transport
        
    async def _register_transport(self, name: str, transport: Transport) -> None:
        """Register a transport with the manager"""
        # Set up transport handlers
        transport.on_error(self._handle_transport_error)
        transport.on_connect(lambda: self._handle_transport_connect(name))
        transport.on_close(lambda: self._handle_transport_close(name))
        
        # Register message handlers
        for method, handler in self._message_handlers.items():
            transport.on_message(method, handler)
            
        self._transports[name] = transport
        
        # Set as primary if first transport
        if self._primary_transport is None:
            self._primary_transport = name
            
        logger.info(f"Registered transport: {name}")
        
    async def remove_transport(self, name: str) -> None:
        """Remove a transport"""
        if name not in self._transports:
            raise TransportError(f"Transport '{name}' not found")
            
        transport = self._transports[name]
        
        # Disconnect if connected
        if transport.state == ConnectionState.CONNECTED:
            await transport.disconnect()
            
        del self._transports[name]
        
        # Update primary if needed
        if self._primary_transport == name:
            self._primary_transport = next(iter(self._transports), None)
            
        logger.info(f"Removed transport: {name}")
        
    async def connect(self, name: Optional[str] = None) -> None:
        """Connect transport(s)"""
        if name:
            # Connect specific transport
            if name not in self._transports:
                raise TransportError(f"Transport '{name}' not found")
            await self._transports[name].connect()
        else:
            # Connect all transports
            tasks = [t.connect() for t in self._transports.values()]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
    async def disconnect(self, name: Optional[str] = None) -> None:
        """Disconnect transport(s)"""
        if name:
            # Disconnect specific transport
            if name not in self._transports:
                raise TransportError(f"Transport '{name}' not found")
            await self._transports[name].disconnect()
        else:
            # Disconnect all transports
            tasks = [t.disconnect() for t in self._transports.values()]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
    async def send_message(self, message: Dict[str, Any], 
                          transport: Optional[str] = None) -> None:
        """Send a message through transport(s)"""
        if transport:
            # Send through specific transport
            if transport not in self._transports:
                raise TransportError(f"Transport '{transport}' not found")
            await self._transports[transport].send_message(message)
        else:
            # Send through primary transport
            if not self._primary_transport:
                raise TransportError("No primary transport available")
            await self._transports[self._primary_transport].send_message(message)
            
        self._stats["total_messages_sent"] += 1
        
    async def broadcast_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Broadcast message to all connected transports"""
        results = {}
        
        for name, transport in self._transports.items():
            if transport.state == ConnectionState.CONNECTED:
                try:
                    await transport.send_message(message)
                    results[name] = {"success": True}
                except Exception as e:
                    results[name] = {"success": False, "error": str(e)}
                    
        return results
        
    async def request(self, method: str, params: Optional[Dict[str, Any]] = None,
                     transport: Optional[str] = None, timeout: Optional[float] = None) -> Any:
        """Send request and wait for response"""
        if transport:
            if transport not in self._transports:
                raise TransportError(f"Transport '{transport}' not found")
            return await self._transports[transport].request(method, params, timeout)
        else:
            if not self._primary_transport:
                raise TransportError("No primary transport available")
            return await self._transports[self._primary_transport].request(method, params, timeout)
            
    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None,
                    transport: Optional[str] = None) -> None:
        """Send notification"""
        if transport:
            if transport not in self._transports:
                raise TransportError(f"Transport '{transport}' not found")
            await self._transports[transport].notify(method, params)
        else:
            if not self._primary_transport:
                raise TransportError("No primary transport available")
            await self._transports[self._primary_transport].notify(method, params)
            
    def on_message(self, method: str, handler: Callable) -> None:
        """Register a message handler for all transports"""
        self._message_handlers[method] = handler
        
        # Register with existing transports
        for transport in self._transports.values():
            transport.on_message(method, handler)
            
    async def receive_messages(self, transport: Optional[str] = None):
        """Receive messages from transport(s)"""
        if transport:
            # Receive from specific transport
            if transport not in self._transports:
                raise TransportError(f"Transport '{transport}' not found")
            async for message in self._transports[transport].receive_messages():
                self._stats["total_messages_received"] += 1
                yield (transport, message)
        else:
            # Receive from all transports
            queues = {
                name: asyncio.create_task(self._queue_messages(name, t))
                for name, t in self._transports.items()
                if t.state == ConnectionState.CONNECTED
            }
            
            while queues:
                done, pending = await asyncio.wait(
                    queues.values(), 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    try:
                        name, message = await task
                        if message:
                            self._stats["total_messages_received"] += 1
                            yield (name, message)
                            
                            # Create new task for this transport
                            if name in self._transports:
                                queues[name] = asyncio.create_task(
                                    self._queue_messages(name, self._transports[name])
                                )
                    except Exception as e:
                        logger.error(f"Error receiving message: {e}")
                        
    async def _queue_messages(self, name: str, transport: Transport):
        """Queue messages from a transport"""
        async for message in transport.receive_messages():
            return (name, message)
        return (name, None)
        
    def set_primary_transport(self, name: str) -> None:
        """Set the primary transport"""
        if name not in self._transports:
            raise TransportError(f"Transport '{name}' not found")
        self._primary_transport = name
        logger.info(f"Set primary transport: {name}")
        
    def get_transport(self, name: str) -> Optional[Transport]:
        """Get a specific transport"""
        return self._transports.get(name)
        
    def list_transports(self) -> List[Dict[str, Any]]:
        """List all transports with their status"""
        return [
            {
                "name": name,
                "type": transport.__class__.__name__,
                "state": transport.state.value,
                "is_primary": name == self._primary_transport,
                "stats": transport.get_stats()
            }
            for name, transport in self._transports.items()
        ]
        
    async def _handle_transport_error(self, error: Exception) -> None:
        """Handle transport error"""
        self._stats["total_errors"] += 1
        await self._event_bus.emit(
            "transport_error",
            EventCategory.ERROR,
            {"error": str(error), "message": f"Transport error: {error}"}
        )
        
    async def _handle_transport_connect(self, name: str) -> None:
        """Handle transport connection"""
        self._stats["total_connections"] += 1
        self._stats["active_connections"] = sum(
            1 for t in self._transports.values() 
            if t.state == ConnectionState.CONNECTED
        )
        
        await self._event_bus.emit(
            "transport_connected",
            EventCategory.LIFECYCLE,
            {"transport": name, "message": f"Transport connected: {name}"}
        )
        
    async def _handle_transport_close(self, name: str) -> None:
        """Handle transport disconnection"""
        self._stats["active_connections"] = sum(
            1 for t in self._transports.values() 
            if t.state == ConnectionState.CONNECTED
        )
        
        await self._event_bus.emit(
            "transport_disconnected",
            EventCategory.LIFECYCLE,
            {"transport": name, "message": f"Transport disconnected: {name}"}
        )
        
    @asynccontextmanager
    async def session(self, transports: Optional[List[str]] = None):
        """Context manager for transport session"""
        # Connect specified transports or all
        if transports:
            for name in transports:
                await self.connect(name)
        else:
            await self.connect()
            
        try:
            yield self
        finally:
            # Disconnect
            if transports:
                for name in transports:
                    await self.disconnect(name)
            else:
                await self.disconnect()
                
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            **self._stats,
            "transports": self.list_transports()
        }