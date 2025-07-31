"""
Error handling framework for Shannon MCP Server.

This module provides comprehensive error handling with:
- Hierarchical exception classes
- Error context preservation
- Automatic error recovery
- Error tracking and metrics
- User-friendly error messages
- Structured error responses
"""

from typing import Optional, Dict, Any, List, Type, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import traceback
import sys
from contextlib import contextmanager
import asyncio
import functools
import structlog

from .logging import get_logger


logger = get_logger("shannon-mcp.errors")


class ErrorSeverity(Enum):
    """Error severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """Error categories for classification."""
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    USER_INPUT = "user_input"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


@dataclass
class ErrorInfo:
    """Structured error information."""
    code: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    cause: Optional[Exception] = None
    suggestions: List[str] = field(default_factory=list)
    documentation_url: Optional[str] = None
    retry_after: Optional[int] = None  # seconds
    is_retryable: bool = False


class ShannonError(Exception):
    """Base exception for all Shannon MCP errors."""
    
    code: str = "SHANNON_ERROR"
    default_message: str = "An error occurred in Shannon MCP"
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: ErrorCategory = ErrorCategory.UNKNOWN
    is_retryable: bool = False
    
    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        **kwargs
    ):
        """Initialize Shannon error."""
        self.message = message or self.default_message
        self.context = context or ErrorContext()
        self.cause = cause
        self.kwargs = kwargs
        
        # Capture stack trace
        if not self.context.stack_trace:
            self.context.stack_trace = traceback.format_exc()
        
        super().__init__(self.message)
    
    def to_info(self) -> ErrorInfo:
        """Convert to structured error info."""
        return ErrorInfo(
            code=self.code,
            message=self.message,
            severity=self.severity,
            category=self.category,
            context=self.context,
            cause=self.cause,
            suggestions=self.get_suggestions(),
            documentation_url=self.get_documentation_url(),
            retry_after=self.get_retry_after(),
            is_retryable=self.is_retryable
        )
    
    def get_suggestions(self) -> List[str]:
        """Get error resolution suggestions."""
        return []
    
    def get_documentation_url(self) -> Optional[str]:
        """Get documentation URL for this error."""
        return f"https://docs.shannon-mcp.com/errors/{self.code.lower()}"
    
    def get_retry_after(self) -> Optional[int]:
        """Get retry delay in seconds."""
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        info = self.to_info()
        return {
            "error": {
                "code": info.code,
                "message": info.message,
                "severity": info.severity.value,
                "category": info.category.value,
                "is_retryable": info.is_retryable,
                "retry_after": info.retry_after,
                "suggestions": info.suggestions,
                "documentation_url": info.documentation_url,
                "context": {
                    "timestamp": info.context.timestamp.isoformat(),
                    "request_id": info.context.request_id,
                    "component": info.context.component,
                    "operation": info.context.operation,
                    "metadata": info.context.metadata
                }
            }
        }


# System Errors

class SystemError(ShannonError):
    """System-level errors."""
    code = "SYSTEM_ERROR"
    default_message = "A system error occurred"
    category = ErrorCategory.SYSTEM
    severity = ErrorSeverity.CRITICAL


class ConfigurationError(ShannonError):
    """Configuration errors."""
    code = "CONFIG_ERROR"
    default_message = "Configuration error"
    category = ErrorCategory.CONFIGURATION
    severity = ErrorSeverity.ERROR
    
    def get_suggestions(self) -> List[str]:
        return [
            "Check your configuration file syntax",
            "Ensure all required configuration values are set",
            "Verify configuration file permissions"
        ]


# Network Errors

class NetworkError(ShannonError):
    """Network-related errors."""
    code = "NETWORK_ERROR"
    default_message = "Network error occurred"
    category = ErrorCategory.NETWORK
    severity = ErrorSeverity.ERROR
    is_retryable = True
    
    def get_retry_after(self) -> Optional[int]:
        return 5  # 5 seconds


class ConnectionError(NetworkError):
    """Connection errors."""
    code = "CONNECTION_ERROR"
    default_message = "Failed to establish connection"
    
    def get_suggestions(self) -> List[str]:
        return [
            "Check your network connection",
            "Verify the target host is reachable",
            "Check firewall settings"
        ]


class TimeoutError(NetworkError):
    """Timeout errors."""
    code = "TIMEOUT_ERROR"
    default_message = "Operation timed out"
    
    def get_retry_after(self) -> Optional[int]:
        return 10  # 10 seconds


# Database Errors

class DatabaseError(ShannonError):
    """Database-related errors."""
    code = "DATABASE_ERROR"
    default_message = "Database error occurred"
    category = ErrorCategory.DATABASE
    severity = ErrorSeverity.ERROR


class DatabaseConnectionError(DatabaseError):
    """Database connection errors."""
    code = "DB_CONNECTION_ERROR"
    default_message = "Failed to connect to database"
    is_retryable = True
    
    def get_retry_after(self) -> Optional[int]:
        return 5


class DatabaseIntegrityError(DatabaseError):
    """Database integrity errors."""
    code = "DB_INTEGRITY_ERROR"
    default_message = "Database integrity constraint violated"
    severity = ErrorSeverity.CRITICAL


# Validation Errors

class ValidationError(ShannonError):
    """Input validation errors."""
    code = "VALIDATION_ERROR"
    default_message = "Validation error"
    category = ErrorCategory.VALIDATION
    severity = ErrorSeverity.WARNING
    
    def __init__(self, field: str, value: Any, constraint: str, **kwargs):
        self.field = field
        self.value = value
        self.constraint = constraint
        message = f"Validation failed for field '{field}': {constraint}"
        super().__init__(message, **kwargs)
    
    def get_suggestions(self) -> List[str]:
        return [
            f"Check the value of field '{self.field}'",
            f"Ensure it meets the constraint: {self.constraint}"
        ]


# Authentication/Authorization Errors

class AuthenticationError(ShannonError):
    """Authentication errors."""
    code = "AUTH_ERROR"
    default_message = "Authentication failed"
    category = ErrorCategory.AUTHENTICATION
    severity = ErrorSeverity.WARNING


class AuthorizationError(ShannonError):
    """Authorization errors."""
    code = "AUTHZ_ERROR"
    default_message = "Authorization failed"
    category = ErrorCategory.AUTHORIZATION
    severity = ErrorSeverity.WARNING


# External Service Errors

class ExternalServiceError(ShannonError):
    """External service errors."""
    code = "EXTERNAL_SERVICE_ERROR"
    default_message = "External service error"
    category = ErrorCategory.EXTERNAL_SERVICE
    severity = ErrorSeverity.ERROR
    is_retryable = True
    
    def __init__(self, service_name: str, **kwargs):
        self.service_name = service_name
        message = f"Error communicating with external service: {service_name}"
        super().__init__(message, **kwargs)
    
    def get_retry_after(self) -> Optional[int]:
        return 30  # 30 seconds


# Error Handler Decorator

def handle_errors(
    *error_classes: Type[Exception],
    fallback: Optional[Callable] = None,
    reraise: bool = True,
    log_level: ErrorSeverity = ErrorSeverity.ERROR
):
    """
    Decorator for handling errors in functions.
    
    Args:
        error_classes: Exception classes to catch
        fallback: Fallback function to call on error
        reraise: Whether to reraise the exception
        log_level: Logging level for errors
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_classes as e:
                logger.log(
                    log_level.value,
                    f"error_in_{func.__name__}",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
                
                if fallback:
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                
                if reraise:
                    raise
                
                return None
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except error_classes as e:
                logger.log(
                    log_level.value,
                    f"error_in_{func.__name__}",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
                
                if fallback:
                    return fallback(*args, **kwargs)
                
                if reraise:
                    raise
                
                return None
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Error Context Manager

@contextmanager
def error_context(
    component: str,
    operation: str,
    reraise: bool = True,
    **metadata
):
    """
    Context manager for error handling with context.
    
    Args:
        component: Component name
        operation: Operation name
        reraise: Whether to reraise exceptions
        **metadata: Additional context metadata
    """
    context = ErrorContext(
        component=component,
        operation=operation,
        metadata=metadata
    )
    
    try:
        yield context
    except ShannonError as e:
        # Update existing error context
        e.context.component = e.context.component or component
        e.context.operation = e.context.operation or operation
        e.context.metadata.update(metadata)
        logger.error(
            "shannon_error_in_context",
            error=e.to_dict(),
            exc_info=True
        )
        if reraise:
            raise
    except Exception as e:
        # Wrap in ShannonError
        shannon_error = ShannonError(
            message=str(e),
            context=context,
            cause=e
        )
        logger.error(
            "unexpected_error_in_context",
            error=shannon_error.to_dict(),
            exc_info=True
        )
        if reraise:
            raise shannon_error from e


# Error Recovery

class ErrorRecovery:
    """Error recovery strategies."""
    
    @staticmethod
    async def exponential_backoff(
        func: Callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exceptions: tuple = (Exception,)
    ) -> Any:
        """
        Retry with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exceptions: Exceptions to retry on
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    return func()
            except exceptions as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "retrying_after_error",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "max_retries_exceeded",
                        attempts=max_retries,
                        error=str(e)
                    )
        
        raise last_exception
    
    @staticmethod
    async def circuit_breaker(
        func: Callable,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        exceptions: tuple = (Exception,)
    ) -> Any:
        """
        Circuit breaker pattern implementation.
        
        Args:
            func: Function to protect
            failure_threshold: Failures before opening circuit
            reset_timeout: Time before attempting reset
            exceptions: Exceptions that trigger the breaker
        """
        # This is a simplified implementation
        # In production, use a proper circuit breaker library
        if not hasattr(circuit_breaker, '_state'):
            circuit_breaker._state = {}
        
        func_name = f"{func.__module__}.{func.__name__}"
        state = circuit_breaker._state.setdefault(func_name, {
            'failures': 0,
            'last_failure': None,
            'is_open': False
        })
        
        # Check if circuit is open
        if state['is_open']:
            if state['last_failure'] and \
               (datetime.utcnow() - state['last_failure']).total_seconds() > reset_timeout:
                state['is_open'] = False
                state['failures'] = 0
                logger.info("circuit_breaker_reset", function=func_name)
            else:
                raise SystemError(f"Circuit breaker open for {func_name}")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            
            # Reset on success
            state['failures'] = 0
            return result
            
        except exceptions as e:
            state['failures'] += 1
            state['last_failure'] = datetime.utcnow()
            
            if state['failures'] >= failure_threshold:
                state['is_open'] = True
                logger.error(
                    "circuit_breaker_opened",
                    function=func_name,
                    failures=state['failures']
                )
            
            raise


# Export public API
__all__ = [
    # Base classes
    'ShannonError',
    'ErrorContext',
    'ErrorInfo',
    'ErrorSeverity',
    'ErrorCategory',
    
    # Error types
    'SystemError',
    'ConfigurationError',
    'NetworkError',
    'ConnectionError',
    'TimeoutError',
    'DatabaseError',
    'DatabaseConnectionError',
    'DatabaseIntegrityError',
    'ValidationError',
    'AuthenticationError',
    'AuthorizationError',
    'ExternalServiceError',
    
    # Utilities
    'handle_errors',
    'error_context',
    'ErrorRecovery',
]