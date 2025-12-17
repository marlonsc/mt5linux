"""Client protocol definitions for mt5linux.

Defines abstract interfaces for both sync and async MT5 clients.
Ensures API consistency across implementations.

Hierarchy Level: 2
- Imports: MT5Types (Level 1) - for type aliases
- Used by: client.py, async_client.py (implementation validation)

Protocols are extracted from async_client.py (source of truth) and ensure
that both sync and async implementations have identical method signatures.

Uses @runtime_checkable for both static (mypy/pyright) and runtime (isinstance)
validation of client implementations.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from numpy import np
    from numpy.typing import NDArray

    from mt5linux.models import MT5Models

from mt5linux.types import MT5Types

# Type alias for convenience (single source of truth)
JSONValue = MT5Types.JSONValue


@runtime_checkable
class SyncClientProtocol(Protocol):
    """Protocol for synchronous MT5 client implementations.

    Defines the complete interface for blocking MT5 operations.
    All implementations must provide these exact signatures.

    All signatures extracted from async_client.py (source of truth).
    Implements both static typing (mypy) and runtime checking (isinstance).

    """

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    def connect(self) -> None:
        """Connect to gRPC server.

        Thread-safe: uses threading.Lock to prevent race conditions.

        """
        ...

    def disconnect(self) -> None:
        """Disconnect from gRPC server."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to gRPC server.

        Returns:
            True if connected, False otherwise.

        """
        ...

    # =========================================================================
    # TERMINAL OPERATIONS
    # =========================================================================

    def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        init_timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection.

        Args:
            path: Path to MT5 terminal executable.
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            init_timeout: Connection timeout in milliseconds.
            portable: Use portable mode.

        Returns:
            True if initialization successful, False otherwise.

        """
        ...

    def login(
        self,
        login: int,
        password: str,
        server: str,
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
        """Shutdown MT5 terminal connection.

        No-op if not connected (graceful degradation).

        """
        ...

    def health_check(self) -> dict[str, bool | int | str]:
        """Check MT5 service health status.

        Returns:
            Dict with health status fields:
            - healthy: bool - Overall service health
            - mt5_available: bool - MT5 module loaded
            - connected: bool - Terminal connected
            - trade_allowed: bool - Trading enabled
            - build: int - Terminal build number
            - reason: str - Error reason if unhealthy

        """
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
            TerminalInfo object or None.

        """
        ...

    def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information.

        Returns:
            AccountInfo object or None.

        """
        ...

    # =========================================================================
    # SYMBOL OPERATIONS
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of available symbols.

        Returns:
            Total count of symbols.

        """
        ...

    def symbols_get(
        self, group: str | None = None
    ) -> list[dict[str, JSONValue]] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern.

        Returns:
            List of symbol dictionaries or None.

        """
        ...

    def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            SymbolInfo object or None.

        """
        ...

    def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Tick object or None.

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
    # MARKET DATA OPERATIONS
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
            flags: Copy ticks flags.

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
    # TRADING OPERATIONS
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
            OrderCheckResult object or None.

        """
        ...

    def order_send(self, request: dict[str, JSONValue]) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary.

        Returns:
            OrderResult object or None.

        """
        ...

    # =========================================================================
    # POSITIONS OPERATIONS
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
    ) -> list[dict[str, JSONValue]] | None:
        """Get open positions with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific position ticket.

        Returns:
            List of position dictionaries or None.

        """
        ...

    # =========================================================================
    # ORDERS OPERATIONS
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
    ) -> list[dict[str, JSONValue]] | None:
        """Get pending orders with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific order ticket.

        Returns:
            List of order dictionaries or None.

        """
        ...

    # =========================================================================
    # HISTORY OPERATIONS
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
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical orders with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific order ticket.
            position: Position ID filter.

        Returns:
            List of historical order dictionaries or None.

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
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical deals with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific deal ticket.
            position: Position ID filter.

        Returns:
            List of historical deal dictionaries or None.

        """
        ...

    # =========================================================================
    # MARKET DEPTH (DOM) OPERATIONS
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

    def market_book_get(self, symbol: str) -> list[dict[str, JSONValue]] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior market_book_add call.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            List of market depth entries or None.

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
class AsyncClientProtocol(Protocol):
    """Protocol for asynchronous MT5 client implementations.

    Defines the complete interface for async MT5 operations.
    All async implementations must provide these exact signatures.

    All signatures extracted from async_client.py (source of truth).
    Identical to SyncClientProtocol but with async/await keywords.

    """

    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================

    async def connect(self) -> None:
        """Connect to gRPC server (async version)."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from gRPC server (async version)."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to gRPC server.

        Returns:
            True if connected, False otherwise.

        """
        ...

    # =========================================================================
    # TERMINAL OPERATIONS
    # =========================================================================

    async def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        init_timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection (async version)."""
        ...

    async def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account (async version)."""
        ...

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection (async version)."""
        ...

    async def health_check(self) -> dict[str, bool | int | str]:
        """Check MT5 service health status (async version)."""
        ...

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version (async version)."""
        ...

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description (async version)."""
        ...

    async def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal information (async version)."""
        ...

    async def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information (async version)."""
        ...

    # =========================================================================
    # SYMBOL OPERATIONS
    # =========================================================================

    async def symbols_total(self) -> int:
        """Get total number of available symbols (async version)."""
        ...

    async def symbols_get(
        self, group: str | None = None
    ) -> list[dict[str, JSONValue]] | None:
        """Get available symbols with optional group filter (async version)."""
        ...

    async def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information (async version)."""
        ...

    async def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol (async version)."""
        ...

    async def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch (async version)."""
        ...

    # =========================================================================
    # MARKET DATA OPERATIONS
    # =========================================================================

    async def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a specific date (async version)."""
        ...

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a bar position (async version)."""
        ...

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates in a date range (async version)."""
        ...

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data from a specific date (async version)."""
        ...

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data in a date range (async version)."""
        ...

    # =========================================================================
    # TRADING OPERATIONS
    # =========================================================================

    async def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin required for an order (async version)."""
        ...

    async def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate potential profit for an order (async version)."""
        ...

    async def order_check(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderCheckResult | None:
        """Check order validity without sending (async version)."""
        ...

    async def order_send(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5 (async version)."""
        ...

    # =========================================================================
    # POSITIONS OPERATIONS
    # =========================================================================

    async def positions_total(self) -> int:
        """Get total number of open positions (async version)."""
        ...

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get open positions with optional filters (async version)."""
        ...

    # =========================================================================
    # ORDERS OPERATIONS
    # =========================================================================

    async def orders_total(self) -> int:
        """Get total number of pending orders (async version)."""
        ...

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get pending orders with optional filters (async version)."""
        ...

    # =========================================================================
    # HISTORY OPERATIONS
    # =========================================================================

    async def history_orders_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical orders in date range (async version)."""
        ...

    async def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical orders with filters (async version)."""
        ...

    async def history_deals_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical deals in date range (async version)."""
        ...

    async def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical deals with filters (async version)."""
        ...

    # =========================================================================
    # MARKET DEPTH (DOM) OPERATIONS
    # =========================================================================

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) for a symbol (async version)."""
        ...

    async def market_book_get(self, symbol: str) -> list[dict[str, JSONValue]] | None:
        """Get market depth (DOM) data for a symbol (async version)."""
        ...

    async def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol (async version)."""
        ...
