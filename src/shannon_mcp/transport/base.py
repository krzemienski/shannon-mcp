"""Base transport implementation for MCP protocol"""

import asyncio
import enum
import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional, Callable, TypeVar
from datetime import datetime
import uuid

from ..utils.logging import get_logger
from ..utils.errors import MCPError

logger = get_logger(__name__)

T = TypeVar('T')


class ConnectionState(enum.Enum):
    """Connection state for transport"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class TransportError(MCPError):
    """Base exception for transport errors"""
    pass


class Transport(ABC):
    """Abstract base class for MCP transports"""
    
    def __init__(self, name: str = None):
        self.name = name or f"{self.__class__.__name__}_{uuid.uuid4().hex[:8]}"
        self.state = ConnectionState.DISCONNECTED
        self._message_id = 0
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._error_handlers: list[Callable] = []
        self._connection_handlers: list[Callable] = []
        self._close_handlers: list[Callable] = []
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "connected_at": None,
            "disconnected_at": None
        }
        
    @abstractmethod
    async def connect(self) -> None:
        """Establish transport connection"""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """Close transport connection"""
        pass
        
    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through the transport"""
        pass
        
    @abstractmethod
    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from the transport"""
        pass
        
    async def request(self, method: str, params: Optional[Dict[str, Any]] = None, 
                     timeout: Optional[float] = None) -> Any:
        """Send a request and wait for response"""
        message_id = self._generate_message_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.Future()
        self._pending_responses[message_id] = future
        
        try:
            # Send request
            await self.send_message(request)
            
            # Wait for response
            if timeout:
                response = await asyncio.wait_for(future, timeout)
            else:
                response = await future
                
            return response
            
        except asyncio.TimeoutError:
            self._pending_responses.pop(message_id, None)
            raise TransportError(f"Request timeout for {method}")
        except Exception as e:
            self._pending_responses.pop(message_id, None)
            raise TransportError(f"Request failed: {e}")
            
    async def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send a notification (no response expected)"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        await self.send_message(notification)
        
    async def respond(self, message_id: str, result: Any = None, error: Any = None) -> None:
        """Send a response to a request"""
        response = {
            "jsonrpc": "2.0",
            "id": message_id
        }
        
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
            
        await self.send_message(response)
        
    def on_message(self, method: str, handler: Callable) -> None:
        """Register a message handler"""
        self._message_handlers[method] = handler
        
    def on_error(self, handler: Callable) -> None:
        """Register an error handler"""
        self._error_handlers.append(handler)
        
    def on_connect(self, handler: Callable) -> None:
        """Register a connection handler"""
        self._connection_handlers.append(handler)
        
    def on_close(self, handler: Callable) -> None:
        """Register a close handler"""
        self._close_handlers.append(handler)
        
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message"""
        self._stats["messages_received"] += 1
        
        # Check if it's a response
        if "id" in message and message["id"] in self._pending_responses:
            future = self._pending_responses.pop(message["id"])
            
            if "error" in message:
                future.set_exception(TransportError(message["error"]))
            else:
                future.set_result(message.get("result"))
                
        # Check if it's a request or notification
        elif "method" in message:
            method = message["method"]
            params = message.get("params", {})
            message_id = message.get("id")
            
            # Find handler
            handler = self._message_handlers.get(method)
            if handler:
                try:
                    result = await handler(params)
                    
                    # Send response if it's a request
                    if message_id is not None:
                        await self.respond(message_id, result=result)
                        
                except Exception as e:
                    logger.error(f"Handler error for {method}: {e}")
                    
                    # Send error response if it's a request
                    if message_id is not None:
                        await self.respond(message_id, error={
                            "code": -32603,
                            "message": str(e)
                        })
            else:
                logger.warning(f"No handler for method: {method}")
                
                # Send method not found error if it's a request
                if message_id is not None:
                    await self.respond(message_id, error={
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    })
                    
    async def _handle_error(self, error: Exception) -> None:
        """Handle transport error"""
        self._stats["errors"] += 1
        logger.error(f"Transport error: {error}")
        
        for handler in self._error_handlers:
            try:
                await handler(error)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
                
    async def _handle_connect(self) -> None:
        """Handle connection established"""
        self.state = ConnectionState.CONNECTED
        self._stats["connected_at"] = datetime.now()
        logger.info(f"Transport connected: {self.name}")
        
        for handler in self._connection_handlers:
            try:
                await handler()
            except Exception as e:
                logger.error(f"Connection handler failed: {e}")
                
    async def _handle_close(self) -> None:
        """Handle connection closed"""
        self.state = ConnectionState.CLOSED
        self._stats["disconnected_at"] = datetime.now()
        logger.info(f"Transport closed: {self.name}")
        
        # Cancel pending responses
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()
        
        for handler in self._close_handlers:
            try:
                await handler()
            except Exception as e:
                logger.error(f"Close handler failed: {e}")
                
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        self._message_id += 1
        return str(self._message_id)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics"""
        return {
            **self._stats,
            "state": self.state.value,
            "pending_responses": len(self._pending_responses)
        }