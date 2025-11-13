"""
Metrics Parser for Analytics Engine.

Parses JSONL metrics files and extracts structured data for analysis.
"""

import json
import asyncio
import aiofiles
import gzip
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, AsyncIterator, Tuple
from dataclasses import dataclass
from collections import defaultdict
from contextlib import asynccontextmanager
import re

from ..utils.logging import get_logger
from ..utils.errors import ShannonError
from .writer import MetricEntry, MetricType

logger = get_logger(__name__)


@dataclass
class ParsedMetric:
    """A parsed metric with extracted fields."""
    entry: MetricEntry
    
    # Extracted fields for quick access
    timestamp: datetime
    type: MetricType
    session_id: Optional[str]
    user_id: Optional[str]
    
    # Type-specific fields
    tool_name: Optional[str] = None
    agent_id: Optional[str] = None
    command_name: Optional[str] = None
    error_type: Optional[str] = None
    operation: Optional[str] = None
    
    # Numeric fields
    duration_ms: Optional[float] = None
    token_count: Optional[int] = None
    success: Optional[bool] = None
    
    @classmethod
    def from_entry(cls, entry: MetricEntry) -> "ParsedMetric":
        """Create parsed metric from entry."""
        metric = cls(
            entry=entry,
            timestamp=entry.timestamp,
            type=entry.type,
            session_id=entry.session_id,
            user_id=entry.user_id
        )
        
        # Extract type-specific fields
        data = entry.data
        
        if entry.type == MetricType.TOOL_USE:
            metric.tool_name = data.get("tool_name")
            metric.duration_ms = data.get("duration_ms")
            metric.success = data.get("success")
            
        elif entry.type == MetricType.AGENT_EXECUTION:
            metric.agent_id = data.get("agent_id")
            metric.duration_ms = data.get("duration_ms")
            metric.success = data.get("success")
            
        elif entry.type == MetricType.COMMAND_EXECUTED:
            metric.command_name = data.get("command_name")
            metric.duration_ms = data.get("duration_ms")
            metric.success = data.get("success", True)
            
        elif entry.type == MetricType.ERROR_OCCURRED:
            metric.error_type = data.get("error_type")
            metric.success = False
            
        elif entry.type == MetricType.PERFORMANCE:
            metric.operation = data.get("operation")
            metric.duration_ms = data.get("duration_ms")
            metric.success = data.get("success")
            
        elif entry.type in [MetricType.SESSION_START, MetricType.SESSION_END]:
            metric.duration_ms = data.get("duration_seconds", 0) * 1000 if data.get("duration_seconds") else None
            metric.token_count = data.get("token_count")
        
        return metric


