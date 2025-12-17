"""Centralized utilities for mt5linux.

Minimal structure with maximum integration:
- Uses MT5Config for all configuration (no separate config classes)
- Uses MT5Constants for enums (CircuitBreakerState)
- All data utilities consolidated in Data class
- All exceptions consolidated in Exceptions class

Hierarchy Level: 2
- Imports: MT5Config, MT5Constants
- Used by: client.py, async_client.py, server.py

Usage:
    from mt5linux.utilities import MT5Utilities

    # Exceptions
    raise MT5Utilities.Exceptions.RetryableError(code, description)
    raise MT5Utilities.Exceptions.CircuitBreakerOpenError()

    # Data utilities
    MT5Utilities.Data.validate_version(value)
    MT5Utilities.Data.wrap(d)
    MT5Utilities.Data.to_timestamp(dt)

    # Circuit Breaker (uses MT5Config directly)
    cb = MT5Utilities.CircuitBreaker(config=mt5_config, name="mt5")
    if cb.can_execute():
        try:
            result = do_operation()
            cb.record_success()
        except Exception:
            cb.record_failure()
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mt5linux.config import MT5Config

from mt5linux.constants import MT5Constants

log = logging.getLogger(__name__)


class MT5Utilities:
    """Centralized utilities for mt5linux.

    Minimal structure:
    - Exceptions: All exception classes
    - Data: All data utilities (validation, wrapping, datetime)
    - CircuitBreaker: Fault tolerance pattern
    """

    # Constants
    VERSION_TUPLE_LEN = 3  # (version, build, version_string)
    ERROR_TUPLE_LEN = 2  # (error_code, error_description)

    # =========================================================================
    # EXCEPTIONS
    # =========================================================================

    class Exceptions:
        """All MT5 exceptions in one container."""

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

        class CircuitBreakerOpenError(Error):
            """Raised when circuit breaker is open."""

            def __init__(
                self,
                message: str = "Circuit breaker is open - too many failures",
                recovery_time: datetime | None = None,
            ) -> None:
                super().__init__(message)
                self.recovery_time = recovery_time

    # =========================================================================
    # DATA UTILITIES
    # =========================================================================

    class Data:
        """Unified data utilities - validation, wrapping, transformation, datetime."""

        class Wrapper:
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

        # --- Validators ---

        @staticmethod
        def validate_version(value: object) -> tuple[int, int, str] | None:
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
        def validate_last_error(value: object) -> tuple[int, str]:
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
        def validate_bool(value: object) -> bool:
            """Validate and convert Any to bool."""
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return bool(value)
            msg = f"Expected bool, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def validate_int(value: object) -> int:
            """Validate and convert Any to int."""
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            msg = f"Expected int, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def validate_int_optional(value: object) -> int | None:
            """Validate and convert Any to int | None."""
            if value is None:
                return None
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            msg = f"Expected int | None, got {type(value).__name__}"
            raise TypeError(msg)

        @staticmethod
        def validate_float_optional(value: object) -> float | None:
            """Validate and convert Any to float | None."""
            if value is None:
                return None
            if isinstance(value, int | float) and not isinstance(value, bool):
                return float(value)
            msg = f"Expected float | None, got {type(value).__name__}"
            raise TypeError(msg)

        # --- Transformations ---

        @staticmethod
        def wrap(d: dict[str, Any] | Any) -> MT5Utilities.Data.Wrapper | Any:
            """Convert dict to object with attribute access."""
            if isinstance(d, dict):
                return MT5Utilities.Data.Wrapper(d)
            return d

        @staticmethod
        def wrap_many(items: tuple | list | None) -> tuple | None:
            """Convert tuple/list of dicts to tuple of objects."""
            if items is None:
                return None
            return tuple(MT5Utilities.Data.wrap(d) for d in items)

        @staticmethod
        def unwrap_chunks(result: dict[str, Any] | None) -> tuple | None:
            """Reassemble chunked response from server into tuple of objects."""
            if result is None:
                return None

            if isinstance(result, dict) and "chunks" in result:
                all_items: list[MT5Utilities.Data.Wrapper] = []
                for chunk in result["chunks"]:
                    all_items.extend(MT5Utilities.Data.Wrapper(d) for d in chunk)
                return tuple(all_items)

            if isinstance(result, tuple | list):
                return MT5Utilities.Data.wrap_many(result)

            return None

        # --- DateTime ---

        @staticmethod
        def to_timestamp(dt: datetime | int | None) -> int | None:
            """Convert datetime to Unix timestamp for MT5 API."""
            if dt is None:
                return None
            if isinstance(dt, datetime):
                return int(dt.timestamp())
            return dt

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================

    class CircuitBreaker:
        """Circuit breaker for fault tolerance.

        Implements the circuit breaker pattern to prevent cascading failures.
        Uses MT5Config directly for configuration (no separate config class).

        States (from MT5Constants.CircuitBreakerState):
            CLOSED: Normal operation, requests pass through
            OPEN: Too many failures, requests blocked
            HALF_OPEN: Testing recovery, limited requests allowed

        Usage:
            cb = MT5Utilities.CircuitBreaker(config=mt5_config, name="mt5-client")
            if cb.can_execute():
                try:
                    result = risky_operation()
                    cb.record_success()
                except Exception:
                    cb.record_failure()
                    raise
            else:
                raise MT5Utilities.Exceptions.CircuitBreakerOpenError()
        """

        def __init__(
            self,
            config: MT5Config,
            name: str = "default",
        ) -> None:
            """Initialize circuit breaker.

            Args:
                config: MT5Config with cb_threshold, cb_recovery, cb_half_open_max.
                name: Name for logging purposes.

            """
            self._config = config
            self.name = name
            self._state = MT5Constants.CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time: datetime | None = None
            self._half_open_calls = 0
            self._lock = threading.RLock()

        @property
        def config(self) -> MT5Config:
            """Get configuration."""
            return self._config

        @property
        def state(self) -> MT5Constants.CircuitBreakerState:
            """Get current circuit state, transitioning if needed."""
            with self._lock:
                if (
                    self._state == MT5Constants.CircuitBreakerState.OPEN
                    and self._should_attempt_reset()
                ):
                    log.info(
                        "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                        self.name,
                    )
                    self._state = MT5Constants.CircuitBreakerState.HALF_OPEN
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
            return self.state == MT5Constants.CircuitBreakerState.CLOSED

        @property
        def is_open(self) -> bool:
            """Check if circuit is open (blocking requests)."""
            return self.state == MT5Constants.CircuitBreakerState.OPEN

        def _should_attempt_reset(self) -> bool:
            """Check if enough time passed to attempt recovery."""
            if self._last_failure_time is None:
                return False
            elapsed = datetime.now(UTC) - self._last_failure_time
            return elapsed >= timedelta(seconds=self._config.cb_recovery)

        def record_success(self) -> None:
            """Record a successful operation."""
            with self._lock:
                self._failure_count = 0
                self._success_count += 1
                if self._state == MT5Constants.CircuitBreakerState.HALF_OPEN:
                    log.info(
                        "Circuit breaker '%s' recovered: HALF_OPEN -> CLOSED",
                        self.name,
                    )
                    self._state = MT5Constants.CircuitBreakerState.CLOSED

        def record_failure(self) -> None:
            """Record a failed operation."""
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.now(UTC)

                if self._state == MT5Constants.CircuitBreakerState.HALF_OPEN:
                    log.warning(
                        "Circuit breaker '%s' failed during recovery",
                        self.name,
                    )
                    self._state = MT5Constants.CircuitBreakerState.OPEN
                elif self._failure_count >= self._config.cb_threshold:
                    log.warning(
                        "Circuit breaker '%s' opened after %d failures",
                        self.name,
                        self._failure_count,
                    )
                    self._state = MT5Constants.CircuitBreakerState.OPEN

        def can_execute(self) -> bool:
            """Check if a request is allowed through the circuit."""
            current_state = self.state

            if current_state == MT5Constants.CircuitBreakerState.CLOSED:
                return True

            if current_state == MT5Constants.CircuitBreakerState.HALF_OPEN:
                with self._lock:
                    if self._half_open_calls < self._config.cb_half_open_max:
                        self._half_open_calls += 1
                        return True
                return False

            return False  # OPEN state

        def reset(self) -> None:
            """Manually reset the circuit breaker to closed state."""
            with self._lock:
                log.info("Circuit breaker '%s' manually reset", self.name)
                self._state = MT5Constants.CircuitBreakerState.CLOSED
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
                    "failure_threshold": self._config.cb_threshold,
                }

                if self._last_failure_time:
                    status["last_failure"] = self._last_failure_time.isoformat()
                    if self._state == MT5Constants.CircuitBreakerState.OPEN:
                        recovery_at = self._last_failure_time + timedelta(
                            seconds=self._config.cb_recovery
                        )
                        status["recovery_at"] = recovery_at.isoformat()

                return status
