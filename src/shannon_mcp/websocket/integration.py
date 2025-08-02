"""WebSocket and session manager integration."""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..managers.session import SessionManager, SessionState
from .manager import WebSocketManager
from ..utils.errors import ValidationError, SystemError

logger = logging.getLogger(__name__)


class WebSocketSessionIntegration:
    """Integrates WebSocket manager with session manager."""
    
    def __init__(self, websocket_manager: WebSocketManager, session_manager: SessionManager):
        """Initialize integration.
        
        Args:
            websocket_manager: WebSocket manager instance
            session_manager: Session manager instance
        """
        self.websocket = websocket_manager
        self.session_manager = session_manager
        
        # Set up integration
        self._setup_integration()
    
    def _setup_integration(self) -> None:
        """Set up the integration between WebSocket and session managers."""
        # Set session manager callback in WebSocket manager
        self.websocket.set_session_manager_callback(self._handle_session_action)
        
        # Subscribe to session events
        self._setup_session_event_handlers()
    
    async def _handle_session_action(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session actions from WebSocket.
        
        Args:
            action: Action to perform (start, prompt, stop)
            data: Action data
            
        Returns:
            Action result
        """
        try:
            if action == 'start':
                return await self._handle_start_session(data)
            elif action == 'prompt':
                return await self._handle_send_prompt(data)
            elif action == 'stop':
                return await self._handle_stop_session(data)
            else:
                raise ValidationError('action', action, 'Unknown action')
                
        except Exception as e:
            logger.error(f"Session action {action} failed: {e}")
            raise
    
    async def _handle_start_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start session request.
        
        Args:
            data: Session start data
            
        Returns:
            Session info
        """
        prompt = data.get('prompt')
        if not prompt:
            raise ValidationError('prompt', prompt, 'Prompt is required')
        
        model = data.get('model', 'claude-3-sonnet')
        checkpoint_id = data.get('checkpoint_id')
        context = data.get('context', {})
        
        # Create session
        session = await self.session_manager.create_session(
            prompt=prompt,
            model=model,
            checkpoint_id=checkpoint_id,
            context=context
        )
        
        # Set up stream callbacks for this session
        self._setup_session_callbacks(session)
        
        return {
            'session_id': session.id,
            'state': session.state.value,
            'model': session.model,
            'created_at': session.created_at.isoformat()
        }
    
    async def _handle_send_prompt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send prompt request.
        
        Args:
            data: Prompt data
            
        Returns:
            Send result
        """
        session_id = data.get('session_id')
        if not session_id:
            raise ValidationError('session_id', session_id, 'Session ID is required')
        
        content = data.get('content')
        if not content:
            raise ValidationError('content', content, 'Content is required')
        
        timeout = data.get('timeout')
        
        # Send message
        await self.session_manager.send_message(
            session_id=session_id,
            content=content,
            timeout=timeout
        )
        
        return {
            'session_id': session_id,
            'sent_at': datetime.utcnow().isoformat()
        }
    
    async def _handle_stop_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stop session request.
        
        Args:
            data: Stop data
            
        Returns:
            Stop result
        """
        session_id = data.get('session_id')
        if not session_id:
            raise ValidationError('session_id', session_id, 'Session ID is required')
        
        # Cancel session
        await self.session_manager.cancel_session(session_id)
        
        return {
            'session_id': session_id,
            'stopped_at': datetime.utcnow().isoformat()
        }
    
    def _setup_session_callbacks(self, session) -> None:
        """Set up streaming callbacks for a session.
        
        Args:
            session: Session instance
        """
        # Add response callback to stream to WebSocket
        async def on_response(content: str, is_partial: bool = False):
            event_type = 'claude-partial' if is_partial else 'claude-response'
            await self.websocket.broadcast_session_event(
                session.id,
                f'{event_type}:{session.id}',
                {
                    'content': content,
                    'is_partial': is_partial,
                    'timestamp': datetime.utcnow().isoformat(),
                    'session_id': session.id
                }
            )
        
        session._response_callbacks.append(on_response)
    
    def _setup_session_event_handlers(self) -> None:
        """Set up session event handlers to broadcast to WebSocket."""
        # This would integrate with the event system from session manager
        # For now, we'll handle this through the streaming callbacks
        pass
    
    async def broadcast_session_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a session message to WebSocket clients.
        
        Args:
            session_id: Session ID
            message: Message to broadcast
        """
        message_type = message.get('type', 'unknown')
        
        # Map message types to WebSocket events
        event_mapping = {
            'partial': 'claude-partial',
            'response': 'claude-response',
            'error': 'claude-error',
            'notification': 'claude-notification',
            'metric': 'claude-metric',
            'debug': 'claude-debug',
            'status': 'claude-status',
            'checkpoint': 'claude-checkpoint'
        }
        
        event_name = event_mapping.get(message_type, 'claude-message')
        
        await self.websocket.broadcast_session_event(
            session_id,
            f'{event_name}:{session_id}',
            {
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id
            }
        )
    
    async def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics.
        
        Returns:
            Integration stats
        """
        websocket_stats = await self.websocket.get_stats()
        
        # Get session manager stats through health check
        session_health = await self.session_manager._health_check()
        
        return {
            'websocket': websocket_stats,
            'sessions': session_health,
            'integration': {
                'callback_configured': self.websocket._session_manager_callback is not None,
                'active_integrations': len(self.websocket.session_subscribers)
            }
        }


async def create_integrated_server(
    websocket_secret_key: str,
    session_manager: SessionManager,
    host: str = '0.0.0.0',
    port: int = 8080
) -> WebSocketSessionIntegration:
    """Create an integrated WebSocket + session server.
    
    Args:
        websocket_secret_key: Secret key for WebSocket JWT auth
        session_manager: Session manager instance
        host: Host to bind to
        port: Port to bind to
        
    Returns:
        Integration instance
    """
    # Create WebSocket manager
    websocket_manager = WebSocketManager(websocket_secret_key)
    
    # Create integration
    integration = WebSocketSessionIntegration(websocket_manager, session_manager)
    
    # Start WebSocket server
    await websocket_manager.start(host, port)
    
    logger.info(f"Integrated server started on {host}:{port}")
    
    return integration