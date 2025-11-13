# Shannon MCP Server - Testing Guide

Comprehensive testing documentation for the Shannon MCP Server project.

## Table of Contents

- [1. Testing Overview](#1-testing-overview)
- [2. Running Tests](#2-running-tests)
- [3. Test Categories](#3-test-categories)
- [4. Test Fixtures](#4-test-fixtures)
- [5. Writing New Tests](#5-writing-new-tests)
- [6. Coverage Analysis](#6-coverage-analysis)
- [7. Continuous Integration](#7-continuous-integration)
- [8. Performance Testing](#8-performance-testing)
- [9. Testing Individual Components](#9-testing-individual-components)
- [10. Troubleshooting Tests](#10-troubleshooting-tests)
- [11. Test Data and Fixtures](#11-test-data-and-fixtures)
- [12. Manual Testing](#12-manual-testing)

---

## 1. Testing Overview

### Test Suite Structure

The Shannon MCP test suite comprises **66 Python test files** with **~17,850 lines of test code**, organized into a comprehensive testing framework:

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── __init__.py
├── functional/                 # Complete component tests (20 files)
│   ├── test_complete_binary_manager.py
│   ├── test_complete_session_manager.py
│   ├── test_complete_checkpoint.py
│   ├── test_complete_analytics.py
│   ├── test_complete_agent.py
│   ├── test_complete_hooks.py
│   ├── test_complete_commands.py
│   ├── test_complete_streaming.py
│   └── test_full_integration.py
├── benchmarks/                 # Performance tests (13 files)
│   ├── benchmark_binary.py
│   ├── benchmark_session.py
│   ├── benchmark_checkpoint.py
│   ├── benchmark_analytics.py
│   ├── benchmark_streaming.py
│   └── visualize_benchmarks.py
├── mcp-integration/           # MCP protocol tests
│   ├── agents/               # Test agents
│   ├── gates/                # Quality gates
│   ├── validators/           # Protocol validators
│   └── run_integration_tests.py
├── utils/                    # Test utilities
│   ├── mock_helpers.py
│   ├── async_helpers.py
│   ├── performance.py
│   └── test_database.py
├── fixtures/                 # Test data generators
├── test_binary_manager.py    # Unit tests
├── test_session_manager.py
├── test_streaming.py
├── test_error_scenarios.py
└── test_server.py
```

### Test Categories

1. **Unit Tests** - Fast, isolated tests for individual functions and classes
2. **Functional Tests** - Complete component testing with all features
3. **Integration Tests** - End-to-end workflows with real MCP protocol
4. **Benchmark Tests** - Performance and regression testing

### Coverage Goals

- **Target Coverage**: 80%+ overall
- **Critical Components**: 90%+ (Binary Manager, Session Manager, MCP Protocol)
- **Current Status**: Run `poetry run pytest --cov` to see current coverage

### Testing Philosophy

1. **Test Behavior, Not Implementation** - Focus on public APIs and outcomes
2. **Fast Feedback** - Unit tests complete in milliseconds, full suite in minutes
3. **No Flakiness** - All tests are deterministic and reliable
4. **Real Services** - No mocking of external services; use real databases and files
5. **AAA Pattern** - Arrange, Act, Assert structure for clarity
6. **Async First** - Proper async/await patterns throughout

---

## 2. Running Tests

### Quick Start

```bash
# Install dependencies first
poetry install

# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_binary_manager.py

# Run specific test function
poetry run pytest tests/test_binary_manager.py::test_discover_system_binaries

# Run specific test class
poetry run pytest tests/test_binary_manager.py::TestBinaryManager
```

### Running Test Categories

```bash
# Run functional tests
poetry run pytest tests/functional/

# Run integration tests (marked with @pytest.mark.integration)
poetry run pytest -m integration

# Run benchmarks (marked with @pytest.mark.benchmark)
poetry run pytest -m benchmark

# Exclude slow tests
poetry run pytest -m "not slow"

# Run only fast unit tests
poetry run pytest tests/ -m "not slow and not integration and not benchmark"
```

### Coverage Reports

```bash
# Run tests with coverage (terminal report)
poetry run pytest --cov=shannon_mcp --cov-report=term-missing

# Generate HTML coverage report
poetry run pytest --cov=shannon_mcp --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML coverage report (for CI)
poetry run pytest --cov=shannon_mcp --cov-report=xml

# All reports at once (configured in pyproject.toml)
poetry run pytest --cov=shannon_mcp
```

### Test Options

```bash
# Stop on first failure
poetry run pytest -x

# Stop after N failures
poetry run pytest --maxfail=3

# Show slowest N tests
poetry run pytest --durations=10

# Parallel execution (requires pytest-xdist)
poetry run pytest -n auto

# Show local variables in tracebacks
poetry run pytest -l

# Show print statements
poetry run pytest -s

# Quiet mode (less output)
poetry run pytest -q

# Show test summary info
poetry run pytest -ra

# Run tests matching expression
poetry run pytest -k "binary or session"

# Run tests in specific order
poetry run pytest --ff  # failed first
poetry run pytest --lf  # last failed only
```

### Using the Functional Test Runner

```bash
# Run all functional tests
python tests/functional/run_functional_tests.py

# Run specific test file
python tests/functional/run_functional_tests.py --test-file test_binary_discovery.py

# Run tests matching name
python tests/functional/run_functional_tests.py -k test_streaming

# Run with coverage
python tests/functional/run_functional_tests.py --coverage

# Run in parallel (4 processes)
python tests/functional/run_functional_tests.py -n 4

# Quick smoke tests
python tests/functional/run_functional_tests.py --quick

# Generate JUnit XML report
python tests/functional/run_functional_tests.py --junit results.xml

# Show 5 slowest tests
python tests/functional/run_functional_tests.py --durations 5
```

---

## 3. Test Categories

### Unit Tests

**Location**: `tests/test_*.py` (root level)

**Purpose**: Fast, isolated tests for individual functions and classes.

**Examples**:
- `tests/test_binary_manager.py` - Binary discovery and management
- `tests/test_session_manager.py` - Session lifecycle
- `tests/test_streaming.py` - JSONL streaming
- `tests/test_error_scenarios.py` - Error handling

**Running Unit Tests**:
```bash
# All unit tests
poetry run pytest tests/test_*.py

# Specific unit test file
poetry run pytest tests/test_binary_manager.py -v
```

**Characteristics**:
- Execute in milliseconds
- No external dependencies
- Use fixtures for test data
- Mock external services when necessary

### Functional Tests

**Location**: `tests/functional/`

**Purpose**: Complete component testing covering all functionality.

**20 Functional Test Files**:
1. `test_agent_system.py` - Complete agent system testing
2. `test_analytics_monitoring.py` - Analytics and monitoring
3. `test_binary_discovery.py` - Binary discovery mechanisms
4. `test_checkpoint_system.py` - Checkpoint operations
5. `test_complete_agent.py` - Exhaustive agent tests
6. `test_complete_analytics.py` - Exhaustive analytics tests
7. `test_complete_binary_manager.py` - Exhaustive binary manager tests
8. `test_complete_checkpoint.py` - Exhaustive checkpoint tests
9. `test_complete_commands.py` - Exhaustive command tests
10. `test_complete_hooks.py` - Exhaustive hook tests
11. `test_complete_session_manager.py` - Exhaustive session tests
12. `test_complete_streaming.py` - Exhaustive streaming tests
13. `test_full_integration.py` - Full system integration
14. `test_hooks_commands.py` - Hooks and commands integration
15. `test_process_registry.py` - Process registry operations
16. `test_session_management.py` - Session management workflows
17. `test_streaming_integration.py` - Streaming integration
18. `run_functional_tests.py` - Test runner

**Running Functional Tests**:
```bash
# All functional tests
poetry run pytest tests/functional/ -v

# Specific component
poetry run pytest tests/functional/test_complete_binary_manager.py

# With coverage
poetry run pytest tests/functional/ --cov=shannon_mcp.managers.binary
```

**Example Test Structure**:
```python
class TestCompleteBinaryManager:
    """Exhaustive tests for every Binary Manager function."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test BinaryManager initialization with all options."""
        # Test default initialization
        manager1 = BinaryManager()
        assert manager1.cache_dir is not None

        # Test custom initialization
        custom_cache = Path("/tmp/custom_binary_cache")
        manager2 = BinaryManager(
            cache_dir=custom_cache,
            discovery_timeout=60,
            auto_discover=False
        )
        assert manager2.cache_dir == custom_cache
```

### Integration Tests

**Location**: `tests/mcp-integration/`

**Purpose**: End-to-end testing with real MCP protocol and Claude Code binary.

**Structure**:
```
mcp-integration/
├── agents/                    # Testing agents
│   ├── session_testing_agent.py
│   ├── streaming_validator_agent.py
│   ├── hook_validation_agent.py
│   └── file_system_agent.py
├── validators/                # Protocol validators
│   └── bidirectional_validator.py
├── gates/                     # Quality gates
│   ├── pre_deployment_gate.py
│   └── production_readiness_gate.py
└── run_integration_tests.py   # Main test runner
```

**Running Integration Tests**:
```bash
# All integration tests
poetry run pytest tests/mcp-integration/ -v

# Run with integration test runner
python tests/mcp-integration/run_integration_tests.py

# Run specific validation
poetry run pytest tests/mcp-integration/validators/ -v
```

**Characteristics**:
- Require Claude Code binary
- Test real MCP protocol communication
- Validate bidirectional streaming
- Test hook execution
- Verify session lifecycle

### Benchmark Tests

**Location**: `tests/benchmarks/`

**Purpose**: Performance testing and regression detection.

**13 Benchmark Suites**:
1. `benchmark_analytics.py` - Analytics performance
2. `benchmark_binary.py` - Binary operations
3. `benchmark_cas.py` - Content-addressable storage
4. `benchmark_checkpoint.py` - Checkpoint system
5. `benchmark_commands.py` - Command execution
6. `benchmark_hooks.py` - Hook system
7. `benchmark_registry.py` - Process registry
8. `benchmark_session.py` - Session operations
9. `benchmark_streaming.py` - Stream processing
10. `benchmark_transport.py` - Transport layer
11. `test_streaming_performance.py` - Streaming benchmarks
12. `visualize_benchmarks.py` - Visualization tools
13. `run_benchmarks.py` - Benchmark runner

**Running Benchmarks**:
```bash
# All benchmarks
poetry run pytest tests/benchmarks/ -v

# Specific benchmark suite
poetry run pytest tests/benchmarks/benchmark_session.py

# Run with benchmark runner
python tests/benchmarks/run_benchmarks.py

# Visualize results
python tests/benchmarks/visualize_benchmarks.py
```

**Example Benchmark**:
```python
@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_session_creation_performance(self, benchmark, session_manager):
    """Benchmark session creation performance."""
    batch_sizes = [1, 10, 50, 100]
    results = {}

    for batch_size in batch_sizes:
        creation_times = []

        for run in range(5):
            start = time.perf_counter()

            sessions = []
            for i in range(batch_size):
                session = await session_manager.create_session(
                    project_path=f"/test/project_{i}",
                    prompt=f"Test prompt {i}",
                    model="claude-3-opus"
                )
                sessions.append(session)

            elapsed = time.perf_counter() - start
            creation_times.append(elapsed)

        results[batch_size] = {
            "mean": statistics.mean(creation_times),
            "median": statistics.median(creation_times),
            "stdev": statistics.stdev(creation_times)
        }
```

---

## 4. Test Fixtures

### Shared Fixtures (conftest.py)

The `tests/conftest.py` file provides shared fixtures used across all tests:

```python
# Event loop for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Temporary directory
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)

# Test database
@pytest.fixture
async def test_db(temp_dir: Path) -> AsyncGenerator[Database, None]:
    """Create a test database."""
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    await db.initialize()
    yield db
    await db.close()

# Test configuration
@pytest.fixture
def test_config(temp_dir: Path) -> ShannonConfig:
    """Create test configuration."""
    config_path = temp_dir / "config.json"
    config_path.write_text(json.dumps(TEST_CONFIG))
    config = ShannonConfig()
    config._config = TEST_CONFIG
    return config

# Component managers
@pytest.fixture
async def binary_manager(test_db, test_config):
    """Create a test binary manager."""
    manager = BinaryManager(test_db, test_config)
    await manager.start()
    yield manager
    await manager.stop()

@pytest.fixture
async def session_manager(test_db, test_config, binary_manager):
    """Create a test session manager."""
    manager = SessionManager(test_db, test_config, binary_manager)
    await manager.start()
    yield manager
    await manager.stop()

@pytest.fixture
async def agent_manager(test_db, test_config):
    """Create a test agent manager."""
    manager = AgentManager(test_db, test_config)
    await manager.start()
    yield manager
    await manager.stop()

# Mock Claude binary
@pytest.fixture
def mock_claude_binary(temp_dir: Path) -> Path:
    """Create a mock Claude binary for testing."""
    if os.name == 'nt':
        binary_path = temp_dir / "claude.exe"
        binary_path.write_text("@echo off\necho Claude Code v1.0.0\n")
    else:
        binary_path = temp_dir / "claude"
        binary_path.write_text("#!/bin/bash\necho 'Claude Code v1.0.0'\n")
        binary_path.chmod(0o755)
    return binary_path

# Sample test data
@pytest.fixture
def sample_agent_data() -> Dict[str, Any]:
    """Sample agent data for testing."""
    return {
        "name": "test-agent",
        "description": "A test agent for unit tests",
        "system_prompt": "You are a test agent.",
        "category": "testing",
        "capabilities": ["test", "debug"]
    }

@pytest.fixture
def sample_session_data() -> Dict[str, Any]:
    """Sample session data for testing."""
    return {
        "id": "test-session-123",
        "project_path": "/test/project",
        "prompt": "Test prompt",
        "model": "claude-3-opus"
    }
```

### Test Utilities

**Location**: `tests/utils/`

```python
# Async helpers (tests/utils/async_helpers.py)
async def wait_for_condition(condition_func, timeout=5.0, interval=0.1):
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)
    return False

# Mock helpers (tests/utils/mock_helpers.py)
class MockBinaryManager:
    """Mock binary manager for testing."""
    pass

# Performance utilities (tests/utils/performance.py)
class PerformanceTimer:
    """Context manager for timing code execution."""
    pass

class PerformanceMonitor:
    """Monitor performance metrics during tests."""
    pass
```

---

## 5. Writing New Tests

### Test Structure (AAA Pattern)

Follow the **Arrange-Act-Assert** pattern:

```python
@pytest.mark.asyncio
async def test_session_creation(session_manager, sample_session_data):
    """Test creating a new session."""

    # ARRANGE - Set up test data and preconditions
    project_path = sample_session_data["project_path"]
    prompt = sample_session_data["prompt"]

    # ACT - Execute the operation being tested
    session = await session_manager.create_session(
        project_path=project_path,
        prompt=prompt,
        model="claude-3-opus"
    )

    # ASSERT - Verify the results
    assert session is not None
    assert session.project_path == project_path
    assert session.prompt == prompt
    assert session.status == SessionStatus.CREATED
```

### Async Test Patterns

```python
# Basic async test
@pytest.mark.asyncio
async def test_async_operation(session_manager):
    """Test an async operation."""
    result = await session_manager.some_async_method()
    assert result is not None

# Testing async context managers
@pytest.mark.asyncio
async def test_async_context_manager():
    """Test async context manager."""
    async with SessionManager() as manager:
        result = await manager.do_something()
        assert result

# Testing async generators
@pytest.mark.asyncio
async def test_async_generator(session_manager):
    """Test async generator."""
    items = []
    async for item in session_manager.stream_events():
        items.append(item)
        if len(items) >= 10:
            break
    assert len(items) == 10

# Testing concurrent operations
@pytest.mark.asyncio
async def test_concurrent_sessions(session_manager):
    """Test multiple concurrent sessions."""
    tasks = [
        session_manager.create_session(f"/project/{i}", f"prompt {i}")
        for i in range(10)
    ]
    sessions = await asyncio.gather(*tasks)
    assert len(sessions) == 10
```

### Parametrized Tests

```python
@pytest.mark.parametrize("timeout,expected", [
    (1.0, True),
    (5.0, True),
    (0.1, False),
])
@pytest.mark.asyncio
async def test_timeout_variations(session_manager, timeout, expected):
    """Test different timeout values."""
    try:
        result = await asyncio.wait_for(
            session_manager.some_operation(),
            timeout=timeout
        )
        assert expected is True
    except asyncio.TimeoutError:
        assert expected is False

@pytest.mark.parametrize("batch_size", [1, 10, 50, 100])
@pytest.mark.asyncio
async def test_batch_processing(session_manager, batch_size):
    """Test different batch sizes."""
    sessions = []
    for i in range(batch_size):
        session = await session_manager.create_session(
            f"/project/{i}",
            f"prompt {i}"
        )
        sessions.append(session)

    assert len(sessions) == batch_size
```

### Test Fixtures Usage

```python
# Using multiple fixtures
@pytest.mark.asyncio
async def test_with_multiple_fixtures(
    binary_manager,
    session_manager,
    test_db,
    sample_session_data
):
    """Test using multiple fixtures."""
    # All fixtures are automatically set up and torn down
    session = await session_manager.create_session(**sample_session_data)
    assert session is not None

# Creating custom fixtures
@pytest.fixture
async def prepared_session(session_manager, sample_session_data):
    """Fixture that creates a prepared session."""
    session = await session_manager.create_session(**sample_session_data)
    await session.start()
    yield session
    await session.stop()

# Using custom fixture
@pytest.mark.asyncio
async def test_with_prepared_session(prepared_session):
    """Test with a pre-prepared session."""
    assert prepared_session.status == SessionStatus.RUNNING
```

### Best Practices

#### Test Naming Conventions

```python
# Good test names - descriptive and specific
def test_binary_manager_discovers_system_binaries():
    """Test that binary manager can discover system binaries."""
    pass

def test_session_creation_fails_with_invalid_project_path():
    """Test that session creation fails with invalid project path."""
    pass

def test_checkpoint_restore_recovers_complete_state():
    """Test that checkpoint restore recovers complete state."""
    pass

# Bad test names - vague and unclear
def test_manager():  # Too vague
    pass

def test_1():  # Meaningless
    pass

def test_stuff():  # Not descriptive
    pass
```

#### Isolation and Independence

```python
# Good - tests are independent
@pytest.mark.asyncio
async def test_create_session(session_manager):
    """Each test creates its own session."""
    session = await session_manager.create_session("/project", "prompt")
    assert session is not None

@pytest.mark.asyncio
async def test_delete_session(session_manager):
    """Each test creates its own session."""
    session = await session_manager.create_session("/project", "prompt")
    await session_manager.delete_session(session.id)
    # Verify deletion
    with pytest.raises(SessionNotFoundError):
        await session_manager.get_session(session.id)

# Bad - tests depend on each other
shared_session = None

def test_create_session_bad(session_manager):
    """Don't share state between tests!"""
    global shared_session
    shared_session = session_manager.create_session("/project", "prompt")

def test_use_session_bad():
    """This test depends on the previous test running first."""
    assert shared_session is not None  # Brittle!
```

#### Fast Tests

```python
# Good - fast tests with minimal delays
@pytest.mark.asyncio
async def test_fast_operation(session_manager):
    """Test completes in milliseconds."""
    result = await session_manager.validate_config()
    assert result is True

# Use smaller timeouts in tests
@pytest.mark.asyncio
async def test_with_short_timeout(session_manager):
    """Use shorter timeouts for faster tests."""
    async with asyncio.timeout(1.0):  # 1 second timeout
        result = await session_manager.some_operation()
        assert result

# Bad - slow tests with unnecessary delays
@pytest.mark.asyncio
async def test_slow_operation(session_manager):
    """Avoid unnecessary delays."""
    result = await session_manager.some_operation()
    await asyncio.sleep(5.0)  # Don't do this!
    assert result
```

#### Clear Assertions

```python
# Good - clear, specific assertions
@pytest.mark.asyncio
async def test_session_state(session_manager):
    """Test session state transitions."""
    session = await session_manager.create_session("/project", "prompt")

    # Clear assertions with messages
    assert session.status == SessionStatus.CREATED, \
        f"Expected CREATED status, got {session.status}"

    await session.start()
    assert session.status == SessionStatus.RUNNING, \
        "Session should be RUNNING after start()"

    # Multiple assertions for complex state
    assert session.project_path == "/project"
    assert session.prompt == "prompt"
    assert session.start_time is not None

# Good - use pytest.raises for exceptions
@pytest.mark.asyncio
async def test_invalid_session_id(session_manager):
    """Test error handling for invalid session ID."""
    with pytest.raises(SessionNotFoundError) as exc_info:
        await session_manager.get_session("invalid-id")

    assert "invalid-id" in str(exc_info.value)

# Bad - vague assertions
@pytest.mark.asyncio
async def test_vague_assertions(session_manager):
    """Avoid vague assertions."""
    session = await session_manager.create_session("/project", "prompt")
    assert session  # What are we checking?
    assert session.status  # Is any status ok?
```

---

## 6. Coverage Analysis

### Running Coverage Reports

```bash
# Terminal report with missing lines
poetry run pytest --cov=shannon_mcp --cov-report=term-missing

# HTML report (opens in browser)
poetry run pytest --cov=shannon_mcp --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
poetry run pytest --cov=shannon_mcp --cov-report=xml

# All reports (configured in pyproject.toml)
poetry run pytest --cov=shannon_mcp
```

### Coverage Goals

**Overall Target**: 80%+

**Component-Specific Targets**:
- **Critical Components** (90%+):
  - Binary Manager (`shannon_mcp.managers.binary`)
  - Session Manager (`shannon_mcp.managers.session`)
  - MCP Protocol (`shannon_mcp.mcp`)
  - Streaming (`shannon_mcp.streaming`)

- **Important Components** (80%+):
  - Agent Manager (`shannon_mcp.managers.agent`)
  - Checkpoint System (`shannon_mcp.checkpoints`)
  - Hooks Framework (`shannon_mcp.hooks`)
  - Analytics (`shannon_mcp.analytics`)

- **Supporting Components** (70%+):
  - Storage (`shannon_mcp.storage`)
  - Utilities (`shannon_mcp.utils`)
  - Registry (`shannon_mcp.registry`)

### Interpreting Coverage Reports

```bash
# Terminal report shows:
# Name                              Stmts   Miss  Cover   Missing
# ---------------------------------------------------------------
# src/shannon_mcp/managers/binary.py   150     15    90%   45-52, 78
# src/shannon_mcp/managers/session.py  200     10    95%   156-160
# src/shannon_mcp/streaming/jsonl.py   120      8    93%   89-94
# ---------------------------------------------------------------
# TOTAL                                470     33    93%

# Missing lines indicate code not executed by tests
# Example: "45-52" means lines 45 through 52 need test coverage
```

### Identifying Coverage Gaps

```bash
# Find files with low coverage
poetry run pytest --cov=shannon_mcp --cov-report=term | grep -E "^[^\s]+\s+\d+\s+\d+\s+[0-7][0-9]%"

# Get coverage for specific module
poetry run pytest --cov=shannon_mcp.managers.binary --cov-report=term

# Generate HTML report and examine specific files
poetry run pytest --cov=shannon_mcp --cov-report=html
# Open htmlcov/index.html and click on files to see uncovered lines
```

### Coverage Configuration

Coverage settings in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/shannon_mcp"]
omit = ["*/tests/*", "*/test_*.py"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "pass",
    "except ImportError:",
]
```

---

## 7. Continuous Integration

### GitHub Actions Integration

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install Poetry
      uses: snok/install-poetry@v1
      with:
        version: 1.7.0

    - name: Install dependencies
      run: poetry install

    - name: Run unit tests
      run: poetry run pytest tests/test_*.py -v

    - name: Run functional tests
      run: poetry run pytest tests/functional/ -v

    - name: Run with coverage
      run: poetry run pytest --cov=shannon_mcp --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=88]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest-fast
        entry: poetry run pytest tests/test_*.py -x
        language: system
        pass_filenames: false
        always_run: true
```

Install pre-commit:
```bash
poetry add --group dev pre-commit
poetry run pre-commit install
poetry run pre-commit run --all-files
```

### Running Tests in CI

```bash
# Fast CI tests (unit tests only)
poetry run pytest tests/test_*.py -v --maxfail=5

# Full CI tests (all except benchmarks)
poetry run pytest tests/ -m "not benchmark" -v

# CI with coverage enforcement (fail if < 80%)
poetry run pytest --cov=shannon_mcp --cov-fail-under=80

# Parallel execution in CI
poetry run pytest -n auto tests/

# Generate multiple report formats
poetry run pytest \
    --cov=shannon_mcp \
    --cov-report=xml \
    --cov-report=html \
    --junitxml=test-results.xml
```

---

## 8. Performance Testing

### Running Benchmarks

```bash
# Run all benchmarks
poetry run pytest tests/benchmarks/ -v -m benchmark

# Run specific benchmark suite
poetry run pytest tests/benchmarks/benchmark_session.py

# Run benchmarks with results output
python tests/benchmarks/run_benchmarks.py

# Save benchmark results
python tests/benchmarks/run_benchmarks.py --output benchmark_results.json

# Compare with baseline
python tests/benchmarks/run_benchmarks.py --baseline benchmark_baseline.json
```

### Benchmark Suites

```bash
# Binary Manager benchmarks
poetry run pytest tests/benchmarks/benchmark_binary.py -v
# Tests: binary discovery, caching, version checking

# Session Manager benchmarks
poetry run pytest tests/benchmarks/benchmark_session.py -v
# Tests: session creation, concurrent sessions, session cleanup

# Streaming benchmarks
poetry run pytest tests/benchmarks/benchmark_streaming.py -v
# Tests: JSONL parsing, stream throughput, backpressure handling

# Checkpoint benchmarks
poetry run pytest tests/benchmarks/benchmark_checkpoint.py -v
# Tests: checkpoint creation, restoration, compression

# Analytics benchmarks
poetry run pytest tests/benchmarks/benchmark_analytics.py -v
# Tests: event writing, querying, aggregation

# CAS benchmarks
poetry run pytest tests/benchmarks/benchmark_cas.py -v
# Tests: content storage, deduplication, retrieval

# Commands benchmarks
poetry run pytest tests/benchmarks/benchmark_commands.py -v
# Tests: command execution, argument parsing, validation

# Hooks benchmarks
poetry run pytest tests/benchmarks/benchmark_hooks.py -v
# Tests: hook execution, event dispatch, hook chaining

# Registry benchmarks
poetry run pytest tests/benchmarks/benchmark_registry.py -v
# Tests: process registration, query performance, cleanup

# Transport benchmarks
poetry run pytest tests/benchmarks/benchmark_transport.py -v
# Tests: stdio transport, message passing, buffering
```

### Interpreting Benchmark Results

```python
# Benchmark output format:
"""
Benchmark: Session Creation (batch_size=100)
  Mean:   1.234 seconds
  Median: 1.189 seconds
  StdDev: 0.089 seconds
  Min:    1.156 seconds
  Max:    1.401 seconds

  Operations/sec: 81.03
  Throughput: 8103.45 sessions/sec
"""

# What to look for:
# - Mean/Median should be similar (consistent performance)
# - Low StdDev indicates stable performance
# - Compare against baseline for regressions
# - Track operations/sec over time
```

### Visualizing Benchmark Results

```bash
# Generate visualization
python tests/benchmarks/visualize_benchmarks.py

# Creates:
# - benchmark_comparison.png - Bar chart comparing components
# - benchmark_timeline.png - Performance over time
# - benchmark_distribution.png - Distribution histograms
```

### Performance Regression Detection

```bash
# Save baseline benchmarks
python tests/benchmarks/run_benchmarks.py --output baseline.json

# Compare current performance to baseline
python tests/benchmarks/run_benchmarks.py \
    --baseline baseline.json \
    --threshold 0.10  # Fail if >10% slower

# Example output:
"""
Comparing to baseline...
  Session creation: 1.234s vs 1.189s (+3.8%) ✓
  Binary discovery: 0.456s vs 0.389s (+17.2%) ✗ REGRESSION!
  Stream parsing:   0.234s vs 0.221s (+5.9%) ✓
"""
```

### Optimization Workflow

1. **Identify Bottlenecks**:
   ```bash
   poetry run pytest tests/benchmarks/ -v --durations=0
   ```

2. **Profile Specific Tests**:
   ```bash
   poetry run python -m cProfile -o profile.stats tests/benchmarks/benchmark_session.py
   poetry run python -m pstats profile.stats
   ```

3. **Make Changes and Re-test**:
   ```bash
   poetry run pytest tests/benchmarks/benchmark_session.py -v
   ```

4. **Compare Results**:
   ```bash
   python tests/benchmarks/run_benchmarks.py --baseline before.json
   ```

---

## 9. Testing Individual Components

### Binary Manager Tests

```bash
# All binary manager tests
poetry run pytest tests/test_binary_manager.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_binary_manager.py -v

# Specific test patterns
poetry run pytest -k "test_discover" -v  # Discovery tests
poetry run pytest -k "test_cache" -v     # Caching tests
poetry run pytest -k "test_version" -v   # Version tests

# With coverage
poetry run pytest tests/test_binary_manager.py \
    --cov=shannon_mcp.managers.binary \
    --cov-report=term-missing

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_binary.py -v
```

**Key Test Areas**:
- Binary discovery (system PATH, custom paths, npm global)
- Version detection and validation
- Binary caching and invalidation
- Automatic updates
- Error handling (missing binary, invalid version)

### Session Manager Tests

```bash
# All session manager tests
poetry run pytest tests/test_session_manager.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_session_manager.py -v

# Session management workflows
poetry run pytest tests/functional/test_session_management.py -v

# Specific test patterns
poetry run pytest -k "test_create_session" -v
poetry run pytest -k "test_concurrent" -v
poetry run pytest -k "test_cleanup" -v

# With coverage
poetry run pytest tests/test_session_manager.py \
    --cov=shannon_mcp.managers.session \
    --cov-report=html

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_session.py -v
```

**Key Test Areas**:
- Session lifecycle (create, start, stop, cleanup)
- Concurrent session handling
- Session state management
- Timeout handling
- Resource cleanup
- Session caching

### Streaming Tests

```bash
# All streaming tests
poetry run pytest tests/test_streaming.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_streaming.py -v

# Streaming integration tests
poetry run pytest tests/functional/test_streaming_integration.py -v

# Specific test patterns
poetry run pytest -k "test_jsonl" -v      # JSONL parsing
poetry run pytest -k "test_backpressure" -v  # Backpressure handling
poetry run pytest -k "test_error" -v      # Error recovery

# With coverage
poetry run pytest tests/test_streaming.py \
    --cov=shannon_mcp.streaming \
    --cov-report=term-missing

# Performance tests
poetry run pytest tests/benchmarks/benchmark_streaming.py -v
poetry run pytest tests/benchmarks/test_streaming_performance.py -v
```

**Key Test Areas**:
- JSONL stream parsing
- Bidirectional streaming
- Backpressure handling
- Error recovery
- Large message handling
- Stream multiplexing

### Checkpoint System Tests

```bash
# All checkpoint tests
poetry run pytest tests/functional/test_checkpoint_system.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_checkpoint.py -v

# Specific test patterns
poetry run pytest -k "test_create_checkpoint" -v
poetry run pytest -k "test_restore" -v
poetry run pytest -k "test_diff" -v

# With coverage
poetry run pytest tests/functional/test_complete_checkpoint.py \
    --cov=shannon_mcp.checkpoints \
    --cov-report=html

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_checkpoint.py -v
```

**Key Test Areas**:
- Checkpoint creation and metadata
- State restoration
- Diff generation
- Compression and storage
- Checkpoint pruning
- Version management

### Analytics Tests

```bash
# All analytics tests
poetry run pytest tests/functional/test_analytics_monitoring.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_analytics.py -v

# Specific test patterns
poetry run pytest -k "test_event_recording" -v
poetry run pytest -k "test_query" -v
poetry run pytest -k "test_aggregation" -v

# With coverage
poetry run pytest tests/functional/test_complete_analytics.py \
    --cov=shannon_mcp.analytics \
    --cov-report=term-missing

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_analytics.py -v
```

**Key Test Areas**:
- Event recording (session, tool, error events)
- JSONL writer performance
- Query performance
- Aggregation and reporting
- Data retention and cleanup
- Export functionality

### Agent System Tests

```bash
# All agent tests
poetry run pytest tests/functional/test_agent_system.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_agent.py -v

# Specific test patterns
poetry run pytest -k "test_agent_registration" -v
poetry run pytest -k "test_agent_execution" -v
poetry run pytest -k "test_agent_communication" -v

# With coverage
poetry run pytest tests/functional/test_complete_agent.py \
    --cov=shannon_mcp.managers.agent \
    --cov-report=html
```

**Key Test Areas**:
- Agent registration and discovery
- Agent execution and lifecycle
- Inter-agent communication
- Agent capabilities and permissions
- Error handling and recovery
- Agent state management

### Hooks System Tests

```bash
# All hooks tests
poetry run pytest tests/functional/test_hooks_commands.py -v

# Complete functional tests
poetry run pytest tests/functional/test_complete_hooks.py -v

# Specific test patterns
poetry run pytest -k "test_hook_registration" -v
poetry run pytest -k "test_hook_execution" -v
poetry run pytest -k "test_hook_chaining" -v

# With coverage
poetry run pytest tests/functional/test_complete_hooks.py \
    --cov=shannon_mcp.hooks \
    --cov-report=term-missing

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_hooks.py -v
```

**Key Test Areas**:
- Hook registration and discovery
- Hook execution lifecycle
- Event dispatch and filtering
- Hook chaining and composition
- Error handling in hooks
- Hook priority and ordering

### Commands Tests

```bash
# Complete functional tests
poetry run pytest tests/functional/test_complete_commands.py -v

# Specific test patterns
poetry run pytest -k "test_command_registration" -v
poetry run pytest -k "test_command_execution" -v
poetry run pytest -k "test_command_validation" -v

# With coverage
poetry run pytest tests/functional/test_complete_commands.py \
    --cov=shannon_mcp.commands \
    --cov-report=html

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_commands.py -v
```

**Key Test Areas**:
- Command registration and discovery
- Argument parsing and validation
- Command execution
- Error handling
- Help and documentation
- Command chaining

### Process Registry Tests

```bash
# All registry tests
poetry run pytest tests/functional/test_process_registry.py -v

# Specific test patterns
poetry run pytest -k "test_process_registration" -v
poetry run pytest -k "test_process_query" -v
poetry run pytest -k "test_process_cleanup" -v

# With coverage
poetry run pytest tests/functional/test_process_registry.py \
    --cov=shannon_mcp.registry \
    --cov-report=term-missing

# Benchmarks
poetry run pytest tests/benchmarks/benchmark_registry.py -v
```

**Key Test Areas**:
- Process registration and tracking
- Process query and filtering
- Process cleanup and lifecycle
- Cross-session process discovery
- Resource monitoring

### Full Integration Tests

```bash
# All integration tests
poetry run pytest tests/functional/test_full_integration.py -v

# MCP protocol integration
poetry run pytest tests/mcp-integration/ -v

# End-to-end workflows
poetry run pytest -k "test_e2e" -v

# With coverage
poetry run pytest tests/functional/test_full_integration.py \
    --cov=shannon_mcp \
    --cov-report=html
```

**Key Test Areas**:
- Complete MCP protocol workflows
- Session creation to completion
- Tool usage and responses
- Error handling end-to-end
- Multi-session scenarios
- Real Claude Code binary integration

---

## 10. Troubleshooting Tests

### Common Test Failures

#### 1. Async Test Issues

**Problem**: `RuntimeError: Event loop is closed`

```python
# Bad - loop management issue
@pytest.mark.asyncio
async def test_bad():
    loop = asyncio.get_event_loop()  # Don't manage loop manually
    result = await some_async_function()

# Good - let pytest-asyncio handle it
@pytest.mark.asyncio
async def test_good():
    result = await some_async_function()  # Just use await
```

**Problem**: `Task was destroyed but it is pending`

```python
# Bad - not cleaning up tasks
@pytest.mark.asyncio
async def test_bad():
    task = asyncio.create_task(long_running_operation())
    # Test ends without awaiting or cancelling task

# Good - clean up tasks
@pytest.mark.asyncio
async def test_good():
    task = asyncio.create_task(long_running_operation())
    try:
        result = await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

#### 2. Database Cleanup Issues

**Problem**: `Database is locked` or `Table already exists`

```python
# Bad - not cleaning up database
@pytest.fixture
async def bad_db():
    db = Database("test.db")
    await db.initialize()
    yield db
    # Missing cleanup!

# Good - always clean up
@pytest.fixture
async def good_db(temp_dir):
    db_path = temp_dir / "test.db"  # Use temp directory
    db = Database(db_path)
    await db.initialize()
    yield db
    await db.close()  # Always close
    # temp_dir fixture cleans up files
```

**Solution**: Use `temp_dir` fixture and always close resources:
```bash
# If tests fail with locked database:
rm -rf tests/__pycache__
rm -rf tests/**/__pycache__
poetry run pytest --cache-clear
```

#### 3. Fixture Problems

**Problem**: `Fixture 'xyz' not found`

```python
# Check fixture is defined in conftest.py or test file
# Check fixture scope matches usage
# Check fixture is imported if from external module
```

**Problem**: `ScopeMismatch: You tried to access the function scoped fixture...`

```python
# Bad - scope mismatch
@pytest.fixture(scope="session")
async def session_fixture(function_fixture):  # function_fixture has narrower scope
    pass

# Good - matching scopes
@pytest.fixture(scope="session")
async def session_fixture(session_fixture_dep):
    pass

@pytest.fixture  # function scope by default
async def function_fixture(function_fixture_dep):
    pass
```

#### 4. Timeout Issues

**Problem**: Tests hang or timeout

```python
# Add timeout to async tests
@pytest.mark.asyncio
@pytest.mark.timeout(30)  # 30 second timeout
async def test_with_timeout():
    result = await potentially_slow_operation()

# Or use asyncio.timeout
@pytest.mark.asyncio
async def test_with_timeout():
    async with asyncio.timeout(5.0):
        result = await potentially_slow_operation()
```

**Solution**: Run with timeout flag:
```bash
poetry run pytest --timeout=60  # Global 60 second timeout
```

#### 5. Import Errors

**Problem**: `ModuleNotFoundError: No module named 'shannon_mcp'`

**Solution**:
```bash
# Ensure src is in Python path (should be automatic with pyproject.toml)
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Or run with pytest's pythonpath
poetry run pytest --pythonpath=src

# Check pyproject.toml has:
# [tool.pytest.ini_options]
# pythonpath = ["src"]
```

#### 6. Flaky Tests

**Problem**: Test sometimes passes, sometimes fails

```python
# Common causes:
# 1. Race conditions
# 2. Timing dependencies
# 3. External service dependencies
# 4. Shared state between tests

# Solutions:
# 1. Add proper synchronization
@pytest.mark.asyncio
async def test_synchronized():
    event = asyncio.Event()

    async def task1():
        await asyncio.sleep(0.1)
        event.set()

    async def task2():
        await event.wait()  # Wait for task1
        return "result"

    await asyncio.gather(task1(), task2())

# 2. Use retry logic for eventually consistent operations
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(0.1))
async def eventually_consistent_check():
    result = await check_condition()
    assert result is True

# 3. Isolate tests with fixtures
@pytest.fixture
async def isolated_resource():
    resource = create_unique_resource()
    yield resource
    cleanup_resource(resource)
```

### Debug Mode

```bash
# Run with verbose output and print statements
poetry run pytest -v -s tests/test_binary_manager.py

# Show local variables on failure
poetry run pytest -l tests/test_binary_manager.py

# Drop into debugger on failure
poetry run pytest --pdb tests/test_binary_manager.py

# Drop into debugger on first failure
poetry run pytest --pdb -x tests/test_binary_manager.py

# Show full traceback
poetry run pytest --tb=long tests/test_binary_manager.py
```

### Logging During Tests

```python
# Enable logging in tests
import logging

@pytest.mark.asyncio
async def test_with_logging(caplog):
    """Test with log capture."""
    caplog.set_level(logging.DEBUG)

    # Your test code
    await some_operation()

    # Check logs
    assert "Expected log message" in caplog.text
    assert caplog.records[0].levelname == "DEBUG"
```

```bash
# Run with log output
poetry run pytest --log-cli-level=DEBUG tests/test_binary_manager.py

# Save logs to file
poetry run pytest --log-file=test.log --log-file-level=DEBUG
```

---

## 11. Test Data and Fixtures

### Location of Test Fixtures

```
tests/fixtures/
├── __init__.py
├── agent_fixtures.py        # Agent test data
├── session_fixtures.py      # Session test data
├── checkpoint_fixtures.py   # Checkpoint test data
├── analytics_fixtures.py    # Analytics event data
└── binary_fixtures.py       # Binary test data
```

### Test Data Generators

```python
# Session data generator
class SessionFixtures:
    @staticmethod
    def create_session_data(
        project_path="/test/project",
        prompt="Test prompt",
        model="claude-3-opus"
    ):
        return {
            "project_path": project_path,
            "prompt": prompt,
            "model": model,
            "temperature": 0.7,
            "max_tokens": 4096
        }

    @staticmethod
    def create_multiple_sessions(count=10):
        return [
            SessionFixtures.create_session_data(
                project_path=f"/test/project_{i}",
                prompt=f"Test prompt {i}"
            )
            for i in range(count)
        ]

# Agent data generator
class AgentFixtures:
    @staticmethod
    def create_agent_data(name="test-agent", category="testing"):
        return {
            "name": name,
            "description": f"Test agent: {name}",
            "system_prompt": f"You are {name}.",
            "category": category,
            "capabilities": ["test", "debug"],
            "metadata": {
                "version": "1.0.0",
                "author": "Test Suite"
            }
        }

# Analytics data generator
class AnalyticsFixtures:
    @staticmethod
    def create_event(event_type="session_start", session_id="test-session"):
        return {
            "id": f"event-{event_type}-{session_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "session_id": session_id,
            "data": {}
        }
```

### Creating Realistic Test Scenarios

```python
@pytest.fixture
async def realistic_session_scenario(session_manager, binary_manager):
    """Create a realistic multi-session scenario."""
    # Create multiple sessions
    sessions = []
    for i in range(5):
        session = await session_manager.create_session(
            project_path=f"/home/user/project_{i}",
            prompt=f"Implement feature {i}",
            model="claude-3-opus",
            temperature=0.7
        )
        sessions.append(session)

    # Start some sessions
    for session in sessions[:3]:
        await session.start()

    # Generate some activity
    for session in sessions[:3]:
        await session.record_tool_use("write_file", {"file": "test.py"})
        await session.record_tool_use("bash", {"command": "pytest"})

    yield sessions

    # Cleanup
    for session in sessions:
        try:
            await session.stop()
        except:
            pass

@pytest.fixture
async def realistic_checkpoint_scenario(checkpoint_manager):
    """Create a realistic checkpoint history."""
    checkpoints = []

    # Create initial checkpoint
    checkpoint1 = await checkpoint_manager.create_checkpoint(
        "Initial implementation",
        state={"file_count": 5, "total_lines": 200}
    )
    checkpoints.append(checkpoint1)

    # Create incremental checkpoints
    for i in range(5):
        checkpoint = await checkpoint_manager.create_checkpoint(
            f"Iteration {i+1}",
            state={"file_count": 5 + i, "total_lines": 200 + i * 50}
        )
        checkpoints.append(checkpoint)

    yield checkpoints

    # Cleanup
    for checkpoint in checkpoints:
        await checkpoint_manager.delete_checkpoint(checkpoint.id)
```

---

## 12. Manual Testing

### Testing MCP Tools Manually

#### Using MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run Shannon MCP server with inspector
mcp-inspector poetry run shannon-mcp

# Inspector opens in browser at http://localhost:5173
# - Test tool execution
# - Inspect messages
# - View logs
# - Test streaming
```

#### Using Python REPL

```python
# Start Python REPL with Shannon MCP
poetry run python

>>> from shannon_mcp.managers.binary import BinaryManager
>>> import asyncio
>>>
>>> # Test binary discovery
>>> async def test_discovery():
...     manager = BinaryManager()
...     await manager.start()
...     binaries = await manager.discover_all()
...     print(f"Found {len(binaries)} binaries")
...     for binary in binaries:
...         print(f"  - {binary.path} (v{binary.version})")
...     await manager.stop()
>>>
>>> asyncio.run(test_discovery())

>>> # Test session creation
>>> async def test_session():
...     from shannon_mcp.managers.session import SessionManager
...     manager = SessionManager()
...     await manager.start()
...     session = await manager.create_session(
...         project_path="/home/user/test-project",
...         prompt="Test prompt"
...     )
...     print(f"Created session: {session.id}")
...     print(f"Status: {session.status}")
...     await manager.stop()
>>>
>>> asyncio.run(test_session())
```

### Testing with Claude Desktop

#### 1. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "poetry",
      "args": ["run", "shannon-mcp"],
      "cwd": "/home/user/shannon-mcp",
      "env": {
        "SHANNON_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

#### 2. Test MCP Server

```bash
# Start Claude Desktop
# Open developer tools (Cmd+Option+I on Mac, Ctrl+Shift+I on Windows)

# In Claude Desktop, test tools:
# "Can you list the available Claude Code binaries?"
# "Create a new session for project at /home/user/test-project"
# "Show me the active sessions"
```

#### 3. Monitor Logs

```bash
# Tail Shannon MCP logs
tail -f ~/.shannon/logs/shannon-mcp.log

# Tail Claude Desktop logs (macOS)
tail -f ~/Library/Logs/Claude/main.log

# Tail Claude Desktop logs (Linux)
tail -f ~/.config/Claude/logs/main.log
```

### Interactive Testing Workflows

#### Test Complete Session Workflow

```bash
# 1. Start interactive Python session
poetry run python

# 2. Set up logging
>>> import logging
>>> logging.basicConfig(level=logging.DEBUG)

# 3. Import and initialize
>>> from shannon_mcp.server import ShannonMCPServer
>>> import asyncio
>>>
>>> async def test_workflow():
...     server = ShannonMCPServer()
...     await server.initialize()
...
...     # Test binary discovery
...     binaries = await server.list_binaries()
...     print(f"Available binaries: {binaries}")
...
...     # Create session
...     session = await server.create_session(
...         project_path="/home/user/test",
...         prompt="Write hello world"
...     )
...     print(f"Session created: {session['id']}")
...
...     # List sessions
...     sessions = await server.list_sessions()
...     print(f"Active sessions: {len(sessions)}")
...
...     # Stream output
...     async for message in server.stream_session(session['id']):
...         print(f"Message: {message}")
...
...     # Cleanup
...     await server.stop_session(session['id'])
...     await server.shutdown()
>>>
>>> asyncio.run(test_workflow())
```

#### Test Checkpoint Workflow

```bash
poetry run python

>>> from shannon_mcp.checkpoints.manager import CheckpointManager
>>> import asyncio
>>>
>>> async def test_checkpoints():
...     manager = CheckpointManager()
...     await manager.initialize()
...
...     # Create checkpoint
...     checkpoint = await manager.create_checkpoint(
...         message="Test checkpoint",
...         state={"file": "test.py", "line": 42}
...     )
...     print(f"Checkpoint created: {checkpoint.id}")
...
...     # List checkpoints
...     checkpoints = await manager.list_checkpoints()
...     for cp in checkpoints:
...         print(f"  {cp.id}: {cp.message}")
...
...     # Restore checkpoint
...     restored_state = await manager.restore_checkpoint(checkpoint.id)
...     print(f"Restored state: {restored_state}")
...
...     await manager.close()
>>>
>>> asyncio.run(test_checkpoints())
```

#### Test Streaming

```bash
poetry run python

>>> from shannon_mcp.streaming.jsonl import JSONLStreamProcessor
>>> import asyncio
>>>
>>> async def test_streaming():
...     processor = JSONLStreamProcessor()
...
...     # Test parsing
...     lines = [
...         '{"type": "session_start", "data": {"session_id": "123"}}',
...         '{"type": "tool_use", "data": {"tool": "bash", "args": ["ls"]}}',
...         '{"type": "tool_result", "data": {"output": "file1.py\\nfile2.py"}}'
...     ]
...
...     for line in lines:
...         message = await processor.parse_line(line)
...         print(f"Parsed: {message['type']}")
...
...     # Test async streaming
...     async def generate_messages():
...         for i in range(5):
...             await asyncio.sleep(0.1)
...             yield f'{{"id": {i}, "message": "Hello {i}"}}\n'
...
...     async for message in processor.stream_messages(generate_messages()):
...         print(f"Streamed: {message}")
>>>
>>> asyncio.run(test_streaming())
```

### Performance Testing Manually

```bash
# Test concurrent session creation
poetry run python

>>> import asyncio
>>> import time
>>> from shannon_mcp.managers.session import SessionManager
>>>
>>> async def benchmark_sessions():
...     manager = SessionManager()
...     await manager.start()
...
...     start = time.perf_counter()
...
...     # Create 100 concurrent sessions
...     tasks = [
...         manager.create_session(f"/project/{i}", f"prompt {i}")
...         for i in range(100)
...     ]
...     sessions = await asyncio.gather(*tasks)
...
...     elapsed = time.perf_counter() - start
...     print(f"Created {len(sessions)} sessions in {elapsed:.2f}s")
...     print(f"Rate: {len(sessions)/elapsed:.2f} sessions/sec")
...
...     await manager.stop()
>>>
>>> asyncio.run(benchmark_sessions())
```

---

## Summary

This testing guide covers:

1. **Testing Overview** - 66 test files, 4 categories, 80%+ coverage goal
2. **Running Tests** - Quick start commands and test options
3. **Test Categories** - Unit, Functional, Integration, Benchmark tests
4. **Test Fixtures** - Shared fixtures in conftest.py and custom fixtures
5. **Writing New Tests** - AAA pattern, async patterns, best practices
6. **Coverage Analysis** - Running reports, interpreting results, identifying gaps
7. **Continuous Integration** - GitHub Actions, pre-commit hooks, CI commands
8. **Performance Testing** - Running benchmarks, visualization, regression detection
9. **Testing Individual Components** - Component-specific test commands
10. **Troubleshooting Tests** - Common failures, debug mode, logging
11. **Test Data and Fixtures** - Test data generators, realistic scenarios
12. **Manual Testing** - MCP Inspector, Claude Desktop, interactive workflows

## Quick Reference

```bash
# Most Common Commands
poetry run pytest                          # Run all tests
poetry run pytest -v                       # Verbose output
poetry run pytest -k "test_name"          # Run specific tests
poetry run pytest --cov=shannon_mcp       # Run with coverage
poetry run pytest -m "not slow"           # Skip slow tests
poetry run pytest tests/functional/       # Run functional tests
poetry run pytest -x                       # Stop on first failure
poetry run pytest --lf                     # Run last failed tests

# Component Testing
poetry run pytest tests/test_binary_manager.py -v
poetry run pytest tests/functional/test_complete_session_manager.py -v
poetry run pytest tests/benchmarks/benchmark_streaming.py -v

# Coverage Reports
poetry run pytest --cov=shannon_mcp --cov-report=html
poetry run pytest --cov=shannon_mcp --cov-report=term-missing

# Debugging
poetry run pytest --pdb -x                # Debug first failure
poetry run pytest -v -s                    # Show print statements
poetry run pytest --log-cli-level=DEBUG   # Show debug logs
```

For more information, see:
- pytest documentation: https://docs.pytest.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- pytest-cov: https://pytest-cov.readthedocs.io/
