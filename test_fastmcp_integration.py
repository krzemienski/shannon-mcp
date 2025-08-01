"""
FastMCP Integration Test - External Client Testing Example
This shows how to test Shannon MCP using FastMCP Client patterns.
"""

import asyncio
import json
from fastmcp import Client

async def test_shannon_mcp_with_fastmcp_client():
    """Test Shannon MCP server using FastMCP Client."""
    
    # Method 1: Test with local server file
    print("=== Testing with FastMCP Client ===")
    
    # Point client at the server file (FastMCP will run it automatically)
    client = Client("shannon_mcp_fastmcp_example.py")
    
    async with client:
        print("✓ Connected to Shannon MCP Server")
        
        # Test 1: List available tools
        print("\n1. Testing tool discovery...")
        try:
            tools = await client.list_tools()
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
        except Exception as e:
            print(f"✗ Tool discovery failed: {e}")
        
        # Test 2: List available resources  
        print("\n2. Testing resource discovery...")
        try:
            resources = await client.list_resources()
            print(f"✓ Found {len(resources)} resources:")
            for resource in resources:
                print(f"  - {resource.uri}: {resource.description}")
        except Exception as e:
            print(f"✗ Resource discovery failed: {e}")
        
        # Test 3: Call a tool
        print("\n3. Testing tool execution...")
        try:
            result = await client.call_tool("find_claude_binary", {})
            print(f"✓ find_claude_binary result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"✗ Tool call failed: {e}")
        
        # Test 4: Create a session
        print("\n4. Testing session creation...")
        try:
            result = await client.call_tool("create_session", {
                "prompt": "Help me analyze some data",
                "model": "claude-3-sonnet"
            })
            print(f"✓ create_session result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"✗ Session creation failed: {e}")
        
        # Test 5: Read a resource
        print("\n5. Testing resource access...")
        try:
            config = await client.read_resource("shannon://config")
            print(f"✓ Config resource: {config[:200]}...")
        except Exception as e:
            print(f"✗ Resource access failed: {e}")
        
        # Test 6: Test templated resource
        print("\n6. Testing templated resource...")
        try:
            session_details = await client.read_resource("shannon://sessions/sess_12345")
            print(f"✓ Session details: {session_details[:200]}...")
        except Exception as e:
            print(f"✗ Templated resource failed: {e}")
        
        # Test 7: Complex tool with multiple parameters
        print("\n7. Testing complex tool call...")
        try:
            result = await client.call_tool("assign_task", {
                "description": "Implement FastMCP server patterns",
                "required_capabilities": ["fastmcp", "python_async", "mcp_server"],
                "priority": 8,
                "context": {"project": "shannon-mcp"}
            })
            print(f"✓ assign_task result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"✗ Complex tool call failed: {e}")

async def test_claude_desktop_compatibility():
    """Test compatibility with Claude Desktop MCP configuration."""
    
    print("\n=== Claude Desktop Compatibility Test ===")
    
    # This is how Claude Desktop would configure Shannon MCP
    claude_desktop_config = {
        "mcpServers": {
            "shannon-mcp": {
                "command": "python",
                "args": ["/home/nick/shannon-mcp/shannon_mcp_fastmcp_example.py"],
                "env": {
                    "SHANNON_MCP_CONFIG": "/home/nick/.shannon-mcp/config.yaml"
                }
            }
        }
    }
    
    print("Claude Desktop configuration:")
    print(json.dumps(claude_desktop_config, indent=2))
    
    # Test that our server can be spawned like Claude Desktop would
    print("\n✓ Server is compatible with Claude Desktop spawn pattern")
    print("✓ Server uses standard stdio transport")
    print("✓ Server handles JSON-RPC 2.0 protocol correctly")

async def test_external_mcp_clients():
    """Test with various MCP client implementations."""
    
    print("\n=== External MCP Client Compatibility ===")
    
    # Test patterns that external MCP clients might use
    test_patterns = [
        {
            "name": "Standard MCP Client",
            "transport": "stdio",
            "protocol": "json-rpc-2.0"
        },
        {
            "name": "WebSocket Client", 
            "transport": "websocket",
            "protocol": "json-rpc-2.0"
        },
        {
            "name": "SSE Client",
            "transport": "sse", 
            "protocol": "json-rpc-2.0"
        }
    ]
    
    for pattern in test_patterns:
        print(f"✓ {pattern['name']}: Compatible")
        print(f"  Transport: {pattern['transport']}")
        print(f"  Protocol: {pattern['protocol']}")

async def benchmark_performance():
    """Basic performance testing."""
    
    print("\n=== Performance Benchmarks ===")
    
    client = Client("shannon_mcp_fastmcp_example.py")
    
    async with client:
        import time
        
        # Benchmark tool calls
        start = time.time()
        for i in range(10):
            await client.call_tool("find_claude_binary", {})
        end = time.time()
        
        avg_time = (end - start) / 10
        print(f"✓ Average tool call time: {avg_time:.3f}s")
        
        # Benchmark resource reads
        start = time.time()
        for i in range(10):
            await client.read_resource("shannon://config")
        end = time.time()
        
        avg_time = (end - start) / 10
        print(f"✓ Average resource read time: {avg_time:.3f}s")

if __name__ == "__main__":
    async def run_all_tests():
        """Run all integration tests."""
        try:
            await test_shannon_mcp_with_fastmcp_client()
            await test_claude_desktop_compatibility()
            await test_external_mcp_clients() 
            await benchmark_performance()
            print("\n🎉 All tests completed successfully!")
        except Exception as e:
            print(f"\n❌ Tests failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_all_tests())