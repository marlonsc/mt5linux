"""Unit tests for mt5linux.client.MetaTrader5 (sync wrapper).

These tests mock the internal `_async_client` instance so no real gRPC server,
Docker container, or MetaTrader5 terminal is required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from mt5linux.client import MetaTrader5
from mt5linux.models import MT5Models

if TYPE_CHECKING:
    from collections.abc import Callable

    from mt5linux.async_client import AsyncMetaTrader5


@pytest.fixture
def mocked_mt5() -> tuple[MetaTrader5, MagicMock]:
    """Return a sync MetaTrader5 client with a mocked async client."""
    mt5 = MetaTrader5(host="unittest", port=12345)
    async_mock = MagicMock()
    async_mock.connect = AsyncMock(return_value=None)
    async_mock.disconnect = AsyncMock(return_value=None)
    async_mock.is_connected = False
    mt5._async_client = async_mock
    return mt5, async_mock


class TestLifecycle:
    """Connection lifecycle tests."""

    def test_init_defaults(self) -> None:
        """MetaTrader5 stores host/port and creates an async client."""
        mt5 = MetaTrader5(host="localhost", port=50051)
        assert mt5._async_client is not None
        assert mt5._async_client._host == "localhost"
        assert mt5._async_client._port == 50051

    def test_connect_delegates(self, mocked_mt5: tuple[MetaTrader5, MagicMock]) -> None:
        """connect() awaits the async client's connect()."""
        mt5, async_mock = mocked_mt5
        mt5.connect()
        async_mock.connect.assert_awaited_once()

    def test_disconnect_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """disconnect() awaits the async client's disconnect()."""
        mt5, async_mock = mocked_mt5
        mt5.disconnect()
        async_mock.disconnect.assert_awaited_once()

    def test_is_connected_reads_async_property(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """is_connected reflects the async client's connection state."""
        mt5, async_mock = mocked_mt5
        async_mock.is_connected = True
        assert mt5.is_connected is True
        async_mock.is_connected = False
        assert mt5.is_connected is False


class TestContextManager:
    """Context manager entry/exit tests."""

    def test_context_manager_connects_and_disconnects(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """__enter__ connects and __exit__ disconnects."""
        mt5, async_mock = mocked_mt5
        with mt5:
            async_mock.connect.assert_awaited_once()
            async_mock.disconnect.assert_not_awaited()
        async_mock.disconnect.assert_awaited_once()

    def test_context_manager_returns_self(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """__enter__ returns the client instance."""
        mt5, _async_mock = mocked_mt5
        with mt5 as entered:
            assert entered is mt5


class TestConstants:
    """__getattr__ delegation for MT5 constants."""

    def test_getattr_delegates_to_async_client(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """Attribute lookups for constants are forwarded."""
        mt5, async_mock = mocked_mt5
        async_mock.configure_mock(TIMEFRAME_H1=16385)
        assert mt5.TIMEFRAME_H1 == 16385

    def test_getattr_missing_raises(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """Missing constants raise AttributeError."""
        mt5, _async_mock = mocked_mt5

        class RaisingClient:
            """Async client stand-in that raises AttributeError for constants."""

            def __getattr__(self, name: str) -> int:
                msg = f"'{type(self).__name__}' object has no attribute '{name}'"
                raise AttributeError(msg)

        mt5._async_client = cast("AsyncMetaTrader5", RaisingClient())
        with pytest.raises(AttributeError, match="UNKNOWN_CONSTANT"):
            _ = mt5.UNKNOWN_CONSTANT


class TestIntrospection:
    """get_methods() and get_models() use the gRPC stub directly."""

    def test_get_methods_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """get_methods() calls GetMethods on the stub returned by _ensure_connected."""
        mt5, async_mock = mocked_mt5
        param = MagicMock()
        param.name = "login"
        param.type_hint = "int"
        param.kind = "POSITIONAL_OR_KEYWORD"
        param.has_default = False
        param.default_value = ""
        method = MagicMock()
        method.name = "login"
        method.parameters = [param]
        method.return_type = "bool"
        method.is_callable = True
        response = MagicMock()
        response.methods = [method]
        stub = MagicMock()
        stub.GetMethods = AsyncMock(return_value=response)
        async_mock.ensure_connected = MagicMock(return_value=stub)
        result = mt5.get_methods()
        stub.GetMethods.assert_awaited_once()
        assert result == [
            {
                "name": "login",
                "parameters": [
                    {
                        "name": "login",
                        "type_hint": "int",
                        "kind": "POSITIONAL_OR_KEYWORD",
                        "has_default": False,
                        "default_value": "",
                    },
                ],
                "return_type": "bool",
                "is_callable": True,
            },
        ]

    def test_get_models_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """get_models() calls GetModels on the stub returned by _ensure_connected."""
        mt5, async_mock = mocked_mt5
        field = MagicMock()
        field.name = "login"
        field.type_hint = "int"
        field.index = 0
        model = MagicMock()
        model.name = "AccountInfo"
        model.fields = [field]
        model.is_namedtuple = True
        response = MagicMock()
        response.models = [model]
        stub = MagicMock()
        stub.GetModels = AsyncMock(return_value=response)
        async_mock.ensure_connected = MagicMock(return_value=stub)
        result = mt5.get_models()
        stub.GetModels.assert_awaited_once()
        assert result == [
            {
                "name": "AccountInfo",
                "fields": [
                    {"name": "login", "type_hint": "int", "index": 0},
                ],
                "is_namedtuple": True,
            },
        ]


class TestTerminalMethods:
    """Terminal/info method delegations."""

    def test_initialize_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """initialize() passes kwargs to the async client."""
        mt5, async_mock = mocked_mt5
        async_mock.initialize = AsyncMock(return_value=True)
        result = mt5.initialize(
            login=12345,
            password="secret",  # noqa: S106
            server="Demo",
        )
        async_mock.initialize.assert_awaited_once_with(
            path=None,
            login=12345,
            password="secret",  # noqa: S106
            server="Demo",
            timeout=None,
            portable=False,
        )
        assert result is True

    def test_login_delegates(self, mocked_mt5: tuple[MetaTrader5, MagicMock]) -> None:
        """login() passes credentials to the async client."""
        mt5, async_mock = mocked_mt5
        async_mock.login = AsyncMock(return_value=True)
        result = mt5.login(12345, "secret", "Demo", 30000)
        async_mock.login.assert_awaited_once_with(
            login=12345,
            password="secret",  # noqa: S106
            server="Demo",
            timeout=30000,
        )
        assert result is True

    def test_shutdown_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """shutdown() awaits the async client."""
        mt5, async_mock = mocked_mt5
        async_mock.shutdown = AsyncMock(return_value=None)
        mt5.shutdown()
        async_mock.shutdown.assert_awaited_once()

    def test_health_check_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """health_check() returns the async client's dict."""
        mt5, async_mock = mocked_mt5
        expected: dict[str, bool | int | str] = {
            "healthy": True,
            "mt5_available": True,
            "connected": True,
            "trade_allowed": True,
            "build": 5956,
            "reason": "",
        }
        async_mock.health_check = AsyncMock(return_value=expected)
        result = mt5.health_check()
        async_mock.health_check.assert_awaited_once()
        assert result == expected

    def test_version_delegates(self, mocked_mt5: tuple[MetaTrader5, MagicMock]) -> None:
        """version() returns the async client's tuple."""
        mt5, async_mock = mocked_mt5
        async_mock.version = AsyncMock(return_value=(5, 0, " build 3550"))
        result = mt5.version()
        async_mock.version.assert_awaited_once()
        assert result == (5, 0, " build 3550")

    def test_last_error_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """last_error() returns the async client's tuple."""
        mt5, async_mock = mocked_mt5
        async_mock.last_error = AsyncMock(return_value=(0, "OK"))
        result = mt5.last_error()
        async_mock.last_error.assert_awaited_once()
        assert result == (0, "OK")

    def test_terminal_info_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """terminal_info() returns the async client's model."""
        mt5, async_mock = mocked_mt5
        info = MT5Models.TerminalInfo(connected=True, build=3550)
        async_mock.terminal_info = AsyncMock(return_value=info)
        result = mt5.terminal_info()
        async_mock.terminal_info.assert_awaited_once()
        assert result == info

    def test_account_info_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """account_info() returns the async client's model."""
        mt5, async_mock = mocked_mt5
        account = MT5Models.AccountInfo(login=12345, balance=10000.0)
        async_mock.account_info = AsyncMock(return_value=account)
        result = mt5.account_info()
        async_mock.account_info.assert_awaited_once()
        assert result == account

    def test_current_account_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """current_account() returns the async client's CurrentAccount."""
        mt5, async_mock = mocked_mt5
        current = MT5Models.CurrentAccount(host="unittest", port=12345, connected=True)
        async_mock.current_account = AsyncMock(return_value=current)
        result = mt5.current_account()
        async_mock.current_account.assert_awaited_once()
        assert result == current

    def test_recover_provisioned_account_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """recover_provisioned_account() returns the async client's model."""
        mt5, async_mock = mocked_mt5
        provisioned = MT5Models.ProvisionedAccount(login=12345, server="Demo")
        async_mock.recover_provisioned_account = AsyncMock(return_value=provisioned)
        result = mt5.recover_provisioned_account()
        async_mock.recover_provisioned_account.assert_awaited_once()
        assert result == provisioned

    def test_create_demo_account_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """create_demo_account() passes the spec to the async client."""
        mt5, async_mock = mocked_mt5
        provisioned = MT5Models.ProvisionedAccount(
            login=12345, server="MetaQuotes-Demo"
        )
        async_mock.create_demo_account = AsyncMock(return_value=provisioned)
        spec = MT5Models.CreateDemoSpec(server="MetaQuotes-Demo", email="a@b.c")
        result = mt5.create_demo_account(spec)
        async_mock.create_demo_account.assert_awaited_once_with(spec)
        assert result == provisioned


class TestSymbolMethods:
    """Symbol-related method delegations."""

    def test_symbols_total_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """symbols_total() returns the async client's int."""
        mt5, async_mock = mocked_mt5
        async_mock.symbols_total = AsyncMock(return_value=80)
        assert mt5.symbols_total() == 80

    def test_symbols_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """symbols_get() passes the optional group filter."""
        mt5, async_mock = mocked_mt5
        info = MT5Models.SymbolInfo(name="EURUSD")
        async_mock.symbols_get = AsyncMock(return_value=(info,))
        result = mt5.symbols_get(group="*USD*")
        async_mock.symbols_get.assert_awaited_once_with(group="*USD*")
        assert result == (info,)

    def test_symbol_info_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """symbol_info() passes the symbol name."""
        mt5, async_mock = mocked_mt5
        info = MT5Models.SymbolInfo(name="EURUSD")
        async_mock.symbol_info = AsyncMock(return_value=info)
        result = mt5.symbol_info("EURUSD")
        async_mock.symbol_info.assert_awaited_once_with("EURUSD")
        assert result == info

    def test_symbol_info_tick_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """symbol_info_tick() passes the symbol name."""
        mt5, async_mock = mocked_mt5
        tick = MT5Models.Tick(time=1, bid=1.1, ask=1.1001)
        async_mock.symbol_info_tick = AsyncMock(return_value=tick)
        result = mt5.symbol_info_tick("EURUSD")
        async_mock.symbol_info_tick.assert_awaited_once_with("EURUSD")
        assert result == tick

    def test_symbol_select_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """symbol_select() passes the symbol and enable flag."""
        mt5, async_mock = mocked_mt5
        async_mock.symbol_select = AsyncMock(return_value=True)
        result = mt5.symbol_select("EURUSD", enable=True)
        async_mock.symbol_select.assert_awaited_once_with("EURUSD", enable=True)
        assert result is True


class TestMarketDataMethods:
    """Market data method delegations."""

    @pytest.mark.parametrize(
        ("method", "args"),
        [
            ("copy_rates_from", ("EURUSD", 16385, 0, 10)),
            ("copy_rates_from_pos", ("EURUSD", 16385, 0, 10)),
            ("copy_rates_range", ("EURUSD", 16385, 0, 1)),
            ("copy_ticks_from", ("EURUSD", 0, 10, 0)),
            ("copy_ticks_range", ("EURUSD", 0, 1, 0)),
        ],
    )
    def test_market_data_delegates(
        self,
        mocked_mt5: tuple[MetaTrader5, MagicMock],
        method: str,
        args: tuple[object, ...],
    ) -> None:
        """Market data methods delegate positional args to the async client."""
        mt5, async_mock = mocked_mt5
        async_method = AsyncMock(return_value=None)
        setattr(async_mock, method, async_method)
        sync_method: Callable[..., object] = getattr(mt5, method)
        result = sync_method(*args)
        async_method.assert_awaited_once()
        assert result is None


class TestTradingMethods:
    """Trading method delegations."""

    def test_order_calc_margin_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_calc_margin() forwards all positional args."""
        mt5, async_mock = mocked_mt5
        async_mock.order_calc_margin = AsyncMock(return_value=100.0)
        result = mt5.order_calc_margin(0, "EURUSD", 1.0, 1.1)
        async_mock.order_calc_margin.assert_awaited_once_with(0, "EURUSD", 1.0, 1.1)
        assert result == 100.0

    def test_order_calc_profit_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_calc_profit() forwards all positional args."""
        mt5, async_mock = mocked_mt5
        async_mock.order_calc_profit = AsyncMock(return_value=50.0)
        result = mt5.order_calc_profit(0, "EURUSD", 1.0, 1.1, 1.2)
        async_mock.order_calc_profit.assert_awaited_once_with(
            0, "EURUSD", 1.0, 1.1, 1.2
        )
        assert result == 50.0

    def test_order_check_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_check() forwards the request dict."""
        mt5, async_mock = mocked_mt5
        check_result = MT5Models.OrderCheckResult(retcode=0)
        async_mock.order_check = AsyncMock(return_value=check_result)
        request: dict[str, int | float | str] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
        }
        result = mt5.order_check(request)
        async_mock.order_check.assert_awaited_once_with(request)
        assert result == check_result

    def test_order_send_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_send() forwards the request dict and returns OrderResult."""
        mt5, async_mock = mocked_mt5
        order_result = MT5Models.OrderResult(retcode=0, order=12345)
        async_mock.order_send = AsyncMock(return_value=order_result)
        request: dict[str, int | float | str] = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
        }
        result = mt5.order_send(request)
        async_mock.order_send.assert_awaited_once_with(request)
        assert result == order_result

    def test_order_send_async_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_send_async() forwards request and callbacks."""
        mt5, async_mock = mocked_mt5
        async_mock.order_send_async = AsyncMock(return_value="RQ001")

        def on_complete(result: MT5Models.OrderResult) -> None:
            pass

        def on_error(error: Exception) -> None:
            pass

        request: dict[str, int | float | str] = {"action": 1, "symbol": "EURUSD"}
        result = mt5.order_send_async(request, on_complete, on_error)
        async_mock.order_send_async.assert_awaited_once_with(
            request, on_complete, on_error
        )
        assert result == "RQ001"

    def test_order_send_batch_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """order_send_batch() forwards requests and callbacks."""
        mt5, async_mock = mocked_mt5
        async_mock.order_send_batch = AsyncMock(return_value=["RQ001", "RQ002"])
        requests: list[dict[str, int | float | str]] = [
            {"action": 1, "symbol": "EURUSD"},
            {"action": 1, "symbol": "GBPUSD"},
        ]

        def on_each_complete(rid: str, result: MT5Models.OrderResult) -> None:
            pass

        def on_each_error(rid: str, error: Exception) -> None:
            pass

        def on_all_complete(
            results: dict[str, MT5Models.OrderResult | Exception],
        ) -> None:
            pass

        result = mt5.order_send_batch(
            requests, on_each_complete, on_each_error, on_all_complete
        )
        async_mock.order_send_batch.assert_awaited_once_with(
            requests, on_each_complete, on_each_error, on_all_complete
        )
        assert result == ["RQ001", "RQ002"]


class TestPositionAndOrderMethods:
    """Positions / orders / history / market depth delegations."""

    def test_positions_total_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """positions_total() returns the async client's int."""
        mt5, async_mock = mocked_mt5
        async_mock.positions_total = AsyncMock(return_value=2)
        assert mt5.positions_total() == 2

    def test_positions_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """positions_get() passes optional filters."""
        mt5, async_mock = mocked_mt5
        position = MT5Models.Position(ticket=100, symbol="EURUSD")
        async_mock.positions_get = AsyncMock(return_value=(position,))
        result = mt5.positions_get(symbol="EURUSD", group="*", ticket=100)
        async_mock.positions_get.assert_awaited_once_with(
            symbol="EURUSD", group="*", ticket=100
        )
        assert result == (position,)

    def test_orders_total_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """orders_total() returns the async client's int."""
        mt5, async_mock = mocked_mt5
        async_mock.orders_total = AsyncMock(return_value=3)
        assert mt5.orders_total() == 3

    def test_orders_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """orders_get() passes optional filters."""
        mt5, async_mock = mocked_mt5
        order = MT5Models.Order(ticket=200, symbol="EURUSD")
        async_mock.orders_get = AsyncMock(return_value=(order,))
        result = mt5.orders_get(symbol="EURUSD", group="*", ticket=200)
        async_mock.orders_get.assert_awaited_once_with(
            symbol="EURUSD", group="*", ticket=200
        )
        assert result == (order,)

    def test_history_orders_total_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """history_orders_total() passes date range."""
        mt5, async_mock = mocked_mt5
        async_mock.history_orders_total = AsyncMock(return_value=5)
        assert mt5.history_orders_total(0, 1) == 5
        async_mock.history_orders_total.assert_awaited_once_with(0, 1)

    def test_history_orders_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """history_orders_get() passes optional filters."""
        mt5, async_mock = mocked_mt5
        order = MT5Models.Order(ticket=300)
        async_mock.history_orders_get = AsyncMock(return_value=(order,))
        result = mt5.history_orders_get(
            date_from=0, date_to=1, group="*", ticket=300, position=10
        )
        async_mock.history_orders_get.assert_awaited_once_with(
            date_from=0, date_to=1, group="*", ticket=300, position=10
        )
        assert result == (order,)

    def test_history_deals_total_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """history_deals_total() passes date range."""
        mt5, async_mock = mocked_mt5
        async_mock.history_deals_total = AsyncMock(return_value=4)
        assert mt5.history_deals_total(0, 1) == 4
        async_mock.history_deals_total.assert_awaited_once_with(0, 1)

    def test_history_deals_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """history_deals_get() passes optional filters."""
        mt5, async_mock = mocked_mt5
        deal = MT5Models.Deal(ticket=400)
        async_mock.history_deals_get = AsyncMock(return_value=(deal,))
        result = mt5.history_deals_get(
            date_from=0, date_to=1, group="*", ticket=400, position=20
        )
        async_mock.history_deals_get.assert_awaited_once_with(
            date_from=0, date_to=1, group="*", ticket=400, position=20
        )
        assert result == (deal,)

    def test_market_book_add_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """market_book_add() passes the symbol."""
        mt5, async_mock = mocked_mt5
        async_mock.market_book_add = AsyncMock(return_value=True)
        assert mt5.market_book_add("EURUSD") is True
        async_mock.market_book_add.assert_awaited_once_with("EURUSD")

    def test_market_book_get_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """market_book_get() passes the symbol."""
        mt5, async_mock = mocked_mt5
        entry = MT5Models.BookEntry(type=0, price=1.1)
        async_mock.market_book_get = AsyncMock(return_value=(entry,))
        result = mt5.market_book_get("EURUSD")
        async_mock.market_book_get.assert_awaited_once_with("EURUSD")
        assert result == (entry,)

    def test_market_book_release_delegates(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """market_book_release() passes the symbol."""
        mt5, async_mock = mocked_mt5
        async_mock.market_book_release = AsyncMock(return_value=True)
        assert mt5.market_book_release("EURUSD") is True
        async_mock.market_book_release.assert_awaited_once_with("EURUSD")


class TestEventLoopReuse:
    """Event loop management for the sync wrapper."""

    def test_run_creates_loop_on_first_use(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """_get_loop() creates a new loop when none exists."""
        mt5, _async_mock = mocked_mt5
        assert mt5._loop is None
        loop = mt5._get_loop()
        assert loop is not None
        assert mt5._loop is loop

    def test_run_reuses_open_loop(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """_get_loop() returns the existing loop if still open."""
        mt5, _async_mock = mocked_mt5
        loop1 = mt5._get_loop()
        loop2 = mt5._get_loop()
        assert loop1 is loop2

    def test_run_replaces_closed_loop(
        self, mocked_mt5: tuple[MetaTrader5, MagicMock]
    ) -> None:
        """_get_loop() creates a new loop if the current one is closed."""
        mt5, _async_mock = mocked_mt5
        loop1 = mt5._get_loop()
        loop1.close()
        loop2 = mt5._get_loop()
        assert loop2 is not loop1
        assert not loop2.is_closed()


class TestConstructionWithSettings:
    """Default construction values."""

    def test_default_host_and_port_from_settings(self) -> None:
        """Default constructor values are propagated to the async client."""
        mt5 = MetaTrader5()
        assert mt5._async_client._host == "localhost"
        assert mt5._async_client._port == 8001
        assert mt5._async_client._timeout == 300

    def test_explicit_constructor_values(self) -> None:
        """Explicit host/port/timeout override defaults."""
        mt5 = MetaTrader5(host="custom", port=12345, timeout=30)
        assert mt5._async_client._host == "custom"
        assert mt5._async_client._port == 12345
        assert mt5._async_client._timeout == 30
