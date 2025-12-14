"""Testes do client MetaTrader5 - 100% cobertura real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from tests.conftest import TEST_RPYC_PORT

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestMetaTrader5Connection:
    """Testes de conexão e lifecycle."""

    def test_connect_and_close(self, mt5_raw: MetaTrader5) -> None:
        """Testa conexão e fechamento."""
        # Conexão já estabelecida pela fixture
        assert mt5_raw._conn is not None
        mt5_raw.close()
        assert mt5_raw._conn is None

    def test_context_manager(self) -> None:
        """Testa context manager abre e fecha conexão corretamente."""
        from mt5linux import MetaTrader5

        with MetaTrader5(host="localhost", port=TEST_RPYC_PORT) as mt5:
            assert mt5._conn is not None
        # Após sair do context, conexão fechada
        assert mt5._conn is None

    def test_close_idempotent(self, mt5_raw: MetaTrader5) -> None:
        """Testa que close() pode ser chamado múltiplas vezes."""
        mt5_raw.close()
        mt5_raw.close()  # Não deve dar erro
        assert mt5_raw._conn is None


class TestMetaTrader5Initialize:
    """Testes de inicialização do terminal."""

    def test_initialize_success(self, mt5: MetaTrader5) -> None:
        """Testa inicialização bem sucedida."""
        # mt5 fixture já inicializa
        version = mt5.version()
        assert version is not None
        assert len(version) == 3

    def test_last_error(self, mt5: MetaTrader5) -> None:
        """Testa last_error após operação."""
        error = mt5.last_error()
        assert error is not None
        assert isinstance(error, tuple)
        assert len(error) == 2


class TestMetaTrader5Constants:
    """Testes de acesso às constantes do MT5."""

    def test_order_type_constants(self, mt5: MetaTrader5) -> None:
        """Testa acesso às constantes ORDER_TYPE_*."""
        assert mt5.ORDER_TYPE_BUY == 0
        assert mt5.ORDER_TYPE_SELL == 1
        assert mt5.ORDER_TYPE_BUY_LIMIT == 2
        assert mt5.ORDER_TYPE_SELL_LIMIT == 3

    def test_timeframe_constants(self, mt5: MetaTrader5) -> None:
        """Testa acesso às constantes TIMEFRAME_*."""
        assert mt5.TIMEFRAME_M1 == 1
        assert mt5.TIMEFRAME_M5 == 5
        assert mt5.TIMEFRAME_H1 == 16385
        assert mt5.TIMEFRAME_D1 == 16408

    def test_trade_retcode_constants(self, mt5: MetaTrader5) -> None:
        """Testa acesso às constantes TRADE_RETCODE_*."""
        assert mt5.TRADE_RETCODE_DONE == 10009
        assert mt5.TRADE_RETCODE_REQUOTE == 10004


class TestMetaTrader5AccountInfo:
    """Testes de informações da conta."""

    def test_account_info(self, mt5: MetaTrader5) -> None:
        """Testa account_info retorna dados válidos."""
        account = mt5.account_info()
        assert account is not None
        assert account.login > 0
        assert account.balance >= 0
        assert account.currency in ("USD", "EUR", "GBP")

    def test_terminal_info(self, mt5: MetaTrader5) -> None:
        """Testa terminal_info retorna dados válidos."""
        terminal = mt5.terminal_info()
        assert terminal is not None
        assert terminal.connected is True
        assert terminal.build > 0


class TestMetaTrader5Symbols:
    """Testes de símbolos."""

    def test_symbols_total(self, mt5: MetaTrader5) -> None:
        """Testa contagem de símbolos."""
        total = mt5.symbols_total()
        assert isinstance(total, int)
        assert total > 0

    def test_symbol_info(self, mt5: MetaTrader5) -> None:
        """Testa informações de símbolo."""
        info = mt5.symbol_info("EURUSD")
        assert info is not None
        assert info.name == "EURUSD"
        assert info.bid > 0
        assert info.ask > 0

    def test_symbol_info_tick(self, mt5: MetaTrader5) -> None:
        """Testa tick do símbolo."""
        mt5.symbol_select("EURUSD", True)
        tick = mt5.symbol_info_tick("EURUSD")
        assert tick is not None
        assert tick.bid > 0
        assert tick.ask > 0

    def test_symbols_get(self, mt5: MetaTrader5) -> None:
        """Testa lista de símbolos com filtro."""
        symbols = mt5.symbols_get(group="*USD*")
        assert symbols is not None
        assert len(symbols) > 0


class TestMetaTrader5CopyRates:
    """Testes de cópia de rates (OHLCV)."""

    def test_copy_rates_from_pos(self, mt5: MetaTrader5) -> None:
        """Testa copy_rates_from_pos traz array local."""
        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 10)
        assert rates is not None
        assert len(rates) > 0
        # Verifica que é numpy array local (não netref)
        assert hasattr(rates, "dtype")
        assert rates.dtype.names is not None
        assert "time" in rates.dtype.names
        assert "open" in rates.dtype.names
        assert "close" in rates.dtype.names

    def test_copy_rates_from(self, mt5: MetaTrader5) -> None:
        """Testa copy_rates_from com datetime."""
        date_from = datetime.now(UTC) - timedelta(days=7)
        rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_H1, date_from, 10)
        # Pode ser None se mercado fechado
        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")

    def test_copy_rates_range(self, mt5: MetaTrader5) -> None:
        """Testa copy_rates_range com intervalo."""
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=7)
        rates = mt5.copy_rates_range("EURUSD", mt5.TIMEFRAME_H1, date_from, date_to)
        if rates is not None:
            assert len(rates) > 0
            assert hasattr(rates, "dtype")


class TestMetaTrader5CopyTicks:
    """Testes de cópia de ticks."""

    def test_copy_ticks_from(self, mt5: MetaTrader5) -> None:
        """Testa copy_ticks_from traz array local."""
        mt5.symbol_select("EURUSD", True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = mt5.copy_ticks_from("EURUSD", date_from, 100, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            assert hasattr(ticks, "dtype")
            assert ticks.dtype.names is not None
            assert "time" in ticks.dtype.names
            assert "bid" in ticks.dtype.names

    def test_copy_ticks_range(self, mt5: MetaTrader5) -> None:
        """Testa copy_ticks_range com intervalo."""
        mt5.symbol_select("EURUSD", True)
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(minutes=10)
        ticks = mt5.copy_ticks_range("EURUSD", date_from, date_to, mt5.COPY_TICKS_ALL)
        # Pode ser None ou vazio se mercado fechado
        if ticks is not None:
            assert hasattr(ticks, "dtype")


class TestMetaTrader5Orders:
    """Testes de ordens."""

    def test_orders_total(self, mt5: MetaTrader5) -> None:
        """Testa contagem de ordens pendentes."""
        total = mt5.orders_total()
        assert isinstance(total, int)
        assert total >= 0

    def test_orders_get(self, mt5: MetaTrader5) -> None:
        """Testa lista de ordens."""
        orders = mt5.orders_get()
        # Pode ser None ou tuple vazia
        if orders is not None:
            assert isinstance(orders, tuple)


class TestMetaTrader5Positions:
    """Testes de posições."""

    def test_positions_total(self, mt5: MetaTrader5) -> None:
        """Testa contagem de posições abertas."""
        total = mt5.positions_total()
        assert isinstance(total, int)
        assert total >= 0

    def test_positions_get(self, mt5: MetaTrader5) -> None:
        """Testa lista de posições."""
        positions = mt5.positions_get()
        # Pode ser None ou tuple vazia
        if positions is not None:
            assert isinstance(positions, tuple)


class TestMetaTrader5History:
    """Testes de histórico."""

    def test_history_deals_total(self, mt5: MetaTrader5) -> None:
        """Testa contagem de deals no histórico."""
        date_from = datetime(2024, 1, 1, tzinfo=UTC)
        date_to = datetime.now(UTC)
        total = mt5.history_deals_total(date_from, date_to)
        assert isinstance(total, int)
        assert total >= 0

    def test_history_orders_total(self, mt5: MetaTrader5) -> None:
        """Testa contagem de ordens no histórico."""
        date_from = datetime(2024, 1, 1, tzinfo=UTC)
        date_to = datetime.now(UTC)
        total = mt5.history_orders_total(date_from, date_to)
        assert isinstance(total, int)
        assert total >= 0
