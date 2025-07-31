"""
Command execution framework for slash commands.

This module provides the execution engine that integrates the markdown parser
and command registry to execute slash commands with full context management.
"""

import asyncio
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

from .parser import MarkdownParser, CommandBlock, FrontmatterData, CommandBlockType
from .registry import CommandRegistry, Command, CommandCategory
from ..utils.logging import get_logger
from ..utils.errors import ValidationError, SystemError
from ..utils.notifications import emit, EventCategory, EventPriority

logger = get_logger(__name__)


class ExecutionStatus(Enum):
    """Status of command execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionPriority(Enum):
    """Priority levels for command execution."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ExecutionContext:
    """Context for command execution."""
    # Session information
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    user_roles: Set[str] = field(default_factory=set)
    
    # File context
    file_path: Optional[Path] = None
    working_directory: Optional[Path] = None
    
    # Execution environment
    environment: Dict[str, str] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Frontmatter data
    frontmatter: Optional[FrontmatterData] = None
    
    # Execution settings
    timeout: Optional[float] = None
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    dry_run: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get variable with fallback to environment."""
        if name in self.variables:
            return self.variables[name]
        if name in self.environment:
            return self.environment[name]
        if self.frontmatter and self.frontmatter.has(name):
            return self.frontmatter.get(name)
        return default
    
    def set_variable(self, name: str, value: Any) -> None:
        """Set variable in context."""
        self.variables[name] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_roles": list(self.user_roles),
            "file_path": str(self.file_path) if self.file_path else None,
            "working_directory": str(self.working_directory) if self.working_directory else None,
            "environment": self.environment,
            "variables": self.variables,
            "frontmatter": self.frontmatter.to_dict() if self.frontmatter else None,
            "timeout": self.timeout,
            "priority": self.priority.value,
            "dry_run": self.dry_run,
            "metadata": self.metadata
        }


@dataclass
class ExecutionResult:
    """Result of command execution."""
    # Command information
    command_name: str
    command_block: CommandBlock
    
    # Execution details
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    
    # Results
    return_value: Any = None
    output: str = ""
    error: Optional[str] = None
    exit_code: Optional[int] = None
    
    # Context
    context: Optional[ExecutionContext] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.COMPLETED and (
            self.exit_code is None or self.exit_code == 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "command_name": self.command_name,
            "command_block": self.command_block.to_dict(),
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "return_value": self.return_value,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "context": self.context.to_dict() if self.context else None,
            "metadata": self.metadata,
            "success": self.success
        }


class CommandExecutor:
    """Command execution engine."""
    
    def __init__(self, registry: Optional[CommandRegistry] = None):
        """Initialize command executor."""
        self.registry = registry or CommandRegistry()
        self.parser = MarkdownParser()
        
        # Execution tracking
        self._active_executions: Dict[str, ExecutionResult] = {}
        self._execution_history: List[ExecutionResult] = []
        self._execution_lock = asyncio.Lock()
        
        # Configuration
        self.max_concurrent_executions = 10
        self.max_history_size = 1000
        self.default_timeout = 300.0  # 5 minutes
        self.enable_history = True
        
        # Execution hooks
        self._pre_execution_hooks: List[callable] = []
        self._post_execution_hooks: List[callable] = []
        
        logger.info("command_executor_initialized")
    
    def add_pre_execution_hook(self, hook: callable) -> None:
        """Add pre-execution hook."""
        self._pre_execution_hooks.append(hook)
        logger.debug("pre_execution_hook_added", hook=hook.__name__)
    
    def add_post_execution_hook(self, hook: callable) -> None:
        """Add post-execution hook."""
        self._post_execution_hooks.append(hook)
        logger.debug("post_execution_hook_added", hook=hook.__name__)
    
    async def execute_markdown(
        self,
        content: str,
        context: Optional[ExecutionContext] = None,
        file_path: Optional[Path] = None
    ) -> List[ExecutionResult]:
        """
        Execute all commands found in markdown content.
        
        Args:
            content: Markdown content to parse and execute
            context: Execution context
            file_path: Optional file path for context
            
        Returns:
            List of execution results
        """
        # Parse markdown content
        parsed = self.parser.parse(content, file_path)
        
        # Create or update context
        if context is None:
            context = ExecutionContext()
        
        if file_path:
            context.file_path = file_path
            context.working_directory = file_path.parent
        
        # Add frontmatter to context
        if parsed.get('frontmatter'):
            context.frontmatter = FrontmatterData(**parsed['frontmatter'])
        
        # Execute all command blocks
        results = []
        for block_data in parsed.get('command_blocks', []):
            command_block = CommandBlock(**block_data)
            
            try:
                result = await self.execute_command_block(command_block, context)
                results.append(result)
            except Exception as e:
                # Create failed result
                result = ExecutionResult(
                    command_name=command_block.command_name,
                    command_block=command_block,
                    status=ExecutionStatus.FAILED,
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    duration=0.0,
                    error=str(e),
                    context=context
                )
                results.append(result)
                
                logger.error(
                    "command_block_execution_failed",
                    command=command_block.command_name,
                    error=str(e)
                )
        
        return results
    
    async def execute_markdown_file(
        self,
        file_path: Path,
        context: Optional[ExecutionContext] = None
    ) -> List[ExecutionResult]:
        """Execute commands in a markdown file."""
        content = file_path.read_text(encoding='utf-8')
        return await self.execute_markdown(content, context, file_path)
    
    async def execute_command_block(
        self,
        command_block: CommandBlock,
        context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """
        Execute a single command block.
        
        Args:
            command_block: Command block to execute
            context: Execution context
            
        Returns:
            Execution result
        """
        if context is None:
            context = ExecutionContext()
        
        # Create execution result
        execution_id = f"{command_block.command_name}_{datetime.utcnow().timestamp()}"
        result = ExecutionResult(
            command_name=command_block.command_name,
            command_block=command_block,
            status=ExecutionStatus.PENDING,
            start_time=datetime.utcnow(),
            context=context
        )
        
        # Check concurrent execution limit
        async with self._execution_lock:
            if len(self._active_executions) >= self.max_concurrent_executions:
                result.status = ExecutionStatus.FAILED
                result.error = "Maximum concurrent executions exceeded"
                result.end_time = datetime.utcnow()
                result.duration = 0.0
                return result
            
            self._active_executions[execution_id] = result
        
        try:
            # Run pre-execution hooks
            for hook in self._pre_execution_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook(command_block, context)
                    else:
                        hook(command_block, context)
                except Exception as e:
                    logger.warning(
                        "pre_execution_hook_failed",
                        hook=hook.__name__,
                        error=str(e)
                    )
            
            # Update status
            result.status = ExecutionStatus.RUNNING
            
            # Execute command
            timeout = context.timeout or self.default_timeout
            
            if context.dry_run:
                # Dry run mode - don't actually execute
                result.status = ExecutionStatus.COMPLETED
                result.output = f"[DRY RUN] Would execute: {command_block.command_name}"
                result.return_value = {"dry_run": True}
            else:
                # Execute with timeout
                try:
                    result.return_value = await asyncio.wait_for(
                        self._execute_command(command_block, context),
                        timeout=timeout
                    )
                    result.status = ExecutionStatus.COMPLETED
                except asyncio.TimeoutError:
                    result.status = ExecutionStatus.TIMEOUT
                    result.error = f"Command timed out after {timeout}s"
                except Exception as e:
                    result.status = ExecutionStatus.FAILED
                    result.error = str(e)
                    raise
            
            # Run post-execution hooks
            for hook in self._post_execution_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook(command_block, context, result)
                    else:
                        hook(command_block, context, result)
                except Exception as e:
                    logger.warning(
                        "post_execution_hook_failed",
                        hook=hook.__name__,
                        error=str(e)
                    )
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            logger.error(
                "command_execution_error",
                command=command_block.command_name,
                error=str(e),
                exc_info=True
            )
            
        finally:
            # Update result timing
            result.end_time = datetime.utcnow()
            result.duration = (result.end_time - result.start_time).total_seconds()
            
            # Remove from active executions
            async with self._execution_lock:
                self._active_executions.pop(execution_id, None)
                
                # Add to history
                if self.enable_history:
                    self._execution_history.append(result)
                    
                    # Trim history if needed
                    if len(self._execution_history) > self.max_history_size:
                        self._execution_history = self._execution_history[-self.max_history_size:]
            
            # Emit execution event
            await self._emit_execution_event(result)
        
        return result
    
    async def _execute_command(
        self,
        command_block: CommandBlock,
        context: ExecutionContext
    ) -> Any:
        """Execute the actual command."""
        # Get command from registry
        command = self.registry.get_command(command_block.command_name)
        if not command:
            raise ValidationError(
                "command",
                command_block.command_name,
                "Command not found in registry"
            )
        
        # Execute using registry
        return await self.registry.execute_command(
            command_block.command_name,
            command_block.arguments,
            command_block.options,
            context=context.to_dict(),
            user_id=context.user_id,
            user_roles=context.user_roles
        )
    
    async def execute_single_command(
        self,
        command_name: str,
        arguments: List[str] = None,
        options: Dict[str, Any] = None,
        context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """Execute a single command by name."""
        if arguments is None:
            arguments = []
        if options is None:
            options = {}
        if context is None:
            context = ExecutionContext()
        
        # Create command block
        command_block = CommandBlock(
            command_type=CommandBlockType.SLASH_COMMAND,
            command_name=command_name,
            arguments=arguments,
            options=options
        )
        
        return await self.execute_command_block(command_block, context)
    
    def get_active_executions(self) -> Dict[str, ExecutionResult]:
        """Get currently active executions."""
        return self._active_executions.copy()
    
    def get_execution_history(
        self,
        limit: Optional[int] = None,
        status: Optional[ExecutionStatus] = None
    ) -> List[ExecutionResult]:
        """Get execution history."""
        history = self._execution_history.copy()
        
        # Filter by status
        if status:
            history = [r for r in history if r.status == status]
        
        # Apply limit
        if limit:
            history = history[-limit:]
        
        return history
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution."""
        async with self._execution_lock:
            if execution_id in self._active_executions:
                result = self._active_executions[execution_id]
                result.status = ExecutionStatus.CANCELLED
                result.end_time = datetime.utcnow()
                result.duration = (result.end_time - result.start_time).total_seconds()
                
                logger.info(
                    "execution_cancelled",
                    execution_id=execution_id,
                    command=result.command_name
                )
                
                return True
        
        return False
    
    async def _emit_execution_event(self, result: ExecutionResult) -> None:
        """Emit execution event."""
        await emit(
            "command_executed",
            EventCategory.SYSTEM,
            {
                "command_name": result.command_name,
                "status": result.status.value,
                "duration": result.duration,
                "success": result.success
            },
            priority=EventPriority.LOW
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        history = self._execution_history
        
        total_executions = len(history)
        if total_executions == 0:
            return {
                "total_executions": 0,
                "active_executions": len(self._active_executions),
                "success_rate": 0.0,
                "average_duration": 0.0,
                "by_status": {},
                "by_command": {}
            }
        
        # Calculate statistics
        successful = len([r for r in history if r.success])
        success_rate = successful / total_executions
        
        durations = [r.duration for r in history if r.duration is not None]
        average_duration = sum(durations) / len(durations) if durations else 0.0
        
        # Group by status
        by_status = {}
        for status in ExecutionStatus:
            count = len([r for r in history if r.status == status])
            if count > 0:
                by_status[status.value] = count
        
        # Group by command
        by_command = {}
        for result in history:
            cmd = result.command_name
            if cmd not in by_command:
                by_command[cmd] = {"count": 0, "success": 0, "avg_duration": 0.0}
            
            by_command[cmd]["count"] += 1
            if result.success:
                by_command[cmd]["success"] += 1
            
            if result.duration:
                current_avg = by_command[cmd]["avg_duration"]
                count = by_command[cmd]["count"]
                by_command[cmd]["avg_duration"] = (
                    (current_avg * (count - 1) + result.duration) / count
                )
        
        return {
            "total_executions": total_executions,
            "active_executions": len(self._active_executions),
            "success_rate": success_rate,
            "average_duration": average_duration,
            "by_status": by_status,
            "by_command": by_command
        }


# Export public API
__all__ = [
    'CommandExecutor',
    'ExecutionContext',
    'ExecutionResult',
    'ExecutionStatus',
    'ExecutionPriority'
]