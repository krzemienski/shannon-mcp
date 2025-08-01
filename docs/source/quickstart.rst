Quick Start Guide
=================

This guide will help you get started with Shannon MCP in just a few minutes.

Starting the MCP Server
-----------------------

Once installed, start the Shannon MCP server:

.. code-block:: bash

   shannon-mcp serve

The server will:

1. Discover Claude Code installations
2. Initialize the MCP server
3. Start listening for connections

Your First Session
------------------

Create a new session with Claude Code:

.. code-block:: python

   import asyncio
   from shannon_mcp import ShannonMCPClient

   async def main():
       # Connect to Shannon MCP server
       client = ShannonMCPClient()
       await client.connect()
       
       # Create a new session
       session = await client.create_session()
       print(f"Created session: {session.id}")
       
       # Send a prompt
       response = await session.prompt("Hello, Claude!")
       print(f"Response: {response}")
       
       # Close the session
       await session.close()
       await client.disconnect()

   asyncio.run(main())

Using the CLI
-------------

Shannon MCP provides a comprehensive CLI for managing sessions:

Creating Sessions
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Create a default session
   shannon-mcp session create
   
   # Create a named session with options
   shannon-mcp session create my-session \
     --model claude-3-opus-20240229 \
     --temperature 0.7

Listing Sessions
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # List all sessions
   shannon-mcp session list
   
   # List active sessions only
   shannon-mcp session list --active

Sending Prompts
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Send a prompt to a session
   shannon-mcp prompt "Write a Python hello world" --session my-session
   
   # Interactive mode
   shannon-mcp chat --session my-session

Working with Checkpoints
------------------------

Save and restore session states:

.. code-block:: bash

   # Create a checkpoint
   shannon-mcp checkpoint create --session my-session --name "v1.0"
   
   # List checkpoints
   shannon-mcp checkpoint list
   
   # Restore from checkpoint
   shannon-mcp checkpoint restore v1.0 --new-session restored-session

Using Agents
------------

Shannon MCP includes 26 specialized agents:

.. code-block:: bash

   # List available agents
   shannon-mcp agent list
   
   # Assign a task to an agent
   shannon-mcp agent assign \
     --agent "Code Review Agent" \
     --task "Review the authentication module"
   
   # Check agent status
   shannon-mcp agent status

Example: Code Review Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def code_review_workflow():
       client = ShannonMCPClient()
       await client.connect()
       
       # Create session
       session = await client.create_session()
       
       # Register code review agent
       agent = await client.register_agent("Code Review Agent")
       
       # Submit code for review
       result = await agent.review_code(
           file_path="src/auth.py",
           focus_areas=["security", "performance", "style"]
       )
       
       print(f"Review completed: {result.summary}")
       for issue in result.issues:
           print(f"- {issue.severity}: {issue.description}")

Setting Up Hooks
----------------

Configure automated actions with hooks:

.. code-block:: yaml

   # .shannon-mcp/hooks.yaml
   hooks:
     - name: "Auto-save checkpoint"
       event: "session.complete"
       command: "shannon-mcp checkpoint create --auto"
       
     - name: "Notify on error"
       event: "session.error"
       command: "notify-send 'Shannon MCP' 'Session error occurred'"
       
     - name: "Log metrics"
       event: "prompt.complete"
       command: "shannon-mcp analytics log --event prompt"

Register hooks:

.. code-block:: bash

   shannon-mcp hooks register .shannon-mcp/hooks.yaml

Monitoring Performance
----------------------

View real-time analytics:

.. code-block:: bash

   # Dashboard
   shannon-mcp analytics dashboard
   
   # Generate report
   shannon-mcp analytics report --period 7d --format html
   
   # Export metrics
   shannon-mcp analytics export --format csv --output metrics.csv

Example Scripts
---------------

Batch Processing
~~~~~~~~~~~~~~~~

Process multiple files with Claude Code:

.. code-block:: python

   async def batch_process(files):
       client = ShannonMCPClient()
       await client.connect()
       
       session = await client.create_session()
       
       for file_path in files:
           # Create checkpoint before processing
           checkpoint = await session.create_checkpoint(f"before-{file_path}")
           
           try:
               # Process file
               result = await session.prompt(
                   f"Refactor and optimize this code:\n{read_file(file_path)}"
               )
               
               # Save result
               write_file(f"{file_path}.optimized", result)
               
           except Exception as e:
               # Restore on error
               await session.restore_checkpoint(checkpoint)
               print(f"Error processing {file_path}: {e}")

Collaborative Agents
~~~~~~~~~~~~~~~~~~~~

Multiple agents working together:

.. code-block:: python

   async def collaborative_development():
       client = ShannonMCPClient()
       await client.connect()
       
       # Create agent team
       architect = await client.register_agent("Architecture Agent")
       developer = await client.register_agent("Backend Developer Agent")
       tester = await client.register_agent("Testing Agent")
       
       # Design phase
       design = await architect.design_system(
           requirements="Build a REST API for user management"
       )
       
       # Implementation phase
       code = await developer.implement(
           design=design,
           language="python",
           framework="fastapi"
       )
       
       # Testing phase
       tests = await tester.create_tests(
           code=code,
           coverage_target=0.9
       )
       
       print("Development complete!")

Next Steps
----------

Now that you've completed the quickstart:

1. Learn about :doc:`architecture/overview`
2. Explore :doc:`api/managers`
3. Read :doc:`guides/sessions` for advanced usage
4. Check :doc:`guides/troubleshooting` if you encounter issues