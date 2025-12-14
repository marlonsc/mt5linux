"""MetaTrader5 bridge for Linux via rpyc.

Transparent bridge connecting to MetaTrader5 running on Windows/Docker
via rpyc. All methods and constants are delegated to the real MT5.

Example:
    >>> from mt5linux import MetaTrader5
    >>> with MetaTrader5(host="localhost", port=8001) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     print(mt5.ORDER_TYPE_BUY)  # Real MT5 constant

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.client import MetaTrader5

__all__ = ["MetaTrader5"]
__version__ = "0.2.1"
