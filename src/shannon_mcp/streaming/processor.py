"""
Stream processor for Shannon MCP Server.

This module handles JSONL stream processing from Claude Code with:
- Async stream reading from subprocess
- JSONL parsing and validation
- Message type routing
- Backpressure handling
- Error recovery
- Metrics extraction
"""

import asyncio
import json
from typing import Optional, Dict, Any, Callable, AsyncIterator
from dataclasses import dataclass
import structlog
from datetime import datetime

from ..utils.logging import get_logger
from ..utils.errors import StreamError, ValidationError, handle_errors, error_context
from ..utils.notifications import emit, EventCategory, EventPriority
from .parser import JSONLParser
from .buffer import StreamBuffer

logger = get_logger("shannon-mcp.streaming")


@dataclass
class StreamMetrics:
    """Stream processing metrics."""
    lines_processed: int = 0
    messages_parsed: int = 0
    errors_encountered: int = 0
    bytes_processed: int = 0
    start_time: datetime = None
    last_activity: datetime = None
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()


class StreamProcessor:
    """Processes JSONL streams from Claude Code."""
    
    def __init__(self, session_manager):
        """
        Initialize stream processor.
        
        Args:
            session_manager: Parent session manager
        """
        self.session_manager = session_manager
        self.parser = JSONLParser()
        self.metrics = StreamMetrics()
        self._handlers: Dict[str, Callable] = self._setup_handlers()
        
    def _setup_handlers(self) -> Dict[str, Callable]:
        """Set up message type handlers."""
        return {
            "partial": self._handle_partial,
            "response": self._handle_response,
            "error": self._handle_error,
            "notification": self._handle_notification,
            "metric": self._handle_metric,
            "debug": self._handle_debug,
            "status": self._handle_status,
            "checkpoint": self._handle_checkpoint,
        }
    
    async def process_session(self, session) -> None:
        """
        Process stream for a session.
        
        Args:
            session: Session to process
        """
        if not session.process or not session.process.stdout:
            raise StreamError("No stdout stream available")
        
        self.metrics.start_time = datetime.utcnow()
        
        try:
            # Create stream buffer
            buffer = StreamBuffer(
                stream=session.process.stdout,
                buffer_size=self.session_manager.session_config.buffer_size
            )
            
            # Process stream
            async for line in self._read_stream(buffer, session):
                try:
                    await self._process_line(line, session)
                except Exception as e:
                    logger.error(
                        "line_processing_error",
                        session_id=session.id,
                        error=str(e),
                        line=line[:100]  # Log first 100 chars
                    )
                    self.metrics.errors_encountered += 1
                    session.metrics.errors_count += 1
            
            # Handle completion
            await self._handle_stream_complete(session)
            
        except asyncio.CancelledError:
            logger.info("stream_processing_cancelled", session_id=session.id)
            raise
        except Exception as e:
            logger.error(
                "stream_processing_error",
                session_id=session.id,
                error=str(e),
                exc_info=True
            )
            await self._handle_stream_error(session, e)
            raise
    
    async def _read_stream(
        self,
        buffer: StreamBuffer,
        session
    ) -> AsyncIterator[str]:
        """
        Read lines from stream with backpressure handling.
        
        Args:
            buffer: Stream buffer
            session: Current session
            
        Yields:
            Decoded lines from stream
        """
        chunk_size = self.session_manager.session_config.stream_chunk_size
        
        while True:
            try:
                # Read chunk with timeout
                chunk = await asyncio.wait_for(
                    buffer.read(chunk_size),
                    timeout=30.0  # 30 second timeout per chunk
                )
                
                if not chunk:
                    # End of stream
                    break
                
                # Update metrics
                self.metrics.bytes_processed += len(chunk)
                session.metrics.stream_bytes_received += len(chunk)
                
                # Process complete lines
                for line in buffer.get_complete_lines():
                    self.metrics.lines_processed += 1
                    self.metrics.update_activity()
                    yield line
                
                # Check backpressure
                if buffer.size > buffer.max_size * 0.8:
                    logger.warning(
                        "buffer_pressure_high",
                        session_id=session.id,
                        buffer_size=buffer.size,
                        max_size=buffer.max_size
                    )
                    # Give session time to process
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                logger.warning(
                    "stream_read_timeout",
                    session_id=session.id,
                    last_activity=self.metrics.last_activity
                )
                # Check if process is still alive
                if session.process.returncode is not None:
                    break
                continue
    
    async def _process_line(self, line: str, session) -> None:
        """
        Process a single line from the stream.
        
        Args:
            line: Line to process
            session: Current session
        """
        # Skip empty lines
        if not line.strip():
            return
        
        try:
            # Parse JSONL
            message = self.parser.parse_line(line)
            self.metrics.messages_parsed += 1
            
            # Extract message type
            msg_type = message.get("type", "unknown")
            
            # Route to handler
            handler = self._handlers.get(msg_type, self._handle_unknown)
            await handler(message, session)
            
            # Emit stream message event
            await emit(
                "stream_message",
                EventCategory.SESSION,
                {
                    "session_id": session.id,
                    "message_type": msg_type,
                    "message": message
                }
            )
            
        except json.JSONDecodeError as e:
            logger.warning(
                "invalid_jsonl",
                session_id=session.id,
                error=str(e),
                line=line[:100]
            )
            # Try to extract as plain text
            await self._handle_plain_text(line, session)
        except Exception as e:
            logger.error(
                "message_processing_error",
                session_id=session.id,
                error=str(e),
                message_type=message.get("type", "unknown") if 'message' in locals() else "unknown"
            )
            raise
    
    async def _handle_partial(self, message: Dict[str, Any], session) -> None:
        """Handle partial response message."""
        content = message.get("content", "")
        session._current_response += content
        
        # Update output buffer
        session._output_buffer.extend(content.encode())
        
        # Notify callbacks
        for callback in session._response_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(content, is_partial=True)
                else:
                    callback(content, is_partial=True)
            except Exception as e:
                logger.error(
                    "callback_error",
                    session_id=session.id,
                    error=str(e)
                )
    
    async def _handle_response(self, message: Dict[str, Any], session) -> None:
        """Handle complete response message."""
        content = message.get("content", "")
        
        # Add to messages
        session.add_message("assistant", content, **message.get("metadata", {}))
        
        # Reset current response
        session._current_response = ""
        
        # Update metrics
        if "token_count" in message:
            session.metrics.tokens_output += message["token_count"]
        
        # Notify callbacks
        for callback in session._response_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(content, is_partial=False)
                else:
                    callback(content, is_partial=False)
            except Exception as e:
                logger.error(
                    "callback_error",
                    session_id=session.id,
                    error=str(e)
                )
    
    async def _handle_error(self, message: Dict[str, Any], session) -> None:
        """Handle error message."""
        error_type = message.get("error_type", "unknown")
        error_msg = message.get("message", "Unknown error")
        
        logger.error(
            "claude_error",
            session_id=session.id,
            error_type=error_type,
            error_message=error_msg
        )
        
        session.error = f"{error_type}: {error_msg}"
        session.metrics.errors_count += 1
        
        # Emit error event
        await emit(
            "session_error",
            EventCategory.SESSION,
            {
                "session_id": session.id,
                "error_type": error_type,
                "error_message": error_msg
            },
            priority=EventPriority.HIGH
        )
    
    async def _handle_notification(self, message: Dict[str, Any], session) -> None:
        """Handle notification message."""
        notification_type = message.get("notification_type", "info")
        content = message.get("content", "")
        
        logger.info(
            "claude_notification",
            session_id=session.id,
            notification_type=notification_type,
            content=content
        )
        
        # Store in context
        if "notifications" not in session.context:
            session.context["notifications"] = []
        session.context["notifications"].append({
            "type": notification_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_metric(self, message: Dict[str, Any], session) -> None:
        """Handle metrics message."""
        metrics = message.get("data", {})
        
        # Update session metrics
        if "tokens_input" in metrics:
            session.metrics.tokens_input = metrics["tokens_input"]
        if "tokens_output" in metrics:
            session.metrics.tokens_output = metrics["tokens_output"]
        
        # Store additional metrics
        if "metrics" not in session.context:
            session.context["metrics"] = {}
        session.context["metrics"].update(metrics)
        
        logger.debug(
            "metrics_received",
            session_id=session.id,
            metrics=metrics
        )
    
    async def _handle_debug(self, message: Dict[str, Any], session) -> None:
        """Handle debug message."""
        debug_info = message.get("data", {})
        
        logger.debug(
            "claude_debug",
            session_id=session.id,
            debug_info=debug_info
        )
        
        # Store debug info if enabled
        if self.session_manager.session_config.enable_metrics:
            if "debug" not in session.context:
                session.context["debug"] = []
            session.context["debug"].append({
                "data": debug_info,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def _handle_status(self, message: Dict[str, Any], session) -> None:
        """Handle status message."""
        status = message.get("status", "unknown")
        details = message.get("details", {})
        
        logger.info(
            "session_status_update",
            session_id=session.id,
            status=status,
            details=details
        )
        
        # Update session state if needed
        status_to_state = {
            "thinking": SessionState.RUNNING,
            "typing": SessionState.RUNNING,
            "complete": SessionState.COMPLETING,
            "error": SessionState.FAILED,
        }
        
        if status in status_to_state:
            from ..managers.session import SessionState
            session.state = status_to_state[status]
    
    async def _handle_checkpoint(self, message: Dict[str, Any], session) -> None:
        """Handle checkpoint message."""
        checkpoint_id = message.get("checkpoint_id")
        checkpoint_data = message.get("data", {})
        
        logger.info(
            "checkpoint_received",
            session_id=session.id,
            checkpoint_id=checkpoint_id
        )
        
        # Update session checkpoint
        session.checkpoint_id = checkpoint_id
        
        # Store checkpoint data
        if "checkpoints" not in session.context:
            session.context["checkpoints"] = []
        session.context["checkpoints"].append({
            "id": checkpoint_id,
            "data": checkpoint_data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Emit checkpoint event
        await emit(
            "checkpoint_created",
            EventCategory.CHECKPOINT,
            {
                "session_id": session.id,
                "checkpoint_id": checkpoint_id,
                "data": checkpoint_data
            }
        )
    
    async def _handle_unknown(self, message: Dict[str, Any], session) -> None:
        """Handle unknown message type."""
        msg_type = message.get("type", "unknown")
        
        logger.warning(
            "unknown_message_type",
            session_id=session.id,
            message_type=msg_type,
            message=message
        )
        
        # Store for debugging
        if "unknown_messages" not in session.context:
            session.context["unknown_messages"] = []
        session.context["unknown_messages"].append(message)
    
    async def _handle_plain_text(self, line: str, session) -> None:
        """Handle plain text output (non-JSONL)."""
        # Append to current response
        session._current_response += line + "\n"
        
        # Store as debug output
        if "plain_output" not in session.context:
            session.context["plain_output"] = []
        session.context["plain_output"].append({
            "line": line,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_stream_complete(self, session) -> None:
        """Handle stream completion."""
        from ..managers.session import SessionState
        
        # Flush any remaining response
        if session._current_response:
            session.add_message("assistant", session._current_response)
            session._current_response = ""
        
        # Update session state
        if session.state == SessionState.RUNNING:
            session.state = SessionState.COMPLETED
        
        session.metrics.end_time = datetime.utcnow()
        
        # Save final state
        await self.session_manager._save_session(session)
        
        # Emit completion event
        await emit(
            "session_completed",
            EventCategory.SESSION,
            {
                "session_id": session.id,
                "duration": session.metrics.duration.total_seconds() if session.metrics.duration else 0,
                "tokens_total": session.metrics.tokens_input + session.metrics.tokens_output
            }
        )
        
        logger.info(
            "stream_complete",
            session_id=session.id,
            lines_processed=self.metrics.lines_processed,
            messages_parsed=self.metrics.messages_parsed,
            errors=self.metrics.errors_encountered
        )
    
    async def _handle_stream_error(self, session, error: Exception) -> None:
        """Handle stream error."""
        from ..managers.session import SessionState
        
        session.state = SessionState.FAILED
        session.error = str(error)
        session.metrics.end_time = datetime.utcnow()
        
        # Save error state
        await self.session_manager._save_session(session)
        
        # Emit error event
        await emit(
            "session_failed",
            EventCategory.SESSION,
            {
                "session_id": session.id,
                "error": str(error)
            },
            priority=EventPriority.HIGH
        )


# Export public API
__all__ = ['StreamProcessor', 'StreamMetrics']