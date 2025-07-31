"""
Graceful shutdown handling for Shannon MCP Server.

This module provides comprehensive shutdown coordination with:
- Signal handling (SIGTERM, SIGINT, etc.)
- Component shutdown ordering
- Active request draining
- Resource cleanup
- Timeout management
- Shutdown hooks
"""

import asyncio
import signal
import sys
import os
from typing import Optional, List, Dict, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import weakref
import functools
import structlog

from .logging import get_logger
from .notifications import emit, EventCategory, EventPriority
from .errors import handle_errors, SystemError


logger = get_logger("shannon-mcp.shutdown")


class ShutdownPhase(Enum):
    """Shutdown phases for ordered component shutdown."""
    PRE_SHUTDOWN = 0       # Pre-shutdown hooks
    STOP_ACCEPTING = 1     # Stop accepting new requests
    DRAIN_REQUESTS = 2     # Drain active requests
    STOP_WORKERS = 3       # Stop worker tasks
    CLOSE_CONNECTIONS = 4  # Close external connections
    CLEANUP_RESOURCES = 5  # Clean up resources
    FINAL_CLEANUP = 6      # Final cleanup
    COMPLETE = 7           # Shutdown complete


@dataclass
class ShutdownComponent:
    """Component registration for shutdown."""
    name: str
    phase: ShutdownPhase
    handler: Callable[[], Any]
    timeout: float = 30.0
    is_async: bool = True
    dependencies: Set[str] = field(default_factory=set)
    
    def __hash__(self):
        return hash(self.name)


