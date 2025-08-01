"""
JSONL Writer for Analytics Engine.

Handles writing metrics to JSONL files with:
- Atomic writes
- File rotation
- Compression support
- Thread-safe operations
"""

import json
import asyncio
import aiofiles
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import gzip
import uuid
from enum import Enum

from ..utils.logging import get_logger
from ..utils.errors import ShannonError

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics we track."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TOOL_USE = "tool_use"
    AGENT_EXECUTION = "agent_execution"
    CHECKPOINT_CREATED = "checkpoint_created"
    HOOK_TRIGGERED = "hook_triggered"
    COMMAND_EXECUTED = "command_executed"
    ERROR_OCCURRED = "error_occurred"
    TOKEN_USAGE = "token_usage"
    PERFORMANCE = "performance"


@dataclass
class MetricEntry:
    """A single metric entry."""
    id: str
    timestamp: datetime
    type: MetricType
    session_id: Optional[str]
    user_id: Optional[str]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "data": self.data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            type=MetricType(data["type"]),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            data=data.get("data", {}),
            metadata=data.get("metadata", {})
        )


class JSONLWriter:
    """Writes metrics to JSONL files with rotation and compression."""
    
    def __init__(
        self,
        base_path: Path,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_files: int = 10,
        compress_old: bool = True,
        buffer_size: int = 100
    ):
        """
        Initialize JSONL writer.
        
        Args:
            base_path: Base directory for analytics files
            max_file_size: Maximum size before rotation
            max_files: Maximum number of files to keep
            compress_old: Whether to compress rotated files
            buffer_size: Number of entries to buffer before writing
        """
        self.base_path = Path(base_path)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.compress_old = compress_old
        self.buffer_size = buffer_size
        
        # Create directory if needed
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Current file and buffer
        self.current_file: Optional[Path] = None
        self.buffer: List[MetricEntry] = []
        self.write_lock = asyncio.Lock()
        
        # File handle cache
        self._file_handle = None
        
    @property
    def metrics_dir(self) -> Path:
        """Get metrics directory."""
        return self.base_path / "metrics"
    
    async def initialize(self) -> None:
        """Initialize writer and ensure current file exists."""
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_current_file()
        
    async def write(self, entry: MetricEntry) -> None:
        """
        Write a metric entry.
        
        Args:
            entry: Metric entry to write
        """
        async with self.write_lock:
            self.buffer.append(entry)
            
            # Flush if buffer is full
            if len(self.buffer) >= self.buffer_size:
                await self._flush_buffer()
    
    async def write_batch(self, entries: List[MetricEntry]) -> None:
        """
        Write multiple metric entries.
        
        Args:
            entries: List of metric entries to write
        """
        async with self.write_lock:
            self.buffer.extend(entries)
            
            # Flush if buffer is full
            if len(self.buffer) >= self.buffer_size:
                await self._flush_buffer()
    
    async def flush(self) -> None:
        """Force flush the buffer."""
        async with self.write_lock:
            await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush buffer to disk."""
        if not self.buffer:
            return
            
        await self._ensure_current_file()
        
        # Write entries
        async with aiofiles.open(self.current_file, 'a') as f:
            for entry in self.buffer:
                line = json.dumps(entry.to_dict(), separators=(',', ':'))
                await f.write(line + '\n')
        
        logger.debug(f"Flushed {len(self.buffer)} metrics to {self.current_file}")
        self.buffer.clear()
        
        # Check if rotation needed
        await self._check_rotation()
    
    async def _ensure_current_file(self) -> None:
        """Ensure we have a current file to write to."""
        if self.current_file and self.current_file.exists():
            return
            
        # Find or create current file
        existing = sorted(
            self.metrics_dir.glob("metrics_*.jsonl"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True
        )
        
        if existing and existing[0].stat().st_size < self.max_file_size:
            self.current_file = existing[0]
        else:
            # Create new file
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.current_file = self.metrics_dir / f"metrics_{timestamp}.jsonl"
            self.current_file.touch()
            logger.info(f"Created new metrics file: {self.current_file}")
    
    async def _check_rotation(self) -> None:
        """Check if file rotation is needed."""
        if not self.current_file or not self.current_file.exists():
            return
            
        size = self.current_file.stat().st_size
        if size >= self.max_file_size:
            await self._rotate_files()
    
    async def _rotate_files(self) -> None:
        """Rotate metrics files."""
        logger.info(f"Rotating metrics file: {self.current_file}")
        
        # Compress current file if needed
        if self.compress_old and self.current_file:
            compressed = self.current_file.with_suffix('.jsonl.gz')
            
            async with aiofiles.open(self.current_file, 'rb') as f_in:
                content = await f_in.read()
                
            async with aiofiles.open(compressed, 'wb') as f_out:
                compressed_content = gzip.compress(content)
                await f_out.write(compressed_content)
            
            # Remove original
            self.current_file.unlink()
            logger.info(f"Compressed {self.current_file} to {compressed}")
        
        # Clean up old files
        await self._cleanup_old_files()
        
        # Reset current file
        self.current_file = None
        await self._ensure_current_file()
    
    async def _cleanup_old_files(self) -> None:
        """Remove old files exceeding max_files limit."""
        # Get all metrics files
        files = []
        for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
            files.extend(self.metrics_dir.glob(pattern))
        
        # Sort by modification time
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Remove excess files
        for f in files[self.max_files:]:
            f.unlink()
            logger.info(f"Removed old metrics file: {f}")
    
    async def close(self) -> None:
        """Close writer and flush remaining data."""
        await self.flush()
        
    # Context manager support
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class MetricsWriter:
    """High-level metrics writer with convenience methods."""
    
    def __init__(self, writer: JSONLWriter):
        """
        Initialize metrics writer.
        
        Args:
            writer: Underlying JSONL writer
        """
        self.writer = writer
        
    async def track_session_start(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> None:
        """Track session start."""
        entry = MetricEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            type=MetricType.SESSION_START,
            session_id=session_id,
            user_id=user_id,
            data={
                "project_path": project_path,
                "model": model,
                **kwargs
            },
            metadata={}
        )
        await self.writer.write(entry)
    
    async def track_session_end(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        token_count: Optional[int] = None,
        **kwargs
    ) -> None:
        """Track session end."""
        entry = MetricEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            type=MetricType.SESSION_END,
            session_id=session_id,
            user_id=user_id,
            data={
                "duration_seconds": duration_seconds,
                "token_count": token_count,
                **kwargs
            },
            metadata={}
        )
        await self.writer.write(entry)
    
    async def track_tool_use(
        self,
        session_id: str,
        tool_name: str,
        success: bool,
        duration_ms: Optional[float] = None,
        **kwargs
    ) -> None:
        """Track tool usage."""
        entry = MetricEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            type=MetricType.TOOL_USE,
            session_id=session_id,
            user_id=None,
            data={
                "tool_name": tool_name,
                "success": success,
                "duration_ms": duration_ms,
                **kwargs
            },
            metadata={}
        )
        await self.writer.write(entry)
    
    async def track_error(
        self,
        session_id: Optional[str],
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs
    ) -> None:
        """Track error occurrence."""
        entry = MetricEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            type=MetricType.ERROR_OCCURRED,
            session_id=session_id,
            user_id=None,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                **kwargs
            },
            metadata={}
        )
        await self.writer.write(entry)
    
    async def track_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        session_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Track performance metrics."""
        entry = MetricEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            type=MetricType.PERFORMANCE,
            session_id=session_id,
            user_id=None,
            data={
                "operation": operation,
                "duration_ms": duration_ms,
                "success": success,
                **kwargs
            },
            metadata={}
        )
        await self.writer.write(entry)