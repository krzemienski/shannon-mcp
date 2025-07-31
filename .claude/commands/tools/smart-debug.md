# Shannon MCP Smart Debug System

DEBUG and troubleshoot the Shannon MCP Server using all 26 specialized Shannon MCP agents with coordinated parallel execution for rapid issue resolution.

## Overview

This command orchestrates comprehensive debugging of the Shannon MCP Server, from initial error analysis through root cause resolution and system validation, using all specialized agents working in parallel coordination.

## Usage - DEBUG SHANNON MCP SERVER ISSUES

```bash
/smart-debug [error-description] [--component=binary|session|streaming|storage|all]
```

## COMPREHENSIVE DEBUG PROCESS - ALL 26 SHANNON MCP AGENTS

### PHASE 1: ERROR ANALYSIS AND TRIAGE (Task tool batch 1)

1. **Error Handler** - Primary error analysis
   ```
   Task: "You are the Error Handler. ANALYZE Shannon MCP error:
   - Examine error symptoms, stack traces, and system state
   - Categorize error type (binary, session, streaming, storage, etc.)
   - Identify immediate containment and mitigation strategies
   - Create error timeline and impact assessment
   DELIVER: Comprehensive error analysis with triage classification"
   ```

2. **Monitoring Agent** - System health assessment
   ```
   Task: "You are the Monitoring Agent. ASSESS Shannon MCP system health:
   - Check all component health endpoints and metrics
   - Analyze system resource usage and performance
   - Identify system-wide impact and cascading effects
   - Review monitoring alerts and system events
   DELIVER: Complete system health report with anomaly detection"
   ```

3. **Analytics Agent** - Historical pattern analysis
   ```
   Task: "You are the Analytics Agent. ANALYZE error patterns:
   - Search historical data for similar error occurrences
   - Identify trends, correlations, and recurring patterns
   - Analyze system usage patterns before error occurrence
   - Create predictive analysis for error prevention
   DELIVER: Historical error analysis with pattern recognition"
   ```

4. **Process Registry Agent** - Process state analysis
   ```
   Task: "You are the Process Registry Agent. ANALYZE process states:
   - Check all Shannon MCP process states in registry
   - Identify orphaned, hung, or crashed processes
   - Analyze resource consumption and process health
   - Create process cleanup and recovery recommendations
   DELIVER: Complete process state analysis with recovery plan"
   ```

### PHASE 2: COMPONENT-SPECIFIC DEBUGGING (Task tool batch 2)

5. **Binary Manager Expert** - Binary system debugging
   ```
   Task: "You are the Binary Manager Expert. DEBUG binary management:
   - Validate Claude Code binary discovery and version detection
   - Check binary cache integrity and path resolution
   - Test binary execution and subprocess creation
   - Analyze binary compatibility and dependency issues
   DELIVER: Binary management debugging report with fixes"
   ```

6. **Session Orchestrator** - Session debugging
   ```
   Task: "You are the Session Orchestrator. DEBUG session management:
   - Analyze session lifecycle and state management issues
   - Check session creation, caching, and cleanup processes
   - Validate session cancellation and timeout handling
   - Debug subprocess execution and resource management
   DELIVER: Session orchestration debugging with resolution steps"
   ```

7. **Streaming Agent** - JSONL streaming debugging
   ```
   Task: "You are the Streaming Agent. DEBUG streaming system:
   - Analyze JSONL stream parsing and backpressure handling
   - Check message buffering and notification forwarding
   - Debug stream interruptions and recovery mechanisms
   - Validate metrics extraction and error handling
   DELIVER: Streaming system debugging with performance fixes"
   ```

8. **Storage Agent** - Database and storage debugging
   ```
   Task: "You are the Storage Agent. DEBUG storage systems:
   - Analyze database connection and query performance
   - Check content-addressable storage integrity
   - Debug data compression and persistence issues
   - Validate storage cleanup and garbage collection
   DELIVER: Storage system debugging with optimization fixes"
   ```

### PHASE 3: ADVANCED SYSTEM DEBUGGING (Task tool batch 3)

