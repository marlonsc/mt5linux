"""
Pydantic 2 models for mt5linux.

This module provides validated data models using Pydantic 2 for all
MT5 data structures. These models offer:
- Runtime validation of MT5 API responses
- Type coercion and normalization
- Computed properties for derived values
- Serialization to/from dict for MT5 API compatibility

Example:
    >>> from mt5linux.models import TradeRequestModel, OrderType, TradeAction
    >>>
    >>> # Create validated trade request
    >>> request = TradeRequestModel(
    ...     action=TradeAction.DEAL,
    ...     symbol="EURUSD",
    ...     volume=0.1,
    ...     type=OrderType.BUY,
    ... )
    >>> request.to_mt5_dict()  # Convert to dict for order_send
    {'action': 1, 'symbol': 'EURUSD', 'volume': 0.1, ...}
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from mt5linux.enums import (
    AccountMarginMode,
    AccountTradeMode,
    DealEntry,
    DealReason,
    DealType,
    OrderFilling,
    OrderState,
    OrderTime,
    OrderType,
    PositionReason,
    PositionType,
    TickFlag,
    TradeAction,
    TradeRetcode,
)


# =============================================================================
# CUSTOM TYPES (Annotated validators)
# =============================================================================

# Positive floats for volumes, prices
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]

# Symbol names (uppercase, stripped)
SymbolName = Annotated[str, Field(min_length=1, max_length=32)]


# =============================================================================
# BASE MODEL CONFIGURATION
# =============================================================================


class MT5BaseModel(BaseModel):
    """Base model for all MT5 data structures."""

    model_config = ConfigDict(
        # Allow extra fields (MT5 may add new fields)
        extra="allow",
        # Validate on assignment
        validate_assignment=True,
        # Use enum values in serialization
        use_enum_values=True,
        # Strict mode for better performance
        strict=False,
        # Allow population by field name or alias
        populate_by_name=True,
        # Allow arbitrary types for computed fields
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_mt5(cls, obj: Any) -> Self:
        """
        Create model from MT5 API response object.

        MT5 returns named tuples or objects with _asdict() method.
        This factory handles conversion to Pydantic model.

        Args:
            obj: Raw MT5 API response (named tuple or object with attributes)

        Returns:
            Validated Pydantic model instance
        """
        if obj is None:
            msg = f"Cannot create {cls.__name__} from None"
            raise ValueError(msg)

        # Convert to dict - MT5 objects have _asdict() method
        if hasattr(obj, "_asdict"):
            data = obj._asdict()
        elif hasattr(obj, "__dict__"):
            data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        elif isinstance(obj, dict):
            data = obj
        else:
            # Try attribute access for each field
            data = {}
            for field_name in cls.model_fields:
                if hasattr(obj, field_name):
                    data[field_name] = getattr(obj, field_name)

        return cls.model_validate(data)


# =============================================================================
# TICK MODELS
# =============================================================================


class TickModel(MT5BaseModel):
    """
    Validated tick data model.

    Represents a single price tick from the market.
    """

    time: int = Field(description="Unix timestamp in seconds")
    bid: NonNegativeFloat = Field(description="Bid price")
    ask: NonNegativeFloat = Field(description="Ask price")
    last: NonNegativeFloat = Field(default=0.0, description="Last trade price")
    volume: NonNegativeInt = Field(default=0, description="Tick volume")
    time_msc: int = Field(description="Unix timestamp in milliseconds")
    flags: int = Field(default=0, description="Tick flags")
    volume_real: float = Field(default=0.0, description="Real volume")

    @computed_field
    def spread(self) -> float:
        """Calculate spread (ask - bid)."""
        return self.ask - self.bid

    @computed_field
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.bid + self.ask) / 2

    @computed_field
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.time)

    def has_flag(self, flag: TickFlag) -> bool:
        """Check if tick has a specific flag."""
        return bool(self.flags & flag)


class RateBarModel(MT5BaseModel):
    """
    Validated OHLCV bar model.

    Represents a single candlestick/bar of price data.
    """

    time: int = Field(description="Bar open time (Unix timestamp)")
    open: float = Field(description="Open price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Close price")
    tick_volume: NonNegativeInt = Field(description="Tick volume")
    spread: NonNegativeInt = Field(default=0, description="Spread in points")
    real_volume: NonNegativeInt = Field(default=0, description="Real volume")

    @model_validator(mode="after")
    def validate_ohlc(self) -> "RateBarModel":
        """Validate OHLC relationship: low <= open,close <= high."""
        if self.low > self.high:
            msg = f"low ({self.low}) cannot be greater than high ({self.high})"
            raise ValueError(msg)
        if not (self.low <= self.open <= self.high):
            msg = f"open ({self.open}) must be between low ({self.low}) and high ({self.high})"
            raise ValueError(msg)
        if not (self.low <= self.close <= self.high):
            msg = f"close ({self.close}) must be between low and high"
            raise ValueError(msg)
        return self

    @computed_field
    def datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.time)

    @computed_field
    def body_size(self) -> float:
        """Size of candle body (absolute)."""
        return abs(self.close - self.open)

    @computed_field
    def range(self) -> float:
        """High-low range."""
        return self.high - self.low

    @computed_field
    def is_bullish(self) -> bool:
        """Check if bar is bullish (close > open)."""
        return self.close > self.open

    @computed_field
    def is_bearish(self) -> bool:
        """Check if bar is bearish (close < open)."""
        return self.close < self.open


# =============================================================================
# ACCOUNT MODELS
# =============================================================================


class AccountInfoModel(MT5BaseModel):
    """
    Validated account information model.

    Represents trading account state and parameters.
    """

    login: PositiveInt = Field(description="Account number")
    trade_mode: AccountTradeMode = Field(description="Account type")
    leverage: PositiveInt = Field(description="Account leverage")
    limit_orders: NonNegativeInt = Field(default=0, description="Max pending orders")
    margin_so_mode: int = Field(default=0, description="Stop out mode")
    trade_allowed: bool = Field(default=True, description="Trading allowed")
    trade_expert: bool = Field(default=True, description="EA trading allowed")
    margin_mode: AccountMarginMode = Field(
        default=AccountMarginMode.RETAIL_NETTING, description="Margin mode"
    )
    currency_digits: int = Field(default=2, description="Currency decimal places")
    balance: float = Field(description="Account balance")
    credit: float = Field(default=0.0, description="Account credit")
    profit: float = Field(default=0.0, description="Floating profit")
    equity: float = Field(description="Account equity")
    margin: NonNegativeFloat = Field(default=0.0, description="Used margin")
    margin_free: float = Field(description="Free margin")
    margin_level: float = Field(default=0.0, description="Margin level %")
    margin_so_call: float = Field(default=0.0, description="Margin call level")
    margin_so_so: float = Field(default=0.0, description="Stop out level")
    name: str = Field(default="", description="Account holder name")
    server: str = Field(default="", description="Trade server name")
    currency: str = Field(default="USD", description="Account currency")
    company: str = Field(default="", description="Broker company name")

    @computed_field
    def is_demo(self) -> bool:
        """Check if account is demo."""
        return self.trade_mode == AccountTradeMode.DEMO

    @computed_field
    def is_real(self) -> bool:
        """Check if account is real."""
        return self.trade_mode == AccountTradeMode.REAL

    @computed_field
    def is_profitable(self) -> bool:
        """Check if floating P/L is positive."""
        return self.profit > 0

    @computed_field
    def margin_usage_percent(self) -> float:
        """Calculate margin usage as percentage of equity."""
        if self.equity == 0:
            return 0.0
        return (self.margin / self.equity) * 100

    @computed_field
    def can_trade(self) -> bool:
        """Check if trading is possible."""
        return self.trade_allowed and self.margin_free > 0


# =============================================================================
# SYMBOL MODELS
# =============================================================================


class SymbolInfoModel(MT5BaseModel):
    """
    Validated symbol information model.

    Represents trading instrument properties.
    """

    name: SymbolName = Field(description="Symbol name")
    visible: bool = Field(default=True, description="Visible in Market Watch")
    select: bool = Field(default=False, description="Selected in Market Watch")
    bid: NonNegativeFloat = Field(default=0.0, description="Current bid")
    ask: NonNegativeFloat = Field(default=0.0, description="Current ask")
    spread: NonNegativeInt = Field(default=0, description="Current spread")
    digits: NonNegativeInt = Field(default=5, description="Price digits")
    point: float = Field(default=0.00001, description="Point size")
    trade_contract_size: PositiveFloat = Field(
        default=100000.0, description="Contract size"
    )
    volume_min: PositiveFloat = Field(default=0.01, description="Minimum volume")
    volume_max: PositiveFloat = Field(default=100.0, description="Maximum volume")
    volume_step: PositiveFloat = Field(default=0.01, description="Volume step")
    trade_mode: int = Field(default=4, description="Trading mode")
    swap_long: float = Field(default=0.0, description="Long swap")
    swap_short: float = Field(default=0.0, description="Short swap")
    currency_base: str = Field(default="", description="Base currency")
    currency_profit: str = Field(default="", description="Profit currency")
    currency_margin: str = Field(default="", description="Margin currency")
    description: str = Field(default="", description="Symbol description")

    @field_validator("name")
    @classmethod
    def uppercase_name(cls, v: str) -> str:
        """Ensure symbol name is uppercase."""
        return v.upper().strip()

    @computed_field
    def spread_value(self) -> float:
        """Calculate spread in price units."""
        return self.spread * self.point

    @computed_field
    def mid_price(self) -> float:
        """Calculate mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return 0.0


