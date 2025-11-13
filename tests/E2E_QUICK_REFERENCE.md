# E2E Integration Test - Quick Reference

## Test File
**Location:** `/home/user/shannon-mcp/tests/test_e2e_integration.py`

## Quick Stats
- **Total Lines:** 660
- **Test Functions:** 12
- **Test Classes:** 2
- **Fixtures:** 4

## Run Commands

### Run All E2E Tests
```bash
poetry run pytest tests/test_e2e_integration.py -v
```

### Run Single Test
```bash
poetry run pytest tests/test_e2e_integration.py::TestE2EIntegration::test_01_server_initialization -v
```

### Run with Coverage
```bash
poetry run pytest tests/test_e2e_integration.py --cov=shannon_mcp --cov-report=term-missing
```

### Run Performance Tests Only
```bash
poetry run pytest tests/test_e2e_integration.py::TestE2EIntegrationPerformance -v
```

## Test Coverage Map

| Test # | Name | Coverage Area | Duration |
|--------|------|---------------|----------|
| 01 | server_initialization | Server startup, manager init | < 0.5s |
| 02 | mcp_list_tools | Tool registration, MCP protocol | < 0.3s |
| 03 | mcp_list_resources | Resource registration | < 0.3s |
| 04 | binary_discovery | Binary manager, discovery | < 0.5s |
| 05 | session_lifecycle | Session CRUD, lifecycle | < 0.5s |
| 06 | agent_system | Agent registry, task assignment | < 0.5s |
| 07 | resource_access | Resource reading | < 0.3s |
| 08 | error_handling | Error cases, shutdown | < 0.3s |
| 09 | checkpoint_creation | Checkpoint system | < 0.3s |
| 10 | concurrent_operations | Concurrency handling | < 0.5s |
| 11 | idempotent_initialization | Multiple init calls | < 0.3s |
| 12 | initialization_speed | Performance benchmark | < 0.5s |

**Total Expected Runtime:** ~5 seconds

## What's Tested

### Core Components ✓
- [x] Server initialization
- [x] Manager lifecycle (start/stop)
- [x] Configuration loading
- [x] Database connections

### MCP Protocol ✓
- [x] list_tools handler (7 tools)
- [x] list_resources handler (3 resources)
- [x] call_tool handler
- [x] read_resource handler

### Binary Management ✓
- [x] Binary discovery
- [x] Version detection
- [x] Binary validation

### Session Management ✓
- [x] Session creation
- [x] Session state transitions
- [x] Message sending
- [x] Session cancellation
- [x] Session listing

### Agent System ✓
- [x] Agent registration (26 agents)
- [x] Agent listing with filters
- [x] Task assignment
- [x] Agent scoring
- [x] Metrics tracking

### Resources ✓
- [x] shannon://config
- [x] shannon://agents
- [x] shannon://sessions

### Advanced Features ✓
- [x] Checkpoint creation
- [x] Concurrent operations
- [x] Error handling
- [x] Graceful shutdown

## What's NOT Tested

### Real Integration
- [ ] Real Claude Code binary execution
- [ ] Real subprocess streaming
- [ ] Real JSONL parsing
- [ ] Network operations
- [ ] File system hooks

### Performance
- [ ] High load (100+ sessions)
- [ ] Memory usage patterns
- [ ] Long-running sessions
- [ ] Large message payloads

### Edge Cases
- [ ] Network failures
- [ ] Disk full scenarios
- [ ] Process crashes
- [ ] Resource exhaustion

*These are intentionally excluded for test speed and should be covered in separate integration/load tests*

## Mocking Strategy

### Always Mocked
```python
✓ load_config() - Avoid file I/O
✓ setup_notifications() - Avoid external services
✓ Manager.initialize() - Avoid database operations
✓ BinaryManager.discover_binary() - Avoid system scanning
✓ Subprocess execution - Avoid real processes
```

### Never Mocked
```python
✓ Server class instantiation
✓ Handler registration
✓ Basic Python logic
✓ Data structure operations
```

## Fixtures Reference

### temp_workspace
```python
# Provides: Path to temporary directory
# Cleanup: Automatic after test
# Use: For creating test files/directories
```

### mock_claude_binary
```python
# Provides: Path to mock executable
# Platform: Cross-platform (Unix/Windows)
# Use: For binary discovery tests
```

### test_config
```python
# Provides: ShannonConfig object
# Managers: All configured with test settings
# Use: For server initialization
```

### mock_binary_info
```python
# Provides: BinaryInfo object
# Version: "1.0.0"
# Use: For session/binary tests
```

## Common Assertions

### Server State
```python
assert server.initialized is True
assert server.config is not None
assert len(server.managers) == 4
```

### Tool Registration
```python
assert len(tools) == 7
assert "find_claude_binary" in tool_names
```

### Session State
```python
assert session.state == SessionState.RUNNING
assert session.id is not None
```

### Agent System
```python
assert len(agents) == 26
assert assignment.score > 0
```

## Debugging Tips

### Test Hangs
```bash
# Add timeout
poetry run pytest tests/test_e2e_integration.py --timeout=10
```

### Mock Not Working
```python
# Check patch path
with patch('shannon_mcp.server.BinaryManager'):  # Correct
with patch('BinaryManager'):  # Wrong
```

### Async Issues
```python
# Ensure @pytest.mark.asyncio
@pytest.mark.asyncio
async def test_something():
    await something()  # Must use await
```

### Import Errors
```bash
# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:./src"
poetry run pytest tests/test_e2e_integration.py
```

## Success Indicators

When tests pass, you have confidence in:
- ✅ Server can start and stop cleanly
- ✅ MCP protocol handlers work
- ✅ Managers integrate properly
- ✅ Binary discovery functions
- ✅ Session lifecycle is correct
- ✅ Agent system operates
- ✅ Resources are accessible
- ✅ Errors are handled
- ✅ System is performant

## Next Steps

After E2E tests pass:
1. Run unit tests: `poetry run pytest tests/`
2. Check coverage: `poetry run pytest --cov`
3. Run integration tests with real binary
4. Perform load testing
5. Test in production-like environment

## Documentation

- **Full Summary:** `/home/user/shannon-mcp/tests/E2E_TEST_SUMMARY.md`
- **Test Code:** `/home/user/shannon-mcp/tests/test_e2e_integration.py`
- **Project Tests:** `/home/user/shannon-mcp/tests/`
