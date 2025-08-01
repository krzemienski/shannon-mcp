"""
JSONL Streaming Processor for Shannon MCP Server.

Handles real-time streaming of JSON Lines with backpressure and error recovery.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable, AsyncIterator, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import traceback

from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.streaming.jsonl")


class StreamState(Enum):
    """Stream states."""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class StreamMetrics:
    """Metrics for stream performance."""
    messages_sent: int = 0
    messages_failed: int = 0
    bytes_sent: int = 0
    start_time: Optional[datetime] = None
    last_message_time: Optional[datetime] = None
    backpressure_events: int = 0
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "bytes_sent": self.bytes_sent,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "backpressure_events": self.backpressure_events,
            "error_count": self.error_count,
            "duration_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0,
            "messages_per_second": self.messages_sent / max((datetime.now(timezone.utc) - self.start_time).total_seconds(), 1) if self.start_time else 0
        }


@dataclass
class StreamConfig:
    """Configuration for JSONL streaming."""
    buffer_size: int = 1000
    max_buffer_size: int = 10000
    backpressure_threshold: float = 0.8  # Trigger backpressure at 80% buffer full
    retry_attempts: int = 3
    retry_delay: float = 1.0
    batch_size: int = 10
    flush_interval: float = 0.1
    enable_compression: bool = False
    enable_metrics: bool = True


class JSONLProcessor:
    """Processes JSONL streaming with backpressure and error handling."""
    
    def __init__(
        self,
        stream_id: str,
        writer: asyncio.StreamWriter,
        config: Optional[StreamConfig] = None,
        error_handler: Optional[Callable] = None
    ):
        """Initialize JSONL processor."""
        self.stream_id = stream_id
        self.writer = writer
        self.config = config or StreamConfig()
        self.error_handler = error_handler
        
        self.state = StreamState.IDLE
        self.buffer: List[Dict[str, Any]] = []
        self.metrics = StreamMetrics()
        
        self._flush_task: Optional[asyncio.Task] = None
        self._backpressure_event = asyncio.Event()
        self._backpressure_event.set()  # Initially not under backpressure
        
        self._closed = False
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """Start the JSONL processor."""
        if self.state != StreamState.IDLE:
            return
        
        logger.info(f"Starting JSONL processor for stream {self.stream_id}")
        
        self.state = StreamState.STREAMING
        self.metrics.start_time = datetime.now(timezone.utc)
        
        # Start flush task
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def stop(self) -> None:
        """Stop the JSONL processor."""
        if self.state == StreamState.CLOSED:
            return
        
        logger.info(f"Stopping JSONL processor for stream {self.stream_id}")
        
        self.state = StreamState.CLOSED
        self._closed = True
        
        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining buffer
        await self._flush_buffer()
        
        # Close writer
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except:
                pass
    
    async def send_message(
        self,
        message: Dict[str, Any],
        priority: int = 5,
        retry: bool = True
    ) -> bool:
        """Send a message through the stream."""
        if self._closed or self.state == StreamState.CLOSED:
            return False
        
        # Wait for backpressure to clear
        await self._backpressure_event.wait()
        
        # Add timestamp and metadata
        enriched_message = {
            **message,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
            "_stream_id": self.stream_id,
            "_priority": priority
        }
        
        async with self._lock:
            # Check buffer capacity
            if len(self.buffer) >= self.config.max_buffer_size:
                logger.warning(f"Buffer overflow for stream {self.stream_id}")
                self.metrics.messages_failed += 1
                return False
            
            # Add to buffer
            self.buffer.append(enriched_message)
            
            # Check backpressure threshold
            if len(self.buffer) >= self.config.buffer_size * self.config.backpressure_threshold:
                self._backpressure_event.clear()
                self.metrics.backpressure_events += 1
                logger.debug(f"Backpressure triggered for stream {self.stream_id}")
        
        return True
    
    async def send_batch(
        self,
        messages: List[Dict[str, Any]],
        priority: int = 5
    ) -> int:
        """Send a batch of messages."""
        sent_count = 0
        
        for message in messages:
            if await self.send_message(message, priority):
                sent_count += 1
            else:
                break
        
        return sent_count
    
    async def send_error(
        self,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send an error message."""
        error_msg = {
            "type": "error",
            "error": {
                "code": error_code,
                "message": error_message,
                "details": details or {}
            }
        }
        
        return await self.send_message(error_msg, priority=1)  # High priority
    
    async def send_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        priority: int = 5
    ) -> bool:
        """Send an event message."""
        event_msg = {
            "type": "event",
            "event": event_type,
            "data": data
        }
        
        return await self.send_message(event_msg, priority)
    
    async def send_response(
        self,
        request_id: str,
        result: Any,
        priority: int = 5
    ) -> bool:
        """Send a response message."""
        response_msg = {
            "type": "response",
            "id": request_id,
            "result": result
        }
        
        return await self.send_message(response_msg, priority)
    
    async def pause(self) -> None:
        """Pause streaming."""
        if self.state == StreamState.STREAMING:
            self.state = StreamState.PAUSED
            logger.info(f"Paused stream {self.stream_id}")
    
    async def resume(self) -> None:
        """Resume streaming."""
        if self.state == StreamState.PAUSED:
            self.state = StreamState.STREAMING
            logger.info(f"Resumed stream {self.stream_id}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get stream metrics."""
        return self.metrics.to_dict()
    
    def get_state(self) -> Dict[str, Any]:
        """Get stream state."""
        return {
            "stream_id": self.stream_id,
            "state": self.state.value,
            "buffer_size": len(self.buffer),
            "buffer_capacity": self.config.buffer_size,
            "backpressure_active": not self._backpressure_event.is_set(),
            "closed": self._closed
        }
    
    async def wait_for_backpressure_clear(self, timeout: Optional[float] = None) -> bool:
        """Wait for backpressure to clear."""
        try:
            await asyncio.wait_for(self._backpressure_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    # Private methods
    
    async def _flush_loop(self) -> None:
        """Background task to flush buffer."""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.flush_interval)
                
                if self.state == StreamState.STREAMING:
                    await self._flush_buffer()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error for stream {self.stream_id}: {e}")
                await self._handle_error(e)
    
    async def _flush_buffer(self) -> None:
        """Flush messages from buffer to stream."""
        if not self.buffer or self._closed:
            return
        
        async with self._lock:
            # Get messages to send
            batch_size = min(len(self.buffer), self.config.batch_size)
            if batch_size == 0:
                return
            
            messages_to_send = self.buffer[:batch_size]
            
            # Send messages
            success_count = 0
            for message in messages_to_send:
                if await self._send_single_message(message):
                    success_count += 1
                else:
                    break
            
            # Remove sent messages from buffer
            if success_count > 0:
                self.buffer = self.buffer[success_count:]
                
                # Clear backpressure if buffer is below threshold
                if (len(self.buffer) < self.config.buffer_size * self.config.backpressure_threshold 
                    and not self._backpressure_event.is_set()):
                    self._backpressure_event.set()
                    logger.debug(f"Backpressure cleared for stream {self.stream_id}")
    
    async def _send_single_message(self, message: Dict[str, Any]) -> bool:
        """Send a single message to the stream."""
        if self._closed or not self.writer:
            return False
        
        try:
            # Serialize message
            json_line = json.dumps(message, separators=(',', ':'), ensure_ascii=False)
            data = (json_line + '\n').encode('utf-8')
            
            # Write to stream
            self.writer.write(data)
            await self.writer.drain()
            
            # Update metrics
            self.metrics.messages_sent += 1
            self.metrics.bytes_sent += len(data)
            self.metrics.last_message_time = datetime.now(timezone.utc)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message on stream {self.stream_id}: {e}")
            self.metrics.messages_failed += 1
            self.metrics.error_count += 1
            
            await self._handle_error(e)
            return False
    
    async def _handle_error(self, error: Exception) -> None:
        """Handle streaming errors."""
        logger.error(f"Stream error on {self.stream_id}: {error}")
        
        self.state = StreamState.ERROR
        
        # Call error handler if provided
        if self.error_handler:
            try:
                await self.error_handler(self.stream_id, error)
            except Exception as handler_error:
                logger.error(f"Error handler failed: {handler_error}")
        
        # Try to recover
        await self._attempt_recovery()
    
    async def _attempt_recovery(self) -> None:
        """Attempt to recover from error state."""
        if self._closed:
            return
        
        logger.info(f"Attempting recovery for stream {self.stream_id}")
        
        # Wait a bit before recovery
        await asyncio.sleep(self.config.retry_delay)
        
        # Check if writer is still valid
        if self.writer and not self.writer.is_closing():
            self.state = StreamState.STREAMING
            logger.info(f"Recovered stream {self.stream_id}")
        else:
            logger.error(f"Could not recover stream {self.stream_id} - writer is closed")
            await self.stop()


class JSONLStreamManager:
    """Manages multiple JSONL streams."""
    
    def __init__(self, default_config: Optional[StreamConfig] = None):
        """Initialize stream manager."""
        self.default_config = default_config or StreamConfig()
        self.streams: Dict[str, JSONLProcessor] = {}
        self._lock = asyncio.Lock()
    
    async def create_stream(
        self,
        stream_id: str,
        writer: asyncio.StreamWriter,
        config: Optional[StreamConfig] = None,
        error_handler: Optional[Callable] = None
    ) -> JSONLProcessor:
        """Create a new JSONL stream."""
        async with self._lock:
            if stream_id in self.streams:
                raise ValueError(f"Stream {stream_id} already exists")
            
            processor = JSONLProcessor(
                stream_id=stream_id,
                writer=writer,
                config=config or self.default_config,
                error_handler=error_handler
            )
            
            self.streams[stream_id] = processor
            await processor.start()
            
            logger.info(f"Created JSONL stream {stream_id}")
            return processor
    
    async def get_stream(self, stream_id: str) -> Optional[JSONLProcessor]:
        """Get an existing stream."""
        return self.streams.get(stream_id)
    
    async def close_stream(self, stream_id: str) -> bool:
        """Close and remove a stream."""
        async with self._lock:
            processor = self.streams.get(stream_id)
            if not processor:
                return False
            
            await processor.stop()
            del self.streams[stream_id]
            
            logger.info(f"Closed JSONL stream {stream_id}")
            return True
    
    async def broadcast_message(
        self,
        message: Dict[str, Any],
        stream_filter: Optional[Callable[[str], bool]] = None,
        priority: int = 5
    ) -> Dict[str, bool]:
        """Broadcast message to multiple streams."""
        results = {}
        
        for stream_id, processor in self.streams.items():
            if stream_filter and not stream_filter(stream_id):
                continue
            
            results[stream_id] = await processor.send_message(message, priority)
        
        return results
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all streams."""
        return {
            stream_id: processor.get_metrics()
            for stream_id, processor in self.streams.items()
        }
    
    async def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state for all streams."""
        return {
            stream_id: processor.get_state()
            for stream_id, processor in self.streams.items()
        }
    
    async def cleanup_closed_streams(self) -> int:
        """Remove closed streams from manager."""
        closed_streams = []
        
        for stream_id, processor in self.streams.items():
            if processor.state == StreamState.CLOSED:
                closed_streams.append(stream_id)
        
        async with self._lock:
            for stream_id in closed_streams:
                del self.streams[stream_id]
        
        if closed_streams:
            logger.info(f"Cleaned up {len(closed_streams)} closed streams")
        
        return len(closed_streams)
    
    async def close_all_streams(self) -> None:
        """Close all managed streams."""
        logger.info("Closing all JSONL streams")
        
        # Close all streams concurrently
        tasks = [
            processor.stop()
            for processor in self.streams.values()
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        async with self._lock:
            self.streams.clear()
        
        logger.info("All JSONL streams closed")


# Utility functions

async def create_jsonl_reader(
    reader: asyncio.StreamReader,
    message_handler: Callable[[Dict[str, Any]], None],
    error_handler: Optional[Callable[[Exception], None]] = None
) -> None:
    """Create a JSONL reader that processes incoming messages."""
    logger.info("Starting JSONL reader")
    
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            
            try:
                # Parse JSON line
                message = json.loads(line.decode('utf-8').strip())
                await message_handler(message)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON line: {e}")
                if error_handler:
                    await error_handler(e)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
                if error_handler:
                    await error_handler(e)
                    
    except Exception as e:
        logger.error(f"JSONL reader error: {e}")
        if error_handler:
            await error_handler(e)
    
    logger.info("JSONL reader stopped")


def serialize_jsonl_message(message: Dict[str, Any]) -> str:
    """Serialize message to JSONL format."""
    return json.dumps(message, separators=(',', ':'), ensure_ascii=False)


def parse_jsonl_message(line: str) -> Dict[str, Any]:
    """Parse JSONL message from string."""
    return json.loads(line.strip())