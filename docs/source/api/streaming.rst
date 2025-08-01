Streaming API Reference
=======================

This section documents the streaming system that handles real-time JSONL communication with Claude Code.

Stream Buffer
-------------

.. module:: shannon_mcp.streaming.buffer

.. autoclass:: StreamBuffer
   :members:
   :undoc-members:
   :show-inheritance:

   Efficient line-based buffering with backpressure handling.

   **Key Features:**

   - Configurable buffer size limits
   - Automatic line splitting
   - Memory-efficient operation
   - Backpressure support

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.streaming.buffer import StreamBuffer

      buffer = StreamBuffer(max_size=1024 * 1024)  # 1MB limit
      
      # Add data
      buffer.add_chunk(b"First line\\nSecond ")
      buffer.add_chunk(b"line\\nThird line")
      
      # Get complete lines
      while buffer.has_line():
          line = buffer.get_line()
          print(f"Line: {line}")
      
      # Check buffer status
      if buffer.is_full():
          print("Buffer full, apply backpressure")

JSONL Parser
------------

.. module:: shannon_mcp.streaming.parser

.. autoclass:: JSONLParser
   :members:
   :undoc-members:
   :show-inheritance:

   Parses JSONL streams with validation and error recovery.

   **Message Types:**

   .. list-table::
      :header-rows: 1

      * - Type
        - Description
        - Fields
      * - content
        - Text content from Claude
        - type, content, token_count
      * - notification
        - Status updates
        - type, message, level
      * - error
        - Error messages
        - type, error, details
      * - metrics
        - Performance data
        - type, metrics, timestamp
      * - completion
        - Stream end marker
        - type, reason, summary

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.streaming.parser import JSONLParser

      parser = JSONLParser(strict=True)
      
      # Parse single line
      try:
          message = parser.parse_line('{"type": "content", "content": "Hello"}')
          print(f"Parsed: {message}")
      except JSONLParseError as e:
          print(f"Parse error: {e}")
      
      # Validate message
      if parser.validate_message(message):
          print("Message is valid")
      
      # Parse with schema
      schema = {
          "type": "object",
          "required": ["type", "content"],
          "properties": {
              "type": {"enum": ["content", "error", "notification"]},
              "content": {"type": "string"}
          }
      }
      
      message = parser.parse_line(line, schema=schema)

Stream Handler
--------------

.. module:: shannon_mcp.streaming.handler

.. autoclass:: StreamHandler
   :members:
   :undoc-members:
   :show-inheritance:

   Routes parsed messages to appropriate handlers.

   **Handler Registration:**

   .. code-block:: python

      from shannon_mcp.streaming.handler import StreamHandler

      handler = StreamHandler()
      
      # Register type handlers
      @handler.register("content")
      async def handle_content(message):
          print(f"Content: {message['content']}")
          return {"processed": True}
      
      @handler.register("error")
      async def handle_error(message):
          logging.error(f"Stream error: {message['error']}")
          raise StreamError(message['error'])
      
      # Register catch-all
      @handler.register_default()
      async def handle_unknown(message):
          logging.warning(f"Unknown message: {message}")
      
      # Process message
      result = await handler.handle(message)

   **Built-in Handlers:**

   .. code-block:: python

      # Content accumulation
      handler.enable_content_accumulation()
      
      # Metrics collection
      handler.enable_metrics_collection()
      
      # Error recovery
      handler.enable_error_recovery(max_retries=3)

Stream Processor
----------------

.. module:: shannon_mcp.streaming.processor

.. autoclass:: StreamProcessor
   :members:
   :undoc-members:
   :show-inheritance:

   High-level stream processing with full pipeline.

   **Pipeline Stages:**

   1. **Reading** - Async reading from subprocess
   2. **Buffering** - Line-based buffering
   3. **Parsing** - JSONL parsing and validation
   4. **Handling** - Message type routing
   5. **Output** - Result aggregation

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.streaming.processor import StreamProcessor

      async def process_claude_stream():
          processor = StreamProcessor(
              buffer_size=1024 * 1024,
              parser_strict=True,
              enable_metrics=True
          )
          
          # Process stream
          async with processor.process_stream(process.stdout) as stream:
              async for message in stream:
                  if message.type == "content":
                      print(message.content, end="", flush=True)
                  elif message.type == "notification":
                      logging.info(f"Status: {message.message}")
          
          # Get metrics
          metrics = processor.get_metrics()
          print(f"Total tokens: {metrics.total_tokens}")
          print(f"Messages: {metrics.message_count}")

Backpressure Manager
--------------------

.. module:: shannon_mcp.streaming.backpressure

.. autoclass:: BackpressureManager
   :members:
   :undoc-members:
   :show-inheritance:

   Manages flow control for streaming operations.

   **Strategies:**

   - **Pause/Resume** - Temporarily pause reading
   - **Buffering** - Use memory buffers
   - **Dropping** - Drop old messages
   - **Throttling** - Slow down processing

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.streaming.backpressure import BackpressureManager

      backpressure = BackpressureManager(
          strategy="adaptive",
          high_watermark=1000,
          low_watermark=100
      )
      
      async def read_with_backpressure():
          async for chunk in stream:
              # Check pressure
              if await backpressure.should_pause():
                  await backpressure.wait_for_resume()
              
              # Process chunk
              await process_chunk(chunk)
              
              # Update metrics
              await backpressure.record_processed(len(chunk))

