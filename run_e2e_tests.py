#!/usr/bin/env python3
"""
Run E2E tests for Shannon MCP using real system resources.
"""

import subprocess
import sys
import json
import os
import argparse
import time
import platform
import shutil
from pathlib import Path
from datetime import datetime
import tempfile

def setup_test_environment():
    """Set up test environment with real directories."""
    # Create test output directory
    test_output = Path("test_output")
    test_output.mkdir(exist_ok=True)
    
    # Create timestamp-based test run directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = test_output / f"run_{timestamp}"
    run_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "coverage").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    
    return run_dir

def check_system_requirements():
    """Check if system has required dependencies."""
    requirements = {
        "python": sys.version_info >= (3, 11),
        "git": shutil.which("git") is not None,
        "sqlite3": True,  # Usually built into Python
        "disk_space": shutil.disk_usage("/").free > 1_000_000_000  # 1GB free
    }
    
    missing = []
    
    if not requirements["python"]:
        missing.append(f"Python 3.11+ required (found {sys.version})")
    
    if not requirements["git"]:
        missing.append("Git not found in PATH")
    
    if not requirements["disk_space"]:
        missing.append("Less than 1GB free disk space")
    
    return missing

def run_e2e_tests(test_type="all", verbose=True, parallel=False):
    """Run E2E tests with real system resources."""
    print("Shannon MCP E2E Test Runner")
    print("=" * 70)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Test Type: {test_type}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Check requirements
    missing = check_system_requirements()
    if missing:
        print("\n❌ Missing requirements:")
        for req in missing:
            print(f"  - {req}")
        return 1
    
    # Set up environment
    run_dir = setup_test_environment()
    print(f"\nTest output directory: {run_dir}")
    
    # Determine test files
    test_files = {
        "all": ["tests/e2e/"],
        "real": ["tests/e2e/test_real_system_e2e.py"],
        "claude": ["tests/e2e/test_claude_integration_e2e.py"],
        "full": ["tests/e2e/test_full_e2e_coverage.py"],
        "edge": ["tests/e2e/test_edge_cases_coverage.py"],
        "stress": ["tests/e2e/test_real_system_e2e.py::TestRealSystemE2E::test_real_performance_characteristics"]
    }
    
    if test_type not in test_files:
        print(f"Unknown test type: {test_type}")
        print(f"Available: {', '.join(test_files.keys())}")
        return 1
    
    # Build pytest command
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        "-v" if verbose else "-q",
        "--tb=short",
        f"--junit-xml={run_dir}/junit-results.xml",
        f"--html={run_dir}/report.html",
        "--self-contained-html",
        "--maxfail=10",
    ]
    
    # Add parallel execution if requested
    if parallel:
        pytest_cmd.extend(["-n", "auto"])
    
    # Add coverage
    pytest_cmd.extend([
        "--cov=shannon_mcp",
        "--cov-report=term-missing",
        f"--cov-report=html:{run_dir}/coverage",
        f"--cov-report=json:{run_dir}/coverage.json"
    ])
    
    # Add test files
    pytest_cmd.extend(test_files[test_type])
    
    # Set up environment variables
    env = os.environ.copy()
    env.update({
        "SHANNON_TEST_DIR": str(run_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_CURRENT_TEST": "1"
    })
    
    # Create log file
    log_file = run_dir / "logs" / "test_run.log"
    
    print(f"\nRunning tests...")
    print(f"Command: {' '.join(pytest_cmd)}")
    print("-" * 70)
    
    # Run tests
    start_time = time.time()
    
    with open(log_file, "w") as log:
        process = subprocess.Popen(
            pytest_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1
        )
        
        # Stream output
        for line in process.stdout:
            print(line, end="")
            log.write(line)
            log.flush()
        
        process.wait()
    
    duration = time.time() - start_time
    
    # Parse results
    results = parse_test_results(run_dir)
    results["duration"] = duration
    results["test_type"] = test_type
    results["timestamp"] = datetime.now().isoformat()
    
    # Save results
    results_file = run_dir / "test_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total Tests: {results['total']}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Skipped: {results['skipped']} ⏭️")
    print(f"Errors: {results['errors']} 💥")
    print(f"Success Rate: {results['success_rate']:.1f}%")
    
    if results.get('coverage'):
        print(f"\nCode Coverage: {results['coverage']:.1f}%")
    
    print(f"\nFull report: {run_dir}/report.html")
    print(f"Coverage report: {run_dir}/coverage/index.html")
    print(f"Logs: {log_file}")
    
    return process.returncode

def parse_test_results(run_dir):
    """Parse test results from various output files."""
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "success_rate": 0.0,
        "coverage": None
    }
    
    # Parse JUnit XML if available
    junit_file = run_dir / "junit-results.xml"
    if junit_file.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            for testsuite in root.findall('testsuite'):
                results["total"] += int(testsuite.get('tests', 0))
                results["errors"] += int(testsuite.get('errors', 0))
                results["failed"] += int(testsuite.get('failures', 0))
                results["skipped"] += int(testsuite.get('skipped', 0))
            
            results["passed"] = results["total"] - results["failed"] - results["errors"] - results["skipped"]
        except Exception as e:
            print(f"Warning: Could not parse JUnit XML: {e}")
    
    # Parse coverage JSON if available
    coverage_file = run_dir / "coverage.json"
    if coverage_file.exists():
        try:
            with open(coverage_file) as f:
                coverage_data = json.load(f)
                if "totals" in coverage_data:
                    results["coverage"] = coverage_data["totals"].get("percent_covered", 0)
        except Exception as e:
            print(f"Warning: Could not parse coverage JSON: {e}")
    
    # Calculate success rate
    if results["total"] > 0:
        results["success_rate"] = (results["passed"] / results["total"]) * 100
    
    return results

def create_test_report(run_dir):
    """Create a comprehensive test report."""
    report = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "run_directory": str(run_dir)
        },
        "system_info": {
            "cpu_count": os.cpu_count(),
            "memory_gb": round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3), 2),
            "disk_free_gb": round(shutil.disk_usage("/").free / (1024**3), 2)
        },
        "test_files": list(run_dir.rglob("test_*.py")),
        "artifacts": list(run_dir.glob("artifacts/*"))
    }
    
    report_file = run_dir / "full_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    return report_file

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Shannon MCP E2E tests with real system resources"
    )
    parser.add_argument(
        "--type",
        choices=["all", "real", "claude", "full", "edge", "stress"],
        default="all",
        help="Type of E2E tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep test artifacts after run"
    )
    
    args = parser.parse_args()
    
    try:
        return run_e2e_tests(args.type, args.verbose, args.parallel)
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test run failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())