"""
Unit tests for tool integration layer.
"""

import pytest

from shannon_mcp.tools.tool_integration import (
    ToolIntegrationLayer,
    ToolDefinition,
    ToolExecutionResult,
    ToolSource,
    ToolCategory,
    MCPToolRegistry,
)


pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestMCPToolRegistry:
    """Test MCP tool registry."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = MCPToolRegistry()

        async def mock_handler(**kwargs):
            return "result"

        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            source=ToolSource.MCP,
            category=ToolCategory.FILE_OPERATIONS,
            parameters={"param": {"type": "string"}},
            returns={"type": "string"},
            handler=mock_handler,
            capabilities=["test"]
        )

        registry.register_tool(tool)

        assert len(registry.tools) == 1
        assert "test_tool" in registry.tools

    def test_get_tool(self):
        """Test getting a tool by name."""
        registry = MCPToolRegistry()

        async def mock_handler(**kwargs):
            return "result"

        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            source=ToolSource.MCP,
            category=ToolCategory.FILE_OPERATIONS,
            parameters={},
            returns={},
            handler=mock_handler
        )

        registry.register_tool(tool)

        retrieved = registry.get_tool("test_tool")

        assert retrieved is not None
        assert retrieved.name == "test_tool"

    def test_list_tools_by_category(self):
        """Test listing tools by category."""
        registry = MCPToolRegistry()

        async def mock_handler(**kwargs):
            return "result"

        tool1 = ToolDefinition(
            name="file_tool",
            description="File tool",
            source=ToolSource.MCP,
            category=ToolCategory.FILE_OPERATIONS,
            parameters={},
            returns={},
            handler=mock_handler
        )

        tool2 = ToolDefinition(
            name="code_tool",
            description="Code tool",
            source=ToolSource.MCP,
            category=ToolCategory.CODE_EXECUTION,
            parameters={},
            returns={},
            handler=mock_handler
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)

        file_tools = registry.list_tools(category=ToolCategory.FILE_OPERATIONS)

        assert len(file_tools) == 1
        assert file_tools[0].name == "file_tool"


class TestToolIntegrationLayer:
    """Test tool integration layer."""

    @pytest.mark.asyncio
    async def test_initialization(self, agent_sdk_config):
        """Test tool integration layer initialization."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        integration = ToolIntegrationLayer(adapter)

        # Standard tools should be registered
        assert len(integration.mcp_registry.tools) > 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_execute_tool(self, agent_sdk_config, tmp_path):
        """Test executing an MCP tool."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        integration = ToolIntegrationLayer(adapter)

        # Test read_file tool
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        result = await integration.execute_tool(
            "read_file",
            {"file_path": str(test_file)}
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert result.result == "Test content"

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_get_available_tools(self, agent_sdk_config):
        """Test getting available tools."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        integration = ToolIntegrationLayer(adapter)

        tools = integration.get_available_tools()

        assert len(tools) > 0
        assert all("name" in tool for tool in tools)
        assert all("description" in tool for tool in tools)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_register_custom_tool(self, agent_sdk_config):
        """Test registering a custom tool."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        integration = ToolIntegrationLayer(adapter)

        async def custom_handler(value: str) -> str:
            return f"Processed: {value}"

        integration.register_custom_tool(
            name="custom_tool",
            description="Custom test tool",
            category=ToolCategory.CUSTOM,
            handler=custom_handler,
            parameters={"value": {"type": "string"}},
            returns={"type": "string"},
            capabilities=["custom"]
        )

        tool = integration.mcp_registry.get_tool("custom_tool")

        assert tool is not None
        assert tool.name == "custom_tool"
        assert tool.category == ToolCategory.CUSTOM

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_invoke_agent_as_tool(self, agent_sdk_config, sdk_agent):
        """Test invoking an SDK agent as a tool."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        adapter.sdk_agents[sdk_agent.id] = sdk_agent

        integration = ToolIntegrationLayer(adapter)

        result = await integration.invoke_agent_as_tool(
            sdk_agent.id,
            "Perform analysis"
        )

        assert isinstance(result, dict)
        assert "success" in result

        await adapter.shutdown()
