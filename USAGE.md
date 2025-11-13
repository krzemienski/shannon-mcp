# Shannon MCP Server - User Guide

Complete guide to using Shannon MCP Server for programmatic management of Claude Code CLI operations.

## Table of Contents

- [Getting Started](#getting-started)
- [Using MCP Tools](#using-mcp-tools)
- [Accessing MCP Resources](#accessing-mcp-resources)
- [Advanced Features](#advanced-features)
- [Multi-Agent Collaboration](#multi-agent-collaboration)
- [Best Practices](#best-practices)
- [Examples and Recipes](#examples-and-recipes)

---

## Getting Started

### What is Shannon MCP Server?

Shannon MCP is a comprehensive Model Context Protocol (MCP) server that provides programmatic control over Claude Code CLI operations. It exposes 7 powerful tools, 3 resources, and a 26-agent collaboration system through the standardized MCP interface.

**Key Benefits:**
- **Programmatic Control**: Manage Claude Code sessions via API
- **Session Management**: Create, monitor, and control multiple sessions
- **AI Agent System**: Leverage 26 specialized agents for complex tasks
- **Real-time Streaming**: Stream Claude Code output in real-time
- **Advanced Features**: Checkpoints, hooks, and analytics

### Quick Start

#### 1. Installation

```bash
# Using pip
pip install shannon-mcp

# Using Poetry (recommended)
poetry add shannon-mcp

# From source
git clone https://github.com/yourusername/shannon-mcp
cd shannon-mcp
poetry install
```

#### 2. Configuration

Add to Claude Desktop configuration (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "python",
      "args": ["-m", "shannon_mcp"],
      "env": {
        "CLAUDE_CODE_BINARY": "/usr/local/bin/claude"
      }
    }
  }
}
```

#### 3. Verify Installation

In Claude Desktop or any MCP client, check available tools:

```python
# List all available tools
tools = await client.list_tools()
print(tools)
# Output: find_claude_binary, create_session, send_message, cancel_session,
#         list_sessions, list_agents, assign_task
```

### Core Concepts

#### MCP Tools
Tools are callable functions that perform actions:
- `find_claude_binary` - Discover Claude Code installation
- `create_session` - Start a new Claude Code session
- `send_message` - Send messages to active sessions
- `cancel_session` - Stop running sessions
- `list_sessions` - View all sessions
- `list_agents` - Browse available AI agents
- `assign_task` - Delegate tasks to specialized agents

#### MCP Resources
Resources provide read-only access to system state:
- `shannon://config` - Current configuration
- `shannon://agents` - Agent information
- `shannon://sessions` - Active session data

#### Multi-Agent System
26 specialized agents collaborate to handle complex tasks:
- **Core Architecture** (4 agents) - System design
- **Infrastructure** (7 agents) - Low-level components
- **Quality & Security** (6 agents) - Testing and validation
- **Specialized** (9 agents) - Domain-specific expertise

---

## Using MCP Tools

### find_claude_binary

**Purpose**: Automatically discover Claude Code installation on your system.

**Use Cases:**
- Verify Claude Code is installed
- Find the binary path for manual operations
- Check version compatibility
- Troubleshoot installation issues

#### Example 1: Basic Discovery

```python
# Discover Claude Code installation
result = await client.call_tool("find_claude_binary", {})

print(result)
# Output:
# {
#   "binary_path": "/usr/local/bin/claude",
#   "version": "0.1.2",
#   "source": "which"
# }
```

#### Example 2: With Claude Desktop

Simply ask Claude:

```
Can you find my Claude Code installation?
```

Claude will use the tool automatically and respond:

```
I found Claude Code installed at /usr/local/bin/claude (version 0.1.2).
It was discovered using the 'which' command method.
```

#### Expected Responses

**Success:**
```json
{
  "binary_path": "/usr/local/bin/claude",
  "version": "0.1.2",
  "source": "which|nvm|standard"
}
```

**Not Found:**
```json
{
  "error": "Claude Code not found",
  "searched_locations": [
    "/usr/local/bin",
    "/usr/bin",
    "~/.nvm/versions/node/*/bin"
  ]
}
```

---

### Session Management Tools

### create_session

**Purpose**: Start a new Claude Code session with a specific prompt and configuration.

**Use Cases:**
- Execute code generation tasks
- Run automated workflows
- Start interactive sessions
- Resume from checkpoints

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | Initial prompt for Claude |
| `model` | string | No | Model to use (default: claude-3-sonnet) |
| `checkpoint_id` | string | No | Resume from checkpoint |
| `context` | object | No | Additional context data |

#### Example 1: Simple Code Generation

```python
# Create a session for building a REST API
session = await client.call_tool("create_session", {
    "prompt": "Create a FastAPI REST API with user authentication",
    "model": "claude-3-sonnet"
})

print(session)
# Output:
# {
#   "session_id": "sess_abc123",
#   "state": "starting",
#   "created_at": "2025-11-13T10:30:00Z",
#   "model": "claude-3-sonnet"
# }
```

#### Example 2: Resume from Checkpoint

```python
# Resume a previous session from a checkpoint
session = await client.call_tool("create_session", {
    "prompt": "Continue implementation",
    "checkpoint_id": "ckpt_xyz789"
})
```

#### Example 3: With Custom Context

```python
# Create session with additional context
session = await client.call_tool("create_session", {
    "prompt": "Refactor the authentication module",
    "context": {
        "project_path": "/home/user/myproject",
        "target_files": ["auth.py", "models.py"],
        "requirements": ["Add OAuth2 support", "Improve error handling"]
    }
})
```

#### Example 4: With Claude Desktop

Natural language request:

```
Start a new Claude Code session to implement a Python CLI tool for managing
TODO lists with SQLite storage.
```

Claude automatically:
1. Calls `create_session` with appropriate parameters
2. Streams the output in real-time
3. Shows progress and results

---

### send_message

**Purpose**: Send a follow-up message to an active session (conversation continuation).

**Use Cases:**
- Continue conversations
- Provide feedback or corrections
- Add requirements
- Ask clarifying questions

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | ID of active session |
| `content` | string | Yes | Message content |
| `timeout` | number | No | Timeout in seconds |

#### Example 1: Basic Continuation

```python
# Send a follow-up message
await client.call_tool("send_message", {
    "session_id": "sess_abc123",
    "content": "Add error handling for network failures"
})
```

#### Example 2: With Timeout

```python
# Send message with custom timeout
await client.call_tool("send_message", {
    "session_id": "sess_abc123",
    "content": "Run all tests and fix any failures",
    "timeout": 300  # 5 minutes
})
```

#### Example 3: Multi-step Workflow

```python
# Create session
session = await client.call_tool("create_session", {
    "prompt": "Create a user registration form"
})

session_id = session["session_id"]

# Wait for initial response, then add requirements
await client.call_tool("send_message", {
    "session_id": session_id,
    "content": "Add email validation using regex"
})

# Add more requirements
await client.call_tool("send_message", {
    "session_id": session_id,
    "content": "Include password strength checker"
})

# Request tests
await client.call_tool("send_message", {
    "session_id": session_id,
    "content": "Write comprehensive tests for the form"
})
```

#### Example 4: Error Correction

```python
# Provide feedback on generated code
await client.call_tool("send_message", {
    "session_id": "sess_abc123",
    "content": """
    The authentication logic has a bug - it's not checking for expired tokens.
    Please add token expiration validation in the verify_token function.
    """
})
```

---

### cancel_session

**Purpose**: Stop a running session immediately.

**Use Cases:**
- Stop long-running operations
- Cancel incorrect workflows
- Free up resources
- Emergency stop

#### Example 1: Basic Cancellation

```python
# Cancel a session
await client.call_tool("cancel_session", {
    "session_id": "sess_abc123"
})

# Response:
# {"success": true}
```

#### Example 2: Bulk Cancellation

```python
# Cancel multiple sessions
sessions = await client.call_tool("list_sessions", {
    "state": "running"
})

for session in sessions:
    await client.call_tool("cancel_session", {
        "session_id": session["session_id"]
    })
```

---

### list_sessions

**Purpose**: View all sessions (active, completed, failed).

**Use Cases:**
- Monitor active sessions
- Review session history
- Debug issues
- Track resource usage

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `state` | string | No | Filter: running, completed, failed, cancelled |
| `limit` | integer | No | Max results (default: 100) |

#### Example 1: List All Sessions

```python
# Get all sessions
sessions = await client.call_tool("list_sessions", {})

print(sessions)
# Output:
# [
#   {
#     "session_id": "sess_abc123",
#     "state": "running",
#     "model": "claude-3-sonnet",
#     "created_at": "2025-11-13T10:30:00Z",
#     "prompt": "Create a REST API"
#   },
#   {
#     "session_id": "sess_def456",
#     "state": "completed",
#     "model": "claude-3-opus",
#     "created_at": "2025-11-13T09:15:00Z",
#     "completed_at": "2025-11-13T09:45:00Z"
#   }
# ]
```

#### Example 2: Filter by State

```python
# Get only running sessions
running = await client.call_tool("list_sessions", {
    "state": "running"
})

# Get failed sessions for debugging
failed = await client.call_tool("list_sessions", {
    "state": "failed"
})
```

#### Example 3: Recent Sessions

```python
# Get last 10 sessions
recent = await client.call_tool("list_sessions", {
    "limit": 10
})
```

#### Example 4: Session Dashboard

```python
# Create a simple dashboard
def print_dashboard():
    sessions = await client.call_tool("list_sessions", {})

    states = {"running": 0, "completed": 0, "failed": 0}
    for session in sessions:
        states[session["state"]] += 1

    print("=== Session Dashboard ===")
    print(f"Running:   {states['running']}")
    print(f"Completed: {states['completed']}")
    print(f"Failed:    {states['failed']}")
    print(f"Total:     {len(sessions)}")
```

---

### Agent System Tools

### list_agents

**Purpose**: Browse the 26 specialized AI agents available in Shannon MCP.

**Use Cases:**
- Discover agent capabilities
- Find the right agent for a task
- View agent categories
- Check agent status

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category |
| `status` | string | No | Filter by availability |
| `capability` | string | No | Filter by specific skill |

#### Example 1: List All Agents

```python
# Get all available agents
agents = await client.call_tool("list_agents", {})

print(f"Found {len(agents)} agents")
for agent in agents:
    print(f"- {agent['name']}: {agent['description']}")
```

Output:
```
Found 26 agents
- Architecture Agent: System design and architectural decisions
- Claude Code SDK Expert: Deep knowledge of Claude Code CLI
- Python MCP Server Expert: MCP protocol implementation specialist
- Database Storage Agent: SQLite optimization and CAS
...
```

#### Example 2: Filter by Category

```python
# Get Core Architecture agents
core_agents = await client.call_tool("list_agents", {
    "category": "core_architecture"
})

# Get Infrastructure agents
infra_agents = await client.call_tool("list_agents", {
    "category": "infrastructure"
})

# Get Quality & Security agents
quality_agents = await client.call_tool("list_agents", {
    "category": "quality_security"
})
```

#### Example 3: Search by Capability

```python
# Find agents with database expertise
db_agents = await client.call_tool("list_agents", {
    "capability": "database"
})

# Find testing experts
test_agents = await client.call_tool("list_agents", {
    "capability": "testing"
})

# Find security specialists
security_agents = await client.call_tool("list_agents", {
    "capability": "security"
})
```

#### Example 4: Agent Details

```python
# Get detailed agent information
agents = await client.call_tool("list_agents", {})

for agent in agents:
    print(f"\n=== {agent['name']} ===")
    print(f"Category: {agent['category']}")
    print(f"Description: {agent['description']}")
    print(f"Capabilities: {', '.join(agent['capabilities'])}")
    print(f"Status: {agent['status']}")
```

---

### assign_task

**Purpose**: Delegate a task to the most appropriate AI agent from the 26-agent system.

**Use Cases:**
- Complex multi-step implementations
- Specialized domain tasks
- Performance-critical operations
- Collaborative problem-solving

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `description` | string | Yes | Task description |
| `required_capabilities` | array | Yes | Required skills |
| `priority` | string | No | low, medium, high (default: medium) |
| `context` | object | No | Additional context |
| `timeout` | integer | No | Timeout in seconds |

#### Example 1: Database Schema Design

```python
# Assign database design to specialized agent
assignment = await client.call_tool("assign_task", {
    "description": """
        Design a database schema for a multi-tenant SaaS application with:
        - User management with roles
        - Subscription billing
        - Audit logging
        - Data isolation per tenant
    """,
    "required_capabilities": ["database", "architecture", "security"],
    "priority": "high"
})

print(assignment)
# Output:
# {
#   "task_id": "task_abc123",
#   "agent_id": "agent_database",
#   "agent_name": "Database Storage Agent",
#   "score": 0.95,
#   "estimated_duration": 1800,
#   "confidence": 0.92
# }
```

#### Example 2: Security Audit

```python
# Assign security audit to security specialist
assignment = await client.call_tool("assign_task", {
    "description": "Perform comprehensive security audit of authentication module",
    "required_capabilities": ["security", "testing", "code_review"],
    "context": {
        "files": ["auth.py", "middleware.py", "models.py"],
        "concerns": ["SQL injection", "XSS", "CSRF"]
    },
    "timeout": 3600
})
```

#### Example 3: Performance Optimization

```python
# Assign optimization to performance specialist
assignment = await client.call_tool("assign_task", {
    "description": """
        Optimize API response time. Current average: 500ms, target: <100ms.
        Investigate database queries, caching strategy, and async patterns.
    """,
    "required_capabilities": ["performance", "database", "async"],
    "priority": "high",
    "context": {
        "metrics": {
            "p50": 450,
            "p95": 680,
            "p99": 1200
        }
    }
})
```

#### Example 4: Full Implementation with Agents

```python
# Complex project using multiple agents

# 1. Architecture design
arch_task = await client.call_tool("assign_task", {
    "description": "Design microservices architecture for e-commerce platform",
    "required_capabilities": ["architecture", "distributed_systems"]
})

# 2. Database schema
db_task = await client.call_tool("assign_task", {
    "description": "Design database schemas for user, product, order services",
    "required_capabilities": ["database", "architecture"]
})

# 3. API implementation
api_task = await client.call_tool("assign_task", {
    "description": "Implement RESTful APIs for all microservices",
    "required_capabilities": ["api_design", "python", "async"]
})

# 4. Testing strategy
test_task = await client.call_tool("assign_task", {
    "description": "Create comprehensive test suite with >90% coverage",
    "required_capabilities": ["testing", "quality_assurance"]
})

# 5. Security hardening
sec_task = await client.call_tool("assign_task", {
    "description": "Implement security best practices across all services",
    "required_capabilities": ["security", "authentication"]
})
```

---

## Accessing MCP Resources

Resources provide read-only access to Shannon MCP's internal state.

### shannon://config

**Purpose**: Access current configuration settings.

**Contains:**
- Binary manager settings
- Session manager configuration
- Agent system settings
- Hooks and checkpoint configuration
- Transport settings

#### Example 1: Read Configuration

```python
# Access configuration
config = await client.read_resource("shannon://config")
config_data = json.loads(config)

print(config_data)
# Output:
# {
#   "version": "0.1.0",
#   "binary_manager": {
#     "search_paths": ["/usr/local/bin", "/usr/bin"],
#     "cache_duration": 3600
#   },
#   "session_manager": {
#     "max_concurrent_sessions": 10,
#     "default_timeout": 300
#   },
#   "agent_manager": {
#     "enabled": true,
#     "agent_count": 26
#   }
# }
```

#### Example 2: Check Settings

```python
# Check specific settings
config = json.loads(await client.read_resource("shannon://config"))

print(f"Max concurrent sessions: {config['session_manager']['max_concurrent_sessions']}")
print(f"Agent system enabled: {config['agent_manager']['enabled']}")
print(f"Cache duration: {config['binary_manager']['cache_duration']}s")
```

---

### shannon://agents

**Purpose**: Access detailed information about all 26 AI agents.

**Contains:**
- Agent names and descriptions
- Capabilities and expertise
- Category and status
- Performance metrics
- Success rates

#### Example 1: View All Agents

```python
# Get agent information
agents = await client.read_resource("shannon://agents")
agents_data = json.loads(agents)

for agent in agents_data:
    print(f"{agent['name']} ({agent['category']})")
    print(f"  Capabilities: {', '.join(agent['capabilities'])}")
    print(f"  Success rate: {agent['metrics']['success_rate']}%")
    print()
```

#### Example 2: Find Specialists

```python
# Find agents by capability
agents = json.loads(await client.read_resource("shannon://agents"))

# Find database experts
db_experts = [a for a in agents if "database" in a['capabilities']]

# Find security specialists
security_experts = [a for a in agents if "security" in a['capabilities']]

print("Database Experts:")
for agent in db_experts:
    print(f"- {agent['name']}")

print("\nSecurity Specialists:")
for agent in security_experts:
    print(f"- {agent['name']}")
```

#### Example 3: Agent Performance Dashboard

```python
# Create performance dashboard
agents = json.loads(await client.read_resource("shannon://agents"))

print("=== Agent Performance Dashboard ===\n")

# Group by category
by_category = {}
for agent in agents:
    cat = agent['category']
    if cat not in by_category:
        by_category[cat] = []
    by_category[cat].append(agent)

for category, agents_list in by_category.items():
    print(f"{category.upper()}:")
    for agent in agents_list:
        metrics = agent['metrics']
        print(f"  - {agent['name']}")
        print(f"    Success: {metrics['success_rate']}% | "
              f"Avg time: {metrics['avg_duration']}s | "
              f"Tasks: {metrics['total_tasks']}")
    print()
```

---

### shannon://sessions

**Purpose**: Access active session data and statistics.

**Contains:**
- Session IDs and states
- Creation and completion times
- Model information
- Resource usage
- Message counts

#### Example 1: Monitor Active Sessions

```python
# Get session data
sessions = await client.read_resource("shannon://sessions")
sessions_data = json.loads(sessions)

print(f"Active sessions: {len(sessions_data)}\n")

for session in sessions_data:
    print(f"Session {session['session_id']}")
    print(f"  State: {session['state']}")
    print(f"  Model: {session['model']}")
    print(f"  Started: {session['created_at']}")
    print(f"  Messages: {session['message_count']}")
    print()
```

#### Example 2: Session Statistics

```python
# Calculate session statistics
sessions = json.loads(await client.read_resource("shannon://sessions"))

states = {}
models = {}
total_messages = 0

for session in sessions:
    # Count by state
    state = session['state']
    states[state] = states.get(state, 0) + 1

    # Count by model
    model = session['model']
    models[model] = models.get(model, 0) + 1

    # Sum messages
    total_messages += session.get('message_count', 0)

print("=== Session Statistics ===")
print(f"\nBy State:")
for state, count in states.items():
    print(f"  {state}: {count}")

print(f"\nBy Model:")
for model, count in models.items():
    print(f"  {model}: {count}")

print(f"\nTotal Messages: {total_messages}")
```

---

## Advanced Features

### Checkpoint System

The checkpoint system provides Git-like versioning for Claude Code sessions, allowing you to save, restore, and branch your work.

#### Concepts

- **Checkpoint**: A snapshot of your project at a specific point in time
- **Content-Addressable Storage (CAS)**: Efficient deduplication using SHA-256 hashes
- **Timeline**: Relationship graph between checkpoints
- **Branching**: Create alternate development paths

#### Example 1: Create Manual Checkpoint

```python
# Create checkpoint before major changes
from datetime import datetime

checkpoint = await checkpoint_manager.create_checkpoint(
    project_path="/home/user/myproject",
    message="Before refactoring authentication system",
    include_files=["auth.py", "models.py", "tests/test_auth.py"]
)

print(f"Created checkpoint: {checkpoint.id}")
print(f"Files captured: {len(checkpoint.files)}")
print(f"Total size: {checkpoint.total_size_bytes} bytes")
```

#### Example 2: Restore from Checkpoint

```python
# Restore to previous state
result = await checkpoint_manager.restore_checkpoint(
    project_path="/home/user/myproject",
    checkpoint_id="ckpt_abc123",
    create_backup=True  # Create backup before restoring
)

print(f"Restored {result.restored_files} files")
print(f"Backup created: {result.backup_id}")
```

#### Example 3: Automatic Checkpoints

Shannon MCP automatically creates checkpoints at key points:

```python
# Automatic checkpoint triggers:
# 1. Before major file operations
# 2. At session completion
# 3. Before dangerous operations

# Enable automatic checkpoints in config
config = {
    "checkpoint_manager": {
        "auto_checkpoint": True,
        "auto_checkpoint_interval": 300,  # Every 5 minutes
        "triggers": [
            "session_start",
            "before_file_write",
            "session_complete"
        ]
    }
}
```

#### Example 4: Checkpoint Workflow

```python
# Complete checkpoint workflow

# 1. Create initial checkpoint
initial = await checkpoint_manager.create_checkpoint(
    project_path="/home/user/project",
    message="Initial state"
)

# 2. Start development session
session = await client.call_tool("create_session", {
    "prompt": "Refactor the user authentication module",
    "checkpoint_id": initial.id
})

# 3. Work continues...

# 4. Create checkpoint after successful changes
success = await checkpoint_manager.create_checkpoint(
    project_path="/home/user/project",
    message="Refactoring complete - all tests passing"
)

# 5. If issues arise, restore to previous checkpoint
if issues_found:
    await checkpoint_manager.restore_checkpoint(
        project_path="/home/user/project",
        checkpoint_id=initial.id
    )
```

#### Example 5: Branch Management

```python
# Create development branches with checkpoints

# Main branch checkpoint
main_checkpoint = await checkpoint_manager.create_checkpoint(
    project_path="/home/user/project",
    message="Stable main branch"
)

# Experiment branch
experiment_checkpoint = await checkpoint_manager.create_checkpoint(
    project_path="/home/user/project",
    message="Experimental feature branch",
    parent_id=main_checkpoint.id
)

# Work on experiment
session = await client.call_tool("create_session", {
    "prompt": "Try implementing feature X",
    "checkpoint_id": experiment_checkpoint.id
})

# If successful, merge by creating new checkpoint
if experiment_successful:
    merged = await checkpoint_manager.create_checkpoint(
        project_path="/home/user/project",
        message="Merged experimental feature",
        parent_id=main_checkpoint.id
    )
else:
    # Discard experiment, restore main
    await checkpoint_manager.restore_checkpoint(
        project_path="/home/user/project",
        checkpoint_id=main_checkpoint.id
    )
```

---

### Hooks Framework

Hooks enable automated workflows triggered by Claude Code events.

#### Hook Types

- **PreToolUse**: Before Claude uses a tool
- **PostToolUse**: After successful tool execution
- **Notification**: On Claude notifications
- **Stop**: On session stop
- **SubagentStop**: On subagent termination
- **UserPromptSubmit**: When user submits prompt

#### Example 1: Auto-format on Save

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "prettier --write \"$CLAUDE_FILE_PATHS\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Usage with Shannon MCP:

```python
# Configure auto-formatting hook
await hooks_manager.update_config(
    scope="project",
    project_path="/home/user/project",
    config={
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "black $CLAUDE_FILE_PATHS"
                        }
                    ]
                }
            ]
        }
    }
)
```

#### Example 2: Run Tests After Changes

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "pytest tests/ -v",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

#### Example 3: Notify on Completion

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Claude Code' 'Session completed successfully'"
          }
        ]
      }
    ]
  }
}
```

#### Example 4: Build Pipeline Hook

```python
# Complete build pipeline
await hooks_manager.update_config(
    scope="project",
    project_path="/home/user/project",
    config={
        "hooks": {
            # Format code
            "PostToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "black $CLAUDE_FILE_PATHS && isort $CLAUDE_FILE_PATHS"
                        }
                    ]
                }
            ],
            # Run tests
            "PostToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "pytest tests/ --cov=. --cov-report=html",
                            "timeout": 300
                        }
                    ]
                }
            ],
            # Build documentation
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "mkdocs build"
                        }
                    ]
                }
            ]
        }
    }
)
```

#### Available Hook Variables

```bash
$CLAUDE_HOOK_TYPE          # Type of hook (PreToolUse, PostToolUse, etc.)
$CLAUDE_PROJECT_PATH       # Project directory path
$CLAUDE_PROJECT_DIR        # Alias for project path
$CLAUDE_SESSION_ID         # Current session ID
$CLAUDE_TOOL_NAME          # Tool being used (Edit, Write, etc.)
$CLAUDE_FILE_PATHS         # Space-separated file paths
$CLAUDE_MESSAGE            # JSON-encoded message data
```

---

### Analytics and Monitoring

Track usage, performance, and costs across all Claude Code sessions.

#### Example 1: Daily Usage Report

```python
# Get usage analytics for last 7 days
from datetime import datetime, timedelta

