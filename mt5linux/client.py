"""MetaTrader5 gRPC client - production-grade with resilience.

Modern gRPC client for connecting to MT5Service:
- Uses grpc.insecure_channel() for sync operations
- Uses generated MT5ServiceStub from mt5_pb2_grpc
- Production-grade error handling with retry and circuit breaker
- numpy array reconstruction from NumpyArray protobuf messages
- JSON deserialization for DictData messages

Resilience features:
- Automatic retry with exponential backoff on transient failures
- Circuit breaker to prevent cascading failures
- Connection health monitoring with auto-reconnect
- Per-operation timeouts

Hierarchy Level: 3
- Imports: MT5Config, MT5Types, MT5Utilities, MT5Models
- Top-level client module

Compatible with grpcio 1.60+ and Python 3.13+.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self

import grpc
import numpy as np

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.models import MT5Models
from mt5linux.utilities import MT5Utilities

if TYPE_CHECKING:
    from types import TracebackType

    from mt5linux.constants import MT5Constants
    from mt5linux.types import MT5Types

log = logging.getLogger(__name__)

# Default config instance
_config = MT5Config()

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"

# Type alias for JSON values (no Any)
JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]

# gRPC channel options for performance and reliability
_CHANNEL_OPTIONS: list[tuple[str, int]] = [
    ("grpc.max_send_message_length", 50 * 1024 * 1024),
    ("grpc.max_receive_message_length", 50 * 1024 * 1024),
    ("grpc.keepalive_time_ms", 30000),
    ("grpc.keepalive_timeout_ms", 10000),
]


# =============================================================================
# Retryable Exceptions (module level for sharing)
# =============================================================================

RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    grpc.RpcError,
    ConnectionError,
    TimeoutError,
    OSError,
)


# =============================================================================
# MetaTrader5 Client with gRPC
# =============================================================================


class MetaTrader5:
    """Modern gRPC client for MetaTrader5.

    Connects to MT5Service via gRPC channel.
    Delegates MT5 operations to generated stub methods.

    Attributes:
        _channel: gRPC channel for communication.
        _stub: Generated MT5ServiceStub for RPC calls.
        _constants: Cached MT5 constants from server.

    Example:
        >>> with MetaTrader5(host="localhost", port=50051) as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     print(account.balance)

    """

    # =========================================================================
    # INSTANCE ATTRIBUTES
    # =========================================================================

    _channel: grpc.Channel | None
    _stub: mt5_pb2_grpc.MT5ServiceStub | None
    _constants: dict[str, int]

    def __init__(  # noqa: PLR0913
        self,
        host: str = _config.host,
        port: int = _config.bridge_port,
        timeout: int = _config.timeout_connection,
        *,
        config: MT5Config | None = None,
        health_check_interval: int | None = None,
        max_reconnect_attempts: int | None = None,
        use_tls: bool = False,
    ) -> None:
        """Initialize gRPC client and connect to MT5 server.

        Args:
            host: gRPC server address (default: localhost).
            port: gRPC server port (default: 8001 from config.bridge_port).
            timeout: Timeout in seconds for operations.
            config: MT5Config instance for all configuration (uses defaults).
            health_check_interval: Seconds between health checks (config override).
            max_reconnect_attempts: Max reconnection attempts (config override).
            use_tls: Whether to use TLS for secure channel (default: False).

        Raises:
            ConnectionError: If initial connection fails.

        """
        self._config = config or _config
        self._host = host
        self._port = port
        self._timeout = timeout
        self._use_tls = use_tls
        self._channel = None
        self._stub = None
        self._constants: dict[str, int] = {}

        # Resilience configuration (uses MT5Config directly)
        self._circuit_breaker = MT5Utilities.CircuitBreaker(
            config=self._config,
            name=f"mt5-{host}:{port}",
        )
        self._health_check_interval = (
            health_check_interval or self._config.timeout_health_check
        )
        self._last_health_check: datetime | None = None
        self._max_reconnect_attempts = (
            max_reconnect_attempts or self._config.retry_max_attempts
        )

        self._connect()

    def _connect(self) -> None:
        """Establish gRPC connection to server.

        Creates either secure or insecure channel based on use_tls flag.
        Initializes stub and loads MT5 constants from server.

        Raises:
            ConnectionError: If connection or constants loading fails.

        """
        if self._channel is not None:
            return

        target = f"{self._host}:{self._port}"
        log.debug("Connecting to gRPC server at %s", target)

        if self._use_tls:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.secure_channel(
                target, credentials, options=_CHANNEL_OPTIONS
            )
        else:
            self._channel = grpc.insecure_channel(target, options=_CHANNEL_OPTIONS)

        self._stub = mt5_pb2_grpc.MT5ServiceStub(self._channel)

        # Load constants from server
        try:
            response = self._stub.GetConstants(
                mt5_pb2.Empty(),
                timeout=self._timeout,
            )
            self._constants = dict(response.values)
            log.info(
                "Connected to MT5 gRPC server at %s, loaded %d constants",
                target,
                len(self._constants),
            )
        except grpc.RpcError as e:
            self._close()
            msg = f"Failed to load MT5 constants: {e}"
            raise ConnectionError(msg) from e

    def __getattr__(self, name: str) -> int:
        """Transparent proxy for MT5 constants (ORDER_TYPE_*, TIMEFRAME_*, etc).

        Args:
            name: Attribute name to look up.

        Returns:
            Integer constant value.

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

    def __enter__(self) -> Self:
        """Context manager entry.

        Returns:
            Self for use in with statement.

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - cleanup.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.

        """
        try:
            self.shutdown()
        except (grpc.RpcError, ConnectionError, OSError):
            log.debug("MT5 shutdown failed during cleanup (may be closed)")
        self._close()

    def _close(self) -> None:
        """Close gRPC channel and reset state."""
        if self._channel is not None:
            try:
                self._channel.close()
            except (OSError, grpc.RpcError):
                log.debug("gRPC channel close failed (may already be closed)")
            self._channel = None
            self._stub = None
            self._constants = {}
            log.debug("gRPC channel closed")

    def close(self) -> None:
        """Close the connection (public API).

        Shuts down MT5 terminal and closes gRPC channel.
        Safe to call multiple times.

        """
        self._close()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_dict_data(
        self, response: mt5_pb2.DictData
    ) -> dict[str, JSONValue] | None:
        """Parse DictData protobuf message to Python dict.

        Args:
            response: DictData message with json_data field.

        Returns:
            Parsed dictionary or None if empty.

        """
        if not response.json_data:
            return None
        data: dict[str, JSONValue] = json.loads(response.json_data)
        return data

    def _parse_dict_list(
        self, response: mt5_pb2.DictList
    ) -> list[dict[str, JSONValue]]:
        """Parse DictList protobuf message to list of dicts.

        Args:
            response: DictList message with json_items field.

        Returns:
            List of parsed dictionaries.

        """
        result: list[dict[str, JSONValue]] = []
        for json_str in response.json_items:
            item: dict[str, JSONValue] = json.loads(json_str)
            result.append(item)
        return result

    def _parse_numpy_array(
        self, response: mt5_pb2.NumpyArray
    ) -> MT5Types.RatesArray | None:
        """Reconstruct numpy array from NumpyArray protobuf message.

        Args:
            response: NumpyArray message with data, dtype, and shape.

        Returns:
            Reconstructed numpy array or None if empty.

        """
        if not response.data:
            return None
        arr: MT5Types.RatesArray = np.frombuffer(
            response.data, dtype=np.dtype(response.dtype)
        )
        if response.shape:
            shape = tuple(response.shape)
            arr = arr.reshape(shape)
        return arr

    def _parse_symbols_response(
        self, response: mt5_pb2.SymbolsResponse
    ) -> list[dict[str, JSONValue]]:
        """Parse SymbolsResponse protobuf message to list of dicts.

        Args:
            response: SymbolsResponse message with chunks field.

        Returns:
            List of parsed symbol dictionaries.

        """
        result: list[dict[str, JSONValue]] = []
        for chunk_json in response.chunks:
            chunk: list[dict[str, JSONValue]] = json.loads(chunk_json)
            result.extend(chunk)
        return result

    def _to_timestamp(self, dt: datetime | int | None) -> int | None:
        """Convert datetime to Unix timestamp for MT5 API.

        Args:
            dt: Datetime or Unix timestamp or None.

        Returns:
            Unix timestamp as int or None.

        """
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return int(dt.timestamp())
        return dt

    # =========================================================================
    # Resilience Methods
    # =========================================================================

    def _reconnect(self) -> None:
        """Reconnect to gRPC server with retry logic.

        Attempts reconnection up to max_reconnect_attempts times
        with exponential backoff between attempts.

        Raises:
            ConnectionError: If all reconnection attempts fail.

        """
        log.info("Attempting reconnection to %s:%d", self._host, self._port)
        self._close()

        last_error: Exception | None = None
        for attempt in range(self._max_reconnect_attempts):
            try:
                self._connect()
            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self._max_reconnect_attempts - 1:
                    delay = self._config.calculate_retry_delay(attempt)
                    log.warning(
                        "Reconnection attempt %d failed: %s, retrying in %.2fs",
                        attempt + 1,
                        e,
                        delay,
                    )
                    time.sleep(delay)
            else:
                log.info("Reconnection successful on attempt %d", attempt + 1)
                return

        msg = f"Reconnection failed after {self._max_reconnect_attempts} attempts"
        log.error(msg)
        if last_error:
            raise ConnectionError(msg) from last_error
        raise ConnectionError(msg)

    def _check_connection_health(self) -> bool:
        """Verify connection is alive with lightweight ping.

        Returns:
            True if connection is healthy, False otherwise.

        """
        if self._channel is None or self._stub is None:
            return False
        try:
            # Use HealthCheck RPC as a ping
            self._stub.HealthCheck(mt5_pb2.Empty(), timeout=5)
        except grpc.RpcError:
            return False
        else:
            return True

    def _ensure_healthy_connection(self) -> None:
        """Ensure connection is healthy, reconnect if needed.

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open.
            ConnectionError: If reconnection fails.

        """
        if not self._circuit_breaker.can_execute():
            raise MT5Utilities.Exceptions.CircuitBreakerOpenError

        now = datetime.now(UTC)
        if (
            self._last_health_check
            and (now - self._last_health_check).total_seconds()
            < self._health_check_interval
        ):
            return

        if not self._check_connection_health():
            log.warning("Connection unhealthy, attempting reconnect")
            try:
                self._reconnect()
            except Exception:
                self._circuit_breaker.record_failure()
                raise

        self._last_health_check = now

    def _ensure_connected(self) -> mt5_pb2_grpc.MT5ServiceStub:
        """Ensure client is connected and return stub.

        Returns:
            The gRPC stub for making calls.

        Raises:
            ConnectionError: If not connected.

        """
        if self._stub is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._stub

    def _safe_rpc_call[T](
        self,
        method_name: str,
        request: object,
    ) -> T:
        """Execute RPC call with full error handling and automatic retry.

        Args:
            method_name: Name of the stub method to call.
            request: Protobuf request message.

        Returns:
            Response from the RPC call.

        Raises:
            ConnectionError: If not connected.
            MaxRetriesError: If all retry attempts fail.

        """
        self._ensure_healthy_connection()

        stub = self._ensure_connected()
        last_exception: Exception | None = None
        max_attempts = self._config.retry_max_attempts
        method = getattr(stub, method_name)

        retryable_codes = (
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
        )

        for attempt in range(max_attempts):
            try:
                result: T = method(request, timeout=self._timeout)
                # Success
                self._circuit_breaker.record_success()
                if attempt > 0:
                    log.info("%s succeeded on attempt %d", method_name, attempt + 1)
            except grpc.RpcError as e:
                last_exception = e
                self._circuit_breaker.record_failure()

                # Check if retryable and we have retries left
                code = e.code() if hasattr(e, "code") else None
                can_retry = code in retryable_codes and attempt < max_attempts - 1
                if can_retry:
                    delay = self._config.calculate_retry_delay(attempt)
                    log.warning(
                        "%s failed (attempt %d/%d): %s, retrying in %.2fs",
                        method_name,
                        attempt + 1,
                        max_attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                # Non-retryable or exhausted retries
                log.exception("%s failed after %d attempts", method_name, attempt + 1)
                raise
            else:
                return result

        if last_exception:
            raise MT5Utilities.Exceptions.MaxRetriesError(
                operation=method_name,
                attempts=max_attempts,
                last_error=last_exception,
            ) from last_exception

        msg = f"{method_name} failed without exception"
        raise RuntimeError(msg)

    # =========================================================================
    # Terminal operations
    # =========================================================================

    def initialize(  # noqa: PLR0913
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        *,
        portable: bool = False,
    ) -> bool:
        """Initialize MT5 terminal.

        Args:
            path: Path to MT5 terminal executable.
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Connection timeout in milliseconds.
            portable: Use portable mode flag.

        Returns:
            True if initialization successful, False otherwise.

        """
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

        response: mt5_pb2.BoolResponse = self._safe_rpc_call("Initialize", request)
        return response.result

    def login(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 60000,
    ) -> bool:
        """Login to trading account.

        Args:
            login: Trading account number.
            password: Account password.
            server: Trade server name.
            timeout: Login timeout in milliseconds.

        Returns:
            True if login successful, False otherwise.

        """
        request = mt5_pb2.LoginRequest(
            login=login,
            password=password,
            server=server,
            timeout=timeout,
        )
        response: mt5_pb2.BoolResponse = self._safe_rpc_call("Login", request)
        return response.result

    def shutdown(self) -> None:
        """Shutdown MT5 terminal.

        Safe to call even if not connected.

        """
        if self._stub is None:
            return
        try:
            self._stub.Shutdown(mt5_pb2.Empty(), timeout=self._timeout)
        except grpc.RpcError:
            log.debug("Shutdown RPC failed (connection may be closed)")

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (major, minor, build_string) or None if unavailable.

        """
        response: mt5_pb2.MT5Version = self._safe_rpc_call("Version", mt5_pb2.Empty())
        if not response.build:
            return None
        return (response.major, response.minor, response.build)

    def last_error(self) -> tuple[int, str]:
        """Get last MT5 error.

        Returns:
            Tuple of (error_code, error_description).

        """
        response: mt5_pb2.ErrorInfo = self._safe_rpc_call("LastError", mt5_pb2.Empty())
        return (response.code, response.message)

    def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal info.

        Returns:
            TerminalInfo model or None if unavailable.

        """
        response: mt5_pb2.DictData = self._safe_rpc_call(
            "TerminalInfo", mt5_pb2.Empty()
        )
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.TerminalInfo.from_mt5(wrapped)

    def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account info.

        Returns:
            AccountInfo model or None if unavailable.

        """
        response: mt5_pb2.DictData = self._safe_rpc_call("AccountInfo", mt5_pb2.Empty())
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.AccountInfo.from_mt5(wrapped)

    # =========================================================================
    # Symbol operations
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of symbols.

        Returns:
            Total count of available symbols.

        """
        response: mt5_pb2.IntResponse = self._safe_rpc_call(
            "SymbolsTotal", mt5_pb2.Empty()
        )
        return response.value

    def symbols_get(
        self, group: str | None = None
    ) -> tuple[MT5Models.SymbolInfo, ...] | None:
        """Get available symbols.

        Args:
            group: Optional group filter pattern (e.g., "*USD*").

        Returns:
            Tuple of SymbolInfo models or None if none found.

        """
        request = mt5_pb2.SymbolsRequest()
        if group is not None:
            request.group = group

        response: mt5_pb2.SymbolsResponse = self._safe_rpc_call("SymbolsGet", request)
        items = self._parse_symbols_response(response)
        if not items:
            return None
        symbols = [
            MT5Models.SymbolInfo.from_mt5(MT5Utilities.Data.wrap(s)) for s in items
        ]
        return tuple(s for s in symbols if s is not None)

    def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get symbol info.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            SymbolInfo model or None if not found.

        """
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response: mt5_pb2.DictData = self._safe_rpc_call("SymbolInfo", request)
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.SymbolInfo.from_mt5(wrapped)

    def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get symbol tick info.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Tick model or None if not available.

        """
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response: mt5_pb2.DictData = self._safe_rpc_call("SymbolInfoTick", request)
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.Tick.from_mt5(wrapped)

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select symbol in Market Watch.

        Args:
            symbol: Symbol name to select.
            enable: True to add to Market Watch, False to remove.

        Returns:
            True if successful, False otherwise.

        """
        request = mt5_pb2.SymbolSelectRequest(symbol=symbol, enable=enable)
        response: mt5_pb2.BoolResponse = self._safe_rpc_call("SymbolSelect", request)
        return response.result

    # =========================================================================
    # Market data operations - numpy array reconstruction
    # =========================================================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        date_from: datetime | int,
        count: int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates from a date.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (e.g., MT5Constants.TimeFrame.H1).
            date_from: Start date as datetime or Unix timestamp.
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        ts = self._to_timestamp(date_from)
        request = mt5_pb2.CopyRatesRequest(
            symbol=symbol,
            timeframe=int(timeframe),
            date_from=ts if ts is not None else 0,
            count=count,
        )
        response: mt5_pb2.NumpyArray = self._safe_rpc_call("CopyRatesFrom", request)
        return self._parse_numpy_array(response)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        start_pos: int,
        count: int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates from a position.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            start_pos: Start position (0 = current bar).
            count: Number of bars to copy.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        request = mt5_pb2.CopyRatesPosRequest(
            symbol=symbol,
            timeframe=int(timeframe),
            start_pos=start_pos,
            count=count,
        )
        response: mt5_pb2.NumpyArray = self._safe_rpc_call("CopyRatesFromPos", request)
        return self._parse_numpy_array(response)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: MT5Constants.TimeFrame | int,
        date_from: datetime | int,
        date_to: datetime | int,
    ) -> MT5Types.RatesArray | None:
        """Copy rates in a date range.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.

        Returns:
            NumPy structured array with OHLCV data or None.

        """
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        request = mt5_pb2.CopyRatesRangeRequest(
            symbol=symbol,
            timeframe=int(timeframe),
            date_from=ts_from if ts_from is not None else 0,
            date_to=ts_to if ts_to is not None else 0,
        )
        response: mt5_pb2.NumpyArray = self._safe_rpc_call("CopyRatesRange", request)
        return self._parse_numpy_array(response)

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime | int,
        count: int,
        flags: MT5Constants.CopyTicksFlag | int,
    ) -> MT5Types.TicksArray | None:
        """Copy ticks from a date.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            count: Number of ticks to copy.
            flags: Copy ticks flags (e.g., MT5Constants.CopyTicksFlag.ALL).

        Returns:
            NumPy structured array with tick data or None.

        """
        ts = self._to_timestamp(date_from)
        request = mt5_pb2.CopyTicksRequest(
            symbol=symbol,
            date_from=ts if ts is not None else 0,
            count=count,
            flags=int(flags),
        )
        response: mt5_pb2.NumpyArray = self._safe_rpc_call("CopyTicksFrom", request)
        return self._parse_numpy_array(response)

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime | int,
        date_to: datetime | int,
        flags: MT5Constants.CopyTicksFlag | int,
    ) -> MT5Types.TicksArray | None:
        """Copy ticks in a date range.

        Args:
            symbol: Symbol name.
            date_from: Start date as datetime or Unix timestamp.
            date_to: End date as datetime or Unix timestamp.
            flags: Copy ticks flags.

        Returns:
            NumPy structured array with tick data or None.

        """
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        request = mt5_pb2.CopyTicksRangeRequest(
            symbol=symbol,
            date_from=ts_from if ts_from is not None else 0,
            date_to=ts_to if ts_to is not None else 0,
            flags=int(flags),
        )
        response: mt5_pb2.NumpyArray = self._safe_rpc_call("CopyTicksRange", request)
        return self._parse_numpy_array(response)

    # =========================================================================
    # Trading operations
    # =========================================================================

    def order_calc_margin(
        self,
        action: MT5Constants.TradeAction | int,
        symbol: str,
        volume: float,
        price: float,
    ) -> float | None:
        """Calculate margin for order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price: Order price.

        Returns:
            Required margin or None if calculation fails.

        """
        request = mt5_pb2.MarginRequest(
            action=int(action),
            symbol=symbol,
            volume=volume,
            price=price,
        )
        response: mt5_pb2.FloatResponse = self._safe_rpc_call(
            "OrderCalcMargin", request
        )
        if not response.HasField("value"):
            return None
        return response.value

    def order_calc_profit(
        self,
        action: MT5Constants.TradeAction | int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        """Calculate profit for order.

        Args:
            action: Trade action type.
            symbol: Symbol name.
            volume: Order volume in lots.
            price_open: Open price.
            price_close: Close price.

        Returns:
            Calculated profit or None if calculation fails.

        """
        request = mt5_pb2.ProfitRequest(
            action=int(action),
            symbol=symbol,
            volume=volume,
            price_open=price_open,
            price_close=price_close,
        )
        response: mt5_pb2.FloatResponse = self._safe_rpc_call(
            "OrderCalcProfit", request
        )
        if not response.HasField("value"):
            return None
        return response.value

    def order_check(
        self, request: MT5Types.OrderRequestDict | dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Check order parameters without sending.

        Args:
            request: Order request dictionary with action, symbol, volume, etc.

        Returns:
            OrderResult model with check results or None.

        """
        json_request = json.dumps(request)
        grpc_request = mt5_pb2.OrderRequest(json_request=json_request)
        response: mt5_pb2.DictData = self._safe_rpc_call("OrderCheck", grpc_request)
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.OrderResult.from_mt5(wrapped)

    def order_send(
        self, request: MT5Types.OrderRequestDict | dict[str, JSONValue]
    ) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary with action, symbol, volume, etc.

        Returns:
            OrderResult model with execution results or None.

        """
        json_request = json.dumps(request)
        grpc_request = mt5_pb2.OrderRequest(json_request=json_request)
        response: mt5_pb2.DictData = self._safe_rpc_call("OrderSend", grpc_request)
        data = self._parse_dict_data(response)
        if data is None:
            return None
        wrapped = MT5Utilities.Data.wrap(data)
        return MT5Models.OrderResult.from_mt5(wrapped)

    # =========================================================================
    # Position operations
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Count of open positions.

        """
        response: mt5_pb2.IntResponse = self._safe_rpc_call(
            "PositionsTotal", mt5_pb2.Empty()
        )
        return response.value

    def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Position, ...] | None:
        """Get open positions.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter (e.g., "*USD*").
            ticket: Specific position ticket to retrieve.

        Returns:
            Tuple of Position models or None if no positions found.

        """
        request = mt5_pb2.PositionsRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket

        response: mt5_pb2.DictList = self._safe_rpc_call("PositionsGet", request)
        items = self._parse_dict_list(response)
        if not items:
            return None
        positions = [
            MT5Models.Position.from_mt5(MT5Utilities.Data.wrap(p)) for p in items
        ]
        return tuple(p for p in positions if p is not None)

    # =========================================================================
    # Order operations
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Count of pending orders.

        """
        response: mt5_pb2.IntResponse = self._safe_rpc_call(
            "OrdersTotal", mt5_pb2.Empty()
        )
        return response.value

    def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get pending orders.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific order ticket to retrieve.

        Returns:
            Tuple of Order models or None if no orders found.

        """
        request = mt5_pb2.OrdersRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket

        response: mt5_pb2.DictList = self._safe_rpc_call("OrdersGet", request)
        items = self._parse_dict_list(response)
        if not items:
            return None
        orders = [MT5Models.Order.from_mt5(MT5Utilities.Data.wrap(o)) for o in items]
        return tuple(o for o in orders if o is not None)

    # =========================================================================
    # History operations
    # =========================================================================

    def history_orders_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical orders.

        Args:
            date_from: Start date for history query.
            date_to: End date for history query.

        Returns:
            Count of historical orders or None.

        """
        request = mt5_pb2.HistoryRequest()
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        if ts_from is not None:
            request.date_from = ts_from
        if ts_to is not None:
            request.date_to = ts_to

        response: mt5_pb2.IntResponse = self._safe_rpc_call(
            "HistoryOrdersTotal", request
        )
        return response.value

    def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Order, ...] | None:
        """Get historical orders.

        Args:
            date_from: Start date for history query (datetime or Unix timestamp).
            date_to: End date for history query (datetime or Unix timestamp).
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific order ticket to retrieve.
            position: Position ID to filter orders by.

        Returns:
            Tuple of Order models or None if no orders found.

        """
        request = mt5_pb2.HistoryRequest()
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        if ts_from is not None:
            request.date_from = ts_from
        if ts_to is not None:
            request.date_to = ts_to
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        if position is not None:
            request.position = position

        response: mt5_pb2.DictList = self._safe_rpc_call("HistoryOrdersGet", request)
        items = self._parse_dict_list(response)
        if not items:
            return None
        orders = [MT5Models.Order.from_mt5(MT5Utilities.Data.wrap(o)) for o in items]
        return tuple(o for o in orders if o is not None)

    def history_deals_total(
        self, date_from: datetime | int, date_to: datetime | int
    ) -> int | None:
        """Get total number of historical deals.

        Args:
            date_from: Start date for history query.
            date_to: End date for history query.

        Returns:
            Count of historical deals or None.

        """
        request = mt5_pb2.HistoryRequest()
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        if ts_from is not None:
            request.date_from = ts_from
        if ts_to is not None:
            request.date_to = ts_to

        response: mt5_pb2.IntResponse = self._safe_rpc_call(
            "HistoryDealsTotal", request
        )
        return response.value

    def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> tuple[MT5Models.Deal, ...] | None:
        """Get historical deals.

        Args:
            date_from: Start date for history query (datetime or Unix timestamp).
            date_to: End date for history query (datetime or Unix timestamp).
            group: Symbol group filter (e.g., "*USD*" for all USD pairs).
            ticket: Specific deal ticket to retrieve.
            position: Position ID to filter deals by.

        Returns:
            Tuple of Deal models or None if no deals found.

        """
        request = mt5_pb2.HistoryRequest()
        ts_from = self._to_timestamp(date_from)
        ts_to = self._to_timestamp(date_to)
        if ts_from is not None:
            request.date_from = ts_from
        if ts_to is not None:
            request.date_to = ts_to
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        if position is not None:
            request.position = position

        response: mt5_pb2.DictList = self._safe_rpc_call("HistoryDealsGet", request)
        items = self._parse_dict_list(response)
        if not items:
            return None
        deals = [MT5Models.Deal.from_mt5(MT5Utilities.Data.wrap(d)) for d in items]
        return tuple(d for d in deals if d is not None)

    # =========================================================================
    # Market Depth (DOM) operations
    # =========================================================================

    def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) updates for a symbol.

        Must be called before market_book_get() to start receiving updates.

        Args:
            symbol: Symbol name to subscribe to.

        Returns:
            True if subscription successful, False otherwise.

        """
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response: mt5_pb2.BoolResponse = self._safe_rpc_call("MarketBookAdd", request)
        return response.result

    def market_book_get(self, symbol: str) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior call to market_book_add() for the symbol.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            Tuple of BookEntry models representing the order book,
            or None if no data available.

        """
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response: mt5_pb2.DictList = self._safe_rpc_call("MarketBookGet", request)
        items = self._parse_dict_list(response)
        if not items:
            return None
        entries = [
            MT5Models.BookEntry.from_mt5(MT5Utilities.Data.wrap(e)) for e in items
        ]
        return tuple(e for e in entries if e is not None)

    def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) updates for a symbol.

        Should be called when market depth data is no longer needed.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.

        """
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response: mt5_pb2.BoolResponse = self._safe_rpc_call(
            "MarketBookRelease", request
        )
        return response.result

    # =========================================================================
    # Health check operations
    # =========================================================================

    def health_check(self) -> dict[str, JSONValue]:
        """Check connection and service health status.

        Returns:
            Dictionary with health status information including:
            - healthy: Whether service is healthy
            - mt5_available: Whether MT5 module is available
            - connected: Whether MT5 terminal is connected
            - trade_allowed: Whether trading is allowed
            - build: MT5 build number
            - reason: Status reason message

        """
        response: mt5_pb2.HealthStatus = self._safe_rpc_call(
            "HealthCheck", mt5_pb2.Empty()
        )
        result: dict[str, JSONValue] = {
            "healthy": response.healthy,
            "mt5_available": response.mt5_available,
            "connected": response.connected,
            "trade_allowed": response.trade_allowed,
            "build": response.build,
            "reason": response.reason,
        }
        return result
