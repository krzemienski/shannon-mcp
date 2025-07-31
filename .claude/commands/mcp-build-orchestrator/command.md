---
name: mcp-build-orchestrator
description: Build the complete Shannon MCP Server using all 26 specialized agents
category: mcp-implementation
---

# MCP Build Orchestrator

BUILD THE ENTIRE SHANNON MCP SERVER CODEBASE using all 26 specialized agents working in coordinated parallel execution.

## Overview

This command orchestrates the complete implementation of the Shannon MCP Server by invoking all specialized agents to build every component according to the full specification. This is NOT a mock command - it builds the actual production codebase.

## Usage - BUILD THE ENTIRE CODEBASE

```bash
/mcp-build-orchestrator build
```

## COMPREHENSIVE BUILD PROCESS - ALL 26 AGENTS

### PHASE 1: FOUNDATION ARCHITECTURE (Task tool batch 1)

1. **Architecture Agent** - Complete system design
   ```
   Task: "You are the Architecture Agent. IMPLEMENT the complete Shannon MCP Server architecture:
   - Create src/shannon_mcp/core/architecture.py with system design
   - Define all component interfaces and integration patterns  
   - Design data flow between all 26 components
   - Create architectural decision records
   - Generate system diagrams and component contracts
   DELIVER: Complete architectural foundation"
   ```

2. **Python MCP Expert** - MCP protocol implementation
   ```
   Task: "You are the Python MCP Expert. IMPLEMENT the complete MCP protocol:
   - Create src/shannon_mcp/server.py with FastMCP implementation
   - Implement all MCP message types and handlers
   - Build async-first server architecture with protocol compliance
   - Create connection management and lifecycle handling
   DELIVER: Production-ready MCP server core"
   ```

3. **Binary Manager Expert** - Binary discovery system
   ```
   Task: "You are the Binary Manager Expert. IMPLEMENT complete binary discovery:
   - Create src/shannon_mcp/managers/binary.py
   - Implement cross-platform Claude Code binary discovery
   - Handle NVM paths, version detection, caching
   - Build update checking and persistence
   DELIVER: Complete binary management system"
   ```

4. **Session Orchestrator** - Session management
   ```
   Task: "You are the Session Orchestrator. IMPLEMENT session lifecycle:
   - Create src/shannon_mcp/managers/session.py
   - Implement subprocess execution wrapper
   - Build session caching, cancellation, timeout handling
   - Create resource management and cleanup
   DELIVER: Complete session management system"
   ```

### PHASE 2: STREAMING & STORAGE (Task tool batch 2)

5. **Streaming Agent** - JSONL streaming system
   ```
   Task: "You are the Streaming Agent. IMPLEMENT JSONL streaming:
   - Create src/shannon_mcp/streaming/jsonl.py
   - Implement async stream reader with backpressure handling
   - Build message buffering and notification forwarding
   - Create metrics extraction and error recovery
   DELIVER: Production streaming system"
   ```

6. **JSONL Agent** - Parser implementation
   ```
   Task: "You are the JSONL Agent. IMPLEMENT JSONL parsing:
   - Create robust JSONL parser with schema validation
   - Handle streaming JSON with error recovery
   - Implement message type handlers
   - Build efficient parsing with buffering
   DELIVER: Complete JSONL processing system"
   ```

7. **Storage Agent** - Database and CAS
   ```
   Task: "You are the Storage Agent. IMPLEMENT database systems:
   - Create src/shannon_mcp/storage/ with SQLite implementation
   - Implement content-addressable storage with SHA-256
   - Build Zstd compression and data persistence
   - Create agent database schema and CRUD operations
   DELIVER: Complete storage infrastructure"
   ```

8. **Checkpoint Expert** - Versioning system
   ```
   Task: "You are the Checkpoint Expert. IMPLEMENT checkpoint system:
   - Create src/shannon_mcp/checkpoint/ with Git-like versioning
   - Implement timeline management and branching support
   - Build restore logic and cleanup routines
   - Create content-addressable checkpoint storage
   DELIVER: Complete versioning system"
   ```

### PHASE 3: INTEGRATION & TRANSPORT (Task tool batch 3)

