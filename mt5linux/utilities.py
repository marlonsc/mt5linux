"""Centralized utilities for mt5linux.

All shared utilities organized in a single MT5Utilities class with nested classes.
Uses Pydantic for configuration validation - no external config dependencies.

Hierarchy Level: 2
- Imports: None (self-contained)
- Used by: client.py, async_client.py, server.py

Usage:
    from mt5linux.utilities import MT5Utilities

    # Validators
    MT5Utilities.Validators.version(value)
    MT5Utilities.Validators.last_error(value)

    # Data transformation
    MT5Utilities.Data.wrap_dict(d)
    MT5Utilities.Data.wrap_dicts(items)

    # Retry configuration (Pydantic)
    config = MT5Utilities.RetryConfig(max_attempts=5)
    delay = config.calculate_delay(attempt=2)

    # DateTime
    MT5Utilities.DateTime.to_timestamp(dt)

    # Exceptions
    MT5Utilities.Error - Base exception
    MT5Utilities.RetryableError - Transient failures
    MT5Utilities.PermanentError - Non-retryable failures
    MT5Utilities.MaxRetriesError - Max retries exceeded
    MT5Utilities.NotAvailableError - MT5 not available

    # Circuit Breaker (Pydantic config)
    cb = MT5Utilities.CircuitBreaker(name="mt5")
    if cb.can_execute():
        try:
            result = do_operation()
            cb.record_success()
        except Exception:
            cb.record_failure()
"""

from __future__ import annotations

import logging
import random
import threading
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)


