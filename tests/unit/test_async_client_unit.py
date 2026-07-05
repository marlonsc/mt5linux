"""Unit tests for AsyncMetaTrader5 async_client.

Tests verify:
1. Connection lifecycle (_connect, _disconnect, connect, disconnect, is_connected)
2. Constant loading and __getattr__ access
3. _ensure_connected error paths
4. Public RPC methods with mocked gRPC stub
5. Error handling (ConnectionError, grpc.RpcError)
6. order_send_async and order_send_batch callback behavior
7. Resilience helpers (circuit breaker hooks, reconnect)

NO live bridge, Docker, or real gRPC server - all dependencies are mocked.
"""

from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import orjson
import pytest

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.models import MT5Models
from mt5linux.settings import MT5Settings
from mt5linux.utilities import MT5Utilities as u

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_T = TypeVar("_T")


def _make_aio_rpc_error(
    code: grpc.StatusCode = grpc.StatusCode.UNAVAILABLE,
) -> grpc.aio.AioRpcError:
    """Create a grpc.aio.AioRpcError with a real status code."""
    return grpc.aio.AioRpcError(code, None, None)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def settings() -> MT5Settings:
    """Return test settings with resilience features tuned for unit tests."""
    return MT5Settings(
        enable_circuit_breaker=False,
        enable_auto_reconnect=False,
        enable_health_monitor=False,
        retry_jitter=False,
        retry_max_attempts=2,
        retry_initial_delay=0.01,
        critical_retry_initial_delay=0.01,
        tx_verify_max_attempts=1,
        tx_verify_propagation_delay=0.01,
        queue_max_concurrent=2,
    )


@pytest.fixture
def client(settings: MT5Settings, monkeypatch: pytest.MonkeyPatch) -> AsyncMetaTrader5:
    """Return an unconnected async client using test settings."""
    monkeypatch.setattr("mt5linux.async_client._settings", settings)
    return AsyncMetaTrader5(host="testhost", port=12345)


