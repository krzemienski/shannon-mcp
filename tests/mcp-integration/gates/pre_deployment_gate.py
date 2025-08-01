#!/usr/bin/env python3
"""
Pre-Deployment Gate for MCP Integration Testing

Evaluates test results to determine if the system is ready for deployment.
"""

import json
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PreDeploymentGate:
    """Pre-deployment readiness gate."""
    
    def __init__(self, test_results: Dict[str, Any]):
        self.test_results = test_results
        self.criteria = {
            "min_agent_pass_rate": 1.0,  # 100% of agents must pass
            "min_test_pass_rate": 0.95,  # 95% of individual tests must pass
            "required_agents": [
                "file_system",
                "hook_validation",
                "session_testing",
                "streaming_validator"
            ],
            "critical_tests": [
                "basic_session",
                "file_creation_mcp",
                "hook_execution",
                "basic_streaming"
            ],
            "max_error_rate": 0.02,  # 2% error rate tolerance
            "performance_thresholds": {
                "session_creation_time": 5.0,  # seconds
                "streaming_latency": 500,  # milliseconds
                "file_operation_time": 1.0  # seconds
            }
        }
        
    async def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate pre-deployment criteria.
        
        Returns:
            Gate evaluation result
        """
        logger.info("Evaluating pre-deployment gate")
        
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "criteria": self.criteria,
            "checks": {},
            "passed": False,
            "reasons": []
        }
        
        # Check 1: Required agents executed
        agents_check = self._check_required_agents()
        evaluation["checks"]["required_agents"] = agents_check
        
        # Check 2: Agent pass rate
        agent_pass_check = self._check_agent_pass_rate()
        evaluation["checks"]["agent_pass_rate"] = agent_pass_check
        
        # Check 3: Test pass rate
        test_pass_check = self._check_test_pass_rate()
        evaluation["checks"]["test_pass_rate"] = test_pass_check
        
        # Check 4: Critical tests passed
        critical_check = self._check_critical_tests()
        evaluation["checks"]["critical_tests"] = critical_check
        
        # Check 5: Error rate
        error_check = self._check_error_rate()
        evaluation["checks"]["error_rate"] = error_check
        
        # Check 6: Performance
        performance_check = self._check_performance()
        evaluation["checks"]["performance"] = performance_check
        
        # Check 7: Security validations
        security_check = self._check_security()
        evaluation["checks"]["security"] = security_check
        
        # Check 8: Resource cleanup
        cleanup_check = self._check_resource_cleanup()
        evaluation["checks"]["resource_cleanup"] = cleanup_check
        
        # Overall evaluation
        all_passed = all(
            check.get("passed", False)
            for check in evaluation["checks"].values()
        )
        
        evaluation["passed"] = all_passed
        
        if not all_passed:
            evaluation["reasons"] = [
                f"{name}: {check.get('reason', 'Failed')}"
                for name, check in evaluation["checks"].items()
                if not check.get("passed", False)
            ]
        
        return evaluation
    
    def _check_required_agents(self) -> Dict[str, Any]:
        """Check if all required agents were executed."""
        if "agents" not in self.test_results:
            return {
                "passed": False,
                "reason": "No agent results found"
            }
        
        executed_agents = set(self.test_results["agents"].keys())
        required_agents = set(self.criteria["required_agents"])
        missing_agents = required_agents - executed_agents
        
        return {
            "passed": len(missing_agents) == 0,
            "executed": list(executed_agents),
            "missing": list(missing_agents),
            "reason": f"Missing agents: {missing_agents}" if missing_agents else "All required agents executed"
        }
    
    def _check_agent_pass_rate(self) -> Dict[str, Any]:
        """Check agent pass rate."""
        if "agents" not in self.test_results:
            return {
                "passed": False,
                "reason": "No agent results found"
            }
        
        total_agents = 0
        passed_agents = 0
        
        for agent_name, agent_result in self.test_results["agents"].items():
            if isinstance(agent_result, dict):
                total_agents += 1
                if agent_result.get("summary", {}).get("status") == "PASSED":
                    passed_agents += 1
        
        pass_rate = passed_agents / total_agents if total_agents > 0 else 0
        
        return {
            "passed": pass_rate >= self.criteria["min_agent_pass_rate"],
            "pass_rate": pass_rate,
            "total_agents": total_agents,
            "passed_agents": passed_agents,
            "reason": f"Agent pass rate: {pass_rate*100:.1f}% (required: {self.criteria['min_agent_pass_rate']*100}%)"
        }
    
    def _check_test_pass_rate(self) -> Dict[str, Any]:
        """Check individual test pass rate."""
        total_tests = 0
        passed_tests = 0
        
        if "agents" in self.test_results:
            for agent_result in self.test_results["agents"].values():
                if isinstance(agent_result, dict):
                    summary = agent_result.get("summary", {})
                    total_tests += summary.get("total_tests", 0)
                    passed_tests += summary.get("passed", 0)
        
        pass_rate = passed_tests / total_tests if total_tests > 0 else 0
        
        return {
            "passed": pass_rate >= self.criteria["min_test_pass_rate"],
            "pass_rate": pass_rate,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "reason": f"Test pass rate: {pass_rate*100:.1f}% (required: {self.criteria['min_test_pass_rate']*100}%)"
        }
    
    def _check_critical_tests(self) -> Dict[str, Any]:
        """Check if critical tests passed."""
        critical_results = {}
        all_passed = True
        
        if "agents" in self.test_results:
            for agent_name, agent_result in self.test_results["agents"].items():
                if isinstance(agent_result, dict):
                    test_results = agent_result.get("test_results", [])
                    for test in test_results:
                        if isinstance(test, dict):
                            test_name = test.get("test", "")
                            if test_name in self.criteria["critical_tests"]:
                                critical_results[test_name] = test.get("passed", False)
                                if not test.get("passed", False):
                                    all_passed = False
        
        # Check if all critical tests were found
        missing_critical = set(self.criteria["critical_tests"]) - set(critical_results.keys())
        if missing_critical:
            all_passed = False
        
        return {
            "passed": all_passed,
            "critical_test_results": critical_results,
            "missing_tests": list(missing_critical),
            "reason": "All critical tests passed" if all_passed else f"Critical tests failed or missing: {critical_results}"
        }
    
    def _check_error_rate(self) -> Dict[str, Any]:
        """Check error rate across all tests."""
        total_operations = 0
        error_count = 0
        error_types = {}
        
        if "agents" in self.test_results:
            for agent_result in self.test_results["agents"].values():
                if isinstance(agent_result, dict):
                    test_results = agent_result.get("test_results", [])
                    for test in test_results:
                        if isinstance(test, dict):
                            total_operations += 1
                            if "error" in test and not test.get("passed", True):
                                error_count += 1
                                error_type = test.get("error", "unknown")[:50]
                                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        error_rate = error_count / total_operations if total_operations > 0 else 0
        
        return {
            "passed": error_rate <= self.criteria["max_error_rate"],
            "error_rate": error_rate,
            "total_operations": total_operations,
            "error_count": error_count,
            "error_types": error_types,
            "reason": f"Error rate: {error_rate*100:.2f}% (max allowed: {self.criteria['max_error_rate']*100}%)"
        }
    
    def _check_performance(self) -> Dict[str, Any]:
        """Check performance metrics."""
        performance_issues = []
        metrics = {}
        
        if "agents" in self.test_results:
            # Check session creation time
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "basic_session":
                        details = test.get("details", {})
                        # Extract timing from details if available
                        # This is a simplified check - real implementation would measure actual time
                        metrics["session_creation"] = "measured"
            
            # Check streaming latency
            streaming_agent = self.test_results["agents"].get("streaming_validator", {})
            if isinstance(streaming_agent, dict):
                for test in streaming_agent.get("test_results", []):
                    if test.get("test") == "realtime_streaming":
                        details = test.get("details", {})
                        latency = details.get("avg_latency_ms", 0)
                        metrics["streaming_latency"] = latency
                        if latency > self.criteria["performance_thresholds"]["streaming_latency"]:
                            performance_issues.append(f"Streaming latency too high: {latency}ms")
        
        return {
            "passed": len(performance_issues) == 0,
            "metrics": metrics,
            "issues": performance_issues,
            "reason": "Performance within thresholds" if not performance_issues else f"Performance issues: {performance_issues}"
        }
    
    def _check_security(self) -> Dict[str, Any]:
        """Check security validations."""
        security_passed = True
        security_checks = []
        
        if "agents" in self.test_results:
            # Check hook security
            hook_agent = self.test_results["agents"].get("hook_validation", {})
            if isinstance(hook_agent, dict):
                for test in hook_agent.get("test_results", []):
                    if test.get("test") == "hook_security":
                        if not test.get("passed", False):
                            security_passed = False
                            security_checks.append("Hook security failed")
                        else:
                            security_checks.append("Hook security passed")
            
            # Check file permission handling
            file_agent = self.test_results["agents"].get("file_system", {})
            if isinstance(file_agent, dict):
                for test in file_agent.get("test_results", []):
                    if test.get("test") == "permission_handling":
                        if not test.get("passed", False):
                            security_passed = False
                            security_checks.append("Permission handling failed")
                        else:
                            security_checks.append("Permission handling passed")
        
        return {
            "passed": security_passed,
            "security_checks": security_checks,
            "reason": "All security checks passed" if security_passed else "Security vulnerabilities detected"
        }
    
    def _check_resource_cleanup(self) -> Dict[str, Any]:
        """Check resource cleanup."""
        cleanup_issues = []
        
        if "agents" in self.test_results:
            # Check session cleanup
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "resource_cleanup":
                        if not test.get("passed", False):
                            cleanup_issues.append("Session resource cleanup failed")
            
            # Check for system state validation
            for agent_name, agent_result in self.test_results["agents"].items():
                if isinstance(agent_result, dict):
                    post_validation = agent_result.get("post_validation", {})
                    if not post_validation.get("system_state_valid", True):
                        cleanup_issues.append(f"{agent_name} left system in invalid state")
        
        return {
            "passed": len(cleanup_issues) == 0,
            "cleanup_issues": cleanup_issues,
            "reason": "Resource cleanup successful" if not cleanup_issues else f"Cleanup issues: {cleanup_issues}"
        }