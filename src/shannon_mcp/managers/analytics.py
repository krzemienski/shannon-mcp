"""
Analytics Manager for Shannon MCP Server.

Tracks usage metrics, performance data, and provides analytics queries.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import statistics

from .base import BaseManager, ManagerConfig, ManagerError
from ..utils.logging import get_logger
from ..utils.config import AnalyticsConfig

logger = get_logger("shannon-mcp.managers.analytics")


class MetricType(Enum):
    """Types of metrics tracked."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class QueryType(Enum):
    """Types of analytics queries."""
    USAGE = "usage"
    PERFORMANCE = "performance"
    ERRORS = "errors"
    SESSIONS = "sessions"
    AGENTS = "agents"
    TOOLS = "tools"
    RESOURCES = "resources"
    CUSTOM = "custom"


@dataclass
class Metric:
    """Represents a metric data point."""
    name: str
    type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata
        }


@dataclass
class SessionAnalytics:
    """Analytics data for a session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    message_count: int = 0
    token_count: int = 0
    error_count: int = 0
    tool_calls: Dict[str, int] = field(default_factory=dict)
    resource_accesses: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "message_count": self.message_count,
            "token_count": self.token_count,
            "error_count": self.error_count,
            "tool_calls": self.tool_calls,
            "resource_accesses": self.resource_accesses
        }


@dataclass
class AgentAnalytics:
    """Analytics data for an agent."""
    agent_id: str
    task_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_duration: float = 0.0
    total_duration: float = 0.0
    last_task_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "task_count": self.task_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_count / max(self.task_count, 1),
            "average_duration": self.average_duration,
            "total_duration": self.total_duration,
            "last_task_time": self.last_task_time.isoformat() if self.last_task_time else None
        }


class AnalyticsManager(BaseManager[Metric]):
    """Manages analytics and metrics tracking."""
    
    def __init__(self, config: AnalyticsConfig, metrics=None):
        """Initialize analytics manager."""
        from .base import ManagerConfig
        from pathlib import Path
        
        manager_config = ManagerConfig(
            name="analytics_manager",
            db_path=config.metrics_path / "analytics.db",
            custom_config={"retention_days": config.retention_days, "aggregation_interval": config.aggregation_interval}
        )
        super().__init__(manager_config)
        self.analytics_config: AnalyticsConfig = config
        self.metrics_collector = metrics
        self._metrics: List[Metric] = []
        self._session_analytics: Dict[str, SessionAnalytics] = {}
        self._agent_analytics: Dict[str, AgentAnalytics] = {}
        self._aggregated_data: Dict[str, Dict[str, Any]] = {}
        self._real_time_subscribers: List[Callable] = []
    
    async def _initialize(self) -> None:
        """Initialize analytics manager."""
        logger.info("Initializing analytics manager")
        
        # Load historical data from database
        if self.db:
            await self._load_historical_data()
    
    async def _start(self) -> None:
        """Start analytics manager operations."""
        logger.info("Starting analytics manager")
        
        # Start background tasks
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if hasattr(self.analytics_config, 'export_path') and self.analytics_config.export_path:
            self._export_task = asyncio.create_task(self._export_loop())
    
    async def _stop(self) -> None:
        """Stop analytics manager operations."""
        logger.info("Stopping analytics manager")
        
        # Cancel background tasks
        for task in ['_aggregation_task', '_cleanup_task', '_export_task']:
            if hasattr(self, task):
                getattr(self, task).cancel()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Check analytics manager health."""
        return {
            "healthy": True,
            "metrics_count": len(self._metrics),
            "session_count": len(self._session_analytics),
            "agent_count": len(self._agent_analytics),
            "subscribers": len(self._real_time_subscribers)
        }
    
    async def _create_schema(self) -> None:
        """Create database schema for analytics."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                tags TEXT,
                metadata TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name_timestamp 
            ON metrics(name, timestamp)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
            ON metrics(timestamp)
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS session_analytics (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds REAL,
                message_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                tool_calls TEXT,
                resource_accesses TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_analytics (
                agent_id TEXT PRIMARY KEY,
                task_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                average_duration REAL DEFAULT 0,
                total_duration REAL DEFAULT 0,
                last_task_time TIMESTAMP
            )
        """)
    
    async def track_metric(
        self,
        name: str,
        value: float,
        type: MetricType = MetricType.GAUGE,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a metric value."""
        metric = Metric(
            name=name,
            type=type,
            value=value,
            timestamp=datetime.now(timezone.utc),
            tags=tags or {},
            metadata=metadata or {}
        )
        
        self._metrics.append(metric)
        
        # Keep memory bounded
        if len(self._metrics) > 10000:
            self._metrics = self._metrics[-10000:]
        
        # Persist to database
        if self.db:
            await self._persist_metric(metric)
        
        # Notify real-time subscribers
        if hasattr(self.analytics_config, 'enable_real_time') and self.analytics_config.enable_real_time:
            await self._notify_subscribers(metric)
        
        # Update metrics collector if available
        if self.metrics_collector:
            if type == MetricType.COUNTER:
                self.metrics_collector.increment(name, value)
            elif type == MetricType.GAUGE:
                self.metrics_collector.gauge(name, value)
    
    async def track_event(
        self,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """Track an analytics event."""
        # Extract relevant metrics from event
        if event.startswith("session."):
            await self._track_session_event(event, data)
        elif event.startswith("task."):
            await self._track_task_event(event, data)
        elif event.startswith("tool."):
            await self._track_tool_event(event, data)
        elif event.startswith("resource."):
            await self._track_resource_event(event, data)
        
        # Track generic event metric
        await self.track_metric(
            f"event.{event}",
            1,
            MetricType.COUNTER,
            tags={"event": event}
        )
    
    async def start_session_tracking(self, session_id: str) -> None:
        """Start tracking analytics for a session."""
        self._session_analytics[session_id] = SessionAnalytics(
            session_id=session_id,
            start_time=datetime.now(timezone.utc)
        )
    
    async def get_session_analytics(self, session_id: str) -> Dict[str, Any]:
        """Get analytics for a specific session."""
        analytics = self._session_analytics.get(session_id)
        if not analytics:
            # Try loading from database
            analytics = await self._load_session_analytics(session_id)
        
        return analytics.to_dict() if analytics else {}
    
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """Get metrics for a specific agent."""
        analytics = self._agent_analytics.get(agent_id)
        if not analytics:
            analytics = AgentAnalytics(agent_id=agent_id)
            self._agent_analytics[agent_id] = analytics
        
        return analytics.to_dict()
    
    async def query(
        self,
        query_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an analytics query."""
        try:
            query_enum = QueryType(query_type)
        except ValueError:
            query_enum = QueryType.CUSTOM
        
        if query_enum == QueryType.USAGE:
            return await self._query_usage(parameters)
        elif query_enum == QueryType.PERFORMANCE:
            return await self._query_performance(parameters)
        elif query_enum == QueryType.ERRORS:
            return await self._query_errors(parameters)
        elif query_enum == QueryType.SESSIONS:
            return await self._query_sessions(parameters)
        elif query_enum == QueryType.AGENTS:
            return await self._query_agents(parameters)
        elif query_enum == QueryType.TOOLS:
            return await self._query_tools(parameters)
        elif query_enum == QueryType.RESOURCES:
            return await self._query_resources(parameters)
        else:
            return await self._query_custom(parameters)
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get analytics summary."""
        now = datetime.now(timezone.utc)
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        # Calculate summaries
        total_sessions = len(self._session_analytics)
        active_sessions = sum(1 for s in self._session_analytics.values() if not s.end_time)
        
        # Recent metrics
        recent_metrics = [m for m in self._metrics if m.timestamp > last_hour]
        
        # Error rate
        error_metrics = [m for m in recent_metrics if "error" in m.name]
        error_rate = len(error_metrics) / max(len(recent_metrics), 1)
        
        # Agent utilization
        agent_tasks = sum(a.task_count for a in self._agent_analytics.values())
        agent_success_rate = sum(a.success_count for a in self._agent_analytics.values()) / max(agent_tasks, 1)
        
        return {
            "timestamp": now.isoformat(),
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "metrics_last_hour": len(recent_metrics),
            "error_rate": error_rate,
            "agent_utilization": {
                "total_tasks": agent_tasks,
                "success_rate": agent_success_rate,
                "active_agents": len(self._agent_analytics)
            },
            "top_tools": await self._get_top_tools(5),
            "top_resources": await self._get_top_resources(5)
        }
    
    async def record_metrics(self, metrics: Dict[str, Any]) -> None:
        """Record a batch of metrics."""
        for name, value in metrics.items():
            if isinstance(value, dict):
                # Nested metrics
                for sub_name, sub_value in value.items():
                    await self.track_metric(
                        f"{name}.{sub_name}",
                        sub_value,
                        MetricType.GAUGE
                    )
            else:
                await self.track_metric(name, value, MetricType.GAUGE)
    
    async def format_as_csv(self, results: Dict[str, Any]) -> str:
        """Format query results as CSV."""
        import csv
        import io
        
        output = io.StringIO()
        data = results.get('data', [])
        
        if not data:
            return ""
        
        # Get headers from first row
        headers = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    async def format_as_chart(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Format query results for charting."""
        data = results.get('data', [])
        
        if not data:
            return {"error": "No data to chart"}
        
        # Extract x and y values
        x_values = []
        y_values = []
        
        for row in data:
            if 'timestamp' in row:
                x_values.append(row['timestamp'])
                # Use first numeric value as y
                for key, value in row.items():
                    if key != 'timestamp' and isinstance(value, (int, float)):
                        y_values.append(value)
                        break
        
        return {
            "type": "line",
            "data": {
                "x": x_values,
                "y": y_values
            },
            "options": {
                "title": results.get('query_type', 'Analytics'),
                "x_label": "Time",
                "y_label": "Value"
            }
        }
    
    # Private helper methods
    
    async def _track_session_event(self, event: str, data: Dict[str, Any]) -> None:
        """Track session-related events."""
        session_id = data.get('session_id')
        if not session_id:
            return
        
        analytics = self._session_analytics.get(session_id)
        if not analytics:
            analytics = SessionAnalytics(
                session_id=session_id,
                start_time=datetime.now(timezone.utc)
            )
            self._session_analytics[session_id] = analytics
        
        if event == "session.created":
            analytics.start_time = datetime.now(timezone.utc)
        elif event == "session.completed":
            analytics.end_time = datetime.now(timezone.utc)
            analytics.duration_seconds = (analytics.end_time - analytics.start_time).total_seconds()
        elif event == "session.message":
            analytics.message_count += 1
            analytics.token_count += data.get('tokens', 0)
        elif event == "session.error":
            analytics.error_count += 1
    
    async def _track_task_event(self, event: str, data: Dict[str, Any]) -> None:
        """Track task-related events."""
        agent_id = data.get('agent_id')
        if not agent_id:
            return
        
        analytics = self._agent_analytics.get(agent_id)
        if not analytics:
            analytics = AgentAnalytics(agent_id=agent_id)
            self._agent_analytics[agent_id] = analytics
        
        if event == "task.assigned":
            analytics.task_count += 1
            analytics.last_task_time = datetime.now(timezone.utc)
        elif event == "task.completed":
            analytics.success_count += 1
            duration = data.get('duration', 0)
            analytics.total_duration += duration
            analytics.average_duration = analytics.total_duration / analytics.task_count
        elif event == "task.failed":
            analytics.failure_count += 1
    
    async def _track_tool_event(self, event: str, data: Dict[str, Any]) -> None:
        """Track tool usage events."""
        tool_name = data.get('tool')
        session_id = data.get('session_id')
        
        if session_id and tool_name:
            analytics = self._session_analytics.get(session_id)
            if analytics:
                if tool_name not in analytics.tool_calls:
                    analytics.tool_calls[tool_name] = 0
                analytics.tool_calls[tool_name] += 1
        
        # Track global tool usage
        await self.track_metric(
            f"tool.{tool_name}.calls",
            1,
            MetricType.COUNTER
        )
    
    async def _track_resource_event(self, event: str, data: Dict[str, Any]) -> None:
        """Track resource access events."""
        resource_uri = data.get('resource')
        session_id = data.get('session_id')
        
        if session_id and resource_uri:
            analytics = self._session_analytics.get(session_id)
            if analytics:
                if resource_uri not in analytics.resource_accesses:
                    analytics.resource_accesses[resource_uri] = 0
                analytics.resource_accesses[resource_uri] += 1
        
        # Track global resource usage
        await self.track_metric(
            f"resource.{resource_uri}.accesses",
            1,
            MetricType.COUNTER
        )
    
    async def _query_usage(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query usage metrics."""
        metric = parameters.get('metric', 'session_count')
        timeframe = parameters.get('timeframe', 'last_hour')
        
        # Calculate time range
        now = datetime.now(timezone.utc)
        if timeframe == 'last_hour':
            start_time = now - timedelta(hours=1)
        elif timeframe == 'last_day':
            start_time = now - timedelta(days=1)
        elif timeframe == 'last_week':
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(hours=1)
        
        # Query metrics
        if metric == 'session_count':
            sessions = [s for s in self._session_analytics.values() 
                       if s.start_time > start_time]
            return {
                "data": [{"count": len(sessions), "timestamp": now.isoformat()}],
                "metric": metric,
                "timeframe": timeframe
            }
        else:
            # Query from metrics
            metrics = [m for m in self._metrics 
                      if m.name == metric and m.timestamp > start_time]
            
            return {
                "data": [{"value": m.value, "timestamp": m.timestamp.isoformat()} 
                        for m in metrics],
                "metric": metric,
                "timeframe": timeframe
            }
    
    async def _query_performance(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query performance metrics."""
        # Implementation would query performance-related metrics
        return {"data": [], "query_type": "performance"}
    
    async def _query_errors(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query error metrics."""
        # Implementation would query error-related metrics
        return {"data": [], "query_type": "errors"}
    
    async def _query_sessions(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query session analytics."""
        limit = parameters.get('limit', 100)
        
        sessions = list(self._session_analytics.values())
        sessions.sort(key=lambda s: s.start_time, reverse=True)
        
        return {
            "data": [s.to_dict() for s in sessions[:limit]],
            "query_type": "sessions",
            "total": len(sessions)
        }
    
    async def _query_agents(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query agent analytics."""
        agents = list(self._agent_analytics.values())
        agents.sort(key=lambda a: a.task_count, reverse=True)
        
        return {
            "data": [a.to_dict() for a in agents],
            "query_type": "agents",
            "total": len(agents)
        }
    
    async def _query_tools(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query tool usage analytics."""
        # Aggregate tool usage across sessions
        tool_usage = {}
        for analytics in self._session_analytics.values():
            for tool, count in analytics.tool_calls.items():
                if tool not in tool_usage:
                    tool_usage[tool] = 0
                tool_usage[tool] += count
        
        # Sort by usage
        sorted_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "data": [{"tool": tool, "calls": count} for tool, count in sorted_tools],
            "query_type": "tools"
        }
    
    async def _query_resources(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Query resource usage analytics."""
        # Similar to tools
        resource_usage = {}
        for analytics in self._session_analytics.values():
            for resource, count in analytics.resource_accesses.items():
                if resource not in resource_usage:
                    resource_usage[resource] = 0
                resource_usage[resource] += count
        
        sorted_resources = sorted(resource_usage.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "data": [{"resource": res, "accesses": count} for res, count in sorted_resources],
            "query_type": "resources"
        }
    
    async def _query_custom(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom analytics query."""
        # Would support custom SQL or aggregation queries
        return {"data": [], "query_type": "custom"}
    
    async def _get_top_tools(self, limit: int) -> List[Dict[str, Any]]:
        """Get top used tools."""
        result = await self._query_tools({})
        return result['data'][:limit]
    
    async def _get_top_resources(self, limit: int) -> List[Dict[str, Any]]:
        """Get top accessed resources."""
        result = await self._query_resources({})
        return result['data'][:limit]
    
    async def _aggregation_loop(self) -> None:
        """Background task to aggregate metrics."""
        while True:
            try:
                await asyncio.sleep(self.analytics_config.aggregation_interval)
                await self._aggregate_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation error: {e}")
    
    async def _aggregate_metrics(self) -> None:
        """Aggregate metrics for efficient querying."""
        # Would implement metric aggregation logic
        pass
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean old data."""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                await self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _cleanup_old_data(self) -> None:
        """Clean up data older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.analytics_config.retention_days)
        
        # Clean metrics
        self._metrics = [m for m in self._metrics if m.timestamp > cutoff]
        
        # Clean from database
        if self.db:
            await self.db.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            await self.db.commit()
    
    async def _export_loop(self) -> None:
        """Background task to export analytics."""
        while True:
            try:
                await asyncio.sleep(getattr(self.analytics_config, 'export_interval', 3600))
                await self._export_analytics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Export error: {e}")
    
    async def _export_analytics(self) -> None:
        """Export analytics to external storage."""
        # Would implement export to file/S3/etc
        pass
    
    async def _notify_subscribers(self, metric: Metric) -> None:
        """Notify real-time subscribers of new metric."""
        for subscriber in self._real_time_subscribers:
            try:
                await subscriber(metric)
            except Exception as e:
                logger.error(f"Subscriber notification error: {e}")
    
    async def _load_historical_data(self) -> None:
        """Load historical analytics from database."""
        # Load recent metrics
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = await self.execute_query(
            "SELECT * FROM metrics WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 1000",
            (cutoff.isoformat(),)
        )
        
        for row in rows:
            metric = Metric(
                name=row['name'],
                type=MetricType(row['type']),
                value=row['value'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                tags=json.loads(row['tags'] or '{}'),
                metadata=json.loads(row['metadata'] or '{}')
            )
            self._metrics.append(metric)
        
        # Load session analytics
        rows = await self.execute_query(
            "SELECT * FROM session_analytics WHERE start_time > ?",
            (cutoff.isoformat(),)
        )
        
        for row in rows:
            analytics = SessionAnalytics(
                session_id=row['session_id'],
                start_time=datetime.fromisoformat(row['start_time']),
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                duration_seconds=row['duration_seconds'] or 0,
                message_count=row['message_count'],
                token_count=row['token_count'],
                error_count=row['error_count'],
                tool_calls=json.loads(row['tool_calls'] or '{}'),
                resource_accesses=json.loads(row['resource_accesses'] or '{}')
            )
            self._session_analytics[analytics.session_id] = analytics
    
    async def _load_session_analytics(self, session_id: str) -> Optional[SessionAnalytics]:
        """Load session analytics from database."""
        if not self.db:
            return None
        
        row = await self.db.execute_fetchone(
            "SELECT * FROM session_analytics WHERE session_id = ?",
            (session_id,)
        )
        
        if not row:
            return None
        
        return SessionAnalytics(
            session_id=row['session_id'],
            start_time=datetime.fromisoformat(row['start_time']),
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
            duration_seconds=row['duration_seconds'] or 0,
            message_count=row['message_count'],
            token_count=row['token_count'],
            error_count=row['error_count'],
            tool_calls=json.loads(row['tool_calls'] or '{}'),
            resource_accesses=json.loads(row['resource_accesses'] or '{}')
        )
    
    async def _persist_metric(self, metric: Metric) -> None:
        """Persist metric to database."""
        await self.db.execute("""
            INSERT INTO metrics (name, type, value, timestamp, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            metric.name,
            metric.type.value,
            metric.value,
            metric.timestamp.isoformat(),
            json.dumps(metric.tags),
            json.dumps(metric.metadata)
        ))
        await self.db.commit()
    
    async def subscribe_real_time(self, callback: Callable) -> None:
        """Subscribe to real-time metric updates."""
        if hasattr(self.analytics_config, 'enable_real_time') and self.analytics_config.enable_real_time:
            self._real_time_subscribers.append(callback)
            logger.info(f"Added real-time subscriber, total: {len(self._real_time_subscribers)}")
    
    async def unsubscribe_real_time(self, callback: Callable) -> None:
        """Unsubscribe from real-time metric updates."""
        if callback in self._real_time_subscribers:
            self._real_time_subscribers.remove(callback)
            logger.info(f"Removed real-time subscriber, remaining: {len(self._real_time_subscribers)}")