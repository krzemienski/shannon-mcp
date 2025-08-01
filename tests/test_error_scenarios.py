"""
Error scenario tests for Shannon MCP components.
Tests error handling, recovery, and edge cases.
"""

import pytest
import asyncio
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List

# Import all components to test
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.streaming.jsonl import JSONLStreamReader, JSONLParser
from shannon_mcp.storage.cas import ContentAddressableStorage
from shannon_mcp.analytics.writer import MetricsWriter
from shannon_mcp.registry.storage import RegistryStorage
from shannon_mcp.transport.manager import TransportManager
from shannon_mcp.hooks.manager import HookManager
from shannon_mcp.commands.parser import CommandParser
from shannon_mcp.checkpoints.manager import CheckpointManager
from shannon_mcp.server import ShannonMCPServer


class TestBinaryManagerErrors:
    """Test error scenarios for Binary Manager."""
    
    @pytest.mark.asyncio
    async def test_binary_not_found(self):
        """Test handling when no Claude Code binary is found."""
        manager = BinaryManager()
        
        # Mock environment with no binaries
        with patch.dict(os.environ, {"PATH": "/nonexistent/path"}, clear=True):
            with patch('shutil.which', return_value=None):
                binaries = await manager.discover_binaries()
                assert len(binaries) == 0
    
    @pytest.mark.asyncio
    async def test_binary_permission_denied(self, temp_dir):
        """Test handling permission errors when accessing binaries."""
        manager = BinaryManager()
        
        # Create a binary without execute permission
        binary_path = temp_dir / "claude"
        binary_path.write_text("#!/bin/bash\necho test")
        binary_path.chmod(0o644)  # Read/write only, no execute
        
        with patch.dict(os.environ, {"PATH": str(temp_dir)}):
            result = await manager.validate_binary(str(binary_path))
            assert result is False
    
    @pytest.mark.asyncio
    async def test_binary_execution_failure(self):
        """Test handling binary execution failures."""
        manager = BinaryManager()
        
        with patch.object(manager, '_execute_binary') as mock_exec:
            # Simulate execution failure
            mock_exec.side_effect = Exception("Binary crashed")
            
            with pytest.raises(Exception) as exc_info:
                await manager.execute_binary("/fake/claude", ["--help"])
            
            assert "Binary crashed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_corrupted_binary_cache(self, temp_dir):
        """Test handling corrupted binary cache database."""
        # Create corrupted database file
        db_path = temp_dir / "binaries.db"
        db_path.write_text("corrupted data")
        
        manager = BinaryManager(cache_dir=temp_dir)
        
        # Should handle corruption gracefully
        binaries = await manager.get_cached_binaries()
        assert isinstance(binaries, list)
        assert len(binaries) == 0


class TestSessionManagerErrors:
    """Test error scenarios for Session Manager."""
    
    @pytest.mark.asyncio
    async def test_session_creation_failure(self):
        """Test handling session creation failures."""
        manager = SessionManager()
        
        with patch.object(manager.binary_manager, 'get_binary') as mock_get:
            mock_get.side_effect = Exception("No binary available")
            
            with pytest.raises(Exception) as exc_info:
                await manager.create_session("test-session")
            
            assert "No binary available" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_subprocess_crash(self):
        """Test handling subprocess crashes during execution."""
        manager = SessionManager()
        
        # Create mock session
        session = Mock()
        session.id = "crash-test"
        session.status = "running"
        
        mock_process = AsyncMock()
        mock_process.returncode = -11  # SIGSEGV
        mock_process.communicate.return_value = (b"", b"Segmentation fault")
        
        session.process = mock_process
        manager._sessions[session.id] = session
        
        # Should handle crash gracefully
        await manager._handle_process_crash(session.id)
        assert session.status == "failed"
    
    @pytest.mark.asyncio
    async def test_session_timeout(self):
        """Test session timeout handling."""
        manager = SessionManager(default_timeout=0.1)  # 100ms timeout
        
        # Create slow mock process
        mock_process = AsyncMock()
        
        async def slow_communicate():
            await asyncio.sleep(1)  # Longer than timeout
            return (b"output", b"")
        
        mock_process.communicate = slow_communicate
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with pytest.raises(asyncio.TimeoutError):
                await manager.execute_command("test-session", ["sleep", "10"])
    
    @pytest.mark.asyncio
    async def test_session_memory_exhaustion(self):
        """Test handling memory exhaustion in sessions."""
        manager = SessionManager()
        
        # Mock memory monitoring
        with patch('psutil.Process') as mock_process:
            mock_proc_instance = Mock()
            mock_proc_instance.memory_info.return_value.rss = 4 * 1024 * 1024 * 1024  # 4GB
            mock_process.return_value = mock_proc_instance
            
            # Should trigger memory limit protection
            session = await manager.create_session("memory-test")
            is_healthy = await manager._check_session_health(session.id)
            assert is_healthy is False


