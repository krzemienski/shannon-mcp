"""Hook configuration schema and definitions"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Set
from datetime import datetime
from dataclasses import dataclass, field

from ..utils.logging import get_logger
from ..utils.errors import ValidationError

logger = get_logger(__name__)


class HookTrigger(str, Enum):
    """Hook trigger types"""
    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_ERROR = "session_error"
    
    # Checkpoint events
    CHECKPOINT_CREATE = "checkpoint_create"
    CHECKPOINT_RESTORE = "checkpoint_restore"
    CHECKPOINT_DELETE = "checkpoint_delete"
    
    # File operations
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    FILE_READ = "file_read"
    
    # Agent events
    AGENT_SPAWN = "agent_spawn"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    
    # Message events
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    NOTIFICATION = "notification"
    
    # Custom events
    CUSTOM = "custom"


class HookActionType(str, Enum):
    """Hook action types"""
    COMMAND = "command"  # Execute shell command
    SCRIPT = "script"    # Run script file
    WEBHOOK = "webhook"  # Call webhook URL
    FUNCTION = "function"  # Call Python function
    NOTIFICATION = "notification"  # Send notification
    LOG = "log"  # Log message
    TRANSFORM = "transform"  # Transform data


@dataclass
class HookCondition:
    """Condition for hook execution"""
    field: str  # Field to check
    operator: str  # Comparison operator (eq, ne, gt, lt, contains, regex)
    value: Any  # Value to compare
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context"""
        field_value = self._get_field_value(context, self.field)
        
        if self.operator == "eq":
            return field_value == self.value
        elif self.operator == "ne":
            return field_value != self.value
        elif self.operator == "gt":
            return field_value > self.value
        elif self.operator == "lt":
            return field_value < self.value
        elif self.operator == "contains":
            return self.value in str(field_value)
        elif self.operator == "regex":
            import re
            return bool(re.match(self.value, str(field_value)))
        else:
            raise ValidationError("operator", self.operator, "Invalid operator")
            
    def _get_field_value(self, context: Dict[str, Any], field: str) -> Any:
        """Get nested field value from context"""
        parts = field.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
                
        return value


@dataclass
class HookAction:
    """Action to execute when hook triggers"""
    type: HookActionType
    config: Dict[str, Any]
    
    # Action-specific fields
    command: Optional[str] = None  # For COMMAND type
    script_path: Optional[Path] = None  # For SCRIPT type
    url: Optional[str] = None  # For WEBHOOK type
    function_name: Optional[str] = None  # For FUNCTION type
    template: Optional[str] = None  # Template string
    
    def validate(self) -> None:
        """Validate action configuration"""
        if self.type == HookActionType.COMMAND:
            if not self.command:
                raise ValidationError("command", None, "Command required for COMMAND action")
                
        elif self.type == HookActionType.SCRIPT:
            if not self.script_path:
                raise ValidationError("script_path", None, "Script path required for SCRIPT action")
            if not self.script_path.exists():
                raise ValidationError("script_path", str(self.script_path), "Script file not found")
                
        elif self.type == HookActionType.WEBHOOK:
            if not self.url:
                raise ValidationError("url", None, "URL required for WEBHOOK action")
                
        elif self.type == HookActionType.FUNCTION:
            if not self.function_name:
                raise ValidationError("function_name", None, "Function name required for FUNCTION action")


@dataclass
class HookConfig:
    """Hook configuration"""
    name: str
    description: str
    triggers: List[HookTrigger]
    actions: List[HookAction]
    enabled: bool = True
    priority: int = 0  # Higher priority executes first
    conditions: List[HookCondition] = field(default_factory=list)
    
    # Execution settings
    async_execution: bool = False
    timeout: Optional[float] = None  # Seconds
    retry_count: int = 0
    retry_delay: float = 1.0  # Seconds
    
    # Security settings
    sandbox: bool = True  # Execute in sandbox
    allowed_paths: List[Path] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    
    # Rate limiting
    rate_limit: Optional[int] = None  # Max executions per minute
    cooldown: Optional[float] = None  # Seconds between executions
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    
    def validate(self) -> None:
        """Validate hook configuration"""
        if not self.name:
            raise ValidationError("name", self.name, "Hook name required")
            
        if not self.triggers:
            raise ValidationError("triggers", self.triggers, "At least one trigger required")
            
        if not self.actions:
            raise ValidationError("actions", self.actions, "At least one action required")
            
        # Validate actions
        for action in self.actions:
            action.validate()
            
    def matches_trigger(self, trigger: Union[HookTrigger, str]) -> bool:
        """Check if hook matches trigger"""
        if isinstance(trigger, str):
            trigger = HookTrigger(trigger)
            
        return trigger in self.triggers or HookTrigger.CUSTOM in self.triggers
        
    def evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """Evaluate all conditions"""
        if not self.conditions:
            return True
            
        return all(condition.evaluate(context) for condition in self.conditions)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "triggers": [t.value for t in self.triggers],
            "actions": [
                {
                    "type": a.type.value,
                    "config": a.config,
                    "command": a.command,
                    "script_path": str(a.script_path) if a.script_path else None,
                    "url": a.url,
                    "function_name": a.function_name,
                    "template": a.template
                }
                for a in self.actions
            ],
            "enabled": self.enabled,
            "priority": self.priority,
            "conditions": [
                {
                    "field": c.field,
                    "operator": c.operator,
                    "value": c.value
                }
                for c in self.conditions
            ],
            "async_execution": self.async_execution,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "sandbox": self.sandbox,
            "allowed_paths": [str(p) for p in self.allowed_paths],
            "environment": self.environment,
            "rate_limit": self.rate_limit,
            "cooldown": self.cooldown,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HookConfig':
        """Create from dictionary"""
        # Parse triggers
        triggers = [HookTrigger(t) for t in data.get("triggers", [])]
        
        # Parse actions
        actions = []
        for action_data in data.get("actions", []):
            action = HookAction(
                type=HookActionType(action_data["type"]),
                config=action_data.get("config", {}),
                command=action_data.get("command"),
                script_path=Path(action_data["script_path"]) if action_data.get("script_path") else None,
                url=action_data.get("url"),
                function_name=action_data.get("function_name"),
                template=action_data.get("template")
            )
            actions.append(action)
            
        # Parse conditions
        conditions = []
        for cond_data in data.get("conditions", []):
            condition = HookCondition(
                field=cond_data["field"],
                operator=cond_data["operator"],
                value=cond_data["value"]
            )
            conditions.append(condition)
            
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            triggers=triggers,
            actions=actions,
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            conditions=conditions,
            async_execution=data.get("async_execution", False),
            timeout=data.get("timeout"),
            retry_count=data.get("retry_count", 0),
            retry_delay=data.get("retry_delay", 1.0),
            sandbox=data.get("sandbox", True),
            allowed_paths=[Path(p) for p in data.get("allowed_paths", [])],
            environment=data.get("environment", {}),
            rate_limit=data.get("rate_limit"),
            cooldown=data.get("cooldown"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            tags=data.get("tags", [])
        )
        
    @classmethod
    def from_file(cls, path: Path) -> 'HookConfig':
        """Load from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)
            
        return cls.from_dict(data)
        
    def save_to_file(self, path: Path) -> None:
        """Save to JSON file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)