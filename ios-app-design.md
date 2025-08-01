# Shannon MCP iOS Testing Application - Comprehensive Design Document

## 1. Executive Summary

This document outlines the design and architecture for a comprehensive iOS SwiftUI application that will test and demonstrate all functionality of the Shannon MCP server. The app will be containerized using Docker for deployment on Linux machines and will feature real-time logging, bidirectional streaming, and complete testing coverage of all MCP server capabilities.

## 2. Shannon MCP Server Analysis

### 2.1 Core MCP Tools

The Shannon MCP server exposes 7 primary tools through the MCP protocol:

1. **find_claude_binary**
   - Purpose: Discover Claude Code installation on the system
   - Input: None
   - Output: Binary path, version, discovery method

2. **create_session**
   - Purpose: Create a new Claude Code session
   - Input: prompt (required), model, checkpoint_id, context
   - Output: Session ID, state, creation timestamp

3. **send_message**
   - Purpose: Send a message to an active session
   - Input: session_id, content, timeout
   - Output: Response content, metrics

4. **cancel_session**
   - Purpose: Cancel a running session
   - Input: session_id
   - Output: Cancellation status

5. **list_sessions**
   - Purpose: List active sessions
   - Input: state filter, limit
   - Output: Array of session objects

6. **list_agents**
   - Purpose: List available AI agents
   - Input: category, status, capability filters
   - Output: Array of agent objects

7. **assign_task**
   - Purpose: Assign a task to an AI agent
   - Input: description, required_capabilities, priority, context, timeout
   - Output: Task assignment details

### 2.2 MCP Resources

The server provides 3 resources:

1. **shannon://config** - Current configuration settings (JSON)
2. **shannon://agents** - List of AI agents (JSON)
3. **shannon://sessions** - Active Claude Code sessions (JSON)

### 2.3 Additional Components

1. **Transport Layers**
   - STDIO Transport (direct stdin/stdout)
   - Process STDIO Transport (subprocess communication)
   - SSE Transport (Server-Sent Events with HTTP POST)
   - Transport Manager (connection pooling and routing)

2. **Streaming System**
   - JSONL Parser for real-time message parsing
   - Stream Buffer with backpressure handling
   - Stream Processor for message routing
   - Metrics collection (tokens, performance)

3. **Checkpoint System**
   - Content-Addressable Storage (CAS) with SHA-256
   - Zstd compression
   - Git-like checkpoint creation and branching
   - Timeline tracking and diff capabilities

4. **Analytics Engine**
   - JSONL writer with rotation
   - Multi-dimensional aggregation
   - Multiple export formats (JSON, CSV, Parquet, Excel)
   - Real-time metrics streaming

5. **Agent System**
   - 26 specialized AI agents
   - Task assignment and routing
   - Performance tracking
   - Collaboration tracking

## 3. iOS Application Architecture

### 3.1 Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        iOS SwiftUI App                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   UI Layer      │  │  View Models │  │  Services       │   │
│  │  (SwiftUI)      │  │  (Combine)   │  │  (Networking)   │   │
│  └────────┬────────┘  └──────┬───────┘  └────────┬────────┘   │
│           │                   │                    │             │
│           └───────────────────┴────────────────────┘             │
│                              │                                   │
├──────────────────────────────┼───────────────────────────────────┤
│                    Communication Layer                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │WebSocket │ │   SSE    │ │   HTTP   │ │  JSONL   │  │    │
│  │  │ Client   │ │  Client  │ │  Client  │ │  Parser  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼───────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Docker Container    │
                    │   Shannon MCP Server  │
                    └───────────────────────┘
```

### 3.2 Key Components

#### 3.2.1 Networking Layer
```swift
// MCPClient.swift
protocol MCPClientProtocol {
    func connect() async throws
    func callTool(name: String, arguments: [String: Any]) async throws -> MCPResponse
    func readResource(uri: String) async throws -> Data
    func streamMessages() -> AsyncStream<MCPMessage>
}

// Transport implementations
class SSETransport: MCPTransport { }
class WebSocketTransport: MCPTransport { }
class HTTPTransport: MCPTransport { }
```

#### 3.2.2 Data Models
```swift
// Core MCP models
struct MCPTool: Codable {
    let name: String
    let description: String
    let inputSchema: JSONSchema
}

