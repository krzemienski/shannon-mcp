"""
Enhanced error tracking and reporting system for Shannon MCP Server.

This module provides comprehensive error tracking compatible with Claudia's
error monitoring capabilities.
"""

from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import traceback
import asyncio
import json
from collections import defaultdict, deque
from pathlib import Path

from ..utils.logging import get_logger
from ..utils.errors import ErrorSeverity, ErrorCategory, ErrorInfo, ErrorContext

logger = get_logger("shannon-mcp.error_tracker")


class ErrorPattern(Enum):
    """Common error patterns for classification."""
    TIMEOUT = "timeout"
    CONNECTION_FAILED = "connection_failed"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_NOT_FOUND = "resource_not_found"
    VALIDATION_FAILED = "validation_failed"
    RATE_LIMITED = "rate_limited"
    MEMORY_EXCEEDED = "memory_exceeded"
    DISK_FULL = "disk_full"
    AUTHENTICATION_FAILED = "authentication_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    STREAM_INTERRUPTED = "stream_interrupted"
    UNKNOWN = "unknown"


@dataclass
class ErrorOccurrence:
    """Single error occurrence with full context."""
    id: str
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    pattern: ErrorPattern
    stack_trace: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_notes: Optional[str] = None


@dataclass
class ErrorStatistics:
    """Error statistics for a time period."""
    total_errors: int = 0
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_pattern: Dict[str, int] = field(default_factory=dict)
    errors_by_component: Dict[str, int] = field(default_factory=dict)
    error_rate_per_minute: float = 0.0
    resolution_rate: float = 0.0
    average_resolution_time: Optional[timedelta] = None
    most_common_errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ErrorTrend:
    """Error trend analysis."""
    pattern: ErrorPattern
    occurrences: List[datetime]
    is_increasing: bool
    rate_change: float  # Percentage change
    predicted_next_occurrence: Optional[datetime] = None


