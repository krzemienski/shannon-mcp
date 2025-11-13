# Shannon MCP - Python Agents SDK Integration Guide

## Overview

Shannon MCP now integrates with the official **Python Agents SDK** from Anthropic, providing advanced agent orchestration capabilities including subagents, Agent Skills, and automatic context management.

## Installation

### Prerequisites

- Python 3.11+
- Node.js 16+ (required by SDK)
- Claude Code 2.0.0+

### Install Dependencies

```bash
# Install Shannon MCP with SDK support
poetry install

# Verify SDK is available
python -c "from claude_agent_sdk import query; print('SDK available')"
```

## Quick Start

### 1. Configuration

Create or update your `config.yaml`:

```yaml
version: "0.2.0"

# Agent SDK Configuration
agent_sdk:
  enabled: true
  agents_directory: ~/.claude/agents
  use_subagents: true
  max_subagents_per_task: 5
  permission_mode: acceptEdits
  allowed_tools:
    - Read
    - Write
    - Bash
  execution_timeout: 300
  max_concurrent_agents: 10
```

### 2. Initialize SDK Adapter

```python
from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter
from shannon_mcp.utils.config import ShannonConfig

# Load configuration
config = ShannonConfig()

# Initialize SDK adapter
adapter = AgentSDKAdapter(config.agent_sdk)
await adapter.initialize()

print(f"Loaded {len(adapter.sdk_agents)} SDK agents")
```

### 3. Create SDK Agents

Create agent files in `~/.claude/agents/`:

```markdown
---
id: my_custom_agent
name: My Custom Agent
category: specialized
capabilities: ["python", "testing", "documentation"]
description: A custom agent for Python development
version: 1.0.0
use_subagents: false
---

You are an expert Python developer specializing in testing and documentation.

## Capabilities

- **python**: Expert Python programming
- **testing**: Write pytest tests
- **documentation**: Create clear docs

## Responsibilities

Help developers write high-quality Python code with good tests and documentation.
```

### 4. Migrate Existing Agents

```bash
# Migrate all agents
python scripts/migrate_agents_to_sdk.py --all --validate

# Migrate specific agent
python scripts/migrate_agents_to_sdk.py --agent-id agent_architecture_agent

# Preview migration (dry run)
python scripts/migrate_agents_to_sdk.py --all --dry-run
```

## Features

### Simple Task Execution

For one-off tasks without state:

```python
from shannon_mcp.adapters.agent_sdk import (
    SDKExecutionRequest,
    ExecutionMode,
)

request = SDKExecutionRequest(
    agent_id="my_custom_agent",
    task_id="task_001",
    task_description="Write a function to calculate fibonacci numbers",
    required_capabilities=["python"],
    execution_mode=ExecutionMode.SIMPLE,
)

# Execute and stream results
async for result in adapter.execute_simple_task(sdk_agent, request):
    print(result["message"])
```

### Complex Tasks with Subagents

For multi-step tasks requiring parallel execution:

```python
request = SDKExecutionRequest(
    agent_id="architecture_agent",
    task_id="task_002",
    task_description="Design and implement a REST API with tests",
    required_capabilities=["system_design", "python", "testing"],
    execution_mode=ExecutionMode.COMPLEX,
    use_subagents=True,
)

# Execute with automatic subagent spawning
result = await adapter.execute_complex_task(sdk_agent, request, use_subagents=True)

print(f"Task completed with {result.subagent_count} subagents")
print(f"Execution time: {result.execution_time_seconds}s")
```

### Agent Capability Matching

```python
# Find agent by capability
agent = adapter._find_agent_by_capability("system_design")
if agent:
    print(f"Found agent: {agent.name}")
    print(f"Capabilities: {', '.join(agent.capabilities)}")
```

## Database Migration

Apply the SDK database schema:

```bash
# Using SQLite
sqlite3 ~/.shannon-mcp/shannon.db < migrations/001_sdk_integration.sql
```

This adds:
- SDK-specific columns to `agents` table
- `subagent_executions` table for tracking subagents
- `agent_memory_files` table for agent memory
- `agent_skills` table for Agent Skills
- Performance views for analytics

## Testing

### Run Unit Tests

