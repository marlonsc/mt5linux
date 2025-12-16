"""Resilience patterns for MT5 API communication.

Implements production-grade error handling:
- Retry decorator with exponential backoff and jitter
- Circuit breaker to prevent cascading failures
- Connection health monitoring
- Per-operation timeout configuration

Based on AWS best practices and MT5-specific error codes.

References:
    - https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html
    - https://www.mql5.com/en/forum/450738 (IPC Connection Errors)
    - https://github.com/tomerfiliba/rpyc/issues/233 (RPyC reconnection)
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)

# =============================================================================
# Type Variables
# =============================================================================

T = TypeVar("T")

# =============================================================================
# Retryable Exceptions and Error Codes
# =============================================================================

# RPyC/Network exceptions that are safe to retry
RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    EOFError,
    ConnectionError,
    BrokenPipeError,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
    OSError,  # Catches socket errors
)

# MT5 error codes that indicate transient failures (safe to retry)
# Based on MQL5 documentation and forum discussions
MT5_RETRYABLE_CODES: frozenset[int] = frozenset({
    -10004,  # No IPC connection to MT5 terminal
    -10005,  # IPC send/receive timeout
    128,     # Trade timeout
    129,     # Invalid price
    136,     # Off quotes
    137,     # Broker is busy
    138,     # Requote
    141,     # Too many requests
    146,     # Trade context is busy
})

# MT5 error codes that should NOT be retried (permanent failures)
MT5_PERMANENT_FAILURE_CODES: frozenset[int] = frozenset({
    10016,   # Invalid stops
    10019,   # Not enough money
    10020,   # Price changed
    10021,   # No quotes to process request
    10024,   # Invalid parameters
    10027,   # AutoTrading disabled
    10030,   # Invalid volume
})


# =============================================================================
# Custom Exceptions
# =============================================================================


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(
        self,
        message: str = "Circuit breaker is open - too many failures",
        recovery_time: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.recovery_time = recovery_time


class MT5RetryableError(Exception):
    """MT5 returned a retryable error code."""

    def __init__(self, code: int, description: str) -> None:
        super().__init__(f"MT5 error {code}: {description}")
        self.code = code
        self.description = description


class MT5PermanentError(Exception):
    """MT5 returned a permanent error code that should not be retried."""

    def __init__(self, code: int, description: str) -> None:
        super().__init__(f"MT5 permanent error {code}: {description}")
        self.code = code
        self.description = description


class MaxRetriesExceededError(Exception):
    """Maximum retry attempts exceeded."""

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_error: Exception | None = None,
    ) -> None:
        msg = f"Operation '{operation}' failed after {attempts} attempts"
        if last_error:
            msg += f": {last_error}"
        super().__init__(msg)
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


# =============================================================================
# Retry Decorator with Exponential Backoff
# =============================================================================


def retry_with_backoff(  # noqa: C901
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    retry_on_none: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff and optional jitter.

    Implements AWS-recommended retry pattern with:
    - Exponential backoff: delay = initial_delay * (base ^ attempt)
    - Jitter: randomize delay by 50-100% to prevent thundering herd
    - Maximum delay cap
    - Optional retry on None returns (for transient MT5 failures)

    Args:
        max_attempts: Maximum number of retry attempts (including first try).
        initial_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Base for exponential calculation.
        jitter: If True, randomize delay to prevent thundering herd.
        retryable_exceptions: Tuple of exception types to retry.
            Defaults to RETRYABLE_EXCEPTIONS.
        retry_on_none: If True, also retry when function returns None.
            Useful for MT5 operations that return None on transient failures.

    Returns:
        Decorator function.

    Example:
        >>> @retry_with_backoff(max_attempts=3, initial_delay=1.0)
        ... def flaky_operation():
        ...     return do_something_unreliable()

        >>> @retry_with_backoff(retry_on_none=True)
        ... def mt5_operation():
        ...     return mt5.account_info()  # May return None transiently
    """
    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:  # noqa: C901
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:  # noqa: C901
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)

                    # Check for None if retry_on_none is enabled
                    if retry_on_none and result is None:
                        if attempt < max_attempts - 1:
                            delay = min(
                                initial_delay * (exponential_base ** attempt),
                                max_delay,
                            )
                            if jitter:
                                delay *= 0.5 + random.random()  # noqa: S311

                            log.warning(
                                "%s returned None (attempt %d/%d), retrying in %.2fs",
                                func.__name__,
                                attempt + 1,
                                max_attempts,
                                delay,
                            )
                            time.sleep(delay)
                            continue
                        log.warning(
                            "%s returned None after %d attempts",
                            func.__name__,
                            max_attempts,
                        )
                        return result  # type: ignore[return-value]

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        # Calculate delay with exponential backoff
                        delay = min(
                            initial_delay * (exponential_base ** attempt),
                            max_delay,
                        )
                        # Apply jitter (50-100% of calculated delay)
                        if jitter:
                            delay *= 0.5 + random.random()  # noqa: S311

                        log.warning(
                            "%s failed (attempt %d/%d): %s, retrying in %.2fs",
                            func.__name__,
                            attempt + 1,
                            max_attempts,
                            e,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        log.exception(
                            "%s failed after %d attempts",
                            func.__name__,
                            max_attempts,
                        )
                else:
                    # Success - log if not first attempt
                    if attempt > 0:
                        log.info(
                            "%s succeeded on attempt %d",
                            func.__name__,
                            attempt + 1,
                        )
                    return result

            # All retries exhausted
            if last_exception is not None:
                raise MaxRetriesExceededError(
                    operation=func.__name__,
                    attempts=max_attempts,
                    last_error=last_exception,
                ) from last_exception

            # Should never reach here, but satisfy type checker
            msg = f"{func.__name__} failed with no exception"
            raise RuntimeError(msg)

        return wrapper

    return decorator


# =============================================================================
# Async Retry Decorator
# =============================================================================


def async_retry_with_backoff(  # noqa: C901
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    retry_on_none: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async version of retry decorator with exponential backoff.

    Same parameters and behavior as retry_with_backoff but uses asyncio.sleep.

    Args:
        max_attempts: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential calculation.
        jitter: If True, randomize delay.
        retryable_exceptions: Tuple of exception types to retry.
        retry_on_none: If True, also retry when function returns None.
            Useful for MT5 operations that return None on transient failures.

    Returns:
        Async decorator function.
    """
    import asyncio

    if retryable_exceptions is None:
        retryable_exceptions = RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: C901
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: C901
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    result = await func(*args, **kwargs)

                    # Check for None if retry_on_none is enabled
                    if retry_on_none and result is None:
                        if attempt < max_attempts - 1:
                            delay = min(
                                initial_delay * (exponential_base ** attempt),
                                max_delay,
                            )
                            if jitter:
                                delay *= 0.5 + random.random()  # noqa: S311

                            log.warning(
                                "%s returned None (attempt %d/%d), retrying in %.2fs",
                                func.__name__,
                                attempt + 1,
                                max_attempts,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        log.warning(
                            "%s returned None after %d attempts",
                            func.__name__,
                            max_attempts,
                        )
                        return result

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(
                            initial_delay * (exponential_base ** attempt),
                            max_delay,
                        )
                        if jitter:
                            delay *= 0.5 + random.random()  # noqa: S311

                        log.warning(
                            "%s failed (attempt %d/%d): %s, retrying in %.2fs",
                            func.__name__,
                            attempt + 1,
                            max_attempts,
                            e,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        log.exception(
                            "%s failed after %d attempts",
                            func.__name__,
                            max_attempts,
                        )
                else:
                    # Success - log if not first attempt
                    if attempt > 0:
                        log.info(
                            "%s succeeded on attempt %d",
                            func.__name__,
                            attempt + 1,
                        )
                    return result

            if last_exception is not None:
                raise MaxRetriesExceededError(
                    operation=func.__name__,
                    attempts=max_attempts,
                    last_error=last_exception,
                ) from last_exception

            msg = f"{func.__name__} failed with no exception"
            raise RuntimeError(msg)

        return wrapper

    return decorator


# =============================================================================
# Circuit Breaker
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"      # Normal operation - requests allowed
    OPEN = "open"          # Failing - requests blocked
    HALF_OPEN = "half_open"  # Testing recovery - limited requests


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.

    States:
        CLOSED: Normal operation, requests pass through.
        OPEN: Too many failures, requests blocked immediately.
        HALF_OPEN: Testing if service recovered, limited requests allowed.

    Transitions:
        CLOSED -> OPEN: When failure_threshold reached.
        OPEN -> HALF_OPEN: After recovery_timeout expires.
        HALF_OPEN -> CLOSED: On successful request.
        HALF_OPEN -> OPEN: On failed request.

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        >>> if breaker.can_execute():
        ...     try:
        ...         result = do_operation()
        ...         breaker.record_success()
        ...     except Exception:
        ...         breaker.record_failure()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        name: str = "default",
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout: Seconds to wait before attempting recovery.
            half_open_max_calls: Max requests allowed in half-open state.
            name: Name for logging purposes.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, transitioning if needed."""
        with self._lock:
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                log.info(
                    "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                    self.name,
                )
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = datetime.now(UTC) - self._last_failure_time
        return elapsed >= timedelta(seconds=self.recovery_timeout)

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self._failure_count = 0
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                log.info(
                    "Circuit breaker '%s' recovered: HALF_OPEN -> CLOSED",
                    self.name,
                )
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            if self._state == CircuitState.HALF_OPEN:
                log.warning(
                    "Circuit breaker '%s' failed during recovery: HALF_OPEN -> OPEN",
                    self.name,
                )
                self._state = CircuitState.OPEN

            elif self._failure_count >= self.failure_threshold:
                log.warning(
                    "Circuit breaker '%s' opened after %d failures",
                    self.name,
                    self._failure_count,
                )
                self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request is allowed through the circuit.

        Returns:
            True if request should be attempted.
        """
        current_state = self.state

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
            return False

        # OPEN state
        return False

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            log.info("Circuit breaker '%s' manually reset", self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status for monitoring.

        Returns:
            Dict with state, failure count, and timing info.
        """
        with self._lock:
            status: dict[str, Any] = {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
            }

            if self._last_failure_time:
                status["last_failure"] = self._last_failure_time.isoformat()
                if self._state == CircuitState.OPEN:
                    recovery_at = self._last_failure_time + timedelta(
                        seconds=self.recovery_timeout
                    )
                    status["recovery_at"] = recovery_at.isoformat()

            return status


# =============================================================================
# Per-Operation Timeout Configuration
# =============================================================================

# Default timeouts in seconds for different MT5 operations
OPERATION_TIMEOUTS: dict[str, int] = {
    "default": 30,
    # Terminal operations
    "initialize": 180,  # Initial connection can be slow
    "login": 60,
    "shutdown": 10,
    # Symbol operations
    "symbols_get": 120,  # Can be 9000+ symbols
    "symbols_total": 30,
    "symbol_info": 30,
    "symbol_info_tick": 30,
    "symbol_select": 30,
    # Market data operations
    "copy_rates_from": 60,
    "copy_rates_from_pos": 60,
    "copy_rates_range": 120,  # Can be large date ranges
    "copy_ticks_from": 60,
    "copy_ticks_range": 120,
    # Trading operations
    "order_send": 60,  # Trade execution needs time
    "order_check": 30,
    "order_calc_margin": 30,
    "order_calc_profit": 30,
    # Position/Order queries
    "positions_get": 30,
    "positions_total": 30,
    "orders_get": 30,
    "orders_total": 30,
    # History operations (can be slow for large ranges)
    "history_orders_get": 60,
    "history_orders_total": 60,
    "history_deals_get": 60,
    "history_deals_total": 60,
    # Health check
    "health_check": 10,
}


def get_operation_timeout(operation: str) -> int:
    """Get timeout for a specific operation.

    Args:
        operation: Name of the MT5 operation.

    Returns:
        Timeout in seconds.
    """
    return OPERATION_TIMEOUTS.get(operation, OPERATION_TIMEOUTS["default"])


# =============================================================================
# Health Check Configuration
# =============================================================================

# Default health check interval in seconds
DEFAULT_HEALTH_CHECK_INTERVAL = 30

# Minimum time between health checks
MIN_HEALTH_CHECK_INTERVAL = 5

# Maximum time between health checks
MAX_HEALTH_CHECK_INTERVAL = 300
