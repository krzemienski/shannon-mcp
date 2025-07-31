---
name: mcp-implement-analytics
description: Implement analytics and telemetry system with OpenTelemetry
category: mcp-component-implementation
---

# MCP Analytics Implementation

Orchestrates the implementation of the analytics and telemetry system using OpenTelemetry standards.

## Overview

This command coordinates the implementation of Tasks 9-10: Usage Analytics and Performance Metrics, establishing comprehensive observability for the MCP server.

## Usage

```bash
/mcp-implement-analytics [action] [options]
```

### Actions

#### `start` - Begin implementation
```bash
/mcp-implement-analytics start
```

Workflow sequence:
1. Monitoring Agent designs OpenTelemetry architecture
2. Analytics Agent implements metrics collection
3. Storage Agent creates analytics database
4. Performance Agent adds monitoring
5. Testing Agent validates telemetry

#### `setup-otel` - Configure OpenTelemetry
```bash
/mcp-implement-analytics setup-otel --exporter [otlp|prometheus|console]
```

Telemetry Agent configures:
- OTLP exporters for traces/metrics
- Prometheus scraping endpoint
- Semantic conventions
- Context propagation
- Sampling strategies

#### `implement-metrics` - Create metrics collectors
```bash
/mcp-implement-analytics implement-metrics --category [session|performance|usage]
```

Categories:
- `session`: Session lifecycle metrics
- `performance`: Latency and throughput metrics
- `usage`: Feature usage analytics

#### `dashboard` - Generate monitoring dashboards
```bash
/mcp-implement-analytics dashboard --format [grafana|prometheus]
```

Creates dashboard configurations for:
- Session activity monitoring
- Performance metrics
- Error rates and alerts
- Resource utilization

## Implementation Architecture

### Phase 1: OpenTelemetry Setup (Telemetry Agent)
```python
from opentelemetry import trace, metrics
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.exporter.otlp.proto.grpc import (
    trace_exporter, metrics_exporter
)

class TelemetrySystem:
    """Comprehensive telemetry with OpenTelemetry"""
    
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self._setup_providers()
        self._setup_instrumentations()
        
    def _setup_providers(self):
        """Configure trace and metrics providers"""
        # Trace provider with OTLP export
        trace_provider = TracerProvider(
            resource=Resource.create({
                "service.name": "claude-code-mcp",
                "service.version": __version__,
                "deployment.environment": self.config.environment
            })
        )
        
        # Add OTLP exporter
        otlp_exporter = trace_exporter.OTLPSpanExporter(
            endpoint=self.config.otlp_endpoint,
            headers=self.config.otlp_headers
        )
        
        trace_provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        
        trace.set_tracer_provider(trace_provider)
        
        # Metrics provider
        metrics_provider = MeterProvider(
            resource=Resource.create({
                "service.name": "claude-code-mcp"
            }),
            metric_readers=[
                PeriodicExportingMetricReader(
                    metrics_exporter.OTLPMetricExporter(),
                    export_interval_millis=10000
                )
            ]
        )
        
        metrics.set_meter_provider(metrics_provider)
        
    def _setup_instrumentations(self):
        """Auto-instrument libraries"""
        # Asyncio instrumentation
        AsyncioInstrumentor().instrument()
        
        # Custom instrumentations
        self._instrument_sessions()
        self._instrument_storage()
```

### Phase 2: Metrics Collection (Analytics Agent)
```python
class MetricsCollector:
    """Collect and expose metrics"""
    
    def __init__(self):
        self.meter = metrics.get_meter("claude-code-mcp")
        self._create_metrics()
        
    def _create_metrics(self):
        """Define all metrics with semantic conventions"""
        # Session metrics
        self.session_counter = self.meter.create_counter(
            name="mcp.sessions.total",
            description="Total number of Claude sessions created",
            unit="1"
        )
        
        self.session_duration = self.meter.create_histogram(
            name="mcp.session.duration",
            description="Duration of Claude sessions",
            unit="s",
            boundaries=[0.1, 0.5, 1, 5, 10, 30, 60, 300, 600]
        )
        
        self.active_sessions = self.meter.create_up_down_counter(
            name="mcp.sessions.active",
            description="Number of active sessions",
            unit="1"
        )
        
        # Performance metrics
        self.message_latency = self.meter.create_histogram(
            name="mcp.message.latency",
            description="Time to process messages",
            unit="ms",
            boundaries=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
        )
        
        self.streaming_throughput = self.meter.create_histogram(
            name="mcp.streaming.throughput",
            description="Messages processed per second",
            unit="msg/s"
        )
        
        # Resource metrics
        self.checkpoint_size = self.meter.create_histogram(
            name="mcp.checkpoint.size",
            description="Size of saved checkpoints",
            unit="By",
            boundaries=[1024, 10240, 102400, 1048576, 10485760]
        )
        
    async def record_session_start(self, session: Session):
        """Record session start metrics"""
        self.session_counter.add(1, {
            "model": session.model,
            "restored": str(session.checkpoint_id is not None)
        })
        self.active_sessions.add(1)
        
    async def record_session_end(self, session: Session, duration: float):
        """Record session completion"""
        self.session_duration.record(duration, {
            "model": session.model,
            "status": session.status
        })
        self.active_sessions.add(-1)
```

