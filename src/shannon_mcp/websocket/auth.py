"""WebSocket authentication middleware."""

import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class WebSocketAuth:
    """Handles WebSocket authentication and token management."""
    
    def __init__(self, secret_key: str, token_expiry_hours: int = 24):
        """Initialize authentication handler.
        
        Args:
            secret_key: Secret key for JWT signing
            token_expiry_hours: Token expiry time in hours
        """
        self.secret_key = secret_key
        self.token_expiry = timedelta(hours=token_expiry_hours)
        self.algorithm = 'HS256'
    
    def generate_token(self, user_id: str, **kwargs) -> str:
        """Generate JWT token for WebSocket authentication.
        
        Args:
            user_id: User identifier
            **kwargs: Additional claims to include in token
            
        Returns:
            JWT token string
        """
        payload = {
            'user_id': user_id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + self.token_expiry,
            **kwargs
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh an existing token.
        
        Args:
            token: Current JWT token
            
        Returns:
            New JWT token or None if current token is invalid
        """
        payload = self.validate_token(token)
        if not payload:
            return None
        
        # Remove old expiry claims
        payload.pop('iat', None)
        payload.pop('exp', None)
        
        # Generate new token with same claims
        return self.generate_token(
            user_id=payload.get('user_id'),
            **{k: v for k, v in payload.items() if k != 'user_id'}
        )
    
    def create_session_token(self, user_id: str, session_id: str, project_id: str) -> str:
        """Create a session-specific token.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            project_id: Project identifier
            
        Returns:
            JWT token with session claims
        """
        return self.generate_token(
            user_id=user_id,
            session_id=session_id,
            project_id=project_id,
            scope='session'
        )