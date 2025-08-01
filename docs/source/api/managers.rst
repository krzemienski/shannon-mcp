Managers API Reference
======================

This section documents the core manager classes that form the foundation of Shannon MCP.

Base Manager
------------

.. module:: shannon_mcp.base.manager

.. autoclass:: BaseManager
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   The BaseManager provides lifecycle management for all Shannon MCP components.

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.base.manager import BaseManager

      class MyManager(BaseManager):
          async def initialize(self):
              await super().initialize()
              # Custom initialization
              
          async def cleanup(self):
              # Custom cleanup
              await super().cleanup()

Binary Manager
--------------

.. module:: shannon_mcp.managers.binary

.. autoclass:: BinaryManager
   :members:
   :undoc-members:
   :show-inheritance:

   Discovers and manages Claude Code binary installations.

   **Key Methods:**

   .. automethod:: discover_binaries
   .. automethod:: get_binary
   .. automethod:: validate_binary
   .. automethod:: check_updates

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.managers.binary import BinaryManager

      async def find_claude_code():
          manager = BinaryManager()
          await manager.initialize()
          
          # Discover all binaries
          binaries = await manager.discover_binaries()
          for binary in binaries:
              print(f"Found: {binary.path} (v{binary.version})")
          
          # Get specific binary
          binary = await manager.get_binary(min_version="1.0.0")
          if binary:
              print(f"Using: {binary.path}")

   **Discovery Methods:**

   The BinaryManager uses multiple strategies to find Claude Code:

   1. **Which Command** - Uses system ``which`` command
   2. **NVM Discovery** - Checks Node Version Manager installations
   3. **Standard Paths** - Searches platform-specific locations
   4. **Database Cache** - Returns previously discovered binaries

Session Manager
---------------

.. module:: shannon_mcp.managers.session

.. autoclass:: SessionManager
   :members:
   :undoc-members:
   :show-inheritance:

   Manages Claude Code session lifecycle and streaming.

   **Key Methods:**

   .. automethod:: create_session
   .. automethod:: get_session
   .. automethod:: execute_prompt
   .. automethod:: stream_prompt
   .. automethod:: cancel_session

   **Session Options:**

   .. code-block:: python

      options = {
          "model": "claude-3-opus-20240229",
          "temperature": 0.7,
          "max_tokens": 4000,
          "system_prompt": "You are a helpful assistant",
          "stop_sequences": ["\\n\\n"],
          "top_p": 0.9,
          "top_k": 40
      }

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.managers.session import SessionManager
      from shannon_mcp.managers.binary import BinaryManager

      async def chat_session():
          binary_manager = BinaryManager()
          session_manager = SessionManager(binary_manager)
          
          await session_manager.initialize()
          
          # Create session
          session = await session_manager.create_session(
              session_id="my-chat",
              options={"temperature": 0.5}
          )
          
          # Execute prompt
          response = await session_manager.execute_prompt(
              session.id,
              "Explain quantum computing"
          )
          print(response)
          
          # Stream response
          async for chunk in session_manager.stream_prompt(
              session.id,
              "Write a story about AI"
          ):
              print(chunk, end="", flush=True)

   **Session States:**

   .. list-table::
      :header-rows: 1

      * - State
        - Description
      * - CREATED
        - Session initialized but not started
      * - STARTING
        - Claude Code process is starting
      * - RUNNING
        - Session is active and ready
      * - COMPLETED
        - Session finished successfully
      * - FAILED
        - Session encountered an error
      * - CANCELLED
        - Session was cancelled by user

Agent Manager
-------------

.. module:: shannon_mcp.managers.agent

