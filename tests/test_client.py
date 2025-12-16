"""MetaTrader5 client tests - real coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mt5linux import MetaTrader5

from .conftest import TEST_RPYC_PORT


class TestMetaTrader5Connection:
    """Connection and lifecycle tests (no credentials required)."""

    def test_connect_and_close(self, mt5_raw: MetaTrader5) -> None:
        """Test connection and close."""
        # Connection already established by fixture
        assert mt5_raw._conn is not None
        mt5_raw.close()
        assert mt5_raw._conn is None

    def test_context_manager(self) -> None:
        """Test context manager opens and closes connection correctly."""
        try:
            with MetaTrader5(host="localhost", port=TEST_RPYC_PORT) as mt5:
                assert mt5._conn is not None
        except (ConnectionError, EOFError, OSError) as e:
            pytest.skip(f"MT5 connection failed: {e}")
        # After exiting context, connection closed
        assert mt5._conn is None

    def test_close_idempotent(self, mt5_raw: MetaTrader5) -> None:
        """Test that close() can be called multiple times."""
        mt5_raw.close()
        mt5_raw.close()  # Should not raise
        assert mt5_raw._conn is None


class TestMetaTrader5Initialize:
    """Terminal initialization tests (requires MT5 credentials)."""

    def test_initialize_success(self, mt5: MetaTrader5) -> None:
        """Test successful initialization."""
        # mt5 fixture already initializes
        version = mt5.version()
        assert version is not None
        assert len(version) == 3

    def test_last_error(self, mt5: MetaTrader5) -> None:
        """Test last_error after operation."""
        error = mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == 2


class TestMetaTrader5Constants:
    """MT5 constants access tests (requires MT5 credentials)."""

    def test_order_type_constants(self, mt5: MetaTrader5) -> None:
        """Test access to ORDER_TYPE_* constants."""
        assert mt5.ORDER_TYPE_BUY == 0
        assert mt5.ORDER_TYPE_SELL == 1
        assert mt5.ORDER_TYPE_BUY_LIMIT == 2
        assert mt5.ORDER_TYPE_SELL_LIMIT == 3

    def test_timeframe_constants(self, mt5: MetaTrader5) -> None:
        """Test access to TIMEFRAME_* constants."""
        assert mt5.TIMEFRAME_M1 == 1
        assert mt5.TIMEFRAME_M5 == 5
        assert mt5.TIMEFRAME_H1 == 16385
        assert mt5.TIMEFRAME_D1 == 16408

    def test_trade_retcode_constants(self, mt5: MetaTrader5) -> None:
        """Test access to TRADE_RETCODE_* constants."""
        assert mt5.TRADE_RETCODE_DONE == 10009
        assert mt5.TRADE_RETCODE_REQUOTE == 10004


class TestMetaTrader5AccountInfo:
    """Account info tests (requires MT5 credentials)."""

    def test_account_info(self, mt5: MetaTrader5) -> None:
        """Test account_info returns valid data."""
        account = mt5.account_info()
        assert account is not None
        assert account.login > 0
        assert account.balance >= 0
        assert account.currency in {"USD", "EUR", "GBP"}

    def test_terminal_info(self, mt5: MetaTrader5) -> None:
        """Test terminal_info returns valid data."""
        terminal = mt5.terminal_info()
        assert terminal is not None
        assert terminal.connected is True
        assert terminal.build > 0


class TestMetaTrader5Symbols:
    """Symbol tests (requires MT5 credentials)."""

    def test_symbols_total(self, mt5: MetaTrader5) -> None:
        """Test symbol count."""
        total = mt5.symbols_total()
        assert isinstance(total, int)
        if total == 0:
            pytest.skip("symbols_total returned 0 (MT5 connection issue)")
        assert total > 0

    def test_symbol_info(self, mt5: MetaTrader5) -> None:
        """Test symbol info."""
        info = mt5.symbol_info("EURUSD")
        assert info is not None
        assert info.name == "EURUSD"
        assert info.bid > 0
        assert info.ask > 0

    def test_symbol_info_tick(self, mt5: MetaTrader5) -> None:
        """Test symbol tick."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")
        assert tick is not None
        assert tick.bid > 0
        assert tick.ask > 0

    def test_symbols_get(self, mt5: MetaTrader5) -> None:
        """Test symbol list with filter."""
        symbols = mt5.symbols_get(group="*USD*")
        assert symbols is not None
        assert len(symbols) > 0