@pytest.fixture
def connected_client(
    client: AsyncMetaTrader5,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncMetaTrader5:
    """Return a client with a mocked connected stub and channel.

    The real _resilient_call path is exercised, but terminal_info is
    monkey-patched to report connected so the terminal guard passes.
    """
    stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
    stub.GetConstants = AsyncMock(
        return_value=mt5_pb2.Constants(values={"TIMEFRAME_H1": 16385})
    )
    stub.HealthCheck = AsyncMock(
        return_value=mt5_pb2.HealthStatus(
            healthy=True,
            mt5_available=True,
            connected=True,
            trade_allowed=True,
            build=5956,
            reason="",
        )
    )
    stub.Version = AsyncMock(
        return_value=mt5_pb2.MT5Version(major=5, minor=0, build="build-1234")
    )
    stub.AccountInfo = AsyncMock(
        return_value=mt5_pb2.DictData(
            json_data='{"login": 12345, "server": "TestServer", "balance": 10000.0}'
        )
    )
    stub.SymbolInfo = AsyncMock(
        return_value=mt5_pb2.DictData(
            json_data='{"name": "EURUSD", "bid": 1.1, "ask": 1.1001}'
        )
    )
    stub.SymbolInfoTick = AsyncMock(
        return_value=mt5_pb2.DictData(
            json_data='{"time": 1234567890, "bid": 1.1, "ask": 1.1001}'
        )
    )
    stub.OrdersGet = AsyncMock(
        return_value=mt5_pb2.DictList(
            json_items=[orjson.dumps({"ticket": 1, "symbol": "EURUSD"}).decode()]
        )
    )
    stub.HistoryOrdersGet = AsyncMock(
        return_value=mt5_pb2.DictList(
            json_items=[orjson.dumps({"ticket": 1, "symbol": "EURUSD"}).decode()]
        )
    )
    stub.HistoryDealsGet = AsyncMock(
        return_value=mt5_pb2.DictList(
            json_items=[
                orjson.dumps(
                    {
                        "ticket": 1,
                        "symbol": "EURUSD",
                        "order": 2,
                        "volume": 0.1,
                        "price": 1.1,
                    }
                ).decode()
            ]
        )
    )
    stub.TerminalInfo = AsyncMock(
        return_value=mt5_pb2.DictData(json_data='{"connected": true, "build": 123}')
    )
    stub.LastError = AsyncMock(return_value=mt5_pb2.ErrorInfo(code=0, message="ok"))
    stub.SymbolsTotal = AsyncMock(return_value=mt5_pb2.IntResponse(value=42))
    stub.SymbolsGet = AsyncMock(
        return_value=mt5_pb2.SymbolsResponse(
            total=1,
            chunks=[orjson.dumps([{"name": "EURUSD"}]).decode()],
        )
    )
    stub.SymbolSelect = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
    stub.OrdersTotal = AsyncMock(return_value=mt5_pb2.IntResponse(value=0))
    stub.PositionsTotal = AsyncMock(return_value=mt5_pb2.IntResponse(value=0))
    stub.PositionsGet = AsyncMock(
        return_value=mt5_pb2.DictList(
            json_items=[orjson.dumps({"ticket": 1, "symbol": "EURUSD"}).decode()]
        )
    )
    stub.HistoryOrdersTotal = AsyncMock(return_value=mt5_pb2.IntResponse(value=0))
    stub.HistoryDealsTotal = AsyncMock(return_value=mt5_pb2.IntResponse(value=0))
    stub.MarketBookAdd = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
    stub.MarketBookGet = AsyncMock(
        return_value=mt5_pb2.DictList(
            json_items=[orjson.dumps({"type": 1, "price": 1.1, "volume": 1.0}).decode()]
        )
    )
    stub.MarketBookRelease = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
    stub.OrderCalcMargin = AsyncMock(return_value=mt5_pb2.FloatResponse(value=123.45))
    stub.OrderCalcProfit = AsyncMock(return_value=mt5_pb2.FloatResponse(value=9.99))
    stub.OrderCheck = AsyncMock(
        return_value=mt5_pb2.DictData(json_data='{"retcode": 0}')
    )
    stub.OrderSend = AsyncMock(
        return_value=mt5_pb2.DictData(
            json_data='{"retcode": 10009, "deal": 1, "order": 2}'
        )
    )
    stub.Initialize = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
    stub.Login = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
    stub.Shutdown = AsyncMock(return_value=mt5_pb2.Empty())
    stub.GetProvisionedAccount = AsyncMock(
        return_value=mt5_pb2.ProvisionedAccount(
            login=12345,
            server="TestServer",
            email="test@example.com",
            connected=True,
            source="test",
        )
    )
    stub.CreateDemoAccount = AsyncMock(
        return_value=mt5_pb2.ProvisionedAccount(
            login=777,
            server="MetaQuotes-Demo",
            email="x@y.z",
            connected=True,
            source="test",
        )
    )
    stub.CopyRatesFrom = AsyncMock(return_value=mt5_pb2.NumpyArray())
    stub.CopyRatesFromPos = AsyncMock(return_value=mt5_pb2.NumpyArray())
    stub.CopyRatesRange = AsyncMock(return_value=mt5_pb2.NumpyArray())
    stub.CopyTicksFrom = AsyncMock(return_value=mt5_pb2.NumpyArray())
    stub.CopyTicksRange = AsyncMock(return_value=mt5_pb2.NumpyArray())

    channel = MagicMock(spec=grpc.aio.Channel)
    channel.close = AsyncMock()

    client._channel = channel
    client._stub = stub
    client._constants = {"TIMEFRAME_H1": 16385}

    # Disable WAL and queue to keep tests focused on async_client logic
    client._wal = None
    client._queue = None

    # terminal_info guard must report connected for login-dependent operations
    async def _terminal_info() -> MT5Models.TerminalInfo:
        return MT5Models.TerminalInfo(connected=True, build=123)

    monkeypatch.setattr(client, "terminal_info", _terminal_info)
    monkeypatch.setattr(client, "_quick_health_check", AsyncMock(return_value=True))

    return client


# ============================================================================
# Connection lifecycle
# ============================================================================


class TestConnectionLifecycle:
    """Test connect/disconnect lifecycle."""

    async def test_is_connected_initially_false(self, client: AsyncMetaTrader5) -> None:
        """New client reports not connected."""
        assert client.is_connected is False

    async def test_connect_creates_channel_and_stub(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_connect creates channel, stub, loads constants, starts queue/WAL."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.GetConstants = AsyncMock(
            return_value=mt5_pb2.Constants(values={"TIMEFRAME_H1": 16385})
        )
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            await client._connect()

        assert client.is_connected is True
        assert client._stub is stub
        assert client._constants == {"TIMEFRAME_H1": 16385}
        assert client._queue is not None
        assert client._wal is not None

        await client._disconnect()
        assert client.is_connected is False

    async def test_connect_idempotent(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_connect is a no-op if already connected."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.GetConstants = AsyncMock(return_value=mt5_pb2.Constants(values={}))
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            await client._connect()
            channel.reset_mock()
            await client._connect()

        assert client._channel is channel
        stub.GetConstants.assert_awaited_once()

    async def test_disconnect_idempotent(self, client: AsyncMetaTrader5) -> None:
        """_disconnect is safe when not connected."""
        await client._disconnect()
        assert client.is_connected is False

    async def test_async_context_manager(self) -> None:
        """Async context manager connects and disconnects."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.GetConstants = AsyncMock(return_value=mt5_pb2.Constants(values={}))
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            async with AsyncMetaTrader5(host="testhost", port=12345) as mt5:
                assert mt5.is_connected is True

        assert channel.close.called


# ============================================================================
# Constants and __getattr__
# ============================================================================


class TestConstants:
    """Test MT5 constants access."""

    async def test_getattr_returns_constant(self, client: AsyncMetaTrader5) -> None:
        """__getattr__ returns loaded constant value."""
        client._constants = {"ORDER_TYPE_BUY": 0}
        assert client.ORDER_TYPE_BUY == 0

    async def test_getattr_missing_raises(self, client: AsyncMetaTrader5) -> None:
        """__getattr__ raises AttributeError for unknown constants."""
        with pytest.raises(AttributeError):
            _ = client.UNKNOWN_CONSTANT

    async def test_getattr_private_raises(self, client: AsyncMetaTrader5) -> None:
        """__getattr__ raises AttributeError for private names."""
        with pytest.raises(AttributeError):
            _ = client._private_attr


# ============================================================================
# _ensure_connected
# ============================================================================


class TestEnsureConnected:
    """Test connection guard."""

    async def test_ensure_connected_returns_stub(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_ensure_connected returns the active stub."""
        stub = connected_client._ensure_connected()
        assert stub is connected_client._stub

    async def test_ensure_connected_raises_when_never_connected(
        self, client: AsyncMetaTrader5
    ) -> None:
        """_ensure_connected raises ConnectionError when never connected."""
        client._host = ""
        with pytest.raises(ConnectionError, match="not established"):
            client._ensure_connected()

    async def test_ensure_connected_raises_connection_lost(
        self, client: AsyncMetaTrader5
    ) -> None:
        """_ensure_connected raises retryable ConnectionError after disconnect."""
        with pytest.raises(ConnectionError, match="Connection lost"):
            client._ensure_connected()


# ============================================================================
# Public RPC methods
# ============================================================================


class TestPublicMethods:
    """Test public RPC methods with mocked stub through real _resilient_call."""

    async def test_health_check(self, connected_client: AsyncMetaTrader5) -> None:
        """health_check returns status dict."""
        result = await connected_client.health_check()
        assert result["healthy"] is True
        assert result["connected"] is True
        assert result["build"] == 5956

    async def test_version(self, connected_client: AsyncMetaTrader5) -> None:
        """Version returns (major, minor, build) tuple."""
        result = await connected_client.version()
        assert result == (5, 0, "build-1234")

    async def test_version_none_when_empty_build(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Version returns None when build is empty."""
        connected_client._stub.Version = AsyncMock(
            return_value=mt5_pb2.MT5Version(major=5, minor=0, build="")
        )
        result = await connected_client.version()
        assert result is None

    async def test_account_info(self, connected_client: AsyncMetaTrader5) -> None:
        """account_info parses AccountInfo from JSON response."""
        result = await connected_client.account_info()
        assert isinstance(result, MT5Models.AccountInfo)
        assert result.login == 12345
        assert result.server == "TestServer"
        assert result.balance == 10000.0

    async def test_symbol_info(self, connected_client: AsyncMetaTrader5) -> None:
        """symbol_info parses SymbolInfo from JSON response."""
        result = await connected_client.symbol_info("EURUSD")
        assert isinstance(result, MT5Models.SymbolInfo)
        assert result.name == "EURUSD"

    async def test_symbol_info_tick(self, connected_client: AsyncMetaTrader5) -> None:
        """symbol_info_tick parses Tick from JSON response."""
        result = await connected_client.symbol_info_tick("EURUSD")
        assert isinstance(result, MT5Models.Tick)
        assert result.bid == 1.1

    async def test_symbols_total(self, connected_client: AsyncMetaTrader5) -> None:
        """symbols_total returns integer count."""
        result = await connected_client.symbols_total()
        assert result == 42

    async def test_symbols_get(self, connected_client: AsyncMetaTrader5) -> None:
        """symbols_get returns tuple of SymbolInfo objects."""
        result = await connected_client.symbols_get(group="*USD*")
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "EURUSD"

    async def test_last_error(self, connected_client: AsyncMetaTrader5) -> None:
        """last_error returns (code, message) tuple."""
        result = await connected_client.last_error()
        assert result == (0, "ok")

    async def test_terminal_info(self, connected_client: AsyncMetaTrader5) -> None:
        """terminal_info parses TerminalInfo from JSON response."""
        connected_client._stub.TerminalInfo = AsyncMock(
            return_value=mt5_pb2.DictData(json_data='{"connected": true, "build": 123}')
        )
        result = await connected_client.terminal_info()
        assert isinstance(result, MT5Models.TerminalInfo)
        assert result.connected is True
        assert result.build == 123

    async def test_order_calc_margin(self, connected_client: AsyncMetaTrader5) -> None:
        """order_calc_margin returns value when present."""
        result = await connected_client.order_calc_margin(0, "EURUSD", 0.1, 1.1)
        assert result == 123.45

    async def test_order_calc_profit(self, connected_client: AsyncMetaTrader5) -> None:
        """order_calc_profit returns value when present."""
        result = await connected_client.order_calc_profit(0, "EURUSD", 0.1, 1.1, 1.2)
        assert result == 9.99

    async def test_order_check(self, connected_client: AsyncMetaTrader5) -> None:
        """order_check parses OrderCheckResult from JSON response."""
        result = await connected_client.order_check({"action": 1, "symbol": "EURUSD"})
        assert isinstance(result, MT5Models.OrderCheckResult)
        assert result.retcode == 0

    async def test_symbol_select(self, connected_client: AsyncMetaTrader5) -> None:
        """symbol_select forwards enable flag."""
        result = await connected_client.symbol_select("EURUSD", enable=True)
        assert result is True
        request = connected_client._stub.SymbolSelect.call_args[0][0]
        assert request.symbol == "EURUSD"
        assert request.enable is True

    async def test_positions_total(self, connected_client: AsyncMetaTrader5) -> None:
        """positions_total returns count."""
        result = await connected_client.positions_total()
        assert result == 0

    async def test_positions_get(self, connected_client: AsyncMetaTrader5) -> None:
        """positions_get returns tuple of Position objects."""
        result = await connected_client.positions_get(symbol="EURUSD")
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1
        assert result[0].symbol == "EURUSD"

    async def test_orders_total(self, connected_client: AsyncMetaTrader5) -> None:
        """orders_total returns count."""
        result = await connected_client.orders_total()
        assert result == 0

    async def test_orders_get(self, connected_client: AsyncMetaTrader5) -> None:
        """orders_get returns tuple of Order objects."""
        result = await connected_client.orders_get(symbol="EURUSD")
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1
        assert result[0].symbol == "EURUSD"

    async def test_history_orders_total(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """history_orders_total returns count."""
        result = await connected_client.history_orders_total(
            datetime.now(UTC), datetime.now(UTC)
        )
        assert result == 0

    async def test_history_orders_get(self, connected_client: AsyncMetaTrader5) -> None:
        """history_orders_get returns tuple of Order objects."""
        result = await connected_client.history_orders_get()
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1
        assert result[0].symbol == "EURUSD"

    async def test_history_deals_total(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """history_deals_total returns count."""
        result = await connected_client.history_deals_total(
            datetime.now(UTC), datetime.now(UTC)
        )
        assert result == 0

    async def test_history_deals_get(self, connected_client: AsyncMetaTrader5) -> None:
        """history_deals_get returns tuple of Deal objects."""
        result = await connected_client.history_deals_get()
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1
        assert result[0].symbol == "EURUSD"

    async def test_market_book_add(self, connected_client: AsyncMetaTrader5) -> None:
        """market_book_add forwards symbol."""
        result = await connected_client.market_book_add("EURUSD")
        assert result is True

    async def test_market_book_get(self, connected_client: AsyncMetaTrader5) -> None:
        """market_book_get returns tuple of BookEntry objects."""
        result = await connected_client.market_book_get("EURUSD")
        assert result is not None
        assert len(result) == 1
        assert result[0].type == 1
        assert result[0].price == 1.1

    async def test_market_book_release(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """market_book_release forwards symbol."""
        result = await connected_client.market_book_release("EURUSD")
        assert result is True

    async def test_copy_rates_from(self, connected_client: AsyncMetaTrader5) -> None:
        """copy_rates_from builds request and returns None for empty array."""
        result = await connected_client.copy_rates_from(
            "EURUSD", 16385, datetime.now(UTC), 10
        )
        assert result is None

    async def test_copy_rates_from_pos(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """copy_rates_from_pos builds request and returns None for empty array."""
        result = await connected_client.copy_rates_from_pos("EURUSD", 16385, 0, 10)
        assert result is None

    async def test_copy_rates_range(self, connected_client: AsyncMetaTrader5) -> None:
        """copy_rates_range builds request and returns None for empty array."""
        result = await connected_client.copy_rates_range(
            "EURUSD", 16385, datetime.now(UTC), datetime.now(UTC)
        )
        assert result is None

    async def test_copy_ticks_from(self, connected_client: AsyncMetaTrader5) -> None:
        """copy_ticks_from builds request and returns None for empty array."""
        result = await connected_client.copy_ticks_from(
            "EURUSD", datetime.now(UTC), 10, 0
        )
        assert result is None

    async def test_copy_ticks_range(self, connected_client: AsyncMetaTrader5) -> None:
        """copy_ticks_range builds request and returns None for empty array."""
        result = await connected_client.copy_ticks_range(
            "EURUSD", datetime.now(UTC), datetime.now(UTC), 0
        )
        assert result is None


# ============================================================================
# Error paths
# ============================================================================


class TestErrorPaths:
    """Test error handling paths."""

    async def test_load_constants_logs_warning_on_rpc_error(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_load_constants swallows AioRpcError and logs a warning."""
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.GetConstants = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNKNOWN)
        )
        client._stub = stub

        await client._load_constants()
        assert client._constants == {}

    async def test_disconnect_suppresses_channel_close_error(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_disconnect suppresses RpcError from channel.close."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock(side_effect=grpc.RpcError("close failed"))
        client._channel = channel
        client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)

        await client._disconnect()
        assert client.is_connected is False

    async def test_public_method_raises_when_not_connected(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """health_check raises MaxRetriesError.

        Raises MaxRetriesError when not connected and retries exhaust.
        """
        with pytest.raises(u.Exceptions.MaxRetriesError):
            await client.health_check()

    async def test_rpc_error_propagates_through_resilient_call(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """grpc.RpcError in a public method is propagated/retried."""
        connected_client._stub.AccountInfo = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE)
        )

        with pytest.raises(u.Exceptions.MaxRetriesError):
            await connected_client.account_info()


# ============================================================================
# Order methods
# ============================================================================


class TestOrderSend:
    """Test order_send, order_send_async, order_send_batch."""

    @pytest.fixture
    def order_client(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> AsyncMetaTrader5:
        """Return a client with _safe_order_send mocked to a deterministic result."""

        async def _safe_order_send(
            request: dict[str, object],
        ) -> MT5Models.OrderResult:
            return MT5Models.OrderResult(
                retcode=10009,
                deal=1,
                order=2,
                comment=str(request.get("symbol", "")),
            )

        monkeypatch.setattr(connected_client, "_safe_order_send", _safe_order_send)
        return connected_client

    async def test_order_send(self, order_client: AsyncMetaTrader5) -> None:
        """order_send delegates to _safe_order_send and returns OrderResult."""
        result = await order_client.order_send({"action": 1, "symbol": "EURUSD"})
        assert isinstance(result, MT5Models.OrderResult)
        assert result.retcode == 10009

    async def test_order_send_async_returns_request_id_and_callbacks(
        self,
        order_client: AsyncMetaTrader5,
    ) -> None:
        """order_send_async returns request_id and invokes on_complete."""
        completed: list[MT5Models.OrderResult] = []

        def on_complete(result: MT5Models.OrderResult) -> None:
            completed.append(result)

        request_id = await order_client.order_send_async(
            {"action": 1, "symbol": "EURUSD"},
            on_complete=on_complete,
        )
        assert request_id.startswith("RQ")
        await asyncio.sleep(0.1)
        assert len(completed) == 1
        assert completed[0].retcode == 10009

    async def test_order_send_async_on_error_callback(
        self,
        order_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """order_send_async invokes on_error on failure."""
        error = ValueError("boom")

        async def _failing(_request: dict[str, object]) -> None:
            raise error

        monkeypatch.setattr(order_client, "_safe_order_send", _failing)

        errors: list[Exception] = []

        def on_error(exc: Exception) -> None:
            errors.append(exc)

        request_id = await order_client.order_send_async(
            {"action": 1, "symbol": "EURUSD"},
            on_error=on_error,
        )
        assert request_id.startswith("RQ")
        await asyncio.sleep(0.1)
        assert len(errors) == 1
        assert errors[0] is error

    async def test_order_send_batch_returns_request_ids(
        self,
        order_client: AsyncMetaTrader5,
    ) -> None:
        """order_send_batch returns list of request_ids."""
        request_ids = await order_client.order_send_batch(
            [
                {"action": 1, "symbol": "EURUSD"},
                {"action": 1, "symbol": "GBPUSD"},
            ]
        )
        assert len(request_ids) == 2
        assert all(rid.startswith("RQ") for rid in request_ids)

    async def test_order_send_batch_callbacks(
        self,
        order_client: AsyncMetaTrader5,
    ) -> None:
        """order_send_batch invokes on_each_complete and on_all_complete."""
        completed: list[tuple[str, MT5Models.OrderResult]] = []
        all_results: dict[str, MT5Models.OrderResult | Exception] | None = None

        def on_each(rid: str, result: MT5Models.OrderResult) -> None:
            completed.append((rid, result))

        def on_all(results: dict[str, MT5Models.OrderResult | Exception]) -> None:
            nonlocal all_results
            all_results = results

        await order_client.order_send_batch(
            [{"action": 1, "symbol": "EURUSD"}],
            on_each_complete=on_each,
            on_all_complete=on_all,
        )
        await asyncio.sleep(0.2)
        assert len(completed) == 1
        assert all_results is not None
        assert len(all_results) == 1


class TestSafeOrderSend:
    """Test _safe_order_send and _execute_order_grpc in isolation."""

    async def test_safe_order_send_returns_result(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_safe_order_send returns OrderResult from TransactionOrchestrator."""
        expected = MT5Models.OrderResult(retcode=10009, deal=1, order=2)

        class FakeOrchestrator:
            class Dependencies:
                def __init__(self, **kwargs: object) -> None:
                    pass

            def __init__(self, _settings: MT5Settings, _deps: object) -> None:
                pass

            async def execute(self, _request: dict[str, object]) -> object:
                return expected

        monkeypatch.setattr(
            "mt5linux.async_client.u.TransactionOrchestrator", FakeOrchestrator
        )

        result = await connected_client._safe_order_send(
            {"action": 1, "symbol": "EURUSD"}
        )
        assert result is expected

    async def test_safe_order_send_filters_non_order_result(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_safe_order_send returns None if orchestrator returns non-OrderResult."""

        class FakeOrchestrator:
            class Dependencies:
                def __init__(self, **kwargs: object) -> None:
                    pass

            def __init__(self, _settings: MT5Settings, _deps: object) -> None:
                pass

            async def execute(self, _request: dict[str, object]) -> object:
                return "unexpected"

        monkeypatch.setattr(
            "mt5linux.async_client.u.TransactionOrchestrator", FakeOrchestrator
        )

        result = await connected_client._safe_order_send({"action": 1})
        assert result is None

    async def test_execute_order_grpc(self, connected_client: AsyncMetaTrader5) -> None:
        """_execute_order_grpc parses OrderResult from stub.OrderSend."""
        result = await connected_client._execute_order_grpc(
            {"action": 1, "symbol": "EURUSD"}, attempt=0
        )
        assert isinstance(result, MT5Models.OrderResult)
        assert result.retcode == 10009
        assert result.deal == 1
        assert result.order == 2


# ============================================================================
# Resilience helpers
# ============================================================================


class TestResilienceHelpers:
    """Test small resilience helpers."""

    async def test_record_circuit_success_no_breaker(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_record_circuit_success is safe when no circuit breaker."""
        client._circuit_breaker = None
        client._record_circuit_success()

    async def test_record_circuit_failure_no_breaker(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_record_circuit_failure is safe when no circuit breaker."""
        client._circuit_breaker = None
        client._record_circuit_failure(ValueError("boom"))

    async def test_check_circuit_breaker_no_breaker(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_check_circuit_breaker is safe when no circuit breaker."""
        client._circuit_breaker = None
        client._check_circuit_breaker("order_send")

    async def test_check_circuit_breaker_open_raises(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_check_circuit_breaker raises when circuit breaker is OPEN."""
        config = MT5Settings(cb_threshold=1, cb_recovery=30.0)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        client._circuit_breaker = cb

        with pytest.raises(ConnectionError, match="Circuit breaker OPEN"):
            client._check_circuit_breaker("order_send")

    async def test_quick_health_check_true(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_quick_health_check returns True when stub responds."""
        result = await connected_client._quick_health_check(timeout=1.0)
        assert result is True

    async def test_quick_health_check_false_when_disconnected(
        self, client: AsyncMetaTrader5
    ) -> None:
        """_quick_health_check returns False when not connected."""
        result = await client._quick_health_check(timeout=1.0)
        assert result is False

    async def test_ensure_terminal_connected_for_operation_excluded(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """Excluded operations skip terminal connection check."""
        # Should complete immediately without calling terminal_info
        await connected_client._ensure_terminal_connected_for_operation("version")

    async def test_ensure_terminal_connected_for_operation_connected(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """Login-dependent operations proceed when terminal is connected."""
        await connected_client._ensure_terminal_connected_for_operation("account_info")


# ============================================================================
# initialize / login / shutdown
# ============================================================================


class TestInitializeLoginShutdown:
    """Test initialize, login, and shutdown methods."""

    async def test_initialize_stores_credentials_and_calls_stub(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Initialize stores credentials and forwards request."""
        password_value = secrets.token_hex(8)
        result = await connected_client.initialize(
            path="/path",
            login=12345,
            password=password_value,
            server="TestServer",
            timeout=5000,
            portable=True,
        )
        assert result is True
        assert connected_client._init_credentials == {
            "path": "/path",
            "login": 12345,
            "password": password_value,
            "server": "TestServer",
            "timeout": 5000,
            "portable": True,
        }
        request = connected_client._stub.Initialize.call_args[0][0]
        assert request.path == "/path"
        assert request.login == 12345
        assert request.password == password_value
        assert request.server == "TestServer"
        assert request.timeout == 5000
        assert request.portable is True

    async def test_initialize_auto_connects_when_not_connected(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Initialize calls _connect when stub is None."""
        connected = {"called": False}
        password_value = secrets.token_hex(8)

        async def fake_connect() -> None:
            connected["called"] = True
            client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
            client._stub.Initialize = AsyncMock(
                return_value=mt5_pb2.BoolResponse(result=True)
            )
            client._channel = MagicMock(spec=grpc.aio.Channel)
            client._channel.close = AsyncMock()

        monkeypatch.setattr(client, "_connect", fake_connect)

        async def _terminal_info() -> MT5Models.TerminalInfo:
            return MT5Models.TerminalInfo(connected=True)

        monkeypatch.setattr(client, "terminal_info", _terminal_info)

        result = await client.initialize(
            login=12345, password=password_value, server="TestServer"
        )
        assert connected["called"] is True
        assert result is True

    async def test_login_forwards_request(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Login forwards request to stub."""
        monkeypatch.setattr(
            connected_client, "_quick_health_check", AsyncMock(return_value=True)
        )
        password_value = secrets.token_hex(8)

        result = await connected_client.login(
            12345, password=password_value, server="TestServer"
        )
        assert result is True
        request = connected_client._stub.Login.call_args[0][0]
        assert request.login == 12345
        assert request.password == password_value
        assert request.server == "TestServer"

    async def test_login_attempts_reconnect_when_unhealthy(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Login attempts reconnect when _quick_health_check is False."""
        connected_client._settings = MT5Settings(
            enable_auto_reconnect=False,
            enable_circuit_breaker=False,
            retry_jitter=False,
        )
        monkeypatch.setattr(
            connected_client, "_quick_health_check", AsyncMock(return_value=False)
        )
        monkeypatch.setattr(
            connected_client, "_reconnect_with_backoff", AsyncMock(return_value=False)
        )

        result = await connected_client.login(12345)
        connected_client._reconnect_with_backoff.assert_awaited_once()
        assert result is True

    async def test_shutdown_when_connected(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Shutdown calls stub.Shutdown when connected."""
        await connected_client.shutdown()
        connected_client._stub.Shutdown.assert_awaited_once()

    async def test_shutdown_no_op_when_disconnected(
        self, client: AsyncMetaTrader5
    ) -> None:
        """Shutdown is a no-op when not connected."""
        await client.shutdown()

    async def test_create_demo_account_maps_spec(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """create_demo_account forwards spec fields and maps response."""
        spec = MT5Models.CreateDemoSpec(
            server="MetaQuotes-Demo",
            email="x@y.z",
            phone="11988887777",
        )
        result = await connected_client.create_demo_account(spec)

        request = connected_client._stub.CreateDemoAccount.call_args[0][0]
        assert request.server == "MetaQuotes-Demo"
        assert request.email == "x@y.z"
        assert request.phone == "11988887777"
        assert result.login == 777

    async def test_recover_provisioned_account(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """recover_provisioned_account maps proto to model."""
        result = await connected_client.recover_provisioned_account()
        assert isinstance(result, MT5Models.ProvisionedAccount)
        assert result.login == 12345
        assert result.server == "TestServer"


# ============================================================================
# Raw infrastructure methods
# ============================================================================


class TestRawMethods:
    """Test raw methods used by order verification."""

    async def test_orders_get_raw(self, connected_client: AsyncMetaTrader5) -> None:
        """_orders_get_raw parses orders from stub response."""
        result = await connected_client._orders_get_raw(ticket=123)
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1

    async def test_orders_get_raw_returns_none_on_rpc_error(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_orders_get_raw returns None on RpcError."""
        connected_client._stub.OrdersGet = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNKNOWN)
        )
        result = await connected_client._orders_get_raw()
        assert result is None

    async def test_history_orders_get_raw(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_history_orders_get_raw parses orders from stub response."""
        result = await connected_client._history_orders_get_raw(ticket=123)
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1

    async def test_history_deals_get_raw(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_history_deals_get_raw parses deals from stub response."""
        result = await connected_client._history_deals_get_raw(ticket=123)
        assert result is not None
        assert len(result) == 1
        assert result[0].ticket == 1


# ============================================================================
# Reconnect / health monitor
# ============================================================================


class TestReconnectAndHealth:
    """Test reconnection and health monitor helpers."""

    async def test_reconnect_with_backoff_success(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_reconnect_with_backoff returns True on successful reconnect."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            result = await client._reconnect_with_backoff()

        assert result is True
        assert client.is_connected is True

    async def test_reconnect_with_backoff_failure(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_reconnect_with_backoff returns False when stub fails."""
        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.HealthCheck = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE)
        )

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            result = await client._reconnect_with_backoff()

        assert result is False

    async def test_ensure_connected_with_reconnect_success(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_ensure_connected_with_reconnect reconnects when auto-reconnect enabled."""
        client._settings = MT5Settings(
            enable_auto_reconnect=True,
            enable_circuit_breaker=False,
            retry_jitter=False,
            retry_max_attempts=1,
        )

        channel = MagicMock(spec=grpc.aio.Channel)
        channel.close = AsyncMock()
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))

        with (
            patch(
                "mt5linux.async_client.grpc.aio.insecure_channel", return_value=channel
            ),
            patch.object(mt5_pb2_grpc, "MT5ServiceStub", return_value=stub),
        ):
            result = await client._ensure_connected_with_reconnect()

        assert result is stub

    async def test_ensure_connected_with_reconnect_failure(
        self, client: AsyncMetaTrader5
    ) -> None:
        """_ensure_connected_with_reconnect raises.

        Raises when not connected and no reconnect.
        """
        client._settings = MT5Settings(
            enable_auto_reconnect=False,
            enable_circuit_breaker=False,
        )
        with pytest.raises(ConnectionError, match="not established"):
            await client._ensure_connected_with_reconnect()

    async def test_start_stop_health_monitor(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_health_monitor and stop_health_monitor manage background task."""
        client._settings = MT5Settings(enable_health_monitor=True)

        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.HealthCheck = AsyncMock(return_value=mt5_pb2.HealthStatus(connected=True))
        client._stub = stub
        client._channel = MagicMock(spec=grpc.aio.Channel)
        client._health_check_interval = 0.01

        await client.start_health_monitor()
        assert client._health_task is not None
        await asyncio.sleep(0.05)
        await client.stop_health_monitor()
        assert client._health_task is None

    async def test_health_monitor_disabled_by_config(
        self, client: AsyncMetaTrader5
    ) -> None:
        """start_health_monitor is a no-op when disabled in config."""
        client._settings = MT5Settings(enable_health_monitor=False)
        await client.start_health_monitor()
        assert client._health_task is None


# ============================================================================
# verify order state
# ============================================================================


class TestVerifyOrderState:
    """Test order state verification paths."""

    async def test_verify_order_state_disabled(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_verify_order_state returns None when tx_verify_on_ambiguous is False."""
        connected_client._settings = MT5Settings(tx_verify_on_ambiguous=False)
        result = MT5Models.OrderResult(retcode=10012)
        verified = await connected_client._verify_order_state(
            result, request_id="RQ1234567890abcdef"
        )
        assert verified is None

    async def test_verify_by_comment_no_deals(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_verify_by_comment returns None when no deals match."""
        result = MT5Models.OrderResult(retcode=10012)
        verified = await connected_client._verify_by_comment(
            "RQ1234567890abcdef", result
        )
        assert verified is None

    async def test_verify_by_comment_found(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_verify_by_comment returns OrderResult when comment matches."""
        connected_client._stub.HistoryDealsGet = AsyncMock(
            return_value=mt5_pb2.DictList(
                json_items=[
                    orjson.dumps(
                        {
                            "ticket": 99,
                            "order": 2,
                            "volume": 0.1,
                            "price": 1.1,
                            "comment": "RQ1234567890abcdef|original",
                        }
                    ).decode()
                ]
            )
        )

        result = MT5Models.OrderResult(retcode=10012, bid=1.0, ask=1.1)
        verified = await connected_client._verify_by_comment(
            "RQ1234567890abcdef", result
        )
        assert isinstance(verified, MT5Models.OrderResult)
        assert verified.deal == 99
        assert verified.order == 2

    async def test_verify_order_state_impl_by_order(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state_impl finds order in pending orders."""

        async def _orders_get_raw(
            ticket: int | None = None,
        ) -> tuple[MT5Models.Order, ...] | None:
            return (MT5Models.Order(ticket=42, symbol="EURUSD"),)

        monkeypatch.setattr(connected_client, "_orders_get_raw", _orders_get_raw)
        monkeypatch.setattr(
            connected_client, "_history_orders_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_history_deals_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_verify_by_comment", AsyncMock(return_value=None)
        )

        result = MT5Models.OrderResult(retcode=10012, order=42)
        verified = await connected_client._verify_order_state_impl(
            result, request_id="RQ1234567890abcdef"
        )
        assert isinstance(verified, MT5Models.OrderResult)
        assert verified.retcode == 10008  # PLACED
        assert verified.order == 42

    async def test_verify_order_state_impl_by_history(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state_impl finds order in history."""

        async def _history_orders_get_raw(
            ticket: int | None = None,
        ) -> tuple[MT5Models.Order, ...] | None:
            return (MT5Models.Order(ticket=42, symbol="EURUSD"),)

        monkeypatch.setattr(
            connected_client, "_orders_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_history_orders_get_raw", _history_orders_get_raw
        )
        monkeypatch.setattr(
            connected_client, "_history_deals_get_raw", AsyncMock(return_value=None)
        )

        result = MT5Models.OrderResult(retcode=10012, order=42)
        verified = await connected_client._verify_order_state_impl(
            result, request_id="RQ1234567890abcdef"
        )
        assert isinstance(verified, MT5Models.OrderResult)
        assert verified.retcode == 10009  # DONE

    async def test_verify_order_state_impl_by_deal(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state_impl finds deal in history."""

        async def _history_deals_get_raw(
            ticket: int | None = None,
            date_from: object = None,
            date_to: object = None,
        ) -> tuple[MT5Models.Deal, ...] | None:
            return (MT5Models.Deal(ticket=99, order=42, symbol="EURUSD"),)

        monkeypatch.setattr(
            connected_client, "_orders_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_history_orders_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_history_deals_get_raw", _history_deals_get_raw
        )

        result = MT5Models.OrderResult(retcode=10012, deal=99)
        verified = await connected_client._verify_order_state_impl(
            result, request_id="RQ1234567890abcdef"
        )
        assert isinstance(verified, MT5Models.OrderResult)
        assert verified.retcode == 10009  # DONE
        assert verified.deal == 99

    async def test_verify_order_state_impl_synthetic_ids_no_request_id(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_verify_order_state_impl returns None when result lacks request_id."""
        result = MT5Models.OrderResult(retcode=10012, order=0, deal=0)
        verified = await connected_client._verify_order_state_impl(
            result, request_id=None
        )
        assert verified is None

    async def test_verify_order_state_impl_by_comment(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state_impl verifies by comment match."""
        expected = MT5Models.OrderResult(retcode=10009, deal=99, order=42)

        async def _verify_by_comment(
            request_id: str, result: MT5Models.OrderResult
        ) -> MT5Models.OrderResult | None:
            return expected

        monkeypatch.setattr(connected_client, "_verify_by_comment", _verify_by_comment)
        monkeypatch.setattr(
            connected_client, "_orders_get_raw", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            connected_client, "_history_orders_get_raw", AsyncMock(return_value=None)
        )

        result = MT5Models.OrderResult(retcode=10012, order=42, deal=0)
        verified = await connected_client._verify_order_state_impl(
            result, request_id="RQ1234567890abcdef"
        )
        assert verified is expected

    async def test_verify_order_state_impl_rpc_error(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state_impl records failure and continues on RpcError."""

        async def _failing(*args: object, **kwargs: object) -> None:
            raise _make_aio_rpc_error(grpc.StatusCode.UNKNOWN)

        monkeypatch.setattr(connected_client, "_orders_get_raw", _failing)

        result = MT5Models.OrderResult(retcode=10012, order=42)
        verified = await connected_client._verify_order_state_impl(
            result, request_id="RQ1234567890abcdef"
        )
        assert verified is None


# ============================================================================
# WAL recovery
# ============================================================================


class TestRecoverIncompleteOrders:
    """Test _recover_incomplete_orders."""

    async def test_recover_incomplete_orders_executed(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_recover_incomplete_orders marks executed orders as recovered."""
        entry = u.WAL.Entry(
            request_id="RQ1234567890abcdef",
            timestamp=datetime.now(UTC),
            request_json='{"action": 1}',
            status=u.WAL.Status.SENT,
        )

        class FakeWAL:
            async def get_incomplete(self) -> list[u.WAL.Entry]:
                return [entry]

            async def mark_recovered(
                self, request_id: str, result: dict[str, object]
            ) -> None:
                recovered["request_id"] = request_id
                recovered["result"] = result

            async def mark_failed(self, request_id: str, error: str) -> None:
                recovered["failed"] = (request_id, error)

        recovered: dict[str, object] = {}
        connected_client._wal = FakeWAL()

        async def _verify_order_state_impl(
            result: MT5Models.OrderResult, request_id: str | None
        ) -> MT5Models.OrderResult | None:
            return MT5Models.OrderResult(retcode=10009, deal=1, order=2)

        monkeypatch.setattr(
            connected_client, "_verify_order_state_impl", _verify_order_state_impl
        )

        await connected_client._recover_incomplete_orders()
        assert recovered.get("request_id") == "RQ1234567890abcdef"
        assert recovered.get("result") == {"retcode": 10009, "order": 2, "deal": 1}

    async def test_recover_incomplete_orders_not_executed(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_recover_incomplete_orders marks unverified orders as failed."""
        entry = u.WAL.Entry(
            request_id="RQ1234567890abcdef",
            timestamp=datetime.now(UTC),
            request_json='{"action": 1}',
            status=u.WAL.Status.SENT,
        )

        class FakeWAL:
            async def get_incomplete(self) -> list[u.WAL.Entry]:
                return [entry]

            async def mark_recovered(
                self, request_id: str, result: dict[str, object]
            ) -> None:
                recovered["recovered"] = (request_id, result)

            async def mark_failed(self, request_id: str, error: str) -> None:
                recovered["failed"] = (request_id, error)

        recovered: dict[str, object] = {}
        connected_client._wal = FakeWAL()

        async def _verify_order_state_impl(
            result: MT5Models.OrderResult, request_id: str | None
        ) -> MT5Models.OrderResult | None:
            return None

        monkeypatch.setattr(
            connected_client, "_verify_order_state_impl", _verify_order_state_impl
        )

        await connected_client._recover_incomplete_orders()
        assert recovered.get("failed") == (
            "RQ1234567890abcdef",
            "Order not found in MT5 after recovery",
        )

    async def test_recover_incomplete_orders_no_wal(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_recover_incomplete_orders is safe when WAL is None."""
        connected_client._wal = None
        await connected_client._recover_incomplete_orders()

    async def test_recover_incomplete_orders_empty(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_recover_incomplete_orders is safe when no incomplete entries."""

        class FakeWAL:
            async def get_incomplete(self) -> list[u.WAL.Entry]:
                return []

        connected_client._wal = FakeWAL()
        await connected_client._recover_incomplete_orders()


# ============================================================================
# Timestamp int paths
# ============================================================================


class TestTimestampIntPaths:
    """Test copy_* methods with integer timestamps."""

    async def test_copy_rates_from_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """copy_rates_from accepts integer date_from."""
        result = await connected_client.copy_rates_from("EURUSD", 16385, 1234567890, 10)
        assert result is None

    async def test_copy_rates_range_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """copy_rates_range accepts integer dates."""
        result = await connected_client.copy_rates_range(
            "EURUSD", 16385, 1234567890, 1234567900
        )
        assert result is None

    async def test_copy_ticks_from_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """copy_ticks_from accepts integer date_from."""
        result = await connected_client.copy_ticks_from("EURUSD", 1234567890, 10, 0)
        assert result is None

    async def test_copy_ticks_range_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """copy_ticks_range accepts integer dates."""
        result = await connected_client.copy_ticks_range(
            "EURUSD", 1234567890, 1234567900, 0
        )
        assert result is None

    async def test_history_orders_total_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """history_orders_total accepts integer dates."""
        result = await connected_client.history_orders_total(1234567890, 1234567900)
        assert result == 0

    async def test_history_deals_total_int(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """history_deals_total accepts integer dates."""
        result = await connected_client.history_deals_total(1234567890, 1234567900)
        assert result == 0


# ============================================================================
# current_account
# ============================================================================


class TestCurrentAccount:
    """Test current_account extension method."""

    async def test_current_account_connected(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """current_account merges live account when connected."""

        async def fake_health() -> dict[str, bool | int | str]:
            return {
                "healthy": True,
                "mt5_available": True,
                "connected": True,
                "trade_allowed": True,
                "build": 5956,
                "reason": "",
            }

        account = MT5Models.AccountInfo(
            login=5052338262,
            server="MetaQuotes-Demo",
            company="MetaQuotes Ltd.",
            name="Auto Trader",
            balance=100000.0,
            currency="USD",
        )

        async def fake_account() -> MT5Models.AccountInfo | None:
            return account

        monkeypatch.setattr(connected_client, "health_check", fake_health)
        monkeypatch.setattr(connected_client, "account_info", fake_account)

        result = await connected_client.current_account()
        assert result.host == "testhost"
        assert result.port == 12345
        assert result.connected is True
        assert result.login == 5052338262

    async def test_current_account_disconnected(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """current_account reports disconnected without calling account_info."""
        called = {"account_info": False}

        async def fake_health() -> dict[str, bool | int | str]:
            return {
                "healthy": False,
                "mt5_available": True,
                "connected": False,
                "trade_allowed": False,
                "build": 0,
                "reason": "Terminal not connected",
            }

        async def fake_account() -> MT5Models.AccountInfo | None:
            called["account_info"] = True
            return None

        monkeypatch.setattr(connected_client, "health_check", fake_health)
        monkeypatch.setattr(connected_client, "account_info", fake_account)

        result = await connected_client.current_account()
        assert result.connected is False
        assert result.login is None
        assert called["account_info"] is False


# ============================================================================
# Queued call fallback
# ============================================================================


class TestQueuedCallFallback:
    """Test _queued_call fallback when queue is not running."""

    async def test_queued_call_fallback_when_queue_none(
        self, connected_client: AsyncMetaTrader5
    ) -> None:
        """_queued_call executes coro directly when queue is None."""
        connected_client._queue = None

        async def coro() -> int:
            return 42

        result = await connected_client._queued_call("test", coro)
        assert result == 42

    async def test_queued_call_uses_queue_when_running(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_queued_call submits to queue when it is running."""

        class FakeQueue:
            is_running = True

            async def submit(
                self,
                operation: str,
                coro_factory: Callable[[], Awaitable[_T]],
                coalesce_key: str | None = None,
            ) -> _T:
                return await coro_factory()

        connected_client._queue = FakeQueue()

        async def coro() -> int:
            return 42

        result = await connected_client._queued_call("test", coro)
        assert result == 42


# ============================================================================
# Additional coverage for previously uncovered branches
# ============================================================================


class TestConnectionCoverage:
    """Cover small connection lifecycle branches."""

    async def test_load_constants_no_stub(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_load_constants returns early when stub is None."""
        client._stub = None
        await client._load_constants()
        assert client._constants == {}

    async def test_recover_incomplete_orders_exception(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_recover_incomplete_orders logs exception from verification."""

        class FakeWAL:
            async def get_incomplete(self) -> list[u.WAL.Entry]:
                entry = u.WAL.Entry(
                    request_id="RQ1234567890abcdef",
                    timestamp=datetime.now(UTC),
                    request_json='{"action": 1}',
                    status=u.WAL.Status.SENT,
                )
                return [entry]

        connected_client._wal = FakeWAL()

        async def _failing(
            _result: MT5Models.OrderResult,
            _request_id: str | None,
        ) -> MT5Models.OrderResult | None:
            raise ValueError

        monkeypatch.setattr(connected_client, "_verify_order_state_impl", _failing)

        await connected_client._recover_incomplete_orders()


class TestResilienceCoverage:
    """Cover resilience helpers not fully exercised."""

    async def test_ensure_connected_with_reconnect_returns_existing_stub(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_ensure_connected_with_reconnect returns stub when already set."""
        client._settings = MT5Settings(
            enable_auto_reconnect=False,
            enable_circuit_breaker=False,
        )
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        client._stub = stub
        result = await client._ensure_connected_with_reconnect()
        assert result is stub

    async def test_reinitialize_terminal_no_credentials(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_reinitialize_terminal returns False with no stored credentials."""
        client._settings = MT5Settings(
            enable_auto_reconnect=True,
            enable_circuit_breaker=False,
        )
        client._init_credentials = {}
        result = await client._reinitialize_terminal()
        assert result is False

    async def test_reinitialize_terminal_auto_reconnect_disabled(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_reinitialize_terminal returns False when auto-reconnect disabled."""
        client._settings = MT5Settings(
            enable_auto_reconnect=False,
            enable_circuit_breaker=False,
        )
        client._init_credentials = {"login": 12345}
        result = await client._reinitialize_terminal()
        assert result is False

    async def test_reinitialize_terminal_success(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_reinitialize_terminal builds request and returns result."""
        client._settings = MT5Settings(
            enable_auto_reconnect=True,
            enable_circuit_breaker=False,
        )
        password_value = secrets.token_hex(8)
        client._init_credentials = {
            "path": "/mt5",
            "login": 12345,
            "password": password_value,
            "server": "TestServer",
            "timeout": 5000,
            "portable": True,
        }

        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.Initialize = AsyncMock(return_value=mt5_pb2.BoolResponse(result=True))
        client._stub = stub

        result = await client._reinitialize_terminal()
        assert result is True
        request = stub.Initialize.call_args[0][0]
        assert request.path == "/mt5"
        assert request.login == 12345
        assert request.password == password_value
        assert request.server == "TestServer"
        assert request.timeout == 5000
        assert request.portable is True

    async def test_reinitialize_terminal_failure(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_reinitialize_terminal returns False when Initialize returns False."""
        client._settings = MT5Settings(
            enable_auto_reconnect=True,
            enable_circuit_breaker=False,
        )
        client._init_credentials = {"login": 12345}

        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.Initialize = AsyncMock(return_value=mt5_pb2.BoolResponse(result=False))
        client._stub = stub

        result = await client._reinitialize_terminal()
        assert result is False

    async def test_reinitialize_terminal_rpc_error(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_reinitialize_terminal returns False on AioRpcError."""
        client._settings = MT5Settings(
            enable_auto_reconnect=True,
            enable_circuit_breaker=False,
        )
        client._init_credentials = {"login": 12345}

        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.Initialize = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE),
        )
        client._stub = stub

        result = await client._reinitialize_terminal()
        assert result is False


class TestEnsureTerminalConnectedCoverage:
    """Cover _ensure_terminal_connected branches."""

    async def test_ensure_terminal_connected_no_stub(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """Returns False when stub is None."""
        client._stub = None
        result = await client._ensure_terminal_connected()
        assert result is False

    async def test_ensure_terminal_connected_true(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """Returns True when terminal_info reports connected."""
        client._settings = MT5Settings(enable_circuit_breaker=False)
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(
            return_value=mt5_pb2.DictData(json_data='{"connected": true}'),
        )
        client._stub = stub
        result = await client._ensure_terminal_connected()
        assert result is True

    async def test_ensure_terminal_connected_reinit_success(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-initializes terminal when disconnected and reinit succeeds."""
        client._settings = MT5Settings(enable_circuit_breaker=False)
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(
            return_value=mt5_pb2.DictData(json_data='{"connected": false}'),
        )
        client._stub = stub
        monkeypatch.setattr(
            client,
            "_reinitialize_terminal",
            AsyncMock(return_value=True),
        )
        result = await client._ensure_terminal_connected()
        assert result is True

    async def test_ensure_terminal_connected_reinit_failure(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns False when terminal disconnected and reinit fails."""
        client._settings = MT5Settings(enable_circuit_breaker=False)
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(
            return_value=mt5_pb2.DictData(json_data='{"connected": false}'),
        )
        client._stub = stub
        monkeypatch.setattr(
            client,
            "_reinitialize_terminal",
            AsyncMock(return_value=False),
        )
        result = await client._ensure_terminal_connected()
        assert result is False

    async def test_ensure_terminal_connected_rpc_error(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """Returns False on AioRpcError."""
        client._settings = MT5Settings(enable_circuit_breaker=False)
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE),
        )
        client._stub = stub
        result = await client._ensure_terminal_connected()
        assert result is False


class TestHealthMonitorCoverage:
    """Cover health monitor task branches."""

    @pytest.fixture
    def health_client(self, client: AsyncMetaTrader5) -> AsyncMetaTrader5:
        """Return a client configured for health monitor tests."""
        client._settings = MT5Settings(
            enable_health_monitor=True,
            enable_circuit_breaker=False,
        )
        client._health_check_interval = 0.01
        client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        client._channel = MagicMock(spec=grpc.aio.Channel)
        return client

    async def test_health_monitor_terminal_not_connected(
        self,
        health_client: AsyncMetaTrader5,
    ) -> None:
        """Counts consecutive failures when terminal not connected."""
        health_client._stub.HealthCheck = AsyncMock(
            return_value=mt5_pb2.HealthStatus(connected=False),
        )
        await health_client.start_health_monitor()
        await asyncio.sleep(0.05)
        await health_client.stop_health_monitor()
        assert health_client._consecutive_failures >= 1

    async def test_health_monitor_timeout_disconnects(
        self,
        health_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TimeoutError branch increments failures and disconnects after threshold."""

        async def fake_wait_for(
            coro: object,
            **kwargs: object,
        ) -> object:
            raise TimeoutError

        health_client._stub.HealthCheck = AsyncMock()

        monkeypatch.setattr(
            "mt5linux.async_client.asyncio.wait_for",
            fake_wait_for,
        )
        monkeypatch.setattr(health_client, "_disconnect", AsyncMock())

        await health_client.start_health_monitor()
        await asyncio.sleep(0.05)
        await health_client.stop_health_monitor()
        health_client._disconnect.assert_awaited()

    async def test_health_monitor_rpc_error(
        self,
        health_client: AsyncMetaTrader5,
    ) -> None:
        """AioRpcError branch increments failures."""
        health_client._stub.HealthCheck = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE),
        )
        await health_client.start_health_monitor()
        await asyncio.sleep(0.05)
        await health_client.stop_health_monitor()
        assert health_client._consecutive_failures >= 1

    async def test_health_monitor_unexpected_error(
        self,
        health_client: AsyncMetaTrader5,
    ) -> None:
        """Generic exception inside inner check is logged by outer handler."""
        health_client._stub.HealthCheck = AsyncMock(side_effect=ValueError("boom"))
        await health_client.start_health_monitor()
        await asyncio.sleep(0.05)
        await health_client.stop_health_monitor()

    async def test_start_health_monitor_already_running(
        self,
        health_client: AsyncMetaTrader5,
    ) -> None:
        """Second start is a no-op when task still running."""
        health_client._stub.HealthCheck = AsyncMock(
            return_value=mt5_pb2.HealthStatus(connected=True),
        )
        await health_client.start_health_monitor()
        task = health_client._health_task
        await health_client.start_health_monitor()
        assert health_client._health_task is task
        await health_client.stop_health_monitor()


class TestTerminalConnectionForOperationCoverage:
    """Cover _ensure_terminal_connected_for_operation retry branches."""

    async def test_terminal_connection_reconnect_raises(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reconnect exception is logged and loop continues."""
        client._settings = MT5Settings(
            enable_circuit_breaker=False,
            retry_max_attempts=1,
            retry_initial_delay=0.0,
        )
        client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)

        async def terminal_info() -> MT5Models.TerminalInfo | None:
            return MT5Models.TerminalInfo(connected=False)

        monkeypatch.setattr(client, "terminal_info", terminal_info)
        monkeypatch.setattr(
            client,
            "_reconnect_with_backoff",
            AsyncMock(side_effect=ConnectionError("boom")),
        )

        with pytest.raises(ConnectionError, match="Terminal not connected"):
            await client._ensure_terminal_connected_for_operation("account_info")

    async def test_terminal_connection_reinit_raises(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Terminal reinitialize exception is logged."""
        client._settings = MT5Settings(
            enable_circuit_breaker=False,
            retry_max_attempts=1,
            retry_initial_delay=0.0,
            enable_auto_reconnect=True,
        )
        client._init_credentials = {"login": 12345}
        client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)

        async def terminal_info() -> MT5Models.TerminalInfo | None:
            return MT5Models.TerminalInfo(connected=False)

        monkeypatch.setattr(client, "terminal_info", terminal_info)
        monkeypatch.setattr(
            client,
            "_reconnect_with_backoff",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            client,
            "_reinitialize_terminal",
            AsyncMock(side_effect=RuntimeError("boom")),
        )

        with pytest.raises(ConnectionError, match="Terminal not connected"):
            await client._ensure_terminal_connected_for_operation("account_info")

    async def test_terminal_connection_info_raises(
        self,
        client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exception from terminal_info itself is logged and loop continues."""
        client._settings = MT5Settings(
            enable_circuit_breaker=False,
            retry_max_attempts=1,
            retry_initial_delay=0.0,
        )
        client._stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        monkeypatch.setattr(
            client,
            "terminal_info",
            AsyncMock(side_effect=ValueError("boom")),
        )

        with pytest.raises(ConnectionError, match="Terminal not connected"):
            await client._ensure_terminal_connected_for_operation("account_info")


class TestQuickHealthCheckCoverage:
    """Cover real _quick_health_check paths."""

    async def test_quick_health_check_true_real(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_quick_health_check returns True when TerminalInfo responds."""
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(return_value=mt5_pb2.DictData())
        client._stub = stub
        result = await client._quick_health_check(timeout=1.0)
        assert result is True

    async def test_quick_health_check_generic_exception(
        self,
        client: AsyncMetaTrader5,
    ) -> None:
        """_quick_health_check returns False on unexpected exception."""
        stub = MagicMock(spec=mt5_pb2_grpc.MT5ServiceStub)
        stub.TerminalInfo = AsyncMock(side_effect=ValueError("boom"))
        client._stub = stub
        result = await client._quick_health_check(timeout=1.0)
        assert result is False


class TestInitializeAndLoginCoverage:
    """Cover initialize field branches and login reconnect exception."""

    async def test_initialize_with_none_fields(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Initialize request omits fields when they are None."""
        result = await connected_client.initialize(portable=True)
        assert result is True
        request = connected_client._stub.Initialize.call_args[0][0]
        assert request.portable is True
        assert not request.HasField("path")
        assert not request.HasField("login")

    async def test_login_reconnect_exception(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Login logs reconnect failure and proceeds."""
        monkeypatch.setattr(
            connected_client,
            "_quick_health_check",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr(
            connected_client,
            "_reconnect_with_backoff",
            AsyncMock(side_effect=ConnectionError("boom")),
        )
        result = await connected_client.login(12345)
        assert result is True


class TestRealTerminalInfo:
    """Exercise the real terminal_info body (fixture normally monkeypatches it)."""

    def _unpatch(self, client: AsyncMetaTrader5) -> None:
        with suppress(AttributeError):
            del client.terminal_info

    async def test_terminal_info_success_real(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Real terminal_info parses response."""
        self._unpatch(connected_client)
        connected_client._stub.TerminalInfo = AsyncMock(
            return_value=mt5_pb2.DictData(
                json_data='{"connected": true, "build": 123}',
            ),
        )
        result = await connected_client.terminal_info()
        assert isinstance(result, MT5Models.TerminalInfo)
        assert result.connected is True
        assert result.build == 123

    async def test_terminal_info_failure_returns_none(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Real terminal_info returns None after retries exhaust."""
        self._unpatch(connected_client)
        connected_client._stub.TerminalInfo = AsyncMock(
            side_effect=_make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE),
        )
        result = await connected_client.terminal_info()
        assert result is None


class TestSymbolsGetCoverage:
    """Cover symbols_get None/empty branches."""

    async def test_symbols_get_no_group(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """symbols_get works without group filter."""
        result = await connected_client.symbols_get()
        assert result is not None
        assert len(result) == 1

    async def test_symbols_get_empty_response(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """symbols_get returns None when response has no items."""
        connected_client._stub.SymbolsGet = AsyncMock(
            return_value=mt5_pb2.SymbolsResponse(total=0, chunks=[]),
        )
        result = await connected_client.symbols_get()
        assert result is None


class TestOrderSendAsyncCoverage:
    """Cover order_send_async branches."""

    @pytest.fixture
    def async_client(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> AsyncMetaTrader5:
        """Return a client with a deterministic _safe_order_send."""

        async def _safe(
            _request: dict[str, object],
        ) -> MT5Models.OrderResult:
            return MT5Models.OrderResult(retcode=10009, deal=1, order=2)

        monkeypatch.setattr(connected_client, "_safe_order_send", _safe)
        return connected_client

    async def test_order_send_async_queue_path(
        self,
        async_client: AsyncMetaTrader5,
    ) -> None:
        """order_send_async submits through running queue."""

        class FakeQueue:
            is_running = True

            async def submit(
                self,
                operation: str,
                coro_factory: Callable[[], Awaitable[_T]],
                coalesce_key: str | None = None,
            ) -> _T:
                return await coro_factory()

        async_client._queue = FakeQueue()
        request_id = await async_client.order_send_async(
            {"action": 1, "symbol": "EURUSD"},
        )
        assert request_id.startswith("RQ")
        await asyncio.sleep(0.05)

    async def test_order_send_async_on_complete_raises(
        self,
        async_client: AsyncMetaTrader5,
    ) -> None:
        """Exception in on_complete is logged and swallowed."""

        def bad_complete(_result: MT5Models.OrderResult) -> None:
            raise ValueError

        request_id = await async_client.order_send_async(
            {"action": 1, "symbol": "EURUSD"},
            on_complete=bad_complete,
        )
        assert request_id.startswith("RQ")
        await asyncio.sleep(0.05)

    async def test_order_send_async_on_error_raises(
        self,
        async_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exception in on_error is logged and swallowed."""

        async def _failing(_request: dict[str, object]) -> None:
            raise ValueError

        monkeypatch.setattr(async_client, "_safe_order_send", _failing)

        def bad_error(_exc: Exception) -> None:
            raise ValueError

        request_id = await async_client.order_send_async(
            {"action": 1, "symbol": "EURUSD"},
            on_error=bad_error,
        )
        assert request_id.startswith("RQ")
        await asyncio.sleep(0.05)


class TestOrderSendBatchCoverage:
    """Cover order_send_batch callback/queue branches."""

    @pytest.fixture
    def batch_client(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> AsyncMetaTrader5:
        """Return a client with a deterministic _safe_order_send."""

        async def _safe(
            _request: dict[str, object],
        ) -> MT5Models.OrderResult:
            return MT5Models.OrderResult(retcode=10009, deal=1, order=2)

        monkeypatch.setattr(connected_client, "_safe_order_send", _safe)
        return connected_client

    async def test_order_send_batch_queue_path(
        self,
        batch_client: AsyncMetaTrader5,
    ) -> None:
        """order_send_batch submits through running queue."""

        class FakeQueue:
            is_running = True

            async def submit(
                self,
                operation: str,
                coro_factory: Callable[[], Awaitable[_T]],
                coalesce_key: str | None = None,
            ) -> _T:
                return await coro_factory()

        batch_client._queue = FakeQueue()
        request_ids = await batch_client.order_send_batch(
            [{"action": 1, "symbol": "EURUSD"}],
        )
        assert len(request_ids) == 1
        await asyncio.sleep(0.05)

    async def test_order_send_batch_none_result(
        self,
        batch_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """None result path and on_each_error exception handling."""

        async def _none(_request: dict[str, object]) -> None:
            return None

        monkeypatch.setattr(batch_client, "_safe_order_send", _none)

        errors: list[tuple[str, Exception]] = []

        def bad_each_error(rid: str, exc: Exception) -> None:
            errors.append((rid, exc))
            raise ValueError

        request_ids = await batch_client.order_send_batch(
            [{"action": 1, "symbol": "EURUSD"}],
            on_each_error=bad_each_error,
        )
        assert len(request_ids) == 1
        await asyncio.sleep(0.1)
        assert len(errors) == 1

    async def test_order_send_batch_on_each_complete_raises(
        self,
        batch_client: AsyncMetaTrader5,
    ) -> None:
        """Exception in on_each_complete is logged and swallowed."""

        def bad_each_complete(_rid: str, _result: MT5Models.OrderResult) -> None:
            raise ValueError

        request_ids = await batch_client.order_send_batch(
            [{"action": 1, "symbol": "EURUSD"}],
            on_each_complete=bad_each_complete,
        )
        assert len(request_ids) == 1
        await asyncio.sleep(0.1)

    async def test_order_send_batch_on_all_complete_raises(
        self,
        batch_client: AsyncMetaTrader5,
    ) -> None:
        """Exception in on_all_complete is logged and swallowed."""

        def bad_all(
            _results: dict[str, MT5Models.OrderResult | Exception],
        ) -> None:
            raise ValueError

        request_ids = await batch_client.order_send_batch(
            [{"action": 1, "symbol": "EURUSD"}],
            on_all_complete=bad_all,
        )
        assert len(request_ids) == 1
        await asyncio.sleep(0.1)


class TestExecuteOrderGrpcCoverage:
    """Cover _execute_order_grpc logging branches."""

    async def test_execute_order_grpc_logs_critical(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """TX log paths covered when tx_log_critical is True."""
        connected_client._settings = MT5Settings(tx_log_critical=True)
        result = await connected_client._execute_order_grpc(
            {"action": 1, "symbol": "EURUSD"},
            attempt=0,
        )
        assert isinstance(result, MT5Models.OrderResult)

    async def test_execute_order_grpc_empty_response(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """Empty JSON response yields an error OrderResult."""
        connected_client._settings = MT5Settings(tx_log_critical=True)
        connected_client._stub.OrderSend = AsyncMock(
            return_value=mt5_pb2.DictData(json_data=""),
        )
        result = await connected_client._execute_order_grpc(
            {"action": 1, "symbol": "EURUSD"},
            attempt=0,
        )
        assert isinstance(result, MT5Models.OrderResult)
        assert result.retcode != 0


class TestVerifyOrderStateCoverage:
    """Cover _verify_order_state and _verify_order_state_impl branches."""

    async def test_verify_order_state_acquires_lock(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_verify_order_state delegates to impl after acquiring operation lock."""
        expected = MT5Models.OrderResult(retcode=10009, deal=1, order=2)

        async def _impl(
            result: MT5Models.OrderResult,
            request_id: str | None,
        ) -> MT5Models.OrderResult | None:
            return expected

        monkeypatch.setattr(connected_client, "_verify_order_state_impl", _impl)
        result = await connected_client._verify_order_state(
            MT5Models.OrderResult(retcode=10012),
            request_id="RQ1234567890abcdef",
        )
        assert result is expected

    async def test_verify_order_state_impl_synthetic_by_comment(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Synthetic result with request_id verifies by comment."""
        expected = MT5Models.OrderResult(retcode=10009, deal=99, order=42)

        async def _verify_by_comment(
            request_id: str,
            result: MT5Models.OrderResult,
        ) -> MT5Models.OrderResult | None:
            return expected

        monkeypatch.setattr(
            connected_client,
            "_verify_by_comment",
            _verify_by_comment,
        )
        result = MT5Models.OrderResult(retcode=10012, order=0, deal=0)
        verified = await connected_client._verify_order_state_impl(
            result,
            request_id="RQ1234567890abcdef",
        )
        assert verified is expected

    async def test_verify_order_state_impl_timeouts(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Timed-out verification attempts record circuit failure and continue."""

        async def _exec(
            coro: object,
            timeout_s: float,
            name: str,
        ) -> tuple[None, bool]:
            return (None, True)

        monkeypatch.setattr(
            "mt5linux.async_client.u.RetryStrategy.execute_with_timeout_and_cancel",
            _exec,
        )
        connected_client._circuit_breaker = None
        result = MT5Models.OrderResult(retcode=10012, order=42, deal=99)
        verified = await connected_client._verify_order_state_impl(
            result,
            request_id="RQ1234567890abcdef",
        )
        assert verified is None

    async def test_verify_order_state_impl_rpc_error(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """RpcError during verification is caught and continues."""

        async def _exec(
            coro: object,
            timeout_s: float,
            name: str,
        ) -> None:
            raise _make_aio_rpc_error(grpc.StatusCode.UNAVAILABLE)

        monkeypatch.setattr(
            "mt5linux.async_client.u.RetryStrategy.execute_with_timeout_and_cancel",
            _exec,
        )
        result = MT5Models.OrderResult(retcode=10012, order=42, deal=99)
        verified = await connected_client._verify_order_state_impl(
            result,
            request_id="RQ1234567890abcdef",
        )
        assert verified is None

    async def test_verify_order_state_impl_name_error_propagates(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NameError/TypeError/AttributeError is re-raised."""

        async def _exec(
            coro: object,
            timeout_s: float,
            name: str,
        ) -> None:
            raise NameError

        monkeypatch.setattr(
            "mt5linux.async_client.u.RetryStrategy.execute_with_timeout_and_cancel",
            _exec,
        )
        result = MT5Models.OrderResult(retcode=10012, order=42, deal=99)
        with pytest.raises(NameError):
            await connected_client._verify_order_state_impl(
                result,
                request_id="RQ1234567890abcdef",
            )

    async def test_verify_order_state_impl_unexpected_error_propagates(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected non-RpcError exceptions are re-raised."""

        async def _exec(
            coro: object,
            timeout_s: float,
            name: str,
        ) -> None:
            raise RuntimeError

        monkeypatch.setattr(
            "mt5linux.async_client.u.RetryStrategy.execute_with_timeout_and_cancel",
            _exec,
        )
        result = MT5Models.OrderResult(retcode=10012, order=42, deal=99)
        with pytest.raises(RuntimeError):
            await connected_client._verify_order_state_impl(
                result,
                request_id="RQ1234567890abcdef",
            )


class TestVerifyByCommentCoverage:
    """Cover _verify_by_comment empty/None branches."""

    async def test_verify_by_comment_none_deals(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns None when raw deals returns None."""
        monkeypatch.setattr(
            connected_client,
            "_history_deals_get_raw",
            AsyncMock(return_value=None),
        )
        result = MT5Models.OrderResult(retcode=10012)
        verified = await connected_client._verify_by_comment(
            "RQ1234567890abcdef",
            result,
        )
        assert verified is None

    async def test_verify_by_comment_empty_deals(
        self,
        connected_client: AsyncMetaTrader5,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns None when raw deals returns empty tuple."""
        monkeypatch.setattr(
            connected_client,
            "_history_deals_get_raw",
            AsyncMock(return_value=()),
        )
        result = MT5Models.OrderResult(retcode=10012)
        verified = await connected_client._verify_by_comment(
            "RQ1234567890abcdef",
            result,
        )
        assert verified is None


class TestRawMethodsCoverage:
    """Cover raw method None branches and public method filter branches."""

    async def test_orders_get_raw_empty(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_orders_get_raw returns None on empty response."""
        connected_client._stub.OrdersGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client._orders_get_raw()
        assert result is None

    async def test_history_orders_get_raw_no_ticket(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_history_orders_get_raw works without ticket filter."""
        connected_client._stub.HistoryOrdersGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client._history_orders_get_raw()
        assert result is None

    async def test_history_deals_get_raw_empty(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """_history_deals_get_raw returns None on empty response."""
        connected_client._stub.HistoryDealsGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client._history_deals_get_raw()
        assert result is None

    async def test_positions_get_with_group_and_ticket(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """positions_get applies group/ticket filters."""
        connected_client._stub.PositionsGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client.positions_get(group="*", ticket=1)
        assert result is None
        request = connected_client._stub.PositionsGet.call_args[0][0]
        assert request.group == "*"
        assert request.ticket == 1

    async def test_orders_get_with_group_and_ticket(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """orders_get applies group/ticket filters."""
        connected_client._stub.OrdersGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client.orders_get(group="*", ticket=1)
        assert result is None
        request = connected_client._stub.OrdersGet.call_args[0][0]
        assert request.group == "*"
        assert request.ticket == 1

    async def test_history_orders_get_with_all_filters(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """history_orders_get applies all optional filters."""
        connected_client._stub.HistoryOrdersGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client.history_orders_get(
            date_from=datetime.now(UTC),
            date_to=datetime.now(UTC),
            group="*",
            ticket=1,
            position=2,
        )
        assert result is None
        request = connected_client._stub.HistoryOrdersGet.call_args[0][0]
        assert request.group == "*"
        assert request.ticket == 1
        assert request.position == 2

    async def test_history_deals_get_with_all_filters(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """history_deals_get applies all optional filters."""
        connected_client._stub.HistoryDealsGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client.history_deals_get(
            date_from=datetime.now(UTC),
            date_to=datetime.now(UTC),
            group="*",
            ticket=1,
            position=2,
        )
        assert result is None
        request = connected_client._stub.HistoryDealsGet.call_args[0][0]
        assert request.group == "*"
        assert request.ticket == 1
        assert request.position == 2

    async def test_market_book_get_empty(
        self,
        connected_client: AsyncMetaTrader5,
    ) -> None:
        """market_book_get returns None on empty response."""
        connected_client._stub.MarketBookGet = AsyncMock(
            return_value=mt5_pb2.DictList(json_items=[]),
        )
        result = await connected_client.market_book_get("EURUSD")
        assert result is None
