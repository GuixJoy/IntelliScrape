"""Smart retry with exponential backoff and rate limiting."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Type


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=list)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    min_delay: float = 0.5
    max_delay: float = 3.0
    requests_per_minute: Optional[int] = None
    burst_size: int = 1
    burst_delay: float = 0.1


class SmartRetry:
    """Smart retry with exponential backoff and jitter."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            delay = delay * random.uniform(0.5, 1.5)

        return delay

    def should_retry(
        self,
        attempt: int,
        status_code: Optional[int] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """Determine if we should retry."""
        if attempt >= self.config.max_retries:
            return False

        if status_code and status_code in self.config.retry_on_status:
            return True

        if exception:
            for exc_type in self.config.retry_on_exceptions:
                if isinstance(exception, exc_type):
                    return True

        return False

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[int, float], None]] = None,
        **kwargs,
    ) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                last_exception = exc

                if not self.should_retry(attempt, exception=exc):
                    raise

                delay = self.calculate_delay(attempt)
                if on_retry:
                    on_retry(attempt + 1, delay)
                time.sleep(delay)

        raise last_exception


class RateLimiter:
    """Intelligent rate limiter with burst support."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._request_times: List[float] = []
        self._last_request: float = 0

    def wait_if_needed(self) -> float:
        """Wait if rate limit would be exceeded. Returns actual wait time."""
        now = time.time()
        wait_time = 0.0

        # Enforce minimum delay
        if self._last_request > 0:
            time_since_last = now - self._last_request
            if time_since_last < self.config.min_delay:
                wait_time = self.config.min_delay - time_since_last
                time.sleep(wait_time)
                now = time.time()

        # Enforce requests per minute
        if self.config.requests_per_minute:
            # Clean old request times
            cutoff = now - 60
            self._request_times = [t for t in self._request_times if t > cutoff]

            if len(self._request_times) >= self.config.requests_per_minute:
                # Wait until oldest request is more than 60s old
                oldest = self._request_times[0]
                wait_time = max(wait_time, 60 - (now - oldest) + 0.1)
                time.sleep(wait_time)
                now = time.time()

        self._last_request = now
        self._request_times.append(now)

        return wait_time

    def get_random_delay(self) -> float:
        """Get a random delay within configured bounds."""
        return random.uniform(self.config.min_delay, self.config.max_delay)


class SmartThrottle:
    """Combined retry and rate limiting."""

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        rate_config: Optional[RateLimitConfig] = None,
    ):
        self.retry = SmartRetry(retry_config)
        self.rate_limiter = RateLimiter(rate_config)

    def execute(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[int, float], None]] = None,
        **kwargs,
    ) -> Any:
        """Execute function with rate limiting and retry."""
        # Wait for rate limit
        self.rate_limiter.wait_if_needed()

        # Execute with retry
        return self.retry.execute_with_retry(func, *args, on_retry=on_retry, **kwargs)
