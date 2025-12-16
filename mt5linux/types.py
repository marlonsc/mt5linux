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
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypedDict, runtime_checkable

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


class MT5Types:
    """MetaTrader5 type definitions container.

    All MT5 type aliases, TypedDicts, and Protocols organized in one class.

    Categories:
    - Array types: RatesArray, TicksArray
    - Dict types: OrderRequestDict, TickDict, RateDict
    - Function types: MT5Function
    - Protocols: MT5ModuleProtocol

    Uses MT5Constants for enum values in TypedDicts.
    """

    # =========================================================================
    # ARRAY TYPE ALIASES
    # =========================================================================

    RatesArray: TypeAlias = "NDArray[np.void]"
    """NumPy array for OHLCV rate data from copy_rates_* functions."""

    TicksArray: TypeAlias = "NDArray[np.void]"
    """NumPy array for tick data from copy_ticks_* functions."""

    # =========================================================================
    # FUNCTION TYPE ALIASES
    # =========================================================================

    MT5Function: TypeAlias = Callable[..., Any]
    """Generic MT5 function callable type."""

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

    # =========================================================================
    # PROTOCOLS
    # =========================================================================

    @runtime_checkable
    class ModuleProtocol(Protocol):
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

        def symbols_get(
            self, *, group: str | None = ...
        ) -> tuple[Any, ...] | None: ...

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


