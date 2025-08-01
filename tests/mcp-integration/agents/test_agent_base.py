#!/usr/bin/env python3
"""
Base Test Agent for MCP Integration Testing

Provides the foundation for all autonomous test agents that validate
MCP server functionality with real host system interactions.
"""

import os
import sys
import json
import asyncio
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shannon_mcp.client import ShannonMCPClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestAgentBase(ABC):
    """Base class for all MCP integration test agents."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.test_results = []
        self.start_time = None
        self.end_time = None
        self.mcp_client = None
        self.test_base_dir = Path(os.environ.get(
            "SHANNON_MCP_TEST_BASE",
            "/tmp/shannon-mcp-integration-test"
        ))
        self.results_dir = self.test_base_dir / "test-results" / "agent-reports"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    async def run(self) -> Dict[str, Any]:
        """
        Run the complete test agent workflow.
        
        Returns:
            Test execution results
        """
        logger.info(f"Starting test agent: {self.name}")
        self.start_time = datetime.now()
        
        try:
            # Initialize MCP connection
            await self._initialize_mcp_connection()
            
            # Run pre-test validation
            pre_validation = await self._pre_test_validation()
            if not pre_validation["passed"]:
                return self._create_failure_report("Pre-test validation failed", pre_validation)
            
            # Execute test scenarios
            test_results = await self.execute_test_scenarios()
            
            # Perform post-test validation
            post_validation = await self._post_test_validation()
            
            # Generate report
            report = await self._generate_report(test_results, post_validation)
            
            return report
            
        except Exception as e:
            logger.error(f"Test agent {self.name} failed: {e}")
            return self._create_failure_report(f"Agent execution failed: {e}")
            
        finally:
            self.end_time = datetime.now()
            await self._cleanup()
    
    async def _initialize_mcp_connection(self):
        """Initialize connection to MCP server."""
        logger.info("Initializing MCP connection...")
        
        try:
            self.mcp_client = ShannonMCPClient()
            await self.mcp_client.connect()
            logger.info("MCP connection established")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def _pre_test_validation(self) -> Dict[str, Any]:
        """Perform pre-test validation checks."""
        logger.info("Running pre-test validation...")
        
        validations = {
            "mcp_connected": self.mcp_client is not None and self.mcp_client.connected,
            "test_directories_exist": self._validate_test_directories(),
            "permissions_valid": await self._validate_permissions(),
            "prerequisites_met": await self.validate_prerequisites()
        }
        
        validations["passed"] = all(validations.values())
        return validations
    
    def _validate_test_directories(self) -> bool:
        """Validate required test directories exist."""
        required_dirs = [
            self.test_base_dir,
            self.test_base_dir / "test-projects",
            self.test_base_dir / "test-hooks",
            self.test_base_dir / "test-sessions",
            self.results_dir
        ]
        return all(d.exists() for d in required_dirs)
    
    async def _validate_permissions(self) -> bool:
        """Validate file system permissions."""
        try:
            test_file = self.test_base_dir / f".permission-test-{self.name}"
            test_file.write_text("test")
            test_file.chmod(0o755)
            test_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Permission validation failed: {e}")
            return False
    
    @abstractmethod
    async def validate_prerequisites(self) -> bool:
        """
        Validate agent-specific prerequisites.
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def execute_test_scenarios(self) -> List[Dict[str, Any]]:
        """
        Execute the agent's test scenarios.
        Must be implemented by subclasses.
        """
        pass
    
    async def _post_test_validation(self) -> Dict[str, Any]:
        """Perform post-test validation."""
        logger.info("Running post-test validation...")
        
        return {
            "artifacts_created": await self._validate_artifacts(),
            "no_orphan_processes": await self._check_orphan_processes(),
            "system_state_valid": await self.validate_system_state()
        }
    
    async def _validate_artifacts(self) -> bool:
        """Validate test artifacts were created."""
        # Check if result files exist
        agent_report = self.results_dir / f"{self.name}-{self.start_time.strftime('%Y%m%d-%H%M%S')}.json"
        return agent_report.exists() or len(self.test_results) > 0
    
    async def _check_orphan_processes(self) -> bool:
        """Check for orphaned processes."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "shannon-mcp"],
                capture_output=True,
                text=True
            )
            # Should have some processes (the server) but not too many
            process_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            return process_count <= 5  # Reasonable limit
        except:
            return True
    
    @abstractmethod
    async def validate_system_state(self) -> bool:
        """
        Validate system state after tests.
        Must be implemented by subclasses.
        """
        pass
    
    async def execute_mcp_operation(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP operation and capture results.
        
        Args:
            operation: MCP operation to execute
            params: Operation parameters
            
        Returns:
            Operation results including success status
        """
        logger.info(f"Executing MCP operation: {operation}")
        
        start_time = datetime.now()
        try:
            # Execute operation based on type
            if operation == "create_session":
                result = await self.mcp_client.create_session(**params)
            elif operation == "execute_prompt":
                result = await self.mcp_client.execute_prompt(**params)
            elif operation == "register_hook":
                result = await self.mcp_client.register_hook(**params)
            elif operation == "discover_projects":
                result = await self.mcp_client.discover_projects(**params)
            else:
                result = await self.mcp_client.execute_command(operation, params)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "operation": operation,
                "params": params,
                "result": result,
                "success": True,
                "execution_time": execution_time,
                "timestamp": start_time.isoformat()
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"MCP operation failed: {e}")
            
            return {
                "operation": operation,
                "params": params,
                "error": str(e),
                "success": False,
                "execution_time": execution_time,
                "timestamp": start_time.isoformat()
            }
    
    async def validate_host_system_change(self, expected_change: Dict[str, Any]) -> bool:
        """
        Validate that an expected change occurred on the host system.
        
        Args:
            expected_change: Description of expected change
            
        Returns:
            True if change is validated
        """
        change_type = expected_change.get("type")
        
        if change_type == "file_created":
            path = Path(expected_change["path"])
            return path.exists() and (
                not expected_change.get("content") or 
                path.read_text() == expected_change["content"]
            )
            
        elif change_type == "file_modified":
            path = Path(expected_change["path"])
            if not path.exists():
                return False
            if expected_change.get("contains"):
                return expected_change["contains"] in path.read_text()
            return True
            
        elif change_type == "directory_created":
            path = Path(expected_change["path"])
            return path.exists() and path.is_dir()
            
        elif change_type == "process_running":
            cmd = ["pgrep", "-f", expected_change["pattern"]]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
            
        elif change_type == "hook_executed":
            marker_file = Path(expected_change.get("marker_file", "/tmp/hook-executed.marker"))
            return marker_file.exists()
            
        else:
            logger.warning(f"Unknown change type: {change_type}")
            return False
    
    async def _generate_report(self, test_results: List[Dict[str, Any]], 
                              post_validation: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        report = {
            "agent": {
                "name": self.name,
                "description": self.description
            },
            "execution": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration": (self.end_time - self.start_time).total_seconds()
            },
            "test_results": test_results,
            "post_validation": post_validation,
            "summary": self._generate_summary(test_results)
        }
        
        # Save report
        report_file = self.results_dir / f"{self.name}-{self.start_time.strftime('%Y%m%d-%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to: {report_file}")
        return report
    
    def _generate_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate test summary statistics."""
        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results if r.get("passed", False))
        failed_tests = total_tests - passed_tests
        
        return {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "status": "PASSED" if failed_tests == 0 else "FAILED"
        }
    
    def _create_failure_report(self, reason: str, details: Any = None) -> Dict[str, Any]:
        """Create a failure report."""
        return {
            "agent": {
                "name": self.name,
                "description": self.description
            },
            "status": "FAILED",
            "reason": reason,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _cleanup(self):
        """Clean up resources."""
        logger.info(f"Cleaning up test agent: {self.name}")
        
        if self.mcp_client:
            try:
                await self.mcp_client.disconnect()
            except:
                pass
        
        # Agent-specific cleanup
        await self.cleanup()
    
    @abstractmethod
    async def cleanup(self):
        """
        Agent-specific cleanup.
        Must be implemented by subclasses.
        """
        pass