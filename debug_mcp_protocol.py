#!/usr/bin/env python3
"""
Debug MCP Protocol Communication
Simple test to debug Shannon MCP protocol handling
"""

import asyncio
import json
import subprocess
import sys
import time

async def test_mcp_protocol():
    """Test basic MCP protocol communication"""
    print("🔧 Starting Shannon MCP server for protocol debugging...")
    
    # Start server
    process = await asyncio.create_subprocess_exec(
        "python", "-m", "shannon_mcp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    print("🔧 Server started, waiting for initialization...")
    await asyncio.sleep(15)  # Wait longer for server to fully initialize
    
    if process.returncode is not None:
        stderr = await process.stderr.read()
        print(f"❌ Server failed: {stderr.decode()}")
        return False
    
    print("✅ Server running, testing MCP initialize...")
    
    # Send initialize message
    init_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "1.0.0",
            "capabilities": {"tools": True, "resources": True},
            "clientInfo": {"name": "Debug Client", "version": "1.0.0"}
        }
    }
    
    message_json = json.dumps(init_message) + "\n"
    print(f"📤 Sending: {message_json.strip()}")
    
    # Write message
    process.stdin.write(message_json.encode())
    await process.stdin.drain()
    
    print("⏱️ Waiting for response...")
    
    # Read response with timeout and show stderr
    try:
        # Try to read stderr first to see if there are errors
        try:
            stderr_data = await asyncio.wait_for(process.stderr.read(1024), timeout=1.0)
            if stderr_data:
                stderr_text = stderr_data.decode('utf-8', errors='replace')
                print(f"📄 Server stderr: {stderr_text}")
        except asyncio.TimeoutError:
            pass  # No stderr data
        
        response_bytes = await asyncio.wait_for(
            process.stdout.readline(), 
            timeout=10.0
        )
        
        if response_bytes:
            response = response_bytes.decode().strip()
            print(f"📥 Received: {response}")
            
            try:
                response_json = json.loads(response)
                if "result" in response_json:
                    print("✅ MCP Initialize successful!")
                    return True
                elif "error" in response_json:
                    print(f"❌ MCP Error: {response_json['error']}")
                    return False
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                return False
        else:
            print("❌ No response received")
            return False
            
    except asyncio.TimeoutError:
        print("❌ Response timeout")
        # Try to read stderr for error info
        try:
            stderr_data = await process.stderr.read(1024)
            if stderr_data:
                stderr_text = stderr_data.decode('utf-8', errors='replace')
                print(f"📄 Server stderr during timeout: {stderr_text}")
        except:
            pass
        return False
    
    finally:
        # Cleanup
        print("🔧 Cleaning up...")
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

if __name__ == "__main__":
    success = asyncio.run(test_mcp_protocol())
    sys.exit(0 if success else 1)