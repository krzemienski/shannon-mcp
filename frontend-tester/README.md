# Shannon MCP Frontend Tester

A comprehensive frontend testing application that exercises all 30 MCP tools exposed by the Shannon MCP Server.

## Features

- **100% Tool Coverage**: Tests all 30 MCP tools through an interactive UI
- **Real-time Connection**: WebSocket/HTTP connection to Shannon MCP Server
- **Visual Testing**: Each tool has its own UI component for testing
- **E2E Testing**: Automated Puppeteer tests for all functionality
- **Response Visualization**: JSON viewer for server responses
- **Error Handling**: Comprehensive error display and recovery

## Tool Categories Covered

### 1. Binary Management (2 tools)
- find_claude_binary
- check_claude_updates

### 2. Session Management (4 tools)
- create_session
- list_sessions
- cancel_session
- send_message

### 3. Agent Management (4 tools)
- create_agent
- list_agents
- execute_agent
- assign_task

### 4. Checkpoint Management (4 tools)
- create_checkpoint
- list_checkpoints
- restore_checkpoint
- branch_checkpoint

### 5. Analytics & Settings (3 tools)
- query_analytics
- manage_settings
- server_status

### 6. Project Management (9 tools)
- create_project
- list_projects
- get_project
- update_project
- clone_project
- archive_project
- get_project_sessions
- set_project_active_session
- create_project_checkpoint

### 7. MCP Server Management (4 tools)
- mcp_add
- mcp_add_json
- mcp_add_from_claude_desktop
- mcp_serve

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the Shannon MCP Server (in the parent directory)

3. Start the frontend:
   ```bash
   npm start
   ```

4. Run E2E tests:
   ```bash
   npm run test:e2e
   ```

## Architecture

- **React + TypeScript**: Type-safe component development
- **Material-UI**: Consistent, accessible UI components
- **MCP Client**: Custom client for Shannon MCP protocol
- **Puppeteer**: Automated browser testing
- **Monaco Editor**: Code editing for test inputs