report = await analytics_manager.get_usage_report(
    start_date=datetime.now() - timedelta(days=7),
    end_date=datetime.now(),
    group_by="day"
)

print("=== 7-Day Usage Report ===\n")
for day in report.daily_stats:
    print(f"{day.date}:")
    print(f"  Sessions: {day.session_count}")
    print(f"  Input tokens: {day.input_tokens:,}")
    print(f"  Output tokens: {day.output_tokens:,}")
    print(f"  Cost: ${day.total_cost:.2f}")
    print()

print(f"Total Cost: ${report.total_cost:.2f}")
```

#### Example 2: Model Comparison

```python
# Compare usage by model
report = await analytics_manager.get_usage_report(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    group_by="model"
)

print("=== Model Usage (30 days) ===\n")
for model_stat in report.model_stats:
    print(f"{model_stat.model}:")
    print(f"  Sessions: {model_stat.session_count}")
    print(f"  Avg tokens/session: {model_stat.avg_tokens:.0f}")
    print(f"  Cost: ${model_stat.total_cost:.2f}")
    print()
```

#### Example 3: Project Analytics

```python
# Analyze usage by project
report = await analytics_manager.get_usage_report(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    group_by="project"
)

print("=== Project Usage (30 days) ===\n")
projects_sorted = sorted(
    report.project_stats,
    key=lambda x: x.total_cost,
    reverse=True
)

