---
name: mcp-agent-context
description: Manage shared context and knowledge for MCP implementation agents
category: mcp-implementation
---

# MCP Agent Context Manager

Manages shared context, knowledge persistence, and cross-agent communication for the MCP server implementation.

## Overview

This command provides a unified interface for agents to:
- Save and retrieve implementation artifacts
- Share knowledge between agents
- Track decisions and rationale
- Maintain implementation state

## Usage

```bash
/mcp-agent-context [action] [options]
```

### Actions

#### `save` - Save agent artifacts
```bash
/mcp-agent-context save --agent [agent-name] --type [code|design|test|doc] --artifact [content]
```

Example:
```bash
/mcp-agent-context save \
  --agent mcp-architecture-agent \
  --type design \
  --artifact "BinaryManager class design with async discovery methods"
```

#### `get` - Retrieve artifacts
```bash
/mcp-agent-context get --component [component-name] --type [code|design|test|doc]
```

Example:
```bash
/mcp-agent-context get --component binary-manager --type code
```

#### `share` - Share knowledge between agents
```bash
/mcp-agent-context share --from [agent] --to [agent] --knowledge [content]
```

Example:
```bash
/mcp-agent-context share \
  --from mcp-claude-sdk-expert \
  --to mcp-streaming-agent \
  --knowledge "JSONL format: each line must be valid JSON, use async readline"
```

#### `decide` - Record architectural decisions
```bash
/mcp-agent-context decide --agent [agent] --decision [content] --rationale [reason]
```

Example:
```bash
/mcp-agent-context decide \
  --agent mcp-architecture-agent \
  --decision "Use asyncio for all I/O operations" \
  --rationale "Required for high-throughput streaming and concurrent sessions"
```

#### `query` - Search shared knowledge
```bash
/mcp-agent-context query --topic [search-term] --agent [optional-filter]
```

Example:
```bash
/mcp-agent-context query --topic "JSONL parsing" --agent mcp-jsonl-streaming
```

#### `checkpoint` - Create context checkpoint
```bash
/mcp-agent-context checkpoint --message [description]
```

Saves current state of all agent contexts for recovery.

## Context Structure

### Per-Agent Storage
```
~/.claude/projects/mcp-server/agents/[agent-name]/
├── current/
│   ├── implementation.py    # Current code being worked on
│   ├── tests.py            # Associated tests
│   └── notes.md            # Agent's working notes
├── artifacts/
│   ├── [timestamp]-[component].py
│   └── [timestamp]-[component].md
├── knowledge.json          # Agent's learned patterns
└── state.json             # Current task and progress
```

### Shared Storage
```
~/.claude/projects/mcp-server/shared/
├── components/
│   ├── binary-manager/
│   │   ├── implementation.py
│   │   ├── tests.py
│   │   ├── design.md
│   │   └── reviews.json
│   └── [other-components]/
├── decisions.log          # Architectural Decision Records
├── dependencies.json      # Component dependencies
├── knowledge-graph.db     # Shared knowledge base
└── integration-tests/     # Cross-component tests
```

## Knowledge Sharing Protocol

### Knowledge Types

#### Implementation Patterns
```json
{
  "type": "pattern",
  "name": "AsyncStreamReader",
  "description": "Pattern for reading JSONL streams",
  "code_example": "async for line in stream: ...",
  "discovered_by": "mcp-streaming-agent",
  "used_in": ["session-manager", "checkpoint-reader"]
}
```

#### Discovered Issues
```json
{
  "type": "issue",
  "component": "binary-discovery",
  "problem": "NVM paths not in standard PATH",
  "solution": "Check ~/.nvm/versions/node/*/bin/",
  "found_by": "mcp-platform-compatibility",
  "severity": "medium"
}
```

#### Best Practices
```json
{
  "type": "best-practice",
  "area": "error-handling",
  "practice": "Always use custom exceptions",
  "rationale": "Better debugging and error recovery",
  "proposed_by": "mcp-error-handling",
  "approved_by": "mcp-architecture-agent"
}
```

## Integration with Agents

### Agent Initialization
When an agent starts working on a task:
```bash
# Agent checks for existing context
/mcp-agent-context get --component [component] --type all

# Agent claims the task
/mcp-agent-context claim --agent [name] --task [task-id]
```

### During Implementation
```bash
# Save progress periodically
/mcp-agent-context save --agent [name] --type code --artifact "[current code]"

# Check for relevant knowledge
/mcp-agent-context query --topic "[what I'm implementing]"

# Share discoveries
/mcp-agent-context share --from [me] --to ALL --knowledge "[what I learned]"
```

### After Completion
```bash
# Save final artifacts
/mcp-agent-context finalize --agent [name] --component [component]

# Request review
/mcp-agent-context request-review --component [component] --reviewers [agents]
```

## Context Queries

### Find Implementation Examples
```bash
# Find all async patterns
/mcp-agent-context query --topic "async" --type pattern

# Find error handling examples
/mcp-agent-context query --topic "exception" --type code
```

### Check Decision History
```bash
# Why did we choose asyncio?
/mcp-agent-context decisions --topic "asyncio"

# What did security agent say about subprocess?
/mcp-agent-context decisions --agent mcp-security-validation --topic "subprocess"
```

### Track Dependencies
```bash
# What depends on binary-manager?
/mcp-agent-context dependencies --component binary-manager

# What does session-manager need?
/mcp-agent-context dependencies --needs session-manager
```

## Conflict Resolution

When multiple agents modify the same component:

```bash
# Show conflicts
/mcp-agent-context conflicts --component [name]

# Merge changes
/mcp-agent-context merge --component [name] --prefer [agent-name]

# Or escalate to coordinator
/mcp-agent-context escalate --component [name] --reason "[conflict description]"
```

## Reporting

### Generate Context Report
```bash
/mcp-agent-context report --format markdown

# Outputs:
# - Components completed
# - Active implementations
# - Knowledge base size
# - Decision count
# - Conflict history
```

### Export for Analysis
```bash
# Export all artifacts
/mcp-agent-context export --output ./mcp-artifacts.tar.gz

# Export knowledge graph
/mcp-agent-context export --type knowledge --format json
```

## Best Practices for Agents

1. **Always check existing context** before starting work
2. **Save progress frequently** (every significant change)
3. **Share discoveries immediately** (helps other agents)
4. **Document decisions** with clear rationale
5. **Query before implementing** (avoid duplication)
6. **Request reviews early** (catch issues sooner)

## Emergency Recovery

If an agent crashes or context is corrupted:

```bash
# Restore from checkpoint
/mcp-agent-context restore --checkpoint [id]

# Rebuild component context
/mcp-agent-context rebuild --component [name]

# Reset agent state
/mcp-agent-context reset --agent [name] --preserve-artifacts
```