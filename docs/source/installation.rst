Installation
============

This guide will help you install Shannon MCP and its dependencies.

Requirements
------------

* Python 3.11 or higher
* Poetry (for dependency management)
* Claude Code binary (automatically discovered)

System Requirements
~~~~~~~~~~~~~~~~~~~

* **Operating System**: Windows, macOS, or Linux
* **Memory**: 4GB RAM minimum, 8GB recommended
* **Disk Space**: 500MB for installation
* **Network**: Internet connection for package installation

Installing with Poetry
----------------------

Shannon MCP uses Poetry for dependency management. First, install Poetry if you haven't already:

.. code-block:: bash

   curl -sSL https://install.python-poetry.org | python3 -

Clone the repository:

.. code-block:: bash

   git clone https://github.com/yourusername/shannon-mcp.git
   cd shannon-mcp

Install dependencies:

.. code-block:: bash

   poetry install

This will create a virtual environment and install all required dependencies.

Installing from PyPI
--------------------

Once published, you'll be able to install Shannon MCP directly from PyPI:

.. code-block:: bash

   pip install shannon-mcp

Development Installation
------------------------

For development, install with extra dependencies:

.. code-block:: bash

   poetry install --with dev,test,docs

This includes:

* Development tools (black, flake8, mypy)
* Testing frameworks (pytest, pytest-asyncio)
* Documentation tools (sphinx, sphinx-rtd-theme)

Verifying Installation
----------------------

After installation, verify Shannon MCP is working:

.. code-block:: bash

   poetry run shannon-mcp --version

Or if installed via pip:

.. code-block:: bash

   shannon-mcp --version

Claude Code Discovery
---------------------

Shannon MCP will automatically discover Claude Code installations in:

1. System PATH
2. NVM installations (macOS/Linux)
3. Standard installation directories:
   
   * macOS: ``/Applications/Claude Code.app``
   * Windows: ``C:\Program Files\Claude Code``
   * Linux: ``/usr/local/bin/claude-code``

You can also specify a custom Claude Code path:

.. code-block:: bash

   shannon-mcp --claude-code-path /path/to/claude-code

Docker Installation
-------------------

A Docker image is available for containerized deployments:

.. code-block:: bash

   docker pull shannon-mcp/shannon-mcp:latest
   
   docker run -it --rm \
     -v ~/.shannon-mcp:/root/.shannon-mcp \
     shannon-mcp/shannon-mcp

Building from Source
--------------------

To build Shannon MCP from source:

.. code-block:: bash

   git clone https://github.com/yourusername/shannon-mcp.git
   cd shannon-mcp
   
   # Build the package
   poetry build
   
   # Install the wheel
   pip install dist/shannon_mcp-*.whl

Environment Variables
---------------------

Shannon MCP supports several environment variables:

.. code-block:: bash

   # Claude Code binary path
   export CLAUDE_CODE_PATH=/custom/path/to/claude-code
   
   # Configuration directory
   export SHANNON_MCP_CONFIG_DIR=~/.config/shannon-mcp
   
   # Data directory
   export SHANNON_MCP_DATA_DIR=~/.local/share/shannon-mcp
   
   # Log level
   export SHANNON_MCP_LOG_LEVEL=DEBUG

Troubleshooting
---------------

Common Installation Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Poetry not found**

If Poetry is not in your PATH after installation:

.. code-block:: bash

   export PATH="$HOME/.local/bin:$PATH"

**Python version mismatch**

Shannon MCP requires Python 3.11+. Check your version:

.. code-block:: bash

   python --version

Use pyenv to install the correct version:

.. code-block:: bash

   pyenv install 3.11.0
   pyenv local 3.11.0

**Dependency conflicts**

Clear Poetry's cache and reinstall:

.. code-block:: bash

   poetry cache clear pypi --all
   poetry install --no-cache

Next Steps
----------

After installation:

1. Read the :doc:`quickstart` guide
2. Configure Shannon MCP with :doc:`configuration`
3. Explore :doc:`basic-usage` examples