"""Hook template support"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .config import HookConfig, HookTrigger, HookAction, HookActionType, HookCondition
from ..utils.logging import get_logger
from ..utils.errors import ValidationError

logger = get_logger(__name__)


@dataclass
class HookTemplate:
    """Template for creating hooks
    
    Templates provide reusable patterns for common hook configurations.
    """
    name: str
    description: str
    category: str
    
    # Template configuration
    triggers: List[HookTrigger]
    action_templates: List[Dict[str, Any]]
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Variable definitions
    variables: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Metadata
    author: str = "system"
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    
    def create_hook(
        self,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> HookConfig:
        """Create hook from template
        
        Args:
            name: Name for the new hook
            variables: Variable values
            overrides: Configuration overrides
            
        Returns:
            Hook configuration
        """
        # Validate variables
        variables = variables or {}
        self._validate_variables(variables)
        
        # Apply defaults
        for var_name, var_def in self.variables.items():
            if var_name not in variables and "default" in var_def:
                variables[var_name] = var_def["default"]
                
        # Create actions from templates
        actions = []
        for action_template in self.action_templates:
            action = self._create_action(action_template, variables)
            actions.append(action)
            
        # Build hook config
        config = {
            "name": name,
            "description": self._substitute_variables(self.description, variables),
            "triggers": self.triggers,
            "actions": actions,
            **self.default_config
        }
        
        # Apply overrides
        if overrides:
            config.update(overrides)
            
        return HookConfig(**config)
        
    def _validate_variables(self, variables: Dict[str, Any]) -> None:
        """Validate provided variables"""
        for var_name, var_def in self.variables.items():
            # Check required variables
            if var_def.get("required", False) and var_name not in variables:
                raise ValidationError(
                    "variable",
                    var_name,
                    f"Required variable '{var_name}' not provided"
                )
                
            # Check type
            if var_name in variables and "type" in var_def:
                expected_type = var_def["type"]
                value = variables[var_name]
                
                if expected_type == "string" and not isinstance(value, str):
                    raise ValidationError(
                        "variable",
                        var_name,
                        f"Expected string, got {type(value).__name__}"
                    )
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    raise ValidationError(
                        "variable",
                        var_name,
                        f"Expected number, got {type(value).__name__}"
                    )
                elif expected_type == "boolean" and not isinstance(value, bool):
                    raise ValidationError(
                        "variable",
                        var_name,
                        f"Expected boolean, got {type(value).__name__}"
                    )
                    
    def _create_action(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> HookAction:
        """Create action from template"""
        # Substitute variables in all string fields
        action_data = {}
        for key, value in template.items():
            if isinstance(value, str):
                action_data[key] = self._substitute_variables(value, variables)
            elif isinstance(value, dict):
                action_data[key] = self._substitute_dict(value, variables)
            else:
                action_data[key] = value
                
        # Create action
        return HookAction(
            type=HookActionType(action_data["type"]),
            config=action_data.get("config", {}),
            command=action_data.get("command"),
            script_path=Path(action_data["script_path"]) if action_data.get("script_path") else None,
            url=action_data.get("url"),
            function_name=action_data.get("function_name"),
            template=action_data.get("template")
        )
        
    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in text"""
        for var_name, value in variables.items():
            text = text.replace(f"${{{var_name}}}", str(value))
        return text
        
    def _substitute_dict(self, d: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively substitute variables in dictionary"""
        result = {}
        for key, value in d.items():
            if isinstance(value, str):
                result[key] = self._substitute_variables(value, variables)
            elif isinstance(value, dict):
                result[key] = self._substitute_dict(value, variables)
            else:
                result[key] = value
        return result
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "triggers": [t.value for t in self.triggers],
            "action_templates": self.action_templates,
            "default_config": self.default_config,
            "variables": self.variables,
            "author": self.author,
            "version": self.version,
            "tags": self.tags
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HookTemplate':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            description=data["description"],
            category=data["category"],
            triggers=[HookTrigger(t) for t in data["triggers"]],
            action_templates=data["action_templates"],
            default_config=data.get("default_config", {}),
            variables=data.get("variables", {}),
            author=data.get("author", "system"),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", [])
        )


class TemplateManager:
    """Manager for hook templates"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize template manager
        
        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = templates_dir
        self._templates: Dict[str, HookTemplate] = {}
        
        # Load built-in templates
        self._load_builtin_templates()
        
    def _load_builtin_templates(self) -> None:
        """Load built-in templates"""
        # Git commit hook
        self._templates["git_commit"] = HookTemplate(
            name="git_commit",
            description="Run actions on git commit",
            category="vcs",
            triggers=[HookTrigger.CUSTOM],
            action_templates=[
                {
                    "type": "command",
                    "command": "git add -A && git commit -m '${message}'",
                    "template": "Commit message: ${message}"
                }
            ],
            variables={
                "message": {
                    "type": "string",
                    "required": True,
                    "description": "Commit message"
                }
            }
        )
        
        # Code formatting hook
        self._templates["code_format"] = HookTemplate(
            name="code_format",
            description="Format code on file save",
            category="development",
            triggers=[HookTrigger.FILE_MODIFY],
            action_templates=[
                {
                    "type": "command",
                    "command": "${formatter} ${file_path}",
                    "config": {
                        "condition": {
                            "field": "file_path",
                            "operator": "regex",
                            "value": "${file_pattern}"
                        }
                    }
                }
            ],
            variables={
                "formatter": {
                    "type": "string",
                    "required": True,
                    "description": "Formatter command (e.g., black, prettier)"
                },
                "file_pattern": {
                    "type": "string",
                    "default": ".*\\.(py|js|ts)$",
                    "description": "File pattern to match"
                }
            },
            default_config={
                "priority": 10,
                "timeout": 30.0
            }
        )
        
        # Test runner hook
        self._templates["test_runner"] = HookTemplate(
            name="test_runner",
            description="Run tests on code changes",
            category="testing",
            triggers=[HookTrigger.FILE_MODIFY, HookTrigger.CHECKPOINT_CREATE],
            action_templates=[
                {
                    "type": "command",
                    "command": "${test_command}",
                    "config": {
                        "working_dir": "${project_root}"
                    }
                },
                {
                    "type": "notification",
                    "config": {
                        "title": "Test Results",
                        "message": "Tests completed for ${file_path}",
                        "type": "info"
                    }
                }
            ],
            variables={
                "test_command": {
                    "type": "string",
                    "required": True,
                    "description": "Test command (e.g., pytest, npm test)"
                },
                "project_root": {
                    "type": "string",
                    "default": ".",
                    "description": "Project root directory"
                }
            }
        )
        
        # Deployment hook
        self._templates["deployment"] = HookTemplate(
            name="deployment",
            description="Deploy application on tag",
            category="deployment",
            triggers=[HookTrigger.CUSTOM],
            action_templates=[
                {
                    "type": "script",
                    "script_path": "${deploy_script}",
                    "config": {
                        "environment": {
                            "DEPLOY_ENV": "${environment}",
                            "DEPLOY_TAG": "${tag}"
                        }
                    }
                },
                {
                    "type": "webhook",
                    "url": "${notification_url}",
                    "config": {
                        "method": "POST",
                        "headers": {
                            "Content-Type": "application/json"
                        }
                    }
                }
            ],
            variables={
                "deploy_script": {
                    "type": "string",
                    "required": True,
                    "description": "Path to deployment script"
                },
                "environment": {
                    "type": "string",
                    "required": True,
                    "description": "Deployment environment (e.g., staging, production)"
                },
                "tag": {
                    "type": "string",
                    "required": True,
                    "description": "Deployment tag/version"
                },
                "notification_url": {
                    "type": "string",
                    "default": "",
                    "description": "Webhook URL for notifications"
                }
            },
            default_config={
                "timeout": 300.0,
                "retry_count": 2,
                "async_execution": True
            }
        )
        
        # Backup hook
        self._templates["backup"] = HookTemplate(
            name="backup",
            description="Create backup on checkpoint",
            category="backup",
            triggers=[HookTrigger.CHECKPOINT_CREATE],
            action_templates=[
                {
                    "type": "command",
                    "command": "tar -czf ${backup_dir}/backup-${timestamp}.tar.gz ${source_dir}",
                    "template": "Creating backup of ${source_dir}"
                },
                {
                    "type": "log",
                    "config": {
                        "level": "info",
                        "message": "Backup created: ${backup_dir}/backup-${timestamp}.tar.gz"
                    }
                }
            ],
            variables={
                "source_dir": {
                    "type": "string",
                    "required": True,
                    "description": "Directory to backup"
                },
                "backup_dir": {
                    "type": "string",
                    "required": True,
                    "description": "Backup destination directory"
                },
                "timestamp": {
                    "type": "string",
                    "default": "${context.timestamp}",
                    "description": "Timestamp for backup filename"
                }
            }
        )
        
    async def initialize(self) -> None:
        """Initialize template manager"""
        if self.templates_dir:
            await self.load_templates_from_directory(self.templates_dir)
            
        logger.info(
            "template_manager_initialized",
            template_count=len(self._templates),
            categories=list(set(t.category for t in self._templates.values()))
        )
        
    async def load_templates_from_directory(self, directory: Path) -> int:
        """Load templates from directory
        
        Args:
            directory: Directory containing template JSON files
            
        Returns:
            Number of templates loaded
        """
        if not directory.exists():
            return 0
            
        loaded = 0
        
        for template_file in directory.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    data = json.load(f)
                    
                template = HookTemplate.from_dict(data)
                self._templates[template.name] = template
                loaded += 1
                
            except Exception as e:
                logger.error(f"Failed to load template from {template_file}: {e}")
                
        logger.info(
            "templates_loaded_from_directory",
            directory=str(directory),
            loaded=loaded
        )
        
        return loaded
        
    def get_template(self, name: str) -> Optional[HookTemplate]:
        """Get template by name"""
        return self._templates.get(name)
        
    def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[HookTemplate]:
        """List available templates
        
        Args:
            category: Filter by category
            tags: Filter by tags
            
        Returns:
            List of templates
        """
        templates = list(self._templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
            
        if tags:
            tag_set = set(tags)
            templates = [t for t in templates if tag_set.intersection(t.tags)]
            
        return templates
        
    def get_categories(self) -> List[str]:
        """Get all template categories"""
        return sorted(list(set(t.category for t in self._templates.values())))
        
    def create_hook_from_template(
        self,
        template_name: str,
        hook_name: str,
        variables: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> HookConfig:
        """Create hook from template
        
        Args:
            template_name: Template to use
            hook_name: Name for the new hook
            variables: Template variables
            overrides: Configuration overrides
            
        Returns:
            Hook configuration
        """
        template = self.get_template(template_name)
        if not template:
            raise ValidationError(
                "template_name",
                template_name,
                "Template not found"
            )
            
        return template.create_hook(hook_name, variables, overrides)
        
    def export_template(
        self,
        template: HookTemplate,
        path: Path
    ) -> None:
        """Export template to file
        
        Args:
            template: Template to export
            path: Export path
        """
        with open(path, 'w') as f:
            json.dump(template.to_dict(), f, indent=2)
            
        logger.info(
            "template_exported",
            name=template.name,
            path=str(path)
        )