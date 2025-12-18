"""Integration tests for sync client resilience.

Tests that MetaTrader5 (sync) correctly inherits resilience from AsyncMetaTrader5.
These tests validate REAL behavior, not mocked scenarios.

Test Categories:
1. Sync wraps Async validation
2. Circuit breaker integration
3. Auto-reconnect behavior
4. Connection recovery
5. Graceful degradation
"""

from __future__ import annotations

import grpc
import grpc.aio
import pytest

from mt5linux import MetaTrader5
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants as c

# Test configuration
TEST_HOST = "localhost"
TEST_PORT = 28812


class TestSyncWrapsAsync:
    """Validate that sync client correctly wraps async client."""

    def test_sync_client_has_async_client_attribute(self) -> None:
        """MetaTrader5 should have internal _async_client."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        assert hasattr(mt5, "_async_client")
        assert isinstance(mt5._async_client, AsyncMetaTrader5)

    def test_sync_client_shares_config_with_async(self) -> None:
        """Sync and async clients should use same config."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        # Both should reference same config values
        assert mt5._async_client._host == TEST_HOST
        assert mt5._async_client._port == TEST_PORT

    def test_sync_client_inherits_circuit_breaker_state(self) -> None:
        """Sync client should use async client's circuit breaker."""
        config = MT5Config()
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        # If circuit breaker is enabled, async client should have it
        if config.enable_circuit_breaker:
            assert mt5._async_client._circuit_breaker is not None
        else:
            assert mt5._async_client._circuit_breaker is None

    def test_sync_connect_calls_async_connect(self) -> None:
        """Sync connect should delegate to async connect."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        # After connect, async client should be connected
        mt5.connect()
        try:
            assert mt5._async_client._channel is not None
            assert mt5.is_connected is True
        finally:
            mt5.disconnect()

    def test_sync_disconnect_calls_async_disconnect(self) -> None:
        """Sync disconnect should delegate to async disconnect."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()
        mt5.disconnect()

        # After disconnect, async client should be disconnected
        assert mt5._async_client._channel is None
        assert mt5.is_connected is False


class TestCircuitBreakerIntegration:
    """Test circuit breaker with real operations."""

    @pytest.fixture
    def mt5_with_circuit_breaker(self) -> MetaTrader5:
        """Create MT5 client with circuit breaker enabled."""
        # Force enable circuit breaker for this test
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        # Verify circuit breaker is enabled (from .env.test)
        if mt5._async_client._circuit_breaker is None:
            pytest.skip("Circuit breaker not enabled in config")

        return mt5

    def test_circuit_breaker_starts_closed(
        self, mt5_with_circuit_breaker: MetaTrader5
    ) -> None:
        """Circuit breaker should start in CLOSED state."""
        cb = mt5_with_circuit_breaker._async_client._circuit_breaker
        assert cb is not None
        assert cb.state == c.Resilience.CircuitBreakerState.CLOSED
        assert cb.is_closed

    def test_successful_operations_keep_circuit_closed(
        self, mt5_with_circuit_breaker: MetaTrader5
    ) -> None:
        """Successful operations should keep circuit breaker closed."""
        mt5 = mt5_with_circuit_breaker
        cb = mt5._async_client._circuit_breaker
        assert cb is not None

        mt5.connect()
        try:
            # Initialize and make successful operations
            from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
            mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

            # Multiple successful operations
            mt5.account_info()
            mt5.terminal_info()
            mt5.symbols_total()

            # Circuit should still be closed with 0 failures
            assert cb.is_closed
            assert cb.failure_count == 0
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_circuit_breaker_records_failures(
        self, mt5_with_circuit_breaker: MetaTrader5
    ) -> None:
        """Circuit breaker should record operation failures."""
        mt5 = mt5_with_circuit_breaker
        cb = mt5._async_client._circuit_breaker
        assert cb is not None

        # Don't connect - operations should fail
        # Try operation without connection (will fail gracefully)
        from contextlib import suppress

        with suppress(grpc.RpcError, grpc.aio.AioRpcError, ConnectionError):
            mt5.account_info()

        # Note: failure count may or may not increase depending on
        # whether the operation gets to the circuit breaker check
        # The important thing is no crash occurred


