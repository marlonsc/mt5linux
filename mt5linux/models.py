"""Pydantic 2 models for mt5linux.

Type-safe models for MetaTrader5 trading data structures.
Compatible with neptor's MT5Bridge models.

Hierarchy Level: 2
- Imports: MT5Constants (Level 0), MT5Config (Level 1)
- Used by: client.py, server.py (optional)

Usage:
    from mt5linux.models import MT5Models

    # Create order request
    request = MT5Models.OrderRequest(...)

    # Parse MT5 response
    result = MT5Models.OrderResult.from_mt5(response)
"""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field

from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants

# Default config instance for model defaults
_config = MT5Config()


class MT5Models:
    """Container for all MT5 Pydantic models.

    All models are nested for clean namespace:
    - Base: Base class for MT5 data models
    - OrderRequest: Order request with validation
    - OrderResult: Order execution result
    - AccountInfo: Account information
    - SymbolInfo: Symbol information
    - Position: Open position
    - Tick: Price tick
    """

    class Base(BaseModel):
        """Base class for MT5 data models.

        Provides a generic `from_mt5()` factory method that handles:
        - None input (returns None)
        - Objects with `_asdict()` method (namedtuples)
        - Objects with attributes (MT5 objects)

        Subclasses can override `from_mt5()` for custom handling.
        """

        model_config = ConfigDict(frozen=True, from_attributes=True)

        @classmethod
        def from_mt5(cls, obj: Any) -> Self | None:
            """Create model from MT5 object.

            Args:
                obj: MT5 object, namedtuple, or dict.

            Returns:
                Model instance or None if obj is None.

            """
            if obj is None:
                return None
            # Check for real namedtuple (_asdict returns actual dict)
            if hasattr(obj, "_asdict") and callable(getattr(obj, "_asdict", None)):
                result = obj._asdict()
                if isinstance(result, dict):
                    return cls.model_validate(result)
            # Use from_attributes for objects with direct attribute access
            return cls.model_validate(obj)

    class OrderRequest(BaseModel):
        """MT5 order request with validation.

        Example:
            >>> request = MT5Models.OrderRequest(
            ...     action=MT5Constants.TradeAction.DEAL,
            ...     symbol="EURUSD",
            ...     volume=0.1,
            ...     type=MT5Constants.OrderType.BUY,
            ...     price=1.1000,
            ... )
            >>> mt5.order_send(request.to_mt5_request())

        """

        model_config = ConfigDict(frozen=True, use_enum_values=True)

        action: MT5Constants.TradeAction
        symbol: str
        volume: float = Field(gt=0, le=1000)
        type: MT5Constants.OrderType
        price: float = Field(ge=0, default=0.0)
        sl: float = Field(ge=0, default=0.0)
        tp: float = Field(ge=0, default=0.0)
        deviation: int = Field(ge=0, default=_config.order_deviation)
        magic: int = Field(ge=0, default=_config.order_magic)
        comment: str = Field(max_length=31, default="")
        type_time: MT5Constants.OrderTime = Field(default=_config.order_time)
        expiration: datetime | None = None
        type_filling: MT5Constants.OrderFilling = Field(default=_config.order_filling)
        position: int = Field(ge=0, default=0)
        position_by: int = Field(ge=0, default=0)

        @computed_field  # type: ignore[prop-decorator]
        @property
        def is_market_order(self) -> bool:
            """Check if this is a market order."""
            market_types = {MT5Constants.OrderType.BUY, MT5Constants.OrderType.SELL}
            return self.type in market_types

        def to_mt5_request(self) -> dict[str, Any]:
            """Export to MT5 API format.

            Returns dict with only non-default, non-zero values for optional fields.
            """
            d: dict[str, Any] = {
                "action": self.action,
                "symbol": self.symbol,
                "volume": self.volume,
                "type": self.type,
                "price": self.price,
                "deviation": self.deviation,
                "magic": self.magic,
                "comment": self.comment,
                "type_time": self.type_time,
                "type_filling": self.type_filling,
            }
            if self.sl > 0:
                d["sl"] = self.sl
            if self.tp > 0:
                d["tp"] = self.tp
            if self.position > 0:
                d["position"] = self.position
            if self.position_by > 0:
                d["position_by"] = self.position_by
            if self.expiration:
                d["expiration"] = int(self.expiration.timestamp())
            return d

    class OrderResult(Base):
        """MT5 order execution result.

        Example:
            >>> result = mt5.order_send(request)
            >>> order_result = MT5Models.OrderResult.from_mt5(result)
            >>> if order_result.is_success:
            ...     print(f"Order placed: {order_result.order}")

        """

        retcode: int
        deal: int = 0
        order: int = 0
        volume: float = 0.0
        price: float = 0.0
        bid: float = 0.0
        ask: float = 0.0
        comment: str = ""
        request_id: int = 0
        retcode_external: int = 0

        @computed_field  # type: ignore[prop-decorator]
        @property
        def is_success(self) -> bool:
            """Check if order was successful."""
            return self.retcode == MT5Constants.TradeRetcode.DONE

        @computed_field  # type: ignore[prop-decorator]
        @property
        def is_partial(self) -> bool:
            """Check if order was partially filled."""
            return self.retcode == MT5Constants.TradeRetcode.DONE_PARTIAL

        @classmethod
        def from_mt5(cls, result: Any) -> Self | None:
            """Create from MT5 OrderSendResult.

            Special handling: returns error result instead of None for None input.
            """
            if result is None:
                return cls(
                    retcode=MT5Constants.TradeRetcode.ERROR,
                    comment="No result from MT5",
                )
            return super().from_mt5(result)

    class AccountInfo(Base):
        """MT5 account information."""

        login: int
        trade_mode: int = 0
        leverage: int = 0
        limit_orders: int = 0
        margin_so_mode: int = 0
        trade_allowed: bool = False
        trade_expert: bool = False
        margin_mode: int = 0
        currency_digits: int = 2
        fifo_close: bool = False
        balance: float = 0.0
        credit: float = 0.0
        profit: float = 0.0
        equity: float = 0.0
        margin: float = 0.0
        margin_free: float = 0.0
        margin_level: float = 0.0
        margin_so_call: float = 0.0
        margin_so_so: float = 0.0
        margin_initial: float = 0.0
        margin_maintenance: float = 0.0
        assets: float = 0.0
        liabilities: float = 0.0
        commission_blocked: float = 0.0
        name: str = ""
        server: str = ""
        currency: str = "USD"
        company: str = ""

    class SymbolInfo(Base):
        """MT5 symbol information (subset of commonly used fields)."""

        name: str
        visible: bool = False
        select: bool = False
        time: int = 0
        digits: int = 0
        spread: int = 0
        spread_float: bool = False
        trade_mode: int = 0
        trade_calc_mode: int = 0
        trade_stops_level: int = 0
        trade_freeze_level: int = 0
        bid: float = 0.0
        ask: float = 0.0
        last: float = 0.0
        volume: float = 0.0
        point: float = 0.0
        trade_tick_value: float = 0.0
        trade_tick_size: float = 0.0
        trade_contract_size: float = 0.0
        volume_min: float = 0.0
        volume_max: float = 0.0
        volume_step: float = 0.0
        currency_base: str = ""
        currency_profit: str = ""
        currency_margin: str = ""
        description: str = ""
        path: str = ""

    class Position(Base):
        """MT5 open position."""

        ticket: int
        time: int = 0
        time_msc: int = 0
        time_update: int = 0
        time_update_msc: int = 0
        type: int = 0
        magic: int = 0
        identifier: int = 0
        reason: int = 0
        volume: float = 0.0
        price_open: float = 0.0
        sl: float = 0.0
        tp: float = 0.0
        price_current: float = 0.0
        swap: float = 0.0
        profit: float = 0.0
        symbol: str = ""
        comment: str = ""
        external_id: str = ""

    class Tick(Base):
        """MT5 price tick."""

        time: int
        bid: float = 0.0
        ask: float = 0.0
        last: float = 0.0
        volume: int = 0
        time_msc: int = 0
        flags: int = 0
        volume_real: float = 0.0

    class Order(Base):
        """MT5 pending order information.

        Represents orders in the pending state (not yet executed).
        Also used for historical orders via history_orders_get().
        """

        ticket: int
        time_setup: int = 0
        time_setup_msc: int = 0
        time_done: int = 0
        time_done_msc: int = 0
        time_expiration: int = 0
        type: int = 0
        type_time: int = 0
        type_filling: int = 0
        state: int = 0
        magic: int = 0
        position_id: int = 0
        position_by_id: int = 0
        reason: int = 0
        volume_initial: float = 0.0
        volume_current: float = 0.0
        price_open: float = 0.0
        sl: float = 0.0
        tp: float = 0.0
        price_current: float = 0.0
        price_stoplimit: float = 0.0
        symbol: str = ""
        comment: str = ""
        external_id: str = ""

    class Deal(Base):
        """MT5 historical deal information.

        Represents executed trades from history_deals_get().
        """

        ticket: int
        order: int = 0
        time: int = 0
        time_msc: int = 0
        type: int = 0
        entry: int = 0
        magic: int = 0
        position_id: int = 0
        reason: int = 0
        volume: float = 0.0
        price: float = 0.0
        commission: float = 0.0
        swap: float = 0.0
        profit: float = 0.0
        fee: float = 0.0
        symbol: str = ""
        comment: str = ""
        external_id: str = ""

    class BookEntry(Base):
        """MT5 market depth (DOM) entry.

        Represents a single entry from market_book_get().
        """

        type: int
        price: float = 0.0
        volume: float = 0.0
        volume_real: float = 0.0

    class TerminalInfo(Base):
        """MT5 terminal information.

        Represents terminal state from terminal_info().
        Contains connection status, permissions, and path information.
        """

        community_account: bool = False
        community_connection: bool = False
        connected: bool = False
        dlls_allowed: bool = False
        trade_allowed: bool = False
        tradeapi_disabled: bool = False
        email_enabled: bool = False
        ftp_enabled: bool = False
        notifications_enabled: bool = False
        mqid: bool = False
        build: int = 0
        maxbars: int = 0
        codepage: int = 0
        ping_last: int = 0
        community_balance: float = 0.0
        retransmission: float = 0.0
        company: str = ""
        name: str = ""
        language: str = ""
        path: str = ""
        data_path: str = ""
        commondata_path: str = ""