9. **Checkpoint Expert** - Checkpoint system debugging
   ```
   Task: "You are the Checkpoint Expert. DEBUG checkpoint system:
   - Analyze checkpoint creation and restoration failures
   - Check content-addressable storage for corrupted data
   - Debug compression and decompression issues
   - Validate checkpoint cleanup and timeline management
   DELIVER: Checkpoint system debugging with data recovery"
   ```

10. **Hooks Framework Agent** - Hooks system debugging
    ```
    Task: "You are the Hooks Framework Agent. DEBUG hooks system:
    - Analyze hook execution failures and timeout issues
    - Check hook configuration and security validation
    - Debug template processing and command execution
    - Validate hook ordering and dependency resolution
    DELIVER: Hooks framework debugging with execution fixes"
    ```

11. **Settings Manager** - Configuration debugging
    ```
    Task: "You are the Settings Manager. DEBUG configuration system:
    - Analyze configuration loading and validation errors
    - Check file watching and hot-reload functionality
    - Debug schema validation and migration issues
    - Validate defaults handling and override logic
    DELIVER: Configuration system debugging with validation fixes"
    ```

12. **MCP Client Expert** - Transport debugging
    ```
    Task: "You are the MCP Client Expert. DEBUG transport layer:
    - Analyze MCP protocol connection and communication issues
    - Check STDIO and SSE transport functionality
    - Debug server discovery and health monitoring
    - Validate protocol compliance and message handling
    DELIVER: Transport layer debugging with connection fixes"
    ```

### PHASE 4: INTEGRATION AND PROTOCOL DEBUGGING (Task tool batch 4)

13. **Python MCP Expert** - MCP protocol debugging
    ```
    Task: "You are the Python MCP Expert. DEBUG MCP implementation:
    - Analyze MCP server initialization and message handling
    - Check protocol compliance and async processing
    - Debug connection management and lifecycle issues
    - Validate FastMCP implementation and performance
    DELIVER: MCP protocol debugging with compliance fixes"
    ```

14. **Integration Agent** - System integration debugging
    ```
    Task: "You are the Integration Agent. DEBUG component integration:
    - Analyze inter-component communication failures
    - Check data flow and interface compatibility
    - Debug component dependency and initialization order
    - Validate system-wide integration and coordination
    DELIVER: Integration debugging with component coordination fixes"
    ```

15. **Command Palette Agent** - Command system debugging
    ```
    Task: "You are the Command Palette Agent. DEBUG command system:
    - Analyze markdown parsing and frontmatter extraction
    - Check command registry and execution framework
    - Debug command validation and categorization
    - Validate command processing and response handling
    DELIVER: Command system debugging with execution fixes"
    ```

16. **JSONL Agent** - JSONL processing debugging
    ```
    Task: "You are the JSONL Agent. DEBUG JSONL processing:
    - Analyze JSONL parsing and validation errors
    - Check message type handling and schema compliance
    - Debug stream processing and buffering issues
    - Validate error recovery and resilience mechanisms
    DELIVER: JSONL processing debugging with parser fixes"
    ```

### PHASE 5: QUALITY AND SECURITY DEBUGGING (Task tool batch 5)

17. **Security Agent** - Security issue debugging
    ```
    Task: "You are the Security Agent. DEBUG security issues:
    - Analyze input validation and sanitization failures
    - Check authentication and authorization problems
    - Debug security sandbox and access control issues
    - Validate encryption and data protection mechanisms
    DELIVER: Security debugging with vulnerability fixes"
    ```

18. **Code Quality Agent** - Code quality debugging
    ```
    Task: "You are the Code Quality Agent. DEBUG code quality issues:
    - Analyze code structure and architectural violations
    - Check design pattern implementation and consistency
    - Debug maintainability and technical debt issues
    - Validate code standards and best practices
    DELIVER: Code quality debugging with refactoring recommendations"
    ```

19. **Testing Agent** - Test failure debugging
    ```
    Task: "You are the Testing Agent. DEBUG test failures:
    - Analyze test suite failures and flaky tests
    - Check test coverage and integration test issues
    - Debug performance benchmark failures
    - Validate test environment and fixture problems
    DELIVER: Test debugging with coverage and stability fixes"
    ```

20. **Performance Agent** - Performance debugging
    ```
    Task: "You are the Performance Agent. DEBUG performance issues:
    - Analyze system bottlenecks and resource contention
    - Check memory leaks and CPU utilization problems
    - Debug I/O performance and latency issues
    - Validate caching and optimization effectiveness
    DELIVER: Performance debugging with optimization fixes"
    ```

