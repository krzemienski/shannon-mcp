# WebSocket Implementation Task Breakdown for Shannon MCP

## Epic: Real-time Streaming Infrastructure

### Story 1: WebSocket Server Foundation
**Goal**: Implement WebSocket server in Shannon MCP backend
**Duration**: 2-3 days

#### Tasks:
1. **Install and configure Socket.IO**
   - Add `python-socketio` and `aiohttp` dependencies
   - Configure async Socket.IO server
   - Set up CORS and authentication middleware
   - Priority: High
   - Estimated: 2 hours

2. **Create WebSocket manager module**
   - Path: `src/shannon_mcp/websocket/manager.py`
   - Implement connection handling
   - Session management and tracking
   - Event routing system
   - Priority: High
   - Estimated: 4 hours

3. **Integrate with FastMCP server**
   - Mount Socket.IO on MCP server
   - Handle dual protocol (MCP + WebSocket)
   - Maintain backwards compatibility
   - Priority: High
   - Estimated: 3 hours

### Story 2: JSONL Streaming Implementation
**Goal**: Stream Claude session output in real-time
**Duration**: 2-3 days

#### Tasks:
1. **Create streaming parser**
   - Path: `src/shannon_mcp/streaming/jsonl_parser.py`
   - Parse JSONL from Claude subprocess
   - Handle partial messages and buffering
   - Error recovery for malformed JSON
   - Priority: High
   - Estimated: 4 hours

2. **Implement stream processor**
   - Path: `src/shannon_mcp/streaming/processor.py`
   - Message type detection and routing
   - Tool result mapping
   - Backpressure handling
   - Priority: High
   - Estimated: 3 hours

3. **Build event broadcaster**
   - Broadcast to connected clients
   - Channel-based routing (session-specific)
   - Message queuing for offline clients
   - Priority: High
   - Estimated: 3 hours

### Story 3: Session Event System
**Goal**: Comprehensive session event broadcasting
**Duration**: 1-2 days

#### Tasks:
1. **Define event types**
   ```python
   # Event types to implement:
   - claude-output:{session_id}
   - claude-error:{session_id}
   - claude-complete:{session_id}
   - session-status:{session_id}
   - tool-execution:{session_id}
   ```
   - Priority: High
   - Estimated: 1 hour

2. **Implement event emitters**
   - Integrate with SessionManager
   - Hook into Claude subprocess lifecycle
   - Error event propagation
   - Priority: High
   - Estimated: 3 hours

3. **Create event handlers**
   - Client subscription management
   - Event filtering and permissions
   - Event history/replay capability
   - Priority: Medium
   - Estimated: 2 hours

### Story 4: Authentication & Security
**Goal**: Secure WebSocket connections
**Duration**: 1-2 days

#### Tasks:
1. **Implement JWT authentication**
   - Token validation on connection
   - Session-based authorization
   - Token refresh mechanism
   - Priority: High
   - Estimated: 3 hours

2. **Add rate limiting**
   - Connection rate limits
   - Message rate limits per client
   - DDoS protection
   - Priority: Medium
   - Estimated: 2 hours

3. **Implement encryption**
   - WSS/TLS configuration
   - Message encryption for sensitive data
   - Key rotation strategy
   - Priority: Medium
   - Estimated: 2 hours

### Story 5: REST API Endpoints
**Goal**: Support frontend configuration needs
**Duration**: 2-3 days

#### Tasks:
1. **Session management endpoints**
   ```python
   POST   /api/sessions/create
   GET    /api/sessions/{id}
   DELETE /api/sessions/{id}
   GET    /api/sessions/active
   POST   /api/sessions/{id}/checkpoint
   ```
   - Priority: High
   - Estimated: 4 hours

2. **Project management endpoints**
   ```python
   GET    /api/projects
   POST   /api/projects
   GET    /api/projects/{id}
   PUT    /api/projects/{id}/settings
   ```
   - Priority: High
   - Estimated: 3 hours

