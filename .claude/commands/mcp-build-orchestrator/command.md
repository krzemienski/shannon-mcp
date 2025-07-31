---
name: mcp-build-orchestrator
description: Orchestrates the multi-agent MCP server implementation
category: mcp-implementation
---

# MCP Build Orchestrator

Master command for orchestrating the Claude Code MCP Server implementation using specialized agents.

## Overview

This command coordinates 26 specialized agents to build the MCP server according to the specification. It manages task distribution, cross-agent communication, and context persistence.

## Usage

```bash
/mcp-build-orchestrator [action] [options]
```

### Actions

#### `init` - Initialize the project
```bash
/mcp-build-orchestrator init --project-path /path/to/claude-code-mcp
```
- Sets up project structure
- Installs all specialized agents
- Creates communication channels
- Initializes shared context database

#### `plan` - Generate implementation plan
```bash
/mcp-build-orchestrator plan --phase [1-6]
```
- Phase 1: Core Infrastructure (25 tasks)
- Phase 2: Advanced Features (25 tasks)
- Phase 3: Analytics & Monitoring (15 tasks)
- Phase 4: Testing & Documentation (10 tasks)
- Phase 5: Production Readiness (10 tasks)
- Phase 6: Advanced Integration (10 tasks)

#### `execute` - Execute implementation tasks
```bash
/mcp-build-orchestrator execute --task-id [task-number] --agent [agent-name]
```
- Assigns task to specified agent
- Monitors execution progress
- Saves agent output to context
- Triggers dependent tasks

#### `coordinate` - Coordinate multiple agents
```bash
/mcp-build-orchestrator coordinate --workflow [workflow-name]
```

Workflows:
- `binary-manager`: Architecture → SDK Expert → Python MCP Expert → Implementation
- `session-streaming`: Streaming Agent → JSONL Agent → Error Handler → Testing
- `checkpoint-system`: Storage Agent → Platform Compat → Migration → Testing
- `hooks-framework`: Security Agent → Functional Agent → Testing
- `telemetry-setup`: Telemetry Agent → Analytics Agent → Monitoring

#### `sync` - Synchronize agent contexts
```bash
/mcp-build-orchestrator sync --agents [agent1,agent2,...]
```
- Shares context between specified agents
- Merges implementation artifacts
- Resolves conflicts
- Updates shared knowledge base

#### `review` - Trigger code review
```bash
/mcp-build-orchestrator review --component [component-name] --reviewers [agents]
```
- Architecture Agent reviews design
- Security Agent reviews security
- Testing Agent reviews test coverage
- Performance Agent reviews optimization

#### `status` - Check implementation status
```bash
/mcp-build-orchestrator status [--detailed]
```
- Shows task completion status
- Lists active agent sessions
- Displays blockers and dependencies
- Estimates completion time

## Agent Communication Protocol

### Message Format
```json
{
  "from_agent": "agent-name",
  "to_agent": "target-agent",
  "message_type": "request|response|notification|review",
  "task_id": "task-identifier",
  "content": {
    "action": "implement|review|test|document",
    "artifact": "code|design|test|doc",
    "data": {}
  },
  "priority": "low|medium|high|critical",
  "timestamp": "ISO-8601"
}
```

### Context Persistence
Each agent maintains context in:
- `~/.claude/projects/mcp-server/agents/[agent-name]/`
  - `state.json` - Current agent state
  - `artifacts/` - Generated code/docs
  - `knowledge.db` - Agent-specific learnings
  - `messages/` - Communication history

### Shared Resources
- `~/.claude/projects/mcp-server/shared/`
  - `implementation.db` - Code artifacts
  - `decisions.log` - Architectural decisions
  - `dependencies.json` - Task dependencies
  - `metrics.jsonl` - Progress metrics

## Implementation Workflows

### Component Implementation Flow
1. **Planning Phase**
   - Architecture Agent designs component
   - Relevant experts review design
   - Coordinator approves implementation

2. **Implementation Phase**
   - Assigned agent implements component
   - Saves artifacts to shared storage
   - Updates task status

3. **Integration Phase**
   - Integration Agent connects components
   - Platform Agent ensures compatibility
   - Testing Agent validates integration

4. **Review Phase**
   - Code review by multiple agents
   - Security audit
   - Performance analysis
   - Documentation check

### Cross-Agent Collaboration Examples

#### Binary Manager Implementation
```bash
# Architecture designs the system
/mcp-build-orchestrator execute --task-id 3.1 --agent mcp-architecture-agent

# SDK Expert implements discovery
/mcp-build-orchestrator execute --task-id 3.2 --agent mcp-claude-sdk-expert

# Platform agent ensures compatibility  
/mcp-build-orchestrator execute --task-id 3.3 --agent mcp-platform-compatibility

# Sync their work
/mcp-build-orchestrator sync --agents mcp-architecture-agent,mcp-claude-sdk-expert,mcp-platform-compatibility
```

#### Streaming System Implementation
```bash
# Coordinate streaming implementation
/mcp-build-orchestrator coordinate --workflow session-streaming

# This automatically:
# 1. Streaming Agent designs architecture
# 2. JSONL Agent implements parser
# 3. Error Handler adds recovery
# 4. Testing Agent creates tests
# 5. Syncs all contexts
```

## Progress Tracking

### Metrics Collected
- Tasks completed per agent
- Lines of code generated
- Test coverage achieved
- Review cycles completed
- Integration points tested

### Reporting
```bash
# Generate progress report
/mcp-build-orchestrator report --format markdown > progress.md

# Send status update
/mcp-build-orchestrator notify --channel slack --message "Phase 1 complete"
```

## Error Recovery

### Agent Failure Handling
- Automatic task reassignment
- Context recovery from checkpoints
- Notification to coordinator
- Dependency adjustment

### Conflict Resolution
- Architecture Agent has final say on design
- Security Agent can veto implementations
- Testing Agent can block releases
- Coordinator resolves deadlocks

## Best Practices

1. **Always sync contexts** after major implementations
2. **Review early and often** to catch issues
3. **Document decisions** in shared knowledge base
4. **Test integrations** immediately after implementation
5. **Monitor agent performance** and reassign if needed

## Example Full Workflow

```bash
# Initialize project
/mcp-build-orchestrator init --project-path ~/claude-code-mcp

# Generate Phase 1 plan
/mcp-build-orchestrator plan --phase 1

# Execute first component
/mcp-build-orchestrator coordinate --workflow binary-manager

# Check status
/mcp-build-orchestrator status --detailed

# Continue with next component
/mcp-build-orchestrator coordinate --workflow session-streaming

# Sync all Phase 1 agents
/mcp-build-orchestrator sync --agents ALL --phase 1

# Generate progress report
/mcp-build-orchestrator report --phase 1
```