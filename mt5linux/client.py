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

Compatible with rpyc 6.x.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

import rpyc
import rpyc.core.channel
import rpyc.core.stream
from rpyc.utils.classic import obtain

from mt5linux._resilience import (
    DEFAULT_HEALTH_CHECK_INTERVAL,
    RETRYABLE_EXCEPTIONS,
    CircuitBreaker,
    CircuitOpenError,
)

# =============================================================================
# RPyC Performance Optimization for Large Data Transfers
# =============================================================================
# When retrieving large datasets (e.g., 9116 symbols via symbols_get()),
# RPyC's default settings cause severe performance issues:
# - Default MAX_IO_CHUNK (8000 bytes) causes excessive network fragmentation
# - Each chunk requires a separate network round-trip
#
# Solution based on RPyC GitHub Issues #279 and #329:
# - Increase chunk size to ~650KB for 30x performance improvement
# - Disable compression (faster for already-structured data)
#
# References:
# - https://github.com/tomerfiliba-org/rpyc/issues/279
# - https://github.com/tomerfiliba-org/rpyc/issues/329
# =============================================================================
rpyc.core.stream.SocketStream.MAX_IO_CHUNK = 65355 * 10  # ~650KB chunks
rpyc.core.channel.Channel.COMPRESSION_LEVEL = 0  # Disable compression for speed

log = logging.getLogger(__name__)

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"

if TYPE_CHECKING:
    from types import TracebackType

    from mt5linux._types import RatesArray, TicksArray


# =============================================================================
# Datetime Serialization Helper - RPyC Fix
# =============================================================================