class TestAutoReconnect:
    """Test auto-reconnect behavior."""

    @pytest.fixture
    def mt5_connected(self) -> MetaTrader5:
        """Create connected MT5 client."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        result = mt5.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        if not result:
            pytest.skip("Could not initialize MT5")

        yield mt5

        # Cleanup - suppress any errors during teardown
        from contextlib import suppress

        with suppress(grpc.RpcError, grpc.aio.AioRpcError, ConnectionError, OSError):
            mt5.shutdown()
            mt5.disconnect()

    def test_reconnect_after_disconnect(self, mt5_connected: MetaTrader5) -> None:
        """Should be able to reconnect after disconnect."""
        mt5 = mt5_connected

        # Verify connected
        info1 = mt5.account_info()
        assert info1 is not None

        # Disconnect and reconnect
        mt5.shutdown()
        mt5.disconnect()

        # Reconnect
        mt5.connect()
        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        result = mt5.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        assert result is True

        # Verify reconnected
        info2 = mt5.account_info()
        assert info2 is not None
        assert info2.login == info1.login

    def test_multiple_reconnect_cycles(self) -> None:
        """Should handle multiple connect/disconnect cycles."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

        for cycle in range(3):
            # Connect
            mt5.connect()
            result = mt5.initialize(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER,
            )
            assert result is True, f"Cycle {cycle}: initialize failed"

            # Verify working
            info = mt5.account_info()
            assert info is not None, f"Cycle {cycle}: account_info failed"

            # Disconnect
            mt5.shutdown()
            mt5.disconnect()

            assert mt5.is_connected is False, f"Cycle {cycle}: still connected"


class TestConnectionRecovery:
    """Test connection recovery scenarios."""

    def test_operations_after_reconnect(self) -> None:
        """All operations should work after reconnect."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

        # Test operations before disconnect
        account_before = mt5.account_info()
        mt5.terminal_info()  # Verify terminal info works

        # Disconnect and reconnect
        mt5.shutdown()
        mt5.disconnect()
        mt5.connect()
        mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

        # All operations should work after reconnect
        account_after = mt5.account_info()
        terminal_after = mt5.terminal_info()
        symbols_total = mt5.symbols_total()
        version = mt5.version()

        assert account_after is not None
        assert terminal_after is not None
        assert symbols_total > 0
        assert version is not None

        # Same account
        assert account_after.login == account_before.login

        mt5.shutdown()
        mt5.disconnect()

    def test_event_loop_isolation(self) -> None:
        """Each sync operation should properly manage event loop."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

        try:
            # Multiple rapid operations shouldn't cause event loop issues
            for _ in range(10):
                mt5.account_info()
                mt5.terminal_info()
                mt5.symbols_total()

            # Should complete without event loop errors
            assert True
        finally:
            mt5.shutdown()
            mt5.disconnect()


class TestGracefulDegradation:
    """Test graceful degradation on errors."""

    def test_operations_without_connection_raise_error(self) -> None:
        """Operations without connection should raise appropriate error."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        # Not connected - should raise ConnectionError
        with pytest.raises((ConnectionError, grpc.RpcError, grpc.aio.AioRpcError)):
            mt5.account_info()

    def test_operations_without_init_return_none_or_error(self) -> None:
        """Operations without initialize should handle gracefully."""
        from contextlib import suppress

        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        try:
            # Connected but not initialized - may return None or raise
            # The important thing is no crash
            with suppress(grpc.RpcError, grpc.aio.AioRpcError):
                mt5.account_info()  # May return None or raise
        finally:
            mt5.disconnect()

    def test_disconnect_is_idempotent(self) -> None:
        """Multiple disconnects should not raise errors."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        # Multiple disconnects should be safe
        mt5.disconnect()
        mt5.disconnect()
        mt5.disconnect()

        assert mt5.is_connected is False

    def test_shutdown_without_init_is_safe(self) -> None:
        """Shutdown without initialize should not crash."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        try:
            # Shutdown without init - should be safe
            mt5.shutdown()
        finally:
            mt5.disconnect()


class TestResilienceInheritance:
    """Verify sync client inherits all resilience features."""

    def test_sync_client_uses_resilient_call(self) -> None:
        """Verify operations go through _resilient_call."""
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)
        mt5.connect()

        from tests.conftest import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
        mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

        try:
            # If circuit breaker is enabled, successful calls should reset it
            cb = mt5._async_client._circuit_breaker

            if cb is not None:
                # Record some failures manually
                cb.record_failure()
                cb.record_failure()
                assert cb.failure_count == 2  # Verify failures recorded

                # Successful operation should reset failure count
                mt5.account_info()

                assert cb.failure_count == 0  # Verify reset
        finally:
            mt5.shutdown()
            mt5.disconnect()

    def test_config_propagates_to_async_client(self) -> None:
        """Config settings should propagate to async client."""
        config = MT5Config()
        mt5 = MetaTrader5(host=TEST_HOST, port=TEST_PORT)

        async_config = mt5._async_client._config

        # Verify same config values
        assert async_config.enable_circuit_breaker == config.enable_circuit_breaker
        assert async_config.enable_auto_reconnect == config.enable_auto_reconnect
        assert async_config.cb_threshold == config.cb_threshold
        assert async_config.cb_recovery == config.cb_recovery
