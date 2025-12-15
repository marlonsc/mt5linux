"""Market depth (order book) tests for MT5 API.

Tests market book subscription and data retrieval.

Markers:
    @pytest.mark.market_depth - Tests requiring market depth subscription
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestMarketBook:
    """Market book (order book) tests."""

    @pytest.mark.market_depth
    def test_market_book_add(self, mt5: MetaTrader5) -> None:
        """Test subscribing to market book."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        result = mt5.market_book_add(symbol)

        # market_book_add returns True on success
        assert result is True

        # Cleanup
        mt5.market_book_release(symbol)

    @pytest.mark.market_depth
    def test_market_book_add_invalid_symbol(self, mt5: MetaTrader5) -> None:
        """Test subscribing to invalid symbol."""
        result = mt5.market_book_add("INVALID_SYMBOL_XYZ")

        # Should return False for invalid symbol
        assert result is False

    @pytest.mark.market_depth
    def test_market_book_get(
        self,
        mt5: MetaTrader5,
        market_book_symbol: str,
    ) -> None:
        """Test getting market book data."""
        # market_book_symbol fixture subscribes and cleans up

        book = mt5.market_book_get(market_book_symbol)

        # Book may be None if no data available (e.g., market closed)
        if book is not None:
            # Should be a tuple of book entries
            assert isinstance(book, tuple)

            # If there's data, verify structure
            if len(book) > 0:
                entry = book[0]
                # Each entry should have type, price, volume
                assert hasattr(entry, "type")
                assert hasattr(entry, "price")
                assert hasattr(entry, "volume")

    @pytest.mark.market_depth
    def test_market_book_get_without_subscription(self, mt5: MetaTrader5) -> None:
        """Test getting market book without subscription."""
        symbol = "GBPUSD"
        mt5.symbol_select(symbol, True)

        # Don't call market_book_add, try to get directly
        book = mt5.market_book_get(symbol)

        # Should return None or empty without subscription
        assert book is None or len(book) == 0

    @pytest.mark.market_depth
    def test_market_book_release(self, mt5: MetaTrader5) -> None:
        """Test unsubscribing from market book."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        # Subscribe first
        mt5.market_book_add(symbol)

        # Unsubscribe
        result = mt5.market_book_release(symbol)

        # market_book_release returns True on success
        assert result is True

    @pytest.mark.market_depth
    def test_market_book_release_not_subscribed(self, mt5: MetaTrader5) -> None:
        """Test unsubscribing when not subscribed."""
        result = mt5.market_book_release("USDJPY")

        # Should return True even if not subscribed (no-op)
        # or False depending on implementation
        assert result is True or result is False

    @pytest.mark.market_depth
    def test_market_book_lifecycle(self, mt5: MetaTrader5) -> None:
        """Test full market book lifecycle: subscribe, get, unsubscribe."""
        symbol = "EURUSD"
        mt5.symbol_select(symbol, True)

        # Step 1: Subscribe
        add_result = mt5.market_book_add(symbol)
        assert add_result is True

        # Step 2: Get data
        book = mt5.market_book_get(symbol)
        # May be None if market closed, that's ok
        if book is not None:
            assert isinstance(book, tuple)

        # Step 3: Unsubscribe
        release_result = mt5.market_book_release(symbol)
        assert release_result is True

        # Step 4: Verify unsubscribed (should get None now)
        book_after = mt5.market_book_get(symbol)
        assert book_after is None or len(book_after) == 0

    @pytest.mark.market_depth
    def test_market_book_multiple_symbols(self, mt5: MetaTrader5) -> None:
        """Test subscribing to multiple symbols simultaneously."""
        symbols = ["EURUSD", "GBPUSD"]

        for symbol in symbols:
            mt5.symbol_select(symbol, True)
            result = mt5.market_book_add(symbol)
            assert result is True

        # Get data from both
        for symbol in symbols:
            book = mt5.market_book_get(symbol)
            # May be None, but should not raise
            assert book is None or isinstance(book, tuple)

        # Cleanup both
        for symbol in symbols:
            mt5.market_book_release(symbol)
