#!/usr/bin/env python3
"""Simple test runner for Shannon MCP - checks basic functionality"""

import sys
import os
import importlib.util
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that core modules can be imported"""
    results = []
    
    modules_to_test = [
        "shannon_mcp",
        "shannon_mcp.utils.config",
        "shannon_mcp.utils.logging",
        "shannon_mcp.utils.errors",
        "shannon_mcp.managers.base",
        "shannon_mcp.managers.binary",
        "shannon_mcp.managers.session",
        "shannon_mcp.managers.agent",
        "shannon_mcp.storage.cas",
        "shannon_mcp.streaming.processor",
        "shannon_mcp.hooks.engine",
        "shannon_mcp.analytics.aggregator",
    ]
    
    for module_name in modules_to_test:
        try:
            module = importlib.import_module(module_name)
            results.append((module_name, "✅ SUCCESS", None))
        except Exception as e:
            results.append((module_name, "❌ FAILED", str(e)))
    
    return results

def test_core_classes():
    """Test that core classes can be instantiated"""
    results = []
    
    # Test BaseManager
    try:
        from shannon_mcp.managers.base import BaseManager, ManagerConfig
        config = ManagerConfig(name="test")
        results.append(("BaseManager Config", "✅ SUCCESS", None))
    except Exception as e:
        results.append(("BaseManager Config", "❌ FAILED", str(e)))
    
    # Test BinaryInfo
    try:
        from shannon_mcp.managers.binary import BinaryInfo
        from pathlib import Path
        info = BinaryInfo(path=Path("/usr/bin/claude"), version="1.0.0")
        results.append(("BinaryInfo", "✅ SUCCESS", None))
    except Exception as e:
        results.append(("BinaryInfo", "❌ FAILED", str(e)))
    
    # Test SessionState
    try:
        from shannon_mcp.managers.session import SessionState
        state = SessionState.CREATED
        results.append(("SessionState", "✅ SUCCESS", None))
    except Exception as e:
        results.append(("SessionState", "❌ FAILED", str(e)))
    
    return results

def test_utils():
    """Test utility functions"""
    results = []
    
    # Test error classes
    try:
        from shannon_mcp.utils.errors import ShannonMCPError, ValidationError
        results.append(("Error Classes", "✅ SUCCESS", None))
    except Exception as e:
        results.append(("Error Classes", "❌ FAILED", str(e)))
    
    # Test logging
    try:
        from shannon_mcp.utils.logging import get_logger
        logger = get_logger("test")
        results.append(("Logging", "✅ SUCCESS", None))
    except Exception as e:
        results.append(("Logging", "❌ FAILED", str(e)))
    
    return results

def main():
    print("🧪 Shannon MCP Basic Test Suite")
    print("=" * 60)
    
    all_results = []
    
    # Run import tests
    print("\n📦 Module Import Tests:")
    import_results = test_imports()
    all_results.extend(import_results)
    for module, status, error in import_results:
        print(f"  {module}: {status}")
        if error:
            print(f"    Error: {error[:100]}...")
    
    # Run class tests
    print("\n🏗️ Core Class Tests:")
    class_results = test_core_classes()
    all_results.extend(class_results)
    for name, status, error in class_results:
        print(f"  {name}: {status}")
        if error:
            print(f"    Error: {error[:100]}...")
    
    # Run utility tests
    print("\n🔧 Utility Function Tests:")
    util_results = test_utils()
    all_results.extend(util_results)
    for name, status, error in util_results:
        print(f"  {name}: {status}")
        if error:
            print(f"    Error: {error[:100]}...")
    
    # Summary
    total = len(all_results)
    passed = len([r for r in all_results if "SUCCESS" in r[1]])
    failed = total - passed
    
    print("\n" + "=" * 60)
    print(f"📊 Test Summary:")
    print(f"  Total Tests: {total}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Success Rate: {(passed/total*100):.1f}%")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())