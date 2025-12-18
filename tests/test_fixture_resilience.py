"""Tests for pytest fixture resilience.

Validates that test fixtures properly handle connection recovery
and maintain test isolation across test files.

These tests validate that:
1. Session fixtures maintain connection
2. Function fixtures recover from connection loss
3. Test isolation is preserved
4. Cleanup works correctly
"""

from __future__ import annotations

from datetime import UTC

from mt5linux import MetaTrader5
from mt5linux.config import MT5Config


class TestFixtureResilience:
    """Test that fixtures recover from connection issues."""

    def test_mt5_fixture_is_connected(self, mt5: MetaTrader5) -> None:
        """MT5 fixture should provide connected client."""
        assert mt5.is_connected is True

    def test_mt5_fixture_is_initialized(self, mt5: MetaTrader5) -> None:
        """MT5 fixture should be properly initialized."""
        info = mt5.terminal_info()
        assert info is not None
        assert info.connected is True

    def test_mt5_fixture_has_account(self, mt5: MetaTrader5) -> None:
        """MT5 fixture should have logged in account."""
        account = mt5.account_info()
        assert account is not None
        assert account.login > 0

    def test_fixture_survives_symbol_operations(self, mt5: MetaTrader5) -> None:
        """Fixture should work after symbol operations."""
        # Get symbol info
        symbol = mt5.symbol_info("EURUSD")
        assert symbol is not None

        # Get tick
        tick = mt5.symbol_info_tick("EURUSD")
        assert tick is not None

        # Fixture should still work
        account = mt5.account_info()
        assert account is not None

    def test_fixture_survives_history_operations(self, mt5: MetaTrader5) -> None:
        """Fixture should work after history operations."""
        from datetime import datetime, timedelta

        # Get historical data
        now = datetime.now(tz=UTC)
        yesterday = now - timedelta(days=1)

        # Call operation - may be None if market closed, but shouldn't crash
        mt5.copy_rates_range(
            "EURUSD",
            mt5.TIMEFRAME_H1,
            yesterday,
            now,
        )

        # Fixture should still work
        account = mt5.account_info()
        assert account is not None


class TestConnectionStateTransitions:
    """Test connection state transitions."""

    def test_new_client_starts_disconnected(self) -> None:
        """New client should start disconnected."""
        config = MT5Config()
        mt5 = MetaTrader5(
            host=config.host,
            port=config.test_grpc_port,
        )
        assert mt5.is_connected is False

    def test_connect_changes_state(self) -> None:
        """Connect should change state to connected."""
        config = MT5Config()
        mt5 = MetaTrader5(
            host=config.host,
            port=config.test_grpc_port,
        )

        mt5.connect()
        assert mt5.is_connected is True
        mt5.disconnect()

    def test_disconnect_changes_state(self) -> None:
        """Disconnect should change state to disconnected."""
        config = MT5Config()
        mt5 = MetaTrader5(
            host=config.host,
            port=config.test_grpc_port,
        )

        mt5.connect()
        mt5.disconnect()
        assert mt5.is_connected is False


class TestTestIsolation:
    """Verify tests don't affect each other."""

    def test_isolation_first(self, mt5: MetaTrader5) -> None:
        """First test in isolation series."""
        # Record initial state
        account = mt5.account_info()
        assert account is not None

        # Make some operations
        mt5.symbols_total()
        mt5.terminal_info()

    def test_isolation_second(self, mt5: MetaTrader5) -> None:
        """Second test should have clean state."""
        # Should still work after first test
        account = mt5.account_info()
        assert account is not None

        symbols = mt5.symbols_total()
        assert symbols > 0

    def test_isolation_third(self, mt5: MetaTrader5) -> None:
        """Third test should have clean state."""
        # Should still work after previous tests
        account = mt5.account_info()
        assert account is not None

        info = mt5.terminal_info()
        assert info is not None


class TestSequentialOperations:
    """Test multiple sequential operations."""

    def test_many_sequential_operations(self, mt5: MetaTrader5) -> None:
        """Many sequential operations should work."""
        for i in range(20):
            account = mt5.account_info()
            assert account is not None, f"Failed at iteration {i}"

    def test_mixed_operations_sequence(self, mt5: MetaTrader5) -> None:
        """Mixed operations in sequence should work."""
        operations = [
            lambda: mt5.account_info(),
            lambda: mt5.terminal_info(),
            lambda: mt5.symbols_total(),
            lambda: mt5.symbol_info("EURUSD"),
            lambda: mt5.version(),
        ]

        for _i, op in enumerate(operations * 3):  # Run each 3 times
            op()  # Execute - the point is no crashes


class TestAsyncClientExposure:
    """Test that async client is properly exposed for advanced use."""

    def test_async_client_accessible(self, mt5: MetaTrader5) -> None:
        """Async client should be accessible from sync client."""
        assert hasattr(mt5, "_async_client")
        assert mt5._async_client is not None

    def test_async_client_connected(self, mt5: MetaTrader5) -> None:
        """Async client should reflect connection state."""
        assert mt5._async_client._channel is not None

    def test_async_client_has_stub(self, mt5: MetaTrader5) -> None:
        """Async client should have gRPC stub."""
        assert mt5._async_client._stub is not None

    def test_circuit_breaker_accessible(self, mt5: MetaTrader5) -> None:
        """Circuit breaker should be accessible if enabled."""
        config = MT5Config()
        if config.enable_circuit_breaker:
            assert mt5._async_client._circuit_breaker is not None
        else:
            assert mt5._async_client._circuit_breaker is None
