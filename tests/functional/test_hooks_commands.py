"""
Functional tests for hooks framework and command system.
"""

import pytest
import asyncio
import json
import time
import tempfile
from pathlib import Path

from shannon_mcp.hooks.manager import HookManager
from shannon_mcp.hooks.registry import HookRegistry
from shannon_mcp.commands.parser import CommandParser
from shannon_mcp.commands.executor import CommandExecutor
from shannon_mcp.commands.registry import CommandRegistry
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestHooksSystem:
    """Test hooks framework with real events."""
    
    @pytest.fixture
    async def hooks_setup(self):
        """Set up hooks system."""
        registry = HookRegistry()
        manager = HookManager(registry)
        
        # Set up session manager for hook integration
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        
        # Connect hooks to session events
        session_manager.hook_manager = manager
        
        yield {
            "registry": registry,
            "manager": manager,
            "session_manager": session_manager
        }
    
    @pytest.mark.asyncio
    async def test_session_hooks(self, hooks_setup):
        """Test hooks triggered by session events."""
        setup = hooks_setup
        manager = setup["manager"]
        session_manager = setup["session_manager"]
        
        # Track hook executions
        hook_calls = []
        
        # Register session lifecycle hooks
        async def on_session_start(event, data):
            hook_calls.append(("start", data.get("session_id")))
            print(f"\n[HOOK] Session started: {data.get('session_id')}")
            return {"status": "handled"}
        
        async def on_session_end(event, data):
            hook_calls.append(("end", data.get("session_id")))
            print(f"\n[HOOK] Session ended: {data.get('session_id')}")
            return {"status": "handled"}
        
        async def on_prompt_execute(event, data):
            hook_calls.append(("prompt", data.get("prompt", "")[:50]))
            print(f"\n[HOOK] Prompt: {data.get('prompt', '')[:50]}...")
            return {"status": "handled"}
        
        # Register hooks
        await manager.register_hook({
            "name": "session_start_logger",
            "event": "session.start",
            "handler": on_session_start,
            "priority": 10
        })
        
        await manager.register_hook({
            "name": "session_end_logger",
            "event": "session.end",
            "handler": on_session_end,
            "priority": 10
        })
        
        await manager.register_hook({
            "name": "prompt_logger",
            "event": "prompt.execute",
            "handler": on_prompt_execute,
            "priority": 5
        })
        
        # Create and use session
        session = await session_manager.create_session("hook-test")
        
        # Trigger start hook
        await manager.trigger_event("session.start", {"session_id": session.id})
        await session_manager.start_session(session.id)
        
        # Execute prompt (trigger prompt hook)
        await manager.trigger_event("prompt.execute", {
            "session_id": session.id,
            "prompt": "What is 2+2?"
        })
        
        result = await session_manager.execute_prompt(session.id, "What is 2+2?")
        
        # Close session (trigger end hook)
        await session_manager.close_session(session.id)
        await manager.trigger_event("session.end", {"session_id": session.id})
        
        # Verify hooks were called
        print(f"\nHook calls: {hook_calls}")
        assert ("start", "hook-test") in hook_calls
        assert ("end", "hook-test") in hook_calls
        assert any(call[0] == "prompt" for call in hook_calls)
    
    @pytest.mark.asyncio
    async def test_conditional_hooks(self, hooks_setup):
        """Test hooks with conditions."""
        setup = hooks_setup
        manager = setup["manager"]
        
        # Track executions
        executions = []
        
        # Hook that only runs for specific models
        async def model_specific_hook(event, data):
            executions.append(f"model:{data.get('model')}")
            return {"handled": True}
        
        # Hook that only runs for long prompts
        async def long_prompt_hook(event, data):
            prompt_len = len(data.get("prompt", ""))
            executions.append(f"long_prompt:{prompt_len}")
            return {"handled": True}
        
        # Register conditional hooks
        await manager.register_hook({
            "name": "opus_only",
            "event": "model.select",
            "handler": model_specific_hook,
            "conditions": {
                "model": "claude-3-opus-20240229"
            }
        })
        
        await manager.register_hook({
            "name": "long_prompts",
            "event": "prompt.validate",
            "handler": long_prompt_hook,
            "conditions": {
                "min_prompt_length": 100
            }
        })
        
        # Test with different conditions
        test_events = [
            ("model.select", {"model": "claude-3-opus-20240229"}),  # Should trigger
            ("model.select", {"model": "claude-3-sonnet-20240229"}),  # Should not trigger
            ("prompt.validate", {"prompt": "short"}),  # Should not trigger
            ("prompt.validate", {"prompt": "x" * 150})  # Should trigger
        ]
        
        for event_name, event_data in test_events:
            await manager.trigger_event(event_name, event_data)
        
        print(f"\nConditional executions: {executions}")
        assert "model:claude-3-opus-20240229" in executions
        assert "model:claude-3-sonnet-20240229" not in executions
        assert any("long_prompt:150" in ex for ex in executions)
        assert not any("long_prompt:5" in ex for ex in executions)
    
    @pytest.mark.asyncio
    async def test_hook_chains(self, hooks_setup):
        """Test chained hook execution."""
        setup = hooks_setup
        manager = setup["manager"]
        
        # Create chain of data transformations
        async def step1_uppercase(event, data):
            data["text"] = data.get("text", "").upper()
            print(f"\n[Chain 1] Uppercase: {data['text']}")
            return {"continue": True, "data": data}
        
        async def step2_reverse(event, data):
            data["text"] = data.get("text", "")[::-1]
            print(f"\n[Chain 2] Reverse: {data['text']}")
            return {"continue": True, "data": data}
        
        async def step3_add_prefix(event, data):
            data["text"] = f"PROCESSED: {data.get('text', '')}"
            print(f"\n[Chain 3] Final: {data['text']}")
            return {"final": True, "result": data["text"]}
        
        # Register hooks in order
        await manager.register_hook({
            "name": "transform_1",
            "event": "text.process",
            "handler": step1_uppercase,
            "priority": 1
        })
        
        await manager.register_hook({
            "name": "transform_2",
            "event": "text.process",
            "handler": step2_reverse,
            "priority": 2
        })
        
        await manager.register_hook({
            "name": "transform_3",
            "event": "text.process",
            "handler": step3_add_prefix,
            "priority": 3
        })
        
        # Process text through chain
        results = await manager.trigger_event("text.process", {"text": "hello world"})
        
        # Get final result
        final_result = None
        for result in results:
            if result.get("final"):
                final_result = result.get("result")
        
        print(f"\nFinal result: {final_result}")
        assert final_result == "PROCESSED: DLROW OLLEH"
    
    @pytest.mark.asyncio
    async def test_hook_error_handling(self, hooks_setup):
        """Test hook error recovery."""
        setup = hooks_setup
        manager = setup["manager"]
        
        # Hooks with different error behaviors
        async def failing_hook(event, data):
            raise Exception("Intentional failure")
        
        async def recovery_hook(event, data):
            print(f"\n[Recovery] Handling after failure")
            return {"recovered": True}
        
        # Register hooks
        await manager.register_hook({
            "name": "will_fail",
            "event": "error.test",
            "handler": failing_hook,
            "priority": 1,
            "error_handler": "continue"  # Continue to next hook
        })
        
        await manager.register_hook({
            "name": "will_recover",
            "event": "error.test",
            "handler": recovery_hook,
            "priority": 2
        })
        
        # Trigger event
        results = await manager.trigger_event("error.test", {"test": True})
        
        # Should have error and recovery
        assert any(r.get("error") for r in results)
        assert any(r.get("recovered") for r in results)


