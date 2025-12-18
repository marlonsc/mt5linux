"""Unified protocol definitions for mt5linux.

Defines ONE protocol that EXACTLY matches the MetaTrader5 PyPI interface.
Both sync and async clients implement the same protocol structure.

Protocol contains 32 methods matching MetaTrader5 PyPI:
- Terminal: initialize, login, shutdown, version, last_error,
            terminal_info, account_info
- Symbol: symbols_total, symbols_get, symbol_info, symbol_info_tick, symbol_select
- Market Data: copy_rates_from, copy_rates_from_pos, copy_rates_range,
              copy_ticks_from, copy_ticks_range
- Trading: order_calc_margin, order_calc_profit, order_check, order_send
- Positions: positions_total, positions_get
- Orders: orders_total, orders_get
- History: history_orders_total, history_orders_get,
           history_deals_total, history_deals_get
- Market Depth: market_book_add, market_book_get, market_book_release

Note: connect(), disconnect(), health_check(), is_connected are NOT in the protocol.
These are mt5linux-specific extensions in the client implementations.

Uses @runtime_checkable for both static (mypy/pyright) and runtime (isinstance)
validation of client implementations.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    import numpy as np
    from numpy.typing import NDArray

    from mt5linux.models import MT5Models

# Type alias for JSON values (single source of truth)
type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]


@runtime_checkable
class MT5Protocol(Protocol):
    """Protocol matching MetaTrader5 PyPI interface with Pydantic return types.

    Defines the complete interface for MT5 operations.
    All implementations must provide these exact 32 method signatures.

    This protocol does NOT include:
    - connect() / disconnect() - mt5linux-specific gRPC connection
    - health_check() - mt5linux-specific health monitoring
    - is_connected - mt5linux-specific connection state

    """

    # =========================================================================
    # TERMINAL OPERATIONS (7 methods)
    # =========================================================================

    def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection.

        Args:
            path: Path to MT5 terminal executable.
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Connection timeout in milliseconds.
            portable: Use portable mode.

        Returns:
            True if initialization successful, False otherwise.

        """
        ...

    def login(
        self,
        login: int,
        password: str | None = None,
        server: str | None = None,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account.

        Args:
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Login timeout in milliseconds.

        Returns:
            True if login successful, False otherwise.

        """
        ...

    def shutdown(self) -> None:
        """Shutdown MT5 terminal connection."""
        ...

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (major, minor, build_string) or None.

        """
        ...

    def last_error(self) -> tuple[int, str]:
        """Get last error code and description.

        Returns:
            Tuple of (error_code, error_message).

        """
        ...

    def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal information.

        Returns:
            TerminalInfo model or None.

        """
        ...

    def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information.

        Returns:
            AccountInfo model or None.

        """
        ...

    # =========================================================================
    # SYMBOL OPERATIONS (5 methods)
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of available symbols.

        Returns:
            Total count of symbols.

        """
        ...

    def symbols_get(
        self, group: str | None = None
    ) -> tuple[MT5Models.SymbolInfo, ...] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern (e.g., "*USD*").

        Returns:
            Tuple of SymbolInfo models or None.

        """
        ...

    def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            SymbolInfo model or None.

        """
        ...

    def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Tick model or None.

        """
        ...

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to add, False to remove from Market Watch.

        Returns:
            True if successful, False otherwise.

        """
        ...

    # =========================================================================
    # MARKET DATA OPERATIONS (5 methods)
    # =========================================================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a specific date.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (e.g., TIMEFRAME_H1).
            date_from: Start date as datetime or Unix timestamp.
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a bar position.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            start_pos: Start position (0 = current bar).
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates in a date range.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        ...

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data from a specific date.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            count: Number of ticks to copy.
            flags: Copy ticks flags (e.g., COPY_TICKS_ALL).

        Returns:
            NumPy structured array with tick data or None.

        """
        ...

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data in a date range.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.
            flags: Copy ticks flags.

        Returns:
            NumPy structured array with tick data or None.

        """
        ...

    # =========================================================================
    # TRADING OPERATIONS (4 methods)
    # =========================================================================

    def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin required for an order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price: Order price.

        Returns:
            Required margin or None.

        """
        ...

    def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate potential profit for an order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price_open: Open price.
            price_close: Close price.

        Returns:
            Calculated profit or None.

        """
        ...

    def order_check(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderCheckResult | None:
        """Check order validity without sending.

        Args:
            request: Order request dictionary.

        Returns:
            OrderCheckResult model or None.

        """
        ...

    def order_send(self, request: dict[str, JSONValue]) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary.

        Returns:
            OrderResult model or None.

        """
        ...

    # =========================================================================
    # POSITIONS OPERATIONS (2 methods)
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Count of open positions.

        """
        ...

    def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Position, ...] | None:
        """Get open positions with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific position ticket.

        Returns:
            Tuple of Position models or None.

        """
        ...

    # =========================================================================
    # ORDERS OPERATIONS (2 methods)
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Count of pending orders.

        """
        ...

    def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get pending orders with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific order ticket.

        Returns:
            Tuple of Order models or None.

        """
        ...

    # =========================================================================
    # HISTORY OPERATIONS (4 methods)
    # =========================================================================

    def history_orders_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical orders in date range.

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            Count of historical orders.

        """
        ...

    def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get historical orders with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific order ticket.
            position: Position ID filter.

        Returns:
            Tuple of Order models or None.

        """
        ...

    def history_deals_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical deals in date range.

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            Count of historical deals.

        """
        ...

    def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Deal, ...] | None:
        """Get historical deals with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific deal ticket.
            position: Position ID filter.

        Returns:
            Tuple of Deal models or None.

        """
        ...

    # =========================================================================
    # MARKET DEPTH (DOM) OPERATIONS (3 methods)
    # =========================================================================

    def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) for a symbol.

        Must be called before market_book_get to receive updates.

        Args:
            symbol: Symbol name to subscribe to.

        Returns:
            True if subscription successful, False otherwise.

        """
        ...

    def market_book_get(self, symbol: str) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior market_book_add call.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            Tuple of BookEntry models or None.

        """
        ...

    def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.

        """
        ...


@runtime_checkable
class AsyncMT5Protocol(Protocol):
    """Async protocol matching MetaTrader5 PyPI interface with Pydantic return types.

    Identical to MT5Protocol but with async/await keywords.
    All implementations must provide these exact 32 method signatures.

    This protocol does NOT include:
    - connect() / disconnect() - mt5linux-specific gRPC connection
    - health_check() - mt5linux-specific health monitoring
    - is_connected - mt5linux-specific connection state

    """

    # =========================================================================
    # TERMINAL OPERATIONS (7 methods)
    # =========================================================================

    async def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection (async)."""
        ...

    async def login(
        self,
        login: int,
        password: str | None = None,
        server: str | None = None,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account (async)."""
        ...

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection (async)."""
        ...

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version (async)."""
        ...

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description (async)."""
        ...

    async def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal information (async)."""
        ...

    async def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information (async)."""
        ...

    # =========================================================================
    # SYMBOL OPERATIONS (5 methods)
    # =========================================================================

    async def symbols_total(self) -> int:
        """Get total number of available symbols (async)."""
        ...

    async def symbols_get(
        self, group: str | None = None
    ) -> tuple[MT5Models.SymbolInfo, ...] | None:
        """Get available symbols with optional group filter (async)."""
        ...

    async def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information (async)."""
        ...

    async def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol (async)."""
        ...

    async def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch (async)."""
        ...

    # =========================================================================
    # MARKET DATA OPERATIONS (5 methods)
    # =========================================================================

    async def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a specific date (async)."""
        ...

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a bar position (async)."""
        ...

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates in a date range (async)."""
        ...

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data from a specific date (async)."""
        ...

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data in a date range (async)."""
        ...

    # =========================================================================
    # TRADING OPERATIONS (4 methods)
    # =========================================================================

    async def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin required for an order (async)."""
        ...

    async def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate potential profit for an order (async)."""
        ...

    async def order_check(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderCheckResult | None:
        """Check order validity without sending (async)."""
        ...

    async def order_send(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5 (async)."""
        ...

    # =========================================================================
    # POSITIONS OPERATIONS (2 methods)
    # =========================================================================

    async def positions_total(self) -> int:
        """Get total number of open positions (async)."""
        ...

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Position, ...] | None:
        """Get open positions with optional filters (async)."""
        ...

    # =========================================================================
    # ORDERS OPERATIONS (2 methods)
    # =========================================================================

    async def orders_total(self) -> int:
        """Get total number of pending orders (async)."""
        ...

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get pending orders with optional filters (async)."""
        ...

    # =========================================================================
    # HISTORY OPERATIONS (4 methods)
    # =========================================================================

    async def history_orders_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical orders in date range (async)."""
        ...

    async def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get historical orders with filters (async)."""
        ...

    async def history_deals_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical deals in date range (async)."""
        ...

    async def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Deal, ...] | None:
        """Get historical deals with filters (async)."""
        ...

    # =========================================================================
    # MARKET DEPTH (DOM) OPERATIONS (3 methods)
    # =========================================================================

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) for a symbol (async)."""
        ...

    async def market_book_get(
        self, symbol: str
    ) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol (async)."""
        ...

    async def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol (async)."""
        ...


# Backwards compatibility aliases (deprecated, will be removed)
SyncClientProtocol = MT5Protocol
AsyncClientProtocol = AsyncMT5Protocol
