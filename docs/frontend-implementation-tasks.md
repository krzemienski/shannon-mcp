# Shannon MCP Frontend Implementation Tasks

## Phase 1: Core Web UI Foundation

### 1. Project Setup
- [ ] Initialize React TypeScript project with Vite
- [ ] Set up ESLint and Prettier
- [ ] Configure TailwindCSS for styling
- [ ] Set up component library (shadcn/ui recommended)
- [ ] Configure WebSocket client library

### 2. Core Infrastructure
- [ ] Create WebSocket service for MCP communication
- [ ] Implement streaming message parser
- [ ] Set up routing (React Router)
- [ ] Create base layout components
- [ ] Implement error boundary

### 3. Session Management
- [ ] Port ClaudeCodeSession component
- [ ] Implement session streaming hooks
- [ ] Create session state management
- [ ] Build message buffering system
- [ ] Add session persistence

### 4. Message Display
- [ ] Port StreamMessage component
- [ ] Implement virtual scrolling
- [ ] Add markdown rendering
- [ ] Configure syntax highlighting
- [ ] Create message filtering

### 5. Tool Widgets
- [ ] Create base ToolWidget component
- [ ] Implement TodoWidget
- [ ] Implement EditWidget
- [ ] Implement BashWidget
- [ ] Implement ReadWidget
- [ ] Implement WriteWidget
- [ ] Implement remaining tool widgets

### 6. Input Components
- [ ] Port FloatingPromptInput
- [ ] Add command history
- [ ] Implement slash command picker
- [ ] Add model selector
- [ ] Create file picker dialog

## Phase 2: MCP Server Management

### 7. MCP UI Components
- [ ] Port MCPManager component
- [ ] Create MCPServerList
- [ ] Build MCPAddServer form
- [ ] Implement server testing
- [ ] Add status indicators

### 8. Import/Export
- [ ] Create import dialog
- [ ] Build export functionality
- [ ] Add URL import feature
- [ ] Implement validation
- [ ] Create success/error feedback

## Phase 3: Agent System UI

### 9. Agent Management
- [ ] Port agent creation UI
- [ ] Build agent list view
- [ ] Create agent editor
- [ ] Add icon picker
- [ ] Implement agent testing

### 10. Agent Execution
- [ ] Port AgentExecution component
- [ ] Create run output viewer
- [ ] Build metrics display
- [ ] Add run history
- [ ] Implement run controls

## Phase 4: Advanced Features

### 11. Checkpoints & Timeline
- [ ] Port TimelineNavigator
- [ ] Create checkpoint UI
- [ ] Build diff viewer
- [ ] Add fork functionality
- [ ] Implement visual timeline

### 12. Analytics Dashboard
- [ ] Port UsageDashboard
- [ ] Create chart components
- [ ] Build cost calculator
- [ ] Add export functionality
- [ ] Implement date filtering

### 13. Project Management
- [ ] Create project list view
- [ ] Build project settings
- [ ] Add project switching
- [ ] Implement project search
- [ ] Create project templates

## Phase 5: Enhancement Features

### 14. WebView Preview
- [ ] Create split-pane layout
- [ ] Build WebView component
- [ ] Add URL navigation
- [ ] Implement refresh controls
- [ ] Add viewport controls

### 15. Visual Editors
- [ ] Create hooks editor
- [ ] Build slash command editor
- [ ] Add CLAUDE.md editor
- [ ] Implement syntax validation
- [ ] Create preview mode

### 16. Developer Tools
- [ ] Build JSONL inspector
- [ ] Create message replay
- [ ] Add performance monitor
- [ ] Implement debug panel
- [ ] Create error logger

## Implementation Guidelines

### Component Structure
```
src/
├── components/
│   ├── session/
│   │   ├── ClaudeCodeSession.tsx
│   │   ├── StreamMessage.tsx
│   │   └── FloatingPromptInput.tsx
│   ├── tools/
│   │   ├── ToolWidget.tsx
│   │   ├── TodoWidget.tsx
│   │   └── [other tool widgets]
│   ├── mcp/
│   │   ├── MCPManager.tsx
│   │   └── MCPServerList.tsx
│   └── common/
│       ├── Layout.tsx
│       └── ErrorBoundary.tsx
├── hooks/
│   ├── useWebSocket.ts
│   ├── useStreaming.ts
│   └── useSession.ts
├── services/
│   ├── websocket.ts
│   ├── api.ts
│   └── storage.ts
└── types/
    ├── streaming.ts
    └── mcp.ts
```

### Key Dependencies
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "react-syntax-highlighter": "^15.5.0",
    "@tanstack/react-virtual": "^3.0.0",
    "socket.io-client": "^4.7.0",
    "tailwindcss": "^3.3.0",
    "lucide-react": "^0.290.0",
    "framer-motion": "^10.16.0",
    "zustand": "^4.4.0"
  }
}
```

### WebSocket Integration
Replace Tauri event system with WebSocket:
```typescript
// Original Tauri
await listen<string>(`claude-output:${sessionId}`, handler);

// WebSocket replacement
socket.on(`claude-output:${sessionId}`, handler);
```

### Streaming Protocol
Implement JSONL parsing over WebSocket:
```typescript
interface StreamingService {
  connect(url: string): Promise<void>;
  subscribe(channel: string, handler: (data: any) => void): void;
  unsubscribe(channel: string): void;
  send(event: string, data: any): void;
}
```

## Testing Strategy

### Unit Tests
- Test individual components
- Mock WebSocket connections
- Test tool widget rendering
- Validate message parsing

### Integration Tests
- Test streaming flow
- Validate tool execution
- Test session management
- Check error handling

### E2E Tests
- Full session workflow
- MCP server configuration
- Agent execution flow
- Import/export functionality