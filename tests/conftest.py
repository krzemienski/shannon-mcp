"""Test configuration for Shannon MCP - Real System Tests"""

import pytest
import asyncio
import tempfile
import shutil
import os
from pathlib import Path
from typing import AsyncGenerator, Generator
import aiosqlite

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.utils.config import ShannonConfig, get_config
from shannon_mcp.utils.logging import setup_logging

# Test configuration
TEST_CONFIG = {
    "binary_search_paths": [
        "/usr/local/bin",
        "/usr/bin",
        "~/.local/bin",
    ],
    "session_timeout": 30,
    "max_concurrent_sessions": 5,
    "checkpoint_interval": 60,
    "analytics_enabled": True,
    "agent_cache_size": 100,
}

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def real_temp_dir() -> Generator[Path, None, None]:
    """Create a real temporary directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="shannon_test_")
    temp_path = Path(temp_dir)
    
    # Create subdirectories
    (temp_path / "logs").mkdir()
    (temp_path / "storage").mkdir()
    (temp_path / "cache").mkdir()
    (temp_path / "checkpoints").mkdir()
    
    yield temp_path
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
async def real_sqlite_db(real_temp_dir: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Create a real SQLite database for testing."""
    db_path = real_temp_dir / "test.db"
    
    # Create and initialize database
    async with aiosqlite.connect(str(db_path)) as db:
        # Create basic tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                hash TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        await db.commit()
        
    # Return connection
    db = await aiosqlite.connect(str(db_path))
    yield db
    await db.close()

@pytest.fixture
def real_server_state(real_temp_dir: Path) -> dict:
    """Create a real server state for testing."""
    return {
        "temp_dir": real_temp_dir,
        "config": ShannonConfig(**TEST_CONFIG),
        "sessions": {},
        "agents": {},
        "processes": {},
        "managers": {},  # Add managers dict for tests
        "is_running": True,
    }

@pytest.fixture
def real_binary_path(real_temp_dir: Path) -> Path:
    """Create a mock Claude binary for testing."""
    bin_dir = real_temp_dir / "bin"
    bin_dir.mkdir()
    
    # Create mock Claude binary
    claude_path = bin_dir / "claude"
    claude_path.write_text("""#!/bin/bash
echo "Claude Code CLI v1.0.0-test"
echo "MCP Server Mode"

# Simple mock that reads JSON and responds
while IFS= read -r line; do
    if [[ "$line" == *"initialize"* ]]; then
        echo '{"jsonrpc": "2.0", "result": {"capabilities": {}}, "id": 1}'
    elif [[ "$line" == *"exit"* ]]; then
        break
    else
        echo '{"jsonrpc": "2.0", "result": {}, "id": 1}'
    fi
done
""")
    claude_path.chmod(0o755)
    
    return claude_path

# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "real_system: marks tests that use real system resources")
    config.addinivalue_line("markers", "requires_claude: marks tests that require Claude binary")
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")

# Setup logging for tests
setup_logging(log_level="DEBUG", log_dir=None)