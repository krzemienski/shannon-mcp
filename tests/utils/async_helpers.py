"""
Async testing helpers.
"""

import asyncio
import functools
from typing import Callable, Any, Optional, TypeVar, Coroutine
from datetime import datetime, timezone
import pytest

T = TypeVar('T')


class AsyncTestHelper:
    """Helper class for async testing."""
    
    @staticmethod
    async def wait_for_condition(
        condition: Callable[[], Coroutine[Any, Any, bool]],
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """Wait for an async condition to become true."""
        start = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start < timeout:
            if await condition():
                return True
            await asyncio.sleep(interval)
        
        return False
    
    @staticmethod
    async def run_with_timeout(
        coro: Coroutine[Any, Any, T],
        timeout: float
    ) -> Optional[T]:
        """Run a coroutine with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    @staticmethod
    def async_test(timeout: float = 10.0):
        """Decorator for async tests with timeout."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await AsyncTestHelper.run_with_timeout(
                    func(*args, **kwargs),
                    timeout=timeout
                )
            return wrapper
        return decorator
    
    @staticmethod
    async def gather_with_errors(
        *coros,
        return_exceptions: bool = True
    ) -> list:
        """Gather multiple coroutines, capturing exceptions."""
        return await asyncio.gather(
            *coros,
            return_exceptions=return_exceptions
        )
    
    @staticmethod
    async def create_tasks_and_wait(
        coros: list,
        wait_for_all: bool = True
    ) -> tuple[set, set]:
        """Create tasks and wait for completion."""
        tasks = [asyncio.create_task(coro) for coro in coros]
        
        if wait_for_all:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.ALL_COMPLETED
            )
        else:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
        
        return done, pending
    
    @staticmethod
    async def assert_completes_within(
        coro: Coroutine[Any, Any, T],
        seconds: float,
        message: str = "Coroutine did not complete within timeout"
    ) -> T:
        """Assert that a coroutine completes within a time limit."""
        try:
            return await asyncio.wait_for(coro, timeout=seconds)
        except asyncio.TimeoutError:
            pytest.fail(f"{message} ({seconds}s)")
    
    @staticmethod
    async def assert_raises_async(
        exception_type: type[Exception],
        coro: Coroutine[Any, Any, Any]
    ) -> Exception:
        """Assert that an async function raises a specific exception."""
        with pytest.raises(exception_type) as exc_info:
            await coro
        return exc_info.value


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition not met"
) -> None:
    """Wait for a sync condition to become true."""
    start = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start < timeout:
        if condition():
            return
        await asyncio.sleep(interval)
    
    raise TimeoutError(f"{message} after {timeout}s")


def async_timeout(seconds: float = 10.0):
    """Pytest mark for async test timeout."""
    return pytest.mark.asyncio(timeout=seconds)


class AsyncContextManager:
    """Test helper for async context managers."""
    
    def __init__(self, enter_result: Any = None, exit_result: Any = None):
        self.enter_result = enter_result
        self.exit_result = exit_result
        self.entered = False
        self.exited = False
        self.exit_exception = None
    
    async def __aenter__(self):
        self.entered = True
        return self.enter_result
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        self.exit_exception = exc_val
        return self.exit_result