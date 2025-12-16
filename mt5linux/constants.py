"""MT5 constants organized in a single container class.

All MetaTrader5 constants are nested inside the MT5Constants class for:
- Clean namespace (no loose code)
- Logical grouping by category
- Easy discovery via IDE autocomplete
- Single import: `from mt5linux.constants import MT5Constants`

Usage:
    >>> from mt5linux.constants import MT5Constants
    >>> MT5Constants.TimeFrame.H1
    16385
    >>> MT5Constants.TradeAction.DEAL
    1
    >>> MT5Constants.OrderType.BUY
    0

Backward compatibility:
    >>> from mt5linux.constants import MT5  # alias for MT5Constants
"""

from __future__ import annotations

from enum import IntEnum


class MT5Constants:
    """MetaTrader5 constants container.

    All MT5 constants organized by category as nested IntEnum classes.

    Categories:
    - Account: Account margin, stopout, trade modes
    - Trade: Actions, return codes
    - Order: Types, filling, time, state, reason
    - Position: Types, reasons
    - Deal: Types, entry, reasons
    - Symbol: Calc mode, chart mode, trade mode, options, swap
    - TimeFrame: M1 to MN1
    - Tick: Flags, copy flags
    - Book: Market depth types
    - DayOfWeek: Calendar days
    """

    # =========================================================================
    # ACCOUNT CONSTANTS
    # =========================================================================

    class AccountMarginMode(IntEnum):
        """Account margin mode."""

        RETAIL_NETTING = 0
        EXCHANGE = 1
        RETAIL_HEDGING = 2

    class AccountStopoutMode(IntEnum):
        """Account stopout mode."""

        PERCENT = 0
        MONEY = 1

    class AccountTradeMode(IntEnum):
        """Account trade mode."""

        DEMO = 0
        CONTEST = 1
        REAL = 2

    # =========================================================================
    # TRADE CONSTANTS
    # =========================================================================

    class TradeAction(IntEnum):
        """Trade request action type."""

        DEAL = 1
        PENDING = 5
        SLTP = 6
        MODIFY = 7
        REMOVE = 8
        CLOSE_BY = 10

    class TradeRetcode(IntEnum):
        """Trade operation return codes."""

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

    # =========================================================================
    # ORDER CONSTANTS
    # =========================================================================

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

    class OrderFilling(IntEnum):
        """Order filling mode."""

        FOK = 0
        IOC = 1
        RETURN = 2
        BOC = 3

    class OrderTime(IntEnum):
        """Order time type."""

        GTC = 0
        DAY = 1
        SPECIFIED = 2
        SPECIFIED_DAY = 3

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

    class OrderReason(IntEnum):
        """Order reason."""

        CLIENT = 0
        MOBILE = 1
        WEB = 2
        EXPERT = 3
        SL = 4
        TP = 5
        SO = 6

    # =========================================================================
    # POSITION CONSTANTS
    # =========================================================================

    class PositionType(IntEnum):
        """Position type."""

        BUY = 0
        SELL = 1

    class PositionReason(IntEnum):
        """Position reason."""

        CLIENT = 0
        MOBILE = 1
        WEB = 2
        EXPERT = 3

    # =========================================================================
    # DEAL CONSTANTS
    # =========================================================================

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

    class DealEntry(IntEnum):
        """Deal entry type."""

        IN = 0
        OUT = 1
        INOUT = 2
        OUT_BY = 3

    class DealReason(IntEnum):
        """Deal reason."""

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

    # =========================================================================
    # SYMBOL CONSTANTS
    # =========================================================================

    class SymbolCalcMode(IntEnum):
        """Symbol calculation mode."""

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

    class SymbolChartMode(IntEnum):
        """Symbol chart mode."""

        BID = 0
        LAST = 1

    class SymbolTradeMode(IntEnum):
        """Symbol trade mode."""

        DISABLED = 0
        LONGONLY = 1
        SHORTONLY = 2
        CLOSEONLY = 3
        FULL = 4

    class SymbolTradeExecution(IntEnum):
        """Symbol trade execution mode."""

        REQUEST = 0
        INSTANT = 1
        MARKET = 2
        EXCHANGE = 3

    class SymbolSwapMode(IntEnum):
        """Symbol swap mode."""

        DISABLED = 0
        POINTS = 1
        CURRENCY_SYMBOL = 2
        CURRENCY_MARGIN = 3
        CURRENCY_DEPOSIT = 4
        INTEREST_CURRENT = 5
        INTEREST_OPEN = 6
        REOPEN_CURRENT = 7
        REOPEN_BID = 8

    class SymbolOptionMode(IntEnum):
        """Symbol option mode."""

        EUROPEAN = 0
        AMERICAN = 1

    class SymbolOptionRight(IntEnum):
        """Symbol option right."""

        CALL = 0
        PUT = 1

    # =========================================================================
    # TIMEFRAME CONSTANTS
    # =========================================================================

    class TimeFrame(IntEnum):
        """Chart timeframes."""

        M1 = 1
        M2 = 2
        M3 = 3
        M4 = 4
        M5 = 5
        M6 = 6
        M10 = 10
        M12 = 12
        M15 = 15
        M20 = 20
        M30 = 30
        H1 = 16385
        H2 = 16386
        H3 = 16387
        H4 = 16388
        H6 = 16390
        H8 = 16392
        H12 = 16396
        D1 = 16408
        W1 = 32769
        MN1 = 49153

    # =========================================================================
    # TICK CONSTANTS
    # =========================================================================

    class TickFlag(IntEnum):
        """Tick flags."""

        BID = 2
        ASK = 4
        LAST = 8
        VOLUME = 16
        BUY = 32
        SELL = 64

    class CopyTicksFlag(IntEnum):
        """Copy ticks flags."""

        ALL = -1
        INFO = 1
        TRADE = 2

    # =========================================================================
    # BOOK CONSTANTS
    # =========================================================================

    class BookType(IntEnum):
        """Market depth book type."""

        SELL = 1
        BUY = 2
        SELL_MARKET = 3
        BUY_MARKET = 4

    # =========================================================================
    # CALENDAR CONSTANTS
    # =========================================================================

    class DayOfWeek(IntEnum):
        """Day of week."""

        SUNDAY = 0
        MONDAY = 1
        TUESDAY = 2
        WEDNESDAY = 3
        THURSDAY = 4
        FRIDAY = 5
        SATURDAY = 6