struct MCPSession: Codable {
    let id: String
    let state: SessionState
    let createdAt: Date
    let messages: [MCPMessage]
}

struct MCPAgent: Codable {
    let id: String
    let name: String
    let category: String
    let capabilities: [String]
    let status: AgentStatus
}
```

#### 3.2.3 View Models
```swift
// SessionViewModel.swift
@MainActor
class SessionViewModel: ObservableObject {
    @Published var sessions: [MCPSession] = []
    @Published var activeSession: MCPSession?
    @Published var isStreaming: Bool = false
    @Published var logs: [LogEntry] = []
    
    private let mcpClient: MCPClientProtocol
    private var streamTask: Task<Void, Never>?
    
    func createSession(prompt: String) async { }
    func sendMessage(content: String) async { }
    func cancelSession() async { }
}
```

### 3.3 UI Screen Design

#### 3.3.1 Main Dashboard
- Server connection status indicator
- Quick stats (active sessions, agents, checkpoints)
- Navigation to all testing sections
- Real-time log viewer

#### 3.3.2 Binary Discovery Screen
- Test `find_claude_binary` tool
- Display discovered binary information
- Version details and discovery method
- Manual binary path configuration

#### 3.3.3 Session Management Screen
- Create new sessions with different prompts
- Active session list with states
- Real-time message streaming view
- Session metrics and token counts
- Cancel/restore session capabilities

#### 3.3.4 Agent Testing Screen
- List all 26 AI agents
- Filter by category/capability
- Assign tasks to agents
- Track task execution progress
- View agent collaboration graph

#### 3.3.5 Checkpoint System Screen
- Create/restore checkpoints
- Visualize checkpoint timeline
- Diff between checkpoints
- Branch management UI
- Storage statistics

#### 3.3.6 Analytics Dashboard
- Real-time metrics visualization
- Token usage graphs
- Performance metrics
- Export functionality
- Custom time range selection

#### 3.3.7 Streaming Test Screen
- JSONL message viewer
- Backpressure simulation
- Error injection testing
- Throughput metrics
- Message type filtering

#### 3.3.8 Configuration Screen
- View/edit MCP server config
- Transport selection (SSE/WebSocket/HTTP)
- Connection parameters
- Debug options
- Log level settings

## 4. Docker Containerization Strategy

### 4.1 Dockerfile for MCP Server
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY src/ ./src/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Expose MCP server ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the MCP server
CMD ["poetry", "run", "shannon-mcp"]
```

### 4.2 Docker Compose Configuration
```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    container_name: shannon-mcp-server
    ports:
      - "8080:8080"  # HTTP/SSE endpoint
      - "8081:8081"  # WebSocket endpoint
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - MCP_LOG_LEVEL=DEBUG
      - MCP_TRANSPORT=sse
      - MCP_ENABLE_ANALYTICS=true
    restart: unless-stopped
    networks:
      - mcp-network

  nginx:
    image: nginx:alpine
    container_name: mcp-nginx
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - mcp-server
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

## 5. Real-Time Features Implementation

### 5.1 Bidirectional Streaming

#### 5.1.1 iOS Implementation
```swift
class StreamingManager {
    private var sseClient: EventSource?
    private var messageSubject = PassthroughSubject<MCPMessage, Never>()
    
    func connectSSE(url: URL) {
        sseClient = EventSource(url: url)
        
        sseClient?.onMessage { [weak self] (id, event, data) in
            if let message = try? JSONDecoder().decode(MCPMessage.self, from: data) {
                self?.messageSubject.send(message)
            }
        }
    }
    
    func sendMessage(_ message: MCPMessage) async throws {
        // POST to MCP server
    }
}
```

#### 5.1.2 JSONL Parsing
```swift
class JSONLParser {
    func parse(_ data: Data) -> AsyncStream<MCPMessage> {
        AsyncStream { continuation in
            let lines = String(data: data, encoding: .utf8)?.split(separator: "\n") ?? []
            
            for line in lines {
                if let data = line.data(using: .utf8),
                   let message = try? JSONDecoder().decode(MCPMessage.self, from: data) {
                    continuation.yield(message)
                }
            }
            
            continuation.finish()
        }
    }
}
```

### 5.2 Real-Time Logging

```swift
class LoggingService: ObservableObject {
    @Published var logs: [LogEntry] = []
    private let maxLogs = 1000
    
