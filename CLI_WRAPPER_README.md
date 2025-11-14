# Shannon MCP CLI Wrapper

A comprehensive command-line interface wrapper for the Shannon MCP Server, providing easy access to all MCP tools and resources.

## Overview

The `mcp-cli` wrapper provides a user-friendly command-line interface to interact with the Shannon MCP Server. Instead of constructing JSON-RPC requests manually, you can use simple shell commands to access all MCP functionality.

## Features

- ✅ **Complete Coverage** - All 7 MCP tools supported
- ✅ **Resource Access** - All 3 MCP resources accessible
- ✅ **User-Friendly** - Simple command syntax with helpful error messages
- ✅ **JSON Parsing** - Automatic JSON response formatting with jq
- ✅ **Color Output** - Clear visual feedback with colored output
- ✅ **Comprehensive Help** - Built-in documentation and examples
- ✅ **Fully Tested** - Comprehensive validation test suite included

## Installation

### Prerequisites

1. **Shannon MCP Server** - Must be installed and configured
   ```bash
   cd shannon-mcp
   poetry install
   ```

2. **jq** - JSON processor
   ```bash
   # Ubuntu/Debian
   sudo apt-get install jq

   # macOS
   brew install jq
   ```

### Setup

1. Make the script executable:
   ```bash
   chmod +x mcp-cli
   ```

2. (Optional) Add to PATH:
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export PATH="$PATH:/path/to/shannon-mcp"
   ```

## Usage

### Basic Syntax

```bash
mcp-cli <command> [arguments]
```

### Available Commands

#### Binary Management

```bash
# Find Claude Code binary on the system
mcp-cli find-claude-binary
```

#### Session Management

```bash
# Create a new session
mcp-cli create-session "Fix the login bug"
mcp-cli create-session "Add new feature" "claude-3-opus"
mcp-cli create-session "Resume work" "claude-3-sonnet" "checkpoint-abc123"

# Send message to a session
mcp-cli send-message "session-123" "Please update the documentation"
mcp-cli send-message "session-456" "Run tests" 60  # with 60s timeout

# List all sessions
mcp-cli list-sessions
mcp-cli list-sessions "active"     # Filter by state
mcp-cli list-sessions "active" 50   # Limit to 50 results

# Cancel a session
mcp-cli cancel-session "session-123"
```

#### Agent Management

```bash
# List all agents
mcp-cli list-agents

# List agents by category
mcp-cli list-agents "core"

# List agents by status
mcp-cli list-agents "" "available"

# List agents by capability
mcp-cli list-agents "" "" "python"

# Assign a task to an agent
mcp-cli assign-task "Implement user authentication" '["python","security"]'
mcp-cli assign-task "Write tests" '["python","testing"]' "high"
mcp-cli assign-task "Optimize database" '["database","performance"]' "medium" 300
```

#### Resources

```bash
# Get current configuration
mcp-cli get-config

# Get agents resource
mcp-cli get-agents-resource

# Get sessions resource
mcp-cli get-sessions-resource
```

#### Utility Commands

```bash
# List all available tools
mcp-cli list-tools

# Show help
mcp-cli help
```

## Examples

### Example 1: Create and Monitor a Session

```bash
# Create a session
SESSION_OUTPUT=$(mcp-cli create-session "Implement login feature")
SESSION_ID=$(echo "$SESSION_OUTPUT" | jq -r '.session_id')

echo "Created session: $SESSION_ID"

# List active sessions
mcp-cli list-sessions "active"

# Send a message
mcp-cli send-message "$SESSION_ID" "Please add input validation"

# Cancel when done
mcp-cli cancel-session "$SESSION_ID"
```

### Example 2: Find and Assign Task to Agent

```bash
# List available Python experts
mcp-cli list-agents "" "" "python"

# Assign a Python task
TASK_OUTPUT=$(mcp-cli assign-task "Refactor authentication module" '["python","refactoring"]' "high")
TASK_ID=$(echo "$TASK_OUTPUT" | jq -r '.task_id')

echo "Task $TASK_ID assigned successfully"
```

### Example 3: System Status Check

```bash
# Check binary
mcp-cli find-claude-binary

# Check configuration
mcp-cli get-config

# Check available agents
mcp-cli list-agents

# Check active sessions
mcp-cli list-sessions "active"
```

## Configuration

### Environment Variables

#### MCP_SERVER

Customize the command used to run the MCP server:

```bash
# Default (uses Poetry)
export MCP_SERVER="poetry run shannon-mcp"

# System installation
export MCP_SERVER="/usr/local/bin/shannon-mcp"

# Development mode
export MCP_SERVER="python -m shannon_mcp.server"

# Custom Python environment
export MCP_SERVER="/path/to/venv/bin/shannon-mcp"
```

Add to your shell configuration:

```bash
# ~/.bashrc or ~/.zshrc
export MCP_SERVER="poetry run shannon-mcp"
```

## Response Format

All commands return JSON responses from the MCP server:

### Success Response

```json
{
  "session_id": "sess-abc123",
  "state": "active",
  "model": "claude-3-sonnet",
  "created_at": "2025-11-14T10:30:00Z"
}
```

### Error Response

```json
{
  "error": "Session not found: sess-xyz789"
}
```

## Testing

A comprehensive test suite is included in the `cli-tests/` directory:

```bash
# Run all tests
cd cli-tests
./run-all-tests.sh

