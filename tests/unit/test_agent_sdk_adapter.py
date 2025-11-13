"""
Unit tests for AgentSDKAdapter.
"""

import pytest
from pathlib import Path
from datetime import datetime
import asyncio

from shannon_mcp.adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKAgent,
    ExecutionMode,
    SDKExecutionRequest,
    SDKExecutionResult,
)
from shannon_mcp.utils.errors import SDKError, AgentError


# Add fixtures path
pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestAgentSDKAdapter:
    """Test AgentSDKAdapter class."""

    @pytest.mark.asyncio
    async def test_initialization(self, agent_sdk_config):
        """Test SDK adapter initializes correctly."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        assert adapter.config == agent_sdk_config
        assert adapter.agents_dir.exists()
        assert isinstance(adapter.sdk_agents, dict)
        assert isinstance(adapter.clients, dict)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_load_agent_from_markdown(
        self,
        agent_sdk_config,
        sample_agent_markdown
    ):
        """Test loading agent from markdown file."""
        adapter = AgentSDKAdapter(agent_sdk_config)

        agent = await adapter._parse_agent_file(sample_agent_markdown)

        assert agent.id == "test_agent_001"
        assert agent.name == "Test Agent"
        assert agent.category == "specialized"
        assert "testing" in agent.capabilities
        assert "validation" in agent.capabilities
        assert agent.markdown_path == sample_agent_markdown

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_load_multiple_agents(
        self,
        agent_sdk_config,
        multiple_agents_files
    ):
        """Test loading multiple agents from directory."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        assert len(adapter.sdk_agents) == len(multiple_agents_files)

        # Verify all agents loaded
        for agent_data in multiple_agents_files:
            assert agent_data["id"] in adapter.sdk_agents
            agent = adapter.sdk_agents[agent_data["id"]]
            assert agent.name == agent_data["name"]

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_migrate_legacy_agent(
        self,
        agent_sdk_config,
        legacy_agent
    ):
        """Test migrating legacy agent to SDK format."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        sdk_agent = await adapter.migrate_agent_to_sdk(legacy_agent)

        assert sdk_agent.id == legacy_agent.id
        assert sdk_agent.name == legacy_agent.name
        assert sdk_agent.markdown_path.exists()
        assert len(sdk_agent.capabilities) == len(legacy_agent.capabilities)

        # Verify markdown file was created
        content = sdk_agent.markdown_path.read_text()
        assert legacy_agent.name in content
        assert "testing" in content
        assert "debugging" in content

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_migrate_agent_no_overwrite(
        self,
        agent_sdk_config,
        legacy_agent,
        temp_agents_dir
    ):
        """Test migration fails if file exists and overwrite=False."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        # Create agent first time
        await adapter.migrate_agent_to_sdk(legacy_agent)

        # Try to migrate again without overwrite
        with pytest.raises(ValueError, match="already exists"):
            await adapter.migrate_agent_to_sdk(legacy_agent, overwrite=False)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_migrate_agent_with_overwrite(
        self,
        agent_sdk_config,
        legacy_agent
    ):
        """Test migration succeeds with overwrite=True."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        # Create agent first time
        sdk_agent_1 = await adapter.migrate_agent_to_sdk(legacy_agent)

        # Migrate again with overwrite
        sdk_agent_2 = await adapter.migrate_agent_to_sdk(
            legacy_agent,
            overwrite=True
        )

        assert sdk_agent_1.id == sdk_agent_2.id
        assert sdk_agent_1.markdown_path == sdk_agent_2.markdown_path

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_find_agent_by_capability(
        self,
        agent_sdk_config,
        multiple_agents_files
    ):
        """Test finding agent by capability."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        # Find agent with capability_1
        agent = adapter._find_agent_by_capability("capability_1")
        assert agent is not None
        assert "capability_1" in agent.capabilities

        # Find agent with non-existent capability
        agent = adapter._find_agent_by_capability("non_existent")
        assert agent is None

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_get_allowed_tools(self, agent_sdk_config, sdk_agent):
        """Test getting allowed tools for agent."""
        adapter = AgentSDKAdapter(agent_sdk_config)

        tools = adapter._get_allowed_tools(sdk_agent)

        # Should have base tools
        assert 'Read' in tools
        assert 'Write' in tools
        assert 'Bash' in tools

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_get_allowed_tools_with_database_capability(
        self,
        agent_sdk_config
    ):
        """Test tools include checkpoint for database capability."""
        adapter = AgentSDKAdapter(agent_sdk_config)

        agent = SDKAgent(
            id="db_agent",
            name="Database Agent",
            markdown_path=Path("/tmp/db-agent.md"),
            system_prompt="Database expert",
            capabilities=["database", "storage"],
            category="infrastructure",
        )

        tools = adapter._get_allowed_tools(agent)

        assert 'create_checkpoint' in tools

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_decompose_task(
        self,
        agent_sdk_config,
        complex_task_request
    ):
        """Test task decomposition for subagents."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        subtasks = await adapter._decompose_task(complex_task_request)

        # Should have subtask for each capability
        assert len(subtasks) == len(complex_task_request.required_capabilities)
        for capability in complex_task_request.required_capabilities:
            assert capability in subtasks
            assert complex_task_request.task_description in subtasks[capability]

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_aggregate_subagent_results(self, agent_sdk_config):
        """Test aggregating results from subagents."""
        adapter = AgentSDKAdapter(agent_sdk_config)

        results = [
            {
                "agent_id": "agent_001",
                "messages": [{"content": "result 1"}],
                "status": "completed",
            },
            {
                "agent_id": "agent_002",
                "messages": [{"content": "result 2"}],
                "status": "completed",
            },
            Exception("Test error"),
        ]

        aggregated = await adapter._aggregate_subagent_results(results)

        assert "messages" in aggregated
        assert len(aggregated["messages"]) == 2
        assert aggregated["total_subagents"] == 3
        assert aggregated["successful"] == 2
        assert len(aggregated["errors"]) == 1

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_sdk_agent_to_dict(self, sdk_agent):
        """Test SDKAgent serialization."""
        agent_dict = sdk_agent.to_dict()

        assert agent_dict["id"] == sdk_agent.id
        assert agent_dict["name"] == sdk_agent.name
        assert agent_dict["capabilities"] == sdk_agent.capabilities
        assert agent_dict["category"] == sdk_agent.category
        assert "created_at" in agent_dict

    @pytest.mark.asyncio
    async def test_execution_result_to_dict(self):
        """Test SDKExecutionResult serialization."""
        result = SDKExecutionResult(
            task_id="task_001",
            agent_id="agent_001",
            agent_name="Test Agent",
            status="completed",
            execution_mode=ExecutionMode.SIMPLE,
            execution_time_seconds=1.5,
        )

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "task_001"
        assert result_dict["agent_id"] == "agent_001"
        assert result_dict["status"] == "completed"
        assert result_dict["execution_mode"] == "simple"
        assert result_dict["execution_time_seconds"] == 1.5

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_clients(
        self,
        agent_sdk_config,
        sdk_agent
    ):
        """Test shutdown closes all SDK clients."""
        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        # Add a mock client
        adapter.clients[sdk_agent.id] = object()

        await adapter.shutdown()

        assert len(adapter.clients) == 0


class TestExecutionModes:
    """Test different execution modes."""

    def test_execution_mode_enum(self):
        """Test ExecutionMode enum values."""
        assert ExecutionMode.SIMPLE.value == "simple"
        assert ExecutionMode.COMPLEX.value == "complex"
        assert ExecutionMode.SUBAGENT.value == "subagent"
        assert ExecutionMode.LEGACY.value == "legacy"


class TestSDKExecutionRequest:
    """Test SDKExecutionRequest class."""

    def test_create_request(self):
        """Test creating execution request."""
        request = SDKExecutionRequest(
            agent_id="agent_001",
            task_id="task_001",
            task_description="Test task",
            required_capabilities=["testing"],
            execution_mode=ExecutionMode.SIMPLE,
        )

        assert request.agent_id == "agent_001"
        assert request.task_id == "task_001"
        assert request.execution_mode == ExecutionMode.SIMPLE
        assert request.priority == "medium"  # default
        assert request.use_subagents is False  # default


class TestSDKExecutionResult:
    """Test SDKExecutionResult class."""

    def test_create_result(self):
        """Test creating execution result."""
        result = SDKExecutionResult(
            task_id="task_001",
            agent_id="agent_001",
            agent_name="Test Agent",
            status="completed",
            execution_mode=ExecutionMode.SIMPLE,
        )

        assert result.task_id == "task_001"
        assert result.agent_id == "agent_001"
        assert result.status == "completed"
        assert result.subagent_count == 0
        assert result.error is None

    def test_result_with_error(self):
        """Test creating result with error."""
        result = SDKExecutionResult(
            task_id="task_001",
            agent_id="agent_001",
            agent_name="Test Agent",
            status="failed",
            execution_mode=ExecutionMode.SIMPLE,
            error="Test error message",
        )

        assert result.status == "failed"
        assert result.error == "Test error message"
