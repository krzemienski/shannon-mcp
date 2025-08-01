#!/usr/bin/env python3
"""
Manual test script for Shannon MCP Server components.
Tests the core functionality built by the multi-agent system.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from shannon_mcp.utils.config import load_config, BinaryManagerConfig, SessionManagerConfig
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging("test-mcp-server")
logger = get_logger("test-mcp-server")


class MCPServerTester:
    """Test harness for Shannon MCP Server components."""
    
    def __init__(self):
        self.results = []
        self.binary_manager = None
        self.session_manager = None
        
    def add_result(self, component: str, test: str, success: bool, details: str = ""):
        """Add a test result."""
        self.results.append({
            "component": component,
            "test": test,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {component} | {test}")
        if details:
            print(f"     Details: {details}")
            
    async def test_binary_manager(self):
        """Test Binary Manager functionality."""
        print("\n=== Testing Binary Manager ===")
        
        try:
            # Create config
            config = BinaryManagerConfig(
                search_paths=["/usr/local/bin", "/usr/bin", "/bin", 
                             str(Path.home() / ".nvm" / "versions" / "node"),
                             str(Path.home() / ".local" / "bin")],
                update_check_interval=3600,
                enable_nvm_search=True,
                enable_which_fallback=True
            )
            
            # Initialize manager
            self.binary_manager = BinaryManager(config)
            await self.binary_manager.initialize()
            
            self.add_result("BinaryManager", "Initialization", True)
            
            # Test discovery
            print("\nDiscovering Claude Code binary...")
            binary = await self.binary_manager.find_binary()
            
            if binary:
                self.add_result("BinaryManager", "Binary Discovery", True, 
                              f"Found at: {binary.path}, Version: {binary.version}")
                
                # Test version parsing
                if binary.version:
                    self.add_result("BinaryManager", "Version Parsing", True, 
                                  f"Parsed version: {binary.version}")
                else:
                    self.add_result("BinaryManager", "Version Parsing", False, 
                                  "No version detected")
            else:
                self.add_result("BinaryManager", "Binary Discovery", False, 
                              "Claude Code binary not found")
                
        except Exception as e:
            self.add_result("BinaryManager", "General Test", False, str(e))
            logger.error(f"Binary manager test failed: {e}")
            
    async def test_session_manager(self):
        """Test Session Manager functionality."""
        print("\n=== Testing Session Manager ===")
        
        if not self.binary_manager:
            self.add_result("SessionManager", "Prerequisites", False, 
                          "Binary manager not initialized")
            return
            
        try:
            # Get binary
            binary = await self.binary_manager.find_binary()
            if not binary:
                self.add_result("SessionManager", "Prerequisites", False, 
                              "No Claude Code binary found")
                return
                
            # Create config
            config = SessionManagerConfig(
                max_sessions=10,
                session_timeout=300,
                enable_checkpoints=True,
                stream_buffer_size=1024
            )
            
            # Initialize manager
            self.session_manager = SessionManager(config, self.binary_manager)
            await self.session_manager.initialize()
            
            self.add_result("SessionManager", "Initialization", True)
            
            # Test session creation
            print("\nCreating test session...")
            session = await self.session_manager.create_session(
                prompt="Hello! Can you tell me about yourself?",
                context={}
            )
            
            if session:
                self.add_result("SessionManager", "Session Creation", True,
                              f"Session ID: {session.id}")
                
                # Wait for response
                print("\nWaiting for Claude's response...")
                await asyncio.sleep(3)
                
                # Check session state
                state = await self.session_manager.get_session_state(session.id)
                self.add_result("SessionManager", "Session State", True,
                              f"State: {state}")
                              
                # Cancel session
                await self.session_manager.cancel_session(session.id)
                self.add_result("SessionManager", "Session Cancellation", True)
            else:
                self.add_result("SessionManager", "Session Creation", False,
                              "Failed to create session")
                
        except Exception as e:
            self.add_result("SessionManager", "General Test", False, str(e))
            logger.error(f"Session manager test failed: {e}")
            
    async def test_streaming(self):
        """Test JSONL streaming functionality."""
        print("\n=== Testing JSONL Streaming ===")
        
        try:
            from shannon_mcp.streaming.parser import JSONLParser
            from shannon_mcp.streaming.buffer import StreamBuffer
            
            # Test parser
            parser = JSONLParser()
            test_data = '{"type":"message","content":"Hello"}\n{"type":"status","state":"running"}\n'
            
            messages = []
            for line in test_data.split('\n'):
                if line:
                    msg = parser.parse_line(line)
                    if msg:
                        messages.append(msg)
                        
            self.add_result("Streaming", "JSONL Parser", len(messages) == 2,
                          f"Parsed {len(messages)} messages")
                          
            # Test buffer
            buffer = StreamBuffer(max_size=1024)
            buffer.add_data(b"Test data\nMore data\n")
            
            lines = []
            async for line in buffer.read_lines():
                lines.append(line)
                if len(lines) >= 2:
                    break
                    
            self.add_result("Streaming", "Stream Buffer", len(lines) == 2,
                          f"Buffered {len(lines)} lines")
                          
        except Exception as e:
            self.add_result("Streaming", "General Test", False, str(e))
            logger.error(f"Streaming test failed: {e}")
            
    async def test_analytics(self):
        """Test Analytics Engine."""
        print("\n=== Testing Analytics Engine ===")
        
        try:
            from shannon_mcp.analytics.writer import JSONLWriter
            from shannon_mcp.analytics.aggregator import MetricsAggregator
            
            # Test writer
            test_dir = Path("/tmp/shannon-mcp-test")
            test_dir.mkdir(exist_ok=True)
            
            writer = JSONLWriter(test_dir, "test_metrics")
            test_metrics = {
                "event": "test_event",
                "timestamp": datetime.now().isoformat(),
                "value": 42
            }
            
            await writer.write(test_metrics)
            await writer.close()
            
            self.add_result("Analytics", "JSONL Writer", True,
                          "Successfully wrote test metrics")
                          
            # Test aggregator
            aggregator = MetricsAggregator()
            aggregator.add_metric(test_metrics)
            
            summary = aggregator.aggregate()
            self.add_result("Analytics", "Metrics Aggregator", True,
                          f"Aggregated {len(summary)} metrics")
                          
        except Exception as e:
            self.add_result("Analytics", "General Test", False, str(e))
            logger.error(f"Analytics test failed: {e}")
            
    async def test_checkpoint_system(self):
        """Test Checkpoint System."""
        print("\n=== Testing Checkpoint System ===")
        
        try:
            from shannon_mcp.checkpoint.cas import ContentAddressableStorage
            from shannon_mcp.checkpoint.checkpoint import CheckpointManager
            
            # Test CAS
            test_dir = Path("/tmp/shannon-mcp-cas-test")
            test_dir.mkdir(exist_ok=True)
            
            cas = ContentAddressableStorage(test_dir)
            content = b"Test content for CAS"
            
            hash_id = await cas.store(content)
            self.add_result("Checkpoint", "CAS Store", True,
                          f"Stored with hash: {hash_id[:8]}...")
                          
            retrieved = await cas.retrieve(hash_id)
            self.add_result("Checkpoint", "CAS Retrieve", 
                          retrieved == content,
                          "Content integrity verified")
                          
            # Test checkpoint manager
            checkpoint_mgr = CheckpointManager(test_dir / "checkpoints")
            await checkpoint_mgr.initialize()
            
            self.add_result("Checkpoint", "Manager Initialization", True)
            
        except Exception as e:
            self.add_result("Checkpoint", "General Test", False, str(e))
            logger.error(f"Checkpoint test failed: {e}")
            
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['component']}: {result['test']}")
                    if result["details"]:
                        print(f"    Reason: {result['details']}")
                        
    async def cleanup(self):
        """Clean up resources."""
        if self.binary_manager:
            await self.binary_manager.cleanup()
        if self.session_manager:
            await self.session_manager.cleanup()
            
    async def run_all_tests(self):
        """Run all tests."""
        print("Shannon MCP Server Component Tests")
        print("==================================")
        print(f"Started at: {datetime.now()}")
        
        await self.test_binary_manager()
        await self.test_session_manager()
        await self.test_streaming()
        await self.test_analytics()
        await self.test_checkpoint_system()
        
        await self.cleanup()
        
        self.print_summary()


async def main():
    """Main entry point."""
    tester = MCPServerTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())