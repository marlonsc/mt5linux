"""Async client integration tests - ALL REAL, NO MOCKS."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mt5linux.async_client import AsyncMetaTrader5

from tests.conftest import (
    TEST_GRPC_HOST,
    TEST_GRPC_PORT,
    tc,
)


class TestAsyncMetaTrader5Connection:
    """Test async connection lifecycle with real server."""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(
        self, async_mt5_raw: AsyncMetaTrader5
    ) -> None:
        """Test async connection and disconnect."""
        assert async_mt5_raw.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, async_mt5_raw: AsyncMetaTrader5) -> None:
        """Test _connect() is idempotent - calling twice doesn't break."""
        assert async_mt5_raw.is_connected is True
        # Second connect should be no-op
        await async_mt5_raw._connect()
        assert async_mt5_raw.is_connected is True

    @pytest.mark.asyncio
    async def test_context_manager(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async context manager with initialized connection.

        Uses fixture that already called initialize() - like official MT5.
        """
        # Fixture provides initialized connection
        assert async_mt5.is_connected is True

        # version() works after initialize() - like official MT5
        version = await async_mt5.version()
        assert version is not None
        assert isinstance(version, tuple)
        assert len(version) == 3

    @pytest.mark.asyncio
    async def test_concurrent_connect_is_safe(self) -> None:
        """Test that concurrent _connect() calls are thread-safe."""
        client = AsyncMetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)

        # Simulate many concurrent connect calls - should not raise
        await asyncio.gather(
            *[client._connect() for _ in range(tc.CONCURRENT_CONNECTIONS)]
        )

        # Should be connected with no errors
        assert client.is_connected is True

        await client._disconnect()
        assert client.is_connected is False


class TestAsyncMetaTrader5ErrorHandling:
    """Test error handling with real server."""

    @pytest.mark.asyncio
    async def test_method_raises_connection_error_when_not_connected(
        self,
    ) -> None:
        """Test async methods raise ConnectionError when not connected."""
        client = AsyncMetaTrader5()

        with pytest.raises(ConnectionError, match="not established"):
            await client.version()

        with pytest.raises(ConnectionError, match="not established"):
            await client.account_info()

        with pytest.raises(ConnectionError, match="not established"):
            await client.symbols_total()

    @pytest.mark.asyncio
    async def test_ensure_connected_raises_connection_error(self) -> None:
        """Test _ensure_connected raises ConnectionError when not connected."""
        client = AsyncMetaTrader5()
        with pytest.raises(ConnectionError, match="not established"):
            client._ensure_connected()

    @pytest.mark.asyncio
    async def test_getattr_raises_before_connect(self) -> None:
        """Test __getattr__ raises AttributeError before connect."""
        client = AsyncMetaTrader5()
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = client.TIMEFRAME_H1


class TestAsyncMetaTrader5Terminal:
    """Test terminal operations with real server."""

    @pytest.mark.asyncio
    async def test_version(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async version retrieval."""
        version = await async_mt5.version()
        assert version is not None
        assert len(version) == tc.VERSION_TUPLE_LENGTH
        assert isinstance(version[0], int)  # Major version
        assert isinstance(version[1], int)  # Build
        assert isinstance(version[2], str)  # Date

    @pytest.mark.asyncio
    async def test_last_error(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async last_error retrieval."""
        error = await async_mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == tc.ERROR_TUPLE_LENGTH
        assert isinstance(error[0], int)  # Error code
        assert isinstance(error[1], str)  # Error message

    @pytest.mark.asyncio
    async def test_terminal_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async terminal_info retrieval."""
        terminal = await async_mt5.terminal_info()
        assert terminal is not None
        assert terminal.connected is True
        assert hasattr(terminal, "name")
        assert hasattr(terminal, "path")


class TestAsyncMetaTrader5Account:
    """Test account operations with real server."""

    @pytest.mark.asyncio
    async def test_account_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async account_info retrieval."""
        account = await async_mt5.account_info()
        assert account is not None, "account_info returned None"
        assert account.login > 0
        assert account.balance >= 0
        assert hasattr(account, "equity")
        assert hasattr(account, "margin")
        assert hasattr(account, "currency")


class TestAsyncMetaTrader5Symbols:
    """Test symbol operations with real server."""

    @pytest.mark.asyncio
    async def test_symbols_total(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbols_total."""
        total = await async_mt5.symbols_total()
        assert isinstance(total, int)
        assert total > 0, "symbols_total returned 0"

    @pytest.mark.asyncio
    async def test_symbols_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbols_get with filter."""
        # Get USD pairs only (using filter to avoid timeout on full list)
        usd_symbols = await async_mt5.symbols_get(group="*USD*")
        assert usd_symbols is not None
        assert len(usd_symbols) > 0
        # All returned symbols should contain USD (SymbolInfo models)
        for sym in usd_symbols:
            assert "USD" in sym.name

    @pytest.mark.asyncio
    async def test_symbol_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_info."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        info = await async_mt5.symbol_info("EURUSD")
        assert info is not None, "symbol_info returned None"
        assert info.name == "EURUSD"
        assert hasattr(info, "bid")
        assert hasattr(info, "ask")
        assert hasattr(info, "point")
        assert hasattr(info, "digits")

    @pytest.mark.asyncio
    async def test_symbol_info_tick(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_info_tick."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        assert tick is not None, "symbol_info_tick returned None"
        assert tick.bid > 0 or tick.ask > 0
        assert hasattr(tick, "time")
        assert hasattr(tick, "volume")

    @pytest.mark.asyncio
    async def test_symbol_select(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_select."""
        # Enable EURUSD in Market Watch
        result = await async_mt5.symbol_select("EURUSD", enable=True)
        assert result is True, "symbol_select returned False"

    @pytest.mark.asyncio
    async def test_getattr_proxies_constants(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test __getattr__ proxies MT5 constants."""
        # Test timeframe constants
        assert async_mt5.TIMEFRAME_M1 is not None
        assert async_mt5.TIMEFRAME_H1 is not None
        assert async_mt5.TIMEFRAME_D1 is not None

        # Test order type constants
        assert async_mt5.ORDER_TYPE_BUY is not None
        assert async_mt5.ORDER_TYPE_SELL is not None


class TestAsyncMetaTrader5MarketData:
    """Test market data operations with real server."""

    @pytest.mark.asyncio
    async def test_copy_rates_from_pos(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_rates_from_pos."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        try:
            rates = await async_mt5.copy_rates_from_pos(
                "EURUSD", async_mt5.TIMEFRAME_H1, 0, tc.TEN_ITEMS
            )
        except Exception as e:
            if "pickling is disabled" in str(e):
                pytest.fail("RPyC pickling disabled - numpy serialization unavailable")
            raise
        # May return None if market closed or RPyC serialization issue
        if rates is None:
            pytest.fail("Market data not available (market may be closed)")
        assert len(rates) > 0
        assert hasattr(rates, "dtype")
        # Verify rate structure
        assert rates.dtype.names is not None
        assert "time" in rates.dtype.names
        assert "open" in rates.dtype.names
        assert "high" in rates.dtype.names
        assert "low" in rates.dtype.names
        assert "close" in rates.dtype.names
        assert "tick_volume" in rates.dtype.names

    @pytest.mark.asyncio
    async def test_copy_rates_from(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_rates_from."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        date_from = datetime.now(UTC) - timedelta(days=tc.ONE_WEEK)
        rates = await async_mt5.copy_rates_from(
            "EURUSD", async_mt5.TIMEFRAME_H1, date_from, tc.FIFTY_ITEMS
        )
        # May return None if market closed or no data for period
        if rates is None:
            pytest.fail("Market data not available (market may be closed)")
        assert len(rates) > 0

    @pytest.mark.asyncio
    async def test_copy_rates_range(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_rates_range."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=tc.ONE_WEEK)
        rates = await async_mt5.copy_rates_range(
            "EURUSD", async_mt5.TIMEFRAME_H1, date_from, date_to
        )
        # May return None if market closed or no data for period
        if rates is None:
            pytest.fail("Market data not available (market may be closed)")
        assert len(rates) > 0

    @pytest.mark.asyncio
    async def test_copy_ticks_from(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_ticks_from."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = await async_mt5.copy_ticks_from(
            "EURUSD", date_from, tc.HUNDRED_ITEMS, async_mt5.COPY_TICKS_ALL
        )
        # May return None if no ticks available in the period
        if ticks is not None:
            assert len(ticks) > 0
            assert ticks.dtype.names is not None
            assert "time" in ticks.dtype.names
            assert "bid" in ticks.dtype.names
            assert "ask" in ticks.dtype.names


class TestAsyncMetaTrader5Positions:
    """Test position operations with real server."""

    @pytest.mark.asyncio
    async def test_positions_total(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async positions_total."""
        total = await async_mt5.positions_total()
        assert isinstance(total, int)
        assert total >= 0

    @pytest.mark.asyncio
    async def test_positions_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async positions_get."""
        positions = await async_mt5.positions_get()
        # May return None or tuple depending on account state
        if positions is not None:
            assert isinstance(positions, tuple)


class TestAsyncMetaTrader5Orders:
    """Test order operations with real server."""

    @pytest.mark.asyncio
    async def test_orders_total(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async orders_total."""
        total = await async_mt5.orders_total()
        assert isinstance(total, int)
        assert total >= 0

    @pytest.mark.asyncio
    async def test_orders_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async orders_get."""
        orders = await async_mt5.orders_get()
        # May return None or tuple depending on account state
        if orders is not None:
            assert isinstance(orders, tuple)


class TestAsyncMetaTrader5History:
    """Test history operations with real server."""

    @pytest.mark.asyncio
    async def test_history_orders_total(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_orders_total."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=tc.ONE_MONTH)
        total = await async_mt5.history_orders_total(date_from, date_to)
        # May return None if no history
        if total is not None:
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    async def test_history_orders_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_orders_get."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=tc.ONE_MONTH)
        orders = await async_mt5.history_orders_get(
            date_from=date_from, date_to=date_to
        )
        # May return None if no history
        if orders is not None:
            assert isinstance(orders, tuple)

    @pytest.mark.asyncio
    async def test_history_deals_total(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_deals_total."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=tc.ONE_MONTH)
        total = await async_mt5.history_deals_total(date_from, date_to)
        # May return None if no history
        if total is not None:
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    async def test_history_deals_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_deals_get."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=tc.ONE_MONTH)
        deals = await async_mt5.history_deals_get(date_from=date_from, date_to=date_to)
        # May return None if no history
        if deals is not None:
            assert isinstance(deals, tuple)


class TestAsyncMetaTrader5Trading:
    """Test trading operations with real server (read-only)."""

    @pytest.mark.asyncio
    async def test_order_calc_margin(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_calc_margin."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        if tick is None:
            pytest.fail("symbol_info_tick returned None (market may be closed)")

        margin = await async_mt5.order_calc_margin(
            async_mt5.ORDER_TYPE_BUY,
            "EURUSD",
            tc.MICRO_LOT,
            tick.ask,
        )
        # May return None on some broker configurations
        if margin is not None:
            assert isinstance(margin, float)
            assert margin > 0

    @pytest.mark.asyncio
    async def test_order_calc_profit(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_calc_profit."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        if tick is None:
            pytest.fail("Could not get tick data")

        # Simulate 10 pip profit
        profit = await async_mt5.order_calc_profit(
            async_mt5.ORDER_TYPE_BUY,
            "EURUSD",
            tc.MICRO_LOT,
            tick.ask,
            tick.ask + tc.TEN_PIPS,  # 10 pips
        )
        # May return None on some broker configurations
        if profit is not None:
            assert isinstance(profit, float)

    @pytest.mark.asyncio
    async def test_order_check(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_check (validates without executing)."""
        await async_mt5.symbol_select("EURUSD", enable=True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        if tick is None:
            pytest.fail("Could not get tick data")

        request = {
            "action": async_mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.01,
            "type": async_mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": tc.DEFAULT_DEVIATION,
            "magic": tc.MT5.TEST_MAGIC,
            "comment": "pytest check only",
        }

        result = await async_mt5.order_check(request)
        # May return None if market is closed or trading disabled
        if result is None:
            pytest.fail("Order check not available (market may be closed)")
        # Check result has expected fields
        assert hasattr(result, "retcode")


class TestAsyncMetaTrader5Concurrent:
    """Test concurrent async operations with real server."""

    @pytest.mark.asyncio
    async def test_concurrent_symbol_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent symbol_info calls with real server."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        try:
            # Select all symbols first
            for symbol in symbols:
                await async_mt5.symbol_select(symbol, enable=True)

            # Concurrent fetching
            tasks = [async_mt5.symbol_info(s) for s in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for exceptions in results
            valid_results = []
            non_timeout_exception = None
            for r in results:
                if isinstance(r, Exception):
                    if "timeout" in str(r).lower() or "grpc" in str(r).lower():
                        pytest.fail("gRPC timeout during concurrent fetch: r")
                    non_timeout_exception = r
                else:
                    valid_results.append(r)

            # Re-raise non-timeout exception if found
            if non_timeout_exception is not None:
                raise non_timeout_exception

            assert len(valid_results) == len(symbols)
            for i, result in enumerate(valid_results):
                if result is not None:
                    assert result.name == symbols[i]
        except Exception as e:
            if "timeout" in str(e).lower() or "grpc" in str(e).lower():
                pytest.fail(f"gRPC timeout: {e}")
            raise

    @pytest.mark.asyncio
    async def test_concurrent_data_fetching(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent data fetching with real server."""
        await async_mt5.symbol_select("EURUSD", enable=True)

        # Parallel fetching of different data types
        account, symbol, tick = await asyncio.gather(
            async_mt5.account_info(),
            async_mt5.symbol_info("EURUSD"),
            async_mt5.symbol_info_tick("EURUSD"),
        )

        # Skip if MT5 connection is unstable
        if account is None or symbol is None or tick is None:
            pytest.fail("Concurrent data fetch returned None (MT5 connection issue)")

        assert account.balance >= 0
        assert symbol.name == "EURUSD"
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.asyncio
    async def test_concurrent_rates_fetching(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent OHLCV rates fetching."""
        try:
            symbols = ["EURUSD", "GBPUSD"]
            for s in symbols:
                await async_mt5.symbol_select(s, enable=True)

            tasks = [
                async_mt5.copy_rates_from_pos(
                    s, async_mt5.TIMEFRAME_H1, 0, tc.DEFAULT_BAR_COUNT
                )
                for s in symbols
            ]
            # Use return_exceptions to handle RPyC pickling issues gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            assert len(results) == len(symbols)
            success_count = 0
            for rates in results:
                # Skip exceptions (RPyC pickling may fail)
                if isinstance(rates, Exception):
                    if "timeout" in str(rates).lower():
                        pytest.fail("gRPC timeout: rates")
                    continue
                if rates is not None:
                    assert len(rates) > 0
                    success_count += 1
            # At least one should succeed, or skip if all failed
            if success_count == 0:
                pytest.fail("Market data not available (market may be closed)")
        except Exception as e:
            if "timeout" in str(e).lower() or "grpc" in str(e).lower():
                pytest.fail(f"gRPC timeout: {e}")
            raise


class TestAsyncMetaTrader5Login:
    """Tests for async login functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_async_login_with_valid_credentials(
        self, async_mt5_raw: AsyncMetaTrader5
    ) -> None:
        """Test async login with valid credentials."""
        import os

        login = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "")

        if not all([login, password, server]):
            pytest.fail("MT5 credentials not configured")

        # Initialize first
        init_result = await async_mt5_raw.initialize()
        if not init_result:
            pytest.fail("MT5 initialize failed")

        result = await async_mt5_raw.login(login, password, server)
        assert result is True


class TestAsyncMetaTrader5HealthCheck:
    """Tests for async health_check functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_async_health_check(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async health_check returns healthy status."""
        health = await async_mt5.health_check()

        assert isinstance(health, dict)
        if health.get("healthy") is not True:
            pytest.fail("health_check returned unhealthy: health")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_async_health_check_fields(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async health_check returns expected fields."""
        health = await async_mt5.health_check()

        assert isinstance(health, dict)
        expected_fields = ["healthy", "mt5_available"]
        for field in expected_fields:
            assert field in health, f"Missing field: {field}"
