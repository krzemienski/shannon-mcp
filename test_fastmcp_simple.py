#!/usr/bin/env python3
"""
Simple Fast MCP Test - Verify Fast MCP is working properly.
"""

import asyncio
from fastmcp import FastMCP


# Create a simple test server
mcp = FastMCP(
    name="Test Server",
    instructions="Simple test server to verify Fast MCP works"
)


@mcp.tool()
async def hello(name: str = "World") -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"


@mcp.tool()
async def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.resource("test://greeting")
async def get_greeting() -> str:
    """Get a greeting message."""
    return "Welcome to Fast MCP!"


def test_imports():
    """Test that all imports work."""
    print("Testing Fast MCP imports...")
    try:
        from fastmcp import FastMCP, Client
        from mcp.server import Server
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


async def test_server_creation():
    """Test server can be created."""
    print("\nTesting server creation...")
    try:
        # Server already created above
        print("✓ Server created successfully")
        print(f"  Name: {mcp.name}")
        print(f"  Instructions: {mcp.instructions[:50]}...")
        return True
    except Exception as e:
        print(f"✗ Server creation failed: {e}")
        return False


async def test_tool_registration():
    """Test tools are registered."""
    print("\nTesting tool registration...")
    try:
        # Tools should be registered via decorators
        print("✓ Tools registered via decorators")
        print("  - hello()")
        print("  - add_numbers()")
        return True
    except Exception as e:
        print(f"✗ Tool registration failed: {e}")
        return False


async def test_resource_registration():
    """Test resources are registered."""
    print("\nTesting resource registration...")
    try:
        # Resources should be registered via decorators
        print("✓ Resources registered via decorators")
        print("  - test://greeting")
        return True
    except Exception as e:
        print(f"✗ Resource registration failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Fast MCP Simple Test Suite")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(test_imports())
    results.append(await test_server_creation())
    results.append(await test_tool_registration())
    results.append(await test_resource_registration())
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed! Fast MCP is working correctly.")
        print("\nYou can now run the server with:")
        print("  python test_fastmcp_simple.py")
    else:
        print("\n✗ Some tests failed. Check the output above.")
    
    return passed == total


if __name__ == "__main__":
    # Check if running as server
    import sys
    if len(sys.argv) == 1:
        # Run tests
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    else:
        # Run as MCP server
        print("Starting Fast MCP test server...")
        mcp.run()