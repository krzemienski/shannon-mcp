# Shannon MCP Architecture

## System Architecture Overview

Shannon MCP implements a comprehensive Model Context Protocol server using FastMCP, providing programmatic access to Claude Code CLI through a multi-layered architecture.

## Core Design Principles

### 1. **Separation of Concerns**
- Each manager handles a specific domain (binary, session, agent, etc.)
- Clear interfaces between components
- Minimal coupling between layers

### 2. **Asynchronous by Design**
- All I/O operations are async
- Non-blocking stream processing
- Concurrent session handling

### 3. **Fault Tolerance**
- Graceful error handling
- Process isolation
- Automatic recovery mechanisms

### 4. **Performance First**
- Sub-10ms response times
- Efficient resource utilization
- Stream processing with backpressure

## Component Architecture

### FastMCP Server Core

```python
# server_fastmcp.py structure
class ShannonMCP:
    """Main MCP server using FastMCP framework"""
    
    def __init__(self):
        self.binary_manager = BinaryManager()
        self.session_manager = SessionManager()
        self.agent_manager = AgentManager()
        self.checkpoint_system = CheckpointSystem()
        self.analytics_engine = AnalyticsEngine()
        self.hook_manager = HookManager()
        self.process_registry = ProcessRegistry()
```

### Manager Layer

Each manager encapsulates specific functionality:

#### Binary Manager
- **Purpose**: Discover and validate Claude Code installations
- **Key Features**:
  - Auto-discovery across multiple paths
  - Version validation
  - Capability checking
  - Binary caching

```python
class BinaryManager:
    async def find_binary(self) -> BinaryInfo
    async def validate_binary(self, path: str) -> bool
    async def get_capabilities(self, binary: str) -> List[str]
```

#### Session Manager
- **Purpose**: Manage Claude Code process lifecycle
- **Key Features**:
  - Process spawning with proper isolation
  - JSONL stream management
  - State tracking
  - Resource cleanup

```python
class SessionManager:
    async def create_session(self, config: SessionConfig) -> Session
    async def send_message(self, session_id: str, message: str) -> Response
    async def stream_output(self, session_id: str) -> AsyncIterator[str]
    async def cancel_session(self, session_id: str) -> None
```

#### Agent Manager
- **Purpose**: Orchestrate AI agents for specialized tasks
- **Key Features**:
  - 26 specialized agents
  - Task routing
  - Collaborative execution
  - Performance tracking

```python
class AgentManager:
    async def list_agents(self) -> List[Agent]
    async def assign_task(self, agent_id: str, task: Task) -> TaskResult
    async def get_agent_status(self, agent_id: str) -> AgentStatus
```

### Storage Layer

#### SQLite Database
- **Schema**: Optimized for MCP operations
- **Tables**:
  - `sessions`: Session metadata and state
  - `messages`: Message history
  - `checkpoints`: Version snapshots
  - `agents`: Agent registry
  - `analytics`: Usage metrics
  - `hooks`: Event configurations

#### Content-Addressable Storage (CAS)
- **Purpose**: Deduplicated content storage
- **Implementation**: SHA-256 based addressing
- **Compression**: zstandard for efficiency

### Streaming Layer

#### JSONL Processor
- **Purpose**: Handle Claude Code's JSONL protocol
- **Features**:
  - Stream parsing
  - Message framing
  - Error recovery
  - Buffering

#### Backpressure Controller
- **Purpose**: Prevent stream overflow
- **Implementation**:
  - Adaptive buffering
  - Consumer feedback
  - Rate limiting

## Data Flow

### Session Creation Flow

```
Client Request → FastMCP Server → Binary Manager (validate)
                                ↓
                          Session Manager (spawn process)
                                ↓
                          Database (store metadata)
                                ↓
                          Process Registry (track PID)
                                ↓
                          Response to Client
```

### Message Processing Flow

