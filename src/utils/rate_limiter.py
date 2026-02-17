"""Rate limiting utilities for API calls."""

import time
import threading
from functools import wraps
from collections import deque
from typing import Callable, Any

from src.utils.logger import setup_logger

logger = setup_logger("rate_limiter")


class RateLimiter:
    """Thread-safe rate limiter using sliding window."""

    def __init__(self, calls: int = 10, period: float = 60.0):
        """Initialize rate limiter.

        Args:
            calls: Maximum number of calls allowed in the period.
            period: Time period in seconds.
        """
        self.calls = calls
        self.period = period
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Acquire permission to make a call. Blocks if rate limit exceeded.

        Returns:
            Time waited in seconds (0 if no wait needed).
        """
        waited = 0.0
        with self._lock:
            now = time.monotonic()

            # Remove timestamps outside the window
            while self._timestamps and now - self._timestamps[0] >= self.period:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.calls:
                sleep_time = self.period - (now - self._timestamps[0])
                if sleep_time > 0:
                    logger.debug(
                        "Rate limit reached (%d/%d). Sleeping %.1fs",
                        len(self._timestamps), self.calls, sleep_time,
                    )
                    self._lock.release()
                    time.sleep(sleep_time)
                    waited = sleep_time
                    self._lock.acquire()
                    now = time.monotonic()
                    while self._timestamps and now - self._timestamps[0] >= self.period:
                        self._timestamps.popleft()

            self._timestamps.append(time.monotonic())

        return waited

    @property
    def remaining(self) -> int:
        """Number of calls remaining in the current window."""
        with self._lock:
            now = time.monotonic()
            while self._timestamps and now - self._timestamps[0] >= self.period:
                self._timestamps.popleft()
            return max(0, self.calls - len(self._timestamps))


# Global registry of rate limiters per source
_limiters: dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def get_limiter(name: str, calls: int = 10, period: float = 60.0) -> RateLimiter:
    """Get or create a named rate limiter."""
    with _registry_lock:
        if name not in _limiters:
            _limiters[name] = RateLimiter(calls=calls, period=period)
        return _limiters[name]


def rate_limit(calls: int = 10, period: float = 60.0) -> Callable:
    """Decorator for rate-limiting function calls.

    Args:
        calls: Maximum calls per period.
        period: Period in seconds.
    """
    limiter = RateLimiter(calls=calls, period=period)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            limiter.acquire()
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            limiter.acquire()
            return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
