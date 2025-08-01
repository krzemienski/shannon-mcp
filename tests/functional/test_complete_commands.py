"""
Exhaustive functional tests for EVERY command system function.
Tests all command functionality with real Claude Code execution.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from shannon_mcp.commands.parser import CommandParser
from shannon_mcp.commands.executor import CommandExecutor
from shannon_mcp.commands.registry import CommandRegistry
from shannon_mcp.commands.validator import CommandValidator
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.storage.database import Database


class TestCompleteCommandSystem:
    """Test every single command system function comprehensively."""
    
    @pytest.fixture
    async def command_setup(self):
        """Set up command testing environment."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "commands.db"
        
        db = Database(db_path)
        await db.initialize()
        
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        
        parser = CommandParser()
        validator = CommandValidator()
        registry = CommandRegistry(db=db)
        executor = CommandExecutor(
            parser=parser,
            validator=validator,
            registry=registry,
            session_manager=session_manager
        )
        
        await registry.initialize()
        await executor.initialize()
        
        yield {
            "executor": executor,
            "parser": parser,
            "validator": validator,
            "registry": registry,
            "session_manager": session_manager,
            "db": db,
            "temp_dir": temp_dir
        }
        
        # Cleanup
        await executor.cleanup()
        await session_manager.cleanup()
        await db.close()
        shutil.rmtree(temp_dir)
    
    async def test_command_parser_complete(self, command_setup):
        """Test command parser with all syntax variations."""
        parser = command_setup["parser"]
        
        # Test basic command
        result1 = parser.parse("/help")
        assert result1["command"] == "help"
        assert result1["args"] == []
        assert result1["options"] == {}
        
        # Test command with arguments
        result2 = parser.parse("/session create test-session")
        assert result2["command"] == "session"
        assert result2["args"] == ["create", "test-session"]
        
        # Test command with options
        result3 = parser.parse("/session create --model claude-3 --temperature 0.7")
        assert result3["command"] == "session"
        assert result3["args"] == ["create"]
        assert result3["options"]["model"] == "claude-3"
        assert result3["options"]["temperature"] == "0.7"
        
        # Test command with quoted arguments
        result4 = parser.parse('/prompt "Hello world" --session test')
        assert result4["args"] == ["Hello world"]
        assert result4["options"]["session"] == "test"
        
        # Test complex command
        result5 = parser.parse(
            '/agent create "Research Agent" --type research '
            '--capabilities "web_search,analysis" --priority 5'
        )
        assert result5["args"] == ["create", "Research Agent"]
        assert result5["options"]["type"] == "research"
        assert result5["options"]["capabilities"] == "web_search,analysis"
        assert result5["options"]["priority"] == "5"
        
        # Test command with flags
        result6 = parser.parse("/checkpoint create --incremental --compress")
        assert result6["options"]["incremental"] is True
        assert result6["options"]["compress"] is True
        
        # Test command with JSON option
        result7 = parser.parse('/config set --data \'{"key": "value", "num": 123}\'')
        assert result7["options"]["data"] == '{"key": "value", "num": 123}'
        
        # Test multiline command
        result8 = parser.parse("""
        /pipeline create \\
            --name "DataPipeline" \\
            --stages "extract,transform,load" \\
            --parallel
        """)
        assert result8["args"] == ["create"]
        assert result8["options"]["name"] == "DataPipeline"
        assert result8["options"]["parallel"] is True
        
        # Test special characters
        result9 = parser.parse('/echo "Special chars: $@#%^&*()"')
        assert "Special chars: $@#%^&*()" in result9["args"][0]
        
        # Test escape sequences
        result10 = parser.parse('/prompt "Line 1\\nLine 2\\tTabbed"')
        assert result10["args"][0] == "Line 1\\nLine 2\\tTabbed"
    
    async def test_command_validation_complete(self, command_setup):
        """Test command validation with all rules."""
        validator = command_setup["validator"]
        registry = command_setup["registry"]
        
        # Register test commands with validation rules
        await registry.register_command({
            "name": "session",
            "description": "Manage sessions",
            "subcommands": {
                "create": {
                    "args": [
                        {
                            "name": "session_id",
                            "type": "string",
                            "required": False,
                            "pattern": "^[a-zA-Z0-9-_]+$"
                        }
                    ],
                    "options": {
                        "model": {
                            "type": "string",
                            "choices": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
                            "default": "claude-3-opus-20240229"
                        },
                        "temperature": {
                            "type": "float",
                            "min": 0.0,
                            "max": 1.0,
                            "default": 0.7
                        },
                        "max_tokens": {
                            "type": "int",
                            "min": 1,
                            "max": 100000
                        }
                    }
                }
            }
        })
        
        # Test valid command
        valid1 = await validator.validate({
            "command": "session",
            "args": ["create", "test-123"],
            "options": {"temperature": "0.5"}
        })
        assert valid1["valid"] is True
        
        # Test invalid session ID pattern
        invalid1 = await validator.validate({
            "command": "session",
            "args": ["create", "test session"],  # Space not allowed
            "options": {}
        })
        assert invalid1["valid"] is False
        assert "pattern" in invalid1["errors"][0]
        
        # Test invalid option type
        invalid2 = await validator.validate({
            "command": "session",
            "args": ["create"],
            "options": {"temperature": "high"}  # Should be float
        })
        assert invalid2["valid"] is False
        assert "type" in invalid2["errors"][0]
        
        # Test out of range value
        invalid3 = await validator.validate({
            "command": "session",
            "args": ["create"],
            "options": {"temperature": "1.5"}  # Max is 1.0
        })
        assert invalid3["valid"] is False
        assert "max" in invalid3["errors"][0]
        
        # Test invalid choice
        invalid4 = await validator.validate({
            "command": "session",
            "args": ["create"],
            "options": {"model": "gpt-4"}  # Not in choices
        })
        assert invalid4["valid"] is False
        assert "choices" in invalid4["errors"][0]
        
        # Test custom validation function
        await registry.register_command({
            "name": "custom",
            "validator": lambda cmd: cmd["options"].get("key") == "secret"
        })
        
        custom_valid = await validator.validate({
            "command": "custom",
            "args": [],
            "options": {"key": "secret"}
        })
        assert custom_valid["valid"] is True
    
    async def test_command_registry_complete(self, command_setup):
        """Test command registry with all features."""
        registry = command_setup["registry"]
        
        # Register various command types
        commands = [
            {
                "name": "help",
                "description": "Show help information",
                "aliases": ["h", "?"],
                "category": "general",
                "handler": "help_handler"
            },
            {
                "name": "session",
                "description": "Session management",
                "category": "core",
                "subcommands": {
                    "create": {"description": "Create new session"},
                    "list": {"description": "List sessions"},
                    "delete": {"description": "Delete session"},
                    "info": {"description": "Show session info"}
                }
            },
            {
                "name": "agent",
                "description": "Agent management",
                "category": "advanced",
                "requires_session": True,
                "permissions": ["agent.manage"],
                "subcommands": {
                    "register": {"description": "Register agent"},
                    "assign": {"description": "Assign task"},
                    "status": {"description": "Check status"}
                }
            },
            {
                "name": "debug",
                "description": "Debug commands",
                "category": "development",
                "hidden": True,
                "admin_only": True
            }
        ]
        
        for cmd in commands:
            await registry.register_command(cmd)
        
        # Test command lookup
        help_cmd = await registry.get_command("help")
        assert help_cmd["name"] == "help"
        assert "h" in help_cmd["aliases"]
        
        # Test alias resolution
        h_cmd = await registry.resolve_alias("h")
        assert h_cmd == "help"
        
        # Test category listing
        categories = await registry.list_categories()
        assert "general" in categories
        assert "core" in categories
        assert "advanced" in categories
        
        # Test commands by category
        general_cmds = await registry.list_commands(category="general")
        assert any(cmd["name"] == "help" for cmd in general_cmds)
        
        # Test hidden commands
        all_cmds = await registry.list_commands(include_hidden=False)
        assert not any(cmd["name"] == "debug" for cmd in all_cmds)
        
        hidden_cmds = await registry.list_commands(include_hidden=True)
        assert any(cmd["name"] == "debug" for cmd in hidden_cmds)
        
        # Test command search
        search_results = await registry.search_commands("session")
        assert len(search_results) > 0
        assert search_results[0]["name"] == "session"
        
        # Test subcommand resolution
        subcommands = await registry.get_subcommands("session")
        assert "create" in subcommands
        assert "list" in subcommands
        
        # Test command updates
        await registry.update_command("help", {
            "description": "Updated help description",
            "aliases": ["h", "?", "help"]
        })
        updated = await registry.get_command("help")
        assert updated["description"] == "Updated help description"
        assert len(updated["aliases"]) == 3
        
        # Test command deletion
        await registry.unregister_command("debug")
        deleted = await registry.get_command("debug")
        assert deleted is None
    
    async def test_command_execution_complete(self, command_setup):
        """Test command execution with all scenarios."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        session_manager = command_setup["session_manager"]
        
        # Register executable commands
        async def help_handler(context):
            return {
                "success": True,
                "output": "Available commands: help, session, echo",
                "data": {"commands": ["help", "session", "echo"]}
            }
        
        async def echo_handler(context):
            message = " ".join(context["args"])
            return {
                "success": True,
                "output": message,
                "data": {"echoed": message}
            }
        
        async def session_create_handler(context):
            session_id = context["args"][1] if len(context["args"]) > 1 else None
            options = context["options"]
            
            session = await session_manager.create_session(
                session_id=session_id,
                model=options.get("model", "claude-3-opus-20240229")
            )
            
            return {
                "success": True,
                "output": f"Created session: {session.id}",
                "data": {"session_id": session.id}
            }
        
        # Register handlers
        await registry.register_handler("help", help_handler)
        await registry.register_handler("echo", echo_handler)
        await registry.register_handler("session.create", session_create_handler)
        
        # Test basic command execution
        result1 = await executor.execute("/help")
        assert result1["success"] is True
        assert "Available commands" in result1["output"]
        
        # Test command with arguments
        result2 = await executor.execute("/echo Hello World!")
        assert result2["output"] == "Hello World!"
        
        # Test subcommand execution
        result3 = await executor.execute("/session create test-session")
        assert result3["success"] is True
        assert "test-session" in result3["output"]
        
        # Test command with options
        result4 = await executor.execute(
            "/session create --model claude-3-sonnet-20240229"
        )
        assert result4["success"] is True
        
        # Test command context
        async def context_handler(context):
            return {
                "success": True,
                "output": f"User: {context.get('user', 'unknown')}",
                "data": context
            }
        
        await registry.register_handler("whoami", context_handler)
        
        result5 = await executor.execute(
            "/whoami",
            context={"user": "test_user", "session": "test_session"}
        )
        assert "User: test_user" in result5["output"]
        
        # Test command pipeline
        pipeline_result = await executor.execute_pipeline([
            "/session create pipeline-test",
            "/echo Session created",
            "/session info pipeline-test"
        ])
        assert len(pipeline_result) == 3
        assert all(r["success"] for r in pipeline_result)
        
        # Test command with error handling
        async def error_handler(context):
            raise ValueError("Test error")
        
        await registry.register_handler("error", error_handler)
        
        result6 = await executor.execute("/error")
        assert result6["success"] is False
        assert "error" in result6["output"].lower()
    
    async def test_command_permissions_security(self, command_setup):
        """Test command permissions and security."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        
        # Register commands with permissions
        await registry.register_command({
            "name": "admin",
            "description": "Admin command",
            "permissions": ["admin.execute"],
            "handler": lambda ctx: {"success": True, "output": "Admin command executed"}
        })
        
        await registry.register_command({
            "name": "restricted",
            "description": "Restricted command",
            "permissions": ["user.advanced", "feature.experimental"],
            "handler": lambda ctx: {"success": True, "output": "Restricted command executed"}
        })
        
        # Test without permissions
        result1 = await executor.execute(
            "/admin",
            context={"permissions": []}
        )
        assert result1["success"] is False
        assert "permission" in result1["output"].lower()
        
        # Test with correct permissions
        result2 = await executor.execute(
            "/admin",
            context={"permissions": ["admin.execute"]}
        )
        assert result2["success"] is True
        
        # Test with partial permissions
        result3 = await executor.execute(
            "/restricted",
            context={"permissions": ["user.advanced"]}
        )
        assert result3["success"] is False
        
        # Test with all permissions
        result4 = await executor.execute(
            "/restricted",
            context={"permissions": ["user.advanced", "feature.experimental"]}
        )
        assert result4["success"] is True
        
        # Test command sanitization
        dangerous_commands = [
            "/exec rm -rf /",
            "/eval __import__('os').system('ls')",
            "/shell && cat /etc/passwd"
        ]
        
        for cmd in dangerous_commands:
            result = await executor.execute(cmd)
            assert result["success"] is False
            assert "not found" in result["output"].lower() or "invalid" in result["output"].lower()
    
    async def test_command_autocomplete(self, command_setup):
        """Test command autocomplete functionality."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        
        # Register commands for autocomplete
        commands = ["help", "session", "agent", "checkpoint", "analytics"]
        for cmd in commands:
            await registry.register_command({
                "name": cmd,
                "description": f"{cmd} command"
            })
        
        # Register subcommands
        await registry.register_command({
            "name": "session",
            "subcommands": {
                "create": {},
                "list": {},
                "delete": {},
                "info": {}
            }
        })
        
        # Test command prefix autocomplete
        suggestions1 = await executor.autocomplete("/he")
        assert "help" in suggestions1
        
        suggestions2 = await executor.autocomplete("/sess")
        assert "session" in suggestions2
        
        # Test subcommand autocomplete
        suggestions3 = await executor.autocomplete("/session cr")
        assert "create" in suggestions3
        
        # Test option autocomplete
        await registry.register_command({
            "name": "test",
            "options": {
                "model": {"choices": ["claude-3-opus", "claude-3-sonnet"]},
                "temperature": {"type": "float"},
                "verbose": {"type": "bool"}
            }
        })
        
        suggestions4 = await executor.autocomplete("/test --mo")
        assert "--model" in suggestions4
        
        suggestions5 = await executor.autocomplete("/test --model ")
        assert "claude-3-opus" in suggestions5
        assert "claude-3-sonnet" in suggestions5
        
        # Test context-aware autocomplete
        async def dynamic_autocomplete(partial, context):
            if "sessions" in context:
                return [s for s in context["sessions"] if s.startswith(partial)]
            return []
        
        await registry.register_autocomplete("session", "delete", dynamic_autocomplete)
        
        suggestions6 = await executor.autocomplete(
            "/session delete test",
            context={"sessions": ["test-1", "test-2", "prod-1"]}
        )
        assert "test-1" in suggestions6
        assert "test-2" in suggestions6
        assert "prod-1" not in suggestions6
    
    async def test_command_history_replay(self, command_setup):
        """Test command history and replay functionality."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        
        # Enable history tracking
        await executor.enable_history(max_size=100)
        
        # Execute commands
        commands = [
            "/help",
            "/echo First command",
            "/echo Second command",
            "/session create history-test"
        ]
        
        for cmd in commands:
            await executor.execute(cmd)
        
        # Test history retrieval
        history = await executor.get_history()
        assert len(history) == 4
        assert history[0]["command"] == "/help"
        assert history[-1]["command"] == "/session create history-test"
        
        # Test history search
        echo_history = await executor.search_history("echo")
        assert len(echo_history) == 2
        
        # Test replay last command
        replay_result = await executor.replay_last()
        assert replay_result["success"] is True
        assert "history-test" in replay_result["output"]
        
        # Test replay by index
        replay_result2 = await executor.replay(1)  # "echo First command"
        assert replay_result2["output"] == "First command"
        
        # Test replay with modifications
        replay_result3 = await executor.replay(
            2,  # "echo Second command"
            modifications={"args": ["Modified command"]}
        )
        assert replay_result3["output"] == "Modified command"
        
        # Test history export
        exported = await executor.export_history()
        assert len(exported) > 0
        assert "timestamp" in exported[0]
        assert "command" in exported[0]
        assert "result" in exported[0]
        
        # Test history import
        await executor.clear_history()
        await executor.import_history(exported)
        imported_history = await executor.get_history()
        assert len(imported_history) == len(exported)
    
    async def test_command_macros_aliases(self, command_setup):
        """Test command macros and custom aliases."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        
        # Register base commands
        await registry.register_handler(
            "echo",
            lambda ctx: {"success": True, "output": " ".join(ctx["args"])}
        )
        
        await registry.register_handler(
            "session.create",
            lambda ctx: {"success": True, "output": f"Session created: {ctx['args'][1]}"}
        )
        
        # Create macros
        await executor.create_macro({
            "name": "setup",
            "description": "Setup development environment",
            "commands": [
                "/session create dev-{timestamp}",
                "/echo Development session created",
                "/agent register --name DevAgent --type developer"
            ],
            "parameters": {
                "timestamp": {
                    "type": "string",
                    "default": "{{datetime.now().strftime('%Y%m%d-%H%M%S')}}"
                }
            }
        })
        
        # Execute macro
        macro_result = await executor.execute("/macro setup")
        assert len(macro_result) == 3
        assert all(r["success"] for r in macro_result)
        
        # Create parameterized macro
        await executor.create_macro({
            "name": "deploy",
            "description": "Deploy to environment",
            "commands": [
                "/echo Deploying to {env}",
                "/session create deploy-{env}-{version}",
                "/echo Deployment complete"
            ],
            "parameters": {
                "env": {"type": "string", "required": True},
                "version": {"type": "string", "default": "latest"}
            }
        })
        
        # Execute with parameters
        deploy_result = await executor.execute(
            "/macro deploy --env production --version 1.2.3"
        )
        assert "Deploying to production" in deploy_result[0]["output"]
        assert "deploy-production-1.2.3" in deploy_result[1]["output"]
        
        # Create command alias
        await executor.create_alias("ll", "/session list --detailed")
        await executor.create_alias("new", "/session create")
        
        # Test aliases
        alias_result1 = await executor.execute("/new test-alias")
        assert "Session created: test-alias" in alias_result1["output"]
        
        # Test macro management
        macros = await executor.list_macros()
        assert len(macros) >= 2
        assert any(m["name"] == "setup" for m in macros)
        
        # Test macro deletion
        await executor.delete_macro("setup")
        macros_after = await executor.list_macros()
        assert len(macros_after) == len(macros) - 1
    
    async def test_command_error_handling_recovery(self, command_setup):
        """Test command error handling and recovery."""
        executor = command_setup["executor"]
        registry = command_setup["registry"]
        
        # Register commands with different error scenarios
        async def timeout_handler(context):
            await asyncio.sleep(10)  # Longer than timeout
            return {"success": True}
        
        async def retry_handler(context):
            if not hasattr(retry_handler, "attempts"):
                retry_handler.attempts = 0
            retry_handler.attempts += 1
            
            if retry_handler.attempts < 3:
                raise ConnectionError("Temporary failure")
            
            return {"success": True, "output": "Success after retries"}
        
        async def validation_handler(context):
            if not context["args"]:
                raise ValueError("Arguments required")
            return {"success": True, "output": "Valid"}
        
        await registry.register_handler("timeout", timeout_handler)
        await registry.register_handler("retry", retry_handler)
        await registry.register_handler("validate", validation_handler)
        
        # Test timeout handling
        timeout_result = await executor.execute(
            "/timeout",
            timeout=1  # 1 second timeout
        )
        assert timeout_result["success"] is False
        assert "timeout" in timeout_result["output"].lower()
        
        # Test retry mechanism
        retry_result = await executor.execute(
            "/retry",
            retry_config={
                "max_retries": 3,
                "delay": 0.1,
                "backoff": 1.5
            }
        )
        assert retry_result["success"] is True
        assert "Success after retries" in retry_result["output"]
        
        # Test validation error
        validation_result = await executor.execute("/validate")
        assert validation_result["success"] is False
        assert "Arguments required" in validation_result["output"]
        
        # Test error recovery suggestions
        async def recoverable_handler(context):
            raise FileNotFoundError("Config file not found: config.json")
        
        await registry.register_handler("recoverable", recoverable_handler)
        await registry.register_recovery_suggestions(
            "FileNotFoundError",
            [
                "Create default config with: /config init",
                "Specify custom config with: --config path/to/config.json",
                "Run in no-config mode with: --no-config"
            ]
        )
        
        recovery_result = await executor.execute("/recoverable")
        assert recovery_result["success"] is False
        assert "suggestions" in recovery_result
        assert len(recovery_result["suggestions"]) == 3
        
        # Test fallback commands
        await executor.register_fallback(
            "timeout",
            "/echo Command timed out, using cached result"
        )
        
        fallback_result = await executor.execute(
            "/timeout",
            timeout=1,
            use_fallback=True
        )
        assert "using cached result" in fallback_result["output"]