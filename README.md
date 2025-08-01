# Shannon MCP - Advanced Claude Code MCP Server

A high-performance Model Context Protocol (MCP) server for Claude Code CLI, built with FastMCP for seamless integration with Claude Desktop and other MCP clients.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Resources](#resources)
- [Advanced Features](#advanced-features)
- [Development Guide](#development-guide)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Contributing](#contributing)

## Overview

Shannon MCP provides comprehensive programmatic access to Claude Code CLI operations through the MCP protocol, offering:

- **🔍 Binary Discovery**: Automatic detection and validation of Claude Code installations
- **📁 Project Management**: Organize multiple sessions within projects for better workflow
- **🎯 Session Management**: Full lifecycle management with real-time JSONL streaming
- **🤖 AI Agent System**: 26 specialized agents for different development tasks
- **💾 Checkpoint System**: Git-like versioning for session state management
- **🪝 Hooks Framework**: Event-driven automation with pre/post operation hooks
- **📊 Analytics Engine**: Comprehensive usage tracking and performance monitoring
- **🔐 Security Features**: Sandboxed execution with command validation
- **⚡ Performance**: Sub-10ms response times with efficient streaming

## Architecture

### System Overview

```
┌─────────────────────────────┐
│   Claude Desktop / Client   │
│  (MCP Protocol Consumer)    │
└──────────────┬──────────────┘
               │
               │ MCP Protocol
               │ (JSON-RPC over STDIO)
               │
┌──────────────▼──────────────┐
│     Shannon MCP Server      │
│        (FastMCP)            │
├─────────────────────────────┤
│  Core Components:           │
│  ├── Binary Manager         │
│  ├── Project Manager        │
│  ├── Session Manager        │
│  ├── Agent Manager          │
│  ├── Checkpoint System      │
│  ├── Analytics Engine       │
│  ├── Hooks Framework        │
│  └── Process Registry       │
├─────────────────────────────┤
│  Storage Layer:             │
│  ├── SQLite Database        │
│  └── CAS (Content Store)    │
└──────────────┬──────────────┘
               │
               │ Process Spawn
               │ & JSONL Stream
               │
┌──────────────▼──────────────┐
│    Claude Code Binary       │
│   (Actual CLI Execution)    │
└─────────────────────────────┘
```

### Component Details

#### Binary Manager
- **Auto-discovery**: Searches standard locations and PATH
- **Version detection**: Validates Claude Code versions
- **Capability checking**: Ensures required features are available
- **Cache management**: Speeds up repeated binary lookups

#### Project Manager
- **Project organization**: Group related sessions together
- **Shared context**: Project-wide settings and defaults
- **Bulk operations**: Manage multiple sessions efficiently
- **Progress tracking**: Aggregate metrics at project level

#### Session Manager
- **Process lifecycle**: Spawns and manages Claude Code processes
- **JSONL streaming**: Real-time bidirectional communication
- **State tracking**: Monitors session status and health
- **Resource cleanup**: Ensures proper process termination

#### Agent System
- **26 specialized agents**: Each with domain expertise
- **Task orchestration**: Intelligent task routing and prioritization
- **Collaborative execution**: Agents work together on complex tasks
- **Learning capabilities**: Improves performance over time

## Installation

### Prerequisites

- Python 3.11 or higher
- Claude Code CLI (install from [claude.ai/code](https://claude.ai/code))
- uv (recommended) or pip for dependency management

### Installation Steps

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or use pip: pip install uv

# Clone the repository
git clone https://github.com/yourusername/shannon-mcp.git
cd shannon-mcp

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .

# Verify installation
uv run shannon-mcp --version
```

### Claude Desktop Integration

Add Shannon MCP to your Claude Desktop configuration:

1. Open Claude Desktop settings
2. Navigate to Developer → MCP Servers
3. Add the following configuration:

```json
{
  "shannon-mcp": {
    "command": "uv",
    "args": ["run", "shannon-mcp"],
    "cwd": "/absolute/path/to/shannon-mcp",
    "env": {
      "SHANNON_DEBUG": "false",
      "SHANNON_ANALYTICS": "true"
    }
  }
}
```

Alternative configurations:

**Using Python directly:**
```json
{
  "shannon-mcp": {
    "command": "python",
    "args": ["-m", "shannon_mcp.stdio_wrapper"],
    "cwd": "/absolute/path/to/shannon-mcp"
  }
}
```

**Using uv's managed venv:**
```json
{
  "shannon-mcp": {
    "command": "/path/to/shannon-mcp/.venv/bin/python",
    "args": ["-m", "shannon_mcp.stdio_wrapper"],
    "cwd": "/absolute/path/to/shannon-mcp"
  }
}
```

## Configuration

### Environment Variables

```bash
# Claude Code binary path (auto-discovered if not set)
export CLAUDE_CODE_PATH="/usr/local/bin/claude"

# Database location (default: ~/.shannon-mcp/shannon.db)
export SHANNON_DB_PATH="/custom/path/shannon.db"

# Debug logging (default: false)
export SHANNON_DEBUG="true"

# Analytics collection (default: true)
export SHANNON_ANALYTICS="false"

# Session timeout in seconds (default: 300)
export SHANNON_SESSION_TIMEOUT="600"

# Maximum concurrent sessions (default: 10)
export SHANNON_MAX_SESSIONS="20"

# Enable experimental features (default: false)
export SHANNON_EXPERIMENTAL="true"
```

### Configuration File

Create `~/.shannon-mcp/config.json` for persistent configuration:

```json
{
  "binary": {
    "search_paths": [
      "~/.nvm/versions/node/*/bin",
      "/usr/local/bin",
      "/opt/homebrew/bin",
      "/opt/claude/bin"
    ],
    "preferred_version": "latest",
    "validate_signature": true,
    "cache_ttl": 3600
  },
  "session": {
    "default_model": "claude-3-sonnet",
    "timeout": 300,
    "auto_cleanup": true,
    "max_retries": 3,
    "stream_buffer_size": 8192
  },
  "agents": {
    "enabled": true,
    "auto_assign": true,
    "max_concurrent": 5,
    "task_timeout": 600
  },
  "analytics": {
    "enabled": true,
    "retention_days": 30,
    "batch_size": 100,
    "flush_interval": 60
  },
  "hooks": {
    "enabled": true,
    "config_path": "~/.shannon-mcp/hooks.json",
    "allow_custom": true
  },
  "security": {
    "sandbox_enabled": true,
    "allowed_commands": ["claude", "git", "npm", "python"],
    "blocked_patterns": ["rm -rf", "sudo", "chmod 777"],
    "max_file_size": 10485760
  }
}
```

## Available Tools

Shannon MCP provides 30+ comprehensive tools for Claude Code interaction:

### Core Tools

#### 1. `find_claude_binary`
Discovers and validates Claude Code installation.

**Parameters:** None

**Returns:**
```json
{
  "path": "/usr/local/bin/claude",
  "version": "0.3.0",
  "capabilities": ["code", "chat", "analysis", "web"],
  "discovered_via": "PATH",
  "validated": true,
  "last_updated": "2024-01-15T10:30:00Z"
}
```

**Example Usage:**
```python
# Find Claude binary
result = await mcp_client.call_tool("find_claude_binary")
claude_path = result["path"]
```

#### 2. `create_project`
Creates a new project to organize multiple sessions.

**Parameters:**
- `name` (string, required): Project name
- `description` (string, optional): Project description
- `tags` (array, optional): Tags for categorization
- `default_model` (string, optional): Default model for sessions
- `default_context` (object, optional): Shared context for sessions

**Returns:**
```json
{
  "project": {
    "id": "proj_abc123",
    "name": "E-commerce Platform",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### 3. `create_session`
Creates a new Claude Code session with advanced options.

**Parameters:**
- `prompt` (string, required): Initial prompt or task description
- `model` (string, optional): Model to use (default: "claude-3-sonnet")
- `project_id` (string, optional): Project to add session to
- `temperature` (float, optional): Creativity setting 0-1 (default: 0.7)
- `max_tokens` (int, optional): Maximum response tokens
- `context` (object, optional): Additional context data
- `checkpoint_id` (string, optional): Restore from checkpoint
- `agent_ids` (array, optional): Pre-assign agents to session

**Returns:**
```json
{
  "session_id": "sess_abc123",
  "status": "active",
  "model": "claude-3-sonnet",
  "created_at": "2024-01-15T10:30:00Z",
  "assigned_agents": ["code-reviewer", "test-writer"],
  "stream_url": "shannon://sessions/sess_abc123/stream"
}
```

**Example Usage:**
```python
# Create project first
project = await mcp_client.call_tool("create_project", {
    "name": "REST API Project",
    "tags": ["api", "backend"]
})

# Create session within project
session = await mcp_client.call_tool("create_session", {
    "prompt": "Build a REST API with authentication",
    "project_id": project["project"]["id"],
    "model": "claude-3-opus",
    "context": {
        "framework": "fastapi",
        "database": "postgresql",
        "auth_type": "jwt"
    },
    "agent_ids": ["architect", "security-scanner"]
})
```

#### 4. `send_message`
Sends a message to an active session with streaming support.

**Parameters:**
- `session_id` (string, required): Target session ID
- `message` (string, required): Message content
- `stream` (boolean, optional): Enable streaming (default: true)
- `attachments` (array, optional): File attachments
- `metadata` (object, optional): Additional metadata

**Returns:**
```json
{
  "message_id": "msg_xyz789",
  "status": "delivered",
  "timestamp": "2024-01-15T10:31:00Z",
  "streaming": true,
  "response_preview": "I'll help you create that API..."
}
```

#### 5. `list_projects`
Lists projects with filtering and pagination.

**Parameters:**
- `status` (string, optional): Filter by status (active/archived/completed)
- `tags` (array, optional): Filter by tags
- `limit` (int, optional): Max results (default: 50)
- `sort_by` (string, optional): Sort field (created_at/updated_at/name)

**Returns:** List of projects with pagination info

#### 6. `get_project_sessions`
Gets all sessions within a project.

**Parameters:**
- `project_id` (string, required): Project ID
- `include_archived` (boolean, optional): Include archived sessions

**Returns:** List of sessions in the project

#### 7. `stream_session_output`
Streams real-time output from a Claude Code session.

**Parameters:**
- `session_id` (string, required): Session to stream from
- `include_stderr` (boolean, optional): Include error output
- `format` (string, optional): Output format (json/text)

**Returns:** Streaming response with chunks

#### 8. `cancel_session`
Gracefully cancels an active session.

**Parameters:**
- `session_id` (string, required): Session to cancel
- `reason` (string, optional): Cancellation reason
- `force` (boolean, optional): Force termination

**Returns:**
```json
{
  "session_id": "sess_abc123",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T10:32:00Z",
  "cleanup_completed": true
}
```

#### 9. `list_sessions`
Lists Claude Code sessions with filtering and pagination.

**Parameters:**
- `status` (string, optional): Filter by status (active/completed/cancelled)
- `limit` (int, optional): Max results (default: 10, max: 100)
- `offset` (int, optional): Pagination offset
- `sort_by` (string, optional): Sort field (created_at/updated_at)
- `sort_order` (string, optional): Sort order (asc/desc)

**Returns:**
```json
{
  "sessions": [
    {
      "session_id": "sess_abc123",
      "status": "active",
      "model": "claude-3-sonnet",
      "created_at": "2024-01-15T10:30:00Z",
      "last_activity": "2024-01-15T10:31:00Z",
      "messages_count": 5
    }
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

#### 10. `get_session_details`
Retrieves comprehensive session information.

**Parameters:**
- `session_id` (string, required): Session ID
- `include_messages` (boolean, optional): Include message history
- `include_metrics` (boolean, optional): Include performance metrics

**Returns:** Detailed session object with history and metrics

### Agent Tools

#### 8. `list_agents`
Lists all available AI agents with capabilities.

**Parameters:**
- `category` (string, optional): Filter by category
- `status` (string, optional): Filter by status (available/busy)

**Returns:**
```json
{
  "agents": [
    {
      "agent_id": "code-reviewer",
      "name": "Code Review Specialist",
      "category": "quality",
      "description": "Performs comprehensive code reviews",
      "capabilities": ["security", "performance", "style"],
      "status": "available",
      "success_rate": 0.95
    }
  ],
  "categories": ["architecture", "development", "quality", "specialized"]
}
```

#### 9. `assign_task`
Assigns a task to an AI agent with priority and context.

**Parameters:**
- `agent_id` (string, required): Target agent ID
- `task` (string, required): Task description
- `priority` (int, optional): Priority 1-10 (default: 5)
- `context` (object, optional): Task-specific context
- `deadline` (string, optional): Task deadline (ISO 8601)
- `dependencies` (array, optional): Task dependencies

**Returns:**
```json
{
  "task_id": "task_def456",
  "agent_id": "code-reviewer",
  "status": "assigned",
  "estimated_duration": 300,
  "started_at": "2024-01-15T10:33:00Z"
}
```

#### 10. `get_agent_status`
Gets detailed status of a specific agent.

**Parameters:**
- `agent_id` (string, required): Agent ID

**Returns:** Agent status with current task and metrics

#### 11. `list_agent_tasks`
Lists tasks assigned to agents.

**Parameters:**
- `agent_id` (string, optional): Filter by agent
- `status` (string, optional): Filter by task status
- `limit` (int, optional): Maximum results

**Returns:** List of tasks with details

### Checkpoint Tools

#### 12. `create_checkpoint`
Creates a session checkpoint for versioning.

**Parameters:**
- `session_id` (string, required): Session to checkpoint
- `label` (string, required): Checkpoint label
- `description` (string, optional): Detailed description
- `include_context` (boolean, optional): Include full context
- `auto_compress` (boolean, optional): Compress checkpoint data

**Returns:**
```json
{
  "checkpoint_id": "ckpt_ghi789",
  "session_id": "sess_abc123",
  "label": "Before refactoring",
  "size_bytes": 1048576,
  "created_at": "2024-01-15T10:34:00Z",
  "parent_checkpoint": "ckpt_xyz123"
}
```

#### 13. `list_checkpoints`
Lists checkpoints for a session.

**Parameters:**
- `session_id` (string, optional): Filter by session
- `include_tree` (boolean, optional): Show checkpoint tree

**Returns:** List of checkpoints with relationships

#### 14. `restore_checkpoint`
Restores session from a checkpoint.

**Parameters:**
- `checkpoint_id` (string, required): Checkpoint to restore
- `create_branch` (boolean, optional): Create new branch
- `session_name` (string, optional): Name for new session

**Returns:** New session created from checkpoint

#### 15. `diff_checkpoints`
Shows differences between checkpoints.

**Parameters:**
- `checkpoint_id_1` (string, required): First checkpoint
- `checkpoint_id_2` (string, required): Second checkpoint

**Returns:** Detailed diff of changes

### Analytics Tools

#### 16. `query_analytics`
Queries usage analytics with aggregation.

**Parameters:**
- `metric` (string, required): Metric to query
- `timeframe` (string, optional): Time range (1h/1d/1w/1m)
- `aggregation` (string, optional): Aggregation method
- `group_by` (string, optional): Grouping field
- `filters` (object, optional): Additional filters

**Returns:**
```json
{
  "metric": "session_duration",
  "timeframe": "1d",
  "data": [
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "value": 1800,
      "count": 25
    }
  ],
  "summary": {
    "average": 1800,
    "total": 45000,
    "max": 3600,
    "min": 300
  }
}
```

#### 17. `get_usage_stats`
Gets comprehensive usage statistics.

**Parameters:**
- `period` (string, optional): Time period (today/week/month)

**Returns:** Detailed usage statistics and trends

### Hook Tools

#### 18. `list_hooks`
Lists configured automation hooks.

**Parameters:**
- `event_type` (string, optional): Filter by event type
- `enabled_only` (boolean, optional): Show only enabled hooks

**Returns:** List of configured hooks with details

#### 19. `create_hook`
Creates a new automation hook.

**Parameters:**
- `event` (string, required): Event to hook into
- `action` (string, required): Action to perform
- `config` (object, required): Hook configuration
- `enabled` (boolean, optional): Enable immediately

**Returns:** Created hook details

#### 20. `trigger_hook`
Manually triggers a hook.

**Parameters:**
- `hook_id` (string, required): Hook to trigger
- `data` (object, optional): Event data

**Returns:** Hook execution result

### Process Tools

#### 21. `get_process_info`
Gets system process information.

**Parameters:**
- `session_id` (string, optional): Get process for specific session

**Returns:**
```json
{
  "processes": [
    {
      "pid": 12345,
      "session_id": "sess_abc123",
      "cpu_percent": 2.5,
      "memory_mb": 256,
      "uptime_seconds": 300,
      "status": "running"
    }
  ],
  "system": {
    "total_sessions": 5,
    "cpu_usage": 12.5,
    "memory_usage": 1280
  }
}
```

## Resources

Shannon MCP exposes various resources for monitoring and configuration:

### Static Resources

- **`shannon://config`** - Server configuration
  ```json
  {
    "version": "0.1.0",
    "binary_path": "/usr/local/bin/claude",
    "database_path": "~/.shannon-mcp/shannon.db",
    "features": {
      "projects": true,
      "agents": true,
      "checkpoints": true,
      "analytics": true,
      "hooks": true
    }
  }
  ```

- **`shannon://projects`** - List of all projects
- **`shannon://agents`** - Available agents catalog
- **`shannon://sessions`** - Active sessions list
- **`shannon://analytics`** - Analytics dashboard data
- **`shannon://hooks`** - Hook configurations
- **`shannon://health`** - Server health status

### Dynamic Resources

- **`shannon://projects/{project_id}`** - Project details with sessions
- **`shannon://sessions/{session_id}`** - Individual session details
- **`shannon://sessions/{session_id}/messages`** - Session message history
- **`shannon://sessions/{session_id}/stream`** - Live session stream
- **`shannon://agents/{agent_id}`** - Agent information and metrics
- **`shannon://checkpoints/{session_id}`** - Session checkpoints
- **`shannon://analytics/{metric}`** - Specific metric data

## Advanced Features

### Project Management

Organize your work with projects that group related sessions:

```python
# Create a project for a web application
project = await create_project(
    name="E-commerce Platform",
    description="Full-stack e-commerce site with React and Node.js",
    tags=["web", "fullstack", "production"],
    default_model="claude-3-opus",
    default_context={
        "tech_stack": ["React", "Node.js", "PostgreSQL", "Redis"],
        "coding_standards": "airbnb",
        "target_audience": "B2C"
    }
)

# Create sessions for different features
auth_session = await create_session(
    prompt="Implement JWT authentication with refresh tokens",
    project_id=project["project"]["id"]
    # Inherits model and context from project
)

payment_session = await create_session(
    prompt="Integrate Stripe payment processing",
    project_id=project["project"]["id"]
)

# Get all sessions in the project
sessions = await get_project_sessions(
    project_id=project["project"]["id"]
)

# Create checkpoint for entire project
checkpoint = await create_project_checkpoint(
    project_id=project["project"]["id"],
    name="MVP Complete",
    description="All core features implemented"
)

# Archive project when done
await archive_project(project_id=project["project"]["id"])
```

### Multi-Agent Collaboration

The agent system includes 26 specialized agents that work together:

**Core Architecture Agents:**
- `architect` - System design and architecture decisions
- `tech-lead` - Technical direction and best practices
- `integration-specialist` - System integration patterns
- `api-designer` - API design and documentation

**Development Agents:**
- `code-generator` - Code generation and scaffolding
- `refactoring-expert` - Code refactoring and optimization
- `test-writer` - Comprehensive test generation
- `doc-generator` - Documentation creation
- `frontend-dev` - Frontend implementation
- `backend-dev` - Backend implementation
- `database-expert` - Database design and queries

**Quality Agents:**
- `code-reviewer` - Automated code reviews
- `security-scanner` - Security vulnerability detection
- `performance-analyzer` - Performance optimization
- `bug-hunter` - Bug detection and fixing
- `quality-auditor` - Code quality assessment

**Specialized Agents:**
- `devops-engineer` - CI/CD and deployment
- `cloud-architect` - Cloud infrastructure design
- `ml-engineer` - Machine learning integration
- `data-analyst` - Data analysis and insights
- `ux-designer` - User experience improvements
- `accessibility-expert` - Accessibility compliance
- `i18n-specialist` - Internationalization
- `mobile-dev` - Mobile app development
- `game-dev` - Game development patterns

### Checkpoint System

Advanced versioning with branching support:

```python
# Create checkpoint before major change
checkpoint = await create_checkpoint(
    session_id="sess_abc123",
    label="v1.0-stable",
    description="Stable version before adding new features",
    include_context=True
)

# Work on new features...

# Create another checkpoint
new_checkpoint = await create_checkpoint(
    session_id="sess_abc123",
    label="v1.1-features",
    description="Added authentication and caching"
)

# Compare changes
diff = await diff_checkpoints(
    checkpoint_id_1=checkpoint["checkpoint_id"],
    checkpoint_id_2=new_checkpoint["checkpoint_id"]
)

# Restore if needed
restored = await restore_checkpoint(
    checkpoint_id=checkpoint["checkpoint_id"],
    create_branch=True,
    session_name="hotfix-branch"
)
```

### Hooks Framework

Automate workflows with event-driven hooks:

```json
{
  "hooks": [
    {
      "id": "auto-test",
      "event": "session.code_generated",
      "action": "assign_task",
      "config": {
        "agent_id": "test-writer",
        "task_template": "Write tests for newly generated code",
        "auto_execute": true
      }
    },
    {
      "id": "security-check",
      "event": "checkpoint.created",
      "action": "security_scan",
      "config": {
        "scan_type": "full",
        "fail_on_critical": true
      }
    },
    {
      "id": "notification",
      "event": "task.completed",
      "action": "notify",
      "config": {
        "channels": ["slack", "email"],
        "template": "Task {{task_id}} completed by {{agent_id}}"
      }
    }
  ]
}
```

### Analytics Dashboard

Comprehensive metrics and insights:

```python
# Query specific metrics
duration_stats = await query_analytics(
    metric="session_duration",
    timeframe="1w",
    aggregation="avg",
    group_by="model"
)

# Get usage trends
usage = await get_usage_stats(period="month")
print(f"Total sessions: {usage['total_sessions']}")
print(f"Average duration: {usage['avg_duration_minutes']} minutes")
print(f"Most used model: {usage['top_model']}")
print(f"Peak usage time: {usage['peak_hour']}")
```

## Development Guide

### Project Structure

```
shannon-mcp/
├── src/shannon_mcp/
│   ├── __init__.py
│   ├── server_fastmcp.py      # Main FastMCP server
│   ├── stdio_wrapper.py       # STDIO communication wrapper
│   ├── managers/              # Component managers
│   │   ├── __init__.py
│   │   ├── binary.py          # Claude binary management
│   │   ├── project.py         # Project management
│   │   ├── session.py         # Session lifecycle
│   │   ├── agent.py           # Agent orchestration
│   │   ├── checkpoint.py      # Checkpoint system
│   │   ├── analytics.py       # Analytics engine
│   │   ├── hook.py            # Hook framework
│   │   └── process.py         # Process registry
│   ├── storage/               # Storage layer
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite operations
│   │   └── cas.py            # Content-addressable storage
│   ├── streaming/             # Streaming components
│   │   ├── __init__.py
│   │   ├── jsonl_processor.py # JSONL processing
│   │   └── backpressure.py   # Backpressure handling
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── validation.py      # Input validation
│       ├── logging.py         # Structured logging
│       └── metrics.py         # Performance metrics
├── tests/                     # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   ├── functional/            # Functional tests
│   └── benchmarks/            # Performance benchmarks
├── docs/                      # Documentation
│   ├── api/                   # API documentation
│   ├── guides/                # User guides
│   └── architecture/          # Architecture docs
├── examples/                  # Example usage
├── scripts/                   # Utility scripts
├── pyproject.toml            # Poetry configuration
├── README.md                 # This file
└── LICENSE                   # MIT License
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test category
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/functional/

# Run with coverage
uv run pytest --cov=shannon_mcp --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_binary_manager.py

# Run with verbose output
uv run pytest -vv

# Run benchmarks
uv run python tests/benchmarks/run_benchmarks.py
```

### Code Quality

```bash
# Format code with black
uv run black .

# Check formatting
uv run black . --check

# Run linting
uv run flake8

# Type checking
uv run mypy .

# Sort imports
uv run isort .

# Run all checks
uv run black . && uv run isort . && uv run flake8 && uv run mypy .

# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### Building and Publishing

```bash
# Build package
uv build

# Build Docker image
docker build -t shannon-mcp:latest .

# Run in Docker
docker run -it --rm \
  -v ~/.shannon-mcp:/root/.shannon-mcp \
  -e CLAUDE_CODE_PATH=/usr/local/bin/claude \
  shannon-mcp:latest

# Publish to PyPI (requires credentials)
uv publish

# Create release
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

## Troubleshooting

### Common Issues and Solutions

#### Claude Code Not Found

**Problem:** Server cannot find Claude Code binary

**Solutions:**
```bash
# 1. Check if Claude is installed
which claude

# 2. Add to PATH
export PATH="/path/to/claude/bin:$PATH"

# 3. Set explicit path
export CLAUDE_CODE_PATH="/absolute/path/to/claude"

# 4. Update config.json
{
  "binary": {
    "path": "/absolute/path/to/claude"
  }
}

# 5. Verify with tool
uv run shannon-mcp test find_claude_binary
```

#### Session Timeout Issues

**Problem:** Sessions timing out prematurely

**Solutions:**
```bash
# 1. Increase timeout in environment
export SHANNON_SESSION_TIMEOUT=600

# 2. Update config.json
{
  "session": {
    "timeout": 600,
    "keep_alive": true
  }
}

# 3. Use session keep-alive
await send_message(
    session_id="sess_abc123",
    message="",
    metadata={"keep_alive": true}
)
```

#### Permission Errors

**Problem:** Database or file permission issues

**Solutions:**
```bash
# 1. Check permissions
ls -la ~/.shannon-mcp/

# 2. Fix permissions
chmod 755 ~/.shannon-mcp/
chmod 644 ~/.shannon-mcp/shannon.db

# 3. Run with different user
sudo -u claude-user uv run shannon-mcp

# 4. Change database location
export SHANNON_DB_PATH=/tmp/shannon.db
```

#### Memory Issues

**Problem:** High memory usage with multiple sessions

**Solutions:**
```bash
# 1. Limit concurrent sessions
export SHANNON_MAX_SESSIONS=5

# 2. Enable aggressive cleanup
{
  "session": {
    "auto_cleanup": true,
    "cleanup_interval": 60
  }
}

# 3. Monitor memory usage
uv run shannon-mcp monitor --memory

# 4. Use session pooling
{
  "session": {
    "pooling": true,
    "pool_size": 3
  }
}
```

### Debug Mode

Enable comprehensive debugging:

```bash
# Set debug environment
export SHANNON_DEBUG=true
export SHANNON_LOG_LEVEL=DEBUG

# Run with debug output
uv run shannon-mcp --debug

# Enable SQL query logging
export SHANNON_LOG_SQL=true

# Trace MCP protocol
export SHANNON_TRACE_MCP=true

# Full debug configuration
{
  "debug": {
    "enabled": true,
    "log_level": "DEBUG",
    "log_sql": true,
    "trace_mcp": true,
    "profile_performance": true,
    "dump_on_error": true
  }
}
```

## API Reference

### Tool Response Format

All tools follow a consistent response format:

```typescript
interface ToolResponse {
  success: boolean;
  data?: any;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  metadata?: {
    duration_ms: number;
    timestamp: string;
    version: string;
  };
}
```

### Error Codes

Standard error codes used across all tools:

- `BINARY_NOT_FOUND` - Claude Code binary not found
- `SESSION_NOT_FOUND` - Session does not exist
- `SESSION_TIMEOUT` - Session timed out
- `AGENT_BUSY` - Agent is busy with another task
- `CHECKPOINT_FAILED` - Checkpoint creation failed
- `INVALID_PARAMS` - Invalid parameters provided
- `PERMISSION_DENIED` - Insufficient permissions
- `RATE_LIMITED` - Rate limit exceeded
- `INTERNAL_ERROR` - Internal server error

### Event Types

Events that can trigger hooks:

- `session.created` - New session created
- `session.completed` - Session completed successfully
- `session.cancelled` - Session was cancelled
- `session.error` - Session encountered error
- `message.sent` - Message sent to session
- `message.received` - Response received from session
- `agent.task_assigned` - Task assigned to agent
- `agent.task_completed` - Agent completed task
- `checkpoint.created` - Checkpoint created
- `checkpoint.restored` - Checkpoint restored
- `analytics.threshold` - Analytics threshold reached

## Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup

```bash
# Fork and clone
git clone https://github.com/yourusername/shannon-mcp.git
cd shannon-mcp

# Install with uv including dev dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Create feature branch
git checkout -b feature/your-feature-name
```

### Contribution Process

1. **Check existing issues** or create a new one
2. **Fork the repository** and create a feature branch
3. **Write tests** for new functionality
4. **Implement changes** following code style
5. **Run tests** and ensure all pass
6. **Update documentation** as needed
7. **Submit pull request** with clear description

### Code Style

- Use Black for formatting (88 char line length)
- Follow PEP 8 guidelines
- Add type hints for all functions
- Write descriptive docstrings
- Keep functions focused and small
- Use meaningful variable names

### Testing Requirements

- Write unit tests for new functions
- Add integration tests for new features
- Maintain >90% code coverage
- Test edge cases and error conditions
- Use pytest fixtures for common setup

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastMCP](https://github.com/fastmcp/fastmcp) - High-performance MCP framework
- Implements [Model Context Protocol](https://modelcontextprotocol.io/) specification
- Integrates with [Claude Code CLI](https://claude.ai/code)
- Inspired by LSP and modern developer tools

## Support

- **Documentation**: [https://shannon-mcp.readthedocs.io/](https://shannon-mcp.readthedocs.io/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/shannon-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/shannon-mcp/discussions)
- **Discord**: [Join our community](https://discord.gg/shannon-mcp)

---

For more detailed information, see our [comprehensive documentation](docs/README.md).