# =============================================================================
# TRADE REQUEST/RESULT MODELS
# =============================================================================


class TradeRequestModel(MT5BaseModel):
    """
    Validated trade request model.

    Used to construct and validate trade orders before sending.
    """

    action: TradeAction = Field(description="Trade action type")
    symbol: SymbolName = Field(description="Trading symbol")
    volume: PositiveFloat = Field(description="Trade volume in lots")
    price: NonNegativeFloat = Field(default=0.0, description="Order price")
    stoplimit: NonNegativeFloat = Field(default=0.0, description="Stop limit price")
    sl: NonNegativeFloat = Field(default=0.0, description="Stop loss price")
    tp: NonNegativeFloat = Field(default=0.0, description="Take profit price")
    deviation: NonNegativeInt = Field(default=20, description="Max price deviation")
    type: OrderType = Field(default=OrderType.BUY, description="Order type")
    type_filling: OrderFilling = Field(
        default=OrderFilling.FOK, description="Order filling"
    )
    type_time: OrderTime = Field(default=OrderTime.GTC, description="Order expiration")
    expiration: int = Field(default=0, description="Order expiration time")
    magic: int = Field(default=0, description="Expert Advisor ID")
    order: int = Field(default=0, description="Order ticket (for modify)")
    position: int = Field(default=0, description="Position ticket")
    position_by: int = Field(default=0, description="Opposite position ticket")
    comment: str = Field(default="", max_length=64, description="Order comment")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper().strip()

    @model_validator(mode="after")
    def validate_request(self) -> "TradeRequestModel":
        """Validate trade request parameters."""
        # Market orders need price for some brokers
        if self.action == TradeAction.DEAL:
            if OrderType.is_pending(self.type):
                msg = "DEAL action cannot have pending order type"
                raise ValueError(msg)

        # Pending orders need price
        if self.action == TradeAction.PENDING:
            if self.price <= 0:
                msg = "PENDING orders require price > 0"
                raise ValueError(msg)

        return self

    def to_mt5_dict(self) -> dict[str, Any]:
        """
        Convert to dict format expected by MT5 order_send.

        Returns:
            Dictionary with enum values converted to integers.
        """
        return {
            "action": self.action.value
            if isinstance(self.action, TradeAction)
            else self.action,
            "symbol": self.symbol,
            "volume": self.volume,
            "price": self.price,
            "stoplimit": self.stoplimit,
            "sl": self.sl,
            "tp": self.tp,
            "deviation": self.deviation,
            "type": self.type.value if isinstance(self.type, OrderType) else self.type,
            "type_filling": self.type_filling.value
            if isinstance(self.type_filling, OrderFilling)
            else self.type_filling,
            "type_time": self.type_time.value
            if isinstance(self.type_time, OrderTime)
            else self.type_time,
            "expiration": self.expiration,
            "magic": self.magic,
            "order": self.order,
            "position": self.position,
            "position_by": self.position_by,
            "comment": self.comment,
        }