### PHASE 6: PLATFORM AND DEPLOYMENT DEBUGGING (Task tool batch 6)

21. **Platform Compatibility** - Cross-platform debugging
    ```
    Task: "You are the Platform Compatibility agent. DEBUG platform issues:
    - Analyze platform-specific failures and incompatibilities
    - Check file system and path handling problems
    - Debug OS-specific functionality and permissions
    - Validate cross-platform feature consistency
    DELIVER: Platform debugging with compatibility fixes"
    ```

22. **Migration Agent** - Migration debugging
    ```
    Task: "You are the Migration Agent. DEBUG migration issues:
    - Analyze data migration failures and corruption
    - Check version compatibility and schema evolution
    - Debug migration rollback and recovery problems
    - Validate migration validation and integrity checks
    DELIVER: Migration debugging with data recovery fixes"
    ```

23. **Deployment Agent** - Deployment debugging
    ```
    Task: "You are the Deployment Agent. DEBUG deployment issues:
    - Analyze CI/CD pipeline failures and deployment errors
    - Check containerization and packaging problems
    - Debug release automation and validation issues
    - Validate deployment monitoring and rollback mechanisms
    DELIVER: Deployment debugging with automation fixes"
    ```

24. **Documentation Agent** - Documentation debugging
    ```
    Task: "You are the Documentation Agent. DEBUG documentation issues:
    - Analyze documentation generation and validation errors
    - Check API documentation accuracy and completeness
    - Debug troubleshooting guide effectiveness
    - Validate documentation consistency and updates
    DELIVER: Documentation debugging with accuracy fixes"
    ```

25. **Claude SDK Expert** - SDK integration debugging
    ```
    Task: "You are the Claude SDK Expert. DEBUG Claude integration:
    - Analyze Claude Code API integration failures
    - Check SDK version compatibility and feature detection
    - Debug authentication and session management issues
    - Validate Claude-specific optimizations and performance
    DELIVER: Claude SDK debugging with integration fixes"
    ```

26. **Architecture Agent** - System architecture debugging
    ```
    Task: "You are the Architecture Agent. DEBUG architectural issues:
    - Analyze system design violations and architectural debt
    - Check component boundaries and interface consistency
    - Debug system scalability and reliability problems
    - Validate architectural decisions and trade-offs
    DELIVER: Architecture debugging with system design fixes"
    ```

## EXECUTION STRATEGY - PARALLEL DEBUG COORDINATION

### CRITICAL: Execute using Task tool in parallel batches

**Implementation Steps:**

1. **Initialize TodoWrite** with all debugging tasks prioritized by severity
2. **Batch 1**: Error analysis, System health, Pattern analysis, Process state
3. **Batch 2**: Component debugging - Binary, Session, Streaming, Storage
4. **Batch 3**: Advanced debugging - Checkpoints, Hooks, Settings, Transport
5. **Batch 4**: Integration debugging - MCP protocol, Integration, Commands, JSONL
6. **Batch 5**: Quality debugging - Security, Code quality, Testing, Performance
7. **Batch 6**: Platform debugging - Compatibility, Migration, Deployment, Documentation, SDK, Architecture

### COORDINATION MECHANISM

- Error Handler leads triage and coordinates all debugging efforts
- Monitoring Agent provides real-time system health during debugging
- Each agent debugs their specific domain while sharing findings
- Integration Agent ensures debugging fixes work together seamlessly
- Architecture Agent validates system consistency after fixes
- Testing Agent validates all debugging fixes with comprehensive tests

### DELIVERABLE

**Complete Shannon MCP Server debugging with:**
- Root cause identification and resolution
- Comprehensive system health validation
- Performance optimization and bottleneck removal
- Security vulnerability fixes and hardening
- Cross-platform compatibility validation
- Complete integration testing and validation
- Documentation updates and troubleshooting guides
- Automated deployment and monitoring improvements
- System architecture validation and optimization
- Long-term reliability and stability improvements

**THIS COMMAND DEBUGS THE REAL SHANNON MCP SERVER - ACTUAL ISSUE RESOLUTION**

Debug target: Shannon MCP Server issue - $ARGUMENTS