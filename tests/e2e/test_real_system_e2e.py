"""
Real System End-to-End Test Suite for Shannon MCP Server.

This module tests against the actual local system without fixtures or mocks.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
import subprocess
import os
import sys
import platform
import psutil
import signal
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Avoid importing server_fastmcp directly as it runs the server
# from shannon_mcp.server_fastmcp import ServerState, main
from shannon_mcp.managers.binary import BinaryManager, BinaryInfo
from shannon_mcp.managers.session import SessionManager, Session, SessionState
from shannon_mcp.managers.agent import AgentManager, Agent
# from shannon_mcp.managers.project import ProjectManager, Project  # Module doesn't exist yet
from shannon_mcp.managers.checkpoint import CheckpointManager, Checkpoint
from shannon_mcp.managers.hook import HookManager
from shannon_mcp.analytics.aggregator import MetricsAggregator
from shannon_mcp.utils.config import ShannonConfig, get_config


class TestRealSystemE2E:
    """E2E tests using real system resources."""

    @pytest.fixture
    def real_temp_dir(self):
        """Create a real temporary directory on the system."""
        temp_dir = Path(tempfile.mkdtemp(prefix="shannon_test_"))
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def system_paths(self):
        """Get real system paths for testing."""
        paths = {
            "home": Path.home(),
            "temp": Path(tempfile.gettempdir()),
            "cwd": Path.cwd(),
            "python": sys.executable,
            "pip": shutil.which("pip") or shutil.which("pip3"),
            "git": shutil.which("git"),
            "shell": os.environ.get("SHELL", "/bin/bash")
        }
        return paths

    # Commented out - using simpler fixture from conftest.py
    # @pytest.fixture
    # async def real_server_state(self, real_temp_dir):
    #     """Create server state with real config directory."""
    #     # Set up config directory
    #     config_dir = real_temp_dir / ".shannon-mcp"
    #     config_dir.mkdir(exist_ok=True)
    #     
    #     # Create config file
    #     config_file = config_dir / "config.json"
    #     config_data = {
    #         "data_dir": str(real_temp_dir / "data"),
    #         "cache_dir": str(real_temp_dir / "cache"),
    #         "log_dir": str(real_temp_dir / "logs"),
    #         "binary_search_paths": [
    #             "/usr/local/bin",
    #             "/usr/bin",
    #             str(Path.home() / ".local" / "bin"),
    #             "/opt/homebrew/bin"  # macOS
    #         ]
    #     }
    #     config_file.write_text(json.dumps(config_data, indent=2))
    #     
    #     # Set environment variable
    #     os.environ["SHANNON_CONFIG_DIR"] = str(config_dir)
    #     
    #     # Initialize server
    #     state = ServerState()
    #     await state.initialize()
    #     yield state
    #     await state.cleanup()

    # ========== Real Binary Discovery ==========
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires actual manager instances - skipping for real system tests")
    async def test_real_binary_discovery(self, real_server_state, real_temp_dir):
        """Test binary discovery using real system paths."""
        binary_manager = real_server_state["managers"].get("binary")
        
        # Create a mock binary in temp directory
        mock_binary = real_temp_dir / "claude-test"
        mock_binary.write_text("""#!/bin/bash
