"""MetaTrader5 bridge for Linux via rpyc.

Transparent bridge connecting to MetaTrader5 running on Windows/Docker
via rpyc 6.x. All methods and constants are delegated to the real MT5.

Example (sync):
    >>> from mt5linux import MetaTrader5
    >>> with MetaTrader5(host="localhost", port=8001) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     print(mt5.ORDER_TYPE_BUY)  # Real MT5 constant

Example (async):
    >>> from mt5linux import AsyncMetaTrader5
    >>> async with AsyncMetaTrader5(host="localhost", port=8001) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     account = await mt5.account_info()
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.client import MetaTrader5
from mt5linux.enums import (
    OrderFilling,
    OrderTime,
    OrderType,
    TradeAction,
    TradeRetcode,
)
from mt5linux.models import (
    AccountInfo,
    OrderRequest,
    OrderResult,
    Position,
    SymbolInfo,
    Tick,
)

__all__ = [
    # Clients
    "MetaTrader5",
    "AsyncMetaTrader5",
    # Pydantic models
    "OrderRequest",
    "OrderResult",
    "AccountInfo",
    "SymbolInfo",
    "Position",
    "Tick",
    # Enums
    "TradeAction",
    "OrderType",
    "OrderFilling",
    "OrderTime",
    "TradeRetcode",
]
__version__ = "0.3.0"
