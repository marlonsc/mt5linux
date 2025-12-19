"""MT5 Linux Package.

A Python package for MetaTrader5 operations on Linux platforms.
Provides both synchronous and asynchronous clients for MT5 trading operations.

Main components:
- AsyncMetaTrader5: Asynchronous gRPC client for MT5 operations
- MetaTrader5: Synchronous client for MT5 operations
- MT5Settings: Configuration management with environment variable support
"""

from importlib.metadata import version

__version__ = version("mt5linux")


from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.models import MT5Models
from mt5linux.settings import MT5Settings

__all__ = [
    "AsyncMetaTrader5",
    "MT5Models",
    "MT5Settings",
    "MetaTrader5",
    "__version__",
]
