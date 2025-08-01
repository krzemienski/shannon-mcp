#!/usr/bin/env python3
"""Test Shannon MCP binary discovery tools specifically."""

import subprocess
import json
import sys
import os
import asyncio
import time

class SimpleMCPClient:
    def __init__(self):
        self.server_process = None
        self.request_id = 0
        
    async def start_server(self):
        """Start Shannon MCP server in stdio mode."""
        print("Starting Shannon MCP server...")
        
        env = os.environ.copy()
        env["SHANNON_MCP_MODE"] = "stdio"
        env["PYTHONUNBUFFERED"] = "1"
        env["FASTMCP_NO_LOG_SETUP"] = "1"
        
        self.server_process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "shannon_mcp.stdio_wrapper",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        print(f"Server PID: {self.server_process.pid}")
        
        # Wait for server to start and initialize
        await asyncio.sleep(5)  # Give more time for initialization
        
        # Check if still running
        if self.server_process.returncode is not None:
            stderr = await self.server_process.stderr.read()
            print(f"Server exited with code: {self.server_process.returncode}")
            print(f"Stderr: {stderr.decode()[:500]}")
            return False
            
        # Start background task to monitor stderr
        asyncio.create_task(self._monitor_stderr())
            
        return True
    
    async def _monitor_stderr(self):
        """Monitor stderr output from server."""
        try:
            while self.server_process and self.server_process.stderr:
                line = await self.server_process.stderr.readline()
                if line:
                    print(f"[STDERR] {line.decode().strip()}")
                else:
                    break
        except:
            pass
        
    async def send_request(self, method, params=None):
        """Send JSON-RPC request and wait for response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": str(self.request_id),
            "method": method
        }
        if params:
            request["params"] = params
            
        # Send request
        request_json = json.dumps(request) + "\n"
        print(f"\nSending: {method}")
        self.server_process.stdin.write(request_json.encode())
        await self.server_process.stdin.drain()
        
        # Read response with proper async handling
        start_time = time.time()
        while time.time() - start_time < 10:
            # Read directly without wait_for to avoid timeout issues
            line_bytes = await self.server_process.stdout.readline()
            
            if not line_bytes:
                await asyncio.sleep(0.1)  # Small delay before retry
                continue
                
            line = line_bytes.decode().strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip non-JSON lines
            if not line.startswith('{'):
                print(f"  Skipping non-JSON: {line[:80]}...")
                continue
                
            # Try to parse JSON
            try:
                response = json.loads(line)
                if response.get("id") == str(self.request_id):
                    print(f"  Got response for request {self.request_id}")
                    return response
            except json.JSONDecodeError as e:
                print(f"  JSON decode error: {e}")
                continue
                
        raise Exception("Timeout waiting for response")
        
    async def test_binary_discovery(self):
        """Test binary discovery functionality."""
        print("\n=== Testing Binary Discovery ===")
        
        # Initialize connection
        print("\nInitializing connection...")
        response = await self.send_request("initialize", {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0"
            }
        })
        
        if "error" in response:
            print(f"Initialize error: {response['error']}")
            return
            
        print("✓ Initialized successfully")
        
        # Send initialized notification
        await self.server_process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }).encode() + b"\n")
        await self.server_process.stdin.drain()
        
        # Test find_claude_binary
        print("\nTesting find_claude_binary...")
        response = await self.send_request("tools/call", {
            "name": "find_claude_binary",
            "arguments": {}
        })
        
        if "error" in response:
            print(f"Error: {response['error']}")
        else:
            result = response.get("result", {})
            content = result.get("content", [])
            if content:
                data = content[0]
                print(f"✓ Binary path: {data.get('binary_path', 'Not found')}")
                print(f"  Version: {data.get('version', 'Unknown')}")
                print(f"  Is valid: {data.get('is_valid', False)}")
                print(f"  Install type: {data.get('install_type', 'Unknown')}")
            else:
                print("✗ No content returned")
                
        # Test check_claude_updates
        print("\nTesting check_claude_updates...")
        response = await self.send_request("tools/call", {
            "name": "check_claude_updates",
            "arguments": {}
        })
        
        if "error" in response:
            print(f"Error: {response['error']}")
        else:
            result = response.get("result", {})
            content = result.get("content", [])
            if content:
                data = content[0]
                print(f"✓ Current version: {data.get('current_version', 'Unknown')}")
                print(f"  Update available: {data.get('update_available', False)}")
                if data.get('update_available'):
                    print(f"  Latest version: {data.get('latest_version', 'Unknown')}")
            else:
                print("✗ No content returned")
                
        # Test list_claude_binaries (find all installations)
        print("\nTesting list_claude_binaries...")
        response = await self.send_request("tools/call", {
            "name": "list_claude_binaries",
            "arguments": {}
        })
        
        if "error" in response:
            print(f"Error: {response['error']}")
        else:
            result = response.get("result", {})
            content = result.get("content", [])
            if content:
                data = content[0]
                binaries = data.get('binaries', [])
                print(f"✓ Found {len(binaries)} Claude installations")
                for binary in binaries[:3]:  # Show first 3
                    print(f"  • {binary.get('path')}: v{binary.get('version', 'Unknown')}")
            else:
                print("✗ No content returned")
                
    async def shutdown(self):
        """Shutdown server."""
        if self.server_process:
            print("\nShutting down server...")
            self.server_process.terminate()
            try:
                await asyncio.wait_for(self.server_process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.server_process.kill()
                await self.server_process.wait()
            print("Server shut down")

async def main():
    """Run binary discovery tests."""
    client = SimpleMCPClient()
    
    try:
        # Start server
        if not await client.start_server():
            print("Failed to start server")
            return
            
        # Run tests
        await client.test_binary_discovery()
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        await client.shutdown()

if __name__ == "__main__":
    asyncio.run(main())