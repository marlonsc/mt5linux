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

Hierarchy Level: 3
- Imports: MT5Config, MT5Types, MT5Utilities
- Top-level client module

Compatible with rpyc 6.x and Python 3.13+.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Self

import rpyc
from rpyc.utils.classic import obtain

from mt5linux.config import MT5Config
from mt5linux.models import MT5Models
from mt5linux.utilities import MT5Utilities

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from types import TracebackType

    from mt5linux.constants import MT5Constants
    from mt5linux.types import MT5Types

# Default config instance
_config = MT5Config()

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"


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
    # INSTANCE ATTRIBUTES
    # =========================================================================

    _conn: rpyc.Connection | None
    _constants: dict[str, Any]

    def __init__(
        self,
        host: str = _config.host,
        port: int = _config.rpyc_port,
        timeout: int = _config.timeout_connection,
        *,
        config: MT5Config | None = None,
        health_check_interval: int | None = None,
        max_reconnect_attempts: int | None = None,
    ) -> None:
        """Connect to rpyc server.

        Args:
            host: rpyc server address.
            port: rpyc server port.
            timeout: Timeout in seconds for operations.
            config: MT5Config instance for all configuration (uses defaults).
            health_check_interval: Seconds between health checks (config override).
            max_reconnect_attempts: Max reconnection attempts (config override).
        """
        self._config = config or _config
        self._host = host
        self._port = port
        self._timeout = timeout
        self._conn = None
        self._constants: dict[str, Any] = {}
        self._service_root: Any = None

        # Resilience configuration (uses MT5Config directly)
        self._circuit_breaker = MT5Utilities.CircuitBreaker(
            config=self._config,
            name=f"mt5-{host}:{port}",
        )
        self._health_check_interval = (
            health_check_interval or self._config.timeout_health_check
        )
        self._last_health_check: datetime | None = None
        self._max_reconnect_attempts = (
            max_reconnect_attempts or self._config.retry_max_attempts
        )

        self._connect()

    def _connect(self) -> None:
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
                "max_io_chunk": _config.rpyc_max_io_chunk,
                "compression_level": _config.rpyc_compression_level,
            },
        )
        if self._conn is None:
            msg = "Failed to establish RPyC connection"
            raise RuntimeError(msg)
        self._service_root = self._conn.root
        self._constants = self._service_root.get_constants()

    def __getattr__(self, name: str) -> Any:
        """Transparent proxy for MT5 constants (ORDER_TYPE_*, TIMEFRAME_*, etc)."""
        if name in self._constants:
            return self._constants[name]
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

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
        self._close()

    def _close(self) -> None:
        """Close rpyc connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except (OSError, ConnectionError, EOFError):
                log.debug("RPyC connection close failed (may already be closed)")
            self._conn = None
            self._constants = {}
            self._service_root = None

    def close(self) -> None:
        """Close the connection (public API)."""
        self._close()

    # =========================================================================
    # Resilience Methods
    # =========================================================================

    def _reconnect(self) -> None:
        """Reconnect to RPyC server with retry logic."""
        log.info("Attempting reconnection to %s:%d", self._host, self._port)
        self._close()

        last_error: Exception | None = None
        for attempt in range(self._max_reconnect_attempts):
            try:
                self._connect()
            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self._max_reconnect_attempts - 1:
                    delay = self._config.calculate_retry_delay(attempt)
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
            raise MT5Utilities.Exceptions.CircuitBreakerOpenError

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
        retry_on_none: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Execute RPC call with full error handling and automatic retry."""
        self._ensure_healthy_connection()

        last_exception: Exception | None = None
        max_attempts = self._config.retry_max_attempts

        for attempt in range(max_attempts):
            try:
                result = self._execute_operation(method_name, *args, **kwargs)

                # Handle None results - retry if configured
                if retry_on_none and result is None and attempt < max_attempts - 1:
                    delay = self._config.calculate_retry_delay(attempt)
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

            except RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                self._circuit_breaker.record_failure()
                if attempt < max_attempts - 1:
                    delay = self._config.calculate_retry_delay(attempt)
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
                    log.exception(
                        "%s failed after %d attempts", method_name, max_attempts
                    )
                    raise

            else:
                return result

        if last_exception:
            raise MT5Utilities.Exceptions.MaxRetriesError(
                operation=method_name,
                attempts=max_attempts,
                last_error=last_exception,
            ) from last_exception

        return None

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
        return MT5Utilities.Data.validate_version(result)

    def last_error(self) -> tuple[int, str]:
        """Get last MT5 error."""
        result = self._safe_rpc_call("last_error")
        return MT5Utilities.Data.validate_last_error(result)

    def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal info."""
        result = self._safe_rpc_call("terminal_info")
        if result is None:
            return None
        wrapped = MT5Utilities.Data.wrap(result)
        return MT5Models.TerminalInfo.from_mt5(wrapped)

    def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account info."""
        result = self._safe_rpc_call("account_info")
        if result is None:
            return None
        wrapped = MT5Utilities.Data.wrap(result)
        return MT5Models.AccountInfo.from_mt5(wrapped)

    # =========================================================================
    # Symbol operations
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of symbols."""
        result = self._safe_rpc_call("symbols_total")
        return int(result) if result is not None else 0

    def symbols_get(
        self, group: str | None = None
    ) -> tuple[MT5Models.SymbolInfo, ...] | None:
        """Get available symbols."""
        result = self._safe_rpc_call("symbols_get", group)
        wrapped = MT5Utilities.Data.unwrap_chunks(result)
        if wrapped is None:
            return None
        symbols = [MT5Models.SymbolInfo.from_mt5(s) for s in wrapped]
        return tuple(s for s in symbols if s is not None)

    def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get symbol info."""
        result = self._safe_rpc_call("symbol_info", symbol)
        if result is None:
            return None
        wrapped = MT5Utilities.Data.wrap(result)
        return MT5Models.SymbolInfo.from_mt5(wrapped)

    def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get symbol tick info."""
        result = self._safe_rpc_call("symbol_info_tick", symbol)
        if result is None:
            return None
        wrapped = MT5Utilities.Data.wrap(result)
        return MT5Models.Tick.from_mt5(wrapped)

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select symbol in Market Watch."""
        return bool(self._safe_rpc_call("symbol_select", symbol, enable))

    # =========================================================================
    # Market data operations - with obtain() for numpy arrays
    # =========================================================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        date_from: datetime | int,
        count: int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates from a date."""
        result = self._safe_rpc_call(
            "copy_rates_from",
            symbol,
            int(timeframe),
            MT5Utilities.Data.to_timestamp(date_from),
            count,
        )
        return obtain(result) if result is not None else None

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        start_pos: int,
        count: int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates from a position."""
        result = self._safe_rpc_call(
            "copy_rates_from_pos",
            symbol,
            int(timeframe),
            start_pos,
            count,
        )
        return obtain(result) if result is not None else None

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates in a date range."""
        result = self._safe_rpc_call(
            "copy_rates_range",
            symbol,
            int(timeframe),
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
        )
        return obtain(result) if result is not None else None

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: MT5Constants.CopyTicksFlag | int,
    ) -> MT5Types.TicksArray | None:
        """Copy ticks from a date."""
        result = self._safe_rpc_call(
            "copy_ticks_from",
            symbol,
            MT5Utilities.Data.to_timestamp(date_from),
            count,
            int(flags),
        )
        return obtain(result) if result is not None else None

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: MT5Constants.CopyTicksFlag | int,
    ) -> MT5Types.TicksArray | None:
        """Copy ticks in a date range."""
        result = self._safe_rpc_call(
            "copy_ticks_range",
            symbol,
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
            int(flags),
        )
        return obtain(result) if result is not None else None

    # =========================================================================
    # Trading operations
    # =========================================================================

    def order_calc_margin(
        self,
        action: MT5Constants.TradeAction | int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin for order."""
        result = self._safe_rpc_call(
            "order_calc_margin", int(action), symbol, volume, price
        )
        return MT5Utilities.Data.validate_float_optional(result)

    def order_calc_profit(
        self,
        action: MT5Constants.TradeAction | int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate profit for order."""
        result = self._safe_rpc_call(
            "order_calc_profit",
            int(action),
            symbol,
            volume,
            price_open,
            price_close,
        )
        return MT5Utilities.Data.validate_float_optional(result)

    def order_check(
        self, request: MT5Types.OrderRequestDict | dict[str, Any]
    ) -> MT5Models.OrderResult | None:
        """Check order parameters without sending."""
        result = self._safe_rpc_call("order_check", dict(request))
        if result is None:
            return None
        wrapped = MT5Utilities.Data.wrap(result)
        return MT5Models.OrderResult.from_mt5(wrapped)

    def order_send(
        self, request: MT5Types.OrderRequestDict | dict[str, Any]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5."""
        result = self._safe_rpc_call("order_send", dict(request))
        return MT5Models.OrderResult.from_mt5(result)

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
    ) -> tuple[MT5Models.Position, ...] | None:
        """Get open positions."""
        result = self._safe_rpc_call("positions_get", symbol, group, ticket)
        wrapped = MT5Utilities.Data.wrap_many(result)
        if wrapped is None:
            return None
        positions = [MT5Models.Position.from_mt5(p) for p in wrapped]
        return tuple(p for p in positions if p is not None)

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
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get pending orders.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific order ticket to retrieve.

        Returns:
            Tuple of Order objects or None if no orders found.
        """
        result = self._safe_rpc_call("orders_get", symbol, group, ticket)
        wrapped = MT5Utilities.Data.wrap_many(result)
        if wrapped is None:
            return None
        orders = [MT5Models.Order.from_mt5(o) for o in wrapped]
        return tuple(o for o in orders if o is not None)

    # =========================================================================
    # History operations
    # =========================================================================

    def history_orders_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical orders."""
        result = self._safe_rpc_call(
            "history_orders_total",
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
        )
        return MT5Utilities.Data.validate_int_optional(result)

    def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get historical orders.

        Args:
            date_from: Start date for history query (datetime or Unix timestamp).
            date_to: End date for history query (datetime or Unix timestamp).
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific order ticket to retrieve.
            position: Position ID to filter orders by.

        Returns:
            Tuple of Order objects or None if no orders found.
        """
        result = self._safe_rpc_call(
            "history_orders_get",
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
            group,
            ticket,
            position,
        )
        wrapped = MT5Utilities.Data.wrap_many(result)
        if wrapped is None:
            return None
        orders = [MT5Models.Order.from_mt5(o) for o in wrapped]
        return tuple(o for o in orders if o is not None)

    def history_deals_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical deals."""
        result = self._safe_rpc_call(
            "history_deals_total",
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
        )
        return MT5Utilities.Data.validate_int_optional(result)

    def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Deal, ...] | None:
        """Get historical deals.

        Args:
            date_from: Start date for history query (datetime or Unix timestamp).
            date_to: End date for history query (datetime or Unix timestamp).
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific deal ticket to retrieve.
            position: Position ID to filter deals by.

        Returns:
            Tuple of Deal objects or None if no deals found.
        """
        result = self._safe_rpc_call(
            "history_deals_get",
            MT5Utilities.Data.to_timestamp(date_from),
            MT5Utilities.Data.to_timestamp(date_to),
            group,
            ticket,
            position,
        )
        wrapped = MT5Utilities.Data.wrap_many(result)
        if wrapped is None:
            return None
        deals = [MT5Models.Deal.from_mt5(d) for d in wrapped]
        return tuple(d for d in deals if d is not None)

    # =========================================================================
    # Market Depth (DOM) operations
    # =========================================================================

    def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) updates for a symbol.

        Must be called before market_book_get() to start receiving updates.

        Args:
            symbol: Symbol name to subscribe to.

        Returns:
            True if subscription successful, False otherwise.
        """
        result = self._safe_rpc_call("market_book_add", symbol)
        return bool(result) if result is not None else False

    def market_book_get(self, symbol: str) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior call to market_book_add() for the symbol.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            Tuple of BookEntry objects representing the order book,
            or None if no data available.
        """
        result = self._safe_rpc_call("market_book_get", symbol)
        wrapped = MT5Utilities.Data.wrap_many(result)
        if wrapped is None:
            return None
        entries = [MT5Models.BookEntry.from_mt5(e) for e in wrapped]
        return tuple(e for e in entries if e is not None)

    def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) updates for a symbol.

        Should be called when market depth data is no longer needed.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.
        """
        result = self._safe_rpc_call("market_book_release", symbol)
        return bool(result) if result is not None else False

    # =========================================================================
    # Health check operations
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Check connection and service health status.

        Returns:
            Dictionary with health status information including:
            - connected: Whether RPyC connection is active
            - mt5_initialized: Whether MT5 terminal is initialized
            - timestamp: Current server timestamp
            - Additional service-specific health metrics
        """
        result = self._safe_rpc_call("health_check", retry_on_none=False)
        return result if isinstance(result, dict) else {}
