"""
Tool integration layer between Python Agents SDK and MCP.

This module bridges SDK tools and MCP tools, enabling:
- SDK agents to use MCP tools
- MCP tools to invoke SDK agents
- Bidirectional tool sharing
- Tool capability matching
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import structlog

from ..adapters.agent_sdk import AgentSDKAdapter
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.tools.integration")


class ToolSource(Enum):
    """Source of a tool."""
    SDK = "sdk"
    MCP = "mcp"
    NATIVE = "native"


class ToolCategory(Enum):
    """Category of tool functionality."""
    FILE_OPERATIONS = "file_operations"
    CODE_EXECUTION = "code_execution"
    SEARCH = "search"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    DATA_PROCESSING = "data_processing"
    SYSTEM = "system"


@dataclass
class ToolDefinition:
    """Definition of an integrated tool."""
    name: str
    description: str
    source: ToolSource
    category: ToolCategory
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    handler: Callable
    capabilities: List[str] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionResult:
    """Result from tool execution."""
    tool_name: str
    success: bool
    result: Any
    execution_time_seconds: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPToolRegistry:
    """
    Registry for MCP tools.

    Maintains a catalog of available MCP tools and their capabilities.
    """

    def __init__(self):
        """Initialize MCP tool registry."""
        self.tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """
        Register an MCP tool.

        Args:
            tool: Tool definition to register
        """
        logger.info(
            "Registering MCP tool",
            tool_name=tool.name,
            category=tool.category.value
        )

        self.tools[tool.name] = tool

    def unregister_tool(self, tool_name: str) -> None:
        """
        Unregister an MCP tool.

        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self.tools:
            logger.info("Unregistering MCP tool", tool_name=tool_name)
            del self.tools[tool_name]

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """
        Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolDefinition or None
        """
        return self.tools.get(tool_name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        capability: Optional[str] = None
    ) -> List[ToolDefinition]:
        """
        List available tools.

        Args:
            category: Optional category filter
            capability: Optional capability filter

        Returns:
            List of ToolDefinition instances
        """
        tools = list(self.tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if capability:
            tools = [t for t in tools if capability in t.capabilities]

        return tools


class SDKToolAdapter:
    """
    Adapter for SDK agents to use MCP tools.

    Wraps MCP tools in a format that SDK agents can consume.
    """

    def __init__(self, tool_registry: MCPToolRegistry):
        """Initialize SDK tool adapter."""
        self.tool_registry = tool_registry

    async def execute_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        Execute an MCP tool from SDK context.

        Args:
            tool_name: Name of the MCP tool
            parameters: Tool parameters

        Returns:
            ToolExecutionResult
        """
        logger.info(
            "Executing MCP tool from SDK",
            tool_name=tool_name
        )

        start_time = datetime.utcnow()

        try:
            # Get tool definition
            tool = self.tool_registry.get_tool(tool_name)

            if not tool:
                raise ValueError(f"Tool not found: {tool_name}")

            if not tool.enabled:
                raise ValueError(f"Tool disabled: {tool_name}")

            # Execute tool handler
            result = await tool.handler(**parameters)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time_seconds=duration
            )

        except Exception as e:
            logger.error(
                "MCP tool execution failed",
                tool_name=tool_name,
                error=str(e)
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result=None,
                execution_time_seconds=duration,
                error=str(e)
            )

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get JSON schema for an MCP tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema dict or None
        """
        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "returns": tool.returns,
            "capabilities": tool.capabilities
        }