class TradeResultModel(MT5BaseModel):
    """
    Validated trade result model.

    Represents the result of a trade operation.
    """

    retcode: TradeRetcode = Field(description="Return code")
    deal: int = Field(default=0, description="Deal ticket")
    order: int = Field(default=0, description="Order ticket")
    volume: float = Field(default=0.0, description="Executed volume")
    price: float = Field(default=0.0, description="Execution price")
    bid: float = Field(default=0.0, description="Current bid")
    ask: float = Field(default=0.0, description="Current ask")
    comment: str = Field(default="", description="Broker comment")
    request_id: int = Field(default=0, description="Request ID")
    retcode_external: int = Field(default=0, description="External return code")

    @computed_field
    def is_success(self) -> bool:
        """Check if trade was successful."""
        return TradeRetcode.is_success(self.retcode.value)

    @computed_field
    def is_error(self) -> bool:
        """Check if trade failed."""
        return not TradeRetcode.is_success(self.retcode.value)

    @computed_field
    def is_retriable(self) -> bool:
        """Check if operation can be retried."""
        return TradeRetcode.is_retriable(self.retcode.value)


# =============================================================================
# ORDER MODELS
# =============================================================================


class OrderInfoModel(MT5BaseModel):
    """
    Validated order information model.

    Represents a pending or filled order.
    """

    ticket: PositiveInt = Field(description="Order ticket")
    time_setup: int = Field(description="Order setup time")
    time_setup_msc: int = Field(default=0, description="Setup time in ms")
    time_done: int = Field(default=0, description="Execution time")
    time_done_msc: int = Field(default=0, description="Execution time in ms")
    time_expiration: int = Field(default=0, description="Expiration time")
    type: OrderType = Field(description="Order type")
    type_time: OrderTime = Field(default=OrderTime.GTC, description="Expiration type")
    type_filling: OrderFilling = Field(
        default=OrderFilling.FOK, description="Filling type"
    )
    state: OrderState = Field(description="Order state")
    magic: int = Field(default=0, description="Expert Advisor ID")
    position_id: int = Field(default=0, description="Position ID")
    volume_initial: PositiveFloat = Field(description="Initial volume")
    volume_current: NonNegativeFloat = Field(default=0.0, description="Current volume")
    price_open: float = Field(description="Order price")
    sl: NonNegativeFloat = Field(default=0.0, description="Stop loss")
    tp: NonNegativeFloat = Field(default=0.0, description="Take profit")
    price_current: float = Field(default=0.0, description="Current price")
    symbol: SymbolName = Field(description="Symbol")
    comment: str = Field(default="", description="Comment")
    external_id: str = Field(default="", description="External ID")

    @computed_field
    def is_active(self) -> bool:
        """Check if order is still active."""
        return OrderState.is_active(
            self.state.value if isinstance(self.state, OrderState) else self.state
        )

    @computed_field
    def is_pending(self) -> bool:
        """Check if order is pending type."""
        return OrderType.is_pending(
            self.type.value if isinstance(self.type, OrderType) else self.type
        )

    @computed_field
    def is_buy(self) -> bool:
        """Check if order is buy direction."""
        return OrderType.is_buy(
            self.type.value if isinstance(self.type, OrderType) else self.type
        )


