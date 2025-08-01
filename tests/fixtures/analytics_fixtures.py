"""
Analytics test fixtures.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
import random
import uuid

from shannon_mcp.analytics.writer import MetricType


class AnalyticsFixtures:
    """Fixtures for Analytics testing."""
    
    @staticmethod
    def create_metric_entry(
        metric_type: MetricType,
        session_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create a single metric entry."""
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
        
        base_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp.isoformat(),
            "type": metric_type.value,
            "session_id": session_id,
            "user_id": f"user_{uuid.uuid4().hex[:6]}",
            "metadata": {}
        }
        
        # Add type-specific data
        if metric_type == MetricType.SESSION_START:
            base_entry["data"] = {
                "project_path": f"/home/user/project_{uuid.uuid4().hex[:6]}",
                "model": random.choice(["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]),
                "temperature": round(random.uniform(0.1, 1.0), 2),
                "max_tokens": random.choice([1024, 2048, 4096, 8192])
            }
        
        elif metric_type == MetricType.SESSION_END:
            base_entry["data"] = {
                "duration_seconds": round(random.uniform(10, 600), 2),
                "total_tokens": random.randint(100, 10000),
                "tools_used": random.randint(0, 20),
                "success": random.random() > 0.1
            }
        
        elif metric_type == MetricType.TOOL_USE:
            tools = ["read_file", "write_file", "bash", "search", "git", "edit"]
            base_entry["data"] = {
                "tool_name": random.choice(tools),
                "success": random.random() > 0.15,
                "duration_ms": random.randint(10, 5000),
                "input_size": random.randint(10, 10000),
                "output_size": random.randint(10, 50000)
            }
        
        elif metric_type == MetricType.TOKEN_USAGE:
            prompt = random.randint(100, 5000)
            completion = random.randint(100, 3000)
            base_entry["data"] = {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
                "model": random.choice(["claude-3-opus", "claude-3-sonnet"])
            }
        
        elif metric_type == MetricType.ERROR_OCCURRED:
            errors = [
                ("TimeoutError", "Operation timed out after 30 seconds"),
                ("ValidationError", "Invalid model specified"),
                ("NetworkError", "Failed to connect to API"),
                ("RateLimitError", "Rate limit exceeded")
            ]
            error_type, message = random.choice(errors)
            base_entry["data"] = {
                "error_type": error_type,
                "error_message": message,
                "stack_trace": f"Traceback:\n  File test.py, line {random.randint(1, 100)}\n  {message}",
                "recoverable": random.random() > 0.5
            }
        
        elif metric_type == MetricType.AGENT_INVOKED:
            base_entry["data"] = {
                "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
                "agent_name": random.choice(["Architecture Agent", "Testing Agent", "Security Agent"]),
                "task": f"Task {random.randint(1, 100)}",
                "duration_seconds": round(random.uniform(1, 30), 2)
            }
        
        elif metric_type == MetricType.CHECKPOINT_CREATED:
            base_entry["data"] = {
                "checkpoint_id": f"checkpoint_{uuid.uuid4().hex[:12]}",
                "message": f"Checkpoint {random.randint(1, 10)}: Implementation complete",
                "files_changed": random.randint(1, 20),
                "lines_added": random.randint(10, 500),
                "lines_removed": random.randint(0, 100)
            }
        
        elif metric_type == MetricType.PERFORMANCE_METRIC:
            base_entry["data"] = {
                "metric_name": random.choice(["cpu_usage", "memory_usage", "disk_io", "network_latency"]),
                "value": round(random.uniform(0, 100), 2),
                "unit": random.choice(["percent", "MB", "ms", "MB/s"]),
                "threshold_exceeded": random.random() > 0.8
            }
        
        else:  # CUSTOM_EVENT
            base_entry["data"] = {
                "event_name": f"custom_event_{random.randint(1, 10)}",
                "custom_field_1": f"value_{uuid.uuid4().hex[:6]}",
                "custom_field_2": random.randint(1, 100)
            }
        
        return base_entry
    
    @staticmethod
    def create_metrics_batch(
        count: int = 100,
        session_count: int = 5,
        time_range_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Create a batch of metrics across multiple sessions."""
        metrics = []
        
        # Generate session IDs
        session_ids = [f"session_{uuid.uuid4().hex[:12]}" for _ in range(session_count)]
        
        # Generate metrics
        start_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)
        
        for i in range(count):
            # Distribute metrics across sessions
            session_id = session_ids[i % session_count]
            
            # Distribute metrics across time
            time_offset = timedelta(hours=time_range_hours * i / count)
            timestamp = start_time + time_offset
            
            # Vary metric types
            metric_type = list(MetricType)[i % len(MetricType)]
            
            metric = AnalyticsFixtures.create_metric_entry(
                metric_type=metric_type,
                session_id=session_id,
                timestamp=timestamp
            )
            
            metrics.append(metric)
        
        return metrics
    
    @staticmethod
    def create_jsonl_file(
        path: Path,
        metrics: List[Dict[str, Any]]
    ) -> Path:
        """Create a JSONL metrics file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            for metric in metrics:
                f.write(json.dumps(metric) + '\n')
        
        return path
    
    @staticmethod
    def create_analytics_directory_structure(
        base_path: Path,
        days: int = 7
    ) -> Dict[str, Path]:
        """Create a realistic analytics directory structure."""
        analytics_dir = base_path / "analytics"
        paths = {}
        
        for i in range(days):
            date = datetime.now(timezone.utc) - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            # Raw metrics
            raw_path = analytics_dir / "raw" / date_str / "metrics.jsonl"
            metrics = AnalyticsFixtures.create_metrics_batch(
                count=50,
                session_count=3,
                time_range_hours=24
            )
            AnalyticsFixtures.create_jsonl_file(raw_path, metrics)
            paths[f"raw_{date_str}"] = raw_path
            
            # Compressed metrics (older than 3 days)
            if i > 3:
                compressed_path = raw_path.with_suffix('.jsonl.zst')
                # In real scenario, would compress the file
                paths[f"compressed_{date_str}"] = compressed_path
        
        # Aggregated data
        agg_path = analytics_dir / "aggregated" / "daily_summary.json"
        agg_path.parent.mkdir(parents=True, exist_ok=True)
        agg_path.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "total_metrics": days * 50
        }, indent=2))
        paths["aggregated"] = agg_path
        
        return paths
    
    @staticmethod
    def create_aggregation_test_data() -> Dict[str, Any]:
        """Create data for testing aggregation functions."""
        sessions = ["session_1", "session_2", "session_3"]
        users = ["user_1", "user_2"]
        
        metrics = []
        start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create metrics with predictable patterns
        for hour in range(24):
            timestamp = start_time + timedelta(hours=hour)
            
            # Session starts - one per session per 8 hours
            if hour % 8 == 0:
                for session in sessions:
                    metrics.append(AnalyticsFixtures.create_metric_entry(
                        MetricType.SESSION_START,
                        session_id=session,
                        timestamp=timestamp
                    ))
            
            # Tool uses - varying by hour
            tools_count = 5 if 9 <= hour <= 17 else 2  # More during work hours
            for _ in range(tools_count):
                session = random.choice(sessions)
                metrics.append(AnalyticsFixtures.create_metric_entry(
                    MetricType.TOOL_USE,
                    session_id=session,
                    timestamp=timestamp + timedelta(minutes=random.randint(0, 59))
                ))
            
            # Token usage - every 2 hours
            if hour % 2 == 0:
                for session in sessions[:2]:  # Only first 2 sessions
                    metrics.append(AnalyticsFixtures.create_metric_entry(
                        MetricType.TOKEN_USAGE,
                        session_id=session,
                        timestamp=timestamp + timedelta(minutes=30)
                    ))
        
        return {
            "metrics": metrics,
            "expected_hourly_tool_uses": {
                "work_hours": 5,
                "off_hours": 2
            },
            "expected_session_counts": len(sessions) * 3,  # 3 starts per session
            "expected_token_events": 12 * 2  # 12 times, 2 sessions
        }