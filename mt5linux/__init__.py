"""MetaTrader5 bridge for Linux via rpyc.

Transparent bridge connecting to MetaTrader5 running on Windows/Docker
via rpyc 6.x. All methods and constants are delegated to the real MT5.

Example (sync):
    >>> from mt5linux import MetaTrader5, MT5
    >>> with MetaTrader5(host="localhost", port=8001) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     print(MT5.TimeFrame.H1)  # 16385

Example (async):
    >>> from mt5linux import AsyncMetaTrader5, MT5
    >>> async with AsyncMetaTrader5(host="localhost", port=8001) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", MT5.TimeFrame.H1, 0, 100)

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.constants import MT5
from mt5linux.models import (
    AccountInfo,
    MT5Model,
    OrderRequest,
    OrderResult,
    Position,
    SymbolInfo,
    Tick,
)
from mt5linux.server import Server
from mt5linux.types import MT5Types

__all__ = [
    # Core clients
    "MetaTrader5",
    "AsyncMetaTrader5",
    "Server",
    # Constants container
    "MT5",
    # Types container
    "MT5Types",
    # Pydantic models
    "MT5Model",
    "OrderRequest",
    "OrderResult",
    "AccountInfo",
    "SymbolInfo",
    "Position",
    "Tick",
]
__version__ = "0.3.0"
