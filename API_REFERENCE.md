# Shannon MCP Server - API Reference

> Comprehensive API documentation for developers integrating with or extending Shannon MCP Server

Version: 0.1.0
Last Updated: 2025-11-13

---

## Table of Contents

1. [MCP Protocol APIs](#1-mcp-protocol-apis)
   - [Tools API](#tools-api)
   - [Resources API](#resources-api)
2. [Python API Reference](#2-python-api-reference)
   - [Core Managers](#core-managers)
   - [Configuration API](#configuration-api)
   - [Logging API](#logging-api)
   - [Error Handling](#error-handling)
   - [Notifications/Events](#notificationsevents)
3. [Advanced Features APIs](#3-advanced-features-apis)
   - [Checkpoint System](#checkpoint-system)
   - [Hooks Framework](#hooks-framework)
   - [Analytics API](#analytics-api)
   - [Process Registry](#process-registry)
4. [Data Models](#4-data-models)
5. [Type Definitions](#5-type-definitions)
6. [Constants](#6-constants)

---

## 1. MCP Protocol APIs

Shannon MCP Server implements the Model Context Protocol for Claude integration.

### Tools API

#### 1.1 find_claude_binary

Discover Claude Code installation on the system.

**Parameters:** None

**Returns:**
```json
{
  "path": "/usr/local/bin/claude",
  "version": "1.2.3",
  "version_string": "1.2.3",
  "build_date": "2025-01-15T10:30:00Z",
  "features": ["streaming", "checkpoints"],
  "environment": {},
  "discovered_at": "2025-11-13T12:00:00Z",
  "last_verified": "2025-11-13T12:00:00Z",
  "update_available": false,
  "latest_version": null,
  "discovery_method": "which",
  "is_valid": true,
  "metadata": {}
}
```

**Error Codes:**
- `BINARY_NOT_FOUND`: Claude Code binary not found on system
- `BINARY_INVALID`: Binary found but failed validation

**Example:**
```bash
# Via MCP Client
{
  "method": "tools/call",
  "params": {
    "name": "find_claude_binary",
    "arguments": {}
  }
}
```

---

#### 1.2 create_session

Create a new Claude Code session for interactive AI assistance.

**Parameters:**
```typescript
{
  prompt: string;              // Required: Initial prompt for the session
  model?: string;              // Optional: Model name (default: "claude-3-sonnet")
  checkpoint_id?: string;      // Optional: Restore from checkpoint
  context?: object;            // Optional: Additional context data
}
```

**Returns:**
```json
{
  "id": "session_abc123def456",
  "binary_path": "/usr/local/bin/claude",
  "model": "claude-3-sonnet",
  "state": "running",
  "messages": [
    {
      "role": "user",
      "content": "Help me build an API",
      "timestamp": "2025-11-13T12:00:00Z",
      "metadata": {}
    }
  ],
  "context": {},
  "checkpoint_id": null,
  "created_at": "2025-11-13T12:00:00Z",
  "error": null,
  "metrics": {
    "start_time": "2025-11-13T12:00:00Z",
    "end_time": null,
    "tokens_input": 0,
    "tokens_output": 0,
    "messages_sent": 1,
    "messages_received": 0,
    "errors_count": 0,
    "duration_seconds": null,
    "tokens_per_second": 0.0
  }
}
```

**Error Codes:**
- `MAX_SESSIONS_REACHED`: Maximum concurrent sessions exceeded
- `BINARY_NOT_FOUND`: Claude Code binary not available
- `SESSION_START_FAILED`: Failed to start session subprocess

**Example:**
```python
from shannon_mcp import SessionManager

# Create session
session = await session_manager.create_session(
    prompt="Help me build a REST API",
    model="claude-3-sonnet",
    context={"project": "/path/to/project"}
)
print(f"Session created: {session.id}")
```

---

#### 1.3 send_message

Send a message to an active session.

**Parameters:**
```typescript
{
  session_id: string;          // Required: Session ID
  content: string;             // Required: Message content
  timeout?: number;            // Optional: Timeout in seconds
}
```

**Returns:**
```json
{
  "success": true
}
```

**Error Codes:**
- `SESSION_NOT_FOUND`: Session ID does not exist
- `SESSION_NOT_RUNNING`: Session is not in running state
- `MESSAGE_TIMEOUT`: Message send timed out
- `MESSAGE_SEND_FAILED`: Failed to send message to subprocess

**Example:**
```python
# Send follow-up message
await session_manager.send_message(
    session_id="session_abc123def456",
    content="Add user authentication",
    timeout=30.0
)
```

---

#### 1.4 cancel_session

Cancel a running session gracefully.

**Parameters:**
```typescript
{
  session_id: string;          // Required: Session ID to cancel
}
```

**Returns:**
```json
{
  "success": true
}
```

**Error Codes:**
- `SESSION_NOT_FOUND`: Session ID does not exist
- `CANCEL_FAILED`: Failed to cancel session

**Example:**
```python
# Cancel session
await session_manager.cancel_session("session_abc123def456")
```

---

#### 1.5 list_sessions

List active sessions with optional filtering.

**Parameters:**
```typescript
{
  state?: string;              // Optional: Filter by state (running, completed, failed)
  limit?: integer;             // Optional: Maximum results (default: 100)
}
```

**Returns:**
```json
[
  {
    "id": "session_abc123def456",
    "model": "claude-3-sonnet",
    "state": "running",
    "created_at": "2025-11-13T12:00:00Z",
    "metrics": { ... }
  }
]
```

**Example:**
```python
# List all running sessions
sessions = await session_manager.list_sessions(state="running", limit=10)
for session in sessions:
    print(f"{session.id}: {session.state}")
```

---

#### 1.6 list_agents

List available AI agents with filtering.

**Parameters:**
```typescript
{
  category?: string;           // Optional: Filter by category
  status?: string;             // Optional: Filter by status
  capability?: string;         // Optional: Filter by capability name
}
```

**Returns:**
```json
[
  {
    "id": "agent_architecture",
    "name": "Architecture Agent",
    "description": "Master architect designing system structure",
    "category": "core_architecture",
    "capabilities": [
      {
        "name": "system_design",
        "description": "Design overall system architecture",
        "expertise_level": 10,
        "tools": []
      }
    ],
    "status": "available",
    "metrics": {
      "tasks_completed": 42,
      "tasks_failed": 2,
      "success_rate": 0.95,
      "average_task_time": 120.5
    }
  }
]
```

**Example:**
```python
# List all available infrastructure agents
agents = await agent_manager.list_agents(
    category="infrastructure",
    status="available"
)
```

---

#### 1.7 assign_task

Assign a task to an AI agent based on capabilities.

**Parameters:**
```typescript
{
  description: string;                    // Required: Task description
  required_capabilities: string[];        // Required: Required capabilities
  priority?: string;                      // Optional: low, medium, high, critical (default: medium)
  context?: object;                       // Optional: Additional context
  timeout?: integer;                      // Optional: Timeout in seconds
}
```

**Returns:**
```json
{
  "task_id": "task_xyz789abc012",
  "agent_id": "agent_architecture",
  "score": 0.92,
  "estimated_duration": 180,
  "confidence": 0.88
}
```

**Error Codes:**
- `NO_SUITABLE_AGENT`: No agent found with required capabilities
- `ALL_AGENTS_BUSY`: All suitable agents are currently busy

**Example:**
```python
# Assign architecture design task
assignment = await agent_manager.assign_task(
    TaskRequest(
        description="Design REST API architecture",
        required_capabilities=["system_design", "api_design"],
        priority="high",
        context={"project_type": "web_service"}
    )
)
print(f"Assigned to: {assignment.agent_id} (score: {assignment.score})")
```

---

### Resources API

Resources provide read-only access to server state and configuration.

#### 1.8 shannon://config

Current server configuration.

**URI Pattern:** `shannon://config`

**Response:**
```json
{
  "app_name": "shannon-mcp",
  "version": "0.1.0",
  "debug": false,
  "database": {
    "path": "/home/user/.shannon-mcp/shannon.db",
    "pool_size": 5,
    "timeout": 30.0
  },
  "logging": {
    "level": "INFO",
    "format": "json",
    "directory": "/home/user/.shannon-mcp/logs"
  },
  "binary_manager": {
    "search_paths": [],
    "nvm_check": true,
    "update_check_interval": 86400
  },
  "session_manager": {
    "max_concurrent_sessions": 10,
    "session_timeout": 3600,
    "buffer_size": 1048576
  }
}
```

**Example:**
```python
# Read configuration resource
config = await mcp_server.read_resource("shannon://config")
print(json.loads(config))
```

---

#### 1.9 shannon://agents

List of all registered AI agents.

**URI Pattern:** `shannon://agents`

**Response:**
```json
[
  {
    "id": "agent_architecture",
    "name": "Architecture Agent",
    "category": "core_architecture",
    "status": "available",
    "capabilities": [ ... ],
    "metrics": { ... }
  }
]
```

---

#### 1.10 shannon://sessions

List of active Claude Code sessions.

**URI Pattern:** `shannon://sessions`

**Response:**
```json
[
  {
    "id": "session_abc123def456",
    "model": "claude-3-sonnet",
    "state": "running",
    "created_at": "2025-11-13T12:00:00Z"
  }
]
```

---

## 2. Python API Reference

### Core Managers

#### 2.1 BinaryManager

Manages Claude Code binary discovery and validation.

##### Constructor

```python
class BinaryManager(config: BinaryManagerConfig)
```

**Parameters:**
- `config`: BinaryManagerConfig - Configuration for binary discovery

**Example:**
```python
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.utils.config import BinaryManagerConfig

config = BinaryManagerConfig(
    search_paths=[Path("/usr/local/bin")],
    nvm_check=True,
    update_check_interval=86400
)
manager = BinaryManager(config)
await manager.initialize()
```

##### Methods

**discover_binary(force: bool = False) -> BinaryInfo**

Discover Claude Code binary using multiple strategies.

```python
# Discover binary
binary = await binary_manager.discover_binary()
print(f"Found: {binary.path} (version {binary.version})")

# Force rediscovery
binary = await binary_manager.discover_binary(force=True)
```

**get_binary() -> Optional[BinaryInfo]**

Get cached binary or discover.

```python
binary = await binary_manager.get_binary()
if binary:
    print(f"Binary available: {binary.path}")
```

**invalidate_cache() -> None**

Invalidate binary cache.

```python
await binary_manager.invalidate_cache()
```

**check_for_updates() -> Optional[str]**

Check if binary has updates available.

```python
new_version = await binary_manager.check_for_updates()
if new_version:
    print(f"Update available: {new_version}")
```

**get_binary_stats() -> Dict[str, Any]**

Get binary usage statistics.

```python
stats = await binary_manager.get_binary_stats()
print(f"Total discoveries: {stats['total_discoveries']}")
```

---

#### 2.2 SessionManager

Manages Claude Code sessions and subprocess execution.

##### Constructor

```python
class SessionManager(
    config: SessionManagerConfig,
    binary_manager: BinaryManager
)
```

##### Methods

**create_session(prompt: str, model: str = "claude-3-sonnet", checkpoint_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Session**

Create a new Claude Code session.

```python
session = await session_manager.create_session(
    prompt="Build a REST API",
    model="claude-3-sonnet",
    context={"project_path": "/path/to/project"}
)
```

**send_message(session_id: str, content: str, timeout: Optional[float] = None) -> None**

Send message to active session.

```python
await session_manager.send_message(
    session_id="session_abc123",
    content="Add authentication",
    timeout=30.0
)
```

**cancel_session(session_id: str) -> None**

Cancel running session.

```python
await session_manager.cancel_session("session_abc123")
```

**get_session(session_id: str) -> Optional[Session]**

Get session by ID.

```python
session = await session_manager.get_session("session_abc123")
if session:
    print(f"State: {session.state.value}")
```

**list_sessions(state: Optional[SessionState] = None, limit: int = 100) -> List[Session]**

List sessions with optional filtering.

```python
# List all running sessions
running = await session_manager.list_sessions(
    state=SessionState.RUNNING,
    limit=10
)
```

**create_checkpoint(session_id: str) -> str**

Create checkpoint for session.

```python
checkpoint_id = await session_manager.create_checkpoint("session_abc123")
print(f"Checkpoint created: {checkpoint_id}")
```

---

#### 2.3 AgentManager

Manages AI agents and task assignments.

##### Constructor

```python
class AgentManager(config: AgentManagerConfig)
```

##### Methods

**register_agent(agent: Agent) -> None**

Register a new agent.

```python
agent = Agent(
    name="Custom Agent",
    description="Custom functionality",
    category=AgentCategory.SPECIALIZED,
    capabilities=[
        AgentCapability(
            name="custom_skill",
            description="Custom skill",
            expertise_level=8
        )
    ]
)
await agent_manager.register_agent(agent)
```

**get_agent(agent_id: str) -> Optional[Agent]**

Get agent by ID.

```python
agent = await agent_manager.get_agent("agent_architecture")
```

**list_agents(category: Optional[AgentCategory] = None, status: Optional[AgentStatus] = None, capability: Optional[str] = None) -> List[Agent]**

List agents with filtering.

```python
# Get all available core architecture agents
agents = await agent_manager.list_agents(
    category=AgentCategory.CORE_ARCHITECTURE,
    status=AgentStatus.AVAILABLE
)
```

**assign_task(request: TaskRequest) -> TaskAssignment**

Assign task to best available agent.

```python
request = TaskRequest(
    description="Design database schema",
    required_capabilities=["database_design", "data_persistence"],
    priority="high"
)
assignment = await agent_manager.assign_task(request)
```

**send_message(from_agent: str, to_agent: str, message_type: str, content: Dict[str, Any], priority: str = "medium") -> str**

Send message between agents.

```python
message_id = await agent_manager.send_message(
    from_agent="orchestrator",
    to_agent="agent_architecture",
    message_type="request",
    content={"task": "review design"},
    priority="high"
)
```

---

#### 2.4 MCPServerManager

Manages MCP server operations and protocol handling.

##### Constructor

```python
class MCPServerManager(config: MCPConfig)
```

##### Methods

**initialize() -> None**

Initialize MCP server manager.

**start() -> None**

Start MCP server operations.

**stop() -> None**

Stop MCP server operations.

**health_check() -> Dict[str, Any]**

Perform health check.

```python
health = await mcp_server.health_check()
print(f"Status: {health['status']}")
```

---

### Configuration API

#### ShannonConfig

Main configuration class using Pydantic for validation.

```python
from shannon_mcp.utils.config import (
    ShannonConfig, load_config, get_config
)

# Load configuration from files and environment
config = await load_config(
    config_paths=[Path("./config.yaml")],
    extra_config={"debug": True}
)

# Access configuration
print(f"Version: {config.version}")
print(f"Database path: {config.database.path}")
print(f"Log level: {config.logging.level}")
```

#### Configuration Classes

**DatabaseConfig**
```python
DatabaseConfig(
    path: Path = Path.home() / ".shannon-mcp" / "shannon.db",
    pool_size: int = 5,
    timeout: float = 30.0,
    journal_mode: str = "WAL",
    synchronous: str = "NORMAL"
)
```

**LoggingConfig**
```python
LoggingConfig(
    level: str = "INFO",
    format: str = "json",
    directory: Path = Path.home() / ".shannon-mcp" / "logs",
    max_size: int = 10 * 1024 * 1024,
    backup_count: int = 10,
    enable_sentry: bool = False,
    sentry_dsn: Optional[str] = None
)
```

**BinaryManagerConfig**
```python
BinaryManagerConfig(
    search_paths: List[Path] = [],
    nvm_check: bool = True,
    update_check_interval: int = 86400,
    cache_timeout: int = 3600,
    allowed_versions: Optional[List[str]] = None
)
```

**SessionManagerConfig**
```python
SessionManagerConfig(
    max_concurrent_sessions: int = 10,
    session_timeout: int = 3600,
    buffer_size: int = 1024 * 1024,
    stream_chunk_size: int = 8192,
    enable_metrics: bool = True,
    enable_replay: bool = False
)
```

**AgentManagerConfig**
```python
AgentManagerConfig(
    enable_default_agents: bool = True,
    github_org: Optional[str] = None,
    github_token: Optional[str] = None,
    max_concurrent_tasks: int = 20,
    task_timeout: int = 300,
    collaboration_enabled: bool = True,
    performance_tracking: bool = True
)
```

#### Configuration Functions

**load_config(config_paths: Optional[List[Union[str, Path]]] = None, extra_config: Optional[Dict[str, Any]] = None) -> ShannonConfig**

Load configuration from multiple sources.

```python
config = await load_config(
    config_paths=[Path("./config.yaml"), Path("./local.yaml")],
    extra_config={"debug": True}
)
```

**get_config() -> ShannonConfig**

Get current loaded configuration.

```python
config = get_config()
print(config.version)
```

---

### Logging API

#### setup_logging()

Setup comprehensive logging with rotation and structured output.

```python
from shannon_mcp.utils.logging import setup_logging, get_logger

# Setup logging
logging_config = setup_logging(
    app_name="shannon-mcp",
    log_level="INFO",
    log_dir=Path.home() / ".shannon-mcp" / "logs",
    enable_json=True,
    enable_sentry=False,
    enable_metrics=True
)

# Get logger
logger = get_logger("my-module")
logger.info("Application started", version="1.0.0", pid=os.getpid())
```

#### get_logger()

Get a structured logger instance.

```python
logger = get_logger("shannon-mcp.mymodule")
logger.info("processing_request", request_id="abc123", user_id="user1")
logger.error("request_failed", error="Connection timeout", exc_info=True)
```

#### MetricsLogger

Logger for performance metrics.

```python
from shannon_mcp.utils.logging import MetricsLogger

metrics = MetricsLogger(logger)
metrics.log_metric("api_requests", 100, tags={"endpoint": "/users"})
metrics.log_duration("query_time", 125.5, tags={"query": "SELECT"})
metrics.log_count("errors", 5, tags={"type": "timeout"})
```

#### log_function_call()

Decorator to log function calls with timing.

```python
from shannon_mcp.utils.logging import log_function_call

@log_function_call(logger)
async def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    # Process data
    return result
```

---

### Error Handling

#### Error Hierarchy

```
ShannonError (base)
├── SystemError
├── ConfigurationError
├── NetworkError
│   ├── ConnectionError
│   └── TimeoutError
├── DatabaseError
│   ├── DatabaseConnectionError
│   └── DatabaseIntegrityError
├── ValidationError
├── AuthenticationError
├── AuthorizationError
├── ExternalServiceError
├── StorageError
├── CacheError
├── StreamError
├── HookExecutionError
├── SecurityError
└── MCPError
```

#### Error Classes

**ShannonError**

Base exception for all Shannon MCP errors.

```python
from shannon_mcp.utils.errors import (
    ShannonError, ErrorContext, ErrorSeverity, ErrorCategory
)

# Raise error with context
raise ShannonError(
    message="Operation failed",
    context=ErrorContext(
        component="session_manager",
        operation="create_session",
        metadata={"session_id": "abc123"}
    )
)

# Convert to structured info
try:
    # operation
    pass
except ShannonError as e:
    error_info = e.to_info()
    print(f"Code: {error_info.code}")
    print(f"Severity: {error_info.severity.value}")
    print(f"Suggestions: {error_info.suggestions}")
```

**ValidationError**

Input validation errors.

```python
from shannon_mcp.utils.errors import ValidationError

raise ValidationError(
    field="email",
    value="invalid-email",
    constraint="must be valid email address"
)
```

#### Error Handling Utilities

**handle_errors() decorator**

```python
from shannon_mcp.utils.errors import handle_errors, SystemError

@handle_errors(SystemError, reraise=True, log_level=ErrorSeverity.ERROR)
async def risky_operation():
    # operation that might fail
    pass
```

**error_context() context manager**

```python
from shannon_mcp.utils.errors import error_context

with error_context("session_manager", "create_session", session_id="abc123"):
    # operations with automatic context tracking
    await create_session()
```

**ErrorRecovery**

Retry and circuit breaker patterns.

```python
from shannon_mcp.utils.errors import ErrorRecovery

# Exponential backoff
result = await ErrorRecovery.exponential_backoff(
    func=lambda: external_api_call(),
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exceptions=(NetworkError, TimeoutError)
)

# Circuit breaker
result = await ErrorRecovery.circuit_breaker(
    func=lambda: external_api_call(),
    failure_threshold=5,
    reset_timeout=60.0,
    exceptions=(NetworkError,)
)
```

---

### Notifications/Events

#### EventBus

Central event bus for pub/sub notifications.

```python
from shannon_mcp.utils.notifications import (
    EventBus, Event, EventCategory, EventPriority,
    get_event_bus, emit, subscribe
)

# Get global event bus
event_bus = get_event_bus()

# Subscribe to events
def handle_session_event(event: Event):
    print(f"Session event: {event.name}")
    print(f"Data: {event.data}")

subscription = subscribe(
    handler=handle_session_event,
    categories=EventCategory.SESSION,
    event_names=["session_created", "session_completed"],
    priority_min=EventPriority.NORMAL
)

# Emit events
await emit(
    name="session_created",
    category=EventCategory.SESSION,
    data={"session_id": "abc123", "model": "claude-3-sonnet"},
    priority=EventPriority.HIGH,
    source="session_manager"
)

# Unsubscribe
event_bus.unsubscribe(subscription)
```

#### Event Classes

**Event**

```python
Event(
    name: str,
    category: EventCategory,
    data: Dict[str, Any],
    timestamp: datetime = datetime.utcnow(),
    priority: EventPriority = EventPriority.NORMAL,
    source: Optional[str] = None,
    correlation_id: Optional[str] = None,
    metadata: Dict[str, Any] = {}
)
```

**EventCategory (Enum)**

- `SYSTEM`: System events
- `SESSION`: Session lifecycle events
- `AGENT`: Agent events
- `CHECKPOINT`: Checkpoint events
- `HOOKS`: Hook execution events
- `ANALYTICS`: Analytics events
- `BINARY`: Binary discovery events
- `MCP`: MCP protocol events
- `USER`: User-triggered events
- `ERROR`: Error events

**EventPriority (Enum)**

- `LOW`: Low priority (value: 1)
- `NORMAL`: Normal priority (value: 2)
- `HIGH`: High priority (value: 3)
- `CRITICAL`: Critical priority (value: 4)

#### Event Handler Decorator

```python
from shannon_mcp.utils.notifications import event_handler

class MyComponent:
    @event_handler(
        categories=EventCategory.SESSION,
        event_names="session_created",
        priority_min=EventPriority.NORMAL
    )
    async def on_session_created(self, event: Event):
        session_id = event.data.get("session_id")
        print(f"New session: {session_id}")
```

#### EventEmitter Mixin

```python
from shannon_mcp.utils.notifications import EventEmitter, EventCategory

class MyManager(EventEmitter):
    async def do_something(self):
        # Do work

        # Emit event
        await self.emit_event(
            name="work_completed",
            category=EventCategory.SYSTEM,
            data={"result": "success"}
        )
```

#### Wait for Event

```python
# Wait for specific event
event = await event_bus.wait_for(
    event_name="session_completed",
    category=EventCategory.SESSION,
    timeout=30.0,
    filter_func=lambda e: e.data.get("session_id") == "abc123"
)
```

---

## 3. Advanced Features APIs

### Checkpoint System

Git-like versioning and checkpoint management.

#### CheckpointManager

```python
from shannon_mcp.checkpoint import CheckpointManager, Checkpoint

# Initialize
checkpoint_manager = CheckpointManager(
    storage_path=Path.home() / ".shannon-mcp" / "checkpoints"
)
await checkpoint_manager.initialize()
```

#### Create Checkpoint

```python
# Create checkpoint with files
files = {
    "src/main.py": b"print('hello')",
    "src/config.py": b"DEBUG=True"
}

checkpoint = await checkpoint_manager.create_checkpoint(
    files=files,
    message="Initial implementation",
    author="developer",
    tags=["v1.0", "stable"]
)
print(f"Checkpoint created: {checkpoint.metadata.checkpoint_id}")
```

#### List Checkpoints

```python
# List all checkpoints
checkpoints = await checkpoint_manager.list_checkpoints(
    limit=10,
    since=datetime(2025, 1, 1),
    tags=["stable"]
)

for cp in checkpoints:
    print(f"{cp.metadata.checkpoint_id}: {cp.metadata.message}")
```

#### Get Checkpoint Files

```python
# Get all files from checkpoint
files = await checkpoint_manager.get_checkpoint_files(
    checkpoint_id="abc123def456"
)

# Get specific files
files = await checkpoint_manager.get_checkpoint_files(
    checkpoint_id="abc123def456",
    paths=["src/main.py", "src/config.py"]
)
```

#### Diff Checkpoints

```python
# Compare checkpoints
diff = await checkpoint_manager.diff_checkpoints(
    from_id="checkpoint1",
    to_id="checkpoint2"
)

print(f"Added: {diff['added']}")
print(f"Removed: {diff['removed']}")
print(f"Modified: {diff['modified']}")
```

#### Restore Checkpoint

```python
# Restore checkpoint
files = await checkpoint_manager.restore_checkpoint("abc123def456")
# Files now contains all files from checkpoint
```

#### References

```python
# Create reference (like git branch)
await checkpoint_manager.create_ref("main", "abc123def456")
await checkpoint_manager.create_ref("stable", "xyz789abc012")

# Get reference
checkpoint_id = await checkpoint_manager.get_ref("main")

# List all references
refs = await checkpoint_manager.list_refs()

# Delete reference
await checkpoint_manager.delete_ref("old-branch")
```

#### Garbage Collection

```python
# Clean up unreferenced content
objects_removed, bytes_freed = await checkpoint_manager.gc()
print(f"Removed {objects_removed} objects, freed {bytes_freed} bytes")
```

---

### Hooks Framework

Event-driven automation with hooks.

#### HookEngine

```python
from shannon_mcp.hooks import HookEngine, HookRegistry, HookConfig

# Initialize
registry = HookRegistry(Path.home() / ".shannon-mcp" / "hooks")
engine = HookEngine(
    registry=registry,
    custom_functions={
        "my_function": my_custom_function
    }
)
await engine.initialize()
```

#### Define Hook

```python
from shannon_mcp.hooks import (
    HookConfig, HookTrigger, HookAction, HookActionType
)

# Define hook configuration
hook = HookConfig(
    name="on-session-start",
    description="Run tests when session starts",
    trigger=HookTrigger.SESSION_START,
    actions=[
        HookAction(
            type=HookActionType.COMMAND,
            command="pytest tests/",
            config={"working_dir": "/path/to/project"}
        ),
        HookAction(
            type=HookActionType.NOTIFICATION,
            config={
                "title": "Tests Started",
                "message": "Running test suite"
            }
        )
    ],
    conditions={"project_type": "python"},
    timeout=300,
    retry_count=2,
    retry_delay=5
)

# Register hook
await registry.register_hook(hook)
```

#### Trigger Hooks

```python
# Trigger hooks for event
results = await engine.trigger(
    trigger=HookTrigger.SESSION_START,
    context={
        "session_id": "abc123",
        "project_type": "python",
        "project_path": "/path/to/project"
    }
)

# Check results
for result in results:
    if result.success:
        print(f"✓ {result.hook_name} completed in {result.duration}s")
    else:
        print(f"✗ {result.hook_name} failed: {result.error}")
```

#### Hook Action Types

**COMMAND** - Execute shell command
```python
HookAction(
    type=HookActionType.COMMAND,
    command="npm test",
    template="${command} --verbose",  # Template substitution
    config={"working_dir": "/path"}
)
```

**SCRIPT** - Execute script file
```python
HookAction(
    type=HookActionType.SCRIPT,
    script_path=Path("./scripts/deploy.sh"),
    config={"args": ["--prod"]}
)
```

**WEBHOOK** - HTTP webhook call
```python
HookAction(
    type=HookActionType.WEBHOOK,
    url="https://api.example.com/webhook",
    config={
        "method": "POST",
        "headers": {"Authorization": "Bearer token"}
    }
)
```

**FUNCTION** - Custom function
```python
HookAction(
    type=HookActionType.FUNCTION,
    function_name="my_function",
    config={"param": "value"}
)
```

**NOTIFICATION** - Send notification
```python
HookAction(
    type=HookActionType.NOTIFICATION,
    config={
        "title": "Hook Triggered",
        "message": "Custom message",
        "type": "info"
    }
)
```

**LOG** - Log message
```python
HookAction(
    type=HookActionType.LOG,
    config={
        "level": "info",
        "message": "Hook executed"
    }
)
```

#### Hook Triggers

- `SESSION_START`: When session starts
- `SESSION_END`: When session ends
- `CHECKPOINT_CREATED`: When checkpoint is created
- `TASK_ASSIGNED`: When task is assigned to agent
- `ERROR_OCCURRED`: When error occurs
- `TOOL_EXECUTED`: When MCP tool is executed
- `FILE_CHANGED`: When file changes (with file watching)

---

### Analytics API

Usage analytics and metrics collection.

#### MetricsWriter

```python
from shannon_mcp.analytics import JSONLWriter, MetricsWriter

# Initialize writer
jsonl_writer = JSONLWriter(
    base_path=Path.home() / ".shannon-mcp" / "metrics",
    max_file_size=100 * 1024 * 1024,  # 100MB
    max_files=10,
    compress_old=True,
    buffer_size=100
)

await jsonl_writer.initialize()
metrics = MetricsWriter(jsonl_writer)
```

#### Track Metrics

```python
# Track session start
await metrics.track_session_start(
    session_id="abc123",
    user_id="user1",
    project_path="/path/to/project",
    model="claude-3-sonnet"
)

# Track session end
await metrics.track_session_end(
    session_id="abc123",
    user_id="user1",
    duration_seconds=125.5,
    token_count=1500
)

# Track tool use
await metrics.track_tool_use(
    session_id="abc123",
    tool_name="find_claude_binary",
    success=True,
    duration_ms=45.2
)

# Track error
await metrics.track_error(
    session_id="abc123",
    error_type="ValidationError",
    error_message="Invalid input",
    stack_trace=traceback.format_exc()
)

# Track performance
await metrics.track_performance(
    operation="database_query",
    duration_ms=12.5,
    success=True,
    session_id="abc123"
)
```

#### MetricEntry

```python
from shannon_mcp.analytics import MetricEntry, MetricType

entry = MetricEntry(
    id=str(uuid.uuid4()),
    timestamp=datetime.now(timezone.utc),
    type=MetricType.SESSION_START,
    session_id="abc123",
    user_id="user1",
    data={
        "model": "claude-3-sonnet",
        "project_path": "/path"
    },
    metadata={}
)

await jsonl_writer.write(entry)
```

#### Flush Metrics

```python
# Force flush buffer to disk
await jsonl_writer.flush()

# Close writer (flushes automatically)
await jsonl_writer.close()
```

---

### Process Registry

System-wide process tracking and management.

#### Registry Operations

```python
from shannon_mcp.registry import (
    ProcessRegistry, ProcessInfo, ProcessState
)

# Initialize registry
registry = ProcessRegistry(
    storage_path=Path.home() / ".shannon-mcp" / "registry"
)
await registry.initialize()

# Register process
process_info = ProcessInfo(
    pid=os.getpid(),
    name="shannon-mcp-server",
    command_line=" ".join(sys.argv),
    state=ProcessState.RUNNING,
    started_at=datetime.utcnow(),
    metadata={"version": "0.1.0"}
)
await registry.register_process(process_info)

# Update process state
await registry.update_state(os.getpid(), ProcessState.STOPPING)

# Get process info
info = await registry.get_process(os.getpid())

# List all processes
processes = await registry.list_processes(
    state=ProcessState.RUNNING,
    name_pattern="shannon-*"
)

# Unregister process
await registry.unregister_process(os.getpid())
```

#### Process Monitoring

```python
# Monitor process health
health = await registry.check_health(os.getpid())
if not health["alive"]:
    print("Process not responding")

# Clean up stale processes
removed = await registry.cleanup_stale_processes(timeout_seconds=300)
print(f"Removed {removed} stale processes")
```

---

## 4. Data Models

### BinaryInfo

Information about Claude Code binary.

```python
@dataclass
class BinaryInfo:
    path: Path
    version: str
    build_date: Optional[datetime] = None
    features: List[str] = field(default_factory=list)
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    discovery_method: str = "unknown"
    is_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    version_string: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    last_verified: Optional[datetime] = None
    update_available: bool = False
    latest_version: Optional[str] = None
```

### Session

Claude Code session.

```python
@dataclass
class Session:
    id: str
    binary: BinaryInfo
    model: str = "claude-3-sonnet"
    state: SessionState = SessionState.CREATED
    process: Optional[asyncio.subprocess.Process] = None
    messages: List[SessionMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    checkpoint_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
```

### SessionMessage

```python
@dataclass
class SessionMessage:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### SessionMetrics

```python
@dataclass
class SessionMetrics:
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    tokens_input: int = 0
    tokens_output: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors_count: int = 0
    checkpoints_created: int = 0
    stream_bytes_received: int = 0

    @property
    def duration(self) -> Optional[timedelta]

    @property
    def tokens_per_second(self) -> float
```

### Agent

AI Agent model.

```python
@dataclass
class Agent:
    id: str
    name: str
    description: str
    category: AgentCategory
    capabilities: List[AgentCapability] = field(default_factory=list)
    status: AgentStatus = AgentStatus.AVAILABLE
    github_url: Optional[str] = None
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

### AgentCapability

```python
@dataclass
class AgentCapability:
    name: str
    description: str
    expertise_level: int  # 1-10
    tools: List[str] = field(default_factory=list)
```

### AgentMetrics

```python
@dataclass
class AgentMetrics:
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_task_time: float = 0.0
    success_rate: float = 0.0
    last_active: Optional[datetime] = None

    def update_metrics(self, task_success: bool, execution_time: float)
```

### TaskRequest

```python
@dataclass
class TaskRequest:
    id: str
    description: str
    required_capabilities: List[str]
    priority: str = "medium"
    context: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
```

### TaskAssignment

```python
@dataclass
class TaskAssignment:
    task_id: str
    agent_id: str
    score: float  # Suitability score 0-1
    estimated_duration: Optional[int] = None  # seconds
    confidence: float = 0.5  # Confidence level 0-1
```

### CheckpointMetadata

```python
@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    parent_id: Optional[str]
    created_at: datetime
    message: str
    author: str
    tags: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
```

### Checkpoint

```python
@dataclass
class Checkpoint:
    metadata: CheckpointMetadata
    files: Dict[str, str]  # path -> content hash
```

### MetricEntry

```python
@dataclass
class MetricEntry:
    id: str
    timestamp: datetime
    type: MetricType
    session_id: Optional[str]
    user_id: Optional[str]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
```

---

## 5. Type Definitions

### Enums

#### SessionState

```python
class SessionState(Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
```

#### AgentCategory

```python
class AgentCategory(Enum):
    CORE_ARCHITECTURE = "core_architecture"
    INFRASTRUCTURE = "infrastructure"
    QUALITY_SECURITY = "quality_security"
    SPECIALIZED = "specialized"
```

#### AgentStatus

```python
class AgentStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"
```

#### ExecutionStatus

```python
class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

#### ErrorSeverity

```python
class ErrorSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"
```

#### ErrorCategory

```python
class ErrorCategory(Enum):
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    USER_INPUT = "user_input"
    INTERNAL = "internal"
    UNKNOWN = "unknown"
```

#### EventCategory

```python
class EventCategory(Enum):
    SYSTEM = "system"
    SESSION = "session"
    AGENT = "agent"
    CHECKPOINT = "checkpoint"
    HOOKS = "hooks"
    ANALYTICS = "analytics"
    BINARY = "binary"
    MCP = "mcp"
    USER = "user"
    ERROR = "error"
```

#### EventPriority

```python
class EventPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
```

#### MetricType

```python
class MetricType(str, Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TOOL_USE = "tool_use"
    AGENT_EXECUTION = "agent_execution"
    CHECKPOINT_CREATED = "checkpoint_created"
    HOOK_TRIGGERED = "hook_triggered"
    COMMAND_EXECUTED = "command_executed"
    ERROR_OCCURRED = "error_occurred"
    TOKEN_USAGE = "token_usage"
    PERFORMANCE = "performance"
```

#### HookTrigger

```python
class HookTrigger(Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    CHECKPOINT_CREATED = "checkpoint_created"
    TASK_ASSIGNED = "task_assigned"
    ERROR_OCCURRED = "error_occurred"
    TOOL_EXECUTED = "tool_executed"
    FILE_CHANGED = "file_changed"
```

#### HookActionType

```python
class HookActionType(Enum):
    COMMAND = "command"
    SCRIPT = "script"
    WEBHOOK = "webhook"
    FUNCTION = "function"
    NOTIFICATION = "notification"
    LOG = "log"
    TRANSFORM = "transform"
```

---

## 6. Constants

### Default Paths

```python
DEFAULT_CONFIG_PATH = Path.home() / ".shannon-mcp" / "config.yaml"
DEFAULT_DATABASE_PATH = Path.home() / ".shannon-mcp" / "shannon.db"
DEFAULT_LOG_PATH = Path.home() / ".shannon-mcp" / "logs"
DEFAULT_CHECKPOINT_PATH = Path.home() / ".shannon-mcp" / "checkpoints"
DEFAULT_METRICS_PATH = Path.home() / ".shannon-mcp" / "metrics"
```

### Timeouts

```python
DEFAULT_SESSION_TIMEOUT = 3600  # 1 hour
DEFAULT_COMMAND_TIMEOUT = 300   # 5 minutes
DEFAULT_HOOK_TIMEOUT = 30       # 30 seconds
DEFAULT_BINARY_CACHE_TIMEOUT = 3600  # 1 hour
```

### Limits

```python
MAX_CONCURRENT_SESSIONS = 10
MAX_CONCURRENT_TASKS = 20
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_BUFFER_SIZE = 1024 * 1024        # 1MB
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024 # 10MB
MAX_METRICS_FILE_SIZE = 100 * 1024 * 1024  # 100MB
```

### Version

```python
SHANNON_VERSION = "0.1.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
MIN_PYTHON_VERSION = "3.11"
```

---

## Complete Example

Here's a complete example showing various APIs working together:

```python
import asyncio
from pathlib import Path
from shannon_mcp.utils.config import load_config
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.managers.session import SessionManager, SessionState
from shannon_mcp.managers.agent import AgentManager, TaskRequest
from shannon_mcp.checkpoint import CheckpointManager
from shannon_mcp.hooks import HookEngine, HookRegistry, HookConfig, HookTrigger
from shannon_mcp.analytics import JSONLWriter, MetricsWriter
from shannon_mcp.utils.logging import setup_logging, get_logger
from shannon_mcp.utils.notifications import get_event_bus, subscribe, EventCategory

async def main():
    # Setup logging
    setup_logging(app_name="my-app", log_level="INFO")
    logger = get_logger("my-app")

    # Load configuration
    config = await load_config()
    logger.info("Configuration loaded", version=config.version)

    # Initialize binary manager
    binary_manager = BinaryManager(config.binary_manager)
    await binary_manager.initialize()
    binary = await binary_manager.discover_binary()
    logger.info("Binary discovered", path=str(binary.path), version=binary.version)

    # Initialize session manager
    session_manager = SessionManager(config.session_manager, binary_manager)
    await session_manager.initialize()

    # Initialize agent manager
    agent_manager = AgentManager(config.agent_manager)
    await agent_manager.initialize()

    # Initialize checkpoint manager
    checkpoint_manager = CheckpointManager(
        Path.home() / ".shannon-mcp" / "checkpoints"
    )
    await checkpoint_manager.initialize()

    # Initialize hooks
    hook_registry = HookRegistry(Path.home() / ".shannon-mcp" / "hooks")
    hook_engine = HookEngine(hook_registry)
    await hook_engine.initialize()

    # Initialize analytics
    metrics_writer = JSONLWriter(Path.home() / ".shannon-mcp" / "metrics")
    await metrics_writer.initialize()
    metrics = MetricsWriter(metrics_writer)

    # Subscribe to events
    event_bus = get_event_bus()

    def on_session_created(event):
        logger.info("Session created event", session_id=event.data["session_id"])

    subscribe(
        handler=on_session_created,
        categories=EventCategory.SESSION,
        event_names="session_created"
    )

    # Create session
    session = await session_manager.create_session(
        prompt="Build a REST API with authentication",
        model="claude-3-sonnet",
        context={"project_path": "/path/to/project"}
    )
    logger.info("Session created", session_id=session.id)

    # Track metrics
    await metrics.track_session_start(
        session_id=session.id,
        model="claude-3-sonnet",
        project_path="/path/to/project"
    )

    # Assign task to agent
    task_request = TaskRequest(
        description="Design REST API architecture",
        required_capabilities=["system_design", "api_design"],
        priority="high",
        context={"session_id": session.id}
    )
    assignment = await agent_manager.assign_task(task_request)
    logger.info("Task assigned", agent=assignment.agent_id, score=assignment.score)

    # Send message
    await session_manager.send_message(
        session_id=session.id,
        content="Add JWT authentication",
        timeout=30.0
    )

    # Create checkpoint
    checkpoint = await checkpoint_manager.create_checkpoint(
        files={"main.py": b"# API code"},
        message="Initial API structure",
        author="developer",
        tags=["v0.1"]
    )
    logger.info("Checkpoint created", checkpoint_id=checkpoint.metadata.checkpoint_id)

    # Trigger hooks
    await hook_engine.trigger(
        trigger=HookTrigger.SESSION_START,
        context={"session_id": session.id}
    )

    # Wait for session to complete (simulated)
    await asyncio.sleep(5)

    # Track session end
    await metrics.track_session_end(
        session_id=session.id,
        duration_seconds=5.0,
        token_count=1500
    )

    # List sessions
    sessions = await session_manager.list_sessions(state=SessionState.COMPLETED)
    logger.info("Total completed sessions", count=len(sessions))

    # Cleanup
    await metrics_writer.close()
    await session_manager.stop()
    await agent_manager.stop()

    logger.info("Application completed")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## See Also

- [README.md](./README.md) - Project overview and getting started
- [INSTALLATION.md](./INSTALLATION.md) - Installation instructions
- [USAGE.md](./USAGE.md) - Usage examples and tutorials
- [TESTING.md](./TESTING.md) - Testing guide
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment instructions

---

**Questions or Issues?**

- GitHub Issues: https://github.com/krzemienski/shannon-mcp/issues
- Documentation: https://docs.shannon-mcp.com
- Discussions: https://github.com/krzemienski/shannon-mcp/discussions