class ShutdownManager:
    """Manages graceful shutdown of the application."""
    
    def __init__(self, timeout: float = 60.0):
        """
        Initialize shutdown manager.
        
        Args:
            timeout: Maximum time to wait for shutdown
        """
        self.timeout = timeout
        self._components: Dict[str, ShutdownComponent] = {}
        self._shutdown_event = asyncio.Event()
        self._shutdown_task: Optional[asyncio.Task] = None
        self._active_requests: Set[weakref.ref] = set()
        self._is_shutting_down = False
        self._shutdown_complete = False
        self._original_handlers: Dict[int, Any] = {}
        self._shutdown_hooks: List[Callable] = []
        self._lock = asyncio.Lock()
    
    def register_component(
        self,
        name: str,
        handler: Callable[[], Any],
        phase: ShutdownPhase = ShutdownPhase.CLEANUP_RESOURCES,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
        is_async: Optional[bool] = None
    ) -> None:
        """
        Register a component for shutdown.
        
        Args:
            name: Component name
            handler: Shutdown handler
            phase: Shutdown phase
            timeout: Component shutdown timeout
            dependencies: Component dependencies
            is_async: Whether handler is async
        """
        if is_async is None:
            is_async = asyncio.iscoroutinefunction(handler)
        
        component = ShutdownComponent(
            name=name,
            phase=phase,
            handler=handler,
            timeout=timeout or 30.0,
            is_async=is_async,
            dependencies=set(dependencies or [])
        )
        
        self._components[name] = component
        logger.debug(
            "component_registered",
            component=name,
            phase=phase.name,
            timeout=component.timeout
        )
    
    def unregister_component(self, name: str) -> bool:
        """
        Unregister a component.
        
        Args:
            name: Component name
        
        Returns:
            True if removed, False if not found
        """
        if name in self._components:
            del self._components[name]
            logger.debug("component_unregistered", component=name)
            return True
        return False
    
    def track_request(self, request: Any) -> None:
        """
        Track an active request.
        
        Args:
            request: Request object to track
        """
        ref = weakref.ref(request, self._cleanup_request_ref)
        self._active_requests.add(ref)
    
    def _cleanup_request_ref(self, ref: weakref.ref) -> None:
        """Clean up dead request reference."""
        self._active_requests.discard(ref)
    
    def untrack_request(self, request: Any) -> None:
        """
        Untrack a completed request.
        
        Args:
            request: Request object to untrack
        """
        # Find and remove the reference
        to_remove = None
        for ref in self._active_requests:
            if ref() is request:
                to_remove = ref
                break
        
        if to_remove:
            self._active_requests.remove(to_remove)
    
    def get_active_request_count(self) -> int:
        """Get count of active requests."""
        # Clean up dead references
        self._active_requests = {ref for ref in self._active_requests if ref() is not None}
        return len(self._active_requests)
    
    def add_shutdown_hook(self, hook: Callable[[], Any]) -> None:
        """
        Add a shutdown hook.
        
        Args:
            hook: Hook function to call during shutdown
        """
        self._shutdown_hooks.append(hook)
    
    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        if sys.platform == "win32":
            # Windows signal handling
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._signal_handler)
        else:
            # Unix signal handling
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                self._original_handlers[sig] = signal.getsignal(sig)
                loop.add_signal_handler(sig, self._signal_handler_async, sig)
        
        logger.info("signal_handlers_installed")
    
    def restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        if sys.platform == "win32":
            for sig, handler in self._original_handlers.items():
                signal.signal(sig, handler)
        else:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                loop.remove_signal_handler(sig)
                if sig in self._original_handlers:
                    signal.signal(sig, self._original_handlers[sig])
        
        self._original_handlers.clear()
        logger.debug("signal_handlers_restored")
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signal (sync)."""
        logger.info("shutdown_signal_received", signal=signal.Signals(signum).name)
        asyncio.create_task(self.shutdown())
    
    def _signal_handler_async(self, signum: int) -> None:
        """Handle shutdown signal (async)."""
        logger.info("shutdown_signal_received", signal=signal.Signals(signum).name)
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self, reason: str = "signal") -> None:
        """
        Initiate graceful shutdown.
        
        Args:
            reason: Shutdown reason
        """
        async with self._lock:
            if self._is_shutting_down:
                logger.warning("shutdown_already_in_progress")
                await self._shutdown_event.wait()
                return
            
            self._is_shutting_down = True
        
        logger.info("shutdown_initiated", reason=reason, timeout=self.timeout)
        
        # Emit shutdown event
        await emit(
            "shutdown_initiated",
            EventCategory.SYSTEM,
            {"reason": reason, "timeout": self.timeout},
            priority=EventPriority.CRITICAL
        )
        
        # Create shutdown task with timeout
        self._shutdown_task = asyncio.create_task(
            self._shutdown_with_timeout()
        )
        
        try:
            await self._shutdown_task
        except asyncio.TimeoutError:
            logger.error("shutdown_timeout_exceeded", timeout=self.timeout)
            # Force exit
            os._exit(1)
    
    async def _shutdown_with_timeout(self) -> None:
        """Execute shutdown with timeout."""
        try:
            await asyncio.wait_for(
                self._execute_shutdown(),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.error("shutdown_timeout", timeout=self.timeout)
            raise
        finally:
            self._shutdown_complete = True
            self._shutdown_event.set()
    
    async def _execute_shutdown(self) -> None:
        """Execute shutdown phases."""
        start_time = datetime.utcnow()
        
        # Execute pre-shutdown hooks
        await self._execute_hooks()
        
        # Group components by phase
        phases: Dict[ShutdownPhase, List[ShutdownComponent]] = {}
        for component in self._components.values():
            if component.phase not in phases:
                phases[component.phase] = []
            phases[component.phase].append(component)
        
        # Execute phases in order
        for phase in ShutdownPhase:
            if phase == ShutdownPhase.COMPLETE:
                continue
            
            if phase in phases:
                logger.info("executing_shutdown_phase", phase=phase.name)
                
                # Special handling for DRAIN_REQUESTS phase
                if phase == ShutdownPhase.DRAIN_REQUESTS:
                    await self._drain_requests()
                
                # Execute components in phase
                await self._execute_phase_components(phases[phase])
                
                # Emit phase complete event
                await emit(
                    "shutdown_phase_complete",
                    EventCategory.SYSTEM,
                    {"phase": phase.name},
                    priority=EventPriority.HIGH
                )
        
        # Restore signal handlers
        self.restore_signal_handlers()
        
        # Calculate shutdown duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "shutdown_complete",
            duration_seconds=duration,
            components_shutdown=len(self._components)
        )
        
        # Emit shutdown complete event
        await emit(
            "shutdown_complete",
            EventCategory.SYSTEM,
            {"duration_seconds": duration},
            priority=EventPriority.CRITICAL
        )
    
    async def _execute_hooks(self) -> None:
        """Execute shutdown hooks."""
        if not self._shutdown_hooks:
            return
        
        logger.info("executing_shutdown_hooks", count=len(self._shutdown_hooks))
        
        for hook in self._shutdown_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                logger.error(
                    "shutdown_hook_error",
                    hook=getattr(hook, '__name__', 'unknown'),
                    error=str(e),
                    exc_info=True
                )
    
    async def _drain_requests(self) -> None:
        """Drain active requests."""
        request_count = self.get_active_request_count()
        
        if request_count == 0:
            logger.info("no_active_requests")
            return
        
        logger.info("draining_requests", count=request_count)
        
        # Wait for requests to complete with timeout
        drain_timeout = min(30.0, self.timeout / 2)
        start_time = datetime.utcnow()
        
        while self.get_active_request_count() > 0:
            if (datetime.utcnow() - start_time).total_seconds() > drain_timeout:
                logger.warning(
                    "request_drain_timeout",
                    remaining=self.get_active_request_count()
                )
                break
            
            await asyncio.sleep(0.1)
        
        final_count = self.get_active_request_count()
        if final_count > 0:
            logger.warning("requests_abandoned", count=final_count)
    
    async def _execute_phase_components(
        self,
        components: List[ShutdownComponent]
    ) -> None:
        """Execute components in a phase respecting dependencies."""
        # Sort components by dependencies
        sorted_components = self._topological_sort(components)
        
        # Execute components
        for component in sorted_components:
            try:
                logger.debug(
                    "shutting_down_component",
                    component=component.name,
                    timeout=component.timeout
                )
                
                if component.is_async:
                    await asyncio.wait_for(
                        component.handler(),
                        timeout=component.timeout
                    )
                else:
                    # Run sync handler in executor
                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, component.handler),
                        timeout=component.timeout
                    )
                
                logger.debug("component_shutdown_complete", component=component.name)
                
            except asyncio.TimeoutError:
                logger.error(
                    "component_shutdown_timeout",
                    component=component.name,
                    timeout=component.timeout
                )
            except Exception as e:
                logger.error(
                    "component_shutdown_error",
                    component=component.name,
                    error=str(e),
                    exc_info=True
                )
    
    def _topological_sort(
        self,
        components: List[ShutdownComponent]
    ) -> List[ShutdownComponent]:
        """Sort components by dependencies."""
        # Simple topological sort
        sorted_list = []
        visited = set()
        visiting = set()
        
        def visit(component: ShutdownComponent):
            if component.name in visiting:
                raise SystemError(f"Circular dependency detected: {component.name}")
            
            if component.name not in visited:
                visiting.add(component.name)
                
                # Visit dependencies first
                for dep_name in component.dependencies:
                    if dep_name in self._components:
                        dep = self._components[dep_name]
                        if dep in components:
                            visit(dep)
                
                visiting.remove(component.name)
                visited.add(component.name)
                sorted_list.append(component)
        
        for component in components:
            visit(component)
        
        return sorted_list
    
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._is_shutting_down
    
    def is_shutdown_complete(self) -> bool:
        """Check if shutdown is complete."""
        return self._shutdown_complete
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete."""
        await self._shutdown_event.wait()


