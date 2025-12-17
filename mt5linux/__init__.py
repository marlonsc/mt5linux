"""MetaTrader5 client/server library for Linux via gRPC.

Provides MetaTrader5 class for connecting to MT5 via gRPC.
Both synchronous and asynchronous clients are available.

Usage (Synchronous):
    >>> from mt5linux import MetaTrader5
    >>> with MetaTrader5(host="localhost", port=50051) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

Usage (Asynchronous):
    >>> from mt5linux import AsyncMetaTrader5
    >>> async with AsyncMetaTrader5(host="localhost", port=50051) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

Version: 0.6.0 - gRPC Migration
- Replaced RPyC with gRPC for communication
- Native async client using grpc.aio
- Native sync client using grpc.insecure_channel
- Full MT5 API coverage including Market Depth
"""

__version__ = "0.6.0"

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
    "__version__",
]
