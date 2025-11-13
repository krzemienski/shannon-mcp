"""
Standalone test suite for Shannon MCP Server API compatibility.

Tests that the server uses the correct MCP 1.x API with decorators
instead of the old add_tool/add_resource methods.
"""

import sys
import inspect
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.server import ShannonMCPServer


def test_server_creates_without_attribute_error():
    """Test that server can be created without AttributeError."""
    try:
        server = ShannonMCPServer()
        print("✓ Server created successfully without AttributeError")
        return True
    except AttributeError as e:
        print(f"✗ AttributeError occurred: {e}")
        return False


def test_no_add_tool_method_used():
    """Verify that the old add_tool method is not used."""
    source = inspect.getsource(ShannonMCPServer)

    if 'self.server.add_tool(' in source:
        print("✗ Old API found: add_tool() method is still being used")
        return False
    else:
        print("✓ Old API removed: No add_tool() calls found")
        return True


def test_no_add_resource_method_used():
    """Verify that the old add_resource method is not used."""
    source = inspect.getsource(ShannonMCPServer)

    if 'self.server.add_resource(' in source:
        print("✗ Old API found: add_resource() method is still being used")
        return False
    else:
        print("✓ Old API removed: No add_resource() calls found")
        return True


def test_list_tools_decorator_used():
    """Verify that @server.list_tools() decorator is used."""
    source = inspect.getsource(ShannonMCPServer)

    if '@self.server.list_tools()' in source:
        print("✓ New API used: @server.list_tools() decorator found")
        return True
    else:
        print("✗ New API missing: @server.list_tools() decorator not found")
        return False


def test_call_tool_decorator_used():
    """Verify that @server.call_tool() decorator is used."""
    source = inspect.getsource(ShannonMCPServer)

    if '@self.server.call_tool()' in source:
        print("✓ New API used: @server.call_tool() decorator found")
        return True
    else:
        print("✗ New API missing: @server.call_tool() decorator not found")
        return False


def test_list_resources_decorator_used():
    """Verify that @server.list_resources() decorator is used."""
    source = inspect.getsource(ShannonMCPServer)

    if '@self.server.list_resources()' in source:
        print("✓ New API used: @server.list_resources() decorator found")
        return True
    else:
        print("✗ New API missing: @server.list_resources() decorator not found")
        return False


def test_read_resource_decorator_used():
    """Verify that @server.read_resource() decorator is used."""
    source = inspect.getsource(ShannonMCPServer)

    if '@self.server.read_resource()' in source:
        print("✓ New API used: @server.read_resource() decorator found")
        return True
    else:
        print("✗ New API missing: @server.read_resource() decorator not found")
        return False


def test_server_has_mcp_server_instance():
    """Test that server has an MCP Server instance."""
    server = ShannonMCPServer()

    if hasattr(server, 'server'):
        print("✓ Server has MCP Server instance")
        return True
    else:
        print("✗ Server missing MCP Server instance")
        return False


def test_server_initialization_state():
    """Test server initialization state."""
    server = ShannonMCPServer()

    if not server.initialized and server.config is None and len(server.managers) == 0:
        print("✓ Server initialization state is correct")
        return True
    else:
        print("✗ Server initialization state is incorrect")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("="*60)
    print("Shannon MCP Server API Compatibility Tests")
    print("="*60)
    print()

    tests = [
        ("Server Creation", test_server_creates_without_attribute_error),
        ("No add_tool() Method", test_no_add_tool_method_used),
        ("No add_resource() Method", test_no_add_resource_method_used),
        ("@list_tools() Decorator", test_list_tools_decorator_used),
        ("@call_tool() Decorator", test_call_tool_decorator_used),
        ("@list_resources() Decorator", test_list_resources_decorator_used),
        ("@read_resource() Decorator", test_read_resource_decorator_used),
        ("MCP Server Instance", test_server_has_mcp_server_instance),
        ("Initialization State", test_server_initialization_state),
    ]

    results = []
    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append((name, False))

    print()
    print("="*60)
    print("Test Results Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {name}: {status}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! MCP API compatibility is correct.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please fix the issues.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
