"""MetaTrader5 client/server library for Linux via RPyC.

Client library for connecting to MetaTrader5 running on Windows/Docker
via RPyC 6.x. Also includes a standalone bridge server for Windows.

Server (run on Windows with MT5):
    python -m mt5linux --server
    python -m mt5linux --server --host 0.0.0.0 --port 18812 --debug

Client (run on Linux):
    >>> from mt5linux import MetaTrader5, MT5Constants
    >>> with MetaTrader5(host="windows-ip", port=18812) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()

Async client:
    >>> from mt5linux import AsyncMetaTrader5
    >>> async with AsyncMetaTrader5(host="windows-ip", port=18812) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants
from mt5linux.models import MT5Models
from mt5linux.types import MT5Types
from mt5linux.utilities import MT5Utilities

__all__ = [
    "AsyncMetaTrader5",
    "MT5Config",
    "MT5Constants",
    "MT5Models",
    "MT5Types",
    "MT5Utilities",
    "MetaTrader5",
]
__version__ = "0.5.1"
