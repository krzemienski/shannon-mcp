"""
Command registry for slash commands.

This module provides a registry system for managing and executing slash commands
with support for categorization, validation, permissions, and metadata.
"""

import asyncio
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

from ..utils.logging import get_logger
from ..utils.errors import ValidationError, SystemError
from ..utils.notifications import emit, EventCategory, EventPriority

logger = get_logger(__name__)


class CommandCategory(Enum):
    """Categories for organizing commands."""
    SYSTEM = "system"              # System and configuration commands
    SESSION = "session"            # Session management commands
    DEVELOPMENT = "development"    # Development and debugging commands
    ANALYSIS = "analysis"          # Data analysis and reporting commands
    UTILITY = "utility"            # General utility commands
    AUTOMATION = "automation"      # Automation and scripting commands
    INTEGRATION = "integration"    # Third-party integrations
    CUSTOM = "custom"              # User-defined custom commands


class CommandStatus(Enum):
    """Status of a command."""
    ACTIVE = "active"              # Command is active and available
    DEPRECATED = "deprecated"      # Command is deprecated but still works
    DISABLED = "disabled"          # Command is disabled
    EXPERIMENTAL = "experimental"  # Command is experimental
    MAINTENANCE = "maintenance"    # Command is under maintenance


class PermissionLevel(Enum):
    """Permission levels for command execution."""
    PUBLIC = "public"              # Anyone can execute
    USER = "user"                  # Authenticated users
    ADMIN = "admin"                # Admin users only
    SYSTEM = "system"              # System-level commands only


@dataclass
class CommandMetadata:
    """Metadata for a command."""
    name: str
    description: str
    category: CommandCategory
    version: str = "1.0.0"
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    
    # Usage information
    examples: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    documentation_url: Optional[str] = None
    
    # Technical details
    async_command: bool = False
    timeout: Optional[float] = None
    rate_limit: Optional[int] = None  # Max executions per minute
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "examples": self.examples,
            "see_also": self.see_also,
            "documentation_url": self.documentation_url,
            "async_command": self.async_command,
            "timeout": self.timeout,
            "rate_limit": self.rate_limit
        }


@dataclass
class CommandArgument:
    """Definition of a command argument."""
    name: str
    description: str
    type: type = str
    required: bool = True
    default: Any = None
    choices: Optional[List[Any]] = None
    
    def validate(self, value: Any) -> Any:
        """Validate and convert argument value."""
        if value is None:
            if self.required:
                raise ValidationError("argument", self.name, "Required argument missing")
            return self.default
        
        # Type conversion
        try:
            if self.type == bool:
                if isinstance(value, str):
                    return value.lower() in ('true', 'yes', '1', 'on')
                return bool(value)
            elif self.type in (int, float):
                return self.type(value)
            else:
                return self.type(value)
        except (ValueError, TypeError) as e:
            raise ValidationError("argument", self.name, f"Invalid type: {e}")
        
        # Choice validation
        if self.choices and value not in self.choices:
            raise ValidationError("argument", self.name, f"Must be one of: {self.choices}")
        
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.__name__,
            "required": self.required,
            "default": self.default,
            "choices": self.choices
        }


@dataclass
class CommandOption:
    """Definition of a command option/flag."""
    name: str
    description: str
    short_name: Optional[str] = None
    type: type = bool
    default: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "short_name": self.short_name,
            "type": self.type.__name__,
            "default": self.default
        }


