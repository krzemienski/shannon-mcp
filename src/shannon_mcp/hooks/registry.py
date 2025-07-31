"""Hook registry for managing hooks"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
from datetime import datetime
from collections import defaultdict

from .config import HookConfig, HookTrigger
from ..utils.logging import get_logger
from ..utils.errors import ValidationError, StorageError

logger = get_logger(__name__)


class HookRegistry:
    """Registry for managing hooks
    
    Features:
    - Hook registration and discovery
    - Priority-based ordering
    - Trigger indexing for fast lookup
    - Rate limiting tracking
    - Hot reload support
    """
    
    def __init__(self, hooks_dir: Optional[Path] = None):
        """Initialize hook registry
        
        Args:
            hooks_dir: Directory to scan for hook configurations
        """
        self.hooks_dir = hooks_dir
        
        # Hook storage
        self._hooks: Dict[str, HookConfig] = {}
        self._hooks_lock = asyncio.Lock()
        
        # Trigger index for fast lookup
        self._trigger_index: Dict[HookTrigger, Set[str]] = defaultdict(set)
        
        # Rate limiting tracking
        self._execution_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._last_execution: Dict[str, datetime] = {}
        
        # File watching
        self._file_mtimes: Dict[Path, float] = {}
        
    async def initialize(self) -> None:
        """Initialize registry"""
        if self.hooks_dir:
            await self.scan_directory(self.hooks_dir)
            
        logger.info(
            "hook_registry_initialized",
            hooks_count=len(self._hooks),
            hooks_dir=str(self.hooks_dir) if self.hooks_dir else None
        )
        
    async def register(self, hook: HookConfig) -> None:
        """Register a hook
        
        Args:
            hook: Hook configuration to register
        """
        # Validate hook
        hook.validate()
        
        async with self._hooks_lock:
            # Check for duplicate name
            if hook.name in self._hooks:
                raise ValidationError("name", hook.name, "Hook name already registered")
                
            # Add to registry
            self._hooks[hook.name] = hook
            
            # Update trigger index
            for trigger in hook.triggers:
                self._trigger_index[trigger].add(hook.name)
                
        logger.info(
            "hook_registered",
            name=hook.name,
            triggers=[t.value for t in hook.triggers],
            priority=hook.priority
        )
        
    async def unregister(self, name: str) -> bool:
        """Unregister a hook
        
        Args:
            name: Hook name to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        async with self._hooks_lock:
            hook = self._hooks.pop(name, None)
            if not hook:
                return False
                
            # Remove from trigger index
            for trigger in hook.triggers:
                self._trigger_index[trigger].discard(name)
                if not self._trigger_index[trigger]:
                    del self._trigger_index[trigger]
                    
        logger.info("hook_unregistered", name=name)
        return True
        
    async def get_hook(self, name: str) -> Optional[HookConfig]:
        """Get hook by name"""
        async with self._hooks_lock:
            return self._hooks.get(name)
            
    async def list_hooks(
        self,
        trigger: Optional[HookTrigger] = None,
        enabled_only: bool = True,
        tags: Optional[List[str]] = None
    ) -> List[HookConfig]:
        """List hooks with filtering
        
        Args:
            trigger: Filter by trigger type
            enabled_only: Only return enabled hooks
            tags: Filter by tags
            
        Returns:
            List of matching hooks
        """
        async with self._hooks_lock:
            hooks = list(self._hooks.values())
            
        # Apply filters
        if trigger:
            hooks = [h for h in hooks if h.matches_trigger(trigger)]
            
        if enabled_only:
            hooks = [h for h in hooks if h.enabled]
            
        if tags:
            tag_set = set(tags)
            hooks = [h for h in hooks if tag_set.intersection(h.tags)]
            
        # Sort by priority (higher first)
        hooks.sort(key=lambda h: h.priority, reverse=True)
        
        return hooks
        
    async def get_hooks_for_trigger(
        self,
        trigger: Union[HookTrigger, str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[HookConfig]:
        """Get all hooks that match a trigger
        
        Args:
            trigger: Trigger to match
            context: Optional context for condition evaluation
            
        Returns:
            List of matching hooks ordered by priority
        """
        if isinstance(trigger, str):
            trigger = HookTrigger(trigger)
            
        # Get hook names from trigger index
        async with self._hooks_lock:
            hook_names = self._trigger_index.get(trigger, set()).copy()
            
            # Add hooks with CUSTOM trigger
            if trigger != HookTrigger.CUSTOM:
                hook_names.update(self._trigger_index.get(HookTrigger.CUSTOM, set()))
                
        # Get enabled hooks
        hooks = []
        for name in hook_names:
            hook = await self.get_hook(name)
            if hook and hook.enabled:
                # Evaluate conditions if context provided
                if context is None or hook.evaluate_conditions(context):
                    hooks.append(hook)
                    
        # Sort by priority (higher first)
        hooks.sort(key=lambda h: h.priority, reverse=True)
        
        return hooks
        
    async def enable_hook(self, name: str) -> bool:
        """Enable a hook"""
        async with self._hooks_lock:
            hook = self._hooks.get(name)
            if not hook:
                return False
                
            hook.enabled = True
            hook.updated_at = datetime.utcnow()
            
        logger.info("hook_enabled", name=name)
        return True
        
    async def disable_hook(self, name: str) -> bool:
        """Disable a hook"""
        async with self._hooks_lock:
            hook = self._hooks.get(name)
            if not hook:
                return False
                
            hook.enabled = False
            hook.updated_at = datetime.utcnow()
            
        logger.info("hook_disabled", name=name)
        return True
        
    async def update_hook(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update hook configuration
        
        Args:
            name: Hook name
            updates: Fields to update
            
        Returns:
            True if updated
        """
        async with self._hooks_lock:
            hook = self._hooks.get(name)
            if not hook:
                return False
                
            # Update allowed fields
            allowed_fields = {
                "description", "enabled", "priority", "timeout",
                "retry_count", "retry_delay", "rate_limit", "cooldown",
                "tags", "environment"
            }
            
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(hook, field, value)
                    
            hook.updated_at = datetime.utcnow()
            
        logger.info("hook_updated", name=name, updates=list(updates.keys()))
        return True
        
    def check_rate_limit(self, hook: HookConfig) -> bool:
        """Check if hook execution is within rate limits
        
        Args:
            hook: Hook to check
            
        Returns:
            True if within limits
        """
        # Check cooldown
        if hook.cooldown:
            last_exec = self._last_execution.get(hook.name)
            if last_exec:
                elapsed = (datetime.utcnow() - last_exec).total_seconds()
                if elapsed < hook.cooldown:
                    return False
                    
        # Check rate limit
        if hook.rate_limit:
            # Clean old executions
            now = datetime.utcnow()
            executions = self._execution_counts[hook.name]
            executions = [
                e for e in executions
                if (now - e).total_seconds() < 60  # Within last minute
            ]
            self._execution_counts[hook.name] = executions
            
            if len(executions) >= hook.rate_limit:
                return False
                
        return True
        
    def record_execution(self, hook: HookConfig) -> None:
        """Record hook execution for rate limiting"""
        now = datetime.utcnow()
        self._last_execution[hook.name] = now
        self._execution_counts[hook.name].append(now)
        
    async def scan_directory(self, directory: Path) -> int:
        """Scan directory for hook configurations
        
        Args:
            directory: Directory to scan
            
        Returns:
            Number of hooks loaded
        """
        if not directory.exists():
            return 0
            
        loaded = 0
        
        for hook_file in directory.glob("*.json"):
            try:
                # Check if file has been modified
                mtime = hook_file.stat().st_mtime
                if hook_file in self._file_mtimes and self._file_mtimes[hook_file] == mtime:
                    continue  # Skip unchanged files
                    
                # Load hook configuration
                hook = HookConfig.from_file(hook_file)
                
                # Register or update
                existing = await self.get_hook(hook.name)
                if existing:
                    await self.unregister(hook.name)
                    
                await self.register(hook)
                self._file_mtimes[hook_file] = mtime
                loaded += 1
                
            except Exception as e:
                logger.error(f"Failed to load hook from {hook_file}: {e}")
                
        logger.info(
            "hooks_loaded_from_directory",
            directory=str(directory),
            loaded=loaded
        )
        
        return loaded
        
    async def reload(self) -> int:
        """Reload hooks from directory
        
        Returns:
            Number of hooks reloaded
        """
        if not self.hooks_dir:
            return 0
            
        return await self.scan_directory(self.hooks_dir)
        
    async def save_hook(self, hook: HookConfig, directory: Optional[Path] = None) -> Path:
        """Save hook to file
        
        Args:
            hook: Hook to save
            directory: Directory to save to (defaults to hooks_dir)
            
        Returns:
            Path to saved file
        """
        directory = directory or self.hooks_dir
        if not directory:
            raise StorageError("No directory specified for saving hook")
            
        directory.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = f"{hook.name.replace(' ', '_').lower()}.json"
        filepath = directory / filename
        
        # Save hook
        hook.save_to_file(filepath)
        
        # Update file mtime tracking
        self._file_mtimes[filepath] = filepath.stat().st_mtime
        
        logger.info("hook_saved", name=hook.name, path=str(filepath))
        return filepath
        
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        trigger_counts = {}
        for trigger, hooks in self._trigger_index.items():
            trigger_counts[trigger.value] = len(hooks)
            
        return {
            "total_hooks": len(self._hooks),
            "enabled_hooks": sum(1 for h in self._hooks.values() if h.enabled),
            "trigger_counts": trigger_counts,
            "hooks_with_rate_limits": sum(
                1 for h in self._hooks.values()
                if h.rate_limit or h.cooldown
            )
        }