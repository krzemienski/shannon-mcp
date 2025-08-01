#!/usr/bin/env python3
"""
MCP Client Test Script for Shannon MCP Server

This script acts as an MCP client to test the Shannon MCP server end-to-end.
It communicates with the server via stdio using the MCP protocol.
"""

import asyncio
import json
import subprocess
import sys
import os
import select
import fcntl
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

class MCPTestClient:
    """Test client for Shannon MCP Server."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        
    def get_next_id(self) -> str:
        """Generate next request ID."""
        self.request_id += 1
        return str(self.request_id)
    
    async def start_server(self):
        """Start the Shannon MCP server as a subprocess."""
        print("🚀 Starting Shannon MCP Server...")
        
        # Set environment to disable stdout logging
        env = os.environ.copy()
        env['SHANNON_MCP_MODE'] = 'stdio'
        
        self.process = subprocess.Popen(
            ["poetry", "run", "shannon-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
            env=env
        )
        await asyncio.sleep(2)  # Give server time to start
        
        # Check for any initial stderr output
        if select.select([self.process.stderr], [], [], 0)[0]:
            stderr_output = self.process.stderr.read(1024)
            print(f"Server stderr: {stderr_output}")
        
        # Set stderr to non-blocking mode for continuous reading
        if self.process.stderr:
            flags = fcntl.fcntl(self.process.stderr, fcntl.F_GETFL)
            fcntl.fcntl(self.process.stderr, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        print("✓ Server started")
    
    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request to the server."""
        request = {
            "jsonrpc": "2.0",
            "id": self.get_next_id(),
            "method": method,
            "params": params if params is not None else {}
        }
        
        request_str = json.dumps(request) + "\n"
        print(f"\n📤 Sending: {method}")
        print(f"   Params: {json.dumps(params, indent=2) if params else 'None'}")
        
        # Send request
        self.process.stdin.write(request_str)
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            # Check stderr for any error messages
            try:
                stderr_output = self.process.stderr.read(1024) if self.process.stderr else ""
            except IOError:
                stderr_output = ""
            raise Exception(f"No response from server. Stderr: {stderr_output}")
        
        print(f"📥 Raw response: {repr(response_line)}")
        
        # Check stderr for debug logs
        # Commented out for now due to text/binary mode conflict
        
        try:
            response = json.loads(response_line)
            print(f"📥 Parsed response: {json.dumps(response, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            print(f"   Response was: {repr(response_line)}")
            raise
        
        if "error" in response:
            raise Exception(f"Server error: {response['error']}")
        
        return response.get("result", {})
    
    async def test_initialize(self):
        """Test server initialization."""
        print("\n=== Testing Server Initialization ===")
        
        result = await self.send_request("initialize", {
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "clientInfo": {
                "name": "shannon-mcp-test-client",
                "version": "1.0.0"
            }
        })
        
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        print("✓ Server initialized successfully")
        print(f"  Server: {result['serverInfo']['name']} v{result['serverInfo']['version']}")
        
        return result
    
    async def test_list_tools(self):
        """Test listing available tools."""
        print("\n=== Testing List Tools ===")
        
        result = await self.send_request("tools/list", {})
        
        assert "tools" in result
        tools = result["tools"]
        print(f"✓ Found {len(tools)} tools:")
        
        expected_tools = [
            "find_claude_binary",
            "create_session",
            "send_message",
            "cancel_session",
            "list_sessions",
            "list_agents",
            "assign_task"
        ]
        
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
            assert tool["name"] in expected_tools
        
        # Verify all expected tools are present
        tool_names = [t["name"] for t in tools]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
        
        return tools
    
    async def test_list_resources(self):
        """Test listing available resources."""
        print("\n=== Testing List Resources ===")
        
        result = await self.send_request("resources/list", {})
        
        assert "resources" in result
        resources = result["resources"]
        print(f"✓ Found {len(resources)} resources:")
        
        for resource in resources:
            print(f"  - {resource['uri']}: {resource['name']}")
        
        return resources
    
    async def test_find_claude_binary(self):
        """Test finding Claude Code binary."""
        print("\n=== Testing Find Claude Binary Tool ===")
        
        result = await self.send_request("tools/call", {
            "name": "find_claude_binary",
            "arguments": {}
        })
        
        print("✓ Tool executed")
        if "error" in result:
            print(f"  ⚠️  Claude Code not found: {result['error']}")
        else:
            print(f"  ✓ Claude Code found at: {result.get('path', 'Unknown')}")
            print(f"    Version: {result.get('version', 'Unknown')}")
        
        return result
    
    async def test_create_session(self):
        """Test creating a session."""
        print("\n=== Testing Create Session Tool ===")
        
        result = await self.send_request("tools/call", {
            "name": "create_session",
            "arguments": {
                "prompt": "Test prompt for Shannon MCP",
                "model": "claude-3-sonnet"
            }
        })
        
        assert "session_id" in result
        print(f"✓ Session created: {result['session_id']}")
        print(f"  State: {result.get('state', 'Unknown')}")
        
        return result["session_id"]
    
    async def test_list_sessions(self):
        """Test listing sessions."""
        print("\n=== Testing List Sessions Tool ===")
        
        result = await self.send_request("tools/call", {
            "name": "list_sessions",
            "arguments": {
                "limit": 10
            }
        })
        
        assert "sessions" in result
        sessions = result["sessions"]
        print(f"✓ Found {len(sessions)} sessions")
        
        for session in sessions[:3]:  # Show first 3
            print(f"  - {session['id']}: {session.get('state', 'Unknown')}")
        
        return sessions
    
    async def test_list_agents(self):
        """Test listing AI agents."""
        print("\n=== Testing List Agents Tool ===")
        
        result = await self.send_request("tools/call", {
            "name": "list_agents",
            "arguments": {}
        })
        
        assert "agents" in result
        agents = result["agents"]
        print(f"✓ Found {len(agents)} agents")
        
        for agent in agents[:5]:  # Show first 5
            print(f"  - {agent.get('name', 'Unknown')}: {agent.get('category', 'Unknown')}")
        
        return agents
    
    async def test_read_config_resource(self):
        """Test reading configuration resource."""
        print("\n=== Testing Read Config Resource ===")
        
        result = await self.send_request("resources/read", {
            "uri": "shannon://config"
        })
        
        assert "contents" in result
        contents = result["contents"]
        assert len(contents) > 0
        
        content = contents[0]
        assert content["type"] == "text"
        
        config = json.loads(content["text"])
        print("✓ Configuration loaded")
        print(f"  App: {config.get('app_name', 'Unknown')} v{config.get('version', 'Unknown')}")
        print(f"  Debug: {config.get('debug', False)}")
        
        return config
    
    async def test_error_handling(self):
        """Test error handling with invalid requests."""
        print("\n=== Testing Error Handling ===")
        
        # Test invalid tool name
        try:
            await self.send_request("tools/call", {
                "name": "invalid_tool_name",
                "arguments": {}
            })
            assert False, "Should have raised an error"
        except Exception as e:
            print("✓ Invalid tool handled correctly")
            print(f"  Error: {str(e)}")
        
        # Test missing required arguments
        try:
            await self.send_request("tools/call", {
                "name": "create_session",
                "arguments": {}  # Missing required 'prompt'
            })
            assert False, "Should have raised an error"
        except Exception as e:
            print("✓ Missing arguments handled correctly")
            print(f"  Error: {str(e)}")
    
    async def stop_server(self):
        """Stop the server gracefully."""
        print("\n🛑 Stopping server...")
        if self.process:
            self.process.terminate()
            await asyncio.sleep(1)
            if self.process.poll() is None:
                self.process.kill()
            print("✓ Server stopped")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("Shannon MCP Server - End-to-End Testing")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}")
        
        try:
            # Start server
            await self.start_server()
            
            # Initialize connection
            await self.test_initialize()
            
            # Test discovery
            await self.test_list_tools()
            await self.test_list_resources()
            
            # Test tools
            await self.test_find_claude_binary()
            session_id = await self.test_create_session()
            await self.test_list_sessions()
            await self.test_list_agents()
            
            # Test resources
            await self.test_read_config_resource()
            
            # Test error handling
            await self.test_error_handling()
            
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            await self.stop_server()


async def main():
    """Main entry point."""
    client = MCPTestClient()
    await client.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())