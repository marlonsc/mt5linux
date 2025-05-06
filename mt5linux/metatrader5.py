# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
"""
MetaTrader5 Central API Interface

This module provides a drop-in compatible MetaTrader5 Python API interface, delegating to modularized account, market, history, and data APIs.

Usage:
    import external.mt5linux.mt5linux.metatrader5 as mt5
    mt5.initialize()
    mt5.symbols_get()
    ...

All methods and signatures are compatible with the official MetaTrader5 Python API.
"""

import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from .api_account import MetaTrader5 as _AccountAPI  # type: ignore
from .api_data import MetaTrader5DataAPI  # type: ignore
from .api_history import MetaTrader5HistoryAPI  # type: ignore
from .api_market import MetaTrader5MarketAPI  # type: ignore


class MetaTrader5:
    """
    Central MetaTrader5 API interface, compatible with the official Python API.
    Delegates to specialized modules for account, market, history, and data.
    """

    def __init__(self, host: str = 'localhost', port: int = 18812, connect: bool = True):
        """
        Initialize the MetaTrader5 central API interface.

        Args:
            host: Hostname or IP address of the RPyC server.
            port: TCP port of the RPyC server.
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
        """
        Initialize connection to MetaTrader 5 terminal.

        Returns:
            True if successful, False otherwise.
        """
        return self._account.initialize(*args, **kwargs)  # type: ignore

    def login(self, *args: object, **kwargs: object) -> Any:
        """
        Log in to a trading account.

        Returns:
            True if successful, False otherwise.
        """
        return self._account.login(*args, **kwargs)  # type: ignore

    def shutdown(self, *args: object, **kwargs: object) -> Any:
        """
        Close the connection to the MetaTrader 5 terminal.
        """
        return self._account.shutdown(*args, **kwargs)  # type: ignore

    def last_error(self, *args: object, **kwargs: object) -> Any:
        """
        Get the last error code and description.

        Returns:
            Tuple of (error_code, description).
        """
        return self._account.last_error(*args, **kwargs)  # type: ignore

    def account_info(self, *args: object, **kwargs: object) -> Any:
        """
        Get information about the current trading account.

        Returns:
            Named tuple with account information, or None on error.
        """
        return self._account.account_info(*args, **kwargs)  # type: ignore

    def terminal_info(self, *args: object, **kwargs: object) -> Any:
        """
        Get information about the MetaTrader 5 terminal.

        Returns:
            Named tuple with terminal information, or None on error.
        """
        return self._account.terminal_info(*args, **kwargs)  # type: ignore

    def version(self, *args: object, **kwargs: object) -> Any:
        """
        Get the MetaTrader 5 terminal version.

        Returns:
            Tuple of (version, build, release_date), or None on error.
        """
        return self._account.version(*args, **kwargs)  # type: ignore

    def eval(self, command: str) -> Any:
        """
        Evaluate a Python command in the remote MetaTrader 5 environment.

        Args:
            command: Python command as string.
        Returns:
            Result of the evaluation.
        """
        return self._account.eval(command)  # type: ignore

    def execute(self, command: str) -> None:
        """
        Execute a Python command in the remote MetaTrader 5 environment.

        Args:
            command: Python command as string.
        """
        self._account.execute(command)  # type: ignore

    # Market methods
    def symbols_total(self, *args: object, **kwargs: object) -> Any:
        """
        Get the total number of financial instruments in the terminal.

        Returns:
            Integer with the number of symbols.
        """
        return self._market.symbols_total(*args, **kwargs)  # type: ignore

    def symbols_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get all financial instruments from the terminal.

        Returns:
            Tuple of symbol info, or None on error.
        """
        return self._market.symbols_get(*args, **kwargs)  # type: ignore

    def symbol_info_tick(self, *args: object, **kwargs: object) -> Any:
        """
        Get the last tick for the specified financial instrument.

        Returns:
            Named tuple with tick info, or None on error.
        """
        return self._market.symbol_info_tick(*args, **kwargs)  # type: ignore

    def symbol_select(self, *args: object, **kwargs: object) -> Any:
        """
        Select or remove a symbol in the MarketWatch window.

        Returns:
            True if successful, False otherwise.
        """
        return self._market.symbol_select(*args, **kwargs)  # type: ignore

    def market_book_add(self, *args: object, **kwargs: object) -> Any:
        """
        Subscribe to Market Depth change events for a symbol.

        Returns:
            True if successful, False otherwise.
        """
        return self._market.market_book_add(*args, **kwargs)  # type: ignore

    def market_book_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get Market Depth (order book) for a symbol.

        Returns:
            Tuple of BookInfo entries, or None on error.
        """
        return self._market.market_book_get(*args, **kwargs)  # type: ignore

    def market_book_release(self, *args: object, **kwargs: object) -> Any:
        """
        Cancel Market Depth subscription for a symbol.

        Returns:
            True if successful, False otherwise.
        """
        return self._market.market_book_release(*args, **kwargs)  # type: ignore

    # History methods
    def orders_total(self, *args: object, **kwargs: object) -> Any:
        """
        Get the number of active orders.

        Returns:
            Integer with the number of active orders.
        """
        return self._history.orders_total(*args, **kwargs)  # type: ignore

    def orders_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get active orders, optionally filtered by symbol, group, or ticket.

        Returns:
            Tuple of order info, or None on error.
        """
        return self._history.orders_get(*args, **kwargs)  # type: ignore

    def order_calc_margin(self, *args: object, **kwargs: object) -> Any:
        """
        Calculate margin required for a trading operation.

        Returns:
            Float with margin value, or None on error.
        """
        return self._history.order_calc_margin(*args, **kwargs)  # type: ignore

    def order_calc_profit(self, *args: object, **kwargs: object) -> Any:
        """
        Calculate profit for a trading operation.

        Returns:
            Float with profit value, or None on error.
        """
        return self._history.order_calc_profit(*args, **kwargs)  # type: ignore

    def order_check(self, *args: object, **kwargs: object) -> Any:
        """
        Check funds sufficiency for a trading operation.

        Returns:
            MqlTradeCheckResult structure.
        """
        return self._history.order_check(*args, **kwargs)  # type: ignore

    def order_send(self, *args: object, **kwargs: object) -> Any:
        """
        Send a trading request to the server.

        Returns:
            MqlTradeResult structure.
        """
        return self._history.order_send(*args, **kwargs)  # type: ignore

    def positions_total(self, *args: object, **kwargs: object) -> Any:
        """
        Get the number of open positions.

        Returns:
            Integer with the number of open positions.
        """
        return self._history.positions_total(*args, **kwargs)  # type: ignore

    def positions_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get open positions, optionally filtered by symbol, group, or ticket.

        Returns:
            Tuple of position info, or None on error.
        """
        return self._history.positions_get(*args, **kwargs)  # type: ignore

    def history_orders_total(self, *args: object, **kwargs: object) -> Any:
        """
        Get the number of orders in trading history for a period.

        Returns:
            Integer with the number of historical orders.
        """
        return self._history.history_orders_total(*args, **kwargs)  # type: ignore

    def history_orders_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get orders from trading history, optionally filtered.

        Returns:
            Tuple of order info, or None on error.
        """
        return self._history.history_orders_get(*args, **kwargs)  # type: ignore

    def history_deals_total(self, *args: object, **kwargs: object) -> Any:
        """
        Get the number of deals in trading history for a period.

        Returns:
            Integer with the number of historical deals.
        """
        return self._history.history_deals_total(*args, **kwargs)  # type: ignore

    def history_deals_get(self, *args: object, **kwargs: object) -> Any:
        """
        Get deals from trading history, optionally filtered.

        Returns:
            Tuple of deal info, or None on error.
        """
        return self._history.history_deals_get(*args, **kwargs)  # type: ignore

    # Data methods
    def copy_rates_from(self, *args: object, **kwargs: object) -> Any:
        """
        Get bars from the terminal starting from a specified date.

        Returns:
            Numpy array with bar data, or None on error.
        """
        return self._data.copy_rates_from(*args, **kwargs)  # type: ignore

    def copy_rates_from_pos(self, *args: object, **kwargs: object) -> Any:
        """
        Get bars from the terminal starting from a specified index.

        Returns:
            Numpy array with bar data, or None on error.
        """
        return self._data.copy_rates_from_pos(*args, **kwargs)  # type: ignore

    def copy_rates_range(self, *args: object, **kwargs: object) -> Any:
        """
        Get bars in a specified date range from the terminal.

        Returns:
            Numpy array with bar data, or None on error.
        """
        return self._data.copy_rates_range(*args, **kwargs)  # type: ignore

    def copy_ticks_from(self, *args: object, **kwargs: object) -> Any:
        """
        Get ticks from the terminal starting from a specified date.

        Returns:
            Numpy array with tick data, or None on error.
        """
        return self._data.copy_ticks_from(*args, **kwargs)  # type: ignore

    def copy_ticks_range(self, *args: object, **kwargs: object) -> Any:
        """
        Get ticks for a specified date range from the terminal.

        Returns:
            Numpy array with tick data, or None on error.
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
