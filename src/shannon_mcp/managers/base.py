"""
Base manager abstract class for Shannon MCP Server.

This module provides the foundation for all manager components with:
- Common initialization patterns
- Database connection management
- Event notification system
- Error handling and recovery
- Lifecycle management (start/stop)
- Health checking
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, TypeVar, Generic
from pathlib import Path
import asyncio
import aiosqlite
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog
from contextlib import asynccontextmanager

from ..utils.logging import get_logger, log_function_call


T = TypeVar('T')


class ManagerState(Enum):
    """Manager lifecycle states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ManagerError(Exception):
    """Base exception for manager errors."""
    pass


class ManagerNotReadyError(ManagerError):
    """Raised when manager operation is called before initialization."""
    pass


class ManagerAlreadyRunningError(ManagerError):
    """Raised when trying to start an already running manager."""
    pass


@dataclass
class ManagerConfig:
    """Base configuration for all managers."""
    name: str
    db_path: Optional[Path] = None
    enable_metrics: bool = True
    enable_notifications: bool = True
    health_check_interval: int = 60  # seconds
    auto_recovery: bool = True
    max_recovery_attempts: int = 3
    recovery_backoff: float = 1.0  # seconds
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Health status information."""
    healthy: bool
    last_check: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BaseManager(ABC, Generic[T]):
    """
    Abstract base class for all manager components.
    
    Provides common functionality for:
    - Lifecycle management
    - Database operations
    - Event notifications
    - Health monitoring
    - Error recovery
    """
    
    def __init__(self, config: ManagerConfig):
        """Initialize base manager."""
        self.config = config
        self.logger = get_logger(f"shannon-mcp.managers.{config.name}")
        self.state = ManagerState.UNINITIALIZED
        self.db: Optional[aiosqlite.Connection] = None
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._health_status = HealthStatus(healthy=True, last_check=datetime.utcnow())
        self._health_task: Optional[asyncio.Task] = None
        self._recovery_attempts = 0
        self._tasks: List[asyncio.Task] = []
        
    @property
    def is_ready(self) -> bool:
        """Check if manager is ready for operations."""
        return self.state in (ManagerState.READY, ManagerState.RUNNING)
    
    @property
    def is_running(self) -> bool:
        """Check if manager is actively running."""
        return self.state == ManagerState.RUNNING
    
    async def initialize(self) -> None:
        """
        Initialize the manager.
        
        Sets up database, performs initial setup, and transitions to READY state.
        """
        if self.state != ManagerState.UNINITIALIZED:
            raise ManagerError(f"Cannot initialize from state: {self.state}")
        
        self.state = ManagerState.INITIALIZING
        self.logger.info("initializing_manager", config=self.config)
        
        try:
            # Set up database if configured
            if self.config.db_path:
                await self._setup_database()
            
            # Perform component-specific initialization
            await self._initialize()
            
            self.state = ManagerState.READY
            self.logger.info("manager_initialized")
            await self._notify_event("initialized", {"manager": self.config.name})
            
        except Exception as e:
            self.state = ManagerState.ERROR
            self.logger.error("initialization_failed", error=str(e), exc_info=True)
            raise ManagerError(f"Failed to initialize {self.config.name}: {e}") from e
    
    async def start(self) -> None:
        """
        Start the manager.
        
        Begins active operations and starts health monitoring.
        """
        if not self.is_ready:
            raise ManagerNotReadyError(f"Manager {self.config.name} not ready")
        
        if self.is_running:
            raise ManagerAlreadyRunningError(f"Manager {self.config.name} already running")
        
        self.state = ManagerState.STARTING
        self.logger.info("starting_manager")
        
        try:
            # Start component-specific operations
            await self._start()
            
            # Start health monitoring
            if self.config.health_check_interval > 0:
                self._health_task = asyncio.create_task(self._health_monitor())
                self._tasks.append(self._health_task)
            
            self.state = ManagerState.RUNNING
            self.logger.info("manager_started")
            await self._notify_event("started", {"manager": self.config.name})
            
        except Exception as e:
            self.state = ManagerState.ERROR
            self.logger.error("start_failed", error=str(e), exc_info=True)
            raise ManagerError(f"Failed to start {self.config.name}: {e}") from e
    
    async def stop(self) -> None:
        """
        Stop the manager gracefully.
        
        Stops all operations and cleans up resources.
        """
        if not self.is_running:
            self.logger.warning("stop_called_when_not_running", state=self.state)
            return
        
        self.state = ManagerState.STOPPING
        self.logger.info("stopping_manager")
        
        try:
            # Cancel health monitoring
            if self._health_task:
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel all managed tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Stop component-specific operations
            await self._stop()
            
            # Close database connection
            if self.db:
                await self.db.close()
                self.db = None
            
            self.state = ManagerState.STOPPED
            self.logger.info("manager_stopped")
            await self._notify_event("stopped", {"manager": self.config.name})
            
        except Exception as e:
            self.state = ManagerState.ERROR
            self.logger.error("stop_failed", error=str(e), exc_info=True)
            raise ManagerError(f"Failed to stop {self.config.name}: {e}") from e
    
    async def restart(self) -> None:
        """Restart the manager."""
        self.logger.info("restarting_manager")
        await self.stop()
        await self.initialize()
        await self.start()
    
    async def health_check(self) -> HealthStatus:
        """
        Perform health check.
        
        Returns current health status of the manager.
        """
        try:
            # Perform component-specific health check
            details = await self._health_check()
            
            self._health_status = HealthStatus(
                healthy=True,
                last_check=datetime.utcnow(),
                details=details
            )
            
        except Exception as e:
            self._health_status = HealthStatus(
                healthy=False,
                last_check=datetime.utcnow(),
                error=str(e)
            )
            self.logger.error("health_check_failed", error=str(e))
        
        return self._health_status
    
    def register_event_handler(self, event: str, handler: Callable) -> None:
        """Register an event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        self.logger.debug("event_handler_registered", event_type=event)
    
    def unregister_event_handler(self, event: str, handler: Callable) -> None:
        """Unregister an event handler."""
        if event in self._event_handlers:
            self._event_handlers[event].remove(handler)
            self.logger.debug("event_handler_unregistered", event_type=event)
    
    async def _notify_event(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all handlers of an event."""
        if not self.config.enable_notifications:
            return
        
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, data)
                else:
                    handler(event, data)
            except Exception as e:
                self.logger.error(
                    "event_handler_error",
                    event_type=event,
                    handler=handler.__name__,
                    error=str(e)
                )
    
    async def _setup_database(self) -> None:
        """Set up database connection and schema."""
        if not self.config.db_path:
            return
        
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(str(self.config.db_path))
        self.db.row_factory = aiosqlite.Row
        
        # Enable foreign keys and WAL mode
        await self.db.execute("PRAGMA foreign_keys = ON")
        await self.db.execute("PRAGMA journal_mode = WAL")
        
        # Create component-specific schema
        await self._create_schema()
        await self.db.commit()
    
    async def _health_monitor(self) -> None:
        """Background task for health monitoring."""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                status = await self.health_check()
                
                if not status.healthy and self.config.auto_recovery:
                    await self._attempt_recovery()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("health_monitor_error", error=str(e))
    
    async def _attempt_recovery(self) -> None:
        """Attempt automatic recovery."""
        if self._recovery_attempts >= self.config.max_recovery_attempts:
            self.logger.error(
                "max_recovery_attempts_exceeded",
                attempts=self._recovery_attempts
            )
            return
        
        self._recovery_attempts += 1
        backoff = self.config.recovery_backoff * self._recovery_attempts
        
        self.logger.info(
            "attempting_recovery",
            attempt=self._recovery_attempts,
            backoff=backoff
        )
        
        await asyncio.sleep(backoff)
        
        try:
            await self._recover()
            self._recovery_attempts = 0
            self.logger.info("recovery_successful")
        except Exception as e:
            self.logger.error("recovery_failed", error=str(e))
    
    @asynccontextmanager
    async def transaction(self):
        """Database transaction context manager."""
        if not self.db:
            raise ManagerError("Database not initialized")
        
        async with self.db.execute("BEGIN"):
            try:
                yield self.db
                await self.db.commit()
            except Exception:
                await self.db.rollback()
                raise
    
    @log_function_call(get_logger("shannon-mcp.managers.base"))
    async def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[aiosqlite.Row]:
        """Execute a database query safely."""
        if not self.db:
            raise ManagerError("Database not initialized")
        
        async with self.db.execute(query, params or ()) as cursor:
            return await cursor.fetchall()
    
    @log_function_call(get_logger("shannon-mcp.managers.base"))
    async def execute_many(
        self,
        query: str,
        params_list: List[tuple]
    ) -> None:
        """Execute many database operations."""
        if not self.db:
            raise ManagerError("Database not initialized")
        
        await self.db.executemany(query, params_list)
        await self.db.commit()
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Component-specific initialization logic."""
        pass
    
    @abstractmethod
    async def _start(self) -> None:
        """Component-specific start logic."""
        pass
    
    @abstractmethod
    async def _stop(self) -> None:
        """Component-specific stop logic."""
        pass
    
    @abstractmethod
    async def _health_check(self) -> Dict[str, Any]:
        """Component-specific health check logic."""
        pass
    
    @abstractmethod
    async def _create_schema(self) -> None:
        """Create component-specific database schema."""
        pass
    
    async def _recover(self) -> None:
        """Component-specific recovery logic."""
        # Default implementation - restart
        await self.restart()


# Export public API
__all__ = [
    'BaseManager',
    'ManagerConfig',
    'ManagerState',
    'ManagerError',
    'ManagerNotReadyError',
    'ManagerAlreadyRunningError',
    'HealthStatus',
]