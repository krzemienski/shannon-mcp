"""
Runner for Shannon MCP functional tests.
Executes all functional tests with proper reporting.
"""

import pytest
import sys
import asyncio
from pathlib import Path
import argparse
from datetime import datetime


def run_functional_tests(args):
    """Run functional tests with specified options."""
    
    # Build pytest arguments
    pytest_args = [
        str(Path(__file__).parent),  # Test directory
        "-v",  # Verbose
        "--tb=short",  # Short traceback format
        f"--maxfail={args.maxfail}",  # Stop after N failures
    ]
    
    # Add specific test file if requested
    if args.test_file:
        pytest_args.append(args.test_file)
    
    # Add specific test if requested
    if args.test_name:
        pytest_args.append(f"-k={args.test_name}")
    
    # Add markers
    if args.markers:
        pytest_args.append(f"-m={args.markers}")
    
    # Show test durations
    if args.durations:
        pytest_args.append(f"--durations={args.durations}")
    
    # Coverage report
    if args.coverage:
        pytest_args.extend([
            "--cov=shannon_mcp",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])
    
    # Parallel execution
    if args.parallel:
        pytest_args.extend(["-n", str(args.parallel)])
    
    # Output format
    if args.junit:
        pytest_args.append(f"--junit-xml={args.junit}")
    
    # Capture output
    if args.capture:
        pytest_args.append(f"--capture={args.capture}")
    
    print(f"\nRunning Shannon MCP Functional Tests")
    print(f"Started at: {datetime.now()}")
    print(f"Arguments: {' '.join(pytest_args)}\n")
    
    # Run tests
    exit_code = pytest.main(pytest_args)
    
    print(f"\nCompleted at: {datetime.now()}")
    
    return exit_code


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Shannon MCP functional tests"
    )
    
    parser.add_argument(
        "--test-file",
        help="Run specific test file (e.g., test_binary_discovery.py)"
    )
    
    parser.add_argument(
        "--test-name",
        "-k",
        help="Run tests matching expression (e.g., 'test_streaming')"
    )
    
    parser.add_argument(
        "--markers",
        "-m",
        help="Run tests with specific markers"
    )
    
    parser.add_argument(
        "--maxfail",
        type=int,
        default=5,
        help="Stop after N failures (default: 5)"
    )
    
    parser.add_argument(
        "--durations",
        type=int,
        metavar="N",
        help="Show N slowest test durations"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        metavar="N",
        help="Run tests in N parallel processes"
    )
    
    parser.add_argument(
        "--junit",
        metavar="FILE",
        help="Generate JUnit XML report"
    )
    
    parser.add_argument(
        "--capture",
        choices=["no", "sys", "fd"],
        default="no",
        help="Per-test output capturing (default: no)"
    )
    
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick smoke tests only"
    )
    
    args = parser.parse_args()
    
    # Quick mode - run only essential tests
    if args.quick:
        args.test_name = "test_discover_system_binaries or test_create_and_execute_session or test_jsonl_stream_parsing"
        args.maxfail = 1
    
    # Check Claude Code availability
    try:
        from shannon_mcp.managers.binary import BinaryManager
        binary_manager = BinaryManager()
        
        # This is sync check - for quick validation
        import subprocess
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("\n⚠️  WARNING: Claude Code binary not found in PATH")
            print("Some tests will be skipped")
            print("Install Claude Code to run all tests\n")
    except Exception as e:
        print(f"\n⚠️  WARNING: Could not check for Claude Code: {e}\n")
    
    # Run tests
    exit_code = run_functional_tests(args)
    
    # Summary
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())