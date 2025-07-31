"""SSE (Server-Sent Events) transport implementation for MCP protocol"""

import asyncio
import json
import aiohttp
from typing import Any, AsyncIterator, Dict, Optional, Union
from contextlib import asynccontextmanager
from urllib.parse import urljoin

from .base import Transport, TransportError, ConnectionState
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SSETransport(Transport):
    """SSE transport for MCP communication
    
    Implements Server-Sent Events transport for MCP protocol.
    Receives events via SSE and sends requests via HTTP POST.
    """
    
    def __init__(self, base_url: str, endpoint: str = "/mcp/sse", 
                 headers: Optional[Dict[str, str]] = None, name: str = None,
                 timeout: float = 30.0, reconnect_delay: float = 1.0):
        super().__init__(name)
        self.base_url = base_url.rstrip('/')
        self.endpoint = endpoint
        self.headers = headers or {}
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self._session: Optional[aiohttp.ClientSession] = None
        self._sse_task: Optional[asyncio.Task] = None
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        
    async def connect(self) -> None:
        """Establish SSE connection"""
        if self.state == ConnectionState.CONNECTED:
            return
            
        try:
            self.state = ConnectionState.CONNECTING
            logger.info(f"Connecting SSE transport to {self.base_url}{self.endpoint}")
            
            # Create HTTP session
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout_config
            )
            
            # Start SSE listener
            self._sse_task = asyncio.create_task(self._sse_loop())
            
            # Wait for initial connection
            await asyncio.sleep(0.5)
            
            if self.state == ConnectionState.CONNECTING:
                await self._handle_connect()
                
        except Exception as e:
            self.state = ConnectionState.ERROR
            if self._session:
                await self._session.close()
            raise TransportError(f"Failed to connect SSE: {e}")
            
    async def disconnect(self) -> None:
        """Close SSE connection"""
        if self.state in (ConnectionState.DISCONNECTED, ConnectionState.CLOSED):
            return
            
        try:
            self.state = ConnectionState.CLOSING
            logger.info("Disconnecting SSE transport")
            
            # Cancel SSE task
            if self._sse_task and not self._sse_task.done():
                self._sse_task.cancel()
                try:
                    await self._sse_task
                except asyncio.CancelledError:
                    pass
                    
            # Close HTTP session
            if self._session and not self._session.closed:
                await self._session.close()
                
            await self._handle_close()
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self.state = ConnectionState.ERROR
            raise TransportError(f"Failed to disconnect SSE: {e}")
            
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message via HTTP POST"""
        if self.state != ConnectionState.CONNECTED:
            raise TransportError(f"Cannot send message in state: {self.state}")
            
        try:
            # Send as HTTP POST
            url = urljoin(self.base_url, "/mcp/message")
            
            async with self._session.post(url, json=message) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise TransportError(f"HTTP {response.status}: {text}")
                    
            self._stats["messages_sent"] += 1
            logger.debug(f"Sent message: {message.get('method', message.get('id'))}")
            
        except aiohttp.ClientError as e:
            await self._handle_error(e)
            raise TransportError(f"Failed to send message: {e}")
            
    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from SSE event queue"""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(
                    self._event_queue.get(), 
                    timeout=1.0
                )
                yield message
                
            except asyncio.TimeoutError:
                # No message available, continue
                continue
            except Exception as e:
                await self._handle_error(e)
                if self.state == ConnectionState.CONNECTED:
                    logger.error(f"Error receiving message: {e}")
                    
    async def _sse_loop(self) -> None:
        """Background task to receive SSE events"""
        url = urljoin(self.base_url, self.endpoint)
        
        while self.state in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            try:
                logger.debug(f"Connecting to SSE endpoint: {url}")
                
                async with self._session.get(url) as response:
                    if response.status >= 400:
                        text = await response.text()
                        raise TransportError(f"HTTP {response.status}: {text}")
                        
                    # Reset reconnect counter on successful connection
                    self._reconnect_attempts = 0
                    
                    # Process SSE stream
                    async for line in response.content:
                        if self.state != ConnectionState.CONNECTED:
                            break
                            
                        line = line.decode('utf-8').strip()
                        
                        # Parse SSE event
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            
                            try:
                                message = json.loads(data)
                                await self._event_queue.put(message)
                                self._stats["messages_received"] += 1
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON in SSE event: {e}")
                                
                        elif line.startswith('event: '):
                            event_type = line[7:]  # Remove 'event: ' prefix
                            logger.debug(f"SSE event type: {event_type}")
                            
                        elif line.startswith('retry: '):
                            try:
                                retry_ms = int(line[7:])
                                self.reconnect_delay = retry_ms / 1000.0
                            except ValueError:
                                pass
                                
            except asyncio.CancelledError:
                logger.debug("SSE loop cancelled")
                break
            except Exception as e:
                logger.error(f"SSE connection error: {e}")
                await self._handle_error(e)
                
                # Reconnect with exponential backoff
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    self._reconnect_attempts += 1
                    delay = self.reconnect_delay * (2 ** (self._reconnect_attempts - 1))
                    logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max reconnection attempts reached")
                    self.state = ConnectionState.ERROR
                    break
                    
    @asynccontextmanager
    async def session(self):
        """Context manager for SSE session"""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
            
    def __repr__(self) -> str:
        return f"SSETransport(url={self.base_url}{self.endpoint}, state={self.state.value})"