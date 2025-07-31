"""
Async stream reader for Shannon MCP Server.

This module provides advanced async stream reading with:
- Multiple stream source management
- Line-based and chunk-based reading
- Flow control and backpressure handling
- Stream multiplexing/demultiplexing
- Pattern-based reading
- Error recovery
"""

import asyncio
from typing import Optional, Dict, Any, List, AsyncIterator, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import io
import re
from contextlib import asynccontextmanager

from .buffer import StreamBuffer
from ..utils.logging import get_logger
from ..utils.errors import StreamError, TimeoutError

logger = get_logger("shannon-mcp.stream-reader")


class StreamState(Enum):
    """Stream state."""
    IDLE = "idle"
    READING = "reading"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"


class ReadMode(Enum):
    """Stream reading mode."""
    LINE = "line"          # Read complete lines
    CHUNK = "chunk"        # Read fixed-size chunks
    PATTERN = "pattern"    # Read until pattern match
    ALL = "all"           # Read all available data


@dataclass
class StreamSource:
    """Individual stream source."""
    name: str
    stream: asyncio.StreamReader
    buffer: StreamBuffer
    state: StreamState = StreamState.IDLE
    priority: int = 0  # Higher priority streams are read first
    encoding: str = "utf-8"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Statistics
    bytes_read: int = 0
    lines_read: int = 0
    errors_count: int = 0
    last_read: Optional[datetime] = None
    
    # Callbacks
    on_data: Optional[Callable[[bytes], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    on_close: Optional[Callable[[], None]] = None


class AsyncStreamReader:
    """Advanced async stream reader with multiplexing support."""
    
    def __init__(
        self,
        max_line_length: int = 1024 * 1024,  # 1MB
        buffer_size: int = 64 * 1024,        # 64KB
        read_timeout: float = 30.0,
        concurrent_reads: int = 10
    ):
        """
        Initialize async stream reader.
        
        Args:
            max_line_length: Maximum line length
            buffer_size: Buffer size for reads
            read_timeout: Default read timeout
            concurrent_reads: Max concurrent stream reads
        """
        self.max_line_length = max_line_length
        self.buffer_size = buffer_size
        self.read_timeout = read_timeout
        self.concurrent_reads = concurrent_reads
        
        self._sources: Dict[str, StreamSource] = {}
        self._read_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(concurrent_reads)
        self._running = False
        self._lock = asyncio.Lock()
    
    async def add_source(
        self,
        name: str,
        stream: asyncio.StreamReader,
        priority: int = 0,
        encoding: str = "utf-8",
        on_data: Optional[Callable[[bytes], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        **metadata
    ) -> StreamSource:
        """
        Add a stream source.
        
        Args:
            name: Source name
            stream: Async stream reader
            priority: Source priority
            encoding: Text encoding
            on_data: Data callback
            on_error: Error callback
            on_close: Close callback
            **metadata: Additional metadata
            
        Returns:
            Created stream source
        """
        async with self._lock:
            if name in self._sources:
                raise StreamError(f"Source '{name}' already exists")
            
            buffer = StreamBuffer(
                stream,
                max_size=self.buffer_size,
                max_line_length=self.max_line_length
            )
            
            source = StreamSource(
                name=name,
                stream=stream,
                buffer=buffer,
                priority=priority,
                encoding=encoding,
                metadata=metadata,
                on_data=on_data,
                on_error=on_error,
                on_close=on_close
            )
            
            self._sources[name] = source
            
            logger.info(
                "stream_source_added",
                name=name,
                priority=priority,
                encoding=encoding
            )
            
            return source
    
    async def remove_source(self, name: str) -> None:
        """Remove a stream source."""
        async with self._lock:
            source = self._sources.pop(name, None)
            if not source:
                return
            
            # Cancel read task if running
            task = self._read_tasks.pop(name, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Mark as closed
            source.state = StreamState.CLOSED
            if source.on_close:
                try:
                    source.on_close()
                except Exception as e:
                    logger.error(
                        "close_callback_error",
                        name=name,
                        error=str(e)
                    )
            
            logger.info("stream_source_removed", name=name)
    
    async def read_line(
        self,
        source_name: str,
        timeout: Optional[float] = None
    ) -> Optional[str]:
        """
        Read a line from a source.
        
        Args:
            source_name: Source to read from
            timeout: Read timeout
            
        Returns:
            Line or None if EOF
        """
        source = self._sources.get(source_name)
        if not source:
            raise StreamError(f"Source '{source_name}' not found")
        
        if source.state == StreamState.CLOSED:
            return None
        
        source.state = StreamState.READING
        source.last_read = datetime.utcnow()
        
        try:
            line = await asyncio.wait_for(
                source.buffer.read_line(),
                timeout=timeout or self.read_timeout
            )
            
            if line is None:
                source.state = StreamState.CLOSED
                return None
            
            source.lines_read += 1
            source.bytes_read += len(line)
            
            if source.on_data:
                try:
                    source.on_data(line)
                except Exception as e:
                    logger.error(
                        "data_callback_error",
                        name=source_name,
                        error=str(e)
                    )
            
            source.state = StreamState.IDLE
            return line.decode(source.encoding, errors='replace')
            
        except asyncio.TimeoutError:
            source.state = StreamState.IDLE
            raise TimeoutError(f"Read timeout on source '{source_name}'")
        except Exception as e:
            source.state = StreamState.ERROR
            source.errors_count += 1
            if source.on_error:
                try:
                    source.on_error(e)
                except Exception as cb_error:
                    logger.error(
                        "error_callback_error",
                        name=source_name,
                        error=str(cb_error)
                    )
            raise
    
    async def read_chunk(
        self,
        source_name: str,
        size: int,
        timeout: Optional[float] = None
    ) -> Optional[bytes]:
        """
        Read a chunk from a source.
        
        Args:
            source_name: Source to read from
            size: Chunk size
            timeout: Read timeout
            
        Returns:
            Chunk or None if EOF
        """
        source = self._sources.get(source_name)
        if not source:
            raise StreamError(f"Source '{source_name}' not found")
        
        if source.state == StreamState.CLOSED:
            return None
        
        source.state = StreamState.READING
        source.last_read = datetime.utcnow()
        
        try:
            chunk = await asyncio.wait_for(
                source.buffer.read(size),
                timeout=timeout or self.read_timeout
            )
            
            if not chunk:
                source.state = StreamState.CLOSED
                return None
            
            source.bytes_read += len(chunk)
            
            if source.on_data:
                try:
                    source.on_data(chunk)
                except Exception as e:
                    logger.error(
                        "data_callback_error",
                        name=source_name,
                        error=str(e)
                    )
            
            source.state = StreamState.IDLE
            return chunk
            
        except asyncio.TimeoutError:
            source.state = StreamState.IDLE
            raise TimeoutError(f"Read timeout on source '{source_name}'")
        except Exception as e:
            source.state = StreamState.ERROR
            source.errors_count += 1
            if source.on_error:
                try:
                    source.on_error(e)
                except Exception:
                    pass
            raise
    
    async def read_until_pattern(
        self,
        source_name: str,
        pattern: Union[str, re.Pattern],
        timeout: Optional[float] = None,
        max_size: int = 1024 * 1024  # 1MB
    ) -> Optional[str]:
        """
        Read until pattern match.
        
        Args:
            source_name: Source to read from
            pattern: Pattern to match
            timeout: Read timeout
            max_size: Maximum read size
            
        Returns:
            Data up to and including pattern, or None if EOF
        """
        source = self._sources.get(source_name)
        if not source:
            raise StreamError(f"Source '{source_name}' not found")
        
        if isinstance(pattern, str):
            pattern = re.compile(pattern.encode(source.encoding))
        elif isinstance(pattern, re.Pattern) and isinstance(pattern.pattern, str):
            pattern = re.compile(pattern.pattern.encode(source.encoding))
        
        buffer = bytearray()
        start_time = asyncio.get_event_loop().time()
        timeout_val = timeout or self.read_timeout
        
        while True:
            remaining_time = timeout_val - (asyncio.get_event_loop().time() - start_time)
            if remaining_time <= 0:
                raise TimeoutError(f"Pattern read timeout on source '{source_name}'")
            
            chunk = await self.read_chunk(source_name, 1024, remaining_time)
            if chunk is None:
                return None
            
            buffer.extend(chunk)
            
            # Check for pattern
            match = pattern.search(buffer)
            if match:
                # Return data up to and including match
                result = buffer[:match.end()]
                # Put remaining data back
                remaining = buffer[match.end():]
                if remaining:
                    source.buffer._buffer = remaining + source.buffer._buffer
                return result.decode(source.encoding, errors='replace')
            
            # Check max size
            if len(buffer) > max_size:
                raise StreamError(f"Pattern not found within {max_size} bytes")
    
    async def read_all_lines(
        self,
        source_name: str,
        max_lines: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Read all lines from a source.
        
        Args:
            source_name: Source to read from
            max_lines: Maximum lines to read
            
        Yields:
            Lines from the source
        """
        lines_read = 0
        while True:
            if max_lines and lines_read >= max_lines:
                break
            
            line = await self.read_line(source_name)
            if line is None:
                break
            
            yield line
            lines_read += 1
    
    async def multiplex_sources(
        self,
        sources: Optional[List[str]] = None,
        mode: ReadMode = ReadMode.LINE,
        timeout: Optional[float] = None
    ) -> AsyncIterator[Tuple[str, Union[str, bytes]]]:
        """
        Read from multiple sources concurrently.
        
        Args:
            sources: Source names (None for all)
            mode: Read mode
            timeout: Read timeout per operation
            
        Yields:
            (source_name, data) tuples
        """
        source_names = sources or list(self._sources.keys())
        
        # Sort by priority
        source_names.sort(
            key=lambda n: self._sources[n].priority,
            reverse=True
        )
        
        async def read_source(name: str):
            try:
                if mode == ReadMode.LINE:
                    data = await self.read_line(name, timeout)
                elif mode == ReadMode.CHUNK:
                    data = await self.read_chunk(name, self.buffer_size, timeout)
                else:
                    raise ValueError(f"Unsupported mode for multiplexing: {mode}")
                
                if data is not None:
                    return (name, data)
                return None
            except Exception as e:
                logger.error(
                    "multiplex_read_error",
                    source=name,
                    error=str(e)
                )
                return None
        
        # Read from all sources concurrently
        while True:
            tasks = []
            for name in source_names:
                source = self._sources.get(name)
                if source and source.state != StreamState.CLOSED:
                    tasks.append(read_source(name))
            
            if not tasks:
                break
            
            # Wait for first result
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Yield results
            for task in done:
                result = await task
                if result:
                    yield result
    
    async def pause_source(self, source_name: str) -> None:
        """Pause reading from a source."""
        source = self._sources.get(source_name)
        if source:
            source.state = StreamState.PAUSED
            logger.info("stream_source_paused", name=source_name)
    
    async def resume_source(self, source_name: str) -> None:
        """Resume reading from a source."""
        source = self._sources.get(source_name)
        if source and source.state == StreamState.PAUSED:
            source.state = StreamState.IDLE
            logger.info("stream_source_resumed", name=source_name)
    
    def get_source_stats(self, source_name: str) -> Dict[str, Any]:
        """Get statistics for a source."""
        source = self._sources.get(source_name)
        if not source:
            return {}
        
        return {
            "state": source.state.value,
            "bytes_read": source.bytes_read,
            "lines_read": source.lines_read,
            "errors_count": source.errors_count,
            "last_read": source.last_read.isoformat() if source.last_read else None,
            "buffer_size": len(source.buffer._buffer)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all sources."""
        return {
            name: self.get_source_stats(name)
            for name in self._sources
        }
    
    @asynccontextmanager
    async def stream_context(self, source_name: str):
        """Context manager for stream operations."""
        try:
            yield self._sources.get(source_name)
        finally:
            # Ensure stream is in valid state
            source = self._sources.get(source_name)
            if source and source.state == StreamState.READING:
                source.state = StreamState.IDLE
    
    async def close_all(self) -> None:
        """Close all sources."""
        source_names = list(self._sources.keys())
        for name in source_names:
            await self.remove_source(name)
        
        logger.info("all_stream_sources_closed")


# Convenience function for creating readers
async def create_subprocess_reader(
    process: asyncio.subprocess.Process,
    read_stdout: bool = True,
    read_stderr: bool = True,
    **kwargs
) -> AsyncStreamReader:
    """
    Create a stream reader for subprocess streams.
    
    Args:
        process: Subprocess
        read_stdout: Read from stdout
        read_stderr: Read from stderr
        **kwargs: Additional reader arguments
        
    Returns:
        Configured stream reader
    """
    reader = AsyncStreamReader(**kwargs)
    
    if read_stdout and process.stdout:
        await reader.add_source(
            "stdout",
            process.stdout,
            priority=10
        )
    
    if read_stderr and process.stderr:
        await reader.add_source(
            "stderr",
            process.stderr,
            priority=5
        )
    
    return reader


# Export public API
__all__ = [
    'AsyncStreamReader',
    'StreamSource',
    'StreamState',
    'ReadMode',
    'create_subprocess_reader',
]