for project in projects_sorted[:10]:  # Top 10
    print(f"{project.project_name}:")
    print(f"  Sessions: {project.session_count}")
    print(f"  Duration: {project.total_duration/3600:.1f} hours")
    print(f"  Cost: ${project.total_cost:.2f}")
    print()
```

#### Example 4: Export Analytics

```python
# Export usage data to CSV
await analytics_manager.export_usage_report(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    format="csv",
    output_path="/home/user/reports/usage_report.csv"
)

# Export to JSON
await analytics_manager.export_usage_report(
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    format="json",
    output_path="/home/user/reports/usage_report.json"
)
```

#### Example 5: Real-time Monitoring

```python
# Monitor active sessions in real-time
async def monitor_sessions():
    while True:
        sessions = await client.call_tool("list_sessions", {
            "state": "running"
        })

        print(f"\r{len(sessions)} active sessions", end="", flush=True)

        # Check resource usage
        for session in sessions:
            if session.get('duration_seconds', 0) > 300:
                print(f"\nWarning: Session {session['session_id']} "
                      f"running for {session['duration_seconds']}s")

        await asyncio.sleep(5)
```

---

## Multi-Agent Collaboration

Shannon MCP employs 26 specialized AI agents working together to handle complex tasks.

### Agent Categories

#### Core Architecture Agents (4)

**1. Architecture Agent**
- System design and architectural decisions
- Component interfaces and data flow
- Scalability and maintainability

```python
# Assign architecture task
assignment = await client.call_tool("assign_task", {
    "description": "Design microservices architecture for payment processing",
    "required_capabilities": ["architecture", "distributed_systems", "scalability"]
})
```

**2. Claude Code SDK Expert**
- Claude Code CLI internals
- SDK patterns and integration
- Command construction and parsing

```python
# Assign Claude Code integration task
assignment = await client.call_tool("assign_task", {
    "description": "Implement advanced Claude Code CLI integration with custom flags",
    "required_capabilities": ["claude_code", "sdk", "cli"]
})
```

**3. Python MCP Server Expert**
- MCP protocol specification
- FastMCP framework
- JSON-RPC communication

```python
# Assign MCP implementation task
assignment = await client.call_tool("assign_task", {
    "description": "Implement custom MCP tools with streaming support",
    "required_capabilities": ["mcp", "protocol", "json_rpc"]
})
```

**4. Functional MCP Server Agent**
- Business logic implementation
- User workflow optimization
- Feature integration

```python
# Assign feature implementation
assignment = await client.call_tool("assign_task", {
    "description": "Implement user authentication with OAuth2 and JWT",
    "required_capabilities": ["api", "authentication", "oauth"]
})
```

#### Infrastructure Agents (7)

**5. Database Storage Agent**
- SQLite optimization
- Content-addressable storage
- Data integrity

**6. Streaming Concurrency Agent**
- Async patterns
- Stream processing
- Backpressure handling

**7. JSONL Streaming Agent**
- Real-time JSONL parsing
- Buffer management
- Error recovery

**8. Process Management Agent**
- System process monitoring
- Resource tracking
- PID management

**9. Filesystem Monitor Agent**
- File system change detection
- Event filtering
- Cross-platform support

**10. Platform Compatibility Agent**
- Cross-platform support
- OS-specific handlers
- Path conventions

**11. Storage Algorithms Agent**
- Content-addressable storage
- Compression optimization
- Deduplication

#### Quality & Security Agents (6)

**12. Security Validation Agent**
- Input validation
- Command injection prevention
- Secret management

**13. Testing Quality Agent**
- Test implementation
- Coverage analysis
- Performance benchmarking

**14. Error Handling Agent**
- Error recovery
- User-friendly messages
- Logging strategies

**15. Performance Optimizer Agent**
- Performance profiling
- Optimization strategies
- Caching implementation

**16. Documentation Agent**
- API documentation
- Usage examples
- Tutorials

**17. DevOps Deployment Agent**
- CI/CD pipelines
- Deployment automation
- Release management

#### Specialized Agents (9)

**18. Telemetry OpenTelemetry Agent**
- Observability implementation
- Metrics collection
- Distributed tracing

**19. Analytics Monitoring Agent**
- Usage analytics
- Report generation
- Data visualization

**20. Integration Specialist Agent**
- Third-party integrations
- API clients
- OAuth flows

**21. Project Coordinator Agent**
- Project management
- Task coordination
- Progress tracking

**22. Migration Specialist Agent**
- Database migrations
- Config migrations
- Version upgrades

**23. SSE Transport Agent**
- Server-Sent Events
- Real-time connections
- Reconnection handling

**24. Resources Specialist Agent**
- MCP resource exposure
- Data serialization
- Access patterns

**25. Prompts Engineer Agent**
- Prompt templates
- Context optimization
- Response parsing

**26. Plugin Architect Agent**
- Plugin system design
- Extension points
- API design

### Multi-Agent Workflows

#### Example 1: Full-Stack Application

```python
# Build complete application with multiple agents