# =============================================================================
# POSITION MODELS
# =============================================================================


class PositionInfoModel(MT5BaseModel):
    """
    Validated position information model.

    Represents an open trading position.
    """

    ticket: PositiveInt = Field(description="Position ticket")
    time: int = Field(description="Position open time")
    time_msc: int = Field(default=0, description="Open time in ms")
    time_update: int = Field(default=0, description="Last update time")
    time_update_msc: int = Field(default=0, description="Update time in ms")
    type: PositionType = Field(description="Position type (buy/sell)")
    magic: int = Field(default=0, description="Expert Advisor ID")
    identifier: int = Field(default=0, description="Position ID")
    reason: PositionReason = Field(
        default=PositionReason.EXPERT, description="Open reason"
    )
    volume: PositiveFloat = Field(description="Position volume")
    price_open: float = Field(description="Open price")
    sl: NonNegativeFloat = Field(default=0.0, description="Stop loss")
    tp: NonNegativeFloat = Field(default=0.0, description="Take profit")
    price_current: float = Field(default=0.0, description="Current price")
    swap: float = Field(default=0.0, description="Accumulated swap")
    profit: float = Field(default=0.0, description="Current profit")
    symbol: SymbolName = Field(description="Symbol")
    comment: str = Field(default="", description="Comment")
    external_id: str = Field(default="", description="External ID")

    @computed_field
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.profit > 0

    @computed_field
    def is_buy(self) -> bool:
        """Check if position is buy."""
        return self.type == PositionType.BUY

    @computed_field
    def is_sell(self) -> bool:
        """Check if position is sell."""
        return self.type == PositionType.SELL

    @computed_field
    def net_profit(self) -> float:
        """Calculate net profit (including swap)."""
        return self.profit + self.swap

    @computed_field
    def datetime(self) -> datetime:
        """Convert open time to datetime."""
        return datetime.fromtimestamp(self.time)


