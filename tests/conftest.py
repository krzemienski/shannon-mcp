"""
Pytest configuration and shared fixtures for Shannon MCP tests.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Generator, AsyncGenerator, Dict, Any
import aiosqlite
import json
import os

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.utils.config import ShannonConfig
from shannon_mcp.storage.database import Database
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.agent import AgentManager
from shannon_mcp.registry.storage import RegistryStorage
from shannon_mcp.analytics.writer import JSONLWriter
from shannon_mcp.utils.logging import setup_logging


# Test configuration
TEST_CONFIG = {
    "binary": {
        "discovery_timeout": 5.0,
        "update_check_interval": 3600,
        "cache_ttl": 1800
    },
    "session": {
        "default_timeout": 30.0,
        "max_concurrent": 3,
        "cache_size": 10
    },
    "logging": {
        "level": "DEBUG",
        "format": "simple"
    }
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
async def test_db(temp_dir: Path) -> AsyncGenerator[Database, None]:
    """Create a test database."""
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def test_config(temp_dir: Path) -> ShannonConfig:
    """Create test configuration."""
    config_path = temp_dir / "config.json"
    config_path.write_text(json.dumps(TEST_CONFIG))

    config = ShannonConfig()
    config._config = TEST_CONFIG
    config._config_path = config_path
    return config


@pytest.fixture
async def binary_manager(test_db: Database, test_config: ShannonConfig) -> AsyncGenerator[BinaryManager, None]:
    """Create a test binary manager."""
    manager = BinaryManager(test_db, test_config)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
async def session_manager(test_db: Database, test_config: ShannonConfig, binary_manager: BinaryManager) -> AsyncGenerator[SessionManager, None]:
    """Create a test session manager."""
    manager = SessionManager(test_db, test_config, binary_manager)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
async def agent_manager(test_db: Database, test_config: ShannonConfig) -> AsyncGenerator[AgentManager, None]:
    """Create a test agent manager."""
    manager = AgentManager(test_db, test_config)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
async def registry_storage(temp_dir: Path) -> AsyncGenerator[RegistryStorage, None]:
    """Create test registry storage."""
    db_path = temp_dir / "registry.db"
    storage = RegistryStorage(db_path)
    await storage.initialize()
    yield storage
    await storage.close()


@pytest.fixture
async def analytics_writer(temp_dir: Path) -> AsyncGenerator[JSONLWriter, None]:
    """Create test analytics writer."""
    analytics_dir = temp_dir / "analytics"
    writer = JSONLWriter(analytics_dir)
    await writer.initialize()
    yield writer
    await writer.close()


@pytest.fixture
def mock_claude_binary(temp_dir: Path) -> Path:
    """Create a mock Claude binary for testing."""
    if os.name == 'nt':
        binary_path = temp_dir / "claude.exe"
        binary_path.write_text("@echo off\necho Claude Code v1.0.0\n")
    else:
        binary_path = temp_dir / "claude"
        binary_path.write_text("#!/bin/bash\necho 'Claude Code v1.0.0'\n")
        binary_path.chmod(0o755)
    
    return binary_path


@pytest.fixture
def sample_agent_data() -> Dict[str, Any]:
    """Sample agent data for testing."""
    return {
        "name": "test-agent",
        "description": "A test agent for unit tests",
        "system_prompt": "You are a test agent.",
        "category": "testing",
        "capabilities": ["test", "debug"],
        "metadata": {
            "version": "1.0.0",
            "author": "Test Suite"
        }
    }


@pytest.fixture
def sample_session_data() -> Dict[str, Any]:
    """Sample session data for testing."""
    return {
        "id": "test-session-123",
        "project_path": "/test/project",
        "prompt": "Test prompt",
        "model": "claude-3-opus",
        "temperature": 0.7,
        "max_tokens": 4096
    }


@pytest.fixture
def sample_metrics_data() -> list:
    """Sample metrics data for testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "id": "metric-1",
            "timestamp": now.isoformat(),
            "type": "session_start",
            "session_id": "session-1",
            "data": {"project_path": "/test/project"}
        },
        {
            "id": "metric-2",
            "timestamp": now.isoformat(),
            "type": "tool_use",
            "session_id": "session-1",
            "data": {"tool_name": "write_file", "success": True}
        },
        {
            "id": "metric-3",
            "timestamp": now.isoformat(),
            "type": "session_end",
            "session_id": "session-1",
            "data": {"duration_seconds": 120, "token_count": 1500}
        }
    ]


@pytest.fixture
def mock_process_info():
    """Mock process information for testing."""
    return {
        "pid": 12345,
        "name": "claude",
        "cmdline": ["claude", "--session", "test-123"],
        "create_time": datetime.now(timezone.utc),
        "status": "running",
        "username": "testuser",
        "cpu_percent": 15.5,
        "memory_info": {"rss": 100 * 1024 * 1024},  # 100MB
        "num_threads": 4
    }


# Async test helpers
async def wait_for_condition(condition_func, timeout=5.0, interval=0.1):
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)
    return False


# Logging setup for tests
setup_logging(log_level="DEBUG", enable_json=False)