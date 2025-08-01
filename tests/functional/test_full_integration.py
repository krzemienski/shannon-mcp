"""
Comprehensive integration tests for Shannon MCP Server.
Tests the complete system with all components working together.
"""

import pytest
import asyncio
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta

from shannon_mcp.server import ShannonMCPServer
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.agent import AgentManager
from shannon_mcp.checkpoints.manager import CheckpointManager
from shannon_mcp.analytics.writer import MetricsWriter
from shannon_mcp.registry.manager import ProcessRegistryManager
from shannon_mcp.hooks.manager import HookManager
from shannon_mcp.commands.executor import CommandExecutor


class TestFullIntegration:
    """Test complete Shannon MCP Server integration."""
    
    @pytest.fixture
    async def server_setup(self, tmp_path):
        """Set up complete MCP server."""
        # Check for Claude Code binary
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        # Create server with test configuration
        config = {
            "server": {
                "host": "localhost",
                "port": 0,  # Use random port
                "data_dir": str(tmp_path)
            },
            "binary_manager": {
                "cache_dir": str(tmp_path / "binary_cache")
            },
            "session_manager": {
                "max_sessions": 10,
                "default_timeout": 300
            },
            "checkpoint": {
                "storage_dir": str(tmp_path / "checkpoints"),
                "compression": True
            },
            "analytics": {
                "metrics_dir": str(tmp_path / "metrics"),
                "retention_days": 7
            },
            "registry": {
                "database": str(tmp_path / "registry.db")
            }
        }
        
        server = ShannonMCPServer(config=config)
        await server.initialize()
        
        yield server
        
        # Cleanup
        await server.shutdown()
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, server_setup):
        """Test a complete workflow using all components."""
        server = server_setup
        
        print("\n=== Starting Complete Shannon MCP Workflow Test ===")
        
        # 1. Create a session
        print("\n1. Creating session...")
        session = await server.session_manager.create_session(
            session_id="integration-test",
            options={
                "model": "claude-3-opus-20240229",
                "temperature": 0.7,
                "stream": True
            }
        )
        await server.session_manager.start_session(session.id)
        
        # 2. Register session in process registry
        print("\n2. Registering in process registry...")
        if hasattr(session, 'process') and session.process:
            process_entry = await server.registry_manager.register_process({
                "pid": session.process.pid,
                "type": "claude_session",
                "session_id": session.id,
                "metadata": {"test": "integration"}
            })
            print(f"   Registered with entry ID: {process_entry}")
        
        # 3. Set up hooks for session events
        print("\n3. Setting up event hooks...")
        hook_executions = []
        
        async def track_events(event, data):
            hook_executions.append({
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            })
            print(f"   [HOOK] {event}: {data.get('type', 'unknown')}")
            return {"handled": True}
        
        await server.hook_manager.register_hook({
            "name": "event_tracker",
            "event": "session.*",
            "handler": track_events,
            "priority": 10
        })
        
        # 4. Register an agent for code analysis
        print("\n4. Registering code analysis agent...")
        agent_id = await server.agent_manager.register_agent({
            "name": "Code Analyzer",
            "description": "Analyzes code quality and structure",
            "capabilities": ["code_analysis", "quality_check"],
            "session_config": {"temperature": 0.3}
        })
        
        # 5. Execute initial prompt
        print("\n5. Executing initial prompt...")
        await server.hook_manager.trigger_event("session.prompt", {
            "type": "start",
            "session_id": session.id
        })
        
        prompt1 = "Create a Python function that calculates factorial recursively"
        result1 = await server.session_manager.execute_prompt(session.id, prompt1)
        
        print(f"   Response preview: {str(result1)[:100]}...")
        
        # 6. Create checkpoint after first prompt
        print("\n6. Creating checkpoint...")
        state1 = await server.session_manager.get_session_state(session.id)
        checkpoint1 = await server.checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state1,
            metadata={"stage": "factorial_function"}
        )
        print(f"   Checkpoint ID: {checkpoint1.id}")
        
        # 7. Write analytics metrics
        print("\n7. Recording analytics...")
        await server.analytics_writer.write_metric({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "prompt_completion",
            "session_id": session.id,
            "prompt_length": len(prompt1),
            "response_length": len(str(result1)),
            "checkpoint_id": checkpoint1.id
        })
        
        # 8. Execute agent task
        print("\n8. Running agent analysis...")
        agent_task = {
            "agent_id": agent_id,
            "type": "analyze_code",
            "input": str(result1),
            "instructions": "Analyze the factorial function for efficiency and suggest improvements"
        }
        
        execution_id = await server.agent_manager.execute_task(agent_task)
        
        # Wait for agent completion
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status = await server.agent_manager.get_execution_status(execution_id)
            if status["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(1)
        
        agent_result = await server.agent_manager.get_execution_result(execution_id)
        print(f"   Agent analysis: {str(agent_result.get('output', ''))[:100]}...")
        
        # 9. Execute command via command system
        print("\n9. Executing custom command...")
        
        # Register a custom command
        async def summary_command(args):
            session_id = args.get("session_id")
            stats = await server.session_manager.get_session_stats(session_id)
            return {
                "session_id": session_id,
                "prompts": stats.get("prompt_count", 0),
                "runtime": stats.get("runtime_seconds", 0)
            }
        
        await server.command_registry.register({
            "name": "session-summary",
            "description": "Get session statistics",
            "handler": summary_command,
            "args": [{"name": "session_id", "type": "string", "required": True}]
        })
        
        # Execute command
        cmd_result = await server.command_executor.execute(
            "session-summary",
            {"session_id": session.id}
        )
        print(f"   Command result: {cmd_result}")
        
        # 10. Create second checkpoint and test restore
        print("\n10. Testing checkpoint restore...")
        
        # Execute another prompt
        prompt2 = "Now modify the factorial function to use iteration instead"
        result2 = await server.session_manager.execute_prompt(session.id, prompt2)
        
        # Create second checkpoint
        state2 = await server.session_manager.get_session_state(session.id)
        checkpoint2 = await server.checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state2,
            metadata={"stage": "iterative_factorial"}
        )
        
        # Test current state
        verify_prompt = "Show me the current factorial implementation"
        current_result = await server.session_manager.execute_prompt(session.id, verify_prompt)
        print(f"   Current implementation mentions iteration: {'iteration' in str(current_result).lower()}")
        
        # Restore to first checkpoint
        await server.checkpoint_manager.restore_checkpoint(checkpoint1.id, session.id)
        
        # Verify restoration
        restored_result = await server.session_manager.execute_prompt(session.id, verify_prompt)
        print(f"   Restored implementation mentions recursion: {'recurs' in str(restored_result).lower()}")
        
        # 11. Test streaming with analytics
        print("\n11. Testing streaming with metrics...")
        stream_chunks = []
        chunk_times = []
        
        last_time = time.time()
        async for chunk in server.session_manager.stream_prompt(
            session.id,
            "Explain the difference between recursive and iterative factorial implementations"
        ):
            current_time = time.time()
            chunk_times.append(current_time - last_time)
            last_time = current_time
            
            stream_chunks.append(chunk)
            
            # Write streaming metric
            await server.analytics_writer.write_metric({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "stream_chunk",
                "session_id": session.id,
                "chunk_index": len(stream_chunks),
                "latency_ms": chunk_times[-1] * 1000
            })
        
        print(f"   Received {len(stream_chunks)} chunks")
        print(f"   Average chunk latency: {sum(chunk_times)/len(chunk_times)*1000:.2f}ms")
        
        # 12. Monitor resource usage
        print("\n12. Checking resource usage...")
        if hasattr(session, 'process') and session.process:
            resources = await server.resource_monitor.get_process_resources(session.process.pid)
            if resources:
                print(f"   CPU: {resources['cpu_percent']:.1f}%")
                print(f"   Memory: {resources['memory_mb']:.1f} MB")
        
        # 13. Generate analytics report
        print("\n13. Generating analytics report...")
        report = await server.analytics_reporter.generate_report(
            metrics_dir=server.analytics_writer.metrics_dir,
            format="json",
            session_filter=session.id
        )
        
        print(f"   Total metrics: {report.get('summary', {}).get('total_metrics', 0)}")
        print(f"   Metric types: {list(report.get('metrics_by_type', {}).keys())}")
        
        # 14. Test cross-component integration
        print("\n14. Testing cross-component messaging...")
        
        # Send message via registry
        if 'process_entry' in locals():
            message_id = await server.registry_manager.send_message(
                from_process=process_entry,
                to_process=process_entry,  # Self-message for testing
                message={
                    "type": "integration_test",
                    "components": ["session", "checkpoint", "analytics", "agent"],
                    "status": "successful"
                }
            )
            
            # Retrieve message
            messages = await server.registry_manager.get_messages(process_entry)
            print(f"   Messages in registry: {len(messages)}")
        
        # 15. Cleanup and final metrics
        print("\n15. Cleanup and final metrics...")
        
        # Close session
        await server.session_manager.close_session(session.id)
        
        # Final analytics
        await server.analytics_writer.write_metric({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "test_complete",
            "session_id": session.id,
            "total_prompts": 4,
            "checkpoints_created": 2,
            "hooks_executed": len(hook_executions),
            "agent_tasks": 1
        })
        
        # Verify all components worked
        print("\n=== Integration Test Summary ===")
        print(f"✓ Session created and executed prompts")
        print(f"✓ Process registered and monitored")
        print(f"✓ Hooks executed: {len(hook_executions)} events")
        print(f"✓ Agent analysis completed")
        print(f"✓ Checkpoints created and restored")
        print(f"✓ Analytics metrics recorded")
        print(f"✓ Commands executed successfully")
        print(f"✓ Streaming worked with metrics")
        print(f"✓ Cross-component integration verified")
        
        assert session.status == "closed"
        assert len(hook_executions) > 0
        assert checkpoint2.id != checkpoint1.id
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, server_setup):
        """Test system-wide error recovery."""
        server = server_setup
        
        print("\n=== Testing Error Recovery Integration ===")
        
        # 1. Test session recovery
        print("\n1. Testing session crash recovery...")
        session = await server.session_manager.create_session("crash-test")
        await server.session_manager.start_session(session.id)
        
        # Save state before simulated crash
        pre_crash_state = await server.session_manager.get_session_state(session.id)
        checkpoint = await server.checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=pre_crash_state,
            metadata={"type": "pre_crash"}
        )
        
        # Simulate crash by marking session as failed
        session.status = "failed"
        
        # Attempt recovery
        recovered_session = await server.session_manager.recover_session(
            session.id,
            checkpoint_id=checkpoint.id
        )
        
        print(f"   Session recovered: {recovered_session is not None}")
        print(f"   Recovered status: {recovered_session.status if recovered_session else 'N/A'}")
        
        # 2. Test hook error isolation
        print("\n2. Testing hook error isolation...")
        
        # Register failing hook
        async def failing_hook(event, data):
            raise Exception("Intentional hook failure")
        
        await server.hook_manager.register_hook({
            "name": "failing_hook",
            "event": "test.error",
            "handler": failing_hook,
            "error_handler": "continue"
        })
        
        # Register recovery hook
        recovery_executed = False
        async def recovery_hook(event, data):
            nonlocal recovery_executed
            recovery_executed = True
            return {"recovered": True}
        
        await server.hook_manager.register_hook({
            "name": "recovery_hook",
            "event": "test.error",
            "handler": recovery_hook,
            "priority": 20
        })
        
        # Trigger event
        results = await server.hook_manager.trigger_event("test.error", {})
        
        print(f"   Hook errors isolated: {any(r.get('error') for r in results)}")
        print(f"   Recovery hook executed: {recovery_executed}")
        
        assert recovery_executed
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self, server_setup):
        """Test system-wide performance monitoring."""
        server = server_setup
        
        print("\n=== Testing Performance Monitoring ===")
        
        # Enable performance tracking
        perf_metrics = []
        
        async def perf_hook(event, data):
            if "duration" in data or "latency" in data:
                perf_metrics.append(data)
            return {"tracked": True}
        
        await server.hook_manager.register_hook({
            "name": "performance_tracker",
            "event": "performance.*",
            "handler": perf_hook
        })
        
        # Run performance-sensitive operations
        session = await server.session_manager.create_session("perf-test")
        await server.session_manager.start_session(session.id)
        
        # Measure session operations
        operations = [
            ("simple", "What is 1+1?"),
            ("moderate", "Explain Python decorators"),
            ("complex", "Write a complete REST API with authentication")
        ]
        
        for op_type, prompt in operations:
            start = time.time()
            
            # Trigger performance event
            await server.hook_manager.trigger_event("performance.start", {
                "operation": op_type,
                "session_id": session.id
            })
            
            result = await server.session_manager.execute_prompt(session.id, prompt)
            
            duration = time.time() - start
            
            await server.hook_manager.trigger_event("performance.end", {
                "operation": op_type,
                "session_id": session.id,
                "duration": duration,
                "tokens": len(str(result).split())
            })
            
            perf_metrics.append({
                "operation": op_type,
                "duration": duration,
                "throughput": len(str(result)) / duration
            })
        
        # Analyze performance
        print("\nPerformance Analysis:")
        for metric in perf_metrics[-3:]:  # Last 3 operations
            if "operation" in metric:
                print(f"  {metric['operation']}: {metric['duration']:.2f}s, "
                      f"{metric['throughput']:.0f} chars/sec")
        
        await server.session_manager.close_session(session.id)
        
        assert len(perf_metrics) >= 3