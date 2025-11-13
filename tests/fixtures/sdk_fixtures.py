"""
Test fixtures for SDK integration tests.
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from shannon_mcp.adapters.agent_sdk import SDKAgent, ExecutionMode, SDKExecutionRequest
from shannon_mcp.utils.config import AgentSDKConfig
from shannon_mcp.models.agent import Agent, AgentCapability, AgentCategory


@pytest.fixture
def temp_agents_dir(tmp_path):
    """Provide a temporary agents directory."""
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    return agents_dir


@pytest.fixture
def temp_memory_dir(tmp_path):
    """Provide a temporary memory directory."""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    return memory_dir


@pytest.fixture
def agent_sdk_config(temp_agents_dir, temp_memory_dir, tmp_path):
    """Provide AgentSDKConfig for testing."""
    return AgentSDKConfig(
        enabled=True,
        agents_directory=temp_agents_dir,
        memory_directory=temp_memory_dir,
        working_directory=tmp_path,
        use_subagents=True,
        max_subagents_per_task=5,
        permission_mode="acceptEdits",
        allowed_tools=['Read', 'Write', 'Bash'],
        execution_timeout=60,
        max_concurrent_agents=5,
        legacy_fallback_enabled=True,
    )


@pytest.fixture
def sample_agent_markdown(temp_agents_dir):
    """Create a sample agent markdown file."""
    agent_file = temp_agents_dir / "test-agent.md"
    content = """---
id: test_agent_001
name: Test Agent
category: specialized
capabilities: ["testing", "validation", "debugging"]
description: A test agent for unit testing
version: 1.0.0
use_subagents: false
---

You are a test agent used for unit testing the Shannon MCP SDK integration.
Your role is to validate that the SDK adapter works correctly.

## Capabilities

- **testing**: Run and validate tests
- **validation**: Validate data and configurations
- **debugging**: Help debug issues

## Test Mode

This agent operates in test mode and should provide deterministic responses
for testing purposes.
"""
    agent_file.write_text(content)
    return agent_file


@pytest.fixture
def sdk_agent(temp_agents_dir, sample_agent_markdown):
    """Provide a sample SDK agent."""
    return SDKAgent(
        id="test_agent_001",
        name="Test Agent",
        markdown_path=sample_agent_markdown,
        system_prompt="You are a test agent.",
        capabilities=["testing", "validation", "debugging"],
        category="specialized",
        description="A test agent for unit testing",
        version="1.0.0",
        use_subagents=False,
    )


@pytest.fixture
def architecture_agent_file(temp_agents_dir):
    """Create architecture agent markdown file."""
    agent_file = temp_agents_dir / "architecture-agent.md"
    content = """---
id: agent_architecture
name: Architecture Agent
category: core_architecture
capabilities: ["system_design", "api_design", "async_patterns"]
description: Expert in system architecture
version: 1.0.0
use_subagents: true
---

You are the Architecture Agent, an expert in system design and architecture.
"""
    agent_file.write_text(content)
    return agent_file


@pytest.fixture
def legacy_agent():
    """Provide a legacy Shannon agent for migration testing."""
    return Agent(
        id="legacy_agent_001",
        name="Legacy Test Agent",
        description="A legacy agent to be migrated to SDK format",
        category=AgentCategory.SPECIALIZED,
        capabilities=[
            AgentCapability(
                name="testing",
                description="Run tests",
                expertise_level=8
            ),
            AgentCapability(
                name="debugging",
                description="Debug issues",
                expertise_level=7
            ),
        ],
        config={
            "system_prompt": "You are a legacy test agent."
        }
    )


@pytest.fixture
def simple_task_request():
    """Provide a simple task request."""
    return SDKExecutionRequest(
        agent_id="test_agent_001",
        task_id="task_001",
        task_description="Run a simple test",
        required_capabilities=["testing"],
        execution_mode=ExecutionMode.SIMPLE,
        use_subagents=False,
        timeout=30,
        priority="medium",
    )


@pytest.fixture
def complex_task_request():
    """Provide a complex task request requiring multiple capabilities."""
    return SDKExecutionRequest(
        agent_id="architecture_agent",
        task_id="task_002",
        task_description="Design a system architecture",
        required_capabilities=["system_design", "api_design", "async_patterns"],
        execution_mode=ExecutionMode.COMPLEX,
        use_subagents=True,
        timeout=120,
        priority="high",
    )


@pytest.fixture
def multiple_agents_files(temp_agents_dir):
    """Create multiple agent files for testing."""
    agents = [
        {
            "filename": "agent-1.md",
            "id": "agent_001",
            "name": "Agent One",
            "capabilities": ["capability_1", "capability_2"],
        },
        {
            "filename": "agent-2.md",
            "id": "agent_002",
            "name": "Agent Two",
            "capabilities": ["capability_2", "capability_3"],
        },
        {
            "filename": "agent-3.md",
            "id": "agent_003",
            "name": "Agent Three",
            "capabilities": ["capability_3", "capability_4"],
        },
    ]

    for agent_data in agents:
        agent_file = temp_agents_dir / agent_data["filename"]
        content = f"""---
id: {agent_data["id"]}
name: {agent_data["name"]}
category: specialized
capabilities: {agent_data["capabilities"]}
description: Test agent {agent_data["id"]}
version: 1.0.0
use_subagents: false
---

You are {agent_data["name"]}, a test agent.
"""
        agent_file.write_text(content)

    return agents


@pytest.fixture(autouse=True)
def cleanup_temp_dirs(request):
    """Cleanup temporary directories after tests."""
    yield
    # Cleanup happens automatically with tmp_path fixture
