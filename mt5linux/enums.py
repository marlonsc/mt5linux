"""
MetaTrader 5 constants as Python IntEnum classes.

This module provides type-safe enum definitions for all MT5 constants.
Using IntEnum allows these values to be used directly as integers while
providing type safety, IDE autocomplete, and self-documenting code.

Example:
    >>> from mt5linux.enums import OrderType, TradeAction
    >>> order_type = OrderType.BUY
    >>> print(order_type)  # OrderType.BUY
    >>> print(order_type.value)  # 0
    >>> print(OrderType.is_market(order_type))  # True
"""

from __future__ import annotations

from enum import Enum, IntEnum, IntFlag, unique


# =============================================================================
# ACCOUNT ENUMS
# =============================================================================


@unique
class AccountMarginMode(IntEnum):
    """Account margin calculation mode."""

    RETAIL_NETTING = 0
    EXCHANGE = 1
    RETAIL_HEDGING = 2


@unique
class AccountStopoutMode(IntEnum):
    """Account stop out mode."""

    PERCENT = 0
    MONEY = 1


@unique
class AccountTradeMode(IntEnum):
    """Account trade mode."""

    DEMO = 0
    CONTEST = 1
    REAL = 2

    @classmethod
    def is_real_trading(cls, mode: int) -> bool:
        """Check if account allows real trading."""
        return mode == cls.REAL


# =============================================================================
# COPY TICKS
# =============================================================================


@unique
class CopyTicksFlag(IntEnum):
    """Flags for copy_ticks_* functions."""

    ALL = -1
    INFO = 1
    TRADE = 2


# =============================================================================
# DAY OF WEEK
# =============================================================================


@unique
class DayOfWeek(IntEnum):
    """Day of week constants."""

    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6

    @classmethod
    def is_weekend(cls, day: int) -> bool:
        """Check if day is weekend."""
        return day in (cls.SATURDAY, cls.SUNDAY)

    @classmethod
    def is_trading_day(cls, day: int) -> bool:
        """Check if day is a typical forex trading day."""
        return day not in (cls.SATURDAY, cls.SUNDAY)


# =============================================================================
# DEAL ENUMS
# =============================================================================


@unique
class DealEntry(IntEnum):
    """Deal entry direction."""

    IN = 0
    OUT = 1
    INOUT = 2
    OUT_BY = 3


@unique
class DealReason(IntEnum):
    """Reason for deal execution."""

    CLIENT = 0
    MOBILE = 1
    WEB = 2
    EXPERT = 3
    SL = 4
    TP = 5
    SO = 6
    ROLLOVER = 7
    VMARGIN = 8
    SPLIT = 9


@unique
class DealType(IntEnum):
    """Deal type."""

    BUY = 0
    SELL = 1
    BALANCE = 2
    CREDIT = 3
    CHARGE = 4
    CORRECTION = 5
    BONUS = 6
    COMMISSION = 7
    COMMISSION_DAILY = 8
    COMMISSION_MONTHLY = 9
    COMMISSION_AGENT_DAILY = 10
    COMMISSION_AGENT_MONTHLY = 11
    INTEREST = 12
    BUY_CANCELED = 13
    SELL_CANCELED = 14
    DIVIDEND = 15
    DIVIDEND_FRANKED = 16
    TAX = 17

    @classmethod
    def is_trade(cls, deal_type: int) -> bool:
        """Check if deal type is a trade (buy/sell)."""
        return deal_type in (cls.BUY, cls.SELL)

    @classmethod
    def is_balance_operation(cls, deal_type: int) -> bool:
        """Check if deal type is a balance operation."""
        return deal_type in (cls.BALANCE, cls.CREDIT, cls.BONUS)


# =============================================================================
# ORDER ENUMS
# =============================================================================


@unique
class OrderReason(IntEnum):
    """Reason for order placement."""

    CLIENT = 0
    MOBILE = 1
    WEB = 2
    EXPERT = 3
    SL = 4
    TP = 5
    SO = 6