# Run specific test
./test-session-lifecycle.sh
```

See [cli-tests/README.md](cli-tests/README.md) for detailed testing documentation.

## Troubleshooting

### "command not found: mcp-cli"

Make sure the script is executable and in your PATH:

```bash
chmod +x mcp-cli
export PATH="$PATH:$(pwd)"
```

### "jq: command not found"

Install jq:

```bash
# Ubuntu/Debian
sudo apt-get install jq

# macOS
brew install jq
```

### "MCP server connection failed"

1. Verify Shannon MCP server is installed:
   ```bash
   poetry run shannon-mcp --help
   ```

2. Check if the server can start:
   ```bash
   poetry run shannon-mcp
   ```

3. Verify the MCP_SERVER environment variable:
   ```bash
   echo $MCP_SERVER
   ```

### "Error parsing JSON response"

The MCP server may have returned an error. Check the raw output:

```bash
mcp-cli your-command 2>&1
```

## Integration

### Shell Scripts

```bash
#!/bin/bash

# Create session and capture ID
SESSION_ID=$(mcp-cli create-session "Automated task" | jq -r '.session_id')

if [[ -n "$SESSION_ID" ]]; then
    echo "Session created: $SESSION_ID"
    mcp-cli send-message "$SESSION_ID" "Execute automated workflow"
fi
```

### Python Scripts

```python
import subprocess
import json

# Call mcp-cli from Python
result = subprocess.run(
    ["./mcp-cli", "list-agents"],
    capture_output=True,
    text=True
)

agents = json.loads(result.stdout)
print(f"Found {len(agents)} agents")
```

### CI/CD Pipelines

```yaml
# GitHub Actions
- name: Check MCP Status
  run: |
    ./mcp-cli find-claude-binary
    ./mcp-cli list-agents

- name: Run Automated Task
  run: |
    SESSION_ID=$(./mcp-cli create-session "CI/CD task" | jq -r '.session_id')
    ./mcp-cli send-message "$SESSION_ID" "Run tests and build"
```

## Architecture

The CLI wrapper communicates with the Shannon MCP Server using the JSON-RPC 2.0 protocol over stdio:

```
┌─────────────┐      JSON-RPC       ┌──────────────────┐
│   mcp-cli   │ ──────────────────> │  Shannon MCP     │
│   (bash)    │ <────────────────── │  Server (Python) │
└─────────────┘      stdio          └──────────────────┘
                                             │
                                             │
                                             v
                                     ┌───────────────┐
                                     │  Claude Code  │
                                     │   Binary      │
                                     └───────────────┘
```

## Tool Reference

### find-claude-binary

Discover Claude Code installation on the system.

**Arguments:** None

**Returns:** Binary information (path, version, etc.)

### create-session

Create a new Claude Code session.

**Arguments:**
- `prompt` (required) - Initial prompt for the session
- `model` (optional) - Model to use (default: claude-3-sonnet)
- `checkpoint_id` (optional) - Checkpoint to restore from

**Returns:** Session object with ID and metadata

### send-message

Send a message to an active session.

**Arguments:**
- `session_id` (required) - Session identifier
- `content` (required) - Message content
- `timeout` (optional) - Timeout in seconds

**Returns:** Success confirmation

### cancel-session

Cancel a running session.

**Arguments:**
- `session_id` (required) - Session to cancel

**Returns:** Success confirmation

### list-sessions

List active sessions.

**Arguments:**
- `state` (optional) - Filter by state (active, completed, etc.)
- `limit` (optional) - Maximum results (default: 100)

**Returns:** Array of session objects

### list-agents

List available AI agents.

**Arguments:**
- `category` (optional) - Filter by category
- `status` (optional) - Filter by status
- `capability` (optional) - Filter by capability

**Returns:** Array of agent objects

### assign-task

Assign a task to an AI agent.

**Arguments:**
- `description` (required) - Task description
- `required_capabilities` (required) - JSON array of required capabilities
- `priority` (optional) - Task priority (default: medium)
- `timeout` (optional) - Timeout in seconds

**Returns:** Task assignment object with task ID and agent ID

## Development

### Adding New Commands

To add support for a new MCP tool:

1. Add a `cmd_your_command()` function following the existing pattern
2. Add the command to the case statement in `main()`
3. Update the help text in `cmd_help()`
4. Create a test in `cli-tests/test-your-command.sh`
5. Add the test to `cli-tests/run-all-tests.sh`

### Code Style

- Use bash strict mode: `set -euo pipefail`
- Quote all variables: `"${var}"`
- Use color codes for output clarity
- Include descriptive comments
- Follow the established naming convention

## Contributing

Contributions are welcome! Please:

1. Follow the existing code style
2. Add tests for new functionality
3. Update documentation
4. Test thoroughly before submitting

## License

Part of the Shannon MCP Server project.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the test suite for examples
- Consult the Shannon MCP Server documentation
- Open an issue on the project repository
