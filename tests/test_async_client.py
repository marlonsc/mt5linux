"""Async client tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mt5linux.async_client import AsyncMetaTrader5


class TestAsyncMetaTrader5Unit:
    """Unit tests for AsyncMetaTrader5 (no server required)."""

    def test_init_default_values(self) -> None:
        """Test default initialization values."""
        client = AsyncMetaTrader5()
        assert client._host == "localhost"
        assert client._port == 18812
        assert client._timeout == 300
        assert client._connected is False
        assert client._sync_client is None

    def test_init_custom_values(self) -> None:
        """Test custom initialization values."""
        client = AsyncMetaTrader5(
            host="192.168.1.100",
            port=8001,
            timeout=600,
            max_workers=8,
        )
        assert client._host == "192.168.1.100"
        assert client._port == 8001
        assert client._timeout == 600

    @pytest.mark.asyncio
    async def test_connect_creates_sync_client(self) -> None:
        """Test connect creates sync client."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()

            mock_mt5.assert_called_once_with("localhost", 18812, 300)
            assert client._connected is True
            assert client._sync_client is mock_instance

    @pytest.mark.asyncio
    async def test_connect_idempotent(self) -> None:
        """Test connect is idempotent."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()
            await client.connect()  # Second call should not create new client

            mock_mt5.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self) -> None:
        """Test disconnect cleans up resources."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()
            await client.disconnect()

            mock_instance.shutdown.assert_called_once()
            mock_instance.close.assert_called_once()
            assert client._connected is False
            assert client._sync_client is None

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_mt5.return_value = mock_instance

            async with AsyncMetaTrader5() as client:
                assert client._connected is True
                assert client._sync_client is mock_instance

            mock_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_calls_sync_client(self) -> None:
        """Test initialize delegates to sync client."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_instance.initialize.return_value = True
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()
            result = await client.initialize(login=12345, password="pass")

            assert result is True
            mock_instance.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_send_delegates(self) -> None:
        """Test order_send delegates to sync client."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_result = MagicMock()
            mock_result.retcode = 10009
            mock_instance = MagicMock()
            mock_instance.order_send.return_value = mock_result
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()
            request = {"action": 1, "symbol": "EURUSD", "volume": 0.1}
            result = await client.order_send(request)

            assert result.retcode == 10009
            mock_instance.order_send.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_getattr_proxies_constants(self) -> None:
        """Test __getattr__ proxies MT5 constants."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_instance.TIMEFRAME_H1 = 16385
            mock_instance.ORDER_TYPE_BUY = 0
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()

            assert client.TIMEFRAME_H1 == 16385
            assert client.ORDER_TYPE_BUY == 0

    @pytest.mark.asyncio
    async def test_getattr_raises_before_connect(self) -> None:
        """Test __getattr__ raises AttributeError before connect."""
        client = AsyncMetaTrader5()
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = client.TIMEFRAME_H1


class TestAsyncMetaTrader5Concurrent:
    """Test concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_symbol_info(self) -> None:
        """Test concurrent symbol info calls."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()

            def mock_symbol_info(symbol: str) -> MagicMock:
                result = MagicMock()
                result.name = symbol
                return result

            mock_instance.symbol_info.side_effect = mock_symbol_info
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()

            symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            tasks = [client.symbol_info(s) for s in symbols]
            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            assert results[0].name == "EURUSD"
            assert results[1].name == "GBPUSD"
            assert results[2].name == "USDJPY"

    @pytest.mark.asyncio
    async def test_concurrent_data_fetching(self) -> None:
        """Test concurrent data fetching with gather."""
        with patch("mt5linux.async_client.MetaTrader5") as mock_mt5:
            mock_instance = MagicMock()
            mock_instance.account_info.return_value = MagicMock(balance=10000)
            mock_instance.symbol_info.return_value = MagicMock(bid=1.1)
            mock_instance.symbol_info_tick.return_value = MagicMock(ask=1.1001)
            mock_mt5.return_value = mock_instance

            client = AsyncMetaTrader5()
            await client.connect()

            # Parallel fetching like neptor's AsyncMT5Bridge
            account, symbol, tick = await asyncio.gather(
                client.account_info(),
                client.symbol_info("EURUSD"),
                client.symbol_info_tick("EURUSD"),
            )

            assert account.balance == 10000
            assert symbol.bid == 1.1
            assert tick.ask == 1.1001
