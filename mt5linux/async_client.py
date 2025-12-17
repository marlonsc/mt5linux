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

Compatible with grpcio 1.60+ and Python 3.13+.

"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Self

import grpc
import grpc.aio
import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config

log = logging.getLogger(__name__)


# Default config instance - Single Source of Truth
_config = MT5Config()

# Error message constant
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect() first"

# gRPC channel options from config (no more hardcoded values)
_CHANNEL_OPTIONS = _config.get_grpc_channel_options()

# Type alias for JSON values (strict typing, no Any)
JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


class AsyncMetaTrader5:
    """Async wrapper for MetaTrader5 client using native gRPC async.

    Uses grpc.aio.insecure_channel for true async operations.
    All MT5 operations are executed via native gRPC async stubs.

    Attributes:
        TIMEFRAME_M1, TIMEFRAME_H1, etc.: MT5 timeframe constants (via __getattr__)
        ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.: MT5 order type constants

    All MetaTrader5 methods are available as async versions.

    """

    _lock = asyncio.Lock()

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

            self._channel = grpc.aio.insecure_channel(
                target, options=_CHANNEL_OPTIONS
            )
            self._stub = mt5_pb2_grpc.MT5ServiceStub(self._channel)

            # Load constants from server
            await self._load_constants()

            log.info("Connected to MT5 gRPC server at %s", target)

    async def _load_constants(self) -> None:
        """Load MT5 constants from server."""
        if self._stub is None:
            return

        try:
            response = await self._stub.GetConstants(mt5_pb2.Empty())
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
            await channel.close()
        except Exception:  # noqa: BLE001
            log.debug("Channel close failed during disconnect")

        log.debug("Disconnected from MT5 gRPC server")

    def _ensure_connected(self) -> mt5_pb2_grpc.MT5ServiceStub:
        """Ensure client is connected and return stub."""
        if self._stub is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)
        return self._stub

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
        result: dict[str, JSONValue] = json.loads(json_data)
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
            json.loads(item) for item in json_items if item
        ]
        return result

    def _numpy_from_proto(
        self, proto: mt5_pb2.NumpyArray
    ) -> NDArray[np.void] | None:
        """Convert NumpyArray proto to numpy array.

        Args:
            proto: NumpyArray protobuf message.

        Returns:
            Numpy structured array or None if empty.

        """
        if not proto.data or not proto.dtype:
            return None
        arr = np.frombuffer(proto.data, dtype=proto.dtype)
        if proto.shape:
            arr = arr.reshape(tuple(proto.shape))
        return arr

    def _unwrap_symbols_chunks(
        self, response: mt5_pb2.SymbolsResponse
    ) -> list[dict[str, JSONValue]] | None:
        """Unwrap chunked symbols response.

        Args:
            response: SymbolsResponse with chunked JSON data.

        Returns:
            List of symbol dictionaries or None if empty.

        """
        if response.total == 0:
            return None
        result: list[dict[str, JSONValue]] = []
        for chunk in response.chunks:
            chunk_data: list[dict[str, JSONValue]] = json.loads(chunk)
            result.extend(chunk_data)
        return result

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

    async def initialize(  # noqa: PLR0913
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

        response = await stub.Initialize(request)
        return response.result

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
        stub = self._ensure_connected()
        request = mt5_pb2.LoginRequest(
            login=login,
            password=password,
            server=server,
            timeout=login_timeout,
        )
        response = await stub.Login(request)
        return response.result

    async def shutdown(self) -> None:
        """Shutdown MT5 terminal connection.

        No-op if not connected (graceful degradation).
        """
        if self._stub is not None:
            with suppress(grpc.aio.AioRpcError):
                await self._stub.Shutdown(mt5_pb2.Empty())

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
        stub = self._ensure_connected()
        response = await stub.HealthCheck(mt5_pb2.Empty())
        return {
            "healthy": response.healthy,
            "mt5_available": response.mt5_available,
            "connected": response.connected,
            "trade_allowed": response.trade_allowed,
            "build": response.build,
            "reason": response.reason,
        }

    async def version(self) -> tuple[int, int, str] | None:
        """Get MT5 terminal version.

        Returns:
            Tuple of (major, minor, build_string) or None.

        """
        stub = self._ensure_connected()
        response = await stub.Version(mt5_pb2.Empty())
        if not response.build:
            return None
        return (response.major, response.minor, response.build)

    async def last_error(self) -> tuple[int, str]:
        """Get last error code and description.

        Returns:
            Tuple of (error_code, error_message).

        """
        stub = self._ensure_connected()
        response = await stub.LastError(mt5_pb2.Empty())
        return (response.code, response.message)

    async def terminal_info(self) -> dict[str, JSONValue] | None:
        """Get terminal information.

        Returns:
            Dictionary with terminal info or None.

        """
        stub = self._ensure_connected()
        response = await stub.TerminalInfo(mt5_pb2.Empty())
        return self._json_to_dict(response.json_data)

    async def account_info(self) -> dict[str, JSONValue] | None:
        """Get account information.

        Returns:
            Dictionary with account info or None.

        """
        stub = self._ensure_connected()
        response = await stub.AccountInfo(mt5_pb2.Empty())
        return self._json_to_dict(response.json_data)

    # =========================================================================
    # SYMBOL METHODS
    # =========================================================================

    async def symbols_total(self) -> int:
        """Get total number of available symbols.

        Returns:
            Total count of symbols.

        """
        stub = self._ensure_connected()
        response = await stub.SymbolsTotal(mt5_pb2.Empty())
        return response.value

    async def symbols_get(
        self, group: str | None = None
    ) -> list[dict[str, JSONValue]] | None:
        """Get available symbols with optional group filter.

        Args:
            group: Optional group filter pattern.

        Returns:
            List of symbol dictionaries or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolsRequest()
        if group is not None:
            request.group = group
        response = await stub.SymbolsGet(request)
        return self._unwrap_symbols_chunks(response)

    async def symbol_info(self, symbol: str) -> dict[str, JSONValue] | None:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Dictionary with symbol info or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = await stub.SymbolInfo(request)
        return self._json_to_dict(response.json_data)

    async def symbol_info_tick(
        self, symbol: str
    ) -> dict[str, JSONValue] | None:
        """Get current tick data for a symbol.

        Args:
            symbol: Symbol name (e.g., "EURUSD").

        Returns:
            Dictionary with tick info or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = await stub.SymbolInfoTick(request)
        return self._json_to_dict(response.json_data)

    async def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        """Select/deselect symbol in Market Watch.

        Args:
            symbol: Symbol name.
            enable: True to add, False to remove from Market Watch.

        Returns:
            True if successful, False otherwise.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolSelectRequest(symbol=symbol, enable=enable)
        response = await stub.SymbolSelect(request)
        return response.result

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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesRequest(
            symbol=symbol,
            timeframe=timeframe,
            date_from=self._to_timestamp(date_from),
            count=count,
        )
        response = await stub.CopyRatesFrom(request)
        return self._numpy_from_proto(response)

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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesPosRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_pos=start_pos,
            count=count,
        )
        response = await stub.CopyRatesFromPos(request)
        return self._numpy_from_proto(response)

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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyRatesRangeRequest(
            symbol=symbol,
            timeframe=timeframe,
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = await stub.CopyRatesRange(request)
        return self._numpy_from_proto(response)

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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyTicksRequest(
            symbol=symbol,
            date_from=self._to_timestamp(date_from),
            count=count,
            flags=flags,
        )
        response = await stub.CopyTicksFrom(request)
        return self._numpy_from_proto(response)

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
        stub = self._ensure_connected()
        request = mt5_pb2.CopyTicksRangeRequest(
            symbol=symbol,
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
            flags=flags,
        )
        response = await stub.CopyTicksRange(request)
        return self._numpy_from_proto(response)

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
        stub = self._ensure_connected()
        request = mt5_pb2.MarginRequest(
            action=action,
            symbol=symbol,
            volume=volume,
            price=price,
        )
        response = await stub.OrderCalcMargin(request)
        return response.value if response.HasField("value") else None

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
        stub = self._ensure_connected()
        request = mt5_pb2.ProfitRequest(
            action=action,
            symbol=symbol,
            volume=volume,
            price_open=price_open,
            price_close=price_close,
        )
        response = await stub.OrderCalcProfit(request)
        return response.value if response.HasField("value") else None

    async def order_check(
        self, request: dict[str, JSONValue]
    ) -> dict[str, JSONValue] | None:
        """Check order validity without sending.

        Args:
            request: Order request dictionary.

        Returns:
            Order check result or None.

        """
        stub = self._ensure_connected()
        grpc_request = mt5_pb2.OrderRequest(json_request=json.dumps(request))
        response = await stub.OrderCheck(grpc_request)
        return self._json_to_dict(response.json_data)

    async def order_send(
        self, request: dict[str, JSONValue]
    ) -> dict[str, JSONValue] | None:
        """Send trading order to MT5.

        Args:
            request: Order request dictionary.

        Returns:
            Order execution result or None.

        """
        stub = self._ensure_connected()
        grpc_request = mt5_pb2.OrderRequest(json_request=json.dumps(request))
        response = await stub.OrderSend(grpc_request)
        return self._json_to_dict(response.json_data)

    # =========================================================================
    # POSITIONS METHODS
    # =========================================================================

    async def positions_total(self) -> int:
        """Get total number of open positions.

        Returns:
            Count of open positions.

        """
        stub = self._ensure_connected()
        response = await stub.PositionsTotal(mt5_pb2.Empty())
        return response.value

    async def positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get open positions with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific position ticket.

        Returns:
            List of position dictionaries or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.PositionsRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        response = await stub.PositionsGet(request)
        return self._json_list_to_dicts(list(response.json_items))

    # =========================================================================
    # ORDERS METHODS
    # =========================================================================

    async def orders_total(self) -> int:
        """Get total number of pending orders.

        Returns:
            Count of pending orders.

        """
        stub = self._ensure_connected()
        response = await stub.OrdersTotal(mt5_pb2.Empty())
        return response.value

    async def orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get pending orders with optional filters.

        Args:
            symbol: Filter by symbol name.
            group: Symbol group filter.
            ticket: Specific order ticket.

        Returns:
            List of order dictionaries or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.OrdersRequest()
        if symbol is not None:
            request.symbol = symbol
        if group is not None:
            request.group = group
        if ticket is not None:
            request.ticket = ticket
        response = await stub.OrdersGet(request)
        return self._json_list_to_dicts(list(response.json_items))

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
        stub = self._ensure_connected()
        request = mt5_pb2.HistoryRequest(
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = await stub.HistoryOrdersTotal(request)
        return response.value

    async def history_orders_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical orders with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific order ticket.
            position: Position ID filter.

        Returns:
            List of historical order dictionaries or None.

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
        response = await stub.HistoryOrdersGet(request)
        return self._json_list_to_dicts(list(response.json_items))

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
        stub = self._ensure_connected()
        request = mt5_pb2.HistoryRequest(
            date_from=self._to_timestamp(date_from),
            date_to=self._to_timestamp(date_to),
        )
        response = await stub.HistoryDealsTotal(request)
        return response.value

    async def history_deals_get(
        self,
        date_from: datetime | int | None = None,
        date_to: datetime | int | None = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> list[dict[str, JSONValue]] | None:
        """Get historical deals with filters.

        Args:
            date_from: Start date.
            date_to: End date.
            group: Symbol group filter.
            ticket: Specific deal ticket.
            position: Position ID filter.

        Returns:
            List of historical deal dictionaries or None.

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
        response = await stub.HistoryDealsGet(request)
        return self._json_list_to_dicts(list(response.json_items))

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
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = await stub.MarketBookAdd(request)
        return response.result

    async def market_book_get(
        self, symbol: str
    ) -> list[dict[str, JSONValue]] | None:
        """Get market depth (DOM) data for a symbol.

        Requires prior market_book_add call.

        Args:
            symbol: Symbol name to get market depth for.

        Returns:
            List of market depth entries or None.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = await stub.MarketBookGet(request)
        return self._json_list_to_dicts(list(response.json_items))

    async def market_book_release(self, symbol: str) -> bool:
        """Unsubscribe from market depth (DOM) for a symbol.

        Args:
            symbol: Symbol name to unsubscribe from.

        Returns:
            True if unsubscription successful, False otherwise.

        """
        stub = self._ensure_connected()
        request = mt5_pb2.SymbolRequest(symbol=symbol)
        response = await stub.MarketBookRelease(request)
        return response.result
