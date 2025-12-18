"""MetaTrader5 synchronous gRPC client for mt5linux.

Native synchronous gRPC client using grpc.insecure_channel for blocking MT5 operations.
This is the primary client for synchronous Python applications.

Features:
- Synchronous API matching MetaTrader5 PyPI exactly
- Direct gRPC calls (no async wrapper)
- Context manager support (__enter__, __exit__)
- All MT5 operations blocking until completion
- Thread-safe channel management

Example:
    >>> from mt5linux import MetaTrader5
    >>> with MetaTrader5(host="localhost", port=50051) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

Thread Safety:
    The sync client uses a threading.Lock for connection operations.
    Multiple threads can safely share the same client instance.
    Each RPC call is independent and can run concurrently.

Compatible with grpcio 1.60+ and Python 3.13+.

"""

from __future__ import annotations

# pylint: disable=no-member  # Protobuf generated code has dynamic members
import ast
import logging
import threading
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Self

import grpc
import numpy as np
import orjson

if TYPE_CHECKING:
    from types import TracebackType

    from numpy.typing import NDArray


from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.models import MT5Models
from mt5linux.protocols import SyncClientProtocol
from mt5linux.types import MT5Types

log = logging.getLogger(__name__)

# Default config instance - Single Source of Truth
_config = MT5Config()

# Error message constant
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect() first"

# gRPC channel options from config (no more hardcoded values)
_CHANNEL_OPTIONS = _config.get_grpc_channel_options()

# Type alias for convenience (single source of truth)
JSONValue = MT5Types.JSONValue


