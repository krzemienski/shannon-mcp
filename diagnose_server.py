#!/usr/bin/env python3
"""
Shannon MCP Server Diagnostic Tool

This tool helps diagnose common issues with the Shannon MCP server
by checking dependencies, configurations, and basic functionality.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
import importlib.util

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """Print a section header"""
    print(f"\n{BLUE}=== {text} ==={RESET}")


def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}!{RESET} {text}")


def check_python_version():
    """Check if Python version meets requirements"""
    print_header("Python Version Check")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major == 3 and version.minor >= 11:
        print_success(f"Python {version_str} (meets requirement >=3.11)")
        return True
    else:
        print_error(f"Python {version_str} (requires >=3.11)")
        return False


def check_dependencies():
    """Check if required dependencies are installed"""
    print_header("Dependency Check")
    
    required_packages = [
        ("mcp", "MCP protocol library"),
        ("fastmcp", "FastMCP framework"),
        ("aiosqlite", "Async SQLite support"),
        ("aiofiles", "Async file operations"),
        ("pydantic", "Data validation"),
        ("structlog", "Structured logging"),
        ("psutil", "Process utilities"),
    ]
    
    all_installed = True
    
    for package, description in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is not None:
            try:
                # Try to get version
                module = importlib.import_module(package)
                version = getattr(module, "__version__", "unknown")
                print_success(f"{package} - {description} (version: {version})")
            except:
                print_success(f"{package} - {description}")
        else:
            print_error(f"{package} - {description} (NOT INSTALLED)")
            all_installed = False
    
    return all_installed


def check_project_structure():
    """Check if project structure is correct"""
    print_header("Project Structure Check")
    
    required_paths = [
        ("src/shannon_mcp", "Source directory"),
        ("src/shannon_mcp/server_fastmcp.py", "FastMCP server"),
        ("src/shannon_mcp/stdio_wrapper.py", "STDIO wrapper"),
        ("src/shannon_mcp/managers", "Manager components"),
        ("src/shannon_mcp/utils", "Utilities"),
        ("pyproject.toml", "Poetry configuration"),
    ]
    
    all_exist = True
    
    for path, description in required_paths:
        full_path = Path(path)
        if full_path.exists():
            print_success(f"{path} - {description}")
        else:
            print_error(f"{path} - {description} (NOT FOUND)")
            all_exist = False
    
    return all_exist


def check_environment():
    """Check environment variables and settings"""
    print_header("Environment Check")
    
    # Check for MCP-related environment variables
    mcp_mode = os.environ.get("SHANNON_MCP_MODE")
    if mcp_mode:
        print_warning(f"SHANNON_MCP_MODE is set to: {mcp_mode}")
    else:
        print_success("SHANNON_MCP_MODE not set (will use default)")
    
    # Check for debug mode
    debug = os.environ.get("SHANNON_DEBUG")
    if debug:
        print_warning(f"SHANNON_DEBUG is set to: {debug}")
    else:
        print_success("SHANNON_DEBUG not set (production mode)")
    
    # Check home directory for configs
    claude_dir = Path.home() / ".claude"
    shannon_dir = Path.home() / ".shannon-mcp"
    
    if claude_dir.exists():
        print_success(f"Claude directory exists: {claude_dir}")
    else:
        print_warning(f"Claude directory not found: {claude_dir}")
    
    if shannon_dir.exists():
        print_success(f"Shannon MCP directory exists: {shannon_dir}")
    else:
        print_warning(f"Shannon MCP directory not found: {shannon_dir} (will be created on first run)")
    
    return True


def test_server_startup():
    """Test if the server can start"""
    print_header("Server Startup Test")
    
    server_path = Path("src/shannon_mcp/stdio_wrapper.py")
    if not server_path.exists():
        print_error("Server script not found")
        return False
    
    try:
        # Try to start the server
        print("Attempting to start server...")
        process = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send a simple MCP initialize message
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "Diagnostic Tool",
                    "version": "1.0.0"
                }
            }
        }
        
        process.stdin.write(json.dumps(init_message) + "\n")
        process.stdin.flush()
        
        # Wait for response with timeout
        import select
        readable, _, _ = select.select([process.stdout], [], [], 5.0)
        
        if readable:
            response = process.stdout.readline()
            if response:
                try:
                    resp_data = json.loads(response)
                    if "result" in resp_data:
                        print_success("Server responded to initialize request")
                        print(f"  Server name: {resp_data['result'].get('serverInfo', {}).get('name', 'Unknown')}")
                        print(f"  Server version: {resp_data['result'].get('serverInfo', {}).get('version', 'Unknown')}")
                        success = True
                    else:
                        print_error("Server returned error response")
                        print(f"  Error: {resp_data.get('error', 'Unknown error')}")
                        success = False
                except json.JSONDecodeError:
                    print_error("Server returned invalid JSON")
                    print(f"  Response: {response}")
                    success = False
            else:
                print_error("Server did not respond")
                success = False
        else:
            print_error("Server startup timeout (5 seconds)")
            success = False
        
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        
        # Check for stderr output
        stderr_output = process.stderr.read()
        if stderr_output:
            print_warning("Server stderr output:")
            for line in stderr_output.strip().split('\n'):
                print(f"  {line}")
        
        return success
        
    except Exception as e:
        print_error(f"Server startup test failed: {e}")
        return False


async def test_manager_initialization():
    """Test if managers can be initialized"""
    print_header("Manager Initialization Test")
    
    try:
        # Set up environment for testing
        os.environ['SHANNON_MCP_MODE'] = 'test'
        
        # Import config loader
        from src.shannon_mcp.utils.config import load_config
        
        print("Loading configuration...")
        config = await load_config()
        
        if config:
            print_success("Configuration loaded successfully")
            print(f"  Version: {config.version}")
            print(f"  Database path: {config.database.path}")
        else:
            print_error("Failed to load configuration")
            return False
        
        # Test individual manager imports
        managers = [
            ("binary", "src.shannon_mcp.managers.binary", "BinaryManager"),
            ("session", "src.shannon_mcp.managers.session", "SessionManager"),
            ("agent", "src.shannon_mcp.managers.agent", "AgentManager"),
        ]
        
        all_imported = True
        for name, module_path, class_name in managers:
            try:
                module = importlib.import_module(module_path)
                manager_class = getattr(module, class_name)
                print_success(f"{name} manager - {class_name} imported successfully")
            except Exception as e:
                print_error(f"{name} manager - Failed to import: {e}")
                all_imported = False
        
        return all_imported
        
    except Exception as e:
        print_error(f"Manager test failed: {e}")
        return False


def generate_report(results):
    """Generate a diagnostic report"""
    print_header("Diagnostic Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results.values() if r)
    
    print(f"\nTotal checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    
    if passed_checks == total_checks:
        print(f"\n{GREEN}All checks passed! The Shannon MCP server should work correctly.{RESET}")
    else:
        print(f"\n{RED}Some checks failed. Please address the issues above.{RESET}")
        
        # Provide recommendations
        print("\nRecommendations:")
        
        if not results.get("python_version"):
            print("  1. Upgrade to Python 3.11 or later")
        
        if not results.get("dependencies"):
            print("  2. Install missing dependencies: poetry install")
        
        if not results.get("project_structure"):
            print("  3. Ensure you're running from the project root directory")
        
        if not results.get("server_startup"):
            print("  4. Check server logs for detailed error messages")


def main():
    """Run all diagnostic checks"""
    print(f"{BLUE}Shannon MCP Server Diagnostic Tool{RESET}")
    print("=" * 40)
    
    results = {}
    
    # Run checks
    results["python_version"] = check_python_version()
    results["dependencies"] = check_dependencies()
    results["project_structure"] = check_project_structure()
    results["environment"] = check_environment()
    results["server_startup"] = test_server_startup()
    
    # Run async tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results["manager_init"] = loop.run_until_complete(test_manager_initialization())
    loop.close()
    
    # Generate report
    generate_report(results)
    
    # Save detailed report
    report_file = Path("diagnostic_report.json")
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": str(Path.ctime(Path.cwd())),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform,
            "results": results,
            "environment": dict(os.environ)
        }, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_file}")
    
    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()