# 1. Architecture design
arch = await client.call_tool("assign_task", {
    "description": "Design architecture for e-commerce platform",
    "required_capabilities": ["architecture", "microservices"]
})

# 2. Database design
db = await client.call_tool("assign_task", {
    "description": "Design database schemas for all services",
    "required_capabilities": ["database", "modeling"]
})

# 3. API implementation
api = await client.call_tool("assign_task", {
    "description": "Implement RESTful APIs for product catalog",
    "required_capabilities": ["api", "rest", "python"]
})

# 4. Security implementation
security = await client.call_tool("assign_task", {
    "description": "Implement authentication and authorization",
    "required_capabilities": ["security", "oauth", "jwt"]
})

# 5. Testing
testing = await client.call_tool("assign_task", {
    "description": "Create comprehensive test suite",
    "required_capabilities": ["testing", "pytest", "integration"]
})

# 6. Deployment
deploy = await client.call_tool("assign_task", {
    "description": "Set up CI/CD pipeline with Docker",
    "required_capabilities": ["devops", "docker", "github_actions"]
})
```

#### Example 2: Performance Optimization Project

```python
# Multi-agent performance optimization

# 1. Profiling
profile = await client.call_tool("assign_task", {
    "description": "Profile application and identify bottlenecks",
    "required_capabilities": ["performance", "profiling"]
})

