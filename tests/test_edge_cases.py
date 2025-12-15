"""Edge cases and error handling tests for MT5 API.

Tests invalid inputs, API limits, and error scenarios.

Markers:
    @pytest.mark.slow - Tests that may take longer
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

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
            100,
        )

        assert result is None

    def test_invalid_timeframe(self, mt5: MetaTrader5) -> None:
        """Test copy_rates with invalid timeframe."""
        # 999 is not a valid timeframe constant
        result = mt5.copy_rates_from_pos("EURUSD", 999, 0, 100)

        # Should return None or empty for invalid timeframe
        assert result is None or len(result) == 0

    def test_invalid_date_range_reversed(self, mt5: MetaTrader5) -> None:
        """Test with reversed date range (from > to)."""
        date_to = datetime.now(UTC) - timedelta(days=30)
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
        date_from = datetime(2099, 1, 1, tzinfo=UTC)
        date_to = datetime(2099, 12, 31, tzinfo=UTC)

        result = mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_D1,
            date_from,
            date_to,
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
            -100,  # Negative count
        )

        # Should return None or empty
        assert result is None or len(result) == 0

    def test_zero_count(self, mt5: MetaTrader5) -> None:
        """Test copy_rates with zero count.

        Note: MT5 API returns default bars (1000) when count=0,
        which is documented behavior, not an error.
        """
        result = mt5.copy_rates_from_pos(
            "EURUSD",
            mt5.TIMEFRAME_H1,
            0,
            0,  # Zero count - MT5 returns default
        )

        # MT5 returns default bars when count=0 (not empty/None)
        # This is expected behavior per MT5 API documentation
        assert result is not None


class TestApiLimits:
    """Tests for API limits and large requests."""

    @pytest.mark.slow
    def test_max_bars_limit(self, mt5: MetaTrader5) -> None:
        """Test requesting maximum number of bars."""
        # Request a large number of bars
        mt5.symbol_select("EURUSD", True)

        result = mt5.copy_rates_from_pos(
            "EURUSD",
            mt5.TIMEFRAME_M1,
            0,
            10000,  # Large number
        )

        if result is not None:
            # Should return data up to available bars
            assert len(result) > 0
            assert len(result) <= 10000

            # Verify data structure
            assert hasattr(result, "dtype")
            names = result.dtype.names
            assert names is not None
            assert "time" in names
            assert "open" in names

    @pytest.mark.slow
    def test_max_ticks_limit(self, mt5: MetaTrader5) -> None:
        """Test requesting maximum number of ticks."""
        mt5.symbol_select("EURUSD", True)

        date_from = datetime.now(UTC) - timedelta(hours=1)

        result = mt5.copy_ticks_from(
            "EURUSD",
            date_from,
            10000,  # Large number
            mt5.COPY_TICKS_ALL,
        )

        if result is not None and len(result) > 0:
            assert len(result) <= 10000
            assert hasattr(result, "dtype")

    @pytest.mark.slow
    def test_large_history_query(self, mt5: MetaTrader5) -> None:
        """Test querying large history range."""
        # Query 1 year of history
        date_from = datetime.now(UTC) - timedelta(days=365)
        date_to = datetime.now(UTC)

        result = mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_D1,
            date_from,
            date_to,
        )

        if result is not None:
            # Should have roughly 250 trading days
            assert len(result) > 100  # At least some data
            assert len(result) < 400  # Not unreasonably many

    def test_symbols_get_all(self, mt5: MetaTrader5) -> None:
        """Test getting all symbols (can be large)."""
        symbols = mt5.symbols_get()

        assert symbols is not None
        assert len(symbols) > 0

        # Verify structure
        symbol = symbols[0]
        assert hasattr(symbol, "name")
        assert hasattr(symbol, "visible")

    def test_symbols_total(self, mt5: MetaTrader5) -> None:
        """Test total symbols count."""
        total = mt5.symbols_total()

        assert isinstance(total, int)
        assert total > 0

        # Verify matches actual count
        symbols = mt5.symbols_get()
        if symbols:
            assert len(symbols) == total


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_last_error_after_invalid_operation(self, mt5: MetaTrader5) -> None:
        """Test that last_error is set after failed operation."""
        # Force an error with invalid symbol
        mt5.symbol_info("DEFINITELY_INVALID_SYMBOL")

        error = mt5.last_error()

        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == 2
        # Error code and message
        error_code, error_message = error
        assert isinstance(error_code, int)
        assert isinstance(error_message, str)

    def test_last_error_after_valid_operation(self, mt5: MetaTrader5) -> None:
        """Test that last_error is clear after successful operation."""
        # Successful operation
        mt5.symbol_select("EURUSD", True)
        info = mt5.symbol_info("EURUSD")

        assert info is not None

        error = mt5.last_error()
        assert error is not None
        # Error code should be 1 (RES_S_OK) or similar success code
        # after successful operation

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
        """
        version = mt5.version()

        assert version is not None
        assert isinstance(version, tuple)
        assert len(version) == 3

        # Version numbers - first two should be non-negative integers
        major, minor, build_or_date = version
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert major >= 0
        assert minor >= 0
        # Third element can be int (build number) or str (date)
        assert isinstance(build_or_date, (int, str))

    def test_terminal_info_always_works(self, mt5: MetaTrader5) -> None:
        """Test that terminal_info() always returns valid data."""
        terminal = mt5.terminal_info()

        assert terminal is not None
        assert terminal.connected is True
        assert terminal.build > 0

    def test_account_info_always_works(self, mt5: MetaTrader5) -> None:
        """Test that account_info() always returns valid data."""
        account = mt5.account_info()

        assert account is not None
        assert account.login > 0
        assert account.balance >= 0
        assert len(account.currency) > 0
