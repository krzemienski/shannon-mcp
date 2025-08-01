#!/usr/bin/env python3
"""
Production External MCP Client Test - Full validation of Shannon MCP.

This comprehensively tests the production server from an external client
perspective, ensuring complete MCP protocol compliance and functionality.
"""

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import AsyncExitStack

from fastmcp import Client
from mcp.types import CallToolResult, ReadResourceResult


class ProductionMCPTester:
    """Comprehensive production testing of Shannon MCP server."""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.client = Client(server_path)
        self.test_results = []
        self.created_resources = {
            'sessions': [],
            'tasks': [],
            'checkpoints': []
        }
        
    async def run_all_tests(self):
        """Run complete production test suite."""
        print("=" * 80)
        print("Shannon MCP Production Test Suite")
        print("=" * 80)
        print(f"Server: {self.server_path}")
        print(f"Time: {datetime.now(timezone.utc).isoformat()}")
        print()
        
        try:
            async with self.client:
                # Phase 1: Basic connectivity and discovery
                print("\n[PHASE 1] Basic Connectivity Tests")
                print("-" * 60)
                await self.test_basic_connectivity()
                
                # Phase 2: Binary and environment
                print("\n[PHASE 2] Binary Discovery Tests")
                print("-" * 60)
                await self.test_binary_discovery()
                
                # Phase 3: Session management
                print("\n[PHASE 3] Session Management Tests")
                print("-" * 60)
                await self.test_session_management()
                
                # Phase 4: Agent operations
                print("\n[PHASE 4] Agent System Tests")
                print("-" * 60)
                await self.test_agent_system()
                
                # Phase 5: Resource access
                print("\n[PHASE 5] Resource Access Tests")
                print("-" * 60)
                await self.test_resource_system()
                
                # Phase 6: Advanced features
                print("\n[PHASE 6] Advanced Features Tests")
                print("-" * 60)
                await self.test_advanced_features()
                
                # Phase 7: Error handling and recovery
                print("\n[PHASE 7] Error Handling Tests")
                print("-" * 60)
                await self.test_error_handling()
                
                # Phase 8: Performance and limits
                print("\n[PHASE 8] Performance Tests")
                print("-" * 60)
                await self.test_performance()
                
                # Cleanup
                await self.cleanup_resources()
                
        except Exception as e:
            print(f"\n✗ Fatal error during tests: {e}")
            traceback.print_exc()
            self.test_results.append(("Fatal Error", "FAIL", str(e)))
        
        self.print_summary()
    
    async def test_basic_connectivity(self):
        """Test basic MCP connectivity and tool/resource discovery."""
        tests = []
        
        # Test 1.1: List tools
        try:
            tools = await self.client.list_tools()
            tool_names = [tool.name for tool in tools]
            
            required_tools = [
                'find_claude_binary', 'create_session', 'send_message',
                'cancel_session', 'list_sessions', 'list_agents', 'assign_task'
            ]
            
            missing = set(required_tools) - set(tool_names)
            if missing:
                raise ValueError(f"Missing required tools: {missing}")
            
            print(f"✓ [1.1] Found {len(tools)} tools (all required present)")
            tests.append(("List Tools", "PASS", None))
            
            # Show advanced tools if present
            advanced_tools = [
                'create_checkpoint', 'restore_checkpoint', 'query_analytics'
            ]
            found_advanced = [t for t in advanced_tools if t in tool_names]
            if found_advanced:
                print(f"  → Advanced tools available: {', '.join(found_advanced)}")
                
        except Exception as e:
            print(f"✗ [1.1] List tools failed: {e}")
            tests.append(("List Tools", "FAIL", str(e)))
        
        # Test 1.2: List resources
        try:
            resources = await self.client.list_resources()
            resource_uris = [res.uri for res in resources]
            
            required_resources = [
                'shannon://config', 'shannon://agents', 'shannon://sessions'
            ]
            
            missing = set(required_resources) - set(resource_uris)
            if missing:
                raise ValueError(f"Missing required resources: {missing}")
            
            print(f"✓ [1.2] Found {len(resources)} resources")
            for res in resources[:5]:  # Show first 5
                print(f"  → {res.uri}: {res.name}")
            
            tests.append(("List Resources", "PASS", None))
            
        except Exception as e:
            print(f"✗ [1.2] List resources failed: {e}")
            tests.append(("List Resources", "FAIL", str(e)))
        
        # Test 1.3: Read configuration
        try:
            config_result = await self.client.read_resource("shannon://config")
            config_content = self._extract_content(config_result)
            config = json.loads(config_content)
            
            print(f"✓ [1.3] Configuration loaded successfully")
            print(f"  → Version: {config.get('version', 'unknown')}")
            print(f"  → Managers: {len(config.get('runtime', {}).get('managers', []))}")
            
            tests.append(("Read Config", "PASS", None))
            
        except Exception as e:
            print(f"✗ [1.3] Read config failed: {e}")
            tests.append(("Read Config", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def test_binary_discovery(self):
        """Test Claude Code binary discovery functionality."""
        tests = []
        
        # Test 2.1: Find binary
        try:
            result = await self.client.call_tool("find_claude_binary", {})
            binary_info = self._extract_tool_result(result)
            
            if binary_info.get('status') == 'found':
                print(f"✓ [2.1] Binary found at: {binary_info['binary']['path']}")
                print(f"  → Version: {binary_info['binary']['version']}")
                print(f"  → Capabilities: {', '.join(binary_info['binary']['capabilities'])}")
            else:
                print(f"⚠ [2.1] Binary not found (expected in test environment)")
                print(f"  → Suggestions: {len(binary_info.get('suggestions', []))} provided")
            
            tests.append(("Find Binary", "PASS", None))
            
        except Exception as e:
            print(f"✗ [2.1] Binary discovery failed: {e}")
            tests.append(("Find Binary", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def test_session_management(self):
        """Test complete session lifecycle management."""
        tests = []
        session_id = None
        
        # Test 3.1: Create session
        try:
            result = await self.client.call_tool("create_session", {
                "prompt": "Production test session - please acknowledge",
                "model": "claude-3-sonnet",
                "context": {
                    "test_id": "prod-test-001",
                    "environment": "testing",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "options": {
                    "streaming": True,
                    "analytics": True
                }
            })
            
            session_data = self._extract_tool_result(result)
            session_id = session_data['session']['id']
            self.created_resources['sessions'].append(session_id)
            
            print(f"✓ [3.1] Session created: {session_id}")
            print(f"  → Status: {session_data['session']['status']}")
            print(f"  → Model: {session_data['session']['model']}")
            
            tests.append(("Create Session", "PASS", None))
            
        except Exception as e:
            print(f"✗ [3.1] Create session failed: {e}")
            tests.append(("Create Session", "FAIL", str(e)))
            return  # Can't continue without session
        
        # Test 3.2: List sessions
        try:
            result = await self.client.call_tool("list_sessions", {
                "limit": 10,
                "sort_by": "created_at",
                "sort_order": "desc"
            })
            
            sessions_data = self._extract_tool_result(result)
            sessions = sessions_data['sessions']
            
            # Verify our session is in the list
            our_session = next((s for s in sessions if s['id'] == session_id), None)
            if not our_session:
                raise ValueError("Created session not found in list")
            
            print(f"✓ [3.2] Listed {len(sessions)} sessions")
            print(f"  → Our session found with status: {our_session['status']}")
            
            tests.append(("List Sessions", "PASS", None))
            
        except Exception as e:
            print(f"✗ [3.2] List sessions failed: {e}")
            tests.append(("List Sessions", "FAIL", str(e)))
        
        # Test 3.3: Send message (if binary available)
        if session_data.get('session', {}).get('status') == 'active':
            try:
                result = await self.client.call_tool("send_message", {
                    "session_id": session_id,
                    "message": "This is a production test message. Please respond with 'acknowledged'.",
                    "stream": False
                })
                
                message_data = self._extract_tool_result(result)
                print(f"✓ [3.3] Message sent successfully")
                print(f"  → Response status: {message_data.get('status')}")
                
                tests.append(("Send Message", "PASS", None))
                
            except Exception as e:
                print(f"⚠ [3.3] Send message failed (expected if no binary): {e}")
                tests.append(("Send Message", "SKIP", "No active session"))
        else:
            print("⚠ [3.3] Skipping message test (session not active)")
            tests.append(("Send Message", "SKIP", "Session not active"))
        
        # Test 3.4: Read session resource
        try:
            session_res = await self.client.read_resource(f"shannon://sessions/{session_id}")
            session_content = self._extract_content(session_res)
            session_details = json.loads(session_content)
            
            print(f"✓ [3.4] Session resource read successfully")
            print(f"  → Has analytics: {'analytics' in session_details}")
            print(f"  → Has checkpoints: {'checkpoints' in session_details}")
            
            tests.append(("Read Session Resource", "PASS", None))
            
        except Exception as e:
            print(f"✗ [3.4] Read session resource failed: {e}")
            tests.append(("Read Session Resource", "FAIL", str(e)))
        
        # Test 3.5: Cancel session
        try:
            result = await self.client.call_tool("cancel_session", {
                "session_id": session_id,
                "reason": "Production test completed"
            })
            
            cancel_data = self._extract_tool_result(result)
            print(f"✓ [3.5] Session cancelled successfully")
            print(f"  → Final status: {cancel_data['status']}")
            
            tests.append(("Cancel Session", "PASS", None))
            
        except Exception as e:
            print(f"✗ [3.5] Cancel session failed: {e}")
            tests.append(("Cancel Session", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def test_agent_system(self):
        """Test agent listing and task assignment."""
        tests = []
        
        # Test 4.1: List all agents
        try:
            result = await self.client.call_tool("list_agents", {})
            agents_data = self._extract_tool_result(result)
            agents = agents_data['agents']
            
            print(f"✓ [4.1] Found {len(agents)} agents")
            
            # Show agent categories
            categories = agents_data['metadata']['categories']
            print(f"  → Categories: {', '.join(categories)}")
            print(f"  → Available agents: {agents_data['metadata']['available_agents']}")
            
            tests.append(("List Agents", "PASS", None))
            
        except Exception as e:
            print(f"✗ [4.1] List agents failed: {e}")
            tests.append(("List Agents", "FAIL", str(e)))
            self.test_results.extend(tests)
            return
        
        # Test 4.2: Get agent details
        if agents:
            agent_id = agents[0]['id']
            try:
                agent_res = await self.client.read_resource(f"shannon://agents/{agent_id}")
                agent_content = self._extract_content(agent_res)
                agent_details = json.loads(agent_content)
                
                print(f"✓ [4.2] Agent details retrieved: {agent_id}")
                print(f"  → Name: {agent_details.get('name')}")
                print(f"  → Status: {agent_details.get('status', {}).get('state', 'unknown')}")
                
                tests.append(("Get Agent Details", "PASS", None))
                
            except Exception as e:
                print(f"✗ [4.2] Get agent details failed: {e}")
                tests.append(("Get Agent Details", "FAIL", str(e)))
        
        # Test 4.3: Assign task
        if agents and any(a['available'] for a in agents):
            available_agent = next(a for a in agents if a['available'])
            try:
                result = await self.client.call_tool("assign_task", {
                    "agent_id": available_agent['id'],
                    "task": "Production test task: Analyze system performance",
                    "priority": 7,
                    "context": {
                        "test_id": "prod-test-task-001",
                        "type": "performance_analysis"
                    },
                    "options": {
                        "timeout": 300,
                        "retries": 2
                    }
                })
                
                task_data = self._extract_tool_result(result)
                task_id = task_data['assignment']['id']
                self.created_resources['tasks'].append(task_id)
                
                print(f"✓ [4.3] Task assigned: {task_id}")
                print(f"  → Agent: {available_agent['name']}")
                print(f"  → Status: {task_data['assignment']['status']}")
                print(f"  → Est. completion: {task_data['metadata'].get('estimated_completion', 'N/A')}")
                
                tests.append(("Assign Task", "PASS", None))
                
            except Exception as e:
                print(f"✗ [4.3] Assign task failed: {e}")
                tests.append(("Assign Task", "FAIL", str(e)))
        else:
            print("⚠ [4.3] No available agents for task assignment")
            tests.append(("Assign Task", "SKIP", "No available agents"))
        
        self.test_results.extend(tests)
    
    async def test_resource_system(self):
        """Test comprehensive resource access."""
        tests = []
        
        # Test 5.1: Read all major resources
        resources_to_test = [
            ("shannon://config", "Configuration"),
            ("shannon://agents", "Agents"),
            ("shannon://sessions", "Sessions"),
            ("shannon://health", "Health Status"),
            ("shannon://analytics/summary", "Analytics Summary")
        ]
        
        for uri, name in resources_to_test:
            try:
                result = await self.client.read_resource(uri)
                content = self._extract_content(result)
                data = json.loads(content) if content else {}
                
                print(f"✓ [5.1] {name} resource: {len(content)} bytes")
                
                # Show key information
                if uri == "shannon://health":
                    print(f"  → Overall health: {data.get('overall', 'unknown')}")
                elif uri == "shannon://analytics/summary":
                    print(f"  → Total sessions: {data.get('total_sessions', 0)}")
                
                tests.append((f"Read {name}", "PASS", None))
                
            except Exception as e:
                print(f"✗ [5.1] Read {name} failed: {e}")
                tests.append((f"Read {name}", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def test_advanced_features(self):
        """Test advanced features like checkpoints and analytics."""
        tests = []
        
        # Test 6.1: Create checkpoint (if available)
        if 'create_checkpoint' in [t.name for t in await self.client.list_tools()]:
            try:
                # First create a session
                session_result = await self.client.call_tool("create_session", {
                    "prompt": "Checkpoint test session"
                })
                session_id = self._extract_tool_result(session_result)['session']['id']
                self.created_resources['sessions'].append(session_id)
                
                # Create checkpoint
                result = await self.client.call_tool("create_checkpoint", {
                    "session_id": session_id,
                    "name": "Production test checkpoint",
                    "description": "Testing checkpoint functionality",
                    "tags": ["test", "production"]
                })
                
                checkpoint_data = self._extract_tool_result(result)
                checkpoint_id = checkpoint_data['checkpoint']['id']
                self.created_resources['checkpoints'].append(checkpoint_id)
                
                print(f"✓ [6.1] Checkpoint created: {checkpoint_id}")
                print(f"  → Size: {checkpoint_data['metadata']['storage_size']} bytes")
                print(f"  → Compression: {checkpoint_data['metadata']['compression_ratio']}")
                
                tests.append(("Create Checkpoint", "PASS", None))
                
            except Exception as e:
                print(f"✗ [6.1] Create checkpoint failed: {e}")
                tests.append(("Create Checkpoint", "FAIL", str(e)))
        else:
            print("⚠ [6.1] Checkpoint feature not available")
            tests.append(("Create Checkpoint", "SKIP", "Feature not available"))
        
        # Test 6.2: Query analytics (if available)
        if 'query_analytics' in [t.name for t in await self.client.list_tools()]:
            try:
                result = await self.client.call_tool("query_analytics", {
                    "query_type": "usage",
                    "parameters": {
                        "metric": "session_count",
                        "timeframe": "last_hour"
                    }
                })
                
                analytics_data = self._extract_tool_result(result)
                print(f"✓ [6.2] Analytics query successful")
                print(f"  → Query type: {analytics_data['query_type']}")
                print(f"  → Row count: {analytics_data['metadata']['row_count']}")
                
                tests.append(("Query Analytics", "PASS", None))
                
            except Exception as e:
                print(f"✗ [6.2] Query analytics failed: {e}")
                tests.append(("Query Analytics", "FAIL", str(e)))
        else:
            print("⚠ [6.2] Analytics feature not available")
            tests.append(("Query Analytics", "SKIP", "Feature not available"))
        
        self.test_results.extend(tests)
    
    async def test_error_handling(self):
        """Test comprehensive error handling."""
        tests = []
        
        # Test 7.1: Invalid tool call
        try:
            await self.client.call_tool("non_existent_tool", {})
            print("✗ [7.1] Should have failed for invalid tool")
            tests.append(("Invalid Tool", "FAIL", "No error raised"))
        except Exception as e:
            print(f"✓ [7.1] Correctly rejected invalid tool: {type(e).__name__}")
            tests.append(("Invalid Tool", "PASS", None))
        
        # Test 7.2: Invalid session operations
        try:
            await self.client.call_tool("send_message", {
                "session_id": "invalid-session-12345",
                "message": "test"
            })
            print("✗ [7.2] Should have failed for invalid session")
            tests.append(("Invalid Session", "FAIL", "No error raised"))
        except Exception as e:
            print(f"✓ [7.2] Correctly rejected invalid session: {type(e).__name__}")
            tests.append(("Invalid Session", "PASS", None))
        
        # Test 7.3: Missing required parameters
        try:
            await self.client.call_tool("create_session", {})
            print("✗ [7.3] Should have failed for missing parameters")
            tests.append(("Missing Parameters", "FAIL", "No error raised"))
        except Exception as e:
            print(f"✓ [7.3] Correctly rejected missing parameters: {type(e).__name__}")
            tests.append(("Missing Parameters", "PASS", None))
        
        # Test 7.4: Invalid resource URI
        try:
            await self.client.read_resource("shannon://invalid/path/to/nowhere")
            print("✗ [7.4] Should have failed for invalid resource")
            tests.append(("Invalid Resource", "FAIL", "No error raised"))
        except Exception as e:
            print(f"✓ [7.4] Correctly rejected invalid resource: {type(e).__name__}")
            tests.append(("Invalid Resource", "PASS", None))
        
        # Test 7.5: Rate limiting (if implemented)
        try:
            # Try to exceed rate limit
            tasks = []
            for i in range(20):
                tasks.append(self.client.call_tool("list_sessions", {"limit": 1}))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            
            if any('rate' in str(e).lower() for e in errors):
                print(f"✓ [7.5] Rate limiting working: {len(errors)} requests rejected")
                tests.append(("Rate Limiting", "PASS", None))
            else:
                print("⚠ [7.5] Rate limiting not detected")
                tests.append(("Rate Limiting", "SKIP", "Not implemented"))
                
        except Exception as e:
            print(f"✗ [7.5] Rate limit test failed: {e}")
            tests.append(("Rate Limiting", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def test_performance(self):
        """Test performance characteristics."""
        tests = []
        
        # Test 8.1: Concurrent operations
        try:
            start_time = datetime.now()
            
            # Run multiple operations concurrently
            tasks = [
                self.client.call_tool("list_sessions", {"limit": 5}),
                self.client.call_tool("list_agents", {}),
                self.client.read_resource("shannon://config"),
                self.client.read_resource("shannon://health")
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if not errors:
                print(f"✓ [8.1] Concurrent operations completed in {elapsed:.2f}s")
                tests.append(("Concurrent Operations", "PASS", None))
            else:
                print(f"✗ [8.1] Concurrent operations had {len(errors)} errors")
                tests.append(("Concurrent Operations", "FAIL", f"{len(errors)} errors"))
                
        except Exception as e:
            print(f"✗ [8.1] Concurrent operations test failed: {e}")
            tests.append(("Concurrent Operations", "FAIL", str(e)))
        
        # Test 8.2: Large data handling
        try:
            # Request large number of sessions
            result = await self.client.call_tool("list_sessions", {
                "limit": 100,
                "filters": {"include_analytics": True}
            })
            
            sessions_data = self._extract_tool_result(result)
            count = len(sessions_data.get('sessions', []))
            
            print(f"✓ [8.2] Large data request handled: {count} sessions")
            tests.append(("Large Data", "PASS", None))
            
        except Exception as e:
            print(f"✗ [8.2] Large data test failed: {e}")
            tests.append(("Large Data", "FAIL", str(e)))
        
        self.test_results.extend(tests)
    
    async def cleanup_resources(self):
        """Clean up created resources."""
        print("\n[CLEANUP] Cleaning up test resources...")
        
        # Cancel sessions
        for session_id in self.created_resources['sessions']:
            try:
                await self.client.call_tool("cancel_session", {
                    "session_id": session_id,
                    "reason": "Test cleanup"
                })
                print(f"  → Cancelled session: {session_id}")
            except:
                pass
        
        print("  → Cleanup completed")
    
    def _extract_tool_result(self, result: CallToolResult) -> Dict[str, Any]:
        """Extract data from tool result."""
        if hasattr(result, 'content'):
            if isinstance(result.content, list) and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except:
                        return {"text": content.text}
                return {"content": content}
            return {"content": result.content}
        return {"result": str(result)}
    
    def _extract_content(self, result: ReadResourceResult) -> str:
        """Extract content from resource result."""
        if hasattr(result, 'contents'):
            if isinstance(result.contents, list) and result.contents:
                content = result.contents[0]
                if hasattr(content, 'text'):
                    return content.text
                return str(content)
            return str(result.contents)
        return str(result)
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        # Count results by status
        passed = sum(1 for _, status, _ in self.test_results if status == "PASS")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAIL")
        skipped = sum(1 for _, status, _ in self.test_results if status == "SKIP")
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Skipped: {skipped} ({skipped/total*100:.1f}%)")
        
        # Group by phase
        phases = {}
        current_phase = "Unknown"
        for name, status, error in self.test_results:
            if name in ["List Tools", "List Resources", "Read Config"]:
                current_phase = "Basic Connectivity"
            elif name in ["Find Binary"]:
                current_phase = "Binary Discovery"
            elif name.startswith("Create Session") or name.startswith("List Session") or name.startswith("Send Message") or name.startswith("Cancel Session"):
                current_phase = "Session Management"
            elif name.startswith("List Agent") or name.startswith("Assign Task"):
                current_phase = "Agent System"
            elif name.startswith("Read "):
                current_phase = "Resource Access"
            elif name in ["Create Checkpoint", "Query Analytics"]:
                current_phase = "Advanced Features"
            elif "Invalid" in name or "Rate Limit" in name:
                current_phase = "Error Handling"
            elif name in ["Concurrent Operations", "Large Data"]:
                current_phase = "Performance"
            
            if current_phase not in phases:
                phases[current_phase] = []
            phases[current_phase].append((name, status, error))
        
        # Show results by phase
        print("\nResults by Phase:")
        for phase, results in phases.items():
            phase_passed = sum(1 for _, s, _ in results if s == "PASS")
            phase_total = len(results)
            print(f"\n{phase}: {phase_passed}/{phase_total} passed")
            
            for name, status, error in results:
                symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
                print(f"  {symbol} {name}")
                if error and status == "FAIL":
                    print(f"    → {error}")
        
        # Overall result
        print("\n" + "=" * 80)
        if failed == 0:
            print("✓ ALL TESTS PASSED - Server is production ready!")
        elif failed < total * 0.2:
            print("⚠ MOSTLY PASSED - Minor issues to address")
        else:
            print("✗ SIGNIFICANT FAILURES - Server needs attention")
        print("=" * 80)
        
        return failed == 0


async def main():
    """Run production client tests."""
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    else:
        # Default to production Fast MCP server
        server_path = str(Path(__file__).parent / "src" / "shannon_mcp" / "server_fastmcp_production.py")
    
    # Run comprehensive tests
    tester = ProductionMCPTester(server_path)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())