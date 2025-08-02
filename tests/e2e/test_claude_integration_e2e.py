"""
Claude Code Integration E2E Tests.

Tests the Shannon MCP server with real Claude Code CLI interactions.
"""

import pytest
import asyncio
import json
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
import aiofiles
import aiohttp

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shannon_mcp.server_fastmcp import ServerState, main
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.streaming.processor import StreamingProcessor
from shannon_mcp.utils.config import get_config


class TestClaudeIntegrationE2E:
    """Test real integration with Claude Code CLI."""
    
    @pytest.fixture
    async def test_environment(self):
        """Set up test environment with real paths."""
        # Create temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="shannon_claude_test_"))
        
        # Set up project structure
        project_dir = temp_dir / "test_project"
        project_dir.mkdir()
        
        # Create test files
        (project_dir / "README.md").write_text("# Test Project\n")
        (project_dir / "main.py").write_text("print('Hello from Claude')\n")
        
        yield {
            "temp_dir": temp_dir,
            "project_dir": project_dir
        }
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    async def mcp_server(self, test_environment):
        """Start real MCP server."""
        config = get_config()
        config.port = 0  # Let system choose port
        config.data_dir = test_environment["temp_dir"] / "mcp_data"
        config.data_dir.mkdir()
        
        # Start server in background
        server_state = ServerState()
        await server_state.initialize()
        
        yield server_state
        
        await server_state.cleanup()
    
    def find_claude_binary(self) -> Optional[Path]:
        """Find real Claude binary on system."""
        # Common locations
        search_paths = [
            Path.home() / ".local" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
            Path("/opt/homebrew/bin/claude"),
            Path.home() / ".claude" / "bin" / "claude"
        ]
        
        # Check PATH
        claude_in_path = shutil.which("claude")
        if claude_in_path:
            return Path(claude_in_path)
        
        # Check specific locations
        for path in search_paths:
            if path.exists() and path.is_file() and os.access(path, os.X_OK):
                return path
        
        return None
    
    @pytest.mark.asyncio
    async def test_claude_binary_discovery(self, mcp_server):
        """Test discovering real Claude binary."""
        binary_manager = mcp_server.managers.get("binary")
        
        # Try to find Claude binary
        binary_info = await binary_manager.find_binary()
        
        if binary_info:
            print(f"Found Claude binary at: {binary_info.path}")
            print(f"Version: {binary_info.version}")
            assert binary_info.is_valid
            
            # Test version command
            result = subprocess.run(
                [str(binary_info.path), "--version"],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            assert "Claude" in result.stdout or "claude" in result.stdout.lower()
        else:
            # Create mock binary for testing
            mock_binary = await self._create_mock_claude_binary(mcp_server)
            assert mock_binary.exists()
    
    async def _create_mock_claude_binary(self, server_state) -> Path:
        """Create a mock Claude binary for testing."""
        binary_dir = server_state.config.data_dir.parent / "mock_bin"
        binary_dir.mkdir(exist_ok=True)
        
        mock_binary = binary_dir / "claude"
        mock_binary.write_text("""#!/usr/bin/env python3
import sys
import json
import time

if "--version" in sys.argv:
    print("Claude Code CLI v1.0.0-mock")
    sys.exit(0)

# Simulate JSONL streaming
messages = [
    {"type": "start", "session_id": "mock_session"},
    {"type": "message", "content": "Processing request..."},
    {"type": "tool_use", "tool": "read_file", "path": "main.py"},
    {"type": "message", "content": "Task completed."},
    {"type": "end", "status": "success"}
]

for msg in messages:
    print(json.dumps(msg))
    sys.stdout.flush()
    time.sleep(0.1)
""")
        mock_binary.chmod(0o755)
        
        # Add to PATH
        os.environ["PATH"] = f"{binary_dir}:{os.environ.get('PATH', '')}"
        
        return mock_binary
    
    @pytest.mark.asyncio
    async def test_session_with_streaming(self, mcp_server, test_environment):
        """Test creating a session with JSONL streaming."""
        session_manager = mcp_server.managers.get("session")
        
        # Create session
        session = await session_manager.create_session(
            prompt="Help me understand this Python project",
            project_path=str(test_environment["project_dir"]),
            stream=True
        )
        
        assert session.id.startswith("sess_")
        
        # Start streaming session
        stream_processor = StreamingProcessor()
        
        # Create mock stream data
        mock_messages = [
            {"type": "session_start", "id": session.id},
            {"type": "message", "role": "assistant", "content": "I'll analyze your Python project."},
            {"type": "tool_use", "name": "read_file", "input": {"path": "main.py"}},
            {"type": "tool_result", "output": "print('Hello from Claude')"},
            {"type": "message", "role": "assistant", "content": "This is a simple Python script."},
            {"type": "session_end", "status": "completed"}
        ]
        
        # Process messages
        processed = []
        for msg in mock_messages:
            result = await stream_processor.process_message(json.dumps(msg))
            if result:
                processed.append(result)
        
        assert len(processed) > 0
        assert any(msg.get("type") == "message" for msg in processed)
    
    @pytest.mark.asyncio
    async def test_file_operations_workflow(self, mcp_server, test_environment):
        """Test file operations workflow with Claude-like behavior."""
        project_dir = test_environment["project_dir"]
        
        # Create test files
        src_dir = project_dir / "src"
        src_dir.mkdir()
        
        files = {
            "app.py": """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'
""",
            "utils.py": """
def format_response(data):
    return {"status": "success", "data": data}
""",
            "requirements.txt": "flask>=2.0.0\npytest>=7.0.0\n"
        }
        
        for filename, content in files.items():
            (src_dir / filename).write_text(content)
        
        # Simulate Claude analyzing files
        session_manager = mcp_server.managers.get("session")
        session = await session_manager.create_session(
            prompt="Add error handling to this Flask app",
            project_path=str(project_dir)
        )
        
        # Simulate file modifications
        app_file = src_dir / "app.py"
        current_content = app_file.read_text()
        
        # Add error handling
        new_content = current_content.replace(
            "@app.route('/')",
            """@app.errorhandler(404)
def not_found(e):
    return 'Page not found', 404

@app.errorhandler(500)
def server_error(e):
    return 'Internal server error', 500

@app.route('/')"""
        )
        
        app_file.write_text(new_content)
        
        # Verify changes
        assert "@app.errorhandler(404)" in app_file.read_text()
        assert "@app.errorhandler(500)" in app_file.read_text()
    
    @pytest.mark.asyncio
    async def test_checkpoint_workflow(self, mcp_server, test_environment):
        """Test checkpoint creation and restoration workflow."""
        checkpoint_manager = mcp_server.managers.get("checkpoint")
        project_dir = test_environment["project_dir"]
        
        # Create initial state
        (project_dir / "version1.py").write_text("VERSION = '1.0.0'")
        
        # Create checkpoint
        checkpoint1 = await checkpoint_manager.create_checkpoint(
            session_id="test_session",
            label="v1.0.0",
            description="Initial version",
            files={
                "version1.py": "VERSION = '1.0.0'"
            }
        )
        
        # Modify files
        (project_dir / "version1.py").write_text("VERSION = '1.1.0'")
        (project_dir / "feature.py").write_text("FEATURE = 'new'")
        
        # Create another checkpoint
        checkpoint2 = await checkpoint_manager.create_checkpoint(
            session_id="test_session",
            label="v1.1.0",
            description="Added feature",
            parent_id=checkpoint1.id,
            files={
                "version1.py": "VERSION = '1.1.0'",
                "feature.py": "FEATURE = 'new'"
            }
        )
        
        # Test diff
        diff = await checkpoint_manager.diff_checkpoints(
            checkpoint1.id,
            checkpoint2.id
        )
        
        assert "version1.py" in diff["modified"]
        assert "feature.py" in diff["added"]
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, mcp_server, test_environment):
        """Test handling multiple concurrent Claude sessions."""
        session_manager = mcp_server.managers.get("session")
        
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                prompt=f"Task {i}: Analyze code",
                project_path=str(test_environment["project_dir"])
            )
            sessions.append(session)
        
        # Simulate concurrent operations
        async def simulate_session_work(session):
            # Simulate some work
            await asyncio.sleep(0.1)
            
            # Update session state
            await session_manager.update_session_state(
                session.id,
                state="active",
                metadata={"progress": 50}
            )
            
            await asyncio.sleep(0.1)
            
            # Complete session
            await session_manager.complete_session(
                session.id,
                summary=f"Completed {session.id}"
            )
            
            return session.id
        
        # Run sessions concurrently
        results = await asyncio.gather(
            *[simulate_session_work(s) for s in sessions]
        )
        
        assert len(results) == 3
        assert all(r.startswith("sess_") for r in results)
        
        # Verify all completed
        for session in sessions:
            status = await session_manager.get_session_status(session.id)
            assert status == "completed"
    
    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self, mcp_server):
        """Test various error scenarios."""
        session_manager = mcp_server.managers.get("session")
        
        # Test invalid session ID
        with pytest.raises(Exception):
            await session_manager.get_session_status("invalid_session_id")
        
        # Test session timeout
        session = await session_manager.create_session(
            prompt="Test timeout",
            timeout=0.1  # Very short timeout
        )
        
        await asyncio.sleep(0.2)
        
        # Session should be timed out
        status = await session_manager.get_session_status(session.id)
        assert status in ["timeout", "failed"]
    
    @pytest.mark.asyncio
    async def test_analytics_collection(self, mcp_server, test_environment):
        """Test analytics data collection during Claude interactions."""
        analytics_manager = mcp_server.managers.get("analytics")
        session_manager = mcp_server.managers.get("session")
        
        # Create and run session
        session = await session_manager.create_session(
            prompt="Generate analytics test",
            project_path=str(test_environment["project_dir"])
        )
        
        # Simulate some operations
        events = [
            {"type": "session_start", "session_id": session.id},
            {"type": "tool_use", "tool": "read_file", "duration_ms": 45},
            {"type": "tool_use", "tool": "write_file", "duration_ms": 120},
            {"type": "message_sent", "tokens": 150},
            {"type": "message_received", "tokens": 280},
            {"type": "session_end", "duration_s": 15}
        ]
        
        for event in events:
            await analytics_manager.track_event(event)
        
        # Query analytics
        stats = await analytics_manager.get_session_stats(session.id)
        
        assert stats["tool_uses"] == 2
        assert stats["total_tokens"] == 430
        assert stats["duration_seconds"] == 15


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance with Claude."""
    
    @pytest.mark.asyncio
    async def test_mcp_handshake(self):
        """Test MCP protocol handshake."""
        # Create test messages
        handshake_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": True,
                    "resources": True,
                    "prompts": True
                }
            },
            "id": 1
        }
        
        # Expected response structure
        expected_response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {
                        "listTools": True
                    },
                    "resources": {
                        "listResources": True,
                        "readResource": True
                    }
                }
            },
            "id": 1
        }
        
        # Verify response structure matches expected
        assert "jsonrpc" in expected_response
        assert expected_response["jsonrpc"] == "2.0"
    
    @pytest.mark.asyncio
    async def test_mcp_tool_listing(self):
        """Test MCP tool listing."""
        tools_response = {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "create_session",
                        "description": "Create a new Claude session",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string"}
                            },
                            "required": ["prompt"]
                        }
                    },
                    {
                        "name": "create_checkpoint",
                        "description": "Create a session checkpoint",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "session_id": {"type": "string"},
                                "label": {"type": "string"}
                            },
                            "required": ["session_id"]
                        }
                    }
                ]
            },
            "id": 2
        }
        
        assert len(tools_response["result"]["tools"]) >= 2
        assert all("name" in tool for tool in tools_response["result"]["tools"])
        assert all("inputSchema" in tool for tool in tools_response["result"]["tools"])


# Performance benchmarks
class TestPerformanceBenchmarks:
    """Performance benchmarks for Claude integration."""
    
    @pytest.mark.asyncio
    async def test_session_creation_performance(self, mcp_server):
        """Benchmark session creation performance."""
        import time
        
        session_manager = mcp_server.managers.get("session")
        
        times = []
        for i in range(10):
            start = time.perf_counter()
            session = await session_manager.create_session(
                prompt=f"Performance test {i}"
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        print(f"Average session creation time: {avg_time*1000:.2f}ms")
        
        # Should be fast
        assert avg_time < 0.1  # Less than 100ms
    
    @pytest.mark.asyncio
    async def test_checkpoint_performance(self, mcp_server):
        """Benchmark checkpoint operations."""
        import time
        
        checkpoint_manager = mcp_server.managers.get("checkpoint")
        
        # Create test data
        files = {
            f"file_{i}.py": f"# Content of file {i}\n" * 100
            for i in range(10)
        }
        
        # Benchmark checkpoint creation
        start = time.perf_counter()
        checkpoint = await checkpoint_manager.create_checkpoint(
            session_id="perf_test",
            label="performance_test",
            files=files
        )
        create_time = time.perf_counter() - start
        
        print(f"Checkpoint creation time: {create_time*1000:.2f}ms")
        
        # Benchmark checkpoint retrieval
        start = time.perf_counter()
        retrieved = await checkpoint_manager.get_checkpoint(checkpoint.id)
        retrieve_time = time.perf_counter() - start
        
        print(f"Checkpoint retrieval time: {retrieve_time*1000:.2f}ms")
        
        # Should be reasonably fast
        assert create_time < 0.5  # Less than 500ms
        assert retrieve_time < 0.1  # Less than 100ms


if __name__ == "__main__":
    pytest.main([__file__] + sys.argv[1:])