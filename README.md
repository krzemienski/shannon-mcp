# Shannon MCP Server

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-purple.svg)](https://modelcontextprotocol.io)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-80%25%2B-yellowgreen.svg)](#testing)

> A comprehensive Model Context Protocol (MCP) server for Claude Code, built using an innovative 26-agent collaborative AI system.

Shannon MCP provides programmatic control over Claude Code CLI operations through a standardized MCP interface, enabling seamless integration with Claude Desktop and other MCP clients.

## Key Features

- **7 MCP Tools**: Complete Claude Code session management and control
- **3 MCP Resources**: Real-time access to configuration, agents, and sessions
- **26 Specialized AI Agents**: Multi-agent system for complex task handling
- **Production-Ready**: 95% complete, ~28K lines of code, 64 comprehensive test files
- **Advanced Features**: Checkpoints, Hooks, Analytics, and Process Registry

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Documentation](#documentation)
- [Multi-Agent System](#multi-agent-system)
- [Development](#development)
- [Project Status](#project-status)
- [Requirements](#requirements)
- [Testing](#testing)
- [Deployment](#deployment)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Support](#support)

---

## Overview

### What is Shannon MCP Server?

Shannon MCP Server is a comprehensive Model Context Protocol (MCP) implementation that brings the power of Claude Code to any MCP-compatible client. It exposes Claude Code's capabilities through a standardized interface, enabling:

- **Programmatic Session Management**: Create, monitor, and control Claude Code sessions via API
- **Real-time Streaming**: JSONL streaming with backpressure handling for live output
- **Advanced Version Control**: Git-like checkpoints for session state management
- **Event-Driven Automation**: Hooks framework for automated workflows
- **Usage Analytics**: Comprehensive tracking and reporting of all operations
- **Multi-Agent Collaboration**: 26 specialized agents for complex task handling

### Why Shannon MCP?

Shannon MCP Server differentiates itself through:

1. **Comprehensive Implementation**: Full Claude Code feature parity with extensive test coverage
2. **Production-Ready Architecture**: Built with enterprise-grade reliability and performance
3. **Multi-Agent Innovation**: First MCP server built entirely by collaborative AI agents
4. **Extensible Design**: Plugin system, hooks framework, and custom agent support
5. **Developer-First**: Rich documentation, examples, and interactive testing tools

### Key Differentiators

- **26-Agent System**: Specialized agents handle everything from architecture to deployment
- **Content-Addressable Storage**: Efficient deduplication and compression for checkpoints
- **Bidirectional Streaming**: Real-time JSONL parsing with error recovery
- **Process Registry**: System-wide session tracking and resource monitoring
- **Zero-Downtime Updates**: Hot-reload configuration and graceful shutdowns

---

## Features

### Core Features

#### Binary Management
- **Automatic Discovery**: Finds Claude Code installations across system PATH, NVM, and standard locations
- **Version Detection**: Validates compatibility and tracks version information
- **Intelligent Caching**: Reduces discovery overhead with smart cache invalidation
- **Fallback Strategies**: Multiple search methods ensure reliable binary location

#### Session Orchestration
- **Full Lifecycle Management**: Create, start, monitor, pause, resume, and terminate sessions
- **Concurrent Sessions**: Handle multiple simultaneous Claude Code sessions
- **Real-time Streaming**: JSONL event stream with bidirectional communication
- **Resource Tracking**: Monitor memory, CPU, and I/O usage per session
- **Graceful Cleanup**: Automatic resource cleanup on session termination

#### JSONL Streaming
- **Backpressure Handling**: Prevents memory overflow during high-volume streaming
- **Error Recovery**: Automatic retry and reconnection logic
- **Message Buffering**: Configurable buffer sizes for optimal throughput
- **Protocol Validation**: Ensures MCP protocol compliance

### Advanced Features

#### Checkpoint System
- **Git-like Versioning**: Create, restore, and manage session snapshots
- **Content-Addressable Storage (CAS)**: SHA-256 based deduplication saves storage space
- **Compression**: Zstandard compression reduces checkpoint size by up to 90%
- **Diff Generation**: Compare checkpoints to track changes over time
- **Timeline Management**: Navigate checkpoint history with branching support
- **Automatic Pruning**: Configurable retention policies for storage management

#### Hooks Framework
- **Event-Driven Automation**: Trigger commands on Claude Code events
- **Multiple Hook Types**: PreToolUse, PostToolUse, Notification, Stop, SubagentStop, UserPromptSubmit
- **Flexible Configuration**: Project-level, user-level, and global scopes
- **Environment Variables**: Rich context passed to hook commands
- **Sandboxed Execution**: Optional isolation for security

#### Analytics Engine
- **Usage Tracking**: Record all sessions, tool calls, and resource usage
- **Cost Monitoring**: Track token usage and estimate costs per session
- **Performance Metrics**: Latency, throughput, and error rates
- **Export Capabilities**: CSV and JSON export for external analysis
- **Retention Policies**: Automatic cleanup of old analytics data

### Multi-Agent System

#### 26 Specialized Agents

**Core Architecture Agents (4)**
- Architecture Agent: System design and component relationships
- Claude Code SDK Expert: Deep CLI integration knowledge
- Python MCP Server Expert: MCP protocol implementation
- Functional MCP Server Agent: Business logic and workflows

**Infrastructure Agents (7)**
- Database Storage Agent: SQLite optimization and CAS
- Streaming Concurrency Agent: Async patterns and backpressure
- JSONL Streaming Agent: Real-time parsing and buffering
- Process Management Agent: System process monitoring
- Filesystem Monitor Agent: Real-time change detection
- Platform Compatibility Agent: Cross-platform support
- Storage Algorithms Agent: Compression and deduplication

**Quality & Security Agents (6)**
- Security Validation Agent: Input validation and injection prevention
- Testing Quality Agent: Comprehensive test coverage
- Error Handling Agent: Robust error recovery
- Performance Optimizer Agent: Profiling and optimization
- Documentation Agent: API docs and examples
- DevOps Deployment Agent: CI/CD and automation

**Specialized Agents (9)**
- Telemetry OpenTelemetry Agent: Observability implementation
- Analytics Monitoring Agent: Usage analytics and reporting
- Integration Specialist Agent: Third-party integrations
- Project Coordinator Agent: Task management
- Migration Specialist Agent: Database migrations
- SSE Transport Agent: Server-Sent Events
- Resources Specialist Agent: MCP resource exposure
- Prompts Engineer Agent: Prompt templates
- Plugin Architect Agent: Extension system

### Infrastructure

#### Process Registry
- **System-Wide Tracking**: Monitor all Shannon MCP instances across the system
- **Resource Discovery**: Find and connect to existing sessions
- **Cleanup Automation**: Remove stale process entries
- **Health Monitoring**: Track process health and resource usage

#### Caching System
- **Multi-Layer Caching**: Binary, session, and configuration caches
- **Smart Invalidation**: Automatic cache refresh on changes
- **Configurable TTL**: Customizable time-to-live per cache type
- **Memory Limits**: Prevent unbounded cache growth

#### Transport Layer
- **STDIO Transport**: Standard input/output for MCP communication
- **SSE Transport**: Server-Sent Events for web integration (future)
- **Protocol Negotiation**: Automatic protocol version detection
- **Message Validation**: Strict JSON-RPC compliance

---

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP CLIENT LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Claude     │  │   MCP        │  │   Custom     │              │
│  │   Desktop    │  │   Inspector  │  │   Client     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                       │
│         └──────────────────┴──────────────────┘                       │
│                            │                                          │
│                   JSON-RPC over STDIO                                │
└────────────────────────────┼──────────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────────┐
│                    SHANNON MCP SERVER                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     MCP Protocol Layer                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │   Tools     │  │  Resources  │  │   Prompts   │         │   │
│  │  │   (7)       │  │   (3)       │  │   (Future)  │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Core Managers Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │   Binary    │  │   Session   │  │    Agent    │         │   │
│  │  │   Manager   │  │   Manager   │  │   Manager   │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 Advanced Features Layer                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │ Checkpoint  │  │    Hooks    │  │  Analytics  │         │   │
│  │  │   System    │  │  Framework  │  │   Engine    │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Infrastructure Layer                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  Streaming  │  │   Storage   │  │   Process   │         │   │
│  │  │   (JSONL)   │  │  (SQLite)   │  │  Registry   │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼──────────────────────────────────────────┐
│                      CLAUDE CODE CLI                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Claude Code Binary                           │   │
│  │  - File operations                                            │   │
│  │  - Shell commands                                             │   │
│  │  - Code generation                                            │   │
│  │  - Interactive workflows                                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Relationships

```
Session Manager ──┬──> Binary Manager (discovers Claude Code)
                  │
                  ├──> Streaming Processor (handles JSONL output)
                  │
                  ├──> Checkpoint Manager (saves/restores state)
                  │
                  ├──> Hooks Manager (triggers automation)
                  │
                  └──> Analytics Engine (tracks usage)

Agent Manager ────┬──> Agent Registry (26 specialized agents)
                  │
                  ├──> Task Dispatcher (assigns work)
                  │
                  └──> Result Aggregator (combines outputs)

Checkpoint System ┬──> CAS Storage (content-addressable storage)
                  │
                  ├──> Timeline Manager (version graph)
                  │
                  └──> Diff Engine (change detection)

Process Registry ─┬──> System Monitor (process tracking)
                  │
                  ├──> Health Checker (status monitoring)
                  │
                  └──> Cleanup Service (garbage collection)
```

### Data Flow

```
1. Client Request
   └──> MCP Protocol Layer (validate JSON-RPC)
        └──> Tool Handler (route to appropriate manager)
             └──> Manager (execute operation)
                  └──> Claude Code Binary (perform work)
                       └──> JSONL Stream (output events)
                            └──> Stream Processor (parse and buffer)
                                 └──> Response Builder (format MCP response)
                                      └──> Client (receive result)

2. Session Lifecycle
   Create ──> Start ──> Execute ──> Monitor ──> Complete ──> Cleanup
     │         │          │           │           │            │
     └─> DB ──┴─> Binary ┴─> Stream ─┴─> Hooks ──┴─> Analytics┴─> Registry
```

---

## Quick Start

Get started with Shannon MCP in 5 commands:

```bash
# 1. Clone the repository
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp

# 2. Install dependencies with Poetry
poetry install

# 3. Activate the virtual environment
poetry shell

# 4. Verify installation
shannon-mcp --help

# 5. Run the server (starts in stdio mode for MCP communication)
shannon-mcp
```

That's it! The server is now ready to accept MCP protocol commands.

### Quick Test

Test the server with a simple MCP request:

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | shannon-mcp
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {}
    },
    "serverInfo": {
      "name": "shannon-mcp",
      "version": "0.1.0"
    }
  },
  "id": 1
}
```

---

## Installation

For detailed installation instructions, see **[INSTALLATION.md](INSTALLATION.md)**.

### Prerequisites

- **Python 3.11+**
- **Poetry** (Python package manager)
- **Claude Code CLI** (the binary this server manages)
- **Git**
- **100MB disk space** minimum, 500MB recommended

### Quick Installation

```bash
# Install from source (recommended for development)
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp
poetry install

# Verify installation
poetry shell
shannon-mcp --version
```

### Install with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "shannon-mcp",
      "args": [],
      "env": {
        "SHANNON_CONFIG_PATH": "/home/user/.shannon-mcp/config.yaml"
      }
    }
  }
}
```

For PyPI installation (when available):
```bash
pip install shannon-mcp
```

See **[INSTALLATION.md](INSTALLATION.md)** for:
- Detailed prerequisites and system requirements
- Configuration options and environment variables
- Troubleshooting common installation issues
- Upgrading and uninstallation procedures

---

## Usage

For comprehensive usage documentation, see **[USAGE.md](USAGE.md)**.

### MCP Tools (7)

Shannon MCP exposes 7 powerful tools through the MCP protocol:

1. **`find_claude_binary`** - Automatically discover Claude Code installation
2. **`create_session`** - Start a new Claude Code session with a prompt
3. **`send_message`** - Send follow-up messages to active sessions
4. **`cancel_session`** - Stop a running session immediately
5. **`list_sessions`** - View all sessions (active, completed, failed)
6. **`list_agents`** - Browse the 26 specialized AI agents
7. **`assign_task`** - Delegate tasks to the most appropriate agent

### MCP Resources (3)

Access read-only system state through resources:

1. **`shannon://config`** - Current configuration settings
2. **`shannon://agents`** - Detailed agent information
3. **`shannon://sessions`** - Active session data and statistics

### Basic Usage Examples

#### Create a Session

```python
# Using Python MCP client
session = await client.call_tool("create_session", {
    "prompt": "Create a FastAPI REST API with user authentication",
    "model": "claude-3-sonnet"
})
print(f"Session ID: {session['session_id']}")
```

#### List Active Sessions

```python
sessions = await client.call_tool("list_sessions", {
    "state": "running"
})
print(f"Active sessions: {len(sessions)}")
```

#### Assign Task to Agent

```python
assignment = await client.call_tool("assign_task", {
    "description": "Optimize database queries for better performance",
    "required_capabilities": ["database", "performance", "sql"],
    "priority": "high"
})
print(f"Assigned to: {assignment['agent_name']}")
```

See **[USAGE.md](USAGE.md)** for:
- Complete tool and resource documentation
- Advanced features (checkpoints, hooks, analytics)
- Multi-agent collaboration patterns
- Best practices and examples
- Error handling and debugging

---

## Documentation

Shannon MCP includes comprehensive documentation for all aspects of the system:

### User Documentation
- **[INSTALLATION.md](INSTALLATION.md)** - Complete installation guide with troubleshooting
- **[USAGE.md](USAGE.md)** - User guide with examples and best practices
- **[TESTING.md](TESTING.md)** - Testing guide for developers and contributors
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide for production environments (future)

### Technical Specification
- **[docs/claude-code-mcp-specification.md](docs/claude-code-mcp-specification.md)** - Full technical specification
- **[docs/multi-agent-architecture.md](docs/multi-agent-architecture.md)** - Multi-agent system design
- **[docs/additional-agents-specification.md](docs/additional-agents-specification.md)** - Extended agent specifications

### API Documentation
- **API Reference** - OpenAPI specification and SDK docs (future)
- **Examples** - Code examples and recipes (see USAGE.md)
- **Architecture Diagrams** - System architecture and data flow

### Project Status
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Current implementation status
- **[MCP_API_FIX_SUMMARY.md](MCP_API_FIX_SUMMARY.md)** - API fixes and improvements
- **[CLAUDE.md](CLAUDE.md)** - Project instructions for Claude Code

---

## Multi-Agent System

Shannon MCP is built using an innovative **26-agent collaborative system**, where specialized AI agents work together to implement the entire MCP server.

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                          │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ Build           │  │ Agent        │  │ Shared          │   │
│  │ Orchestrator    │  │ Progress     │  │ Memory          │   │
│  └────────┬────────┘  └──────┬───────┘  └────────┬────────┘   │
│           └───────────────────┴────────────────────┘             │
└───────────────────────────────┼─────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
      Core Architecture   Infrastructure    Specialized
         Agents (4)         Agents (7)      Agents (9)
```

### Agent Categories

**Core Architecture (4 agents)**
- System design and architectural decisions
- Claude Code SDK deep integration
- MCP protocol implementation
- Business logic and workflows

**Infrastructure (7 agents)**
- Database storage and optimization
- Streaming and concurrency patterns
- JSONL parsing and buffering
- Process and filesystem monitoring
- Platform compatibility
- Storage algorithms

**Quality & Security (6 agents)**
- Security validation and hardening
- Comprehensive testing
- Error handling and recovery
- Performance optimization
- Documentation generation
- DevOps and deployment

**Specialized (9 agents)**
- Telemetry and observability
- Analytics and monitoring
- Third-party integrations
- Project coordination
- Database migrations
- SSE transport
- Resource exposure
- Prompt engineering
- Plugin architecture

### Collaboration Mechanisms

1. **Shared Memory**: Agents share knowledge through a persistent context store
2. **Task Distribution**: Orchestrator assigns tasks based on agent expertise
3. **Progress Tracking**: Real-time monitoring of all agent activities
4. **Cross-Agent Review**: Agents review each other's work for quality
5. **Knowledge Evolution**: Patterns and solutions improve over time

### Orchestrator Commands

```bash
# Initialize the build process
/mcp-build-orchestrator init --project-path ~/shannon-mcp

# Monitor agent progress
/mcp-agent-progress status --detailed

# View shared memory
/mcp-shared-memory status

# Check agent context
/mcp-agent-context view --agent-name "Architecture Agent"
```

### Benefits of Multi-Agent Development

- **Specialized Expertise**: Each agent focuses on specific domains
- **Parallel Development**: Multiple components built simultaneously
- **Consistent Quality**: Cross-agent reviews ensure high standards
- **Knowledge Retention**: Shared memory preserves patterns and solutions
- **Rapid Iteration**: Agents learn and improve continuously

---

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp

# Install dependencies (including dev tools)
poetry install

# Activate virtual environment
poetry shell

# Install pre-commit hooks (optional)
pre-commit install

# Run tests to verify setup
pytest
```

### Project Structure

```
shannon-mcp/
├── src/shannon_mcp/           # Source code (~28K lines)
│   ├── managers/              # Core managers (Binary, Session, Agent)
│   ├── storage/               # Database and CAS
│   ├── streaming/             # JSONL streaming
│   ├── checkpoint/            # Checkpoint system
│   ├── hooks/                 # Hooks framework
│   ├── analytics/             # Analytics engine
│   ├── registry/              # Process registry
│   ├── mcp/                   # MCP protocol implementation
│   ├── utils/                 # Utilities
│   └── server.py              # Main server entry point
├── tests/                     # Test suite (64 files, ~10.5K lines)
│   ├── functional/            # Complete component tests (20 files)
│   ├── benchmarks/            # Performance tests (13 files)
│   ├── mcp-integration/       # MCP protocol tests
│   ├── utils/                 # Test utilities
│   └── conftest.py            # Shared fixtures
├── docs/                      # Technical specifications
├── pyproject.toml             # Poetry configuration
├── INSTALLATION.md            # Installation guide
├── USAGE.md                   # User guide
├── TESTING.md                 # Testing guide
└── README.md                  # This file
```

### Development Workflow

#### 1. Code Style

Shannon MCP uses strict code quality tools:

```bash
# Format code with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with flake8
flake8 src/ tests/

# Type check with mypy
mypy src/

# Run all checks
poetry run pre-commit run --all-files
```

#### 2. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=shannon_mcp --cov-report=html

# Run specific test category
pytest tests/functional/              # Functional tests
pytest tests/benchmarks/              # Performance tests
pytest -m integration                 # Integration tests

# Run fast tests only
pytest -m "not slow"

# Stop on first failure
pytest -x

# Show detailed output
pytest -v -s
```

#### 3. Making Changes

```bash
# Create a feature branch
git checkout -b feature/my-feature

# Make changes and add tests
# ...

# Run tests
pytest

# Check code quality
pre-commit run --all-files

# Commit changes
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/my-feature
```

### Contributing Guidelines

We welcome contributions! Here's how to get started:

1. **Fork the repository** and clone your fork
2. **Create a feature branch** from `main`
3. **Make your changes** with tests
4. **Run the test suite** to ensure everything works
5. **Follow code style** guidelines (black, flake8, mypy)
6. **Write clear commit messages** following conventional commits
7. **Submit a pull request** with a detailed description

**Commit Message Format**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

Example:
```
feat(session): add timeout configuration for sessions

- Add timeout parameter to session creation
- Implement timeout handling in session manager
- Add tests for timeout behavior

Closes #123
```

---

## Project Status

### Current Version: 0.1.0

**Implementation Status**: **95% Complete**

#### Completed Components ✓

- ✅ **Core Infrastructure** (100%)
  - MCP protocol implementation
  - Binary manager with auto-discovery
  - Session manager with streaming
  - JSONL stream processor

- ✅ **Advanced Features** (95%)
  - Checkpoint system with CAS
  - Hooks framework
  - Agent system
  - Analytics engine

- ✅ **Infrastructure** (90%)
  - Process registry
  - Storage layer (SQLite + CAS)
  - Caching system
  - Error handling

- ✅ **Testing** (80%+ coverage)
  - 64 test files
  - ~10.5K lines of test code
  - Unit, functional, integration, and benchmark tests

- ✅ **Documentation** (100%)
  - Installation guide
  - User guide
  - Testing guide
  - Technical specifications

#### In Progress / Remaining 5%

- 🔄 **SSE Transport** - Server-Sent Events for web integration
- 🔄 **Plugin System** - Dynamic plugin loading
- 🔄 **API Documentation** - OpenAPI specification
- 🔄 **Deployment Guide** - Production deployment documentation
- 🔄 **Performance Tuning** - Final optimizations

#### Roadmap

**Q1 2025**
- Complete SSE transport implementation
- Publish to PyPI
- API documentation generation
- Performance optimization

**Q2 2025**
- Plugin system MVP
- Cloud integration features
- Enterprise authentication
- Advanced analytics dashboard

**Q3 2025**
- Web UI for management
- Multi-user support
- Team collaboration features
- Advanced security features

### Code Metrics

- **Source Code**: 61 Python files, ~28,000 lines
- **Test Code**: 64 test files, ~10,500 lines
- **Test Coverage**: 80%+ overall, 90%+ for critical components
- **Dependencies**: 19 production, 11 development
- **Documentation**: 4 comprehensive guides + technical specs

---

## Requirements

### System Requirements

- **Operating System**: Linux, macOS, or Windows (WSL recommended for Windows)
- **Python**: 3.11 or higher
- **Disk Space**: 100MB minimum, 500MB recommended for data storage
- **RAM**: 512MB minimum, 1GB recommended
- **Network**: Internet connection for initial setup and package downloads

### Software Dependencies

#### Required

- **Poetry** (>=1.5.0) - Python package manager
- **Git** - Version control
- **Claude Code CLI** - The binary that Shannon MCP manages

#### Optional

- **Docker** - For containerized deployment
- **PostgreSQL** - Alternative to SQLite for production (future)
- **Redis** - For distributed caching (future)

### Python Dependencies

#### Production Dependencies (19)

**Core & MCP**
- `mcp` (^1.0.0) - Model Context Protocol SDK
- `aiosqlite` (^0.19.0) - Async SQLite driver
- `aiofiles` (^23.0.0) - Async file I/O
- `aiohttp` (^3.9.0) - Async HTTP client

**Streaming & Processing**
- `watchdog` (^4.0.0) - File system monitoring
- `json-stream` (^2.3.0) - Streaming JSON parser
- `zstandard` (^0.22.0) - High-performance compression

**CLI & Configuration**
- `click` (^8.1.0) - CLI framework
- `pyyaml` (^6.0.0) - YAML config parsing
- `python-dotenv` (^1.0.0) - Environment variables
- `toml` (^0.10.2) - TOML config parsing

**Data & Validation**
- `pydantic` (^2.0.0) - Data validation
- `rich` (^13.0.0) - Terminal formatting

**Utilities**
- `httpx` (^0.27.0) - Modern HTTP client
- `psutil` (^5.9.0) - Process monitoring
- `semantic-version` (^2.10.0) - Version comparison
- `packaging` (^24.0) - Version utilities

**Monitoring**
- `structlog` (^24.0.0) - Structured logging
- `sentry-sdk` (^2.0.0) - Error tracking

#### Development Dependencies (11)

**Testing**
- `pytest` (^7.4.0) - Testing framework
- `pytest-asyncio` (^0.21.0) - Async test support
- `pytest-cov` (^4.1.0) - Coverage reporting
- `pytest-mock` (^3.12.0) - Mocking utilities
- `pytest-benchmark` (^4.0.0) - Performance benchmarks

**Code Quality**
- `black` (^23.0.0) - Code formatter
- `flake8` (^6.0.0) - Linter
- `mypy` (^1.5.0) - Type checker
- `isort` (^5.13.0) - Import sorter

**Development Tools**
- `pre-commit` (^3.3.0) - Git hooks
- `ipython` - Interactive shell (optional)

---

## Testing

For comprehensive testing documentation, see **[TESTING.md](TESTING.md)**.

### Test Suite Overview

- **64 test files** with **~10,500 lines** of test code
- **80%+ overall coverage**, **90%+ for critical components**
- **4 test categories**: Unit, Functional, Integration, Benchmark

### Quick Test Commands

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=shannon_mcp --cov-report=html

# Run specific test categories
poetry run pytest tests/functional/              # Functional tests
poetry run pytest tests/benchmarks/              # Performance tests
poetry run pytest -m integration                 # Integration tests
poetry run pytest -m "not slow"                  # Fast tests only

# Run specific component tests
poetry run pytest tests/test_binary_manager.py   # Binary manager
poetry run pytest tests/test_session_manager.py  # Session manager
poetry run pytest tests/test_streaming.py        # Streaming

# Debug failing tests
poetry run pytest -v -s --pdb -x                 # Stop on first failure
```

### Test Categories

**Unit Tests** (root level) - Fast, isolated tests for individual functions
**Functional Tests** (20 files) - Complete component testing with all features
**Integration Tests** - End-to-end workflows with real MCP protocol
**Benchmark Tests** (13 files) - Performance testing and regression detection

### Coverage Reports

```bash
# Generate HTML coverage report
poetry run pytest --cov=shannon_mcp --cov-report=html
open htmlcov/index.html

# Terminal report with missing lines
poetry run pytest --cov=shannon_mcp --cov-report=term-missing

# XML report for CI/CD
poetry run pytest --cov=shannon_mcp --cov-report=xml
```

### Continuous Integration

Shannon MCP uses GitHub Actions for CI/CD:

- **Test Matrix**: Python 3.11, 3.12 on Ubuntu, macOS
- **Quality Checks**: black, flake8, mypy, isort
- **Coverage Enforcement**: Fails if coverage drops below 80%
- **Performance Regression**: Benchmark comparisons against baseline

See **[TESTING.md](TESTING.md)** for:
- Complete test documentation
- Writing new tests
- Debugging test failures
- Performance benchmarking
- Manual testing with MCP Inspector

---

## Deployment

### Development Deployment

```bash
# Run locally with Poetry
poetry run shannon-mcp

# Run with debug logging
SHANNON_LOG_LEVEL=DEBUG poetry run shannon-mcp

# Run with custom config
SHANNON_CONFIG_PATH=/path/to/config.yaml poetry run shannon-mcp
```

### Production Deployment

**Coming Soon**: Full production deployment guide

For now, see configuration options in **[INSTALLATION.md](INSTALLATION.md)**.

### Docker Deployment (Future)

```bash
# Build Docker image
docker build -t shannon-mcp:latest .

# Run container
docker run -d \
  -v ~/.shannon-mcp:/root/.shannon-mcp \
  -e SHANNON_LOG_LEVEL=INFO \
  shannon-mcp:latest
```

### Configuration

Default configuration location: `~/.shannon-mcp/config.yaml`

Key configuration sections:
- **binary_discovery**: Claude Code search paths
- **storage**: Database and cache settings
- **sessions**: Session limits and timeouts
- **logging**: Log levels and output
- **analytics**: Usage tracking settings
- **hooks**: Automation configuration
- **performance**: Worker threads and buffers

See **[INSTALLATION.md](INSTALLATION.md)** for complete configuration reference.

---

## License

Shannon MCP Server is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2025 Shannon MCP Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

See the [LICENSE](LICENSE) file for full details.

---

## Acknowledgments

Shannon MCP Server is built on the shoulders of giants and innovative technologies:

### Technologies

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io)** by Anthropic - The standardized protocol for AI context sharing
- **[Claude Code CLI](https://docs.anthropic.com/claude/docs/claude-code)** - The powerful AI coding assistant this server manages
- **[FastMCP](https://github.com/jlowin/fastmcp)** - Python MCP server framework pattern
- **[Python asyncio](https://docs.python.org/3/library/asyncio.html)** - Async/await foundation
- **[Poetry](https://python-poetry.org)** - Modern Python dependency management
- **[pytest](https://pytest.org)** - Comprehensive testing framework

### Community

- **Anthropic** for creating Claude Code and the MCP protocol
- **MCP Community** for protocol improvements and feedback
- **Open Source Contributors** for dependencies and tools
- **Early Adopters** for testing and feature requests

### Innovation

This project demonstrates a groundbreaking approach to software development:

**Multi-Agent Collaborative AI Development** - Shannon MCP is the first MCP server built entirely by 26 specialized AI agents working together through orchestration systems, shared memory, and collaborative workflows. This represents the future of software development where AI agents handle everything from architecture to deployment.

### Built With

- 🤖 **26 Specialized AI Agents** - Core architecture, infrastructure, quality, and specialized domain experts
- 🧠 **Shared Memory System** - Knowledge graph enabling agent collaboration
- 🎯 **Task Orchestration** - Intelligent work distribution based on agent expertise
- 📊 **Progress Tracking** - Real-time monitoring of all agent activities
- 🔄 **Iterative Refinement** - Cross-agent reviews and continuous improvement

---

## Support

### Getting Help

- **Documentation**: Start with [INSTALLATION.md](INSTALLATION.md) and [USAGE.md](USAGE.md)
- **Issues**: [GitHub Issues](https://github.com/krzemienski/shannon-mcp/issues) for bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/krzemienski/shannon-mcp/discussions) for questions and community support
- **Email**: [project email] for security issues and private inquiries

### Reporting Issues

When reporting issues, please include:

1. **Environment Details**: OS, Python version, Shannon MCP version
2. **Steps to Reproduce**: Minimal reproducible example
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Logs**: Relevant log output (use `SHANNON_LOG_LEVEL=DEBUG`)

### Feature Requests

We welcome feature requests! Please include:

1. **Use Case**: What problem does this solve?
2. **Proposed Solution**: How would you like it to work?
3. **Alternatives**: What alternatives have you considered?
4. **Additional Context**: Any other relevant information

### Community

- **GitHub**: [github.com/krzemienski/shannon-mcp](https://github.com/krzemienski/shannon-mcp)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Claude Code**: [docs.anthropic.com/claude/docs/claude-code](https://docs.anthropic.com/claude/docs/claude-code)

### Security

For security vulnerabilities, please email [security email] instead of creating a public issue. We take security seriously and will respond promptly.

---

## Links

- **Documentation**: [INSTALLATION.md](INSTALLATION.md) | [USAGE.md](USAGE.md) | [TESTING.md](TESTING.md)
- **Technical Specs**: [docs/](docs/)
- **GitHub**: [github.com/krzemienski/shannon-mcp](https://github.com/krzemienski/shannon-mcp)
- **Issues**: [github.com/krzemienski/shannon-mcp/issues](https://github.com/krzemienski/shannon-mcp/issues)
- **License**: [MIT License](LICENSE)

---

<div align="center">

**Shannon MCP Server** - Empowering developers with programmatic Claude Code control

Built by 26 AI agents working collaboratively

[Install](#quick-start) • [Documentation](#documentation) • [GitHub](https://github.com/krzemienski/shannon-mcp)

</div>