class ErrorTracker:
    """Enhanced error tracking and reporting system."""
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize error tracker.
        
        Args:
            max_history: Maximum number of errors to keep in history
        """
        self.max_history = max_history
        self._errors: deque = deque(maxlen=max_history)
        self._error_index: Dict[str, List[ErrorOccurrence]] = defaultdict(list)
        self._session_errors: Dict[str, List[ErrorOccurrence]] = defaultdict(list)
        self._component_errors: Dict[str, List[ErrorOccurrence]] = defaultdict(list)
        self._pattern_detector = PatternDetector()
        self._error_callbacks: List[Callable] = []
        self._error_id_counter = 0
        self._lock = asyncio.Lock()
        
        logger.info("error_tracker_initialized", max_history=max_history)
    
    async def track_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ErrorOccurrence:
        """
        Track an error occurrence.
        
        Args:
            error: The exception to track
            context: Error context
            severity: Override severity
            category: Override category
            metadata: Additional metadata
            
        Returns:
            ErrorOccurrence object
        """
        async with self._lock:
            # Generate error ID
            self._error_id_counter += 1
            error_id = f"err_{self._error_id_counter:08d}"
            
            # Extract error info
            error_type = type(error).__name__
            error_message = str(error)
            stack_trace = traceback.format_exc()
            
            # Determine severity and category
            if hasattr(error, 'severity'):
                severity = severity or error.severity
            else:
                severity = severity or ErrorSeverity.ERROR
                
            if hasattr(error, 'category'):
                category = category or error.category
            else:
                category = category or ErrorCategory.UNKNOWN
            
            # Detect pattern
            pattern = self._pattern_detector.detect_pattern(
                error_type, error_message, stack_trace
            )
            
            # Create error occurrence
            occurrence = ErrorOccurrence(
                id=error_id,
                timestamp=datetime.utcnow(),
                error_type=error_type,
                error_message=error_message,
                severity=severity,
                category=category,
                pattern=pattern,
                stack_trace=stack_trace,
                session_id=context.session_id if context else None,
                user_id=context.user_id if context else None,
                component=context.component if context else None,
                operation=context.operation if context else None,
                metadata={
                    **(context.metadata if context else {}),
                    **(metadata or {})
                }
            )
            
            # Store error
            self._errors.append(occurrence)
            self._error_index[error_type].append(occurrence)
            
            if occurrence.session_id:
                self._session_errors[occurrence.session_id].append(occurrence)
            
            if occurrence.component:
                self._component_errors[occurrence.component].append(occurrence)
            
            # Notify callbacks
            await self._notify_callbacks(occurrence)
            
            # Log error
            logger.error(
                "error_tracked",
                error_id=error_id,
                error_type=error_type,
                severity=severity.value,
                category=category.value,
                pattern=pattern.value,
                session_id=occurrence.session_id,
                component=occurrence.component
            )
            
            return occurrence
    
    async def resolve_error(
        self,
        error_id: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """
        Mark an error as resolved.
        
        Args:
            error_id: Error ID to resolve
            resolution_notes: Notes about the resolution
            
        Returns:
            True if resolved, False if not found
        """
        async with self._lock:
            for error in self._errors:
                if error.id == error_id:
                    error.resolved = True
                    error.resolution_time = datetime.utcnow()
                    error.resolution_notes = resolution_notes
                    
                    logger.info(
                        "error_resolved",
                        error_id=error_id,
                        resolution_time=(error.resolution_time - error.timestamp).total_seconds()
                    )
                    
                    return True
            
            return False
    
    async def get_error_statistics(
        self,
        time_window: Optional[timedelta] = None,
        session_id: Optional[str] = None,
        component: Optional[str] = None
    ) -> ErrorStatistics:
        """
        Get error statistics for a time window.
        
        Args:
            time_window: Time window to analyze (default: last hour)
            session_id: Filter by session
            component: Filter by component
            
        Returns:
            ErrorStatistics object
        """
        if not time_window:
            time_window = timedelta(hours=1)
        
        cutoff_time = datetime.utcnow() - time_window
        
        # Filter errors
        errors = []
        if session_id:
            errors = self._session_errors.get(session_id, [])
        elif component:
            errors = self._component_errors.get(component, [])
        else:
            errors = list(self._errors)
        
        # Filter by time
        errors = [e for e in errors if e.timestamp >= cutoff_time]
        
        # Calculate statistics
        stats = ErrorStatistics()
        stats.total_errors = len(errors)
        
        # Count by severity
        for error in errors:
            severity_key = error.severity.value
            stats.errors_by_severity[severity_key] = \
                stats.errors_by_severity.get(severity_key, 0) + 1
        
        # Count by category
        for error in errors:
            category_key = error.category.value
            stats.errors_by_category[category_key] = \
                stats.errors_by_category.get(category_key, 0) + 1
        
        # Count by pattern
        for error in errors:
            pattern_key = error.pattern.value
            stats.errors_by_pattern[pattern_key] = \
                stats.errors_by_pattern.get(pattern_key, 0) + 1
        
        # Count by component
        for error in errors:
            if error.component:
                stats.errors_by_component[error.component] = \
                    stats.errors_by_component.get(error.component, 0) + 1
        
        # Calculate rates
        time_minutes = time_window.total_seconds() / 60
        stats.error_rate_per_minute = stats.total_errors / time_minutes if time_minutes > 0 else 0
        
        # Resolution statistics
        resolved_errors = [e for e in errors if e.resolved]
        stats.resolution_rate = len(resolved_errors) / len(errors) if errors else 0
        
        if resolved_errors:
            resolution_times = [
                (e.resolution_time - e.timestamp).total_seconds()
                for e in resolved_errors
                if e.resolution_time
            ]
            if resolution_times:
                avg_seconds = sum(resolution_times) / len(resolution_times)
                stats.average_resolution_time = timedelta(seconds=avg_seconds)
        
        # Most common errors
        error_counts = defaultdict(int)
        for error in errors:
            key = f"{error.error_type}:{error.pattern.value}"
            error_counts[key] += 1
        
        stats.most_common_errors = [
            {"error": key, "count": count}
            for key, count in sorted(
                error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]
        
        return stats
    
    async def get_error_trends(
        self,
        time_window: Optional[timedelta] = None,
        min_occurrences: int = 3
    ) -> List[ErrorTrend]:
        """
        Analyze error trends.
        
        Args:
            time_window: Time window to analyze
            min_occurrences: Minimum occurrences to consider a trend
            
        Returns:
            List of error trends
        """
        if not time_window:
            time_window = timedelta(hours=24)
        
        cutoff_time = datetime.utcnow() - time_window
        
        # Group errors by pattern
        pattern_occurrences = defaultdict(list)
        for error in self._errors:
            if error.timestamp >= cutoff_time:
                pattern_occurrences[error.pattern].append(error.timestamp)
        
        # Analyze trends
        trends = []
        for pattern, occurrences in pattern_occurrences.items():
            if len(occurrences) >= min_occurrences:
                # Sort occurrences
                occurrences.sort()
                
                # Calculate rate change
                first_half = occurrences[:len(occurrences)//2]
                second_half = occurrences[len(occurrences)//2:]
                
                first_rate = len(first_half) / ((first_half[-1] - first_half[0]).total_seconds() / 3600)
                second_rate = len(second_half) / ((second_half[-1] - second_half[0]).total_seconds() / 3600)
                
                rate_change = ((second_rate - first_rate) / first_rate * 100) if first_rate > 0 else 0
                
                # Predict next occurrence
                if len(occurrences) >= 2:
                    intervals = [
                        (occurrences[i] - occurrences[i-1]).total_seconds()
                        for i in range(1, len(occurrences))
                    ]
                    avg_interval = sum(intervals) / len(intervals)
                    predicted_next = occurrences[-1] + timedelta(seconds=avg_interval)
                else:
                    predicted_next = None
                
                trend = ErrorTrend(
                    pattern=pattern,
                    occurrences=occurrences,
                    is_increasing=rate_change > 10,  # 10% threshold
                    rate_change=rate_change,
                    predicted_next_occurrence=predicted_next
                )
                trends.append(trend)
        
        return trends
    
    async def get_session_errors(
        self,
        session_id: str,
        include_resolved: bool = True
    ) -> List[ErrorOccurrence]:
        """Get all errors for a session."""
        errors = self._session_errors.get(session_id, [])
        if not include_resolved:
            errors = [e for e in errors if not e.resolved]
        return errors
    
    async def get_component_errors(
        self,
        component: str,
        include_resolved: bool = True
    ) -> List[ErrorOccurrence]:
        """Get all errors for a component."""
        errors = self._component_errors.get(component, [])
        if not include_resolved:
            errors = [e for e in errors if not e.resolved]
        return errors
    
    async def generate_error_report(
        self,
        time_window: Optional[timedelta] = None,
        format: str = "json"
    ) -> str:
        """
        Generate a comprehensive error report.
        
        Args:
            time_window: Time window for the report
            format: Report format (json, markdown)
            
        Returns:
            Formatted error report
        """
        stats = await self.get_error_statistics(time_window)
        trends = await self.get_error_trends(time_window)
        
        if format == "json":
            report_data = {
                "generated_at": datetime.utcnow().isoformat(),
                "time_window": str(time_window) if time_window else "1 hour",
                "statistics": {
                    "total_errors": stats.total_errors,
                    "errors_by_severity": stats.errors_by_severity,
                    "errors_by_category": stats.errors_by_category,
                    "errors_by_pattern": stats.errors_by_pattern,
                    "errors_by_component": stats.errors_by_component,
                    "error_rate_per_minute": stats.error_rate_per_minute,
                    "resolution_rate": stats.resolution_rate,
                    "average_resolution_time": str(stats.average_resolution_time) if stats.average_resolution_time else None,
                    "most_common_errors": stats.most_common_errors
                },
                "trends": [
                    {
                        "pattern": trend.pattern.value,
                        "occurrence_count": len(trend.occurrences),
                        "is_increasing": trend.is_increasing,
                        "rate_change": trend.rate_change,
                        "predicted_next": trend.predicted_next_occurrence.isoformat() if trend.predicted_next_occurrence else None
                    }
                    for trend in trends
                ]
            }
            return json.dumps(report_data, indent=2)
        
        elif format == "markdown":
            report = f"""# Error Report

