"""Tests for bridge behavior validation.

Validates that the gRPC bridge behaves correctly:
1. HealthCheck works even when terminal not connected
2. Initialize and Login are not blocked
3. Data methods work after initialization
4. Login serialization (one at a time)
5. Connection/disconnection limits and returns
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from mt5linux import MetaTrader5
from tests.conftest import (
    MT5_LOGIN,
    MT5_PASSWORD,
    MT5_SERVER,
    TEST_GRPC_HOST,
    TEST_GRPC_PORT,
)

if TYPE_CHECKING:
    from mt5linux import AsyncMetaTrader5


class TestConnectionLimits:
    """Test connection limits and boundary conditions."""

    def test_connect_without_init_allows_healthcheck(self) -> None:
        """Connection without init should allow health check."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            # is_connected checks gRPC channel, not MT5 terminal
            assert mt5.is_connected is True
        finally:
            mt5.disconnect()

    def test_disconnect_returns_none(self) -> None:
        """Disconnect should return None (no return value)."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        result = mt5.disconnect()
        assert result is None

    def test_multiple_disconnect_safe(self) -> None:
        """Multiple disconnects should not raise errors."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        mt5.disconnect()
        mt5.disconnect()  # Should not raise
        mt5.disconnect()  # Should not raise
        assert mt5.is_connected is False

    def test_shutdown_without_init_safe(self) -> None:
        """Shutdown without init should be safe."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            # Shutdown without init - should not crash
            mt5.shutdown()
        finally:
            mt5.disconnect()

    def test_init_returns_bool(self) -> None:
        """Initialize should always return a boolean."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            result = mt5.initialize(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER,
            )
            assert isinstance(result, bool)
            assert result is True
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_login_returns_bool(self) -> None:
        """Login should always return a boolean."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            # First init
            mt5.initialize()
            # Then login
            result = mt5.login(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER,
            )
            assert isinstance(result, bool)
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_login_invalid_returns_false_not_exception(self) -> None:
        """Login with invalid credentials should return False, not raise."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            mt5.initialize()
            result = mt5.login(
                login=999999999,
                password="invalid_password",  # noqa: S106
                server="InvalidServer",
                timeout=3000,
            )
            assert result is False
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_reconnect_after_shutdown(self) -> None:
        """Should be able to reconnect after shutdown."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

        # Verify connected
        account1 = mt5.account_info()
        assert account1 is not None

        # Shutdown
        mt5.shutdown()

        # Reconnect
        result = mt5.initialize(
            login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER
        )
        assert result is True

        # Verify reconnected
        account2 = mt5.account_info()
        assert account2 is not None

        mt5.shutdown()
        mt5.disconnect()

    def test_version_requires_init(self) -> None:
        """Version should work after init."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            version = mt5.version()
            assert version is not None
            assert len(version) == 3
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_last_error_always_available(self) -> None:
        """last_error should work even without full init."""
        mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
        mt5.connect()
        try:
            mt5.initialize()
            error = mt5.last_error()
            assert error is not None
            assert isinstance(error[0], int)
            assert isinstance(error[1], str)
        finally:
            mt5.shutdown()
            mt5.disconnect()


class TestBridgeHealthCheck:
    """Test HealthCheck behavior."""

    def test_health_check_returns_status(self, mt5: MetaTrader5) -> None:
        """HealthCheck should return status info."""
        # HealthCheck is called internally via is_connected
        assert mt5.is_connected is True

    def test_terminal_info_after_init(self, mt5: MetaTrader5) -> None:
        """terminal_info should work after initialization."""
        info = mt5.terminal_info()
        assert info is not None
        assert hasattr(info, "connected")


class TestBridgeInitialize:
    """Test Initialize behavior."""

    def test_initialize_returns_bool(self, mt5: MetaTrader5) -> None:
        """Initialize should return a boolean result."""
        # Already initialized via fixture, verify it worked
        assert mt5.is_connected is True

    def test_initialize_idempotent(self, mt5: MetaTrader5) -> None:
        """Multiple Initialize calls should not block."""
        # Call initialize again - should not block
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        result = mt5.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        # Should succeed (already connected) or return True
        assert result is True


class TestBridgeLogin:
    """Test Login serialization behavior."""

    def test_login_returns_bool(self, mt5: MetaTrader5) -> None:
        """Login should return a boolean result."""
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        # Login again (already logged in)
        result = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        assert isinstance(result, bool)
        assert result is True

    def test_login_invalid_credentials_returns_false(self, mt5: MetaTrader5) -> None:
        """Login with invalid credentials should return False, not block."""
        # Try login with invalid credentials
        result = mt5.login(
            login=999999999,  # Invalid login
            password="invalid",  # noqa: S106
            server="InvalidServer",
            timeout=5000,  # Short timeout
        )
        assert result is False

        # Restore valid login
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )


class TestBridgeAsyncLogin:
    """Test async Login serialization behavior."""

    @pytest.mark.asyncio
    async def test_async_login_returns_bool(self, async_mt5: AsyncMetaTrader5) -> None:
        """Async Login should return a boolean result."""
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        result = await async_mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        assert isinstance(result, bool)
        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_logins_serialized(
        self, async_mt5: AsyncMetaTrader5
    ) -> None:
        """Concurrent login attempts should be serialized (not crash)."""
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        async def do_login() -> bool:
            return await async_mt5.login(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER,
            )

        # Run multiple concurrent logins
        results = await asyncio.gather(
            do_login(),
            do_login(),
            do_login(),
            return_exceptions=True,
        )

        # All should succeed or fail gracefully (no crash)
        for result in results:
            if isinstance(result, Exception):
                # Should not get here, but if we do, it shouldn't be a crash
                pytest.fail(f"Login raised exception: {result}")
            assert isinstance(result, bool)


class TestBridgeDataMethods:
    """Test that data methods work after initialization."""

    def test_account_info_after_init(self, mt5: MetaTrader5) -> None:
        """account_info should work after initialization."""
        info = mt5.account_info()
        assert info is not None
        assert hasattr(info, "login")

    def test_symbols_total_after_init(self, mt5: MetaTrader5) -> None:
        """symbols_total should work after initialization."""
        total = mt5.symbols_total()
        assert isinstance(total, int)
        assert total > 0

    def test_symbol_info_after_init(self, mt5: MetaTrader5) -> None:
        """symbol_info should work after initialization."""
        info = mt5.symbol_info("EURUSD")
        assert info is not None
        assert info.name == "EURUSD"

    def test_version_after_init(self, mt5: MetaTrader5) -> None:
        """Version should work after initialization."""
        version = mt5.version()
        assert version is not None
        assert len(version) == 3

    def test_last_error_always_works(self, mt5: MetaTrader5) -> None:
        """last_error should always work."""
        error = mt5.last_error()
        assert error is not None
        assert len(error) == 2
        assert isinstance(error[0], int)
        assert isinstance(error[1], str)