@unique
class OrderState(IntEnum):
    """Order state."""

    STARTED = 0
    PLACED = 1
    CANCELED = 2
    PARTIAL = 3
    FILLED = 4
    REJECTED = 5
    EXPIRED = 6
    REQUEST_ADD = 7
    REQUEST_MODIFY = 8
    REQUEST_CANCEL = 9

    @classmethod
    def is_active(cls, state: int) -> bool:
        """Check if order state indicates an active order."""
        return state in (cls.STARTED, cls.PLACED, cls.PARTIAL)

    @classmethod
    def is_final(cls, state: int) -> bool:
        """Check if order state is final (no longer active)."""
        return state in (cls.CANCELED, cls.FILLED, cls.REJECTED, cls.EXPIRED)


@unique
class OrderType(IntEnum):
    """Order type."""

    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BUY_STOP_LIMIT = 6
    SELL_STOP_LIMIT = 7
    CLOSE_BY = 8

    @classmethod
    def is_market(cls, order_type: int) -> bool:
        """Check if order type is market order."""
        return order_type in (cls.BUY, cls.SELL)

    @classmethod
    def is_pending(cls, order_type: int) -> bool:
        """Check if order type is pending order."""
        return order_type in (
            cls.BUY_LIMIT,
            cls.SELL_LIMIT,
            cls.BUY_STOP,
            cls.SELL_STOP,
            cls.BUY_STOP_LIMIT,
            cls.SELL_STOP_LIMIT,
        )

    @classmethod
    def is_buy(cls, order_type: int) -> bool:
        """Check if order is a buy direction."""
        return order_type in (cls.BUY, cls.BUY_LIMIT, cls.BUY_STOP, cls.BUY_STOP_LIMIT)

    @classmethod
    def is_sell(cls, order_type: int) -> bool:
        """Check if order is a sell direction."""
        return order_type in (
            cls.SELL,
            cls.SELL_LIMIT,
            cls.SELL_STOP,
            cls.SELL_STOP_LIMIT,
        )


@unique
class OrderFilling(IntEnum):
    """Order filling policy."""

    FOK = 0  # Fill or Kill
    IOC = 1  # Immediate or Cancel
    RETURN = 2  # Return remaining


@unique
class OrderTime(IntEnum):
    """Order expiration type."""

    GTC = 0  # Good Till Cancelled
    DAY = 1  # Day order
    SPECIFIED = 2  # Specified expiration time
    SPECIFIED_DAY = 3  # Specified expiration day


# =============================================================================
# POSITION ENUMS
# =============================================================================


@unique
class PositionReason(IntEnum):
    """Reason for position opening."""

    CLIENT = 0
    MOBILE = 1
    WEB = 2
    EXPERT = 3


@unique
class PositionType(IntEnum):
    """Position type (direction)."""

    BUY = 0
    SELL = 1

    @classmethod
    def opposite(cls, position_type: int) -> "PositionType":
        """Get the opposite position type."""
        return cls.SELL if position_type == cls.BUY else cls.BUY


# =============================================================================
# SYMBOL ENUMS
# =============================================================================


@unique
class SymbolCalcMode(IntEnum):
    """Symbol profit calculation mode."""

    FOREX = 0
    FUTURES = 1
    CFD = 2
    CFDINDEX = 3
    CFDLEVERAGE = 4
    FOREX_NO_LEVERAGE = 5
    EXCH_STOCKS = 32
    EXCH_FUTURES = 33
    EXCH_OPTIONS = 34
    EXCH_OPTIONS_MARGIN = 36
    EXCH_BONDS = 37
    EXCH_STOCKS_MOEX = 38
    EXCH_BONDS_MOEX = 39
    SERV_COLLATERAL = 64


@unique
class SymbolChartMode(IntEnum):
    """Symbol chart display mode."""

    BID = 0
    LAST = 1


@unique
class SymbolOptionMode(IntEnum):
    """Option type."""

    EUROPEAN = 0
    AMERICAN = 1


@unique
class SymbolOptionRight(IntEnum):
    """Option right type."""

    CALL = 0
    PUT = 1


@unique
class SymbolOrdersMode(IntEnum):
    """Symbol orders mode."""

    GTC = 0
    DAILY = 1
    DAILY_NO_STOPS = 2


