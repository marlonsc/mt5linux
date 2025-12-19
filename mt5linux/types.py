"""Type definitions for mt5linux.

All type definitions organized in a single container class for:
- Clean namespace (no loose code)
- Logical grouping by category
- Easy discovery via IDE autocomplete
- Single import: `from mt5linux.types import MT5Types`

Hierarchy Level: 1
- Dependencies: MT5Constants (Level 0) - used via enums in type definitions
- Used by: MT5Models, MT5Utilities, client.py, server.py

Usage:
    >>> from mt5linux.types import MT5Types
    >>> def process_rates(data: MT5Types.RatesArray) -> None: ...
    >>> def create_request() -> MT5Types.OrderRequestDict: ...

"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict, TypeVar

import numpy as np
from numpy.typing import NDArray

T = TypeVar("T")


class MT5Types:
    """MetaTrader5 type definitions container.

    All MT5 type aliases and TypedDicts organized in one class.

    Categories:
    - Array types: RatesArray, TicksArray
    - Dict types: OrderRequestDict, TickDict, RateDict
    - Function types: MT5Function
    - JSON types: JSONPrimitive, JSONValue

    Note: MT5Protocol and AsyncMT5Protocol are in mt5linux.protocols module.

    """

    # =========================================================================
    # ARRAY TYPE ALIASES
    # =========================================================================

    type RatesArray = NDArray[np.void]
    """NumPy array for OHLCV rate data from copy_rates_* functions."""

    type TicksArray = NDArray[np.void]
    """NumPy array for tick data from copy_ticks_* functions."""

    # =========================================================================
    # FUNCTION TYPE ALIASES
    # =========================================================================

    type MT5Function = Callable[..., object]
    """Generic MT5 function callable type."""

    # =========================================================================
    # JSON TYPE ALIASES
    # =========================================================================

    type JSONPrimitive = str | int | float | bool | None
    """Primitive JSON-compatible values."""

    type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]
    """Recursive JSON-compatible value type (strict typing, no Any)."""

    # =========================================================================
    # TYPED DICTS
    # =========================================================================

    class OrderRequestDict(TypedDict, total=False):
        """MT5 order request dictionary structure.

        Used for order_check() and order_send() functions.
        All fields except action and symbol are optional.

        """

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
        """MT5 tick data structure.

        Represents a single price tick from symbol_info_tick().

        """

        time: int
        bid: float
        ask: float
        last: float
        volume: int
        time_msc: int
        flags: int
        volume_real: float

    class RateDict(TypedDict):
        """MT5 OHLCV bar structure.

        Represents a single bar from copy_rates_* functions.

        """

        time: int
        open: float
        high: float
        low: float
        close: float
        tick_volume: int
        spread: int
        real_volume: int
