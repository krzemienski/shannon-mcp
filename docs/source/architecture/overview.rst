Architecture Overview
=====================

Shannon MCP is built on a modular, async-first architecture designed for scalability, reliability, and extensibility. This document provides a comprehensive overview of the system architecture.

Core Architecture Principles
----------------------------

1. **Async-First Design**
   
   All components use Python's asyncio for concurrent operations:
   
   - Non-blocking I/O for subprocess communication
   - Concurrent session management
   - Parallel agent execution
   - Asynchronous database operations

2. **Manager Pattern**
   
   Each major component extends ``BaseManager`` for consistent lifecycle:
   
   .. code-block:: python
   
      async def lifecycle():
          manager = ComponentManager()
          await manager.initialize()  # Setup resources
          try:
              await manager.operate()  # Main operations
          finally:
              await manager.cleanup()  # Clean shutdown

3. **Event-Driven Communication**
   
   Components communicate through a central notification system:
   
   - Loose coupling between components
   - Pub/sub pattern for scalability
   - Priority-based event handling
   - Async event processing

4. **Layered Architecture**
   
   Clear separation of concerns across layers:
   
   .. code-block:: text
   
      ┌─────────────────────────────────────┐
      │         MCP Interface Layer         │
      ├─────────────────────────────────────┤
      │         Manager Layer               │
      │  (Binary, Session, Agent, etc.)     │
      ├─────────────────────────────────────┤
      │         Core Services Layer         │
      │  (Streaming, Storage, Analytics)    │
      ├─────────────────────────────────────┤
      │      Infrastructure Layer           │
      │  (Database, Filesystem, Network)    │
      └─────────────────────────────────────┘

System Components
-----------------

MCP Server
~~~~~~~~~~

The main entry point that implements the Model Context Protocol:

.. code-block:: text

   ┌──────────────────┐
   │   MCP Client     │
   │  (Claude Code)   │
   └────────┬─────────┘
            │ MCP Protocol
   ┌────────▼─────────┐
   │  Shannon MCP     │
   │     Server       │
   ├──────────────────┤
   │ • Request Router │
   │ • Auth Handler   │
   │ • Rate Limiter   │
   │ • Response Cache │
   └──────────────────┘

Binary Manager
~~~~~~~~~~~~~~

Discovers and manages Claude Code installations:

.. code-block:: text

   ┌─────────────────────┐
   │   Binary Manager    │
   ├─────────────────────┤
   │ Discovery Strategies│
   │ ┌─────────────────┐ │
   │ │ Which Command   │ │
   │ │ NVM Paths       │ │
   │ │ Standard Paths  │ │
   │ │ Database Cache  │ │
   │ └─────────────────┘ │
   ├─────────────────────┤
   │ Version Management  │
   │ Update Checking     │
   └─────────────────────┘

Session Manager
~~~~~~~~~~~~~~~

Manages Claude Code session lifecycle:

.. code-block:: text

   ┌──────────────────────┐
   │   Session Manager    │
   ├──────────────────────┤
   │  Session Lifecycle   │
   │  ┌────────────────┐  │
   │  │ Created        │  │
   │  │   ↓            │  │
   │  │ Starting       │  │
   │  │   ↓            │  │
   │  │ Running        │  │
   │  │   ↓            │  │
   │  │ Completed/     │  │
   │  │ Failed/        │  │
   │  │ Cancelled      │  │
   │  └────────────────┘  │
   ├──────────────────────┤
   │ • Process Management │
   │ • Stream Handling    │
   │ • State Tracking     │
   └──────────────────────┘

Streaming System
~~~~~~~~~~~~~~~~

Handles JSONL communication with Claude Code:

.. code-block:: text

   ┌─────────────────────────────────────┐
   │         Streaming Pipeline          │
   ├─────────────────────────────────────┤
   │  Claude Code Process                │
   │         ↓                           │
   │  Async Stream Reader                │
   │         ↓                           │
   │  Stream Buffer (Backpressure)       │
   │         ↓                           │
   │  JSONL Parser                       │
   │         ↓                           │
   │  Message Router                     │
   │         ↓                           │
   │  Type Handlers                      │
   │    • Content Handler                │
   │    • Notification Handler           │
   │    • Error Handler                  │
   │    • Metrics Handler                │
   └─────────────────────────────────────┘

Storage Architecture
~~~~~~~~~~~~~~~~~~~~

Multi-tier storage system:

.. code-block:: text

   ┌──────────────────────────────────┐
   │      Storage Architecture        │
   ├──────────────────────────────────┤
   │  Content-Addressable Storage     │
   │  • SHA-256 deduplication         │
   │  • Zstd compression              │
   │  • Chunked storage               │
   ├──────────────────────────────────┤
   │  SQLite Database                 │
   │  • Metadata storage              │
   │  • Relational data              │
   │  • Full-text search             │
   ├──────────────────────────────────┤
   │  Filesystem                      │
   │  • Binary files                  │
   │  • Temporary data                │
   │  • Log files                     │
   └──────────────────────────────────┘

Agent System
~~~~~~~~~~~~

26 specialized agents with orchestration:

