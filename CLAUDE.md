# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shannon MCP is a comprehensive Model Context Protocol (MCP) server implementation for Claude Code, built using an innovative multi-agent collaborative system. The project employs 26 specialized AI agents working together to implement the entire MCP server specification in Python.

## Key Architecture Components

### Multi-Agent System
- **26 specialized agents** with deep expertise in specific domains
- Agents collaborate through shared memory and orchestration systems
- Key agent categories:
  - Core Architecture Agents (4)
  - Infrastructure Agents (7)
  - Quality & Security Agents (6)
  - Specialized Agents (9)

### MCP Server Architecture
```
MCP Client (Claude) <-> Claude Code MCP Server <-> Claude Code Binary
```

The server implements:
- Binary Management (automatic Claude Code discovery)
- Session Orchestration (real-time JSONL streaming)
- Agent System (custom AI agents)
- Checkpoint System (Git-like versioning)
- Hooks Framework (event-driven automation)
- Analytics Engine (usage tracking)
- Process Registry (system-wide session tracking)

## Development Commands

### Agent System Commands
```bash
# Activate the multi-agent system (agents installed in ~/.claude/)
python ~/.claude/activate-mcp-system.py

# Start the build orchestrator
/mcp-build-orchestrator init --project-path ~/shannon-mcp

# Monitor agent progress
/mcp-agent-progress status --detailed

# Check shared memory between agents
/mcp-shared-memory status

# View agent context
/mcp-agent-context view --agent-name "Architecture Agent"
```

### Project Setup (once implemented)
```bash
# Install dependencies with Poetry
poetry install

# Run tests
poetry run pytest

# Run linting
poetry run black . --check
poetry run flake8
poetry run mypy .

# Build package
poetry build

# Run MCP server
poetry run shannon-mcp
```

## Project Structure

```
shannon-mcp/
├── docs/                        # Detailed specifications
│   ├── claude-code-mcp-specification.md  # Full technical spec
│   ├── multi-agent-architecture.md       # Agent system design
│   └── additional-agents-specification.md # Extended agent specs
├── src/shannon_mcp/             # Source code (to be created)
│   ├── managers/               # Component managers
│   ├── storage/               # Database and CAS
│   ├── streaming/             # JSONL streaming
│   ├── mcp/                   # MCP protocol implementation
│   └── utils/                 # Utilities
├── tests/                      # Test suites (to be created)
├── pyproject.toml             # Poetry configuration (to be created)
└── README.md                  # Project documentation
```

## Key Technical Details

### Dependencies
- Python 3.11+
- Core: `mcp`, `aiosqlite`, `aiofiles`, `watchdog`, `zstandard`
- MCP: FastMCP pattern for server implementation
- Storage: SQLite with content-addressable storage (CAS)
- Streaming: JSONL with backpressure handling

### Implementation Phases
1. **Core Infrastructure** (25 tasks) - MCP server foundation, Binary/Session managers
2. **Advanced Features** (25 tasks) - Agent system, Checkpoints, Hooks
3. **Analytics & Monitoring** (15 tasks) - Usage tracking, Process registry
4. **Testing & Documentation** (10 tasks) - Integration tests, API docs
5. **Production Readiness** (10 tasks) - Performance, Security, Deployment
6. **Advanced Integration** (10 tasks) - Claude Desktop, Cloud features

### Key Implementation Files (to be created)
- `src/shannon_mcp/server.py` - Main MCP server
- `src/shannon_mcp/managers/binary.py` - Claude Code binary management
- `src/shannon_mcp/managers/session.py` - Session orchestration
- `src/shannon_mcp/managers/agent.py` - Agent system
- `src/shannon_mcp/storage/cas.py` - Content-addressable storage
- `src/shannon_mcp/streaming/jsonl.py` - JSONL stream processor

## Testing Strategy

- Use `pytest` with `pytest-asyncio` for async tests
- Integration tests with real Claude Code binary
- Performance benchmarks for streaming
- Security tests for command injection prevention
- No mock testing - all tests use real services

## Important Notes

1. This is a specification repository - implementation is pending
2. Multi-agent system coordinates the build process
3. Each agent has specific expertise and responsibilities
4. Agents communicate through structured protocols
5. Shared memory enables knowledge transfer between agents