9. **Integration Agent** - Component integration
   ```
   Task: "You are the Integration Agent. IMPLEMENT component integration:
   - Connect all components with proper API integration
   - Design data flow and component communication
   - Ensure seamless interaction between all 26 agents' work
   - Create integration testing and validation
   DELIVER: Fully integrated system"
   ```

10. **MCP Client Expert** - Transport protocols
    ```
    Task: "You are the MCP Client Expert. IMPLEMENT transport layer:
    - Create src/shannon_mcp/transport/ with STDIO, SSE support
    - Implement connection testing and config import
    - Build server discovery and health monitoring
    - Create transport protocol negotiation
    DELIVER: Complete transport infrastructure"
    ```

11. **Settings Manager** - Configuration system
    ```
    Task: "You are the Settings Manager. IMPLEMENT configuration:
    - Create src/shannon_mcp/utils/config.py (already exists - enhance)
    - Implement file watchers and hot reload
    - Build validation logic and migration system
    - Create defaults handling and schema validation
    DELIVER: Complete configuration management"
    ```

12. **Hooks Framework Agent** - Event system
    ```
    Task: "You are the Hooks Framework Agent. IMPLEMENT hooks system:
    - Enhance src/shannon_mcp/hooks/ (already exists)
    - Implement execution engine and security sandbox
    - Build template system and command validation
    - Create comprehensive hook configuration
    DELIVER: Production hooks framework"
    ```

### PHASE 4: QUALITY & SECURITY (Task tool batch 4)

13. **Testing Agent** - Complete test coverage
    ```
    Task: "You are the Testing Agent. IMPLEMENT comprehensive testing:
    - Create tests/ directory with full test infrastructure
    - Build unit tests, integration tests, end-to-end tests
    - Implement performance benchmarks and error scenario tests
    - Create test fixtures and automated test runners
    DELIVER: Complete test coverage for all components"
    ```

14. **Security Agent** - Security implementation
    ```
    Task: "You are the Security Agent. IMPLEMENT security features:
    - Build input validation and command sanitization
    - Implement audit logging and rate limiting
    - Create encryption support and vulnerability prevention
    - Ensure security across all components
    DELIVER: Production security implementation"
    ```

15. **Code Quality Agent** - Standards enforcement
    ```
    Task: "You are the Code Quality Agent. ENFORCE code standards:
    - Review and refactor all code for maintainability
    - Implement design patterns and code quality checks
    - Ensure SOLID principles and architectural consistency
    - Create code review automation
    DELIVER: High-quality, maintainable codebase"
    ```

16. **Error Handler** - Error management
    ```
    Task: "You are the Error Handler. IMPLEMENT error handling:
    - Create comprehensive error handling framework
    - Implement recovery strategies and graceful degradation
    - Build structured logging and error tracking
    - Ensure robust error handling across all components
    DELIVER: Production-grade error management"
    ```

### PHASE 5: MONITORING & ANALYTICS (Task tool batch 5)

17. **Monitoring Agent** - System monitoring
    ```
    Task: "You are the Monitoring Agent. IMPLEMENT monitoring:
    - Create health check endpoints and metrics collection
    - Implement alerting rules and distributed tracing
    - Build system observability and performance tracking
    - Create monitoring dashboards and alerts
    DELIVER: Complete monitoring infrastructure"
    ```

18. **Analytics Agent** - Usage analytics
    ```
    Task: "You are the Analytics Agent. IMPLEMENT analytics:
    - Create src/shannon_mcp/analytics/ with usage tracking
    - Implement metrics aggregation and report generation
    - Build data visualization and analytics processing
    - Create usage analytics and reporting system
    DELIVER: Complete analytics infrastructure"
    ```

19. **Performance Agent** - Performance optimization
    ```
    Task: "You are the Performance Agent. OPTIMIZE performance:
    - Profile all critical paths and optimize bottlenecks
    - Implement caching layers and connection pooling
    - Optimize database queries and file operations
    - Create performance monitoring and optimization
    DELIVER: High-performance optimized system"
    ```