def _to_timestamp(dt: datetime | int | None) -> int | None:
    """Convert datetime to Unix timestamp for MT5 API.

    RPyC doesn't properly serialize datetime objects to Wine/Windows.
    MT5 API accepts Unix timestamps (seconds since epoch).

    Args:
        dt: datetime object, Unix timestamp (int), or None

    Returns:
        Unix timestamp (int) or None
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    return dt  # Already int


# =============================================================================
# Type Validation Helpers - Convert RPyC's Any to Concrete Types
# =============================================================================

# Constants for tuple length validation
_VERSION_TUPLE_LEN = 3  # (version, build, version_string)
_ERROR_TUPLE_LEN = 2  # (error_code, error_description)


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
    if isinstance(value, (int, float)) and not isinstance(value, bool):
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
# Server returns dicts to avoid IPC timeout. Client wraps them for attribute access.


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

    # Fallback for non-chunked response
    if isinstance(result, (tuple, list)):
        return _wrap_dicts(result)

    return result


class MetaTrader5:
    """Modern RPyC client for MetaTrader5.

    Connects to MT5Service (modern rpyc.Service) via rpyc.connect().
    Delegates MT5 operations to exposed service methods.

    Example:
        >>> with MetaTrader5(host="localhost", port=18812) as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     print(mt5.ORDER_TYPE_BUY)  # Real MT5 constant
    """

    _conn: rpyc.Connection | None
    _mt5: Any

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
        *,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_recovery: float = 60.0,
        health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
        max_reconnect_attempts: int = 3,
    ) -> None:
        """Connect to rpyc server.

        Args:
            host: rpyc server address.
            port: rpyc server port.
            timeout: Timeout in seconds for operations.
            circuit_breaker_threshold: Failures before circuit opens.
            circuit_breaker_recovery: Seconds to wait before recovery attempt.
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
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_recovery,
            name=f"mt5-{host}:{port}",
        )
        self._health_check_interval = health_check_interval
        self._last_health_check: datetime | None = None
        self._max_reconnect_attempts = max_reconnect_attempts

        self.connect()

    def connect(self) -> None:
        """Establish connection to rpyc server using modern API."""
        if self._conn is not None:
            return

        # Modern rpyc.connect() instead of deprecated rpyc.classic.connect()
        # allow_pickle=True required for efficient large data transfer (9000+ symbols)
        self._conn = rpyc.connect(
            self._host,
            self._port,
            config={
                "sync_request_timeout": self._timeout,
                "allow_public_attrs": True,
                "allow_pickle": True,
            },
        )
        if self._conn is None:
            msg = "Failed to establish RPyC connection"
            raise RuntimeError(msg)
        self._service_root = self._conn.root

        # Get MT5 module reference via exposed_get_mt5()
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
        """Reconnect to RPyC server with retry logic.

        Closes current connection and establishes a new one.
        Uses exponential backoff on failures.
        """
        import random
        import time

        log.info("Attempting reconnection to %s:%d", self._host, self._port)
        self.close()

        # Use retry decorator logic manually for reconnection
        last_error: Exception | None = None
        for attempt in range(self._max_reconnect_attempts):
            try:
                self.connect()
            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self._max_reconnect_attempts - 1:
                    delay = min(0.5 * (2**attempt), 10.0)
                    delay *= 0.5 + random.random()  # noqa: S311
                    log.warning(
                        "Reconnection attempt %d failed: %s, retrying in %.2fs",
                        attempt + 1,
                        e,
                        delay,
                    )
                    time.sleep(delay)
            else:
                log.info(
                    "Reconnection successful on attempt %d",
                    attempt + 1,
                )
                return

        msg = f"Reconnection failed after {self._max_reconnect_attempts} attempts"
        log.error(msg)
        if last_error:
            raise ConnectionError(msg) from last_error
        raise ConnectionError(msg)

    def _check_connection_health(self) -> bool:
        """Verify connection is alive with lightweight ping.

        Returns:
            True if connection is healthy.
        """
        if self._conn is None:
            return False
        try:
            # Check if connection is closed
            if getattr(self._conn, "closed", False):
                return False
            # Try a lightweight operation to verify connection is responsive
            # Access the root service to trigger any connection issues
            _ = self._service_root
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    def _ensure_healthy_connection(self) -> None:
        """Ensure connection is healthy, reconnect if needed.

        Raises:
            CircuitOpenError: If circuit breaker is open.
        """
        # Check circuit breaker first
        if not self._circuit_breaker.can_execute():
            raise CircuitOpenError

        # Skip health check if recent
        from datetime import UTC

        now = datetime.now(UTC)
        if (
            self._last_health_check
            and (now - self._last_health_check).total_seconds()
            < self._health_check_interval
        ):
            return

        # Perform health check
        if not self._check_connection_health():
            log.warning("Connection unhealthy, attempting reconnect")
            try:
                self._reconnect()
            except Exception:
                self._circuit_breaker.record_failure()
                raise

        self._last_health_check = now

    def _safe_rpc_call(  # noqa: C901
        self,
        method_name: str,
        *args: Any,
        retry_on_none: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Execute RPC call with full error handling and automatic retry.

        Resilience is automatic and transparent:
        - Retries on connection errors with exponential backoff
        - Retries on None returns (transient MT5 failures)
        - Circuit breaker prevents cascading failures
        - Auto-reconnect on connection loss

        Args:
            method_name: Name of the exposed method to call.
            *args: Positional arguments for the method.
            retry_on_none: If True (default), retry when method returns None.
                Set to False for methods where None is a valid response.
            **kwargs: Keyword arguments for the method.

        Returns:
            Result from the RPC call.

        Raises:
            CircuitOpenError: If circuit breaker is open.
            ConnectionError: If connection fails after all retries.
        """
        import random
        import time

        max_attempts = 3
        initial_delay = 0.5
        max_delay = 10.0

        self._ensure_healthy_connection()

        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)

        last_exception: Exception | None = None

        for attempt in range(max_attempts):
            # Ensure connection is valid before each attempt
            if self._service_root is None:
                try:
                    self._reconnect()
                except Exception as reconnect_err:  # noqa: BLE001
                    last_exception = reconnect_err
                    if attempt < max_attempts - 1:
                        delay = min(initial_delay * (2**attempt), max_delay)
                        delay *= 0.5 + random.random()  # noqa: S311
                        log.warning(
                            "%s reconnect failed (attempt %d/%d): %s, retrying in %.2fs",
                            method_name,
                            attempt + 1,
                            max_attempts,
                            reconnect_err,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    else:
                        raise ConnectionError(
                            f"Connection failed after {max_attempts} attempts"
                        ) from reconnect_err

            try:
                method = getattr(self._service_root, method_name)
                result = method(*args, **kwargs)

                # Retry on None if enabled
                if retry_on_none and result is None:
                    if attempt < max_attempts - 1:
                        delay = min(initial_delay * (2**attempt), max_delay)
                        delay *= 0.5 + random.random()  # noqa: S311
                        log.warning(
                            "%s returned None (attempt %d/%d), retrying in %.2fs",
                            method_name,
                            attempt + 1,
                            max_attempts,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    log.warning(
                        "%s returned None after %d attempts",
                        method_name,
                        max_attempts,
                    )

                # Success
                self._circuit_breaker.record_success()
                if attempt > 0:
                    log.info("%s succeeded on attempt %d", method_name, attempt + 1)
                return result  # noqa: TRY300

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                self._circuit_breaker.record_failure()
                if attempt < max_attempts - 1:
                    delay = min(initial_delay * (2**attempt), max_delay)
                    delay *= 0.5 + random.random()  # noqa: S311
                    log.warning(
                        "%s failed (attempt %d/%d): %s, retrying in %.2fs",
                        method_name,
                        attempt + 1,
                        max_attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    # Try reconnecting before next attempt
                    try:  # noqa: SIM105
                        self._reconnect()
                    except Exception:  # noqa: BLE001, S110
                        pass  # Will fail on next attempt if reconnect failed
                else:
                    log.exception(
                        "%s failed after %d attempts", method_name, max_attempts
                    )
                    raise

            except Exception:
                log.exception("Unexpected error in %s", method_name)
                raise

        # Should not reach here, but satisfy type checker
        if last_exception is not None:
            raise last_exception
        return None

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status for monitoring.

        Returns:
            Dict with circuit breaker state and metrics.
        """
        return self._circuit_breaker.get_status()

    def reset_client_circuit_breaker(self) -> None:
        """Manually reset the client's circuit breaker."""
        self._circuit_breaker.reset()

    # =========================================================================
    # Health and diagnostics
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Get server health status.

        Returns:
            Health status dict from server.

        Raises:
            ConnectionError: If not connected.
        """
        result = self._safe_rpc_call("health_check")
        return dict(result)

    def reset_circuit_breaker(self) -> bool:
        """Reset server circuit breaker.

        Returns:
            True if reset successful.

        Raises:
            ConnectionError: If not connected.
        """
        return bool(self._safe_rpc_call("reset_circuit_breaker"))

    # =========================================================================
    # Terminal operations - delegate to service
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
        """Initialize MT5 terminal.

        Args:
            path: Path to the MetaTrader 5 terminal executable.
            login: Trading account number.
            password: Trading account password.
            server: Trade server name.
            timeout: Connection timeout.
            portable: Portable mode flag.

        Returns:
            True if successful, False otherwise.
        """
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
        """Login to trading account.

        Args:
            login: Trading account number.
            password: Trading account password.
            server: Trade server name.
            timeout: Connection timeout in milliseconds.

        Returns:
            True if successful, False otherwise.
        """
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
            # Ignore connection errors during shutdown
            log.debug("Shutdown RPC failed (connection may be closed)")

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (version, build, version_string) or None.
        """
        result = self._safe_rpc_call("version")
        return _validate_version(result)

    def last_error(self) -> tuple[int, str]:
        """Get last MT5 error.

        Returns:
            Tuple of (error_code, error_description).
        """
        result = self._safe_rpc_call("last_error")
        return _validate_last_error(result)

    def terminal_info(self) -> Any:
        """Get terminal info.

        Returns:
            TerminalInfo-like object with attribute access.
        """
        result = self._safe_rpc_call("terminal_info")
        return _wrap_dict(result)

    def account_info(self) -> Any:
        """Get account info.

        Returns:
            AccountInfo-like object with attribute access.
        """
        result = self._safe_rpc_call("account_info")
        return _wrap_dict(result)

    # =========================================================================
    # Symbol operations
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of symbols.

        Returns:
            Number of available symbols.
        """
        result = self._safe_rpc_call("symbols_total")
        return int(result) if result is not None else 0

    def symbols_get(self, group: str | None = None) -> tuple | None:
        """Get available symbols.

        Args:
            group: Optional group filter.

        Returns:
            Tuple of SymbolInfo-like objects or None.
        """
        result = self._safe_rpc_call("symbols_get", group)
        return _unwrap_chunks(result)

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol info.

        Args:
            symbol: Symbol name.

        Returns:
            SymbolInfo-like object with attribute access, or None.
        """
        result = self._safe_rpc_call("symbol_info", symbol)
        return _wrap_dict(result) if result else None

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick info.

        Args:
            symbol: Symbol name.

        Returns:
            Tick-like object with attribute access, or None.
        """
        result = self._safe_rpc_call("symbol_info_tick", symbol)
        return _wrap_dict(result) if result else None

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to select, False to remove.

        Returns:
            True if successful.
        """
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
        """Copy rates from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (TIMEFRAME_M1, etc.).
            date_from: Start datetime or Unix timestamp.
            count: Number of bars to copy.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
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
        """Copy rates from a position. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            start_pos: Start position (0 = current bar).
            count: Number of bars to copy.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
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
        """Copy rates in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
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
        """Copy ticks from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime or Unix timestamp.
            count: Number of ticks to copy.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
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
        """Copy ticks in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
        result = self._safe_rpc_call(
            "copy_ticks_range",
            symbol,
            _to_timestamp(date_from),
            _to_timestamp(date_to),
            flags,
        )
        return obtain(result) if result is not None else None

    # =========================================================================
    # Trading operations - direct service calls (no conn.execute hack)
    # =========================================================================

    def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin for order.

        Args:
            action: Order action (ORDER_TYPE_BUY, ORDER_TYPE_SELL).
            symbol: Symbol name.
            volume: Order volume.
            price: Order price.

        Returns:
            Required margin or None.
        """
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
        """Calculate profit for order.

        Args:
            action: Order action (ORDER_TYPE_BUY, ORDER_TYPE_SELL).
            symbol: Symbol name.
            volume: Order volume.
            price_open: Open price.
            price_close: Close price.

        Returns:
            Calculated profit or None.
        """
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
        """Check order parameters without sending.

        Args:
            request: Order request dict to validate.

        Returns:
            OrderCheckResult-like object with attribute access.

        Raises:
            ConnectionError: If not connected to MT5 server.
        """
        result = self._safe_rpc_call("order_check", request)
        return _wrap_dict(result) if result else None

    def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order to MT5.

        Args:
            request: Order request dict with keys like action, symbol, volume, etc.

        Returns:
            OrderSendResult-like object with attribute access.

        Raises:
            ConnectionError: If not connected to MT5 server.
        """
        result = self._safe_rpc_call("order_send", request)
        return _wrap_dict(result) if result else None

    # =========================================================================
    # Position operations
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Number of open positions.
        """
        result = self._safe_rpc_call("positions_total")
        return int(result) if result is not None else 0

    def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple | None:
        """Get open positions.

        Args:
            symbol: Filter by symbol.
            group: Filter by group.
            ticket: Filter by ticket.

        Returns:
            Tuple of TradePosition-like objects with attribute access, or None.
        """
        result = self._safe_rpc_call("positions_get", symbol, group, ticket)
        return _wrap_dicts(result)

    # =========================================================================
    # Order operations
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Number of pending orders.
        """
        result = self._safe_rpc_call("orders_total")
        return int(result) if result is not None else 0

    def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple | None:
        """Get pending orders.

        Args:
            symbol: Filter by symbol.
            group: Filter by group.
            ticket: Filter by ticket.

        Returns:
            Tuple of TradeOrder-like objects with attribute access, or None.
        """
        result = self._safe_rpc_call("orders_get", symbol, group, ticket)
        return _wrap_dicts(result)

    # =========================================================================
    # History operations
    # =========================================================================

    def history_orders_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical orders.

        Args:
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.

        Returns:
            Number of historical orders or None.
        """
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
        """Get historical orders.

        Args:
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.
            group: Filter by group.
            ticket: Filter by ticket.
            position: Filter by position.

        Returns:
            Tuple of TradeOrder-like objects with attribute access, or None.
        """
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
        """Get total number of historical deals.

        Args:
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.

        Returns:
            Number of historical deals or None.
        """
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
        """Get historical deals.

        Args:
            date_from: Start datetime or Unix timestamp.
            date_to: End datetime or Unix timestamp.
            group: Filter by group.
            ticket: Filter by ticket.
            position: Filter by position.

        Returns:
            Tuple of TradeDeal-like objects with attribute access, or None.
        """
        result = self._safe_rpc_call(
            "history_deals_get",
            _to_timestamp(date_from),
            _to_timestamp(date_to),
            group,
            ticket,
            position,
        )
        return _wrap_dicts(result)
