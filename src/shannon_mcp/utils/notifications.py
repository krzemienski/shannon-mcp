"""
Notification system for Shannon MCP Server.

This module provides event-driven notifications with:
- Publish/subscribe pattern
- Async event handling
- Event filtering and routing
- Priority-based delivery
- Event persistence
- Retry mechanisms
"""

from typing import Optional, Dict, Any, List, Callable, Set, Union, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
from abc import ABC, abstractmethod
import weakref
import json
import structlog
from collections import defaultdict

from .logging import get_logger
from .errors import ShannonError, handle_errors


logger = get_logger("shannon-mcp.notifications")
T = TypeVar('T')


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventCategory(Enum):
    """Event categories for routing."""
    SYSTEM = "system"
    SESSION = "session"
    AGENT = "agent"
    CHECKPOINT = "checkpoint"
    HOOKS = "hooks"
    ANALYTICS = "analytics"
    BINARY = "binary"
    MCP = "mcp"
    USER = "user"
    ERROR = "error"


class NotificationType(Enum):
    """Notification types (alias for EventCategory)."""
    SYSTEM = "system"
    SESSION = "session"
    AGENT = "agent"
    CHECKPOINT = "checkpoint"
    HOOKS = "hooks"
    ANALYTICS = "analytics"
    BINARY = "binary"
    MCP = "mcp"
    USER = "user"
    ERROR = "error"


@dataclass
class Event:
    """Event data structure."""
    name: str
    category: EventCategory
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            category=EventCategory(data["category"]),
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=EventPriority(data.get("priority", EventPriority.NORMAL.value)),
            source=data.get("source"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {})
        )


@dataclass
class Subscription:
    """Event subscription."""
    handler: Callable[[Event], Any]
    categories: Optional[Set[EventCategory]] = None
    event_names: Optional[Set[str]] = None
    priority_min: EventPriority = EventPriority.LOW
    is_async: bool = True
    filter_func: Optional[Callable[[Event], bool]] = None
    weak_ref: bool = False
    
    def matches(self, event: Event) -> bool:
        """Check if subscription matches event."""
        # Check priority
        if event.priority.value < self.priority_min.value:
            return False
        
        # Check categories
        if self.categories and event.category not in self.categories:
            return False
        
        # Check event names
        if self.event_names and event.name not in self.event_names:
            return False
        
        # Apply custom filter
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True


