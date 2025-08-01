"""
Hook Manager for Shannon MCP Server.

Manages event hooks for automation and extensibility.
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import httpx

from .base import BaseManager, ManagerConfig, ManagerError
from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.managers.hook")


class HookType(Enum):
    """Types of hooks supported."""
    SHELL = "shell"
    HTTP = "http"
    FUNCTION = "function"
    WEBHOOK = "webhook"


class HookEvent(Enum):
    """Events that can trigger hooks."""
    SESSION_CREATED = "session.created"
    SESSION_COMPLETED = "session.completed"
    SESSION_CANCELLED = "session.cancelled"
    SESSION_ERROR = "session.error"
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    TASK_ASSIGNED = "task.assigned"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    SERVER_STARTED = "server.started"
    SERVER_STOPPED = "server.stopped"
    CUSTOM = "custom"


@dataclass
class Hook:
    """Represents a hook configuration."""
    id: str
    name: str
    event: str
    type: HookType
    target: str  # Command, URL, or function name
    active: bool = True
    filter_pattern: Optional[str] = None  # Regex pattern to filter events
    retry_count: int = 3
    timeout: int = 30  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "event": self.event,
            "type": self.type.value,
            "target": self.target,
            "active": self.active,
            "filter_pattern": self.filter_pattern,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "trigger_count": self.trigger_count
        }


@dataclass
class HookResult:
    """Result of hook execution."""
    hook_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    retries: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HookConfig(ManagerConfig):
    """Configuration for hook manager."""
    max_hooks_per_event: int = 10
    global_timeout: int = 60
    enable_shell_hooks: bool = True
    enable_http_hooks: bool = True
    allowed_shell_commands: List[str] = field(default_factory=list)
    blocked_shell_commands: List[str] = field(default_factory=lambda: ["rm", "dd", "format"])
    http_retry_count: int = 3
    http_timeout: int = 30


class HookManager(BaseManager[Hook]):
    """Manages event hooks for automation."""
    
    def __init__(self, config: HookConfig):
        """Initialize hook manager."""
        super().__init__(config)
        self.config: HookConfig = config
        self._hooks: Dict[str, Hook] = {}
        self._event_hooks: Dict[str, List[str]] = {}
        self._function_hooks: Dict[str, Callable] = {}
        self._hook_results: List[HookResult] = []
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _initialize(self) -> None:
        """Initialize hook manager."""
        logger.info("Initializing hook manager")
        
        # Create HTTP client
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.http_timeout),
            follow_redirects=True
        )
        
        # Load existing hooks from database
        if self.config.db_path:
            await self._load_hooks()
        
        # Register built-in hooks
        self._register_builtin_hooks()
    
    async def _start(self) -> None:
        """Start hook manager operations."""
        logger.info("Starting hook manager")
    
    async def _stop(self) -> None:
        """Stop hook manager operations."""
        logger.info("Stopping hook manager")
        
        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Check hook manager health."""
        return {
            "healthy": True,
            "hook_count": len(self._hooks),
            "active_hooks": sum(1 for h in self._hooks.values() if h.active),
            "recent_results": len([r for r in self._hook_results[-100:] if r.success])
        }
    
    async def _create_schema(self) -> None:
        """Create database schema for hooks."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS hooks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                event TEXT NOT NULL,
                type TEXT NOT NULL,
                target TEXT NOT NULL,
                active BOOLEAN DEFAULT 1,
                filter_pattern TEXT,
                retry_count INTEGER DEFAULT 3,
                timeout INTEGER DEFAULT 30,
                metadata TEXT,
                created_at TIMESTAMP NOT NULL,
                last_triggered TIMESTAMP,
                trigger_count INTEGER DEFAULT 0
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_hooks_event 
            ON hooks(event)
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS hook_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hook_id TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                output TEXT,
                error TEXT,
                duration REAL,
                retries INTEGER,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (hook_id) REFERENCES hooks(id)
            )
        """)
    
    async def register_hook(
        self,
        name: str,
        event: str,
        type: Union[str, HookType],
        target: str,
        filter_pattern: Optional[str] = None,
        retry_count: int = 3,
        timeout: int = 30,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Hook:
        """Register a new hook."""
        # Validate hook type
        if isinstance(type, str):
            try:
                hook_type = HookType(type)
            except ValueError:
                raise ManagerError(f"Invalid hook type: {type}")
        else:
            hook_type = type
        
        # Validate based on type
        if hook_type == HookType.SHELL and not self.config.enable_shell_hooks:
            raise ManagerError("Shell hooks are disabled")
        
        if hook_type == HookType.HTTP and not self.config.enable_http_hooks:
            raise ManagerError("HTTP hooks are disabled")
        
        # Check for blocked commands
        if hook_type == HookType.SHELL:
            for blocked in self.config.blocked_shell_commands:
                if blocked in target:
                    raise ManagerError(f"Command contains blocked term: {blocked}")
        
        # Create hook
        hook_id = f"hook_{len(self._hooks) + 1}"
        hook = Hook(
            id=hook_id,
            name=name,
            event=event,
            type=hook_type,
            target=target,
            filter_pattern=filter_pattern,
            retry_count=retry_count,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        # Store hook
        self._hooks[hook_id] = hook
        
        # Index by event
        if event not in self._event_hooks:
            self._event_hooks[event] = []
        self._event_hooks[event].append(hook_id)
        
        # Persist to database
        if self.db:
            await self._persist_hook(hook)
        
        logger.info(f"Registered hook {hook_id}: {name} for event {event}")
        return hook
    
    async def register_function_hook(
        self,
        name: str,
        event: str,
        function: Callable,
        filter_pattern: Optional[str] = None
    ) -> Hook:
        """Register a function hook."""
        # Store function
        func_name = f"func_{function.__name__}_{len(self._function_hooks)}"
        self._function_hooks[func_name] = function
        
        # Create hook
        return await self.register_hook(
            name=name,
            event=event,
            type=HookType.FUNCTION,
            target=func_name,
            filter_pattern=filter_pattern
        )
    
    async def register_session_hook(
        self,
        session_id: str,
        event: str,
        action: Dict[str, Any]
    ) -> Hook:
        """Register a hook specific to a session."""
        # Create filter pattern for session
        filter_pattern = f"session_id.*{session_id}"
        
        return await self.register_hook(
            name=f"Session {session_id} - {event}",
            event=event,
            type=action['type'],
            target=action['target'],
            filter_pattern=filter_pattern,
            metadata={"session_id": session_id}
        )
    
    async def register_task_callback(
        self,
        task_id: str,
        callback_url: str
    ) -> Hook:
        """Register a webhook callback for task completion."""
        return await self.register_hook(
            name=f"Task {task_id} callback",
            event=HookEvent.TASK_COMPLETED.value,
            type=HookType.WEBHOOK,
            target=callback_url,
            filter_pattern=f"task_id.*{task_id}",
            metadata={"task_id": task_id}
        )
    
    async def trigger_hook(
        self,
        event: str,
        data: Dict[str, Any]
    ) -> List[HookResult]:
        """Trigger all hooks for an event."""
        hook_ids = self._event_hooks.get(event, [])
        if not hook_ids:
            return []
        
        results = []
        tasks = []
        
        for hook_id in hook_ids:
            hook = self._hooks.get(hook_id)
            if not hook or not hook.active:
                continue
            
            # Check filter pattern
            if hook.filter_pattern:
                pattern = re.compile(hook.filter_pattern)
                data_str = json.dumps(data)
                if not pattern.search(data_str):
                    continue
            
            # Execute hook asynchronously
            task = asyncio.create_task(self._execute_hook(hook, event, data))
            tasks.append(task)
        
        # Wait for all hooks with timeout
        if tasks:
            done, pending = await asyncio.wait(
                tasks,
                timeout=self.config.global_timeout
            )
            
            # Collect results
            for task in done:
                try:
                    result = await task
                    results.append(result)
                except Exception as e:
                    logger.error(f"Hook execution error: {e}")
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
        
        return results
    
    async def list_hooks(
        self,
        event: Optional[str] = None,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List all hooks, optionally filtered."""
        hooks = []
        
        for hook in self._hooks.values():
            if event and hook.event != event:
                continue
            if active_only and not hook.active:
                continue
            
            hooks.append(hook.to_dict())
        
        return hooks
    
    async def update_hook(
        self,
        hook_id: str,
        updates: Dict[str, Any]
    ) -> Hook:
        """Update hook configuration."""
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ManagerError(f"Hook {hook_id} not found")
        
        # Update allowed fields
        allowed_fields = ['name', 'active', 'filter_pattern', 'retry_count', 'timeout', 'metadata']
        for field in allowed_fields:
            if field in updates:
                setattr(hook, field, updates[field])
        
        # Persist changes
        if self.db:
            await self._update_hook_db(hook)
        
        return hook
    
    async def delete_hook(self, hook_id: str) -> None:
        """Delete a hook."""
        hook = self._hooks.get(hook_id)
        if not hook:
            return
        
        # Remove from indices
        del self._hooks[hook_id]
        if hook.event in self._event_hooks:
            self._event_hooks[hook.event].remove(hook_id)
        
        # Remove from database
        if self.db:
            await self.db.execute("DELETE FROM hooks WHERE id = ?", (hook_id,))
            await self.db.commit()
        
        logger.info(f"Deleted hook {hook_id}")
    
    # Private helper methods
    
    async def _execute_hook(
        self,
        hook: Hook,
        event: str,
        data: Dict[str, Any]
    ) -> HookResult:
        """Execute a single hook."""
        start_time = datetime.now()
        result = HookResult(hook_id=hook.id, success=False)
        
        for attempt in range(hook.retry_count):
            try:
                if hook.type == HookType.SHELL:
                    output = await self._execute_shell_hook(hook, data)
                elif hook.type == HookType.HTTP:
                    output = await self._execute_http_hook(hook, data)
                elif hook.type == HookType.WEBHOOK:
                    output = await self._execute_webhook_hook(hook, data)
                elif hook.type == HookType.FUNCTION:
                    output = await self._execute_function_hook(hook, data)
                else:
                    raise ManagerError(f"Unknown hook type: {hook.type}")
                
                result.success = True
                result.output = output
                result.retries = attempt
                break
                
            except Exception as e:
                logger.warning(f"Hook {hook.id} attempt {attempt + 1} failed: {e}")
                result.error = str(e)
                
                if attempt < hook.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # Update hook statistics
        hook.last_triggered = datetime.now(timezone.utc)
        hook.trigger_count += 1
        
        # Calculate duration
        result.duration = (datetime.now() - start_time).total_seconds()
        
        # Store result
        self._hook_results.append(result)
        if len(self._hook_results) > 1000:
            self._hook_results = self._hook_results[-1000:]
        
        # Persist result
        if self.db:
            await self._persist_hook_result(result)
        
        return result
    
    async def _execute_shell_hook(self, hook: Hook, data: Dict[str, Any]) -> str:
        """Execute shell command hook."""
        # Prepare command with data substitution
        command = hook.target
        for key, value in data.items():
            command = command.replace(f"{{{key}}}", str(value))
        
        # Execute command
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "SHANNON_HOOK_DATA": json.dumps(data)}
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=hook.timeout
            )
            
            if proc.returncode != 0:
                raise ManagerError(f"Command failed: {stderr.decode()}")
            
            return stdout.decode()
            
        except asyncio.TimeoutError:
            proc.kill()
            raise ManagerError("Command timed out")
    
    async def _execute_http_hook(self, hook: Hook, data: Dict[str, Any]) -> str:
        """Execute HTTP request hook."""
        # Parse URL and method from target
        parts = hook.target.split(' ', 1)
        method = parts[0] if len(parts) > 1 else "POST"
        url = parts[1] if len(parts) > 1 else parts[0]
        
        # Make request
        response = await self._http_client.request(
            method=method,
            url=url,
            json=data,
            timeout=hook.timeout
        )
        
        response.raise_for_status()
        return response.text
    
    async def _execute_webhook_hook(self, hook: Hook, data: Dict[str, Any]) -> str:
        """Execute webhook hook."""
        # Webhook is just POST to URL
        response = await self._http_client.post(
            hook.target,
            json=data,
            timeout=hook.timeout
        )
        
        response.raise_for_status()
        return response.text
    
    async def _execute_function_hook(self, hook: Hook, data: Dict[str, Any]) -> str:
        """Execute function hook."""
        func = self._function_hooks.get(hook.target)
        if not func:
            raise ManagerError(f"Function {hook.target} not found")
        
        # Execute function
        if asyncio.iscoroutinefunction(func):
            result = await func(data)
        else:
            result = func(data)
        
        return str(result)
    
    def _register_builtin_hooks(self) -> None:
        """Register built-in system hooks."""
        # Example: Log all errors to file
        async def log_errors(data: Dict[str, Any]) -> str:
            logger.error(f"Session error: {data}")
            return "Logged"
        
        self._function_hooks["builtin_log_errors"] = log_errors
    
    async def _load_hooks(self) -> None:
        """Load hooks from database."""
        rows = await self.execute_query("""
            SELECT id, name, event, type, target, active,
                   filter_pattern, retry_count, timeout, metadata,
                   created_at, last_triggered, trigger_count
            FROM hooks
            ORDER BY created_at DESC
        """)
        
        for row in rows:
            hook = Hook(
                id=row['id'],
                name=row['name'],
                event=row['event'],
                type=HookType(row['type']),
                target=row['target'],
                active=bool(row['active']),
                filter_pattern=row['filter_pattern'],
                retry_count=row['retry_count'],
                timeout=row['timeout'],
                metadata=json.loads(row['metadata'] or '{}'),
                created_at=datetime.fromisoformat(row['created_at']),
                last_triggered=datetime.fromisoformat(row['last_triggered']) if row['last_triggered'] else None,
                trigger_count=row['trigger_count']
            )
            
            self._hooks[hook.id] = hook
            
            if hook.event not in self._event_hooks:
                self._event_hooks[hook.event] = []
            self._event_hooks[hook.event].append(hook.id)
    
    async def _persist_hook(self, hook: Hook) -> None:
        """Persist hook to database."""
        await self.db.execute("""
            INSERT INTO hooks (
                id, name, event, type, target, active,
                filter_pattern, retry_count, timeout, metadata,
                created_at, last_triggered, trigger_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hook.id,
            hook.name,
            hook.event,
            hook.type.value,
            hook.target,
            hook.active,
            hook.filter_pattern,
            hook.retry_count,
            hook.timeout,
            json.dumps(hook.metadata),
            hook.created_at.isoformat(),
            hook.last_triggered.isoformat() if hook.last_triggered else None,
            hook.trigger_count
        ))
        await self.db.commit()
    
    async def _update_hook_db(self, hook: Hook) -> None:
        """Update hook in database."""
        await self.db.execute("""
            UPDATE hooks SET
                name = ?, active = ?, filter_pattern = ?,
                retry_count = ?, timeout = ?, metadata = ?,
                last_triggered = ?, trigger_count = ?
            WHERE id = ?
        """, (
            hook.name,
            hook.active,
            hook.filter_pattern,
            hook.retry_count,
            hook.timeout,
            json.dumps(hook.metadata),
            hook.last_triggered.isoformat() if hook.last_triggered else None,
            hook.trigger_count,
            hook.id
        ))
        await self.db.commit()
    
    async def _persist_hook_result(self, result: HookResult) -> None:
        """Persist hook result to database."""
        await self.db.execute("""
            INSERT INTO hook_results (
                hook_id, success, output, error,
                duration, retries, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result.hook_id,
            result.success,
            result.output,
            result.error,
            result.duration,
            result.retries,
            result.timestamp.isoformat()
        ))
        await self.db.commit()