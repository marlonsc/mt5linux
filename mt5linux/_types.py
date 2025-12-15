"""Type definitions for mt5linux.

Python 3.13+ type aliases and TypedDicts for MetaTrader5 data structures.
These types are compatible with neptor's Pydantic models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypedDict

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

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
