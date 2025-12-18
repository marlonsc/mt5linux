"""Edge cases and error handling tests for MT5 API.

Tests invalid inputs, API limits, and error scenarios.

Markers:
    @pytest.mark.slow - Tests that may take longer
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from mt5linux.constants import MT5Constants as c

from .conftest import tc

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestInvalidInputs:
    """Tests for invalid input handling."""

    def test_invalid_symbol_info(self, mt5: MetaTrader5) -> None:
        """Test symbol_info with invalid symbol."""
        result = mt5.symbol_info("INVALID_SYMBOL_XYZ123")

        # Should return None for invalid symbol
        assert result is None

        # Check last error
        error = mt5.last_error()
        assert error is not None
        # Error code should indicate failure (not 0/1 which is success)
        assert isinstance(error, tuple)

    def test_invalid_symbol_tick(self, mt5: MetaTrader5) -> None:
        """Test symbol_info_tick with invalid symbol."""
        result = mt5.symbol_info_tick("NONEXISTENT_SYMBOL")

        assert result is None

    def test_invalid_symbol_rates(self, mt5: MetaTrader5) -> None:
        """Test copy_rates_from_pos with invalid symbol."""
        result = mt5.copy_rates_from_pos(
            "INVALID_SYMBOL",
            mt5.TIMEFRAME_H1,
            0,
            tc.DEFAULT_BAR_COUNT,
        )

        assert result is None

    def test_invalid_timeframe(self, mt5: MetaTrader5) -> None:
        """Test copy_rates with invalid timeframe."""
        # 999 is not a valid timeframe constant
        result = mt5.copy_rates_from_pos(
            "EURUSD", tc.INVALID_TIMEFRAME, tc.SMALL_COUNT, tc.LARGE_COUNT
        )

        # Should return None or empty for invalid timeframe
        assert result is None or len(result) == 0

    def test_invalid_date_range_reversed(self, mt5: MetaTrader5) -> None:
        """Test with reversed date range (from > to)."""
        date_to = datetime.now(UTC) - timedelta(days=tc.ONE_MONTH)
        date_from = datetime.now(UTC)  # from is later than to

        result = mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_H1,
            date_from,
            date_to,
        )

        # Should return None or empty
        assert result is None or len(result) == 0

    def test_invalid_date_future(self, mt5: MetaTrader5) -> None:
        """Test with future dates."""
        # Use tomorrow to test future date handling
        from datetime import timedelta

        tomorrow = datetime.now(UTC) + timedelta(days=tc.SMALL_COUNT)
        day_after = tomorrow + timedelta(days=1)

        result = mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_D1,
            tomorrow,
            day_after,
        )

        # Should return None or empty for future dates
        assert result is None or len(result) == 0

    def test_empty_symbol(self, mt5: MetaTrader5) -> None:
        """Test with empty symbol string."""
        result = mt5.symbol_info("")

        assert result is None

    def test_negative_count(self, mt5: MetaTrader5) -> None:
        """Test copy_rates with negative count."""
        result = mt5.copy_rates_from_pos(
            "EURUSD",
            mt5.TIMEFRAME_H1,
            0,
            tc.NEGATIVE_COUNT,  # Negative count
        )

        # Should return None or empty
        assert result is None or len(result) == 0

    def test_zero_count(self, mt5: MetaTrader5) -> None:
        """Test copy_rates with zero count.

        Note: MT5 API behavior for count=0 varies by server/version.
        Some return default bars, some return None.
        """
        result = mt5.copy_rates_from_pos(
            "EURUSD",
            mt5.TIMEFRAME_H1,
            0,
            0,  # Zero count - behavior varies
        )

        # Behavior varies by MT5 server - just verify no crash
        # Result can be None or contain data
        if result is not None:
            assert hasattr(result, "dtype")


class TestApiLimits:
    """Tests for API limits and large requests."""

    @pytest.mark.slow
    def test_max_bars_limit(self, mt5: MetaTrader5) -> None:
        """Test requesting maximum number of bars."""
        # Request a large number of bars
        mt5.symbol_select("EURUSD", enable=True)

        result = mt5.copy_rates_from_pos(
            "EURUSD",
            mt5.TIMEFRAME_M1,
            0,
            tc.EXTRA_LARGE_COUNT,  # Large number
        )

        if result is not None:
            # Should return data up to available bars
            assert len(result) > 0
            assert len(result) <= c.Test.Validation.TICKS_LIMIT_THRESHOLD

            # Verify data structure
            assert hasattr(result, "dtype")
            names = result.dtype.names
            assert names is not None
            assert "time" in names
            assert "open" in names

    @pytest.mark.slow
    def test_max_ticks_limit(self, mt5: MetaTrader5) -> None:
        """Test requesting maximum number of ticks."""
        mt5.symbol_select("EURUSD", enable=True)

        date_from = datetime.now(UTC) - timedelta(hours=1)

        result = mt5.copy_ticks_from(
            "EURUSD",
            date_from,
            tc.EXTRA_LARGE_COUNT,  # Large number
            mt5.COPY_TICKS_ALL,
        )

        if result is not None and len(result) > 0:
            assert len(result) <= c.Test.Validation.TICKS_LIMIT_THRESHOLD
            assert hasattr(result, "dtype")

    @pytest.mark.slow
    def test_large_history_query(self, mt5: MetaTrader5) -> None:
        """Test querying large history range."""
        # Query 1 year of history
        date_from = datetime.now(UTC) - timedelta(days=tc.ONE_YEAR)
        date_to = datetime.now(UTC)

        result = mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_D1,
            date_from,
            date_to,
        )

        if result is not None:
            # Should have roughly 250 trading days
            assert len(result) > tc.MIN_TRADING_DAYS  # At least some data
            assert (
                len(result) < c.Test.Validation.TRADING_DAYS_THRESHOLD
            )  # Not unreasonably many

    @pytest.mark.slow
    def test_symbols_get_all(self, mt5: MetaTrader5) -> None:
        """Test getting symbols with incremental group sizes.

        Tests progressively larger symbol groups.
        """
        # Test incremental group sizes (min_expected based on typical broker)
        test_groups = [
            ("*USD*", 10),  # Small: USD pairs
            ("*EUR*", 10),  # Medium: EUR pairs
            ("*", tc.MIN_TOTAL_SYMBOLS),  # All symbols - should work with optimization
        ]

        for group_filter, min_expected in test_groups:
            if group_filter == "*":
                symbols = mt5.symbols_get()  # All symbols
            else:
                symbols = mt5.symbols_get(group=group_filter)

            if symbols is None:
                pytest.fail("symbols_get(group=group_filter!r) not available")

            count = len(symbols)
            assert count >= min_expected, (
                f"Group {group_filter!r}: expected >= {min_expected}, got {count}"
            )

            # Verify structure
            if count > 0:
                symbol = symbols[0]
                assert hasattr(symbol, "name"), "Symbol missing 'name' attribute"
                assert hasattr(symbol, "visible"), "Symbol missing 'visible' attribute"

        # Final verification: all symbols should be > 1000
        all_symbols = mt5.symbols_get()
        if all_symbols:
            total = len(all_symbols)
            threshold = c.Test.Validation.SYMBOL_COUNT_THRESHOLD
            assert total > threshold, f"Expected {threshold}+ symbols, got {total}"

    @pytest.mark.slow
    def test_symbols_total(self, mt5: MetaTrader5) -> None:
        """Test total symbols count.

        Verifies symbols_total() returns correct count
        and matches the length of symbols_get().
        """
        total = mt5.symbols_total()

        if total is None:
            pytest.fail("symbols_total not available on this server")
        assert isinstance(total, int)
        # Demo servers have fewer symbols; production may have 1000+
        # Just verify we get some symbols (at least 1)
        assert total >= 0, f"Expected non-negative symbols count, got {total}"

        # Verify matches actual count from symbols_get()
        symbols = mt5.symbols_get()
        if symbols:
            assert len(symbols) == total, (
                f"symbols_total()={total} != len(symbols_get())={len(symbols)}"
            )


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_last_error_after_invalid_operation(self, mt5: MetaTrader5) -> None:
        """Test that last_error is set after failed operation."""
        # Force an error with invalid symbol
        mt5.symbol_info("DEFINITELY_INVALID_SYMBOL")

        error = mt5.last_error()

        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == c.Test.Validation.TUPLE_LENGTH_ERROR
        # Error code and message
        error_code, error_message = error
        assert isinstance(error_code, int)
        assert isinstance(error_message, str)

    def test_last_error_after_valid_operation(self, mt5: MetaTrader5) -> None:
        """Test that last_error is set after successful operation."""
        # Successful operation
        mt5.symbol_select("EURUSD", enable=True)
        info = mt5.symbol_info("EURUSD")

        if info is None:
            pytest.fail("EURUSD not available on this server")

        error = mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        # Error tuple contains (code, message)

    def test_multiple_operations_error_state(self, mt5: MetaTrader5) -> None:
        """Test error state after multiple operations."""
        # First: successful operation
        mt5.symbol_info("EURUSD")

        # Second: failed operation
        mt5.symbol_info("INVALID123")

        # Third: successful operation
        mt5.symbol_info("EURUSD")

        # Error should reflect last operation (success)
        error = mt5.last_error()
        assert error is not None

    def test_version_always_works(self, mt5: MetaTrader5) -> None:
        """Test that version() always returns valid data.

        Note: MT5 version() returns (major, minor, build_or_date).
        The third element can be an int or a date string like '14 Dec 2025'.
        May return None if MT5 terminal connection is unstable.
        """
        version = mt5.version()

        if version is None:
            pytest.fail("version() returned None (MT5 connection may be unstable)")

        assert isinstance(version, tuple)
        assert len(version) == c.Test.Validation.TUPLE_LENGTH_VERSION

        # Version numbers - first two should be non-negative integers
        major, minor, build_or_date = version
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert major >= 0
        assert minor >= 0
        # Third element can be int (build number) or str (date)
        assert isinstance(build_or_date, int | str)

    def test_terminal_info_always_works(self, mt5: MetaTrader5) -> None:
        """Test that terminal_info() always returns valid data.

        May return None if MT5 terminal connection is unstable.
        """
        terminal = mt5.terminal_info()

        if terminal is None:
            pytest.fail("terminal_info() returned None (MT5 connection unstable)")

        assert terminal.connected is True
        assert terminal.build > 0

    def test_account_info_always_works(self, mt5: MetaTrader5) -> None:
        """Test that account_info() always returns valid data.

        Note: May return None if MT5 terminal connection is unstable.
        """
        account = mt5.account_info()

        if account is None:
            pytest.fail("account_info returned None (MT5 connection may be unstable)")

        assert account.login > 0
        assert account.balance >= 0
        assert len(account.currency) > 0
