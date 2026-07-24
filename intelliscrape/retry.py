"""Smart retry logic with engine fallback for IntelliScrape."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .exceptions import IntelliScrapeError


@dataclass
class RetryConfig:
    """Configuration for smart retries."""
    max_retries: int = 3
    backoff_factor: float = 1.5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    retry_on_status: Tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_on_exceptions: Tuple[type, ...] = (ConnectionError, TimeoutError)


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt: int
    engine: str
    delay: float
    error: Optional[str] = None
    success: bool = False


class SmartRetry:
    """Smart retry with engine fallback."""
    
    # Engine fallback order
    ENGINE_FALLBACK = ["static", "playwright_stealth", "camoufox", "nodriver"]
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.attempts: List[RetryAttempt] = []
    
    def execute_with_retry(
        self,
        func: Callable,
        engines: Dict[str, Callable],
        url: str,
        *,
        preferred_engine: Optional[str] = None,
        on_retry: Optional[Callable[[RetryAttempt], None]] = None,
    ) -> Tuple[any, str]:
        """Execute function with smart retry and engine fallback.
        
        Parameters
        ----------
        func : callable
            Function to execute (called if no engine specified).
        engines : dict
            Dictionary of engine_name -> fetch_function.
        url : str
            URL being fetched.
        preferred_engine : str, optional
            Preferred engine to try first.
        on_retry : callable, optional
            Callback when retry occurs.
            
        Returns
        -------
        tuple
            (result, engine_used)
        """
        self.attempts = []
        
        # Determine engine order
        engine_order = self._get_engine_order(preferred_engine, engines)
        
        attempt = 0
        last_error = None
        
        for engine_name in engine_order:
            if engine_name not in engines:
                continue
            
            fetch_func = engines[engine_name]
            
            for retry in range(self.config.max_retries):
                attempt += 1
                delay = self._calculate_delay(retry)
                
                try:
                    # Execute
                    result = fetch_func(url)
                    
                    # Record success
                    attempt_info = RetryAttempt(
                        attempt=attempt,
                        engine=engine_name,
                        delay=delay,
                        success=True,
                    )
                    self.attempts.append(attempt_info)
                    
                    if on_retry:
                        on_retry(attempt_info)
                    
                    return result, engine_name
                    
                except Exception as e:
                    last_error = str(e)
                    
                    # Record failure
                    attempt_info = RetryAttempt(
                        attempt=attempt,
                        engine=engine_name,
                        delay=delay,
                        error=last_error,
                        success=False,
                    )
                    self.attempts.append(attempt_info)
                    
                    if on_retry:
                        on_retry(attempt_info)
                    
                    # Check if we should retry
                    if not self._should_retry(e, retry):
                        break
                    
                    # Wait before retry
                    if delay > 0:
                        time.sleep(delay)
        
        # All attempts failed
        raise IntelliScrapeError(
            f"All retry attempts failed for {url}. "
            f"Last error: {last_error}"
        )
    
    def execute_with_fallback(
        self,
        fetch_funcs: Dict[str, Callable[[str], any]],
        url: str,
        *,
        preferred_engine: Optional[str] = None,
        on_engine_change: Optional[Callable[[str, str], None]] = None,
    ) -> Tuple[any, str]:
        """Execute with automatic engine fallback.
        
        Parameters
        ----------
        fetch_funcs : dict
            Dictionary of engine_name -> fetch_function(url).
        url : str
            URL to fetch.
        preferred_engine : str, optional
            Preferred engine to try first.
        on_engine_change : callable, optional
            Callback when engine changes: (old_engine, new_engine).
            
        Returns
        -------
        tuple
            (result, engine_used)
        """
        engine_order = self._get_engine_order(preferred_engine, fetch_funcs)
        
        last_engine = None
        
        for engine_name in engine_order:
            if engine_name not in fetch_funcs:
                continue
            
            fetch_func = fetch_funcs[engine_name]
            
            # Notify engine change
            if last_engine and on_engine_change:
                on_engine_change(last_engine, engine_name)
            
            try:
                result = fetch_func(url)
                return result, engine_name
            except Exception as e:
                last_engine = engine_name
                continue
        
        raise IntelliScrapeError(f"All engines failed for {url}")
    
    def _get_engine_order(
        self,
        preferred: Optional[str],
        available: Dict[str, any],
    ) -> List[str]:
        """Get engine execution order."""
        order = []
        
        # Add preferred engine first
        if preferred and preferred in available:
            order.append(preferred)
        
        # Add fallback engines
        for engine in self.ENGINE_FALLBACK:
            if engine not in order and engine in available:
                order.append(engine)
        
        return order
    
    def _calculate_delay(self, retry: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.config.initial_delay * (self.config.backoff_factor ** retry)
        return min(delay, self.config.max_delay)
    
    def _should_retry(self, error: Exception, retry: int) -> bool:
        """Check if we should retry."""
        # Check retry count
        if retry >= self.config.max_retries - 1:
            return False
        
        # Check exception type
        if isinstance(error, self.config.retry_on_exceptions):
            return True
        
        # Check status code (if HTTPError)
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            if error.response.status_code in self.config.retry_on_status:
                return True
        
        return False
    
    def get_stats(self) -> Dict:
        """Get retry statistics."""
        return {
            "total_attempts": len(self.attempts),
            "successful": sum(1 for a in self.attempts if a.success),
            "failed": sum(1 for a in self.attempts if not a.success),
            "engines_tried": list(set(a.engine for a in self.attempts)),
            "attempts": [
                {
                    "attempt": a.attempt,
                    "engine": a.engine,
                    "success": a.success,
                    "error": a.error,
                }
                for a in self.attempts
            ],
        }
