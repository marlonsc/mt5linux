"""MT5 Constants - Centralized business domain constants for MT5Linux.

All magic numbers, configuration values, and enums are defined here.
Access via: from mt5linux.constants import MT5Constants as c
Usage: c.Network.GRPC_PORT, c.Order.TradeAction.DEAL, etc.
"""

from enum import IntEnum
from typing import Final


class MT5Constants:
    """Centralized constants organized by business domain namespaces.

    Namespaces are organized by business function, not data type.
    All constants are accessed via c.Namespace.CONSTANT or c.Namespace.Enum.VALUE
    """

    # ==================== NETWORK & INFRASTRUCTURE ====================
    class Network:
        """Network configuration and port constants."""

        # Container internal ports
        GRPC_PORT: Final = 8001
        VNC_PORT: Final = 3000
        HEALTH_PORT: Final = 8002

        # Docker host mapped ports
        DOCKER_GRPC_PORT: Final = 38812
        DOCKER_VNC_PORT: Final = 33000
        DOCKER_HEALTH_PORT: Final = 38002

        # Test isolated ports
        TEST_GRPC_PORT: Final = 28812
        TEST_VNC_PORT: Final = 23000
        TEST_HEALTH_PORT: Final = 28002

        # Host addresses
        LOCALHOST: Final = "localhost"
        BIND_ALL: Final = "0.0.0.0"  # noqa: S104

        # gRPC configuration
        MAX_MESSAGE_SIZE: Final = 50 * 1024 * 1024  # 50MB
        KEEPALIVE_TIME_MS: Final = 30000  # 30 seconds
        KEEPALIVE_TIMEOUT_MS: Final = 10000  # 10 seconds

        # Timeouts (seconds)  # noqa: ERA001
        TEST_STARTUP_TIMEOUT: Final = 420  # 7 minutes
        TIMEOUT_HEALTH_CHECK: Final = 60
        TIMEOUT_CONNECTION: Final = 300
        STARTUP_HEALTH_TIMEOUT: Final = 30.0

    # ==================== RETRY & RESILIENCE ====================
    class Resilience:
        """Retry and resilience configuration."""

        # Retry configuration
        MAX_ATTEMPTS: Final = 3
        INITIAL_DELAY: Final = 0.5  # seconds
        MAX_DELAY: Final = 10.0  # seconds
        EXPONENTIAL_BASE: Final = 2.0
        JITTER_ENABLED: Final = True

        # Startup retry configuration
        STARTUP_MIN_INTERVAL: Final = 0.5  # seconds
        STARTUP_MAX_INTERVAL: Final = 5.0  # seconds

        # Circuit breaker configuration
        CIRCUIT_BREAKER_THRESHOLD: Final = 5  # failures to trip
        CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Final = 30.0  # seconds
        CIRCUIT_BREAKER_HALF_OPEN_MAX: Final = 3  # requests in half-open

        class CircuitBreakerState(IntEnum):
            """Circuit breaker states."""

            CLOSED = 0
            OPEN = 1
            HALF_OPEN = 2

    # ==================== ORDER MANAGEMENT ====================
    class Order:
        """Order types, states, and trading actions."""

        # Order defaults
        DEFAULT_DEVIATION: Final = 20  # points
        DEFAULT_MAGIC: Final = 0

        # Comment max length
        MAX_COMMENT_LENGTH: Final = 31

        class TradeAction(IntEnum):
            """Trade action types."""

            DEAL = 1
            PENDING = 5
            SLTP = 6
            MODIFY = 7
            REMOVE = 8
            CLOSE_BY = 10

        class OrderType(IntEnum):
            """Order types for trading."""

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
            """Order filling modes."""

            FOK = 0  # Fill-or-Kill
            IOC = 1  # Immediate-or-Cancel
            RETURN = 2
            BOC = 3  # Buy-or-Cancel

        class OrderTime(IntEnum):
            """Order time types."""

            GTC = 0  # Good-till-canceled
            DAY = 1
            SPECIFIED = 2
            SPECIFIED_DAY = 3

        class OrderState(IntEnum):
            """Order states during lifecycle."""

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
            """Reason for order creation or modification."""

            CLIENT = 0
            MOBILE = 1
            WEB = 2
            EXPERT = 3
            SL = 4  # Stop loss
            TP = 5  # Take profit
            SO = 6  # Margin call
            ROLLOVER = 7
            VMARGIN = 8  # Virtual margin call
            SPLIT = 9  # Symbol split

        class TradeRetcode(IntEnum):
            """Trade return codes - execution results."""

            REQUOTE = 10004
            REJECT = 10006
            CANCEL = 10007
            PLACED = 10008
            DONE = 10009  # SUCCESS
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

        # Order result field defaults
        RESULT_DEFAULT_DEAL: Final = 0
        RESULT_DEFAULT_ORDER: Final = 0
        RESULT_DEFAULT_VOLUME: Final = 0.0
        RESULT_DEFAULT_PRICE: Final = 0.0
        RESULT_DEFAULT_REQUEST_ID: Final = 0

    # ==================== TRADING & EXECUTION ====================
    class Trading:
        """Trading positions, deals, and execution details."""

        class PositionType(IntEnum):
            """Position types."""

            BUY = 0
            SELL = 1

        class DealType(IntEnum):
            """Deal types representing executed transactions."""

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
            """Deal entry/exit types."""

            IN = 0  # Entry
            OUT = 1  # Exit
            INOUT = 2  # Entry and exit
            OUT_BY = 3  # Exit by

        class DealReason(IntEnum):
            """Reason for deal execution."""

            CLIENT = 0
            MOBILE = 1
            WEB = 2
            EXPERT = 3
            SL = 4  # Stop loss
            TP = 5  # Take profit
            SO = 6  # Margin call
            ROLLOVER = 7
            VMARGIN = 8  # Virtual margin call
            SPLIT = 9  # Symbol split

        class PositionReason(IntEnum):
            """Reason for position opening/modification."""

            CLIENT = 0
            MOBILE = 1
            WEB = 2
            EXPERT = 3
            SL = 4  # Stop loss
            TP = 5  # Take profit
            SO = 6  # Margin call
            ROLLOVER = 7
            VMARGIN = 8  # Virtual margin call
            SPLIT = 9  # Symbol split

        # Trading utility constant
        DEFAULT_MAGIC_NUMBER: int = 0

    # ==================== MARKET DATA ====================
    class MarketData:
        """Timeframes, ticks, and market depth data."""

        class TimeFrame(IntEnum):
            """Timeframe constants (in minutes, unless specified)."""

            # Minutes
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
            # Hours
            H1 = 16385
            H2 = 16386
            H3 = 16387
            H4 = 16388
            H6 = 16390
            H8 = 16392
            H12 = 16396
            # Days/Weeks/Months
            D1 = 16408
            W1 = 32769
            MN1 = 49153

        class TickFlag(IntEnum):
            """Tick data flags."""

            BID = 2
            ASK = 4
            LAST = 8
            VOLUME = 16
            BUY = 32
            SELL = 64

        class CopyTicksFlag(IntEnum):
            """Flags for copying tick data."""

            ALL = -1
            INFO = 1
            TRADE = 2

        class BookType(IntEnum):
            """Market depth (order book) types."""

            SELL = 1
            BUY = 2
            SELL_MARKET = 3
            BUY_MARKET = 4

    # ==================== ACCOUNT CONFIGURATION ====================
    class Account:
        """Account types, modes, and settings."""

        # Account info defaults
        DEFAULT_CURRENCY_DIGITS: Final = 2

        class MarginMode(IntEnum):
            """Account margin calculation modes."""

            RETAIL_NETTING = 0
            EXCHANGE = 1
            RETAIL_HEDGING = 2

        class StopoutMode(IntEnum):
            """Account stopout calculation mode."""

            PERCENT = 0
            MONEY = 1

        class TradeMode(IntEnum):
            """Account trade mode (demo/contest/real)."""

            DEMO = 0
            CONTEST = 1
            REAL = 2

    # ==================== SYMBOL PROPERTIES ====================
    class Symbol:
        """Symbol calculation modes, chart modes, and trading modes."""

        class CalcMode(IntEnum):
            """Symbol profit calculation modes."""

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

        class ChartMode(IntEnum):
            """Symbol chart price source."""

            BID = 0
            LAST = 1

        class TradeMode(IntEnum):
            """Symbol trading mode restrictions."""

            DISABLED = 0
            LONGONLY = 1
            SHORTONLY = 2
            CLOSEONLY = 3
            FULL = 4

        class SwapMode(IntEnum):
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

        class OptionMode(IntEnum):
            """Option style (European/American)."""

            EUROPEAN = 0
            AMERICAN = 1

        class OptionRight(IntEnum):
            """Option type (call/put)."""

            CALL = 0
            PUT = 1

        class TradeExecution(IntEnum):
            """Symbol trade execution mode."""

            REQUEST = 0
            INSTANT = 1
            MARKET = 2
            EXCHANGE = 3

    # ==================== CALENDAR & TIMING ====================
    class Calendar:
        """Day of week and calendar constants."""

        class DayOfWeek(IntEnum):
            """Days of the week."""

            SUNDAY = 0
            MONDAY = 1
            TUESDAY = 2
            WEDNESDAY = 3
            THURSDAY = 4
            FRIDAY = 5
            SATURDAY = 6

    # ==================== VALIDATION & UTILITIES ====================
    class Validation:
        """Data validation and utility constants."""

        # Tuple structure sizes
        VERSION_TUPLE_LENGTH: Final = 3  # (version, build, string)
        ERROR_TUPLE_LENGTH: Final = 2  # (code, description)

    # ==================== TEST CONSTANTS ====================
    class Test:
        """Test-specific constants for pytest and fixtures."""

        class Timing:
            """Test timing constants (seconds)."""

            FAST_CHECK: Final = 2
            STARTUP_TIMEOUT: Final = 420  # 7 minutes
            DEFAULT_TIMEOUT: Final = 60
            SLOW_COMMAND: Final = 30
            CONTAINER_TIMEOUT: Final = 300
            CODEGEN_TIMEOUT: Final = 60

        class Network:
            """Test network configuration."""

            GRPC_PORT: Final = 28812
            VNC_PORT: Final = 23000
            HEALTH_PORT: Final = 28002

        class Order:
            """Test order constants."""

            HISTORY_MAGIC: Final = 888888
            TEST_MAGIC: Final = 999999
            INVALID_MAGIC: Final = -1
            COMMENT: Final = "test_order"

        class Financial:
            """Test financial data."""

            BASE_PRICE: Final = 1.1  # EURUSD
            DEFAULT_SYMBOL: Final = "EURUSD"
            VOLUME_MICRO: Final = 0.01  # micro lot
            VOLUME_MINI: Final = 0.1  # mini lot
            VOLUME_STANDARD: Final = 1.0  # standard lot
            VOLUME_HALF: Final = 0.5
            VOLUME_DOUBLE: Final = 2.0
            VOLUME_FIVE: Final = 5.0
            VOLUME_TEN: Final = 10.0
            VOLUME_MIN: Final = 0.01
            VOLUME_MAX: Final = 1000.0

            # Percentage-based stops
            SL_PERCENTAGE: Final = 0.005  # 0.5%
            TP_PERCENTAGE: Final = 0.005  # 0.5%

            # Price data
            PRICE_VOLATILITY: Final = 0.001
            PRICE_NOISE: Final = 0.0008
            PRICE_INCREMENT: Final = 0.0001
            HIGH_LOW_SPREAD: Final = 0.0005
            CLOSE_ADJUSTMENT: Final = 0.0002

            # Contract
            CONTRACT_SIZE: Final = 100000

            # Deviations
            DEVIATION_TIGHT: Final = 10
            DEVIATION_NORMAL: Final = 20
            DEVIATION_WIDE: Final = 50

        class Historical:
            """Test historical data."""

            BAR_COUNT_SMALL: Final = 100
            BAR_COUNT_MEDIUM: Final = 500
            BAR_COUNT_LARGE: Final = 5000
            DEFAULT_PERIODS: Final = 100

            DAYS_BACK_RECENT: Final = 7
            DAYS_BACK_MEDIUM: Final = 30
            DAYS_BACK_LONG: Final = 365
            MARKET_DATA_DAYS: Final = 30

            BASE_VOLUME: Final = 1000
            INTEGRATION_PERIODS: Final = 100

        class Prediction:
            """Test ML/prediction constants."""

            CONFIDENCE_THRESHOLD: Final = 0.6
            CONFIDENCE_THRESHOLD_HIGH: Final = 0.8
            CONFIDENCE_THRESHOLD_LOW: Final = 0.5

        class Database:
            """Test database constants."""

            POSTGRES_DEFAULT_PORT: Final = 5432
            CLICKHOUSE_DEFAULT_PORT: Final = 9000

        class Kafka:
            """Test Kafka constants."""

            DEFAULT_PORT: Final = 9092
            SOCKET_TIMEOUT: Final = 2.0

        class Validation:
            """Test validation constants."""

            STDOUT_TRUNCATE_LENGTH: Final = 50
            CONTAINER_NAME: Final = "mt5linux-test"
            LOG_TAIL_LINES: Final = 50
            ERROR_DISPLAY_LIMIT: Final = 20  # Max items to show in error messages

            # Test thresholds for edge case validation
            SYMBOL_COUNT_THRESHOLD: Final = 1000  # Minimum expected symbols
            TICKS_LIMIT_THRESHOLD: Final = 10000  # Maximum ticks to expect
            TRADING_DAYS_THRESHOLD: Final = 400  # Rough trading days in year
            TUPLE_LENGTH_ERROR: Final = 2  # Error tuple structure
            TUPLE_LENGTH_VERSION: Final = 3  # Version tuple structure

        class Hypothesis:
            """Hypothesis strategy ranges for property-based testing."""

            # Volume strategies (lots)
            VOLUME_MICRO_MIN: Final = 0.01
            VOLUME_MICRO_MAX: Final = 0.1

            VOLUME_MINI_MIN: Final = 0.1
            VOLUME_MINI_MAX: Final = 1.0

            VOLUME_STANDARD_MIN: Final = 1.0
            VOLUME_STANDARD_MAX: Final = 10.0

            VOLUME_VALID_MIN: Final = 0.01
            VOLUME_VALID_MAX: Final = 10.0

            # Deviation strategies (points)
            DEVIATION_TIGHT_MIN: Final = 1
            DEVIATION_TIGHT_MAX: Final = 10

            DEVIATION_NORMAL_MIN: Final = 10
            DEVIATION_NORMAL_MAX: Final = 50

            DEVIATION_WIDE_MIN: Final = 50
            DEVIATION_WIDE_MAX: Final = 100

            DEVIATION_VALID_MIN: Final = 1
            DEVIATION_VALID_MAX: Final = 100

            # Bar count strategies
            BAR_COUNT_SMALL_MIN: Final = 1
            BAR_COUNT_SMALL_MAX: Final = 10

            BAR_COUNT_MEDIUM_MIN: Final = 100
            BAR_COUNT_MEDIUM_MAX: Final = 1000

            BAR_COUNT_LARGE_MIN: Final = 1000
            BAR_COUNT_LARGE_MAX: Final = 10000

            BAR_COUNT_VALID_MIN: Final = 1
            BAR_COUNT_VALID_MAX: Final = 10000

            # Days back strategies
            DAYS_BACK_RECENT_MIN: Final = 1
            DAYS_BACK_RECENT_MAX: Final = 7

            DAYS_BACK_MEDIUM_MIN: Final = 7
            DAYS_BACK_MEDIUM_MAX: Final = 30

            DAYS_BACK_LONG_MIN: Final = 30
            DAYS_BACK_LONG_MAX: Final = 365

    # ==================== TOP-LEVEL ALIASES FOR COMPATIBILITY ====================
    # These aliases allow direct access to enum classes at the top level
    # e.g., c.TimeFrame instead of c.MarketData.TimeFrame
    TimeFrame = MarketData.TimeFrame
    TickFlag = MarketData.TickFlag
    CopyTicksFlag = MarketData.CopyTicksFlag
    BookType = MarketData.BookType

    TradeAction = Order.TradeAction
    OrderType = Order.OrderType
    OrderFilling = Order.OrderFilling
    OrderTime = Order.OrderTime
    OrderState = Order.OrderState
    OrderReason = Order.OrderReason
    TradeRetcode = Order.TradeRetcode

    PositionType = Trading.PositionType
    DealType = Trading.DealType
    DealEntry = Trading.DealEntry
    DealReason = Trading.DealReason
    PositionReason = Trading.PositionReason

    MarginMode = Account.MarginMode
    StopoutMode = Account.StopoutMode
    AccountTradeMode = Account.TradeMode

    # Account aliases with different naming
    AccountStopoutMode = Account.StopoutMode
    AccountMarginMode = Account.MarginMode

    SymbolCalcMode = Symbol.CalcMode
    SymbolChartMode = Symbol.ChartMode
    SymbolTradeMode = Symbol.TradeMode
    SymbolSwapMode = Symbol.SwapMode
    SymbolOptionMode = Symbol.OptionMode
    SymbolOptionRight = Symbol.OptionRight
    SymbolTradeExecution = Symbol.TradeExecution

    DayOfWeek = Calendar.DayOfWeek


# Convenient alias for shorter imports: from mt5linux.constants import c
c = MT5Constants  # pylint: disable=invalid-name  # Intentional short alias


# =============================================================================
# CONSTANTS USAGE GUIDELINES - CRITICAL FOR MAINTAINABILITY
# =============================================================================
"""
CONSTANTS SEPARATION RULES - CRITICAL FOR MAINTAINABILITY
==========================================================

1. c.* (mt5linux/constants.py) - SHARED CONSTANTS
   - Use c.* ONLY when constants SHARE DATA with MT5 source code
   - These constants exist in the actual MT5 API or core MT5 logic
   - Examples: c.OrderType.BUY, c.TimeFrame.H1, c.TradeRetcode.DONE

2. tc.* (mt5linux/tests/constants.py) - TEST-ONLY CONSTANTS
   - Use tc.* ONLY for constants used EXCLUSIVELY in tests
   - These constants DO NOT exist in MT5 source code
   - Examples: tc.TEST_PRICE_BASE, tc.TEST_VOLUME_MICRO, tc.TEST_MAGIC_DEFAULT

3. NEVER MIX:
   - Test constants should NEVER go into mt5linux/constants.py
   - Source constants should NEVER be duplicated in tests/constants.py
   - Each constant belongs to EXACTLY ONE place

4. IMPORT RULES:
   - Tests import c from mt5linux.constants (for shared constants)
   - Tests import tc from tests.constants (for test-only constants)

This separation ensures:
- No duplication between source and test constants
- Clear ownership of each constant
- Easy maintenance and refactoring
- Consistent usage patterns across all test files

EXAMPLES:
---------
# ✅ CORRECT: Shared MT5 constant
assert mt5.ORDER_TYPE_BUY == c.OrderType.BUY

# ✅ CORRECT: Test-only constant
assert request.price == tc.TEST_PRICE_BASE

# ❌ WRONG: Don't put test constants in source
# c.TEST_PRICE_BASE = 1.0900  # NEVER DO THIS

# ❌ WRONG: Don't duplicate source constants in tests
# tc.ORDER_TYPE_BUY = 0  # NEVER DO THIS
"""
