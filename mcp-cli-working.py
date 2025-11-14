#!/usr/bin/env python3
"""
Shannon MCP CLI - Working version without full server initialization.

This CLI provides direct access to MCP tools without requiring full
manager initialization, which prevents background task hangs.
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


async def list_tools_cmd():
    """List all available MCP tools."""
    tools = [
        {
            "name": "find_claude_binary",
            "description": "Discover Claude Code installation on the system"
        },
        {
            "name": "create_session",
            "description": "Create a new Claude Code session"
        },
        {
            "name": "send_message",
            "description": "Send a message to an active session"
        },
        {
            "name": "cancel_session",
            "description": "Cancel a running session"
        },
        {
            "name": "list_sessions",
            "description": "List active sessions"
        },
        {
            "name": "list_agents",
            "description": "List available AI agents"
        },
        {
            "name": "assign_task",
            "description": "Assign a task to an AI agent"
        }
    ]
    print(json.dumps(tools, indent=2))


async def list_resources_cmd():
    """List all available MCP resources."""
    resources = [
        {
            "uri": "shannon://config",
            "name": "Shannon MCP Configuration",
            "description": "Current configuration settings"
        },
        {
            "uri": "shannon://agents",
            "name": "Available Agents",
            "description": "List of AI agents"
        },
        {
            "uri": "shannon://sessions",
            "name": "Active Sessions",
            "description": "List of active Claude Code sessions"
        }
    ]
    print(json.dumps(resources, indent=2))


async def test_tool_cmd(tool_name: str):
    """Test that a tool exists."""
    tools = ["find_claude_binary", "create_session", "send_message",
             "cancel_session", "list_sessions", "list_agents", "assign_task"]

    if tool_name in tools:
        print(json.dumps({
            "tool": tool_name,
            "status": "available",
            "note": "Tool is defined in MCP server but requires full initialization to execute"
        }, indent=2))
    else:
        print(json.dumps({
            "tool": tool_name,
            "status": "not_found",
            "error": f"Tool '{tool_name}' not found in MCP server"
        }, indent=2))
        sys.exit(1)


async def server_status_cmd():
    """Show server status."""
    status = {
        "server": "Shannon MCP Server",
        "version": "0.1.0",
        "tools": 7,
        "resources": 3,
        "status": "defined",
        "note": "Server tools are defined. Full initialization blocked by background task hangs.",
        "tools_list": [
            "find_claude_binary",
            "create_session",
            "send_message",
            "cancel_session",
            "list_sessions",
            "list_agents",
            "assign_task"
        ],
        "resources_list": [
            "shannon://config",
            "shannon://agents",
            "shannon://sessions"
        ]
    }
    print(json.dumps(status, indent=2))


async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Shannon MCP CLI - Lightweight tool access"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Utility commands
    subparsers.add_parser("list-tools", help="List all available tools")
    subparsers.add_parser("list-resources", help="List all available resources")
    subparsers.add_parser("status", help="Show server status")

    # Test command
    test_parser = subparsers.add_parser("test-tool", help="Test if a tool exists")
    test_parser.add_argument("tool_name", help="Name of the tool to test")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "list-tools":
            await list_tools_cmd()
        elif args.command == "list-resources":
            await list_resources_cmd()
        elif args.command == "status":
            await server_status_cmd()
        elif args.command == "test-tool":
            await test_tool_cmd(args.tool_name)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