class TestCommandSystem:
    """Test command system functionality."""
    
    @pytest.fixture
    async def command_setup(self):
        """Set up command system."""
        parser = CommandParser()
        registry = CommandRegistry()
        executor = CommandExecutor(registry)
        
        # Set up session manager
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        
        yield {
            "parser": parser,
            "registry": registry,
            "executor": executor,
            "session_manager": session_manager
        }
    
    @pytest.mark.asyncio
    async def test_command_registration_execution(self, command_setup):
        """Test registering and executing commands."""
        setup = command_setup
        registry = setup["registry"]
        executor = setup["executor"]
        
        # Track command executions
        executions = []
        
        # Register test commands
        async def hello_command(args):
            name = args.get("name", "World")
            greeting = f"Hello, {name}!"
            executions.append(("hello", greeting))
            return {"message": greeting}
        
        async def calc_command(args):
            op = args.get("operation", "add")
            a = args.get("a", 0)
            b = args.get("b", 0)
            
            if op == "add":
                result = a + b
            elif op == "multiply":
                result = a * b
            else:
                result = 0
            
            executions.append(("calc", result))
            return {"result": result, "operation": op}
        
        # Register commands
        await registry.register({
            "name": "hello",
            "description": "Greet someone",
            "handler": hello_command,
            "args": [
                {"name": "name", "type": "string", "default": "World"}
            ]
        })
        
        await registry.register({
            "name": "calc",
            "description": "Perform calculations",
            "handler": calc_command,
            "args": [
                {"name": "operation", "type": "string", "choices": ["add", "multiply"]},
                {"name": "a", "type": "number", "required": True},
                {"name": "b", "type": "number", "required": True}
            ]
        })
        
        # Execute commands
        test_commands = [
            ("/hello", {}),
            ("/hello --name Alice", {"name": "Alice"}),
            ("/calc --operation add --a 5 --b 3", {"operation": "add", "a": 5, "b": 3}),
            ("/calc --operation multiply --a 4 --b 7", {"operation": "multiply", "a": 4, "b": 7})
        ]
        
        for cmd_str, expected_args in test_commands:
            parsed = setup["parser"].parse(cmd_str)
            result = await executor.execute(parsed["command"], parsed.get("args", {}))
            
            print(f"\nCommand: {cmd_str}")
            print(f"Result: {result}")
        
        # Verify executions
        assert ("hello", "Hello, World!") in executions
        assert ("hello", "Hello, Alice!") in executions
        assert ("calc", 8) in executions  # 5 + 3
        assert ("calc", 28) in executions  # 4 * 7
    
    @pytest.mark.asyncio
    async def test_command_validation(self, command_setup):
        """Test command argument validation."""
        setup = command_setup
        registry = setup["registry"]
        executor = setup["executor"]
        parser = setup["parser"]
        
        # Register command with strict validation
        async def validated_command(args):
            return {"received": args}
        
        await registry.register({
            "name": "strict",
            "handler": validated_command,
            "args": [
                {
                    "name": "age",
                    "type": "integer",
                    "min": 0,
                    "max": 150,
                    "required": True
                },
                {
                    "name": "email",
                    "type": "string",
                    "pattern": r"^[^@]+@[^@]+\.[^@]+$",
                    "required": True
                },
                {
                    "name": "role",
                    "type": "string",
                    "choices": ["admin", "user", "guest"],
                    "default": "user"
                }
            ]
        })
        
        # Test valid command
        valid_cmd = "/strict --age 25 --email test@example.com --role admin"
        parsed = parser.parse(valid_cmd)
        result = await executor.execute(parsed["command"], parsed["args"])
        
        assert result["received"]["age"] == 25
        assert result["received"]["email"] == "test@example.com"
        assert result["received"]["role"] == "admin"
        
        # Test invalid commands
        invalid_commands = [
            "/strict --age 200 --email test@example.com",  # Age out of range
            "/strict --age 25 --email invalid-email",  # Invalid email
            "/strict --age 25 --email test@example.com --role superuser",  # Invalid role
            "/strict --email test@example.com",  # Missing required age
        ]
        
        for invalid_cmd in invalid_commands:
            parsed = parser.parse(invalid_cmd)
            
            with pytest.raises(Exception) as exc_info:
                await executor.execute(parsed["command"], parsed.get("args", {}))
            
            print(f"\nValidation error for '{invalid_cmd}': {exc_info.value}")
            assert "validation" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_command_aliases(self, command_setup):
        """Test command aliases."""
        setup = command_setup
        registry = setup["registry"]
        executor = setup["executor"]
        parser = setup["parser"]
        
        # Register command with aliases
        async def status_command(args):
            verbose = args.get("verbose", False)
            return {
                "status": "running",
                "details": "All systems operational" if verbose else None
            }
        
        await registry.register({
            "name": "status",
            "aliases": ["st", "stat", "info"],
            "handler": status_command,
            "args": [
                {"name": "verbose", "type": "boolean", "short": "v"}
            ]
        })
        
        # Test all aliases
        aliases_to_test = ["/status", "/st", "/stat", "/info"]
        
        for alias in aliases_to_test:
            parsed = parser.parse(f"{alias} --verbose")
            result = await executor.execute_by_alias(
                parsed["command"],
                parsed.get("args", {})
            )
            
            print(f"\nAlias '{alias}' result: {result}")
            assert result["status"] == "running"
            assert result["details"] is not None
    
    @pytest.mark.asyncio
    async def test_command_pipeline(self, command_setup):
        """Test command pipelines."""
        setup = command_setup
        registry = setup["registry"]
        executor = setup["executor"]
        
        # Register pipeline commands
        async def generate_data(args):
            count = args.get("count", 5)
            return {"data": list(range(1, count + 1))}
        
        async def transform_data(args):
            data = args.get("input", [])
            operation = args.get("op", "double")
            
            if operation == "double":
                result = [x * 2 for x in data]
            elif operation == "square":
                result = [x * x for x in data]
            else:
                result = data
            
            return {"data": result}
        
        async def summarize_data(args):
            data = args.get("input", [])
            return {
                "count": len(data),
                "sum": sum(data),
                "average": sum(data) / len(data) if data else 0
            }
        
        # Register commands
        for cmd_def in [
            ("generate", generate_data),
            ("transform", transform_data),
            ("summarize", summarize_data)
        ]:
            await registry.register({
                "name": cmd_def[0],
                "handler": cmd_def[1],
                "supports_pipeline": True
            })
        
        # Execute pipeline
        pipeline = [
            {"command": "generate", "args": {"count": 10}},
            {"command": "transform", "args": {"op": "square"}},
            {"command": "summarize", "args": {}}
        ]
        
        # Run pipeline
        current_output = None
        
        for i, step in enumerate(pipeline):
            # Pass previous output as input
            if current_output and "data" in current_output:
                step["args"]["input"] = current_output["data"]
            
            current_output = await executor.execute(
                step["command"],
                step["args"]
            )
            
            print(f"\nPipeline step {i+1} ({step['command']}):")
            print(f"  Output: {current_output}")
        
        # Verify pipeline result
        # Generated 1-10, squared them, then summarized
        assert current_output["count"] == 10
        assert current_output["sum"] == sum(x*x for x in range(1, 11))  # 385
        assert current_output["average"] == 38.5