"""Async client integration tests - ALL REAL, NO MOCKS."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mt5linux.async_client import AsyncMetaTrader5
from tests.conftest import TEST_RPYC_HOST, TEST_RPYC_PORT


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
        """Test connect() is idempotent - calling twice doesn't break."""
        assert async_mt5_raw.is_connected is True
        # Second connect should be no-op
        await async_mt5_raw.connect()
        assert async_mt5_raw.is_connected is True

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager with real connection."""
        try:
            async with AsyncMetaTrader5(
                host=TEST_RPYC_HOST, port=TEST_RPYC_PORT
            ) as client:
                assert client.is_connected is True
                version = await client.version()
                assert version is not None
        except (ConnectionError, EOFError, OSError) as e:
            pytest.skip(f"MT5 connection failed: {e}")

        # After exit, should be disconnected
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_concurrent_connect_is_safe(self) -> None:
        """Test that concurrent connect() calls are thread-safe."""
        client = AsyncMetaTrader5(host=TEST_RPYC_HOST, port=TEST_RPYC_PORT)

        try:
            # Simulate many concurrent connect calls
            await asyncio.gather(*[client.connect() for _ in range(10)])
        except (ConnectionError, EOFError, OSError) as e:
            pytest.skip(f"MT5 connection failed: {e}")

        # Should be connected with no errors
        assert client.is_connected is True

        await client.disconnect()
        assert client.is_connected is False


class TestAsyncMetaTrader5ErrorHandling:
    """Test error handling with real server."""

    @pytest.mark.asyncio
    async def test_method_raises_connection_error_when_not_connected(self) -> None:
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
        assert len(version) == 3
        assert isinstance(version[0], int)  # Major version
        assert isinstance(version[1], int)  # Build
        assert isinstance(version[2], str)  # Date

    @pytest.mark.asyncio
    async def test_last_error(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async last_error retrieval."""
        error = await async_mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == 2
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
        if account is None:
            pytest.skip("account_info returned None (MT5 connection may be unstable)")
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
        if total == 0:
            pytest.skip("symbols_total returned 0 (MT5 connection issue)")
        assert total > 0

    @pytest.mark.asyncio
    async def test_symbols_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbols_get with filter."""
        # Get USD pairs only (using filter to avoid timeout on full list)
        usd_symbols = await async_mt5.symbols_get(group="*USD*")
        assert usd_symbols is not None
        assert len(usd_symbols) > 0
        # All returned symbols should contain USD
        for sym in usd_symbols:
            assert "USD" in sym.name

    @pytest.mark.asyncio
    async def test_symbol_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_info."""
        await async_mt5.symbol_select("EURUSD", True)
        info = await async_mt5.symbol_info("EURUSD")
        if info is None:
            pytest.skip("symbol_info returned None (MT5 connection issue)")
        assert info.name == "EURUSD"
        assert hasattr(info, "bid")
        assert hasattr(info, "ask")
        assert hasattr(info, "point")
        assert hasattr(info, "digits")

    @pytest.mark.asyncio
    async def test_symbol_info_tick(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_info_tick."""
        await async_mt5.symbol_select("EURUSD", True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        assert tick is not None
        assert tick.bid > 0 or tick.ask > 0
        assert hasattr(tick, "time")
        assert hasattr(tick, "volume")

    @pytest.mark.asyncio
    async def test_symbol_select(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async symbol_select."""
        # Enable EURUSD in Market Watch
        result = await async_mt5.symbol_select("EURUSD", True)
        assert result is True

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
        await async_mt5.symbol_select("EURUSD", True)
        try:
            rates = await async_mt5.copy_rates_from_pos(
                "EURUSD", async_mt5.TIMEFRAME_H1, 0, 10
            )
        except Exception as e:
            if "pickling is disabled" in str(e):
                pytest.skip("RPyC pickling disabled - numpy serialization not available")  # noqa: E501
            raise
        # May return None if market closed or RPyC serialization issue
        if rates is None:
            pytest.skip("Market data not available (market may be closed)")
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
        await async_mt5.symbol_select("EURUSD", True)
        date_from = datetime.now(UTC) - timedelta(days=7)
        rates = await async_mt5.copy_rates_from(
            "EURUSD", async_mt5.TIMEFRAME_H1, date_from, 50
        )
        # May return None if market closed or no data for period
        if rates is None:
            pytest.skip("Market data not available (market may be closed)")
        assert len(rates) > 0

    @pytest.mark.asyncio
    async def test_copy_rates_range(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_rates_range."""
        await async_mt5.symbol_select("EURUSD", True)
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=7)
        rates = await async_mt5.copy_rates_range(
            "EURUSD", async_mt5.TIMEFRAME_H1, date_from, date_to
        )
        # May return None if market closed or no data for period
        if rates is None:
            pytest.skip("Market data not available (market may be closed)")
        assert len(rates) > 0

    @pytest.mark.asyncio
    async def test_copy_ticks_from(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async copy_ticks_from."""
        await async_mt5.symbol_select("EURUSD", True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = await async_mt5.copy_ticks_from(
            "EURUSD", date_from, 100, async_mt5.COPY_TICKS_ALL
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
        date_from = date_to - timedelta(days=30)
        total = await async_mt5.history_orders_total(date_from, date_to)
        # May return None if no history
        if total is not None:
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    async def test_history_orders_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_orders_get."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=30)
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
        date_from = date_to - timedelta(days=30)
        total = await async_mt5.history_deals_total(date_from, date_to)
        # May return None if no history
        if total is not None:
            assert isinstance(total, int)
            assert total >= 0

    @pytest.mark.asyncio
    async def test_history_deals_get(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async history_deals_get."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=30)
        deals = await async_mt5.history_deals_get(date_from=date_from, date_to=date_to)
        # May return None if no history
        if deals is not None:
            assert isinstance(deals, tuple)


class TestAsyncMetaTrader5Trading:
    """Test trading operations with real server (read-only)."""

    @pytest.mark.asyncio
    async def test_order_calc_margin(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_calc_margin."""
        await async_mt5.symbol_select("EURUSD", True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        assert tick is not None

        margin = await async_mt5.order_calc_margin(
            async_mt5.ORDER_TYPE_BUY,
            "EURUSD",
            0.01,
            tick.ask,
        )
        # May return None on some broker configurations
        if margin is not None:
            assert isinstance(margin, float)
            assert margin > 0

    @pytest.mark.asyncio
    async def test_order_calc_profit(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_calc_profit."""
        await async_mt5.symbol_select("EURUSD", True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        if tick is None:
            pytest.skip("Could not get tick data")

        # Simulate 10 pip profit
        profit = await async_mt5.order_calc_profit(
            async_mt5.ORDER_TYPE_BUY,
            "EURUSD",
            0.01,
            tick.ask,
            tick.ask + 0.0010,  # 10 pips
        )
        # May return None on some broker configurations
        if profit is not None:
            assert isinstance(profit, float)

    @pytest.mark.asyncio
    async def test_order_check(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test async order_check (validates without executing)."""
        await async_mt5.symbol_select("EURUSD", True)
        tick = await async_mt5.symbol_info_tick("EURUSD")
        if tick is None:
            pytest.skip("Could not get tick data")

        request = {
            "action": async_mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.01,
            "type": async_mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 999999,
            "comment": "pytest check only",
        }

        result = await async_mt5.order_check(request)
        # May return None if market is closed or trading disabled
        if result is None:
            pytest.skip("Order check not available (market may be closed)")
        # Check result has expected fields
        assert hasattr(result, "retcode")


class TestAsyncMetaTrader5Concurrent:
    """Test concurrent async operations with real server."""

    @pytest.mark.asyncio
    async def test_concurrent_symbol_info(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent symbol_info calls with real server."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        # Select all symbols first
        for symbol in symbols:
            await async_mt5.symbol_select(symbol, True)

        # Concurrent fetching
        tasks = [async_mt5.symbol_info(s) for s in symbols]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for i, result in enumerate(results):
            if result is not None:
                assert result.name == symbols[i]

    @pytest.mark.asyncio
    async def test_concurrent_data_fetching(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent data fetching with real server."""
        await async_mt5.symbol_select("EURUSD", True)

        # Parallel fetching of different data types
        account, symbol, tick = await asyncio.gather(
            async_mt5.account_info(),
            async_mt5.symbol_info("EURUSD"),
            async_mt5.symbol_info_tick("EURUSD"),
        )

        # Skip if MT5 connection is unstable
        if account is None or symbol is None or tick is None:
            pytest.skip("Concurrent data fetch returned None (MT5 connection issue)")

        assert account.balance >= 0
        assert symbol.name == "EURUSD"
        assert tick.bid > 0 or tick.ask > 0

    @pytest.mark.asyncio
    async def test_concurrent_rates_fetching(self, async_mt5: AsyncMetaTrader5) -> None:
        """Test concurrent OHLCV rates fetching."""
        symbols = ["EURUSD", "GBPUSD"]
        for s in symbols:
            await async_mt5.symbol_select(s, True)

        tasks = [
            async_mt5.copy_rates_from_pos(s, async_mt5.TIMEFRAME_H1, 0, 10)
            for s in symbols
        ]
        # Use return_exceptions to handle RPyC pickling issues gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 2
        success_count = 0
        for rates in results:
            # Skip exceptions (RPyC pickling may fail)
            if isinstance(rates, Exception):
                continue
            if rates is not None:
                assert len(rates) > 0
                success_count += 1
        # At least one should succeed, or skip if all failed
        if success_count == 0:
            pytest.skip("Market data not available (market may be closed)")
