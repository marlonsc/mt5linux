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

# pylint: disable=no-member  # Protobuf generated code has dynamic members
import asyncio
import logging
import random
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NoReturn, Protocol, TypeVar, runtime_checkable

import numpy as np
import orjson

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from numpy.typing import NDArray

    from mt5linux.config import MT5Config


from mt5linux.constants import MT5Constants as c

T = TypeVar("T")


# Protocols for gRPC protobuf types
@runtime_checkable
class _NumpyArrayProto(Protocol):
    """Protocol for NumpyArray protobuf message."""

    data: bytes
    dtype: str
    shape: Sequence[int]


@runtime_checkable
class _SymbolsResponseProto(Protocol):
    """Protocol for SymbolsResponse protobuf message."""

    total: int
    chunks: Sequence[bytes]


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
                """Initialize retryable error.

                Args:
                    code: MT5 error code.
                    description: Error description.

                """
                super().__init__(f"MT5 error {code}: {description}")
                self.code = code
                self.description = description

        class PermanentError(Error):
            """Error that should not be retried."""

            def __init__(self, code: int, description: str) -> None:
                """Initialize permanent error.

                Args:
                    code: MT5 error code.
                    description: Error description.

                """
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
                """Initialize max retries error.

                Args:
                    operation: Name of the failed operation.
                    attempts: Number of attempts made.
                    last_error: The last exception that occurred.

                """
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
                """Initialize circuit breaker open error.

                Args:
                    message: Error message.
                    recovery_time: When the circuit breaker will attempt reset.

                """
                super().__init__(message)
                self.recovery_time = recovery_time

        class EmptyResponseError(RetryableError):
            """Raised when MT5 returns empty response that should have data.

            This is a transient condition that should trigger retry.
            Used to distinguish between:
            - Valid None (e.g., symbol doesn't exist)
            - Transient failure (e.g., MT5 not ready, connection hiccup)

            """

            def __init__(self, operation: str, detail: str = "") -> None:
                """Initialize empty response error.

                Args:
                    operation: Name of the operation that returned empty.
                    detail: Additional context about the empty response.

                """
                msg = f"Empty response from {operation}"
                if detail:
                    msg += f": {detail}"
                # Use code -1 to indicate empty response (not a real MT5 error)
                super().__init__(code=-1, description=msg)
                self.operation = operation
                self.detail = detail

    # =========================================================================
    # DATA UTILITIES
    # =========================================================================

    class Data:
        """Unified data utilities - validation, wrapping, transformation, datetime."""

        class Wrapper:
            """Wrapper for MT5 data dict with attribute access."""

            __slots__ = ("_data",)
            _data: dict[str, object]

            def __init__(self, data: dict[str, object]) -> None:
                """Initialize wrapper with data dict.

                Args:
                    data: Dictionary to wrap for attribute access.

                """
                object.__setattr__(self, "_data", data)

            def __getattr__(self, name: str) -> object:
                """Get attribute from underlying dict.

                Args:
                    name: Attribute name to retrieve.

                Returns:
                    Value from the underlying dictionary.

                Raises:
                    AttributeError: If key not found in dict.

                """
                try:
                    return self._data[name]
                except KeyError:
                    msg = f"'{type(self).__name__}' has no attribute '{name}'"
                    raise AttributeError(msg) from None

            def __repr__(self) -> str:
                """Return string representation.

                Returns:
                    String representation of the wrapper.

                """
                return f"{type(self).__name__}({self._data})"

            def _asdict(self) -> dict[str, object]:
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
        def wrap(
            d: dict[str, object] | object,
        ) -> MT5Utilities.Data.Wrapper | object:
            """Convert dict to object with attribute access.

            Args:
                d: Dictionary or other object.

            Returns:
                Wrapper if dict, otherwise original object.

            """
            if isinstance(d, dict):
                return MT5Utilities.Data.Wrapper(d)
            return d

        @staticmethod
        def wrap_many(
            items: tuple[object, ...] | list[object] | None,
        ) -> tuple[object, ...] | None:
            """Convert tuple/list of dicts to tuple of objects.

            Args:
                items: Tuple or list of dictionaries.

            Returns:
                Tuple of wrapped objects or None.

            """
            if items is None:
                return None
            return tuple(MT5Utilities.Data.wrap(d) for d in items)

        @staticmethod
        def unwrap_chunks(
            result: dict[str, object] | None,
        ) -> tuple[object, ...] | None:
            """Reassemble chunked response from server into tuple of objects.

            Args:
                result: Chunked response dict or None.

            Returns:
                Tuple of wrapped objects or None.

            """
            if result is None:
                return None

            if isinstance(result, dict) and "chunks" in result:
                all_items: list[MT5Utilities.Data.Wrapper] = []
                chunks = result["chunks"]
                if isinstance(chunks, list):
                    for chunk in chunks:
                        if isinstance(chunk, list):
                            all_items.extend(
                                MT5Utilities.Data.Wrapper(d)
                                for d in chunk
                                if isinstance(d, dict)
                            )
                return tuple(all_items)

            if isinstance(result, tuple | list):
                return MT5Utilities.Data.wrap_many(list(result))

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

        @staticmethod
        def json_to_dict(json_data: str) -> dict[str, object] | None:
            """Convert JSON string from gRPC to dict.

            Used by both sync and async clients for gRPC responses.

            Args:
                json_data: JSON string to parse.

            Returns:
                Parsed dictionary or None if empty.

            """
            if not json_data:
                return None
            return orjson.loads(json_data)

        @staticmethod
        def unwrap_proto_list_to_dicts(
            json_items: list[str],
        ) -> list[dict[str, object]] | None:
            """Convert list of JSON strings from gRPC to list of dicts.

            Used by both sync and async clients for gRPC responses containing
            lists of JSON-serialized objects (positions, orders, history, etc).

            Args:
                json_items: List of JSON strings to parse.

            Returns:
                List of dictionaries or None if empty.

            """
            if not json_items:
                return None
            return [orjson.loads(item) for item in json_items if item]

        @staticmethod
        def unwrap_proto_list_to_tuple(
            json_items: list[str],
        ) -> tuple[dict[str, object], ...] | None:
            """Convert list of JSON strings from gRPC to tuple of dicts.

            Maintains compatibility with original MetaTrader5 API which
            returns tuples from methods like positions_get(), orders_get().

            Args:
                json_items: List of JSON strings to parse.

            Returns:
                Tuple of dictionaries or None if empty.

            """
            result = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if result is None:
                return None
            return tuple(result)

        @staticmethod
        def numpy_from_proto(
            proto: _NumpyArrayProto | None,
        ) -> NDArray[np.void] | None:
            """Convert NumpyArray proto to numpy array.

            Used by both sync and async clients to deserialize OHLCV and tick data
            from gRPC NumpyArray protobuf messages.

            Handles both simple dtypes ('float64') and structured array dtypes
            ("[('time', '<i8'), ('open', '<f8'), ...]").

            Args:
                proto: NumpyArray protobuf message with .data, .dtype, .shape
                 attributes.

            Returns:
                NumPy structured array or None if empty.

            """
            import ast

            if proto is None or not proto.data or not proto.dtype:
                return None

            # Parse dtype string to numpy dtype
            dtype_str = proto.dtype
            if dtype_str.startswith("["):
                # Structured array dtype - parse the list of tuples
                dtype_spec = ast.literal_eval(dtype_str)
                dtype = np.dtype(dtype_spec)
            else:
                # Simple dtype like 'float64', '<f8'
                dtype = np.dtype(dtype_str)

            arr: NDArray[np.void] = np.frombuffer(proto.data, dtype=dtype)
            if proto.shape:
                arr = arr.reshape(tuple(proto.shape))
            return arr

        @staticmethod
        def unwrap_symbols_chunks(
            response: _SymbolsResponseProto | None,
        ) -> list[dict[str, object]] | None:
            """Unwrap chunked symbols response from gRPC.

            Used by both sync and async clients to reassemble large symbol lists
            that are sent in chunks to avoid gRPC message size limits.

            Args:
                response: SymbolsResponse protobuf with .total and .chunks attributes.

            Returns:
                List of symbol dictionaries or None if empty.

            """
            if response is None or response.total == 0:
                return None
            result: list[dict[str, object]] = []
            for chunk in response.chunks:
                chunk_data: list[dict[str, object]] = orjson.loads(chunk)
                result.extend(chunk_data)
            return result

    # =========================================================================
    # INTROSPECTION UTILITIES
    # =========================================================================

    class Introspection:
        """Python introspection utilities for tuple subclasses."""

        @staticmethod
        def get_tuple_field_order(tuple_cls: type) -> list[str] | None:
            """Get field names in correct positional order from tuple subclass.

            Uses Python's built-in introspection - NO hardcoding.
            Tries multiple methods in order of reliability:
            1. __match_args__ (Python 3.10+ structseq types)
            2. _fields (standard namedtuples)
            3. Test instance mapping (universal for member_descriptor types)

            Args:
                tuple_cls: The tuple subclass to introspect.

            Returns:
                List of field names in positional order, or None if fails.

            """
            # Python 3.10+ structseq types have __match_args__
            if hasattr(tuple_cls, "__match_args__"):
                return list(tuple_cls.__match_args__)

            # Standard namedtuples have _fields
            if hasattr(tuple_cls, "_fields"):
                return list(tuple_cls._fields)

            # For types without either, create test instance and map indices
            member_fields = [
                name
                for name in dir(tuple_cls)
                if not name.startswith("_")
                and type(getattr(tuple_cls, name, None)).__name__
                == "member_descriptor"
            ]

            if not member_fields:
                return None

            # Create instance with sentinel values to determine positional order
            try:
                n = len(member_fields)
                instance = tuple_cls.__new__(tuple_cls, tuple(range(n)))

                # Map each field to its positional index
                field_to_index: dict[str, int] = {}
                for field_name in member_fields:
                    value = getattr(instance, field_name)
                    if isinstance(value, int) and 0 <= value < n:
                        field_to_index[field_name] = value

                # Sort by index to get positional order
                if len(field_to_index) == n:
                    return [
                        f
                        for f, _ in sorted(
                            field_to_index.items(), key=lambda x: x[1]
                        )
                    ]
            except (TypeError, ValueError, AttributeError):
                pass

            return None

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================

    class CircuitBreaker:
        """Circuit breaker for fault tolerance.

        Implements the circuit breaker pattern to prevent cascading failures.
        Uses MT5Config directly for configuration (no separate config class).

        States (from c.Resilience.CircuitBreakerState):
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
            self._state = c.Resilience.CircuitBreakerState.CLOSED
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
        def state(self) -> c.Resilience.CircuitBreakerState:
            """Get current circuit state, transitioning if needed."""
            with self._lock:
                if (
                    self._state == c.Resilience.CircuitBreakerState.OPEN
                    and self._should_attempt_reset()
                ):
                    log.info(
                        "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                        self.name,
                    )
                    self._state = c.Resilience.CircuitBreakerState.HALF_OPEN
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
            return self.state == c.Resilience.CircuitBreakerState.CLOSED

        @property
        def is_open(self) -> bool:
            """Check if circuit is open (blocking requests)."""
            return self.state == c.Resilience.CircuitBreakerState.OPEN

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
                if self._state == c.Resilience.CircuitBreakerState.HALF_OPEN:
                    log.info(
                        "Circuit breaker '%s' recovered: HALF_OPEN -> CLOSED",
                        self.name,
                    )
                    self._state = c.Resilience.CircuitBreakerState.CLOSED

        def record_failure(self) -> None:
            """Record a failed operation."""
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.now(UTC)

                if self._state == c.Resilience.CircuitBreakerState.HALF_OPEN:
                    log.warning(
                        "Circuit breaker '%s' failed during recovery",
                        self.name,
                    )
                    self._state = c.Resilience.CircuitBreakerState.OPEN
                elif self._failure_count >= self._config.cb_threshold:
                    log.warning(
                        "Circuit breaker '%s' opened after %d failures",
                        self.name,
                        self._failure_count,
                    )
                    self._state = c.Resilience.CircuitBreakerState.OPEN

        def can_execute(self) -> bool:
            """Check if a request is allowed through the circuit.

            CRITICAL FIX: Entire operation is now under lock to prevent race
            conditions where state could change between read and decision.
            Previously, reset() could be called between state read and action.
            """
            with self._lock:
                # Inline state check (don't call property which also locks)
                if (
                    self._state == c.Resilience.CircuitBreakerState.OPEN
                    and self._should_attempt_reset()
                ):
                    log.info(
                        "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                        self.name,
                    )
                    self._state = c.Resilience.CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0

                current_state = self._state

                if current_state == c.Resilience.CircuitBreakerState.CLOSED:
                    return True

                if current_state == c.Resilience.CircuitBreakerState.HALF_OPEN:
                    if self._half_open_calls < self._config.cb_half_open_max:
                        self._half_open_calls += 1
                        return True
                    return False

                return False  # OPEN state

        def reset(self) -> None:
            """Manually reset the circuit breaker to closed state."""
            with self._lock:
                log.info("Circuit breaker '%s' manually reset", self.name)
                self._state = c.Resilience.CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._last_failure_time = None
                self._half_open_calls = 0

        def get_status(self) -> dict[str, str | int]:
            """Get circuit breaker status for monitoring.

            Returns:
                Dictionary with circuit breaker state information.

            """
            with self._lock:
                status: dict[str, str | int] = {
                    "name": self.name,
                    "state": self._state.name,
                    "failure_count": self._failure_count,
                    "success_count": self._success_count,
                    "failure_threshold": self._config.cb_threshold,
                }

                if self._last_failure_time:
                    status["last_failure"] = self._last_failure_time.isoformat()
                    if self._state == c.Resilience.CircuitBreakerState.OPEN:
                        recovery_at = self._last_failure_time + timedelta(
                            seconds=self._config.cb_recovery
                        )
                        status["recovery_at"] = recovery_at.isoformat()

                return status

        # -----------------------------------------------------------------
        # Retry helpers (part of CircuitBreaker resilience pattern)
        # -----------------------------------------------------------------

        @staticmethod
        def is_retryable_grpc_code(code: int) -> bool:
            """Check if gRPC status code is retryable.

            Args:
                code: gRPC status code (integer value).

            Returns:
                True if the code indicates a transient error.

            """
            retryable_codes = {
                c.Resilience.GrpcRetryableCode.UNAVAILABLE,
                c.Resilience.GrpcRetryableCode.DEADLINE_EXCEEDED,
                c.Resilience.GrpcRetryableCode.ABORTED,
                c.Resilience.GrpcRetryableCode.RESOURCE_EXHAUSTED,
            }
            return code in retryable_codes

        @staticmethod
        def is_retryable_exception(error: Exception) -> bool:
            """Check if exception should trigger retry.

            Args:
                error: Exception to check.

            Returns:
                True if exception is retryable.

            """
            # Check for gRPC errors (duck typing to avoid import)
            if hasattr(error, "code") and callable(error.code):
                code = error.code()
                # grpc.StatusCode is an enum, get its value
                code_value = code.value[0] if hasattr(code, "value") else int(code)
                return MT5Utilities.CircuitBreaker.is_retryable_grpc_code(code_value)

            # MT5 retryable errors (includes EmptyResponseError)
            if isinstance(error, MT5Utilities.Exceptions.RetryableError):
                return True

            # Connection/timeout errors are retryable, EXCEPT "not established"
            # which means client was never connected (programming error, not transient)
            if isinstance(error, ConnectionError):
                msg = str(error).lower()
                # Client never connected is not retryable; connection lost is retryable
                return "not established" not in msg and "call connect" not in msg

            return isinstance(error, (TimeoutError, OSError))

        # -----------------------------------------------------------------
        # MT5 Retcode Classification (transaction error handling)
        # -----------------------------------------------------------------

        @staticmethod
        def classify_mt5_retcode(  # noqa: PLR0911
            retcode: int,
        ) -> c.Resilience.ErrorClassification:
            """Classify MT5 retcode into error category.

            Used to determine how each error should be handled:
            - SUCCESS: Operation completed successfully
            - PARTIAL: Partially completed (may need follow-up)
            - RETRYABLE: Transient error, safe to retry (order NOT executed)
            - VERIFY_REQUIRED: MUST verify state before retry (order MAY executed)
            - CONDITIONAL: May be retryable depending on context
            - PERMANENT: Permanent error, do not retry
            - UNKNOWN: Unknown error code

            Args:
                retcode: MT5 TradeRetcode value.

            Returns:
                ErrorClassification indicating how to handle this code.

            """
            if retcode in c.Resilience.MT5_SUCCESS_CODES:
                return c.Resilience.ErrorClassification.SUCCESS
            if retcode in c.Resilience.MT5_PARTIAL_CODES:
                return c.Resilience.ErrorClassification.PARTIAL
            if retcode in c.Resilience.MT5_VERIFY_REQUIRED_CODES:
                return c.Resilience.ErrorClassification.VERIFY_REQUIRED
            if retcode in c.Resilience.MT5_RETRYABLE_CODES:
                return c.Resilience.ErrorClassification.RETRYABLE
            if retcode in c.Resilience.MT5_CONDITIONAL_CODES:
                return c.Resilience.ErrorClassification.CONDITIONAL
            if retcode in c.Resilience.MT5_PERMANENT_CODES:
                return c.Resilience.ErrorClassification.PERMANENT
            return c.Resilience.ErrorClassification.UNKNOWN

        @staticmethod
        def is_retryable_mt5_code(retcode: int) -> bool:
            """Check if MT5 TradeRetcode is retryable.

            Args:
                retcode: MT5 TradeRetcode value.

            Returns:
                True if the code indicates a transient error.

            """
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(retcode)
            return classification == c.Resilience.ErrorClassification.RETRYABLE

        @staticmethod
        def is_permanent_mt5_code(retcode: int) -> bool:
            """Check if MT5 TradeRetcode is permanent.

            Args:
                retcode: MT5 TradeRetcode value.

            Returns:
                True if the code indicates a permanent error.

            """
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(retcode)
            return classification == c.Resilience.ErrorClassification.PERMANENT

        @staticmethod
        def get_operation_criticality(
            operation: str,
        ) -> c.Resilience.OperationCriticality:
            """Get criticality level for an operation.

            Used to determine retry strategy and state verification:
            - CRITICAL: More retries, state verification on ambiguous errors
            - HIGH/NORMAL/LOW: Standard retry behavior

            Args:
                operation: Operation name (e.g., "order_send").

            Returns:
                OperationCriticality level (defaults to NORMAL if unknown).

            """
            criticality_value = c.Resilience.OPERATION_CRITICALITY.get(
                operation,
                c.Resilience.OperationCriticality.NORMAL,
            )
            return c.Resilience.OperationCriticality(criticality_value)

        @staticmethod
        def should_verify_state(
            operation: str,
            classification: c.Resilience.ErrorClassification,
        ) -> bool:
            """Determine if state verification is needed after error.

            For CRITICAL operations with ambiguous errors (CONDITIONAL, UNKNOWN),
            we need to verify the actual state before reporting to caller.

            Args:
                operation: Operation name.
                classification: Error classification from classify_mt5_retcode().

            Returns:
                True if state verification is recommended.

            """
            criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
                operation
            )
            if criticality != c.Resilience.OperationCriticality.CRITICAL:
                return False

            # For critical ops, verify state on ambiguous errors
            return classification in {
                c.Resilience.ErrorClassification.CONDITIONAL,
                c.Resilience.ErrorClassification.UNKNOWN,
                c.Resilience.ErrorClassification.VERIFY_REQUIRED,
            }

        @staticmethod
        async def async_retry_with_backoff(
            coro_factory: Callable[[], Awaitable[T]],
            config: MT5Config,
            operation_name: str = "operation",
            *,
            should_retry: Callable[[Exception], bool] | None = None,
            on_success: Callable[[], None] | None = None,
            on_failure: Callable[[Exception], None] | None = None,
            before_retry: Callable[[], Awaitable[None]] | None = None,
            max_attempts_override: int | None = None,
        ) -> T:
            """Execute async operation with exponential backoff retry.

            Part of CircuitBreaker since retry is a resilience pattern.
            Uses MT5Config values for retry parameters.

            This is the SINGLE implementation of retry logic used by both
            generic operations and MT5-specific operations (via hooks).

            Args:
                coro_factory: Callable that returns an awaitable (not a coroutine).
                config: MT5Config with retry_* settings.
                operation_name: Name for logging purposes.
                should_retry: Optional predicate to decide if exception is retryable.
                    If None, all exceptions are retryable. If returns False,
                    exception is raised immediately without retry.
                on_success: Optional callback invoked on successful execution.
                    Used by circuit breaker to record success.
                on_failure: Optional callback invoked when non-retryable exception
                    occurs or all retries exhausted. Used by circuit breaker.
                before_retry: Optional async callback invoked before each retry.
                    Used for reconnection attempts.
                max_attempts_override: Override config.retry_max_attempts.
                    Used by _resilient_call for different attempt counts.

            Returns:
                Result of successful operation.

            Raises:
                MT5Utilities.Exceptions.MaxRetriesError: If all retries fail.
                Exception: Non-retryable exceptions propagate immediately.

            Example:
                >>> # Simple retry (all exceptions retryable)
                >>> async def fetch():
                ...     return await client.get_data()
                >>> result = await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                ...     fetch, config, "get_data"
                ... )

                >>> # With circuit breaker hooks
                >>> result = await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                ...     fetch, config, "get_data",
                ...     should_retry=is_retryable_exception,
                ...     on_success=cb.record_success,
                ...     on_failure=cb.record_failure,
                ... )

            """
            last_exception: Exception | None = None
            max_attempts = max_attempts_override or config.retry_max_attempts

            for attempt in range(max_attempts):
                try:
                    result = await coro_factory()
                except Exception as e:
                    last_exception = e

                    # Check if retryable (default: all exceptions are retryable)
                    if should_retry is not None and not should_retry(e):
                        # Non-retryable: record failure and propagate
                        if on_failure:
                            on_failure(e)
                        raise

                    # Check if more attempts available
                    if attempt < max_attempts - 1:
                        # Calculate backoff delay using config
                        delay = config.calculate_retry_delay(attempt)

                        log.warning(
                            "Operation '%s' attempt %d/%d failed: %s. Retrying in %.2fs",
                            operation_name,
                            attempt + 1,
                            max_attempts,
                            e,
                            delay,
                        )

                        await asyncio.sleep(delay)

                        # Before retry callback (e.g., reconnection)
                        # CRITICAL FIX: Handle exceptions in before_retry gracefully
                        # to prevent infinite hangs when reconnection fails
                        if before_retry:
                            try:
                                await before_retry()
                            except Exception as before_retry_error:  # noqa: BLE001
                                # Log but don't raise - let the main retry continue
                                log.warning(
                                    "before_retry callback failed: %s",
                                    before_retry_error,
                                )
                    else:
                        # Last attempt failed
                        if on_failure:
                            on_failure(e)
                        log.exception(
                            "Operation '%s' failed after %d attempts",
                            operation_name,
                            max_attempts,
                        )
                        raise MT5Utilities.Exceptions.MaxRetriesError(
                            operation_name,
                            max_attempts,
                            last_exception,
                        ) from e
                else:
                    # Success - invoke callback and return
                    if on_success:
                        on_success()
                    return result

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise MT5Utilities.Exceptions.MaxRetriesError(
                    operation_name,
                    max_attempts,
                    last_exception,
                )
            msg = f"Retry failed for '{operation_name}' with no exception recorded"
            raise RuntimeError(msg)

        @staticmethod
        async def async_reconnect_with_backoff(
            connect_factory: Callable[[], Awaitable[bool]],
            config: MT5Config,
            name: str = "reconnect",
        ) -> bool:
            """Attempt reconnection with exponential backoff and jitter.

            Part of CircuitBreaker since reconnection is a resilience pattern.
            Uses MT5Config values for retry parameters.

            Args:
                connect_factory: Callable that returns awaitable bool (True=success).
                config: MT5Config with retry_* settings.
                name: Name for logging purposes.

            Returns:
                True if reconnection successful, False otherwise.

            """
            delay = config.retry_initial_delay

            for attempt in range(config.retry_max_attempts):
                try:
                    log.info(
                        "Reconnection '%s' attempt %d/%d",
                        name,
                        attempt + 1,
                        config.retry_max_attempts,
                    )

                    success = await connect_factory()
                    if success:
                        log.info(
                            "Reconnection '%s' successful after %d attempts",
                            name,
                            attempt + 1,
                        )
                        return True

                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "Reconnection '%s' attempt %d/%d failed: %s",
                        name,
                        attempt + 1,
                        config.retry_max_attempts,
                        e,
                    )

                # Exponential backoff with jitter
                if config.retry_jitter:
                    # S311: random is fine for jitter - not cryptographic
                    jitter = random.uniform(0, delay * 0.1)  # noqa: S311
                    wait_time = delay + jitter
                else:
                    wait_time = delay

                await asyncio.sleep(wait_time)
                delay = min(
                    delay * config.retry_exponential_base,
                    config.retry_max_delay,
                )

            log.error(
                "Reconnection '%s' failed after %d attempts",
                name,
                config.retry_max_attempts,
            )
            return False

    # =========================================================================
    # TRANSACTION HANDLER (order_send orchestration)
    # =========================================================================

    class TransactionHandler:
        """Handler for critical transaction orchestration.

        Centralizes transaction logic used by _safe_order_send:
        - Request preparation with idempotency markers
        - Result classification and outcome determination
        - Retry decision logic

        All methods are static - no state stored.

        Contains RequestTracker as nested class for idempotency tracking.
        """

        class RequestTracker:
            """Track order requests to prevent double execution.

            Uses comment field as idempotency marker since MT5 doesn't have
            native support for request deduplication. Each order_send gets
            a unique request_id embedded in the comment field.

            MT5 Limitations:
            - No native idempotency (each request creates new order)
            - Comment field is 31 chars max
            - No "order already exists" detection

            Format: RQ<10chars>|<original_comment>
            Example: RQ1a2b3c4d5e|my_strategy_order

            Nested inside TransactionHandler since it's only used
            for transaction idempotency tracking.
            """

            @staticmethod
            def generate_request_id() -> str:
                """Generate unique request ID for idempotency.

                Format: RQ + 10 hex chars = 12 chars total.
                Fits comfortably in MT5 comment field (31 chars max).

                Returns:
                    12-character request ID starting with 'RQ'.

                """
                import uuid

                return f"RQ{uuid.uuid4().hex[:10]}"

            @staticmethod
            def mark_comment(comment: str | None, request_id: str) -> str:
                """Add request_id marker to comment field.

                Embeds request_id at the start of comment for later extraction.
                Preserves as much of original comment as possible.

                Args:
                    comment: Original comment (may be None or empty).
                    request_id: Request ID to embed (12 chars).

                Returns:
                    Marked comment: 'RQ<10chars>|<original>' or just 'RQ<10chars>'.

                """
                if comment:
                    # Leave room for request_id + separator + some original
                    max_original = 31 - len(request_id) - 1
                    return f"{request_id}|{comment[:max_original]}"
                return request_id

            # Expected request_id length: RQ + 10 hex chars = 12 chars
            REQUEST_ID_LENGTH = 12
            REQUEST_ID_PREFIX = "RQ"
            REQUEST_ID_HEX_LENGTH = 10

            @staticmethod
            def extract_request_id(comment: str | None) -> str | None:
                """Extract request_id from marked comment field.

                CRITICAL FIX: Added validation to prevent false matches:
                - Length must be exactly 12 chars (RQ + 10 hex)
                - Must start with "RQ"
                - Remaining 10 chars must be valid hex
                This prevents matching corrupted/concatenated comments.

                Args:
                    comment: Comment field from order/deal.

                Returns:
                    Request ID if found and valid, None otherwise.

                """
                tracker = MT5Utilities.TransactionHandler.RequestTracker
                if not comment or not comment.startswith(tracker.REQUEST_ID_PREFIX):
                    return None

                # Extract candidate (before separator if present)
                candidate = comment.split("|")[0]

                # Validate length
                if len(candidate) != tracker.REQUEST_ID_LENGTH:
                    log.debug(
                        "Invalid request_id length: %d (expected %d)",
                        len(candidate),
                        tracker.REQUEST_ID_LENGTH,
                    )
                    return None

                # Validate hex portion (chars 2-12 should be hex)
                hex_part = candidate[len(tracker.REQUEST_ID_PREFIX) :]
                try:
                    int(hex_part, 16)  # Validate hex
                except ValueError:
                    log.debug(
                        "Invalid request_id hex portion: %s",
                        hex_part,
                    )
                    return None

                return candidate

        @staticmethod
        def prepare_request(
            request: dict[str, object],
            operation: str,
        ) -> tuple[dict[str, object], str]:
            """Prepare request with idempotency marker.

            Adds request_id to comment field for tracking and verification.

            Args:
                request: Order request dictionary.
                operation: Operation name for logging.

            Returns:
                Tuple of (modified_request, request_id).

            """
            tracker = MT5Utilities.TransactionHandler.RequestTracker
            request_id = tracker.generate_request_id()
            original_comment = request.get("comment", "") or ""
            request["comment"] = tracker.mark_comment(
                str(original_comment), request_id
            )
            log.debug(
                "TX_PREPARE: %s request_id=%s",
                operation,
                request_id,
            )
            return request, request_id

        @staticmethod
        def classify_result(
            retcode: int,
        ) -> c.Resilience.TransactionOutcome:
            """Classify result retcode into transaction outcome (PUBLIC API).

            This is the BRIDGE function between:
            - ErrorClassification (7 values, internal, detailed)
            - TransactionOutcome (5 values, public, simplified)

            Mapping:
                SUCCESS → SUCCESS
                PARTIAL → PARTIAL
                RETRYABLE → RETRY
                VERIFY_REQUIRED → VERIFY_REQUIRED
                PERMANENT → PERMANENT_FAILURE
                CONDITIONAL → VERIFY_REQUIRED (conservative, verify state)
                UNKNOWN → VERIFY_REQUIRED (conservative, verify state)

            Why CONDITIONAL/UNKNOWN → VERIFY_REQUIRED (not PERMANENT_FAILURE)?
            - These represent ambiguous states where order MAY have executed
            - Conservative approach: verify state before deciding
            - Prevents both: double execution (retry when executed) AND
              missed execution (fail when actually succeeded)

            Args:
                retcode: MT5 TradeRetcode value.

            Returns:
                TransactionOutcome indicating next action for caller.

            Example:
                >>> outcome = TransactionHandler.classify_result(10012)  # TIMEOUT
                >>> outcome == TransactionOutcome.VERIFY_REQUIRED
                True

            """
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(retcode)

            if classification == c.Resilience.ErrorClassification.SUCCESS:
                return c.Resilience.TransactionOutcome.SUCCESS
            if classification == c.Resilience.ErrorClassification.PARTIAL:
                return c.Resilience.TransactionOutcome.PARTIAL
            if classification == c.Resilience.ErrorClassification.RETRYABLE:
                return c.Resilience.TransactionOutcome.RETRY
            if classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED:
                return c.Resilience.TransactionOutcome.VERIFY_REQUIRED
            if classification == c.Resilience.ErrorClassification.PERMANENT:
                return c.Resilience.TransactionOutcome.PERMANENT_FAILURE
            # CONDITIONAL and UNKNOWN - verify state (conservative approach)
            return c.Resilience.TransactionOutcome.VERIFY_REQUIRED

        @staticmethod
        def should_retry(
            outcome: c.Resilience.TransactionOutcome,
            attempt: int,
            max_attempts: int,
        ) -> bool:
            """Determine if transaction should be retried.

            Args:
                outcome: Current transaction outcome.
                attempt: Current attempt number (0-based).
                max_attempts: Maximum attempts allowed.

            Returns:
                True if retry is allowed.

            """
            if attempt >= max_attempts - 1:
                return False
            return outcome == c.Resilience.TransactionOutcome.RETRY

        @staticmethod
        def get_retry_config(
            config: MT5Config,
            operation: str,
        ) -> tuple[int, bool]:
            """Get retry configuration for operation.

            Args:
                config: MT5Config instance.
                operation: Operation name.

            Returns:
                Tuple of (max_attempts, is_critical).

            """
            criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
                operation
            )
            is_critical = (
                criticality == c.Resilience.OperationCriticality.CRITICAL
            )
            max_attempts = (
                config.critical_retry_max_attempts
                if is_critical
                else config.retry_max_attempts
            )
            return max_attempts, is_critical

        @staticmethod
        def handle_success(
            cb: object,
            result: object,
            outcome: c.Resilience.TransactionOutcome,
        ) -> None:
            """Record success in circuit breaker and log if partial.

            Args:
                cb: CircuitBreaker instance.
                result: Order result for logging.
                outcome: Transaction outcome (SUCCESS or PARTIAL).

            """
            cb.record_success()
            if outcome == c.Resilience.TransactionOutcome.PARTIAL:
                log.warning("Order partially filled: %s", result)

        @staticmethod
        def raise_permanent(retcode: int, comment: str | None) -> NoReturn:
            """Raise PermanentError for non-retryable errors.

            Args:
                retcode: MT5 retcode that caused the error.
                comment: Error description.

            Raises:
                PermanentError: Always raised.

            """
            raise MT5Utilities.Exceptions.PermanentError(
                retcode, comment or f"Permanent error: {retcode}"
            )

        @staticmethod
        def raise_exhausted(
            operation: str,
            max_attempts: int,
            last_result: object | None,
            last_error: Exception | None,
        ) -> NoReturn:
            """Raise appropriate error after all retries exhausted.

            Args:
                operation: Operation name for error message.
                max_attempts: Number of attempts made.
                last_result: Last result received (if any).
                last_error: Last exception (if any).

            Raises:
                PermanentError: If we have a result with retcode.
                MaxRetriesError: Otherwise.

            """
            if last_result and hasattr(last_result, "retcode") and last_result.retcode:
                raise MT5Utilities.Exceptions.PermanentError(
                    last_result.retcode,
                    f"Max retries exceeded. Last retcode: {last_result.retcode}",
                )
            raise MT5Utilities.Exceptions.MaxRetriesError(
                operation, max_attempts, last_error
            )