20. **Process Registry Agent** - Process tracking
    ```
    Task: "You are the Process Registry Agent. IMPLEMENT process registry:
    - Create src/shannon_mcp/registry/ with PID tracking
    - Implement process validation and cleanup routines
    - Build resource monitoring and registry storage
    - Create system-wide process management
    DELIVER: Complete process registry system"
    ```

### PHASE 6: SPECIALIZED FEATURES (Task tool batch 6)

21. **Command Palette Agent** - Command system
    ```
    Task: "You are the Command Palette Agent. IMPLEMENT command system:
    - Create src/shannon_mcp/commands/ with markdown parsing
    - Implement frontmatter extraction and command registry
    - Build execution framework and categorization
    - Create command validation and processing
    DELIVER: Complete command palette system"
    ```

22. **Claude SDK Expert** - SDK integration
    ```
    Task: "You are the Claude SDK Expert. IMPLEMENT SDK integration:
    - Deep integration with Claude Code internals and APIs
    - Implement SDK usage patterns and API connections
    - Build Claude-specific optimizations and features
    - Create seamless Claude Code integration
    DELIVER: Production Claude SDK integration"
    ```

23. **Platform Compatibility** - Cross-platform support
    ```
    Task: "You are the Platform Compatibility agent. ENSURE compatibility:
    - Implement cross-platform path handling and OS integration
    - Handle platform-specific features and requirements
    - Build compatibility layers for Linux/macOS/Windows
    - Test and validate cross-platform functionality
    DELIVER: Full cross-platform compatibility"
    ```

24. **Migration Agent** - Version migration
    ```
    Task: "You are the Migration Agent. IMPLEMENT migration:
    - Create data migration between versions
    - Implement backward compatibility and schema evolution
    - Build migration tools and compatibility layers
    - Ensure smooth version transitions
    DELIVER: Complete migration infrastructure"
    ```

25. **Deployment Agent** - CI/CD and deployment
    ```
    Task: "You are the Deployment Agent. IMPLEMENT deployment:
    - Create GitHub Actions workflow and PyPI publishing
    - Implement version tagging and changelog generation
    - Build release automation and deployment pipelines
    - Create containerization and CI/CD infrastructure
    DELIVER: Complete deployment automation"
    ```

26. **Documentation Agent** - Complete documentation
    ```
    Task: "You are the Documentation Agent. CREATE documentation:
    - Write comprehensive API documentation and user guides
    - Create troubleshooting guides and deployment docs
    - Build code documentation and usage examples
    - Generate complete project documentation
    DELIVER: Production-ready documentation"
    ```

## EXECUTION STRATEGY - PARALLEL COORDINATION

### CRITICAL: Execute using Task tool in parallel batches

**Implementation Steps:**

1. **Initialize TodoWrite** with all 125+ Shannon MCP tasks from specification
2. **Batch 1**: Spawn Architecture Agent, Python MCP Expert, Binary Manager Expert, Session Orchestrator
3. **Batch 2**: Spawn Streaming Agent, JSONL Agent, Storage Agent, Checkpoint Expert  
4. **Batch 3**: Spawn Integration Agent, MCP Client Expert, Settings Manager, Hooks Framework Agent
5. **Batch 4**: Spawn Testing Agent, Security Agent, Code Quality Agent, Error Handler
6. **Batch 5**: Spawn Monitoring Agent, Analytics Agent, Performance Agent, Process Registry Agent
7. **Batch 6**: Spawn Command Palette Agent, Claude SDK Expert, Platform Compatibility, Migration Agent, Deployment Agent, Documentation Agent

### COORDINATION MECHANISM

- Each agent works on specific file paths in src/shannon_mcp/
- Agents coordinate through shared file system and interfaces
- Integration Agent ensures all components work together
- Architecture Agent provides system design constraints
- Testing Agent validates all integrations

### DELIVERABLE

**Complete, production-ready Shannon MCP Server with:**
- Full MCP protocol implementation
- Binary discovery and session management
- JSONL streaming and checkpointing
- Hooks framework and command system
- Analytics and monitoring
- Security and performance optimization
- Cross-platform compatibility
- Complete test coverage
- Comprehensive documentation
- CI/CD and deployment automation

**THIS COMMAND BUILDS THE ENTIRE SHANNON MCP SERVER - NOT A MOCK**