"""Hooks Framework for Shannon MCP

This module provides an extensible hooks system for:
- Pre/post operation hooks
- Event-driven automation
- Custom hook development
- Security sandboxing
- Template support
"""

from .config import HookConfig, HookTrigger, HookAction
from .registry import HookRegistry
from .engine import HookEngine
from .templates import HookTemplate, TemplateManager
from .sandbox import HookSandbox

__all__ = [
    "HookConfig",
    "HookTrigger", 
    "HookAction",
    "HookRegistry",
    "HookEngine",
    "HookTemplate",
    "TemplateManager",
    "HookSandbox"
]