# Global shutdown manager instance
_shutdown_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    """Get global shutdown manager instance."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager


# Convenience functions

def register_shutdown_handler(
    name: str,
    handler: Callable[[], Any],
    phase: ShutdownPhase = ShutdownPhase.CLEANUP_RESOURCES,
    timeout: Optional[float] = None,
    dependencies: Optional[List[str]] = None
) -> None:
    """Register a shutdown handler."""
    get_shutdown_manager().register_component(
        name=name,
        handler=handler,
        phase=phase,
        timeout=timeout,
        dependencies=dependencies
    )


def track_request(request: Any) -> None:
    """Track an active request."""
    get_shutdown_manager().track_request(request)


def untrack_request(request: Any) -> None:
    """Untrack a completed request."""
    get_shutdown_manager().untrack_request(request)


def add_shutdown_hook(hook: Callable[[], Any]) -> None:
    """Add a shutdown hook."""
    get_shutdown_manager().add_shutdown_hook(hook)


async def shutdown(reason: str = "manual") -> None:
    """Initiate graceful shutdown."""
    await get_shutdown_manager().shutdown(reason)


def is_shutting_down() -> bool:
    """Check if shutdown is in progress."""
    return get_shutdown_manager().is_shutting_down()


# Decorator for request tracking

def track_request_lifetime(func):
    """Decorator to track request lifetime."""
    @functools.wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        track_request(self)
        try:
            return await func(self, *args, **kwargs)
        finally:
            untrack_request(self)
    
    @functools.wraps(func)
    def sync_wrapper(self, *args, **kwargs):
        track_request(self)
        try:
            return func(self, *args, **kwargs)
        finally:
            untrack_request(self)
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# Export public API
__all__ = [
    'ShutdownManager',
    'ShutdownPhase',
    'ShutdownComponent',
    'get_shutdown_manager',
    'register_shutdown_handler',
    'track_request',
    'untrack_request',
    'add_shutdown_hook',
    'shutdown',
    'is_shutting_down',
    'track_request_lifetime',
]