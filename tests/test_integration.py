"""
Integration tests for mt5linux with real MT5 server.

These tests require mt5docker running with RPyC server on port 8001.
Run with: pytest --run-integration tests/test_integration.py

Credentials: MetaQuotes Demo Account
- Login: 10008704586
- Password: Lw!8IzEe
- Server: MetaQuotes-Demo
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from mt5linux import MetaTrader5

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestMT5DemoConnection:
    """Test real connection to MT5 demo server."""

    def test_connection_to_rpyc_server(
        self, real_mt5: MetaTrader5, mt5_connection_params: dict[str, Any]
    ) -> None:
        """Test basic connection to RPyC server."""
        assert real_mt5 is not None
        print(f"Connected to {mt5_connection_params['host']}:{mt5_connection_params['port']}")

    def test_initialize_with_demo_credentials(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test MT5 initialization with demo credentials."""
        result = real_mt5.initialize(**mt5_credentials)
        assert result is True, f"Initialize failed: {real_mt5.last_error()}"

    def test_version_after_initialize(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting MT5 version after initialization."""
        real_mt5.initialize(**mt5_credentials)
        version = real_mt5.version()
        assert version is not None
        assert len(version) == 3
        print(f"MT5 Version: {version}")

    def test_terminal_info(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting terminal info."""
        real_mt5.initialize(**mt5_credentials)
        info = real_mt5.terminal_info()
        assert info is not None
        assert hasattr(info, "connected")
        print(f"Terminal: {info.name} (build {info.build})")

    def test_account_info(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting account info."""
        real_mt5.initialize(**mt5_credentials)
        account = real_mt5.account_info()
        assert account is not None
        assert hasattr(account, "login")
        assert hasattr(account, "balance")
        print(f"Account: {account.login}, Balance: {account.balance} {account.currency}")

    def test_symbols_total(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting total symbols count."""
        real_mt5.initialize(**mt5_credentials)
        total = real_mt5.symbols_total()
        assert isinstance(total, int)
        assert total > 0
        print(f"Total symbols: {total}")

    def test_shutdown(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test shutdown after operations."""
        real_mt5.initialize(**mt5_credentials)
        result = real_mt5.shutdown()
        assert result is True


class TestMT5MarketData:
    """Test market data retrieval from MT5 demo."""

    def test_symbol_info_eurusd(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting EURUSD symbol info."""
        real_mt5.initialize(**mt5_credentials)
        info = real_mt5.symbol_info("EURUSD")
        assert info is not None
        assert hasattr(info, "bid")
        assert hasattr(info, "ask")
        print(f"EURUSD: Bid={info.bid}, Ask={info.ask}")

    def test_symbol_info_tick(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting current tick for EURUSD."""
        real_mt5.initialize(**mt5_credentials)
        real_mt5.symbol_select("EURUSD", True)
        tick = real_mt5.symbol_info_tick("EURUSD")
        assert tick is not None
        assert hasattr(tick, "bid")
        assert hasattr(tick, "ask")
        assert hasattr(tick, "time")
        print(f"EURUSD Tick: Bid={tick.bid}, Ask={tick.ask}")

    def test_symbols_get_forex(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting forex symbols."""
        real_mt5.initialize(**mt5_credentials)
        symbols = real_mt5.symbols_get(group="*USD*")
        assert symbols is not None
        assert len(symbols) > 0
        print(f"USD symbols: {len(symbols)}")

    def test_copy_rates_from_pos(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test copying historical rates."""
        from mt5linux import MetaTrader5 as MT5

        real_mt5.initialize(**mt5_credentials)
        rates = real_mt5.copy_rates_from_pos("EURUSD", MT5.TIMEFRAME_H1, 0, 10)
        assert rates is not None
        assert len(rates) > 0
        print(f"Got {len(rates)} EURUSD H1 bars")


class TestMT5TradingInfo:
    """Test trading info retrieval (no actual trading)."""

    def test_orders_total(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting pending orders count."""
        real_mt5.initialize(**mt5_credentials)
        total = real_mt5.orders_total()
        assert isinstance(total, int)
        assert total >= 0
        print(f"Pending orders: {total}")

    def test_positions_total(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting open positions count."""
        real_mt5.initialize(**mt5_credentials)
        total = real_mt5.positions_total()
        assert isinstance(total, int)
        assert total >= 0
        print(f"Open positions: {total}")

    def test_order_calc_margin(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test calculating margin for a hypothetical order."""
        from mt5linux import MetaTrader5 as MT5

        real_mt5.initialize(**mt5_credentials)
        margin = real_mt5.order_calc_margin(
            MT5.ORDER_TYPE_BUY, "EURUSD", 0.1, 1.0
        )
        # margin can be None if symbol not available or price invalid
        if margin is not None:
            assert isinstance(margin, float)
            print(f"Margin for 0.1 lot EURUSD: {margin}")

    def test_history_deals_total(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test getting history deals count."""
        from datetime import datetime, timezone

        real_mt5.initialize(**mt5_credentials)
        from_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        to_date = datetime.now(timezone.utc)
        total = real_mt5.history_deals_total(from_date, to_date)
        assert isinstance(total, int)
        assert total >= 0
        print(f"History deals: {total}")


class TestMT5ConnectionResilience:
    """Test connection resilience and error handling."""

    def test_multiple_initialize_calls(
        self, real_mt5: MetaTrader5, mt5_credentials: dict[str, Any]
    ) -> None:
        """Test multiple initialize calls don't crash."""
        result1 = real_mt5.initialize(**mt5_credentials)
        result2 = real_mt5.initialize(**mt5_credentials)
        assert result1 is True
        # Second call might return True or False depending on MT5 state

    def test_operations_without_initialize(
        self, real_mt5: MetaTrader5
    ) -> None:
        """Test operations without initialize return appropriate errors."""
        # This should fail gracefully without crashing
        try:
            info = real_mt5.terminal_info()
            # May return None or raise exception
        except Exception as e:
            print(f"Expected error: {e}")

    def test_last_error_after_failure(
        self, real_mt5: MetaTrader5
    ) -> None:
        """Test last_error returns meaningful info after failure."""
        # Try to initialize with invalid credentials
        result = real_mt5.initialize(
            login=99999999,
            password="invalid",
            server="NonExistent-Server",
        )
        if not result:
            error = real_mt5.last_error()
            assert error is not None
            print(f"Error after failed init: {error}")
