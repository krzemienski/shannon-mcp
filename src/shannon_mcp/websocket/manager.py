"""WebSocket manager for real-time streaming communication."""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, Callable
from datetime import datetime
import socketio
from aiohttp import web
import jwt
from collections import defaultdict

from ..utils.errors import AuthenticationError, SessionNotFoundError

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self, secret_key: str):
        """Initialize WebSocket manager.
        
        Args:
            secret_key: Secret key for JWT validation
        """
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*',  # Configure appropriately for production
            logger=logger,
            engineio_logger=False
        )
        self.app = web.Application()
        self.sio.attach(self.app)
        
        self.secret_key = secret_key
        self.clients: Dict[str, Dict[str, Any]] = {}  # sid -> client info
        self.session_subscribers: Dict[str, Set[str]] = defaultdict(set)  # session_id -> set of sids
        self.client_sessions: Dict[str, Set[str]] = defaultdict(set)  # sid -> set of session_ids
        
        # Message buffer for disconnected clients
        self.message_buffer: Dict[str, list] = defaultdict(list)
        self.buffer_size = 1000  # Max messages per session
        
        # Session manager callback
        self._session_manager_callback: Optional[Callable] = None
        
        # Setup event handlers
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up Socket.IO event handlers."""
        
        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle client connection."""
            try:
                # Validate JWT token
                if not auth or 'token' not in auth:
                    raise AuthenticationError("No authentication token provided")
                
                token_data = self._validate_token(auth['token'])
                
                # Store client info
                self.clients[sid] = {
                    'user_id': token_data.get('user_id'),
                    'connected_at': datetime.utcnow(),
                    'auth': token_data
                }
                
                logger.info(f"Client {sid} connected (user: {token_data.get('user_id')})")
                
                # Send buffered messages if any
                await self._send_buffered_messages(sid)
                
                return True
                
            except Exception as e:
                logger.error(f"Connection failed for {sid}: {e}")
                return False
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection."""
            client_info = self.clients.get(sid, {})
            logger.info(f"Client {sid} disconnected (user: {client_info.get('user_id')})")
            
            # Clean up subscriptions
            for session_id in self.client_sessions[sid]:
                self.session_subscribers[session_id].discard(sid)
            
            del self.client_sessions[sid]
            del self.clients[sid]
        
        @self.sio.event
        async def subscribe_session(sid, data):
            """Subscribe to session events."""
            try:
                session_id = data.get('session_id')
                if not session_id:
                    raise ValueError("No session_id provided")
                
                # Add subscription
                self.session_subscribers[session_id].add(sid)
                self.client_sessions[sid].add(session_id)
                
                logger.info(f"Client {sid} subscribed to session {session_id}")
                
                # Send any buffered messages for this session
                await self._send_session_buffer(sid, session_id)
                
                return {'success': True}
                
            except Exception as e:
                logger.error(f"Subscribe failed: {e}")
                return {'success': False, 'error': str(e)}
        
        @self.sio.event
        async def unsubscribe_session(sid, data):
            """Unsubscribe from session events."""
            try:
                session_id = data.get('session_id')
                if not session_id:
                    raise ValueError("No session_id provided")
                
                # Remove subscription
                self.session_subscribers[session_id].discard(sid)
                self.client_sessions[sid].discard(session_id)
                
                logger.info(f"Client {sid} unsubscribed from session {session_id}")
                
                return {'success': True}
                
            except Exception as e:
                logger.error(f"Unsubscribe failed: {e}")
                return {'success': False, 'error': str(e)}
        
        @self.sio.event
        async def claude_start(sid, data):
            """Start a Claude session."""
            try:
                # This will be handled by the session manager
                # Just forward the request
                return await self._forward_to_session_manager('start', data)
                
            except Exception as e:
                logger.error(f"Start session failed: {e}")
                return {'success': False, 'error': str(e)}
        
        @self.sio.event
        async def claude_prompt(sid, data):
            """Send prompt to Claude session."""
            try:
                # Forward to session manager
                return await self._forward_to_session_manager('prompt', data)
                
            except Exception as e:
                logger.error(f"Send prompt failed: {e}")
                return {'success': False, 'error': str(e)}
        
        @self.sio.event
        async def claude_stop(sid, data):
            """Stop a Claude session."""
            try:
                # Forward to session manager
                return await self._forward_to_session_manager('stop', data)
                
            except Exception as e:
                logger.error(f"Stop session failed: {e}")
                return {'success': False, 'error': str(e)}
    
    def _validate_token(self, token: str) -> dict:
        """Validate JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token data
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    async def broadcast_session_event(self, session_id: str, event: str, data: Any):
        """Broadcast event to all clients subscribed to a session.
        
        Args:
            session_id: Session ID
            event: Event name
            data: Event data
        """
        subscribers = self.session_subscribers.get(session_id, set())
        
        if subscribers:
            # Send to connected clients
            await self.sio.emit(event, data, room=list(subscribers))
            logger.debug(f"Broadcasted {event} to {len(subscribers)} clients for session {session_id}")
        else:
            # No subscribers, buffer the message
            self._buffer_message(session_id, event, data)
    
    async def broadcast_session_output(self, session_id: str, message: dict):
        """Broadcast Claude output message.
        
        Args:
            session_id: Session ID
            message: Claude message dict
        """
        await self.broadcast_session_event(
            session_id,
            f'claude-output:{session_id}',
            message
        )
    
    async def broadcast_session_error(self, session_id: str, error: str):
        """Broadcast session error.
        
        Args:
            session_id: Session ID
            error: Error message
        """
        await self.broadcast_session_event(
            session_id,
            f'claude-error:{session_id}',
            error
        )
    
    async def broadcast_session_complete(self, session_id: str, success: bool = True):
        """Broadcast session completion.
        
        Args:
            session_id: Session ID
            success: Whether session completed successfully
        """
        await self.broadcast_session_event(
            session_id,
            f'claude-complete:{session_id}',
            success
        )
    
    def _buffer_message(self, session_id: str, event: str, data: Any):
        """Buffer message for later delivery.
        
        Args:
            session_id: Session ID
            event: Event name
            data: Event data
        """
        buffer = self.message_buffer[session_id]
        buffer.append({
            'event': event,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Limit buffer size
        if len(buffer) > self.buffer_size:
            buffer.pop(0)
    
    async def _send_buffered_messages(self, sid: str):
        """Send all buffered messages to a client.
        
        Args:
            sid: Socket ID
        """
        for session_id in self.client_sessions[sid]:
            await self._send_session_buffer(sid, session_id)
    
    async def _send_session_buffer(self, sid: str, session_id: str):
        """Send buffered messages for a specific session.
        
        Args:
            sid: Socket ID
            session_id: Session ID
        """
        buffer = self.message_buffer.get(session_id, [])
        if buffer:
            logger.info(f"Sending {len(buffer)} buffered messages to {sid} for session {session_id}")
            
            for msg in buffer:
                await self.sio.emit(msg['event'], msg['data'], to=sid)
            
            # Clear buffer after sending
            self.message_buffer[session_id] = []
    
    async def _forward_to_session_manager(self, action: str, data: dict) -> dict:
        """Forward request to session manager.
        
        Args:
            action: Action to perform
            data: Request data
            
        Returns:
            Response dict
        """
        if not self._session_manager_callback:
            logger.error("No session manager callback configured")
            return {'success': False, 'error': 'Session manager not available'}
        
        try:
            result = await self._session_manager_callback(action, data)
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Session manager error for {action}: {e}")
            return {'success': False, 'error': str(e)}
    
    def set_session_manager_callback(self, callback: Callable):
        """Set callback for session manager integration.
        
        Args:
            callback: Async function to handle session operations
        """
        self._session_manager_callback = callback
    
    async def start(self, host: str = '0.0.0.0', port: int = 8080):
        """Start the WebSocket server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info(f"WebSocket server started on {host}:{port}")
    
    async def get_stats(self) -> dict:
        """Get server statistics.
        
        Returns:
            Server statistics dict
        """
        return {
            'connected_clients': len(self.clients),
            'active_sessions': len(self.session_subscribers),
            'total_subscriptions': sum(len(subs) for subs in self.session_subscribers.values()),
            'buffered_messages': sum(len(buf) for buf in self.message_buffer.values()),
            'clients': [
                {
                    'sid': sid,
                    'user_id': info.get('user_id'),
                    'connected_at': info.get('connected_at').isoformat(),
                    'subscriptions': len(self.client_sessions[sid])
                }
                for sid, info in self.clients.items()
            ]
        }