# 2. Database optimization
db_opt = await client.call_tool("assign_task", {
    "description": "Optimize database queries and indexes",
    "required_capabilities": ["database", "performance", "sql"]
})

# 3. Caching strategy
cache = await client.call_tool("assign_task", {
    "description": "Implement multi-layer caching strategy",
    "required_capabilities": ["caching", "redis", "architecture"]
})

# 4. Async optimization
async_opt = await client.call_tool("assign_task", {
    "description": "Optimize async patterns and concurrency",
    "required_capabilities": ["async", "concurrency", "python"]
})

# 5. Monitoring
monitor = await client.call_tool("assign_task", {
    "description": "Set up performance monitoring and alerting",
    "required_capabilities": ["monitoring", "telemetry", "prometheus"]
})
```

---

## Best Practices

### Session Management Patterns

#### 1. Use Descriptive Prompts

```python
# Bad
session = await client.call_tool("create_session", {
    "prompt": "make api"
})

# Good
session = await client.call_tool("create_session", {
    "prompt": """
    Create a RESTful API for user management with the following requirements:
    - CRUD operations for users
    - JWT authentication
    - Input validation with Pydantic
    - Async SQLAlchemy for database
    - Comprehensive error handling
    - OpenAPI documentation
    """
})
```

#### 2. Monitor Long-Running Sessions

```python
# Set appropriate timeouts
session = await client.call_tool("create_session", {
    "prompt": "Large refactoring task",
    "timeout": 600  # 10 minutes
})

