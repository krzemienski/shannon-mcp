# Shannon MCP Frontend Implementation Guide

## Summary

We've successfully extracted key frontend components from the Claudia desktop implementation that can be adapted for Shannon MCP's web interface. The main difference is that Claudia uses Tauri (Rust) for desktop integration, while Shannon MCP will use WebSocket/SSE for real-time communication.

## What We've Extracted

### 1. Components
- **StreamMessage.tsx** - Core message rendering component with tool widget support
- **ToolWidgets.tsx** - Individual widgets for each Claude Code tool type
- **Frontend structure** - Component organization and architecture patterns

### 2. Types
- **streaming.ts** - TypeScript types for Claude streaming messages
- All message types, session types, MCP server types, and agent types

### 3. Services
- **websocket.ts** - WebSocket service to replace Tauri's event system
- Streaming protocol implementation
- Session management helpers

### 4. Documentation
- **missing-features-analysis.md** - Comprehensive analysis of features to implement
- **frontend-implementation-tasks.md** - Detailed task breakdown
- **frontend/README.md** - Component extraction guide

## Key Adaptations Required

### 1. Replace Tauri with WebSocket
```typescript
// Original (Tauri)
await listen<string>(`claude-output:${sessionId}`, handler);

// New (WebSocket)
socket.on(`claude-output:${sessionId}`, handler);
```

### 2. File System Access
- Replace Tauri file dialogs with HTML5 file input or server-side file browser
- Implement server-side file operations through MCP tools

### 3. State Management
- Keep React hooks pattern from Claudia
- Add global state management (Zustand/Valtio) for session data
- Implement proper WebSocket reconnection handling

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
1. Set up React TypeScript project with Vite
2. Implement WebSocket service
3. Create base layout and routing
4. Port StreamMessage component
5. Implement basic tool widgets

### Phase 2: Session Management (Week 2)
1. Port ClaudeCodeSession component
2. Implement message streaming
3. Add virtual scrolling
4. Create input components
5. Add session persistence

### Phase 3: MCP Features (Week 3)
1. Port MCP server management UI
2. Implement server configuration
3. Add import/export functionality
4. Create server status monitoring
5. Build agent management UI

### Phase 4: Advanced Features (Week 4)
1. Implement checkpoint/timeline UI
2. Add analytics dashboard
3. Create WebView preview
4. Build visual editors
5. Add developer tools

## Technical Stack

### Core Dependencies
```json
{
  "react": "^18.2.0",
  "typescript": "^5.0.0",
  "vite": "^5.0.0",
  "react-router-dom": "^6.20.0",
  "socket.io-client": "^4.7.0",
  "tailwindcss": "^3.3.0",
  "@tanstack/react-virtual": "^3.0.0",
  "react-markdown": "^9.0.0",
  "react-syntax-highlighter": "^15.5.0",
  "lucide-react": "^0.290.0",
  "framer-motion": "^10.16.0"
}
```

### UI Components
- Use shadcn/ui for consistent design
- TailwindCSS for styling
- Lucide icons (same as Claudia)

## Backend Requirements

Shannon MCP server needs to implement:

### 1. WebSocket Endpoints
- `/ws` - Main WebSocket connection
- Session management events
- Streaming message broadcast
- Tool execution notifications

### 2. REST API Endpoints
- `/api/sessions` - Session CRUD
- `/api/projects` - Project management
- `/api/agents` - Agent operations
- `/api/mcp-servers` - MCP server config
- `/api/analytics` - Usage data

### 3. Streaming Protocol
- JSONL over WebSocket
- Backpressure handling
- Message buffering
- Reconnection support

## Security Considerations

### 1. Authentication
- JWT-based authentication
- Session tokens for WebSocket
- API key management for MCP servers

### 2. Authorization
- Role-based access control
- Project-level permissions
- Resource isolation

### 3. Data Protection
- Encrypted WebSocket connections (WSS)
- Secure storage for API keys
- Audit logging

## Performance Optimization

### 1. Frontend
- Virtual scrolling for messages
- Lazy loading for components
- Memoization for expensive renders
- WebSocket connection pooling

### 2. Backend
- Efficient JSONL streaming
- Message compression
- Database query optimization
- Caching strategies

## Testing Strategy

### 1. Unit Tests
- Component testing with React Testing Library
- Service layer testing
- Type safety validation

### 2. Integration Tests
- WebSocket communication
- Tool widget rendering
- Session management flow

### 3. E2E Tests
- Full session workflow
- MCP server configuration
- Agent execution

## Next Steps

1. **Initialize Frontend Project**
   ```bash
   cd /home/nick/shannon-mcp
   npm create vite@latest frontend -- --template react-ts
   cd frontend
   npm install
   ```

2. **Copy Extracted Components**
   - Move components from `src/frontend/` to the new project
   - Adapt imports and dependencies

3. **Implement WebSocket Server**
   - Add Socket.IO to Shannon MCP backend
   - Implement streaming endpoints
   - Add session management

4. **Start with Core Features**
   - Focus on session streaming first
   - Add tool widgets incrementally
   - Test with real Claude Code binary

## Conclusion

We have a solid foundation from the Claudia implementation. The main work is:
1. Adapting desktop features to web
2. Implementing WebSocket communication
3. Building the missing backend endpoints
4. Creating the web-specific UI components

The architecture and patterns from Claudia provide an excellent blueprint for Shannon MCP's frontend implementation.