3. **MCP server configuration endpoints**
   ```python
   GET    /api/mcp-servers
   POST   /api/mcp-servers
   DELETE /api/mcp-servers/{name}
   POST   /api/mcp-servers/{name}/test
   ```
   - Priority: Medium
   - Estimated: 3 hours

4. **Analytics endpoints**
   ```python
   GET    /api/analytics/usage
   GET    /api/analytics/costs
   GET    /api/analytics/sessions
   ```
   - Priority: Low
   - Estimated: 2 hours

### Story 6: Testing & Validation
**Goal**: Comprehensive testing suite
**Duration**: 1-2 days

#### Tasks:
1. **Unit tests**
   - WebSocket connection tests
   - Streaming parser tests
   - Event system tests
   - Priority: High
   - Estimated: 3 hours

2. **Integration tests**
   - End-to-end streaming tests
   - Multi-client scenarios
   - Error recovery tests
   - Priority: High
   - Estimated: 3 hours

3. **Performance tests**
   - Load testing with multiple clients
   - Streaming throughput tests
   - Memory leak detection
   - Priority: Medium
   - Estimated: 2 hours

## Implementation Order

### Phase 1: Core Infrastructure (Week 1)
1. WebSocket server foundation
2. JSONL streaming implementation
3. Basic event broadcasting

### Phase 2: Full Integration (Week 2)
1. Session event system
2. REST API endpoints
3. Authentication & security

### Phase 3: Testing & Optimization (Week 3)
1. Comprehensive testing
2. Performance optimization
3. Documentation

## Technical Implementation Details

### WebSocket Manager Structure
```python
# src/shannon_mcp/websocket/manager.py
class WebSocketManager:
    def __init__(self, mcp_server):
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*'
        )
        self.sessions = {}
        self.clients = {}
        
    async def handle_connect(self, sid, environ, auth):
        """Handle client connection with JWT auth"""
        
    async def handle_disconnect(self, sid):
        """Clean up client resources"""
        
    async def subscribe_to_session(self, sid, session_id):
        """Subscribe client to session events"""
        
    async def broadcast_session_event(self, session_id, event, data):
        """Broadcast event to all subscribed clients"""
```

### JSONL Stream Processor
```python
# src/shannon_mcp/streaming/processor.py
class JSONLStreamProcessor:
    def __init__(self, session_id, websocket_manager):
        self.session_id = session_id
        self.ws_manager = websocket_manager
        self.buffer = ""
        
    async def process_chunk(self, chunk: bytes):
        """Process incoming chunk from Claude subprocess"""
        text = chunk.decode('utf-8', errors='ignore')
        self.buffer += text
        
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line.strip():
                await self.process_line(line)
                
    async def process_line(self, line: str):
        """Parse and broadcast single JSONL line"""
        try:
            message = json.loads(line)
            await self.ws_manager.broadcast_session_event(
                self.session_id,
                f'claude-output:{self.session_id}',
                message
            )
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSONL: {line}")
```

### Integration with Session Manager
```python
# Modify existing SessionManager
class SessionManager:
    def __init__(self, websocket_manager=None):
        self.ws_manager = websocket_manager
        
    async def _stream_session_output(self, session_id, process):
        """Stream session output with WebSocket broadcasting"""
        processor = JSONLStreamProcessor(session_id, self.ws_manager)
        
        async for chunk in process.stdout:
            # Store in session history
            await self._store_chunk(session_id, chunk)
            
            # Broadcast via WebSocket
            if self.ws_manager:
                await processor.process_chunk(chunk)
```

## Success Criteria

1. **Streaming Performance**
   - < 50ms latency for message broadcast
   - Support 100+ concurrent clients
   - No message loss under normal conditions

2. **Reliability**
   - Automatic reconnection handling
   - Message buffering during disconnects
   - Graceful degradation

3. **Security**
   - All connections authenticated
   - No unauthorized session access
   - Encrypted sensitive data

4. **Compatibility**
   - Works with existing MCP protocol
   - Frontend can use extracted Claudia components
   - Backwards compatible with CLI usage