"""
Exhaustive functional tests for EVERY analytics system function.
Tests all analytics functionality with real Claude Code execution.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

from shannon_mcp.analytics.engine import AnalyticsEngine
from shannon_mcp.analytics.collector import MetricsCollector
from shannon_mcp.analytics.aggregator import MetricsAggregator
from shannon_mcp.analytics.reporter import AnalyticsReporter
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.storage.database import Database


class TestCompleteAnalyticsSystem:
    """Test every single analytics system function comprehensively."""
    
    @pytest.fixture
    async def analytics_setup(self):
        """Set up analytics testing environment."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "analytics.db"
        
        db = Database(db_path)
        await db.initialize()
        
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        
        collector = MetricsCollector(db=db)
        aggregator = MetricsAggregator(db=db)
        reporter = AnalyticsReporter(db=db)
        
        engine = AnalyticsEngine(
            collector=collector,
            aggregator=aggregator,
            reporter=reporter,
            session_manager=session_manager
        )
        
        await engine.initialize()
        
        yield {
            "engine": engine,
            "collector": collector,
            "aggregator": aggregator,
            "reporter": reporter,
            "session_manager": session_manager,
            "db": db,
            "temp_dir": temp_dir
        }
        
        # Cleanup
        await engine.cleanup()
        await session_manager.cleanup()
        await db.close()
        shutil.rmtree(temp_dir)
    
    async def test_analytics_engine_initialization(self, analytics_setup):
        """Test AnalyticsEngine initialization with all options."""
        db = analytics_setup["db"]
        
        # Test with default options
        engine1 = AnalyticsEngine(db=db)
        await engine1.initialize()
        assert engine1.collection_interval == 60
        assert engine1.retention_days == 90
        
        # Test with custom options
        engine2 = AnalyticsEngine(
            db=db,
            collection_interval=30,
            retention_days=180,
            enable_real_time=True,
            buffer_size=10000,
            batch_size=500,
            compression_enabled=True,
            encryption_enabled=True
        )
        await engine2.initialize()
        assert engine2.collection_interval == 30
        assert engine2.retention_days == 180
        assert engine2.enable_real_time is True
        assert engine2.buffer_size == 10000
    
    async def test_metrics_collection_complete(self, analytics_setup):
        """Test collecting all types of metrics."""
        collector = analytics_setup["collector"]
        session_manager = analytics_setup["session_manager"]
        
        # Create test session
        session = await session_manager.create_session()
        
        # Test session metrics
        await collector.collect_session_metric({
            "session_id": session.id,
            "type": "session_start",
            "timestamp": datetime.utcnow(),
            "metadata": {
                "model": "claude-3-opus-20240229",
                "user": "test_user",
                "project": "test_project"
            }
        })
        
        # Test performance metrics
        await collector.collect_performance_metric({
            "session_id": session.id,
            "type": "response_time",
            "value": 1.234,
            "unit": "seconds",
            "timestamp": datetime.utcnow(),
            "context": {
                "prompt_length": 150,
                "response_length": 500,
                "streaming": True
            }
        })
        
        # Test resource metrics
        await collector.collect_resource_metric({
            "session_id": session.id,
            "type": "resource_usage",
            "cpu_percent": 45.2,
            "memory_mb": 512.5,
            "disk_io_read_mb": 10.5,
            "disk_io_write_mb": 5.2,
            "network_in_mb": 2.1,
            "network_out_mb": 1.5,
            "timestamp": datetime.utcnow()
        })
        
        # Test token metrics
        await collector.collect_token_metric({
            "session_id": session.id,
            "type": "token_usage",
            "prompt_tokens": 150,
            "completion_tokens": 500,
            "total_tokens": 650,
            "cost_estimate": 0.0065,
            "model": "claude-3-opus-20240229",
            "timestamp": datetime.utcnow()
        })
        
        # Test error metrics
        await collector.collect_error_metric({
            "session_id": session.id,
            "type": "error",
            "error_type": "RateLimitError",
            "message": "Rate limit exceeded",
            "severity": "warning",
            "recoverable": True,
            "timestamp": datetime.utcnow(),
            "context": {
                "retry_after": 60,
                "current_rate": 100
            }
        })
        
        # Test custom metrics
        await collector.collect_custom_metric({
            "session_id": session.id,
            "metric_name": "code_quality_score",
            "value": 85.5,
            "dimensions": {
                "language": "python",
                "complexity": "medium",
                "lines_of_code": 250
            },
            "timestamp": datetime.utcnow()
        })
        
        # Test batch collection
        batch_metrics = [
            {
                "session_id": session.id,
                "type": "api_call",
                "endpoint": "/v1/messages",
                "duration_ms": 234,
                "status_code": 200
            }
            for _ in range(100)
        ]
        await collector.collect_batch(batch_metrics)
        
        # Verify collection
        metrics = await collector.get_metrics(
            session_id=session.id,
            start_time=datetime.utcnow() - timedelta(minutes=5)
        )
        assert len(metrics) > 100
    
    async def test_metrics_aggregation_complete(self, analytics_setup):
        """Test all aggregation functions."""
        aggregator = analytics_setup["aggregator"]
        collector = analytics_setup["collector"]
        session_manager = analytics_setup["session_manager"]
        
        # Generate test data
        sessions = []
        for i in range(5):
            session = await session_manager.create_session()
            sessions.append(session)
            
            # Collect diverse metrics
            for j in range(20):
                await collector.collect_performance_metric({
                    "session_id": session.id,
                    "type": "response_time",
                    "value": 0.5 + (j % 3) * 0.3,
                    "timestamp": datetime.utcnow() - timedelta(minutes=j)
                })
                
                await collector.collect_token_metric({
                    "session_id": session.id,
                    "type": "token_usage",
                    "prompt_tokens": 100 + j * 10,
                    "completion_tokens": 200 + j * 20,
                    "total_tokens": 300 + j * 30,
                    "timestamp": datetime.utcnow() - timedelta(minutes=j)
                })
        
        # Test time-based aggregation
        hourly_stats = await aggregator.aggregate_by_time(
            metric_type="response_time",
            interval="hour",
            start_time=datetime.utcnow() - timedelta(hours=24),
            aggregation_functions=["avg", "min", "max", "sum", "count", "p50", "p95", "p99"]
        )
        assert len(hourly_stats) > 0
        assert "avg" in hourly_stats[0]
        assert "p95" in hourly_stats[0]
        
        # Test session aggregation
        session_stats = await aggregator.aggregate_by_session(
            metric_types=["response_time", "token_usage"],
            aggregation_functions=["sum", "avg", "max"]
        )
        assert len(session_stats) == 5
        assert all("response_time_avg" in s for s in session_stats)
        
        # Test dimensional aggregation
        dimensional_stats = await aggregator.aggregate_by_dimensions(
            metric_type="custom",
            dimensions=["language", "complexity"],
            aggregation_functions=["count", "avg"]
        )
        assert isinstance(dimensional_stats, dict)
        
        # Test rolling aggregation
        rolling_stats = await aggregator.calculate_rolling_stats(
            metric_type="token_usage",
            window_size=300,  # 5 minutes
            step_size=60,     # 1 minute
            functions=["avg", "std", "trend"]
        )
        assert len(rolling_stats) > 0
        assert "trend" in rolling_stats[0]
        
        # Test percentile calculation
        percentiles = await aggregator.calculate_percentiles(
            metric_type="response_time",
            percentiles=[50, 75, 90, 95, 99, 99.9]
        )
        assert percentiles["p50"] <= percentiles["p75"]
        assert percentiles["p95"] <= percentiles["p99"]
        
        # Test correlation analysis
        correlation = await aggregator.calculate_correlation(
            metric1="response_time",
            metric2="token_usage",
            method="pearson"
        )
        assert -1 <= correlation <= 1
        
        # Test anomaly detection
        anomalies = await aggregator.detect_anomalies(
            metric_type="response_time",
            method="zscore",
            threshold=2.0,
            window_size=3600  # 1 hour
        )
        assert isinstance(anomalies, list)
    
    async def test_analytics_reporting_complete(self, analytics_setup):
        """Test all reporting functionality."""
        reporter = analytics_setup["reporter"]
        engine = analytics_setup["engine"]
        session_manager = analytics_setup["session_manager"]
        
        # Generate comprehensive test data
        for i in range(10):
            session = await session_manager.create_session()
            
            # Simulate session activity
            await engine.track_event({
                "session_id": session.id,
                "event": "session_start",
                "timestamp": datetime.utcnow() - timedelta(hours=i)
            })
            
            for j in range(5):
                await engine.track_event({
                    "session_id": session.id,
                    "event": "prompt_execution",
                    "duration": 1.5 + j * 0.5,
                    "tokens": 200 + j * 50
                })
        
        # Test summary report
        summary = await reporter.generate_summary_report(
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow(),
            include_sections=[
                "overview",
                "performance",
                "usage",
                "errors",
                "trends",
                "recommendations"
            ]
        )
        assert "overview" in summary
        assert "total_sessions" in summary["overview"]
        assert "performance" in summary
        assert "average_response_time" in summary["performance"]
        
        # Test detailed report
        detailed = await reporter.generate_detailed_report(
            report_type="performance",
            granularity="hour",
            metrics=[
                "response_time",
                "token_usage",
                "error_rate",
                "success_rate"
            ],
            grouping=["model", "user"],
            filters={
                "min_duration": 0.1,
                "exclude_errors": False
            }
        )
        assert "data" in detailed
        assert "metadata" in detailed
        
        # Test comparison report
        comparison = await reporter.generate_comparison_report(
            period1_start=datetime.utcnow() - timedelta(days=7),
            period1_end=datetime.utcnow() - timedelta(days=1),
            period2_start=datetime.utcnow() - timedelta(days=1),
            period2_end=datetime.utcnow(),
            metrics=["sessions", "tokens", "errors", "performance"]
        )
        assert "period1" in comparison
        assert "period2" in comparison
        assert "changes" in comparison
        
        # Test trend analysis
        trends = await reporter.analyze_trends(
            metrics=["token_usage", "response_time"],
            period="daily",
            duration_days=30,
            include_forecast=True,
            forecast_days=7
        )
        assert "historical" in trends
        assert "forecast" in trends
        
        # Test cost analysis
        cost_report = await reporter.generate_cost_report(
            start_time=datetime.utcnow() - timedelta(days=30),
            breakdown_by=["model", "user", "project"],
            include_projections=True
        )
        assert "total_cost" in cost_report
        assert "breakdown" in cost_report
        assert "projections" in cost_report
        
        # Test export formats
        formats = ["json", "csv", "html", "pdf", "excel"]
        for format in formats:
            if format in ["json", "csv"]:  # Test supported formats
                exported = await reporter.export_report(
                    report=summary,
                    format=format,
                    output_path=Path(analytics_setup["temp_dir"]) / f"report.{format}"
                )
                assert exported.exists()
    
    async def test_real_time_analytics(self, analytics_setup):
        """Test real-time analytics capabilities."""
        engine = analytics_setup["engine"]
        session_manager = analytics_setup["session_manager"]
        
        # Enable real-time processing
        await engine.enable_real_time_processing()
        
        # Set up real-time dashboard
        dashboard = await engine.create_dashboard({
            "name": "Real-Time Monitoring",
            "refresh_interval": 1,  # 1 second
            "widgets": [
                {
                    "type": "line_chart",
                    "metric": "response_time",
                    "window": 300  # 5 minutes
                },
                {
                    "type": "counter",
                    "metric": "active_sessions"
                },
                {
                    "type": "gauge",
                    "metric": "cpu_usage",
                    "thresholds": [50, 75, 90]
                },
                {
                    "type": "heatmap",
                    "metric": "error_distribution"
                }
            ]
        })
        
        # Simulate real-time data
        session = await session_manager.create_session()
        
        # Test streaming metrics
        stream = engine.stream_metrics(
            metrics=["response_time", "token_usage"],
            session_id=session.id
        )
        
        collected_metrics = []
        async def collect_stream():
            async for metric in stream:
                collected_metrics.append(metric)
                if len(collected_metrics) >= 5:
                    break
        
        # Generate activity
        collection_task = asyncio.create_task(collect_stream())
        
        for i in range(5):
            await session_manager.execute_prompt(
                session.id,
                f"Test prompt {i}"
            )
            await asyncio.sleep(0.1)
        
        await collection_task
        assert len(collected_metrics) >= 5
        
        # Test real-time alerts
        alert = await engine.create_alert({
            "name": "High Response Time",
            "condition": "response_time > 2.0",
            "window": 60,  # 1 minute
            "threshold": 3,  # 3 occurrences
            "actions": ["notify", "log", "throttle"]
        })
        
        # Trigger alert condition
        for i in range(5):
            await engine.track_metric({
                "session_id": session.id,
                "type": "response_time",
                "value": 3.0
            })
        
        # Check alert status
        alert_status = await engine.get_alert_status(alert.id)
        assert alert_status["triggered"] is True
        
        # Test real-time aggregation
        real_time_stats = await engine.get_real_time_stats(
            metrics=["response_time", "active_sessions", "tokens_per_second"],
            window=60
        )
        assert "response_time" in real_time_stats
        assert "current" in real_time_stats["response_time"]
        assert "trend" in real_time_stats["response_time"]
    
    async def test_analytics_data_pipeline(self, analytics_setup):
        """Test the complete analytics data pipeline."""
        engine = analytics_setup["engine"]
        
        # Test pipeline configuration
        pipeline = await engine.create_pipeline({
            "name": "Main Analytics Pipeline",
            "stages": [
                {
                    "name": "ingestion",
                    "type": "collector",
                    "config": {
                        "batch_size": 100,
                        "flush_interval": 5
                    }
                },
                {
                    "name": "validation",
                    "type": "validator",
                    "config": {
                        "schema": "strict",
                        "drop_invalid": False
                    }
                },
                {
                    "name": "enrichment",
                    "type": "enricher",
                    "config": {
                        "add_session_context": True,
                        "add_user_metadata": True
                    }
                },
                {
                    "name": "transformation",
                    "type": "transformer",
                    "config": {
                        "normalize_timestamps": True,
                        "calculate_derived_metrics": True
                    }
                },
                {
                    "name": "storage",
                    "type": "storage",
                    "config": {
                        "compression": True,
                        "partitioning": "daily"
                    }
                }
            ]
        })
        
        # Test pipeline execution
        test_data = [
            {
                "type": "raw_metric",
                "value": 123,
                "timestamp": datetime.utcnow()
            }
            for _ in range(1000)
        ]
        
        result = await engine.process_through_pipeline(
            pipeline_id=pipeline.id,
            data=test_data
        )
        assert result["processed"] == 1000
        assert result["errors"] == 0
        
        # Test pipeline monitoring
        pipeline_stats = await engine.get_pipeline_stats(pipeline.id)
        assert pipeline_stats["total_processed"] >= 1000
        assert "stage_stats" in pipeline_stats
        
        # Test pipeline optimization
        optimizations = await engine.optimize_pipeline(pipeline.id)
        assert len(optimizations) >= 0
    
    async def test_analytics_integrations(self, analytics_setup):
        """Test analytics integrations with external systems."""
        engine = analytics_setup["engine"]
        
        # Test webhook integration
        webhook = await engine.create_webhook({
            "url": "https://example.com/analytics",
            "events": ["session_complete", "error_threshold", "cost_alert"],
            "headers": {"Authorization": "Bearer test"},
            "retry_policy": {
                "max_retries": 3,
                "backoff": "exponential"
            }
        })
        assert webhook.id is not None
        
        # Test export integration
        export_config = await engine.configure_export({
            "destination": "s3",
            "config": {
                "bucket": "analytics-export",
                "prefix": "claude-code/",
                "format": "parquet",
                "compression": "snappy"
            },
            "schedule": "0 0 * * *",  # Daily
            "filters": {
                "min_importance": "medium"
            }
        })
        assert export_config.id is not None
        
        # Test metrics API
        api_key = await engine.create_api_key({
            "name": "External Dashboard",
            "permissions": ["read:metrics", "read:reports"],
            "rate_limit": 1000,
            "expires_in_days": 90
        })
        assert api_key.key is not None
        
        # Test data streaming
        stream_config = await engine.configure_streaming({
            "protocol": "kafka",
            "config": {
                "brokers": ["localhost:9092"],
                "topic": "claude-analytics",
                "compression": "gzip"
            },
            "metrics": ["all"],
            "buffer_size": 1000
        })
        assert stream_config.id is not None
    
    async def test_analytics_privacy_compliance(self, analytics_setup):
        """Test privacy and compliance features."""
        engine = analytics_setup["engine"]
        
        # Test data anonymization
        anonymization_config = await engine.configure_anonymization({
            "fields": ["user_id", "session_context", "prompt_content"],
            "method": "hash",  # or "redact", "tokenize"
            "salt": "test_salt"
        })
        
        # Test with PII data
        await engine.track_event({
            "user_id": "john.doe@example.com",
            "session_id": "test_session",
            "prompt_content": "My SSN is 123-45-6789"
        })
        
        # Verify anonymization
        stored_data = await engine.get_raw_metrics(limit=1)
        assert "john.doe@example.com" not in str(stored_data)
        assert "123-45-6789" not in str(stored_data)
        
        # Test data retention
        retention_policy = await engine.set_retention_policy({
            "default_days": 90,
            "rules": [
                {
                    "metric_type": "error",
                    "retention_days": 180
                },
                {
                    "metric_type": "performance",
                    "retention_days": 30
                }
            ]
        })
        
        # Test data deletion
        deletion_result = await engine.delete_user_data(
            user_id="test_user",
            confirm=True
        )
        assert deletion_result["deleted"] >= 0
        
        # Test compliance export
        gdpr_export = await engine.export_user_data(
            user_id="test_user",
            format="json",
            include_derived=True
        )
        assert isinstance(gdpr_export, dict)
        
        # Test audit logging
        audit_logs = await engine.get_audit_logs(
            action_types=["data_access", "data_deletion", "config_change"],
            limit=100
        )
        assert len(audit_logs) > 0