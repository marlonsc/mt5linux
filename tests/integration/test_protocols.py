"""Test protocol compliance for MT5 clients.

Validates that both sync and async clients implement their respective protocols.
Uses runtime_checkable protocols to ensure type safety.

"""

from __future__ import annotations

from mt5linux import MetaTrader5
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.protocols import AsyncClientProtocol, SyncClientProtocol
from tests.conftest import tc


class TestSyncClientProtocol:
    """Test SyncClientProtocol implementation."""

    def test_sync_client_is_instance_of_protocol(self) -> None:
        """Verify MetaTrader5 is an instance of SyncClientProtocol."""
        client = MetaTrader5(host="localhost", port=tc.TEST_PROTOCOL_PORT)
        assert isinstance(client, SyncClientProtocol)

    def test_sync_client_has_all_required_methods(self) -> None:
        """Verify SyncClientProtocol defines all required methods.

        Note: connect, disconnect, is_connected, and health_check are mt5linux
        extensions NOT part of the standard MT5Protocol (MetaTrader5 PyPI).
        """
        required_methods = {
            # Terminal (Protocol methods only - 32 methods matching MT5 PyPI)
            "initialize",
            "login",
            "shutdown",
            "version",
            "last_error",
            "terminal_info",
            "account_info",
            # Symbols
            "symbols_total",
            "symbols_get",
            "symbol_info",
            "symbol_info_tick",
            "symbol_select",
            # Market data
            "copy_rates_from",
            "copy_rates_from_pos",
            "copy_rates_range",
            "copy_ticks_from",
            "copy_ticks_range",
            # Trading
            "order_calc_margin",
            "order_calc_profit",
            "order_check",
            "order_send",
            # Positions
            "positions_total",
            "positions_get",
            # Orders
            "orders_total",
            "orders_get",
            # History
            "history_orders_total",
            "history_orders_get",
            "history_deals_total",
            "history_deals_get",
            # Market depth
            "market_book_add",
            "market_book_get",
            "market_book_release",
        }

        for method in required_methods:
            assert hasattr(SyncClientProtocol, method), (
                f"SyncClientProtocol missing method: {method}"
            )

    def test_sync_client_instance_has_all_methods(self) -> None:
        """Verify MetaTrader5 instance has all required methods."""
        client = MetaTrader5(host="localhost", port=tc.TEST_PROTOCOL_PORT)

        required_methods = [
            "connect",
            "disconnect",
            "initialize",
            "login",
            "shutdown",
            "account_info",
            "symbol_info",
            "copy_rates_from",
            "order_send",
            "positions_get",
        ]

        for method in required_methods:
            assert hasattr(client, method), (
                f"MetaTrader5 instance missing method: {method}"
            )


class TestAsyncClientProtocol:
    """Test AsyncClientProtocol implementation."""

    def test_async_client_is_instance_of_protocol(self) -> None:
        """Verify AsyncMetaTrader5 is an instance of AsyncClientProtocol."""
        client = AsyncMetaTrader5(host="localhost", port=tc.TEST_PROTOCOL_PORT)
        assert isinstance(client, AsyncClientProtocol)

    def test_async_client_has_all_required_methods(self) -> None:
        """Verify AsyncClientProtocol defines all required methods.

        Note: connect, disconnect, is_connected, and health_check are mt5linux
        extensions NOT part of the standard MT5Protocol (MetaTrader5 PyPI).
        """
        required_methods = {
            # Terminal (Protocol methods only - 32 methods matching MT5 PyPI)
            "initialize",
            "login",
            "shutdown",
            "version",
            "last_error",
            "terminal_info",
            "account_info",
            # Symbols
            "symbols_total",
            "symbols_get",
            "symbol_info",
            "symbol_info_tick",
            "symbol_select",
            # Market data
            "copy_rates_from",
            "copy_rates_from_pos",
            "copy_rates_range",
            "copy_ticks_from",
            "copy_ticks_range",
            # Trading
            "order_calc_margin",
            "order_calc_profit",
            "order_check",
            "order_send",
            # Positions
            "positions_total",
            "positions_get",
            # Orders
            "orders_total",
            "orders_get",
            # History
            "history_orders_total",
            "history_orders_get",
            "history_deals_total",
            "history_deals_get",
            # Market depth
            "market_book_add",
            "market_book_get",
            "market_book_release",
        }

        for method in required_methods:
            assert hasattr(AsyncClientProtocol, method), (
                f"AsyncClientProtocol missing method: {method}"
            )

    def test_async_client_instance_has_all_methods(self) -> None:
        """Verify AsyncMetaTrader5 instance has all required methods."""
        client = AsyncMetaTrader5(host="localhost", port=tc.TEST_PROTOCOL_PORT)

        required_methods = [
            "connect",
            "disconnect",
            "initialize",
            "login",
            "shutdown",
            "account_info",
            "symbol_info",
            "copy_rates_from",
            "order_send",
            "positions_get",
        ]

        for method in required_methods:
            assert hasattr(client, method), (
                f"AsyncMetaTrader5 instance missing method: {method}"
            )


class TestProtocolConsistency:
    """Test consistency between sync and async protocols."""

    def test_both_protocols_have_same_methods(self) -> None:
        """Verify both protocols have identical method signatures."""
        # Get all protocol attributes
        sync_attrs = {
            name for name in dir(SyncClientProtocol) if not name.startswith("_")
        }
        async_attrs = {
            name for name in dir(AsyncClientProtocol) if not name.startswith("_")
        }

        # Both should have same method set
        sync_only = sync_attrs - async_attrs
        async_only = async_attrs - sync_attrs
        msg = f"Protocol methods mismatch. Sync only: {sync_only}. "
        msg += f"Async only: {async_only}"
        assert sync_attrs == async_attrs, msg