@unique
class SymbolSwapMode(IntEnum):
    """Symbol swap calculation mode."""

    DISABLED = 0
    POINTS = 1
    CURRENCY_SYMBOL = 2
    CURRENCY_MARGIN = 3
    CURRENCY_DEPOSIT = 4
    INTEREST_CURRENT = 5
    INTEREST_OPEN = 6
    REOPEN_CURRENT = 7
    REOPEN_BID = 8


@unique
class SymbolTradeExecution(IntEnum):
    """Symbol trade execution mode."""

    REQUEST = 0
    INSTANT = 1
    MARKET = 2
    EXCHANGE = 3


@unique
class SymbolTradeMode(IntEnum):
    """Symbol trading mode."""

    DISABLED = 0
    LONGONLY = 1
    SHORTONLY = 2
    CLOSEONLY = 3
    FULL = 4


# =============================================================================
# TICK FLAGS
# =============================================================================


class TickFlag(IntFlag):
    """
    Tick flags indicating what changed.

    Uses IntFlag for bitwise operations since multiple flags
    can be set simultaneously.
    """

    BID = 2
    ASK = 4
    LAST = 8
    VOLUME = 16
    BUY = 32
    SELL = 64


# =============================================================================
# TIMEFRAME
# =============================================================================


@unique
class TimeFrame(IntEnum):
    """Chart timeframe."""

    M1 = 1  # 1 minute
    M2 = 2  # 2 minutes
    M3 = 3  # 3 minutes
    M4 = 4  # 4 minutes
    M5 = 5  # 5 minutes
    M6 = 6  # 6 minutes
    M10 = 10  # 10 minutes
    M12 = 12  # 12 minutes
    M15 = 15  # 15 minutes
    M20 = 20  # 20 minutes
    M30 = 30  # 30 minutes
    H1 = 16385  # 1 hour
    H2 = 16386  # 2 hours
    H3 = 16387  # 3 hours
    H4 = 16388  # 4 hours
    H6 = 16390  # 6 hours
    H8 = 16392  # 8 hours
    H12 = 16396  # 12 hours
    D1 = 16408  # 1 day
    W1 = 32769  # 1 week
    MN1 = 49153  # 1 month

    @classmethod
    def minutes(cls, tf: "TimeFrame") -> int | None:
        """Get the number of minutes for a timeframe."""
        minute_map = {
            cls.M1: 1,
            cls.M2: 2,
            cls.M3: 3,
            cls.M4: 4,
            cls.M5: 5,
            cls.M6: 6,
            cls.M10: 10,
            cls.M12: 12,
            cls.M15: 15,
            cls.M20: 20,
            cls.M30: 30,
            cls.H1: 60,
            cls.H2: 120,
            cls.H3: 180,
            cls.H4: 240,
            cls.H6: 360,
            cls.H8: 480,
            cls.H12: 720,
            cls.D1: 1440,
            cls.W1: 10080,
            cls.MN1: 43200,  # Approximate
        }
        return minute_map.get(tf)


# =============================================================================
# TRADE ENUMS
# =============================================================================


@unique
class TradeAction(IntEnum):
    """Trade request action type."""

    DEAL = 1  # Market order
    PENDING = 5  # Pending order
    SLTP = 6  # Modify SL/TP
    MODIFY = 7  # Modify order
    REMOVE = 8  # Delete pending order
    CLOSE_BY = 10  # Close by opposite position