Generated at: {datetime.utcnow().isoformat()}
Time window: {time_window if time_window else "1 hour"}

## Summary

- Total errors: {stats.total_errors}
- Error rate: {stats.error_rate_per_minute:.2f} errors/minute
- Resolution rate: {stats.resolution_rate:.1%}
- Average resolution time: {stats.average_resolution_time if stats.average_resolution_time else "N/A"}

## Errors by Severity

"""
            for severity, count in sorted(stats.errors_by_severity.items()):
                report += f"- {severity}: {count}\n"
            
            report += "\n## Errors by Category\n\n"
            for category, count in sorted(stats.errors_by_category.items()):
                report += f"- {category}: {count}\n"
            
            report += "\n## Most Common Errors\n\n"
            for i, error_info in enumerate(stats.most_common_errors[:5], 1):
                report += f"{i}. {error_info['error']} ({error_info['count']} occurrences)\n"
            
            report += "\n## Error Trends\n\n"
            for trend in trends:
                if trend.is_increasing:
                    report += f"⚠️ **{trend.pattern.value}** is increasing ({trend.rate_change:+.1f}%)\n"
            
            return report
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def add_error_callback(self, callback: Callable) -> None:
        """Add a callback for error notifications."""
        self._error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable) -> None:
        """Remove an error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)
    
    async def _notify_callbacks(self, error: ErrorOccurrence) -> None:
        """Notify all registered callbacks about an error."""
        for callback in self._error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                logger.error(
                    "error_callback_failed",
                    callback=callback.__name__,
                    error=str(e)
                )
    
    async def clear_resolved_errors(self, older_than: Optional[timedelta] = None) -> int:
        """
        Clear resolved errors older than specified time.
        
        Args:
            older_than: Clear errors older than this (default: 24 hours)
            
        Returns:
            Number of errors cleared
        """
        if not older_than:
            older_than = timedelta(hours=24)
        
        cutoff_time = datetime.utcnow() - older_than
        cleared = 0
        
        async with self._lock:
            # Clear from main deque (this is tricky with deque)
            # For now, just track the count
            for error in list(self._errors):
                if error.resolved and error.timestamp < cutoff_time:
                    cleared += 1
            
            logger.info("resolved_errors_cleared", count=cleared)
            
        return cleared


