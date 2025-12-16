"""MetaTrader5 client - modern RPyC bridge with resilience.

Modern RPyC client for connecting to MT5Service:
- Uses rpyc.connect() instead of deprecated rpyc.classic.connect()
- Direct method calls via conn.root.exposed_*
- Production-grade error handling with retry and circuit breaker
- numpy array handling via rpyc.utils.classic.obtain()

Resilience features:
- Automatic retry with exponential backoff on transient failures
- Circuit breaker to prevent cascading failures
- Connection health monitoring with auto-reconnect
- Per-operation timeouts

Compatible with rpyc 6.x and Python 3.12+.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from functools import cache
from typing import TYPE_CHECKING, Any, Self

import rpyc
import rpyc.core.channel
import rpyc.core.stream
from rpyc.utils.classic import obtain

# =============================================================================
# RPyC Performance Optimization for Large Data Transfers
# =============================================================================
RPYC_MAX_IO_CHUNK = 65355 * 10  # ~650KB chunks
RPYC_COMPRESSION_LEVEL = 0  # Disable compression for speed

log = logging.getLogger(__name__)

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"

if TYPE_CHECKING:
    from types import TracebackType

    from mt5linux.types import MT5Types

    RatesArray = MT5Types.RatesArray
    TicksArray = MT5Types.TicksArray


# =============================================================================
# Retryable Exceptions (module level for sharing)
# =============================================================================

RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    EOFError,
    ConnectionError,
    BrokenPipeError,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
    OSError,
)


# =============================================================================
# Shared Utilities
# =============================================================================


@cache
def _calculate_retry_delay(
    attempt: int,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
) -> float:
    """Calculate exponential backoff delay."""
    delay = min(initial_delay * (exponential_base**attempt), max_delay)
    delay *= 0.5 + random.random()  # noqa: S311
    return delay


def _to_timestamp(dt: datetime | int | None) -> int | None:
    """Convert datetime to Unix timestamp for MT5 API."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    return dt


# =============================================================================
# Type Validation Helpers
# =============================================================================

_VERSION_TUPLE_LEN = 3
_ERROR_TUPLE_LEN = 2


def _validate_version(value: object) -> tuple[int, int, str] | None:
    """Validate and convert Any to version tuple."""
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != _VERSION_TUPLE_LEN:
        msg = f"Expected tuple[int, int, str] | None, got {type(value).__name__}"
        raise TypeError(msg)
    try:
        return (int(value[0]), int(value[1]), str(value[2]))
    except (ValueError, IndexError, TypeError) as e:
        msg = f"Invalid version tuple: {e}"
        raise TypeError(msg) from e


def _validate_last_error(value: object) -> tuple[int, str]:
    """Validate and convert Any to last_error tuple."""
    if not isinstance(value, tuple) or len(value) != _ERROR_TUPLE_LEN:
        msg = f"Expected tuple[int, str], got {type(value).__name__}"
        raise TypeError(msg)
    try:
        return (int(value[0]), str(value[1]))
    except (ValueError, IndexError, TypeError) as e:
        msg = f"Invalid error tuple: {e}"
        raise TypeError(msg) from e


def _validate_float_optional(value: object) -> float | None:
    """Validate and convert Any to float | None."""
    if value is None:
        return None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    msg = f"Expected float | None, got {type(value).__name__}"
    raise TypeError(msg)


