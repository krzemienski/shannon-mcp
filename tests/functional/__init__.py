"""
Functional tests for Shannon MCP Server.

These tests exercise real functionality with actual Claude Code execution,
file I/O, process management, and component integration.

Test Categories:
- Binary Discovery: Real Claude Code binary discovery and execution
- Session Management: Full session lifecycle with Claude Code
- Streaming: JSONL streaming with real Claude responses  
- Checkpoints: Session state saving and restoration
- Agent System: Multi-agent task execution
- Analytics: Metrics collection and reporting
- Process Registry: System process tracking
- Hooks & Commands: Event handling and command execution
- Full Integration: Complete system workflow tests

Requirements:
- Claude Code binary must be installed and in PATH
- Sufficient disk space for test data
- Network access for some integration tests

Usage:
    pytest tests/functional/  # Run all functional tests
    pytest tests/functional/test_binary_discovery.py  # Run specific test
    python tests/functional/run_functional_tests.py --quick  # Quick smoke test
"""