@unique
class TradeRetcode(IntEnum):
    """Trade server return codes."""

    REQUOTE = 10004
    REJECT = 10006
    CANCEL = 10007
    PLACED = 10008
    DONE = 10009
    DONE_PARTIAL = 10010
    ERROR = 10011
    TIMEOUT = 10012
    INVALID = 10013
    INVALID_VOLUME = 10014
    INVALID_PRICE = 10015
    INVALID_STOPS = 10016
    TRADE_DISABLED = 10017
    MARKET_CLOSED = 10018
    NO_MONEY = 10019
    PRICE_CHANGED = 10020
    PRICE_OFF = 10021
    INVALID_EXPIRATION = 10022
    ORDER_CHANGED = 10023
    TOO_MANY_REQUESTS = 10024
    NO_CHANGES = 10025
    SERVER_DISABLES_AT = 10026
    CLIENT_DISABLES_AT = 10027
    LOCKED = 10028
    FROZEN = 10029
    INVALID_FILL = 10030
    CONNECTION = 10031
    ONLY_REAL = 10032
    LIMIT_ORDERS = 10033
    LIMIT_VOLUME = 10034
    INVALID_ORDER = 10035
    POSITION_CLOSED = 10036
    INVALID_CLOSE_VOLUME = 10038
    CLOSE_ORDER_EXIST = 10039
    LIMIT_POSITIONS = 10040
    REJECT_CANCEL = 10041
    LONG_ONLY = 10042
    SHORT_ONLY = 10043
    CLOSE_ONLY = 10044
    FIFO_CLOSE = 10045
    HEDGE_PROHIBITED = 10046

    @classmethod
    def is_success(cls, code: int) -> bool:
        """Check if return code indicates success."""
        return code in (cls.DONE, cls.DONE_PARTIAL, cls.PLACED)

    @classmethod
    def is_error(cls, code: int) -> bool:
        """Check if return code indicates an error."""
        return not cls.is_success(code)

    @classmethod
    def is_retriable(cls, code: int) -> bool:
        """Check if the operation can be retried."""
        return code in (
            cls.REQUOTE,
            cls.TIMEOUT,
            cls.PRICE_CHANGED,
            cls.TOO_MANY_REQUESTS,
            cls.CONNECTION,
        )


# =============================================================================
# BOOK TYPE
# =============================================================================


@unique
class BookType(IntEnum):
    """Market depth book entry type."""

    SELL = 1
    BUY = 2
    SELL_MARKET = 3
    BUY_MARKET = 4


# =============================================================================
# CIRCUIT BREAKER STATE
# =============================================================================


class CircuitState(str, Enum):
    """
    Circuit breaker states for failure protection pattern.

    Used by resilient_server to implement the circuit breaker pattern:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# =============================================================================
# RESULT CODES (Internal)
# =============================================================================


@unique
class ResultCode(IntEnum):
    """Internal result codes from rpyc bridge."""

    E_INTERNAL_FAIL_TIMEOUT = -10005
    E_INTERNAL_FAIL_CONNECT = -10004
    E_INTERNAL_FAIL_INIT = -10003
    E_INTERNAL_FAIL_RECEIVE = -10002
    E_INTERNAL_FAIL_SEND = -10001
    E_INTERNAL_FAIL = -10000
    E_AUTO_TRADING_DISABLED = -8
    E_UNSUPPORTED = -7
    E_AUTH_FAILED = -6
    E_INVALID_VERSION = -5
    E_NOT_FOUND = -4
    E_NO_MEMORY = -3
    E_INVALID_PARAMS = -2
    E_FAIL = -1
    S_OK = 1

    @classmethod
    def is_success(cls, code: int) -> bool:
        """Check if result code indicates success."""
        return code == cls.S_OK

    @classmethod
    def is_connection_error(cls, code: int) -> bool:
        """Check if result indicates a connection problem."""
        return code in (
            cls.E_INTERNAL_FAIL_TIMEOUT,
            cls.E_INTERNAL_FAIL_CONNECT,
            cls.E_INTERNAL_FAIL_INIT,
        )


# =============================================================================
# ALL ENUMS EXPORT
# =============================================================================

__all__ = [
    # Account
    "AccountMarginMode",
    "AccountStopoutMode",
    "AccountTradeMode",
    # Copy ticks
    "CopyTicksFlag",
    # Day of week
    "DayOfWeek",
    # Deal
    "DealEntry",
    "DealReason",
    "DealType",
    # Order
    "OrderReason",
    "OrderState",
    "OrderType",
    "OrderFilling",
    "OrderTime",
    # Position
    "PositionReason",
    "PositionType",
    # Symbol
    "SymbolCalcMode",
    "SymbolChartMode",
    "SymbolOptionMode",
    "SymbolOptionRight",
    "SymbolOrdersMode",
    "SymbolSwapMode",
    "SymbolTradeExecution",
    "SymbolTradeMode",
    # Tick
    "TickFlag",
    # Timeframe
    "TimeFrame",
    # Trade
    "TradeAction",
    "TradeRetcode",
    # Book
    "BookType",
    # Circuit breaker
    "CircuitState",
    # Result
    "ResultCode",
]