class MT5Utilities:
    """Centralized utilities for mt5linux.

    All configuration uses Pydantic models - no external dependencies.
    """

    # Constants
    VERSION_TUPLE_LEN = 3  # (version, build, version_string)
    ERROR_TUPLE_LEN = 2  # (error_code, error_description)

    # =========================================================================
    # VALIDATORS
    # =========================================================================

    class Validators:
        """Type validators for MT5 data."""

        @staticmethod
        def version(value: object) -> tuple[int, int, str] | None:
            """Validate and convert Any to version tuple."""
            if value is None:
                return None
            expected_len = MT5Utilities.VERSION_TUPLE_LEN
            if not isinstance(value, tuple) or len(value) != expected_len:
                msg = f"Expected version tuple | None, got {type(value).__name__}"
                raise TypeError(msg)
            try:
                return (int(value[0]), int(value[1]), str(value[2]))
            except (ValueError, IndexError, TypeError) as e:
                msg = f"Invalid version tuple: {e}"
                raise TypeError(msg) from e

        @staticmethod
        def last_error(value: object) -> tuple[int, str]:
            """Validate and convert Any to last_error tuple."""
            expected_len = MT5Utilities.ERROR_TUPLE_LEN
            if not isinstance(value, tuple) or len(value) != expected_len:
                msg = f"Expected tuple[int, str], got {type(value).__name__}"
                raise TypeError(msg)
            try:
                return (int(value[0]), str(value[1]))
            except (ValueError, IndexError, TypeError) as e:
                msg = f"Invalid error tuple: {e}"
                raise TypeError(msg) from e

        @staticmethod
        def bool_value(value: object) -> bool:
            """Validate and convert Any to bool."""
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return bool(value)
            msg = f"Expected bool, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def int_value(value: object) -> int:
            """Validate and convert Any to int."""
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            msg = f"Expected int, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def int_optional(value: object) -> int | None:
            """Validate and convert Any to int | None."""
            if value is None:
                return None
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            msg = f"Expected int | None, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def float_optional(value: object) -> float | None:
            """Validate and convert Any to float | None."""
            if value is None:
                return None
            if isinstance(value, int | float) and not isinstance(value, bool):
                return float(value)
            msg = f"Expected float | None, got {type(value).__name__}"
            raise TypeError(msg)

    # =========================================================================
    # DATA WRAPPER
    # =========================================================================

    class DataWrapper:
        """Wrapper for MT5 data dict with attribute access."""

        __slots__ = ("_data",)

        def __init__(self, data: dict[str, Any]) -> None:
            object.__setattr__(self, "_data", data)

        def __getattr__(self, name: str) -> Any:
            try:
                return self._data[name]
            except KeyError:
                msg = f"'{type(self).__name__}' has no attribute '{name}'"
                raise AttributeError(msg) from None

        def __repr__(self) -> str:
            return f"{type(self).__name__}({self._data})"

        def _asdict(self) -> dict[str, Any]:
            """Return underlying dict (compatibility with named tuples)."""
            return self._data

    class Data:
        """Transform MT5 data between formats."""

        @staticmethod
        def wrap_dict(d: dict[str, Any] | Any) -> MT5Utilities.DataWrapper | Any:
            """Convert dict to object with attribute access."""
            if isinstance(d, dict):
                return MT5Utilities.DataWrapper(d)
            return d

        @staticmethod
        def wrap_dicts(items: tuple | list | None) -> tuple | None:
            """Convert tuple/list of dicts to tuple of objects."""
            if items is None:
                return None
            return tuple(MT5Utilities.Data.wrap_dict(d) for d in items)

        @staticmethod
        def unwrap_chunks(result: dict[str, Any] | None) -> tuple | None:
            """Reassemble chunked response from server into tuple of objects."""
            if result is None:
                return None

            if isinstance(result, dict) and "chunks" in result:
                all_items: list[MT5Utilities.DataWrapper] = []
                for chunk in result["chunks"]:
                    all_items.extend(MT5Utilities.DataWrapper(d) for d in chunk)
                return tuple(all_items)

            if isinstance(result, tuple | list):
                return MT5Utilities.Data.wrap_dicts(result)

            return None

    # =========================================================================
    # DATETIME
    # =========================================================================

    class DateTime:
        """DateTime conversion utilities."""

        @staticmethod
        def to_timestamp(dt: datetime | int | None) -> int | None:
            """Convert datetime to Unix timestamp for MT5 API."""
            if dt is None:
                return None
            if isinstance(dt, datetime):
                return int(dt.timestamp())
            return dt

    # =========================================================================
    # EXCEPTIONS
    # =========================================================================

    class Error(Exception):
        """Base exception for all MT5 client errors."""

    class RetryableError(Error):
        """Error that can be retried (transient failure)."""

        def __init__(self, code: int, description: str) -> None:
            super().__init__(f"MT5 error {code}: {description}")
            self.code = code
            self.description = description

    class PermanentError(Error):
        """Error that should not be retried."""

        def __init__(self, code: int, description: str) -> None:
            super().__init__(f"MT5 permanent error {code}: {description}")
            self.code = code
            self.description = description

    class MaxRetriesError(Error):
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

    class NotAvailableError(Error):
        """MT5 module not available."""

    # =========================================================================
    # RETRY CONFIG (Pydantic)
    # =========================================================================

    class RetryConfig(BaseModel):
        """Retry behavior configuration with Pydantic validation.

        Usage:
            config = MT5Utilities.RetryConfig(max_attempts=5)
            delay = config.calculate_delay(attempt=2)
        """

        model_config = ConfigDict(frozen=True)

        max_attempts: int = Field(default=3, ge=1, le=10)
        initial_delay: float = Field(default=0.5, ge=0.1, le=10.0)
        max_delay: float = Field(default=10.0, ge=1.0, le=300.0)
        exponential_base: float = Field(default=2.0, ge=1.5, le=4.0)
        jitter: bool = True
        retry_on_none: bool = True

        def calculate_delay(self, attempt: int) -> float:
            """Calculate exponential backoff delay with optional jitter.

            Args:
                attempt: Current attempt number (0-indexed).

            Returns:
                Delay in seconds before next retry.
            """
            delay = min(
                self.initial_delay * (self.exponential_base**attempt),
                self.max_delay,
            )
            if self.jitter:
                # Add 0-100% jitter
                delay *= 0.5 + random.random()  # noqa: S311
            return delay

    # =========================================================================
    # CIRCUIT BREAKER CONFIG (Pydantic)
    # =========================================================================

    class CircuitBreakerConfig(BaseModel):
        """Circuit breaker configuration with Pydantic validation.

        Usage:
            config = MT5Utilities.CircuitBreakerConfig(failure_threshold=3)
            cb = MT5Utilities.CircuitBreaker(config=config)
        """

        model_config = ConfigDict(frozen=True)

        failure_threshold: int = Field(default=5, ge=1, le=100)
        recovery_timeout: float = Field(default=60.0, ge=1.0, le=3600.0)
        half_open_max_calls: int = Field(default=1, ge=1, le=10)

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================

    class CircuitBreaker:
        """Circuit breaker for fault tolerance.

        Implements the circuit breaker pattern to prevent cascading failures.

        States:
            CLOSED: Normal operation, requests pass through
            OPEN: Too many failures, requests blocked
            HALF_OPEN: Testing recovery, limited requests allowed

        Usage:
            cb = MT5Utilities.CircuitBreaker(name="mt5-client")
            if cb.can_execute():
                try:
                    result = risky_operation()
                    cb.record_success()
                except Exception:
                    cb.record_failure()
                    raise
            else:
                raise MT5Utilities.CircuitBreaker.OpenError()
        """

        class State(IntEnum):
            """Circuit breaker state."""

            CLOSED = 0  # Normal operation
            OPEN = 1  # Failing - requests blocked
            HALF_OPEN = 2  # Testing recovery

        class OpenError(Exception):
            """Raised when circuit is open."""

            def __init__(
                self,
                message: str = "Circuit breaker is open - too many failures",
                recovery_time: datetime | None = None,
            ) -> None:
                super().__init__(message)
                self.recovery_time = recovery_time

        def __init__(
            self,
            config: MT5Utilities.CircuitBreakerConfig | None = None,
            name: str = "default",
        ) -> None:
            """Initialize circuit breaker.

            Args:
                config: Circuit breaker configuration (Pydantic model).
                name: Name for logging purposes.
            """
            self._config = config or MT5Utilities.CircuitBreakerConfig()
            self.name = name
            self._state = MT5Utilities.CircuitBreaker.State.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time: datetime | None = None
            self._half_open_calls = 0
            self._lock = threading.RLock()

        @property
        def config(self) -> MT5Utilities.CircuitBreakerConfig:
            """Get circuit breaker configuration."""
            return self._config

        @property
        def state(self) -> MT5Utilities.CircuitBreaker.State:
            """Get current circuit state, transitioning if needed."""
            with self._lock:
                if (
                    self._state == MT5Utilities.CircuitBreaker.State.OPEN
                    and self._should_attempt_reset()
                ):
                    log.info(
                        "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                        self.name,
                    )
                    self._state = MT5Utilities.CircuitBreaker.State.HALF_OPEN
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
            return self.state == MT5Utilities.CircuitBreaker.State.CLOSED

        @property
        def is_open(self) -> bool:
            """Check if circuit is open (blocking requests)."""
            return self.state == MT5Utilities.CircuitBreaker.State.OPEN

        def _should_attempt_reset(self) -> bool:
            """Check if enough time passed to attempt recovery."""
            if self._last_failure_time is None:
                return False
            elapsed = datetime.now(UTC) - self._last_failure_time
            return elapsed >= timedelta(seconds=self._config.recovery_timeout)

        def record_success(self) -> None:
            """Record a successful operation."""
            with self._lock:
                self._failure_count = 0
                self._success_count += 1
                if self._state == MT5Utilities.CircuitBreaker.State.HALF_OPEN:
                    log.info(
                        "Circuit breaker '%s' recovered: HALF_OPEN -> CLOSED",
                        self.name,
                    )
                    self._state = MT5Utilities.CircuitBreaker.State.CLOSED

        def record_failure(self) -> None:
            """Record a failed operation."""
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.now(UTC)

                if self._state == MT5Utilities.CircuitBreaker.State.HALF_OPEN:
                    log.warning(
                        "Circuit breaker '%s' failed during recovery",
                        self.name,
                    )
                    self._state = MT5Utilities.CircuitBreaker.State.OPEN
                elif self._failure_count >= self._config.failure_threshold:
                    log.warning(
                        "Circuit breaker '%s' opened after %d failures",
                        self.name,
                        self._failure_count,
                    )
                    self._state = MT5Utilities.CircuitBreaker.State.OPEN

        def can_execute(self) -> bool:
            """Check if a request is allowed through the circuit."""
            current_state = self.state

            if current_state == MT5Utilities.CircuitBreaker.State.CLOSED:
                return True

            if current_state == MT5Utilities.CircuitBreaker.State.HALF_OPEN:
                with self._lock:
                    if self._half_open_calls < self._config.half_open_max_calls:
                        self._half_open_calls += 1
                        return True
                return False

            return False  # OPEN state

        def reset(self) -> None:
            """Manually reset the circuit breaker to closed state."""
            with self._lock:
                log.info("Circuit breaker '%s' manually reset", self.name)
                self._state = MT5Utilities.CircuitBreaker.State.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._last_failure_time = None
                self._half_open_calls = 0

        def get_status(self) -> dict[str, Any]:
            """Get circuit breaker status for monitoring."""
            with self._lock:
                status: dict[str, Any] = {
                    "name": self.name,
                    "state": self._state.name,
                    "failure_count": self._failure_count,
                    "success_count": self._success_count,
                    "failure_threshold": self._config.failure_threshold,
                }

                if self._last_failure_time:
                    status["last_failure"] = self._last_failure_time.isoformat()
                    if self._state == MT5Utilities.CircuitBreaker.State.OPEN:
                        recovery_at = self._last_failure_time + timedelta(
                            seconds=self._config.recovery_timeout
                        )
                        status["recovery_at"] = recovery_at.isoformat()

                return status

    # =========================================================================
    # BACKOFF CONFIG (Pydantic) - For server restart
    # =========================================================================

    class BackoffConfig(BaseModel):
        """Backoff configuration for server restarts.

        Usage:
            config = MT5Utilities.BackoffConfig()
            delay = config.calculate_delay(attempt=3)
        """

        model_config = ConfigDict(frozen=True)

        base_delay: float = Field(default=1.0, ge=0.1, le=30.0)
        max_delay: float = Field(default=60.0, ge=1.0, le=300.0)
        multiplier: float = Field(default=2.0, ge=1.5, le=4.0)
        jitter_factor: float = Field(default=0.1, ge=0.0, le=0.5)

        def calculate_delay(self, attempt: int) -> float:
            """Calculate delay with exponential backoff and jitter.

            Args:
                attempt: Current attempt number (0-indexed).

            Returns:
                Delay in seconds with jitter applied.
            """
            delay = self.base_delay * (self.multiplier**attempt)
            delay = min(delay, self.max_delay)
            # S311: random is fine for jitter - not cryptographic
            jitter = delay * self.jitter_factor * (2 * random.random() - 1)  # noqa: S311
            return max(0, delay + jitter)
