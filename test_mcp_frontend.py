#!/usr/bin/env python3
"""
Simple MCP-based frontend test for Shannon MCP Claude Code integration.

This script demonstrates how to use the MCP tools we've implemented instead of
Tauri IPC commands. It replaces the frontend JavaScript logic with Python MCP calls.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any

# Import MCP client (we'll use a simple subprocess approach for now)
import subprocess
import sys
import time


class MCPClaudeClient:
    """
    Simple MCP client to test Claude Code session management tools.
    
    This replaces the Tauri frontend functionality with direct MCP calls.
    """
    
    def __init__(self, mcp_server_path: str = None):
        self.mcp_server_path = mcp_server_path or "uv run shannon-mcp"
        self.session_id = None
        
    async def call_mcp_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an MCP tool and return the result."""
        try:
            # For now, we'll use a simple approach - in production this would use proper MCP protocol
            cmd = [
                "python", "-c", f"""
import asyncio
import sys
sys.path.append('/home/nick/shannon-mcp/src')

from shannon_mcp.server_fastmcp import {tool_name}

async def main():
    try:
        result = await {tool_name}({', '.join(f'{k}={repr(v)}' for k, v in kwargs.items())})
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))

if __name__ == "__main__":
    import json
    asyncio.run(main())
"""
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return json.loads(stdout.decode())
            else:
                return {"error": f"Process failed: {stderr.decode()}"}
                
        except Exception as e:
            return {"error": f"Failed to call MCP tool: {str(e)}"}
    
    async def start_claude_session(self, project_path: str, prompt: str, model: str = "sonnet") -> Dict[str, Any]:
        """Start a new Claude Code session (replaces Claudia's execute_claude_code)."""
        print(f"🚀 Starting Claude session in {project_path}")
        result = await self.call_mcp_tool("start_claude_session", 
                                        project_path=project_path, 
                                        prompt=prompt, 
                                        model=model)
        
        if "session_id" in result:
            self.session_id = result["session_id"]
            print(f"✅ Session started: {self.session_id}")
        else:
            print(f"❌ Failed to start session: {result.get('error', 'Unknown error')}")
            
        return result
    
    async def continue_claude_session(self, prompt: str, model: str = "sonnet") -> Dict[str, Any]:
        """Continue the current session (replaces Claudia's continue_claude_code)."""
        if not self.session_id:
            return {"error": "No active session"}
            
        print(f"📝 Continuing session {self.session_id}")
        result = await self.call_mcp_tool("continue_claude_session",
                                        session_id=self.session_id,
                                        prompt=prompt,
                                        model=model)
        
        if result.get("status") == "continued":
            print("✅ Session continued successfully")
        else:
            print(f"❌ Failed to continue session: {result.get('error', 'Unknown error')}")
            
        return result
    
    async def list_claude_sessions(self, project_path: str = None) -> Dict[str, Any]:
        """List Claude sessions (replaces Claudia's get_project_sessions)."""
        print("📋 Listing Claude sessions")
        result = await self.call_mcp_tool("list_claude_sessions", project_path=project_path)
        
        if "sessions" in result:
            print(f"✅ Found {len(result['sessions'])} sessions")
        else:
            print(f"❌ Failed to list sessions: {result.get('error', 'Unknown error')}")
            
        return result
    
    async def get_session_history(self, session_id: str = None) -> Dict[str, Any]:
        """Get session history (replaces Claudia's load_session_history)."""
        session_id = session_id or self.session_id
        if not session_id:
            return {"error": "No session ID provided"}
            
        print(f"📚 Getting history for session {session_id}")
        result = await self.call_mcp_tool("get_claude_session_history", session_id=session_id)
        
        if "history" in result:
            print("✅ Retrieved session history")
        else:
            print(f"❌ Failed to get history: {result.get('error', 'Unknown error')}")
            
        return result
    
    async def stop_claude_session(self, session_id: str = None) -> Dict[str, Any]:
        """Stop a Claude session (replaces Claudia's cancel_claude_execution)."""
        session_id = session_id or self.session_id
        if not session_id:
            return {"error": "No session ID provided"}
            
        print(f"🛑 Stopping session {session_id}")
        result = await self.call_mcp_tool("stop_claude_session", session_id=session_id)
        
        if result.get("status") == "stopped":
            print("✅ Session stopped successfully")
            if session_id == self.session_id:
                self.session_id = None
        else:
            print(f"❌ Failed to stop session: {result.get('error', 'Unknown error')}")
            
        return result


async def test_mcp_claude_integration():
    """
    Test the MCP Claude Code integration end-to-end.
    
    This simulates what the frontend would do, but using MCP tools instead of Tauri IPC.
    """
    print("🧪 Testing Shannon MCP Claude Code Integration")
    print("=" * 50)
    
    # Create a temporary test project
    with tempfile.TemporaryDirectory() as temp_dir:
        test_project = Path(temp_dir) / "test_project"
        test_project.mkdir()
        
        # Create a simple test file
        test_file = test_project / "test.py"
        test_file.write_text("""
# Simple test file for Claude Code
def hello_world():
    print("Hello from Shannon MCP!")

if __name__ == "__main__":
    hello_world()
""")
        
        print(f"📁 Created test project: {test_project}")
        
        # Initialize MCP client
        client = MCPClaudeClient()
        
        # Test 1: Start a new Claude session
        print("\n🧪 Test 1: Starting Claude session")
        result = await client.start_claude_session(
            project_path=str(test_project),
            prompt="Analyze this Python file and suggest improvements",
            model="sonnet"
        )
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Test 2: List sessions
        print("\n🧪 Test 2: Listing sessions")
        result = await client.list_claude_sessions(project_path=str(test_project))
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Test 3: Continue the session (simulate user interaction)
        print("\n🧪 Test 3: Continuing session")
        result = await client.continue_claude_session(
            prompt="Add error handling to the hello_world function"
        )
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Test 4: Get session history
        print("\n🧪 Test 4: Getting session history")
        result = await client.get_session_history()
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Test 5: Stop the session
        print("\n🧪 Test 5: Stopping session")
        result = await client.stop_claude_session()
        print(f"Result: {json.dumps(result, indent=2)}")
        
        print("\n✅ MCP Claude Code integration test completed!")


async def test_mcp_tools_exist():
    """Test that our MCP tools are properly defined."""
    print("🔍 Testing MCP tool availability")
    
    try:
        # Import the server module to check tools exist
        sys.path.append('/home/nick/shannon-mcp/src')
        from shannon_mcp.server_fastmcp import (
            start_claude_session,
            continue_claude_session, 
            resume_claude_session,
            stop_claude_session,
            list_claude_sessions,
            get_claude_session_history
        )
        
        print("✅ All MCP Claude session tools are available:")
        print("  - start_claude_session")
        print("  - continue_claude_session") 
        print("  - resume_claude_session")
        print("  - stop_claude_session")
        print("  - list_claude_sessions")
        print("  - get_claude_session_history")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import MCP tools: {e}")
        return False


if __name__ == "__main__":
    print("Shannon MCP Claude Code Integration Test")
    print("=" * 50)
    
    # First test that tools exist
    if asyncio.run(test_mcp_tools_exist()):
        # Then run the integration test
        asyncio.run(test_mcp_claude_integration())
    else:
        print("💥 Cannot run integration test - MCP tools not available")
        sys.exit(1)