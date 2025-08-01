# Shannon MCP API Reference

## Overview

Shannon MCP implements the Model Context Protocol (MCP) specification, providing tools and resources for managing Claude Code CLI operations.

## Tools

### Binary Management

#### `find_claude_binary`

Discovers Claude Code installation on the system using multiple search strategies.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "find_claude_binary",
    "arguments": {}
  }
}
```

**Response:**
```json
{
  "path": "/Users/username/.nvm/versions/node/v20.11.0/bin/claude",
  "version": "0.3.0",
  "capabilities": ["code", "chat", "analysis"],
  "discovered_via": "PATH",
  "env": {
    "NODE_VERSION": "20.11.0",
    "NVM_BIN": "/Users/username/.nvm/versions/node/v20.11.0/bin"
  }
}
```

**Error Response:**
```json
{
  "error": "Claude Code not found",
  "suggestions": [
    "Install Claude Code from claude.ai/code",
    "Check PATH environment variable",
    "Specify path manually in configuration"
  ]
}
```

### Session Management

#### `create_session`

Creates a new Claude Code session with optional configuration.

**Parameters:**
- `prompt` (string, required): Initial prompt for the session
- `model` (string, optional): Model to use. Default: "claude-3-sonnet"
- `checkpoint_id` (string, optional): Restore from checkpoint
- `context` (object, optional): Additional context for the session

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_session",
    "arguments": {
      "prompt": "Build a REST API with authentication",
      "model": "claude-3-sonnet",
      "context": {
        "framework": "fastapi",
        "database": "postgresql",
        "auth": "jwt"
      }
    }
  }
}
```

**Response:**
```json
{
  "id": "session_abc123",
  "status": "active",
  "model": "claude-3-sonnet",
  "created_at": "2024-01-15T10:30:00Z",
  "process_id": 12345,
  "streaming_port": 8081
}
```

#### `send_message`

Sends a message to an active Claude Code session.

**Parameters:**
- `session_id` (string, required): Target session ID
- `message` (string, required): Message content
- `stream` (boolean, optional): Enable streaming. Default: true

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "send_message",
    "arguments": {
      "session_id": "session_abc123",
      "message": "Add user authentication endpoints",
      "stream": true
    }
  }
}
```

**Response:**
```json
{
  "status": "sent",
  "session_id": "session_abc123",
  "message_id": "msg_xyz789",
  "timestamp": "2024-01-15T10:31:00Z"
}
```

#### `cancel_session`

Cancels an active session and cleans up resources.

**Parameters:**
- `session_id` (string, required): Session to cancel

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "cancel_session",
    "arguments": {
      "session_id": "session_abc123"
    }
  }
}
```

**Response:**
```json
{
  "status": "cancelled",
  "session_id": "session_abc123",
  "cancelled_at": "2024-01-15T10:35:00Z"
}
```

#### `list_sessions`

Lists Claude Code sessions with optional filtering.

**Parameters:**
- `status` (string, optional): Filter by status: "active", "completed", "cancelled"
- `limit` (integer, optional): Maximum results. Default: 10

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_sessions",
    "arguments": {
      "status": "active",
      "limit": 5
    }
  }
}
```

**Response:**
```json
{
  "sessions": [
    {
      "id": "session_abc123",
      "status": "active",
      "model": "claude-3-sonnet",
      "created_at": "2024-01-15T10:30:00Z",
      "last_activity": "2024-01-15T10:31:00Z"
    },
    {
      "id": "session_def456",
      "status": "active",
      "model": "claude-3-opus",
      "created_at": "2024-01-15T09:00:00Z",
      "last_activity": "2024-01-15T09:45:00Z"
    }
  ],
  "total": 2,
  "has_more": false
}
```

### Agent System

#### `list_agents`

Lists available AI agents with their capabilities.

**Parameters:**
- `category` (string, optional): Filter by category

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_agents",
    "arguments": {
      "category": "code-quality"
    }
  }
}
```

**Response:**
```json
{
  "agents": [
    {
      "id": "code-reviewer",
      "name": "Code Reviewer",
      "category": "code-quality",
      "capabilities": ["syntax-check", "best-practices", "security-scan"],
      "description": "Automated code review with focus on quality and security"
    },
    {
      "id": "test-writer",
      "name": "Test Writer",
      "category": "code-quality",
      "capabilities": ["unit-tests", "integration-tests", "coverage-analysis"],
      "description": "Generates comprehensive test suites"
    }
  ]
}
```

#### `assign_task`

Assigns a task to a specialized AI agent.

**Parameters:**
- `agent_id` (string, required): Agent to assign to
- `task` (string, required): Task description
- `priority` (integer, optional): Priority 1-10. Default: 5
- `context` (object, optional): Additional context

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "assign_task",
    "arguments": {
      "agent_id": "code-reviewer",
      "task": "Review the authentication module for security vulnerabilities",
      "priority": 8,
      "context": {
        "focus": ["sql-injection", "jwt-security", "password-handling"],
        "severity": "high"
      }
    }
  }
}
```

**Response:**
```json
{
  "task_id": "task_789xyz",
  "agent_id": "code-reviewer",
  "status": "assigned",
  "estimated_duration": 300,
  "confidence": 0.95,
  "score": 0.98
}
```

### Checkpoint System

#### `create_checkpoint`

Creates a checkpoint of the current session state.

**Parameters:**
- `session_id` (string, required): Session to checkpoint
- `label` (string, required): Checkpoint label
- `include_context` (boolean, optional): Include session context. Default: true

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_checkpoint",
    "arguments": {
      "session_id": "session_abc123",
      "label": "Before adding authentication",
      "include_context": true
    }
  }
}
```

