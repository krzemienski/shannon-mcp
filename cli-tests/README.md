# Shannon MCP CLI - Test Suite

Comprehensive validation tests for the Shannon MCP CLI wrapper.

## Overview

This test suite validates all functionality of the `mcp-cli` wrapper script, ensuring that every MCP tool and resource can be accessed correctly via the command line interface.

## Test Files

### Core Tests

1. **test-help.sh** - Validates the help command and documentation
2. **test-list-tools.sh** - Validates the list-tools utility command
3. **test-find-claude-binary.sh** - Tests binary discovery functionality

### Session Tests

4. **test-session-lifecycle.sh** - Complete session lifecycle testing:
   - Creating sessions
   - Listing sessions
   - Sending messages to sessions
   - Canceling sessions

### Agent Tests

5. **test-agents.sh** - Agent system validation:
   - Listing all agents
   - Filtering agents by category
   - Filtering agents by capability
   - Assigning tasks to agents

### Resource Tests

6. **test-resources.sh** - MCP resource access:
   - Getting configuration resource
   - Getting agents resource
   - Getting sessions resource

## Running Tests

### Run All Tests

```bash
./run-all-tests.sh
```

This will execute all validation tests in sequence and provide a comprehensive summary.

### Run Individual Tests

```bash
# Test help command
./test-help.sh

# Test session lifecycle
./test-session-lifecycle.sh

# Test agent commands
./test-agents.sh

# Test resources
./test-resources.sh
```

## Prerequisites

### Required Dependencies

1. **jq** - JSON processing
   ```bash
   # Ubuntu/Debian
   sudo apt-get install jq

   # macOS
   brew install jq
   ```

2. **Poetry** - Python dependency management (for running the MCP server)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Shannon MCP Server** - Must be installed and configured
   ```bash
   cd /path/to/shannon-mcp
   poetry install
   ```

## Environment Variables

### MCP_SERVER

Customize the command used to run the MCP server:

```bash
# Default
export MCP_SERVER="poetry run shannon-mcp"

# Custom path
export MCP_SERVER="/usr/local/bin/shannon-mcp"

# Development mode
export MCP_SERVER="python -m shannon_mcp.server"
```

## Test Output

### Success Example

```
========================================
Shannon MCP CLI - Validation Test Suite
========================================

Running: test-help.sh
----------------------------------------
Testing help command...
✓ help command test passed - all expected sections found

Running: test-list-tools.sh
----------------------------------------
Testing list-tools command...
✓ list-tools test passed - all expected tools found

...

========================================
Test Summary
========================================

  ✓ test-help.sh: PASSED
  ✓ test-list-tools.sh: PASSED
  ✓ test-find-claude-binary.sh: PASSED
  ✓ test-agents.sh: PASSED
  ✓ test-resources.sh: PASSED
  ✓ test-session-lifecycle.sh: PASSED

----------------------------------------
Passed:  6
Warnings: 0
Failed:  0
Total:   6
----------------------------------------
All tests passed!
```

### Failure Example

```
✗ create-session failed - unexpected output format
Output: Error: connection refused

----------------------------------------
Passed:  3
Warnings: 1
Failed:  2
Total:   6
----------------------------------------
Some tests failed!
```

## Troubleshooting

### "MCP server not running"

Ensure the Shannon MCP server is properly installed:

```bash
cd shannon-mcp
poetry install
poetry run shannon-mcp --help
```

### "jq: command not found"

Install jq using your package manager (see Prerequisites above).

### "Permission denied"

Make sure all scripts are executable:

```bash
chmod +x *.sh
chmod +x ../mcp-cli
```

### Tests timeout or hang

Some tests interact with the actual MCP server and may take time. If tests hang:

1. Check if the MCP server is responsive
2. Verify network connectivity
3. Check for any background Claude Code sessions

## Test Coverage

The test suite covers:

- ✅ All 7 MCP tools
- ✅ All 3 MCP resources
- ✅ Help and utility commands
- ✅ Error handling
- ✅ Parameter validation
- ✅ JSON response parsing
- ✅ Session lifecycle management
- ✅ Agent assignment workflows

## Adding New Tests

To add a new test:

1. Create a new test script in `cli-tests/`:
   ```bash
   touch test-new-feature.sh
   chmod +x test-new-feature.sh
   ```

2. Follow the test template:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   CLI="${SCRIPT_DIR}/../mcp-cli"

   echo "Testing new feature..."

   OUTPUT=$("${CLI}" your-command 2>&1 || true)

   if echo "${OUTPUT}" | grep -q "expected-pattern"; then
       echo "✓ Test passed"
       exit 0
   else
       echo "✗ Test failed"
       exit 1
   fi
   ```

3. Add the test to `run-all-tests.sh`:
   ```bash
   TESTS=(
       ...
       "test-new-feature.sh"
   )
   ```

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run MCP CLI Tests
  run: |
    cd cli-tests
    ./run-all-tests.sh
```

## License

Part of the Shannon MCP Server project.
