Configuration
=============

Shannon MCP uses a flexible configuration system that supports environment variables, configuration files, and runtime options.

Configuration File
------------------

The main configuration file is located at ``~/.shannon-mcp/config.yaml``:

.. code-block:: yaml

   # Shannon MCP Configuration
   
   # Server settings
   server:
     host: "127.0.0.1"
     port: 8765
     enable_ssl: false
     ssl_cert: null
     ssl_key: null
   
   # Claude Code settings
   claude_code:
     # Path to Claude Code binary (auto-discovered if not set)
     binary_path: null
     # Minimum required version
     min_version: "1.0.0"
     # Discovery timeout
     discovery_timeout: 30
     # Update check interval (seconds)
     update_check_interval: 86400
   
   # Session settings
   sessions:
     # Default session options
     defaults:
       model: "claude-3-opus-20240229"
       temperature: 0.7
       max_tokens: 4000
       top_p: 0.9
     # Session timeout (seconds)
     timeout: 3600
     # Maximum concurrent sessions
     max_concurrent: 10
     # Session cache settings
     cache:
       enabled: true
       max_size: 100
       ttl: 3600
   
   # Storage settings
   storage:
     # Base directory for all data
     base_dir: "~/.shannon-mcp/data"
     # Database settings
     database:
       path: "shannon.db"
       wal_mode: true
       journal_mode: "WAL"
     # Content-addressable storage
     cas:
       path: "cas"
       compression: true
       compression_level: 6
     # Checkpoint settings
     checkpoints:
       path: "checkpoints"
       max_checkpoints: 1000
       auto_checkpoint: true
       checkpoint_interval: 300
   
   # Agent settings
   agents:
     # Maximum number of agents
     max_agents: 50
     # Agent timeout (seconds)
     timeout: 600
     # Enable multi-agent collaboration
     collaboration: true
     # Agent registry source
     registry: "~/.shannon-mcp/agents"
   
   # Analytics settings
   analytics:
     enabled: true
     # Metrics collection interval
     collection_interval: 60
     # Data retention (days)
     retention_days: 90
     # Export settings
     export:
       enabled: true
       format: "jsonl"
       path: "~/.shannon-mcp/analytics"
       rotation: "daily"
   
   # Hooks settings
   hooks:
     enabled: true
     # Hooks directory
     directory: "~/.shannon-mcp/hooks"
     # Execution timeout
     timeout: 30
     # Security settings
     security:
       sandboxing: true
       allowed_commands: ["echo", "curl", "notify-send"]
       blocked_paths: ["/etc", "/sys", "/proc"]
   
   # Logging settings
   logging:
     # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
     level: "INFO"
     # Log file path
     file: "~/.shannon-mcp/logs/shannon.log"
     # Log rotation
     rotation:
       enabled: true
       max_size: "10MB"
       backup_count: 5
     # Console logging
     console:
       enabled: true
       colorize: true
   
   # Performance settings
   performance:
     # Buffer sizes
     stream_buffer_size: 1048576  # 1MB
     # Worker threads
     worker_threads: 4
     # Connection pooling
     connection_pool_size: 20
     # Async settings
     async_timeout: 30
     async_max_tasks: 100

Environment Variables
---------------------

All configuration options can be overridden using environment variables:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Environment Variable
     - Description
   * - ``SHANNON_MCP_CONFIG_FILE``
     - Path to configuration file
   * - ``SHANNON_MCP_SERVER_HOST``
     - Server bind address
   * - ``SHANNON_MCP_SERVER_PORT``
     - Server port number
   * - ``SHANNON_MCP_CLAUDE_CODE_PATH``
     - Claude Code binary path
   * - ``SHANNON_MCP_DATA_DIR``
     - Base data directory
   * - ``SHANNON_MCP_LOG_LEVEL``
     - Logging level
   * - ``SHANNON_MCP_DEBUG``
     - Enable debug mode
   * - ``SHANNON_MCP_ANALYTICS_ENABLED``
     - Enable/disable analytics
   * - ``SHANNON_MCP_HOOKS_ENABLED``
     - Enable/disable hooks

