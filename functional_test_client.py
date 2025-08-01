#!/usr/bin/env python3
"""
Shannon MCP Server Functional Test Client

This script acts as an MCP client to comprehensively test the Shannon MCP server.
It spawns the server as a subprocess and communicates via the MCP protocol over stdio.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Configure logging with detailed format for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MCPTestClient")

# Test configuration
SERVER_PATH = Path(__file__).parent / "src" / "shannon_mcp" / "stdio_wrapper.py"
PYTHON_CMD = sys.executable


@dataclass
class MCPMessage:
    """Represents an MCP protocol message"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPTestClient:
    """MCP Test Client for functional testing"""
    
    def __init__(self):
        self.server_process: Optional[subprocess.Popen] = None
        self.message_id = 0
        self.reader_task: Optional[asyncio.Task] = None
        self.response_futures: Dict[int, asyncio.Future] = {}
        self.notifications: List[Dict[str, Any]] = []
        self._stop_reader = False
        
    async def start_server(self) -> bool:
        """Start the Shannon MCP server subprocess"""
        logger.info("Starting Shannon MCP server...")
        
        try:
            # Start server with stdio transport
            self.server_process = subprocess.Popen(
                [PYTHON_CMD, str(SERVER_PATH)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Use binary mode for proper encoding control
                bufsize=0  # Unbuffered
            )
            
            # Start reader task
            self.reader_task = asyncio.create_task(self._read_server_output())
            
            # Give server time to initialize
            await asyncio.sleep(2)
            
            # Send initialize request
            logger.info("Sending initialize request...")
            response = await self.send_request("initialize", {
                "protocolVersion": "1.0.0",
                "capabilities": {
                    "tools": True,
                    "resources": True
                },
                "clientInfo": {
                    "name": "Shannon MCP Test Client",
                    "version": "1.0.0"
                }
            })
            
            if response and "result" in response:
                logger.info(f"Server initialized: {json.dumps(response['result'], indent=2)}")
                return True
            else:
                logger.error(f"Failed to initialize: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    async def _read_server_output(self):
        """Read server output continuously"""
        logger.debug("Starting server output reader...")
        
        buffer = b""
        while not self._stop_reader and self.server_process and self.server_process.poll() is None:
            try:
                # Read available data
                chunk = self.server_process.stdout.read1(4096)
                if not chunk:
                    await asyncio.sleep(0.01)
                    continue
                
                buffer += chunk
                
                # Process complete messages
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    
                    try:
                        # Decode and parse JSON
                        message = json.loads(line.decode('utf-8'))
                        logger.debug(f"Received: {json.dumps(message, indent=2)}")
                        
                        # Handle response or notification
                        if "id" in message and message["id"] in self.response_futures:
                            # Response to a request
                            future = self.response_futures.pop(message["id"])
                            if not future.done():
                                future.set_result(message)
                        else:
                            # Notification or unexpected message
                            self.notifications.append(message)
                            logger.info(f"Notification: {message.get('method', 'unknown')}")
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON: {e}, line: {line}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
            except Exception as e:
                logger.error(f"Reader error: {e}")
                await asyncio.sleep(0.1)
    
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
        logger.debug(f"Sending: {json.dumps(message, indent=2)}")
        message_bytes = (json.dumps(message) + "\n").encode('utf-8')
        self.server_process.stdin.write(message_bytes)
        self.server_process.stdin.flush()
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            self.response_futures.pop(self.message_id, None)
            return None
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        """Call a tool and return success status and result"""
        response = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        
        if response and "result" in response:
            return True, response["result"]
        elif response and "error" in response:
            logger.error(f"Tool error: {response['error']}")
            return False, response["error"]
        else:
            return False, "No response"
    
    async def get_resource(self, uri: str) -> Tuple[bool, Any]:
        """Get a resource by URI"""
        response = await self.send_request("resources/read", {
            "uri": uri
        })
        
        if response and "result" in response:
            return True, response["result"]
        elif response and "error" in response:
            logger.error(f"Resource error: {response['error']}")
            return False, response["error"]
        else:
            return False, "No response"
    
    async def stop_server(self):
        """Stop the server subprocess"""
        logger.info("Stopping server...")
        
        # Stop reader
        self._stop_reader = True
        if self.reader_task:
            await self.reader_task
        
        # Terminate server
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()
            
            # Log any stderr output
            if self.server_process.stderr:
                stderr = self.server_process.stderr.read()
                if stderr:
                    logger.debug(f"Server stderr: {stderr.decode('utf-8', errors='replace')}")


async def run_functional_tests():
    """Run comprehensive functional tests"""
    client = MCPTestClient()
    test_results = []
    
    def record_test(name: str, success: bool, details: Any = None):
        """Record test result"""
        result = {
            "test": name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        test_results.append(result)
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f"{status}: {name}")
        if details:
            logger.debug(f"Details: {json.dumps(details, indent=2)}")
    
    try:
        # Start server
        logger.info("="*60)
        logger.info("SHANNON MCP FUNCTIONAL TEST SUITE")
        logger.info("="*60)
        
        if not await client.start_server():
            record_test("Server Startup", False, "Failed to start server")
            return test_results
        
        record_test("Server Startup", True)
        
        # Test 1: Server Status
        logger.info("\n--- Test 1: Server Status ---")
        success, result = await client.call_tool("server_status")
        record_test("Server Status Check", success, result)
        
        # Wait for full initialization
        await asyncio.sleep(3)
        
        # Test 2: Binary Discovery
        logger.info("\n--- Test 2: Binary Discovery ---")
        success, result = await client.call_tool("find_claude_binary")
        record_test("Binary Discovery", success and result.get("status") in ["found", "not_found"], result)
        
        # Test 3: List Available Agents
        logger.info("\n--- Test 3: List Agents ---")
        success, result = await client.call_tool("list_agents")
        record_test("List Agents", success and "agents" in result, {
            "agent_count": len(result.get("agents", [])) if success else 0,
            "categories": result.get("metadata", {}).get("categories", []) if success else []
        })
        
        # Test 4: Create Custom Agent
        logger.info("\n--- Test 4: Create Custom Agent ---")
        agent_config = {
            "name": "TestAgent",
            "role": "test_automation",
            "capabilities": ["testing", "validation", "reporting"],
            "description": "Agent for automated testing",
            "temperature": 0.7,
            "category": "specialized"
        }
        success, result = await client.call_tool("create_agent", agent_config)
        test_agent_id = result.get("agent", {}).get("id") if success else None
        record_test("Create Custom Agent", success and test_agent_id, result)
        
        # Test 5: Create Project
        logger.info("\n--- Test 5: Create Project ---")
        project_config = {
            "name": "Test Project",
            "description": "Project for functional testing",
            "tags": ["test", "functional"],
            "default_model": "claude-3-sonnet"
        }
        success, result = await client.call_tool("create_project", project_config)
        test_project_id = result.get("project", {}).get("id") if success else None
        record_test("Create Project", success and test_project_id, result)
        
        # Test 6: List Projects
        logger.info("\n--- Test 6: List Projects ---")
        success, result = await client.call_tool("list_projects", {
            "status": "active",
            "limit": 10
        })
        record_test("List Projects", success and "projects" in result, {
            "project_count": len(result.get("projects", [])) if success else 0
        })
        
        # Test 7: Create Session in Project
        logger.info("\n--- Test 7: Create Session in Project ---")
        session_config = {
            "prompt": "Test session for functional testing",
            "model": "claude-3-sonnet",
            "project_id": test_project_id,
            "context": {"test": True, "timestamp": datetime.now().isoformat()},
            "options": {"streaming": True, "analytics": True}
        }
        success, result = await client.call_tool("create_session", session_config)
        test_session_id = result.get("session", {}).get("id") if success else None
        record_test("Create Session in Project", success and test_session_id and result.get("project_id") == test_project_id, result)
        
        # Test 8: Get Project Sessions
        if test_project_id:
            logger.info("\n--- Test 8: Get Project Sessions ---")
            success, result = await client.call_tool("get_project_sessions", {
                "project_id": test_project_id
            })
            record_test("Get Project Sessions", success and "sessions" in result, {
                "session_count": result.get("session_count", 0) if success else 0
            })
        
        # Test 9: Send Message (if session created)
        if test_session_id:
            logger.info("\n--- Test 9: Send Message ---")
            message_config = {
                "session_id": test_session_id,
                "message": "What is 2 + 2?",
                "stream": False
            }
            success, result = await client.call_tool("send_message", message_config)
            record_test("Send Message", success, result)
        
        # Test 10: Create Checkpoint (if session created)
        if test_session_id:
            logger.info("\n--- Test 10: Create Checkpoint ---")
            checkpoint_config = {
                "session_id": test_session_id,
                "name": "Test Checkpoint",
                "description": "Checkpoint for functional testing",
                "tags": ["test", "functional"]
            }
            success, result = await client.call_tool("create_checkpoint", checkpoint_config)
            test_checkpoint_id = result.get("checkpoint", {}).get("id") if success else None
            record_test("Create Checkpoint", success and test_checkpoint_id, result)
        
        # Test 11: Create Project Checkpoint
        if test_project_id:
            logger.info("\n--- Test 11: Create Project Checkpoint ---")
            success, result = await client.call_tool("create_project_checkpoint", {
                "project_id": test_project_id,
                "name": "Test Project Checkpoint",
                "description": "Checkpoint for entire project"
            })
            record_test("Create Project Checkpoint", success, result)
        
        # Test 12: List Sessions
        logger.info("\n--- Test 12: List Sessions ---")
        success, result = await client.call_tool("list_sessions", {
            "limit": 10,
            "sort_by": "created_at"
        })
        record_test("List Sessions", success and "sessions" in result, {
            "session_count": len(result.get("sessions", [])) if success else 0
        })
        
        # Test 13: Execute Agent Task (if agent created)
        if test_agent_id:
            logger.info("\n--- Test 13: Execute Agent Task ---")
            task_config = {
                "agent_id": test_agent_id,
                "task": "Validate that the functional test is working correctly",
                "context": {"test_run_id": str(uuid.uuid4())},
                "priority": "high"
            }
            success, result = await client.call_tool("execute_agent", task_config)
            record_test("Execute Agent Task", success, result)
        
        # Test 14: Query Analytics
        logger.info("\n--- Test 14: Query Analytics ---")
        analytics_config = {
            "query_type": "usage",
            "parameters": {
                "start_date": datetime.now().isoformat(),
                "metrics": ["sessions", "messages", "tokens"]
            }
        }
        success, result = await client.call_tool("query_analytics", analytics_config)
        record_test("Query Analytics", success, result)
        
        # Test 15: Resource Access - Projects
        logger.info("\n--- Test 15: Resource Access - Projects ---")
        success, result = await client.get_resource("shannon://projects")
        record_test("Get Projects Resource", success, {
            "has_projects": "projects" in str(result) if success else False
        })
        
        # Test 16: Resource Access - Config
        logger.info("\n--- Test 16: Resource Access - Config ---")
        success, result = await client.get_resource("shannon://config")
        record_test("Get Config Resource", success, {
            "has_runtime": "runtime" in str(result) if success else False
        })
        
        # Test 17: Resource Access - Health
        logger.info("\n--- Test 17: Resource Access - Health ---")
        success, result = await client.get_resource("shannon://health")
        record_test("Get Health Resource", success, result)
        
        # Test 18: Settings Management
        logger.info("\n--- Test 18: Settings Management ---")
        success, result = await client.call_tool("manage_settings", {
            "action": "list",
            "section": "binary_manager"
        })
        record_test("List Settings", success, result)
        
        # Test 19: MCP Server Management
        logger.info("\n--- Test 19: MCP Server Management ---")
        mcp_config = {
            "name": "test-mcp-server",
            "command": "echo",
            "args": ["test"],
            "transport": "stdio",
            "enabled": False
        }
        success, result = await client.call_tool("mcp_add", mcp_config)
        record_test("Add MCP Server", success, result)
        
        # Test 20: Archive Project (if project created)
        if test_project_id:
            logger.info("\n--- Test 20: Archive Project ---")
            success, result = await client.call_tool("archive_project", {
                "project_id": test_project_id
            })
            record_test("Archive Project", success, result)
        
        # Test 21: Cancel Session (if session created)
        if test_session_id:
            logger.info("\n--- Test 21: Cancel Session ---")
            success, result = await client.call_tool("cancel_session", {
                "session_id": test_session_id,
                "reason": "Test completed"
            })
            record_test("Cancel Session", success, result)
        
    except Exception as e:
        logger.error(f"Test suite error: {e}", exc_info=True)
        record_test("Test Suite Execution", False, str(e))
    finally:
        # Stop server
        await client.stop_server()
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        passed = sum(1 for r in test_results if r["success"])
        failed = sum(1 for r in test_results if not r["success"])
        total = len(test_results)
        
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed} ✅")
        logger.info(f"Failed: {failed} ❌")
        logger.info(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        # List failed tests
        if failed > 0:
            logger.info("\nFailed Tests:")
            for result in test_results:
                if not result["success"]:
                    logger.info(f"  - {result['test']}")
                    if result.get("details"):
                        logger.info(f"    Details: {result['details']}")
        
        # Save detailed results
        results_file = Path("functional_test_results.json")
        with open(results_file, "w") as f:
            json.dump({
                "test_run": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "success_rate": passed/total if total > 0 else 0
                },
                "results": test_results
            }, f, indent=2)
        
        logger.info(f"\nDetailed results saved to: {results_file}")
        
        return test_results


def main():
    """Main entry point"""
    logger.info("Starting Shannon MCP Functional Test Client")
    
    # Check if server exists
    if not SERVER_PATH.exists():
        logger.error(f"Server not found at: {SERVER_PATH}")
        logger.error("Please ensure the Shannon MCP server is properly installed")
        sys.exit(1)
    
    # Run tests
    results = asyncio.run(run_functional_tests())
    
    # Exit with appropriate code
    failed = sum(1 for r in results if not r["success"])
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()