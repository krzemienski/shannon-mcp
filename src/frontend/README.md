# Frontend Components from Claudia Implementation

This directory contains frontend components extracted from the Claudia desktop app that can be reused for Shannon MCP's web interface.

## Key Components to Extract

### 1. Core Session Management
- **ClaudeCodeSession.tsx** - Main session component with streaming support
- **useClaudeMessages.ts** - Hook for managing Claude messages
- **SessionHeader.tsx** - Session header with project info
- **MessageList.tsx** - Virtual scrolling message list
- **FloatingPromptInput.tsx** - Input component for sending prompts

### 2. Streaming & Real-time Updates
- **StreamMessage.tsx** - Message rendering with tool detection
- **ToolWidgets.tsx** - Individual widgets for each tool type:
  - TodoWidget (task management)
  - EditWidget (file editing)
  - BashWidget (command execution)
  - ReadWidget (file reading)
  - WriteWidget (file writing)
  - GrepWidget (search)
  - LSWidget (directory listing)
  - MCPWidget (MCP tool calls)
  - TaskWidget (sub-agent tasks)
  - WebSearchWidget/WebFetchWidget (web operations)

### 3. MCP Server Management
- **MCPManager.tsx** - Main MCP server management interface
- **MCPServerList.tsx** - Display list of configured servers
- **MCPAddServer.tsx** - Add new MCP server UI
- **MCPImportExport.tsx** - Import/export server configurations

### 4. Agent System
- **AgentExecution.tsx** - Agent execution interface
- **AgentRunsList.tsx** - List of agent runs
- **CreateAgent.tsx** - Create new agent UI
- **AgentRunOutputViewer.tsx** - View agent output

### 5. Checkpoint & Timeline
- **TimelineNavigator.tsx** - Visual timeline navigation
- **CheckpointSettings.tsx** - Checkpoint configuration
- **useCheckpoints.ts** - Hook for checkpoint management

### 6. Project Management
- **ProjectList.tsx** - List of projects
- **ProjectSettings.tsx** - Project configuration

### 7. Analytics & Usage
- **UsageDashboard.tsx** - Usage statistics dashboard

## Key Features to Implement

### 1. Real-time JSONL Streaming
The Claudia implementation uses Tauri's event system for real-time streaming. For Shannon MCP web interface, we need:
- WebSocket or Server-Sent Events for streaming
- Backpressure handling
- Message buffering and replay

### 2. Virtual Scrolling
Uses @tanstack/react-virtual for efficient rendering of large message lists

### 3. Markdown Rendering
Uses react-markdown with syntax highlighting for code blocks

### 4. State Management
- Local component state with hooks
- Session state management
- Tool result mapping

## Missing Functionality in Shannon MCP

Based on the comparison, here are features that might be missing from our Shannon MCP specification:

### 1. Frontend Implementation
Shannon MCP is backend-only. We need to implement:
- Web-based UI (React/Vue/Svelte)
- WebSocket/SSE for real-time streaming
- Authentication/authorization for web access

### 2. WebView Preview
- **WebviewPreview.tsx** - Live preview of web content
- Split pane interface for code/preview

### 3. Visual Features
- Icon picker for agents
- Syntax highlighting themes
- Dark/light mode support

### 4. Import/Export
- Import MCP servers from URL
- Export server configurations
- Batch import functionality

### 5. Advanced Session Features
- Session forking from checkpoints
- Visual timeline with branching
- Diff view between checkpoints

### 6. Hooks Editor
- Visual hooks configuration
- Event trigger testing

### 7. Slash Commands Manager
- Visual slash command editor
- Command testing interface

## Implementation Priority

1. **High Priority** (Core functionality):
   - Session streaming UI
   - Basic tool widgets
   - MCP server management
   - Agent execution

2. **Medium Priority** (Enhanced UX):
   - Checkpoint/timeline UI
   - Analytics dashboard
   - Import/export
   - WebView preview

3. **Low Priority** (Nice to have):
   - Visual editors (hooks, commands)
   - Advanced theming
   - Icon customization