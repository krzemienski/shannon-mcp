# Changelog

All notable changes to Shannon MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive API documentation in `docs/API.md`
- Detailed architecture documentation in `docs/ARCHITECTURE.md`
- iOS client application with Swift Package Manager support
- Performance benchmarking suite in `tests/benchmarks/`
- Integration test framework in `tests/mcp-integration/`

### Changed
- **BREAKING**: Migrated from custom MCP implementation to FastMCP framework
- Consolidated multiple server implementations into single `server_fastmcp.py`
- Restructured project to follow FastMCP best practices
- Updated all managers to use on-demand initialization pattern
- Improved error handling with proper timeout management

### Removed
- Legacy server implementations (`server.py`, `server_new.py`)
- Redundant test files from root directory (moved to `tests/`)
- Duplicate iOS project directories
- Temporary worktree directories
- Obsolete documentation and report files

### Fixed
- Circular initialization dependency causing server hangs
- Subprocess timeout issues in BinaryManager
- JSON-RPC parameter validation errors
- Module import compatibility issues

## [1.0.0] - 2024-01-15

### Added
- Initial FastMCP-based implementation
- Core manager system:
  - Binary Manager for Claude Code discovery
  - Session Manager for process lifecycle
  - Agent Manager for AI orchestration
  - Checkpoint Manager for versioning
  - Analytics Manager for metrics
  - Hooks Manager for automation
- MCP tools:
  - `find_claude_binary`
  - `create_session`
  - `send_message`
  - `cancel_session`
  - `list_sessions`
  - `list_agents`
  - `assign_task`
  - `create_checkpoint`
  - `restore_checkpoint`
  - `query_analytics`
  - `execute_hook`
- MCP resources:
  - Static: config, agents, sessions, analytics, hooks
  - Dynamic: sessions/{id}, agents/{id}, checkpoints/{id}
- JSONL streaming with backpressure handling
- Content-addressable storage (CAS) system
- SQLite database with async support
- Comprehensive test suites
- Docker and Kubernetes deployment configurations

### Security
- Input validation on all parameters
- Command injection prevention
- Path traversal protection
- Process isolation with resource limits

### Performance
- Sub-10ms tool response times
- Efficient streaming with circular buffers
- Connection pooling for database
- Caching layer for frequently accessed data
- Async/await throughout for non-blocking operations

## [0.5.0] - 2023-12-01

### Added
- Multi-agent collaborative system
- 26 specialized AI agents for implementation
- Shared memory context between agents
- Progress tracking system
- Agent orchestration commands

### Changed
- Shifted from manual implementation to AI-driven development
- Introduced knowledge graph for agent collaboration
- Added semantic search capabilities

## [0.1.0] - 2023-10-15

### Added
- Initial proof of concept
- Basic Claude Code integration
- Simple session management
- Prototype MCP server

[Unreleased]: https://github.com/yourusername/shannon-mcp/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/shannon-mcp/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/yourusername/shannon-mcp/compare/v0.1.0...v0.5.0
[0.1.0]: https://github.com/yourusername/shannon-mcp/releases/tag/v0.1.0