class MetricsParser:
    """Parses metrics from JSONL files."""
    
    def __init__(self, base_path: Path):
        """
        Initialize parser.
        
        Args:
            base_path: Base directory containing metrics
        """
        self.base_path = Path(base_path)
        self.metrics_dir = self.base_path / "metrics"
        
    async def parse_file(self, file_path: Path) -> List[ParsedMetric]:
        """
        Parse a single metrics file.
        
        Args:
            file_path: Path to metrics file
            
        Returns:
            List of parsed metrics
        """
        metrics = []
        
        # Determine if compressed
        if file_path.suffix == '.gz':
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                lines = gzip.decompress(content).decode('utf-8').splitlines()
        else:
            async with aiofiles.open(file_path, 'r') as f:
                lines = await f.readlines()
        
        # Parse each line
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                data = json.loads(line)
                entry = MetricEntry.from_dict(data)
                metric = ParsedMetric.from_entry(entry)
                metrics.append(metric)
            except Exception as e:
                logger.warning(f"Failed to parse line {line_num} in {file_path}: {e}")
                continue
        
        logger.debug(f"Parsed {len(metrics)} metrics from {file_path}")
        return metrics
    
    async def parse_time_range(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[ParsedMetric]:
        """
        Parse metrics within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of parsed metrics in range
        """
        metrics = []
        
        # Find relevant files
        files = await self._find_files_in_range(start_time, end_time)
        
        # Parse each file
        for file_path in files:
            file_metrics = await self.parse_file(file_path)
            
            # Filter by time range
            for metric in file_metrics:
                if start_time <= metric.timestamp <= end_time:
                    metrics.append(metric)
        
        # Sort by timestamp
        metrics.sort(key=lambda m: m.timestamp)
        
        logger.info(f"Parsed {len(metrics)} metrics from {start_time} to {end_time}")
        return metrics
    
    async def stream_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        batch_size: int = 1000
    ) -> AsyncIterator[List[ParsedMetric]]:
        """
        Stream metrics in batches.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            batch_size: Number of metrics per batch
            
        Yields:
            Batches of parsed metrics
        """
        # Find files to process
        if start_time and end_time:
            files = await self._find_files_in_range(start_time, end_time)
        else:
            files = sorted(
                self.metrics_dir.glob("metrics_*.jsonl*"),
                key=lambda p: p.stat().st_mtime
            )
        
        batch = []
        
        for file_path in files:
            # Parse file
            async with self._open_metrics_file(file_path) as lines:
                async for line in lines:
                    if not line.strip():
                        continue
                        
                    try:
                        data = json.loads(line)
                        entry = MetricEntry.from_dict(data)
                        
                        # Apply time filter if specified
                        if start_time and entry.timestamp < start_time:
                            continue
                        if end_time and entry.timestamp > end_time:
                            continue
                        
                        metric = ParsedMetric.from_entry(entry)
                        batch.append(metric)
                        
                        # Yield batch if full
                        if len(batch) >= batch_size:
                            yield batch
                            batch = []
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse line in {file_path}: {e}")
                        continue
        
        # Yield remaining metrics
        if batch:
            yield batch
    
    async def get_sessions(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Tuple[datetime, datetime]]:
        """
        Get all sessions with their start/end times.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            Dict mapping session_id to (start_time, end_time)
        """
        sessions = {}
        
        async for batch in self.stream_metrics(start_time, end_time):
            for metric in batch:
                if not metric.session_id:
                    continue
                    
                if metric.type == MetricType.SESSION_START:
                    if metric.session_id not in sessions:
                        sessions[metric.session_id] = (metric.timestamp, None)
                    else:
                        # Update start time if earlier
                        start, end = sessions[metric.session_id]
                        if metric.timestamp < start:
                            sessions[metric.session_id] = (metric.timestamp, end)
                            
                elif metric.type == MetricType.SESSION_END:
                    if metric.session_id in sessions:
                        start, _ = sessions[metric.session_id]
                        sessions[metric.session_id] = (start, metric.timestamp)
                    else:
                        # Session without start
                        sessions[metric.session_id] = (metric.timestamp, metric.timestamp)
        
        return sessions
    
    async def get_summary_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for metrics.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            Summary statistics dictionary
        """
        stats = {
            "total_metrics": 0,
            "metrics_by_type": defaultdict(int),
            "total_sessions": 0,
            "total_errors": 0,
            "tools_used": defaultdict(int),
            "agents_executed": defaultdict(int),
            "commands_run": defaultdict(int),
            "avg_session_duration_seconds": 0,
            "total_tokens": 0
        }
        
        sessions = await self.get_sessions(start_time, end_time)
        stats["total_sessions"] = len(sessions)
        
        # Calculate average session duration
        durations = []
        for start, end in sessions.values():
            if start and end:
                durations.append((end - start).total_seconds())
        
        if durations:
            stats["avg_session_duration_seconds"] = sum(durations) / len(durations)
        
        # Process all metrics
        async for batch in self.stream_metrics(start_time, end_time):
            for metric in batch:
                stats["total_metrics"] += 1
                stats["metrics_by_type"][metric.type.value] += 1
                
                if metric.type == MetricType.ERROR_OCCURRED:
                    stats["total_errors"] += 1
                    
                elif metric.type == MetricType.TOOL_USE and metric.tool_name:
                    stats["tools_used"][metric.tool_name] += 1
                    
                elif metric.type == MetricType.AGENT_EXECUTION and metric.agent_id:
                    stats["agents_executed"][metric.agent_id] += 1
                    
                elif metric.type == MetricType.COMMAND_EXECUTED and metric.command_name:
                    stats["commands_run"][metric.command_name] += 1
                    
                elif metric.token_count:
                    stats["total_tokens"] += metric.token_count
        
        # Convert defaultdicts to regular dicts
        stats["metrics_by_type"] = dict(stats["metrics_by_type"])
        stats["tools_used"] = dict(stats["tools_used"])
        stats["agents_executed"] = dict(stats["agents_executed"])
        stats["commands_run"] = dict(stats["commands_run"])
        
        return stats
    
    async def _find_files_in_range(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Path]:
        """Find metrics files that might contain data in the given range."""
        files = []
        
        for pattern in ["metrics_*.jsonl", "metrics_*.jsonl.gz"]:
            for file_path in self.metrics_dir.glob(pattern):
                # Extract timestamp from filename
                match = re.search(r'metrics_(\d{8}_\d{6})', file_path.name)
                if match:
                    try:
                        file_time = datetime.strptime(
                            match.group(1),
                            "%Y%m%d_%H%M%S"
                        ).replace(tzinfo=timezone.utc)
                        
                        # Include file if it might overlap with range
                        # (conservative approach - file might contain older data too)
                        if file_time <= end_time:
                            files.append(file_path)
                    except ValueError:
                        # Include file if we can't parse timestamp
                        files.append(file_path)
                else:
                    # Include files without timestamp
                    files.append(file_path)
        
        # Sort by modification time
        files.sort(key=lambda p: p.stat().st_mtime)
        return files
    
    @asynccontextmanager
    async def _open_metrics_file(self, file_path: Path):
        """Open metrics file handling compression."""
        if file_path.suffix == '.gz':
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                lines = gzip.decompress(content).decode('utf-8').splitlines()
                for line in lines:
                    yield line
        else:
            async with aiofiles.open(file_path, 'r') as f:
                async for line in f:
                    yield line