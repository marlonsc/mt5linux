# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
"""
metatrader5.py - Central MetaTrader5 API Interface

Provides a drop-in compatible MetaTrader5 Python API interface, delegating to modularized account, market, history, and data APIs. All methods and signatures are compatible with the official MetaTrader5 Python API.

Usage:
    import external.mt5linux.mt5linux.metatrader5 as mt5
    mt5.initialize()
    mt5.symbols_get()
"""

import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from .api_account import MetaTrader5 as _AccountAPI  # type: ignore
from .api_data import MetaTrader5DataAPI  # type: ignore
from .api_history import MetaTrader5HistoryAPI  # type: ignore
from .api_market import MetaTrader5MarketAPI  # type: ignore


class MetaTrader5:
    """Central MetaTrader5 API interface, compatible with the official Python API.
    Delegates to specialized modules for account, market, history, and data.


    """

    def __init__(self, host: str = 'localhost', port: int = 18812, connect: bool = True):
        """Initialize the MetaTrader5 central API interface.

        Args:
            host: Hostname or IP address of the RPyC server. Default is 'localhost'.
            port: TCP port of the RPyC server. Default is 18812.
            connect: Whether to connect to the server immediately. Set to False for testing.
        """
        if connect:
            self._account = _AccountAPI(host, port)  # type: ignore
            self._market = MetaTrader5MarketAPI(host, port)  # type: ignore
            self._history = MetaTrader5HistoryAPI(host, port)  # type: ignore
            self._data = MetaTrader5DataAPI(host, port)  # type: ignore
        else:
            # Create dummy objects for testing
            self._account = None
            self._market = None
            self._history = None
            self._data = None

    # Account methods
    def initialize(self, *args: object, **kwargs: object) -> Any:
        """Initialize connection to MetaTrader 5 terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: True if successful, False otherwise.
        :rtype: Any

        """
        return self._account.initialize(*args, **kwargs)  # type: ignore

    def login(self, *args: object, **kwargs: object) -> Any:
        """Log in to a trading account.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: True if successful, False otherwise.
        :rtype: Any

        """
        return self._account.login(*args, **kwargs)  # type: ignore

    def shutdown(self, *args: object, **kwargs: object) -> Any:
        """Close the connection to the MetaTrader 5 terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :rtype: Any

        """
        return self._account.shutdown(*args, **kwargs)  # type: ignore

    def last_error(self, *args: object, **kwargs: object) -> Any:
        """Get the last error code and description.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of (error_code, description).
        :rtype: Any

        """
        return self._account.last_error(*args, **kwargs)  # type: ignore

    def account_info(self, *args: object, **kwargs: object) -> Any:
        """Get information about the current trading account.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Named tuple with account information, or None on error.
        :rtype: Any

        """
        return self._account.account_info(*args, **kwargs)  # type: ignore

    def terminal_info(self, *args: object, **kwargs: object) -> Any:
        """Get information about the MetaTrader 5 terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Named tuple with terminal information, or None on error.
        :rtype: Any

        """
        return self._account.terminal_info(*args, **kwargs)  # type: ignore

    def version(self, *args: object, **kwargs: object) -> Any:
        """Get the MetaTrader 5 terminal version.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of (version, build, release_date), or None on error.
        :rtype: Any

        """
        return self._account.version(*args, **kwargs)  # type: ignore

    def eval(self, command: str) -> Any:
        """Evaluate a Python command in the remote MetaTrader 5 environment.

        :param command: 
        :type command: str
        :returns: Result of the evaluation.
        :rtype: Any

        """
        return self._account.eval(command)  # type: ignore

    def execute(self, command: str) -> None:
        """Execute a Python command in the remote MetaTrader 5 environment.

        :param command: Python command as string.
        :type command: str
        :rtype: None

        """
        self._account.execute(command)  # type: ignore

    # Market methods
    def symbols_total(self, *args: object, **kwargs: object) -> Any:
        """Get the total number of financial instruments in the terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Integer with the number of symbols.
        :rtype: Any

        """
        return self._market.symbols_total(*args, **kwargs)  # type: ignore

    def symbols_get(self, *args: object, **kwargs: object) -> Any:
        """Get all financial instruments from the terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of symbol info, or None on error.
        :rtype: Any

        """
        return self._market.symbols_get(*args, **kwargs)  # type: ignore

    def symbol_info_tick(self, *args: object, **kwargs: object) -> Any:
        """Get the last tick for the specified financial instrument.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Named tuple with tick info, or None on error.
        :rtype: Any

        """
        return self._market.symbol_info_tick(*args, **kwargs)  # type: ignore

    def symbol_select(self, *args: object, **kwargs: object) -> Any:
        """Select or remove a symbol in the MarketWatch window.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: True if successful, False otherwise.
        :rtype: Any

        """
        return self._market.symbol_select(*args, **kwargs)  # type: ignore

    def market_book_add(self, *args: object, **kwargs: object) -> Any:
        """Subscribe to Market Depth change events for a symbol.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: True if successful, False otherwise.
        :rtype: Any

        """
        return self._market.market_book_add(*args, **kwargs)  # type: ignore

    def market_book_get(self, *args: object, **kwargs: object) -> Any:
        """Get Market Depth (order book) for a symbol.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of BookInfo entries, or None on error.
        :rtype: Any

        """
        return self._market.market_book_get(*args, **kwargs)  # type: ignore

    def market_book_release(self, *args: object, **kwargs: object) -> Any:
        """Cancel Market Depth subscription for a symbol.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: True if successful, False otherwise.
        :rtype: Any

        """
        return self._market.market_book_release(*args, **kwargs)  # type: ignore

    # History methods
    def orders_total(self, *args: object, **kwargs: object) -> Any:
        """Get the number of active orders.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Integer with the number of active orders.
        :rtype: Any

        """
        return self._history.orders_total(*args, **kwargs)  # type: ignore

    def orders_get(self, *args: object, **kwargs: object) -> Any:
        """Get active orders, optionally filtered by symbol, group, or ticket.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of order info, or None on error.
        :rtype: Any

        """
        return self._history.orders_get(*args, **kwargs)  # type: ignore

    def order_calc_margin(self, *args: object, **kwargs: object) -> Any:
        """Calculate margin required for a trading operation.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Float with margin value, or None on error.
        :rtype: Any

        """
        return self._history.order_calc_margin(*args, **kwargs)  # type: ignore

    def order_calc_profit(self, *args: object, **kwargs: object) -> Any:
        """Calculate profit for a trading operation.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Float with profit value, or None on error.
        :rtype: Any

        """
        return self._history.order_calc_profit(*args, **kwargs)  # type: ignore

    def order_check(self, *args: object, **kwargs: object) -> Any:
        """Check funds sufficiency for a trading operation.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: MqlTradeCheckResult structure.
        :rtype: Any

        """
        return self._history.order_check(*args, **kwargs)  # type: ignore

    def order_send(self, *args: object, **kwargs: object) -> Any:
        """Send a trading request to the server.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: MqlTradeResult structure.
        :rtype: Any

        """
        return self._history.order_send(*args, **kwargs)  # type: ignore

    def positions_total(self, *args: object, **kwargs: object) -> Any:
        """Get the number of open positions.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Integer with the number of open positions.
        :rtype: Any

        """
        return self._history.positions_total(*args, **kwargs)  # type: ignore

    def positions_get(self, *args: object, **kwargs: object) -> Any:
        """Get open positions, optionally filtered by symbol, group, or ticket.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of position info, or None on error.
        :rtype: Any

        """
        return self._history.positions_get(*args, **kwargs)  # type: ignore

    def history_orders_total(self, *args: object, **kwargs: object) -> Any:
        """Get the number of orders in trading history for a period.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Integer with the number of historical orders.
        :rtype: Any

        """
        return self._history.history_orders_total(*args, **kwargs)  # type: ignore

    def history_orders_get(self, *args: object, **kwargs: object) -> Any:
        """Get orders from trading history, optionally filtered.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of order info, or None on error.
        :rtype: Any

        """
        return self._history.history_orders_get(*args, **kwargs)  # type: ignore

    def history_deals_total(self, *args: object, **kwargs: object) -> Any:
        """Get the number of deals in trading history for a period.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Integer with the number of historical deals.
        :rtype: Any

        """
        return self._history.history_deals_total(*args, **kwargs)  # type: ignore

    def history_deals_get(self, *args: object, **kwargs: object) -> Any:
        """Get deals from trading history, optionally filtered.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Tuple of deal info, or None on error.
        :rtype: Any

        """
        return self._history.history_deals_get(*args, **kwargs)  # type: ignore

    # Data methods
    def copy_rates_from(self, *args: object, **kwargs: object) -> Any:
        """Get bars from the terminal starting from a specified date.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Numpy array with bar data, or None on error.
        :rtype: Any

        """
        return self._data.copy_rates_from(*args, **kwargs)  # type: ignore

    def copy_rates_from_pos(self, *args: object, **kwargs: object) -> Any:
        """Get bars from the terminal starting from a specified index.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Numpy array with bar data, or None on error.
        :rtype: Any

        """
        return self._data.copy_rates_from_pos(*args, **kwargs)  # type: ignore

    def copy_rates_range(self, *args: object, **kwargs: object) -> Any:
        """Get bars in a specified date range from the terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Numpy array with bar data, or None on error.
        :rtype: Any

        """
        return self._data.copy_rates_range(*args, **kwargs)  # type: ignore

    def copy_ticks_from(self, *args: object, **kwargs: object) -> Any:
        """Get ticks from the terminal starting from a specified date.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Numpy array with tick data, or None on error.
        :rtype: Any

        """
        return self._data.copy_ticks_from(*args, **kwargs)  # type: ignore

    def copy_ticks_range(self, *args: object, **kwargs: object) -> Any:
        """Get ticks for a specified date range from the terminal.

        :param *args: 
        :type *args: object
        :param **kwargs: 
        :type **kwargs: object
        :returns: Numpy array with tick data, or None on error.
        :rtype: Any

        """
        return self._data.copy_ticks_range(*args, **kwargs)  # type: ignore


# Default instance for drop-in compatibility with the original MetaTrader5 module
# Create a dummy instance for testing
mt5 = MetaTrader5(host="dummy", port=0, connect=False)

# Replace with a real instance when not testing
if __name__ != "__main__" and "pytest" not in sys.modules:
    try:
        mt5 = MetaTrader5()
    except Exception:
        # If connection fails, keep the dummy instance
        pass