@dataclass
class Command:
    """A registered slash command."""
    metadata: CommandMetadata
    handler: Callable
    arguments: List[CommandArgument] = field(default_factory=list)
    options: List[CommandOption] = field(default_factory=list)
    
    # Access control
    permission_level: PermissionLevel = PermissionLevel.PUBLIC
    allowed_users: Set[str] = field(default_factory=set)
    allowed_roles: Set[str] = field(default_factory=set)
    
    # Status and lifecycle
    status: CommandStatus = CommandStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    
    # Rate limiting
    execution_history: List[datetime] = field(default_factory=list)
    
    def can_execute(self, user_id: Optional[str] = None, user_roles: Optional[Set[str]] = None) -> bool:
        """Check if command can be executed by user."""
        if self.status == CommandStatus.DISABLED:
            return False
        
        # Check permission levels
        if self.permission_level == PermissionLevel.SYSTEM:
            return False  # System commands cannot be executed directly
        
        if self.permission_level == PermissionLevel.ADMIN:
            user_roles = user_roles or set()
            if 'admin' not in user_roles:
                return False
        
        # Check specific user/role permissions
        if self.allowed_users and user_id:
            if user_id not in self.allowed_users:
                return False
        
        if self.allowed_roles and user_roles:
            if not self.allowed_roles.intersection(user_roles):
                return False
        
        return True
    
    def check_rate_limit(self) -> bool:
        """Check if command is within rate limits."""
        if not self.metadata.rate_limit:
            return True
        
        now = datetime.utcnow()
        # Remove executions older than 1 minute
        cutoff = now.timestamp() - 60
        self.execution_history = [
            dt for dt in self.execution_history 
            if dt.timestamp() > cutoff
        ]
        
        return len(self.execution_history) < self.metadata.rate_limit
    
    def record_execution(self) -> None:
        """Record a command execution."""
        now = datetime.utcnow()
        self.last_used = now
        self.usage_count += 1
        self.execution_history.append(now)
    
    def validate_arguments(self, args: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Validate command arguments and options."""
        validated = {}
        
        # Validate positional arguments
        for i, arg_def in enumerate(self.arguments):
            if i < len(args):
                validated[arg_def.name] = arg_def.validate(args[i])
            else:
                validated[arg_def.name] = arg_def.validate(None)
        
        # Check for extra arguments
        if len(args) > len(self.arguments):
            extra_args = args[len(self.arguments):]
            logger.warning(
                "extra_arguments_ignored",
                command=self.metadata.name,
                extra_args=extra_args
            )
        
        # Validate options
        option_map = {opt.name: opt for opt in self.options}
        if opt.short_name:
            option_map[opt.short_name] = opt
        
        for opt_name, opt_value in options.items():
            if opt_name in option_map:
                opt_def = option_map[opt_name]
                validated[opt_def.name] = opt_def.validate(opt_value)
            else:
                logger.warning(
                    "unknown_option_ignored",
                    command=self.metadata.name,
                    option=opt_name
                )
        
        # Set defaults for missing options
        for opt_def in self.options:
            if opt_def.name not in validated:
                validated[opt_def.name] = opt_def.default
        
        return validated
    
    def get_usage_string(self) -> str:
        """Get usage string for the command."""
        usage_parts = [f"/{self.metadata.name}"]
        
        # Add arguments
        for arg in self.arguments:
            if arg.required:
                usage_parts.append(f"<{arg.name}>")
            else:
                usage_parts.append(f"[{arg.name}]")
        
        # Add options
        for opt in self.options:
            opt_str = f"--{opt.name}"
            if opt.short_name:
                opt_str += f"|-{opt.short_name}"
            if opt.type != bool:
                opt_str += f" <{opt.type.__name__}>"
            usage_parts.append(f"[{opt_str}]")
        
        return " ".join(usage_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "arguments": [arg.to_dict() for arg in self.arguments],
            "options": [opt.to_dict() for opt in self.options],
            "permission_level": self.permission_level.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "usage_count": self.usage_count,
            "usage_string": self.get_usage_string()
        }


class CommandRegistry:
    """Registry for managing slash commands."""
    
    def __init__(self):
        """Initialize command registry."""
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command_name
        self._categories: Dict[CommandCategory, List[str]] = {}
        self._handlers: Dict[str, Callable] = {}
        
        # Initialize categories
        for category in CommandCategory:
            self._categories[category] = []
    
    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        category: CommandCategory = CommandCategory.UTILITY,
        **kwargs
    ) -> Command:
        """
        Register a new command.
        
        Args:
            name: Command name
            handler: Function to handle the command
            description: Command description
            category: Command category
            **kwargs: Additional metadata
            
        Returns:
            Registered command
        """
        if name in self._commands:
            raise ValidationError("command_name", name, "Command already registered")
        
        # Create metadata
        metadata = CommandMetadata(
            name=name,
            description=description,
            category=category,
            async_command=inspect.iscoroutinefunction(handler),
            **kwargs
        )
        
        # Extract arguments and options from handler signature
        arguments, options = self._extract_signature(handler)
        
        # Create command
        command = Command(
            metadata=metadata,
            handler=handler,
            arguments=arguments,
            options=options
        )
        
        # Register command
        self._commands[name] = command
        self._handlers[name] = handler
        self._categories[category].append(name)
        
        logger.info(
            "command_registered",
            name=name,
            category=category.value,
            async_command=metadata.async_command
        )
        
        # Emit registration event
        asyncio.create_task(self._emit_registration_event(command))
        
        return command
    
    def register_decorator(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: CommandCategory = CommandCategory.UTILITY,
        **kwargs
    ):
        """Decorator for registering commands."""
        def decorator(func: Callable) -> Callable:
            cmd_name = name or func.__name__
            cmd_description = description or func.__doc__ or f"Execute {cmd_name}"
            
            self.register(cmd_name, func, cmd_description, category, **kwargs)
            return func
        return decorator
    
    def unregister(self, name: str) -> bool:
        """Unregister a command."""
        if name not in self._commands:
            return False
        
        command = self._commands[name]
        
        # Remove from category
        if command.metadata.category in self._categories:
            category_commands = self._categories[command.metadata.category]
            if name in category_commands:
                category_commands.remove(name)
        
        # Remove command
        del self._commands[name]
        del self._handlers[name]
        
        # Remove aliases
        aliases_to_remove = [alias for alias, cmd_name in self._aliases.items() if cmd_name == name]
        for alias in aliases_to_remove:
            del self._aliases[alias]
        
        logger.info("command_unregistered", name=name)
        return True
    
    def add_alias(self, alias: str, command_name: str) -> None:
        """Add an alias for a command."""
        if command_name not in self._commands:
            raise ValidationError("command_name", command_name, "Command not found")
        
        if alias in self._commands or alias in self._aliases:
            raise ValidationError("alias", alias, "Alias conflicts with existing command or alias")
        
        self._aliases[alias] = command_name
        logger.debug("command_alias_added", alias=alias, command=command_name)
    
    def remove_alias(self, alias: str) -> bool:
        """Remove a command alias."""
        if alias in self._aliases:
            del self._aliases[alias]
            logger.debug("command_alias_removed", alias=alias)
            return True
        return False
    
    def get_command(self, name: str) -> Optional[Command]:
        """Get a command by name or alias."""
        # Check direct command name
        if name in self._commands:
            return self._commands[name]
        
        # Check aliases
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        
        return None
    
    def list_commands(
        self,
        category: Optional[CommandCategory] = None,
        status: Optional[CommandStatus] = None,
        include_disabled: bool = False
    ) -> List[Command]:
        """List registered commands with optional filtering."""
        commands = list(self._commands.values())
        
        # Filter by category
        if category:
            commands = [cmd for cmd in commands if cmd.metadata.category == category]
        
        # Filter by status
        if status:
            commands = [cmd for cmd in commands if cmd.status == status]
        elif not include_disabled:
            commands = [cmd for cmd in commands if cmd.status != CommandStatus.DISABLED]
        
        return sorted(commands, key=lambda c: c.metadata.name)
    
    def get_categories(self) -> List[CommandCategory]:
        """Get list of available categories."""
        return [cat for cat, commands in self._categories.items() if commands]
    
    def search_commands(self, query: str) -> List[Command]:
        """Search commands by name, description, or tags."""
        query = query.lower()
        matches = []
        
        for command in self._commands.values():
            # Check name
            if query in command.metadata.name.lower():
                matches.append(command)
                continue
            
            # Check description
            if query in command.metadata.description.lower():
                matches.append(command)
                continue
            
            # Check tags
            if any(query in tag.lower() for tag in command.metadata.tags):
                matches.append(command)
                continue
        
        return sorted(matches, key=lambda c: c.metadata.name)
    
    def get_command_help(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed help for a command."""
        command = self.get_command(name)
        if not command:
            return None
        
        return {
            "name": command.metadata.name,
            "description": command.metadata.description,
            "usage": command.get_usage_string(),
            "category": command.metadata.category.value,
            "arguments": [arg.to_dict() for arg in command.arguments],
            "options": [opt.to_dict() for opt in command.options],
            "examples": command.metadata.examples,
            "see_also": command.metadata.see_also,
            "status": command.status.value,
            "permission_level": command.permission_level.value
        }
    
    async def execute_command(
        self,
        name: str,
        arguments: List[str],
        options: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        user_roles: Optional[Set[str]] = None
    ) -> Any:
        """
        Execute a command.
        
        Args:
            name: Command name or alias
            arguments: Command arguments
            options: Command options
            context: Execution context
            user_id: User ID for permission checking
            user_roles: User roles for permission checking
            
        Returns:
            Command execution result
        """
        command = self.get_command(name)
        if not command:
            raise ValidationError("command", name, "Command not found")
        
        # Check permissions
        if not command.can_execute(user_id, user_roles):
            raise ValidationError("permission", name, "Insufficient permissions to execute command")
        
        # Check rate limits
        if not command.check_rate_limit():
            raise ValidationError("rate_limit", name, "Command rate limit exceeded")
        
        # Validate arguments
        try:
            validated_params = command.validate_arguments(arguments, options)
        except ValidationError as e:
            logger.warning(
                "command_validation_failed",
                command=name,
                error=str(e)
            )
            raise
        
        # Add context to parameters
        if context:
            validated_params["context"] = context
        
        # Record execution
        command.record_execution()
        
        try:
            # Execute command
            start_time = datetime.utcnow()
            
            if command.metadata.async_command:
                if command.metadata.timeout:
                    result = await asyncio.wait_for(
                        command.handler(**validated_params),
                        timeout=command.metadata.timeout
                    )
                else:
                    result = await command.handler(**validated_params)
            else:
                result = command.handler(**validated_params)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Log successful execution
            logger.info(
                "command_executed",
                command=name,
                execution_time=execution_time,
                user_id=user_id
            )
            
            # Emit execution event
            await self._emit_execution_event(command, validated_params, result, execution_time)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("command_timeout", command=name, timeout=command.metadata.timeout)
            raise SystemError(f"Command '{name}' timed out after {command.metadata.timeout}s")
        except Exception as e:
            logger.error(
                "command_execution_failed",
                command=name,
                error=str(e),
                exc_info=True
            )
            raise SystemError(f"Command '{name}' execution failed: {e}") from e
    
    def _extract_signature(self, handler: Callable) -> tuple[List[CommandArgument], List[CommandOption]]:
        """Extract arguments and options from handler signature."""
        arguments = []
        options = []
        
        sig = inspect.signature(handler)
        
        for param_name, param in sig.parameters.items():
            # Skip context parameter
            if param_name == 'context':
                continue
            
            # Determine if it's an option (has default) or argument
            if param.default != inspect.Parameter.empty:
                # It's an option
                option = CommandOption(
                    name=param_name,
                    description=f"Option: {param_name}",
                    type=param.annotation if param.annotation != inspect.Parameter.empty else type(param.default),
                    default=param.default
                )
                options.append(option)
            else:
                # It's an argument
                argument = CommandArgument(
                    name=param_name,
                    description=f"Argument: {param_name}",
                    type=param.annotation if param.annotation != inspect.Parameter.empty else str,
                    required=True
                )
                arguments.append(argument)
        
        return arguments, options
    
    async def _emit_registration_event(self, command: Command) -> None:
        """Emit command registration event."""
        await emit(
            "command_registered",
            EventCategory.SYSTEM,
            {
                "command_name": command.metadata.name,
                "category": command.metadata.category.value,
                "description": command.metadata.description
            },
            priority=EventPriority.LOW
        )
    
    async def _emit_execution_event(
        self,
        command: Command,
        parameters: Dict[str, Any],
        result: Any,
        execution_time: float
    ) -> None:
        """Emit command execution event."""
        await emit(
            "command_executed",
            EventCategory.SYSTEM,
            {
                "command_name": command.metadata.name,
                "category": command.metadata.category.value,
                "execution_time": execution_time,
                "parameters": parameters,
                "success": True
            },
            priority=EventPriority.LOW
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_commands = len(self._commands)
        by_category = {cat.value: len(cmds) for cat, cmds in self._categories.items() if cmds}
        by_status = {}
        
        for status in CommandStatus:
            count = sum(1 for cmd in self._commands.values() if cmd.status == status)
            if count > 0:
                by_status[status.value] = count
        
        return {
            "total_commands": total_commands,
            "total_aliases": len(self._aliases),
            "by_category": by_category,
            "by_status": by_status,
            "most_used": sorted(
                self._commands.values(),
                key=lambda c: c.usage_count,
                reverse=True
            )[:5]
        }


# Export public API
__all__ = [
    'CommandRegistry',
    'Command',
    'CommandMetadata',
    'CommandArgument',
    'CommandOption',
    'CommandCategory',
    'CommandStatus',
    'PermissionLevel'
]