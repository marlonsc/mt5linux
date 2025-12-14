"""
Protocol definitions for mt5linux.

This module defines structural typing interfaces using Python 3.8+ Protocol.
These protocols enable duck typing with static type checking support.

Protocols define what methods/attributes an object must have, without
requiring explicit inheritance. This enables:
- Type-safe duck typing
- Better IDE autocomplete
- Runtime type checking with @runtime_checkable

Example:
    >>> from mt5linux.protocols import PositionLike
    >>>
    >>> class MyPosition:
    ...     ticket: int = 12345
    ...     symbol: str = "EURUSD"
    ...     type: int = 0
    ...     volume: float = 0.1
    ...     price_open: float = 1.1000
    ...     sl: float = 1.0950
    ...     tp: float = 1.1100
    ...     profit: float = 50.0
    ...
    >>> pos = MyPosition()
    >>> isinstance(pos, PositionLike)  # True at runtime
    True
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# =============================================================================
# MARKET DATA PROTOCOLS
# =============================================================================


@runtime_checkable
class Tickable(Protocol):
    """
    Protocol for tick-like data structures.

    Any object with these attributes can be used where Tickable is expected.
    This includes MT5 tick tuples, custom tick classes, or pandas rows.
    """

    time: int
    """Unix timestamp in seconds."""

    bid: float
    """Bid price."""

    ask: float
    """Ask price."""

    last: float
    """Last trade price."""

    volume: int
    """Tick volume."""

    time_msc: int
    """Unix timestamp in milliseconds."""

    flags: int
    """Tick flags (see TickFlag enum)."""


@runtime_checkable
class RateBar(Protocol):
    """
    Protocol for OHLCV bar data.

    Compatible with MT5 rates tuples and pandas OHLCV dataframes.
    """

    time: int
    """Bar open time (Unix timestamp)."""

    open: float
    """Open price."""

    high: float
    """High price."""

    low: float
    """Low price."""

    close: float
    """Close price."""

    tick_volume: int
    """Tick volume."""

    spread: int
    """Spread in points."""

    real_volume: int
    """Real volume (if available)."""


@runtime_checkable
class Tradeable(Protocol):
    """
    Protocol for tradeable instruments (symbols).

    Minimal interface for anything that can be traded.
    """

    symbol: str
    """Symbol name (e.g., 'EURUSD')."""

    bid: float
    """Current bid price."""

    ask: float
    """Current ask price."""


# =============================================================================
# ORDER/POSITION PROTOCOLS
# =============================================================================


@runtime_checkable
class OrderLike(Protocol):
    """
    Protocol for order-like objects.

    Represents pending or active orders.
    """

    ticket: int
    """Unique order ticket."""

    symbol: str
    """Trading symbol."""

    type: int
    """Order type (see OrderType enum)."""

    volume: float
    """Order volume in lots."""

    price: float
    """Order price."""

    sl: float
    """Stop loss price (0 if not set)."""

    tp: float
    """Take profit price (0 if not set)."""


@runtime_checkable
class PositionLike(Protocol):
    """
    Protocol for position-like objects.

    Represents open trading positions.
    """

    ticket: int
    """Unique position ticket."""

    symbol: str
    """Trading symbol."""

    type: int
    """Position type (0=buy, 1=sell)."""

    volume: float
    """Position volume in lots."""

    price_open: float
    """Position opening price."""

    sl: float
    """Stop loss price (0 if not set)."""

    tp: float
    """Take profit price (0 if not set)."""

    profit: float
    """Current unrealized profit."""


@runtime_checkable
class DealLike(Protocol):
    """
    Protocol for deal-like objects.

    Represents executed trades in history.
    """

    ticket: int
    """Unique deal ticket."""

    order: int
    """Order ticket that triggered this deal."""

    symbol: str
    """Trading symbol."""

    type: int
    """Deal type (see DealType enum)."""

    volume: float
    """Deal volume in lots."""

    price: float
    """Deal price."""

    profit: float
    """Deal profit."""

    commission: float
    """Commission charged."""

    swap: float
    """Swap charged."""


# =============================================================================
# ACCOUNT PROTOCOLS
# =============================================================================


@runtime_checkable
class AccountLike(Protocol):
    """
    Protocol for account information.

    Represents trading account state.
    """

    login: int
    """Account number."""

    balance: float
    """Account balance."""

    equity: float
    """Account equity (balance + floating P/L)."""

    margin: float
    """Used margin."""

    margin_free: float
    """Free margin available."""

    currency: str
    """Account currency (e.g., 'USD')."""


@runtime_checkable
class AccountFullInfo(AccountLike, Protocol):
    """
    Extended account information protocol.

    Includes additional trading parameters.
    """

    leverage: int
    """Account leverage."""

    trade_allowed: bool
    """Whether trading is allowed."""

    trade_expert: bool
    """Whether EA trading is allowed."""

    profit: float
    """Current floating profit."""

    margin_level: float
    """Margin level percentage."""


# =============================================================================
# TERMINAL/CONNECTION PROTOCOLS
# =============================================================================


@runtime_checkable
class TerminalLike(Protocol):
    """
    Protocol for terminal information.

    Represents the MetaTrader terminal state.
    """

    connected: bool
    """Whether terminal is connected to broker."""

    trade_allowed: bool
    """Whether trading is allowed."""

    build: int
    """Terminal build number."""

    company: str
    """Broker company name."""

    name: str
    """Terminal name."""


@runtime_checkable
class ConnectionInfo(Protocol):
    """
    Protocol for connection information.

    Represents the rpyc connection state.
    """

    host: str
    """Server host."""

    port: int
    """Server port."""

    connected: bool
    """Whether connected to server."""


# =============================================================================
# TRADE REQUEST/RESULT PROTOCOLS
# =============================================================================


@runtime_checkable
class TradeRequestLike(Protocol):
    """
    Protocol for trade request objects.

    Represents a request to execute a trade.
    """

    action: int
    """Trade action (see TradeAction enum)."""

    symbol: str
    """Trading symbol."""

    volume: float
    """Trade volume in lots."""


@runtime_checkable
class TradeResultLike(Protocol):
    """
    Protocol for trade result objects.

    Represents the result of a trade operation.
    """

    retcode: int
    """Return code (see TradeRetcode enum)."""

    deal: int
    """Deal ticket (if executed)."""

    order: int
    """Order ticket."""


# =============================================================================
# SYMBOL INFO PROTOCOLS
# =============================================================================


@runtime_checkable
class SymbolInfoLike(Protocol):
    """
    Protocol for symbol information.

    Represents basic symbol properties.
    """

    name: str
    """Symbol name."""

    bid: float
    """Current bid price."""

    ask: float
    """Current ask price."""

    spread: int
    """Current spread in points."""

    digits: int
    """Price decimal places."""

    trade_mode: int
    """Trading mode (see SymbolTradeMode enum)."""


@runtime_checkable
class SymbolFullInfo(SymbolInfoLike, Protocol):
    """
    Extended symbol information protocol.

    Includes trading parameters.
    """

    trade_contract_size: float
    """Contract size."""

    volume_min: float
    """Minimum volume."""

    volume_max: float
    """Maximum volume."""

    volume_step: float
    """Volume step."""

    swap_long: float
    """Long swap rate."""

    swap_short: float
    """Short swap rate."""


# =============================================================================
# UTILITY PROTOCOLS
# =============================================================================


@runtime_checkable
class HasTicket(Protocol):
    """Protocol for objects with a ticket attribute."""

    ticket: int


@runtime_checkable
class HasSymbol(Protocol):
    """Protocol for objects with a symbol attribute."""

    symbol: str


@runtime_checkable
class HasVolume(Protocol):
    """Protocol for objects with a volume attribute."""

    volume: float


@runtime_checkable
class ProfitBearing(Protocol):
    """Protocol for objects that track profit."""

    profit: float

    @property
    def is_profitable(self) -> bool:
        """Check if profit is positive."""
        ...


# =============================================================================
# RESILIENT SERVER PROTOCOLS
# =============================================================================


@runtime_checkable
class Startable(Protocol):
    """
    Protocol for components that can be started and stopped.

    Used by resilient_server for lifecycle management of components
    like ProcessSupervisor, HealthChecker, ConnectionWatchdog.
    """

    def start(self) -> None:
        """Start the component."""
        ...

    def stop(self) -> None:
        """Stop the component."""
        ...


@runtime_checkable
class HealthProvider(Protocol):
    """
    Protocol for components that provide health status.

    Used by resilient_server for health check functionality
    and Kubernetes readiness/liveness probes.
    """

    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        ...

    def get_health_status(self) -> dict[str, Any]:
        """Get detailed health status."""
        ...


# =============================================================================
# MT5 CLIENT PROTOCOL
# =============================================================================


class MT5Client(Protocol):
    """
    Protocol for MT5 client interface.

    Defines the expected interface for any MT5 client implementation.
    This allows for testing with mock clients.
    """

    def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        """Initialize connection to MT5 terminal."""
        ...

    def shutdown(self) -> None:
        """Shutdown connection to MT5 terminal."""
        ...

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 version info."""
        ...

    def last_error(self) -> tuple[int, str]:
        """Get last error code and description."""
        ...

    def account_info(self) -> Any:
        """Get account information."""
        ...

    def terminal_info(self) -> Any:
        """Get terminal information."""
        ...

    def symbol_info(self, symbol: str) -> Any:
        """Get symbol information."""
        ...

    def symbol_info_tick(self, symbol: str) -> Any:
        """Get current tick for symbol."""
        ...

    def order_send(self, request: dict[str, Any]) -> Any:
        """Send trade request."""
        ...

    def positions_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get open positions."""
        ...

    def orders_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get pending orders."""
        ...


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Market data
    "Tickable",
    "RateBar",
    "Tradeable",
    # Orders/Positions
    "OrderLike",
    "PositionLike",
    "DealLike",
    # Account
    "AccountLike",
    "AccountFullInfo",
    # Terminal
    "TerminalLike",
    "ConnectionInfo",
    # Trade
    "TradeRequestLike",
    "TradeResultLike",
    # Symbol
    "SymbolInfoLike",
    "SymbolFullInfo",
    # Utility
    "HasTicket",
    "HasSymbol",
    "HasVolume",
    "ProfitBearing",
    # Client
    "MT5Client",
    # Resilient server
    "Startable",
    "HealthProvider",
]