# Monitor progress
async def monitor_session(session_id):
    while True:
        sessions = await client.call_tool("list_sessions", {})
        session = next((s for s in sessions if s['session_id'] == session_id), None)

        if not session or session['state'] != 'running':
            break

        print(f"Session still running: {session.get('duration_seconds', 0)}s")
        await asyncio.sleep(10)
```

#### 3. Handle Errors Gracefully

```python
try:
    session = await client.call_tool("create_session", {
        "prompt": "Complex task"
    })
except Exception as e:
    logger.error(f"Session creation failed: {e}")
    # Fallback logic
    session = await client.call_tool("create_session", {
        "prompt": "Simpler alternative task"
    })
```

### Error Handling

#### 1. Retry Logic

```python
async def create_session_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await client.call_tool("create_session", {
                "prompt": prompt
            })
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

#### 2. Graceful Degradation

```python
# Try with preferred model, fall back to alternatives
models = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]

for model in models:
    try:
        session = await client.call_tool("create_session", {
            "prompt": prompt,
            "model": model
        })
        break
    except Exception as e:
        logger.warning(f"Failed with {model}: {e}")
        continue
else:
    raise Exception("All models failed")
```

### Performance Optimization

#### 1. Batch Operations

```python
# Create multiple sessions in parallel
async def create_sessions_parallel(prompts):
    tasks = [
        client.call_tool("create_session", {"prompt": p})
        for p in prompts
    ]
    return await asyncio.gather(*tasks)

sessions = await create_sessions_parallel([
    "Task 1",
    "Task 2",
    "Task 3"
])
```

