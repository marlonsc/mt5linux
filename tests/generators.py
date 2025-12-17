"""Test data generators for MT5 API validation.

Provides:
- Hypothesis strategies for property-based testing
- Date range generators
- Symbol constants
- Order request builders
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import strategies as st

# =============================================================================
# SYMBOL CONSTANTS
# =============================================================================

MAJOR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
ALL_FOREX = [*MAJOR_PAIRS, "USDCHF", "USDCAD", "EURGBP", "EURJPY"]

# Test magic number to identify test orders
TEST_MAGIC = 999999
TEST_COMMENT = "mt5linux_test"

# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Volume strategies (lot size)
volume_micro = st.floats(min_value=0.01, max_value=0.1)
volume_mini = st.floats(min_value=0.1, max_value=1.0)
volume_standard = st.floats(min_value=1.0, max_value=10.0)
volume_valid = st.floats(min_value=0.01, max_value=10.0)

# Price deviation (slippage tolerance in points)
deviation_tight = st.integers(min_value=1, max_value=10)
deviation_normal = st.integers(min_value=10, max_value=50)
deviation_wide = st.integers(min_value=50, max_value=100)
deviation_valid = st.integers(min_value=1, max_value=100)

# Bar/tick count strategies
bar_count_small = st.integers(min_value=1, max_value=100)
bar_count_medium = st.integers(min_value=100, max_value=1000)
bar_count_large = st.integers(min_value=1000, max_value=10000)
bar_count_valid = st.integers(min_value=1, max_value=10000)

# Days back for history queries
days_back_recent = st.integers(min_value=1, max_value=7)
days_back_medium = st.integers(min_value=7, max_value=30)
days_back_long = st.integers(min_value=30, max_value=365)


# =============================================================================
# DATE RANGE GENERATORS
# =============================================================================


def date_range_last_n_days(days: int) -> tuple[datetime, datetime]:
    """Generate date range for last N days.

    Args:
        days: Number of days back from now.

    Returns:
        Tuple of (date_from, date_to) in UTC.

    """
    date_to = datetime.now(UTC)
    date_from = date_to - timedelta(days=days)
    return (date_from, date_to)


def date_range_last_week() -> tuple[datetime, datetime]:
    """Generate date range for last 7 days."""
    return date_range_last_n_days(7)


def date_range_last_month() -> tuple[datetime, datetime]:
    """Generate date range for last 30 days."""
    return date_range_last_n_days(30)


def date_range_last_year() -> tuple[datetime, datetime]:
    """Generate date range for last 365 days."""
    return date_range_last_n_days(365)


def date_range_ytd() -> tuple[datetime, datetime]:
    """Generate date range from start of year to now."""
    now = datetime.now(UTC)
    start_of_year = datetime(now.year, 1, 1, tzinfo=UTC)
    return (start_of_year, now)


# =============================================================================
# ORDER REQUEST BUILDERS
# =============================================================================


def build_market_buy_request(
    symbol: str = "EURUSD",
    volume: float = 0.01,
    deviation: int = 20,
    magic: int = TEST_MAGIC,
    comment: str = TEST_COMMENT,
) -> dict[str, str | float | int]:
    """Build a market buy order request.

    Note: action and type will be set using MT5 constants in test fixtures.

    Args:
        symbol: Trading symbol.
        volume: Lot size (minimum 0.01).
        deviation: Maximum price deviation in points.
        magic: Magic number for order identification.
        comment: Order comment.

    Returns:
        Order request dict (without action/type - add in fixture).

    """
    return {
        "symbol": symbol,
        "volume": volume,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
    }


def build_market_sell_request(
    symbol: str = "EURUSD",
    volume: float = 0.01,
    deviation: int = 20,
    magic: int = TEST_MAGIC,
    comment: str = TEST_COMMENT,
) -> dict[str, str | float | int]:
    """Build a market sell order request.

    Args:
        symbol: Trading symbol.
        volume: Lot size (minimum 0.01).
        deviation: Maximum price deviation in points.
        magic: Magic number for order identification.
        comment: Order comment.

    Returns:
        Order request dict (without action/type - add in fixture).

    """
    return {
        "symbol": symbol,
        "volume": volume,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
    }


def build_limit_order_request(
    symbol: str = "EURUSD",
    volume: float = 0.01,
    price: float = 1.0,
    deviation: int = 20,
    magic: int = TEST_MAGIC,
    comment: str = TEST_COMMENT,
) -> dict[str, str | float | int]:
    """Build a limit order request.

    Args:
        symbol: Trading symbol.
        volume: Lot size (minimum 0.01).
        price: Limit price.
        deviation: Maximum price deviation in points.
        magic: Magic number for order identification.
        comment: Order comment.

    Returns:
        Order request dict (without action/type - add in fixture).

    """
    return {
        "symbol": symbol,
        "volume": volume,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
    }


def build_close_position_request(
    position_ticket: int,
    symbol: str = "EURUSD",
    volume: float = 0.01,
    deviation: int = 20,
    magic: int = TEST_MAGIC,
    comment: str = TEST_COMMENT,
) -> dict[str, str | float | int]:
    """Build a close position request.

    Args:
        position_ticket: Ticket of position to close.
        symbol: Trading symbol.
        volume: Volume to close.
        deviation: Maximum price deviation in points.
        magic: Magic number for order identification.
        comment: Order comment.

    Returns:
        Order request dict (without action/type - add in fixture).

    """
    return {
        "position": position_ticket,
        "symbol": symbol,
        "volume": volume,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
    }