```bash
# Run all SDK tests
pytest tests/unit/test_agent_sdk_adapter.py -v

# Run with coverage
pytest tests/unit/test_agent_sdk_adapter.py --cov=shannon_mcp.adapters
```

### Run Integration Tests

```bash
# Run integration tests (requires SDK installed)
pytest tests/integration/test_sdk_integration.py -v -m integration
```

### Run Functional Tests

```bash
# Test full SDK integration
python scripts/test_sdk_integration.py
```

## Configuration Options

### AgentSDKConfig

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `true` | Enable SDK integration |
| `agents_directory` | Path | `~/.claude/agents` | SDK agent files location |
| `use_subagents` | bool | `true` | Enable subagent parallelization |
| `max_subagents_per_task` | int | `5` | Max subagents per task |
| `max_context_size` | int | `200000` | Max context window (tokens) |
| `auto_compact_threshold` | float | `0.8` | Auto-compact at % of max |
| `permission_mode` | str | `acceptEdits` | Permission mode |
| `allowed_tools` | list | `['Read', 'Write', 'Bash']` | Default tools |
| `execution_timeout` | int | `300` | Timeout in seconds |
| `max_concurrent_agents` | int | `10` | Max concurrent executions |
| `legacy_fallback_enabled` | bool | `true` | Fall back to legacy agents |

## Best Practices

### 1. Use Subagents for Parallelizable Tasks

**Good**:
```python
# Let SDK decompose and parallelize
request = SDKExecutionRequest(
    description="Optimize performance, security, and documentation",
    required_capabilities=["performance", "security", "documentation"],
    use_subagents=True
)
```

**Bad**:
```python
# Sequential execution (slower)
for capability in ["performance", "security", "documentation"]:
    request = SDKExecutionRequest(
        description=f"Handle {capability}",
        required_capabilities=[capability],
        use_subagents=False
    )
```

### 2. Organize Agent Files

```
~/.claude/agents/
├── architecture-agent.md      # System design
├── testing-agent.md           # Test creation
├── security-agent.md          # Security review
└── performance-agent.md       # Optimization
```

### 3. Monitor Performance

Track SDK execution metrics:

```python
# View execution statistics
result = await adapter.execute_complex_task(agent, request)

print(f"Execution mode: {result.execution_mode.value}")
print(f"Subagents used: {result.subagent_count}")
print(f"Context tokens: {result.context_tokens_used}")
print(f"Time: {result.execution_time_seconds}s")
```

## Troubleshooting

### SDK Not Available

```
Error: Python Agents SDK not available
```

**Solution**:
```bash
pip install claude-agent-sdk
# Verify Node.js is installed
node --version
```

### Agent File Not Found

```
Error: Agent file not found: ~/.claude/agents/my-agent.md
```

**Solution**:
```bash
# Create agent directory
mkdir -p ~/.claude/agents

# Migrate agents
python scripts/migrate_agents_to_sdk.py --all
```

### Context Window Exceeded

```
Error: Context window exceeded: 205000 tokens
```

**Solution**:
```yaml
agent_sdk:
  auto_compact_threshold: 0.7  # Compact earlier
  max_context_size: 150000     # Reduce max size
```

## Examples

See the following for complete examples:

- **Sample Agents**: `~/.claude/agents/architecture-agent.md`, `testing-agent.md`
- **Migration Script**: `scripts/migrate_agents_to_sdk.py`
- **Functional Tests**: `scripts/test_sdk_integration.py`
- **Unit Tests**: `tests/unit/test_agent_sdk_adapter.py`
- **Integration Tests**: `tests/integration/test_sdk_integration.py`

## Support

For issues or questions:

1. Check logs: `~/.shannon-mcp/logs/shannon-mcp.log`
2. Run diagnostic: `python scripts/test_sdk_integration.py`
3. Review integration plan: `AGENTS_SDK_INTEGRATION_PLAN.md`
4. Open issue: https://github.com/krzemienski/shannon-mcp/issues

## Next Steps

1. **Install dependencies**: `poetry install`
2. **Migrate agents**: `python scripts/migrate_agents_to_sdk.py --all`
3. **Run tests**: `pytest tests/`
4. **Configure**: Update `config.yaml` with SDK settings
5. **Use SDK**: Start using SDK agents in your workflows

---

**Version**: 0.2.0
**Last Updated**: 2025-01-13
**Status**: Production Ready
