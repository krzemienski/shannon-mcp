#!/usr/bin/env python3
"""
Working Fast MCP Test - Properly handles Fast MCP client/server communication.
"""

import asyncio
import json
from fastmcp import Client
from pathlib import Path


async def test_fastmcp_server():
    """Test Fast MCP server with proper response handling."""
    print("=" * 60)
    print("Fast MCP Server Test")
    print("=" * 60)
    
    # Use the minimal test server
    client = Client("test_server_minimal.py")
    
    async with client:
        print("\n1. Testing tool listing...")
        try:
            tools = await client.list_tools()
            print(f"✓ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n2. Testing resource listing...")
        try:
            resources = await client.list_resources()
            print(f"✓ Found {len(resources)} resources:")
            for res in resources:
                print(f"  - {res.uri}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n3. Testing binary discovery...")
        try:
            # Call tool and get the actual result
            result = await client.call_tool("find_claude_binary", {})
            # Access the data property of CallToolResult
            data = result.data
            print(f"✓ Binary status: {data.get('status', 'unknown') if data else 'no data'}")
            if data.get('status') == 'found':
                print(f"  Path: {data['binary']['path']}")
                print(f"  Version: {data['binary']['version']}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n4. Testing session creation...")
        session_id = None
        try:
            result = await client.call_tool("create_session", {
                "prompt": "Test session from Fast MCP client"
            })
            data = result.data
            if 'session' in data:
                session_id = data['session']['id']
                print(f"✓ Session created: {session_id}")
                print(f"  Status: {data['session']['status']}")
            else:
                # Try direct access
                session_id = data.get('id')
                print(f"✓ Session created: {session_id}")
                print(f"  Status: {data.get('status')}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n5. Testing session listing...")
        try:
            result = await client.call_tool("list_sessions", {"limit": 5})
            data = result.data
            sessions = data['sessions']
            print(f"✓ Found {len(sessions)} sessions")
            for session in sessions[:3]:
                print(f"  - {session['id']}: {session['status']}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n6. Testing agent listing...")
        try:
            result = await client.call_tool("list_agents", {})
            data = result.data
            agents = data['agents']
            print(f"✓ Found {len(agents)} agents")
            for agent in agents:
                print(f"  - {agent['id']}: {agent['name']}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n7. Testing resource reading...")
        try:
            # Read config resource
            config_result = await client.read_resource("shannon://config")
            # Fast MCP client returns the text content directly
            config = config_result
            print(f"✓ Config resource: {len(config)} bytes")
            
            # Read agents resource
            agents_result = await client.read_resource("shannon://agents")
            # Fast MCP returns the actual content
            agents = agents_result
            agents_data = json.loads(agents)
            print(f"✓ Agents resource: {len(agents_data['agents'])} agents")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n8. Testing error handling...")
        try:
            await client.call_tool("invalid_tool", {})
            print("✗ Should have raised an error")
        except Exception as e:
            print(f"✓ Correctly raised error: {type(e).__name__}")
        
        # Cleanup
        if session_id:
            try:
                result = await client.call_tool("cancel_session", {"session_id": session_id})
                print(f"\n✓ Cleaned up session: {session_id}")
            except:
                pass
    
    print("\n" + "=" * 60)
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(test_fastmcp_server())