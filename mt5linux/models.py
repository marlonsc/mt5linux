"""Pydantic 2 models for mt5linux.

Type-safe models for MetaTrader5 trading data structures.
Compatible with neptor's MT5Bridge models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mt5linux.enums import (
    OrderFilling,
    OrderTime,
    OrderType,
    TradeAction,
    TradeRetcode,
)


class OrderRequest(BaseModel):
    """MT5 order request with validation.

    Example:
        >>> request = OrderRequest(
        ...     action=TradeAction.DEAL,
        ...     symbol="EURUSD",
        ...     volume=0.1,
        ...     type=OrderType.BUY,
        ...     price=1.1000,
        ... )
        >>> mt5.order_send(request.to_dict())
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    action: TradeAction
    symbol: str
    volume: float = Field(gt=0, le=1000)
    type: OrderType
    price: float = Field(ge=0, default=0.0)
    sl: float = Field(ge=0, default=0.0)
    tp: float = Field(ge=0, default=0.0)
    deviation: int = Field(ge=0, default=20)
    magic: int = Field(ge=0, default=0)
    comment: str = Field(max_length=31, default="")
    type_time: OrderTime = OrderTime.GTC
    expiration: datetime | None = None
    type_filling: OrderFilling = OrderFilling.FOK
    position: int = Field(ge=0, default=0)
    position_by: int = Field(ge=0, default=0)

    @property
    def is_market_order(self) -> bool:
        """Check if this is a market order."""
        return self.type in {OrderType.BUY, OrderType.SELL}

    def to_dict(self) -> dict[str, Any]:
        """Convert to MT5 API request dict."""
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


class OrderResult(BaseModel):
    """MT5 order execution result.

    Example:
        >>> result = mt5.order_send(request)
        >>> order_result = OrderResult.from_mt5(result)
        >>> if order_result.is_success:
        ...     print(f"Order placed: {order_result.order}")
    """

    model_config = ConfigDict(frozen=True)

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

    @property
    def is_success(self) -> bool:
        """Check if order was successful."""
        return self.retcode == TradeRetcode.DONE

    @property
    def is_partial(self) -> bool:
        """Check if order was partially filled."""
        return self.retcode == TradeRetcode.DONE_PARTIAL

    @classmethod
    def from_mt5(cls, result: Any) -> OrderResult:
        """Create from MT5 OrderSendResult."""
        if result is None:
            return cls(retcode=TradeRetcode.ERROR, comment="No result from MT5")
        return cls(
            retcode=result.retcode,
            deal=result.deal,
            order=result.order,
            volume=result.volume,
            price=result.price,
            bid=result.bid,
            ask=result.ask,
            comment=result.comment,
            request_id=result.request_id,
            retcode_external=getattr(result, "retcode_external", 0),
        )


class AccountInfo(BaseModel):
    """MT5 account information."""

    model_config = ConfigDict(frozen=True)

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

    @classmethod
    def from_mt5(cls, info: Any) -> AccountInfo:
        """Create from MT5 AccountInfo."""
        if info is None:
            return cls(login=0)
        return cls(
            login=info.login,
            trade_mode=info.trade_mode,
            leverage=info.leverage,
            limit_orders=info.limit_orders,
            margin_so_mode=info.margin_so_mode,
            trade_allowed=info.trade_allowed,
            trade_expert=info.trade_expert,
            margin_mode=info.margin_mode,
            currency_digits=info.currency_digits,
            fifo_close=info.fifo_close,
            balance=info.balance,
            credit=info.credit,
            profit=info.profit,
            equity=info.equity,
            margin=info.margin,
            margin_free=info.margin_free,
            margin_level=info.margin_level,
            margin_so_call=info.margin_so_call,
            margin_so_so=info.margin_so_so,
            margin_initial=info.margin_initial,
            margin_maintenance=info.margin_maintenance,
            assets=info.assets,
            liabilities=info.liabilities,
            commission_blocked=info.commission_blocked,
            name=info.name,
            server=info.server,
            currency=info.currency,
            company=info.company,
        )


class SymbolInfo(BaseModel):
    """MT5 symbol information (subset of commonly used fields)."""

    model_config = ConfigDict(frozen=True)

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

    @classmethod
    def from_mt5(cls, info: Any) -> SymbolInfo:
        """Create from MT5 SymbolInfo."""
        if info is None:
            return cls(name="")
        return cls(
            name=info.name,
            visible=info.visible,
            select=info.select,
            time=info.time,
            digits=info.digits,
            spread=info.spread,
            spread_float=info.spread_float,
            trade_mode=info.trade_mode,
            trade_calc_mode=info.trade_calc_mode,
            trade_stops_level=info.trade_stops_level,
            trade_freeze_level=info.trade_freeze_level,
            bid=info.bid,
            ask=info.ask,
            last=info.last,
            volume=info.volume,
            point=info.point,
            trade_tick_value=info.trade_tick_value,
            trade_tick_size=info.trade_tick_size,
            trade_contract_size=info.trade_contract_size,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            currency_base=info.currency_base,
            currency_profit=info.currency_profit,
            currency_margin=info.currency_margin,
            description=info.description,
            path=info.path,
        )


class Position(BaseModel):
    """MT5 open position."""

    model_config = ConfigDict(frozen=True)

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

    @classmethod
    def from_mt5(cls, pos: Any) -> Position:
        """Create from MT5 TradePosition."""
        if pos is None:
            return cls(ticket=0)
        return cls(
            ticket=pos.ticket,
            time=pos.time,
            time_msc=pos.time_msc,
            time_update=pos.time_update,
            time_update_msc=pos.time_update_msc,
            type=pos.type,
            magic=pos.magic,
            identifier=pos.identifier,
            reason=pos.reason,
            volume=pos.volume,
            price_open=pos.price_open,
            sl=pos.sl,
            tp=pos.tp,
            price_current=pos.price_current,
            swap=pos.swap,
            profit=pos.profit,
            symbol=pos.symbol,
            comment=pos.comment,
            external_id=getattr(pos, "external_id", ""),
        )


class Tick(BaseModel):
    """MT5 price tick."""

    model_config = ConfigDict(frozen=True)

    time: int
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    time_msc: int = 0
    flags: int = 0
    volume_real: float = 0.0

    @classmethod
    def from_mt5(cls, tick: Any) -> Tick:
        """Create from MT5 Tick."""
        if tick is None:
            return cls(time=0)
        return cls(
            time=tick.time,
            bid=tick.bid,
            ask=tick.ask,
            last=tick.last,
            volume=tick.volume,
            time_msc=tick.time_msc,
            flags=tick.flags,
            volume_real=tick.volume_real,
        )