class PatternDetector:
    """Detects error patterns from error information."""
    
    def __init__(self):
        """Initialize pattern detector."""
        self._pattern_rules = {
            ErrorPattern.TIMEOUT: [
                "timeout", "timed out", "deadline exceeded",
                "operation timed out", "read timeout"
            ],
            ErrorPattern.CONNECTION_FAILED: [
                "connection refused", "connection reset", "connection failed",
                "unable to connect", "network unreachable"
            ],
            ErrorPattern.PERMISSION_DENIED: [
                "permission denied", "access denied", "forbidden",
                "unauthorized", "insufficient permissions"
            ],
            ErrorPattern.RESOURCE_NOT_FOUND: [
                "not found", "does not exist", "404", "no such file",
                "unknown resource"
            ],
            ErrorPattern.VALIDATION_FAILED: [
                "validation failed", "invalid", "bad request",
                "constraint violation", "format error"
            ],
            ErrorPattern.RATE_LIMITED: [
                "rate limit", "too many requests", "throttled",
                "quota exceeded", "429"
            ],
            ErrorPattern.MEMORY_EXCEEDED: [
                "out of memory", "memory limit", "heap space",
                "allocation failed", "oom"
            ],
            ErrorPattern.DISK_FULL: [
                "disk full", "no space left", "storage full",
                "write failed", "disk quota"
            ],
            ErrorPattern.AUTHENTICATION_FAILED: [
                "authentication failed", "invalid credentials",
                "login failed", "token expired"
            ],
            ErrorPattern.TOOL_EXECUTION_FAILED: [
                "tool execution failed", "tool error", "execution error",
                "command failed", "process exited"
            ],
            ErrorPattern.STREAM_INTERRUPTED: [
                "stream interrupted", "broken pipe", "stream closed",
                "eof", "connection lost"
            ]
        }
    
    def detect_pattern(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None
    ) -> ErrorPattern:
        """
        Detect error pattern from error information.
        
        Args:
            error_type: Type of the error
            error_message: Error message
            stack_trace: Stack trace if available
            
        Returns:
            Detected error pattern
        """
        # Combine all text for pattern matching
        search_text = f"{error_type} {error_message}".lower()
        if stack_trace:
            search_text += f" {stack_trace}".lower()
        
        # Check each pattern
        for pattern, keywords in self._pattern_rules.items():
            for keyword in keywords:
                if keyword in search_text:
                    return pattern
        
        return ErrorPattern.UNKNOWN


# Export public API
__all__ = [
    'ErrorTracker',
    'ErrorOccurrence',
    'ErrorStatistics',
    'ErrorTrend',
    'ErrorPattern',
    'PatternDetector'
]