.. code-block:: text

   ┌────────────────────────────────────┐
   │         Agent System               │
   ├────────────────────────────────────┤
   │     Agent Orchestrator             │
   │  ┌──────────┬─────────────────┐   │
   │  │ Scheduler│ Task Distributor│   │
   │  └─────┬────┴────────┬────────┘   │
   │        │             │             │
   │  ┌─────▼─────┐ ┌────▼──────┐     │
   │  │   Agent   │ │   Agent   │     │
   │  │  Pool 1   │ │  Pool 2   │     │
   │  └───────────┘ └───────────┘     │
   ├────────────────────────────────────┤
   │  Collaboration Framework           │
   │  • Message Passing                 │
   │  • Shared Memory                   │
   │  • Task Dependencies               │
   └────────────────────────────────────┘

Data Flow
---------

Request Processing Flow
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   Client Request
        ↓
   MCP Server (Authentication & Routing)
        ↓
   Request Handler (Validation)
        ↓
   Manager Layer (Business Logic)
        ↓
   Core Services (Execution)
        ↓
   Response Assembly
        ↓
   Client Response

Session Execution Flow
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   Create Session Request
        ↓
   Binary Manager (Find Claude Code)
        ↓
   Session Manager (Create Process)
        ↓
   Stream Processor (Setup Pipeline)
        ↓
   Execute Prompt
        ↓
   JSONL Streaming (Real-time)
        ↓
   Message Handling
        ↓
   Response Aggregation

Concurrency Model
-----------------

Task Management
~~~~~~~~~~~~~~~

Shannon MCP uses hierarchical task management:

.. code-block:: python

   # Root task
   server_task = asyncio.create_task(server.run())
   
   # Manager tasks
   manager_tasks = [
       asyncio.create_task(binary_manager.run()),
       asyncio.create_task(session_manager.run()),
       asyncio.create_task(agent_manager.run())
   ]
   
   # Session tasks (dynamic)
   session_tasks = {}
   for session in active_sessions:
       session_tasks[session.id] = asyncio.create_task(
           process_session(session)
       )

Resource Pooling
~~~~~~~~~~~~~~~~

Connection and resource pooling for efficiency:

.. code-block:: text

   ┌─────────────────────────┐
   │   Resource Pools        │
   ├─────────────────────────┤
   │ Database Connections    │
   │ • Max: 20               │
   │ • Timeout: 30s          │
   ├─────────────────────────┤
   │ Process Pool            │
   │ • Max: 10               │
   │ • Reuse: Yes            │
   ├─────────────────────────┤
   │ Thread Pool             │
   │ • Workers: 4            │
   │ • Queue: 100            │
   └─────────────────────────┘

Scalability Considerations
--------------------------

Horizontal Scaling
~~~~~~~~~~~~~~~~~~

Shannon MCP supports horizontal scaling through:

1. **Stateless Design** - Sessions can be distributed
2. **Shared Storage** - CAS and database can be centralized
3. **Event Bus** - Can be replaced with message queue
4. **Load Balancing** - Multiple server instances

Vertical Scaling
~~~~~~~~~~~~~~~~

Optimize single instance performance:

1. **Connection Pooling** - Reuse expensive resources
2. **Caching Layers** - Multiple levels of caching
3. **Async I/O** - Non-blocking operations
4. **Resource Limits** - Prevent resource exhaustion

Performance Optimization
------------------------

Critical Path Optimizations
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Binary Discovery** - Cached after first lookup
2. **Session Creation** - Process pool for fast startup
3. **Stream Processing** - Zero-copy buffering
4. **Message Parsing** - Optimized JSONL parser
5. **Database Queries** - Prepared statements and indices

Monitoring Points
~~~~~~~~~~~~~~~~~

Key metrics for performance monitoring:

.. list-table::
   :header-rows: 1

   * - Component
     - Metrics
   * - Binary Manager
     - Discovery time, cache hit rate
   * - Session Manager
     - Creation time, active sessions, queue depth
   * - Streaming
     - Throughput, latency, buffer usage
   * - Storage
     - I/O operations, compression ratio
   * - Agents
     - Task completion time, success rate

Security Architecture
---------------------

Defense in Depth
~~~~~~~~~~~~~~~~

Multiple security layers:

.. code-block:: text

   ┌─────────────────────────┐
   │   Security Layers       │
   ├─────────────────────────┤
   │ 1. Network Security     │
   │    • TLS/SSL            │
   │    • IP Filtering       │
   ├─────────────────────────┤
   │ 2. Authentication       │
   │    • API Keys           │
   │    • Token Validation   │
   ├─────────────────────────┤
   │ 3. Authorization        │
   │    • Role-Based Access  │
   │    • Resource Limits    │
   ├─────────────────────────┤
   │ 4. Process Isolation    │
   │    • Sandboxing         │
   │    • Resource Limits    │
   ├─────────────────────────┤
   │ 5. Data Protection      │
   │    • Encryption at Rest │
   │    • Secure Deletion    │
   └─────────────────────────┘

Extensibility
-------------

Shannon MCP is designed for extensibility:

1. **Plugin System** - Add custom managers
2. **Hook Framework** - Event-driven extensions
3. **Custom Agents** - Domain-specific agents
4. **Transport Adapters** - Alternative protocols
5. **Storage Backends** - Pluggable storage