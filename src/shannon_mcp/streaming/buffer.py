"""
Stream buffer for Shannon MCP Server.

This module provides buffering for async streams with:
- Efficient line buffering
- Backpressure handling
- Memory management
- Partial line handling
"""

import asyncio
from typing import Optional, List, AsyncIterator
from collections import deque
import structlog

from ..utils.logging import get_logger
from ..utils.errors import StreamError

logger = get_logger("shannon-mcp.buffer")


class StreamBuffer:
    """Buffers stream data and extracts complete lines."""
    
    def __init__(
        self,
        stream: asyncio.StreamReader,
        buffer_size: int = 1024 * 1024,  # 1MB default
        max_line_length: int = 1024 * 1024  # 1MB max line
    ):
        """
        Initialize stream buffer.
        
        Args:
            stream: Async stream to read from
            buffer_size: Maximum buffer size
            max_line_length: Maximum line length
        """
        self.stream = stream
        self.max_size = buffer_size
        self.max_line_length = max_line_length
        
        # Buffers
        self._buffer = bytearray()
        self._lines: deque[str] = deque()
        self._partial_line = ""
        
        # Stats
        self._total_bytes = 0
        self._total_lines = 0
        self._overflow_count = 0
    
    @property
    def size(self) -> int:
        """Current buffer size in bytes."""
        return len(self._buffer)
    
    @property
    def line_count(self) -> int:
        """Number of complete lines buffered."""
        return len(self._lines)
    
    async def read(self, chunk_size: int = 8192) -> bytes:
        """
        Read data from stream into buffer.
        
        Args:
            chunk_size: Size of chunk to read
            
        Returns:
            Bytes read (empty if EOF)
            
        Raises:
            StreamError: If buffer overflow
        """
        # Check buffer space
        if self.size >= self.max_size:
            self._overflow_count += 1
            raise StreamError(
                f"Buffer overflow: {self.size} bytes exceeds max {self.max_size}"
            )
        
        # Read chunk
        try:
            chunk = await self.stream.read(chunk_size)
            
            if chunk:
                self._buffer.extend(chunk)
                self._total_bytes += len(chunk)
                self._extract_lines()
            
            return chunk
            
        except asyncio.LimitOverrunError as e:
            logger.error(
                "stream_limit_overrun",
                limit=e.consumed,
                chunk_size=chunk_size
            )
            raise StreamError(f"Stream limit overrun: {e.consumed} bytes") from e
        except Exception as e:
            logger.error(
                "stream_read_error",
                error=str(e),
                chunk_size=chunk_size
            )
            raise StreamError(f"Stream read error: {str(e)}") from e
    
    def _extract_lines(self) -> None:
        """Extract complete lines from buffer."""
        # Find newlines
        while b'\n' in self._buffer:
            # Find line end
            line_end = self._buffer.index(b'\n')
            
            # Extract line
            line_bytes = self._buffer[:line_end]
            
            # Remove from buffer (including newline)
            del self._buffer[:line_end + 1]
            
            # Decode line
            try:
                line = line_bytes.decode('utf-8', errors='replace')
                
                # Handle partial line from previous read
                if self._partial_line:
                    line = self._partial_line + line
                    self._partial_line = ""
                
                # Check line length
                if len(line) > self.max_line_length:
                    logger.warning(
                        "line_too_long",
                        length=len(line),
                        max_length=self.max_line_length
                    )
                    # Truncate line
                    line = line[:self.max_line_length] + "... [truncated]"
                
                # Add to line queue
                self._lines.append(line)
                self._total_lines += 1
                
            except UnicodeDecodeError as e:
                logger.error(
                    "decode_error",
                    error=str(e),
                    line_length=len(line_bytes)
                )
                # Skip malformed line
                continue
        
        # Handle remaining partial line
        if self._buffer:
            try:
                self._partial_line = self._buffer.decode('utf-8', errors='replace')
                self._buffer.clear()
            except UnicodeDecodeError:
                # Keep as bytes for next read
                pass
    
    def get_line(self) -> Optional[str]:
        """
        Get next complete line.
        
        Returns:
            Complete line or None if no lines available
        """
        if self._lines:
            return self._lines.popleft()
        return None
    
    def get_complete_lines(self) -> List[str]:
        """
        Get all complete lines.
        
        Returns:
            List of complete lines
        """
        lines = list(self._lines)
        self._lines.clear()
        return lines
    
    async def read_until_line(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Read until a complete line is available.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Complete line or None if timeout/EOF
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check for existing line
            line = self.get_line()
            if line is not None:
                return line
            
            # Check timeout
            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    return None
                remaining = timeout - elapsed
            else:
                remaining = None
            
            # Read more data
            try:
                chunk = await asyncio.wait_for(
                    self.read(),
                    timeout=remaining
                )
                
                if not chunk:
                    # EOF - return partial line if exists
                    if self._partial_line:
                        line = self._partial_line
                        self._partial_line = ""
                        return line
                    return None
                    
            except asyncio.TimeoutError:
                return None
    
    async def read_all_lines(self) -> AsyncIterator[str]:
        """
        Read all lines from stream.
        
        Yields:
            Complete lines as they become available
        """
        while True:
            # Yield buffered lines
            while self._lines:
                yield self._lines.popleft()
            
            # Read more data
            chunk = await self.read()
            if not chunk:
                # EOF - yield final partial line if exists
                if self._partial_line:
                    yield self._partial_line
                    self._partial_line = ""
                break
    
    def flush(self) -> List[str]:
        """
        Flush buffer and return all data.
        
        Returns:
            All buffered lines plus partial data
        """
        lines = list(self._lines)
        self._lines.clear()
        
        # Add partial line if exists
        if self._partial_line:
            lines.append(self._partial_line)
            self._partial_line = ""
        
        # Add remaining buffer data
        if self._buffer:
            try:
                lines.append(self._buffer.decode('utf-8', errors='replace'))
            except:
                # Ignore decode errors on flush
                pass
            self._buffer.clear()
        
        return lines
    
    def clear(self) -> None:
        """Clear all buffers."""
        self._buffer.clear()
        self._lines.clear()
        self._partial_line = ""
    
    def get_stats(self) -> dict:
        """Get buffer statistics."""
        return {
            "current_size": self.size,
            "max_size": self.max_size,
            "line_count": self.line_count,
            "total_bytes": self._total_bytes,
            "total_lines": self._total_lines,
            "overflow_count": self._overflow_count,
            "has_partial": bool(self._partial_line)
        }


class CircularBuffer:
    """Circular buffer for efficient streaming."""
    
    def __init__(self, size: int = 1024 * 1024):
        """
        Initialize circular buffer.
        
        Args:
            size: Buffer size in bytes
        """
        self.size = size
        self.buffer = bytearray(size)
        self.read_pos = 0
        self.write_pos = 0
        self.data_size = 0
    
    @property
    def available(self) -> int:
        """Bytes available to read."""
        return self.data_size
    
    @property
    def free_space(self) -> int:
        """Free space available."""
        return self.size - self.data_size
    
    def write(self, data: bytes) -> int:
        """
        Write data to buffer.
        
        Args:
            data: Data to write
            
        Returns:
            Bytes written
        """
        if not data:
            return 0
        
        # Calculate writable amount
        writable = min(len(data), self.free_space)
        
        if writable == 0:
            return 0
        
        # Write data
        if self.write_pos + writable <= self.size:
            # Simple write
            self.buffer[self.write_pos:self.write_pos + writable] = data[:writable]
            self.write_pos = (self.write_pos + writable) % self.size
        else:
            # Wrap around
            first_part = self.size - self.write_pos
            self.buffer[self.write_pos:] = data[:first_part]
            self.buffer[:writable - first_part] = data[first_part:writable]
            self.write_pos = writable - first_part
        
        self.data_size += writable
        return writable
    
    def read(self, size: int) -> bytes:
        """
        Read data from buffer.
        
        Args:
            size: Maximum bytes to read
            
        Returns:
            Data read
        """
        if self.data_size == 0:
            return b''
        
        # Calculate readable amount
        readable = min(size, self.data_size)
        
        # Read data
        if self.read_pos + readable <= self.size:
            # Simple read
            data = bytes(self.buffer[self.read_pos:self.read_pos + readable])
            self.read_pos = (self.read_pos + readable) % self.size
        else:
            # Wrap around
            first_part = self.size - self.read_pos
            data = bytes(self.buffer[self.read_pos:]) + bytes(self.buffer[:readable - first_part])
            self.read_pos = readable - first_part
        
        self.data_size -= readable
        return data
    
    def peek(self, size: int) -> bytes:
        """
        Peek at data without consuming.
        
        Args:
            size: Maximum bytes to peek
            
        Returns:
            Data peeked
        """
        if self.data_size == 0:
            return b''
        
        # Calculate readable amount
        readable = min(size, self.data_size)
        
        # Peek data
        if self.read_pos + readable <= self.size:
            # Simple peek
            return bytes(self.buffer[self.read_pos:self.read_pos + readable])
        else:
            # Wrap around
            first_part = self.size - self.read_pos
            return bytes(self.buffer[self.read_pos:]) + bytes(self.buffer[:readable - first_part])
    
    def clear(self) -> None:
        """Clear buffer."""
        self.read_pos = 0
        self.write_pos = 0
        self.data_size = 0


# Export public API
__all__ = ['StreamBuffer', 'CircularBuffer']