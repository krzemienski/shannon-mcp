# MCP Integration Testing Framework

This directory contains comprehensive integration tests for Shannon MCP server within Claude's execution environment. These tests validate real host system interactions and ensure MCP operations genuinely affect the system.

## Architecture

### Directory Structure

- `setup/` - Installation and configuration scripts
- `agents/` - Autonomous test agents that drive testing
- `validators/` - Bidirectional validation components
- `gates/` - Production readiness gates
- `fixtures/` - Test data and expected results
- `results/` - Test execution results and reports

### Testing Philosophy

1. **Agentic Testing**: Each test is an autonomous agent using Claude SDK
2. **Real System Validation**: No mocks - all operations affect real filesystem
3. **Bidirectional Verification**: MCP→Host and Host→MCP changes validated
4. **Production Gates**: Strict criteria before deployment approval

## Key Test Scenarios

### 1. Hook System Persistence
- Validates hook modifications persist in user scope
- Tests global hook reflection across sessions
- Verifies hook execution affects real system

### 2. Project Discovery
- Tests real directory scanning and discovery
- Validates project metadata extraction
- Ensures discovered projects are accessible

### 3. Session Management
- Tests real Claude Code process creation
- Validates session lifecycle with actual processes
- Verifies resource cleanup after session termination

### 4. Streaming Command Execution
- Tests real command execution via MCP
- Validates JSONL streaming with actual output
- Ensures proper error handling and recovery

## Running Tests

### Prerequisites
```bash
# Install Shannon MCP server
cd /home/nick/shannon-mcp
poetry install

# Install test dependencies
poetry install --with test
```

### Full Test Suite
```bash
# Run all integration tests
python -m pytest tests/mcp-integration/ -v

# Run specific test category
python -m pytest tests/mcp-integration/agents/test_file_system_agent.py -v

# Run with production gates
python -m pytest tests/mcp-integration/ --production-gates
```

### Individual Test Agents
```bash
# File system validation
python tests/mcp-integration/agents/file_system_agent.py

# Hook persistence testing
python tests/mcp-integration/agents/hook_validation_agent.py

# Session management testing
python tests/mcp-integration/agents/session_testing_agent.py
```

## Test Results

Results are stored in `results/` with timestamps:
- `results/YYYY-MM-DD-HH-MM-SS/`
  - `summary.json` - Overall test results
  - `agent-reports/` - Individual agent reports
  - `validation-logs/` - Detailed validation logs
  - `gate-decisions/` - Production gate outcomes

## Production Gates

### Pre-Deployment Gate
- All tests must pass
- No critical issues identified
- Performance within acceptable limits
- Security validations pass

### Production Readiness Gate
- Extended stress testing passed
- Real-world scenario validation complete
- Documentation and procedures verified
- Rollback procedures tested

## Troubleshooting

### Common Issues

1. **MCP Server Not Found**
   - Ensure Shannon MCP is installed: `poetry install`
   - Check server is running: `shannon-mcp serve`

2. **Permission Errors**
   - Tests need write access to test directories
   - May need elevated permissions for hook modifications

3. **Process Cleanup**
   - Use `pkill -f shannon-mcp` if processes hang
   - Check `ps aux | grep claude` for orphaned processes

## Contributing

When adding new tests:
1. Create agent in `agents/` following `test_agent_base.py`
2. Add validators in `validators/` for bidirectional checks
3. Update gates in `gates/` if new criteria needed
4. Document test scenarios in agent docstrings