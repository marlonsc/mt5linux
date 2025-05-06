"""
Comprehensive API tests for the MetaTrader5 Linux integration.

These tests verify that the MetaTrader5 class properly exposes all
the required API methods and constants. They do not test actual
connectivity to a MetaTrader5 server.
"""

import sys
import unittest.mock as mock
import pytest
from mt5linux import constants_mt5
from mt5linux.metatrader5 import MetaTrader5


# Mock the rpyc connection to avoid actual connection attempts
@pytest.fixture(autouse=True)
def mock_rpyc_connect():
    """Mock rpyc.classic.connect to avoid actual connection attempts."""
    with mock.patch('rpyc.classic.connect') as mock_connect:
        # Create a mock connection object
        mock_conn = mock.MagicMock()
        mock_connect.return_value = mock_conn
        yield mock_connect


def test_api_constants():
    """Test that all required constants are exposed."""
    # Check a sample of constants from different categories
    assert hasattr(constants_mt5, 'TIMEFRAME_M1')
    assert hasattr(constants_mt5, 'TIMEFRAME_H1')
    assert hasattr(constants_mt5, 'TIMEFRAME_D1')
    
    assert hasattr(constants_mt5, 'ACCOUNT_MARGIN_MODE_RETAIL_NETTING')
    assert hasattr(constants_mt5, 'ACCOUNT_MARGIN_MODE_RETAIL_HEDGING')
    
    assert hasattr(constants_mt5, 'ORDER_TYPE_BUY')
    assert hasattr(constants_mt5, 'ORDER_TYPE_SELL')
    
    assert hasattr(constants_mt5, 'SYMBOL_CALC_MODE_FOREX')
    assert hasattr(constants_mt5, 'SYMBOL_CALC_MODE_FUTURES')


def test_api_methods():
    """Test that all required methods are exposed."""
    # Create instance without connecting
    mt5_instance = MetaTrader5(host='dummy', port=9999)
    
    # Account methods
    assert hasattr(mt5_instance, 'initialize')
    assert hasattr(mt5_instance, 'login')
    assert hasattr(mt5_instance, 'shutdown')
    assert hasattr(mt5_instance, 'version')
    assert hasattr(mt5_instance, 'last_error')
    assert hasattr(mt5_instance, 'account_info')
    assert hasattr(mt5_instance, 'terminal_info')
    
    # Market methods
    assert hasattr(mt5_instance, 'symbols_total')
    assert hasattr(mt5_instance, 'symbols_get')
    assert hasattr(mt5_instance, 'symbol_info_tick')
    assert hasattr(mt5_instance, 'symbol_select')
    
    # History methods
    assert hasattr(mt5_instance, 'orders_total')
    assert hasattr(mt5_instance, 'orders_get')
    assert hasattr(mt5_instance, 'history_orders_total')
    assert hasattr(mt5_instance, 'history_orders_get')
    assert hasattr(mt5_instance, 'history_deals_total')
    assert hasattr(mt5_instance, 'history_deals_get')
    
    # Data methods
    assert hasattr(mt5_instance, 'copy_rates_from')
    assert hasattr(mt5_instance, 'copy_rates_from_pos')
    assert hasattr(mt5_instance, 'copy_rates_range')
    assert hasattr(mt5_instance, 'copy_ticks_from')
    assert hasattr(mt5_instance, 'copy_ticks_range')


def test_method_delegation():
    """Test that methods properly delegate to the appropriate API."""
    mt5_instance = MetaTrader5(host='dummy', port=9999)
    
    # Mock the internal API objects
    mt5_instance._account = mock.MagicMock()
    mt5_instance._market = mock.MagicMock()
    mt5_instance._history = mock.MagicMock()
    mt5_instance._data = mock.MagicMock()
    
    # Test account method delegation
    mt5_instance.initialize(param1="test")
    mt5_instance._account.initialize.assert_called_once_with(param1="test")
    
    # Test market method delegation
    mt5_instance.symbols_get("EURUSD")
    mt5_instance._market.symbols_get.assert_called_once_with("EURUSD")
    
    # Test history method delegation
    mt5_instance.orders_get()
    mt5_instance._history.orders_get.assert_called_once()
    
    # Test data method delegation
    mt5_instance.copy_rates_from_pos("EURUSD", 1, 0, 100)
    mt5_instance._data.copy_rates_from_pos.assert_called_once_with("EURUSD", 1, 0, 100)