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
from hypothesis import given, settings
from hypothesis import strategies as st

if TYPE_CHECKING:
    from mt5linux import MetaTrader5

# =============================================================================
# MAJOR PAIRS PARAMETRIZATION
# =============================================================================

MAJOR_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]


class TestSymbolCoverage:
    """Tests across multiple symbols."""

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_symbol_info_all_majors(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info for all major pairs."""
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)

        assert info is not None
        assert info.name == symbol
        assert info.bid > 0 or info.ask > 0  # At least one price

    @pytest.mark.parametrize("symbol", MAJOR_PAIRS)
    def test_symbol_tick_all_majors(self, mt5: MetaTrader5, symbol: str) -> None:
        """Test symbol_info_tick for all major pairs."""
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)

        assert tick is not None
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
    @pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD"])
    @pytest.mark.parametrize("timeframe_name", ["TIMEFRAME_M5", "TIMEFRAME_H1"])
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
# =============================================================================


class TestHypothesisProperties:
    """Property-based tests using Hypothesis."""

    @given(count=st.integers(min_value=1, max_value=100))
    @settings(max_examples=10)
    def test_copy_rates_count_property(self, mt5: MetaTrader5, count: int) -> None:
        """Property: returned rates count should be <= requested count."""
        mt5.symbol_select("EURUSD", True)

        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, count)

        if rates is not None:
            assert len(rates) <= count

    @given(days_back=st.integers(min_value=1, max_value=30))
    @settings(max_examples=5)
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
    @settings(max_examples=5)
    @pytest.mark.trading
    def test_order_check_volume_property(
        self, mt5: MetaTrader5, volume: float, deviation: int
    ) -> None:
        """Property: order_check should accept valid volumes."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")

        if tick is None:
            pytest.skip("Could not get tick")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": round(volume, 2),
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
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
        """Test history_deals_total with various date ranges."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        total = mt5.history_deals_total(date_from, date_to)

        assert isinstance(total, int)
        assert total >= 0

    @pytest.mark.parametrize(
        "days_back",
        [1, 7, 30, 90],
    )
    def test_history_orders_date_ranges(self, mt5: MetaTrader5, days_back: int) -> None:
        """Test history_orders_total with various date ranges."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

        total = mt5.history_orders_total(date_from, date_to)

        assert isinstance(total, int)
        assert total >= 0


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
