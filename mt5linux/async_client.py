"""Async MetaTrader5 client for mt5linux.

Non-blocking wrapper using asyncio.to_thread for MT5 operations.
All resilience (circuit breaker, retries) is handled by the sync client.

This is a thin async wrapper that dynamically converts sync methods to async
via __getattr__. No method duplication - DRY principle.

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
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
from typing import Any, Self

from mt5linux.client import _NOT_CONNECTED_MSG, MetaTrader5
from mt5linux.config import MT5Config

# Default config instance
_config = MT5Config()

log = logging.getLogger(__name__)


class AsyncMetaTrader5:
    """Async wrapper for MetaTrader5 client.

    Uses composition + __getattr__ to dynamically wrap sync methods as async.
    All MT5 operations are executed via asyncio.to_thread() to avoid blocking
    the asyncio event loop.

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants (via __getattr__)
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants

    All MetaTrader5 methods are available as async versions automatically.
    """

    # Class-level lock for initializing instance locks (thread-safe)
    _lock_init_guard = threading.Lock()

    # Methods that should NOT be wrapped (private or special)
    _PRIVATE_ATTRS = frozenset({
        "_connect", "_close", "_reconnect", "_safe_rpc_call",
        "_check_connection_health", "_ensure_healthy_connection",
        "_execute_operation",
    })

    def __init__(
        self,
        host: str = _config.host,
        port: int = _config.rpyc_port,
        timeout: int = _config.timeout_connection,
        *,
        health_check_interval: int = _config.timeout_health_check,
        max_reconnect_attempts: int = _config.retry_max_attempts,
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
        """Check if client is connected."""
        return self._sync_client is not None

    def __getattr__(self, name: str) -> Any:
        """Dynamic async wrapper for sync client methods and attributes.

        - For callable methods: returns an async wrapper
        - For non-callable attributes (constants): returns directly
        - Blocks access to private methods
        - Constants (uppercase) raise AttributeError when not connected
        - Methods (lowercase) return wrapper that raises ConnectionError when called
        """
        # Block private method access
        if name.startswith("_"):
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)

        # Not connected
        if self._sync_client is None:
            # Constants (uppercase like TIMEFRAME_H1) - raise AttributeError
            if name[0].isupper():
                msg = f"'{type(self).__name__}' object has no attribute '{name}'"
                raise AttributeError(msg)

            # Methods (lowercase) - return wrapper that raises ConnectionError
            async def not_connected_wrapper(*args: Any, **kwargs: Any) -> Any:
                raise ConnectionError(_NOT_CONNECTED_MSG)

            return not_connected_wrapper

        attr = getattr(self._sync_client, name)

        # Non-callable (constants like TIMEFRAME_H1) - return directly
        if not callable(attr):
            return attr

        # Callable (methods) - return async wrapper
        @functools.wraps(attr)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.to_thread(attr, *args, **kwargs)

        return async_wrapper

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self._disconnect()

    async def _connect(self) -> None:
        """Connect to RPyC server.

        Thread-safe: uses asyncio.Lock to prevent race conditions.
        """
        with self._lock_init_guard:
            if self._connect_lock is None:
                self._connect_lock = asyncio.Lock()

        async with self._connect_lock:
            if self._sync_client is not None:
                return

            def _create_client() -> MetaTrader5:
                return MetaTrader5(
                    self._host,
                    self._port,
                    self._timeout,
                    health_check_interval=self._health_check_interval,
                    max_reconnect_attempts=self._max_reconnect_attempts,
                )

            self._sync_client = await asyncio.to_thread(_create_client)
            log.debug("Connected to MT5 at %s:%s", self._host, self._port)

    async def _disconnect(self) -> None:
        """Disconnect from RPyC server."""
        if self._sync_client is None:
            return

        client = self._sync_client
        self._sync_client = None

        try:
            await asyncio.to_thread(client.shutdown)
        except (OSError, ConnectionError, EOFError):
            log.debug("MT5 shutdown failed during disconnect")

        try:
            await asyncio.to_thread(client._close)  # noqa: SLF001
        except (OSError, ConnectionError, EOFError):
            log.debug("RPyC close failed during disconnect")

        log.debug("Disconnected from MT5")

    def _ensure_connected(self) -> MetaTrader5:
        """Ensure client is connected and return sync client."""
        if self._sync_client is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._sync_client

    # =========================================================================
    # Special methods that need custom handling
    # =========================================================================

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

        Auto-connects if not already connected.
        """
        if self._sync_client is None:
            await self._connect()
        client = self._ensure_connected()
        return await asyncio.to_thread(
            client.initialize,
            path=path,
            login=login,
            password=password,
            server=server,
            timeout=timeout,
            portable=portable,
        )

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection.

        No-op if not connected (graceful degradation).
        """
        if self._sync_client is not None:
            await asyncio.to_thread(self._sync_client.shutdown)
