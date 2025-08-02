# Shannon MCP Frontend

A modern React TypeScript frontend for Shannon MCP (Model Context Protocol) server, providing a web-based interface for managing Claude Code sessions.

## Features

- **Real-time WebSocket Communication**: Live streaming of Claude responses
- **Session Management**: Create, manage, and monitor Claude Code sessions
- **Virtual Scrolling**: Efficient rendering of large message lists
- **Tool Widget System**: Interactive widgets for Claude tools (in progress)
- **Modern UI**: Clean, accessible interface built with Tailwind CSS
- **TypeScript**: Full type safety with extracted Claudia types
- **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Socket.IO** for WebSocket communication
- **TanStack Virtual** for efficient list rendering
- **TanStack Query** for server state management
- **Zustand** for client state management
- **React Router** for navigation
- **React Markdown** for message rendering
- **React Syntax Highlighter** for code blocks

## Development

### Prerequisites

- Node.js 18+
- npm or yarn
- Shannon MCP backend server running

### Setup

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open http://localhost:3000 in your browser

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript checks

## Configuration

The frontend expects the Shannon MCP backend to be running on:
- **WebSocket**: `localhost:8080` for real-time communication
- **HTTP API**: `localhost:8000` for REST endpoints (when implemented)

These can be configured in `vite.config.ts`.

## Architecture

### Components

- **Layout**: Main application layout with sidebar navigation
- **SessionPage**: Main chat interface for Claude interactions
- **MessageList**: Virtual scrolling list of messages
- **MessageComponent**: Individual message rendering with markdown/code support
- **MessageInput**: Auto-resizing text input with send functionality
- **DashboardPage**: Overview of sessions and server status
- **SettingsPage**: Configuration interface

### State Management

- **SessionStore** (Zustand): Manages sessions, messages, and UI state
- **WebSocket Hook**: Handles real-time communication with backend
- **React Query**: Server state and caching (for REST APIs)

### Type System

Types are extracted from the Claudia desktop application and adapted for Shannon MCP:
- **ClaudeStreamMessage**: Message format from Claude
- **SessionState**: Session lifecycle and metadata
- **WebSocketMessage**: Real-time event format

## Integration with Backend

The frontend integrates with Shannon MCP backend through:

1. **WebSocket Connection** (`/socket.io`):
   - Session events: start, stop, subscribe
   - Real-time message streaming
   - Connection status and error handling

2. **REST API** (`/api` - planned):
   - Session management
   - MCP server configuration
   - Agent management
   - Analytics and metrics

3. **Authentication**:
   - JWT token-based authentication
   - Session-scoped permissions
   - Auto-reconnection on token refresh

## Message Flow

1. User types message in MessageInput
2. WebSocket sends message to backend
3. Backend forwards to Claude Code subprocess
4. Claude responses stream back via WebSocket
5. Messages appear in real-time in MessageList
6. State updates trigger UI re-renders

## Upcoming Features

- **Tool Widget System**: Interactive widgets for Claude tools
- **MCP Server Management**: Add/remove/configure servers
- **Agent System**: Custom AI agents with scheduling
- **Checkpoint Visualization**: Timeline view of session history
- **Analytics Dashboard**: Usage metrics and performance monitoring
- **Settings Management**: User preferences and configuration
- **File Upload/Download**: Artifact management
- **WebView Preview**: Live preview of generated web content

## Contributing

1. Follow the existing code style and patterns
2. Add TypeScript types for new features
3. Include tests for complex logic
4. Update this README for significant changes

## Deployment

Build for production:
```bash
npm run build
```

The built files will be in the `dist/` directory, ready for deployment to any static hosting service.

For integration with Shannon MCP server, the frontend can be served by the backend or deployed separately with proper CORS configuration.