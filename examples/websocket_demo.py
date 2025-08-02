#!/usr/bin/env python3
"""
WebSocket integration demonstration for Shannon MCP.

This script demonstrates the real-time WebSocket streaming functionality
by creating a test server that can handle Claude Code sessions.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for demo
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.websocket import create_integrated_server
from shannon_mcp.utils.config import SessionManagerConfig, BinaryManagerConfig
from shannon_mcp.websocket.auth import WebSocketAuth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run the WebSocket demo server."""
    logger.info("Starting Shannon MCP WebSocket Demo")
    
    try:
        # Create configurations
        binary_config = BinaryManagerConfig()
        session_config = SessionManagerConfig(
            max_concurrent_sessions=10,
            session_timeout=300.0,  # 5 minutes
            buffer_size=8192,
            enable_metrics=True
        )
        
        # Create managers
        binary_manager = BinaryManager(binary_config)
        session_manager = SessionManager(session_config, binary_manager)
        
        # Initialize managers
        logger.info("Initializing managers...")
        await binary_manager.initialize()
        await session_manager.initialize()
        
        # Start managers
        await binary_manager.start()
        await session_manager.start()
        
        # Create auth system
        auth = WebSocketAuth("demo-secret-key-change-in-production")
        
        # Generate a demo token
        demo_token = auth.generate_token(
            user_id="demo_user",
            session_scope="demo",
            permissions=["sessions:create", "sessions:manage"]
        )
        
        logger.info(f"Demo token: {demo_token}")
        
        # Create integrated server
        logger.info("Creating integrated WebSocket server...")
        integration = await create_integrated_server(
            websocket_secret_key="demo-secret-key-change-in-production",
            session_manager=session_manager,
            host="localhost",
            port=8080
        )
        
        logger.info("="*60)
        logger.info("Shannon MCP WebSocket Server Started!")
        logger.info("="*60)
        logger.info("Server running on: http://localhost:8080")
        logger.info(f"Demo token: {demo_token}")
        logger.info("")
        logger.info("Test with Socket.IO client:")
        logger.info("1. Connect with token authentication")
        logger.info("2. Subscribe to session events")
        logger.info("3. Start Claude sessions")
        logger.info("4. Send prompts and receive real-time responses")
        logger.info("")
        logger.info("Example JavaScript client:")
        logger.info("""
const io = require('socket.io-client');
const socket = io('http://localhost:8080', {
  auth: { token: '%s' }
});

socket.on('connect', () => {
  console.log('Connected to Shannon MCP');
  
  // Start a session
  socket.emit('claude_start', {
    prompt: 'Hello, Claude! Can you help me with Python?',
    model: 'claude-3-sonnet'
  }, (response) => {
    console.log('Session started:', response);
    if (response.success) {
      const sessionId = response.result.session_id;
      
      // Subscribe to session events
      socket.emit('subscribe_session', { session_id: sessionId });
      
      // Listen for responses
      socket.on(`claude-response:${sessionId}`, (data) => {
        console.log('Claude response:', data.content);
      });
    }
  });
});
        """ % demo_token)
        logger.info("="*60)
        
        # Keep server running
        try:
            while True:
                # Print stats every 30 seconds
                await asyncio.sleep(30)
                stats = await integration.get_integration_stats()
                logger.info(f"Server stats: {stats}")
                
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
            
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1
    
    finally:
        # Cleanup
        try:
            if 'session_manager' in locals():
                await session_manager.stop()
            if 'binary_manager' in locals():
                await binary_manager.stop()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))