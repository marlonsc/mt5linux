"""MetaTrader5 client - modern RPyC bridge.

Modern RPyC client for connecting to MT5Service:
- Uses rpyc.connect() instead of deprecated rpyc.classic.connect()
- Direct method calls via conn.root.exposed_*
- Fail-fast error handling
- numpy array handling via rpyc.utils.classic.obtain()

Compatible with rpyc 6.x.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self

import rpyc
from rpyc.utils.classic import obtain

log = logging.getLogger(__name__)

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"

if TYPE_CHECKING:
    from datetime import datetime
    from types import TracebackType

    from mt5linux._types import RatesArray, TicksArray


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
    ) -> None:
        """Connect to rpyc server.

        Args:
            host: rpyc server address.
            port: rpyc server port.
            timeout: Timeout in seconds for operations.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._conn = None
        self._mt5 = None
        self._service_root: Any = None
        self.connect()

    def connect(self) -> None:
        """Establish connection to rpyc server using modern API."""
        if self._conn is not None:
            return

        # Modern rpyc.connect() instead of deprecated rpyc.classic.connect()
        self._conn = rpyc.connect(
            self._host,
            self._port,
            config={
                "sync_request_timeout": self._timeout,
                "allow_public_attrs": True,
            },
        )
        if self._conn is None:
            raise RuntimeError("Failed to establish RPyC connection")
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
    # Health and diagnostics
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """Get server health status.

        Returns:
            Health status dict from server.

        Raises:
            ConnectionError: If not connected.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return dict(self._service_root.health_check())

    def reset_circuit_breaker(self) -> bool:
        """Reset server circuit breaker.

        Returns:
            True if reset successful.

        Raises:
            ConnectionError: If not connected.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return bool(self._service_root.reset_circuit_breaker())

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
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return bool(
            self._service_root.initialize(path, login, password, server, timeout, portable)
        )

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
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return bool(self._service_root.login(login, password, server, timeout))

    def shutdown(self) -> None:
        """Shutdown MT5 terminal."""
        if self._service_root is None:
            return
        self._service_root.shutdown()

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (version, build, version_string) or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.version()

    def last_error(self) -> tuple[int, str]:
        """Get last MT5 error.

        Returns:
            Tuple of (error_code, error_description).
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.last_error()

    def terminal_info(self) -> Any:
        """Get terminal info.

        Returns:
            TerminalInfo object from MT5.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.terminal_info()

    def account_info(self) -> Any:
        """Get account info.

        Returns:
            AccountInfo object from MT5.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.account_info()

    # =========================================================================
    # Symbol operations
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of symbols.

        Returns:
            Number of available symbols.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return int(self._service_root.symbols_total())

    def symbols_get(self, group: str | None = None) -> Any:
        """Get available symbols.

        Args:
            group: Optional group filter.

        Returns:
            Tuple of SymbolInfo objects.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.symbols_get(group)

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol info.

        Args:
            symbol: Symbol name.

        Returns:
            SymbolInfo object or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.symbol_info(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick info.

        Args:
            symbol: Symbol name.

        Returns:
            Tick object or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.symbol_info_tick(symbol)

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to select, False to remove.

        Returns:
            True if successful.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return bool(self._service_root.symbol_select(symbol, enable))

    # =========================================================================
    # Market data operations - with obtain() for numpy arrays
    # =========================================================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        count: int,
    ) -> RatesArray | None:
        """Copy rates from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (TIMEFRAME_M1, etc.).
            date_from: Start datetime.
            count: Number of bars to copy.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        result = self._service_root.copy_rates_from(symbol, timeframe, date_from, count)
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
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        result = self._service_root.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        return obtain(result) if result is not None else None

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> RatesArray | None:
        """Copy rates in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start datetime.
            date_to: End datetime.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        result = self._service_root.copy_rates_range(symbol, timeframe, date_from, date_to)
        return obtain(result) if result is not None else None

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime.
            count: Number of ticks to copy.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        result = self._service_root.copy_ticks_from(symbol, date_from, count, flags)
        return obtain(result) if result is not None else None

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime.
            date_to: End datetime.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        result = self._service_root.copy_ticks_range(symbol, date_from, date_to, flags)
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
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.order_calc_margin(action, symbol, volume, price)

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
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.order_calc_profit(
            action, symbol, volume, price_open, price_close
        )

    def order_check(self, request: dict[str, Any]) -> Any:
        """Check order parameters without sending.

        Args:
            request: Order request dict to validate.

        Returns:
            OrderCheckResult from MT5.

        Raises:
            ConnectionError: If not connected to MT5 server.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)

        # Direct service call - no conn.execute() hack needed
        return self._service_root.order_check(request)

    def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order to MT5.

        Args:
            request: Order request dict with keys like action, symbol, volume, etc.

        Returns:
            OrderSendResult from MT5.

        Raises:
            ConnectionError: If not connected to MT5 server.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)

        # Direct service call - no conn.execute() hack needed
        return self._service_root.order_send(request)

    # =========================================================================
    # Position operations
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Number of open positions.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return int(self._service_root.positions_total())

    def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get open positions.

        Args:
            symbol: Filter by symbol.
            group: Filter by group.
            ticket: Filter by ticket.

        Returns:
            Tuple of TradePosition objects or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.positions_get(symbol, group, ticket)

    # =========================================================================
    # Order operations
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Number of pending orders.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return int(self._service_root.orders_total())

    def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get pending orders.

        Args:
            symbol: Filter by symbol.
            group: Filter by group.
            ticket: Filter by ticket.

        Returns:
            Tuple of TradeOrder objects or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.orders_get(symbol, group, ticket)

    # =========================================================================
    # History operations
    # =========================================================================

    def history_orders_total(self, date_from: datetime, date_to: datetime) -> int | None:
        """Get total number of historical orders.

        Args:
            date_from: Start datetime.
            date_to: End datetime.

        Returns:
            Number of historical orders or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.history_orders_total(date_from, date_to)

    def history_orders_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get historical orders.

        Args:
            date_from: Start datetime.
            date_to: End datetime.
            group: Filter by group.
            ticket: Filter by ticket.
            position: Filter by position.

        Returns:
            Tuple of TradeOrder objects or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.history_orders_get(
            date_from, date_to, group, ticket, position
        )

    def history_deals_total(self, date_from: datetime, date_to: datetime) -> int | None:
        """Get total number of historical deals.

        Args:
            date_from: Start datetime.
            date_to: End datetime.

        Returns:
            Number of historical deals or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.history_deals_total(date_from, date_to)

    def history_deals_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get historical deals.

        Args:
            date_from: Start datetime.
            date_to: End datetime.
            group: Filter by group.
            ticket: Filter by ticket.
            position: Filter by position.

        Returns:
            Tuple of TradeDeal objects or None.
        """
        if self._service_root is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._service_root.history_deals_get(
            date_from, date_to, group, ticket, position
        )
