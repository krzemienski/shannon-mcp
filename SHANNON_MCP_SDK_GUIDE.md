# Shannon MCP Claude Code SDK Integration Guide

## Overview

This guide explains how to integrate Shannon MCP with the Claude Code SDK, enabling programmatic access to Shannon MCP's powerful features including multi-agent collaboration, session management, and advanced analytics.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation & Configuration](#installation--configuration)
3. [Basic Usage](#basic-usage)
4. [Advanced Features](#advanced-features)
5. [API Reference](#api-reference)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

- Claude Code CLI installed (`claude` command available)
- Anthropic API key (get from [console.anthropic.com](https://console.anthropic.com))
- Node.js 18+ (for TypeScript SDK)
- Python 3.8+ (for Python SDK)
- Poetry installed (for Shannon MCP dependencies)

## Installation & Configuration

### 1. Install Shannon MCP Dependencies

```bash
cd ~/Desktop/shannon-mcp
poetry install
```

### 2. Add Shannon MCP to Claude Code

Using the Claude CLI:

```bash
# Add the FastMCP version (recommended)
claude mcp add shannon-mcp "poetry run shannon-mcp-fastmcp" \
    --working-dir "$HOME/Desktop/shannon-mcp" \
    --env SHANNON_LOG_LEVEL=DEBUG

# Or add the production version
claude mcp add shannon-mcp-prod "poetry run shannon-mcp-production" \
    --working-dir "$HOME/Desktop/shannon-mcp" \
    --env SHANNON_ENABLE_ANALYTICS=true
```

### 3. Create Project Configuration

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "poetry",
      "args": ["run", "shannon-mcp-fastmcp"],
      "cwd": "${PROJECT_DIR}",
      "env": {
        "SHANNON_LOG_LEVEL": "INFO",
        "SHANNON_CONFIG_PATH": "${PROJECT_DIR}/config.yaml"
      }
    }
  }
}
```

### 4. Set API Key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

## Basic Usage

### CLI Usage

```bash
# Find Claude binary
claude query "Use Shannon MCP to find the Claude Code binary" \
    --allowed-tools "shannon-mcp.*"

# Create a session
claude query "Create a new Claude session for Python development" \
    --allowed-tools "shannon-mcp.*"

# List agents
claude query "List all available Shannon MCP agents" \
    --allowed-tools "shannon-mcp.*"
```

### TypeScript SDK

```typescript
import { query } from "@anthropic-ai/claude-code";

async function useShannonMCP() {
    // Basic tool usage
    for await (const message of query({
        prompt: "Use Shannon MCP to find the Claude binary",
        options: {
            allowedTools: ["shannon-mcp.*"],
            maxTurns: 1
        }
    })) {
        console.log(message.text);
    }
}
```

### Python SDK

```python
import asyncio
from claude_code import query

async def use_shannon_mcp():
    # Basic tool usage
    async for message in query(
        prompt="Use Shannon MCP to create a coding session",
        options={
            "allowed_tools": ["shannon-mcp.*"],
            "max_turns": 1
        }
    ):
        print(message.text)

asyncio.run(use_shannon_mcp())
```

## Advanced Features

### 1. Multi-Agent Collaboration

```typescript
// Assign a complex task to multiple agents
async function multiAgentTask() {
    const result = query({
        prompt: `Use Shannon MCP to:
                 1. Create a task for building a REST API
                 2. Assign it to appropriate agents
                 3. Monitor progress`,
        options: {
            allowedTools: ["shannon-mcp.*"],
            maxTurns: 5,
            systemPrompt: "Coordinate multiple agents for efficient development"
        }
    });

    for await (const message of result) {
        console.log(`Agent Update: ${message.text}`);
    }
}
```

### 2. Session Streaming

```python
async def streaming_session():
    """Create a session with streaming responses."""
    
    # Create session
    session_id = None
    async for msg in query(
        "Create a Shannon MCP session for real-time code analysis",
        options={"allowed_tools": ["shannon-mcp.*"]}
    ):
        # Extract session ID from response
        session_id = parse_session_id(msg.text)
    
    # Send streaming message
    async for msg in query(
        f"Send a message to session {session_id} asking for a detailed code review with streaming enabled",
        options={
            "allowed_tools": ["shannon-mcp.*"],
            "stream": True
        }
    ):
        print(msg.text, end='', flush=True)
```

### 3. Checkpoint Management

```bash
#!/bin/bash
# Create and manage checkpoints

# Create checkpoint before major changes
SESSION_ID=$(claude query "Create a Shannon MCP session" \
    --allowed-tools "shannon-mcp.*" \
    --format json | jq -r '.session_id')

claude query "Create a checkpoint for session $SESSION_ID labeled 'pre-refactor'" \
    --allowed-tools "shannon-mcp.*"

# Make changes...

# Restore if needed
claude query "Restore checkpoint 'pre-refactor' for session $SESSION_ID" \
    --allowed-tools "shannon-mcp.*"
```

### 4. Analytics Queries

```typescript
// Query performance metrics
async function queryAnalytics() {
    for await (const message of query({
        prompt: `Use Shannon MCP to:
                 - Query token usage for the last 24 hours
                 - Show agent performance metrics
                 - List top resource access patterns`,
        options: {
            allowedTools: ["shannon-mcp.*"],
            maxTurns: 3
        }
    })) {
        console.log("Analytics:", message.text);
    }
}
```

### 5. Resource Access

```python
# Access MCP resources directly
async def access_resources():
    resources = [
        "shannon://config",
        "shannon://agents",
        "shannon://sessions",
        "shannon://analytics/summary"
    ]
    
    for resource in resources:
        async for msg in query(
            f"Access the {resource} resource and show its contents",
            options={"allowed_tools": ["shannon-mcp.*"]}
        ):
            print(f"\n{resource}:\n{msg.text}")
```

## API Reference

### Available Tools

#### Binary Management
- `find_claude_binary()` - Discover Claude Code installation
- `get_binary_info(path)` - Get detailed binary information

#### Session Management
- `create_session(prompt, model, context)` - Create new session
- `send_message(session_id, message, stream)` - Send message
- `list_sessions(status, limit)` - List sessions
- `cancel_session(session_id)` - Cancel active session
- `get_session_details(session_id)` - Get session info

#### Agent System
- `list_agents(category)` - List available agents
- `assign_task(title, description, category, priority)` - Create task
- `get_task_status(task_id)` - Check task progress
- `get_agent_metrics(agent_id)` - Agent performance

#### Advanced Features
- `create_checkpoint(session_id, label)` - Save state
- `restore_checkpoint(checkpoint_id)` - Restore state
- `query_analytics(metrics, time_range)` - Usage stats
- `register_hook(name, config)` - Event automation
- `execute_hook(name, context)` - Run hook

### Available Resources

- `shannon://config` - Server configuration
- `shannon://agents` - Agent listing
- `shannon://agents/{id}` - Agent details
- `shannon://sessions` - Session listing
- `shannon://sessions/{id}` - Session details
- `shannon://checkpoints` - Saved states
- `shannon://hooks` - Registered hooks
- `shannon://analytics/summary` - Usage dashboard
- `shannon://health` - System health

## Troubleshooting

### Common Issues

#### 1. MCP Server Not Found
```bash
# Check if server is configured
claude mcp list

# Re-add if missing
claude mcp add shannon-mcp "poetry run shannon-mcp-fastmcp"
```

#### 2. Authentication Errors
```bash
# Verify API key
echo $ANTHROPIC_API_KEY

# Test authentication
claude query "Hello" --max-turns 1
```

#### 3. Tool Access Denied
```bash
# Ensure tools are allowed
claude query "Test" --allowed-tools "shannon-mcp.*"

# Check server logs
tail -f ~/.shannon-mcp/logs/server.log
```

#### 4. Connection Issues
```python
# Test direct connection
from fastmcp import Client

async def test_connection():
    client = Client("src/shannon_mcp/server_fastmcp.py")
    async with client:
        tools = await client.list_tools()
        print(f"Connected! Found {len(tools)} tools")
```

### Debug Commands

```bash
# Enable debug logging
export SHANNON_LOG_LEVEL=DEBUG

# Check MCP configuration
cat ~/.claude/settings.json | jq '.mcpServers'

# Test server directly
cd ~/Desktop/shannon-mcp
poetry run shannon-mcp-fastmcp

# Monitor real-time logs
tail -f ~/.shannon-mcp/logs/*.log
```

### Performance Optimization

1. **Use Specific Tools**: Instead of `shannon-mcp.*`, specify exact tools:
   ```bash
   --allowed-tools "shannon-mcp.find_claude_binary,shannon-mcp.create_session"
   ```

2. **Limit Turns**: Keep `maxTurns` low for single operations:
   ```typescript
   options: { maxTurns: 1, allowedTools: ["shannon-mcp.specific_tool"] }
   ```

3. **Batch Operations**: Combine multiple operations in one prompt:
   ```python
   prompt = """Use Shannon MCP to:
               1. Create a session
               2. List agents
               3. Query current metrics"""
   ```

## Best Practices

1. **Always specify allowed tools** to prevent unintended tool usage
2. **Use streaming for long responses** to improve perceived performance
3. **Create checkpoints before major operations** for easy rollback
4. **Monitor analytics regularly** to optimize usage
5. **Configure project-specific MCP settings** in `.mcp.json`
6. **Use appropriate models** - Claude 3 Sonnet for complex tasks, Haiku for simple queries
7. **Handle errors gracefully** with try-catch blocks
8. **Log important operations** for debugging

## Examples Repository

Find more examples at:
- `test_sdk_typescript.ts` - TypeScript examples
- `test_sdk_python.py` - Python examples
- `test_sdk_cli.sh` - CLI examples
- `advanced_sdk_examples.md` - Advanced patterns

## Support

- Shannon MCP Issues: [GitHub Issues](https://github.com/shannon-mcp/issues)
- Claude Code Docs: [docs.anthropic.com/claude-code](https://docs.anthropic.com/claude-code)
- API Status: [status.anthropic.com](https://status.anthropic.com)

---

*Version: 1.0.0 | Last Updated: 2025-08-01*