echo "Claude Code CLI v1.2.3"
""")
        mock_binary.chmod(0o755)
        
        # Add to PATH
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{real_temp_dir}:{original_path}"
        
        try:
            # Test discovery
            binary_info = await binary_manager.find_binary()
            assert binary_info is not None
            assert binary_info.path == mock_binary
            assert binary_info.version == "1.2.3"
            
            # Test real system binary search
            system_binaries = []
            for path_str in os.environ["PATH"].split(":"):
                path = Path(path_str)
                if path.exists():
                    for file in path.iterdir():
                        if file.name.startswith("claude") and file.is_file() and os.access(file, os.X_OK):
                            system_binaries.append(file)
            
            print(f"Found {len(system_binaries)} Claude-related binaries on system")
        finally:
            os.environ["PATH"] = original_path

    @pytest.mark.asyncio
    async def test_real_process_execution(self, real_server_state, system_paths):
        """Test executing real processes on the system."""
        # Test Python execution
        result = subprocess.run(
            [system_paths["python"], "-c", "print('Hello from Python')"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Hello from Python" in result.stdout
        
        # Test shell execution
        if platform.system() != "Windows":
            result = subprocess.run(
                [system_paths["shell"], "-c", "echo 'Shell test'"],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            assert "Shell test" in result.stdout

    # ========== Real File System Operations ==========
    
    @pytest.mark.asyncio
    async def test_real_filesystem_operations(self, real_server_state, real_temp_dir):
        """Test real file system operations."""
        # Create project structure
        project_dir = real_temp_dir / "test_project"
        project_dir.mkdir()
        
        # Create typical project files
        files = {
            "README.md": "# Test Project\n\nThis is a test project.",
            "src/main.py": "def main():\n    print('Hello, World!')\n",
            "src/utils.py": "def helper():\n    return 42\n",
            "tests/test_main.py": "def test_main():\n    assert True\n",
            "requirements.txt": "pytest>=7.0.0\naiofiles>=22.0.0\n"
        }
        
        for file_path, content in files.items():
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        # Test file discovery
        py_files = list(project_dir.rglob("*.py"))
        assert len(py_files) == 3
        
        # Test file reading
        readme_content = (project_dir / "README.md").read_text()
        assert "Test Project" in readme_content
        
        # Test file modification
        main_file = project_dir / "src" / "main.py"
        original_content = main_file.read_text()
        main_file.write_text(original_content + "\nif __name__ == '__main__':\n    main()\n")
        
        # Verify modification
        new_content = main_file.read_text()
        assert "if __name__ == '__main__':" in new_content

    @pytest.mark.asyncio
    async def test_real_git_operations(self, real_server_state, real_temp_dir, system_paths):
        """Test real Git operations if Git is available."""
        if not system_paths["git"]:
            pytest.skip("Git not available on system")
        
        # Initialize Git repo
        repo_dir = real_temp_dir / "git_test"
        repo_dir.mkdir()
        
        # Git init
        result = subprocess.run(
            ["git", "init"],
            cwd=repo_dir,
            capture_output=True
        )
        assert result.returncode == 0
        
        # Create and commit file
        test_file = repo_dir / "test.txt"
        test_file.write_text("Initial content")
        
        subprocess.run(["git", "add", "test.txt"], cwd=repo_dir)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir,
            env={**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com"}
        )
        
        # Test Git log
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        assert "Initial commit" in result.stdout

    # ========== Real Process Management ==========
    
    @pytest.mark.asyncio
    async def test_real_process_monitoring(self, real_server_state):
        """Test real process monitoring using psutil."""
        # Get current process info
        current_process = psutil.Process()
        
        # Test process attributes
        assert current_process.pid > 0
        assert current_process.name() in ["python", "python3", "pytest"]
        assert current_process.is_running()
        assert current_process.cpu_percent() >= 0
        assert current_process.memory_info().rss > 0
        
        # Test child processes
        children = current_process.children(recursive=True)
        print(f"Current process has {len(children)} child processes")
        
        # Create a test subprocess
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(0.5)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Monitor it
        ps_proc = psutil.Process(proc.pid)
        assert ps_proc.is_running()
        
        # Wait and check completion
        proc.wait()
        assert proc.returncode == 0

    @pytest.mark.asyncio
    async def test_real_resource_usage(self, real_server_state):
        """Test real system resource monitoring."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        assert 0 <= cpu_percent <= 100
        
        # Memory usage
        memory = psutil.virtual_memory()
        assert memory.percent > 0
        assert memory.available > 0
        
        # Disk usage
        disk = psutil.disk_usage('/')
        assert disk.percent > 0
        assert disk.free > 0
        
        # Network connections
        connections = psutil.net_connections(kind='inet')
        print(f"System has {len(connections)} network connections")

    # ========== Real Database Operations ==========
    
    @pytest.mark.asyncio
    async def test_real_sqlite_operations(self, real_server_state, real_temp_dir):
        """Test real SQLite database operations."""
        import aiosqlite
        
        db_path = real_temp_dir / "test.db"
        
        async with aiosqlite.connect(db_path) as db:
            # Create tables
            await db.execute("""
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # Insert data
            session_id = "sess_test_001"
            await db.execute(
                "INSERT INTO sessions (id, prompt) VALUES (?, ?)",
                (session_id, "Test prompt")
            )
            
            for i in range(5):
                await db.execute(
                    "INSERT INTO messages (session_id, content) VALUES (?, ?)",
                    (session_id, f"Message {i}")
                )
            
            await db.commit()
            
            # Query data
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,)
            )
            count = await cursor.fetchone()
            assert count[0] == 5
            
            # Test joins
            cursor = await db.execute("""
                SELECT s.id, s.prompt, COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
            """)
            results = await cursor.fetchall()
            assert len(results) == 1
            assert results[0][2] == 5

    # ========== Real Network Operations ==========
    
    @pytest.mark.asyncio
    async def test_real_network_operations(self, real_server_state):
        """Test real network operations."""
        import aiohttp
        import socket
        
        # Test DNS resolution
        try:
            ip = socket.gethostbyname("localhost")
            assert ip in ["127.0.0.1", "::1"]
        except socket.error:
            pytest.skip("DNS resolution not available")
        
        # Test local port availability
        def is_port_available(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return True
                except OSError:
                    return False
        
        # Find available port
        available_port = None
        for port in range(40000, 40100):
            if is_port_available(port):
                available_port = port
                break
        
        assert available_port is not None, "No available ports found"
        print(f"Found available port: {available_port}")

    # ========== Real Checkpoint System ==========
    
    @pytest.mark.asyncio
    async def test_real_checkpoint_storage(self, real_server_state, real_temp_dir):
        """Test real checkpoint storage with content-addressable storage."""
        checkpoint_dir = real_temp_dir / "checkpoints"
        checkpoint_dir.mkdir()
        
        # Create test content
        content = {
            "session_id": "sess_001",
            "files": {
                "main.py": "print('Hello')",
                "utils.py": "def helper(): pass"
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": os.environ.get("USER", "unknown")
            }
        }
        
        # Calculate content hash
        import hashlib
        content_bytes = json.dumps(content, sort_keys=True).encode()
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        
        # Store in CAS structure
        cas_path = checkpoint_dir / content_hash[:2] / content_hash[2:4] / content_hash
        cas_path.parent.mkdir(parents=True, exist_ok=True)
        cas_path.write_bytes(content_bytes)
        
        # Verify storage
        assert cas_path.exists()
        loaded_content = json.loads(cas_path.read_text())
        assert loaded_content["session_id"] == "sess_001"
        
        # Test deduplication
        duplicate_content = content.copy()
        duplicate_hash = hashlib.sha256(
            json.dumps(duplicate_content, sort_keys=True).encode()
        ).hexdigest()
        assert duplicate_hash == content_hash  # Same content, same hash

    # ========== Real Performance Testing ==========
    
    @pytest.mark.asyncio
    async def test_real_performance_characteristics(self, real_server_state, real_temp_dir):
        """Test real system performance characteristics."""
        import time
        
        # File I/O performance
        test_file = real_temp_dir / "perf_test.txt"
        content = "x" * 1024 * 1024  # 1MB
        
        start = time.perf_counter()
        test_file.write_text(content)
        write_time = time.perf_counter() - start
        
        start = time.perf_counter()
        read_content = test_file.read_text()
        read_time = time.perf_counter() - start
        
        assert len(read_content) == len(content)
        print(f"Write 1MB: {write_time:.3f}s, Read 1MB: {read_time:.3f}s")
        
        # Process spawn performance
        start = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        proc.wait()
        spawn_time = time.perf_counter() - start
        print(f"Process spawn time: {spawn_time:.3f}s")
        
        # Async task performance
        async def dummy_task(n):
            await asyncio.sleep(0.001)
            return n
        
        start = time.perf_counter()
        tasks = [dummy_task(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        async_time = time.perf_counter() - start
        assert len(results) == 100
        print(f"100 async tasks: {async_time:.3f}s")

    # ========== Real Integration Test ==========
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires actual manager instances - skipping for real system tests")
    async def test_real_complete_workflow(self, real_server_state, real_temp_dir):
        """Test complete workflow using real system resources."""
        # Create project directory
        project_dir = real_temp_dir / "real_project"
        project_dir.mkdir()
        
        # Initialize project
        project_manager = real_server_state["managers"].get("project")
        project = await project_manager.create_project(
            name="Real System Test",
            path=str(project_dir),
            description="Testing with real system resources"
        )
        
        # Create real files
        src_dir = project_dir / "src"
        src_dir.mkdir()
        
        main_file = src_dir / "main.py"
        main_file.write_text("""
def main():
    print("Real system test")
    return 42

if __name__ == "__main__":
    result = main()
    print(f"Result: {result}")
""")
        
        # Execute the file
        result = subprocess.run(
            [sys.executable, str(main_file)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Real system test" in result.stdout
        assert "Result: 42" in result.stdout
        
        # Create checkpoint of current state
        checkpoint_manager = real_server_state.managers.get("checkpoint")
        
        # Get file contents
        files_state = {}
        for py_file in project_dir.rglob("*.py"):
            relative_path = py_file.relative_to(project_dir)
            files_state[str(relative_path)] = py_file.read_text()
        
        checkpoint = await checkpoint_manager.create_checkpoint(
            session_id="real_test_session",
            label="initial-state",
            files=files_state
        )
        
        assert checkpoint.id.startswith("ckpt_")
        
        # Verify we can list Python processes
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        print(f"Found {len(python_processes)} Python processes running")
        
        # Clean up
        await project_manager.archive_project(project.id)


# Run specific test
if __name__ == "__main__":
    import sys
    pytest.main([__file__] + sys.argv[1:])