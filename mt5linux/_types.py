"""Type definitions for mt5linux.

Python 3.13+ type aliases and TypedDicts for MetaTrader5 data structures.
These types are compatible with neptor's Pydantic models.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypedDict, runtime_checkable

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


# =============================================================================
# MT5 Module Protocol
# =============================================================================


@runtime_checkable
class MT5ModuleProtocol(Protocol):
    """Protocol defining the MetaTrader5 module interface.

    This allows type-safe calls to the MT5 module without requiring
    the actual MetaTrader5 package to be installed.
    """

    # Terminal operations
    def initialize(
        self,
        path: str | None = ...,
        login: int | None = ...,
        password: str | None = ...,
        server: str | None = ...,
        timeout: int | None = ...,
        portable: bool = ...,
    ) -> bool: ...

    def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = ...,
    ) -> bool: ...

    def shutdown(self) -> None: ...

    def version(self) -> tuple[int, int, str] | None: ...

    def last_error(self) -> tuple[int, str]: ...

    def terminal_info(self) -> Any: ...

    def account_info(self) -> Any: ...

    # Symbol operations
    def symbols_total(self) -> int: ...

    def symbols_get(self, *, group: str | None = ...) -> tuple[Any, ...] | None: ...

    def symbol_info(self, symbol: str) -> Any: ...

    def symbol_info_tick(self, symbol: str) -> Any: ...

    def symbol_select(self, symbol: str, enable: bool = ...) -> bool: ...

    # Market data operations
    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        count: int,
    ) -> Any: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> Any: ...

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        flags: int,
    ) -> Any: ...

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int,
    ) -> Any: ...

    # Trading operations
    def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None: ...

    def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None: ...

    def order_check(self, request: dict[str, Any]) -> Any: ...

    def order_send(self, request: dict[str, Any]) -> Any: ...

    # Position operations
    def positions_total(self) -> int: ...

    def positions_get(
        self,
        *,
        symbol: str | None = ...,
        group: str | None = ...,
        ticket: int | None = ...,
    ) -> tuple[Any, ...] | None: ...

    # Order operations
    def orders_total(self) -> int: ...

    def orders_get(
        self,
        *,
        symbol: str | None = ...,
        group: str | None = ...,
        ticket: int | None = ...,
    ) -> tuple[Any, ...] | None: ...

    # History operations
    def history_orders_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None: ...

    def history_orders_get(
        self,
        *,
        date_from: datetime | None = ...,
        date_to: datetime | None = ...,
        group: str | None = ...,
        ticket: int | None = ...,
        position: int | None = ...,
    ) -> tuple[Any, ...] | None: ...

    def history_deals_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None: ...

    def history_deals_get(
        self,
        *,
        date_from: datetime | None = ...,
        date_to: datetime | None = ...,
        group: str | None = ...,
        ticket: int | None = ...,
        position: int | None = ...,
    ) -> tuple[Any, ...] | None: ...


# Type alias for MT5 functions
MT5Function: TypeAlias = Callable[..., Any]

# Array types for OHLCV and tick data
RatesArray: TypeAlias = "NDArray[np.void]"
TicksArray: TypeAlias = "NDArray[np.void]"


class OrderRequestDict(TypedDict, total=False):
    """MT5 order request dictionary structure."""

    action: int
    symbol: str
    volume: float
    type: int
    price: float
    sl: float
    tp: float
    deviation: int
    magic: int
    comment: str
    type_time: int
    expiration: int
    type_filling: int
    position: int
    position_by: int


class TickDict(TypedDict):
    """MT5 tick data structure."""

    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float


class RateDict(TypedDict):
    """MT5 OHLCV bar structure."""

    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


# Trade action constants
TRADE_ACTION_DEAL: int = 1
TRADE_ACTION_PENDING: int = 5
TRADE_ACTION_SLTP: int = 6
TRADE_ACTION_MODIFY: int = 7
TRADE_ACTION_REMOVE: int = 8
TRADE_ACTION_CLOSE_BY: int = 10

# Order type constants
ORDER_TYPE_BUY: int = 0
ORDER_TYPE_SELL: int = 1
ORDER_TYPE_BUY_LIMIT: int = 2
ORDER_TYPE_SELL_LIMIT: int = 3
ORDER_TYPE_BUY_STOP: int = 4
ORDER_TYPE_SELL_STOP: int = 5
ORDER_TYPE_BUY_STOP_LIMIT: int = 6
ORDER_TYPE_SELL_STOP_LIMIT: int = 7
ORDER_TYPE_CLOSE_BY: int = 8

# Order filling constants
ORDER_FILLING_FOK: int = 0
ORDER_FILLING_IOC: int = 1
ORDER_FILLING_RETURN: int = 2

# Order time constants
ORDER_TIME_GTC: int = 0
ORDER_TIME_DAY: int = 1
ORDER_TIME_SPECIFIED: int = 2
ORDER_TIME_SPECIFIED_DAY: int = 3

# Trade return codes
TRADE_RETCODE_DONE: int = 10009
TRADE_RETCODE_REQUOTE: int = 10004
TRADE_RETCODE_ERROR: int = 10006
TRADE_RETCODE_REJECT: int = 10006
TRADE_RETCODE_CANCEL: int = 10007
TRADE_RETCODE_PLACED: int = 10008
TRADE_RETCODE_DONE_PARTIAL: int = 10010

# Timeframe constants
TIMEFRAME_M1: int = 1
TIMEFRAME_M2: int = 2
TIMEFRAME_M3: int = 3
TIMEFRAME_M4: int = 4
TIMEFRAME_M5: int = 5
TIMEFRAME_M6: int = 6
TIMEFRAME_M10: int = 10
TIMEFRAME_M12: int = 12
TIMEFRAME_M15: int = 15
TIMEFRAME_M20: int = 20
TIMEFRAME_M30: int = 30
TIMEFRAME_H1: int = 16385
TIMEFRAME_H2: int = 16386
TIMEFRAME_H3: int = 16387
TIMEFRAME_H4: int = 16388
TIMEFRAME_H6: int = 16390
TIMEFRAME_H8: int = 16392
TIMEFRAME_H12: int = 16396
TIMEFRAME_D1: int = 16408
TIMEFRAME_W1: int = 32769
TIMEFRAME_MN1: int = 49153

# Copy ticks flags
COPY_TICKS_ALL: int = -1
COPY_TICKS_INFO: int = 1
COPY_TICKS_TRADE: int = 2
