"""
Metrics Aggregator for Analytics Engine.

Performs aggregation and analysis on parsed metrics data.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import statistics

from ..utils.logging import get_logger
from .parser import ParsedMetric, MetricsParser
from .writer import MetricType

logger = get_logger(__name__)


class AggregationType(str, Enum):
    """Types of aggregations supported."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    BY_SESSION = "by_session"
    BY_USER = "by_user"
    BY_TOOL = "by_tool"
    BY_AGENT = "by_agent"
    BY_PROJECT = "by_project"


@dataclass
class AggregationResult:
    """Result of an aggregation operation."""
    type: AggregationType
    start_time: datetime
    end_time: datetime
    
    # Count metrics
    total_metrics: int = 0
    total_sessions: int = 0
    total_users: int = 0
    total_errors: int = 0
    
    # Time metrics (milliseconds)
    total_duration_ms: float = 0
    avg_duration_ms: float = 0
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    p50_duration_ms: Optional[float] = None
    p95_duration_ms: Optional[float] = None
    p99_duration_ms: Optional[float] = None
    
    # Token metrics
    total_tokens: int = 0
    avg_tokens_per_session: float = 0
    
    # Success metrics
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    
    # Breakdowns
    metrics_by_type: Dict[str, int] = field(default_factory=dict)
    tools_usage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    agents_usage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Time series data (for charting)
    time_series: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_metrics": self.total_metrics,
            "total_sessions": self.total_sessions,
            "total_users": self.total_users,
            "total_errors": self.total_errors,
            "duration_stats": {
                "total_ms": self.total_duration_ms,
                "avg_ms": self.avg_duration_ms,
                "min_ms": self.min_duration_ms,
                "max_ms": self.max_duration_ms,
                "p50_ms": self.p50_duration_ms,
                "p95_ms": self.p95_duration_ms,
                "p99_ms": self.p99_duration_ms
            },
            "token_stats": {
                "total": self.total_tokens,
                "avg_per_session": self.avg_tokens_per_session
            },
            "success_metrics": {
                "success_count": self.success_count,
                "failure_count": self.failure_count,
                "success_rate": self.success_rate
            },
            "breakdowns": {
                "by_type": self.metrics_by_type,
                "tools": self.tools_usage,
                "agents": self.agents_usage,
                "errors": self.errors_by_type
            },
            "time_series": self.time_series
        }