def _validate_int_optional(value: object) -> int | None:
    """Validate and convert Any to int | None."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"Expected int | None, got {type(value).__name__}"
    raise TypeError(msg)


# =============================================================================
# Dict-to-Object Wrappers for MT5 Data
# =============================================================================


class _MT5Object:
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


def _wrap_dict(d: dict[str, Any] | Any) -> _MT5Object | Any:
    """Convert dict to object with attribute access."""
    if isinstance(d, dict):
        return _MT5Object(d)
    return d


def _wrap_dicts(items: tuple | list | None) -> tuple | None:
    """Convert tuple/list of dicts to tuple of objects."""
    if items is None:
        return None
    return tuple(_wrap_dict(d) for d in items)


def _unwrap_chunks(result: dict[str, Any] | None) -> tuple | None:
    """Reassemble chunked response from server into tuple of objects."""
    if result is None:
        return None

    if isinstance(result, dict) and "chunks" in result:
        all_items: list[_MT5Object] = []
        for chunk in result["chunks"]:
            all_items.extend(_MT5Object(d) for d in chunk)
        return tuple(all_items)

    if isinstance(result, tuple | list):
        return _wrap_dicts(result)

    return None


# =============================================================================
# MetaTrader5 Client with Nested Classes
# =============================================================================


class MetaTrader5:
    """Modern RPyC client for MetaTrader5.

    Connects to MT5Service (modern rpyc.Service) via rpyc.connect().
    Delegates MT5 operations to exposed service methods.

    Example:
        >>> with MetaTrader5(host="localhost", port=18812) as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     print(account.balance)
    """

    # =========================================================================
    # NESTED EXCEPTIONS
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
    # NESTED CIRCUIT BREAKER
    # =========================================================================

    class CircuitBreaker:
        """Circuit breaker for fault tolerance."""

        class State(IntEnum):
            """Circuit breaker state."""

            CLOSED = 0  # Normal operation
            OPEN = 1  # Failing - requests blocked
            HALF_OPEN = 2  # Testing recovery

        @dataclass
        class Config:
            """Circuit breaker configuration."""

            failure_threshold: int = 5
            recovery_timeout: float = 60.0
            half_open_max_calls: int = 1

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
            config: MetaTrader5.CircuitBreaker.Config | None = None,
            name: str = "default",
        ) -> None:
            """Initialize circuit breaker."""
            self._config = config or MetaTrader5.CircuitBreaker.Config()
            self.name = name
            self._state = MetaTrader5.CircuitBreaker.State.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time: datetime | None = None
            self._half_open_calls = 0
            self._lock = threading.RLock()

        @property
        def state(self) -> MetaTrader5.CircuitBreaker.State:
            """Get current circuit state, transitioning if needed."""
            with self._lock:
                if (
                    self._state == MetaTrader5.CircuitBreaker.State.OPEN
                    and self._should_attempt_reset()
                ):
                    log.info(
                        "Circuit breaker '%s' transitioning OPEN -> HALF_OPEN",
                        self.name,
                    )
                    self._state = MetaTrader5.CircuitBreaker.State.HALF_OPEN
                    self._half_open_calls = 0
                return self._state

        @property
        def failure_count(self) -> int:
            """Get current failure count."""
            with self._lock:
                return self._failure_count

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
                if self._state == MetaTrader5.CircuitBreaker.State.HALF_OPEN:
                    log.info(
                        "Circuit breaker '%s' recovered: HALF_OPEN -> CLOSED",
                        self.name,
                    )
                    self._state = MetaTrader5.CircuitBreaker.State.CLOSED

        def record_failure(self) -> None:
            """Record a failed operation."""
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.now(UTC)

                if self._state == MetaTrader5.CircuitBreaker.State.HALF_OPEN:
                    log.warning(
                        "Circuit breaker '%s' failed during recovery: HALF_OPEN -> OPEN",
                        self.name,
                    )
                    self._state = MetaTrader5.CircuitBreaker.State.OPEN
                elif self._failure_count >= self._config.failure_threshold:
                    log.warning(
                        "Circuit breaker '%s' opened after %d failures",
                        self.name,
                        self._failure_count,
                    )
                    self._state = MetaTrader5.CircuitBreaker.State.OPEN

        def can_execute(self) -> bool:
            """Check if a request is allowed through the circuit."""
            current_state = self.state

            if current_state == MetaTrader5.CircuitBreaker.State.CLOSED:
                return True

            if current_state == MetaTrader5.CircuitBreaker.State.HALF_OPEN:
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
                self._state = MetaTrader5.CircuitBreaker.State.CLOSED
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
                    if self._state == MetaTrader5.CircuitBreaker.State.OPEN:
                        recovery_at = self._last_failure_time + timedelta(
                            seconds=self._config.recovery_timeout
                        )
                        status["recovery_at"] = recovery_at.isoformat()

                return status

    # =========================================================================
    # NESTED RETRY CONFIG
    # =========================================================================

    @dataclass
    class RetryConfig:
        """Retry behavior configuration."""

        max_attempts: int = 3
        initial_delay: float = 0.5
        max_delay: float = 10.0
        exponential_base: float = 2.0
        jitter: bool = True
        retry_on_none: bool = True

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    DEFAULT_HEALTH_CHECK_INTERVAL: int = 30

    # =========================================================================
    # INSTANCE ATTRIBUTES
    # =========================================================================

    _conn: rpyc.Connection | None
    _mt5: Any

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
        *,
        circuit_breaker_config: CircuitBreaker.Config | None = None,
        retry_config: RetryConfig | None = None,
        health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
        max_reconnect_attempts: int = 3,
    ) -> None:
        """Connect to rpyc server.

        Args:
            host: rpyc server address.
            port: rpyc server port.
            timeout: Timeout in seconds for operations.
            circuit_breaker_config: Circuit breaker configuration.
            retry_config: Retry behavior configuration.
            health_check_interval: Seconds between connection health checks.
            max_reconnect_attempts: Max attempts for reconnection.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._conn = None
        self._mt5 = None
        self._service_root: Any = None

        # Resilience configuration
        cb_config = circuit_breaker_config or MetaTrader5.CircuitBreaker.Config()
        self._circuit_breaker = MetaTrader5.CircuitBreaker(
            config=cb_config,
            name=f"mt5-{host}:{port}",
        )
        self._retry_config = retry_config or MetaTrader5.RetryConfig()
        self._health_check_interval = health_check_interval
        self._last_health_check: datetime | None = None
        self._max_reconnect_attempts = max_reconnect_attempts

        self.connect()

    def connect(self) -> None:
        """Establish connection to rpyc server using modern API."""
        if self._conn is not None:
            return

        self._conn = rpyc.connect(
            self._host,
            self._port,
            config={
                "sync_request_timeout": self._timeout,
                "allow_public_attrs": True,
                "allow_pickle": True,
                "max_io_chunk": RPYC_MAX_IO_CHUNK,
                "compression_level": RPYC_COMPRESSION_LEVEL,
            },
        )
        if self._conn is None:
            msg = "Failed to establish RPyC connection"
            raise RuntimeError(msg)
        self._service_root = self._conn.root
        self._mt5 = self._service_root.get_mt5()

    def __getattr__(self, name: str) -> Any:
        """Transparent proxy for any MT5 attribute."""
        if self._mt5 is None:
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)
        return getattr(self._mt5, name)

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - cleanup."""
        try:
            self.shutdown()
        except (OSError, ConnectionError, EOFError):
            log.debug("MT5 shutdown failed during cleanup (connection may be closed)")
        self.close()

    def close(self) -> None:
        """Close rpyc connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except (OSError, ConnectionError, EOFError):
                log.debug("RPyC connection close failed (may already be closed)")
            self._conn = None
            self._mt5 = None
            self._service_root = None

    # =========================================================================
    # Resilience Methods
    # =========================================================================

    def _reconnect(self) -> None:
        """Reconnect to RPyC server with retry logic."""
        log.info("Attempting reconnection to %s:%d", self._host, self._port)
        self.close()

        last_error: Exception | None = None
        for attempt in range(self._max_reconnect_attempts):
            try:
                self.connect()
            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self._max_reconnect_attempts - 1:
                    delay = _calculate_retry_delay(attempt)
                    log.warning(
                        "Reconnection attempt %d failed: %s, retrying in %.2fs",
                        attempt + 1,
                        e,
                        delay,
                    )
                    time.sleep(delay)
            else:
                log.info("Reconnection successful on attempt %d", attempt + 1)
                return

        msg = f"Reconnection failed after {self._max_reconnect_attempts} attempts"
        log.error(msg)
        if last_error:
            raise ConnectionError(msg) from last_error
        raise ConnectionError(msg)

    def _check_connection_health(self) -> bool:
        """Verify connection is alive with lightweight ping."""
        if self._conn is None:
            return False
        try:
            if getattr(self._conn, "closed", False):
                return False
            _ = self._service_root
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    def _ensure_healthy_connection(self) -> None:
        """Ensure connection is healthy, reconnect if needed."""
        if not self._circuit_breaker.can_execute():
            raise MetaTrader5.CircuitBreaker.OpenError

        now = datetime.now(UTC)
        if (
            self._last_health_check
            and (now - self._last_health_check).total_seconds()
            < self._health_check_interval
        ):
            return

        if not self._check_connection_health():
            log.warning("Connection unhealthy, attempting reconnect")
            try:
                self._reconnect()
            except Exception:
                self._circuit_breaker.record_failure()
                raise

        self._last_health_check = now

    def _execute_operation(self, operation_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute MT5 operation via RPyC."""
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        method = getattr(self._service_root, operation_name)
        return method(*args, **kwargs)

    def _safe_rpc_call(
        self,
        method_name: str,
        *args: Any,
        retry_on_none: bool | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute RPC call with full error handling and automatic retry."""
        self._ensure_healthy_connection()

        if retry_on_none is None:
            retry_on_none = self._retry_config.retry_on_none

        last_exception: Exception | None = None
        max_attempts = self._retry_config.max_attempts

        for attempt in range(max_attempts):
            try:
                result = self._execute_operation(method_name, *args, **kwargs)

                # Handle None results
                if retry_on_none and result is None:
                    if attempt < max_attempts - 1:
                        delay = _calculate_retry_delay(attempt)
                        log.warning(
                            "%s returned None (attempt %d/%d), retrying in %.2fs",
                            method_name,
                            attempt + 1,
                            max_attempts,
                            delay,
                        )
                        time.sleep(delay)
                        continue

                # Success
                self._circuit_breaker.record_success()
                if attempt > 0:
                    log.info("%s succeeded on attempt %d", method_name, attempt + 1)
                return result

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                self._circuit_breaker.record_failure()
                if attempt < max_attempts - 1:
                    delay = _calculate_retry_delay(attempt)
                    log.warning(
                        "%s failed (attempt %d/%d): %s, retrying in %.2fs",
                        method_name,
                        attempt + 1,
                        max_attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    log.exception("%s failed after %d attempts", method_name, max_attempts)
                    raise

        if last_exception:
            raise MetaTrader5.MaxRetriesError(
                operation=method_name,
                attempts=max_attempts,
                last_error=last_exception,
            ) from last_exception

        return None

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status for monitoring."""
        return self._circuit_breaker.get_status()

    def reset_client_circuit_breaker(self) -> None:
        """Manually reset the client's circuit breaker."""
        self._circuit_breaker.reset()

    # =========================================================================
    # Health and diagnostics
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Get server health status."""
        result = self._safe_rpc_call("health_check")
        return dict(result)

    def reset_circuit_breaker(self) -> bool:
        """Reset server circuit breaker."""
        return bool(self._safe_rpc_call("reset_circuit_breaker"))

    # =========================================================================
    # Terminal operations
    # =========================================================================

    def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal."""
        result = self._safe_rpc_call(
            "initialize",
            path=path,
            login=login,
            password=password,
            server=server,
            timeout=timeout,
            portable=portable,
        )
        return bool(result)

    def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 60000,
    ) -> bool:
        """Login to trading account."""
        result = self._safe_rpc_call(
            "login",
            login=login,
            password=password,
            server=server,
            timeout=timeout,
        )
        return bool(result)

    def shutdown(self) -> None:
        """Shutdown MT5 terminal."""
        if self._service_root is None:
            return
        try:
            self._safe_rpc_call("shutdown")
        except RETRYABLE_EXCEPTIONS:
            log.debug("Shutdown RPC failed (connection may be closed)")

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version."""
        result = self._safe_rpc_call("version")
        return _validate_version(result)

    def last_error(self) -> tuple[int, str]:
        """Get last MT5 error."""
        result = self._safe_rpc_call("last_error")
        return _validate_last_error(result)

    def terminal_info(self) -> Any:
        """Get terminal info."""
        result = self._safe_rpc_call("terminal_info")
        return _wrap_dict(result)

    def account_info(self) -> Any:
        """Get account info."""
        result = self._safe_rpc_call("account_info")
        return _wrap_dict(result)

    # =========================================================================
    # Symbol operations
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of symbols."""
        result = self._safe_rpc_call("symbols_total")
        return int(result) if result is not None else 0

    def symbols_get(self, group: str | None = None) -> tuple | None:
        """Get available symbols."""
        result = self._safe_rpc_call("symbols_get", group)
        return _unwrap_chunks(result)

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol info."""
        result = self._safe_rpc_call("symbol_info", symbol)
        return _wrap_dict(result) if result else None

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick info."""
        result = self._safe_rpc_call("symbol_info_tick", symbol)
        return _wrap_dict(result) if result else None

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select symbol in Market Watch."""
        return bool(self._safe_rpc_call("symbol_select", symbol, enable))

    # =========================================================================
    # Market data operations - with obtain() for numpy arrays
    # =========================================================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        count: int,
    ) -> RatesArray | None:
        """Copy rates from a date."""
        result = self._safe_rpc_call(
            "copy_rates_from",
            symbol,
            timeframe,
            _to_timestamp(date_from),
            count,
        )
        return obtain(result) if result is not None else None

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> RatesArray | None:
        """Copy rates from a position."""
        result = self._safe_rpc_call(
            "copy_rates_from_pos",
            symbol,
            timeframe,
            start_pos,
            count,
        )
        return obtain(result) if result is not None else None

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> RatesArray | None:
        """Copy rates in a date range."""
        result = self._safe_rpc_call(
            "copy_rates_range",
            symbol,
            timeframe,
            _to_timestamp(date_from),
            _to_timestamp(date_to),
        )
        return obtain(result) if result is not None else None

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks from a date."""
        result = self._safe_rpc_call(
            "copy_ticks_from",
            symbol,
            _to_timestamp(date_from),
            count,
            flags,
        )
        return obtain(result) if result is not None else None

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks in a date range."""
        result = self._safe_rpc_call(
            "copy_ticks_range",
            symbol,
            _to_timestamp(date_from),
            _to_timestamp(date_to),
            flags,
        )
        return obtain(result) if result is not None else None

    # =========================================================================
    # Trading operations
    # =========================================================================

    def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin for order."""
        result = self._safe_rpc_call("order_calc_margin", action, symbol, volume, price)
        return _validate_float_optional(result)

    def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate profit for order."""
        result = self._safe_rpc_call(
            "order_calc_profit",
            action,
            symbol,
            volume,
            price_open,
            price_close,
        )
        return _validate_float_optional(result)

    def order_check(self, request: dict[str, Any]) -> Any:
        """Check order parameters without sending."""
        result = self._safe_rpc_call("order_check", request)
        return _wrap_dict(result) if result else None

    def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order to MT5."""
        result = self._safe_rpc_call("order_send", request)
        return _wrap_dict(result) if result else None

    # =========================================================================
    # Position operations
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions."""
        result = self._safe_rpc_call("positions_total")
        return int(result) if result is not None else 0

    def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple | None:
        """Get open positions."""
        result = self._safe_rpc_call("positions_get", symbol, group, ticket)
        return _wrap_dicts(result)

    # =========================================================================
    # Order operations
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders."""
        result = self._safe_rpc_call("orders_total")
        return int(result) if result is not None else 0

    def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple | None:
        """Get pending orders."""
        result = self._safe_rpc_call("orders_get", symbol, group, ticket)
        return _wrap_dicts(result)

    # =========================================================================
    # History operations
    # =========================================================================

    def history_orders_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical orders."""
        result = self._safe_rpc_call(
            "history_orders_total",
            _to_timestamp(date_from),
            _to_timestamp(date_to),
        )
        return _validate_int_optional(result)

    def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple | None:
        """Get historical orders."""
        result = self._safe_rpc_call(
            "history_orders_get",
            _to_timestamp(date_from),
            _to_timestamp(date_to),
            group,
            ticket,
            position,
        )
        return _wrap_dicts(result)

    def history_deals_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical deals."""
        result = self._safe_rpc_call(
            "history_deals_total",
            _to_timestamp(date_from),
            _to_timestamp(date_to),
        )
        return _validate_int_optional(result)

    def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple | None:
        """Get historical deals."""
        result = self._safe_rpc_call(
            "history_deals_get",
            _to_timestamp(date_from),
            _to_timestamp(date_to),
            group,
            ticket,
            position,
        )
        return _wrap_dicts(result)


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# For imports that expect these at module level
CircuitBreaker = MetaTrader5.CircuitBreaker
CircuitOpenError = MetaTrader5.CircuitBreaker.OpenError
MT5Error = MetaTrader5.Error
MT5RetryableError = MetaTrader5.RetryableError
MT5PermanentError = MetaTrader5.PermanentError
MaxRetriesExceededError = MetaTrader5.MaxRetriesError
