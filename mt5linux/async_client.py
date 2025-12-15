"""Async MetaTrader5 client for mt5linux.

Non-blocking wrapper using asyncio.to_thread for MT5 operations.

Example:
    >>> async with AsyncMetaTrader5(host="localhost", port=8001) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     account = await mt5.account_info()
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from mt5linux.client import MetaTrader5

if TYPE_CHECKING:
    from mt5linux._types import RatesArray, TicksArray

log = logging.getLogger(__name__)


class AsyncMetaTrader5:
    """Async wrapper for MetaTrader5 client.

    All MT5 operations are executed in a thread pool to avoid blocking
    the asyncio event loop. This is essential for neptor's concurrent
    order processing.

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
        max_workers: int = 4,
    ) -> None:
        """Initialize async MT5 client.

        Args:
            host: RPyC server address.
            port: RPyC server port.
            timeout: Timeout in seconds for MT5 operations.
            max_workers: Max threads for concurrent operations.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sync_client: MetaTrader5 | None = None
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._connected = False

    def __getattr__(self, name: str) -> Any:
        """Proxy MT5 constants (TIMEFRAME_*, ORDER_TYPE_*, etc.)."""
        if self._sync_client is not None:
            return getattr(self._sync_client, name)
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to RPyC server."""
        if self._connected:
            return

        def _connect() -> MetaTrader5:
            return MetaTrader5(self._host, self._port, self._timeout)

        self._sync_client = await asyncio.to_thread(_connect)
        self._connected = True
        log.debug("Connected to MT5 at %s:%s", self._host, self._port)

    async def disconnect(self) -> None:
        """Disconnect from RPyC server."""
        if not self._connected or self._sync_client is None:
            return

        try:
            await asyncio.to_thread(self._sync_client.shutdown)
        except (OSError, ConnectionError, EOFError):
            log.debug("MT5 shutdown failed during disconnect")

        await asyncio.to_thread(self._sync_client.close)
        self._sync_client = None
        self._connected = False
        self._executor.shutdown(wait=False)
        log.debug("Disconnected from MT5")

    # ========================================
    # Connection & Terminal
    # ========================================

    async def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection.

        Args:
            path: Path to MT5 terminal.
            login: Account number.
            password: Account password.
            server: Trade server name.
            timeout: Connection timeout.
            portable: Use portable mode.

        Returns:
            True if successful.
        """
        if self._sync_client is None:
            await self.connect()
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.initialize,
            path,
            login,
            password,
            server,
            timeout,
            portable,
        )

    async def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.login, login, password, server, timeout
        )

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection."""
        if self._sync_client is not None:
            await asyncio.to_thread(self._sync_client.shutdown)

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.version)

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.last_error)

    async def terminal_info(self) -> Any:
        """Get terminal info."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.terminal_info)

    async def account_info(self) -> Any:
        """Get account info."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.account_info)

    # ========================================
    # Symbols
    # ========================================

    async def symbols_total(self) -> int:
        """Get total number of symbols."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.symbols_total)

    async def symbols_get(self, group: str | None = None) -> tuple[Any, ...] | None:
        """Get symbols matching filter."""
        assert self._sync_client is not None
        if group:
            return await asyncio.to_thread(self._sync_client.symbols_get, group=group)
        return await asyncio.to_thread(self._sync_client.symbols_get)

    async def symbol_info(self, symbol: str) -> Any:
        """Get symbol info."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.symbol_info, symbol)

    async def symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick info."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.symbol_info_tick, symbol)

    async def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.symbol_select, symbol, enable)

    # ========================================
    # Market Data
    # ========================================

    async def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        count: int,
    ) -> RatesArray | None:
        """Copy OHLCV rates from date."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.copy_rates_from,
            symbol,
            timeframe,
            date_from,
            count,
        )

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> RatesArray | None:
        """Copy OHLCV rates from position."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.copy_rates_from_pos,
            symbol,
            timeframe,
            start_pos,
            count,
        )

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> RatesArray | None:
        """Copy OHLCV rates in date range."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.copy_rates_range,
            symbol,
            timeframe,
            date_from,
            date_to,
        )

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks from date."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.copy_ticks_from,
            symbol,
            date_from,
            count,
            flags,
        )

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks in date range."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.copy_ticks_range,
            symbol,
            date_from,
            date_to,
            flags,
        )

    # ========================================
    # Trading
    # ========================================

    async def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin for order."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.order_calc_margin,
            action,
            symbol,
            volume,
            price,
        )

    async def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate profit for order."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.order_calc_profit,
            action,
            symbol,
            volume,
            price_open,
            price_close,
        )

    async def order_check(self, request: dict[str, Any]) -> Any:
        """Check order parameters."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.order_check, request)

    async def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.order_send, request)

    # ========================================
    # Positions
    # ========================================

    async def positions_total(self) -> int:
        """Get total open positions."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.positions_total)

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get open positions."""
        assert self._sync_client is not None
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return await asyncio.to_thread(self._sync_client.positions_get, **kwargs)
        return await asyncio.to_thread(self._sync_client.positions_get)

    # ========================================
    # Orders
    # ========================================

    async def orders_total(self) -> int:
        """Get total pending orders."""
        assert self._sync_client is not None
        return await asyncio.to_thread(self._sync_client.orders_total)

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get pending orders."""
        assert self._sync_client is not None
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return await asyncio.to_thread(self._sync_client.orders_get, **kwargs)
        return await asyncio.to_thread(self._sync_client.orders_get)

    # ========================================
    # History
    # ========================================

    async def history_orders_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None:
        """Get total historical orders."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.history_orders_total,
            date_from,
            date_to,
        )

    async def history_orders_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get historical orders."""
        assert self._sync_client is not None
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return await asyncio.to_thread(
                self._sync_client.history_orders_get, **kwargs
            )
        return await asyncio.to_thread(self._sync_client.history_orders_get)

    async def history_deals_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None:
        """Get total historical deals."""
        assert self._sync_client is not None
        return await asyncio.to_thread(
            self._sync_client.history_deals_total,
            date_from,
            date_to,
        )

    async def history_deals_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[Any, ...] | None:
        """Get historical deals."""
        assert self._sync_client is not None
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return await asyncio.to_thread(
                self._sync_client.history_deals_get, **kwargs
            )
        return await asyncio.to_thread(self._sync_client.history_deals_get)