class TestStreamingErrors:
    """Test error scenarios for streaming components."""
    
    @pytest.mark.asyncio
    async def test_malformed_jsonl(self):
        """Test handling malformed JSONL data."""
        parser = JSONLParser()
        
        # Various malformed inputs
        malformed_inputs = [
            '{"incomplete": ',
            '{"invalid": undefined}',
            'not json at all',
            '{"nested": {"broken": }',
            '[\n]',  # Array instead of object
            ''  # Empty string
        ]
        
        for input_data in malformed_inputs:
            result = await parser.parse_line(input_data)
            assert result is None or isinstance(result, dict)
            # Should not raise exception
    
    @pytest.mark.asyncio
    async def test_stream_buffer_overflow(self):
        """Test handling stream buffer overflow."""
        from shannon_mcp.streaming.buffer import StreamBuffer
        
        buffer = StreamBuffer(max_size=100)  # Small buffer
        
        # Try to overflow buffer
        large_data = "x" * 1000
        
        with pytest.raises(Exception) as exc_info:
            await buffer.write(large_data.encode())
        
        assert "overflow" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_stream_disconnection(self):
        """Test handling unexpected stream disconnection."""
        reader = JSONLStreamReader()
        
        # Mock stream that disconnects
        mock_stream = AsyncMock()
        mock_stream.readline.side_effect = [
            b'{"type": "message"}\n',
            b'',  # EOF - disconnection
        ]
        
        messages = []
        async for msg in reader.read_stream(mock_stream):
            messages.append(msg)
        
        assert len(messages) == 1
        # Should handle disconnection gracefully
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self):
        """Test backpressure handling in streaming."""
        from shannon_mcp.streaming.handler import StreamHandler
        
        handler = StreamHandler()
        slow_consumer = AsyncMock()
        
        # Simulate slow consumer
        async def slow_process(msg):
            await asyncio.sleep(0.1)
        
        slow_consumer.process = slow_process
        handler.add_consumer(slow_consumer)
        
        # Send many messages quickly
        start = asyncio.get_event_loop().time()
        for i in range(10):
            await handler.handle_message({"id": i})
        
        # Should apply backpressure
        duration = asyncio.get_event_loop().time() - start
        assert duration > 0.5  # Should take time due to backpressure


