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

from tests.conftest import tc

# =============================================================================
# SYMBOL CONSTANTS (moved to TestConstants)
# =============================================================================

# Constants are now accessed via c.* for consistency

# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Volume strategies (lot size)
volume_micro = st.floats(
    min_value=tc.Generators.VOLUME_MIN, max_value=tc.Generators.VOLUME_DEFAULT
)
volume_mini = st.floats(
    min_value=tc.Generators.VOLUME_DEFAULT, max_value=tc.Generators.VOLUME_MAX
)
volume_standard = st.floats(
    min_value=tc.Generators.VOLUME_DEFAULT, max_value=tc.Generators.VOLUME_MAX
)
volume_valid = st.floats(
    min_value=tc.Generators.VOLUME_MIN, max_value=tc.Generators.VOLUME_MAX
)

# Price deviation (slippage tolerance in points)
deviation_tight = st.integers(
    min_value=tc.Generators.DEVIATION_MIN, max_value=tc.Generators.DEVIATION_TIGHT
)
deviation_normal = st.integers(
    min_value=tc.Generators.DEVIATION_TIGHT, max_value=tc.Generators.DEVIATION_NORMAL
)
deviation_wide = st.integers(
    min_value=tc.Generators.DEVIATION_NORMAL, max_value=tc.Generators.DEVIATION_WIDE
)
deviation_valid = st.integers(
    min_value=tc.Generators.DEVIATION_MIN, max_value=tc.Generators.DEVIATION_WIDE
)

# Bar/tick count strategies
bar_count_small = st.integers(
    min_value=tc.Generators.BAR_COUNT_MIN, max_value=tc.Generators.BAR_COUNT_SMALL
)
bar_count_medium = st.integers(
    min_value=tc.Generators.BAR_COUNT_SMALL, max_value=tc.Generators.BAR_COUNT_MEDIUM
)
bar_count_large = st.integers(
    min_value=tc.Generators.BAR_COUNT_MEDIUM, max_value=tc.Generators.BAR_COUNT_LARGE
)
bar_count_valid = st.integers(
    min_value=tc.Generators.BAR_COUNT_MIN, max_value=tc.Generators.BAR_COUNT_LARGE
)

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
    magic: int = tc.INVALID_TEST_MAGIC,
    comment: str = tc.TEST_COMMENT,
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
    magic: int = tc.INVALID_TEST_MAGIC,
    comment: str = tc.TEST_COMMENT,
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


def build_limit_order_request(  # noqa: PLR0913
    symbol: str = "EURUSD",
    volume: float = 0.01,
    price: float = 1.0,
    deviation: int = 20,
    magic: int = tc.INVALID_TEST_MAGIC,
    comment: str = tc.TEST_COMMENT,
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


def build_close_position_request(  # noqa: PLR0913
    position_ticket: int,
    symbol: str = "EURUSD",
    volume: float = 0.01,
    deviation: int = 20,
    magic: int = tc.INVALID_TEST_MAGIC,
    comment: str = tc.TEST_COMMENT,
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
