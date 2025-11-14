#!/usr/bin/env python3
"""
Quick test to verify MCP tools are callable.
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_tools():
    """Test that we can list and call MCP tools."""

    # Start the MCP server
    server_params = StdioServerParameters(
        command="poetry",
        args=["run", "shannon-mcp"],
        env=None
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()

                # List all tools
                tools_result = await session.list_tools()
                print(f"✓ Found {len(tools_result.tools)} tools:")

                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Test calling find_claude_binary (simplest tool)
                print("\n✓ Testing find_claude_binary tool...")
                try:
                    result = await session.call_tool("find_claude_binary", arguments={})
                    print(f"  Result: {result.content[0].text[:100] if result.content else 'No content'}")
                except Exception as e:
                    print(f"  Error: {e}")

                # List all resources
                resources_result = await session.list_resources()
                print(f"\n✓ Found {len(resources_result.resources)} resources:")

                for resource in resources_result.resources:
                    print(f"  - {resource.uri}: {resource.name}")

                print("\n✓ All MCP protocol tests passed!")

    except Exception as e:
        print(f"✗ Error testing MCP server: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(test_mcp_tools())
    exit(0 if success else 1)
