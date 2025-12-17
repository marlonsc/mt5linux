"""MT5 Linux Package.

A Python package for MetaTrader5 operations on Linux platforms.
Provides both synchronous and asynchronous clients for MT5 trading operations.

Main components:
- AsyncMetaTrader5: Asynchronous gRPC client for MT5 operations
- MetaTrader5: Synchronous client for MT5 operations
- MT5Config: Configuration management with environment variable support
"""

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.config import MT5Config
from mt5linux.models import MT5Models

__all__ = [
    "AsyncMetaTrader5",
    "MT5Config",
    "MT5Models",
    "MetaTrader5",
]
