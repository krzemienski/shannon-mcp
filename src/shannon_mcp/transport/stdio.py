"""STDIO transport implementation for MCP protocol"""

import asyncio
import json
import sys
from typing import Any, AsyncIterator, Dict, Optional, TextIO
from contextlib import asynccontextmanager

from .base import Transport, TransportError, ConnectionState
from ..utils.logging import get_logger
from ..streaming.buffer import StreamBuffer
from ..streaming.parser import JSONLParser

logger = get_logger(__name__)


class StdioTransport(Transport):
    """STDIO transport for MCP communication
    
    Communicates via stdin/stdout using JSON-RPC over newline-delimited JSON.
    """
    
    def __init__(self, stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None, 
                 stderr: Optional[TextIO] = None, name: str = None):
        super().__init__(name)
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._buffer = StreamBuffer(max_size=1024 * 1024)  # 1MB buffer
        self._parser = JSONLParser()
        self._write_lock = asyncio.Lock()
        
    async def connect(self) -> None:
        """Establish STDIO connection"""
        if self.state == ConnectionState.CONNECTED:
            return
            
        try:
            self.state = ConnectionState.CONNECTING
            logger.info("Connecting STDIO transport")
            
            # Create async streams from stdio
            loop = asyncio.get_event_loop()
            
            # For stdin, we need to create a reader
            self._reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, self._stdin)
            
            # For stdout, we need to create a writer
            transport, protocol = await loop.connect_write_pipe(
                lambda: asyncio.Protocol(), self._stdout
            )
            self._writer = asyncio.StreamWriter(transport, protocol, self._reader, loop)
            
            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            await self._handle_connect()
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            raise TransportError(f"Failed to connect STDIO: {e}")
            
    async def disconnect(self) -> None:
        """Close STDIO connection"""
        if self.state in (ConnectionState.DISCONNECTED, ConnectionState.CLOSED):
            return
            
        try:
            self.state = ConnectionState.CLOSING
            logger.info("Disconnecting STDIO transport")
            
            # Cancel receive task
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
                try:
                    await self._receive_task
                except asyncio.CancelledError:
                    pass
                    
            # Close writer
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
                
            await self._handle_close()
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self.state = ConnectionState.ERROR
            raise TransportError(f"Failed to disconnect STDIO: {e}")
            
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through STDIO"""
        if self.state != ConnectionState.CONNECTED:
            raise TransportError(f"Cannot send message in state: {self.state}")
            
        try:
            # Serialize message
            data = json.dumps(message, separators=(',', ':'))
            line = data + '\n'
            
            # Write with lock to ensure atomic writes
            async with self._write_lock:
                self._writer.write(line.encode('utf-8'))
                await self._writer.drain()
                
            self._stats["messages_sent"] += 1
            logger.debug(f"Sent message: {message.get('method', message.get('id'))}")
            
        except Exception as e:
            await self._handle_error(e)
            raise TransportError(f"Failed to send message: {e}")
            
    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from STDIO"""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Read from buffer
                if self._buffer.has_complete_line():
                    line = await self._buffer.read_line()
                    if line:
                        try:
                            message = self._parser.parse_line(line)
                            if message:
                                yield message
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON received: {e}")
                            await self._handle_error(e)
                else:
                    # Wait for more data
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                await self._handle_error(e)
                if self.state == ConnectionState.CONNECTED:
                    logger.error(f"Error receiving message: {e}")
                    
    async def _receive_loop(self) -> None:
        """Background task to read from stdin into buffer"""
        try:
            while self.state == ConnectionState.CONNECTED:
                # Read data from stdin
                data = await self._reader.read(4096)
                if not data:
                    # EOF reached
                    logger.info("STDIO EOF reached")
                    break
                    
                # Add to buffer
                await self._buffer.write(data)
                
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            await self._handle_error(e)
        finally:
            # Trigger disconnect if still connected
            if self.state == ConnectionState.CONNECTED:
                await self.disconnect()
                
    @asynccontextmanager
    async def session(self):
        """Context manager for STDIO session"""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
            
    async def write_error(self, message: str) -> None:
        """Write error message to stderr"""
        try:
            self._stderr.write(f"ERROR: {message}\n")
            self._stderr.flush()
        except Exception as e:
            logger.error(f"Failed to write to stderr: {e}")
            
    def __repr__(self) -> str:
        return f"StdioTransport(name={self.name}, state={self.state.value})"