class EventBus:
    """Central event bus for notifications."""
    
    def __init__(self):
        """Initialize event bus."""
        self._subscriptions: List[Subscription] = []
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._handlers_cache: Dict[str, List[Subscription]] = {}
        self._weak_refs: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    
    def subscribe(
        self,
        handler: Callable[[Event], Any],
        categories: Optional[Union[EventCategory, List[EventCategory]]] = None,
        event_names: Optional[Union[str, List[str]]] = None,
        priority_min: EventPriority = EventPriority.LOW,
        is_async: Optional[bool] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        weak_ref: bool = False
    ) -> Subscription:
        """
        Subscribe to events.
        
        Args:
            handler: Event handler function
            categories: Event categories to subscribe to
            event_names: Specific event names to subscribe to
            priority_min: Minimum priority level
            is_async: Whether handler is async (auto-detected if None)
            filter_func: Custom filter function
            weak_ref: Use weak reference for handler
        
        Returns:
            Subscription object
        """
        # Convert single values to sets
        if isinstance(categories, EventCategory):
            categories = {categories}
        elif isinstance(categories, list):
            categories = set(categories)
        
        if isinstance(event_names, str):
            event_names = {event_names}
        elif isinstance(event_names, list):
            event_names = set(event_names)
        
        # Auto-detect async
        if is_async is None:
            is_async = asyncio.iscoroutinefunction(handler)
        
        # Create subscription
        subscription = Subscription(
            handler=handler,
            categories=categories,
            event_names=event_names,
            priority_min=priority_min,
            is_async=is_async,
            filter_func=filter_func,
            weak_ref=weak_ref
        )
        
        # Store weak reference if requested
        if weak_ref:
            self._weak_refs[id(subscription)] = handler
        
        self._subscriptions.append(subscription)
        self._invalidate_cache()
        
        logger.debug(
            "subscription_added",
            categories=[c.value for c in categories] if categories else None,
            event_names=list(event_names) if event_names else None,
            handler=handler.__name__ if hasattr(handler, '__name__') else str(handler)
        )
        
        return subscription
    
    def unsubscribe(self, subscription: Subscription) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription: Subscription to remove
        
        Returns:
            True if removed, False if not found
        """
        try:
            self._subscriptions.remove(subscription)
            self._invalidate_cache()
            logger.debug("subscription_removed")
            return True
        except ValueError:
            return False
    
    async def emit(
        self,
        name: str,
        category: EventCategory,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **metadata
    ) -> None:
        """
        Emit an event.
        
        Args:
            name: Event name
            category: Event category
            data: Event data
            priority: Event priority
            source: Event source
            correlation_id: Correlation ID for tracking
            **metadata: Additional metadata
        """
        event = Event(
            name=name,
            category=category,
            data=data,
            priority=priority,
            source=source,
            correlation_id=correlation_id,
            metadata=metadata
        )
        
        # Add to history
        self._add_to_history(event)
        
        # Queue for processing
        await self._event_queue.put(event)
        
        # Start processor if not running
        if not self._processing:
            self._processor_task = asyncio.create_task(self._process_events())
        
        logger.debug(
            "event_emitted",
            event_name=name,
            category=category.value,
            priority=priority.value,
            queue_size=self._event_queue.qsize()
        )
    
    def emit_sync(
        self,
        name: str,
        category: EventCategory,
        data: Dict[str, Any],
        **kwargs
    ) -> None:
        """Synchronous event emission (creates task)."""
        asyncio.create_task(self.emit(name, category, data, **kwargs))
    
    async def _process_events(self) -> None:
        """Process queued events."""
        self._processing = True
        
        try:
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                    
                    # Process event
                    await self._dispatch_event(event)
                    
                except asyncio.TimeoutError:
                    # Check if queue is empty and stop
                    if self._event_queue.empty():
                        break
                except Exception as e:
                    logger.error(
                        "event_processing_error",
                        error=str(e),
                        exc_info=True
                    )
        finally:
            self._processing = False
    
    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to subscribed handlers."""
        # Get matching subscriptions
        subscriptions = self._get_matching_subscriptions(event)
        
        if not subscriptions:
            logger.debug(
                "no_subscribers",
                event_name=event.name,
                category=event.category.value
            )
            return
        
        # Sort by priority
        subscriptions.sort(
            key=lambda s: s.priority_min.value,
            reverse=True
        )
        
        # Dispatch to handlers
        tasks = []
        for subscription in subscriptions:
            # Check if weak reference is still valid
            if subscription.weak_ref:
                if id(subscription) not in self._weak_refs:
                    self._subscriptions.remove(subscription)
                    continue
            
            try:
                if subscription.is_async:
                    task = asyncio.create_task(
                        self._call_async_handler(subscription.handler, event)
                    )
                    tasks.append(task)
                else:
                    self._call_sync_handler(subscription.handler, event)
            except Exception as e:
                logger.error(
                    "handler_dispatch_error",
                    handler=getattr(subscription.handler, '__name__', 'unknown'),
                    error=str(e),
                    exc_info=True
                )
        
        # Wait for async handlers
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _get_matching_subscriptions(self, event: Event) -> List[Subscription]:
        """Get subscriptions matching an event."""
        # Check cache
        cache_key = f"{event.name}:{event.category.value}"
        if cache_key in self._handlers_cache:
            return self._handlers_cache[cache_key]
        
        # Find matching subscriptions
        matching = [
            sub for sub in self._subscriptions
            if sub.matches(event)
        ]
        
        # Cache result
        self._handlers_cache[cache_key] = matching
        
        return matching
    
    async def _call_async_handler(
        self,
        handler: Callable[[Event], Any],
        event: Event
    ) -> None:
        """Call async event handler."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "async_handler_error",
                handler=getattr(handler, '__name__', 'unknown'),
                event_name=event.name,
                error=str(e),
                exc_info=True
            )
    
    def _call_sync_handler(
        self,
        handler: Callable[[Event], Any],
        event: Event
    ) -> None:
        """Call sync event handler."""
        try:
            handler(event)
        except Exception as e:
            logger.error(
                "sync_handler_error",
                handler=getattr(handler, '__name__', 'unknown'),
                event_name=event.name,
                error=str(e),
                exc_info=True
            )
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._event_history.append(event)
        
        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
    
    def _invalidate_cache(self) -> None:
        """Invalidate handler cache."""
        self._handlers_cache.clear()
    
    def get_history(
        self,
        category: Optional[EventCategory] = None,
        event_name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Get event history.
        
        Args:
            category: Filter by category
            event_name: Filter by event name
            since: Filter by timestamp
            limit: Maximum events to return
        
        Returns:
            List of events
        """
        events = self._event_history
        
        # Apply filters
        if category:
            events = [e for e in events if e.category == category]
        
        if event_name:
            events = [e for e in events if e.name == event_name]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        # Apply limit
        if limit:
            events = events[-limit:]
        
        return events
    
    async def wait_for(
        self,
        event_name: str,
        category: Optional[EventCategory] = None,
        timeout: Optional[float] = None,
        filter_func: Optional[Callable[[Event], bool]] = None
    ) -> Optional[Event]:
        """
        Wait for a specific event.
        
        Args:
            event_name: Event name to wait for
            category: Event category
            timeout: Timeout in seconds
            filter_func: Additional filter
        
        Returns:
            Event if received, None if timeout
        """
        future: asyncio.Future[Event] = asyncio.Future()
        
        def handler(event: Event) -> None:
            if not future.done():
                future.set_result(event)
        
        # Subscribe temporarily
        subscription = self.subscribe(
            handler=handler,
            event_names=[event_name],
            categories=[category] if category else None,
            filter_func=filter_func,
            is_async=False
        )
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(subscription)
    
    async def shutdown(self) -> None:
        """Shutdown event bus."""
        # Cancel processor
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Clear subscriptions
        self._subscriptions.clear()
        self._handlers_cache.clear()
        self._event_history.clear()
        
        logger.info("event_bus_shutdown")


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Convenience functions