#### 2. Use Checkpoints Strategically

```python
# Create checkpoints at key milestones
milestones = [
    "Initial setup complete",
    "Core features implemented",
    "Tests passing",
    "Production ready"
]

for milestone in milestones:
    # Work...
    checkpoint = await checkpoint_manager.create_checkpoint(
        project_path=project_path,
        message=milestone
    )
    logger.info(f"Checkpoint created: {checkpoint.id}")
```

#### 3. Optimize Agent Selection

```python
# Be specific with capabilities to get best agent match
assignment = await client.call_tool("assign_task", {
    "description": task_description,
    "required_capabilities": [
        "specific_skill_1",
        "specific_skill_2",
        "specific_skill_3"
    ],  # More specific = better match
    "priority": "high"
})
```

### Security Considerations

#### 1. Validate Input

```python
# Validate prompts before sending
def validate_prompt(prompt: str) -> bool:
    # Check for dangerous patterns
    dangerous_patterns = [
        "rm -rf",
        "sudo",
        "exec",
        "eval"
    ]
    return not any(p in prompt.lower() for p in dangerous_patterns)

if validate_prompt(prompt):
    session = await client.call_tool("create_session", {"prompt": prompt})
else:
    raise ValueError("Prompt contains dangerous patterns")
```

#### 2. Limit Session Duration

```python
# Set maximum session duration
MAX_SESSION_DURATION = 1800  # 30 minutes

session = await client.call_tool("create_session", {
    "prompt": prompt,
    "timeout": MAX_SESSION_DURATION
})
```

#### 3. Use Hooks for Validation

```python
# Validate files before writing
await hooks_manager.update_config(
    scope="project",
    project_path=project_path,
    config={
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python validate_content.py $CLAUDE_FILE_PATHS"
                        }
                    ]
                }
            ]
        }
    }
)
```

---

## Examples and Recipes

### Recipe 1: Automated Code Review

```python
async def automated_code_review(files: List[str]):
    """Perform automated code review using specialized agents."""

    # 1. Assign to security agent
    security_review = await client.call_tool("assign_task", {
        "description": f"Security review of: {', '.join(files)}",
        "required_capabilities": ["security", "code_review"],
        "context": {"files": files}
    })

    # 2. Assign to performance agent
    perf_review = await client.call_tool("assign_task", {
        "description": f"Performance review of: {', '.join(files)}",
        "required_capabilities": ["performance", "optimization"],
        "context": {"files": files}
    })

    # 3. Assign to testing agent
    test_review = await client.call_tool("assign_task", {
        "description": f"Test coverage review of: {', '.join(files)}",
        "required_capabilities": ["testing", "quality"],
        "context": {"files": files}
    })

    return {
        "security": security_review,
        "performance": perf_review,
        "testing": test_review
    }
```

### Recipe 2: Progressive Enhancement

```python
async def progressive_feature_development(feature_spec: str):
    """Develop feature with checkpoints at each stage."""

    stages = [
        ("Basic implementation", "basic"),
        ("Add error handling", "error_handling"),
        ("Add input validation", "validation"),
        ("Add comprehensive tests", "tests"),
        ("Optimize performance", "optimized"),
        ("Add documentation", "documented")
    ]

    checkpoints = []

    for stage_name, stage_id in stages:
        # Create session for this stage
        session = await client.call_tool("create_session", {
            "prompt": f"{feature_spec}\n\nStage: {stage_name}",
            "checkpoint_id": checkpoints[-1] if checkpoints else None
        })

        # Wait for completion
        await wait_for_session_completion(session['session_id'])

        # Create checkpoint
        checkpoint = await checkpoint_manager.create_checkpoint(
            project_path=project_path,
            message=f"{stage_name} complete"
        )
        checkpoints.append(checkpoint.id)

        print(f"✓ {stage_name} complete (checkpoint: {checkpoint.id})")

    return checkpoints
```

### Recipe 3: Multi-Service Development

```python
async def develop_microservices(services: List[Dict]):
    """Develop multiple microservices in parallel."""

    async def develop_service(service_spec):
        # Architecture
        arch = await client.call_tool("assign_task", {
            "description": f"Design architecture for {service_spec['name']}",
            "required_capabilities": ["architecture", "microservices"]
        })

        # Database
        db = await client.call_tool("assign_task", {
            "description": f"Design database for {service_spec['name']}",
            "required_capabilities": ["database"]
        })

        # Implementation
        impl = await client.call_tool("create_session", {
            "prompt": f"Implement {service_spec['name']} service: {service_spec['description']}"
        })

        # Tests
        tests = await client.call_tool("assign_task", {
            "description": f"Create tests for {service_spec['name']}",
            "required_capabilities": ["testing"]
        })

        return {
            "service": service_spec['name'],
            "architecture": arch,
            "database": db,
            "implementation": impl,
            "tests": tests
        }

    # Develop all services in parallel
    results = await asyncio.gather(*[
        develop_service(service)
        for service in services
    ])

    return results
```

### Recipe 4: Continuous Testing Pipeline

```python
async def setup_continuous_testing():
    """Set up automated testing pipeline with hooks."""

    # Configure hooks for automatic testing
    await hooks_manager.update_config(
        scope="project",
        project_path=project_path,
        config={
            "hooks": {
                # Format code
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "black $CLAUDE_FILE_PATHS && isort $CLAUDE_FILE_PATHS"
                            }
                        ]
                    }
                ],
                # Run linters
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "flake8 $CLAUDE_FILE_PATHS && mypy $CLAUDE_FILE_PATHS"
                            }
                        ]
                    }
                ],
                # Run tests
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "pytest tests/ -v --cov=. --cov-report=html",
                                "timeout": 300
                            }
                        ]
                    }
                ],
                # Generate report
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python generate_test_report.py"
                            }
                        ]
                    }
                ]
            }
        }
    )
```