class MetricsAggregator:
    """Aggregates metrics data for analysis and reporting."""
    
    def __init__(self, parser: MetricsParser):
        """
        Initialize aggregator.
        
        Args:
            parser: Metrics parser instance
        """
        self.parser = parser
        
    async def aggregate(
        self,
        aggregation_type: AggregationType,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> AggregationResult:
        """
        Perform aggregation on metrics.
        
        Args:
            aggregation_type: Type of aggregation to perform
            start_time: Start of time range
            end_time: End of time range
            filters: Optional filters to apply
            
        Returns:
            Aggregation result
        """
        result = AggregationResult(
            type=aggregation_type,
            start_time=start_time,
            end_time=end_time
        )
        
        # Collect metrics
        metrics = await self._collect_metrics(start_time, end_time, filters)
        result.total_metrics = len(metrics)
        
        if not metrics:
            return result
        
        # Perform base aggregations
        await self._aggregate_base_stats(metrics, result)
        
        # Perform type-specific aggregations
        if aggregation_type == AggregationType.HOURLY:
            await self._aggregate_hourly(metrics, result)
        elif aggregation_type == AggregationType.DAILY:
            await self._aggregate_daily(metrics, result)
        elif aggregation_type == AggregationType.WEEKLY:
            await self._aggregate_weekly(metrics, result)
        elif aggregation_type == AggregationType.MONTHLY:
            await self._aggregate_monthly(metrics, result)
        elif aggregation_type == AggregationType.BY_SESSION:
            await self._aggregate_by_session(metrics, result)
        elif aggregation_type == AggregationType.BY_USER:
            await self._aggregate_by_user(metrics, result)
        elif aggregation_type == AggregationType.BY_TOOL:
            await self._aggregate_by_tool(metrics, result)
        elif aggregation_type == AggregationType.BY_AGENT:
            await self._aggregate_by_agent(metrics, result)
        elif aggregation_type == AggregationType.BY_PROJECT:
            await self._aggregate_by_project(metrics, result)
        
        return result
    
    async def _collect_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ParsedMetric]:
        """Collect metrics with optional filters."""
        all_metrics = []
        
        async for batch in self.parser.stream_metrics(start_time, end_time):
            for metric in batch:
                # Apply filters
                if filters:
                    if "session_id" in filters and metric.session_id != filters["session_id"]:
                        continue
                    if "user_id" in filters and metric.user_id != filters["user_id"]:
                        continue
                    if "type" in filters and metric.type != filters["type"]:
                        continue
                    if "tool_name" in filters and metric.tool_name != filters["tool_name"]:
                        continue
                    if "agent_id" in filters and metric.agent_id != filters["agent_id"]:
                        continue
                
                all_metrics.append(metric)
        
        return all_metrics
    
    async def _aggregate_base_stats(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate base statistics."""
        sessions: Set[str] = set()
        users: Set[str] = set()
        durations: List[float] = []
        
        for metric in metrics:
            # Count by type
            result.metrics_by_type[metric.type.value] = \
                result.metrics_by_type.get(metric.type.value, 0) + 1
            
            # Track sessions and users
            if metric.session_id:
                sessions.add(metric.session_id)
            if metric.user_id:
                users.add(metric.user_id)
            
            # Track errors
            if metric.type == MetricType.ERROR_OCCURRED:
                result.total_errors += 1
                if metric.error_type:
                    result.errors_by_type[metric.error_type] = \
                        result.errors_by_type.get(metric.error_type, 0) + 1
            
            # Track durations
            if metric.duration_ms is not None:
                durations.append(metric.duration_ms)
                result.total_duration_ms += metric.duration_ms
            
            # Track success/failure
            if metric.success is not None:
                if metric.success:
                    result.success_count += 1
                else:
                    result.failure_count += 1
            
            # Track tokens
            if metric.token_count:
                result.total_tokens += metric.token_count
            
            # Track tool usage
            if metric.tool_name:
                if metric.tool_name not in result.tools_usage:
                    result.tools_usage[metric.tool_name] = {
                        "count": 0,
                        "success": 0,
                        "failure": 0,
                        "total_duration_ms": 0,
                        "avg_duration_ms": 0
                    }
                
                tool_stats = result.tools_usage[metric.tool_name]
                tool_stats["count"] += 1
                if metric.success:
                    tool_stats["success"] += 1
                else:
                    tool_stats["failure"] += 1
                if metric.duration_ms:
                    tool_stats["total_duration_ms"] += metric.duration_ms
            
            # Track agent usage
            if metric.agent_id:
                if metric.agent_id not in result.agents_usage:
                    result.agents_usage[metric.agent_id] = {
                        "count": 0,
                        "success": 0,
                        "failure": 0,
                        "total_duration_ms": 0,
                        "avg_duration_ms": 0
                    }
                
                agent_stats = result.agents_usage[metric.agent_id]
                agent_stats["count"] += 1
                if metric.success:
                    agent_stats["success"] += 1
                else:
                    agent_stats["failure"] += 1
                if metric.duration_ms:
                    agent_stats["total_duration_ms"] += metric.duration_ms
        
        # Set counts
        result.total_sessions = len(sessions)
        result.total_users = len(users)
        
        # Calculate duration statistics
        if durations:
            result.avg_duration_ms = statistics.mean(durations)
            result.min_duration_ms = min(durations)
            result.max_duration_ms = max(durations)
            
            # Calculate percentiles
            sorted_durations = sorted(durations)
            n = len(sorted_durations)
            result.p50_duration_ms = sorted_durations[n // 2]
            result.p95_duration_ms = sorted_durations[int(n * 0.95)]
            result.p99_duration_ms = sorted_durations[int(n * 0.99)]
        
        # Calculate success rate
        total_outcomes = result.success_count + result.failure_count
        if total_outcomes > 0:
            result.success_rate = result.success_count / total_outcomes
        
        # Calculate average tokens per session
        if result.total_sessions > 0:
            result.avg_tokens_per_session = result.total_tokens / result.total_sessions
        
        # Calculate tool/agent averages
        for tool_stats in result.tools_usage.values():
            if tool_stats["count"] > 0 and tool_stats["total_duration_ms"] > 0:
                tool_stats["avg_duration_ms"] = \
                    tool_stats["total_duration_ms"] / tool_stats["count"]
        
        for agent_stats in result.agents_usage.values():
            if agent_stats["count"] > 0 and agent_stats["total_duration_ms"] > 0:
                agent_stats["avg_duration_ms"] = \
                    agent_stats["total_duration_ms"] / agent_stats["count"]
    
    async def _aggregate_hourly(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by hour."""
        hourly_data = defaultdict(lambda: {
            "count": 0,
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            # Round to hour
            hour = metric.timestamp.replace(minute=0, second=0, microsecond=0)
            hour_data = hourly_data[hour]
            
            hour_data["count"] += 1
            if metric.type == MetricType.ERROR_OCCURRED:
                hour_data["errors"] += 1
            if metric.duration_ms:
                hour_data["duration_ms"] += metric.duration_ms
            if metric.token_count:
                hour_data["tokens"] += metric.token_count
        
        # Convert to time series
        for hour, data in sorted(hourly_data.items()):
            result.time_series.append({
                "timestamp": hour.isoformat(),
                "metrics_count": data["count"],
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_daily(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by day."""
        daily_data = defaultdict(lambda: {
            "count": 0,
            "sessions": set(),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            # Round to day
            day = metric.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            day_data = daily_data[day]
            
            day_data["count"] += 1
            if metric.session_id:
                day_data["sessions"].add(metric.session_id)
            if metric.type == MetricType.ERROR_OCCURRED:
                day_data["errors"] += 1
            if metric.duration_ms:
                day_data["duration_ms"] += metric.duration_ms
            if metric.token_count:
                day_data["tokens"] += metric.token_count
        
        # Convert to time series
        for day, data in sorted(daily_data.items()):
            result.time_series.append({
                "timestamp": day.isoformat(),
                "metrics_count": data["count"],
                "sessions": len(data["sessions"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_weekly(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by week."""
        weekly_data = defaultdict(lambda: {
            "count": 0,
            "sessions": set(),
            "users": set(),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            # Get start of week (Monday)
            week_start = metric.timestamp - timedelta(days=metric.timestamp.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_data = weekly_data[week_start]
            
            week_data["count"] += 1
            if metric.session_id:
                week_data["sessions"].add(metric.session_id)
            if metric.user_id:
                week_data["users"].add(metric.user_id)
            if metric.type == MetricType.ERROR_OCCURRED:
                week_data["errors"] += 1
            if metric.duration_ms:
                week_data["duration_ms"] += metric.duration_ms
            if metric.token_count:
                week_data["tokens"] += metric.token_count
        
        # Convert to time series
        for week, data in sorted(weekly_data.items()):
            result.time_series.append({
                "week_start": week.isoformat(),
                "metrics_count": data["count"],
                "sessions": len(data["sessions"]),
                "users": len(data["users"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_monthly(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by month."""
        monthly_data = defaultdict(lambda: {
            "count": 0,
            "sessions": set(),
            "users": set(),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            # Round to month
            month = metric.timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_data = monthly_data[month]
            
            month_data["count"] += 1
            if metric.session_id:
                month_data["sessions"].add(metric.session_id)
            if metric.user_id:
                month_data["users"].add(metric.user_id)
            if metric.type == MetricType.ERROR_OCCURRED:
                month_data["errors"] += 1
            if metric.duration_ms:
                month_data["duration_ms"] += metric.duration_ms
            if metric.token_count:
                month_data["tokens"] += metric.token_count
        
        # Convert to time series
        for month, data in sorted(monthly_data.items()):
            result.time_series.append({
                "month": month.isoformat(),
                "metrics_count": data["count"],
                "sessions": len(data["sessions"]),
                "users": len(data["users"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_by_session(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by session."""
        session_data = defaultdict(lambda: {
            "start_time": None,
            "end_time": None,
            "metrics_count": 0,
            "tool_uses": defaultdict(int),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            if not metric.session_id:
                continue
                
            session = session_data[metric.session_id]
            session["metrics_count"] += 1
            
            # Track time range
            if session["start_time"] is None or metric.timestamp < session["start_time"]:
                session["start_time"] = metric.timestamp
            if session["end_time"] is None or metric.timestamp > session["end_time"]:
                session["end_time"] = metric.timestamp
            
            # Track metrics
            if metric.tool_name:
                session["tool_uses"][metric.tool_name] += 1
            if metric.type == MetricType.ERROR_OCCURRED:
                session["errors"] += 1
            if metric.duration_ms:
                session["duration_ms"] += metric.duration_ms
            if metric.token_count:
                session["tokens"] += metric.token_count
        
        # Convert to time series
        for session_id, data in session_data.items():
            duration_seconds = 0
            if data["start_time"] and data["end_time"]:
                duration_seconds = (data["end_time"] - data["start_time"]).total_seconds()
            
            result.time_series.append({
                "session_id": session_id,
                "start_time": data["start_time"].isoformat() if data["start_time"] else None,
                "end_time": data["end_time"].isoformat() if data["end_time"] else None,
                "duration_seconds": duration_seconds,
                "metrics_count": data["metrics_count"],
                "tool_uses": dict(data["tool_uses"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_by_user(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by user."""
        user_data = defaultdict(lambda: {
            "sessions": set(),
            "metrics_count": 0,
            "tool_uses": defaultdict(int),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            if not metric.user_id:
                continue
                
            user = user_data[metric.user_id]
            user["metrics_count"] += 1
            
            if metric.session_id:
                user["sessions"].add(metric.session_id)
            if metric.tool_name:
                user["tool_uses"][metric.tool_name] += 1
            if metric.type == MetricType.ERROR_OCCURRED:
                user["errors"] += 1
            if metric.duration_ms:
                user["duration_ms"] += metric.duration_ms
            if metric.token_count:
                user["tokens"] += metric.token_count
        
        # Convert to results
        for user_id, data in user_data.items():
            result.time_series.append({
                "user_id": user_id,
                "sessions": len(data["sessions"]),
                "metrics_count": data["metrics_count"],
                "tool_uses": dict(data["tool_uses"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })
    
    async def _aggregate_by_tool(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by tool."""
        # Tool usage is already aggregated in base stats
        # Create time series from tools_usage
        for tool_name, stats in result.tools_usage.items():
            result.time_series.append({
                "tool": tool_name,
                **stats
            })
    
    async def _aggregate_by_agent(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by agent."""
        # Agent usage is already aggregated in base stats
        # Create time series from agents_usage
        for agent_id, stats in result.agents_usage.items():
            result.time_series.append({
                "agent": agent_id,
                **stats
            })
    
    async def _aggregate_by_project(
        self,
        metrics: List[ParsedMetric],
        result: AggregationResult
    ) -> None:
        """Aggregate metrics by project path."""
        project_data = defaultdict(lambda: {
            "sessions": set(),
            "users": set(),
            "metrics_count": 0,
            "tool_uses": defaultdict(int),
            "errors": 0,
            "duration_ms": 0,
            "tokens": 0
        })
        
        for metric in metrics:
            # Extract project path from session data
            project_path = None
            if metric.type == MetricType.SESSION_START:
                project_path = metric.entry.data.get("project_path")
            
            if not project_path:
                continue
                
            project = project_data[project_path]
            project["metrics_count"] += 1
            
            if metric.session_id:
                project["sessions"].add(metric.session_id)
            if metric.user_id:
                project["users"].add(metric.user_id)
            if metric.tool_name:
                project["tool_uses"][metric.tool_name] += 1
            if metric.type == MetricType.ERROR_OCCURRED:
                project["errors"] += 1
            if metric.duration_ms:
                project["duration_ms"] += metric.duration_ms
            if metric.token_count:
                project["tokens"] += metric.token_count
        
        # Convert to results
        for project_path, data in project_data.items():
            result.time_series.append({
                "project_path": project_path,
                "sessions": len(data["sessions"]),
                "users": len(data["users"]),
                "metrics_count": data["metrics_count"],
                "tool_uses": dict(data["tool_uses"]),
                "errors": data["errors"],
                "total_duration_ms": data["duration_ms"],
                "tokens": data["tokens"]
            })