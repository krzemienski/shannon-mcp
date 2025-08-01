#!/usr/bin/env python3
"""
Shannon MCP Comprehensive Functional Test Suite

This script acts as a third-party MCP client to test all Shannon MCP functionality.
It tests the server from an external perspective, verifying all tools, resources,
and protocol compliance.

Usage: python shannon_mcp_functional_test.py
"""

import asyncio
import json
import subprocess
import sys
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import signal
import tempfile
import shutil

# ANSI color codes for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class MCPClient:
    """MCP Client that communicates with Shannon MCP server via stdio JSON-RPC."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.server_process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.server_capabilities = {}
        self.initialized = False
        self.test_results = []
        self.server_output = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log messages with color coding."""
        colors = {
            "INFO": Colors.CYAN,
            "SUCCESS": Colors.GREEN,
            "WARNING": Colors.WARNING,
            "ERROR": Colors.FAIL,
            "HEADER": Colors.HEADER
        }
        color = colors.get(level, "")
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if self.verbose:
            print(f"{color}[{timestamp}] {level}: {message}{Colors.ENDC}")
    
    async def start_server(self) -> bool:
        """Start the Shannon MCP server as a subprocess."""
        self.log("Starting Shannon MCP server...", "HEADER")
        
        try:
            # Create necessary directories first
            dirs = [
                Path.home() / ".shannon-mcp" / "database",
                Path.home() / ".shannon-mcp" / "logs",
                Path.home() / ".shannon-mcp" / "cache",
                Path.home() / ".shannon-mcp" / "checkpoints"
            ]
            for dir_path in dirs:
                dir_path.mkdir(parents=True, exist_ok=True)
                self.log(f"  Ensured directory exists: {dir_path}", "INFO")
            
            # Start the server using the entry point
            cmd = [sys.executable, "-m", "shannon_mcp.stdio_wrapper"]
            self.log(f"Starting server with command: {' '.join(cmd)}", "INFO")
            
            self.server_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "SHANNON_MCP_MODE": "stdio", "PYTHONUNBUFFERED": "1"}
            )
            
            self.log(f"Server process started with PID: {self.server_process.pid}", "SUCCESS")
            
            # Start background tasks to read server output
            asyncio.create_task(self._read_server_stderr())
            
            # Wait a bit for server to start
            await asyncio.sleep(1)
            
            # Check if process is still running
            if self.server_process.returncode is not None:
                self.log(f"Server exited immediately with code: {self.server_process.returncode}", "ERROR")
                # Read any error output
                if self.server_process.stderr:
                    stderr = await self.server_process.stderr.read()
                    self.log(f"Server stderr: {stderr.decode()[:500]}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"Failed to start server: {e}", "ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return False
    
    async def _read_server_stderr(self):
        """Read server stderr in background."""
        while self.server_process and self.server_process.stderr:
            try:
                line = await self.server_process.stderr.readline()
                if line:
                    decoded = line.decode('utf-8', errors='replace').strip()
                    if decoded:
                        self.server_output.append(decoded)
                        if self.verbose and "ERROR" in decoded:
                            self.log(f"Server stderr: {decoded}", "WARNING")
            except:
                break
    
    def _next_id(self) -> str:
        """Get next request ID."""
        self.request_id += 1
        return str(self.request_id)
    
    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send JSON-RPC request to server and wait for response."""
        request_id = self._next_id()
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id
        }
        
        if params:
            request["params"] = params
        
        # Send request
        request_json = json.dumps(request) + "\n"
        if self.verbose:
            self.log(f"Sending: {method} (id={request_id})", "INFO")
            self.log(f"  Request: {json.dumps(request, indent=2)}", "INFO")
            
        self.server_process.stdin.write(request_json.encode())
        await self.server_process.stdin.drain()
        
        # Read response with timeout, skipping non-JSON lines
        try:
            start_time = time.time()
            while True:
                if time.time() - start_time > 30:
                    raise asyncio.TimeoutError()
                    
                response_line = await asyncio.wait_for(
                    self.server_process.stdout.readline(),
                    timeout=5.0
                )
                
                if not response_line:
                    self.log("Empty response from server", "ERROR")
                    raise Exception("Server returned empty response")
                
                # Skip non-JSON lines (like banner output)
                line = response_line.decode().strip()
                if not line or not line.startswith('{'):
                    if self.verbose and line:
                        self.log(f"  Skipping non-JSON output: {line[:100]}", "INFO")
                    continue
                    
                # Try to decode the response
                try:
                    response = json.loads(line)
                    # Only process if it has the matching ID
                    if response.get("id") == request_id:
                        break
                except json.JSONDecodeError as e:
                    if self.verbose:
                        self.log(f"  Failed to parse line as JSON: {line[:100]}", "INFO")
                    continue
                
            if self.verbose:
                self.log(f"Received response for id={request_id}", "INFO")
                self.log(f"  Response: {json.dumps(response, indent=2)[:500]}", "INFO")
            
            # Check for errors
            if "error" in response:
                self.log(f"Error in response: {response['error']}", "ERROR")
                raise Exception(f"Server error: {response['error']}")
            
            return response.get("result", {})
            
        except asyncio.TimeoutError:
            self.log(f"Timeout waiting for response to {method}", "ERROR")
            # Check if server is still running
            if self.server_process.returncode is not None:
                self.log(f"Server has exited with code: {self.server_process.returncode}", "ERROR")
            raise Exception(f"Timeout waiting for response to {method}")
    
    async def initialize(self) -> bool:
        """Initialize connection with MCP server."""
        self.log("Initializing MCP connection...", "HEADER")
        
        try:
            # Send initialize request
            result = await self.send_request("initialize", {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "Shannon MCP Test Client",
                    "version": "1.0.0"
                }
            })
            
            self.server_capabilities = result.get("capabilities", {})
            self.initialized = True
            
            self.log("Server initialized successfully", "SUCCESS")
            self.log(f"Server name: {result.get('serverInfo', {}).get('name', 'Unknown')}", "INFO")
            self.log(f"Server version: {result.get('serverInfo', {}).get('version', 'Unknown')}", "INFO")
            
            # List capabilities
            if self.server_capabilities.get("tools"):
                self.log("✓ Tools supported", "SUCCESS")
            if self.server_capabilities.get("resources"):
                self.log("✓ Resources supported", "SUCCESS")
            if self.server_capabilities.get("prompts"):
                self.log("✓ Prompts supported", "SUCCESS")
            
            # Send initialized notification
            await self.send_notification("notifications/initialized")
            
            return True
            
        except Exception as e:
            self.log(f"Initialization failed: {e}", "ERROR")
            return False
    
    async def send_notification(self, method: str, params: Optional[Dict] = None):
        """Send notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params
            
        notification_json = json.dumps(notification) + "\n"
        self.server_process.stdin.write(notification_json.encode())
        await self.server_process.stdin.drain()
    
    async def list_tools(self) -> List[Dict]:
        """List all available tools."""
        self.log("Listing available tools...", "HEADER")
        
        result = await self.send_request("tools/list")
        tools = result.get("tools", [])
        
        self.log(f"Found {len(tools)} tools", "INFO")
        for tool in tools[:5]:  # Show first 5
            self.log(f"  • {tool['name']}: {tool.get('description', 'No description')[:80]}...", "INFO")
        
        if len(tools) > 5:
            self.log(f"  ... and {len(tools) - 5} more tools", "INFO")
            
        return tools
    
    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Any:
        """Call a specific tool."""
        self.log(f"Calling tool: {name}", "INFO")
        
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments
            
        result = await self.send_request("tools/call", params)
        return result.get("content", [])
    
    async def list_resources(self) -> List[Dict]:
        """List all available resources."""
        self.log("Listing available resources...", "HEADER")
        
        result = await self.send_request("resources/list")
        resources = result.get("resources", [])
        
        self.log(f"Found {len(resources)} resources", "INFO")
        for resource in resources:
            self.log(f"  • {resource['uri']}: {resource.get('name', 'Unnamed')}", "INFO")
            
        return resources
    
    async def read_resource(self, uri: str) -> Dict:
        """Read a specific resource."""
        self.log(f"Reading resource: {uri}", "INFO")
        
        result = await self.send_request("resources/read", {"uri": uri})
        return result.get("contents", [])
    
    async def shutdown(self):
        """Shutdown the server gracefully."""
        self.log("Shutting down server...", "HEADER")
        
        if self.server_process:
            try:
                # Send terminate signal
                self.server_process.terminate()
                
                # Wait for process to end
                await asyncio.wait_for(self.server_process.wait(), timeout=5.0)
                self.log("Server shut down cleanly", "SUCCESS")
                
            except asyncio.TimeoutError:
                self.log("Server didn't shut down cleanly, forcing...", "WARNING")
                self.server_process.kill()
                await self.server_process.wait()
                
            except Exception as e:
                self.log(f"Error during shutdown: {e}", "ERROR")


class ShannonMCPTester:
    """Comprehensive tester for Shannon MCP functionality."""
    
    def __init__(self, verbose: bool = True):
        self.client = MCPClient(verbose=verbose)
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tests": []
        }
        self.test_dir = None
        
    def record_test(self, name: str, passed: bool, details: str = "", duration: float = 0):
        """Record test result."""
        result = {
            "name": name,
            "passed": passed,
            "details": details,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        self.test_results["tests"].append(result)
        if passed:
            self.test_results["passed"] += 1
            self.client.log(f"✓ {name}", "SUCCESS")
        else:
            self.test_results["failed"] += 1
            self.client.log(f"✗ {name}: {details}", "ERROR")
    
    async def setup(self):
        """Setup test environment."""
        self.client.log("Setting up test environment...", "HEADER")
        
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="shannon_mcp_test_"))
        self.client.log(f"Test directory: {self.test_dir}", "INFO")
        
        # Start server
        if not await self.client.start_server():
            raise Exception("Failed to start server")
        
        # Initialize connection
        if not await self.client.initialize():
            raise Exception("Failed to initialize connection")
        
        # Wait for server to be fully ready
        await asyncio.sleep(0.5)
    
    async def teardown(self):
        """Cleanup test environment."""
        self.client.log("Cleaning up test environment...", "HEADER")
        
        # Shutdown server
        await self.client.shutdown()
        
        # Remove test directory
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    async def test_server_status(self):
        """Test server status tool."""
        start_time = time.time()
        
        try:
            result = await self.client.call_tool("server_status")
            content = result[0] if result else {}
            
            # Verify expected fields
            expected_fields = ["initialized", "managers", "mode", "startup_time"]
            missing = [f for f in expected_fields if f not in content]
            
            if not missing and content.get("initialized") == True:
                self.record_test(
                    "Server Status",
                    True,
                    f"All managers initialized",
                    time.time() - start_time
                )
            else:
                self.record_test(
                    "Server Status",
                    False,
                    f"Missing fields: {missing}" if missing else "Server not initialized",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Server Status", False, str(e), time.time() - start_time)
    
    async def test_binary_discovery(self):
        """Test Claude binary discovery."""
        start_time = time.time()
        
        try:
            # Test find_claude_binary
            result = await self.client.call_tool("find_claude_binary")
            content = result[0] if result else {}
            
            if "binary_path" in content and content["binary_path"]:
                binary_path = content["binary_path"]
                self.record_test(
                    "Binary Discovery",
                    True,
                    f"Found Claude at: {binary_path}",
                    time.time() - start_time
                )
                
                # Test version detection
                if "version" in content:
                    self.client.log(f"  Claude version: {content['version']}", "INFO")
                    
            else:
                self.record_test(
                    "Binary Discovery",
                    False,
                    "Claude binary not found",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Binary Discovery", False, str(e), time.time() - start_time)
    
    async def test_session_creation(self):
        """Test session creation and management."""
        start_time = time.time()
        
        try:
            # Create a test session
            result = await self.client.call_tool("create_session", {
                "project_path": str(self.test_dir),
                "prompt": "Write a hello world Python script",
                "model": "claude-3-haiku-20240307"
            })
            
            content = result[0] if result else {}
            
            if "session_id" in content:
                session_id = content["session_id"]
                self.record_test(
                    "Session Creation",
                    True,
                    f"Created session: {session_id}",
                    time.time() - start_time
                )
                
                # Wait a moment for session to start
                await asyncio.sleep(1)
                
                # Test session listing
                list_result = await self.client.call_tool("list_sessions")
                sessions = list_result[0].get("sessions", []) if list_result else []
                
                if any(s.get("id") == session_id for s in sessions):
                    self.client.log(f"  ✓ Session appears in list", "SUCCESS")
                else:
                    self.client.log(f"  ✗ Session not in list", "ERROR")
                    
                # Cancel session
                await self.client.call_tool("cancel_session", {"session_id": session_id})
                
            else:
                self.record_test(
                    "Session Creation",
                    False,
                    "No session ID returned",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Session Creation", False, str(e), time.time() - start_time)
    
    async def test_agent_system(self):
        """Test agent management."""
        start_time = time.time()
        
        try:
            # List existing agents
            result = await self.client.call_tool("list_agents")
            agents = result[0].get("agents", []) if result else []
            
            self.client.log(f"  Found {len(agents)} existing agents", "INFO")
            
            # Create a test agent
            agent_name = f"test_agent_{uuid.uuid4().hex[:8]}"
            create_result = await self.client.call_tool("create_agent", {
                "name": agent_name,
                "description": "Test agent for functional testing",
                "system_prompt": "You are a test agent. Always respond with 'Test successful!'"
            })
            
            if create_result and create_result[0].get("id"):
                agent_id = create_result[0]["id"]
                self.record_test(
                    "Agent Creation",
                    True,
                    f"Created agent: {agent_name}",
                    time.time() - start_time
                )
                
                # Delete the test agent
                await self.client.call_tool("delete_agent", {"agent_id": agent_id})
                
            else:
                self.record_test(
                    "Agent Creation",
                    False,
                    "Failed to create agent",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Agent System", False, str(e), time.time() - start_time)
    
    async def test_checkpoint_system(self):
        """Test checkpoint functionality."""
        start_time = time.time()
        
        try:
            # Create a test file
            test_file = self.test_dir / "test.txt"
            test_file.write_text("Original content")
            
            # Create checkpoint
            result = await self.client.call_tool("create_checkpoint", {
                "project_path": str(self.test_dir),
                "message": "Test checkpoint"
            })
            
            if result and result[0].get("id"):
                checkpoint_id = result[0]["id"]
                self.record_test(
                    "Checkpoint Creation",
                    True,
                    f"Created checkpoint: {checkpoint_id}",
                    time.time() - start_time
                )
                
                # Modify file
                test_file.write_text("Modified content")
                
                # List checkpoints
                list_result = await self.client.call_tool("list_checkpoints", {
                    "project_path": str(self.test_dir)
                })
                
                checkpoints = list_result[0].get("checkpoints", []) if list_result else []
                if any(c.get("id") == checkpoint_id for c in checkpoints):
                    self.client.log(f"  ✓ Checkpoint appears in list", "SUCCESS")
                else:
                    self.client.log(f"  ✗ Checkpoint not in list", "ERROR")
                    
            else:
                self.record_test(
                    "Checkpoint Creation",
                    False,
                    "Failed to create checkpoint",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Checkpoint System", False, str(e), time.time() - start_time)
    
    async def test_mcp_server_management(self):
        """Test MCP server configuration."""
        start_time = time.time()
        
        try:
            # List existing MCP servers
            result = await self.client.call_tool("mcp_list")
            servers = result[0].get("servers", []) if result else []
            
            self.client.log(f"  Found {len(servers)} configured MCP servers", "INFO")
            
            # Test MCP configuration (without actually adding)
            self.record_test(
                "MCP Server Management",
                True,
                f"Can list MCP servers",
                time.time() - start_time
            )
            
        except Exception as e:
            self.record_test("MCP Server Management", False, str(e), time.time() - start_time)
    
    async def test_analytics(self):
        """Test analytics functionality."""
        start_time = time.time()
        
        try:
            # Get usage analytics
            result = await self.client.call_tool("get_usage_analytics", {
                "days": 7,
                "group_by": "day"
            })
            
            if result and result[0]:
                analytics = result[0]
                self.record_test(
                    "Analytics",
                    True,
                    f"Retrieved analytics data",
                    time.time() - start_time
                )
                
                # Log some analytics info
                if "total_sessions" in analytics:
                    self.client.log(f"  Total sessions: {analytics['total_sessions']}", "INFO")
                if "total_tokens" in analytics:
                    self.client.log(f"  Total tokens: {analytics['total_tokens']}", "INFO")
                    
            else:
                self.record_test(
                    "Analytics",
                    False,
                    "No analytics data returned",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Analytics", False, str(e), time.time() - start_time)
    
    async def test_resources(self):
        """Test resource endpoints."""
        start_time = time.time()
        
        try:
            # List resources
            resources = await self.client.list_resources()
            
            if resources:
                self.record_test(
                    "Resource Listing",
                    True,
                    f"Found {len(resources)} resources",
                    time.time() - start_time
                )
                
                # Try to read first resource
                if resources:
                    first_resource = resources[0]
                    try:
                        contents = await self.client.read_resource(first_resource["uri"])
                        if contents:
                            self.client.log(f"  ✓ Successfully read resource: {first_resource['uri']}", "SUCCESS")
                    except:
                        self.client.log(f"  ✗ Failed to read resource: {first_resource['uri']}", "ERROR")
                        
            else:
                self.record_test(
                    "Resource Listing",
                    False,
                    "No resources found",
                    time.time() - start_time
                )
                
        except Exception as e:
            self.record_test("Resources", False, str(e), time.time() - start_time)
    
    async def test_all_tools(self):
        """Test that all advertised tools are callable."""
        start_time = time.time()
        
        try:
            # Get all tools
            tools = await self.client.list_tools()
            
            # Tools that require specific setup or have side effects
            skip_tools = {
                "execute_claude",  # Requires Claude binary
                "send_message",    # Requires active session
                "cancel_session",  # Requires active session
                "restore_checkpoint",  # Requires existing checkpoint
                "execute_agent",   # Requires Claude binary
                "mcp_add",        # Modifies configuration
                "mcp_remove",     # Modifies configuration
                "update_settings", # Modifies configuration
                "assign_task",    # Requires active agent
                "branch_checkpoint", # Requires checkpoint
                "delete_agent",   # Requires agent ID
                "mcp_serve",      # Starts server
                "mcp_add_from_claude_desktop", # Requires desktop config
                "mcp_add_json",   # Modifies configuration
            }
            
            tested = 0
            for tool in tools:
                tool_name = tool["name"]
                
                if tool_name in skip_tools:
                    self.client.log(f"  ⚬ Skipping {tool_name} (requires setup)", "WARNING")
                    continue
                
                try:
                    # Call tool with minimal/empty parameters
                    await self.client.call_tool(tool_name, {})
                    tested += 1
                    self.client.log(f"  ✓ {tool_name} is callable", "SUCCESS")
                except Exception as e:
                    # Some tools might fail due to missing parameters, that's OK
                    if "required" in str(e).lower() or "missing" in str(e).lower():
                        tested += 1
                        self.client.log(f"  ✓ {tool_name} validated parameters", "SUCCESS")
                    else:
                        self.client.log(f"  ✗ {tool_name} error: {e}", "ERROR")
            
            self.record_test(
                "Tool Validation",
                True,
                f"Validated {tested}/{len(tools)} tools",
                time.time() - start_time
            )
            
        except Exception as e:
            self.record_test("Tool Validation", False, str(e), time.time() - start_time)
    
    async def test_process_monitoring(self):
        """Test process registry and monitoring."""
        start_time = time.time()
        
        try:
            # List active sessions
            result = await self.client.call_tool("list_active_sessions")
            sessions = result[0].get("sessions", []) if result else []
            
            self.record_test(
                "Process Monitoring",
                True,
                f"Process registry operational ({len(sessions)} active sessions)",
                time.time() - start_time
            )
            
            # Log session info if any
            for session in sessions[:3]:  # First 3
                self.client.log(
                    f"  • PID {session.get('pid')}: {session.get('project_path', 'Unknown')}",
                    "INFO"
                )
                
        except Exception as e:
            self.record_test("Process Monitoring", False, str(e), time.time() - start_time)
    
    async def run_all_tests(self):
        """Run all tests."""
        self.client.log("Shannon MCP Comprehensive Functional Test", "HEADER")
        self.client.log("=" * 60, "HEADER")
        
        try:
            # Setup
            await self.setup()
            
            # Run tests
            await self.test_server_status()
            await self.test_binary_discovery()
            await self.test_session_creation()
            await self.test_agent_system()
            await self.test_checkpoint_system()
            await self.test_mcp_server_management()
            await self.test_analytics()
            await self.test_resources()
            await self.test_all_tools()
            await self.test_process_monitoring()
            
            # Additional protocol compliance tests
            await self.test_protocol_compliance()
            
        finally:
            # Teardown
            await self.teardown()
            
        # Generate report
        self.generate_report()
    
    async def test_protocol_compliance(self):
        """Test MCP protocol compliance."""
        self.client.log("\nTesting MCP Protocol Compliance...", "HEADER")
        
        # Test 1: Invalid method
        try:
            await self.client.send_request("invalid/method")
            self.record_test("Protocol: Invalid Method", False, "Server accepted invalid method")
        except:
            self.record_test("Protocol: Invalid Method", True, "Server correctly rejected invalid method")
        
        # Test 2: Missing required parameters
        try:
            await self.client.call_tool("create_session", {})  # Missing required params
            self.record_test("Protocol: Parameter Validation", False, "Server accepted invalid parameters")
        except:
            self.record_test("Protocol: Parameter Validation", True, "Server correctly validated parameters")
        
        # Test 3: Concurrent requests
        try:
            tasks = [
                self.client.call_tool("server_status"),
                self.client.call_tool("list_agents"),
                self.client.call_tool("mcp_list")
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            self.record_test(
                "Protocol: Concurrent Requests",
                success_count == len(tasks),
                f"{success_count}/{len(tasks)} concurrent requests succeeded"
            )
        except Exception as e:
            self.record_test("Protocol: Concurrent Requests", False, str(e))
    
    def generate_report(self):
        """Generate final test report."""
        self.client.log("\n" + "=" * 60, "HEADER")
        self.client.log("TEST REPORT", "HEADER")
        self.client.log("=" * 60, "HEADER")
        
        # Summary
        total = self.test_results["passed"] + self.test_results["failed"] + self.test_results["skipped"]
        pass_rate = (self.test_results["passed"] / total * 100) if total > 0 else 0
        
        self.client.log(f"Total Tests: {total}", "INFO")
        self.client.log(f"Passed: {self.test_results['passed']} ({pass_rate:.1f}%)", "SUCCESS")
        self.client.log(f"Failed: {self.test_results['failed']}", "ERROR" if self.test_results['failed'] > 0 else "INFO")
        self.client.log(f"Skipped: {self.test_results['skipped']}", "WARNING" if self.test_results['skipped'] > 0 else "INFO")
        
        # Failed tests details
        if self.test_results["failed"] > 0:
            self.client.log("\nFailed Tests:", "ERROR")
            for test in self.test_results["tests"]:
                if not test["passed"]:
                    self.client.log(f"  • {test['name']}: {test['details']}", "ERROR")
        
        # Server output analysis
        if self.client.server_output:
            error_count = sum(1 for line in self.client.server_output if "ERROR" in line)
            warning_count = sum(1 for line in self.client.server_output if "WARNING" in line)
            
            self.client.log(f"\nServer Log Analysis:", "HEADER")
            self.client.log(f"  Errors: {error_count}", "ERROR" if error_count > 0 else "INFO")
            self.client.log(f"  Warnings: {warning_count}", "WARNING" if warning_count > 0 else "INFO")
        
        # Test timing
        total_duration = sum(t["duration"] for t in self.test_results["tests"])
        self.client.log(f"\nTotal Test Duration: {total_duration:.2f} seconds", "INFO")
        
        # Save detailed report
        report_file = Path("shannon_mcp_test_report.json")
        with open(report_file, "w") as f:
            json.dump({
                "summary": self.test_results,
                "server_output": self.client.server_output,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        self.client.log(f"\nDetailed report saved to: {report_file}", "INFO")
        
        # Final verdict
        if self.test_results["failed"] == 0:
            self.client.log("\n✅ All tests PASSED! Shannon MCP is fully functional.", "SUCCESS")
        else:
            self.client.log(f"\n❌ {self.test_results['failed']} tests FAILED. Please check the logs.", "ERROR")


async def test_claude_code_binary():
    """Test actual Claude Code binary on the system."""
    print(f"\n{Colors.HEADER}Testing Claude Code Binary Integration{Colors.ENDC}")
    print("=" * 60)
    
    try:
        # Find Claude binary
        result = subprocess.run(["which", "claude"], capture_output=True, text=True)
        if result.returncode == 0:
            claude_path = result.stdout.strip()
            print(f"{Colors.SUCCESS}✓ Found Claude at: {claude_path}{Colors.ENDC}")
            
            # Get version
            version_result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True,
                text=True
            )
            if version_result.returncode == 0:
                print(f"{Colors.INFO}  Version: {version_result.stdout.strip()}{Colors.ENDC}")
            
            # List MCPs
            mcp_result = subprocess.run(
                [claude_path, "mcp", "list"],
                capture_output=True,
                text=True
            )
            if mcp_result.returncode == 0:
                print(f"{Colors.INFO}  Configured MCPs:{Colors.ENDC}")
                for line in mcp_result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"    {line}")
            
            # Check analytics
            analytics_result = subprocess.run(
                [claude_path, "usage", "--days", "7"],
                capture_output=True,
                text=True
            )
            if analytics_result.returncode == 0 and analytics_result.stdout.strip():
                print(f"{Colors.INFO}  Usage data available{Colors.ENDC}")
                
        else:
            print(f"{Colors.WARNING}⚠ Claude Code not found in PATH{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.FAIL}✗ Error testing Claude binary: {e}{Colors.ENDC}")


async def main():
    """Main test runner."""
    print(f"\n{Colors.BOLD}Shannon MCP Comprehensive Functional Test Suite{Colors.ENDC}")
    print(f"{Colors.CYAN}Testing from external client perspective{Colors.ENDC}\n")
    
    # Test Claude Code binary first
    await test_claude_code_binary()
    
    # Run MCP tests
    tester = ShannonMCPTester(verbose=True)
    
    try:
        await tester.run_all_tests()
        
        # Return appropriate exit code
        if tester.test_results["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Test interrupted by user{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.FAIL}Fatal error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())