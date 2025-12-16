"""Parametrized tests for comprehensive MT5 API coverage.

Uses pytest.mark.parametrize for testing across multiple symbols and timeframes.
Uses Hypothesis for property-based testing with generated inputs.

Markers:
    @pytest.mark.slow - Tests that may take longer
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_symbol_price(
    mt5: MetaTrader5, symbol: str
) -> tuple[float | None, float | None]:
    """Get bid/ask prices for a symbol, trying tick first then symbol_info.

    Returns:
        Tuple of (bid, ask) prices, or (None, None) if unavailable.
    """
    # Try tick first (most recent price)
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None and (tick.bid > 0 or tick.ask > 0):
        return tick.bid, tick.ask

    # Fall back to symbol_info (has bid/ask too)
    info = mt5.symbol_info(symbol)
    if info is not None and (info.bid > 0 or info.ask > 0):
        return info.bid, info.ask

    return None, None


def get_symbol_info_with_price(
    mt5: MetaTrader5, symbol: str
) -> tuple[object | None, float | None, float | None]:
    """Get symbol info and prices in one call.

    Returns:
        Tuple of (info, bid, ask). info is None if symbol unavailable.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, None, None

    bid, ask = info.bid, info.ask

    # If info has no prices, try tick
    if bid <= 0 and ask <= 0:
        tick = mt5.symbol_info_tick(symbol)
        if tick is not None:
            bid, ask = tick.bid, tick.ask

    return info, bid, ask


# =============================================================================
# SYMBOL LISTS FOR PARAMETRIZATION
# =============================================================================

# G10 Major Forex Pairs (USD base or quote)
MAJOR_PAIRS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
]

# Cross Pairs (no USD)
CROSS_PAIRS = [
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "EURAUD",
    "EURCHF",
    "AUDNZD",
    "GBPAUD",
    "AUDJPY",
    "CADJPY",
    "NZDJPY",
]

# Precious Metals
METALS = [
    "XAUUSD",  # Gold
    "XAGUSD",  # Silver
]

# Popular Indices (symbol names vary by broker)
INDICES = [
    "US30",     # Dow Jones
    "US500",    # S&P 500
    "US100",    # NASDAQ 100
    "GER40",    # DAX 40
    "UK100",    # FTSE 100
]

# All symbols for comprehensive testing
ALL_SYMBOLS = MAJOR_PAIRS + CROSS_PAIRS + METALS + INDICES

# =============================================================================
# TIMEFRAME LISTS
# =============================================================================

# All available timeframes
ALL_TIMEFRAMES = [
    "TIMEFRAME_M1",
    "TIMEFRAME_M2",
    "TIMEFRAME_M3",
    "TIMEFRAME_M4",
    "TIMEFRAME_M5",
    "TIMEFRAME_M6",
    "TIMEFRAME_M10",
    "TIMEFRAME_M12",
    "TIMEFRAME_M15",
    "TIMEFRAME_M20",
    "TIMEFRAME_M30",
    "TIMEFRAME_H1",
    "TIMEFRAME_H2",
    "TIMEFRAME_H3",
    "TIMEFRAME_H4",
    "TIMEFRAME_H6",
    "TIMEFRAME_H8",
    "TIMEFRAME_H12",
    "TIMEFRAME_D1",
    "TIMEFRAME_W1",
    "TIMEFRAME_MN1",
]

# Common timeframes for faster tests
COMMON_TIMEFRAMES = [
    "TIMEFRAME_M1",
    "TIMEFRAME_M5",
    "TIMEFRAME_M15",
    "TIMEFRAME_M30",
    "TIMEFRAME_H1",
    "TIMEFRAME_H4",
    "TIMEFRAME_D1",
]

# =============================================================================
# LOT SIZE DEFINITIONS
# =============================================================================

# Standard lot sizes for forex
LOT_SIZES_FOREX = [
    0.01,   # Micro lot (1,000 units)
    0.02,
    0.05,
    0.1,    # Mini lot (10,000 units)
    0.2,
    0.5,
    1.0,    # Standard lot (100,000 units)
    2.0,
    5.0,
    10.0,
]