# =============================================================================
# DEAL MODELS
# =============================================================================


class DealInfoModel(MT5BaseModel):
    """
    Validated deal information model.

    Represents an executed trade in history.
    """

    ticket: PositiveInt = Field(description="Deal ticket")
    order: int = Field(default=0, description="Order ticket")
    time: int = Field(description="Deal time")
    time_msc: int = Field(default=0, description="Deal time in ms")
    type: DealType = Field(description="Deal type")
    entry: DealEntry = Field(description="Deal entry direction")
    magic: int = Field(default=0, description="Expert Advisor ID")
    reason: DealReason = Field(default=DealReason.EXPERT, description="Deal reason")
    position_id: int = Field(default=0, description="Position ID")
    volume: NonNegativeFloat = Field(default=0.0, description="Deal volume")
    price: float = Field(default=0.0, description="Deal price")
    commission: float = Field(default=0.0, description="Commission")
    swap: float = Field(default=0.0, description="Swap")
    profit: float = Field(default=0.0, description="Profit")
    fee: float = Field(default=0.0, description="Fee")
    symbol: str = Field(default="", description="Symbol")
    comment: str = Field(default="", description="Comment")
    external_id: str = Field(default="", description="External ID")

    @computed_field
    def is_trade(self) -> bool:
        """Check if deal is a trade (buy/sell)."""
        return DealType.is_trade(
            self.type.value if isinstance(self.type, DealType) else self.type
        )

    @computed_field
    def net_profit(self) -> float:
        """Calculate net profit (profit + swap - commission - fee)."""
        return self.profit + self.swap - self.commission - self.fee

    @computed_field
    def datetime(self) -> datetime:
        """Convert deal time to datetime."""
        return datetime.fromtimestamp(self.time)


# =============================================================================
# TERMINAL MODEL
# =============================================================================


class TerminalInfoModel(MT5BaseModel):
    """
    Validated terminal information model.

    Represents MetaTrader terminal state.
    """

    connected: bool = Field(description="Connected to broker")
    trade_allowed: bool = Field(description="Trading allowed")
    dlls_allowed: bool = Field(default=False, description="DLLs allowed")
    tradeapi_disabled: bool = Field(default=False, description="Trade API disabled")
    build: NonNegativeInt = Field(description="Terminal build")
    maxbars: NonNegativeInt = Field(default=0, description="Max bars in chart")
    codepage: int = Field(default=0, description="Code page")
    ping_last: int = Field(default=0, description="Last ping (ms)")
    company: str = Field(default="", description="Broker company")
    name: str = Field(default="", description="Terminal name")
    language: str = Field(default="", description="Terminal language")
    path: str = Field(default="", description="Terminal path")
    data_path: str = Field(default="", description="Data path")
    commondata_path: str = Field(default="", description="Common data path")

    @computed_field
    def can_trade(self) -> bool:
        """Check if trading is possible."""
        return self.connected and self.trade_allowed and not self.tradeapi_disabled


