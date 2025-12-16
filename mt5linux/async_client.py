"""Async MetaTrader5 client for mt5linux.

Non-blocking wrapper using asyncio.to_thread for MT5 operations.
All resilience (circuit breaker, retries) is handled by the sync client.

Example:
    >>> async with AsyncMetaTrader5(host="localhost", port=8001) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     account = await mt5.account_info()
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

Thread Safety:
    The async client wraps a synchronous MetaTrader5 client and executes
    operations via asyncio.to_thread(). While the async interface is safe
    for concurrent coroutines, the underlying sync client shares a single
    RPyC connection. High-concurrency scenarios may experience serialization
    at the connection level.

Attribute Access:
    The __getattr__ method proxies MT5 constants (TIMEFRAME_*, ORDER_TYPE_*, etc.)
    directly from the sync client. These are simple attribute lookups and do not
    block. Do NOT call methods via __getattr__ - use the explicit async methods.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from mt5linux.client import _NOT_CONNECTED_MSG, MetaTrader5

if TYPE_CHECKING:
    from mt5linux.types import MT5Types

    RatesArray = MT5Types.RatesArray
    TicksArray = MT5Types.TicksArray

log = logging.getLogger(__name__)

# Default health check interval in seconds
DEFAULT_HEALTH_CHECK_INTERVAL = 60

# _NOT_CONNECTED_MSG imported from client.py (DRY)


class AsyncMetaTrader5:
    """Async wrapper for MetaTrader5 client.

    All MT5 operations are executed via asyncio.to_thread() to avoid blocking
    the asyncio event loop. Resilience (circuit breaker, retries) is handled
    by the underlying sync client.

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants (via __getattr__)
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants
        (via __getattr__)

    Thread Safety:
        - connect() is protected by asyncio.Lock (safe for concurrent calls)
        - Lock initialization uses threading.Lock guard (safe across threads)
        - Operations on the sync client may serialize at the RPyC connection level
    """

    # Class-level lock for initializing instance locks (thread-safe)
    _lock_init_guard = threading.Lock()

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
        *,
        health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
        max_reconnect_attempts: int = 3,
    ) -> None:
        """Initialize async MT5 client.

        Args:
            host: RPyC server address.
            port: RPyC server port.
            timeout: Timeout in seconds for MT5 operations.
            health_check_interval: Seconds between connection health checks.
            max_reconnect_attempts: Max attempts for reconnection.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._health_check_interval = health_check_interval
        self._max_reconnect_attempts = max_reconnect_attempts
        self._sync_client: MetaTrader5 | None = None
        self._connect_lock: asyncio.Lock | None = None

    @property
    def is_connected(self) -> bool:
        """Check if client is connected.

        Returns:
            True if connected to RPyC server.
        """
        return self._sync_client is not None

    def __getattr__(self, name: str) -> Any:
        """Proxy MT5 constants (TIMEFRAME_*, ORDER_TYPE_*, etc.).

        Warning:
            This only works for attribute access (constants).
            Do NOT call methods via this - use the explicit async methods.
        """
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
        """Connect to RPyC server.

        Thread-safe: uses asyncio.Lock to prevent race conditions
        when multiple coroutines call connect() concurrently.
        Lock initialization uses threading.Lock for thread safety.
        """
        # Thread-safe lock initialization
        with self._lock_init_guard:
            if self._connect_lock is None:
                self._connect_lock = asyncio.Lock()

        async with self._connect_lock:
            if self._sync_client is not None:
                return

            def _connect() -> MetaTrader5:
                return MetaTrader5(
                    self._host,
                    self._port,
                    self._timeout,
                    health_check_interval=self._health_check_interval,
                    max_reconnect_attempts=self._max_reconnect_attempts,
                )

            self._sync_client = await asyncio.to_thread(_connect)
            log.debug("Connected to MT5 at %s:%s", self._host, self._port)

    async def disconnect(self) -> None:
        """Disconnect from RPyC server.

        Safe cleanup: resets state FIRST, then attempts cleanup operations.
        This ensures the client is in a consistent state even if cleanup fails.
        """
        if self._sync_client is None:
            return

        # Capture reference and reset state FIRST (atomic-ish)
        client = self._sync_client
        self._sync_client = None

        # Attempt graceful shutdown
        try:
            await asyncio.to_thread(client.shutdown)
        except (OSError, ConnectionError, EOFError):
            log.debug(
                "MT5 shutdown failed during disconnect (connection may be closed)"
            )

        # Always attempt to close connection
        try:
            await asyncio.to_thread(client.close)
        except (OSError, ConnectionError, EOFError):
            log.debug("RPyC close failed during disconnect (may already be closed)")

        log.debug("Disconnected from MT5")

    def _ensure_connected(self) -> MetaTrader5:
        """Ensure client is connected and return sync client.

        Raises:
            ConnectionError: If not connected.

        Returns:
            The sync MetaTrader5 client.
        """
        if self._sync_client is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._sync_client

    async def _call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call sync client method via asyncio.to_thread.

        All resilience (circuit breaker, retries) is handled by the sync client.

        Args:
            method_name: Name of the method to call on sync client.
            *args: Positional arguments for the method.
            **kwargs: Keyword arguments for the method.

        Returns:
            Result from the method call.

        Raises:
            ConnectionError: If not connected.
        """
        client = self._ensure_connected()
        method = getattr(client, method_name)
        return await asyncio.to_thread(method, *args, **kwargs)

    # ========================================
    # Health & Diagnostics
    # ========================================

    async def health_check(self) -> dict[str, Any]:
        """Get server health status.

        Returns:
            Health status dict from server.

        Raises:
            ConnectionError: If not connected.
        """
        return await self._call("health_check")

    async def reset_circuit_breaker(self) -> bool:
        """Reset server circuit breaker.

        Returns:
            True if reset successful.

        Raises:
            ConnectionError: If not connected.
        """
        return await self._call("reset_circuit_breaker")

    async def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get client circuit breaker status for monitoring.

        Returns:
            Dict with circuit breaker state and metrics.

        Raises:
            ConnectionError: If not connected.
        """
        return await self._call("get_circuit_breaker_status")

    async def reset_client_circuit_breaker(self) -> None:
        """Manually reset the client's circuit breaker.

        Raises:
            ConnectionError: If not connected.
        """
        await self._call("reset_client_circuit_breaker")

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
        return await self._call(
            "initialize", path, login, password, server, timeout, portable
        )

    async def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account."""
        return await self._call("login", login, password, server, timeout)

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection.

        Note: This is a no-op if not connected (graceful degradation).
        """
        if self._sync_client is not None:
            await self._call("shutdown")

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version."""
        return await self._call("version")

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description."""
        return await self._call("last_error")

    async def terminal_info(self) -> Any:
        """Get terminal info."""
        return await self._call("terminal_info")

    async def account_info(self) -> Any:
        """Get account info."""
        return await self._call("account_info")

    # ========================================
    # Symbols
    # ========================================

    async def symbols_total(self) -> int:
        """Get total number of symbols."""
        return await self._call("symbols_total")

    async def symbols_get(self, group: str | None = None) -> Any:
        """Get symbols matching filter."""
        return await self._call("symbols_get", group)

    async def symbol_info(self, symbol: str) -> Any:
        """Get symbol info."""
        return await self._call("symbol_info", symbol)

    async def symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick info."""
        return await self._call("symbol_info_tick", symbol)

    async def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch."""
        return await self._call("symbol_select", symbol, enable)

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
        return await self._call("copy_rates_from", symbol, timeframe, date_from, count)

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> RatesArray | None:
        """Copy OHLCV rates from position."""
        return await self._call(
            "copy_rates_from_pos", symbol, timeframe, start_pos, count
        )

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> RatesArray | None:
        """Copy OHLCV rates in date range."""
        return await self._call(
            "copy_rates_range", symbol, timeframe, date_from, date_to
        )

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks from date."""
        return await self._call("copy_ticks_from", symbol, date_from, count, flags)

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks in date range."""
        return await self._call("copy_ticks_range", symbol, date_from, date_to, flags)

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
        return await self._call("order_calc_margin", action, symbol, volume, price)

    async def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate profit for order."""
        return await self._call(
            "order_calc_profit", action, symbol, volume, price_open, price_close
        )

    async def order_check(self, request: dict[str, Any]) -> Any:
        """Check order parameters."""
        return await self._call("order_check", request)

    async def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order."""
        return await self._call("order_send", request)

    # ========================================
    # Positions
    # ========================================

    async def positions_total(self) -> int:
        """Get total open positions."""
        return await self._call("positions_total")

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get open positions."""
        return await self._call("positions_get", symbol, group, ticket)

    # ========================================
    # Orders
    # ========================================

    async def orders_total(self) -> int:
        """Get total pending orders."""
        return await self._call("orders_total")

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get pending orders."""
        return await self._call("orders_get", symbol, group, ticket)

    # ========================================
    # History
    # ========================================

    async def history_orders_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None:
        """Get total historical orders."""
        return await self._call("history_orders_total", date_from, date_to)

    async def history_orders_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get historical orders."""
        return await self._call(
            "history_orders_get", date_from, date_to, group, ticket, position
        )

    async def history_deals_total(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> int | None:
        """Get total historical deals."""
        return await self._call("history_deals_total", date_from, date_to)

    async def history_deals_get(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get historical deals."""
        return await self._call(
            "history_deals_get", date_from, date_to, group, ticket, position
        )
