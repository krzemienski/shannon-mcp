"""Hook execution engine"""

import asyncio
import subprocess
import aiohttp
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime
from string import Template
import traceback

from .config import HookConfig, HookAction, HookActionType, HookTrigger
from .registry import HookRegistry
from .sandbox import HookSandbox
from ..utils.logging import get_logger
from ..utils.errors import HookExecutionError
from ..utils.notifications import NotificationCenter, NotificationType

logger = get_logger(__name__)


class HookExecutionResult:
    """Result of hook execution"""
    
    def __init__(
        self,
        hook_name: str,
        success: bool,
        output: Optional[Any] = None,
        error: Optional[str] = None,
        duration: float = 0.0
    ):
        self.hook_name = hook_name
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration
        self.timestamp = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hook_name": self.hook_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat()
        }


class HookEngine:
    """Engine for executing hooks
    
    Features:
    - Multiple action type support
    - Async and sync execution
    - Retry logic
    - Timeout handling
    - Sandboxed execution
    - Template variable substitution
    """
    
    def __init__(
        self,
        registry: HookRegistry,
        notification_center: Optional[NotificationCenter] = None,
        custom_functions: Optional[Dict[str, Callable]] = None
    ):
        """Initialize hook engine
        
        Args:
            registry: Hook registry
            notification_center: Optional notification center
            custom_functions: Custom functions for FUNCTION action type
        """
        self.registry = registry
        self.notification_center = notification_center or NotificationCenter()
        self.custom_functions = custom_functions or {}
        
        # Execution tracking
        self._running_hooks: Set[str] = set()
        self._execution_history: List[HookExecutionResult] = []
        self._max_history = 1000
        
        # Sandbox for secure execution
        self.sandbox = HookSandbox()
        
    async def initialize(self) -> None:
        """Initialize engine"""
        await self.sandbox.initialize()
        
        logger.info(
            "hook_engine_initialized",
            custom_functions=list(self.custom_functions.keys())
        )
        
    async def trigger(
        self,
        trigger: Union[HookTrigger, str],
        context: Dict[str, Any]
    ) -> List[HookExecutionResult]:
        """Trigger hooks for an event
        
        Args:
            trigger: Trigger type
            context: Execution context
            
        Returns:
            List of execution results
        """
        # Get matching hooks
        hooks = await self.registry.get_hooks_for_trigger(trigger, context)
        
        if not hooks:
            logger.debug(f"No hooks found for trigger: {trigger}")
            return []
            
        logger.info(
            "hooks_triggered",
            trigger=trigger.value if isinstance(trigger, HookTrigger) else trigger,
            hook_count=len(hooks),
            hooks=[h.name for h in hooks]
        )
        
        # Execute hooks
        results = []
        tasks = []
        
        for hook in hooks:
            # Check rate limits
            if not self.registry.check_rate_limit(hook):
                logger.warning(
                    "hook_rate_limited",
                    name=hook.name,
                    trigger=trigger
                )
                continue
                
            # Record execution
            self.registry.record_execution(hook)
            
            # Execute hook
            if hook.async_execution:
                # Execute asynchronously
                task = asyncio.create_task(self._execute_hook(hook, context))
                tasks.append(task)
            else:
                # Execute synchronously
                result = await self._execute_hook(hook, context)
                results.append(result)
                
        # Wait for async tasks
        if tasks:
            async_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in async_results:
                if isinstance(result, Exception):
                    logger.error(f"Async hook execution failed: {result}")
                else:
                    results.append(result)
                    
        return results
        
    async def execute_hook(
        self,
        hook_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> HookExecutionResult:
        """Execute a specific hook
        
        Args:
            hook_name: Hook name to execute
            context: Optional execution context
            
        Returns:
            Execution result
        """
        hook = await self.registry.get_hook(hook_name)
        if not hook:
            return HookExecutionResult(
                hook_name=hook_name,
                success=False,
                error=f"Hook not found: {hook_name}"
            )
            
        return await self._execute_hook(hook, context or {})
        
    async def _execute_hook(
        self,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> HookExecutionResult:
        """Execute a hook with retry logic
        
        Args:
            hook: Hook to execute
            context: Execution context
            
        Returns:
            Execution result
        """
        # Check if already running
        if hook.name in self._running_hooks:
            return HookExecutionResult(
                hook_name=hook.name,
                success=False,
                error="Hook already running"
            )
            
        self._running_hooks.add(hook.name)
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Execute with retries
            last_error = None
            for attempt in range(hook.retry_count + 1):
                if attempt > 0:
                    await asyncio.sleep(hook.retry_delay)
                    logger.info(f"Retrying hook {hook.name} (attempt {attempt + 1})")
                    
                try:
                    # Execute all actions
                    outputs = []
                    for action in hook.actions:
                        output = await self._execute_action(
                            action,
                            hook,
                            context
                        )
                        outputs.append(output)
                        
                    # Success
                    duration = asyncio.get_event_loop().time() - start_time
                    result = HookExecutionResult(
                        hook_name=hook.name,
                        success=True,
                        output=outputs,
                        duration=duration
                    )
                    
                    self._add_to_history(result)
                    
                    # Send notification
                    await self.notification_center.notify(
                        NotificationType.HOOK,
                        f"Hook executed: {hook.name}",
                        {
                            "hook_name": hook.name,
                            "success": True,
                            "duration": duration
                        }
                    )
                    
                    return result
                    
                except Exception as e:
                    last_error = str(e)
                    logger.error(
                        f"Hook execution failed: {hook.name}",
                        exc_info=True
                    )
                    
            # All retries failed
            duration = asyncio.get_event_loop().time() - start_time
            result = HookExecutionResult(
                hook_name=hook.name,
                success=False,
                error=last_error,
                duration=duration
            )
            
            self._add_to_history(result)
            
            # Send notification
            await self.notification_center.notify(
                NotificationType.ERROR,
                f"Hook failed: {hook.name}",
                {
                    "hook_name": hook.name,
                    "error": last_error,
                    "duration": duration
                }
            )
            
            return result
            
        finally:
            self._running_hooks.discard(hook.name)
            
    async def _execute_action(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Any:
        """Execute a single action
        
        Args:
            action: Action to execute
            hook: Parent hook configuration
            context: Execution context
            
        Returns:
            Action output
        """
        # Substitute template variables
        substituted_context = self._substitute_templates(action, context)
        
        # Execute based on type
        if action.type == HookActionType.COMMAND:
            return await self._execute_command(action, hook, substituted_context)
            
        elif action.type == HookActionType.SCRIPT:
            return await self._execute_script(action, hook, substituted_context)
            
        elif action.type == HookActionType.WEBHOOK:
            return await self._execute_webhook(action, hook, substituted_context)
            
        elif action.type == HookActionType.FUNCTION:
            return await self._execute_function(action, hook, substituted_context)
            
        elif action.type == HookActionType.NOTIFICATION:
            return await self._execute_notification(action, hook, substituted_context)
            
        elif action.type == HookActionType.LOG:
            return await self._execute_log(action, hook, substituted_context)
            
        elif action.type == HookActionType.TRANSFORM:
            return await self._execute_transform(action, hook, substituted_context)
            
        else:
            raise HookExecutionError(f"Unknown action type: {action.type}")
            
    async def _execute_command(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute shell command"""
        command = action.command
        if not command:
            raise HookExecutionError("No command specified")
            
        # Apply template substitution
        if action.template:
            template = Template(action.template)
            command = template.safe_substitute(**context)
            
        # Build environment
        env = os.environ.copy()
        env.update(hook.environment)
        
        # Execute command
        if hook.sandbox:
            result = await self.sandbox.execute_command(
                command,
                env=env,
                allowed_paths=hook.allowed_paths,
                timeout=hook.timeout
            )
        else:
            # Direct execution (less secure)
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=hook.timeout
                )
                
                result = {
                    "returncode": process.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else ""
                }
                
            except asyncio.TimeoutError:
                process.kill()
                raise HookExecutionError(f"Command timed out: {command}")
                
        if result["returncode"] != 0:
            raise HookExecutionError(
                f"Command failed: {command}\n{result['stderr']}"
            )
            
        return result
        
    async def _execute_script(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute script file"""
        if not action.script_path or not action.script_path.exists():
            raise HookExecutionError("Script file not found")
            
        # Determine interpreter
        extension = action.script_path.suffix.lower()
        if extension == ".py":
            interpreter = ["python"]
        elif extension == ".sh":
            interpreter = ["bash"]
        elif extension == ".js":
            interpreter = ["node"]
        else:
            interpreter = []  # Execute directly
            
        # Build command
        command = interpreter + [str(action.script_path)]
        
        # Build environment
        env = os.environ.copy()
        env.update(hook.environment)
        
        # Add context to environment as JSON
        env["HOOK_CONTEXT"] = json.dumps(context)
        
        # Execute script
        if hook.sandbox:
            result = await self.sandbox.execute_script(
                action.script_path,
                env=env,
                allowed_paths=hook.allowed_paths,
                timeout=hook.timeout
            )
        else:
            # Direct execution
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=hook.timeout
                )
                
                result = {
                    "returncode": process.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else ""
                }
                
            except asyncio.TimeoutError:
                process.kill()
                raise HookExecutionError(f"Script timed out: {action.script_path}")
                
        if result["returncode"] != 0:
            raise HookExecutionError(
                f"Script failed: {action.script_path}\n{result['stderr']}"
            )
            
        return result
        
    async def _execute_webhook(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute webhook call"""
        if not action.url:
            raise HookExecutionError("No webhook URL specified")
            
        # Apply template substitution
        url = action.url
        if action.template:
            template = Template(action.template)
            url = template.safe_substitute(**context)
            
        # Build request
        headers = action.config.get("headers", {})
        method = action.config.get("method", "POST").upper()
        
        # Build payload
        payload = {
            "hook_name": hook.name,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context
        }
        
        # Execute request
        timeout = aiohttp.ClientTimeout(total=hook.timeout)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        return await self._process_webhook_response(response)
                        
                elif method == "POST":
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers
                    ) as response:
                        return await self._process_webhook_response(response)
                        
                else:
                    raise HookExecutionError(f"Unsupported HTTP method: {method}")
                    
            except asyncio.TimeoutError:
                raise HookExecutionError(f"Webhook timed out: {url}")
            except Exception as e:
                raise HookExecutionError(f"Webhook failed: {url} - {e}")
                
    async def _process_webhook_response(
        self,
        response: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """Process webhook response"""
        text = await response.text()
        
        result = {
            "status_code": response.status,
            "headers": dict(response.headers),
            "body": text
        }
        
        # Try to parse JSON
        try:
            result["json"] = json.loads(text)
        except:
            pass
            
        if response.status >= 400:
            raise HookExecutionError(
                f"Webhook returned error: {response.status} - {text}"
            )
            
        return result
        
    async def _execute_function(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Any:
        """Execute custom function"""
        if not action.function_name:
            raise HookExecutionError("No function name specified")
            
        func = self.custom_functions.get(action.function_name)
        if not func:
            raise HookExecutionError(f"Function not found: {action.function_name}")
            
        # Execute function
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(hook, action, context)
            else:
                # Run sync function in executor
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    func,
                    hook,
                    action,
                    context
                )
        except Exception as e:
            raise HookExecutionError(f"Function failed: {action.function_name} - {e}")
            
    async def _execute_notification(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send notification"""
        # Get notification config
        title = action.config.get("title", f"Hook: {hook.name}")
        message = action.config.get("message", "Hook triggered")
        notification_type = action.config.get("type", NotificationType.INFO)
        
        # Apply template substitution
        if action.template:
            template = Template(action.template)
            message = template.safe_substitute(**context)
            
        # Send notification
        await self.notification_center.notify(
            notification_type,
            title,
            {
                "message": message,
                "hook_name": hook.name,
                "context": context
            }
        )
        
        return {
            "notification_sent": True,
            "title": title,
            "message": message
        }
        
    async def _execute_log(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Log message"""
        # Get log config
        level = action.config.get("level", "info").lower()
        message = action.config.get("message", f"Hook {hook.name} triggered")
        
        # Apply template substitution
        if action.template:
            template = Template(action.template)
            message = template.safe_substitute(**context)
            
        # Log message
        log_func = getattr(logger, level, logger.info)
        log_func(
            message,
            hook_name=hook.name,
            context=context
        )
        
        return {
            "logged": True,
            "level": level,
            "message": message
        }
        
    async def _execute_transform(
        self,
        action: HookAction,
        hook: HookConfig,
        context: Dict[str, Any]
    ) -> Any:
        """Transform data"""
        # Get transform config
        transform_type = action.config.get("type", "json")
        expression = action.config.get("expression")
        
        if not expression:
            raise HookExecutionError("No transform expression specified")
            
        # Apply template substitution
        if action.template:
            template = Template(action.template)
            expression = template.safe_substitute(**context)
            
        # Execute transform
        if transform_type == "json":
            # JSONPath-like transformation
            import jsonpath_ng
            jsonpath_expr = jsonpath_ng.parse(expression)
            matches = jsonpath_expr.find(context)
            return [match.value for match in matches]
            
        elif transform_type == "jmespath":
            # JMESPath transformation
            import jmespath
            return jmespath.search(expression, context)
            
        else:
            raise HookExecutionError(f"Unknown transform type: {transform_type}")
            
    def _substitute_templates(
        self,
        action: HookAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Substitute template variables in context"""
        if not action.template:
            return context
            
        # Create flat context for template substitution
        flat_context = self._flatten_dict(context)
        
        # Apply substitution to string values in config
        substituted_config = {}
        for key, value in action.config.items():
            if isinstance(value, str):
                template = Template(value)
                substituted_config[key] = template.safe_substitute(**flat_context)
            else:
                substituted_config[key] = value
                
        # Update action config
        action.config = substituted_config
        
        return context
        
    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: str = "_"
    ) -> Dict[str, Any]:
        """Flatten nested dictionary for template substitution"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
        
    def _add_to_history(self, result: HookExecutionResult) -> None:
        """Add execution result to history"""
        self._execution_history.append(result)
        
        # Limit history size
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]
            
    def get_execution_history(
        self,
        hook_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[HookExecutionResult]:
        """Get execution history
        
        Args:
            hook_name: Filter by hook name
            limit: Maximum results
            
        Returns:
            List of execution results
        """
        results = self._execution_history
        
        if hook_name:
            results = [r for r in results if r.hook_name == hook_name]
            
        if limit:
            results = results[-limit:]
            
        return results
        
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        success_count = sum(1 for r in self._execution_history if r.success)
        failure_count = len(self._execution_history) - success_count
        
        avg_duration = 0.0
        if self._execution_history:
            avg_duration = sum(r.duration for r in self._execution_history) / len(self._execution_history)
            
        return {
            "total_executions": len(self._execution_history),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / max(1, len(self._execution_history)),
            "average_duration": avg_duration,
            "running_hooks": list(self._running_hooks),
            "custom_functions": list(self.custom_functions.keys())
        }