class TestMetaTrader5CopyRates:
    """OHLCV rates copy tests (requires MT5 credentials)."""

    def test_copy_rates_from_pos(self, mt5: MetaTrader5) -> None:
        """Test copy_rates_from_pos returns local array."""
        try:
            rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 10)
        except Exception as e:
            if "pickling is disabled" in str(e):
                pytest.skip("RPyC pickling disabled - numpy serialization not available")  # noqa: E501
            raise
        if rates is None:
            pytest.skip("Market data not available (market may be closed)")
        assert len(rates) > 0
        # Verify it's a local numpy array (not netref)
        assert hasattr(rates, "dtype")
        assert rates.dtype.names is not None
        assert "time" in rates.dtype.names
        assert "open" in rates.dtype.names
        assert "close" in rates.dtype.names

    def test_copy_rates_from(self, mt5: MetaTrader5) -> None:
        """Test copy_rates_from with datetime."""
        date_from = datetime.now(UTC) - timedelta(days=7)
        rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_H1, date_from, 10)
        # May be None if market closed
        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")

    def test_copy_rates_range(self, mt5: MetaTrader5) -> None:
        """Test copy_rates_range with interval."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=7)
        rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_H1, date_from, date_to)
        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")


class TestMetaTrader5CopyTicks:
    """Tick copy tests (requires MT5 credentials)."""

    def test_copy_ticks_from(self, mt5: MetaTrader5) -> None:
        """Test copy_ticks_from returns local array."""
        mt5.symbol_select("EURUSD", True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = mt5.copy_ticks_from("EURUSD", date_from, 100, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            assert hasattr(ticks, "dtype")
            assert ticks.dtype.names is not None
            assert "time" in ticks.dtype.names
            assert "bid" in ticks.dtype.names

    def test_copy_ticks_range(self, mt5: MetaTrader5) -> None:
        """Test copy_ticks_range with interval."""
        mt5.symbol_select("EURUSD", True)
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(minutes=10)
        ticks = mt5.copy_ticks_range("EURUSD", date_from, date_to, mt5.COPY_TICKS_ALL)
        # May be None or empty if market closed
        if ticks is not None:
            assert hasattr(ticks, "dtype")


class TestMetaTrader5Orders:
    """Order tests (requires MT5 credentials)."""

    def test_orders_total(self, mt5: MetaTrader5) -> None:
        """Test pending orders count."""
        total = mt5.orders_total()
        assert isinstance(total, int)
        assert total >= 0

    def test_orders_get(self, mt5: MetaTrader5) -> None:
        """Test orders list."""
        orders = mt5.orders_get()
        # May be None or empty tuple
        if orders is not None:
            assert isinstance(orders, tuple)


class TestMetaTrader5Positions:
    """Position tests (requires MT5 credentials)."""

    def test_positions_total(self, mt5: MetaTrader5) -> None:
        """Test open positions count."""
        total = mt5.positions_total()
        assert isinstance(total, int)
        assert total >= 0

    def test_positions_get(self, mt5: MetaTrader5) -> None:
        """Test positions list."""
        positions = mt5.positions_get()
        # May be None or empty tuple
        if positions is not None:
            assert isinstance(positions, tuple)


class TestMetaTrader5History:
    """History tests (requires MT5 credentials)."""

    def test_history_deals_total(self, mt5: MetaTrader5) -> None:
        """Test history deals count."""
        date_from = datetime(2024, 1, 1, tzinfo=UTC)
        date_to = datetime.now(UTC)
        total = mt5.history_deals_total(date_from, date_to)
        # May return None if no history available
        assert total is None or (isinstance(total, int) and total >= 0)

    def test_history_orders_total(self, mt5: MetaTrader5) -> None:
        """Test history orders count."""
        date_from = datetime(2024, 1, 1, tzinfo=UTC)
        date_to = datetime.now(UTC)
        total = mt5.history_orders_total(date_from, date_to)
        # May return None if no history available
        assert total is None or (isinstance(total, int) and total >= 0)


class TestMetaTrader5Login:
    """Tests for explicit login functionality."""

    @pytest.mark.integration
    def test_login_with_valid_credentials(self, mt5_raw: MetaTrader5) -> None:
        """Test login with valid credentials."""
        import os

        login = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "")

        if not all([login, password, server]):
            pytest.skip("MT5 credentials not configured")

        # Initialize first (required before login)
        init_result = mt5_raw.initialize()
        if not init_result:
            pytest.skip("MT5 initialize failed")

        result = mt5_raw.login(login, password, server)
        assert result is True

        # Verify logged in
        account = mt5_raw.account_info()
        assert account is not None
        assert account.login == login

    @pytest.mark.integration
    def test_login_with_invalid_credentials(self, mt5_raw: MetaTrader5) -> None:
        """Test login with invalid credentials returns False."""
        # Initialize first
        init_result = mt5_raw.initialize()
        if not init_result:
            pytest.skip("MT5 initialize failed")

        result = mt5_raw.login(99999999, "wrong_password", "InvalidServer")
        assert result is False

    @pytest.mark.integration
    def test_login_after_initialize(self, mt5: MetaTrader5) -> None:
        """Test that login works after initialize."""
        import os

        login = int(os.getenv("MT5_LOGIN", "0"))
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "")

        if not all([login, password, server]):
            pytest.skip("MT5 credentials not configured")

        # Already initialized via fixture, login should work
        result = mt5.login(login, password, server)
        assert result is True


class TestMetaTrader5HealthCheck:
    """Tests for health_check functionality."""

    @pytest.mark.integration
    def test_health_check_connected(self, mt5: MetaTrader5) -> None:
        """Test health_check returns healthy status when connected."""
        health = mt5.health_check()

        assert isinstance(health, dict)
        assert "healthy" in health
        assert "mt5_available" in health
        assert health["healthy"] is True
        assert health["mt5_available"] is True
        assert health["connected"] is True

    @pytest.mark.integration
    def test_health_check_fields(self, mt5: MetaTrader5) -> None:
        """Test health_check returns expected fields."""
        health = mt5.health_check()

        # Verify expected fields
        expected_fields = ["healthy", "mt5_available", "connected"]
        for field in expected_fields:
            assert field in health, f"Missing field: {field}"

    @pytest.mark.integration
    def test_health_check_raw_connection(self, mt5_raw: MetaTrader5) -> None:
        """Test health_check on raw connection (not initialized)."""
        health = mt5_raw.health_check()

        assert isinstance(health, dict)
        # Raw connection - MT5 may not be fully initialized
        assert "healthy" in health


class TestMetaTrader5Resilience:
    """Tests for resilience features (retry, circuit breaker)."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_connection_recovery_after_close(self, mt5: MetaTrader5) -> None:
        """Test that client handles connection issues gracefully."""
        # Get initial data
        account1 = mt5.account_info()
        assert account1 is not None

        # Force close and verify error on next call
        mt5._close()

        # This should raise since connection is closed
        with pytest.raises((ConnectionError, RuntimeError, AttributeError)):
            mt5.account_info()

    @pytest.mark.integration
    def test_close_is_idempotent(self, mt5_raw: MetaTrader5) -> None:
        """Test that _close() can be called multiple times safely."""
        mt5_raw._close()
        mt5_raw._close()  # Should not raise
        mt5_raw._close()  # Should not raise

    @pytest.mark.integration
    def test_multiple_operations_same_connection(self, mt5: MetaTrader5) -> None:
        """Test multiple sequential operations on same connection."""
        # Perform multiple operations
        for _ in range(5):
            account = mt5.account_info()
            assert account is not None

            symbols = mt5.symbols_total()
            assert symbols > 0

            terminal = mt5.terminal_info()
            assert terminal is not None
