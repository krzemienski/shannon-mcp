#!/usr/bin/env python3
"""
MCP Integration Test Orchestrator

Orchestrates the execution of all test agents and generates comprehensive
reports for MCP server integration validation.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import logging
import argparse

# Add directories to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import test components
from setup.install_mcp_server import MCPServerInstaller
from setup.configure_environment import TestEnvironmentConfigurator
from agents.file_system_agent import FileSystemAgent
from agents.hook_validation_agent import HookValidationAgent
from agents.session_testing_agent import SessionTestingAgent
from agents.streaming_validator_agent import StreamingValidatorAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTestOrchestrator:
    """Orchestrates MCP integration testing."""
    
    def __init__(self, args):
        self.args = args
        self.test_base_dir = Path(args.test_dir)
        self.results_dir = self.test_base_dir / "test-results"
        self.start_time = None
        self.end_time = None
        self.test_results = {}
        
    async def run(self) -> Dict[str, Any]:
        """Run complete integration test suite."""
        logger.info("Starting MCP Integration Test Suite")
        self.start_time = datetime.now()
        
        try:
            # Phase 1: Setup
            if not self.args.skip_setup:
                setup_results = await self._setup_phase()
                if not setup_results["success"]:
                    return self._create_failure_report("Setup phase failed", setup_results)
                self.test_results["setup"] = setup_results
            
            # Phase 2: Run Test Agents
            agent_results = await self._test_phase()
            self.test_results["agents"] = agent_results
            
            # Phase 3: Validation Gates
            if self.args.production_gates:
                gate_results = await self._gate_phase()
                self.test_results["gates"] = gate_results
            
            # Phase 4: Generate Reports
            report = await self._report_phase()
            self.test_results["report"] = report
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"Test orchestration failed: {e}")
            return self._create_failure_report(f"Orchestration error: {e}")
            
        finally:
            self.end_time = datetime.now()
            if not self.args.skip_cleanup:
                await self._cleanup_phase()
    
    async def _setup_phase(self) -> Dict[str, Any]:
        """Execute setup phase."""
        logger.info("=== SETUP PHASE ===")
        
        setup_results = {
            "server_installation": None,
            "environment_configuration": None,
            "success": False
        }
        
        # Install MCP Server
        if not self.args.skip_install:
            logger.info("Installing MCP server...")
            installer = MCPServerInstaller(self.test_base_dir / "mcp-server")
            install_result = await installer.install()
            setup_results["server_installation"] = install_result
            
            if install_result["status"] != "success":
                return setup_results
        
        # Configure Environment
        logger.info("Configuring test environment...")
        configurator = TestEnvironmentConfigurator(self.test_base_dir)
        config_result = await configurator.configure()
        setup_results["environment_configuration"] = config_result
        
        if config_result["status"] != "ready":
            return setup_results
        
        setup_results["success"] = True
        return setup_results
    
    async def _test_phase(self) -> Dict[str, Any]:
        """Execute test agents."""
        logger.info("=== TEST PHASE ===")
        
        # Define test agents
        test_agents = [
            ("file_system", FileSystemAgent),
            ("hook_validation", HookValidationAgent),
            ("session_testing", SessionTestingAgent),
            ("streaming_validator", StreamingValidatorAgent)
        ]
        
        # Filter agents if specific ones requested
        if self.args.agents:
            requested = set(self.args.agents.split(','))
            test_agents = [(name, cls) for name, cls in test_agents if name in requested]
        
        agent_results = {}
        
        # Run agents based on mode
        if self.args.parallel:
            # Run agents in parallel
            logger.info("Running agents in parallel mode")
            tasks = []
            for name, agent_class in test_agents:
                agent = agent_class()
                tasks.append((name, agent.run()))
            
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            
            for (name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    agent_results[name] = {
                        "status": "FAILED",
                        "error": str(result)
                    }
                else:
                    agent_results[name] = result
        else:
            # Run agents sequentially
            logger.info("Running agents in sequential mode")
            for name, agent_class in test_agents:
                logger.info(f"Running {name} agent...")
                agent = agent_class()
                
                try:
                    result = await agent.run()
                    agent_results[name] = result
                except Exception as e:
                    logger.error(f"Agent {name} failed: {e}")
                    agent_results[name] = {
                        "status": "FAILED",
                        "error": str(e)
                    }
                
                # Stop on failure if not forced
                if not self.args.force and agent_results[name].get("status") == "FAILED":
                    logger.error(f"Stopping due to {name} agent failure")
                    break
        
        return agent_results
    
    async def _gate_phase(self) -> Dict[str, Any]:
        """Execute production gates."""
        logger.info("=== GATE PHASE ===")
        
        gate_results = {
            "pre_deployment": None,
            "production_readiness": None,
            "decision": "NOT_READY"
        }
        
        # Import gates dynamically
        try:
            from gates.pre_deployment_gate import PreDeploymentGate
            from gates.production_readiness_gate import ProductionReadinessGate
        except ImportError:
            logger.warning("Gate modules not found, skipping gate phase")
            return gate_results
        
        # Pre-deployment gate
        pre_gate = PreDeploymentGate(self.test_results)
        pre_result = await pre_gate.evaluate()
        gate_results["pre_deployment"] = pre_result
        
        if not pre_result["passed"]:
            gate_results["decision"] = "FAILED_PRE_DEPLOYMENT"
            return gate_results
        
        # Production readiness gate
        prod_gate = ProductionReadinessGate(self.test_results)
        prod_result = await prod_gate.evaluate()
        gate_results["production_readiness"] = prod_result
        
        if prod_result["passed"]:
            gate_results["decision"] = "READY_FOR_PRODUCTION"
        else:
            gate_results["decision"] = "NEEDS_IMPROVEMENT"
        
        return gate_results
    
    async def _report_phase(self) -> Dict[str, Any]:
        """Generate comprehensive reports."""
        logger.info("=== REPORT PHASE ===")
        
        # Create timestamped results directory
        timestamp = self.start_time.strftime("%Y-%m-%d-%H-%M-%S")
        report_dir = self.results_dir / timestamp
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate summary
        summary = self._generate_summary()
        
        # Write summary report
        summary_file = report_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Copy agent reports
        agent_reports_dir = report_dir / "agent-reports"
        agent_reports_dir.mkdir(exist_ok=True)
        
        # Copy individual agent reports
        source_reports = self.test_base_dir / "test-results" / "agent-reports"
        if source_reports.exists():
            import shutil
            for report in source_reports.glob("*.json"):
                shutil.copy2(report, agent_reports_dir)
        
        # Generate HTML report if requested
        if self.args.html_report:
            html_file = report_dir / "report.html"
            self._generate_html_report(summary, html_file)
        
        logger.info(f"Reports saved to: {report_dir}")
        
        return {
            "report_dir": str(report_dir),
            "summary_file": str(summary_file),
            "summary": summary
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        # Count results
        total_agents = 0
        passed_agents = 0
        total_tests = 0
        passed_tests = 0
        
        if "agents" in self.test_results:
            for agent_name, agent_result in self.test_results["agents"].items():
                total_agents += 1
                
                if isinstance(agent_result, dict):
                    agent_summary = agent_result.get("summary", {})
                    if agent_summary.get("status") == "PASSED":
                        passed_agents += 1
                    
                    # Count individual tests
                    total_tests += agent_summary.get("total_tests", 0)
                    passed_tests += agent_summary.get("passed", 0)
        
        # Overall status
        if passed_agents == total_agents and total_agents > 0:
            overall_status = "PASSED"
        elif passed_agents > 0:
            overall_status = "PARTIAL"
        else:
            overall_status = "FAILED"
        
        # Gate status
        gate_decision = "N/A"
        if "gates" in self.test_results:
            gate_decision = self.test_results["gates"].get("decision", "N/A")
        
        return {
            "execution": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration": (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
            },
            "agents": {
                "total": total_agents,
                "passed": passed_agents,
                "failed": total_agents - passed_agents
            },
            "tests": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0
            },
            "overall_status": overall_status,
            "gate_decision": gate_decision,
            "configuration": {
                "parallel": self.args.parallel,
                "production_gates": self.args.production_gates,
                "agents_run": list(self.test_results.get("agents", {}).keys())
            }
        }
    
    def _generate_html_report(self, summary: Dict[str, Any], output_file: Path):
        """Generate HTML report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>MCP Integration Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .partial {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .agent-result {{ margin-top: 20px; }}
        .test-details {{ margin-left: 20px; }}
    </style>
</head>
<body>
    <h1>MCP Integration Test Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Status:</strong> <span class="{summary['overall_status'].lower()}">{summary['overall_status']}</span></p>
        <p><strong>Duration:</strong> {summary['execution']['duration']:.2f} seconds</p>
        <p><strong>Agents:</strong> {summary['agents']['passed']}/{summary['agents']['total']} passed</p>
        <p><strong>Tests:</strong> {summary['tests']['passed']}/{summary['tests']['total']} passed ({summary['tests']['success_rate']*100:.1f}%)</p>
        <p><strong>Gate Decision:</strong> {summary['gate_decision']}</p>
    </div>
    
    <h2>Agent Results</h2>
"""
        
        # Add agent results
        if "agents" in self.test_results:
            for agent_name, agent_result in self.test_results["agents"].items():
                if isinstance(agent_result, dict):
                    agent_summary = agent_result.get("summary", {})
                    status_class = agent_summary.get("status", "FAILED").lower()
                    
                    html_content += f"""
    <div class="agent-result">
        <h3>{agent_name.replace('_', ' ').title()}</h3>
        <p><strong>Status:</strong> <span class="{status_class}">{agent_summary.get('status', 'FAILED')}</span></p>
        <p><strong>Tests:</strong> {agent_summary.get('passed', 0)}/{agent_summary.get('total_tests', 0)} passed</p>
        
        <table>
            <tr>
                <th>Test</th>
                <th>Status</th>
                <th>Details</th>
            </tr>
"""
                    
                    # Add test results
                    test_results = agent_result.get("test_results", [])
                    for test in test_results:
                        if isinstance(test, dict):
                            test_status = "passed" if test.get("passed", False) else "failed"
                            details = json.dumps(test.get("details", {}), indent=2)
                            
                            html_content += f"""
            <tr>
                <td>{test.get('test', 'Unknown')}</td>
                <td class="{test_status}">{test_status.upper()}</td>
                <td><pre>{details}</pre></td>
            </tr>
"""
                    
                    html_content += """        </table>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html_content)
    
    async def _cleanup_phase(self):
        """Clean up test environment."""
        logger.info("=== CLEANUP PHASE ===")
        
        # Clean test directory if requested
        if self.args.clean_all and self.test_base_dir.exists():
            logger.info(f"Cleaning test directory: {self.test_base_dir}")
            import shutil
            shutil.rmtree(self.test_base_dir)
    
    def _create_failure_report(self, reason: str, details: Any = None) -> Dict[str, Any]:
        """Create a failure report."""
        return {
            "status": "FAILED",
            "reason": reason,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run MCP Integration Tests"
    )
    
    # Test configuration
    parser.add_argument(
        "--test-dir",
        default="/tmp/shannon-mcp-integration-test",
        help="Base directory for tests"
    )
    
    parser.add_argument(
        "--agents",
        help="Comma-separated list of specific agents to run"
    )
    
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run agents in parallel"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continue on agent failures"
    )
    
    # Setup options
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip setup phase"
    )
    
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip MCP server installation"
    )
    
    # Gate options
    parser.add_argument(
        "--production-gates",
        action="store_true",
        help="Run production readiness gates"
    )
    
    # Reporting options
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML report"
    )
    
    # Cleanup options
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip cleanup phase"
    )
    
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Remove entire test directory after completion"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Print configuration
    print("\n" + "="*60)
    print("MCP Integration Test Suite")
    print("="*60)
    print(f"Test Directory: {args.test_dir}")
    print(f"Parallel Mode: {args.parallel}")
    print(f"Production Gates: {args.production_gates}")
    print(f"Agents: {args.agents or 'all'}")
    print("="*60 + "\n")
    
    # Run tests
    orchestrator = IntegrationTestOrchestrator(args)
    results = await orchestrator.run()
    
    # Print summary
    if "report" in results:
        summary = results["report"].get("summary", {})
        print("\n" + "="*60)
        print("Test Results Summary")
        print("="*60)
        print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
        print(f"Agents: {summary['agents']['passed']}/{summary['agents']['total']} passed")
        print(f"Tests: {summary['tests']['passed']}/{summary['tests']['total']} passed")
        print(f"Success Rate: {summary['tests']['success_rate']*100:.1f}%")
        print(f"Gate Decision: {summary.get('gate_decision', 'N/A')}")
        print(f"\nReports saved to: {results['report']['report_dir']}")
        print("="*60)
    
    # Exit with appropriate code
    exit_code = 0 if results.get("report", {}).get("summary", {}).get("overall_status") == "PASSED" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())