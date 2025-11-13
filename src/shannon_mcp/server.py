"""
Shannon MCP Server - Main server implementation using MCP SDK 1.x API.

This is the core MCP server that orchestrates all components for managing
Claude Code CLI operations through the Model Context Protocol.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, Resource, TextContent, CallToolResult
import mcp.types as types
import mcp.server.stdio

from .managers.binary import BinaryManager
from .managers.session import SessionManager, SessionState
from .managers.agent import AgentManager, TaskRequest
from .managers.mcp_server import MCPServerManager
from .utils.config import load_config, get_config, ShannonConfig
from .utils.logging import setup_logging, get_logger
from .utils.notifications import setup_notifications

# Setup logging
setup_logging("shannon-mcp.server")
logger = get_logger("shannon-mcp.server")


class ShannonMCPServer:
    """Main MCP server coordinating all Claude Code operations."""

    def __init__(self):
        self.config: Optional[ShannonConfig] = None
        self.managers: Dict[str, Any] = {}
        self.initialized = False
        self.server = Server("shannon-mcp")

        # Register handlers using decorators
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP handlers using decorators."""

        # Register list_tools handler
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List all available tools."""
            return [
                types.Tool(
                    name="find_claude_binary",
                    description="Discover Claude Code installation on the system",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                types.Tool(
                    name="create_session",
                    description="Create a new Claude Code session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Initial prompt"},
                            "model": {"type": "string", "description": "Model to use", "default": "claude-3-sonnet"},
                            "checkpoint_id": {"type": "string", "description": "Optional checkpoint to restore from"},
                            "context": {"type": "object", "description": "Additional context"}
                        },
                        "required": ["prompt"]
                    }
                ),
                types.Tool(
                    name="send_message",
                    description="Send a message to an active session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Session ID"},
                            "content": {"type": "string", "description": "Message content"},
                            "timeout": {"type": "number", "description": "Optional timeout in seconds"}
                        },
                        "required": ["session_id", "content"]
                    }
                ),
                types.Tool(
                    name="cancel_session",
                    description="Cancel a running session",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Session ID to cancel"}
                        },
                        "required": ["session_id"]
                    }
                ),
                types.Tool(
                    name="list_sessions",
                    description="List active sessions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "state": {"type": "string", "description": "Filter by state"},
                            "limit": {"type": "integer", "description": "Maximum results", "default": 100}
                        },
                        "required": []
                    }
                ),
                types.Tool(
                    name="list_agents",
                    description="List available AI agents",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Filter by category"},
                            "status": {"type": "string", "description": "Filter by status"},
                            "capability": {"type": "string", "description": "Filter by capability"}
                        },
                        "required": []
                    }
                ),
                types.Tool(
                    name="assign_task",
                    description="Assign a task to an AI agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Task description"},
                            "required_capabilities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Required agent capabilities"
                            },
                            "priority": {"type": "string", "description": "Task priority", "default": "medium"},
                            "context": {"type": "object", "description": "Additional context"},
                            "timeout": {"type": "integer", "description": "Timeout in seconds"}
                        },
                        "required": ["description", "required_capabilities"]
                    }
                )
            ]

        # Register call_tool handler
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> types.CallToolResult:
            """Handle tool execution."""
            await self.initialize()

            try:
                if name == "find_claude_binary":
                    binary_info = await self.managers['binary'].discover_binary()
                    result = binary_info.to_dict() if binary_info else {"error": "Claude Code not found"}
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps(result, indent=2))]
                    )

                elif name == "create_session":
                    session = await self.managers['session'].create_session(
                        prompt=arguments["prompt"],
                        model=arguments.get("model", "claude-3-sonnet"),
                        checkpoint_id=arguments.get("checkpoint_id"),
                        context=arguments.get("context")
                    )
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps(session.to_dict(), indent=2))]
                    )

                elif name == "send_message":
                    await self.managers['session'].send_message(
                        session_id=arguments["session_id"],
                        content=arguments["content"],
                        timeout=arguments.get("timeout")
                    )
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps({"success": True}, indent=2))]
                    )

                elif name == "cancel_session":
                    await self.managers['session'].cancel_session(arguments["session_id"])
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps({"success": True}, indent=2))]
                    )

                elif name == "list_sessions":
                    session_state = SessionState(arguments["state"]) if arguments.get("state") else None
                    sessions = await self.managers['session'].list_sessions(
                        state=session_state,
                        limit=arguments.get("limit", 100)
                    )
                    result = [s.to_dict() for s in sessions]
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps(result, indent=2))]
                    )

                elif name == "list_agents":
                    agents = await self.managers['agent'].list_agents(
                        category=arguments.get("category"),
                        status=arguments.get("status"),
                        capability=arguments.get("capability")
                    )
                    result = [a.to_dict() for a in agents]
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps(result, indent=2))]
                    )

                elif name == "assign_task":
                    request = TaskRequest(
                        id="",  # Will be auto-generated
                        description=arguments["description"],
                        required_capabilities=arguments["required_capabilities"],
                        priority=arguments.get("priority", "medium"),
                        context=arguments.get("context", {}),
                        timeout=arguments.get("timeout")
                    )
                    assignment = await self.managers['agent'].assign_task(request)
                    result = {
                        "task_id": assignment.task_id,
                        "agent_id": assignment.agent_id,
                        "score": assignment.score,
                        "estimated_duration": assignment.estimated_duration,
                        "confidence": assignment.confidence
                    }
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps(result, indent=2))]
                    )

                else:
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))],
                        isError=True
                    )

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))],
                    isError=True
                )

        # Register list_resources handler
        @self.server.list_resources()
        async def handle_list_resources() -> List[types.Resource]:
            """List all available resources."""
            return [
                types.Resource(
                    uri="shannon://config",
                    name="Shannon MCP Configuration",
                    description="Current configuration settings",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="shannon://agents",
                    name="Available Agents",
                    description="List of AI agents",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="shannon://sessions",
                    name="Active Sessions",
                    description="List of active Claude Code sessions",
                    mimeType="application/json"
                )
            ]

        # Register read_resource handler
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a resource."""
            await self.initialize()

            try:
                if uri == "shannon://config":
                    return json.dumps(self.config.dict(), indent=2)

                elif uri == "shannon://agents":
                    agents = await self.managers['agent'].list_agents()
                    return json.dumps([a.to_dict() for a in agents], indent=2)

                elif uri == "shannon://sessions":
                    sessions = await self.managers['session'].list_sessions()
                    return json.dumps([s.to_dict() for s in sessions], indent=2)

                else:
                    raise ValueError(f"Unknown resource URI: {uri}")

            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}", exc_info=True)
                raise

    async def initialize(self):
        """Initialize all manager components."""
        if self.initialized:
            return

        logger.info("Initializing Shannon MCP Server...")

        # Load configuration
        self.config = await load_config()

        # Set up notifications
        await setup_notifications(self.config)

        # Initialize core managers
        self.managers['binary'] = BinaryManager(self.config.binary_manager)
        self.managers['session'] = SessionManager(
            self.config.session_manager,
            self.managers['binary']
        )
        self.managers['agent'] = AgentManager(self.config.agent_manager)
        self.managers['mcp_server'] = MCPServerManager(self.config.mcp)

        # Initialize all managers
        for name, manager in self.managers.items():
            await manager.initialize()
            logger.info(f"Initialized {name} manager")

        self.initialized = True
        logger.info("Shannon MCP Server initialized successfully")

    async def shutdown(self):
        """Graceful shutdown of all components."""
        logger.info("Shutting down Shannon MCP Server...")

        # Stop all managers
        for name, manager in self.managers.items():
            await manager.stop()
            logger.info(f"Stopped {name} manager")

        self.initialized = False
        logger.info("Shannon MCP Server shutdown complete")

    async def run(self):
        """Run the MCP server."""
        try:
            # Initialize server
            await self.initialize()

            # Create initialization options
            init_options = InitializationOptions(
                server_name="shannon-mcp",
                server_version=self.config.version if self.config else "0.1.0",
                capabilities={}
            )

            # Run server
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    init_options
                )
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()


# Global server instance
server_instance = ShannonMCPServer()


# Main entry point
def main():
    """Main entry point for the MCP server."""
    import sys

    # Setup asyncio event loop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Run the MCP server
    try:
        asyncio.run(server_instance.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
