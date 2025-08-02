"""Backpressure management for streaming operations."""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BackpressureMetrics:
    """Metrics for backpressure monitoring."""
    messages_buffered: int = 0
    messages_sent: int = 0
    max_buffer_size: int = 0
    pressure_events: int = 0
    last_pressure_time: Optional[datetime] = None
    total_wait_time: float = 0.0


class BackpressureManager:
    """Manages backpressure for streaming operations."""
    
    def __init__(
        self,
        session_id: str,
        max_buffer_size: int = 1000,
        pressure_threshold: float = 0.8,
        max_wait_time: float = 5.0,
        backoff_factor: float = 1.5
    ):
        """Initialize backpressure manager.
        
        Args:
            session_id: Session identifier
            max_buffer_size: Maximum buffer size before applying backpressure
            pressure_threshold: Threshold (0-1) for starting backpressure
            max_wait_time: Maximum time to wait during backpressure
            backoff_factor: Exponential backoff factor
        """
        self.session_id = session_id
        self.max_buffer_size = max_buffer_size
        self.pressure_threshold = pressure_threshold
        self.max_wait_time = max_wait_time
        self.backoff_factor = backoff_factor
        
        # Current state
        self.current_buffer_size = 0
        self.current_wait_time = 0.1  # Start with 100ms
        self.under_pressure = False
        
        # Metrics
        self.metrics = BackpressureMetrics(max_buffer_size=max_buffer_size)
        
        # Pressure detection
        self._pressure_start_time: Optional[datetime] = None
    
    async def check_and_wait(self) -> None:
        """Check if backpressure should be applied and wait if necessary."""
        pressure_level = self._calculate_pressure_level()
        
        if pressure_level > self.pressure_threshold:
            await self._apply_backpressure(pressure_level)
        else:
            await self._release_pressure()
    
    def _calculate_pressure_level(self) -> float:
        """Calculate current pressure level (0.0 to 1.0).
        
        Returns:
            Pressure level from 0.0 (no pressure) to 1.0+ (high pressure)
        """
        if self.max_buffer_size == 0:
            return 0.0
        
        # Base pressure from buffer size
        buffer_pressure = self.current_buffer_size / self.max_buffer_size
        
        # Additional pressure factors
        pressure_multiplier = 1.0
        
        # If we've been under pressure recently, be more conservative
        if self.metrics.last_pressure_time:
            time_since_pressure = (
                datetime.utcnow() - self.metrics.last_pressure_time
            ).total_seconds()
            
            # Apply multiplier if pressure was recent (within last 30 seconds)
            if time_since_pressure < 30:
                pressure_multiplier = 1.2
        
        return buffer_pressure * pressure_multiplier
    
    async def _apply_backpressure(self, pressure_level: float) -> None:
        """Apply backpressure by waiting.
        
        Args:
            pressure_level: Current pressure level
        """
        if not self.under_pressure:
            # Starting new pressure event
            self.under_pressure = True
            self._pressure_start_time = datetime.utcnow()
            self.metrics.pressure_events += 1
            self.metrics.last_pressure_time = self._pressure_start_time
            
            logger.warning(
                f"Backpressure started for session {self.session_id}: "
                f"pressure={pressure_level:.2f}, buffer={self.current_buffer_size}"
            )
        
        # Calculate wait time based on pressure level
        base_wait = self.current_wait_time
        pressure_wait = base_wait * (pressure_level / self.pressure_threshold)
        wait_time = min(pressure_wait, self.max_wait_time)
        
        # Apply exponential backoff
        self.current_wait_time = min(
            self.current_wait_time * self.backoff_factor,
            self.max_wait_time
        )
        
        # Track wait time
        self.metrics.total_wait_time += wait_time
        
        logger.debug(
            f"Applying backpressure for session {self.session_id}: "
            f"waiting {wait_time:.3f}s"
        )
        
        await asyncio.sleep(wait_time)
    
    async def _release_pressure(self) -> None:
        """Release backpressure and reset wait times."""
        if self.under_pressure:
            # Ending pressure event
            self.under_pressure = False
            pressure_duration = 0.0
            
            if self._pressure_start_time:
                pressure_duration = (
                    datetime.utcnow() - self._pressure_start_time
                ).total_seconds()
            
            logger.info(
                f"Backpressure released for session {self.session_id}: "
                f"duration={pressure_duration:.2f}s"
            )
            
            self._pressure_start_time = None
        
        # Reset wait time (with gradual reduction)
        self.current_wait_time = max(0.1, self.current_wait_time * 0.9)
    
    def update_metrics(
        self,
        buffer_size: Optional[int] = None,
        messages_sent: int = 0,
        messages_buffered: int = 0
    ) -> None:
        """Update metrics and buffer size.
        
        Args:
            buffer_size: Current buffer size
            messages_sent: Number of messages sent
            messages_buffered: Number of messages added to buffer
        """
        if buffer_size is not None:
            self.current_buffer_size = buffer_size
        
        self.metrics.messages_sent += messages_sent
        self.metrics.messages_buffered += messages_buffered
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics.
        
        Returns:
            Statistics dictionary
        """
        current_pressure = self._calculate_pressure_level()
        
        stats = {
            'session_id': self.session_id,
            'current_pressure': current_pressure,
            'under_pressure': self.under_pressure,
            'current_buffer_size': self.current_buffer_size,
            'max_buffer_size': self.max_buffer_size,
            'pressure_threshold': self.pressure_threshold,
            'current_wait_time': self.current_wait_time,
            'metrics': {
                'messages_sent': self.metrics.messages_sent,
                'messages_buffered': self.metrics.messages_buffered,
                'pressure_events': self.metrics.pressure_events,
                'total_wait_time': self.metrics.total_wait_time,
                'last_pressure_time': (
                    self.metrics.last_pressure_time.isoformat()
                    if self.metrics.last_pressure_time else None
                )
            }
        }
        
        # Add current pressure duration if under pressure
        if self.under_pressure and self._pressure_start_time:
            stats['current_pressure_duration'] = (
                datetime.utcnow() - self._pressure_start_time
            ).total_seconds()
        
        return stats
    
    def is_under_pressure(self) -> bool:
        """Check if currently under backpressure.
        
        Returns:
            True if under backpressure
        """
        return self.under_pressure
    
    def get_pressure_level(self) -> float:
        """Get current pressure level.
        
        Returns:
            Pressure level (0.0 to 1.0+)
        """
        return self._calculate_pressure_level()
    
    def configure(
        self,
        max_buffer_size: Optional[int] = None,
        pressure_threshold: Optional[float] = None,
        max_wait_time: Optional[float] = None,
        backoff_factor: Optional[float] = None
    ) -> None:
        """Reconfigure backpressure parameters.
        
        Args:
            max_buffer_size: New maximum buffer size
            pressure_threshold: New pressure threshold
            max_wait_time: New maximum wait time
            backoff_factor: New backoff factor
        """
        if max_buffer_size is not None:
            self.max_buffer_size = max_buffer_size
            self.metrics.max_buffer_size = max_buffer_size
            
        if pressure_threshold is not None:
            self.pressure_threshold = max(0.0, min(1.0, pressure_threshold))
            
        if max_wait_time is not None:
            self.max_wait_time = max(0.1, max_wait_time)
            
        if backoff_factor is not None:
            self.backoff_factor = max(1.0, backoff_factor)
        
        logger.info(
            f"Backpressure configuration updated for session {self.session_id}: "
            f"max_buffer={self.max_buffer_size}, "
            f"threshold={self.pressure_threshold}, "
            f"max_wait={self.max_wait_time}, "
            f"backoff={self.backoff_factor}"
        )
    
    async def wait_for_pressure_release(self, timeout: float = 30.0) -> bool:
        """Wait for backpressure to be released.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if pressure was released, False if timeout
        """
        start_time = datetime.utcnow()
        
        while self.under_pressure:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= timeout:
                return False
            
            # Wait a bit and check again
            await asyncio.sleep(0.1)
        
        return True