#!/usr/bin/env python3
"""
Production Readiness Gate for MCP Integration Testing

Evaluates comprehensive criteria to determine production readiness.
"""

import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProductionReadinessGate:
    """Production readiness evaluation gate."""
    
    def __init__(self, test_results: Dict[str, Any]):
        self.test_results = test_results
        self.criteria = {
            "stress_test_requirements": {
                "concurrent_sessions": 10,
                "sustained_duration": 300,  # 5 minutes
                "error_threshold": 0.001  # 0.1% error rate under load
            },
            "reliability_requirements": {
                "uptime_percentage": 99.9,
                "recovery_time": 30,  # seconds
                "data_integrity": 100.0  # No data loss
            },
            "performance_requirements": {
                "p95_latency": 1000,  # milliseconds
                "p99_latency": 2000,  # milliseconds
                "throughput_ops_per_sec": 100
            },
            "security_requirements": {
                "authentication_required": True,
                "encryption_enabled": True,
                "audit_logging": True,
                "vulnerability_scan_passed": True
            },
            "operational_requirements": {
                "monitoring_enabled": True,
                "alerting_configured": True,
                "backup_tested": True,
                "documentation_complete": True,
                "runbook_available": True
            },
            "compliance_requirements": {
                "data_privacy": True,
                "security_policies": True,
                "audit_trail": True
            }
        }
        
    async def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate production readiness criteria.
        
        Returns:
            Gate evaluation result
        """
        logger.info("Evaluating production readiness gate")
        
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "criteria": self.criteria,
            "checks": {},
            "passed": False,
            "recommendations": [],
            "risk_assessment": {}
        }
        
        # Check 1: Stress testing
        stress_check = self._check_stress_testing()
        evaluation["checks"]["stress_testing"] = stress_check
        
        # Check 2: Reliability
        reliability_check = self._check_reliability()
        evaluation["checks"]["reliability"] = reliability_check
        
        # Check 3: Performance
        performance_check = self._check_performance_requirements()
        evaluation["checks"]["performance"] = performance_check
        
        # Check 4: Security
        security_check = self._check_security_requirements()
        evaluation["checks"]["security"] = security_check
        
        # Check 5: Operational readiness
        operational_check = self._check_operational_readiness()
        evaluation["checks"]["operational"] = operational_check
        
        # Check 6: Compliance
        compliance_check = self._check_compliance()
        evaluation["checks"]["compliance"] = compliance_check
        
        # Risk assessment
        evaluation["risk_assessment"] = self._assess_risks()
        
        # Generate recommendations
        evaluation["recommendations"] = self._generate_recommendations(evaluation["checks"])
        
        # Overall evaluation
        critical_checks = ["stress_testing", "reliability", "security"]
        critical_passed = all(
            evaluation["checks"].get(check, {}).get("passed", False)
            for check in critical_checks
        )
        
        all_passed = all(
            check.get("passed", False)
            for check in evaluation["checks"].values()
        )
        
        # Production ready if critical checks pass and risk is acceptable
        evaluation["passed"] = (
            critical_passed and
            evaluation["risk_assessment"].get("overall_risk", "high") != "high"
        )
        
        if not evaluation["passed"]:
            if not critical_passed:
                evaluation["decision"] = "NOT_READY_CRITICAL_FAILURES"
            else:
                evaluation["decision"] = "NOT_READY_HIGH_RISK"
        else:
            if all_passed:
                evaluation["decision"] = "READY_FOR_PRODUCTION"
            else:
                evaluation["decision"] = "READY_WITH_CONDITIONS"
        
        return evaluation
    
    def _check_stress_testing(self) -> Dict[str, Any]:
        """Check stress testing results."""
        # Look for concurrent session test results
        stress_metrics = {
            "max_concurrent_tested": 0,
            "sustained_load_duration": 0,
            "error_rate_under_load": 0
        }
        
        if "agents" in self.test_results:
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "concurrent_sessions":
                        details = test.get("details", {})
                        stress_metrics["max_concurrent_tested"] = test.get("target_sessions", 0)
                        if test.get("passed"):
                            stress_metrics["error_rate_under_load"] = 0
                    
                    if test.get("test") == "session_limits":
                        details = test.get("details", {})
                        stress_metrics["max_concurrent_tested"] = max(
                            stress_metrics["max_concurrent_tested"],
                            details.get("sessions_created", 0)
                        )
        
        passed = (
            stress_metrics["max_concurrent_tested"] >= self.criteria["stress_test_requirements"]["concurrent_sessions"] and
            stress_metrics["error_rate_under_load"] <= self.criteria["stress_test_requirements"]["error_threshold"]
        )
        
        return {
            "passed": passed,
            "metrics": stress_metrics,
            "reason": "Stress testing passed" if passed else "Insufficient stress testing"
        }
    
    def _check_reliability(self) -> Dict[str, Any]:
        """Check reliability metrics."""
        reliability_metrics = {
            "session_recovery_tested": False,
            "data_integrity_verified": False,
            "cleanup_successful": False
        }
        
        if "agents" in self.test_results:
            # Check session recovery
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "session_persistence":
                        reliability_metrics["session_recovery_tested"] = test.get("passed", False)
                    
                    if test.get("test") == "resource_cleanup":
                        reliability_metrics["cleanup_successful"] = test.get("passed", False)
            
            # Check data integrity
            file_agent = self.test_results["agents"].get("file_system", {})
            if isinstance(file_agent, dict):
                # Look for any data corruption issues
                data_tests_passed = all(
                    test.get("passed", False)
                    for test in file_agent.get("test_results", [])
                    if "file" in test.get("test", "")
                )
                reliability_metrics["data_integrity_verified"] = data_tests_passed
        
        passed = all(reliability_metrics.values())
        
        return {
            "passed": passed,
            "metrics": reliability_metrics,
            "reason": "Reliability requirements met" if passed else "Reliability issues detected"
        }
    
    def _check_performance_requirements(self) -> Dict[str, Any]:
        """Check performance requirements."""
        performance_metrics = {
            "latency_acceptable": False,
            "throughput_tested": False,
            "streaming_performance": False
        }
        
        if "agents" in self.test_results:
            # Check streaming performance
            streaming_agent = self.test_results["agents"].get("streaming_validator", {})
            if isinstance(streaming_agent, dict):
                for test in streaming_agent.get("test_results", []):
                    if test.get("test") == "realtime_streaming":
                        details = test.get("details", {})
                        avg_latency = details.get("avg_latency_ms", float('inf'))
                        performance_metrics["latency_acceptable"] = (
                            avg_latency < self.criteria["performance_requirements"]["p95_latency"]
                        )
                        performance_metrics["streaming_performance"] = test.get("passed", False)
                    
                    if test.get("test") == "large_streaming":
                        details = test.get("details", {})
                        throughput = details.get("throughput_mbps", 0)
                        performance_metrics["throughput_tested"] = throughput > 1.0
        
        passed = all(performance_metrics.values())
        
        return {
            "passed": passed,
            "metrics": performance_metrics,
            "reason": "Performance requirements met" if passed else "Performance below requirements"
        }
    
    def _check_security_requirements(self) -> Dict[str, Any]:
        """Check security requirements."""
        security_status = {
            "hook_sandboxing": False,
            "permission_enforcement": False,
            "secure_cleanup": False
        }
        
        if "agents" in self.test_results:
            # Check hook security
            hook_agent = self.test_results["agents"].get("hook_validation", {})
            if isinstance(hook_agent, dict):
                for test in hook_agent.get("test_results", []):
                    if test.get("test") == "hook_security":
                        security_status["hook_sandboxing"] = test.get("passed", False)
            
            # Check file permissions
            file_agent = self.test_results["agents"].get("file_system", {})
            if isinstance(file_agent, dict):
                for test in file_agent.get("test_results", []):
                    if test.get("test") == "permission_handling":
                        details = test.get("details", {})
                        security_status["permission_enforcement"] = (
                            test.get("passed", False) and
                            test.get("restricted_access_blocked", False)
                        )
            
            # Check secure cleanup
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "resource_cleanup":
                        security_status["secure_cleanup"] = test.get("passed", False)
        
        # Note: Some security requirements may need external validation
        external_requirements = {
            "authentication_required": "Requires external validation",
            "encryption_enabled": "Requires external validation",
            "audit_logging": "Requires external validation",
            "vulnerability_scan_passed": "Requires external validation"
        }
        
        passed = all(security_status.values())
        
        return {
            "passed": passed,
            "tested_requirements": security_status,
            "external_requirements": external_requirements,
            "reason": "Security requirements partially validated" if passed else "Security issues found"
        }
    
    def _check_operational_readiness(self) -> Dict[str, Any]:
        """Check operational readiness."""
        # These typically require external validation
        operational_status = {
            "error_handling_tested": False,
            "recovery_procedures_tested": False,
            "resource_limits_tested": False
        }
        
        if "agents" in self.test_results:
            # Check error handling
            session_agent = self.test_results["agents"].get("session_testing", {})
            if isinstance(session_agent, dict):
                for test in session_agent.get("test_results", []):
                    if test.get("test") == "error_handling":
                        operational_status["error_handling_tested"] = test.get("passed", False)
                    
                    if test.get("test") == "session_persistence":
                        operational_status["recovery_procedures_tested"] = test.get("passed", False)
                    
                    if test.get("test") == "session_limits":
                        operational_status["resource_limits_tested"] = test.get("passed", False)
        
        external_requirements = {
            "monitoring_enabled": "Requires deployment validation",
            "alerting_configured": "Requires deployment validation",
            "backup_tested": "Requires operational validation",
            "documentation_complete": "Requires manual review",
            "runbook_available": "Requires manual review"
        }
        
        passed = all(operational_status.values())
        
        return {
            "passed": passed,
            "tested_capabilities": operational_status,
            "external_requirements": external_requirements,
            "reason": "Basic operational capabilities tested" if passed else "Operational gaps identified"
        }
    
    def _check_compliance(self) -> Dict[str, Any]:
        """Check compliance requirements."""
        compliance_indicators = {
            "no_sensitive_data_exposed": True,
            "audit_trail_capability": False
        }
        
        if "agents" in self.test_results:
            # Check for any sensitive data exposure
            for agent_result in self.test_results["agents"].values():
                if isinstance(agent_result, dict):
                    for test in agent_result.get("test_results", []):
                        # Check if any test exposed sensitive data
                        if "password" in str(test) or "secret" in str(test):
                            compliance_indicators["no_sensitive_data_exposed"] = False
            
            # Check audit capability through hook system
            hook_agent = self.test_results["agents"].get("hook_validation", {})
            if isinstance(hook_agent, dict):
                # If hooks work, audit trail is possible
                compliance_indicators["audit_trail_capability"] = any(
                    test.get("passed", False)
                    for test in hook_agent.get("test_results", [])
                )
        
        external_requirements = {
            "data_privacy": "Requires legal review",
            "security_policies": "Requires policy validation"
        }
        
        passed = all(compliance_indicators.values())
        
        return {
            "passed": passed,
            "compliance_indicators": compliance_indicators,
            "external_requirements": external_requirements,
            "reason": "Basic compliance requirements met" if passed else "Compliance issues identified"
        }
    
    def _assess_risks(self) -> Dict[str, Any]:
        """Assess deployment risks."""
        risks = {
            "high": [],
            "medium": [],
            "low": []
        }
        
        # Assess based on test results
        if "checks" in self.test_results:
            # High risks
            if not self.test_results["checks"].get("security", {}).get("passed", True):
                risks["high"].append("Security vulnerabilities detected")
            
            if not self.test_results["checks"].get("reliability", {}).get("passed", True):
                risks["high"].append("Reliability issues could cause data loss")
            
            # Medium risks
            if not self.test_results["checks"].get("performance", {}).get("passed", True):
                risks["medium"].append("Performance may degrade under load")
            
            if not self.test_results["checks"].get("operational", {}).get("passed", True):
                risks["medium"].append("Operational procedures incomplete")
            
            # Low risks
            if not self.test_results["checks"].get("compliance", {}).get("passed", True):
                risks["low"].append("Compliance validation incomplete")
        
        # Calculate overall risk
        if risks["high"]:
            overall_risk = "high"
        elif len(risks["medium"]) > 2:
            overall_risk = "high"
        elif risks["medium"]:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        return {
            "risks": risks,
            "overall_risk": overall_risk,
            "mitigation_required": overall_risk in ["high", "medium"]
        }
    
    def _generate_recommendations(self, checks: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on checks."""
        recommendations = []
        
        # Stress testing recommendations
        if not checks.get("stress_testing", {}).get("passed", False):
            recommendations.append(
                "Conduct extended stress testing with higher concurrent load"
            )
        
        # Reliability recommendations
        if not checks.get("reliability", {}).get("passed", False):
            recommendations.append(
                "Implement comprehensive backup and recovery procedures"
            )
        
        # Performance recommendations
        if not checks.get("performance", {}).get("passed", False):
            recommendations.append(
                "Optimize performance bottlenecks before production deployment"
            )
        
        # Security recommendations
        if not checks.get("security", {}).get("passed", False):
            recommendations.append(
                "Complete security audit and penetration testing"
            )
        else:
            recommendations.append(
                "Conduct external security validation and vulnerability scanning"
            )
        
        # Operational recommendations
        recommendations.extend([
            "Set up comprehensive monitoring and alerting",
            "Create detailed runbooks for common scenarios",
            "Establish on-call rotation and escalation procedures",
            "Plan and test disaster recovery procedures"
        ])
        
        # Compliance recommendations
        if not checks.get("compliance", {}).get("passed", False):
            recommendations.append(
                "Complete compliance audit with legal team"
            )
        
        return recommendations