```
Client Message → FastMCP Server → Session Manager
                                ↓
                          JSONL Processor (format)
                                ↓
                          Claude Process (stdin)
                                ↓
                          Stream Output (stdout)
                                ↓
                          JSONL Processor (parse)
                                ↓
                          Backpressure Controller
                                ↓
                          Client Response Stream
```

### Agent Task Flow

```
Task Request → Agent Manager → Task Queue
                            ↓
                      Agent Selection
                            ↓
                      Task Execution
                            ↓
                      Result Processing
                            ↓
                      Analytics Update
                            ↓
                      Client Response
```

## Communication Protocols

### MCP Protocol (Client ↔ Server)
- **Transport**: STDIO (stdin/stdout)
- **Format**: JSON-RPC 2.0
- **Features**: Request/response, notifications, batch

### JSONL Protocol (Server ↔ Claude)
- **Transport**: Process pipes
- **Format**: Newline-delimited JSON
- **Streaming**: Bidirectional, real-time

## Security Architecture

### Process Isolation
- Each Claude session runs in isolated process
- No shared memory between sessions
- Clean environment variables

### Command Validation
- Whitelist allowed commands
- Pattern matching for dangerous operations
- Sandboxed execution environment

### Access Control
- File system restrictions
- Network access limitations
- Resource quotas per session

## Performance Architecture

### Caching Strategy
- Binary discovery cache (TTL: 1 hour)
- Session metadata cache
- Agent capability cache
- Analytics aggregation cache

### Concurrency Model
- Async/await throughout
- Process pool for sessions
- Thread pool for I/O operations
- Event loop optimization

### Resource Management
- Session limits (default: 10 concurrent)
- Memory monitoring
- CPU throttling
- Automatic cleanup

## Scalability Considerations

### Horizontal Scaling
- Stateless server design
- External session storage
- Load balancer compatible
- Distributed process registry

### Vertical Scaling
- Efficient memory usage
- Process pooling
- Connection pooling
- Optimized queries

## Error Handling

### Error Categories
1. **Binary Errors**: Discovery, validation failures
2. **Session Errors**: Spawn, communication failures
3. **Stream Errors**: Protocol, parsing issues
4. **Storage Errors**: Database, file system
5. **Network Errors**: Timeout, connection issues

### Recovery Strategies
- Automatic retry with backoff
- Graceful degradation
- Error context preservation
- User-friendly error messages

## Monitoring and Observability

### Metrics Collection
- Request/response times
- Session durations
- Error rates
- Resource usage
- Agent performance

### Logging Architecture
- Structured logging (JSON)
- Log levels and filtering
- Correlation IDs
- Performance tracing

### Health Checks
- Binary availability
- Database connectivity
- Process health
- Resource availability

## Extension Points

### Plugin System
- Hook registration
- Custom agents
- Storage backends
- Protocol handlers

### Configuration
- Environment variables
- Configuration files
- Runtime updates
- Feature flags

## Future Architecture Considerations

### Planned Enhancements
1. **Distributed Architecture**: Multi-node support
2. **Cloud Native**: Kubernetes deployment
3. **Advanced Caching**: Redis integration
4. **Message Queue**: RabbitMQ/Kafka support
5. **GraphQL API**: Alternative interface

### Performance Goals
- < 5ms response time
- 10,000 concurrent sessions
- 99.99% uptime
- Zero data loss

## Architecture Decision Records (ADRs)

### ADR-001: FastMCP Framework
**Decision**: Use FastMCP for MCP server implementation
**Rationale**: High performance, built-in MCP support, async design

### ADR-002: SQLite Database
**Decision**: Use SQLite for metadata storage
**Rationale**: Embedded, reliable, sufficient for use case

### ADR-003: Process Isolation
**Decision**: Run each Claude session in separate process
**Rationale**: Security, stability, resource isolation

### ADR-004: JSONL Streaming
**Decision**: Use JSONL for Claude communication
**Rationale**: Native Claude format, streaming support

### ADR-005: Content-Addressable Storage
**Decision**: Implement CAS for content deduplication
**Rationale**: Storage efficiency, data integrity