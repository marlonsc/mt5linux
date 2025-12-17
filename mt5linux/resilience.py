"""Resilience patterns for MT5Linux.

Implements circuit breaker, retry, and health monitoring utilities
for high-availability gRPC communication.

Hierarchy Level: 1
- Imports: config.py (Level 1)
- Used by: async_client.py, client.py

Usage:
    >>> from mt5linux.resilience import CircuitBreaker
    >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
    >>> if cb.can_execute():
    ...     try:
    ...         result = await some_operation()
    ...         cb.record_success()
    ...     except Exception:
    ...         cb.record_failure()
    ...         raise

"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states.

    States:
        CLOSED: Normal operation, requests pass through.
        OPEN: Service failing, requests immediately rejected.
        HALF_OPEN: Testing recovery, limited requests allowed.

    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker implementation.

    Prevents cascading failures by stopping requests when
    a service is failing repeatedly.

    The circuit has three states:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, requests immediately rejected
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Attributes:
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds to wait before trying again (OPEN → HALF_OPEN).
        half_open_max_calls: Max test calls in HALF_OPEN state.

    Example:
        >>> cb = CircuitBreaker(failure_threshold=3)
        >>> for _ in range(3):
        ...     cb.record_failure()
        >>> cb.state
        <CircuitState.OPEN: 'open'>

    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout.

        Returns:
            Current CircuitState, transitioning OPEN → HALF_OPEN if timeout elapsed.

        """
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                log.info(
                    "Circuit breaker transitioning OPEN → HALF_OPEN "
                    "(recovery timeout %.1fs elapsed)",
                    elapsed,
                )
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is in CLOSED state (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is in OPEN state (rejecting requests)."""
        return self.state == CircuitState.OPEN

    def record_success(self) -> None:
        """Record a successful call.

        In HALF_OPEN: After enough successes, transitions to CLOSED.
        In CLOSED: Resets failure count.

        """
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            log.debug(
                "Circuit breaker HALF_OPEN: success %d/%d",
                self._half_open_calls,
                self.half_open_max_calls,
            )
            if self._half_open_calls >= self.half_open_max_calls:
                log.info(
                    "Circuit breaker transitioning HALF_OPEN → CLOSED "
                    "(recovered after %d successes)",
                    self._half_open_calls,
                )
                self._state = CircuitState.CLOSED
                self._failure_count = 0

        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call.

        In HALF_OPEN: Immediately transitions back to OPEN.
        In CLOSED: Increments failure count, may transition to OPEN.

        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            log.warning(
                "Circuit breaker transitioning HALF_OPEN → OPEN (failure during test)"
            )
            self._state = CircuitState.OPEN

        elif self._failure_count >= self.failure_threshold:
            log.warning(
                "Circuit breaker transitioning CLOSED → OPEN (threshold %d reached)",
                self.failure_threshold,
            )
            self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a call is allowed.

        Returns:
            True if call allowed (CLOSED or HALF_OPEN with capacity).
            False if circuit is OPEN.

        """
        state = self.state  # Triggers recovery check
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False  # OPEN

    def reset(self) -> None:
        """Reset circuit to initial CLOSED state.

        Use with caution - typically for testing or manual intervention.

        """
        log.info("Circuit breaker manually reset to CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = 0.0


async def retry_with_backoff[T](
    coro_factory: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> T:
    """Execute async operation with exponential backoff retry.

    Args:
        coro_factory: Callable that returns an awaitable (not a coroutine directly).
        max_attempts: Maximum number of attempts.
        initial_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter: Add random jitter to delays.

    Returns:
        Result of successful operation.

    Raises:
        Exception: Last exception if all retries fail.

    Example:
        >>> async def fetch():
        ...     return await client.get_data()
        >>> result = await retry_with_backoff(fetch, max_attempts=3)

    """
    delay = initial_delay
    last_exception: BaseException | None = None

    for attempt in range(max_attempts):
        try:
            return await coro_factory()
        except Exception as e:
            last_exception = e
            if attempt == max_attempts - 1:
                log.error(
                    "All %d retry attempts failed. Last error: %s",
                    max_attempts,
                    e,
                )
                raise

            # Calculate backoff delay
            wait_time = min(delay, max_delay)
            if jitter:
                # Add 0-50% random jitter
                jitter_amount = wait_time * random.uniform(0, 0.5)  # noqa: S311
                wait_time += jitter_amount

            log.warning(
                "Attempt %d/%d failed: %s. Retrying in %.2fs",
                attempt + 1,
                max_attempts,
                e,
                wait_time,
            )

            await asyncio.sleep(wait_time)
            delay *= exponential_base

    # Should not reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    msg = "Retry failed with no exception recorded"
    raise RuntimeError(msg)


class ConnectionState(Enum):
    """Connection state for health monitoring."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class HealthStatus:
    """Health status snapshot.

    Attributes:
        state: Current connection state.
        last_check: Timestamp of last health check.
        consecutive_failures: Number of consecutive failed checks.
        circuit_state: Circuit breaker state if enabled.

    """

    state: ConnectionState
    last_check: float
    consecutive_failures: int = 0
    circuit_state: CircuitState | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        return self.state == ConnectionState.CONNECTED
