#!/usr/bin/env python3
"""
Simple MCP CLI - Direct method calls without stdio overhead.

This bypasses the stdio MCP protocol and calls the server methods directly.
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from shannon_mcp.server import ShannonMCPServer


async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Shannon MCP CLI - Simple direct interface"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Utility commands
    subparsers.add_parser("list-tools", help="List all available tools")

    # Binary management
    subparsers.add_parser("find-binary", help="Find Claude Code binary")

    # Session management
    session_create = subparsers.add_parser("create-session", help="Create a new session")
    session_create.add_argument("prompt", help="Initial prompt")
    session_create.add_argument("--model", default="claude-3-sonnet", help="Model to use")

    list_sess = subparsers.add_parser("list-sessions", help="List sessions")
    list_sess.add_argument("--limit", type=int, default=100, help="Maximum results")

    # Agent management
    list_ag = subparsers.add_parser("list-agents", help="List agents")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create server instance
    server = ShannonMCPServer()

    try:
        # Get the handlers
        list_tools_handler = None
        call_tool_handler = None

        # Access the registered handlers from the MCP server
        if hasattr(server.server, '_tool_handlers'):
            handlers = server.server._tool_handlers
        elif hasattr(server.server, '_request_handlers'):
            handlers = server.server._request_handlers
        else:
            # Try to find handlers another way
            handlers = {}

        # Execute command by simulating the MCP protocol
        if args.command == "list-tools":
            # Call the list_tools handler directly
            print("Attempting to list tools...")
            await server.initialize()

            # Get tools by calling the decorated function
            # We need to manually trigger the list_tools handler
            tools_result = await server.server._tool_handlers.get('list_tools', lambda: [])()

            tools = [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in tools_result
            ]
            print(json.dumps(tools, indent=2))

        elif args.command == "find-binary":
            await server.initialize()
            result = await server.managers['binary'].discover_binary()
            print(json.dumps(result.to_dict() if result else {"error": "Not found"}, indent=2))

        elif args.command == "list-sessions":
            await server.initialize()
            sessions = await server.managers['session'].list_sessions(limit=args.limit)
            print(json.dumps([s.to_dict() for s in sessions], indent=2))

        elif args.command == "list-agents":
            await server.initialize()
            agents = await server.managers['agent'].list_agents()
            print(json.dumps([a.to_dict() for a in agents], indent=2))

        elif args.command == "create-session":
            await server.initialize()
            session = await server.managers['session'].create_session(
                prompt=args.prompt,
                model=args.model
            )
            print(json.dumps(session.to_dict(), indent=2))

        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        await server.shutdown()


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
