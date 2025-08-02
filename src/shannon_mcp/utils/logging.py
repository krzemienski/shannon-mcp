"""
Logging configuration for Shannon MCP Server.

This module provides centralized logging setup with:
- Structured logging with rich formatting
- Log rotation and archival
- Performance metrics logging
- Error tracking and alerting
- Distributed tracing support
"""

import logging
import logging.handlers
import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime
import structlog
from rich.logging import RichHandler
from rich.console import Console
from rich.traceback import install as install_rich_traceback
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration


# Install rich traceback handler for better error display
install_rich_traceback()

# Console for rich output
# Check if running as MCP server (stdio mode) - will be rechecked in setup_logging
import os

# Default console - will be reconfigured in setup_logging based on MCP mode
console = Console(file=sys.stdout, force_terminal=True)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process,
        }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info'):
                try:
                    # Try to serialize the value to check if it's JSON-serializable
                    json.dumps(value)
                    log_obj[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    log_obj[key] = str(value)
                
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


class MetricsLogger:
    """Logger for performance metrics and analytics."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._metrics: Dict[str, Any] = {}
    
    def log_metric(self, name: str, value: Any, tags: Optional[Dict[str, str]] = None):
        """Log a metric value."""
        self.logger.info(
            "metric",
            metric_name=name,
            metric_value=value,
            metric_tags=tags or {},
            metric_timestamp=datetime.utcnow().isoformat()
        )
    
    def log_duration(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None):
        """Log a duration metric."""
        self.log_metric(f"{name}.duration_ms", duration_ms, tags)
    
    def log_count(self, name: str, count: int = 1, tags: Optional[Dict[str, str]] = None):
        """Log a count metric."""
        self.log_metric(f"{name}.count", count, tags)
    
    def log_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Log a gauge metric."""
        self.log_metric(f"{name}.gauge", value, tags)


def setup_logging(
    app_name: str = "shannon-mcp",
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_json: bool = True,
    enable_sentry: bool = False,
    sentry_dsn: Optional[str] = None,
    enable_metrics: bool = True
) -> Dict[str, Any]:
    """
    Set up comprehensive logging for the application.
    
    Args:
        app_name: Application name for log identification
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (defaults to ~/.shannon-mcp/logs)
        enable_json: Enable JSON structured logging
        enable_sentry: Enable Sentry error tracking
        sentry_dsn: Sentry DSN for error tracking
        enable_metrics: Enable metrics logging
        
    Returns:
        Dictionary with logger instances and configuration
    """
    # Detect MCP mode - must be done in function since env var set after import
    mcp_mode = os.environ.get('SHANNON_MCP_MODE') == 'stdio'
    
    # Reconfigure console for MCP mode
    global console
    if mcp_mode:
        # In MCP mode, create a null console to suppress all Rich output
        import io
        console = Console(file=io.StringIO(), force_terminal=False)
    
    # Create log directory
    if log_dir is None:
        log_dir = Path.home() / ".shannon-mcp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    # In MCP mode, always use JSON renderer to avoid console output
    renderer = structlog.processors.JSONRenderer() if (enable_json or mcp_mode) else structlog.dev.ConsoleRenderer()
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with rich formatting
    # Only add console handler if not in MCP stdio mode
    if not mcp_mode:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            tracebacks_suppress=[
                "click",
                "asyncio",
            ]
        )
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    else:
        # In MCP mode, send logs to a null handler to suppress all console output
        # This is critical - MCP requires clean JSON-RPC on stdout/stderr
        null_handler = logging.NullHandler()
        root_logger.addHandler(null_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{app_name}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    if enable_json:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
    
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{app_name}-errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter() if enable_json else file_formatter)
    root_logger.addHandler(error_handler)
    
    # Metrics file handler
    metrics_logger = None
    if enable_metrics:
        metrics_logger_instance = logging.getLogger(f"{app_name}.metrics")
        metrics_handler = logging.handlers.RotatingFileHandler(
            log_dir / f"{app_name}-metrics.jsonl",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10,
            encoding='utf-8'
        )
        metrics_handler.setLevel(logging.INFO)
        metrics_handler.setFormatter(JSONFormatter())
        metrics_logger_instance.addHandler(metrics_handler)
        metrics_logger_instance.propagate = False
        metrics_logger = MetricsLogger(metrics_logger_instance)
    
    # Set up Sentry if enabled
    if enable_sentry and sentry_dsn:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[sentry_logging],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
    
    # Create specialized loggers
    loggers = {
        'main': structlog.get_logger(app_name),
        'binary': structlog.get_logger(f"{app_name}.binary"),
        'session': structlog.get_logger(f"{app_name}.session"),
        'agent': structlog.get_logger(f"{app_name}.agent"),
        'checkpoint': structlog.get_logger(f"{app_name}.checkpoint"),
        'hooks': structlog.get_logger(f"{app_name}.hooks"),
        'analytics': structlog.get_logger(f"{app_name}.analytics"),
        'mcp': structlog.get_logger(f"{app_name}.mcp"),
        'storage': structlog.get_logger(f"{app_name}.storage"),
        'streaming': structlog.get_logger(f"{app_name}.streaming"),
        'metrics': metrics_logger,
    }
    
    # Log startup
    loggers['main'].info(
        "logging_initialized",
        app_name=app_name,
        log_level=log_level,
        log_dir=str(log_dir),
        enable_json=enable_json,
        enable_sentry=enable_sentry,
        enable_metrics=enable_metrics,
        pid=os.getpid() if hasattr(os, 'getpid') else None,
    )
    
    return {
        'loggers': loggers,
        'log_dir': log_dir,
        'console': console,
        'config': {
            'app_name': app_name,
            'log_level': log_level,
            'enable_json': enable_json,
            'enable_sentry': enable_sentry,
            'enable_metrics': enable_metrics,
        }
    }


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance by name."""
    return structlog.get_logger(name)


def log_function_call(logger: structlog.BoundLogger):
    """Decorator to log function calls with timing."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            logger.debug(f"calling_{func.__name__}", args=args, kwargs=kwargs)
            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(
                    f"completed_{func.__name__}",
                    duration_ms=duration_ms,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"failed_{func.__name__}",
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            logger.debug(f"calling_{func.__name__}", args=args, kwargs=kwargs)
            try:
                result = func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(
                    f"completed_{func.__name__}",
                    duration_ms=duration_ms,
                    success=True
                )
                return result
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.error(
                    f"failed_{func.__name__}",
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Export main setup function and utilities
__all__ = [
    'setup_logging',
    'get_logger',
    'log_function_call',
    'MetricsLogger',
    'JSONFormatter',
]