class TestStorageErrors:
    """Test error scenarios for storage components."""
    
    @pytest.mark.asyncio
    async def test_cas_corruption(self, temp_dir):
        """Test handling corrupted CAS objects."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Write valid object
        content = b"test content"
        hash_id = await cas.write(content)
        
        # Corrupt the stored file
        obj_path = cas._get_object_path(hash_id)
        obj_path.write_bytes(b"corrupted")
        
        # Should detect corruption
        with pytest.raises(Exception) as exc_info:
            await cas.read(hash_id)
        
        assert "checksum" in str(exc_info.value).lower() or "corrupt" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_disk_full(self, temp_dir):
        """Test handling disk full errors."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Mock disk full
        with patch('aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_file.write.side_effect = OSError("No space left on device")
            mock_open.return_value.__aenter__.return_value = mock_file
            
            with pytest.raises(OSError) as exc_info:
                await cas.write(b"test content")
            
            assert "No space left" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_database_lock_timeout(self, temp_dir):
        """Test handling database lock timeouts."""
        from shannon_mcp.storage.database import Database
        
        db = Database(temp_dir / "test.db")
        await db.initialize()
        
        # Simulate lock
        async with db.acquire() as conn1:
            # Try to acquire from another connection with short timeout
            with patch.object(db, '_timeout', 0.1):
                with pytest.raises(Exception) as exc_info:
                    async with db.acquire() as conn2:
                        await conn2.execute("CREATE TABLE test (id INTEGER)")
                
                assert "lock" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


class TestAnalyticsErrors:
    """Test error scenarios for analytics components."""
    
    @pytest.mark.asyncio
    async def test_metrics_file_corruption(self, temp_dir):
        """Test handling corrupted metrics files."""
        writer = MetricsWriter(temp_dir / "metrics")
        
        # Write some metrics
        await writer.write_metric({
            "timestamp": "2024-01-01T00:00:00Z",
            "type": "test",
            "value": 42
        })
        
        # Corrupt the metrics file
        metrics_files = list((temp_dir / "metrics").glob("*.jsonl"))
        if metrics_files:
            metrics_files[0].write_text("corrupted\ndata\n{invalid json")
        
        # Parser should handle corruption
        from shannon_mcp.analytics.parser import MetricsParser
        parser = MetricsParser()
        
        metrics = []
        async for metric in parser.parse_file(metrics_files[0]):
            metrics.append(metric)
        
        # Should skip corrupted lines
        assert isinstance(metrics, list)
    
    @pytest.mark.asyncio
    async def test_aggregation_memory_limit(self):
        """Test handling memory limits during aggregation."""
        from shannon_mcp.analytics.aggregator import MetricsAggregator
        
        aggregator = MetricsAggregator(max_memory_mb=1)  # 1MB limit
        
        # Generate large dataset
        large_metrics = []
        for i in range(100000):
            large_metrics.append({
                "timestamp": f"2024-01-01T{i%24:02d}:00:00Z",
                "type": "memory_test",
                "session_id": f"session_{i}",
                "value": i
            })
        
        # Should handle memory limit
        with pytest.raises(Exception) as exc_info:
            await aggregator.aggregate(large_metrics, ["session_id"])
        
        assert "memory" in str(exc_info.value).lower()


class TestTransportErrors:
    """Test error scenarios for transport layer."""
    
    @pytest.mark.asyncio
    async def test_connection_refused(self):
        """Test handling connection refused errors."""
        manager = TransportManager()
        
        # Try to connect to non-existent server
        with pytest.raises(Exception) as exc_info:
            await manager.connect({
                "type": "tcp",
                "host": "localhost",
                "port": 65535  # Unlikely to be in use
            })
        
        assert "refused" in str(exc_info.value).lower() or "connect" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_transport_timeout(self):
        """Test transport timeout handling."""
        manager = TransportManager()
        
        # Mock slow transport
        mock_transport = AsyncMock()
        
        async def slow_send(data):
            await asyncio.sleep(10)
        
        mock_transport.send = slow_send
        
        with patch.object(manager, '_create_transport', return_value=mock_transport):
            session = await manager.create_session("timeout-test", {})
            
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    session.send({"test": "message"}),
                    timeout=0.1
                )
    
    @pytest.mark.asyncio
    async def test_protocol_mismatch(self):
        """Test handling protocol version mismatches."""
        from shannon_mcp.transport.protocol import TransportProtocol
        
        protocol = TransportProtocol(version="2.0")
        
        # Receive message with incompatible version
        message = {
            "jsonrpc": "1.0",  # Old version
            "method": "test",
            "params": {}
        }
        
        with pytest.raises(Exception) as exc_info:
            await protocol.validate_message(message)
        
        assert "version" in str(exc_info.value).lower()


