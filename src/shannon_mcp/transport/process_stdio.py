"""Process-based STDIO transport implementation for MCP protocol"""

import asyncio
import json
import os
from typing import Any, AsyncIterator, Dict, Optional, List
from contextlib import asynccontextmanager

from .base import Transport, TransportError, ConnectionState
from ..utils.logging import get_logger
from ..streaming.buffer import StreamBuffer
from ..streaming.parser import JSONLParser

logger = get_logger(__name__)


class ProcessStdioTransport(Transport):
    """Process-based STDIO transport for MCP communication
    
    Launches a subprocess and communicates via its stdin/stdout using 
    JSON-RPC over newline-delimited JSON.
    """
    
    def __init__(self, command: str, args: Optional[List[str]] = None,
                 env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None,
                 name: str = None):
        super().__init__(name)
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self._process: Optional[asyncio.subprocess.Process] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._error_task: Optional[asyncio.Task] = None
        self._stdout_buffer = StreamBuffer(max_size=1024 * 1024)  # 1MB buffer
        self._stderr_buffer = StreamBuffer(max_size=256 * 1024)   # 256KB buffer for errors
        self._parser = JSONLParser()
        self._write_lock = asyncio.Lock()
        
    async def connect(self) -> None:
        """Launch subprocess and establish STDIO connection"""
        if self.state == ConnectionState.CONNECTED:
            return
            
        try:
            self.state = ConnectionState.CONNECTING
            logger.info(f"Launching process: {self.command}")
            
            # Prepare environment
            process_env = {**os.environ, **self.env}
            
            # Create subprocess
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=self.cwd
            )
            
            # Start receive tasks
            self._receive_task = asyncio.create_task(self._receive_stdout_loop())
            self._error_task = asyncio.create_task(self._receive_stderr_loop())
            
            # Wait a bit for process to start
            await asyncio.sleep(0.1)
            
            # Check if process is still running
            if self._process.returncode is not None:
                stderr = await self._read_stderr()
                raise TransportError(f"Process exited immediately with code {self._process.returncode}: {stderr}")
            
            await self._handle_connect()
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            if self._process:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
            raise TransportError(f"Failed to connect process STDIO: {e}")
            
    async def disconnect(self) -> None:
        """Terminate subprocess and close STDIO connection"""
        if self.state in (ConnectionState.DISCONNECTED, ConnectionState.CLOSED):
            return
            
        try:
            self.state = ConnectionState.CLOSING
            logger.info("Disconnecting process STDIO transport")
            
            # Cancel receive tasks
            for task in [self._receive_task, self._error_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    
            # Terminate process
            if self._process and self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Process did not terminate, killing")
                    self._process.kill()
                    await self._process.wait()
                    
            await self._handle_close()
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self.state = ConnectionState.ERROR
            raise TransportError(f"Failed to disconnect process STDIO: {e}")
            
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message through process STDIO"""
        if self.state != ConnectionState.CONNECTED:
            raise TransportError(f"Cannot send message in state: {self.state}")
            
        if not self._process or self._process.returncode is not None:
            raise TransportError("Process not running")
            
        try:
            # Serialize message
            data = json.dumps(message, separators=(',', ':'))
            line = data + '\n'
            
            # Write with lock to ensure atomic writes
            async with self._write_lock:
                self._process.stdin.write(line.encode('utf-8'))
                await self._process.stdin.drain()
                
            self._stats["messages_sent"] += 1
            logger.debug(f"Sent message: {message.get('method', message.get('id'))}")
            
        except Exception as e:
            await self._handle_error(e)
            raise TransportError(f"Failed to send message: {e}")
            
    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from process STDIO"""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Check if process is still running
                if self._process and self._process.returncode is not None:
                    stderr = await self._read_stderr()
                    raise TransportError(f"Process exited with code {self._process.returncode}: {stderr}")
                
                # Read from buffer
                if self._stdout_buffer.has_complete_line():
                    line = await self._stdout_buffer.read_line()
                    if line:
                        try:
                            message = self._parser.parse_line(line)
                            if message:
                                yield message
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON received: {e}")
                            logger.debug(f"Invalid line: {line}")
                            await self._handle_error(e)
                else:
                    # Wait for more data
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                await self._handle_error(e)
                if self.state == ConnectionState.CONNECTED:
                    logger.error(f"Error receiving message: {e}")
                    
    async def _receive_stdout_loop(self) -> None:
        """Background task to read from process stdout into buffer"""
        try:
            while self.state == ConnectionState.CONNECTED and self._process:
                # Read data from stdout
                data = await self._process.stdout.read(4096)
                if not data:
                    # EOF reached
                    logger.info("Process stdout EOF reached")
                    break
                    
                # Add to buffer
                await self._stdout_buffer.write(data)
                
        except asyncio.CancelledError:
            logger.debug("Stdout receive loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Stdout receive loop error: {e}")
            await self._handle_error(e)
        finally:
            # Trigger disconnect if still connected
            if self.state == ConnectionState.CONNECTED:
                await self.disconnect()
                
    async def _receive_stderr_loop(self) -> None:
        """Background task to read from process stderr"""
        try:
            while self.state == ConnectionState.CONNECTED and self._process:
                # Read data from stderr
                data = await self._process.stderr.read(4096)
                if not data:
                    # EOF reached
                    break
                    
                # Add to buffer and log
                await self._stderr_buffer.write(data)
                
                # Log stderr output
                try:
                    text = data.decode('utf-8', errors='replace').strip()
                    if text:
                        logger.warning(f"Process stderr: {text}")
                except Exception:
                    pass
                
        except asyncio.CancelledError:
            logger.debug("Stderr receive loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Stderr receive loop error: {e}")
            
    async def _read_stderr(self) -> str:
        """Read accumulated stderr output"""
        lines = []
        while self._stderr_buffer.has_complete_line():
            line = await self._stderr_buffer.read_line()
            if line:
                lines.append(line)
        return '\n'.join(lines)
        
    @asynccontextmanager
    async def session(self):
        """Context manager for process STDIO session"""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
            
    def get_process_info(self) -> Dict[str, Any]:
        """Get process information"""
        info = {
            "command": self.command,
            "args": self.args,
            "state": self.state.value,
            "pid": None,
            "returncode": None
        }
        
        if self._process:
            info["pid"] = self._process.pid
            info["returncode"] = self._process.returncode
            
        return info
        
    def __repr__(self) -> str:
        return f"ProcessStdioTransport(command={self.command}, state={self.state.value})"