class MCPAgentBridge:
    """
    Bridge for MCP tools to invoke SDK agents.

    Allows MCP tools to delegate work to SDK agents.
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize MCP agent bridge."""
        self.sdk_adapter = sdk_adapter

    async def invoke_agent(
        self,
        agent_id: str,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke an SDK agent from MCP tool context.

        Args:
            agent_id: ID of the agent to invoke
            task_description: Task for the agent
            context: Optional context data

        Returns:
            Agent execution result
        """
        logger.info(
            "Invoking SDK agent from MCP",
            agent_id=agent_id
        )

        try:
            from ..adapters.agent_sdk import SDKExecutionRequest, ExecutionMode

            # Get agent
            agent = self.sdk_adapter.sdk_agents.get(agent_id)

            if not agent:
                return {
                    "success": False,
                    "error": f"Agent not found: {agent_id}"
                }

            # Create execution request
            request = SDKExecutionRequest(
                agent_id=agent.id,
                task_id=f"mcp_bridge_{datetime.utcnow().timestamp()}",
                task_description=task_description,
                required_capabilities=agent.capabilities[:1],
                execution_mode=ExecutionMode.SIMPLE,
                context=context or {}
            )

            # Execute agent
            result = await self.sdk_adapter.execute_complex_task(
                agent,
                request,
                use_subagents=False
            )

            return {
                "success": result.status == "completed",
                "agent_name": agent.name,
                "result": result.messages[-1] if result.messages else "",
                "duration_seconds": result.execution_time_seconds,
                "tokens_used": result.context_tokens_used
            }

        except Exception as e:
            logger.error(
                "Agent invocation from MCP failed",
                agent_id=agent_id,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e)
            }

    def list_available_agents(
        self,
        capability: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List available SDK agents for MCP tools.

        Args:
            capability: Optional capability filter

        Returns:
            List of agent info dicts
        """
        agents = list(self.sdk_adapter.sdk_agents.values())

        if capability:
            agents = [
                a for a in agents
                if capability in a.capabilities
            ]

        return [
            {
                "id": agent.id,
                "name": agent.name,
                "category": agent.category,
                "capabilities": agent.capabilities,
                "description": agent.description
            }
            for agent in agents
            if agent.enabled
        ]


class ToolIntegrationLayer:
    """
    Complete tool integration layer.

    Provides bidirectional integration between SDK and MCP tools,
    enabling seamless tool sharing and execution.
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize tool integration layer."""
        self.sdk_adapter = sdk_adapter
        self.mcp_registry = MCPToolRegistry()
        self.sdk_adapter_tool = SDKToolAdapter(self.mcp_registry)
        self.mcp_bridge = MCPAgentBridge(sdk_adapter)

        # Initialize with standard MCP tools
        self._register_standard_tools()

    def _register_standard_tools(self) -> None:
        """Register standard MCP tools."""
        # File operations
        self.mcp_registry.register_tool(ToolDefinition(
            name="read_file",
            description="Read contents of a file",
            source=ToolSource.MCP,
            category=ToolCategory.FILE_OPERATIONS,
            parameters={
                "file_path": {"type": "string", "description": "Path to file"}
            },
            returns={"type": "string", "description": "File contents"},
            handler=self._read_file_handler,
            capabilities=["file_read"]
        ))

        self.mcp_registry.register_tool(ToolDefinition(
            name="write_file",
            description="Write contents to a file",
            source=ToolSource.MCP,
            category=ToolCategory.FILE_OPERATIONS,
            parameters={
                "file_path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            returns={"type": "boolean", "description": "Success status"},
            handler=self._write_file_handler,
            capabilities=["file_write"]
        ))

        # Code execution
        self.mcp_registry.register_tool(ToolDefinition(
            name="execute_code",
            description="Execute Python code",
            source=ToolSource.MCP,
            category=ToolCategory.CODE_EXECUTION,
            parameters={
                "code": {"type": "string", "description": "Python code to execute"}
            },
            returns={"type": "object", "description": "Execution result"},
            handler=self._execute_code_handler,
            capabilities=["code_execution"]
        ))

        # Search
        self.mcp_registry.register_tool(ToolDefinition(
            name="search_codebase",
            description="Search codebase for patterns",
            source=ToolSource.MCP,
            category=ToolCategory.SEARCH,
            parameters={
                "pattern": {"type": "string", "description": "Search pattern"},
                "file_pattern": {"type": "string", "description": "File pattern filter"}
            },
            returns={"type": "array", "description": "Search results"},
            handler=self._search_codebase_handler,
            capabilities=["search"]
        ))

        logger.info(
            "Standard MCP tools registered",
            count=len(self.mcp_registry.tools)
        )

    async def _read_file_handler(self, file_path: str) -> str:
        """Handler for read_file tool."""
        from pathlib import Path

        try:
            return Path(file_path).read_text()
        except Exception as e:
            raise ValueError(f"Failed to read file: {e}")

    async def _write_file_handler(self, file_path: str, content: str) -> bool:
        """Handler for write_file tool."""
        from pathlib import Path

        try:
            Path(file_path).write_text(content)
            return True
        except Exception as e:
            raise ValueError(f"Failed to write file: {e}")

    async def _execute_code_handler(self, code: str) -> Dict[str, Any]:
        """Handler for execute_code tool."""
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(code, {})

            return {
                "success": True,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue()
            }

    async def _search_codebase_handler(
        self,
        pattern: str,
        file_pattern: str = "**/*.py"
    ) -> List[Dict[str, Any]]:
        """Handler for search_codebase tool."""
        from pathlib import Path
        import re

        results = []
        cwd = Path.cwd()

        try:
            for file_path in cwd.glob(file_pattern):
                if file_path.is_file():
                    content = file_path.read_text()
                    matches = re.finditer(pattern, content)

                    for match in matches:
                        results.append({
                            "file": str(file_path),
                            "line": content[:match.start()].count('\n') + 1,
                            "match": match.group(),
                            "context": content[max(0, match.start()-50):match.end()+50]
                        })
        except Exception as e:
            logger.error("Search failed", error=str(e))

        return results

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        source_context: str = "unknown"
    ) -> ToolExecutionResult:
        """
        Execute a tool from either SDK or MCP context.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            source_context: Context where tool is being called from

        Returns:
            ToolExecutionResult
        """
        logger.info(
            "Executing integrated tool",
            tool_name=tool_name,
            source=source_context
        )

        return await self.sdk_adapter_tool.execute_mcp_tool(
            tool_name,
            parameters
        )

    def get_available_tools(
        self,
        for_agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available tools for an agent or in general.

        Args:
            for_agent_id: Optional agent ID to filter by capabilities

        Returns:
            List of tool info dicts
        """
        tools = self.mcp_registry.list_tools()

        if for_agent_id:
            agent = self.sdk_adapter.sdk_agents.get(for_agent_id)
            if agent:
                # Filter to tools matching agent capabilities
                tools = [
                    t for t in tools
                    if any(cap in agent.capabilities for cap in t.capabilities)
                ]

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category.value,
                "source": tool.source.value,
                "capabilities": tool.capabilities,
                "parameters": tool.parameters
            }
            for tool in tools
            if tool.enabled
        ]

    async def invoke_agent_as_tool(
        self,
        agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke an SDK agent as if it were a tool.

        Args:
            agent_id: Agent to invoke
            task: Task description
            context: Optional context

        Returns:
            Execution result
        """
        return await self.mcp_bridge.invoke_agent(
            agent_id,
            task,
            context
        )

    def register_custom_tool(
        self,
        name: str,
        description: str,
        category: ToolCategory,
        handler: Callable,
        parameters: Dict[str, Any],
        returns: Dict[str, Any],
        capabilities: List[str]
    ) -> None:
        """
        Register a custom MCP tool.

        Args:
            name: Tool name
            description: Tool description
            category: Tool category
            handler: Async function to handle tool execution
            parameters: Parameter schema
            returns: Return value schema
            capabilities: Required capabilities
        """
        tool = ToolDefinition(
            name=name,
            description=description,
            source=ToolSource.MCP,
            category=category,
            parameters=parameters,
            returns=returns,
            handler=handler,
            capabilities=capabilities
        )

        self.mcp_registry.register_tool(tool)

        logger.info(
            "Custom tool registered",
            tool_name=name,
            category=category.value
        )


__all__ = [
    'ToolIntegrationLayer',
    'ToolDefinition',
    'ToolExecutionResult',
    'ToolSource',
    'ToolCategory',
    'MCPToolRegistry',
    'SDKToolAdapter',
    'MCPAgentBridge',
]
