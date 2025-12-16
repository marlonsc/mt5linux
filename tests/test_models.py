"""Pydantic model tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from mt5linux.constants import MT5Constants
from mt5linux.models import MT5Models

# Type aliases for test convenience
OrderRequest = MT5Models.OrderRequest
OrderResult = MT5Models.OrderResult
AccountInfo = MT5Models.AccountInfo
SymbolInfo = MT5Models.SymbolInfo
Position = MT5Models.Position
Tick = MT5Models.Tick


class TestOrderRequest:
    """Tests for OrderRequest model."""

    def test_valid_market_order(self) -> None:
        """Test valid market buy order."""
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=MT5Constants.OrderType.BUY,
        )
        assert request.action == MT5Constants.TradeAction.DEAL
        assert request.symbol == "EURUSD"
        assert request.volume == 0.1
        assert request.type == MT5Constants.OrderType.BUY
        assert request.is_market_order is True

    def test_valid_limit_order(self) -> None:
        """Test valid limit order."""
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.5,
            type=MT5Constants.OrderType.BUY_LIMIT,
            price=1.0900,
            sl=1.0850,
            tp=1.1000,
        )
        assert request.type == MT5Constants.OrderType.BUY_LIMIT
        assert request.price == 1.0900
        assert request.is_market_order is False

    def test_invalid_volume_zero(self) -> None:
        """Test validation rejects zero volume."""
        with pytest.raises(ValidationError) as exc_info:
            OrderRequest(
                action=MT5Constants.TradeAction.DEAL,
                symbol="EURUSD",
                volume=0,
                type=MT5Constants.OrderType.BUY,
            )
        assert "volume" in str(exc_info.value)

    def test_invalid_volume_negative(self) -> None:
        """Test validation rejects negative volume."""
        with pytest.raises(ValidationError):
            OrderRequest(
                action=MT5Constants.TradeAction.DEAL,
                symbol="EURUSD",
                volume=-0.1,
                type=MT5Constants.OrderType.BUY,
            )

    def test_invalid_volume_too_large(self) -> None:
        """Test validation rejects volume > 1000."""
        with pytest.raises(ValidationError):
            OrderRequest(
                action=MT5Constants.TradeAction.DEAL,
                symbol="EURUSD",
                volume=1001,
                type=MT5Constants.OrderType.BUY,
            )

    def test_to_mt5_request_basic(self) -> None:
        """Test to_mt5_request produces valid MT5 request."""
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=MT5Constants.OrderType.BUY,
            deviation=20,
        )
        d = request.to_mt5_request()

        assert d["action"] == 1  # MT5Constants.TradeAction.DEAL
        assert d["symbol"] == "EURUSD"
        assert d["volume"] == 0.1
        assert d["type"] == 0  # MT5Constants.OrderType.BUY
        assert d["deviation"] == 20
        assert "sl" not in d  # Zero values excluded
        assert "tp" not in d

    def test_to_mt5_request_with_sl_tp(self) -> None:
        """Test to_mt5_request includes sl/tp when set."""
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=MT5Constants.OrderType.BUY,
            sl=1.0900,
            tp=1.1100,
        )
        d = request.to_mt5_request()

        assert d["sl"] == 1.0900
        assert d["tp"] == 1.1100

    def test_to_mt5_request_with_expiration(self) -> None:
        """Test to_mt5_request converts expiration to timestamp."""
        exp = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=MT5Constants.OrderType.BUY_LIMIT,
            price=1.0900,
            type_time=MT5Constants.OrderTime.SPECIFIED,
            expiration=exp,
        )
        d = request.to_mt5_request()

        assert "expiration" in d
        assert isinstance(d["expiration"], int)

    def test_frozen_model(self) -> None:
        """Test model is frozen (immutable)."""
        request = OrderRequest(
            action=MT5Constants.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=MT5Constants.OrderType.BUY,
        )
        with pytest.raises(ValidationError):
            request.volume = 0.2


class TestOrderResult:
    """Tests for OrderResult model."""

    def test_success_result(self) -> None:
        """Test successful order result."""
        result = OrderResult(
            retcode=MT5Constants.TradeRetcode.DONE,
            deal=12345,
            order=67890,
            volume=0.1,
            price=1.1000,
        )
        assert result.is_success is True
        assert result.is_partial is False
        assert result.deal == 12345
        assert result.order == 67890

    def test_partial_result(self) -> None:
        """Test partial fill result."""
        result = OrderResult(
            retcode=MT5Constants.TradeRetcode.DONE_PARTIAL,
            volume=0.05,
        )
        assert result.is_success is False
        assert result.is_partial is True

    def test_error_result(self) -> None:
        """Test error result."""
        result = OrderResult(
            retcode=MT5Constants.TradeRetcode.NO_MONEY,
            comment="Not enough money",
        )
        assert result.is_success is False
        assert result.comment == "Not enough money"

    def test_from_mt5_success(self) -> None:
        """Test from_mt5 with valid MT5 result."""
        mock_result = MagicMock()
        mock_result.retcode = 10009
        mock_result.deal = 12345
        mock_result.order = 67890
        mock_result.volume = 0.1
        mock_result.price = 1.1000
        mock_result.bid = 1.0999
        mock_result.ask = 1.1001
        mock_result.comment = "Request executed"
        mock_result.request_id = 1

        result = OrderResult.from_mt5(mock_result)

        assert result.retcode == 10009
        assert result.is_success is True
        assert result.deal == 12345

    def test_from_mt5_none(self) -> None:
        """Test from_mt5 with None returns error result."""
        result = OrderResult.from_mt5(None)

        assert result.retcode == MT5Constants.TradeRetcode.ERROR
        assert "No result" in result.comment


class TestAccountInfo:
    """Tests for AccountInfo model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid AccountInfo."""
        mock_info = MagicMock()
        mock_info.login = 12345
        mock_info.trade_mode = 0
        mock_info.leverage = 100
        mock_info.limit_orders = 200
        mock_info.margin_so_mode = 0
        mock_info.trade_allowed = True
        mock_info.trade_expert = True
        mock_info.margin_mode = 0
        mock_info.currency_digits = 2
        mock_info.fifo_close = False
        mock_info.balance = 10000.00
        mock_info.credit = 0.0
        mock_info.profit = 150.50
        mock_info.equity = 10150.50
        mock_info.margin = 100.0
        mock_info.margin_free = 10050.50
        mock_info.margin_level = 10150.5
        mock_info.margin_so_call = 50.0
        mock_info.margin_so_so = 30.0
        mock_info.margin_initial = 0.0
        mock_info.margin_maintenance = 0.0
        mock_info.assets = 0.0
        mock_info.liabilities = 0.0
        mock_info.commission_blocked = 0.0
        mock_info.name = "Test Account"
        mock_info.server = "MetaQuotes-Demo"
        mock_info.currency = "USD"
        mock_info.company = "MetaQuotes"

        account = AccountInfo.from_mt5(mock_info)

        assert account.login == 12345
        assert account.balance == 10000.00
        assert account.equity == 10150.50
        assert account.currency == "USD"

    def test_from_mt5_none(self) -> None:
        """Test from_mt5 with None returns None."""
        account = AccountInfo.from_mt5(None)
        assert account is None


class TestSymbolInfo:
    """Tests for SymbolInfo model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid SymbolInfo."""
        mock_info = MagicMock()
        mock_info.name = "EURUSD"
        mock_info.visible = True
        mock_info.select = True
        mock_info.time = 1702000000
        mock_info.digits = 5
        mock_info.spread = 10
        mock_info.spread_float = True
        mock_info.trade_mode = 4
        mock_info.trade_calc_mode = 0
        mock_info.trade_stops_level = 0
        mock_info.trade_freeze_level = 0
        mock_info.bid = 1.0900
        mock_info.ask = 1.0901
        mock_info.last = 0.0
        mock_info.volume = 0.0
        mock_info.point = 0.00001
        mock_info.trade_tick_value = 1.0
        mock_info.trade_tick_size = 0.00001
        mock_info.trade_contract_size = 100000.0
        mock_info.volume_min = 0.01
        mock_info.volume_max = 100.0
        mock_info.volume_step = 0.01
        mock_info.currency_base = "EUR"
        mock_info.currency_profit = "USD"
        mock_info.currency_margin = "EUR"
        mock_info.description = "Euro vs US Dollar"
        mock_info.path = "Forex\\EURUSD"

        symbol = SymbolInfo.from_mt5(mock_info)

        assert symbol.name == "EURUSD"
        assert symbol.bid == 1.0900
        assert symbol.ask == 1.0901
        assert symbol.digits == 5


class TestPosition:
    """Tests for Position model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid Position."""
        mock_pos = MagicMock()
        mock_pos.ticket = 12345678
        mock_pos.time = 1702000000
        mock_pos.time_msc = 1702000000123
        mock_pos.time_update = 1702001000
        mock_pos.time_update_msc = 1702001000456
        mock_pos.type = 0  # BUY
        mock_pos.magic = 123456
        mock_pos.identifier = 12345678
        mock_pos.reason = 0
        mock_pos.volume = 0.1
        mock_pos.price_open = 1.0900
        mock_pos.sl = 1.0850
        mock_pos.tp = 1.1000
        mock_pos.price_current = 1.0950
        mock_pos.swap = -0.50
        mock_pos.profit = 50.00
        mock_pos.symbol = "EURUSD"
        mock_pos.comment = "Test position"
        mock_pos.external_id = ""

        position = Position.from_mt5(mock_pos)

        assert position.ticket == 12345678
        assert position.volume == 0.1
        assert position.profit == 50.00
        assert position.symbol == "EURUSD"


class TestTick:
    """Tests for Tick model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid Tick."""
        mock_tick = MagicMock()
        mock_tick.time = 1702000000
        mock_tick.bid = 1.0900
        mock_tick.ask = 1.0901
        mock_tick.last = 0.0
        mock_tick.volume = 100
        mock_tick.time_msc = 1702000000123
        mock_tick.flags = 6
        mock_tick.volume_real = 100.0

        tick = Tick.from_mt5(mock_tick)

        assert tick.time == 1702000000
        assert tick.bid == 1.0900
        assert tick.ask == 1.0901


class TestEnums:
    """Tests for enum values."""

    def test_trade_action_values(self) -> None:
        """Test TradeAction enum values match MT5Constants."""
        assert MT5Constants.TradeAction.DEAL.value == 1
        assert MT5Constants.TradeAction.PENDING.value == 5
        assert MT5Constants.TradeAction.CLOSE_BY.value == 10

    def test_order_type_values(self) -> None:
        """Test OrderType enum values match MT5Constants."""
        assert MT5Constants.OrderType.BUY.value == 0
        assert MT5Constants.OrderType.SELL.value == 1
        assert MT5Constants.OrderType.BUY_LIMIT.value == 2
        assert MT5Constants.OrderType.SELL_LIMIT.value == 3

    def test_order_filling_values(self) -> None:
        """Test OrderFilling enum values match MT5Constants."""
        assert MT5Constants.OrderFilling.FOK.value == 0
        assert MT5Constants.OrderFilling.IOC.value == 1
        assert MT5Constants.OrderFilling.RETURN.value == 2

    def test_trade_retcode_values(self) -> None:
        """Test TradeRetcode enum values match MT5Constants."""
        assert MT5Constants.TradeRetcode.DONE.value == 10009
        assert MT5Constants.TradeRetcode.REQUOTE.value == 10004
        assert MT5Constants.TradeRetcode.NO_MONEY.value == 10019


class TestOrder:
    """Tests for Order model."""

    def test_from_mt5(self) -> None:
        """Test creating Order from MT5 data."""
        from mt5linux.models import MT5Models

        mock_order = MagicMock()
        mock_order.ticket = 12345678
        mock_order.time_setup = 1702000000
        mock_order.time_setup_msc = 1702000000123
        mock_order.time_done = 0
        mock_order.time_done_msc = 0
        mock_order.time_expiration = 0
        mock_order.type = 2  # BUY_LIMIT
        mock_order.type_time = 0  # GTC
        mock_order.type_filling = 0  # FOK
        mock_order.state = 1  # PLACED
        mock_order.magic = 123456
        mock_order.position_id = 0
        mock_order.position_by_id = 0
        mock_order.reason = 0  # CLIENT
        mock_order.volume_initial = 0.1
        mock_order.volume_current = 0.1
        mock_order.price_open = 1.0900
        mock_order.sl = 1.0850
        mock_order.tp = 1.1000
        mock_order.price_current = 1.0895
        mock_order.price_stoplimit = 0.0
        mock_order.symbol = "EURUSD"
        mock_order.comment = "test order"
        mock_order.external_id = ""

        order = MT5Models.Order.from_mt5(mock_order)

        assert order is not None
        assert order.ticket == 12345678
        assert order.type == 2
        assert order.volume_initial == 0.1
        assert order.symbol == "EURUSD"

    def test_from_mt5_none(self) -> None:
        """Test Order.from_mt5 with None returns None."""
        from mt5linux.models import MT5Models

        result = MT5Models.Order.from_mt5(None)
        assert result is None


class TestDeal:
    """Tests for Deal model."""

    def test_from_mt5(self) -> None:
        """Test creating Deal from MT5 data."""
        from mt5linux.models import MT5Models

        mock_deal = MagicMock()
        mock_deal.ticket = 87654321
        mock_deal.order = 12345678
        mock_deal.time = 1702000000
        mock_deal.time_msc = 1702000000123
        mock_deal.type = 0  # BUY
        mock_deal.entry = 0  # IN
        mock_deal.magic = 123456
        mock_deal.position_id = 99999
        mock_deal.reason = 0  # CLIENT
        mock_deal.volume = 0.1
        mock_deal.price = 1.0900
        mock_deal.commission = -0.50
        mock_deal.swap = 0.0
        mock_deal.profit = 10.0
        mock_deal.fee = 0.0
        mock_deal.symbol = "EURUSD"
        mock_deal.comment = "test deal"
        mock_deal.external_id = ""

        deal = MT5Models.Deal.from_mt5(mock_deal)

        assert deal is not None
        assert deal.ticket == 87654321
        assert deal.order == 12345678
        assert deal.volume == 0.1
        assert deal.profit == 10.0
        assert deal.symbol == "EURUSD"

    def test_from_mt5_none(self) -> None:
        """Test Deal.from_mt5 with None returns None."""
        from mt5linux.models import MT5Models

        result = MT5Models.Deal.from_mt5(None)
        assert result is None


class TestBookEntry:
    """Tests for BookEntry model."""

    def test_from_mt5(self) -> None:
        """Test creating BookEntry from MT5 data."""
        from mt5linux.models import MT5Models

        mock_entry = MagicMock()
        mock_entry.type = 2  # BUY
        mock_entry.price = 1.0900
        mock_entry.volume = 100.0
        mock_entry.volume_real = 100.0

        entry = MT5Models.BookEntry.from_mt5(mock_entry)

        assert entry is not None
        assert entry.type == 2
        assert entry.price == 1.0900
        assert entry.volume == 100.0

    def test_from_mt5_none(self) -> None:
        """Test BookEntry.from_mt5 with None returns None."""
        from mt5linux.models import MT5Models

        result = MT5Models.BookEntry.from_mt5(None)
        assert result is None