### Recipe 5: Smart Rollback System

```python
async def smart_rollback_system():
    """Implement intelligent rollback based on test results."""

    # Create initial checkpoint
    baseline = await checkpoint_manager.create_checkpoint(
        project_path=project_path,
        message="Baseline - all tests passing"
    )

    # Development session
    session = await client.call_tool("create_session", {
        "prompt": "Implement new feature X"
    })

    await wait_for_session_completion(session['session_id'])

    # Run tests
    test_result = await run_tests()

    if test_result['failed'] > 0:
        # Tests failed - automatic rollback
        print(f"Tests failed ({test_result['failed']} failures)")
        print("Rolling back to baseline...")

        await checkpoint_manager.restore_checkpoint(
            project_path=project_path,
            checkpoint_id=baseline.id
        )

        # Create session to fix issues
        fix_session = await client.call_tool("create_session", {
            "prompt": f"""
            The previous implementation failed {test_result['failed']} tests.
            Failures: {test_result['failure_details']}

            Please fix these issues.
            """,
            "checkpoint_id": baseline.id
        })
    else:
        # Tests passed - create new checkpoint
        print(f"All {test_result['passed']} tests passed!")

        success_checkpoint = await checkpoint_manager.create_checkpoint(
            project_path=project_path,
            message="Feature X complete - all tests passing"
        )
```

### Recipe 6: Resource Monitoring Dashboard

```python
async def resource_monitoring_dashboard():
    """Create real-time monitoring dashboard."""

    import time
    from rich.console import Console
    from rich.table import Table

    console = Console()

    while True:
        console.clear()

        # Get sessions
        sessions = json.loads(await client.read_resource("shannon://sessions"))

        # Get agents
        agents = json.loads(await client.read_resource("shannon://agents"))

        # Get config
        config = json.loads(await client.read_resource("shannon://config"))

        # Create sessions table
        sessions_table = Table(title="Active Sessions")
        sessions_table.add_column("ID")
        sessions_table.add_column("State")
        sessions_table.add_column("Model")
        sessions_table.add_column("Duration")

        for session in sessions:
            sessions_table.add_row(
                session['session_id'][:8],
                session['state'],
                session['model'],
                f"{session.get('duration_seconds', 0)}s"
            )

        # Create agents table
        agents_table = Table(title="Agent Status")
        agents_table.add_column("Agent")
        agents_table.add_column("Category")
        agents_table.add_column("Status")
        agents_table.add_column("Tasks")

        for agent in agents[:10]:  # Top 10
            agents_table.add_row(
                agent['name'][:20],
                agent['category'],
                agent['status'],
                str(agent['metrics']['total_tasks'])
            )

        # Display
        console.print(sessions_table)
        console.print()
        console.print(agents_table)
        console.print()
        console.print(f"Max Sessions: {config['session_manager']['max_concurrent_sessions']}")
        console.print(f"Agent Count: {len(agents)}")

        await asyncio.sleep(5)
```

### Recipe 7: Batch Processing Pipeline

```python
async def batch_processing_pipeline(tasks: List[str]):
    """Process multiple tasks in parallel with rate limiting."""

    from asyncio import Semaphore

    # Rate limiting
    max_concurrent = 5
    semaphore = Semaphore(max_concurrent)

    async def process_task(task):
        async with semaphore:
            session = await client.call_tool("create_session", {
                "prompt": task
            })

            # Wait for completion
            while True:
                sessions = await client.call_tool("list_sessions", {})
                session_data = next(
                    (s for s in sessions if s['session_id'] == session['session_id']),
                    None
                )

                if not session_data or session_data['state'] != 'running':
                    break

                await asyncio.sleep(5)

            return session_data

    # Process all tasks
    results = await asyncio.gather(*[
        process_task(task)
        for task in tasks
    ])

    # Generate report
    successful = [r for r in results if r and r['state'] == 'completed']
    failed = [r for r in results if r and r['state'] == 'failed']

    print(f"Completed: {len(successful)}/{len(tasks)}")
    print(f"Failed: {len(failed)}/{len(tasks)}")

    return {
        "successful": successful,
        "failed": failed
    }
```

---

## Additional Resources

### Environment Variables

```bash
# Binary discovery
export CLAUDE_CODE_BINARY=/path/to/claude

# Session configuration
export SHANNON_MAX_SESSIONS=10
export SHANNON_SESSION_TIMEOUT=600

# Agent system
export SHANNON_ENABLE_AGENTS=true
export SHANNON_AGENT_TIMEOUT=1800

# Analytics
export SHANNON_ENABLE_ANALYTICS=true
export SHANNON_ANALYTICS_PATH=~/.shannon/analytics

# Debugging
export SHANNON_LOG_LEVEL=DEBUG
export SHANNON_DEBUG=true
```

### Configuration File

Location: `~/.shannon/config.json`

```json
{
  "version": "0.1.0",
  "binary_manager": {
    "search_paths": ["/usr/local/bin", "/usr/bin"],
    "cache_duration": 3600
  },
  "session_manager": {
    "max_concurrent_sessions": 10,
    "default_timeout": 300,
    "auto_checkpoint": true
  },
  "agent_manager": {
    "enabled": true,
    "max_concurrent_tasks": 5
  },
  "checkpoint_manager": {
    "auto_checkpoint": true,
    "compression_level": 3,
    "gc_enabled": true
  },
  "hooks": {
    "enabled": true,
    "scope": "project"
  },
  "analytics": {
    "enabled": true,
    "retention_days": 90
  }
}
```

### Support and Documentation

- **GitHub**: https://github.com/yourusername/shannon-mcp
- **Documentation**: https://shannon-mcp.readthedocs.io
- **Issues**: https://github.com/yourusername/shannon-mcp/issues
- **Discord**: https://discord.gg/shannon-mcp

### Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### License

MIT License - See [LICENSE](LICENSE) file for details.

---

**Shannon MCP Server** - Empowering developers with programmatic Claude Code control.
