#!/usr/bin/env python3
"""Synchronous test of Shannon MCP binary discovery tools."""

import subprocess
import json
import sys
import os
import time
import select

def send_request(proc, method, params=None, request_id=1):
    """Send a JSON-RPC request and get response."""
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method
    }
    if params:
        request["params"] = params
    
    request_str = json.dumps(request) + "\n"
    print(f"   Sending: {method} (id={request_id})")
    proc.stdin.write(request_str)
    proc.stdin.flush()
    
    # Read response
    start_time = time.time()
    lines_checked = 0
    while time.time() - start_time < 10:  # Increased timeout
        readable, _, _ = select.select([proc.stdout], [], [], 0.1)
        if readable:
            line = proc.stdout.readline()
            if line:
                lines_checked += 1
                line = line.strip()
                if line.startswith('{'):
                    try:
                        response = json.loads(line)
                        print(f"   Received response (after {lines_checked} lines)")
                        return response
                    except Exception as e:
                        print(f"   JSON parse error: {e}")
                        continue
                else:
                    print(f"   Skipping non-JSON: {line[:50]}...")
    
    # Check if process died
    if proc.poll() is not None:
        print(f"   Server died with exit code: {proc.poll()}")
    
    raise Exception(f"Timeout waiting for response to {method} (checked {lines_checked} lines)")

def main():
    """Test binary discovery tools."""
    print("Shannon MCP Binary Discovery Test")
    print("=" * 50)
    
    # Start server
    env = {"SHANNON_MCP_MODE": "stdio", "PYTHONUNBUFFERED": "1", **os.environ}
    cmd = [sys.executable, "-m", "shannon_mcp.stdio_wrapper"]
    
    print("\nStarting server...")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    print(f"Server PID: {proc.pid}")
    
    # Monitor stderr for a moment to see startup
    print("\nServer startup messages:")
    start_time = time.time()
    while time.time() - start_time < 3:
        readable, _, _ = select.select([proc.stderr], [], [], 0.1)
        if readable:
            line = proc.stderr.readline()
            if line and "INFO" in line:
                print(f"  {line.strip()}")
    
    # Wait for server to be ready
    time.sleep(1)
    
    try:
        # Initialize
        print("\n1. Initializing connection...")
        response = send_request(proc, "initialize", {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        })
        
        if "result" in response:
            print("   ✓ Initialized successfully")
            server_info = response["result"]["serverInfo"]
            print(f"   Server: {server_info['name']} v{server_info['version']}")
        else:
            print("   ✗ Initialization failed")
            return
        
        # Send initialized notification
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        proc.stdin.flush()
        
        # Test find_claude_binary
        print("\n2. Testing find_claude_binary...")
        response = send_request(proc, "tools/call", {
            "name": "find_claude_binary",
            "arguments": {}
        }, 2)
        
        if "result" in response and response["result"].get("content"):
            content = response["result"]["content"][0]
            binary_path = content.get("binary_path", "Not found")
            
            if binary_path and binary_path != "Not found":
                print("   ✓ Found Claude binary")
                print(f"   Path: {binary_path}")
                print(f"   Version: {content.get('version', 'Unknown')}")
                print(f"   Valid: {content.get('is_valid', False)}")
                print(f"   Type: {content.get('install_type', 'Unknown')}")
            else:
                print("   ⚠ Claude binary not found on this system")
        else:
            print("   ✗ Tool call failed")
            if "error" in response:
                print(f"   Error: {response['error']}")
        
        # Test check_claude_updates
        print("\n3. Testing check_claude_updates...")
        response = send_request(proc, "tools/call", {
            "name": "check_claude_updates",
            "arguments": {}
        }, 3)
        
        if "result" in response and response["result"].get("content"):
            content = response["result"]["content"][0]
            current = content.get("current_version", "Unknown")
            
            if current != "Unknown":
                print("   ✓ Update check completed")
                print(f"   Current version: {current}")
                print(f"   Update available: {content.get('update_available', False)}")
                if content.get('update_available'):
                    print(f"   Latest version: {content.get('latest_version', 'Unknown')}")
            else:
                print("   ⚠ Could not check for updates (no binary found)")
        else:
            print("   ✗ Tool call failed")
            if "error" in response:
                print(f"   Error: {response['error']}")
        
        # Test list_claude_binaries
        print("\n4. Testing list_claude_binaries...")
        response = send_request(proc, "tools/call", {
            "name": "list_claude_binaries",
            "arguments": {}
        }, 4)
        
        if "result" in response and response["result"].get("content"):
            content = response["result"]["content"][0]
            binaries = content.get('binaries', [])
            
            print(f"   ✓ Found {len(binaries)} Claude installation(s)")
            
            if binaries:
                for i, binary in enumerate(binaries[:5]):  # Show first 5
                    print(f"   {i+1}. {binary.get('path', 'Unknown path')}")
                    print(f"      Version: {binary.get('version', 'Unknown')}")
                    print(f"      Type: {binary.get('install_type', 'Unknown')}")
                
                if len(binaries) > 5:
                    print(f"   ... and {len(binaries) - 5} more")
            else:
                print("   ⚠ No Claude installations found")
        else:
            print("   ✗ Tool call failed")
            if "error" in response:
                print(f"   Error: {response['error']}")
        
        print("\n" + "=" * 50)
        print("Binary discovery tests completed!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\nShutting down server...")
        proc.terminate()
        proc.wait()
        print("Done!")

if __name__ == "__main__":
    main()