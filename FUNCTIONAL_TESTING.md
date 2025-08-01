# Shannon MCP Functional Testing Guide

## Overview

The Shannon MCP Functional Test Client is a comprehensive end-to-end testing tool that acts as a real MCP (Model Context Protocol) client to test the Shannon MCP server. Unlike traditional unit tests, this client spawns the actual server as a subprocess and communicates with it using the MCP protocol over stdio, ensuring real-world behavior validation.

## Architecture

```
┌─────────────────────────┐         MCP Protocol          ┌──────────────────────┐
│  Functional Test Client │ ◄────────────────────────────► │  Shannon MCP Server  │
│  (functional_test_      │         (stdio/JSONRPC)        │  (server_fastmcp.py) │
│   client.py)            │                                │                      │
└─────────────────────────┘                                └──────────────────────┘
        │                                                           │
        │                                                           │
        ▼                                                           ▼
┌─────────────────────────┐                                ┌──────────────────────┐
│   Test Results JSON     │                                │    Server Managers   │
│ (functional_test_       │                                │  - Binary Manager    │
│  results.json)          │                                │  - Session Manager   │
└─────────────────────────┘                                │  - Agent Manager     │
                                                           │  - etc...            │
                                                           └──────────────────────┘
```

## Features

### Comprehensive Test Coverage

The functional test client tests all major server functionality:

1. **Server Initialization** - Verifies the server starts correctly
2. **Binary Discovery** - Tests Claude Code binary detection
3. **Agent Management** - Creates and lists AI agents
4. **Project Management** - Creates projects to organize sessions
5. **Session Management** - Creates sessions within projects and sends messages
6. **Project Sessions** - Tests session organization within projects
7. **Checkpoint System** - Creates and manages checkpoints for sessions and projects
8. **Analytics** - Queries usage analytics
9. **Resource Access** - Tests MCP resource endpoints including projects
10. **Settings Management** - Tests runtime configuration
11. **MCP Server Management** - Tests adding MCP servers
12. **Project Lifecycle** - Tests archiving and managing project states
13. **Error Handling** - Validates error responses

### Debug Logging

The test client includes comprehensive debug logging:
- Detailed MCP message tracing (requests and responses)
- Server subprocess output capture
- Timing information for each operation
- Error details with stack traces

### Real Protocol Testing

Unlike mocked tests, this client:
- Spawns the actual server process
- Communicates via real MCP protocol messages
- Tests actual stdio transport layer
- Validates actual server responses
- Handles async streaming responses

## Usage

### Quick Start

```bash
# Run all functional tests
./run_functional_tests.sh

# Or run directly with Python
python3 functional_test_client.py
```

### Output

The test client provides multiple forms of output:

1. **Console Output** - Real-time test progress with color-coded results
2. **Log Files** - Detailed logs saved to `logs/` directory
3. **JSON Results** - Structured results in `functional_test_results.json`

### Example Output

```
========================================
SHANNON MCP FUNCTIONAL TEST SUITE
========================================

--- Test 1: Server Status ---
✅ PASSED: Server Status Check

--- Test 2: Binary Discovery ---
✅ PASSED: Binary Discovery

--- Test 3: List Agents ---
✅ PASSED: List Agents

[... more tests ...]

========================================
TEST SUMMARY
========================================
Total Tests: 15
Passed: 14 ✅
Failed: 1 ❌
Success Rate: 93.3%
```

## Test Details

### Server Lifecycle

1. **Startup**: The client spawns the server as a subprocess
2. **Initialize**: Sends MCP initialize request and waits for response
3. **Testing**: Executes all test cases sequentially
4. **Shutdown**: Gracefully terminates the server process

### Message Flow

Each test follows this pattern:

```python
# 1. Send MCP request
response = await client.call_tool("tool_name", {
    "param1": "value1",
    "param2": "value2"
})

# 2. Validate response
if response and "result" in response:
    # Test passed
else:
    # Test failed
```

### Error Handling

The client handles various error scenarios:
- Server startup failures
- Timeout errors (30 second default)
- Malformed responses
- Server crashes
- Protocol errors

## Debugging

### Enable Maximum Logging

Set environment variables for more detailed output:

```bash
export SHANNON_DEBUG=true
export PYTHONUNBUFFERED=1
./run_functional_tests.sh
```

### Analyzing Failed Tests

1. Check the console output for immediate feedback
2. Review the log file in `logs/` for detailed traces
3. Examine `functional_test_results.json` for structured data
4. Look for server stderr output in the logs

### Common Issues

**Server Won't Start**
- Check Python version (requires 3.11+)
- Verify all dependencies are installed
- Check for port conflicts (if using non-stdio transport)

**Tests Timeout**
- Increase timeout in test client (default 30s)
- Check if server is hanging during initialization
- Review server logs for errors

**Protocol Errors**
- Verify MCP message format
- Check for encoding issues
- Ensure proper JSONRPC formatting

## Extending Tests

### Adding New Test Cases

1. Add test in `run_functional_tests()`:

```python
# Test N: Your New Test
logger.info("\n--- Test N: Your New Test ---")
success, result = await client.call_tool("your_tool", {
    "param": "value"
})
record_test("Your New Test", success and validation_logic, result)
```

2. Update test numbering and summary

### Custom Assertions

Create custom validation functions:

```python
def validate_complex_response(result):
    """Custom validation logic"""
    return (
        result.get("status") == "success" and
        len(result.get("data", [])) > 0 and
        all(item.get("valid") for item in result["data"])
    )
```

## Performance Considerations

- Tests run sequentially to avoid race conditions
- Server initialization can take 2-5 seconds
- Each test has a 30 second timeout
- Total test suite typically completes in 1-2 minutes

## Integration with CI/CD

The functional test client is designed for CI/CD integration:

```yaml
# Example GitHub Actions
- name: Run Functional Tests
  run: |
    ./run_functional_tests.sh
  env:
    SHANNON_DEBUG: true
```

Exit codes:
- 0: All tests passed
- 1: One or more tests failed

## Troubleshooting

### Server Logs

Enable server debug logging by modifying the server startup:

```python
# In server_fastmcp.py
setup_logging("shannon-mcp.server", level=logging.DEBUG)
```

### Client Logs

Increase client verbosity:

```python
# In functional_test_client.py
logging.basicConfig(level=logging.DEBUG)
```

### MCP Protocol Debugging

Add protocol tracing:

```python
# Log raw messages
logger.debug(f"Raw send: {message_bytes}")
logger.debug(f"Raw recv: {line}")
```

## Summary

The Shannon MCP Functional Test Client provides comprehensive, real-world testing of the MCP server by acting as an actual MCP client. This approach ensures that the server behaves correctly in production scenarios and validates the complete stack from protocol handling to business logic execution.