class MetaTrader5(SyncClientProtocol):
    """Synchronous MetaTrader5 client using native gRPC.

    Uses grpc.insecure_channel for blocking gRPC calls.
    Implements SyncClientProtocol for type-safe client operations.
    All MT5 operations block until completion.

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants (via __getattr__)
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants

    All MetaTrader5 methods are available as synchronous versions.

    Example:
        >>> with MetaTrader5() as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)

    """

    def __init__(
        self,
        host: str = _config.host,
        port: int = _config.grpc_port,
        timeout: int = _config.timeout_connection,
    ) -> None:
        """Initialize sync MT5 client.

        Args:
            host: gRPC server address.
            port: gRPC server port.
            timeout: Timeout in seconds for MT5 operations.

        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._channel: grpc.Channel | None = None
        self._stub: mt5_pb2_grpc.MT5ServiceStub | None = None
        self._constants: dict[str, int] = {}
        self._connect_lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to gRPC server.

        Returns:
            True if connected, False otherwise.

        """
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

    def __enter__(self) -> Self:
        """Context manager entry - connects to gRPC server.

        Returns:
            Self for use in with statement.

        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - disconnects from gRPC server.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.

        """
        self.disconnect()

    def connect(self) -> None:
        """Connect to gRPC server.

        Thread-safe: uses threading.Lock to prevent race conditions.

        """
        with self._connect_lock:
            if self._channel is not None:
                return

            target = f"{self._host}:{self._port}"
            log.debug("Connecting to gRPC server at %s", target)

            self._channel = grpc.insecure_channel(target, options=_CHANNEL_OPTIONS)
            self._stub = mt5_pb2_grpc.MT5ServiceStub(self._channel)

            # Load constants from server
            self._load_constants()

            log.info("Connected to MT5 gRPC server at %s", target)

    def _load_constants(self) -> None:
        """Load MT5 constants from server."""
        if self._stub is None:
            return

        try:
            response = self._stub.GetConstants(mt5_pb2.Empty())
            self._constants = dict(response.values)
            log.debug("Loaded %d constants from server", len(self._constants))
        except grpc.RpcError as e:
            log.warning("Failed to load constants: %s", e)

    def disconnect(self) -> None:
        """Disconnect from gRPC server."""
        if self._channel is None:
            return

        channel = self._channel
        self._channel = None
        self._stub = None

        try:
            channel.close()
        except Exception:  # noqa: BLE001
            log.debug("Channel close failed during disconnect")

        log.debug("Disconnected from MT5 gRPC server")

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

    def initialize(  # noqa: PLR0913
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

        Auto-connects to gRPC server if not already connected.

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
            self.connect()
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

        response = stub.Initialize(request)
        return response.result

    def login(
        self,
        login: int,
        password: str,
        server: str,
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
        stub = self._ensure_connected()
        request = mt5_pb2.LoginRequest(
            login=login,
            password=password,
            server=server,
            timeout=timeout,
        )
        response = stub.Login(request)
        return response.result

    def shutdown(self) -> None:
        """Shutdown MT5 terminal connection.

        No-op if not connected (graceful degradation).

        """
        if self._stub is not None:
            with suppress(grpc.RpcError):
                self._stub.Shutdown(mt5_pb2.Empty())

    def health_check(self) -> dict[str, bool | int | str]:
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
        stub = self._ensure_connected()
        response = stub.HealthCheck(mt5_pb2.Empty())
        return {
            "healthy": response.healthy,
            "mt5_available": response.mt5_available,
            "connected": response.connected,
            "trade_allowed": response.trade_allowed,
            "build": response.build,
            "reason": response.reason,
        }

    def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (major, minor, build_string) or None.

        """
        stub = self._ensure_connected()
        response = stub.Version(mt5_pb2.Empty())
        if not response.build:
            return None
        return (response.major, response.minor, response.build)

    def last_error(self) -> tuple[int, str]:
        """Get last error code and description.

        Returns:
            Tuple of (error_code, error_message).

        """
        stub = self._ensure_connected()
        response = stub.LastError(mt5_pb2.Empty())
        return (response.code, response.message)

    def terminal_info(self) -> MT5Models.TerminalInfo | None:
        """Get terminal information.

        Returns:
            TerminalInfo object or None.

        """
        stub = self._ensure_connected()
        response = stub.TerminalInfo(mt5_pb2.Empty())
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.TerminalInfo.from_mt5(result_dict)

    def account_info(self) -> MT5Models.AccountInfo | None:
        """Get account information.

        Returns:
            AccountInfo object or None.

        """
        stub = self._ensure_connected()
        response = stub.AccountInfo(mt5_pb2.Empty())
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.AccountInfo.from_mt5(result_dict)

    # =========================================================================
    # SYMBOL METHODS
    # =========================================================================

    def symbols_total(self) -> int:
        """Get total number of available symbols.

        Returns:
            Total count of symbols.

        """
        stub = self._ensure_connected()
        response = stub.SymbolsTotal(mt5_pb2.Empty())
        return response.value

    def symbols_get(
        self, group: str | None = None
    ) -> tuple[dict[str, JSONValue], ...] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern.

        Returns:
            Tuple of symbol dictionaries or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolsRequest()
        if group is not None:
            request.group = group
        response = stub.SymbolsGet(request)
        return self._unwrap_symbols_chunks(response)

    def symbol_info(self, symbol: str) -> MT5Models.SymbolInfo | None:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            SymbolInfo object or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = stub.SymbolInfo(request)
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.SymbolInfo.from_mt5(result_dict)

    def symbol_info_tick(self, symbol: str) -> MT5Models.Tick | None:
        """Get current tick data for a symbol.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Tick object or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = stub.SymbolInfoTick(request)
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.Tick.from_mt5(result_dict)

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to add, False to remove from Market Watch.

        Returns:
            True if successful, False otherwise.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolSelectRequest(symbol=symbol, enable=enable)
        response = stub.SymbolSelect(request)
        return response.result

    # =========================================================================
    # MARKET DATA METHODS
    # =========================================================================

    def copy_rates_from(
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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesRequest(
            symbol=symbol,
            timeframe=timeframe,
            date_from=self._to_timestamp(date_from),
            count=count,
        )
        response = stub.CopyRatesFrom(request)
        return self._numpy_from_proto(response)

    def copy_rates_from_pos(
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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesPosRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_pos=start_pos,
            count=count,
        )
        response = stub.CopyRatesFromPos(request)
        return self._numpy_from_proto(response)

    def copy_rates_range(
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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesRangeRequest(
            symbol=symbol,
            timeframe=timeframe,
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = stub.CopyRatesRange(request)
        return self._numpy_from_proto(response)

    def copy_ticks_from(
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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyTicksRequest(
            symbol=symbol,
            date_from=self._to_timestamp(date_from),
            count=count,
            flags=flags,
        )
        response = stub.CopyTicksFrom(request)
        return self._numpy_from_proto(response)

    def copy_ticks_range(
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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyTicksRangeRequest(
            symbol=symbol,
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
            flags=flags,
        )
        response = stub.CopyTicksRange(request)
        return self._numpy_from_proto(response)

    # =========================================================================
    # TRADING METHODS
    # =========================================================================

    def order_calc_margin(
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
        stub = self._ensure_connected()
        request = mt5_pb2.MarginRequest(
            action=action,
            symbol=symbol,
            volume=volume,
            price=price,
        )
        response = stub.OrderCalcMargin(request)
        return response.value if response.HasField("value") else None

    def order_calc_profit(
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
        stub = self._ensure_connected()
        request = mt5_pb2.ProfitRequest(
            action=action,
            symbol=symbol,
            volume=volume,
            price_open=price_open,
            price_close=price_close,
        )
        response = stub.OrderCalcProfit(request)
        return response.value if response.HasField("value") else None

    def order_check(
        self, request: dict[str, JSONValue]
    ) -> MT5Models.OrderCheckResult | None:
        """Check order validity without sending.

        Args:
            request: Order request dictionary.

        Returns:
            Order check result object or None if error occurs.

        """
        stub = self._ensure_connected()
        grpc_request = mt5_pb2.OrderRequest(json_request=orjson.dumps(request).decode())
        try:
            response = stub.OrderCheck(grpc_request)
        except grpc.RpcError:
            # Server error (e.g., invalid symbol) - return None
            return None
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.OrderCheckResult.from_mt5(result_dict)

    def order_send(self, request: dict[str, JSONValue]) -> MT5Models.OrderResult | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary.

        Returns:
            Order execution result object or None.

        """
        stub = self._ensure_connected()
        grpc_request = mt5_pb2.OrderRequest(json_request=orjson.dumps(request).decode())
        response = stub.OrderSend(grpc_request)
        result_dict = self._json_to_dict(response.json_data)
        return MT5Models.OrderResult.from_mt5(result_dict)

    # =========================================================================
    # POSITIONS METHODS
    # =========================================================================

    def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Count of open positions.

        """
        stub = self._ensure_connected()
        response = stub.PositionsTotal(mt5_pb2.Empty())
        return response.value

    def positions_get(
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
        stub = self._ensure_connected()
        request = mt5_pb2.PositionsRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        response = stub.PositionsGet(request)
        dicts = self._json_list_to_dicts(list(response.json_items))
        if dicts is None:
            return None
        return tuple(MT5Models.Position.model_validate(d) for d in dicts)

    # =========================================================================
    # ORDERS METHODS
    # =========================================================================

    def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Count of pending orders.

        """
        stub = self._ensure_connected()
        response = stub.OrdersTotal(mt5_pb2.Empty())
        return response.value

    def orders_get(
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
        stub = self._ensure_connected()
        request = mt5_pb2.OrdersRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        response = stub.OrdersGet(request)
        dicts = self._json_list_to_dicts(list(response.json_items))
        if dicts is None:
            return None
        return tuple(MT5Models.Order.model_validate(d) for d in dicts)

    # =========================================================================
    # HISTORY METHODS
    # =========================================================================

    def history_orders_total(
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
        stub = self._ensure_connected()
        request = mt5_pb2.HistoryRequest(
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = stub.HistoryOrdersTotal(request)
        return response.value

    def history_orders_get(
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
        response = stub.HistoryOrdersGet(request)
        dicts = self._json_list_to_dicts(list(response.json_items))
        if dicts is None:
            return None
        return tuple(MT5Models.Order.model_validate(d) for d in dicts)

    def history_deals_total(
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
        stub = self._ensure_connected()
        request = mt5_pb2.HistoryRequest(
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = stub.HistoryDealsTotal(request)
        return response.value

    def history_deals_get(
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
        response = stub.HistoryDealsGet(request)
        dicts = self._json_list_to_dicts(list(response.json_items))
        if dicts is None:
            return None
        return tuple(MT5Models.Deal.model_validate(d) for d in dicts)

    # =========================================================================
    # MARKET DEPTH METHODS
    # =========================================================================

    def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market depth (DOM) for a symbol.

        Must be called before market_book_get to receive updates.

        Args:
            symbol: Symbol name to subscribe to.

        Returns:
            True if subscription successful, False otherwise.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = stub.MarketBookAdd(request)
        return response.result

    def market_book_get(self, symbol: str) -> tuple[MT5Models.BookEntry, ...] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior market_book_add call.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            Tuple of BookEntry objects or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = stub.MarketBookGet(request)
        dicts = self._json_list_to_dicts(list(response.json_items))
        if dicts is None:
            return None
        return tuple(MT5Models.BookEntry.model_validate(d) for d in dicts)

    def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = stub.MarketBookRelease(request)
        return response.result
