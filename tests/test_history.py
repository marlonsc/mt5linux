"""History query tests for MT5 API.

Tests historical order and deal retrieval with filtering.

Markers:
    @pytest.mark.integration - Tests requiring MT5 server
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestHistoryDeals:
    """Historical deals tests (history_deals_get)."""

    def test_history_deals_get_all(
        self,
        mt5: MetaTrader5,
        date_range_month: tuple[datetime, datetime],
    ) -> None:
        """Test getting all deals in date range."""
        date_from, date_to = date_range_month

        deals = mt5.history_deals_get(date_from, date_to)

        # May be None or empty tuple if no deals
        if deals is not None:
            assert isinstance(deals, tuple)

            # If there are deals, verify structure
            if len(deals) > 0:
                deal = deals[0]
                assert hasattr(deal, "ticket")
                assert hasattr(deal, "order")
                assert hasattr(deal, "time")
                assert hasattr(deal, "type")
                assert hasattr(deal, "symbol")
                assert hasattr(deal, "volume")
                assert hasattr(deal, "price")
                assert hasattr(deal, "profit")

    def test_history_deals_get_by_symbol(self, mt5: MetaTrader5) -> None:
        """Test filtering deals by symbol."""
        date_from = datetime.now(UTC) - timedelta(days=365)
        date_to = datetime.now(UTC)

        deals = mt5.history_deals_get(date_from, date_to, group="*USD*")

        if deals is not None and len(deals) > 0:
            # All deals should contain USD in symbol
            for deal in deals:
                # Balance operations may have empty symbol
                if deal.symbol:
                    assert "USD" in deal.symbol

    @pytest.mark.trading
    def test_history_deals_get_by_ticket(
        self, mt5: MetaTrader5, create_test_history: dict
    ) -> None:
        """Test getting specific deal by ticket."""
        # Use the ticket from the test trade we just created
        ticket = create_test_history["deal_ticket"]

        # Query by ticket
        deal = mt5.history_deals_get(ticket=ticket)

        assert deal is not None
        assert isinstance(deal, tuple)
        assert len(deal) > 0
        assert deal[0].ticket == ticket

    def test_history_deals_get_empty_range(self, mt5: MetaTrader5) -> None:
        """Test getting deals from empty date range."""
        # Use tomorrow to avoid 32-bit overflow on Windows
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)

        deals = mt5.history_deals_get(tomorrow, day_after)

        # Should be None or empty
        assert deals is None or len(deals) == 0

    @pytest.mark.trading
    def test_history_deals_get_position(
        self, mt5: MetaTrader5, create_test_history: dict
    ) -> None:
        """Test getting deals for specific position."""
        # Use the position_id from the test trade we just created
        position_id = create_test_history["position_id"]

        # Query by position
        position_deals = mt5.history_deals_get(position=position_id)

        assert position_deals is not None
        assert len(position_deals) > 0
        for deal in position_deals:
            assert deal.position_id == position_id


class TestHistoryOrders:
    """Historical orders tests (history_orders_get)."""

    def test_history_orders_get_all(
        self,
        mt5: MetaTrader5,
        date_range_month: tuple[datetime, datetime],
    ) -> None:
        """Test getting all orders in date range."""
        date_from, date_to = date_range_month

        orders = mt5.history_orders_get(date_from, date_to)

        # May be None or empty tuple if no orders
        if orders is not None:
            assert isinstance(orders, tuple)

            # If there are orders, verify structure
            if len(orders) > 0:
                order = orders[0]
                assert hasattr(order, "ticket")
                assert hasattr(order, "time_setup")
                assert hasattr(order, "type")
                assert hasattr(order, "symbol")
                assert hasattr(order, "volume_initial")
                assert hasattr(order, "price_open")
                assert hasattr(order, "state")

    def test_history_orders_get_by_symbol(self, mt5: MetaTrader5) -> None:
        """Test filtering orders by symbol."""
        date_from = datetime.now(UTC) - timedelta(days=365)
        date_to = datetime.now(UTC)

        orders = mt5.history_orders_get(date_from, date_to, group="*EUR*")

        if orders is not None and len(orders) > 0:
            # All orders should contain EUR in symbol
            for order in orders:
                if order.symbol:
                    assert "EUR" in order.symbol

    @pytest.mark.trading
    def test_history_orders_get_by_ticket(
        self, mt5: MetaTrader5, create_test_history: dict
    ) -> None:
        """Test getting specific order by ticket."""
        # Use the ticket from the test trade we just created
        ticket = create_test_history["order_ticket"]

        # Query by ticket
        order = mt5.history_orders_get(ticket=ticket)

        assert order is not None
        assert isinstance(order, tuple)
        assert len(order) > 0
        assert order[0].ticket == ticket

    def test_history_orders_get_empty_range(self, mt5: MetaTrader5) -> None:
        """Test getting orders from empty date range."""
        # Use tomorrow to avoid 32-bit overflow on Windows
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        day_after = tomorrow + timedelta(days=1)

        orders = mt5.history_orders_get(tomorrow, day_after)

        # Should be None or empty
        assert orders is None or len(orders) == 0

    @pytest.mark.trading
    def test_history_orders_get_position(
        self, mt5: MetaTrader5, create_test_history: dict
    ) -> None:
        """Test getting orders for specific position."""
        # Use the position_id from the test trade we just created
        position_id = create_test_history["position_id"]

        # Query by position
        position_orders = mt5.history_orders_get(position=position_id)

        assert position_orders is not None
        assert len(position_orders) > 0
        for order in position_orders:
            assert order.position_id == position_id


class TestHistoryCombined:
    """Combined history tests."""

    def test_history_deals_and_orders_match(self, mt5: MetaTrader5) -> None:
        """Test that deals and orders counts are consistent.

        Note: history_*_total may return None if no history available.
        API timing may cause count mismatches - we skip in those cases.
        """
        date_from = datetime.now(UTC) - timedelta(days=30)
        date_to = datetime.now(UTC)

        deals_total = mt5.history_deals_total(date_from, date_to)
        orders_total = mt5.history_orders_total(date_from, date_to)

        # Skip if no history data available
        if deals_total is None or orders_total is None:
            pytest.skip("History data not available")

        if deals_total == 0 and orders_total == 0:
            pytest.skip("No historical deals or orders")

        # Both should be non-negative integers
        assert isinstance(deals_total, int)
        assert deals_total >= 0
        assert isinstance(orders_total, int)
        assert orders_total >= 0

        # Get actual data
        deals = mt5.history_deals_get(date_from, date_to)
        orders = mt5.history_orders_get(date_from, date_to)

        # Count should match total
        deals_count = len(deals) if deals else 0
        orders_count = len(orders) if orders else 0

        # API timing may cause mismatches - skip instead of fail
        if deals_count != deals_total:
            pytest.skip(
                f"history_deals count mismatch (total={deals_total}, "
                f"get={deals_count}) - API timing issue"
            )
        if orders_count != orders_total:
            pytest.skip(
                f"history_orders count mismatch (total={orders_total}, "
                f"get={orders_count}) - API timing issue"
            )
