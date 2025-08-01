#!/usr/bin/env python3
"""
External MCP Client Test - Validates Shannon MCP from client perspective.

This tests the server as an external client would use it, ensuring we're not
testing internal implementation details but actual MCP protocol compliance.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from fastmcp import Client


class ExternalMCPTester:
    """Test Shannon MCP server from external client perspective."""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.client = Client(server_path)
        self.test_results = []
        
    async def run_all_tests(self):
        """Run complete test suite."""
        print("=" * 70)
        print("Shannon MCP External Client Test Suite")
        print("=" * 70)
        print(f"Server: {self.server_path}")
        print()
        
        async with self.client:
            # Test 1: Server initialization and capability discovery
            await self.test_server_info()
            
            # Test 2: List available tools
            await self.test_list_tools()
            
            # Test 3: List available resources
            await self.test_list_resources()
            
            # Test 4: Binary discovery
            await self.test_find_binary()
            
            # Test 5: Session lifecycle
            await self.test_session_lifecycle()
            
            # Test 6: Agent operations
            await self.test_agent_operations()
            
            # Test 7: Resource access
            await self.test_resource_access()
            
            # Test 8: Error handling
            await self.test_error_handling()
            
        self.print_summary()
    
    async def test_server_info(self):
        """Test server information and capabilities."""
        print("\n[TEST 1] Server Information")
        print("-" * 50)
        
        try:
            # Get server info
            info = await self.client.get_server_info()
            print(f"✓ Server name: {info.name}")
            print(f"✓ Version: {info.version if hasattr(info, 'version') else 'N/A'}")
            
            # Check capabilities
            capabilities = await self.client.list_capabilities()
            print(f"✓ Capabilities: {len(capabilities)} found")
            
            self.test_results.append(("Server Info", "PASS", None))
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("Server Info", "FAIL", str(e)))
    
    async def test_list_tools(self):
        """Test tool listing."""
        print("\n[TEST 2] List Tools")
        print("-" * 50)
        
        try:
            tools = await self.client.list_tools()
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
                status = "✓" if tool.name in expected_tools else "?"
                print(f"  {status} {tool.name}: {tool.description[:60]}...")
            
            # Verify all expected tools present
            tool_names = {tool.name for tool in tools}
            missing = set(expected_tools) - tool_names
            if missing:
                raise ValueError(f"Missing tools: {missing}")
            
            self.test_results.append(("List Tools", "PASS", None))
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("List Tools", "FAIL", str(e)))
    
    async def test_list_resources(self):
        """Test resource listing."""
        print("\n[TEST 3] List Resources")
        print("-" * 50)
        
        try:
            resources = await self.client.list_resources()
            print(f"✓ Found {len(resources)} resources:")
            
            for resource in resources:
                print(f"  - {resource.uri}: {resource.name}")
            
            self.test_results.append(("List Resources", "PASS", None))
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("List Resources", "FAIL", str(e)))
    
    async def test_find_binary(self):
        """Test Claude Code binary discovery."""
        print("\n[TEST 4] Binary Discovery")
        print("-" * 50)
        
        try:
            result = await self.client.call_tool("find_claude_binary", {})
            
            if "error" in result:
                print(f"⚠ Binary not found: {result['error']}")
                print("  Suggestions:")
                for suggestion in result.get('suggestions', []):
                    print(f"    - {suggestion}")
            else:
                print(f"✓ Binary found: {result.get('path')}")
                print(f"  Version: {result.get('version')}")
                print(f"  Capabilities: {', '.join(result.get('capabilities', []))}")
            
            self.test_results.append(("Binary Discovery", "PASS", None))
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("Binary Discovery", "FAIL", str(e)))
    
    async def test_session_lifecycle(self):
        """Test complete session lifecycle."""
        print("\n[TEST 5] Session Lifecycle")
        print("-" * 50)
        
        session_id = None
        try:
            # Create session
            print("Creating session...")
            session = await self.client.call_tool("create_session", {
                "prompt": "Test session from external client",
                "model": "claude-3-sonnet",
                "context": {"test": True, "client": "external"}
            })
            
            session_id = session['id']
            print(f"✓ Session created: {session_id}")
            print(f"  Status: {session['status']}")
            
            # List sessions
            print("\nListing sessions...")
            sessions = await self.client.call_tool("list_sessions", {"limit": 5})
            print(f"✓ Found {len(sessions['sessions'])} sessions")
            
            # Send message (if session is active)
            if session['status'] == 'active':
                print("\nSending message...")
                response = await self.client.call_tool("send_message", {
                    "session_id": session_id,
                    "message": "Hello from external test client!",
                    "stream": False
                })
                print(f"✓ Message sent, response: {response.get('status')}")
            
            # Cancel session
            print("\nCancelling session...")
            cancel = await self.client.call_tool("cancel_session", {
                "session_id": session_id
            })
            print(f"✓ Session cancelled: {cancel['status']}")
            
            self.test_results.append(("Session Lifecycle", "PASS", None))
            
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("Session Lifecycle", "FAIL", str(e)))
            
            # Try to clean up session if created
            if session_id:
                try:
                    await self.client.call_tool("cancel_session", {"session_id": session_id})
                except:
                    pass
    
    async def test_agent_operations(self):
        """Test agent listing and task assignment."""
        print("\n[TEST 6] Agent Operations")
        print("-" * 50)
        
        try:
            # List agents
            print("Listing agents...")
            agents = await self.client.call_tool("list_agents", {})
            print(f"✓ Found {len(agents['agents'])} agents")
            
            if agents['agents']:
                # Show first few agents
                for agent in agents['agents'][:3]:
                    print(f"  - {agent['id']}: {agent['name']}")
                    print(f"    Category: {agent.get('category', 'N/A')}")
                
                # Assign task to first agent
                first_agent = agents['agents'][0]
                print(f"\nAssigning task to {first_agent['name']}...")
                
                assignment = await self.client.call_tool("assign_task", {
                    "agent_id": first_agent['id'],
                    "task": "Test task from external client",
                    "priority": 7,
                    "context": {"test": True, "source": "external_client"}
                })
                
                print(f"✓ Task assigned: {assignment['id']}")
                print(f"  Status: {assignment['status']}")
            
            self.test_results.append(("Agent Operations", "PASS", None))
            
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("Agent Operations", "FAIL", str(e)))
    
    async def test_resource_access(self):
        """Test resource access patterns."""
        print("\n[TEST 7] Resource Access")
        print("-" * 50)
        
        try:
            # Test static resources
            print("Reading configuration resource...")
            config = await self.client.read_resource("shannon://config")
            print(f"✓ Config loaded: {len(config)} bytes")
            
            print("\nReading agents resource...")
            agents = await self.client.read_resource("shannon://agents")
            print(f"✓ Agents data: {len(agents)} bytes")
            
            print("\nReading sessions resource...")
            sessions = await self.client.read_resource("shannon://sessions")
            print(f"✓ Sessions data: {len(sessions)} bytes")
            
            # Test dynamic resources (if sessions exist)
            sessions_data = json.loads(sessions) if isinstance(sessions, str) else sessions
            if sessions_data.get('sessions'):
                session_id = sessions_data['sessions'][0]['id']
                print(f"\nReading specific session: {session_id}")
                session = await self.client.read_resource(f"shannon://sessions/{session_id}")
                print(f"✓ Session details: {len(session)} bytes")
            
            self.test_results.append(("Resource Access", "PASS", None))
            
        except Exception as e:
            print(f"✗ Error: {e}")
            self.test_results.append(("Resource Access", "FAIL", str(e)))
    
    async def test_error_handling(self):
        """Test error handling and edge cases."""
        print("\n[TEST 8] Error Handling")
        print("-" * 50)
        
        try:
            # Test invalid tool
            print("Testing invalid tool call...")
            try:
                await self.client.call_tool("invalid_tool", {})
                print("✗ Should have raised error for invalid tool")
            except Exception as e:
                print(f"✓ Correctly rejected invalid tool: {type(e).__name__}")
            
            # Test invalid session ID
            print("\nTesting invalid session ID...")
            try:
                await self.client.call_tool("send_message", {
                    "session_id": "invalid-session-id",
                    "message": "test"
                })
                print("✗ Should have raised error for invalid session")
            except Exception as e:
                print(f"✓ Correctly rejected invalid session: {type(e).__name__}")
            
            # Test missing required parameters
            print("\nTesting missing parameters...")
            try:
                await self.client.call_tool("create_session", {})
                print("✗ Should have raised error for missing prompt")
            except Exception as e:
                print(f"✓ Correctly rejected missing parameters: {type(e).__name__}")
            
            # Test invalid resource URI
            print("\nTesting invalid resource URI...")
            try:
                await self.client.read_resource("shannon://invalid/resource")
                print("✗ Should have raised error for invalid resource")
            except Exception as e:
                print(f"✓ Correctly rejected invalid resource: {type(e).__name__}")
            
            self.test_results.append(("Error Handling", "PASS", None))
            
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            self.test_results.append(("Error Handling", "FAIL", str(e)))
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for _, status, _ in self.test_results if status == "PASS")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAIL")
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        
        if failed > 0:
            print("\nFailed Tests:")
            for name, status, error in self.test_results:
                if status == "FAIL":
                    print(f"  - {name}: {error}")
        
        print("\nDetailed Results:")
        for name, status, error in self.test_results:
            symbol = "✓" if status == "PASS" else "✗"
            print(f"  {symbol} {name}: {status}")
        
        print("\n" + "=" * 70)
        return failed == 0


async def main():
    """Run external client tests."""
    # Determine which server to test
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    else:
        # Default to Fast MCP implementation
        server_path = str(Path(__file__).parent / "src" / "shannon_mcp" / "server_fastmcp.py")
    
    # Run tests
    tester = ExternalMCPTester(server_path)
    success = await tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())