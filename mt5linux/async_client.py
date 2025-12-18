"""Async MetaTrader5 client for mt5linux.

Native gRPC async client using grpc.aio for non-blocking MT5 operations.
No asyncio.to_thread() - pure async gRPC calls.

Example:
    >>> async with AsyncMetaTrader5(host="localhost", port=50051) as mt5:
    ...     await mt5.initialize(login=12345)
    ...     account = await mt5.account_info()
    ...     rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

Thread Safety:
    The async client uses grpc.aio for true async operations.
    Multiple concurrent coroutines can safely make requests in parallel.
    HTTP/2 connection multiplexing allows efficient concurrent operations.

Resilience Features (opt-in via config):
    - Automatic reconnection with exponential backoff
    - Background health monitoring
    - Circuit breaker for cascading failure prevention

Compatible with grpcio 1.60+ and Python 3.13+.

"""

from __future__ import annotations

# pylint: disable=no-member  # Protobuf generated code has dynamic members
import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Self, TypeVar

import grpc
import grpc.aio
import orjson

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants as c
from mt5linux.models import MT5Models
from mt5linux.protocols import AsyncMT5Protocol
from mt5linux.types import MT5Types
from mt5linux.utilities import MT5Utilities

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import numpy as np
    from numpy.typing import NDArray

# TypeVar for generic return type in _resilient_call
T = TypeVar("T")

log = logging.getLogger(__name__)


# Default config instance - Single Source of Truth
_config = MT5Config()

# Error message constant
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect() first"

# Health check failure threshold before marking disconnected
_HEALTH_CHECK_FAILURE_THRESHOLD = 3

# gRPC channel options from config (no more hardcoded values)
_CHANNEL_OPTIONS = _config.get_grpc_channel_options()

# Type alias for convenience (single source of truth)
JSONValue = MT5Types.JSONValue