.. autoclass:: AgentManager
   :members:
   :undoc-members:
   :show-inheritance:

   Manages the 26 specialized AI agents.

   **Agent Types:**

   .. list-table::
      :header-rows: 1

      * - Category
        - Agents
      * - Core Architecture
        - Architecture, Infrastructure, Integration, Orchestration
      * - Development
        - Backend, Frontend, Full-Stack, Database
      * - Quality
        - Testing, Code Review, Documentation, Security
      * - Operations
        - DevOps, Monitoring, Performance, Deployment
      * - Specialized
        - UI/UX, API, Data Engineering, ML, Mobile, Cloud

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.managers.agent import AgentManager

      async def use_agents():
          manager = AgentManager(db, session_manager)
          await manager.initialize()
          
          # Register an agent
          agent = await manager.register_agent({
              "name": "Code Review Agent",
              "type": "quality",
              "capabilities": ["code_review", "security_audit"],
              "expertise_level": 0.9
          })
          
          # Assign task
          task = await manager.assign_task(
              agent_id=agent.id,
              task_type="review",
              description="Review authentication module",
              context={"file_path": "src/auth.py"}
          )
          
          # Execute task
          result = await manager.execute_task(task.id)
          print(f"Review: {result.output}")

   **Multi-Agent Collaboration:**

   .. code-block:: python

      # Create collaboration group
      group = await manager.create_collaboration_group({
          "name": "Feature Team",
          "agents": [architect.id, developer.id, tester.id],
          "coordination": "sequential"
      })
      
      # Assign collaborative task
      result = await manager.assign_collaborative_task({
          "group_id": group.id,
          "description": "Implement user registration",
          "subtasks": [
              {"agent": architect.id, "task": "Design API"},
              {"agent": developer.id, "task": "Implement endpoints"},
              {"agent": tester.id, "task": "Write tests"}
          ]
      })

Checkpoint Manager
------------------

.. module:: shannon_mcp.storage.checkpoint

.. autoclass:: CheckpointManager
   :members:
   :undoc-members:
   :show-inheritance:

   Provides Git-like checkpoint functionality for sessions.

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.storage.checkpoint import CheckpointManager

      async def checkpoint_workflow():
          manager = CheckpointManager(checkpoint_dir, cas, session_manager)
          
          # Create checkpoint
          checkpoint = await manager.create_checkpoint(
              session_id="my-session",
              description="Before major refactoring",
              tags=["stable", "v1.0"]
          )
          
          # List checkpoints
          checkpoints = await manager.list_checkpoints(
              session_id="my-session",
              tags=["stable"]
          )
          
          # Restore checkpoint
          new_session = await manager.restore_checkpoint(
              checkpoint.id,
              new_session_id="restored-session"
          )
          
          # Create branch
          branch = await manager.create_branch(
              checkpoint.id,
              branch_name="feature/new-ui"
          )

Analytics Manager
-----------------

.. module:: shannon_mcp.analytics.engine

.. autoclass:: AnalyticsEngine
   :members:
   :undoc-members:
   :show-inheritance:

   Collects and analyzes usage metrics.

   **Metrics Types:**

   - Session metrics (start, complete, duration)
   - Performance metrics (response time, throughput)
   - Resource metrics (CPU, memory, disk)
   - Token metrics (usage, cost estimates)
   - Error metrics (types, frequency, recovery)

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.analytics.engine import AnalyticsEngine

      async def analytics_example():
          engine = AnalyticsEngine(db)
          await engine.initialize()
          
          # Track metric
          await engine.track_metric({
              "type": "session_complete",
              "session_id": "123",
              "duration": 145.3,
              "tokens_used": 1523
          })
          
          # Generate report
          report = await engine.generate_report(
              start_date=datetime.now() - timedelta(days=7),
              metrics=["sessions", "tokens", "errors"],
              format="html"
          )
          
          # Real-time monitoring
          async for metric in engine.stream_metrics():
              print(f"{metric.type}: {metric.value}")

Common Patterns
---------------

Manager Lifecycle
~~~~~~~~~~~~~~~~~

All managers follow a consistent lifecycle pattern:

.. code-block:: python

   manager = SomeManager(dependencies)
   
   try:
       # Initialize (connect to resources)
       await manager.initialize()
       
       # Use the manager
       result = await manager.some_operation()
       
   finally:
       # Always cleanup
       await manager.cleanup()

Error Handling
~~~~~~~~~~~~~~

Managers provide consistent error handling:

.. code-block:: python

   from shannon_mcp.errors import (
       BinaryNotFoundError,
       SessionError,
       AgentError
   )

   try:
       binary = await binary_manager.get_binary()
   except BinaryNotFoundError:
       print("Claude Code not found. Please install it.")
   except Exception as e:
       print(f"Unexpected error: {e}")

Event System
~~~~~~~~~~~~

Managers emit events through the notification system:

.. code-block:: python

   from shannon_mcp.notifications import NotificationCenter

   async def setup_listeners():
       center = NotificationCenter()
       
       # Subscribe to events
       await center.subscribe(
           "session.created",
           lambda event: print(f"New session: {event.session_id}")
       )
       
       await center.subscribe(
           "agent.task_complete",
           lambda event: print(f"Task done: {event.result}")
       )