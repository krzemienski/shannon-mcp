"""
Session Manager for Shannon MCP Server.

This module manages Claude Code sessions with:
- Subprocess execution and management
- JSONL stream parsing and handling
- Session lifecycle management
- Checkpoint support
- Cancellation and timeout handling
- Metrics collection
"""

import asyncio
import subprocess
import os
import signal
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import weakref
import structlog
import re

from ..managers.base import BaseManager, ManagerConfig, HealthStatus
from ..managers.binary import BinaryManager, BinaryInfo
from ..managers.process_registry import ProcessRegistryManager, ProcessRegistryConfig, RegisteredSession
from ..utils.config import SessionManagerConfig
from ..utils.errors import (
    SystemError, TimeoutError, ValidationError,
    handle_errors, error_context, ErrorRecovery
)
from ..utils.notifications import emit, EventCategory, EventPriority, event_handler
from ..utils.shutdown import track_request_lifetime, register_shutdown_handler, ShutdownPhase
from ..utils.logging import get_logger
from .cache import SessionCache


logger = get_logger("shannon-mcp.session")


class SessionState(Enum):
    """Session lifecycle states."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class MessageType(Enum):
    """JSONL message types from Claude."""
    PARTIAL = "partial"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"
    METRIC = "metric"
    DEBUG = "debug"
    STATUS = "status"
    CHECKPOINT = "checkpoint"


@dataclass
class SessionMessage:
    """Message in a session."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMetrics:
    """Comprehensive session metrics similar to Claudia's analytics."""
    # Timing metrics
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    first_message_time: Optional[datetime] = None
    last_activity_time: datetime = field(default_factory=datetime.utcnow)
    
    # Activity metrics (from Claudia)
    prompts_sent: int = 0
    tools_executed: int = 0
    tools_failed: int = 0
    files_created: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    code_blocks_generated: int = 0
    errors_encountered: int = 0
    
    # Performance metrics
    tool_execution_times: List[float] = field(default_factory=list)
    checkpoint_count: int = 0
    model_changes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Token and message metrics
    tokens_input: int = 0
    tokens_output: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    stream_bytes_received: int = 0
    
    # Session state
    was_resumed: bool = False
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        duration = self.duration
        if duration and duration.total_seconds() > 0:
            return self.tokens_output / duration.total_seconds()
        return 0.0
    
    @property
    def time_to_first_message(self) -> Optional[float]:
        """Time to first message in milliseconds."""
        if self.first_message_time:
            delta = self.first_message_time - self.start_time
            return delta.total_seconds() * 1000
        return None
    
    @property
    def idle_time(self) -> float:
        """Idle time since last activity in milliseconds."""
        delta = datetime.utcnow() - self.last_activity_time
        return delta.total_seconds() * 1000
    
    @property
    def average_tool_execution_time(self) -> Optional[float]:
        """Average tool execution time in milliseconds."""
        if self.tool_execution_times:
            return sum(self.tool_execution_times) / len(self.tool_execution_times)
        return None
    
    def track_tool_execution_start(self) -> datetime:
        """Track start of tool execution."""
        return datetime.utcnow()
    
    def track_tool_execution_end(self, start_time: datetime, success: bool = True) -> None:
        """Track end of tool execution."""
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.tool_execution_times.append(execution_time)
        self.tools_executed += 1
        if not success:
            self.tools_failed += 1
        self.last_activity_time = datetime.utcnow()
    
    def track_file_operation(self, operation: str) -> None:
        """Track file operations."""
        if operation == "create":
            self.files_created += 1
        elif operation == "modify":
            self.files_modified += 1
        elif operation == "delete":
            self.files_deleted += 1
        self.last_activity_time = datetime.utcnow()
    
    def track_code_block(self) -> None:
        """Track code block generation."""
        self.code_blocks_generated += 1
        self.last_activity_time = datetime.utcnow()
    
    def track_error(self) -> None:
        """Track error occurrence."""
        self.errors_encountered += 1
        self.last_activity_time = datetime.utcnow()
    
    def track_model_change(self, from_model: str, to_model: str) -> None:
        """Track model changes."""
        self.model_changes.append({
            "from": from_model,
            "to": to_model,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity_time = datetime.utcnow()


@dataclass
class Session:
    """Claude Code session."""
    id: str
    binary: BinaryInfo
    model: str = "claude-3-sonnet"
    state: SessionState = SessionState.CREATED
    process: Optional[asyncio.subprocess.Process] = None
    messages: List[SessionMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    checkpoint_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    # Stream handling
    _output_buffer: bytearray = field(default_factory=bytearray, init=False)
    _current_response: str = field(default="", init=False)
    _stream_task: Optional[asyncio.Task] = field(default=None, init=False)
    _response_callbacks: List[Callable] = field(default_factory=list, init=False)
    
    def add_message(self, role: str, content: str, **metadata) -> SessionMessage:
        """Add a message to the session."""
        message = SessionMessage(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        return message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "binary_path": str(self.binary.path),
            "model": self.model,
            "state": self.state.value,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in self.messages
            ],
            "context": self.context,
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at.isoformat(),
            "error": self.error,
            "metrics": {
                "start_time": self.metrics.start_time.isoformat(),
                "end_time": self.metrics.end_time.isoformat() if self.metrics.end_time else None,
                "first_message_time": self.metrics.first_message_time.isoformat() if self.metrics.first_message_time else None,
                "last_activity_time": self.metrics.last_activity_time.isoformat(),
                "duration_seconds": self.metrics.duration.total_seconds() if self.metrics.duration else None,
                "time_to_first_message_ms": self.metrics.time_to_first_message,
                "idle_time_ms": self.metrics.idle_time,
                "average_tool_execution_time_ms": self.metrics.average_tool_execution_time,
                "tokens_input": self.metrics.tokens_input,
                "tokens_output": self.metrics.tokens_output,
                "tokens_per_second": self.metrics.tokens_per_second,
                "messages_sent": self.metrics.messages_sent,
                "messages_received": self.metrics.messages_received,
                "prompts_sent": self.metrics.prompts_sent,
                "tools_executed": self.metrics.tools_executed,
                "tools_failed": self.metrics.tools_failed,
                "files_created": self.metrics.files_created,
                "files_modified": self.metrics.files_modified,
                "files_deleted": self.metrics.files_deleted,
                "code_blocks_generated": self.metrics.code_blocks_generated,
                "errors_encountered": self.metrics.errors_encountered,
                "checkpoint_count": self.metrics.checkpoint_count,
                "was_resumed": self.metrics.was_resumed,
                "model_changes": self.metrics.model_changes
            }
        }


class SessionManager(BaseManager[Session]):
    """Manages Claude Code sessions."""
    
    def __init__(self, config: SessionManagerConfig, binary_manager: BinaryManager):
        """Initialize session manager."""
        manager_config = ManagerConfig(
            name="session_manager",
            db_path=Path.home() / ".shannon-mcp" / "sessions.db",
            custom_config=config.model_dump()
        )
        super().__init__(manager_config)
        
        self.session_config = config
        self.binary_manager = binary_manager
        self._sessions: Dict[str, Session] = {}
        self._session_lock = asyncio.Lock()
        
        # Initialize process registry for tracking running sessions
        registry_config = ProcessRegistryConfig(
            name="session_process_registry",
            db_path=Path.home() / ".shannon-mcp" / "session_registry.db"
        )
        self.process_registry = ProcessRegistryManager(registry_config)
        
        # Stream processor will be initialized in _initialize
        self._stream_processor = None
        
        # Session cache
        cache_dir = Path.home() / ".shannon-mcp" / "session_cache"
        self._session_cache = SessionCache(
            max_sessions=config.max_concurrent_sessions * 2,  # Cache 2x active sessions
            max_size_mb=500,  # 500MB cache
            session_ttl=config.session_timeout * 2,  # 2x session timeout
            persistence_dir=cache_dir
        )
        
        # Register shutdown handler
        register_shutdown_handler(
            "session_manager",
            self._shutdown_sessions,
            phase=ShutdownPhase.STOP_WORKERS,
            timeout=30.0
        )
    
    async def _initialize(self) -> None:
        """Initialize session manager."""
        logger.info("initializing_session_manager")
        
        # Import StreamProcessor here to avoid circular imports
        from ..streaming.processor import StreamProcessor
        self._stream_processor = StreamProcessor(self)
        
        # Initialize cache
        await self._session_cache.initialize()
        
        # Initialize process registry
        await self.process_registry.initialize()
        await self.process_registry.start()
        
        # Load active sessions from database
        await self._load_active_sessions()
    
    async def _start(self) -> None:
        """Start session manager operations."""
        # Start session monitoring
        self._tasks.append(
            asyncio.create_task(self._monitor_sessions())
        )
    
    async def _stop(self) -> None:
        """Stop session manager operations."""
        # Gracefully terminate all sessions
        await self._shutdown_sessions()
        
        # Shutdown process registry
        await self.process_registry.stop()
        
        # Shutdown cache
        await self._session_cache.shutdown()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        active_sessions = len(self._sessions)
        running_sessions = sum(
            1 for s in self._sessions.values()
            if s.state == SessionState.RUNNING
        )
        
        cache_stats = self._session_cache.get_stats()
        
        return {
            "active_sessions": active_sessions,
            "running_sessions": running_sessions,
            "max_concurrent": self.session_config.max_concurrent_sessions,
            "buffer_size": self.session_config.buffer_size,
            "metrics_enabled": self.session_config.enable_metrics,
            "cache_stats": cache_stats
        }
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                binary_path TEXT NOT NULL,
                model TEXT NOT NULL,
                state TEXT NOT NULL,
                checkpoint_id TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                error TEXT,
                metrics TEXT,
                context TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_state 
            ON sessions(state)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_checkpoint 
            ON sessions(checkpoint_id)
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session 
            ON session_messages(session_id)
        """)
    
    @track_request_lifetime
    async def create_session(
        self,
        prompt: str,
        model: str = "claude-3-sonnet",
        checkpoint_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new Claude Code session.
        
        Args:
            prompt: Initial prompt
            model: Model to use
            checkpoint_id: Optional checkpoint to restore from
            context: Additional context
            
        Returns:
            Created session
            
        Raises:
            SystemError: If session creation fails
            ValidationError: If parameters are invalid
        """
        async with self._session_lock:
            # Check concurrent session limit
            if len(self._sessions) >= self.session_config.max_concurrent_sessions:
                raise SystemError(
                    f"Maximum concurrent sessions ({self.session_config.max_concurrent_sessions}) reached"
                )
            
            with error_context("session_manager", "create_session"):
                # Discover binary
                binary = await self.binary_manager.discover_binary()
                
                # Generate session ID
                session_id = f"session_{uuid.uuid4().hex[:12]}"
                
                # Create session
                session = Session(
                    id=session_id,
                    binary=binary,
                    model=model,
                    checkpoint_id=checkpoint_id,
                    context=context or {}
                )
                
                # Set resume flag if checkpoint provided
                if checkpoint_id:
                    session.metrics.was_resumed = True
                
                # Add initial message
                session.add_message("user", prompt)
                session.metrics.prompts_sent += 1
                
                # Register with process registry for tracking
                await self.process_registry.register_claude_session(
                    session_id=session_id,
                    project_path=context.get("project_path", "") if context else "",
                    task=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    model=model,
                    was_resumed=bool(checkpoint_id)
                )
                
                # Store session
                self._sessions[session_id] = session
                
                # Save to database
                await self._save_session(session)
                
                # Start the session
                await self._start_session(session, prompt)
                
                # Emit event
                await emit(
                    "session_created",
                    EventCategory.SESSION,
                    {
                        "session_id": session_id,
                        "model": model,
                        "checkpoint_id": checkpoint_id
                    }
                )
                
                logger.info(
                    "session_created",
                    session_id=session_id,
                    model=model,
                    checkpoint_id=checkpoint_id
                )
                
                return session
    
    async def _start_session(self, session: Session, prompt: str) -> None:
        """Start a session subprocess."""
        session.state = SessionState.STARTING
        
        try:
            # Build command
            cmd = [
                str(session.binary.path),
                "--model", session.model,
                "--output-format", "stream-json",
                "--no-color",
                "--quiet"
            ]
            
            # Add checkpoint if provided
            if session.checkpoint_id:
                cmd.extend(["--resume", session.checkpoint_id])
            
            # Set environment
            env = os.environ.copy()
            env["CLAUDE_SESSION_ID"] = session.id
            
            # Create subprocess
            session.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            session.state = SessionState.RUNNING
            session.metrics.start_time = datetime.utcnow()
            
            # Start stream processing
            session._stream_task = asyncio.create_task(
                self._stream_processor.process_session(session)
            )
            
            # Send initial prompt
            if session.process.stdin:
                await session.process.stdin.write(f"{prompt}\n".encode())
                await session.process.stdin.drain()
                session.metrics.messages_sent += 1
                
                # Track first message time
                if not session.metrics.first_message_time:
                    session.metrics.first_message_time = datetime.utcnow()
                
                # Update process registry
                await self.process_registry.update_session_status(
                    session.id, "running"
                )
            
            logger.info(
                "session_started",
                session_id=session.id,
                pid=session.process.pid
            )
            
        except Exception as e:
            session.state = SessionState.FAILED
            session.error = str(e)
            logger.error(
                "session_start_failed",
                session_id=session.id,
                error=str(e),
                exc_info=True
            )
            raise SystemError(f"Failed to start session: {e}") from e
    
    async def send_message(
        self,
        session_id: str,
        content: str,
        timeout: Optional[float] = None
    ) -> None:
        """
        Send a message to a session.
        
        Args:
            session_id: Session ID
            content: Message content
            timeout: Optional timeout
            
        Raises:
            ValidationError: If session not found
            SystemError: If send fails
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError("session_id", session_id, "Session not found")
        
        if session.state != SessionState.RUNNING:
            raise SystemError(f"Session not in running state: {session.state.value}")
        
        if not session.process or not session.process.stdin:
            raise SystemError("Session process not available")
        
        with error_context("session_manager", "send_message", session_id=session_id):
            try:
                # Add message to history
                session.add_message("user", content)
                session.metrics.prompts_sent += 1
                
                # Send to process
                await asyncio.wait_for(
                    session.process.stdin.write(f"{content}\n".encode()),
                    timeout=timeout or self.session_config.session_timeout
                )
                await session.process.stdin.drain()
                
                session.metrics.messages_sent += 1
                session.metrics.last_activity_time = datetime.utcnow()
                
                # Update process registry
                await self.process_registry.update_session_metrics(
                    session_id, {
                        "prompts_sent": session.metrics.prompts_sent,
                        "messages_sent": session.metrics.messages_sent
                    }
                )
                
                # Save session state
                await self._save_session(session)
                
                logger.debug(
                    "message_sent",
                    session_id=session_id,
                    content_length=len(content)
                )
                
            except asyncio.TimeoutError:
                raise TimeoutError(f"Send message timeout after {timeout}s")
            except Exception as e:
                session.metrics.errors_count += 1
                raise SystemError(f"Failed to send message: {e}") from e
    
    async def cancel_session(self, session_id: str) -> None:
        """
        Cancel a running session.
        
        Args:
            session_id: Session ID
            
        Raises:
            ValidationError: If session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError("session_id", session_id, "Session not found")
        
        if session.state not in (SessionState.RUNNING, SessionState.STARTING):
            logger.warning(
                "cancel_not_running",
                session_id=session_id,
                state=session.state.value
            )
            return
        
        session.state = SessionState.CANCELLING
        
        with error_context("session_manager", "cancel_session", session_id=session_id):
            try:
                if session.process:
                    # Send SIGTERM
                    if os.name == 'nt':
                        session.process.terminate()
                    else:
                        os.killpg(os.getpgid(session.process.pid), signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    try:
                        await asyncio.wait_for(
                            session.process.wait(),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        # Force kill
                        if os.name == 'nt':
                            session.process.kill()
                        else:
                            os.killpg(os.getpgid(session.process.pid), signal.SIGKILL)
                        await session.process.wait()
                
                session.state = SessionState.CANCELLED
                session.metrics.end_time = datetime.utcnow()
                
                # Update process registry
                await self.process_registry.update_session_status(
                    session.id, "cancelled"
                )
                
                # Cancel stream task
                if session._stream_task:
                    session._stream_task.cancel()
                    try:
                        await session._stream_task
                    except asyncio.CancelledError:
                        pass
                
                # Save final state
                await self._save_session(session)
                
                # Emit event
                await emit(
                    "session_cancelled",
                    EventCategory.SESSION,
                    {"session_id": session_id}
                )
                
                logger.info("session_cancelled", session_id=session_id)
                
            except Exception as e:
                session.state = SessionState.FAILED
                session.error = f"Cancel failed: {e}"
                logger.error(
                    "session_cancel_failed",
                    session_id=session_id,
                    error=str(e),
                    exc_info=True
                )
                raise
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        # Check active sessions first
        session = self._sessions.get(session_id)
        if session:
            return session
        
        # Try cache
        cached_session = await self._session_cache.get_session(session_id)
        if cached_session:
            # Return cached session directly
            return cached_session
        
        return None
    
    async def list_sessions(
        self,
        state: Optional[SessionState] = None,
        limit: int = 100
    ) -> List[Session]:
        """List sessions with optional filtering."""
        sessions = list(self._sessions.values())
        
        if state:
            sessions = [s for s in sessions if s.state == state]
        
        # Sort by creation time, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        
        return sessions[:limit]
    
    async def get_session_output(
        self,
        session_id: str,
        since_message: Optional[int] = None
    ) -> List[SessionMessage]:
        """Get session output messages."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError("session_id", session_id, "Session not found")
        
        messages = [m for m in session.messages if m.role == "assistant"]
        
        if since_message is not None:
            messages = messages[since_message:]
        
        return messages
    
    async def get_session_live_stream(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get live streaming output from a Claude Code session (replaces Tauri events).
        
        This method provides real-time output that replaces the claude-output, 
        claude-error, and claude-complete Tauri events from Claudia.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of stream messages with type, message, and timestamp
            
        Raises:
            ValidationError: If session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError("session_id", session_id, "Session not found")
        
        # Convert session messages to stream format expected by frontend
        stream_messages = []
        
        for message in session.messages:
            stream_message = {
                "type": message.role,  # "user", "assistant", "system"
                "message": {
                    "content": message.content,
                    "usage": getattr(message, "usage", None)
                },
                "timestamp": message.timestamp.isoformat() if message.timestamp else None,
                "isMeta": message.role == "system",
                "leafUuid": getattr(message, "id", None)
            }
            stream_messages.append(stream_message)
        
        return stream_messages
    
    async def list_running_claude_sessions(self) -> List[Dict[str, Any]]:
        """
        List all running Claude Code sessions (Claudia API compatibility).
        
        Returns list of active sessions in Claudia-compatible format with ProcessInfo.
        This replaces the Tauri command listRunningClaudeSessions().
        
        Returns:
            List of running session info in Claudia format
        """
        running_sessions = await self.process_registry.get_running_claude_sessions()
        
        # Convert to Claudia-compatible format
        claudia_sessions = []
        for process_info in running_sessions:
            session_data = {
                "run_id": process_info.run_id,
                "process_type": {
                    "ClaudeSession": {
                        "session_id": process_info.session_id
                    }
                },
                "pid": process_info.pid,
                "started_at": process_info.metrics.start_time.isoformat(),
                "project_path": process_info.project_path,
                "task": process_info.task,
                "model": process_info.model,
                "status": process_info.status.value if hasattr(process_info.status, 'value') else process_info.status,
                "metrics": process_info.metrics.to_dict() if hasattr(process_info.metrics, 'to_dict') else {}
            }
            claudia_sessions.append(session_data)
        
        return claudia_sessions
    
    async def create_checkpoint(self, session_id: str) -> str:
        """
        Create a checkpoint for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Checkpoint ID
            
        Raises:
            ValidationError: If session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValidationError("session_id", session_id, "Session not found")
        
        # This would integrate with checkpoint storage
        # For now, generate a checkpoint ID
        checkpoint_id = f"checkpoint_{uuid.uuid4().hex[:12]}"
        
        session.metrics.checkpoints_created += 1
        session.metrics.checkpoint_count += 1
        session.metrics.last_activity_time = datetime.utcnow()
        
        # Update process registry
        await self.process_registry.update_session_metrics(
            session_id, {
                "checkpoint_count": session.metrics.checkpoint_count
            }
        )
        
        # Emit checkpoint event to Claude
        if session.process and session.process.stdin:
            checkpoint_msg = json.dumps({
                "type": "checkpoint",
                "checkpoint_id": checkpoint_id
            })
            await session.process.stdin.write(f"{checkpoint_msg}\n".encode())
            await session.process.stdin.drain()
        
        logger.info(
            "checkpoint_created",
            session_id=session_id,
            checkpoint_id=checkpoint_id
        )
        
        return checkpoint_id
    
    async def _save_session(self, session: Session) -> None:
        """Save session to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO sessions 
            (id, binary_path, model, state, checkpoint_id, created_at,
             started_at, ended_at, error, metrics, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id,
            str(session.binary.path),
            session.model,
            session.state.value,
            session.checkpoint_id,
            session.created_at.isoformat(),
            session.metrics.start_time.isoformat(),
            session.metrics.end_time.isoformat() if session.metrics.end_time else None,
            session.error,
            json.dumps({
                "tokens_input": session.metrics.tokens_input,
                "tokens_output": session.metrics.tokens_output,
                "messages_sent": session.metrics.messages_sent,
                "messages_received": session.metrics.messages_received,
                "errors_count": session.metrics.errors_count,
                "checkpoints_created": session.metrics.checkpoints_created
            }),
            json.dumps(session.context)
        ))
        
        # Save messages
        for message in session.messages:
            await self.db.execute("""
                INSERT INTO session_messages 
                (session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.id,
                message.role,
                message.content,
                message.timestamp.isoformat(),
                json.dumps(message.metadata)
            ))
        
        await self.db.commit()
        
        # Also cache the session
        # Determine TTL based on state
        if session.state in (SessionState.COMPLETED, SessionState.FAILED, SessionState.CANCELLED, SessionState.TIMEOUT):
            ttl = 300  # 5 minutes for completed sessions
        else:
            ttl = None  # Use default TTL for active sessions
        
        await self._session_cache.cache_session(session, ttl=ttl)
    
    async def _load_active_sessions(self) -> None:
        """Load active sessions from database."""
        # For now, we don't persist sessions across restarts
        # This could be implemented to restore running sessions
        pass
    
    async def _monitor_sessions(self) -> None:
        """Monitor sessions for timeouts and cleanup."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                now = datetime.utcnow()
                sessions_to_clean = []
                
                for session_id, session in self._sessions.items():
                    # Check for timeout
                    if session.state == SessionState.RUNNING:
                        duration = now - session.metrics.start_time
                        if duration.total_seconds() > self.session_config.session_timeout:
                            logger.warning(
                                "session_timeout",
                                session_id=session_id,
                                duration_seconds=duration.total_seconds()
                            )
                            session.state = SessionState.TIMEOUT
                            sessions_to_clean.append(session_id)
                    
                    # Clean up completed/failed sessions after a delay
                    elif session.state in (
                        SessionState.COMPLETED,
                        SessionState.FAILED,
                        SessionState.CANCELLED,
                        SessionState.TIMEOUT
                    ):
                        if session.metrics.end_time:
                            age = now - session.metrics.end_time
                            if age.total_seconds() > 300:  # 5 minutes
                                sessions_to_clean.append(session_id)
                
                # Clean up sessions
                for session_id in sessions_to_clean:
                    await self._cleanup_session(session_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("session_monitor_error", error=str(e))
    
    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up a session."""
        session = self._sessions.pop(session_id, None)
        if not session:
            return
        
        # Ensure process is terminated
        if session.process:
            try:
                session.process.terminate()
                await asyncio.wait_for(session.process.wait(), timeout=5.0)
            except:
                pass
        
        logger.info("session_cleaned_up", session_id=session_id)
    
    async def _shutdown_sessions(self) -> None:
        """Shutdown all sessions gracefully."""
        logger.info("shutting_down_sessions", count=len(self._sessions))
        
        # Cancel all running sessions
        tasks = []
        for session_id in list(self._sessions.keys()):
            tasks.append(self.cancel_session(session_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # Event handlers
    
    @event_handler(categories=EventCategory.SESSION, event_names="stream_message")
    async def _handle_stream_message(self, event) -> None:
        """Handle stream messages from processor with comprehensive analytics."""
        session_id = event.data.get("session_id")
        message = event.data.get("message")
        
        session = self._sessions.get(session_id)
        if session and message:
            # Track enhanced tool execution (similar to Claudia)
            if message.get("type") == "assistant" and message.get("message", {}).get("content"):
                content = message["message"]["content"]
                if isinstance(content, list):
                    # Track tool uses
                    for item in content:
                        if item.get("type") == "tool_use":
                            # Track tool execution start
                            tool_name = item.get("name", "").lower()
                            session.metrics.tools_executed += 1
                            session.metrics.last_activity_time = datetime.utcnow()
                            
                            # Track file operations based on tool name
                            if "create" in tool_name or "write" in tool_name:
                                session.metrics.track_file_operation("create")
                            elif "edit" in tool_name or "multiedit" in tool_name or "search_replace" in tool_name:
                                session.metrics.track_file_operation("modify")
                            elif "delete" in tool_name:
                                session.metrics.track_file_operation("delete")
                
                # Track code blocks in text content
                text_content = ""
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            text_content += item.get("text", "")
                elif isinstance(content, str):
                    text_content = content
                
                # Count code blocks
                code_block_pattern = r'```[\s\S]*?```'
                code_blocks = re.findall(code_block_pattern, text_content)
                if code_blocks:
                    session.metrics.code_blocks_generated += len(code_blocks)
            
            # Track tool results and errors
            if message.get("type") == "user" and message.get("message", {}).get("content"):
                content = message["message"]["content"]
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_result":
                            is_error = item.get("is_error", False)
                            if is_error:
                                session.metrics.tools_failed += 1
                                session.metrics.track_error()
            
            # Track system errors
            if message.get("type") == "system" and (message.get("subtype") == "error" or message.get("error")):
                session.metrics.track_error()
            
            # Update token metrics
            if message.get("type") == "metric":
                metrics = message.get("data", {})
                session.metrics.tokens_input = metrics.get("tokens_input", session.metrics.tokens_input)
                session.metrics.tokens_output = metrics.get("tokens_output", session.metrics.tokens_output)
            
            # Track message usage if present
            if message.get("message", {}).get("usage"):
                usage = message["message"]["usage"]
                session.metrics.tokens_input += usage.get("input_tokens", 0)
                session.metrics.tokens_output += usage.get("output_tokens", 0)
            
            # Track received messages
            session.metrics.messages_received += 1
            session.metrics.last_activity_time = datetime.utcnow()
            
            # Update process registry with latest metrics
            await self.process_registry.update_session_metrics(
                session_id, {
                    "tools_executed": session.metrics.tools_executed,
                    "tools_failed": session.metrics.tools_failed,
                    "files_created": session.metrics.files_created,
                    "files_modified": session.metrics.files_modified,
                    "files_deleted": session.metrics.files_deleted,
                    "code_blocks_generated": session.metrics.code_blocks_generated,
                    "errors_encountered": session.metrics.errors_encountered,
                    "tokens_input": session.metrics.tokens_input,
                    "tokens_output": session.metrics.tokens_output
                }
            )


# Export public API
__all__ = [
    'SessionManager',
    'Session',
    'SessionState',
    'SessionMessage',
    'SessionMetrics',
    'MessageType',
]