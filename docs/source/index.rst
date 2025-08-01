.. Shannon MCP documentation master file

Shannon MCP Documentation
=========================

.. image:: https://img.shields.io/badge/Python-3.11+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python Version

.. image:: https://img.shields.io/badge/License-MIT-green.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License

Shannon MCP is a comprehensive Model Context Protocol (MCP) server implementation for Claude Code, 
built using an innovative multi-agent collaborative system. The project employs 26 specialized AI 
agents working together to implement the entire MCP server specification in Python.

Key Features
------------

* **Automatic Claude Code Discovery** - Finds and manages Claude Code binaries across platforms
* **Real-time Session Management** - JSONL streaming with backpressure handling
* **Multi-Agent System** - 26 specialized agents for different aspects of development
* **Git-like Checkpoints** - Save and restore session states with branching
* **Hooks Framework** - Event-driven automation with security sandboxing
* **Analytics Engine** - Comprehensive usage tracking and reporting
* **Process Registry** - System-wide session tracking and resource monitoring

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   configuration
   basic-usage

.. toctree::
   :maxdepth: 2
   :caption: Architecture

   architecture/overview
   architecture/components
   architecture/multi-agent
   architecture/mcp-protocol

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/managers
   api/streaming
   api/storage
   api/analytics
   api/hooks
   api/commands
   api/agents
   api/transport

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide

   dev/contributing
   dev/testing
   dev/extending
   dev/best-practices

.. toctree::
   :maxdepth: 2
   :caption: User Guides

   guides/sessions
   guides/checkpoints
   guides/agents
   guides/hooks
   guides/analytics
   guides/troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources

   changelog
   faq
   glossary
   license

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`