**Response:**
```json
{
  "id": "checkpoint_123abc",
  "session_id": "session_abc123",
  "label": "Before adding authentication",
  "created_at": "2024-01-15T10:32:00Z",
  "size": 45678,
  "hash": "sha256:abcdef..."
}
```

#### `restore_checkpoint`

Restores a session from a checkpoint.

**Parameters:**
- `checkpoint_id` (string, required): Checkpoint to restore
- `create_branch` (boolean, optional): Create new branch. Default: false

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "restore_checkpoint",
    "arguments": {
      "checkpoint_id": "checkpoint_123abc",
      "create_branch": true
    }
  }
}
```

**Response:**
```json
{
  "session_id": "session_new789",
  "checkpoint_id": "checkpoint_123abc",
  "branch": "feature/auth-rollback",
  "restored_at": "2024-01-15T11:00:00Z"
}
```

#### `list_checkpoints`

Lists checkpoints for a session.

**Parameters:**
- `session_id` (string, required): Session ID
- `limit` (integer, optional): Maximum results. Default: 20

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_checkpoints",
    "arguments": {
      "session_id": "session_abc123",
      "limit": 10
    }
  }
}
```

**Response:**
```json
{
  "checkpoints": [
    {
      "id": "checkpoint_123abc",
      "label": "Before adding authentication",
      "created_at": "2024-01-15T10:32:00Z",
      "size": 45678
    },
    {
      "id": "checkpoint_456def",
      "label": "Initial API structure",
      "created_at": "2024-01-15T10:15:00Z",
      "size": 23456
    }
  ],
  "total": 2
}
```

### Analytics

#### `query_analytics`

Queries usage analytics and metrics.

**Parameters:**
- `metric` (string, required): Metric to query
- `timeframe` (string, optional): Time range. Default: "24h"
- `aggregation` (string, optional): Aggregation method. Default: "sum"

**Available Metrics:**
- `sessions.total`: Total sessions
- `sessions.duration`: Session durations
- `messages.count`: Message count
- `tokens.usage`: Token usage
- `errors.rate`: Error rate

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "query_analytics",
    "arguments": {
      "metric": "tokens.usage",
      "timeframe": "7d",
      "aggregation": "daily"
    }
  }
}
```

**Response:**
```json
{
  "metric": "tokens.usage",
  "timeframe": "7d",
  "data": [
    {"date": "2024-01-09", "value": 125000},
    {"date": "2024-01-10", "value": 143000},
    {"date": "2024-01-11", "value": 168000},
    {"date": "2024-01-12", "value": 134000},
    {"date": "2024-01-13", "value": 156000},
    {"date": "2024-01-14", "value": 189000},
    {"date": "2024-01-15", "value": 87000}
  ],
  "total": 1002000,
  "average": 143142
}
```

### Hooks

#### `execute_hook`

Executes a configured hook manually.

**Parameters:**
- `hook_id` (string, required): Hook to execute
- `params` (object, optional): Hook parameters

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_hook",
    "arguments": {
      "hook_id": "backup-session",
      "params": {
        "session_id": "session_abc123",
        "destination": "~/backups/"
      }
    }
  }
}
```

**Response:**
```json
{
  "hook_id": "backup-session",
  "status": "success",
  "result": {
    "backup_path": "~/backups/session_abc123_20240115.tar.gz",
    "size": 123456
  }
}
```

## Resources

### Static Resources

#### `shannon://config`

Returns server configuration.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "shannon://config"
  }
}
```

**Response:**
```json
{
  "contents": [
    {
      "uri": "shannon://config",
      "mimeType": "application/json",
      "text": "{\"version\": \"1.0.0\", \"binary\": {...}, \"session\": {...}}"
    }
  ]
}
```

#### `shannon://agents`

Returns list of available agents.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "shannon://agents"
  }
}
```

#### `shannon://sessions`

Returns active sessions.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "shannon://sessions"
  }
}
```

### Dynamic Resources

#### `shannon://sessions/{session_id}`

Returns detailed information about a specific session.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "shannon://sessions/session_abc123"
  }
}
```

**Response:**
```json
{
  "contents": [
    {
      "uri": "shannon://sessions/session_abc123",
      "mimeType": "application/json",
      "text": "{\"id\": \"session_abc123\", \"status\": \"active\", ...}"
    }
  ]
}
```

#### `shannon://agents/{agent_id}`

Returns detailed information about a specific agent.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "resources/read",
  "params": {
    "uri": "shannon://agents/code-reviewer"
  }
}
```

## Error Handling

All errors follow the JSON-RPC 2.0 error format:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "details": "Session not found",
      "session_id": "session_invalid"
    }
  },
  "id": 1
}
```

### Common Error Codes

- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32000`: Server error (custom)

## Rate Limits

- **Tool calls**: 1000/minute
- **Resource reads**: 5000/minute
- **Session creates**: 100/hour
- **Analytics queries**: 500/hour

## Best Practices

1. **Session Management**
   - Always cancel sessions when done
   - Use checkpoints for long-running sessions
   - Monitor session duration and token usage

2. **Error Handling**
   - Implement retry logic for transient errors
   - Check session status before sending messages
   - Handle stream interruptions gracefully

3. **Performance**
   - Batch operations when possible
   - Use streaming for real-time updates
   - Cache resource responses appropriately

4. **Security**
   - Validate all input parameters
   - Use secure transport (TLS)
   - Rotate API keys regularly