Stream Metrics
--------------

.. module:: shannon_mcp.streaming.metrics

.. autoclass:: StreamMetrics
   :members:
   :undoc-members:
   :show-inheritance:

   Collects and analyzes streaming performance metrics.

   **Collected Metrics:**

   .. list-table::
      :header-rows: 1

      * - Metric
        - Description
        - Unit
      * - bytes_read
        - Total bytes read from stream
        - bytes
      * - lines_processed
        - Number of lines parsed
        - count
      * - messages_handled
        - Messages successfully handled
        - count
      * - parse_errors
        - Failed parse attempts
        - count
      * - processing_time
        - Total processing duration
        - seconds
      * - throughput
        - Data processing rate
        - bytes/sec
      * - latency_p50
        - Median message latency
        - milliseconds
      * - latency_p99
        - 99th percentile latency
        - milliseconds

   **Example Usage:**

   .. code-block:: python

      from shannon_mcp.streaming.metrics import StreamMetrics

      metrics = StreamMetrics()
      
      # Record events
      metrics.record_bytes(1024)
      metrics.record_message("content", processing_time=0.005)
      metrics.record_error("parse_error")
      
      # Get summary
      summary = metrics.get_summary()
      print(f"Throughput: {summary.throughput_mbps:.2f} MB/s")
      print(f"Success rate: {summary.success_rate:.1%}")
      print(f"P99 latency: {summary.latency_p99:.1f}ms")

Complete Streaming Example
--------------------------

Here's a complete example showing all streaming components working together:

.. code-block:: python

   import asyncio
   from shannon_mcp.streaming import (
       StreamProcessor,
       StreamHandler,
       BackpressureManager,
       StreamMetrics
   )

   async def stream_claude_response(prompt: str):
       # Initialize components
       processor = StreamProcessor()
       handler = StreamHandler()
       backpressure = BackpressureManager()
       metrics = StreamMetrics()
       
       # Set up handlers
       content_buffer = []
       
       @handler.register("content")
       async def handle_content(msg):
           content_buffer.append(msg["content"])
           metrics.record_message("content")
       
       @handler.register("notification")
       async def handle_notification(msg):
           print(f"\\n[{msg['level']}] {msg['message']}\\n")
           metrics.record_message("notification")
       
       @handler.register("error")
       async def handle_error(msg):
           metrics.record_error("stream_error")
           raise Exception(f"Stream error: {msg['error']}")
       
       # Start streaming
       process = await start_claude_process(prompt)
       
       try:
           async with processor.process_stream(
               process.stdout,
               handler=handler,
               backpressure=backpressure
           ) as stream:
               async for message in stream:
                   # Backpressure check
                   if backpressure.is_pressured():
                       await asyncio.sleep(0.1)
           
           # Return complete response
           return {
               "content": "".join(content_buffer),
               "metrics": metrics.get_summary()
           }
           
       finally:
           process.terminate()
           await process.wait()

Error Handling
--------------

The streaming system provides comprehensive error handling:

.. code-block:: python

   from shannon_mcp.streaming.errors import (
       StreamError,
       ParseError,
       BackpressureError,
       StreamTimeoutError
   )

   try:
       async for message in stream:
           process_message(message)
           
   except ParseError as e:
       # Invalid JSONL format
       logger.error(f"Parse error at line {e.line_number}: {e.content}")
       
   except BackpressureError as e:
       # Buffer overflow
       logger.error(f"Backpressure limit reached: {e.buffer_size}")
       
   except StreamTimeoutError as e:
       # No data received within timeout
       logger.error(f"Stream timeout after {e.timeout}s")
       
   except StreamError as e:
       # General streaming error
       logger.error(f"Stream error: {e}")

Best Practices
--------------

1. **Buffer Management**

   .. code-block:: python

      # Use appropriate buffer sizes
      buffer = StreamBuffer(
          max_size=1024 * 1024,  # 1MB for normal use
          max_lines=1000         # Prevent line accumulation
      )

2. **Error Recovery**

   .. code-block:: python

      # Implement retry logic
      async def stream_with_retry(process, max_retries=3):
          for attempt in range(max_retries):
              try:
                  return await stream_response(process)
              except StreamError as e:
                  if attempt == max_retries - 1:
                      raise
                  await asyncio.sleep(2 ** attempt)

3. **Resource Cleanup**

   .. code-block:: python

      # Always use context managers
      async with StreamProcessor() as processor:
          async with processor.process_stream(stdout) as stream:
              # Processing here
              pass
      # Automatic cleanup

4. **Performance Monitoring**

   .. code-block:: python

      # Monitor streaming performance
      if metrics.throughput < threshold:
          logger.warning(f"Low throughput: {metrics.throughput}")
      
      if metrics.error_rate > 0.01:  # 1% error rate
          logger.error(f"High error rate: {metrics.error_rate}")