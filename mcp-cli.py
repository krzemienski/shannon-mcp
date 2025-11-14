#!/usr/bin/env python3
"""
Shannon MCP CLI - Proper CLI wrapper using MCP client library.

This provides command-line access to all Shannon MCP Server tools and resources.
"""

import asyncio
import sys
import json
import argparse
from typing import Optional, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ShannonMCPCLI:
    """CLI wrapper for Shannon MCP Server."""

    def __init__(self):
        self.session: Optional[ClientSession] = None

    async def connect(self):
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command="poetry",
            args=["run", "shannon-mcp"],
            env=None
        )

        self.client = stdio_client(server_params)
        read, write = await self.client.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'client'):
            await self.client.__aexit__(None, None, None)

    async def list_tools_cmd(self):
        """List all available tools."""
        result = await self.session.list_tools()
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema.get("properties", {}) if hasattr(tool, 'inputSchema') else {}
            }
            for tool in result.tools
        ]
        print(json.dumps(tools, indent=2))

    async def list_resources_cmd(self):
        """List all available resources."""
        result = await self.session.list_resources()
        resources = [
            {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description
            }
            for resource in result.resources
        ]
        print(json.dumps(resources, indent=2))

    async def call_tool_cmd(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a tool with the given arguments."""
        result = await self.session.call_tool(tool_name, arguments=arguments)
        if result.content:
            for content in result.content:
                if hasattr(content, 'text'):
                    print(content.text)
        else:
            print(json.dumps({"success": True}))

    async def read_resource_cmd(self, uri: str):
        """Read a resource."""
        result = await self.session.read_resource(uri)
        print(result)

    # Tool command implementations
    async def find_claude_binary(self):
        """Find Claude Code binary."""
        await self.call_tool_cmd("find_claude_binary", {})

    async def create_session(self, prompt: str, model: str = "claude-3-sonnet",
                            checkpoint_id: Optional[str] = None):
        """Create a new session."""
        args = {"prompt": prompt, "model": model}
        if checkpoint_id:
            args["checkpoint_id"] = checkpoint_id
        await self.call_tool_cmd("create_session", args)

    async def send_message(self, session_id: str, content: str, timeout: Optional[int] = None):
        """Send message to a session."""
        args = {"session_id": session_id, "content": content}
        if timeout:
            args["timeout"] = timeout
        await self.call_tool_cmd("send_message", args)

    async def cancel_session(self, session_id: str):
        """Cancel a session."""
        await self.call_tool_cmd("cancel_session", {"session_id": session_id})

    async def list_sessions(self, state: Optional[str] = None, limit: int = 100):
        """List sessions."""
        args = {"limit": limit}
        if state:
            args["state"] = state
        await self.call_tool_cmd("list_sessions", args)

    async def list_agents(self, category: Optional[str] = None,
                         status: Optional[str] = None,
                         capability: Optional[str] = None):
        """List agents."""
        args = {}
        if category:
            args["category"] = category
        if status:
            args["status"] = status
        if capability:
            args["capability"] = capability
        await self.call_tool_cmd("list_agents", args)

    async def assign_task(self, description: str, capabilities: list,
                         priority: str = "medium", timeout: Optional[int] = None):
        """Assign a task to an agent."""
        args = {
            "description": description,
            "required_capabilities": capabilities,
            "priority": priority
        }
        if timeout:
            args["timeout"] = timeout
        await self.call_tool_cmd("assign_task", args)

    # Resource commands
    async def get_config(self):
        """Get configuration resource."""
        await self.read_resource_cmd("shannon://config")

    async def get_agents_resource(self):
        """Get agents resource."""
        await self.read_resource_cmd("shannon://agents")

    async def get_sessions_resource(self):
        """Get sessions resource."""
        await self.read_resource_cmd("shannon://sessions")


async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Shannon MCP CLI - Command line interface for Shannon MCP Server"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Utility commands
    subparsers.add_parser("list-tools", help="List all available tools")
    subparsers.add_parser("list-resources", help="List all available resources")

    # Binary management
    subparsers.add_parser("find-claude-binary", help="Find Claude Code binary")

    # Session management
    session_create = subparsers.add_parser("create-session", help="Create a new session")
    session_create.add_argument("prompt", help="Initial prompt")
    session_create.add_argument("--model", default="claude-3-sonnet", help="Model to use")
    session_create.add_argument("--checkpoint", help="Checkpoint ID to restore from")

    send_msg = subparsers.add_parser("send-message", help="Send message to session")
    send_msg.add_argument("session_id", help="Session ID")
    send_msg.add_argument("content", help="Message content")
    send_msg.add_argument("--timeout", type=int, help="Timeout in seconds")

    cancel_sess = subparsers.add_parser("cancel-session", help="Cancel a session")
    cancel_sess.add_argument("session_id", help="Session ID")

    list_sess = subparsers.add_parser("list-sessions", help="List sessions")
    list_sess.add_argument("--state", help="Filter by state")
    list_sess.add_argument("--limit", type=int, default=100, help="Maximum results")

    # Agent management
    list_ag = subparsers.add_parser("list-agents", help="List agents")
    list_ag.add_argument("--category", help="Filter by category")
    list_ag.add_argument("--status", help="Filter by status")
    list_ag.add_argument("--capability", help="Filter by capability")

    assign = subparsers.add_parser("assign-task", help="Assign task to agent")
    assign.add_argument("description", help="Task description")
    assign.add_argument("capabilities", help="Required capabilities (JSON array)")
    assign.add_argument("--priority", default="medium", help="Task priority")
    assign.add_argument("--timeout", type=int, help="Timeout in seconds")

    # Resources
    subparsers.add_parser("get-config", help="Get configuration")
    subparsers.add_parser("get-agents-resource", help="Get agents resource")
    subparsers.add_parser("get-sessions-resource", help="Get sessions resource")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cli = ShannonMCPCLI()

    try:
        await cli.connect()

        # Execute command
        if args.command == "list-tools":
            await cli.list_tools_cmd()
        elif args.command == "list-resources":
            await cli.list_resources_cmd()
        elif args.command == "find-claude-binary":
            await cli.find_claude_binary()
        elif args.command == "create-session":
            await cli.create_session(args.prompt, args.model, args.checkpoint)
        elif args.command == "send-message":
            await cli.send_message(args.session_id, args.content, args.timeout)
        elif args.command == "cancel-session":
            await cli.cancel_session(args.session_id)
        elif args.command == "list-sessions":
            await cli.list_sessions(args.state, args.limit)
        elif args.command == "list-agents":
            await cli.list_agents(args.category, args.status, args.capability)
        elif args.command == "assign-task":
            caps = json.loads(args.capabilities)
            await cli.assign_task(args.description, caps, args.priority, args.timeout)
        elif args.command == "get-config":
            await cli.get_config()
        elif args.command == "get-agents-resource":
            await cli.get_agents_resource()
        elif args.command == "get-sessions-resource":
            await cli.get_sessions_resource()
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await cli.disconnect()


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