### Phase 3: Distributed Tracing (Telemetry Agent)
```python
class TracedSessionManager:
    """Session manager with distributed tracing"""
    
    def __init__(self):
        self.tracer = trace.get_tracer("mcp.session_manager")
        
    async def create_session(self, prompt: str, model: str) -> Session:
        """Create session with full tracing"""
        with self.tracer.start_as_current_span(
            "session.create",
            kind=trace.SpanKind.SERVER
        ) as span:
            span.set_attributes({
                "mcp.model": model,
                "mcp.prompt.length": len(prompt),
                "mcp.session.type": "new"
            })
            
            # Binary discovery span
            with self.tracer.start_as_current_span("binary.discover"):
                binary = await self.binary_manager.discover()
                span.set_attribute("mcp.binary.version", binary.version)
            
            # Process start span
            with self.tracer.start_as_current_span("process.start"):
                session = Session(id=generate_id(), model=model)
                await session.start(prompt)
                
            # Record session created event
            span.add_event("session.created", {
                "mcp.session.id": session.id,
                "mcp.process.pid": session.process.pid
            })
            
            return session
```

### Phase 4: Analytics Storage (Storage Agent)
```python
class AnalyticsDatabase:
    """Optimized storage for analytics data"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()
        
    async def _init_schema(self):
        """Create analytics tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Session analytics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS session_metrics (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    token_count INTEGER,
                    message_count INTEGER,
                    checkpoint_count INTEGER,
                    error_count INTEGER,
                    INDEX idx_start_time (start_time),
                    INDEX idx_model (model)
                )
            """)
            
            # Performance metrics (time-series)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    timestamp TIMESTAMP NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    labels TEXT,  -- JSON
                    PRIMARY KEY (timestamp, metric_name)
                )
            """)
            
            # Feature usage
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feature_usage (
                    date DATE NOT NULL,
                    feature TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    unique_users INTEGER DEFAULT 0,
                    PRIMARY KEY (date, feature)
                )
            """)
```

### Phase 5: Monitoring Dashboards (Analytics Agent)
```python
# Grafana dashboard configuration
GRAFANA_DASHBOARD = {
    "dashboard": {
        "title": "Claude Code MCP Server",
        "panels": [
            {
                "title": "Active Sessions",
                "targets": [{
                    "expr": "mcp_sessions_active"
                }],
                "type": "graph"
            },
            {
                "title": "Session Duration (p95)",
                "targets": [{
                    "expr": 'histogram_quantile(0.95, mcp_session_duration_bucket)'
                }],
                "type": "graph"
            },
            {
                "title": "Message Processing Latency",
                "targets": [{
                    "expr": 'rate(mcp_message_latency_sum[5m]) / rate(mcp_message_latency_count[5m])'
                }],
                "type": "graph"
            },
            {
                "title": "Error Rate",
                "targets": [{
                    "expr": 'rate(mcp_errors_total[5m])'
                }],
                "type": "graph"
            }
        ]
    }
}

# Prometheus alerts
PROMETHEUS_ALERTS = """
groups:
  - name: mcp_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(mcp_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          
      - alert: SessionLeaks
        expr: mcp_sessions_active > 100
        for: 10m
        annotations:
          summary: "Possible session leak"
          
      - alert: HighLatency
        expr: histogram_quantile(0.95, mcp_message_latency_bucket) > 1000
        for: 5m
        annotations:
          summary: "High message processing latency"
"""
```

## Success Criteria

1. **Observability Coverage**: 100% of critical paths traced
2. **Metrics Cardinality**: <10,000 unique series
3. **Performance Impact**: <1% overhead from telemetry
4. **Data Retention**: 30 days of metrics history
5. **Alert Coverage**: All critical failures monitored
6. **Dashboard Usability**: Single pane of glass monitoring

## Example Usage

```bash
# Full analytics implementation
/mcp-implement-analytics start

# Just OpenTelemetry setup
/mcp-implement-analytics setup-otel --exporter otlp

# Create Grafana dashboards
/mcp-implement-analytics dashboard --format grafana

# Test telemetry pipeline
/mcp-implement-analytics test --load-test

# Export metrics schema
/mcp-implement-analytics export-schema
```