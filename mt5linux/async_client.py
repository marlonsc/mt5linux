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
import ast
import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Self, TypeVar

import grpc
import grpc.aio
import numpy as np
import orjson

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from numpy.typing import NDArray

# TypeVar for generic return type in _resilient_call
T = TypeVar("T")

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.models import MT5Models
from mt5linux.protocols import AsyncClientProtocol
from mt5linux.types import MT5Types
from mt5linux.utilities import MT5Utilities

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

# TypeVar for generic return type in _resilient_call
from typing import TypeVar

T = TypeVar("T")


class AsyncMetaTrader5(AsyncClientProtocol):
    """Async wrapper for MetaTrader5 client using native gRPC async.

    Uses grpc.aio.insecure_channel for true async operations.
    Implements AsyncClientProtocol for type-safe async MT5 operations.
    All MT5 operations are executed via native gRPC async stubs.

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
        """Disconnect from gRPC server."""
        if self._channel is None:
            return

        channel = self._channel
        self._channel = None
        self._stub = None

        try:
            await channel.close(grace=None)
        except grpc.RpcError:
            log.debug("Channel close failed during disconnect")

        log.debug("Disconnected from MT5 gRPC server")

    def _ensure_connected(self) -> mt5_pb2_grpc.MT5ServiceStub:
        """Ensure client is connected and return stub."""
        if self._stub is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._stub

    # =========================================================================
    # RESILIENCE METHODS
    # =========================================================================

    async def _reconnect_with_backoff(self) -> bool:
        """Attempt reconnection with exponential backoff and jitter.

        Uses MT5Utilities.async_reconnect_with_backoff with MT5Config values.

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

        return await MT5Utilities.async_reconnect_with_backoff(
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
        self._health_task = asyncio.create_task(self._health_monitor_task())
        log.info("Health monitor task created")

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

    def _record_circuit_failure(self) -> None:
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

    async def _resilient_call(
        self,
        operation: str,
        call_factory: "Callable[[], Awaitable[T]]",
    ) -> T:
        """Execute gRPC call with circuit breaker protection.

        Integrates existing CircuitBreaker into all operations.
        Checks circuit breaker before call, records success/failure after.

        Args:
            operation: Name of the operation for logging.
            call_factory: Callable returning an awaitable (the gRPC call).

        Returns:
            Result of the gRPC call.

        Raises:
            ConnectionError: If circuit breaker is OPEN.
            Exception: Re-raises any exception from the call after recording failure.

        """
        # 1. Check if circuit allows execution
        self._check_circuit_breaker(operation)

        try:
            # 2. Execute the operation
            result = await call_factory()

            # 3. Record success
            self._record_circuit_success()
            return result

        except Exception:
            # 4. Record failure
            self._record_circuit_failure()
            raise

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
    # HELPER METHODS
    # =========================================================================

    def _json_to_dict(self, json_data: str) -> dict[str, JSONValue] | None:
        """Convert JSON string to dict.

        Args:
            json_data: JSON string to parse.

        Returns:
            Parsed dictionary or None if empty.

        """
        if not json_data:
            return None
        result: dict[str, JSONValue] = orjson.loads(json_data)
        return result

    def _json_list_to_dicts(
        self, json_items: list[str]
    ) -> list[dict[str, JSONValue]] | None:
        """Convert list of JSON strings to list of dicts.

        Args:
            json_items: List of JSON strings to parse.

        Returns:
            List of parsed dictionaries or None if empty.

        """
        if not json_items:
            return None
        result: list[dict[str, JSONValue]] = [
            orjson.loads(item) for item in json_items if item
        ]
        return result

    def _json_list_to_tuple(
        self, json_items: list[str]
    ) -> tuple[dict[str, JSONValue], ...] | None:
        """Convert list of JSON strings to tuple of dicts.

        This maintains compatibility with the original MetaTrader5 API
        which returns tuples from methods like positions_get(), orders_get(), etc.

        Args:
            json_items: List of JSON strings to parse.

        Returns:
            Tuple of parsed dictionaries or None if empty.

        """
        result = self._json_list_to_dicts(json_items)
        if result is None:
            return None
        return tuple(result)

    def _numpy_from_proto(self, proto: mt5_pb2.NumpyArray) -> NDArray[np.void] | None:
        """Convert NumpyArray proto to numpy array.

        Args:
            proto: NumpyArray protobuf message.

        Returns:
            Numpy structured array or None if empty.

        """
        if not proto.data or not proto.dtype:
            return None
        # Parse dtype string back to numpy dtype
        # The dtype comes as str(arr.dtype) e.g. "[('time', '<i8'), ...]"
        dtype_str = proto.dtype
        if dtype_str.startswith("["):
            # Structured array dtype - parse the list of tuples
            dtype_spec = ast.literal_eval(dtype_str)
            dtype = np.dtype(dtype_spec)
        else:
            # Simple dtype like 'float64', '<f8'
            dtype = np.dtype(dtype_str)
        arr = np.frombuffer(proto.data, dtype=dtype)
        if proto.shape:
            arr = arr.reshape(tuple(proto.shape))
        return arr

    def _unwrap_symbols_chunks(
        self, response: mt5_pb2.SymbolsResponse
    ) -> tuple[dict[str, JSONValue], ...] | None:
        """Unwrap chunked symbols response.

        Args:
            response: SymbolsResponse with chunked JSON data.

        Returns:
            Tuple of symbol dictionaries or None if empty.

        """
        if response.total == 0:
            return None
        result: list[dict[str, JSONValue]] = []
        for chunk in response.chunks:
            chunk_data: list[dict[str, JSONValue]] = orjson.loads(chunk)
            result.extend(chunk_data)
        return tuple(result)

    def _to_timestamp(self, dt: datetime | int) -> int:
        """Convert datetime or int to Unix timestamp.

        Args:
            dt: Datetime object or Unix timestamp.

        Returns:
            Unix timestamp as integer.

        """
        if isinstance(dt, datetime):
            return int(dt.timestamp())
        return int(dt)

    # =========================================================================
    # TERMINAL METHODS
    # =========================================================================

    async def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        init_timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal connection.

        Auto-connects if not already connected.

        Args:
            path: Path to MT5 terminal executable.
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            init_timeout: Connection timeout in milliseconds.
            portable: Use portable mode.

        Returns:
            True if initialization successful, False otherwise.

        """
        if self._stub is None:
            await self._connect()

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
            if init_timeout is not None:
                request.timeout = init_timeout
            response = await stub.Initialize(request, timeout=self._timeout)
            return response.result

        return await self._resilient_call("initialize", _call)

    async def login(
        self,
        login: int,
        password: str,
        server: str,
        login_timeout: int = 60000,
    ) -> bool:
        """Login to MT5 account.

        Args:
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            login_timeout: Login timeout in milliseconds.

        Returns:
            True if login successful, False otherwise.

        """

        async def _call() -> bool:
            stub = self._ensure_connected()
            request = mt5_pb2.LoginRequest(
                login=login,
                password=password,
                server=server,
                timeout=login_timeout,
            )
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

        """

        async def _call() -> MT5Models.TerminalInfo | None:
            stub = self._ensure_connected()
            response = await stub.TerminalInfo(mt5_pb2.Empty(), timeout=self._timeout)
            result_dict = self._json_to_dict(response.json_data)
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
            result_dict = self._json_to_dict(response.json_data)
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
    ) -> tuple[dict[str, JSONValue], ...] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern.

        Returns:
            Tuple of symbol dictionaries or None.

        """

        async def _call() -> tuple[dict[str, JSONValue], ...] | None:
            stub = self._ensure_connected()
            request = mt5_pb2.SymbolsRequest()
            if group is not None:
                request.group = group
            response = await stub.SymbolsGet(request, timeout=self._timeout)
            return self._unwrap_symbols_chunks(response)

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
            result_dict = self._json_to_dict(response.json_data)
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
            result_dict = self._json_to_dict(response.json_data)
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
                date_from=self._to_timestamp(date_from),
                count=count,
            )
            response = await stub.CopyRatesFrom(request, timeout=self._timeout)
            return self._numpy_from_proto(response)

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
            return self._numpy_from_proto(response)

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
                date_from=self._to_timestamp(date_from),
                date_to=self._to_timestamp(date_to),
            )
            response = await stub.CopyRatesRange(request, timeout=self._timeout)
            return self._numpy_from_proto(response)

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
                date_from=self._to_timestamp(date_from),
                count=count,
                flags=flags,
            )
            response = await stub.CopyTicksFrom(request, timeout=self._timeout)
            return self._numpy_from_proto(response)

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
                date_from=self._to_timestamp(date_from),
                date_to=self._to_timestamp(date_to),
                flags=flags,
            )
            response = await stub.CopyTicksRange(request, timeout=self._timeout)
            return self._numpy_from_proto(response)

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
            result_dict = self._json_to_dict(response.json_data)
            return MT5Models.OrderCheckResult.from_mt5(result_dict)

        return await self._resilient_call("order_check", _call)

    async def order_send(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary.

        Returns:
            Order execution result object or None.

        """

        async def _call() -> MT5Models.OrderResult | None:
            stub = self._ensure_connected()
            grpc_request = mt5_pb2.OrderRequest(
                json_request=orjson.dumps(request).decode()
            )
            response = await stub.OrderSend(grpc_request, timeout=self._timeout)
            result_dict = self._json_to_dict(response.json_data)
            return MT5Models.OrderResult.from_mt5(result_dict)

        return await self._resilient_call("order_send", _call)

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
            dicts = self._json_list_to_dicts(list(response.json_items))
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
            dicts = self._json_list_to_dicts(list(response.json_items))
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
                date_from=self._to_timestamp(date_from),
                date_to=self._to_timestamp(date_to),
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
                request.date_from = self._to_timestamp(date_from)
            if date_to is not None:
                request.date_to = self._to_timestamp(date_to)
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            if position is not None:
                request.position = position
            response = await stub.HistoryOrdersGet(request, timeout=self._timeout)
            dicts = self._json_list_to_dicts(list(response.json_items))
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
                date_from=self._to_timestamp(date_from),
                date_to=self._to_timestamp(date_to),
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
                request.date_from = self._to_timestamp(date_from)
            if date_to is not None:
                request.date_to = self._to_timestamp(date_to)
            if group is not None:
                request.group = group
            if ticket is not None:
                request.ticket = ticket
            if position is not None:
                request.position = position
            response = await stub.HistoryDealsGet(request, timeout=self._timeout)
            dicts = self._json_list_to_dicts(list(response.json_items))
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
            dicts = self._json_list_to_dicts(list(response.json_items))
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