Example:

.. code-block:: bash

   export SHANNON_MCP_LOG_LEVEL=DEBUG
   export SHANNON_MCP_SERVER_PORT=9000
   export SHANNON_MCP_CLAUDE_CODE_PATH=/custom/path/claude-code
   
   shannon-mcp serve

Command Line Options
--------------------

Configuration can also be set via command line arguments:

.. code-block:: bash

   shannon-mcp serve \
     --host 0.0.0.0 \
     --port 8080 \
     --config /custom/config.yaml \
     --log-level DEBUG \
     --data-dir /var/lib/shannon-mcp

Priority Order
--------------

Configuration sources are applied in this order (highest to lowest priority):

1. Command line arguments
2. Environment variables
3. Configuration file
4. Default values

Per-Session Configuration
-------------------------

Sessions can have individual configurations:

.. code-block:: python

   session_config = {
       "model": "claude-3-sonnet-20240229",
       "temperature": 0.5,
       "max_tokens": 2000,
       "system_prompt": "You are a Python expert",
       "stop_sequences": ["```"],
       "metadata": {
           "project": "my-app",
           "user": "developer"
       }
   }
   
   session = await client.create_session(config=session_config)

Model-Specific Settings
-----------------------

Different Claude models can have specific configurations:

.. code-block:: yaml

   models:
     claude-3-opus-20240229:
       max_tokens: 4000
       default_temperature: 0.7
       timeout: 120
     
     claude-3-sonnet-20240229:
       max_tokens: 2000
       default_temperature: 0.5
       timeout: 60
     
     claude-3-haiku-20240229:
       max_tokens: 1000
       default_temperature: 0.3
       timeout: 30

Security Configuration
----------------------

Security-related settings:

.. code-block:: yaml

   security:
     # API authentication
     api:
       enabled: true
       key_file: "~/.shannon-mcp/api_keys.json"
       rate_limiting:
         enabled: true
         requests_per_minute: 60
     
     # Process isolation
     isolation:
       enabled: true
       use_containers: false
       resource_limits:
         cpu: "50%"
         memory: "2GB"
         disk_io: "100MB/s"
     
     # Network security
     network:
       allowed_hosts: ["localhost", "127.0.0.1"]
       blocked_ports: [22, 3389]
       ssl_required: false

Advanced Configuration
----------------------

Resource Limits
~~~~~~~~~~~~~~~

Configure resource usage limits:

.. code-block:: yaml

   limits:
     # Memory limits
     memory:
       session_max: "512MB"
       total_max: "4GB"
       warning_threshold: 0.8
     
     # CPU limits
     cpu:
       session_max_percent: 50
       total_max_percent: 80
     
     # Disk usage
     disk:
       cas_max_size: "10GB"
       checkpoint_max_size: "5GB"
       analytics_max_size: "2GB"

Performance Tuning
~~~~~~~~~~~~~~~~~~

Optimize for different workloads:

.. code-block:: yaml

   # For high-throughput scenarios
   performance_profiles:
     high_throughput:
       stream_buffer_size: 4194304  # 4MB
       worker_threads: 8
       connection_pool_size: 50
       async_max_tasks: 200
     
     # For low-latency scenarios  
     low_latency:
       stream_buffer_size: 65536  # 64KB
       worker_threads: 2
       connection_pool_size: 10
       async_max_tasks: 50
     
     # For resource-constrained environments
     lightweight:
       stream_buffer_size: 262144  # 256KB
       worker_threads: 1
       connection_pool_size: 5
       async_max_tasks: 20

Validation
----------

Validate your configuration:

.. code-block:: bash

   # Check configuration
   shannon-mcp config validate
   
   # Show effective configuration
   shannon-mcp config show
   
   # Test specific settings
   shannon-mcp config test --component storage

Migration
---------

Migrate from older configurations:

.. code-block:: bash

   # Migrate from v0.x to v1.x
   shannon-mcp config migrate --from 0.x --to 1.x
   
   # Backup before migration
   shannon-mcp config backup --output config.backup.yaml