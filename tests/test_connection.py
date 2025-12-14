"""
Unit tests for mt5linux connection and basic functionality.

These tests use mocked rpyc connection and don't require MT5 server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from mt5linux import MetaTrader5

if TYPE_CHECKING:
    from tests.conftest import MockRpycConnection


class TestMetaTrader5Constants:
    """Test MT5 constants are correctly defined."""

    def test_account_margin_modes(self) -> None:
        """Test account margin mode constants."""
        assert MetaTrader5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING == 0
        assert MetaTrader5.ACCOUNT_MARGIN_MODE_EXCHANGE == 1
        assert MetaTrader5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING == 2

    def test_account_trade_modes(self) -> None:
        """Test account trade mode constants."""
        assert MetaTrader5.ACCOUNT_TRADE_MODE_DEMO == 0
        assert MetaTrader5.ACCOUNT_TRADE_MODE_CONTEST == 1
        assert MetaTrader5.ACCOUNT_TRADE_MODE_REAL == 2

    def test_timeframe_constants(self) -> None:
        """Test timeframe constants."""
        assert MetaTrader5.TIMEFRAME_M1 == 1
        assert MetaTrader5.TIMEFRAME_M5 == 5
        assert MetaTrader5.TIMEFRAME_M15 == 15
        assert MetaTrader5.TIMEFRAME_H1 == 16385
        assert MetaTrader5.TIMEFRAME_D1 == 16408
        assert MetaTrader5.TIMEFRAME_W1 == 32769
        assert MetaTrader5.TIMEFRAME_MN1 == 49153

    def test_order_types(self) -> None:
        """Test order type constants."""
        assert MetaTrader5.ORDER_TYPE_BUY == 0
        assert MetaTrader5.ORDER_TYPE_SELL == 1
        assert MetaTrader5.ORDER_TYPE_BUY_LIMIT == 2
        assert MetaTrader5.ORDER_TYPE_SELL_LIMIT == 3
        assert MetaTrader5.ORDER_TYPE_BUY_STOP == 4
        assert MetaTrader5.ORDER_TYPE_SELL_STOP == 5

    def test_trade_actions(self) -> None:
        """Test trade action constants."""
        assert MetaTrader5.TRADE_ACTION_DEAL == 1
        assert MetaTrader5.TRADE_ACTION_PENDING == 5
        assert MetaTrader5.TRADE_ACTION_SLTP == 6
        assert MetaTrader5.TRADE_ACTION_MODIFY == 7
        assert MetaTrader5.TRADE_ACTION_REMOVE == 8

    def test_position_types(self) -> None:
        """Test position type constants."""
        assert MetaTrader5.POSITION_TYPE_BUY == 0
        assert MetaTrader5.POSITION_TYPE_SELL == 1

    def test_result_codes(self) -> None:
        """Test result code constants."""
        assert MetaTrader5.RES_S_OK == 1
        assert MetaTrader5.RES_E_FAIL == -1
        assert MetaTrader5.RES_E_INVALID_PARAMS == -2


class TestMetaTrader5Connection:
    """Test MT5 connection functionality with mocked rpyc."""

    def test_init_creates_connection(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test that __init__ creates rpyc connection."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        assert mt5 is not None

    def test_init_sets_timeout(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test that __init__ sets sync_request_timeout to 300s."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        assert mock_rpyc_connection._config["sync_request_timeout"] == 300

    def test_init_imports_metatrader5(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test that __init__ imports MetaTrader5 module."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        assert "import MetaTrader5 as mt5" in mock_rpyc_connection._executed_code

    def test_init_imports_datetime(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test that __init__ imports datetime module."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        assert "import datetime" in mock_rpyc_connection._executed_code


class TestMetaTrader5Methods:
    """Test MT5 methods with mocked rpyc."""

    def test_initialize_returns_true(self, mock_mt5: MetaTrader5) -> None:
        """Test initialize() returns True on success."""
        result = mock_mt5.initialize()
        assert result is True

    def test_initialize_with_credentials(self, mock_mt5: MetaTrader5) -> None:
        """Test initialize() with login credentials."""
        result = mock_mt5.initialize(
            login=10008704586,
            password="Lw!8IzEe",
            server="MetaQuotes-Demo",
        )
        assert result is True

    def test_terminal_info_returns_data(self, mock_mt5: MetaTrader5) -> None:
        """Test terminal_info() returns terminal information."""
        info = mock_mt5.terminal_info()
        assert info is not None
        assert hasattr(info, "connected")
        assert info.connected is True

    def test_account_info_returns_data(self, mock_mt5: MetaTrader5) -> None:
        """Test account_info() returns account information."""
        info = mock_mt5.account_info()
        assert info is not None
        assert hasattr(info, "login")
        assert hasattr(info, "balance")

    def test_version_returns_tuple(self, mock_mt5: MetaTrader5) -> None:
        """Test version() returns version tuple."""
        version = mock_mt5.version()
        assert version is not None
        assert isinstance(version, tuple)
        assert len(version) == 3

    def test_last_error_returns_tuple(self, mock_mt5: MetaTrader5) -> None:
        """Test last_error() returns error tuple."""
        error = mock_mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == 2

    def test_shutdown_returns_true(self, mock_mt5: MetaTrader5) -> None:
        """Test shutdown() returns True."""
        result = mock_mt5.shutdown()
        assert result is True

    def test_symbols_total_returns_int(self, mock_mt5: MetaTrader5) -> None:
        """Test symbols_total() returns integer."""
        total = mock_mt5.symbols_total()
        assert isinstance(total, int)
        assert total >= 0


class TestMetaTrader5CustomPort:
    """Test MT5 with custom host/port."""

    def test_custom_host_port(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test connection with custom host and port."""
        mt5 = MetaTrader5(host="192.168.1.100", port=8001)
        assert mt5 is not None

    def test_default_host_port(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test connection with default host and port."""
        mt5 = MetaTrader5()
        assert mt5 is not None


class TestMetaTrader5ConnectionFeatures:
    """Test new connection features (retry, context manager, etc.)."""

    def test_context_manager(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test context manager usage."""
        with MetaTrader5(host="localhost", port=18812) as mt5:
            assert mt5 is not None
            result = mt5.initialize()
            assert result is True

    def test_connection_info(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test connection_info property."""
        mt5 = MetaTrader5(host="localhost", port=8001, timeout=600)
        info = mt5.connection_info
        assert info["host"] == "localhost"
        assert info["port"] == 8001
        assert info["timeout"] == 600
        assert "connected" in info

    def test_custom_timeout(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test custom timeout setting."""
        mt5 = MetaTrader5(host="localhost", port=18812, timeout=600)
        assert mt5._timeout == 600

    def test_custom_retry_settings(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test custom retry settings."""
        mt5 = MetaTrader5(
            host="localhost",
            port=18812,
            retry_attempts=5,
            retry_delay=2.0,
        )
        assert mt5._retry_attempts == 5
        assert mt5._retry_delay == 2.0

    def test_close_method(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test close method."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        mt5.close()
        # Should not raise even if called multiple times
        mt5.close()

    def test_reconnect_method(
        self, mock_rpyc_connection: MockRpycConnection
    ) -> None:
        """Test reconnect method."""
        mt5 = MetaTrader5(host="localhost", port=18812)
        result = mt5.reconnect()
        assert result is True