async def emit(
    name: str,
    category: EventCategory,
    data: Dict[str, Any],
    **kwargs
) -> None:
    """Emit an event to global bus."""
    await get_event_bus().emit(name, category, data, **kwargs)


def subscribe(
    handler: Callable[[Event], Any],
    **kwargs
) -> Subscription:
    """Subscribe to events on global bus."""
    return get_event_bus().subscribe(handler, **kwargs)


def unsubscribe(subscription: Subscription) -> bool:
    """Unsubscribe from global bus."""
    return get_event_bus().unsubscribe(subscription)


# Decorator for event handlers

def event_handler(
    categories: Optional[Union[EventCategory, List[EventCategory]]] = None,
    event_names: Optional[Union[str, List[str]]] = None,
    priority_min: EventPriority = EventPriority.LOW,
    filter_func: Optional[Callable[[Event], bool]] = None
):
    """
    Decorator for event handler methods.
    
    Usage:
        @event_handler(categories=EventCategory.SESSION, event_names="session_started")
        async def on_session_started(self, event: Event):
            # Handle event
    """
    def decorator(func):
        func._event_handler_config = {
            'categories': categories,
            'event_names': event_names,
            'priority_min': priority_min,
            'filter_func': filter_func
        }
        return func
    
    return decorator


class EventEmitter:
    """Mixin class for objects that emit events."""
    
    def __init__(self, *args, **kwargs):
        """Initialize event emitter."""
        super().__init__(*args, **kwargs)
        self._event_source = self.__class__.__name__
        self._register_event_handlers()
    
    def _register_event_handlers(self) -> None:
        """Register decorated event handlers."""
        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, '_event_handler_config'):
                config = attr._event_handler_config
                subscribe(
                    handler=attr,
                    **config,
                    weak_ref=True
                )
    
    async def emit_event(
        self,
        name: str,
        category: EventCategory,
        data: Dict[str, Any],
        **kwargs
    ) -> None:
        """Emit an event with source set."""
        await emit(
            name=name,
            category=category,
            data=data,
            source=self._event_source,
            **kwargs
        )


async def setup_notifications(config) -> None:
    """Set up notification system with configuration."""
    # Initialize notification system with config
    # This is a placeholder for now
    pass


def emit_sync(name: str, category: EventCategory, data: Dict[str, Any], **kwargs) -> None:
    """Synchronous event emission."""
    get_event_bus().emit_sync(name, category, data, **kwargs)


def get_notification_system() -> EventBus:
    """Get the notification system (alias for get_event_bus)."""
    return get_event_bus()


async def notify_event(name: str, data: Dict[str, Any], priority: EventPriority = EventPriority.NORMAL) -> None:
    """Send an event notification (backward compatibility alias for emit)."""
    # Infer category from event name
    category = EventCategory.SYSTEM  # default
    if name.startswith("session."):
        category = EventCategory.SESSION
    elif name.startswith("agent."):
        category = EventCategory.AGENT
    elif name.startswith("checkpoint."):
        category = EventCategory.CHECKPOINT
    elif name.startswith("hook."):
        category = EventCategory.HOOKS
    elif name.startswith("analytics."):
        category = EventCategory.ANALYTICS
    elif name.startswith("binary."):
        category = EventCategory.BINARY
    elif name.startswith("mcp."):
        category = EventCategory.MCP
    
    await emit(name, category, data, priority=priority)


class EventHandler:
    """Alias for Subscription for backward compatibility."""
    pass


# Alias for backward compatibility
NotificationCenter = EventBus


# Export public API
__all__ = [
    'Event',
    'EventCategory',
    'EventPriority',
    'EventBus',
    'EventHandler',
    'Subscription',
    'get_event_bus',
    'get_notification_system',
    'emit',
    'emit_sync',
    'subscribe',
    'unsubscribe',
    'event_handler',
    'EventEmitter',
    'setup_notifications',
    'notify_event',
    'NotificationCenter',
    'NotificationType',
]