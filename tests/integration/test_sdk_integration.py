"""
Integration tests for SDK functionality.

NOTE: These tests require claude-agent-sdk to be installed and configured.
If the SDK is not available, tests will be skipped.
"""

import pytest
from pathlib import Path
import asyncio

from shannon_mcp.adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKAgent,
    ExecutionMode,
    SDKExecutionRequest,
    SDK_AVAILABLE,
)


pytestmark = pytest.mark.skipif(
    not SDK_AVAILABLE,
    reason="Python Agents SDK not installed"
)
pytest_plugins = ["tests.fixtures.sdk_fixtures"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_adapter_initialization_with_real_agents(
    agent_sdk_config,
    architecture_agent_file
):
    """Test SDK adapter initializes with real agent files."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Should have loaded the architecture agent
    assert len(adapter.sdk_agents) > 0

    # Find architecture agent
    arch_agent = None
    for agent in adapter.sdk_agents.values():
        if "architecture" in agent.name.lower():
            arch_agent = agent
            break

    assert arch_agent is not None
    assert arch_agent.enabled
    assert len(arch_agent.capabilities) > 0

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_migration_end_to_end(
    agent_sdk_config,
    legacy_agent
):
    """Test complete agent migration workflow."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Migrate agent
    sdk_agent = await adapter.migrate_agent_to_sdk(legacy_agent)

    # Verify migration
    assert sdk_agent.id == legacy_agent.id
    assert sdk_agent.markdown_path.exists()

    # Verify can be loaded again
    await adapter._load_sdk_agents()
    assert sdk_agent.id in adapter.sdk_agents

    # Verify markdown content
    content = sdk_agent.markdown_path.read_text()
    assert "---" in content  # Has frontmatter
    assert legacy_agent.name in content
    assert "testing" in content  # Has capabilities

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_decomposition_integration(
    agent_sdk_config,
    complex_task_request
):
    """Test task decomposition with real configuration."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    subtasks = await adapter._decompose_task(complex_task_request)

    # Verify subtasks created
    assert len(subtasks) > 0
    assert all(isinstance(desc, str) for desc in subtasks.values())
    assert all(len(desc) > 0 for desc in subtasks.values())

    # Verify each capability has a subtask
    for capability in complex_task_request.required_capabilities:
        assert capability in subtasks

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_capability_matching(
    agent_sdk_config,
    multiple_agents_files
):
    """Test finding agents by capabilities."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Test finding each capability
    for agent_data in multiple_agents_files:
        for capability in agent_data["capabilities"]:
            agent = adapter._find_agent_by_capability(capability)
            assert agent is not None
            assert capability in agent.capabilities

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_agent_initialization(agent_sdk_config):
    """Test multiple adapters can be initialized concurrently."""
    async def init_adapter(config):
        adapter = AgentSDKAdapter(config)
        await adapter.initialize()
        return adapter

    # Create multiple adapters concurrently
    tasks = [init_adapter(agent_sdk_config) for _ in range(3)]
    adapters = await asyncio.gather(*tasks)

    # All should initialize successfully
    assert len(adapters) == 3
    for adapter in adapters:
        assert isinstance(adapter, AgentSDKAdapter)
        await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_adapter_shutdown_cleanup(
    agent_sdk_config,
    multiple_agents_files
):
    """Test adapter shutdown cleans up resources."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Track initial state
    initial_agent_count = len(adapter.sdk_agents)
    assert initial_agent_count > 0

    # Shutdown
    await adapter.shutdown()

    # Verify cleanup
    assert len(adapter.clients) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_handling_for_invalid_agent_file(
    agent_sdk_config,
    temp_agents_dir
):
    """Test handling of invalid agent markdown files."""
    # Create invalid agent file (missing frontmatter)
    invalid_file = temp_agents_dir / "invalid-agent.md"
    invalid_file.write_text("This is not a valid agent file")

    adapter = AgentSDKAdapter(agent_sdk_config)

    # Should not raise during initialization
    # Invalid files should be logged and skipped
    await adapter.initialize()

    # Should not have loaded the invalid agent
    assert "invalid_agent" not in [a.id for a in adapter.sdk_agents.values()]

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_reload_after_file_change(
    agent_sdk_config,
    sample_agent_markdown
):
    """Test reloading agents after file changes."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Get initial agent count
    initial_count = len(adapter.sdk_agents)

    # Modify agent file
    content = sample_agent_markdown.read_text()
    modified_content = content.replace("1.0.0", "1.0.1")
    sample_agent_markdown.write_text(modified_content)

    # Reload agents
    adapter.sdk_agents.clear()
    await adapter._load_sdk_agents()

    # Should have same number of agents
    assert len(adapter.sdk_agents) == initial_count

    # Find the modified agent
    test_agent = None
    for agent in adapter.sdk_agents.values():
        if agent.name == "Test Agent":
            test_agent = agent
            break

    assert test_agent is not None
    assert test_agent.version == "1.0.1"

    await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_usage_with_many_agents(agent_sdk_config, temp_agents_dir):
    """Test memory usage with many agents."""
    # Create 50 agent files
    for i in range(50):
        agent_file = temp_agents_dir / f"agent-{i}.md"
        content = f"""---
id: agent_{i:03d}
name: Agent {i}
category: specialized
capabilities: ["capability_{i}"]
description: Test agent {i}
version: 1.0.0
use_subagents: false
---

You are Agent {i}.
"""
        agent_file.write_text(content)

    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    # Should load all agents
    assert len(adapter.sdk_agents) == 50

    # All agents should be accessible
    for i in range(50):
        agent_id = f"agent_{i:03d}"
        assert agent_id in adapter.sdk_agents

    await adapter.shutdown()


@pytest.mark.integration
def test_sdk_configuration_validation(agent_sdk_config):
    """Test SDK configuration validation."""
    # Valid configuration
    assert agent_sdk_config.enabled is True
    assert agent_sdk_config.agents_directory.exists()
    assert agent_sdk_config.use_subagents is True
    assert agent_sdk_config.max_subagents_per_task > 0
    assert agent_sdk_config.execution_timeout > 0


@pytest.mark.integration
def test_execution_mode_selection():
    """Test execution mode enum and selection."""
    # Test all execution modes are defined
    assert ExecutionMode.SIMPLE.value == "simple"
    assert ExecutionMode.COMPLEX.value == "complex"
    assert ExecutionMode.SUBAGENT.value == "subagent"
    assert ExecutionMode.LEGACY.value == "legacy"

    # Test mode selection logic
    simple_request = SDKExecutionRequest(
        agent_id="agent_001",
        task_id="task_001",
        task_description="Simple task",
        required_capabilities=["testing"],
        execution_mode=ExecutionMode.SIMPLE,
    )
    assert simple_request.execution_mode == ExecutionMode.SIMPLE

    complex_request = SDKExecutionRequest(
        agent_id="agent_001",
        task_id="task_002",
        task_description="Complex task",
        required_capabilities=["a", "b", "c"],
        execution_mode=ExecutionMode.COMPLEX,
        use_subagents=True,
    )
    assert complex_request.use_subagents is True
    assert len(complex_request.required_capabilities) > 1