    func log(_ level: LogLevel, _ message: String, metadata: [String: Any]? = nil) {
        let entry = LogEntry(
            timestamp: Date(),
            level: level,
            message: message,
            metadata: metadata
        )
        
        DispatchQueue.main.async {
            self.logs.append(entry)
            if self.logs.count > self.maxLogs {
                self.logs.removeFirst()
            }
        }
    }
}
```

## 6. Testing Strategy

### 6.1 Unit Tests
- Test each MCP tool independently
- Mock server responses
- Test error handling
- Validate data models

### 6.2 Integration Tests
- Test full request/response cycles
- Verify streaming functionality
- Test checkpoint operations
- Validate analytics collection

### 6.3 Performance Tests
- Measure streaming throughput
- Test with large message volumes
- Monitor memory usage
- Benchmark UI responsiveness

### 6.4 End-to-End Tests
- Complete user workflows
- Multi-session management
- Agent task assignment
- Checkpoint branching scenarios

## 7. Configuration Management

### 7.1 iOS App Configuration
```swift
struct MCPConfiguration {
    let serverURL: URL
    let transport: TransportType
    let authToken: String?
    let logLevel: LogLevel
    let enableAnalytics: Bool
    let streamingBufferSize: Int
    let requestTimeout: TimeInterval
}

// UserDefaults storage
extension MCPConfiguration {
    static var current: MCPConfiguration {
        // Load from UserDefaults
    }
    
    func save() {
        // Save to UserDefaults
    }
}
```

### 7.2 Server Discovery
- mDNS/Bonjour for local discovery
- Manual server configuration
- QR code scanning for quick setup
- Configuration profiles

## 8. Security Considerations

### 8.1 Authentication
- API key authentication
- Optional OAuth2 integration
- Secure keychain storage
- Certificate pinning for HTTPS

### 8.2 Data Protection
- Encrypt sensitive data at rest
- Use App Transport Security
- Implement proper session management
- Clear memory on app background

## 9. Deployment Strategy

### 9.1 iOS App Distribution
- TestFlight for beta testing
- Enterprise distribution for internal use
- App Store distribution (if applicable)
- Ad-hoc distribution for development

### 9.2 Docker Deployment
- Container registry setup
- Kubernetes deployment manifests
- Health checks and monitoring
- Auto-scaling configuration

## 10. Monitoring & Analytics

### 10.1 App Analytics
- Session duration tracking
- Feature usage metrics
- Error rate monitoring
- Performance metrics

### 10.2 Server Monitoring
- Prometheus metrics export
- Grafana dashboards
- Alert configuration
- Log aggregation

## 11. Documentation Plan

### 11.1 User Documentation
- Getting started guide
- Feature walkthroughs
- Troubleshooting guide
- FAQ section

### 11.2 Developer Documentation
- API reference
- Architecture overview
- Contribution guidelines
- Testing procedures

## 12. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- Set up iOS project structure
- Implement basic MCP client
- Create main UI screens
- Docker container setup

### Phase 2: Core Features (Week 3-4)
- Implement all MCP tools
- Add streaming support
- Create session management
- Basic logging implementation

### Phase 3: Advanced Features (Week 5-6)
- Checkpoint system integration
- Agent management
- Analytics dashboard
- Real-time monitoring

### Phase 4: Polish & Testing (Week 7-8)
- Comprehensive testing
- Performance optimization
- UI/UX refinements
- Documentation completion

## 13. Success Metrics

- ✅ All 7 MCP tools fully functional
- ✅ Real-time streaming working reliably
- ✅ < 100ms latency for tool calls
- ✅ 99.9% uptime for containerized server
- ✅ Comprehensive test coverage (>80%)
- ✅ Complete documentation
- ✅ Successful deployment on Linux

## 14. Future Enhancements

- iPad and macOS Catalyst support
- Widget extensions for quick access
- Siri Shortcuts integration
- CloudKit sync for configurations
- Multi-server management
- Plugin system for custom tools