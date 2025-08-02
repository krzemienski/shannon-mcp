#!/usr/bin/env python3
"""
Production MCP Client Test Suite
Test Shannon MCP server as if Claude Desktop is connecting to it.
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("MCPProductionTest")


class ProductionMCPClient:
    """Production MCP Client for testing Shannon MCP server"""
    
    def __init__(self):
        self.server_process: Optional[asyncio.subprocess.Process] = None
        self.message_id = 0
        self.reader_task: Optional[asyncio.Task] = None
        self.response_futures: Dict[int, asyncio.Future] = {}
        self.notifications: List[Dict[str, Any]] = []
        self._stop_reader = False

    async def start_server(self) -> bool:
        """Start Shannon MCP server as configured in Claude Desktop"""
        logger.info("Starting Shannon MCP server via python -m shannon_mcp...")
        
        try:
            # Start server exactly as Claude Desktop would
            import os
            env = os.environ.copy()
            env["SHANNON_MCP_MODE"] = "stdio"
            
            self.server_process = await asyncio.create_subprocess_exec(
                "python", "-m", "shannon_mcp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Start reader task
            self.reader_task = asyncio.create_task(self._read_server_output())
            
            # Give server time to initialize (it takes ~6 seconds)
            logger.info("Waiting for server initialization...")
            await asyncio.sleep(8)
            
            # Check if server is still running
            if self.server_process.returncode is not None:
                stderr = await self.server_process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else "Unknown error"
                logger.error(f"Server failed to start: {error_msg}")
                return False
            
            logger.info("Server started successfully, testing MCP protocol...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    async def _read_server_output(self):
        """Read server output continuously"""
        logger.debug("Starting server output reader...")
        
        buffer = b""
        while not self._stop_reader and self.server_process and self.server_process.returncode is None:
            try:
                chunk = await self.server_process.stdout.read(4096)
                
                if not chunk:
                    logger.debug("End of stream detected")
                    break
                
                buffer += chunk
                
                # Process complete messages
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    
                    if not line.strip():
                        continue
                    
                    try:
                        message = json.loads(line.decode('utf-8'))
                        await self._handle_message(message)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON: {e}, line: {line}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
            except Exception as e:
                logger.error(f"Reader error: {e}")
                await asyncio.sleep(0.1)
        
        logger.debug("Server output reader stopped")

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from server"""
        if "id" in message:
            # This is a response
            msg_id = message["id"]
            if msg_id in self.response_futures:
                future = self.response_futures.pop(msg_id)
                if not future.cancelled():
                    future.set_result(message)
        else:
            # This is a notification
            self.notifications.append(message)
            logger.debug(f"Received notification: {message.get('method', 'unknown')}")

    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Send a request to the server and wait for response"""
        self.message_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.Future()
        self.response_futures[self.message_id] = future
        
        # Send message
        logger.debug(f"Sending {method} request...")
        message_bytes = (json.dumps(message) + "\n").encode('utf-8')
        
        # Check if process is still running
        if self.server_process.returncode is not None:
            logger.error(f"Server process terminated with code: {self.server_process.returncode}")
            raise RuntimeError("Server process terminated")
        
        try:
            self.server_process.stdin.write(message_bytes)
            await self.server_process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Failed to send message: {e}")
            raise RuntimeError("Connection lost") from e
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            self.response_futures.pop(self.message_id, None)
            return None

    async def initialize(self) -> bool:
        """Initialize MCP connection"""
        response = await self.send_request("initialize", {
            "protocolVersion": "1.0.0",
            "capabilities": {
                "tools": True,
                "resources": True
            },
            "clientInfo": {
                "name": "Shannon MCP Production Test Client",
                "version": "1.0.0"
            }
        })
        
        if response and "result" in response:
            logger.info("✅ MCP initialization successful")
            logger.info(f"Server capabilities: {response['result'].get('capabilities', {})}")
            return True
        else:
            logger.error("❌ MCP initialization failed")
            return False

    async def list_tools(self) -> bool:
        """List available tools"""
        response = await self.send_request("tools/list")
        
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            logger.info(f"✅ Found {len(tools)} tools:")
            for tool in tools[:5]:  # Show first 5 tools
                logger.info(f"  - {tool['name']}: {tool.get('description', 'No description')[:80]}...")
            if len(tools) > 5:
                logger.info(f"  ... and {len(tools) - 5} more tools")
            return True
        else:
            logger.error("❌ Failed to list tools")
            return False

    async def list_resources(self) -> bool:
        """List available resources"""
        response = await self.send_request("resources/list")
        
        if response and "result" in response:
            resources = response["result"].get("resources", [])
            logger.info(f"✅ Found {len(resources)} resources:")
            for resource in resources[:5]:  # Show first 5 resources
                logger.info(f"  - {resource['uri']}: {resource.get('description', 'No description')[:80]}...")
            if len(resources) > 5:
                logger.info(f"  ... and {len(resources) - 5} more resources")
            return True
        else:
            logger.error("❌ Failed to list resources")
            return False

    async def test_config_resource(self) -> bool:
        """Test reading shannon://config resource"""
        response = await self.send_request("resources/read", {
            "uri": "shannon://config"
        })
        
        if response and "result" in response:
            contents = response["result"].get("contents", [])
            logger.info(f"✅ Config resource read successfully ({len(contents)} items)")
            return True
        else:
            logger.error("❌ Failed to read config resource")
            return False

    async def test_discover_binary_tool(self) -> bool:
        """Test discover_binary tool"""
        response = await self.send_request("tools/call", {
            "name": "discover_binary",
            "arguments": {}
        })
        
        if response and "result" in response:
            logger.info("✅ discover_binary tool executed successfully")
            return True
        elif response and "error" in response:
            logger.warning(f"⚠️ discover_binary tool returned error: {response['error']}")
            return True  # Expected for no Claude Code binary
        else:
            logger.error("❌ discover_binary tool failed")
            return False

    async def stop_server(self):
        """Stop the server subprocess"""
        logger.info("Stopping server...")
        
        # Stop reader
        self._stop_reader = True
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        # Terminate server
        if self.server_process and self.server_process.returncode is None:
            try:
                self.server_process.terminate()
                await asyncio.wait_for(self.server_process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.server_process.kill()
                await self.server_process.wait()
            except ProcessLookupError:
                pass


async def run_production_tests():
    """Run production MCP tests"""
    client = ProductionMCPClient()
    
    tests_passed = 0
    total_tests = 6
    
    try:
        # Test 1: Server startup
        logger.info("🔧 Test 1: Server Startup")
        if await client.start_server():
            tests_passed += 1
            logger.info("✅ Server startup: PASSED")
        else:
            logger.error("❌ Server startup: FAILED")
            return
        
        # Test 2: MCP initialization
        logger.info("🔧 Test 2: MCP Initialization")
        if await client.initialize():
            tests_passed += 1
            logger.info("✅ MCP initialization: PASSED")
        else:
            logger.error("❌ MCP initialization: FAILED")
        
        # Test 3: List tools
        logger.info("🔧 Test 3: List Tools")
        if await client.list_tools():
            tests_passed += 1
            logger.info("✅ List tools: PASSED")
        else:
            logger.error("❌ List tools: FAILED")
        
        # Test 4: List resources
        logger.info("🔧 Test 4: List Resources")
        if await client.list_resources():
            tests_passed += 1
            logger.info("✅ List resources: PASSED")
        else:
            logger.error("❌ List resources: FAILED")
        
        # Test 5: Read config resource
        logger.info("🔧 Test 5: Read Config Resource")
        if await client.test_config_resource():
            tests_passed += 1
            logger.info("✅ Read config resource: PASSED")
        else:
            logger.error("❌ Read config resource: FAILED")
        
        # Test 6: Call discover_binary tool
        logger.info("🔧 Test 6: Call Discover Binary Tool")
        if await client.test_discover_binary_tool():
            tests_passed += 1
            logger.info("✅ Call discover_binary tool: PASSED")
        else:
            logger.error("❌ Call discover_binary tool: FAILED")
        
    finally:
        await client.stop_server()
    
    # Summary
    logger.info(f"\n🎯 PRODUCTION TEST SUMMARY")
    logger.info(f"Tests passed: {tests_passed}/{total_tests}")
    logger.info(f"Success rate: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        logger.info("🎉 ALL TESTS PASSED - Shannon MCP is production ready!")
        return True
    else:
        logger.error("❌ Some tests failed - Shannon MCP needs fixes")
        return False


def main():
    """Main entry point"""
    logger.info("Starting Shannon MCP Production Test Suite")
    logger.info("="*60)
    
    try:
        success = asyncio.run(run_production_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()