# =============================================================================
# RESILIENT SERVER MODELS
# =============================================================================


class ServerConfig(BaseModel):
    """
    Immutable server configuration for resilient_server.

    All resilience parameters with validation constraints.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = "0.0.0.0"
    port: int = Field(default=18812, ge=1, le=65535)
    wine_cmd: str = "wine"
    python_path: str = "python.exe"
    server_dir: str = "/tmp/mt5linux"

    # Resilience
    max_restart_attempts: int = Field(default=10, ge=1)
    restart_cooldown: float = Field(default=5.0, gt=0)
    restart_backoff_multiplier: float = Field(default=2.0, ge=1)
    max_restart_delay: float = Field(default=300.0, gt=0)

    # Health check
    health_check_port: int = Field(default=8002, ge=1, le=65535)
    health_check_interval: float = Field(default=15.0, gt=0)

    # Watchdog
    watchdog_timeout: float = Field(default=60.0, gt=0)
    connection_timeout: float = Field(default=300.0, gt=0)

    # Limits
    max_connections: int = Field(default=10, ge=1)

    # Circuit breaker
    circuit_failure_threshold: int = Field(default=5, ge=1)
    circuit_recovery_timeout: float = Field(default=30.0, gt=0)
    circuit_half_open_max_calls: int = Field(default=3, ge=1)

    # Rate limiting
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def validate_delays(self) -> "ServerConfig":
        """Ensure max_restart_delay >= restart_cooldown."""
        if self.max_restart_delay < self.restart_cooldown:
            raise ValueError("max_restart_delay must be >= restart_cooldown")
        return self


class ServerMetrics(BaseModel):
    """
    Server metrics for monitoring and observability.

    Tracks request counts, connection stats, and uptime.
    """

    model_config = ConfigDict(extra="forbid")

    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    connections_total: int = 0
    connections_active: int = 0
    connections_rejected: int = 0
    restarts_total: int = 0
    uptime_seconds: float = 0.0
    last_request_time: datetime | None = None
    circuit_trips: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to structured dictionary for JSON export."""
        return {
            "requests": {
                "total": self.requests_total,
                "success": self.requests_success,
                "failed": self.requests_failed,
            },
            "connections": {
                "total": self.connections_total,
                "active": self.connections_active,
                "rejected": self.connections_rejected,
            },
            "restarts_total": self.restarts_total,
            "uptime_seconds": self.uptime_seconds,
            "last_request_time": (
                self.last_request_time.isoformat() if self.last_request_time else None
            ),
            "circuit_trips": self.circuit_trips,
        }


class ServerState(BaseModel):
    """
    Mutable server state for resilient_server.

    Tracks runtime state, connections, errors, and metrics.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = "stopped"
    start_time: datetime | None = None
    restart_count: int = 0
    last_restart_time: datetime | None = None
    last_health_check: datetime | None = None
    active_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    wine_process_pid: int | None = None
    metrics: ServerMetrics = Field(default_factory=ServerMetrics)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_running(self) -> bool:
        """Check if server is in running state."""
        return self.status == "running"


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Custom types
    "PositiveFloat",
    "NonNegativeFloat",
    "PositiveInt",
    "NonNegativeInt",
    "SymbolName",
    # Base
    "MT5BaseModel",
    # Tick/Rate
    "TickModel",
    "RateBarModel",
    # Account
    "AccountInfoModel",
    # Symbol
    "SymbolInfoModel",
    # Trade
    "TradeRequestModel",
    "TradeResultModel",
    # Order
    "OrderInfoModel",
    # Position
    "PositionInfoModel",
    # Deal
    "DealInfoModel",
    # Terminal
    "TerminalInfoModel",
    # Resilient server
    "ServerConfig",
    "ServerMetrics",
    "ServerState",
]
