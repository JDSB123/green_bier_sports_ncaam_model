"""
Retry utilities for resilient API calls.

Implements exponential backoff with jitter for transient failures.
"""

import asyncio
import functools
import logging
import random
from typing import Callable, TypeVar, Any, Optional, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay with exponential backoff and optional jitter."""
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay,
    )
    
    if config.jitter:
        # Add random jitter (0-25% of delay)
        delay = delay * (1 + random.uniform(0, 0.25))
    
    return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs,
) -> T:
    """
    Execute an async function with retry logic.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func
        
    Raises:
        Last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed. Last error: {e}"
                )
    
    raise last_exception


def retry_sync(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs,
) -> T:
    """
    Execute a sync function with retry logic.
    
    Args:
        func: Function to execute
        *args: Positional arguments for func
        config: Retry configuration
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func
        
    Raises:
        Last exception if all retries fail
    """
    import time
    
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed. Last error: {e}"
                )
    
    raise last_exception


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to a function.
    
    Usage:
        @with_retry(RetryConfig(max_attempts=5))
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=config, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return retry_sync(func, *args, config=config, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Simple circuit breaker implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> str:
        return self._state
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker."""
        async with self._lock:
            if self._state == self.OPEN:
                # Check if timeout has passed
                import time
                if time.time() - self._last_failure_time >= self.timeout:
                    self._state = self.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker is open. Retry after {self.timeout}s"
                    )
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        async with self._lock:
            self._failure_count = 0
            
            if self._state == self.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = self.CLOSED
                    logger.info("Circuit breaker CLOSED - service recovered")
    
    async def _on_failure(self):
        import time
        
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                logger.warning("Circuit breaker OPEN - service still failing")
            elif self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self._failure_count} failures"
                )


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass

