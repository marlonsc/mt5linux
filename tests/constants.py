"""Centralized test constants for Neptor trading platform.

This module contains all magic numbers, default values, and configuration constants
used throughout the test suite. Organized by business domain namespaces.

Advanced patterns used:
- StrEnum for string enumerations (nested in business domain classes)
- IntEnum for integer enumerations (nested in business domain classes)
- Literal types for restricted string values
- Final constants for immutable values
- Frozen sets for immutable collections
- Typed mappings for structured constants
- Class-based namespaces organized by business domain, NOT by data type

Usage (Test Constants - tc):
    from tests.constants import TestConstants as tc
    port = tc.MT5.GRPC_PORT
    symbol = tc.Financial.DEFAULT_SYMBOL
    timeout = tc.Network.SOCKET_TIMEOUT
    compression_type = tc.Kafka.CompressionType.GZIP

Usage (Source Constants - c):
    from mt5linux.constants import c
    port = c.Network.TEST_GRPC_PORT
    timeout = c.Network.TIMEOUT_CONNECTION
"""

from __future__ import annotations

import os
from enum import IntEnum, StrEnum
from typing import Final

# =============================================================================
# GLOBAL CONSTANTS - Available throughout the test suite
# =============================================================================

# Environment defaults
DEFAULT_SKIP_DOCKER: Final[str] = "0"
DEFAULT_MT5_LOGIN: Final[str] = "0"

# Test-specific constants
TEST_ORDER_MAGIC: Final[int] = 123456
HISTORY_TEST_MAGIC: Final[int] = 888888
INVALID_TEST_MAGIC: Final[int] = 999999

# Trading parameters
DEFAULT_DEVIATION: Final[int] = 20
HIGH_DEVIATION: Final[int] = 50
INVALID_DEVIATION: Final[int] = 0

# Volumes
MICRO_LOT: Final[float] = 0.01
MINI_LOT: Final[float] = 0.1
STANDARD_LOT: Final[float] = 1.0

# Timeouts
FAST_TIMEOUT: Final[int] = 2
MEDIUM_TIMEOUT: Final[int] = 5
SLOW_TIMEOUT: Final[int] = 10
CONTAINER_TIMEOUT: Final[int] = 60

# Data counts
LOG_TAIL_LINES: Final[int] = 50

# Strings
TEST_COMMENT: Final[str] = "pytest test order"
TEST_CLOSE_COMMENT: Final[str] = "pytest cleanup"

# Invalid values
INVALID_TIMEFRAME: Final[int] = 999

# =============================================================================
# MAIN TEST CONSTANTS CLASS
# =============================================================================


class TestConstants:
    """Centralized constants for all tests.

    Advanced patterns with flat namespace organization:
    - StrEnum classes for string enumerations
    - IntEnum classes for integer enumerations
    - Final constants for immutable values
    - Literal types for restricted string values
    - Frozen sets for immutable collections
    - Typed mappings for structured constants

    All constants accessed directly via c.* (no additional aliases).
    """

    # =========================================================================
    # MT5 & INFRASTRUCTURE CONSTANTS
    # =========================================================================

    class MT5:
        """MT5 Docker and connection constants."""

        # Enums for configuration
        class EnvironmentType(StrEnum):
            """Application environment types."""

            DEVELOPMENT = "development"
            TESTING = "testing"
            STAGING = "staging"
            PRODUCTION = "production"

        class LogLevelType(StrEnum):
            """Logging level types."""

            DEBUG = "DEBUG"
            INFO = "INFO"
            WARNING = "WARNING"
            ERROR = "ERROR"
            CRITICAL = "CRITICAL"

        # Configuration values
        GRPC_PORT: Final[int] = int(os.getenv("MT5_GRPC_PORT", "28812"))
        VNC_PORT: Final[int] = int(os.getenv("MT5_VNC_PORT", "23000"))
        HEALTH_PORT: Final[int] = int(os.getenv("MT5_HEALTH_PORT", "28002"))
        STARTUP_TIMEOUT: Final[int] = int(os.getenv("MT5_STARTUP_TIMEOUT", "420"))
        DEFAULT_TIMEOUT: Final[int] = 60
        DEFAULT_MT5_LOGIN: Final[str] = "0"  # Default test login ID
        HISTORY_MAGIC: Final[int] = 888888  # Magic for history test orders
        TEST_MAGIC: Final[int] = 999999  # Magic for test orders
        TEST_ORDER_MAGIC: Final[int] = 777777  # Magic for test order execution
        INVALID_TEST_MAGIC: Final[int] = -1  # Invalid magic for error testing
        INVALID_LOGIN: Final[int] = 99999999  # Invalid login for error testing
        DEFAULT_SKIP_DOCKER: Final[str] = "0"  # Run Docker tests by default
        DEFAULT_DEVIATION: Final[int] = 20  # Default price deviation
        HIGH_DEVIATION: Final[int] = 100  # High deviation for volatile markets
        LOG_TAIL_LINES: Final[int] = 50  # Lines to show from container logs
        TEST_COMMENT: Final[str] = "test_order"  # Default test order comment
        INVALID_TIMEFRAME: Final[int] = 99999  # Invalid timeframe for error tests

    class Connection:
        """Connection and API constants."""

        DEFAULT_TIMEOUT: Final[int] = 60
        CONNECTION_TIMEOUT_MS: Final[int] = 60000  # 60s in milliseconds
        IPC_TIMEOUT_ERROR: Final[int] = -10005

    class Database:
        """Database connection constants."""

        POSTGRES_DEFAULT_PORT: Final[int] = 5432
        POSTGRES_DEFAULT_HOST: Final = "localhost"
        POSTGRES_TEST_DATABASE: Final = "test_db"
        POSTGRES_TEST_USER: Final = "test_user"
        CLICKHOUSE_DEFAULT_PORT: Final[int] = 9000
        MAX_CONNECTIONS_DEFAULT: Final[int] = 20
        CONNECTION_TIMEOUT_DEFAULT: Final[int] = 30
        CUSTOM_CLICKHOUSE_PORT: Final[int] = 9001
        CUSTOM_POSTGRES_PORT: Final[int] = 5433
        CUSTOM_MAX_CONNECTIONS: Final[int] = 50

    class Kafka:
        """Kafka configuration constants."""

        # Enums for Kafka configuration
        class CompressionType(StrEnum):
            """Kafka compression types."""

            NONE = "none"
            GZIP = "gzip"
            SNAPPY = "snappy"
            LZ4 = "lz4"
            ZSTD = "zstd"

        class AcksMode(StrEnum):
            """Kafka acknowledgment modes."""

            ZERO = "0"
            ONE = "1"
            ALL = "all"
            LEADER = "-1"

        # Configuration values
        BOOTSTRAP_SERVERS: Final[tuple[str, ...]] = ("localhost:9092",)
        DEFAULT_PORT: Final[int] = 9092
        DEFAULT_HOST: Final = "localhost"
        DEFAULT_RETRIES: Final[int] = 3
        CUSTOM_RETRIES: Final[int] = 5
        SOCKET_TIMEOUT: Final[float] = 2.0

    class Network:
        """Network and connection constants."""

        SOCKET_TIMEOUT: Final[float] = 2.0
        GRPC_DEFAULT_TIMEOUT: Final[float] = 10.0
        GRPC_STARTUP_TIMEOUT: Final[float] = 30.0
        PORT_CHECK_MAX_ATTEMPTS: Final[int] = 3
        GRPC_MAX_MESSAGE_SIZE: Final[int] = 50 * 1024 * 1024  # 50MB
        TEST_GRPC_HOST: Final[str] = "localhost"
        TEST_GRPC_PORT: Final[int] = 28812
        TEST_PROTOCOL_PORT: Final[int] = 28812
        CONCURRENT_CONNECTIONS: Final[int] = 5  # For concurrency tests

    class Timing:
        """Timing and retry constants."""

        MIN_RETRY_INTERVAL: Final[float] = 0.5
        MAX_RETRY_INTERVAL: Final[float] = 5.0
        RETRY_BACKOFF_MULTIPLIER: Final[float] = 1.5
        DOCKER_START_TIMEOUT: Final[int] = 300
        SLOW_TIMEOUT: Final[int] = 30  # Timeout for slow operations like Docker
        FAST_TIMEOUT: Final[int] = 2  # Fast timeout for quick checks
        CONTAINER_TIMEOUT: Final[int] = 60  # Timeout for container operations
        MEDIUM_TIMEOUT: Final[float] = 5.0  # Medium timeout for general ops
        FIVE_ITERATIONS: Final[int] = 5  # Common iteration count

    # =========================================================================
    # FINANCIAL & TRADING CONSTANTS
    # =========================================================================

    class Financial:
        """Financial and trading constants."""

        DEFAULT_BASE_PRICE: Final[float] = 1.1000
        DEFAULT_SYMBOL: Final = "EURUSD"
        DEFAULT_VOLUME: Final[float] = 0.1
        DEFAULT_SL_PERCENTAGE: Final[float] = 0.005  # 0.5%
        DEFAULT_TP_PERCENTAGE: Final[float] = 0.005  # 0.5%
        PRICE_VOLATILITY: Final[float] = 0.001
        PRICE_NOISE: Final[float] = 0.0008
        HIGH_LOW_SPREAD: Final[float] = 0.0005
        VOLUME_MIN: Final[int] = 1000
        VOLUME_MAX: Final[int] = 10000
        SYMBOL_POINT_DEFAULT: Final[float] = 0.00001
        VOLUME_MIN_DEFAULT: Final[float] = 0.01
        VOLUME_MAX_DEFAULT: Final[float] = 1000.0
        VOLUME_STEP_DEFAULT: Final[float] = 0.01
        CONTRACT_SIZE_DEFAULT: Final[int] = 100000
        MARGIN_REQUIRED_DEFAULT: Final[float] = 1000.0

        # Lot sizes (in standard lots)
        MICRO_LOT: Final[float] = 0.01  # 1,000 units
        MINI_LOT: Final[float] = 0.1  # 10,000 units
        HALF_STANDARD_LOT: Final[float] = 0.5  # 50,000 units
        STANDARD_LOT: Final[float] = 1.0  # 100,000 units
        DOUBLE_STANDARD_LOT: Final[float] = 2.0  # 200,000 units
        FIVE_STANDARD_LOTS: Final[float] = 5.0  # 500,000 units
        TEN_STANDARD_LOTS: Final[float] = 10.0  # 1,000,000 units

        # Invalid/edge case values for testing
        INVALID_VOLUME: Final[float] = 1500.0  # Exceeds max (1000.0)
        ZERO_VOLUME: Final[float] = 0.0  # Zero volume for error tests

        # Price increments
        TEN_PIPS: Final[float] = 0.0010  # 10 pips for EURUSD
        ONE_PERCENT: Final[float] = 0.01  # 1% for calculations

    class Risk:
        """Risk management constants."""

        # Enums for risk configuration
        class RiskProfileType(StrEnum):
            """Risk profile types."""

            CONSERVATIVE = "CONSERVATIVE"
            MODERATE = "MODERATE"
            AGGRESSIVE = "AGGRESSIVE"
            CUSTOM = "CUSTOM"

        # Configuration values
        MAX_POSITION_SIZE_DEFAULT: Final[float] = 0.05
        MAX_PORTFOLIO_RISK_DEFAULT: Final[float] = 0.02
        MAX_DRAWDOWN_DEFAULT: Final[float] = 0.15
        MAX_POSITIONS_DEFAULT: Final[int] = 10
        MAX_LEVERAGE_DEFAULT: Final[float] = 1.0
        CUSTOM_MAX_POSITION_SIZE: Final[float] = 0.1
        CUSTOM_MAX_PORTFOLIO_RISK: Final[float] = 0.05
        CUSTOM_MAX_POSITIONS: Final[int] = 20
        INVALID_MAX_POSITION_SIZE: Final[float] = 0.5
        INVALID_MAX_PORTFOLIO_RISK: Final[float] = 0.15
        INVALID_MAX_DRAWDOWN: Final[float] = 0.6

    class Signal:
        """Trading signal configuration constants."""

        # Enums for signals
        class SignalType(StrEnum):
            """Trading signal types."""

            BUY = "BUY"
            SELL = "SELL"
            HOLD = "HOLD"

        class IndicatorType(StrEnum):
            """Technical indicator types."""

            RSI = "RSI"
            MACD = "MACD"
            BOLLINGER_BANDS = "BOLLINGER_BANDS"
            SMA = "SMA"
            EMA = "EMA"
            STOCHASTIC = "STOCHASTIC"
            ADX = "ADX"
            ATR = "ATR"
            WILLIAMS_R = "WILLIAMS_R"
            CCI = "CCI"

        # Configuration values
        DEFAULT_CONFIDENCE: Final[float] = 0.8
        SIGNAL_STOP_LOSS_FACTOR: Final[float] = 0.995  # 0.5% below entry
        SIGNAL_TAKE_PROFIT_FACTOR: Final[float] = 1.02  # 2% above entry
        RSI_OVERSOLD_DEFAULT: Final[float] = 30.0
        RSI_OVERBOUGHT_DEFAULT: Final[float] = 70.0
        RSI_PERIOD_DEFAULT: Final[int] = 14
        MACD_FAST_DEFAULT: Final[int] = 12
        MACD_SLOW_DEFAULT: Final[int] = 26
        MACD_SIGNAL_DEFAULT: Final[int] = 9
        MIN_CONFIDENCE_DEFAULT: Final[float] = 0.6
        CUSTOM_RSI_OVERSOLD: Final[float] = 25.0
        CUSTOM_RSI_OVERBOUGHT: Final[float] = 75.0
        CUSTOM_MIN_CONFIDENCE: Final[float] = 0.7
        INVALID_RSI_OVERSOLD: Final[float] = -5.0
        INVALID_RSI_OVERBOUGHT: Final[float] = 105.0
        INVALID_MIN_CONFIDENCE: Final[float] = 0.3

    class Order:
        """Order execution constants."""

        # Enums for orders
        class OrderMechanism(StrEnum):
            """Order execution mechanisms."""

            MARKET = "MARKET"
            LIMIT = "LIMIT"
            STOP = "STOP"
            STOP_LIMIT = "STOP_LIMIT"
            TRAILING_STOP = "TRAILING_STOP"

        class OrderStatus(StrEnum):
            """Order lifecycle status."""

            PENDING = "PENDING"
            SUBMITTED = "SUBMITTED"
            FILLED = "FILLED"
            PARTIALLY_FILLED = "PARTIALLY_FILLED"
            REJECTED = "REJECTED"
            CANCELLED = "CANCELLED"
            EXPIRED = "EXPIRED"

        class RouterPriority(IntEnum):
            """Order router priority levels."""

            LOW = 1
            HIGH = 2

        # Configuration values
        ROUTER_DEFAULT_LATENCY: Final[float] = 0.0
        ROUTER_DEFAULT_SUCCESS_RATE: Final[float] = 1.0
        ROUTER_HIGH_LATENCY: Final[float] = 15.5
        ROUTER_MEDIUM_SUCCESS_RATE: Final[float] = 0.98
        ROUTER_ROUTING_COST: Final[float] = 0.001
        ROUTER_SUCCESS_PROBABILITY: Final[float] = 0.95

    # =========================================================================
    # TESTING & ML CONSTANTS
    # =========================================================================

    class Backtest:
        """Backtesting configuration constants."""

        INITIAL_CAPITAL_DEFAULT: Final[float] = 100000.0
        COMMISSION_DEFAULT: Final[float] = 0.001
        SLIPPAGE_DEFAULT: Final[float] = 0.0001
        RISK_FREE_RATE_DEFAULT: Final[float] = 0.02
        CUSTOM_MAX_POSITION_SIZE_BT: Final[float] = 0.10
        CUSTOM_INITIAL_CAPITAL: Final[float] = 50000.0
        CUSTOM_COMMISSION: Final[float] = 0.002
        INVALID_INITIAL_CAPITAL: Final[float] = 0.0
        INVALID_COMMISSION: Final[float] = 1.5
        INVALID_RISK_FREE_RATE: Final[float] = -0.1
        DURATION_DAYS_DEFAULT: Final[int] = 365
        FINAL_CAPITAL_DEFAULT: Final[float] = 110000.0
        TOTAL_RETURN_DEFAULT: Final[float] = 0.10

    class ML:
        """Machine learning training constants."""

        TRAIN_SIZE_DEFAULT: Final[float] = 0.8
        VALIDATION_SIZE_DEFAULT: Final[float] = 0.1
        TEST_SIZE_DEFAULT: Final[float] = 0.1
        RANDOM_STATE: Final[int] = 42
        LOOKBACK_PERIODS: Final[int] = 5
        TREND_DEFAULT: Final[float] = 0.00001
        CUSTOM_TRAIN_SIZE: Final[float] = 0.7
        CUSTOM_VALIDATION_SIZE: Final[float] = 0.15
        CUSTOM_TEST_SIZE: Final[float] = 0.15
        INVALID_TRAIN_SIZE_SUM: Final[float] = 0.5
        INVALID_VALIDATION_SIZE_SUM: Final[float] = 0.3
        INVALID_TEST_SIZE_SUM: Final[float] = 0.3
        VALID_TRAIN_SIZE: Final[float] = 0.6
        VALID_VALIDATION_SIZE: Final[float] = 0.2
        VALID_TEST_SIZE: Final[float] = 0.2

    class Prediction:
        """ML prediction constants."""

        CONFIDENCE_THRESHOLD_DEFAULT: Final[float] = 0.6
        CONFIDENCE_THRESHOLD_HIGH: Final[float] = 0.8
        CONFIDENCE_THRESHOLD_LOW: Final[float] = 0.5
        CONFIDENCE_THRESHOLD_MAX: Final[float] = 1.0
        CONFIDENCE_THRESHOLD_INVALID_LOW: Final[float] = -0.1
        CONFIDENCE_THRESHOLD_INVALID_HIGH: Final[float] = 1.1

    class Benchmark:
        """Performance benchmarking constants."""

        ITERATIONS: Final[int] = 100
        PERF_P99_PERCENTILE: Final[float] = 0.99
        CACHE_TTL_DEFAULT: Final[float] = 60.0

    # =========================================================================
    # TEST DATA & VALIDATION CONSTANTS
    # =========================================================================

    class TestData:
        """Test data generation and validation constants."""

        # Enums for test data
        class IssueType(StrEnum):
            """Test data issue types."""

            INVALID_OHLC = "invalid_ohlc"
            NEGATIVE_PRICES = "negative_prices"
            MISSING_DATA = "missing_data"

        class TrendType(StrEnum):
            """Test data trend types."""

            UPWARD = "upward"
            DOWNWARD = "downward"
            SIDEWAYS = "sideways"

        # Configuration values
        DEFAULT_PERIODS: Final[int] = 100
        MARKET_DATA_DAYS: Final[int] = 30
        TEST_PERIODS_VALID: Final[int] = 50
        TEST_PERIODS_EMPTY: Final[int] = 0
        TEST_PERIODS_SMALL: Final[int] = 20
        INTEGRATION_PERIODS_DEFAULT: Final[int] = 100
        INTEGRATION_PERIODS_SMALL: Final[int] = 20
        OHLC_INVALID_THRESHOLD: Final[int] = 0
        INVALID_HIGH_PRICE: Final[float] = 1.0990
        INVALID_LOW_PRICE: Final[float] = 1.0985
        INVALID_CLOSE_PRICE: Final[float] = 1.1005
        TREND_UP_VALUE: Final[float] = 0.0001
        TREND_DOWN_VALUE: Final[float] = -0.0001
        TREND_SIDEWAYS_VALUE: Final[float] = 0.0
        VOLATILITY_LOW: Final[float] = 0.0001
        VOLATILITY_MEDIUM: Final[float] = 0.0005
        PRICE_INCREMENT: Final[float] = 0.0001
        HIGH_LOW_SPREAD_SU: Final[float] = 0.0005
        CLOSE_ADJUSTMENT: Final[float] = 0.0002
        BASE_VOLUME_SU: Final[int] = 1000

        # Bar and tick data constants
        DEFAULT_BAR_COUNT: Final[int] = 100
        DEFAULT_TICK_COUNT: Final[int] = 1000
        HUNDRED_ITEMS: Final[int] = 100
        ONE_WEEK: Final[int] = 7
        ONE_MONTH: Final[int] = 30
        EXTRA_LARGE_COUNT: Final[int] = 10000

        # Count constants for tests
        TEN_ITEMS: Final[int] = 10
        FIFTY_ITEMS: Final[int] = 50
        SMALL_COUNT: Final[int] = 1
        MEDIUM_COUNT: Final[int] = 30
        LARGE_COUNT: Final[int] = 500
        NEGATIVE_COUNT: Final[int] = -1

        # Time durations
        ONE_HOUR: Final[int] = 1  # hours
        ONE_YEAR: Final[int] = 365  # days

        # Trading test data
        MIN_TRADING_DAYS: Final[int] = 200
        MIN_TOTAL_SYMBOLS: Final[int] = 10

        # Parametrized test ranges
        BAR_COUNTS: Final[tuple[int, ...]] = (10, 50, 100, 500)
        TICK_COUNTS: Final[tuple[int, ...]] = (100, 500, 1000, 5000)
        DATE_RANGES_DAYS: Final[tuple[int, ...]] = (1, 7, 30, 90)

    class Validation:
        """Data validation constants."""

        MODEL_SIZE_MIN_BYTES: Final[int] = 0
        TEST_TIMEOUT_SECONDS: Final[int] = 120
        TEST_EXECUTION_TIMEOUT: Final[int] = 120
        STDOUT_TRUNCATE_LENGTH: Final[int] = 1000
        VERSION_TUPLE_LENGTH: Final[int] = 3  # (version, build, string)
        ERROR_TUPLE_LENGTH: Final[int] = 2  # (code, description)
        SYMBOLS_TEST_COUNT: Final[int] = 5  # Number of symbols for batch tests
        SYMBOLS_RATES_COUNT: Final[int] = 5  # Number of symbols for rates tests

    class Logging:
        """Logging configuration constants."""

        MIN_LOGGER_HANDLERS: Final[int] = 1
        MIN_LOGGER_HANDLERS_WITH_FILE: Final[int] = 2

    # =========================================================================
    # COLLECTIONS & ENUMERATIONS
    # =========================================================================

    class Collections:
        """Immutable collections for test configuration."""

        # Note: Enums referenced here will be initialized after
        # TestConstants class definition
        # See post-class initialization block below
        COMPRESSION_TYPES: frozenset[str]  # Initialized post-class
        ACKS_MODES: frozenset[str]  # Initialized post-class
        SAFE_TEST_SYMBOLS: Final[tuple[str, ...]] = (
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCAD",
            "USDCHF",
            "NZDUSD",
            "EURJPY",
            "GBPJPY",
            "BTCUSD",
        )
        REQUIRED_OHLC_COLUMNS: Final[frozenset[str]] = frozenset(
            {"Open", "High", "Low", "Close", "Volume"}
        )
        TEST_TIMEFRAMES: Final[tuple[str, ...]] = ("M1", "M5", "M15", "H1", "H4", "D1")

    # =========================================================================
    # DIRECT ACCESS ALIASES (FREQUENTLY USED)
    # =========================================================================

    # These are the ONLY aliases allowed - direct access to frequently used constants

    # Financial constants
    DEFAULT_SYMBOL = Financial.DEFAULT_SYMBOL
    DEFAULT_VOLUME = Financial.DEFAULT_VOLUME
    DEFAULT_BASE_PRICE = Financial.DEFAULT_BASE_PRICE

    # Database constants
    POSTGRES_DEFAULT_HOST = Database.POSTGRES_DEFAULT_HOST
    POSTGRES_DEFAULT_PORT = Database.POSTGRES_DEFAULT_PORT
    POSTGRES_TEST_DATABASE = Database.POSTGRES_TEST_DATABASE
    POSTGRES_TEST_USER = Database.POSTGRES_TEST_USER
    CLICKHOUSE_DEFAULT_PORT = Database.CLICKHOUSE_DEFAULT_PORT
    MAX_CONNECTIONS_DEFAULT = Database.MAX_CONNECTIONS_DEFAULT
    CONNECTION_TIMEOUT_DEFAULT = Database.CONNECTION_TIMEOUT_DEFAULT
    CUSTOM_CLICKHOUSE_PORT = Database.CUSTOM_CLICKHOUSE_PORT
    CUSTOM_POSTGRES_PORT = Database.CUSTOM_POSTGRES_PORT
    CUSTOM_MAX_CONNECTIONS = Database.CUSTOM_MAX_CONNECTIONS

    # Test data constants
    DEFAULT_PERIODS = TestData.DEFAULT_PERIODS
    TEST_PERIODS_VALID = TestData.TEST_PERIODS_VALID
    INTEGRATION_PERIODS_DEFAULT = TestData.INTEGRATION_PERIODS_DEFAULT
    INVALID_HIGH_PRICE = TestData.INVALID_HIGH_PRICE
    INVALID_LOW_PRICE = TestData.INVALID_LOW_PRICE
    INVALID_CLOSE_PRICE = TestData.INVALID_CLOSE_PRICE
    TREND_UP_VALUE = TestData.TREND_UP_VALUE
    TREND_DOWN_VALUE = TestData.TREND_DOWN_VALUE
    TREND_SIDEWAYS_VALUE = TestData.TREND_SIDEWAYS_VALUE
    VOLATILITY_LOW = TestData.VOLATILITY_LOW
    VOLATILITY_MEDIUM = TestData.VOLATILITY_MEDIUM
    OHLC_INVALID_THRESHOLD = TestData.OHLC_INVALID_THRESHOLD
    PRICE_INCREMENT = TestData.PRICE_INCREMENT
    HIGH_LOW_SPREAD_SU = TestData.HIGH_LOW_SPREAD_SU
    CLOSE_ADJUSTMENT = TestData.CLOSE_ADJUSTMENT
    BASE_VOLUME_SU = TestData.BASE_VOLUME_SU
    TEST_PERIODS_EMPTY = TestData.TEST_PERIODS_EMPTY
    TEST_PERIODS_SMALL = TestData.TEST_PERIODS_SMALL
    INTEGRATION_PERIODS_SMALL = TestData.INTEGRATION_PERIODS_SMALL

    # Validation constants
    MODEL_SIZE_MIN_BYTES = Validation.MODEL_SIZE_MIN_BYTES
    TEST_TIMEOUT_SECONDS = Validation.TEST_TIMEOUT_SECONDS
    TEST_EXECUTION_TIMEOUT = Validation.TEST_EXECUTION_TIMEOUT
    STDOUT_TRUNCATE_LENGTH = Validation.STDOUT_TRUNCATE_LENGTH

    # Logging constants
    MIN_LOGGER_HANDLERS = Logging.MIN_LOGGER_HANDLERS
    MIN_LOGGER_HANDLERS_WITH_FILE = Logging.MIN_LOGGER_HANDLERS_WITH_FILE

    # Prediction constants
    CONFIDENCE_THRESHOLD_DEFAULT = Prediction.CONFIDENCE_THRESHOLD_DEFAULT
    CONFIDENCE_THRESHOLD_HIGH = Prediction.CONFIDENCE_THRESHOLD_HIGH
    CONFIDENCE_THRESHOLD_LOW = Prediction.CONFIDENCE_THRESHOLD_LOW
    CONFIDENCE_THRESHOLD_MAX = Prediction.CONFIDENCE_THRESHOLD_MAX
    CONFIDENCE_THRESHOLD_INVALID_LOW = Prediction.CONFIDENCE_THRESHOLD_INVALID_LOW
    CONFIDENCE_THRESHOLD_INVALID_HIGH = Prediction.CONFIDENCE_THRESHOLD_INVALID_HIGH

    # Environment defaults
    DEFAULT_SKIP_DOCKER = DEFAULT_SKIP_DOCKER
    DEFAULT_MT5_LOGIN = DEFAULT_MT5_LOGIN

    # MT5 legacy alias for backward compatibility
    MT5_DEFAULT_TIMEOUT = MT5.DEFAULT_TIMEOUT

    # Lot size aliases (direct access)
    MICRO_LOT = Financial.MICRO_LOT
    MINI_LOT = Financial.MINI_LOT
    HALF_STANDARD_LOT = Financial.HALF_STANDARD_LOT
    STANDARD_LOT = Financial.STANDARD_LOT
    DOUBLE_STANDARD_LOT = Financial.DOUBLE_STANDARD_LOT
    FIVE_STANDARD_LOTS = Financial.FIVE_STANDARD_LOTS
    TEN_STANDARD_LOTS = Financial.TEN_STANDARD_LOTS

    # Test data aliases (direct access)
    DEFAULT_BAR_COUNT = TestData.DEFAULT_BAR_COUNT
    DEFAULT_TICK_COUNT = TestData.DEFAULT_TICK_COUNT
    HUNDRED_ITEMS = TestData.HUNDRED_ITEMS
    ONE_MONTH = TestData.ONE_MONTH
    EXTRA_LARGE_COUNT = TestData.EXTRA_LARGE_COUNT
    BAR_COUNTS = TestData.BAR_COUNTS
    TICK_COUNTS = TestData.TICK_COUNTS
    DATE_RANGES_DAYS = TestData.DATE_RANGES_DAYS

    # Timing aliases (direct access)
    SLOW_TIMEOUT = Timing.SLOW_TIMEOUT
    FAST_TIMEOUT = Timing.FAST_TIMEOUT
    CONTAINER_TIMEOUT = Timing.CONTAINER_TIMEOUT
    DEFAULT_MT5_LOGIN = DEFAULT_MT5_LOGIN

    # MT5 trading aliases (direct access)
    TEST_ORDER_MAGIC = MT5.TEST_ORDER_MAGIC
    DEFAULT_DEVIATION = MT5.DEFAULT_DEVIATION
    HIGH_DEVIATION = MT5.HIGH_DEVIATION
    LOG_TAIL_LINES = MT5.LOG_TAIL_LINES

    # Test data time aliases
    ONE_WEEK = TestData.ONE_WEEK
    ONE_HOUR = TestData.ONE_HOUR
    ONE_YEAR = TestData.ONE_YEAR

    # Test data count aliases
    TEN_ITEMS = TestData.TEN_ITEMS
    FIFTY_ITEMS = TestData.FIFTY_ITEMS
    SMALL_COUNT = TestData.SMALL_COUNT
    MEDIUM_COUNT = TestData.MEDIUM_COUNT
    LARGE_COUNT = TestData.LARGE_COUNT
    NEGATIVE_COUNT = TestData.NEGATIVE_COUNT
    MIN_TRADING_DAYS = TestData.MIN_TRADING_DAYS
    MIN_TOTAL_SYMBOLS = TestData.MIN_TOTAL_SYMBOLS

    # Network aliases
    GRPC_MAX_MESSAGE_SIZE = Network.GRPC_MAX_MESSAGE_SIZE
    TEST_GRPC_HOST = Network.TEST_GRPC_HOST
    TEST_GRPC_PORT = Network.TEST_GRPC_PORT
    TEST_PROTOCOL_PORT = Network.TEST_PROTOCOL_PORT
    CONCURRENT_CONNECTIONS = Network.CONCURRENT_CONNECTIONS

    # Timing additional aliases
    MEDIUM_TIMEOUT = Timing.MEDIUM_TIMEOUT
    FIVE_ITERATIONS = Timing.FIVE_ITERATIONS

    # Mappings and Sets are available as module-level constants
    # Access via: from tests.constants import VOLUME_TO_UNITS, VALID_LOT_SIZES

    # Validation aliases
    VERSION_TUPLE_LENGTH = Validation.VERSION_TUPLE_LENGTH
    ERROR_TUPLE_LENGTH = Validation.ERROR_TUPLE_LENGTH
    SYMBOLS_TEST_COUNT = Validation.SYMBOLS_TEST_COUNT
    SYMBOLS_RATES_COUNT = Validation.SYMBOLS_RATES_COUNT

    # Financial aliases
    ZERO_VOLUME = Financial.ZERO_VOLUME
    TEN_PIPS = Financial.TEN_PIPS
    ONE_PERCENT = Financial.ONE_PERCENT
    INVALID_VOLUME = Financial.INVALID_VOLUME
    # MT5 additional aliases (referencing existing constants)
    INVALID_TEST_MAGIC = MT5.INVALID_TEST_MAGIC
    TEST_COMMENT = MT5.TEST_COMMENT
    INVALID_TIMEFRAME = MT5.INVALID_TIMEFRAME

    # Test model constants (test-only values)
    TEST_VOLUME_MICRO: Final[float] = 0.01
    TEST_PRICE_BASE: Final[float] = 1.0900
    TEST_PRICE_HIGH: Final[float] = 1.1000
    TEST_DEVIATION_NORMAL: Final[int] = 20
    TEST_MAGIC_DEFAULT: Final[int] = 123456
    TEST_ORDER_DEFAULT: Final[int] = 1
    TEST_RETCODE_SUCCESS: Final[int] = 0
    TEST_ACCOUNT_BALANCE: Final[float] = 10000.0
    TEST_ACCOUNT_EQUITY_HIGH: Final[float] = 10500.0
    TEST_PRICE_INCREMENT: Final[float] = 0.0001
    TEST_SPREAD_POINTS: Final[int] = 2
    TEST_MAGIC_LARGE: Final[int] = 999999
    TEST_ACCOUNT_LOW: Final[float] = 9500.0
    TEST_TIMESTAMP_EPOCH: Final[int] = 0
    TEST_ORDER_COUNT_LOW: Final[int] = 1
    TEST_ORDER_COUNT_HIGH: Final[int] = 10
    TEST_RETCODE_REQUOTE: Final[int] = 10004
    TEST_RETCODE_NO_MONEY: Final[int] = 10019
    TEST_MAGIC_ALT: Final[int] = 654321
    TEST_ACCOUNT_LEVERAGE: Final[int] = 100
    TEST_CONFIDENCE_HIGH: Final[float] = 0.95


# =============================================================================
# POST-CLASS INITIALIZATION (Collections that depend on enums)
# =============================================================================
# Initialize Collections with actual enum values after class definition
TestConstants.Collections.COMPRESSION_TYPES = frozenset(
    compression.value for compression in TestConstants.Kafka.CompressionType
)
TestConstants.Collections.ACKS_MODES = frozenset(
    acks.value for acks in TestConstants.Kafka.AcksMode
)


# =============================================================================
# CONSTANTS USAGE GUIDELINES - CRITICAL FOR MAINTAINABILITY
# =============================================================================
"""
TEST CONSTANTS SEPARATION RULES - CRITICAL FOR MAINTAINABILITY
===============================================================

This file (mt5linux/tests/constants.py) contains ONLY constants
used EXCLUSIVELY in tests.

1. tc.* (mt5linux/tests/constants.py) - TEST-ONLY CONSTANTS
   - Constants that exist ONLY in test code
   - NEVER duplicated from source constants
   - Examples: tc.TEST_PRICE_BASE, tc.TEST_VOLUME_MICRO

2. c.* (mt5linux/constants.py) - SHARED CONSTANTS
   - Constants that SHARE DATA with MT5 source code
   - These exist in the actual MT5 API or core logic
   - Examples: c.Order.OrderType.BUY, c.MarketData.TimeFrame.H1

3. NEVER MIX:
   - Source constants should NEVER be duplicated here
   - Test constants should NEVER go into mt5linux/constants.py

4. IMPORT RULES:
   - Use tc.* for constants defined in this file
   - Use c.* for constants shared with MT5 source

EXAMPLES:
---------
# Correct: Test-only constant (defined in TestConstants)
assert request.price == tc.TEST_PRICE_BASE

# Correct: Shared constant (imported from mt5linux.constants)
assert mt5.ORDER_TYPE_BUY == c.Order.OrderType.BUY

# Wrong: Don't duplicate source constants
# tc.ORDER_TYPE_BUY = 0  <- NEVER DO THIS

# Wrong: Don't reference test constants from source
# TEST_PRICE_BASE = c.Validation.TEST_PRICE_BASE  <- NEVER DO THIS
"""