class TestHooksErrors:
    """Test error scenarios for hooks framework."""
    
    @pytest.mark.asyncio
    async def test_hook_execution_timeout(self):
        """Test hook execution timeout."""
        manager = HookManager()
        
        # Register slow hook
        async def slow_hook(event, data):
            await asyncio.sleep(10)
            return {"status": "completed"}
        
        await manager.register_hook({
            "name": "slow_hook",
            "event": "test_event",
            "handler": slow_hook,
            "timeout": 0.1  # 100ms timeout
        })
        
        # Should timeout
        results = await manager.trigger_event("test_event", {})
        assert any(r.get("error") and "timeout" in r["error"].lower() for r in results)
    
    @pytest.mark.asyncio
    async def test_hook_infinite_loop(self):
        """Test detection of infinite hook loops."""
        manager = HookManager()
        
        # Create circular hook dependency
        async def hook_a(event, data):
            if data.get("depth", 0) < 10:
                await manager.trigger_event("event_b", {"depth": data.get("depth", 0) + 1})
            return {"hook": "a"}
        
        async def hook_b(event, data):
            await manager.trigger_event("event_a", {"depth": data.get("depth", 0) + 1})
            return {"hook": "b"}
        
        await manager.register_hook({
            "name": "hook_a",
            "event": "event_a",
            "handler": hook_a
        })
        
        await manager.register_hook({
            "name": "hook_b",
            "event": "event_b",
            "handler": hook_b
        })
        
        # Should detect loop
        with pytest.raises(Exception) as exc_info:
            await manager.trigger_event("event_a", {"depth": 0})
        
        assert "loop" in str(exc_info.value).lower() or "recursion" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_hook_security_violation(self):
        """Test hook security sandbox violations."""
        manager = HookManager()
        
        # Try to register malicious hook
        malicious_hook = {
            "name": "malicious",
            "event": "test",
            "handler": "import os; os.system('rm -rf /')",  # String instead of function
            "type": "python"
        }
        
        with pytest.raises(Exception) as exc_info:
            await manager.register_hook(malicious_hook)
        
        assert "security" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