# Lot sizes for metals (may differ by broker)
LOT_SIZES_METALS = [
    0.01,
    0.05,
    0.1,
    0.5,
    1.0,
]

# Lot sizes for indices
LOT_SIZES_INDICES = [
    0.1,
    0.5,
    1.0,
    2.0,
    5.0,
]

# =============================================================================
# DATA COUNT RANGES
# =============================================================================

# Bar/candle counts to test
BAR_COUNTS = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000]

# Tick counts to test
TICK_COUNTS = [1, 10, 50, 100, 500, 1000]

# Date ranges in days
DATE_RANGES_DAYS = [1, 3, 7, 14, 30, 60, 90, 180, 365]

# Position offsets
POSITION_OFFSETS = [0, 10, 50, 100, 500, 1000]


class TestSymbolCoverage:
    """Tests across multiple symbols."""

    # -------------------------------------------------------------------------
    # Major Pairs Tests
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_symbol_info_all_majors(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info for all major pairs."""
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available on this server")
        # Broker may add suffix (e.g., EURUSD.a), so check symbol is contained
        assert symbol in info.name or info.name.startswith(symbol)
        assert info.bid > 0 or info.ask > 0  # At least one price

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_symbol_tick_all_majors(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info_tick for all major pairs."""
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            pytest.skip(f"Symbol {symbol} tick not available on this server")
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_copy_rates_all_symbols(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_rates_from_pos for all major pairs."""
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10)

        # May be None if market data not available for symbol
        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")
            assert rates.dtype.names is not None
            assert "open" in rates.dtype.names
            assert "close" in rates.dtype.names

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_copy_ticks_all_symbols(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_ticks_from for all major pairs."""
        mt5.symbol_select(symbol, True)

        date_from = datetime.now(UTC) - timedelta(minutes=30)
        ticks = mt5.copy_ticks_from(symbol, date_from, 100, mt5.COPY_TICKS_ALL)

        # May be None if tick data not available
        if ticks is not None and len(ticks) > 0:
            assert hasattr(ticks, "dtype")
            assert ticks.dtype.names is not None
            assert "bid" in ticks.dtype.names

    # -------------------------------------------------------------------------
    # Cross Pairs Tests
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("symbol", CROSS_PAIRS)
    def test_symbol_info_cross_pairs(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info for all cross pairs (no USD)."""
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available on this server")
        # Broker may add suffix (e.g., GBPAUD.c), so check symbol is contained
        assert symbol in info.name or info.name.startswith(symbol)
        assert info.bid > 0 or info.ask > 0

    @pytest.mark.parametrize("symbol", CROSS_PAIRS)
    def test_symbol_tick_cross_pairs(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info_tick for all cross pairs."""
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            pytest.skip(f"Symbol {symbol} tick not available on this server")
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.parametrize("symbol", CROSS_PAIRS)
    def test_copy_rates_cross_pairs(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_rates_from_pos for all cross pairs."""
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10)

        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")
            assert rates.dtype.names is not None

    # -------------------------------------------------------------------------
    # Metals Tests
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("symbol", METALS)
    def test_symbol_info_metals(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info for precious metals."""
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Metal {symbol} not available on this server")
        # Broker may add suffix (e.g., XAUUSD.a), so check symbol is contained
        assert symbol in info.name or info.name.startswith(symbol)
        # Metals have much higher prices than forex
        assert info.bid > 0 or info.ask > 0

    @pytest.mark.parametrize("symbol", METALS)
    def test_symbol_tick_metals(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info_tick for precious metals."""
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            pytest.skip(f"Metal {symbol} tick not available on this server")
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.parametrize("symbol", METALS)
    def test_copy_rates_metals(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_rates_from_pos for precious metals."""
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10)

        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")

    # -------------------------------------------------------------------------
    # Indices Tests
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("symbol", INDICES)
    def test_symbol_info_indices(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info for stock indices.

        Note: Index symbol names vary significantly between brokers.
        Common variations: US30/DJ30/DJI, US500/SP500/SPX, etc.
        """
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Index {symbol} not available on this server")
        # Broker may add suffix (e.g., US30.a), so check symbol is contained
        assert symbol in info.name or info.name.startswith(symbol)
        assert info.bid > 0 or info.ask > 0

    @pytest.mark.parametrize("symbol", INDICES)
    def test_symbol_tick_indices(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info_tick for stock indices."""
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            pytest.skip(f"Index {symbol} tick not available on this server")
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.parametrize("symbol", INDICES)
    def test_copy_rates_indices(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_rates_from_pos for stock indices."""
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10)

        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")


# =============================================================================
# TIMEFRAME PARAMETRIZATION
# =============================================================================


class TestTimeframeCoverage:
    """Tests across multiple timeframes."""

    @pytest.mark.parametrize(
        "timeframe_name",
        ["TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_H1"],
    )
    def test_copy_rates_all_timeframes(
        self, mt5: MetaTrader5, timeframe_name: str
    ) -> None:
        """Test copy_rates for all common timeframes."""
        timeframe = getattr(mt5, timeframe_name)
        mt5.symbol_select("EURUSD", True)

        rates = mt5.copy_rates_from_pos("EURUSD", timeframe, 0, 10)

        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")

    @pytest.mark.parametrize(
        "timeframe_name",
        ["TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_H1"],
    )
    def test_copy_rates_from_date_all_timeframes(
        self, mt5: MetaTrader5, timeframe_name: str
    ) -> None:
        """Test copy_rates_from with datetime for multiple timeframes."""
        timeframe = getattr(mt5, timeframe_name)
        mt5.symbol_select("EURUSD", True)

        date_from = datetime.now(UTC) - timedelta(days=7)
        rates = mt5.copy_rates_from("EURUSD", timeframe, date_from, 10)

        if rates is not None:
            assert len(rates) > 0


# =============================================================================
# COMBINED PARAMETRIZATION
# =============================================================================


class TestCombinedCoverage:
    """Tests with combined symbol x timeframe parametrization."""

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "symbol", ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "EURGBP"]
    )
    @pytest.mark.parametrize(
        "timeframe_name",
        ["TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_H1", "TIMEFRAME_H4"],
    )
    def test_rates_matrix(
        self, mt5: MetaTrader5, symbol: str, timeframe_name: str
    ) -> None:
        """Test rates for symbol x timeframe combinations."""
        timeframe = getattr(mt5, timeframe_name)
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 10)

        if rates is not None:
            assert len(rates) > 0
            # Verify OHLCV data
            if (
                rates.dtype
                and hasattr(rates.dtype, "names")
                and rates.dtype.names is not None
            ):
                for name in ["open", "high", "low", "close", "tick_volume"]:
                    assert name in rates.dtype.names
            else:
                pytest.fail("rates object does not have named fields in dtype")

    @pytest.mark.slow
    @pytest.mark.parametrize("symbol", ALL_SYMBOLS)
    def test_symbol_select_all(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_select for all defined symbols.

        This ensures all symbols in our test lists can be selected.
        Unavailable symbols are skipped gracefully.
        """
        result = mt5.symbol_select(symbol, True)

        if not result:
            info = mt5.symbol_info(symbol)
            if info is None:
                pytest.skip(f"Symbol {symbol} not available on this server")

    @pytest.mark.slow
    @pytest.mark.parametrize("symbol", ALL_SYMBOLS)
    def test_market_book_all_symbols(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test market_book_add/release for all symbols.

        Market depth may not be available for all symbols.
        """
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available on this server")

        # Try to subscribe to market depth
        result = mt5.market_book_add(symbol)
        if result:
            # Get market depth data
            book = mt5.market_book_get(symbol)
            # May be None if no depth data available
            if book is not None:
                assert isinstance(book, tuple)

            # Clean up subscription
            mt5.market_book_release(symbol)


# =============================================================================


class TestHypothesisProperties:
    """Property-based tests using Hypothesis."""

    @given(count=st.integers(min_value=1, max_value=100))
    @settings(
        max_examples=10,
        deadline=None,  # RPyC operations can be slow
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_copy_rates_count_property(self, mt5: MetaTrader5, count: int) -> None:
        """Property: returned rates count should be <= requested count."""
        mt5.symbol_select("EURUSD", True)

        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, count)

        if rates is not None:
            assert len(rates) <= count

    @given(days_back=st.integers(min_value=1, max_value=30))
    @settings(
        max_examples=5,
        deadline=None,  # RPyC operations can be slow
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_rates_range_property(self, mt5: MetaTrader5, days_back: int) -> None:
        """Property: rates in range should be within requested dates."""
        mt5.symbol_select("EURUSD", True)

        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_D1, date_from, date_to)

        if rates is not None and len(rates) > 0:
            # First rate should be >= date_from
            first_time = datetime.fromtimestamp(rates[0]["time"], tz=UTC)
            assert first_time >= date_from - timedelta(days=1)  # Allow 1 day tolerance

    @given(
        volume=st.floats(min_value=0.01, max_value=1.0),
        deviation=st.integers(min_value=1, max_value=50),
    )
    @settings(
        max_examples=5,
        deadline=None,  # RPyC operations can be slow
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @pytest.mark.trading
    def test_order_check_volume_property(
        self, mt5: MetaTrader5, volume: float, deviation: int
    ) -> None:
        """Property: order_check should accept valid volumes."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None or ask is None or ask <= 0:
            pytest.skip(f"Symbol {symbol} or price not available")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": round(volume, 2),
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask,
            "deviation": deviation,
            "magic": 999999,
            "comment": "hypothesis_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_check(request)

        # Should either succeed or fail gracefully
        if result is not None:
            assert result.balance >= 0


# =============================================================================
# DATE RANGE PARAMETRIZATION
# =============================================================================


class TestDateRangeCoverage:
    """Tests with various date range configurations."""

    @pytest.mark.parametrize(
        "days_back",
        [1, 7, 30, 90],
    )
    def test_history_deals_date_ranges(self, mt5: MetaTrader5, days_back: int) -> None:
        """Test history_deals_total with various date ranges.

        Note: May return None if no history available for the date range.
        """
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        total = mt5.history_deals_total(date_from, date_to)

        # May return None if no history available
        assert total is None or (isinstance(total, int) and total >= 0)

    @pytest.mark.parametrize(
        "days_back",
        [1, 7, 30, 90],
    )
    def test_history_orders_date_ranges(self, mt5: MetaTrader5, days_back: int) -> None:
        """Test history_orders_total with various date ranges.

        Note: May return None if no history available for the date range.
        """
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        total = mt5.history_orders_total(date_from, date_to)

        # May return None if no history available
        assert total is None or (isinstance(total, int) and total >= 0)


# =============================================================================
# CONSTANTS VALIDATION
# =============================================================================


class TestConstantsAccess:
    """Tests for MT5 constants access."""

    @pytest.mark.parametrize(
        ("constant_name", "expected_value"),
        [
            ("ORDER_TYPE_BUY", 0),
            ("ORDER_TYPE_SELL", 1),
            ("ORDER_TYPE_BUY_LIMIT", 2),
            ("ORDER_TYPE_SELL_LIMIT", 3),
            ("ORDER_TYPE_BUY_STOP", 4),
            ("ORDER_TYPE_SELL_STOP", 5),
        ],
    )
    def test_order_type_constants(
        self, mt5: MetaTrader5, constant_name: str, expected_value: int
    ) -> None:
        """Test ORDER_TYPE_* constants have expected values."""
        value = getattr(mt5, constant_name)
        assert value == expected_value

    @pytest.mark.parametrize(
        ("constant_name", "expected_value"),
        [
            ("TIMEFRAME_M1", 1),
            ("TIMEFRAME_M5", 5),
            ("TIMEFRAME_M15", 15),
            ("TIMEFRAME_M30", 30),
            ("TIMEFRAME_H1", 16385),
            ("TIMEFRAME_H4", 16388),
            ("TIMEFRAME_D1", 16408),
            ("TIMEFRAME_W1", 32769),
            ("TIMEFRAME_MN1", 49153),
        ],
    )
    def test_timeframe_constants(
        self, mt5: MetaTrader5, constant_name: str, expected_value: int
    ) -> None:
        """Test TIMEFRAME_* constants have expected values."""
        value = getattr(mt5, constant_name)
        assert value == expected_value

    @pytest.mark.parametrize(
        "constant_name",
        [
            "TRADE_RETCODE_DONE",
            "TRADE_RETCODE_REQUOTE",
            "TRADE_RETCODE_REJECT",
            "TRADE_RETCODE_CANCEL",
            "TRADE_RETCODE_PLACED",
            "TRADE_RETCODE_ERROR",
        ],
    )
    def test_trade_retcode_constants_exist(
        self, mt5: MetaTrader5, constant_name: str
    ) -> None:
        """Test TRADE_RETCODE_* constants exist."""
        value = getattr(mt5, constant_name)
        assert isinstance(value, int)


# =============================================================================
# LOT SIZE VALIDATION
# =============================================================================


class TestLotSizeCoverage:
    """Tests for lot size validation across different instruments."""

    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "USDJPY"])
    @pytest.mark.parametrize("lot_size", LOT_SIZES_FOREX)
    def test_order_check_forex_lot_sizes(
        self, mt5: MetaTrader5, symbol: str, lot_size: float
    ) -> None:
        """Test order_check with various forex lot sizes."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        # Check lot size is within broker limits
        if lot_size < info.volume_min or lot_size > info.volume_max:
            pytest.skip(
                f"Lot size {lot_size} outside broker limits "
                f"({info.volume_min}-{info.volume_max})"
            )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask,
            "deviation": 20,
            "magic": 999999,
            "comment": "lot_size_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_check(request)

        # Should return a result (success or failure with reason)
        if result is not None:
            assert hasattr(result, "retcode")
            assert hasattr(result, "balance")

    @pytest.mark.parametrize("lot_size", LOT_SIZES_METALS)
    def test_order_check_gold_lot_sizes(
        self, mt5: MetaTrader5, lot_size: float
    ) -> None:
        """Test order_check with various gold lot sizes."""
        symbol = "XAUUSD"
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        if lot_size < info.volume_min or lot_size > info.volume_max:
            pytest.skip(
                f"Lot size {lot_size} outside broker limits "
                f"({info.volume_min}-{info.volume_max})"
            )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask,
            "deviation": 50,
            "magic": 999999,
            "comment": "gold_lot_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_check(request)

        if result is not None:
            assert hasattr(result, "retcode")

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS[:3])
    def test_symbol_volume_limits(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test that symbol volume limits are properly returned."""
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        # Volume limits should be positive and make sense
        assert info.volume_min > 0
        assert info.volume_max > info.volume_min
        assert info.volume_step > 0
        assert info.volume_step <= info.volume_min

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD", "US30"])
    def test_margin_calculation_various_lots(
        self, mt5: MetaTrader5, symbol: str
    ) -> None:
        """Test margin calculation for different lot sizes."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        # Test with minimum lot
        margin_min = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY, symbol, info.volume_min, ask
        )

        # Test with 1.0 lot (if within limits)
        if info.volume_max >= 1.0:
            margin_1lot = mt5.order_calc_margin(
                mt5.ORDER_TYPE_BUY, symbol, 1.0, ask
            )

            if margin_min is not None and margin_1lot is not None:
                # Margin should scale with lot size
                ratio = 1.0 / info.volume_min
                expected_ratio = margin_1lot / margin_min
                # Allow 10% tolerance for rounding
                assert abs(ratio - expected_ratio) / ratio < 0.1


# =============================================================================
# DATA RANGE COVERAGE
# =============================================================================


class TestDataRangeCoverage:
    """Tests for various data count and date range combinations."""

    @pytest.mark.parametrize("count", BAR_COUNTS)
    def test_copy_rates_various_counts(self, mt5: MetaTrader5, count: int) -> None:
        """Test copy_rates_from_pos with various bar counts."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, count)

        if rates is not None:
            assert len(rates) <= count
            assert len(rates) > 0
            # Verify data structure
            assert "time" in rates.dtype.names
            assert "open" in rates.dtype.names
            assert "high" in rates.dtype.names
            assert "low" in rates.dtype.names
            assert "close" in rates.dtype.names

    @pytest.mark.parametrize("count", TICK_COUNTS)
    def test_copy_ticks_various_counts(self, mt5: MetaTrader5, count: int) -> None:
        """Test copy_ticks_from with various tick counts."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = mt5.copy_ticks_from(symbol, date_from, count, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            assert len(ticks) <= count
            assert "time" in ticks.dtype.names
            assert "bid" in ticks.dtype.names
            assert "ask" in ticks.dtype.names

    @pytest.mark.parametrize("days_back", DATE_RANGES_DAYS)
    def test_copy_rates_range_various_periods(
        self, mt5: MetaTrader5, days_back: int
    ) -> None:
        """Test copy_rates_range with various date ranges."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, date_from, date_to)

        if rates is not None and len(rates) > 0:
            # Should return approximately days_back bars (excluding weekends)
            # Allow for market closures
            assert len(rates) <= days_back + 1
            # Verify chronological order
            for i in range(1, len(rates)):
                assert rates[i]["time"] > rates[i - 1]["time"]

    @pytest.mark.parametrize("offset", POSITION_OFFSETS)
    def test_copy_rates_various_offsets(self, mt5: MetaTrader5, offset: int) -> None:
        """Test copy_rates_from_pos with various position offsets."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, offset, 10)

        if rates is not None and len(rates) > 0:
            assert len(rates) <= 10
            # Verify OHLC validity
            for rate in rates:
                assert rate["high"] >= rate["low"]
                assert rate["high"] >= rate["open"]
                assert rate["high"] >= rate["close"]
                assert rate["low"] <= rate["open"]
                assert rate["low"] <= rate["close"]

    @pytest.mark.slow
    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "XAUUSD"])
    @pytest.mark.parametrize("count", [100, 1000, 5000])
    def test_copy_rates_symbol_count_matrix(
        self, mt5: MetaTrader5, symbol: str, count: int
    ) -> None:
        """Test copy_rates with symbol x count combinations."""
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)

        if rates is not None:
            assert len(rates) <= count
            assert len(rates) > 0


# =============================================================================
# COMPREHENSIVE TIMEFRAME COVERAGE
# =============================================================================


class TestAllTimeframes:
    """Tests covering all MT5 timeframes."""

    @pytest.mark.slow
    @pytest.mark.parametrize("timeframe_name", ALL_TIMEFRAMES)
    def test_copy_rates_all_timeframes(
        self, mt5: MetaTrader5, timeframe_name: str
    ) -> None:
        """Test copy_rates_from_pos for all available timeframes."""
        try:
            timeframe = getattr(mt5, timeframe_name)
        except AttributeError:
            pytest.skip(f"Timeframe {timeframe_name} not available")

        mt5.symbol_select("EURUSD", True)
        rates = mt5.copy_rates_from_pos("EURUSD", timeframe, 0, 100)

        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")

    @pytest.mark.slow
    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD"])
    @pytest.mark.parametrize("timeframe_name", COMMON_TIMEFRAMES)
    @pytest.mark.parametrize("count", [10, 100, 1000])
    def test_symbol_timeframe_count_matrix(
        self, mt5: MetaTrader5, symbol: str, timeframe_name: str, count: int
    ) -> None:
        """Test comprehensive symbol x timeframe x count matrix."""
        timeframe = getattr(mt5, timeframe_name)
        mt5.symbol_select(symbol, True)

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

        if rates is not None:
            assert len(rates) <= count
            assert len(rates) > 0
            # Verify OHLCV structure
            required_fields = ["time", "open", "high", "low", "close", "tick_volume"]
            for field in required_fields:
                assert field in rates.dtype.names


# =============================================================================
# TICK DATA COVERAGE
# =============================================================================


class TestTickDataCoverage:
    """Tests for tick data retrieval with various parameters."""

    @pytest.mark.parametrize(
        "tick_flag_name",
        ["COPY_TICKS_ALL", "COPY_TICKS_INFO", "COPY_TICKS_TRADE"],
    )
    def test_copy_ticks_all_flags(
        self, mt5: MetaTrader5, tick_flag_name: str
    ) -> None:
        """Test copy_ticks with different tick flags."""
        tick_flag = getattr(mt5, tick_flag_name)
        mt5.symbol_select("EURUSD", True)

        date_from = datetime.now(UTC) - timedelta(minutes=30)
        ticks = mt5.copy_ticks_from("EURUSD", date_from, 100, tick_flag)

        if ticks is not None and len(ticks) > 0:
            assert hasattr(ticks, "dtype")
            # All tick types should have these fields
            assert "time" in ticks.dtype.names
            assert "bid" in ticks.dtype.names
            assert "ask" in ticks.dtype.names

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS[:4])
    @pytest.mark.parametrize("minutes_back", [5, 15, 30, 60])
    def test_copy_ticks_symbol_time_matrix(
        self, mt5: MetaTrader5, symbol: str, minutes_back: int
    ) -> None:
        """Test copy_ticks with symbol x time range combinations."""
        mt5.symbol_select(symbol, True)

        date_from = datetime.now(UTC) - timedelta(minutes=minutes_back)
        ticks = mt5.copy_ticks_from(symbol, date_from, 500, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            # Verify tick data validity
            for tick in ticks[:10]:  # Check first 10
                assert tick["bid"] > 0 or tick["ask"] > 0
                # Spread should be non-negative
                if tick["bid"] > 0 and tick["ask"] > 0:
                    assert tick["ask"] >= tick["bid"]

    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD"])
    def test_copy_ticks_range(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test copy_ticks_range with date boundaries."""
        mt5.symbol_select(symbol, True)

        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(minutes=10)

        ticks = mt5.copy_ticks_range(symbol, date_from, date_to, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            # Verify chronological order
            for i in range(1, min(len(ticks), 100)):
                assert ticks[i]["time_msc"] >= ticks[i - 1]["time_msc"]


# =============================================================================
# ORDER TYPE COMBINATIONS
# =============================================================================


class TestOrderTypeCombinations:
    """Tests for various order type and filling mode combinations."""

    @pytest.mark.parametrize(
        "order_type_name",
        ["ORDER_TYPE_BUY", "ORDER_TYPE_SELL"],
    )
    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "XAUUSD"])
    def test_order_check_buy_sell(
        self, mt5: MetaTrader5, order_type_name: str, symbol: str
    ) -> None:
        """Test order_check for BUY and SELL across symbols."""
        order_type = getattr(mt5, order_type_name)
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        price = ask if order_type == mt5.ORDER_TYPE_BUY else bid
        if price is None or price <= 0:
            pytest.skip(f"No price available for {symbol}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": info.volume_min,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 999999,
            "comment": "order_type_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_check(request)

        if result is not None:
            assert hasattr(result, "retcode")
            assert hasattr(result, "request")

    @pytest.mark.parametrize(
        "order_type_name",
        [
            "ORDER_TYPE_BUY_LIMIT",
            "ORDER_TYPE_SELL_LIMIT",
            "ORDER_TYPE_BUY_STOP",
            "ORDER_TYPE_SELL_STOP",
        ],
    )
    def test_order_check_pending_types(
        self, mt5: MetaTrader5, order_type_name: str
    ) -> None:
        """Test order_check for pending order types."""
        order_type = getattr(mt5, order_type_name)
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if bid is None or ask is None or bid <= 0 or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        # Set price based on order type
        if order_type_name in ["ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_STOP"]:
            price = bid - (100 * info.point)  # Below current price
        else:  # SELL_LIMIT, BUY_STOP
            price = ask + (100 * info.point)  # Above current price

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": info.volume_min,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 999999,
            "comment": "pending_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_check(request)

        if result is not None:
            assert hasattr(result, "retcode")

    @pytest.mark.parametrize(
        "filling_name",
        ["ORDER_FILLING_FOK", "ORDER_FILLING_IOC", "ORDER_FILLING_RETURN"],
    )
    def test_order_check_filling_modes(
        self, mt5: MetaTrader5, filling_name: str
    ) -> None:
        """Test order_check with different filling modes."""
        filling_mode = getattr(mt5, filling_name)
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": info.volume_min,
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask,
            "deviation": 20,
            "magic": 999999,
            "comment": "filling_test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        result = mt5.order_check(request)

        # Should return a result (may reject invalid filling for symbol)
        if result is not None:
            assert hasattr(result, "retcode")


# =============================================================================
# PROFIT CALCULATION COVERAGE
# =============================================================================


class TestProfitCalculation:
    """Tests for profit calculation with various parameters."""

    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "USDJPY"])
    @pytest.mark.parametrize("lot_size", [0.01, 0.1, 1.0])
    @pytest.mark.parametrize("pips", [10, 50, 100])
    def test_order_calc_profit_matrix(
        self, mt5: MetaTrader5, symbol: str, lot_size: float, pips: int
    ) -> None:
        """Test profit calculation for symbol x lot x pips combinations."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        if lot_size < info.volume_min or lot_size > info.volume_max:
            pytest.skip(f"Lot size {lot_size} outside limits")

        # Calculate profit for a winning trade
        price_open = ask
        price_close = price_open + (pips * info.point * 10)  # pips in points

        profit = mt5.order_calc_profit(
            mt5.ORDER_TYPE_BUY, symbol, lot_size, price_open, price_close
        )

        if profit is not None:
            # Profit should be positive for a winning BUY trade
            assert profit > 0

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD"])
    def test_order_calc_profit_buy_vs_sell(
        self, mt5: MetaTrader5, symbol: str
    ) -> None:
        """Test that BUY and SELL profits are symmetric."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if bid is None or bid <= 0:
            pytest.skip(f"No price available for {symbol}")

        lot = info.volume_min
        price1 = bid
        price2 = bid + (100 * info.point)

        # BUY: enter at price1, exit at price2 (profit)
        profit_buy = mt5.order_calc_profit(
            mt5.ORDER_TYPE_BUY, symbol, lot, price1, price2
        )

        # SELL: enter at price2, exit at price1 (profit)
        profit_sell = mt5.order_calc_profit(
            mt5.ORDER_TYPE_SELL, symbol, lot, price2, price1
        )

        if profit_buy is not None and profit_sell is not None:
            # Both should be positive (winning trades)
            assert profit_buy > 0
            assert profit_sell > 0
            # Should be approximately equal
            assert abs(profit_buy - profit_sell) / profit_buy < 0.1


# =============================================================================
# MARGIN CALCULATION COVERAGE
# =============================================================================


class TestMarginCalculation:
    """Tests for margin calculation with various parameters."""

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS[:4])
    @pytest.mark.parametrize("lot_size", [0.01, 0.1, 1.0])
    def test_order_calc_margin_matrix(
        self, mt5: MetaTrader5, symbol: str, lot_size: float
    ) -> None:
        """Test margin calculation for symbol x lot combinations."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        if lot_size < info.volume_min or lot_size > info.volume_max:
            pytest.skip(f"Lot size {lot_size} outside limits")

        margin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY, symbol, lot_size, ask
        )

        if margin is not None:
            assert margin > 0

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD", "US30"])
    def test_margin_scales_with_lot(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test that margin scales linearly with lot size."""
        mt5.symbol_select(symbol, True)
        info, bid, ask = get_symbol_info_with_price(mt5, symbol)

        if info is None:
            pytest.skip(f"Symbol {symbol} not available")

        if ask is None or ask <= 0:
            pytest.skip(f"No price available for {symbol}")

        lot1 = info.volume_min
        lot2 = lot1 * 2

        if lot2 > info.volume_max:
            pytest.skip("Cannot test with doubled lot size")

        margin1 = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot1, ask)
        margin2 = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot2, ask)

        if margin1 is not None and margin2 is not None:
            # Margin should approximately double
            ratio = margin2 / margin1
            assert 1.9 < ratio < 2.1  # Allow 5% tolerance
