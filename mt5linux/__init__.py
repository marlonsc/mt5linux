"""MetaTrader5 bridge for Linux via rpyc.

Transparent bridge connecting to MetaTrader5 running on Windows/Docker
via rpyc 6.x. All methods and constants are delegated to the real MT5.

Example (sync):
    >>> from mt5linux import MetaTrader5, MT5
    >>> with MetaTrader5() as mt5:  # Uses config defaults (localhost:18812)
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     print(MT5.TimeFrame.H1)  # 16385

Example (async):
    >>> from mt5linux import AsyncMetaTrader5, MT5
    >>> async with AsyncMetaTrader5() as mt5:  # Uses config defaults
    ...     await mt5.initialize(login=12345)
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", MT5.TimeFrame.H1, 0, 100)

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.config import MT5Config, config
from mt5linux.constants import MT5
from mt5linux.models import MT5Models
from mt5linux.server import MT5Server
from mt5linux.types import MT5Types
from mt5linux.utilities import MT5Utilities

# Backward compatibility aliases (to be removed in next major version)
Defaults = MT5Config.Defaults
Server = MT5Server
MT5Model = MT5Models.Base
OrderRequest = MT5Models.OrderRequest
OrderResult = MT5Models.OrderResult
AccountInfo = MT5Models.AccountInfo
SymbolInfo = MT5Models.SymbolInfo
Position = MT5Models.Position
Tick = MT5Models.Tick

__all__ = [
    # Core clients
    "MetaTrader5",
    "AsyncMetaTrader5",
    # Server
    "MT5Server",
    "Server",  # backward compat
    # Configuration
    "MT5Config",
    "config",
    "Defaults",  # backward compat
    # Constants container
    "MT5",
    # Types container
    "MT5Types",
    # Utilities container
    "MT5Utilities",
    # Models container
    "MT5Models",
    # Pydantic models (backward compat aliases)
    "MT5Model",
    "OrderRequest",
    "OrderResult",
    "AccountInfo",
    "SymbolInfo",
    "Position",
    "Tick",
]
__version__ = "0.3.0"