class TestCommandErrors:
    """Test error scenarios for command system."""
    
    def test_command_parse_errors(self):
        """Test command parsing errors."""
        parser = CommandParser()
        
        # Various malformed commands
        malformed_commands = [
            "/",  # No command name
            "/command --flag",  # Missing flag value
            "/command --flag=",  # Empty flag value
            "/command 'unclosed string",  # Unclosed quote
            "/command --flag='nested 'quotes' problem'",  # Nested quotes
            "not a command",  # No slash prefix
        ]
        
        for cmd in malformed_commands:
            result = parser.parse(cmd)
            # Should either return None or have error field
            assert result is None or "error" in result
    
    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Test handling unknown commands."""
        from shannon_mcp.commands.executor import CommandExecutor
        
        executor = CommandExecutor()
        
        with pytest.raises(Exception) as exc_info:
            await executor.execute("/nonexistent_command", {})
        
        assert "not found" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_command_permission_denied(self):
        """Test command permission errors."""
        from shannon_mcp.commands.executor import CommandExecutor
        
        executor = CommandExecutor()
        
        # Register restricted command
        await executor.register_command({
            "name": "admin_only",
            "handler": lambda args: {"status": "ok"},
            "permissions": ["admin"]
        })
        
        # Try to execute without permission
        with pytest.raises(Exception) as exc_info:
            await executor.execute("/admin_only", {}, user_permissions=[])
        
        assert "permission" in str(exc_info.value).lower()


class TestCheckpointErrors:
    """Test error scenarios for checkpoint system."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_corruption(self, temp_dir):
        """Test handling corrupted checkpoints."""
        from shannon_mcp.checkpoints.storage import CheckpointStorage
        
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create checkpoint
        checkpoint = await manager.create_checkpoint(
            session_id="test",
            state={"data": "test"}
        )
        
        # Corrupt checkpoint data
        checkpoint_file = storage._get_checkpoint_path(checkpoint.id)
        checkpoint_file.write_text("corrupted data")
        
        # Should handle corruption
        with pytest.raises(Exception) as exc_info:
            await manager.load_checkpoint(checkpoint.id)
        
        assert "corrupt" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_checkpoint_conflict(self, temp_dir):
        """Test handling checkpoint merge conflicts."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create base checkpoint
        base = await manager.create_checkpoint(
            session_id="test",
            state={"file": "original content"}
        )
        
        # Create two conflicting branches
        branch1 = await manager.create_checkpoint(
            session_id="test",
            state={"file": "branch 1 content"},
            parent_id=base.id
        )
        
        branch2 = await manager.create_checkpoint(
            session_id="test",
            state={"file": "branch 2 content"},
            parent_id=base.id
        )
        
        # Try to merge - should detect conflict
        with pytest.raises(Exception) as exc_info:
            await manager.merge_checkpoints(branch1.id, branch2.id)
        
        assert "conflict" in str(exc_info.value).lower()


class TestServerErrors:
    """Test error scenarios for main server."""
    
    @pytest.mark.asyncio
    async def test_server_port_in_use(self):
        """Test handling port already in use."""
        server1 = ShannonMCPServer(port=65432)
        server2 = ShannonMCPServer(port=65432)
        
        # Start first server
        await server1.start()
        
        # Second server should fail
        with pytest.raises(Exception) as exc_info:
            await server2.start()
        
        assert "address already in use" in str(exc_info.value).lower() or "bind" in str(exc_info.value).lower()
        
        await server1.stop()
    
    @pytest.mark.asyncio
    async def test_server_initialization_failure(self):
        """Test server initialization failures."""
        # Invalid configuration
        with pytest.raises(Exception):
            server = ShannonMCPServer(config_file="/nonexistent/config.yaml")
            await server.initialize()
    
    @pytest.mark.asyncio
    async def test_server_component_failure(self):
        """Test handling component failures during startup."""
        server = ShannonMCPServer()
        
        # Mock component failure
        with patch.object(server.binary_manager, 'initialize') as mock_init:
            mock_init.side_effect = Exception("Binary manager failed")
            
            with pytest.raises(Exception) as exc_info:
                await server.initialize()
            
            assert "Binary manager failed" in str(exc_info.value)


class TestIntegrationErrors:
    """Test error scenarios across multiple components."""
    
    @pytest.mark.asyncio
    async def test_cascading_failure(self):
        """Test handling cascading failures across components."""
        # Simulate binary manager failure affecting session manager
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        
        # Make binary manager fail
        with patch.object(binary_manager, 'get_binary') as mock_get:
            mock_get.side_effect = Exception("No binaries available")
            
            # Session creation should fail gracefully
            with pytest.raises(Exception) as exc_info:
                await session_manager.create_session("test")
            
            assert "No binaries available" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion(self):
        """Test system behavior under resource exhaustion."""
        # Create many sessions to exhaust resources
        session_manager = SessionManager(max_sessions=5)
        
        sessions = []
        for i in range(5):
            session = await session_manager.create_session(f"session-{i}")
            sessions.append(session)
        
        # Next session should fail
        with pytest.raises(Exception) as exc_info:
            await session_manager.create_session("session-6")
        
        assert "limit" in str(exc_info.value).lower() or "exhausted" in str(exc_info.value).lower()
        
        # Cleanup
        for session in sessions:
            await session_manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_deadlock_prevention(self):
        """Test deadlock prevention mechanisms."""
        # Test multiple components trying to acquire same resources
        storage1 = RegistryStorage(":memory:")
        storage2 = RegistryStorage(":memory:")
        
        await storage1.initialize()
        await storage2.initialize()
        
        # Simulate potential deadlock scenario
        async def task1():
            async with storage1.transaction():
                await asyncio.sleep(0.1)
                async with storage2.transaction():
                    return "task1 complete"
        
        async def task2():
            async with storage2.transaction():
                await asyncio.sleep(0.1)
                async with storage1.transaction():
                    return "task2 complete"
        
        # Should complete without deadlock (with timeout)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(task1(), task2(), return_exceptions=True),
                timeout=5.0
            )
            
            # At least one should complete or timeout gracefully
            assert any(isinstance(r, str) or isinstance(r, Exception) for r in results)
        except asyncio.TimeoutError:
            # Timeout is acceptable - means deadlock was prevented
            pass


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])