class AsyncMetaTrader5(AsyncMT5Protocol):
    """Async wrapper for MetaTrader5 client using native gRPC async.

    Uses grpc.aio.insecure_channel for true async operations.
    Implements AsyncMT5Protocol (32 methods matching MetaTrader5 PyPI exactly).
    All MT5 operations are executed via native gRPC async stubs.

    Note: connect(), disconnect(), health_check(), is_connected are mt5linux
    extensions NOT part of the AsyncMT5Protocol (not in MetaTrader5 PyPI).

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants (via __getattr__)
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants

    All MetaTrader5 methods are available as async versions.

    """

    def __init__(
        self,
        host: str = _config.host,
        port: int = _config.bridge_port,
        timeout: int = _config.timeout_connection,
        *,
        health_check_interval: int = _config.timeout_health_check,
        max_reconnect_attempts: int = _config.retry_max_attempts,
    ) -> None:
        """Initialize async MT5 client.

        Args:
            host: gRPC server address.
            port: gRPC server port.
            timeout: Timeout in seconds for MT5 operations.
            health_check_interval: Seconds between connection health checks.
            max_reconnect_attempts: Max attempts for reconnection.

        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._health_check_interval = health_check_interval
        self._max_reconnect_attempts = max_reconnect_attempts
        self._channel: grpc.aio.Channel | None = None
        self._stub: mt5_pb2_grpc.MT5ServiceStub | None = None
        self._constants: dict[str, int] = {}
        self._connect_lock: asyncio.Lock | None = None
        # Instance-level lock - each client has its own lock (not class-level)
        self._lock = asyncio.Lock()

        # Resilience components (opt-in via config)
        self._config = _config
        self._circuit_breaker: MT5Utilities.CircuitBreaker | None = None
        if self._config.enable_circuit_breaker:
            self._circuit_breaker = MT5Utilities.CircuitBreaker(
                config=self._config,
                name="async-mt5-client",
            )

        # Health monitoring
        self._health_task: asyncio.Task[None] | None = None
        self._health_monitor_running = False
        self._consecutive_failures = 0

        # Request queue for parallel execution (100% transparent)
        self._queue: MT5Utilities.RequestQueue | None = None

        # Write-Ahead Log for order persistence (100% transparent)
        self._wal: MT5Utilities.WAL | None = None

        # Background tasks for fire-and-forget operations (prevent GC)
        self._background_tasks: set[asyncio.Task[object]] = set()

        # Operation lock for critical sections (e.g., verify during disconnect)
        self._operation_lock = asyncio.Lock()

        # Stored credentials for auto-reinitialize when terminal disconnects
        self._init_credentials: dict[str, str | int | None] = {}

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._channel is not None

    def __getattr__(self, name: str) -> int:
        """Get MT5 constants (TIMEFRAME_H1, ORDER_TYPE_BUY, etc).

        Args:
            name: Constant name to retrieve.

        Returns:
            Integer value of the constant.

        Raises:
            AttributeError: If constant not found.

        """
        if name.startswith("_"):
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)

        if name in self._constants:
            return self._constants[name]

        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self._connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self._disconnect()

    async def _connect(self) -> None:
        """Connect to gRPC server.

        Thread-safe: uses asyncio.Lock to prevent race conditions.
        Also initializes Queue and WAL (100% transparent).
        """
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()

        async with self._connect_lock:
            if self._channel is not None:
                return

            target = f"{self._host}:{self._port}"
            log.debug("Connecting to gRPC server at %s", target)

            self._channel = grpc.aio.insecure_channel(target, options=_CHANNEL_OPTIONS)
            self._stub = mt5_pb2_grpc.MT5ServiceStub(self._channel)

            # Load constants from server
            await self._load_constants()

            # Initialize WAL (100% transparent)
            self._wal = MT5Utilities.WAL(self._config)
            await self._wal.initialize()

            # Recover incomplete orders from WAL
            await self._recover_incomplete_orders()

            # Start request queue (100% transparent - parallel execution)
            self._queue = MT5Utilities.RequestQueue(self._config)
            await self._queue.start()

            log.info("Connected to MT5 gRPC server at %s", target)

    async def _load_constants(self) -> None:
        """Load MT5 constants from server."""
        if self._stub is None:
            return

        try:
            response = await self._stub.GetConstants(
                mt5_pb2.Empty(), timeout=self._timeout
            )
            self._constants = dict(response.values)
            log.debug("Loaded %d constants from server", len(self._constants))
        except grpc.aio.AioRpcError as e:
            log.warning("Failed to load constants: %s", e)

    async def _disconnect(self) -> None:
        """Disconnect from gRPC server.

        Also stops Queue and WAL (100% transparent).
        """
        if self._channel is None:
            return

        # Stop queue first (graceful drain of active tasks)
        if self._queue:
            await self._queue.stop()
            self._queue = None

        # Close WAL
        if self._wal:
            await self._wal.close()
            self._wal = None

        channel = self._channel
        self._channel = None
        self._stub = None

        try:
            await channel.close(grace=None)
        except grpc.RpcError:
            log.debug("Channel close failed during disconnect")

        log.debug("Disconnected from MT5 gRPC server")

    def _ensure_connected(self) -> mt5_pb2_grpc.MT5ServiceStub:
        """Ensure client is connected and return stub.

        Raises:
            ConnectionError: "Connection lost" (retryable) if was connected,
                            "not established" (not retryable) if never connected.

        """
        if self._stub is None:
            # Check if we were previously connected (have host/port set)
            if hasattr(self, "_host") and self._host:
                # Was previously connected - retryable via _before_retry reconnect
                msg = "Connection lost - will retry with reconnect"
                raise ConnectionError(msg)
            # Never connected - programming error, not retryable
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._stub

    # =========================================================================
    # QUEUE AND WAL INTEGRATION (100% TRANSPARENT)
    # =========================================================================

    async def _queued_call(
        self,
        operation: str,
        coro_factory: Callable[[], Awaitable[T]],
        coalesce_key: str | None = None,
    ) -> T:
        """Route call through queue for parallel execution.

        100% transparent - all operations pass through this wrapper.
        Queue handles priority ordering and parallel execution.

        Args:
            operation: Operation name (e.g., "symbol_info_tick").
            coro_factory: Callable that returns the awaitable.
            coalesce_key: Optional key for request deduplication.

        Returns:
            Result from the operation.

        """
        if self._queue and self._queue.is_running:
            return await self._queue.submit(operation, coro_factory, coalesce_key)
        # Fallback if queue not ready (during connect/disconnect)
        return await coro_factory()

    async def _recover_incomplete_orders(self) -> None:
        """Recover orders that were incomplete when last disconnected.

        Called during connect() to verify WAL entries against MT5 history.
        Ensures no duplicate orders are created on reconnection.
        """
        if not self._wal:
            return

        incomplete = await self._wal.get_incomplete()
        if not incomplete:
            return

        log.info("WAL: Recovering %d incomplete orders", len(incomplete))

        for entry in incomplete:
            try:
                # Verify order state in MT5
                # Create synthetic result for verification
                synthetic_result = MT5Models.OrderResult(
                    retcode=0,
                    deal=0,
                    order=0,
                    volume=0.0,
                    price=0.0,
                    bid=0.0,
                    ask=0.0,
                    comment="",
                    request_id=0,
                )
                verified = await self._verify_order_state_impl(
                    synthetic_result, entry.request_id
                )

                if verified:
                    # Order was executed
                    await self._wal.mark_recovered(
                        entry.request_id,
                        {
                            "retcode": verified.retcode,
                            "order": verified.order,
                            "deal": verified.deal,
                        },
                    )
                    log.info(
                        "WAL: Recovered order %s - EXECUTED (order=%d, deal=%d)",
                        entry.request_id,
                        verified.order,
                        verified.deal,
                    )
                else:
                    # Order was not executed - mark failed
                    await self._wal.mark_failed(
                        entry.request_id,
                        "Order not found in MT5 after recovery",
                    )
                    log.warning(
                        "WAL: Recovered order %s - NOT FOUND",
                        entry.request_id,
                    )
            except Exception:
                log.exception(
                    "WAL: Recovery failed for %s",
                    entry.request_id,
                )

    # =========================================================================
    # RESILIENCE METHODS
    # =========================================================================

    async def _reconnect_with_backoff(self) -> bool:
        """Attempt reconnection with exponential backoff and jitter.

        Uses MT5Utilities.CircuitBreaker.async_reconnect_with_backoff
        with MT5Config values.

        Returns:
            True if reconnection successful, False otherwise.

        """

        async def attempt_connect() -> bool:
            """Single connection attempt."""
            # Close existing channel if any
            if self._channel is not None:
                with suppress(Exception):
                    await self._channel.close(grace=None)
                self._channel = None
                self._stub = None

            # Create new connection
            target = f"{self._host}:{self._port}"
            self._channel = grpc.aio.insecure_channel(target, options=_CHANNEL_OPTIONS)
            self._stub = mt5_pb2_grpc.MT5ServiceStub(self._channel)

            # Test connection with health check
            await self._stub.HealthCheck(mt5_pb2.Empty(), timeout=5.0)
            self._consecutive_failures = 0
            return True

        return await MT5Utilities.CircuitBreaker.async_reconnect_with_backoff(
            attempt_connect,
            self._config,
            name=f"mt5-{self._host}:{self._port}",
        )

    async def _ensure_connected_with_reconnect(self) -> mt5_pb2_grpc.MT5ServiceStub:
        """Ensure connection with auto-reconnect if enabled.

        Returns:
            gRPC stub for making calls.

        Raises:
            ConnectionError: If not connected and reconnection fails.

        """
        if self._stub is not None:
            return self._stub

        if self._config.enable_auto_reconnect:
            success = await self._reconnect_with_backoff()
            if success and self._stub is not None:
                return self._stub
            msg = f"Failed to reconnect after {self._max_reconnect_attempts} attempts"
            raise ConnectionError(msg)

        raise ConnectionError(_NOT_CONNECTED_MSG)

    async def _reinitialize_terminal(self) -> bool:
        """Re-initialize MT5 terminal using stored credentials.

        Called when terminal_info().connected is False but gRPC is connected.
        Single attempt - NO retry loop (caller handles retry via _resilient_call).

        Returns:
            True if re-initialization successful, False otherwise.

        """
        if not self._init_credentials:
            log.debug("No stored credentials for re-initialization")
            return False

        if not self._config.enable_auto_reconnect:
            log.debug("Auto-reconnect disabled, skipping re-initialization")
            return False

        log.info("Re-initializing MT5 terminal with stored credentials")

        try:
            stub = self._ensure_connected()
            creds = self._init_credentials
            request = mt5_pb2.InitRequest(portable=bool(creds.get("portable", False)))
            if creds.get("path") is not None:
                request.path = str(creds["path"])
            if creds.get("login") is not None:
                request.login = int(creds["login"])  # type: ignore[arg-type]
            if creds.get("password") is not None:
                request.password = str(creds["password"])
            if creds.get("server") is not None:
                request.server = str(creds["server"])
            if creds.get("timeout") is not None:
                request.timeout = int(creds["timeout"])  # type: ignore[arg-type]
            response = await stub.Initialize(request, timeout=self._timeout)
            return response.result
        except (grpc.aio.AioRpcError, ConnectionError) as e:
            log.warning("Re-initialization failed: %s", e)
            return False

    async def _ensure_terminal_connected(self) -> bool:
        """Ensure MT5 terminal is connected, re-initialize if needed.

        Returns:
            True if terminal is connected (or was re-connected).

        """
        if self._stub is None:
            return False

        try:
            response = await self._stub.TerminalInfo(
                mt5_pb2.Empty(), timeout=self._timeout
            )
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            if result_dict and result_dict.get("connected"):
                return True

            # Terminal not connected - try to re-initialize
            log.warning("MT5 terminal not connected, attempting re-initialization")
            return await self._reinitialize_terminal()

        except grpc.aio.AioRpcError as e:
            log.warning("Failed to check terminal status: %s", e)
            return False

    async def _health_monitor_task(self) -> None:
        """Background task that monitors connection health.

        Runs periodically and checks connection status.
        Marks connection as disconnected if health check fails.

        """
        log.info("Health monitor started (interval: %ds)", self._health_check_interval)

        while self._health_monitor_running:
            try:
                await asyncio.sleep(self._health_check_interval)

                if self._stub is not None:
                    try:
                        result = await asyncio.wait_for(
                            self._stub.HealthCheck(mt5_pb2.Empty()),
                            timeout=5.0,
                        )
                        if not result.connected:
                            log.warning("Health check: MT5 terminal not connected")
                            self._consecutive_failures += 1
                        else:
                            self._consecutive_failures = 0
                            log.debug("Health check: OK")

                    except TimeoutError:
                        log.warning("Health check timeout")
                        self._consecutive_failures += 1
                        threshold = _HEALTH_CHECK_FAILURE_THRESHOLD
                        if self._consecutive_failures >= threshold:
                            log.warning(
                                "Health check failed %d times, marking disconnected",
                                self._consecutive_failures,
                            )
                            await self._disconnect()

                    except grpc.aio.AioRpcError as e:
                        log.warning("Health check gRPC error: %s", e)
                        self._consecutive_failures += 1

            except asyncio.CancelledError:
                log.info("Health monitor cancelled")
                break
            except Exception as e:  # noqa: BLE001
                log.warning("Health monitor unexpected error: %s", e)

        log.info("Health monitor stopped")

    async def start_health_monitor(self) -> None:
        """Start the health monitoring background task.

        Only starts if enable_health_monitor is True in config.

        """
        if not self._config.enable_health_monitor:
            log.debug("Health monitor disabled in config")
            return

        if self._health_task is not None and not self._health_task.done():
            log.debug("Health monitor already running")
            return

        self._health_monitor_running = True
        # CRITICAL FIX v4: Wrap create_task in try-except for defensive programming
        # While create_task() rarely fails, this prevents silent failures
        try:
            self._health_task = asyncio.create_task(self._health_monitor_task())
            log.info("Health monitor task created")
        except Exception:
            log.exception("Failed to create health monitor task")
            self._health_monitor_running = False

    async def stop_health_monitor(self) -> None:
        """Stop the health monitoring background task."""
        self._health_monitor_running = False

        if self._health_task is not None:
            self._health_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_task
            self._health_task = None
            log.info("Health monitor stopped")

    def _record_circuit_success(self) -> None:
        """Record successful operation in circuit breaker."""
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_success()

    def _record_circuit_failure(self, _error: Exception | None = None) -> None:
        """Record failed operation in circuit breaker."""
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_failure()

    def _check_circuit_breaker(self, operation: str) -> None:
        """Check if circuit breaker allows operation.

        Args:
            operation: Name of operation for logging.

        Raises:
            ConnectionError: If circuit breaker is OPEN.

        """
        cb = self._circuit_breaker
        if cb is not None and not cb.can_execute():
            msg = f"Circuit breaker OPEN for {operation} ({cb.failure_count} failures)"
            raise ConnectionError(msg)

    async def _quick_health_check(self, timeout: float = 2.0) -> bool:
        """Quick health check to verify MT5 is reachable.

        CRITICAL FIX v4: Used before retry to distinguish between:
        1. MT5 slow (transient) → retry is safe
        2. MT5 offline (permanent) → retry is UNSAFE (order may have executed)

        Uses terminal_info() as a lightweight connectivity check.

        Args:
            timeout: Timeout in seconds (default 2s for quick check).

        Returns:
            True if MT5 is reachable, False if not.

        """
        try:
            stub = self._ensure_connected()
            grpc_request = mt5_pb2.GenericRequest()
            await asyncio.wait_for(
                stub.GetTerminalInfo(grpc_request),
                timeout=timeout,
            )
            return True
        except (TimeoutError, grpc.RpcError, ConnectionError):
            return False
        except Exception:  # noqa: BLE001
            return False

    async def _resilient_call(
        self,
        operation: str,
        call_factory: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute gRPC call with circuit breaker AND retry protection.

        Delegates to MT5Utilities.CircuitBreaker.async_retry_with_backoff()
        with circuit breaker hooks for unified retry logic.

        Args:
            operation: Name of the operation for logging.
            call_factory: Callable returning an awaitable (the gRPC call).

        Returns:
            Result of the gRPC call.

        Raises:
            ConnectionError: If circuit breaker is OPEN.
            MT5Utilities.Exceptions.MaxRetriesError: If all retries fail.
            Exception: Non-retryable exceptions propagate immediately.

        """
        # 1. Check if circuit allows execution BEFORE retry loop
        self._check_circuit_breaker(operation)

        # 2. Define before_retry callback for gRPC reconnection only
        # IMPORTANT: Keep this simple - no nested retry loops or recursive calls
        async def _before_retry() -> None:
            if not self.is_connected:
                try:
                    await self._reconnect_with_backoff()
                except Exception as reconnect_error:  # noqa: BLE001
                    log.warning("gRPC reconnection failed: %s", reconnect_error)

        # 3. Delegate to unified retry implementation with CB hooks
        return await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
            call_factory,
            _config,
            operation,
            should_retry=MT5Utilities.CircuitBreaker.is_retryable_exception,
            on_success=self._record_circuit_success,
            on_failure=self._record_circuit_failure,
            before_retry=_before_retry,
        )

    # =========================================================================
    # Public connection methods
    # =========================================================================

    async def connect(self) -> None:
        """Connect to gRPC server (public API)."""
        await self._connect()

    async def disconnect(self) -> None:
        """Disconnect from gRPC server (public API)."""
        await self._disconnect()

    # =========================================================================
    # TERMINAL METHODS
    # =========================================================================

    async def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection.

        Auto-connects if not already connected.
        Stores credentials for auto-reinitialize if terminal disconnects.

        Args:
            path: Path to MT5 terminal executable.
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Connection timeout in milliseconds.
            portable: Use portable mode.

        Returns:
            True if initialization successful, False otherwise.

        """
        if self._stub is None:
            await self._connect()

        # Store credentials for auto-reinitialize
        self._init_credentials = {
            "path": path,
            "login": login,
            "password": password,
            "server": server,
            "timeout": timeout,
            "portable": portable,
        }

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.InitRequest(portable=portable)
            if path is not None:
                request.path = path
            if login is not None:
                request.login = login
            if password is not None:
                request.password = password
            if server is not None:
                request.server = server
            if timeout is not None:
                request.timeout = timeout
            response = await stub.Initialize(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("initialize", _call)

    async def login(
        self,
        login: int,
        password: str | None = None,
        server: str | None = None,
        timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account.

        Args:
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Login timeout in milliseconds.

        Returns:
            True if login successful, False otherwise.

        """

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.LoginRequest(login=login, timeout=timeout)
            if password is not None:
                request.password = password
            if server is not None:
                request.server = server
            response = await stub.Login(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("login", _call)

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection.

        No-op if not connected (graceful degradation).
        """
        if self._stub is not None:
            with suppress(grpc.aio.AioRpcError):
                await self._stub.Shutdown(mt5_pb2.Empty(), timeout=self._timeout)

    async def health_check(self) -> dict[str, bool | int | str]:
        """Check MT5 service health status.

        Returns:
            Dict with health status fields:
            - healthy: bool - Overall service health
            - mt5_available: bool - MT5 module loaded
            - connected: bool - Terminal connected
            - trade_allowed: bool - Trading enabled
            - build: int - Terminal build number
            - reason: str - Error reason if unhealthy

        """

        async def _call() -> dict[str, bool | int | str]:
            stub = self._ensure_connected()
            response = await stub.HealthCheck(mt5_pb2.Empty(), timeout=self._timeout)
            return {
                "healthy": response.healthy,
                "mt5_available": response.mt5_available,
                "connected": response.connected,
                "trade_allowed": response.trade_allowed,
                "build": response.build,
                "reason": response.reason,
            }

        return await self._resilient_call("health_check", _call)

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (major, minor, build_string) or None.

        """

        async def _call() -> tuple[int, int, str] | None:
            stub = self._ensure_connected()
            response = await stub.Version(mt5_pb2.Empty(), timeout=self._timeout)
            if not response.build:
                return None
            return (response.major, response.minor, response.build)

        return await self._resilient_call("version", _call)

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description.

        Returns:
            Tuple of (error_code, error_message).

        """

        async def _call() -> tuple[int, str]:
            stub = self._ensure_connected()
            response = await stub.LastError(mt5_pb2.Empty(), timeout=self._timeout)
            return (response.code, response.message)

        return await self._resilient_call("last_error", _call)

    async def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal information.

        Returns:
            TerminalInfo object or None.

        Note:
            Auto-reinitialize is handled by _before_retry in _resilient_call,
            not here (avoids recursive loops).

        """

        async def _call() -> MT5Models.TerminalInfo | None:
            stub = self._ensure_connected()
            response = await stub.TerminalInfo(mt5_pb2.Empty(), timeout=self._timeout)
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            return MT5Models.TerminalInfo.from_mt5(result_dict)

        return await self._resilient_call("terminal_info", _call)

    async def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information.

        Returns:
            AccountInfo object or None.

        """

        async def _call() -> MT5Models.AccountInfo | None:
            stub = self._ensure_connected()
            response = await stub.AccountInfo(mt5_pb2.Empty(), timeout=self._timeout)
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            return MT5Models.AccountInfo.from_mt5(result_dict)

        return await self._resilient_call("account_info", _call)

    # =========================================================================
    # SYMBOL METHODS
    # =========================================================================

    async def symbols_total(self) -> int:
        """Get total number of available symbols.

        Returns:
            Total count of symbols.

        """

        async def _call() -> int:
            stub = self._ensure_connected()
            response = await stub.SymbolsTotal(mt5_pb2.Empty(), timeout=self._timeout)
            return response.value

        return await self._resilient_call("symbols_total", _call)

    async def symbols_get(
        self, group: str | None = None
    ) -> tuple[MT5Models.SymbolInfo, ...] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern.

        Returns:
            Tuple of SymbolInfo objects or None.

        """

        async def _call() -> tuple[MT5Models.SymbolInfo, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolsRequest()
            if group is not None:
                request.group = group
            response = await stub.SymbolsGet(request, timeout=self._timeout)
            dicts = MT5Utilities.Data.unwrap_symbols_chunks(response)
            if dicts is None:
                return None
            result = [
                s for d in dicts if (s := MT5Models.SymbolInfo.from_mt5(d)) is not None
            ]
            return tuple(result) if result else None

        return await self._resilient_call("symbols_get", _call)

    async def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            SymbolInfo object or None.

        """

        async def _call() -> MT5Models.SymbolInfo | None:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolRequest(symbol=symbol)
            response = await stub.SymbolInfo(request, timeout=self._timeout)
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            return MT5Models.SymbolInfo.from_mt5(result_dict)

        return await self._resilient_call("symbol_info", _call)

    async def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Tick object or None.

        """

        async def _call() -> MT5Models.Tick | None:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolRequest(symbol=symbol)
            response = await stub.SymbolInfoTick(request, timeout=self._timeout)
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            return MT5Models.Tick.from_mt5(result_dict)

        return await self._resilient_call("symbol_info_tick", _call)

    async def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to add, False to remove from Market Watch.

        Returns:
            True if successful, False otherwise.

        """

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolSelectRequest(symbol=symbol, enable=enable)
            response = await stub.SymbolSelect(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("symbol_select", _call)

    # =========================================================================
    # MARKET DATA METHODS
    # =========================================================================

    async def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a specific date.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (e.g., TIMEFRAME_H1).
            date_from: Start date as datetime or Unix timestamp.
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """

        async def _call() -> NDArray[np.void] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.CopyRatesRequest(
                symbol=symbol,
                timeframe=timeframe,
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                count=count,
            )
            response = await stub.CopyRatesFrom(request, timeout=self._timeout)
            return MT5Utilities.Data.numpy_from_proto(response)

        return await self._resilient_call("copy_rates_from", _call)

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates from a bar position.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            start_pos: Start position (0 = current bar).
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """

        async def _call() -> NDArray[np.void] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.CopyRatesPosRequest(
                symbol=symbol,
                timeframe=timeframe,
                start_pos=start_pos,
                count=count,
            )
            response = await stub.CopyRatesFromPos(request, timeout=self._timeout)
            return MT5Utilities.Data.numpy_from_proto(response)

        return await self._resilient_call("copy_rates_from_pos", _call)

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> NDArray[np.void] | None:
        """Copy OHLCV rates in a date range.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.

        Returns:
            NumPy structured array with OHLCV data or None.

        """

        async def _call() -> NDArray[np.void] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.CopyRatesRangeRequest(
                symbol=symbol,
                timeframe=timeframe,
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                date_to=MT5Utilities.Data.to_timestamp(date_to),
            )
            response = await stub.CopyRatesRange(request, timeout=self._timeout)
            return MT5Utilities.Data.numpy_from_proto(response)

        return await self._resilient_call("copy_rates_range", _call)

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data from a specific date.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            count: Number of ticks to copy.
            flags: Copy ticks flags.

        Returns:
            NumPy structured array with tick data or None.

        """

        async def _call() -> NDArray[np.void] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.CopyTicksRequest(
                symbol=symbol,
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                count=count,
                flags=flags,
            )
            response = await stub.CopyTicksFrom(request, timeout=self._timeout)
            return MT5Utilities.Data.numpy_from_proto(response)

        return await self._resilient_call("copy_ticks_from", _call)

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: int,
    ) -> NDArray[np.void] | None:
        """Copy tick data in a date range.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.
            flags: Copy ticks flags.

        Returns:
            NumPy structured array with tick data or None.

        """

        async def _call() -> NDArray[np.void] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.CopyTicksRangeRequest(
                symbol=symbol,
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                date_to=MT5Utilities.Data.to_timestamp(date_to),
                flags=flags,
            )
            response = await stub.CopyTicksRange(request, timeout=self._timeout)
            return MT5Utilities.Data.numpy_from_proto(response)

        return await self._resilient_call("copy_ticks_range", _call)

    # =========================================================================
    # TRADING METHODS
    # =========================================================================

    async def order_calc_margin(
        self,
        action: int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin required for an order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price: Order price.

        Returns:
            Required margin or None.

        """

        async def _call() -> float | None:
            stub = self._ensure_connected()
            request = mt5_pb2.MarginRequest(
                action=action,
                symbol=symbol,
                volume=volume,
                price=price,
            )
            response = await stub.OrderCalcMargin(request, timeout=self._timeout)
            return response.value if response.HasField("value") else None

        return await self._resilient_call("order_calc_margin", _call)

    async def order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate potential profit for an order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price_open: Open price.
            price_close: Close price.

        Returns:
            Calculated profit or None.

        """

        async def _call() -> float | None:
            stub = self._ensure_connected()
            request = mt5_pb2.ProfitRequest(
                action=action,
                symbol=symbol,
                volume=volume,
                price_open=price_open,
                price_close=price_close,
            )
            response = await stub.OrderCalcProfit(request, timeout=self._timeout)
            return response.value if response.HasField("value") else None

        return await self._resilient_call("order_calc_profit", _call)

    async def order_check(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderCheckResult | None:
        """Check order validity without sending.

        Args:
            request: Order request dictionary.

        Returns:
            Order check result object or None.

        """

        async def _call() -> MT5Models.OrderCheckResult | None:
            stub = self._ensure_connected()
            grpc_request = mt5_pb2.OrderRequest(
                json_request=orjson.dumps(request).decode()
            )
            response = await stub.OrderCheck(grpc_request, timeout=self._timeout)
            result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
            return MT5Models.OrderCheckResult.from_mt5(result_dict)

        return await self._resilient_call("order_check", _call)

    async def order_send(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        For CRITICAL operations like order_send, uses enhanced transaction
        handling with proper error classification and state verification.

        Args:
            request: Order request dictionary.

        Returns:
            Order execution result object or None.

        Raises:
            PermanentError: For non-retryable errors (REJECT, NO_MONEY, etc).
            MaxRetriesError: After exhausting all retry attempts.

        """
        return await self._safe_order_send(request)

    async def order_send_async(
        self,
        request: dict[str, JSONValue],
        on_complete: Callable[[MT5Models.OrderResult], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> str:
        """Send order asynchronously with callback notification.

        COMPATIBLE with order_send() - same request format, same result type.

        Returns IMMEDIATELY with request_id.
        Executes order in background via queue.
        Calls on_complete(result) or on_error(exception) when done.

        Args:
            request: Order request dict (same format as order_send).
            on_complete: Callback called with OrderResult on success.
            on_error: Callback called with Exception on failure.

        Returns:
            request_id: Unique ID to track this order (also in WAL).

        Example:
            def handle_result(result):
                print(f"Order {result.order} executed: {result.retcode}")

            def handle_error(error):
                print(f"Order failed: {error}")

            # Fire-and-forget with callbacks
            request_id = await mt5.order_send_async(
                {"action": TRADE_ACTION_DEAL, "symbol": "EURUSD", ...},
                on_complete=handle_result,
                on_error=handle_error,
            )
            print(f"Order queued: {request_id}")
            # Returns immediately, callbacks called later

        """
        th = MT5Utilities.TransactionHandler

        # Generate request_id BEFORE enqueuing
        prepared_request, request_id = th.prepare_request(dict(request), "order_send")

        async def _execute_with_callback() -> MT5Models.OrderResult | None:
            try:
                result = await self._safe_order_send(prepared_request)
                if on_complete and result is not None:
                    try:
                        on_complete(result)
                    except Exception:
                        log.exception("order_send_async on_complete callback failed")
                return result
            except Exception as e:
                if on_error:
                    try:
                        on_error(e)
                    except Exception:
                        log.exception("order_send_async on_error callback failed")
                raise

        # Submit to queue - fire and forget (store task ref to prevent GC)
        if self._queue and self._queue.is_running:
            task = asyncio.create_task(
                self._queue.submit(
                    operation="order_send",
                    coro_factory=_execute_with_callback,
                    coalesce_key=None,  # NEVER coalesce orders
                )
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        else:
            # Fallback: execute directly in background
            task = asyncio.create_task(_execute_with_callback())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return request_id

    async def order_send_batch(
        self,
        requests: list[dict[str, JSONValue]],
        on_each_complete: Callable[[str, MT5Models.OrderResult], None] | None = None,
        on_each_error: Callable[[str, Exception], None] | None = None,
        on_all_complete: (
            Callable[[dict[str, MT5Models.OrderResult | Exception]], None] | None
        ) = None,
    ) -> list[str]:
        """Send multiple orders in parallel with batch callbacks.

        All orders execute SIMULTANEOUSLY (up to queue_max_concurrent).
        Each order gets individual callback, plus batch completion callback.

        Args:
            requests: List of order request dicts.
            on_each_complete: Called for each successful order (request_id, result).
            on_each_error: Called for each failed order (request_id, exception).
            on_all_complete: Called when ALL orders complete (dict of results/errors).

        Returns:
            List of request_ids for all orders.

        Example:
            def on_each(rid, result):
                print(f"Order {rid}: {result.retcode}")

            def on_all(all_results):
                print(f"Batch complete: {len(all_results)} orders")

            request_ids = await mt5.order_send_batch(
                [order1, order2, order3],
                on_each_complete=on_each,
                on_all_complete=on_all,
            )

        """
        th = MT5Utilities.TransactionHandler
        request_ids: list[str] = []
        pending: dict[str, asyncio.Future[MT5Models.OrderResult | Exception]] = {}

        # Prepare all requests with unique IDs
        prepared_requests: list[tuple[dict[str, JSONValue], str]] = []
        for req in requests:
            prepared_req, request_id = th.prepare_request(dict(req), "order_send")
            request_ids.append(request_id)
            prepared_requests.append((prepared_req, request_id))

            loop = asyncio.get_running_loop()
            pending[request_id] = loop.create_future()

        async def _execute_one(req: dict[str, JSONValue], rid: str) -> None:
            try:
                result = await self._safe_order_send(req)
                if result is not None:
                    pending[rid].set_result(result)
                    if on_each_complete:
                        try:
                            on_each_complete(rid, result)
                        except Exception:
                            log.exception("order_send_batch on_each_complete failed")
                else:
                    # None result treated as error
                    exc = RuntimeError(f"order_send returned None for {rid}")
                    pending[rid].set_exception(exc)
                    if on_each_error:
                        try:
                            on_each_error(rid, exc)
                        except Exception:
                            log.exception("order_send_batch on_each_error failed")
            except Exception as e:  # noqa: BLE001 - propagate to future
                pending[rid].set_exception(e)
                if on_each_error:
                    try:
                        on_each_error(rid, e)
                    except Exception:
                        log.exception("order_send_batch on_each_error failed")

        # Fire all orders in parallel (store task refs to prevent GC)
        for prepared_req, request_id in prepared_requests:
            if self._queue and self._queue.is_running:
                task = asyncio.create_task(
                    self._queue.submit(
                        operation="order_send",
                        coro_factory=lambda r=prepared_req, rid=request_id: (
                            _execute_one(r, rid)
                        ),
                        coalesce_key=None,
                    )
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            else:
                task = asyncio.create_task(_execute_one(prepared_req, request_id))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

        # Wait for all and call batch callback
        if on_all_complete:

            async def _wait_all() -> None:
                all_results: dict[str, MT5Models.OrderResult | Exception] = {}
                for rid, future in pending.items():
                    try:
                        all_results[rid] = await future
                    except Exception as e:  # noqa: BLE001 - catch all for callbacks
                        all_results[rid] = e
                try:
                    on_all_complete(all_results)
                except Exception:
                    log.exception("order_send_batch on_all_complete callback failed")

            wait_task = asyncio.create_task(_wait_all())
            self._background_tasks.add(wait_task)
            wait_task.add_done_callback(self._background_tasks.discard)

        return request_ids

    async def _safe_order_send(
        self,
        request: dict[str, JSONValue],
    ) -> MT5Models.OrderResult | None:
        """Send order with full transaction handling.

        Uses TransactionHandler for orchestration:
        1. Prepare request with idempotency marker
        2. Execute with circuit breaker protection
        3. Classify result and handle by outcome
        4. Verify state when required (TIMEOUT/CONNECTION)

        Args:
            request: Order request dictionary.

        Returns:
            OrderResult with guaranteed correct status, or None.

        Raises:
            PermanentError: For non-retryable errors.
            MaxRetriesError: After exhausting retries.

        """
        th = MT5Utilities.TransactionHandler
        operation = "order_send"

        max_attempts, _ = th.get_retry_config(self._config, operation)
        request, request_id = th.prepare_request(request, operation)  # type: ignore[arg-type]

        # WAL: Log intent BEFORE sending (crash recovery)
        if self._wal:
            await self._wal.log_intent(request_id, dict(request))

        last_result: MT5Models.OrderResult | None = None
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                # PRE-EXECUTION: Check circuit breaker
                self._check_circuit_breaker(operation)

                # WAL: Mark as sent (gRPC call initiated)
                if self._wal:
                    await self._wal.mark_sent(request_id)

                # EXECUTION: Send order via gRPC
                result = await self._execute_order_grpc(request, attempt)

                # CRITICAL FIX: EmptyResponse means order MAY have executed but
                # response was lost. MUST verify state instead of blindly retrying
                # (which could create duplicate orders).
                if result is None:
                    log.warning(
                        "TX_EMPTY_RESPONSE: Empty result for order_send, "
                        "verifying state before retry (request_id=%s)",
                        request_id,
                    )
                    # Create synthetic result for verification
                    # (we don't have order/deal IDs, so verification will
                    # rely on request_id in comment field)
                    synthetic_result = MT5Models.OrderResult(
                        retcode=0,  # Unknown
                        deal=0,
                        order=0,
                        volume=0.0,
                        price=0.0,
                        bid=0.0,
                        ask=0.0,
                        comment="",
                        request_id=0,
                    )
                    verified = await self._verify_order_state(
                        synthetic_result, request_id
                    )
                    if verified:
                        log.info(
                            "TX_EMPTY_RESPONSE: Order found via verification, "
                            "avoiding duplicate (request_id=%s)",
                            request_id,
                        )
                        self._record_circuit_success()
                        return verified
                    # Not found - check MT5 health before retry
                    # CRITICAL FIX v4: If MT5 is offline, order might have executed
                    # before crash - retrying would duplicate
                    if not await self._quick_health_check():
                        log.error(
                            "TX_EMPTY_RESPONSE: MT5 unreachable after verification, "
                            "UNSAFE to retry (request_id=%s)",
                            request_id,
                        )
                        th.raise_permanent(
                            0,
                            f"MT5 unreachable after empty response: {request_id}",
                        )

                    log.warning(
                        "TX_EMPTY_RESPONSE: Order not found via verification, "
                        "MT5 healthy - safe to retry (request_id=%s)",
                        request_id,
                    )
                    self._record_circuit_failure()
                    delay = self._config.calculate_critical_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue  # Retry

                last_result = result

                # CLASSIFY and HANDLE
                outcome = th.classify_result(result.retcode)

                if outcome in {
                    c.Resilience.TransactionOutcome.SUCCESS,
                    c.Resilience.TransactionOutcome.PARTIAL,
                }:
                    # FIX: Use safe wrapper instead of direct CB call
                    self._record_circuit_success()
                    if outcome == c.Resilience.TransactionOutcome.PARTIAL:
                        log.warning("Order partially filled: %s", result)
                    # WAL: Mark as verified (order confirmed)
                    if self._wal:
                        wal_data = {
                            "retcode": result.retcode,
                            "order": result.order,
                            "deal": result.deal,
                        }
                        await self._wal.mark_verified(request_id, wal_data)
                    return result

                if outcome == c.Resilience.TransactionOutcome.PERMANENT_FAILURE:
                    # FIX: Use safe wrapper instead of direct CB call
                    self._record_circuit_failure()
                    # WAL: Mark as failed (permanent error)
                    if self._wal:
                        error_msg = f"Permanent: {result.retcode}"
                        await self._wal.mark_failed(request_id, error_msg)
                    th.raise_permanent(result.retcode, result.comment)

                if outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED:
                    log.warning(
                        "TX_VERIFY_REQUIRED: retcode=%d, request_id=%s",
                        result.retcode,
                        request_id,
                    )
                    verified = await self._verify_order_state(result, request_id)
                    if verified:
                        # FIX: Use safe wrapper instead of direct CB call
                        self._record_circuit_success()
                        # WAL: Mark as verified (order confirmed via verification)
                        if self._wal:
                            wal_data = {
                                "retcode": verified.retcode,
                                "order": verified.order,
                                "deal": verified.deal,
                            }
                            await self._wal.mark_verified(request_id, wal_data)
                        return verified
                    # FIX: Use safe wrapper instead of direct CB call
                    self._record_circuit_failure()
                    # WAL: Mark as failed (verification failed)
                    if self._wal:
                        await self._wal.mark_failed(
                            request_id, f"Verification failed: retcode={result.retcode}"
                        )
                    th.raise_permanent(
                        result.retcode,
                        f"Verification failed: {request_id}",
                    )

                # RETRY: Record failure and delay
                # FIX: Use safe wrapper instead of direct CB call
                self._record_circuit_failure()
                delay = self._config.calculate_critical_retry_delay(attempt)
                log.warning(
                    "Retryable error %d, attempt %d/%d, retrying in %.2fs",
                    result.retcode,
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            except MT5Utilities.Exceptions.PermanentError:
                raise
            except Exception as e:
                last_error = e
                if not MT5Utilities.CircuitBreaker.is_retryable_exception(e):
                    # FIX: Use safe wrapper instead of direct CB call
                    self._record_circuit_failure()
                    raise
                # FIX: Use safe wrapper instead of direct CB call
                self._record_circuit_failure()

                # CRITICAL FIX v4: If MT5 went offline (ConnectionError, Timeout),
                # order MAY have been sent before the connection dropped.
                # Verify health before retrying to avoid duplicate orders.
                if not await self._quick_health_check():
                    log.error(  # noqa: TRY400 - intentional, no traceback needed
                        "order_send exception with MT5 unreachable: %s - "
                        "UNSAFE to retry (request_id=%s)",
                        e,
                        request_id,
                    )
                    # Try to verify state one more time
                    if request_id:
                        synthetic_result = MT5Models.OrderResult(
                            retcode=0,
                            deal=0,
                            order=0,
                            volume=0.0,
                            price=0.0,
                            bid=0.0,
                            ask=0.0,
                            comment="",
                            request_id=0,
                        )
                        verified = await self._verify_order_state(
                            synthetic_result, request_id
                        )
                        if verified:
                            log.info(
                                "order_send exception but order found: %s",
                                request_id,
                            )
                            return verified
                    th.raise_permanent(
                        0,
                        f"MT5 unreachable after exception: {e} ({request_id})",
                    )

                delay = self._config.calculate_critical_retry_delay(attempt)
                log.warning(
                    "Exception in order_send: %s, attempt %d/%d, MT5 healthy - "
                    "retrying in %.2fs",
                    e,
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

        th.raise_exhausted(operation, max_attempts, last_result, last_error)
        return None  # Unreachable - raise_exhausted always raises

    async def _execute_order_grpc(
        self,
        request: dict[str, JSONValue],
        attempt: int,
    ) -> MT5Models.OrderResult | None:
        """Execute order via gRPC and parse result.

        Args:
            request: Order request dictionary.
            attempt: Current attempt number.

        Returns:
            Parsed OrderResult or None.

        """
        if self._config.tx_log_critical:
            log.info(
                "TX_INTENT: order_send attempt=%d request=%s", attempt + 1, request
            )

        stub = self._ensure_connected()
        grpc_request = mt5_pb2.OrderRequest(json_request=orjson.dumps(request).decode())
        response = await stub.OrderSend(grpc_request, timeout=self._timeout)
        result_dict = MT5Utilities.Data.json_to_dict(response.json_data)
        result = MT5Models.OrderResult.from_mt5(result_dict)

        if result and self._config.tx_log_critical:
            log.info(
                "TX_RESULT: order_send retcode=%d deal=%d order=%d",
                result.retcode,
                result.deal,
                result.order,
            )
        return result

    async def _execute_with_timeout_and_cancel(
        self,
        coro: object,
        timeout: float,
        operation_name: str,
    ) -> tuple[object | None, bool]:
        """Execute coroutine with timeout and proper task cancellation.

        CRITICAL FIX: asyncio.wait_for() doesn't guarantee cleanup of child tasks.
        This helper ensures:
        1. Task is explicitly created for tracking
        2. On timeout, task is explicitly cancelled
        3. We wait for cancellation to complete (no orphan tasks)

        Args:
            coro: Coroutine to execute.
            timeout: Timeout in seconds.
            operation_name: Name for logging.

        Returns:
            Tuple of (result, timed_out) where:
            - result: Result of coroutine, or None on timeout/cancel
            - timed_out: True if operation timed out, False otherwise

        Raises:
            ValueError: If timeout <= 0.
            Exception: Any non-timeout exception from the coroutine.

        """
        # CRITICAL FIX v4: Validate timeout > 0
        # timeout=0 causes immediate TimeoutError without giving task a chance
        if timeout <= 0:
            msg = f"timeout must be > 0, got {timeout}"
            raise ValueError(msg)

        task: asyncio.Task[T] = asyncio.create_task(coro)  # type: ignore[arg-type]
        try:
            result = await asyncio.wait_for(task, timeout=timeout)
            return result, False
        except TimeoutError:
            # CRITICAL FIX v4: Check if result arrived just before timeout
            # This handles the race condition where result arrives exactly at
            # the timeout boundary - we shouldn't discard a valid result!
            if task.done() and not task.cancelled():
                try:
                    result = task.result()
                    log.debug(
                        "TX_VERIFY: %s completed at timeout boundary (%.1fs)",
                        operation_name,
                        timeout,
                    )
                    return result, False  # Result arrived! Not a timeout.
                except Exception:  # noqa: BLE001, S110 - treat as timeout
                    pass

            # Task didn't complete - cancel it
            task.cancel()
            # Wait for cancellation to complete (suppress CancelledError)
            with suppress(asyncio.CancelledError):
                await task
            log.debug(
                "TX_VERIFY: %s cancelled after %.1fs timeout",
                operation_name,
                timeout,
            )
            return None, True

    async def _verify_order_state(
        self,
        result: MT5Models.OrderResult,
        request_id: str | None = None,
    ) -> MT5Models.OrderResult | None:
        """Verify actual order state after ambiguous response.

        For CRITICAL operations (especially TIMEOUT/CONNECTION errors),
        we MUST know the true state before deciding to retry.

        Improvements for safety:
        - Initial propagation delay (500ms) for MT5 internal sync
        - Multiple verification attempts with delay between
        - Verification by comment field (request_id) for definitive match
        - CRITICAL FIX: Explicit task cancellation on timeout
        - CRITICAL FIX: Circuit breaker failure recorded on each verify error
        - CRITICAL FIX: Uses _operation_lock to prevent disconnect during verify

        Args:
            result: The ambiguous result from order_send.
            request_id: Optional request ID for comment field matching.

        Returns:
            Verified OrderResult if state determined, None otherwise.

        """
        if not self._config.tx_verify_on_ambiguous:
            return None

        # CRITICAL: Acquire operation lock to prevent _disconnect() during verify
        # If disconnect happens while we're verifying, we'd get ConnectionError,
        # which would make verification return None, allowing unsafe retry
        async with self._operation_lock:
            return await self._verify_order_state_impl(result, request_id)

    async def _verify_order_state_impl(
        self,
        result: MT5Models.OrderResult,
        request_id: str | None = None,
    ) -> MT5Models.OrderResult | None:
        """Implement order state verification.

        Separated from _verify_order_state to keep the lock acquisition clean.
        This method assumes _operation_lock is already held.
        """
        # Get verification settings from config
        verify_timeout = self._config.tx_verify_timeout
        max_attempts = self._config.tx_verify_max_attempts
        propagation_delay = self._config.tx_verify_propagation_delay

        # Retry verification up to max_attempts times with delay
        for attempt in range(max_attempts):
            # Propagation delay before each attempt (MT5 may not have synced yet)
            await asyncio.sleep(propagation_delay)

            try:
                # CRITICAL FIX v4: Handle synthetic/empty result (order=0, deal=0)
                # When both IDs are zero (e.g., from EmptyResponseError), we can ONLY
                # verify by comment. Without request_id, we cannot verify at all.
                if not result.order and not result.deal:
                    if not request_id:
                        log.warning(
                            "TX_VERIFY attempt %d: Cannot verify - order=0, deal=0, "
                            "no request_id available",
                            attempt + 1,
                        )
                        # No way to verify - continue to next attempt in case
                        # MT5 propagation delay causes IDs to appear
                        continue

                    # Only option is verify_by_comment
                    verified, timed_out = await self._execute_with_timeout_and_cancel(
                        self._verify_by_comment(request_id, result),
                        verify_timeout,
                        f"verify_by_comment_only({request_id})",
                    )
                    if timed_out:
                        self._record_circuit_failure()
                        log.warning(
                            "TX_VERIFY attempt %d: verify_by_comment timeout (ids=0)",
                            attempt + 1,
                        )
                        continue
                    if verified:
                        log.info(
                            "TX_VERIFY: Found by comment %s (ids=0, attempt %d)",
                            request_id,
                            attempt + 1,
                        )
                        return verified
                    # Not found - continue to next attempt
                    continue

                # Check 1: Pending orders (if we have order ticket)
                if result.order:
                    orders, timed_out = await self._execute_with_timeout_and_cancel(
                        self.orders_get(ticket=result.order),
                        verify_timeout,
                        f"orders_get({result.order})",
                    )
                    if timed_out:
                        # CRITICAL FIX: Record CB failure on each timeout
                        self._record_circuit_failure()
                        log.warning(
                            "TX_VERIFY attempt %d: orders_get timeout after %.1fs",
                            attempt + 1,
                            verify_timeout,
                        )
                        continue
                    if orders:
                        log.info(
                            "TX_VERIFY: Order %d found pending (attempt %d)",
                            result.order,
                            attempt + 1,
                        )
                        return MT5Models.OrderResult(
                            retcode=c.Order.TradeRetcode.PLACED,
                            deal=result.deal,
                            order=result.order,
                            volume=result.volume,
                            price=result.price,
                            bid=result.bid,
                            ask=result.ask,
                            comment=result.comment,
                            request_id=result.request_id,
                        )

                    # Check 2: History orders
                    history, timed_out = await self._execute_with_timeout_and_cancel(
                        self.history_orders_get(ticket=result.order),
                        verify_timeout,
                        f"history_orders_get({result.order})",
                    )
                    if timed_out:
                        # CRITICAL FIX: Record CB failure on each timeout
                        self._record_circuit_failure()
                        log.warning(
                            "TX_VERIFY attempt %d: history_orders_get timeout",
                            attempt + 1,
                        )
                        continue
                    if history:
                        log.info(
                            "TX_VERIFY: Order %d found in history (attempt %d)",
                            result.order,
                            attempt + 1,
                        )
                        return MT5Models.OrderResult(
                            retcode=c.Order.TradeRetcode.DONE,
                            deal=result.deal,
                            order=result.order,
                            volume=result.volume,
                            price=result.price,
                            bid=result.bid,
                            ask=result.ask,
                            comment=result.comment,
                            request_id=result.request_id,
                        )

                # Check 3: Deals (definitive execution proof)
                if result.deal:
                    deals, timed_out = await self._execute_with_timeout_and_cancel(
                        self.history_deals_get(ticket=result.deal),
                        verify_timeout,
                        f"history_deals_get({result.deal})",
                    )
                    if timed_out:
                        # CRITICAL FIX: Record CB failure on each timeout
                        self._record_circuit_failure()
                        log.warning(
                            "TX_VERIFY attempt %d: history_deals_get timeout",
                            attempt + 1,
                        )
                        continue
                    if deals:
                        log.info(
                            "TX_VERIFY: Deal %d confirmed (attempt %d)",
                            result.deal,
                            attempt + 1,
                        )
                        return MT5Models.OrderResult(
                            retcode=c.Order.TradeRetcode.DONE,
                            deal=result.deal,
                            order=result.order,
                            volume=result.volume,
                            price=result.price,
                            bid=result.bid,
                            ask=result.ask,
                            comment=result.comment,
                            request_id=result.request_id,
                        )

                # Check 4: Verify by comment field (if we have request_id)
                if request_id:
                    verified, timed_out = await self._execute_with_timeout_and_cancel(
                        self._verify_by_comment(request_id, result),
                        verify_timeout,
                        f"verify_by_comment({request_id})",
                    )
                    if timed_out:
                        # CRITICAL FIX: Record CB failure on each timeout
                        self._record_circuit_failure()
                        log.warning(
                            "TX_VERIFY attempt %d: verify_by_comment timeout",
                            attempt + 1,
                        )
                        continue
                    if verified:
                        log.info(
                            "TX_VERIFY: Found by comment %s (attempt %d)",
                            request_id,
                            attempt + 1,
                        )
                        return verified

            except grpc.RpcError as e:
                # CRITICAL FIX: Record CB failure on gRPC errors during verify
                self._record_circuit_failure()
                log.warning(
                    "TX_VERIFY attempt %d: gRPC error: %s",
                    attempt + 1,
                    e.code() if hasattr(e, "code") else str(e),
                )
                continue
            except (NameError, TypeError, AttributeError):
                # Bug in code - don't hide it!
                log.exception("TX_VERIFY BUG detected")
                raise
            except Exception:
                # Unexpected error - log and propagate
                log.exception("TX_VERIFY unexpected error")
                raise

        log.warning("TX_VERIFY: Could not verify after %d attempts", max_attempts)
        return None

    async def _verify_by_comment(
        self,
        request_id: str,
        result: MT5Models.OrderResult,
    ) -> MT5Models.OrderResult | None:
        """Verify order by comment field match.

        Searches recent history deals for matching request_id in comment.
        This provides definitive proof of execution when order/deal IDs
        weren't returned in the ambiguous response.

        Args:
            request_id: Request ID to search for.
            result: Original result to copy fields from.

        Returns:
            Verified OrderResult if found, None otherwise.

        """
        now = datetime.now(UTC)
        # Use configurable window to handle clock skew and propagation delays
        search_window = self._config.tx_verify_search_window_minutes
        from_time = now - timedelta(minutes=search_window)

        # Search recent deals by comment
        deals = await self.history_deals_get(date_from=from_time, date_to=now)
        tracker = MT5Utilities.TransactionHandler.RequestTracker

        # CRITICAL FIX v4: Explicitly handle None vs empty list
        # - None: Could be gRPC error (logged elsewhere)
        # - []: No deals in time window (normal)
        # - (): Empty tuple (treat same as [])
        if deals is None:
            log.debug("TX_VERIFY: history_deals_get returned None")
            return None

        if not deals:  # Empty list or tuple
            log.debug("TX_VERIFY: No deals in search window")
            return None

        for deal in deals:
            req_id = tracker.extract_request_id(deal.comment)
            if req_id == request_id:
                log.info(
                    "TX_VERIFY: Found deal %d by comment match %s",
                    deal.ticket,
                    request_id,
                )
                return MT5Models.OrderResult(
                    retcode=c.Order.TradeRetcode.DONE,
                    deal=deal.ticket,
                    order=deal.order,
                    volume=deal.volume,
                    price=deal.price,
                    bid=result.bid,
                    ask=result.ask,
                    comment=deal.comment,
                    request_id=result.request_id,
                )

        return None

    # =========================================================================
    # POSITIONS METHODS
    # =========================================================================

    async def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Count of open positions.

        """

        async def _call() -> int:
            stub = self._ensure_connected()
            response = await stub.PositionsTotal(mt5_pb2.Empty(), timeout=self._timeout)
            return response.value

        return await self._resilient_call("positions_total", _call)

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Position, ...] | None:
        """Get open positions with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific position ticket.

        Returns:
            Tuple of Position objects or None.

        """

        async def _call() -> tuple[MT5Models.Position, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.PositionsRequest()
            if symbol is not None:
                request.symbol = symbol
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            response = await stub.PositionsGet(request, timeout=self._timeout)
            json_items = list(response.json_items)
            dicts = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if dicts is None:
                return None
            return tuple(MT5Models.Position.model_validate(d) for d in dicts)

        return await self._resilient_call("positions_get", _call)

    # =========================================================================
    # ORDERS METHODS
    # =========================================================================

    async def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Count of pending orders.

        """

        async def _call() -> int:
            stub = self._ensure_connected()
            response = await stub.OrdersTotal(mt5_pb2.Empty(), timeout=self._timeout)
            return response.value

        return await self._resilient_call("orders_total", _call)

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get pending orders with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific order ticket.

        Returns:
            Tuple of Order objects or None.

        """

        async def _call() -> tuple[MT5Models.Order, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.OrdersRequest()
            if symbol is not None:
                request.symbol = symbol
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            response = await stub.OrdersGet(request, timeout=self._timeout)
            json_items = list(response.json_items)
            dicts = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if dicts is None:
                return None
            return tuple(MT5Models.Order.model_validate(d) for d in dicts)

        return await self._resilient_call("orders_get", _call)

    # =========================================================================
    # HISTORY METHODS
    # =========================================================================

    async def history_orders_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical orders in date range.

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            Count of historical orders.

        """

        async def _call() -> int:
            stub = self._ensure_connected()
            request = mt5_pb2.HistoryRequest(
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                date_to=MT5Utilities.Data.to_timestamp(date_to),
            )
            response = await stub.HistoryOrdersTotal(request, timeout=self._timeout)
            return response.value

        return await self._resilient_call("history_orders_total", _call)

    async def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get historical orders with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific order ticket.
            position: Position ID filter.

        Returns:
            Tuple of Order objects or None.

        """

        async def _call() -> tuple[MT5Models.Order, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.HistoryRequest()
            if date_from is not None:
                request.date_from = MT5Utilities.Data.to_timestamp(date_from)
            if date_to is not None:
                request.date_to = MT5Utilities.Data.to_timestamp(date_to)
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            if position is not None:
                request.position = position
            response = await stub.HistoryOrdersGet(request, timeout=self._timeout)
            json_items = list(response.json_items)
            dicts = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if dicts is None:
                return None
            return tuple(MT5Models.Order.model_validate(d) for d in dicts)

        return await self._resilient_call("history_orders_get", _call)

    async def history_deals_total(
        self,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> int:
        """Get total count of historical deals in date range.

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            Count of historical deals.

        """

        async def _call() -> int:
            stub = self._ensure_connected()
            request = mt5_pb2.HistoryRequest(
                date_from=MT5Utilities.Data.to_timestamp(date_from),
                date_to=MT5Utilities.Data.to_timestamp(date_to),
            )
            response = await stub.HistoryDealsTotal(request, timeout=self._timeout)
            return response.value

        return await self._resilient_call("history_deals_total", _call)

    async def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Deal, ...] | None:
        """Get historical deals with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific deal ticket.
            position: Position ID filter.

        Returns:
            Tuple of Deal objects or None.

        """

        async def _call() -> tuple[MT5Models.Deal, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.HistoryRequest()
            if date_from is not None:
                request.date_from = MT5Utilities.Data.to_timestamp(date_from)
            if date_to is not None:
                request.date_to = MT5Utilities.Data.to_timestamp(date_to)
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            if position is not None:
                request.position = position
            response = await stub.HistoryDealsGet(request, timeout=self._timeout)
            json_items = list(response.json_items)
            dicts = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if dicts is None:
                return None
            return tuple(MT5Models.Deal.model_validate(d) for d in dicts)

        return await self._resilient_call("history_deals_get", _call)

    # =========================================================================
    # MARKET DEPTH METHODS
    # =========================================================================

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) for a symbol.

        Must be called before market_book_get to receive updates.

        Args:
            symbol: Symbol name to subscribe to.

        Returns:
            True if subscription successful, False otherwise.

        """

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolRequest(symbol=symbol)
            response = await stub.MarketBookAdd(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("market_book_add", _call)

    async def market_book_get(
        self, symbol: str
    ) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior market_book_add call.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            Tuple of BookEntry objects or None.

        """

        async def _call() -> tuple[MT5Models.BookEntry, ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolRequest(symbol=symbol)
            response = await stub.MarketBookGet(request, timeout=self._timeout)
            json_items = list(response.json_items)
            dicts = MT5Utilities.Data.unwrap_proto_list_to_dicts(json_items)
            if dicts is None:
                return None
            return tuple(MT5Models.BookEntry.model_validate(d) for d in dicts)

        return await self._resilient_call("market_book_get", _call)

    async def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.

        """

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolRequest(symbol=symbol)
            response = await stub.MarketBookRelease(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("market_book_release", _call)
