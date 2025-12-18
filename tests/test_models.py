"""Pydantic model tests.

NO MOCKING - tests use namedtuples or explicit classes to simulate MT5 data.
"""

from __future__ import annotations

from collections import namedtuple
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mt5linux.models import MT5Models

from .conftest import c, tc

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
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=tc.TEST_VOLUME_MICRO,
            type=c.Order.OrderType.BUY,
        )
        assert request.action == c.Order.TradeAction.DEAL
        assert request.symbol == "EURUSD"
        assert request.volume == tc.TEST_VOLUME_MICRO
        assert request.type == c.Order.OrderType.BUY
        assert request.is_market_order is True

    def test_valid_limit_order(self) -> None:
        """Test valid limit order."""
        request = OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.5,
            type=c.Order.OrderType.BUY_LIMIT,
            price=tc.TEST_PRICE_BASE,
            sl=1.0850,
            tp=1.1000,
        )
        assert request.type == c.Order.OrderType.BUY_LIMIT
        assert request.price == tc.TEST_PRICE_BASE
        assert request.is_market_order is False

    def test_invalid_volume_zero(self) -> None:
        """Test validation rejects zero volume."""
        with pytest.raises(ValidationError) as exc_info:
            OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=0,
                type=c.Order.OrderType.BUY,
            )
        assert "volume" in str(exc_info.value)

    def test_invalid_volume_negative(self) -> None:
        """Test validation rejects negative volume."""
        with pytest.raises(ValidationError):
            OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=-tc.MINI_LOT,
                type=c.Order.OrderType.BUY,
            )

    def test_invalid_volume_too_large(self) -> None:
        """Test validation rejects volume > 1000."""
        with pytest.raises(ValidationError):
            OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=tc.INVALID_VOLUME,
                type=c.Order.OrderType.BUY,
            )

    def test_to_mt5_request_basic(self) -> None:
        """Test to_mt5_request produces valid MT5 request."""
        request = OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=tc.TEST_VOLUME_MICRO,
            type=c.Order.OrderType.BUY,
            deviation=tc.DEFAULT_DEVIATION,
        )
        d = request.to_mt5_request()

        assert d["action"] == 1  # c.Order.TradeAction.DEAL
        assert d["symbol"] == "EURUSD"
        assert d["volume"] == tc.TEST_VOLUME_MICRO
        assert d["type"] == 0  # c.Order.OrderType.BUY
        assert d["deviation"] == tc.TEST_DEVIATION_NORMAL
        assert "sl" not in d  # Zero values excluded
        assert "tp" not in d

    def test_to_mt5_request_with_sl_tp(self) -> None:
        """Test to_mt5_request includes sl/tp when set."""
        request = OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=tc.TEST_VOLUME_MICRO,
            type=c.Order.OrderType.BUY,
            sl=1.0900,
            tp=tc.TEST_PRICE_HIGH,
        )
        d = request.to_mt5_request()

        assert d["sl"] == tc.TEST_PRICE_BASE
        assert d["tp"] == tc.TEST_PRICE_HIGH

    def test_to_mt5_request_with_expiration(self) -> None:
        """Test to_mt5_request converts expiration to timestamp."""
        exp = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
        request = OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=tc.TEST_VOLUME_MICRO,
            type=c.Order.OrderType.BUY_LIMIT,
            price=tc.TEST_PRICE_BASE,
            type_time=c.Order.OrderTime.SPECIFIED,
            expiration=exp,
        )
        d = request.to_mt5_request()

        assert "expiration" in d
        assert isinstance(d["expiration"], int)

    def test_frozen_model(self) -> None:
        """Test model is frozen (immutable)."""
        request = OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=tc.TEST_VOLUME_MICRO,
            type=c.Order.OrderType.BUY,
        )
        with pytest.raises(ValidationError):
            request.volume = 0.2


class TestOrderResult:
    """Tests for OrderResult model."""

    def test_success_result(self) -> None:
        """Test successful order result."""
        result = OrderResult(
            retcode=c.Order.TradeRetcode.DONE,
            deal=tc.TEST_MAGIC_DEFAULT,
            order=tc.TEST_ORDER_DEFAULT,
            volume=tc.TEST_VOLUME_MICRO,
            price=1.1000,
        )
        assert result.is_success is True
        assert result.is_partial is False
        assert result.deal == tc.TEST_MAGIC_DEFAULT
        assert result.order == tc.TEST_ORDER_DEFAULT

    def test_partial_result(self) -> None:
        """Test partial fill result."""
        result = OrderResult(
            retcode=c.Order.TradeRetcode.DONE_PARTIAL,
            volume=0.05,
        )
        assert result.is_success is False
        assert result.is_partial is True

    def test_error_result(self) -> None:
        """Test error result."""
        result = OrderResult(
            retcode=c.Order.TradeRetcode.NO_MONEY,
            comment="Not enough money",
        )
        assert result.is_success is False
        assert result.comment == "Not enough money"

    def test_from_mt5_success(self) -> None:
        """Test from_mt5 with valid MT5 result (using namedtuple)."""
        # Create namedtuple to simulate MT5 OrderSendResult
        OrderSendResult = namedtuple(  # noqa: PYI024
            "OrderSendResult",
            [
                "retcode",
                "deal",
                "order",
                "volume",
                "price",
                "bid",
                "ask",
                "comment",
                "request_id",
                "retcode_external",
            ],
        )
        mt5_result = OrderSendResult(
            retcode=c.Order.TradeRetcode.DONE,
            deal=tc.TEST_MAGIC_DEFAULT,
            order=tc.TEST_ORDER_DEFAULT,
            volume=0.1,
            price=1.1000,
            bid=1.0999,
            ask=1.1001,
            comment="Request executed",
            request_id=1,
            retcode_external=0,
        )

        result = MT5Models.OrderResult.from_mt5(mt5_result)

        assert result.retcode == c.Order.TradeRetcode.DONE
        assert result.is_success is True
        assert result.deal == tc.TEST_MAGIC_DEFAULT

    def test_from_mt5_none(self) -> None:
        """Test from_mt5 with None returns error result."""
        result = OrderResult.from_mt5(None)

        assert result.retcode == c.Order.TradeRetcode.ERROR
        assert "No result" in result.comment


class TestAccountInfo:
    """Tests for AccountInfo model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid AccountInfo (using namedtuple)."""
        # Create namedtuple with all 28 AccountInfo fields
        AccountInfoTuple = namedtuple(  # noqa: PYI024
            "AccountInfoTuple",
            [
                "assets",
                "balance",
                "commission_blocked",
                "company",
                "credit",
                "currency",
                "currency_digits",
                "equity",
                "fifo_close",
                "leverage",
                "liabilities",
                "limit_orders",
                "login",
                "margin",
                "margin_free",
                "margin_initial",
                "margin_level",
                "margin_maintenance",
                "margin_mode",
                "margin_so_call",
                "margin_so_mode",
                "margin_so_so",
                "name",
                "profit",
                "server",
                "trade_allowed",
                "trade_expert",
                "trade_mode",
            ],
        )
        mt5_info = AccountInfoTuple(
            assets=0.0,
            balance=tc.TEST_ACCOUNT_BALANCE,
            commission_blocked=0.0,
            company="MetaQuotes",
            credit=0.0,
            currency="USD",
            currency_digits=2,
            equity=tc.TEST_ACCOUNT_EQUITY_HIGH,
            fifo_close=False,
            leverage=100,
            liabilities=0.0,
            limit_orders=200,
            login=tc.TEST_MAGIC_DEFAULT,
            margin=100.0,
            margin_free=10050.50,
            margin_initial=0.0,
            margin_level=10150.5,
            margin_maintenance=0.0,
            margin_mode=0,
            margin_so_call=50.0,
            margin_so_mode=0,
            margin_so_so=30.0,
            name="Test Account",
            profit=150.50,
            server="MetaQuotes-Demo",
            trade_allowed=True,
            trade_expert=True,
            trade_mode=0,
        )

        account = AccountInfo.from_mt5(mt5_info)

        assert account.login == tc.TEST_MAGIC_DEFAULT
        assert account.balance == tc.TEST_ACCOUNT_BALANCE
        assert account.equity == tc.TEST_ACCOUNT_EQUITY_HIGH
        assert account.currency == "USD"

    def test_from_mt5_none(self) -> None:
        """Test from_mt5 with None returns None."""
        account = AccountInfo.from_mt5(None)
        assert account is None


class TestSymbolInfo:
    """Tests for SymbolInfo model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid SymbolInfo (using dict)."""
        # Use dict since SymbolInfo has 96 fields - too many for namedtuple
        mt5_info = {
            # Core identification
            "name": "EURUSD",
            "description": "Euro vs US Dollar",
            "path": "Forex\\EURUSD",
            "isin": "",
            "bank": "",
            "page": "",
            "category": "",
            "exchange": "",
            "formula": "",
            "basis": "",
            # Currency
            "currency_base": "EUR",
            "currency_profit": "USD",
            "currency_margin": "EUR",
            # Selection/Visibility
            "visible": True,
            "select": True,
            "custom": False,
            # Time
            "time": 1702000000,
            "start_time": 0,
            "expiration_time": 0,
            # Digits/Spread
            "digits": 5,
            "spread": 10,
            "spread_float": True,
            # Trade mode/settings
            "trade_mode": 4,
            "trade_calc_mode": 0,
            "trade_stops_level": 0,
            "trade_freeze_level": 0,
            "trade_exemode": 0,
            "chart_mode": 0,
            "filling_mode": 0,
            "expiration_mode": 0,
            "order_mode": 0,
            "order_gtc_mode": 0,
            # Option fields
            "option_mode": 0,
            "option_right": 0,
            "option_strike": 0.0,
            # Prices - current
            "bid": 1.0900,
            "ask": 1.0901,
            "last": 0.0,
            # Prices - high/low
            "bidhigh": 0.0,
            "bidlow": 0.0,
            "askhigh": 0.0,
            "asklow": 0.0,
            "lasthigh": 0.0,
            "lastlow": 0.0,
            # Price change/volatility
            "price_change": 0.0,
            "price_volatility": 0.0,
            "price_theoretical": 0.0,
            "price_sensitivity": 0.0,
            # Greeks
            "price_greeks_delta": 0.0,
            "price_greeks_gamma": 0.0,
            "price_greeks_theta": 0.0,
            "price_greeks_vega": 0.0,
            "price_greeks_rho": 0.0,
            "price_greeks_omega": 0.0,
            # Point/Tick
            "point": 0.00001,
            "trade_tick_value": 1.0,
            "trade_tick_value_profit": 0.0,
            "trade_tick_value_loss": 0.0,
            "trade_tick_size": 0.00001,
            "ticks_bookdepth": 0,
            # Contract
            "trade_contract_size": 100000.0,
            "trade_face_value": 0.0,
            "trade_accrued_interest": 0.0,
            "trade_liquidity_rate": 0.0,
            # Volume
            "volume": 0.0,
            "volume_real": 0.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
            "volume_limit": 0.0,
            "volumehigh": 0.0,
            "volumehigh_real": 0.0,
            "volumelow": 0.0,
            "volumelow_real": 0.0,
            # Margin
            "margin_initial": 0.0,
            "margin_maintenance": 0.0,
            "margin_hedged": 0.0,
            "margin_hedged_use_leg": False,
            # Swap
            "swap_mode": 0,
            "swap_long": 0.0,
            "swap_short": 0.0,
            "swap_rollover3days": 0,
            # Session data
            "session_volume": 0.0,
            "session_turnover": 0.0,
            "session_interest": 0.0,
            "session_deals": 0.0,
            "session_buy_orders": 0.0,
            "session_buy_orders_volume": 0.0,
            "session_sell_orders": 0.0,
            "session_sell_orders_volume": 0.0,
            "session_open": 0.0,
            "session_close": 0.0,
            "session_aw": 0.0,
            "session_price_settlement": 0.0,
            "session_price_limit_min": 0.0,
            "session_price_limit_max": 0.0,
        }

        symbol = SymbolInfo.from_mt5(mt5_info)

        assert symbol.name == "EURUSD"
        assert symbol.bid == 1.0900
        assert symbol.ask == 1.0901
        assert symbol.digits == 5


class TestPosition:
    """Tests for Position model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid Position (using namedtuple)."""
        PositionTuple = namedtuple(  # noqa: PYI024
            "PositionTuple",
            [
                "ticket",
                "time",
                "time_msc",
                "time_update",
                "time_update_msc",
                "type",
                "magic",
                "identifier",
                "reason",
                "volume",
                "price_open",
                "sl",
                "tp",
                "price_current",
                "swap",
                "profit",
                "symbol",
                "comment",
                "external_id",
            ],
        )
        mt5_pos = PositionTuple(
            ticket=tc.TEST_MAGIC_LARGE,
            time=1702000000,
            time_msc=1702000000123,
            time_update=1702001000,
            time_update_msc=1702001000456,
            type=0,  # BUY
            magic=c.Trading.DEFAULT_MAGIC_NUMBER,
            identifier=tc.TEST_MAGIC_LARGE,
            reason=0,
            volume=0.1,
            price_open=1.0900,
            sl=1.0850,
            tp=1.1000,
            price_current=1.0950,
            swap=-0.50,
            profit=50.00,
            symbol="EURUSD",
            comment="Test position",
            external_id="",
        )

        position = Position.from_mt5(mt5_pos)

        assert position.ticket == tc.TEST_MAGIC_LARGE
        assert position.volume == 0.1
        assert position.profit == 50.00
        assert position.symbol == "EURUSD"


class TestTick:
    """Tests for Tick model."""

    def test_from_mt5(self) -> None:
        """Test from_mt5 creates valid Tick (using namedtuple)."""
        TickTuple = namedtuple(  # noqa: PYI024
            "TickTuple",
            ["time", "bid", "ask", "last", "volume", "time_msc", "flags", "volume_real"],  # noqa: E501
        )
        mt5_tick = TickTuple(
            time=tc.TEST_TIMESTAMP_EPOCH,
            bid=1.0900,
            ask=1.0901,
            last=0.0,
            volume=100,
            time_msc=1702000000123,
            flags=6,
            volume_real=100.0,
        )

        tick = Tick.from_mt5(mt5_tick)

        assert tick.time == tc.TEST_TIMESTAMP_EPOCH
        assert tick.bid == 1.0900
        assert tick.ask == 1.0901


class TestEnums:
    """Tests for enum values."""

    def test_trade_action_values(self) -> None:
        """Test TradeAction enum values match c."""
        assert c.Order.TradeAction.DEAL.value == 1
        assert c.Order.TradeAction.PENDING.value == 5
        assert c.Order.TradeAction.CLOSE_BY.value == 10

    def test_order_type_values(self) -> None:
        """Test OrderType enum values match c."""
        assert c.Order.OrderType.BUY.value == 0
        assert c.Order.OrderType.SELL.value == 1
        assert c.Order.OrderType.BUY_LIMIT.value == 2
        assert c.Order.OrderType.SELL_LIMIT.value == 3

    def test_order_filling_values(self) -> None:
        """Test OrderFilling enum values match c."""
        assert c.Order.OrderFilling.FOK.value == 0
        assert c.Order.OrderFilling.IOC.value == 1
        assert c.Order.OrderFilling.RETURN.value == 2

    def test_trade_retcode_values(self) -> None:
        """Test TradeRetcode enum values match c."""
        assert c.Order.TradeRetcode.DONE.value == 10009
        assert c.Order.TradeRetcode.REQUOTE.value == tc.TEST_RETCODE_REQUOTE
        assert c.Order.TradeRetcode.NO_MONEY.value == tc.TEST_RETCODE_NO_MONEY


class TestOrder:
    """Tests for Order model."""

    def test_from_mt5(self) -> None:
        """Test creating Order from MT5 data (using namedtuple)."""
        OrderTuple = namedtuple(  # noqa: PYI024
            "OrderTuple",
            [
                "ticket",
                "time_setup",
                "time_setup_msc",
                "time_done",
                "time_done_msc",
                "time_expiration",
                "type",
                "type_time",
                "type_filling",
                "state",
                "magic",
                "position_id",
                "position_by_id",
                "reason",
                "volume_initial",
                "volume_current",
                "price_open",
                "sl",
                "tp",
                "price_current",
                "price_stoplimit",
                "symbol",
                "comment",
                "external_id",
            ],
        )
        mt5_order = OrderTuple(
            ticket=tc.TEST_MAGIC_LARGE,
            time_setup=1702000000,
            time_setup_msc=1702000000123,
            time_done=0,
            time_done_msc=0,
            time_expiration=0,
            type=2,  # BUY_LIMIT
            type_time=0,  # GTC
            type_filling=0,  # FOK
            state=1,  # PLACED
            magic=c.Trading.DEFAULT_MAGIC_NUMBER,
            position_id=0,
            position_by_id=0,
            reason=0,  # CLIENT
            volume_initial=0.1,
            volume_current=0.1,
            price_open=1.0900,
            sl=1.0850,
            tp=1.1000,
            price_current=1.0895,
            price_stoplimit=0.0,
            symbol="EURUSD",
            comment="test order",
            external_id="",
        )

        order = MT5Models.Order.from_mt5(mt5_order)

        assert order is not None
        assert order.ticket == tc.TEST_MAGIC_LARGE
        assert order.type == 2
        assert order.volume_initial == 0.1
        assert order.symbol == "EURUSD"

    def test_from_mt5_none(self) -> None:
        """Test Order.from_mt5 with None returns None."""
        result = MT5Models.Order.from_mt5(None)
        assert result is None


class TestDeal:
    """Tests for Deal model."""

    def test_from_mt5(self) -> None:
        """Test creating Deal from MT5 data (using namedtuple)."""
        DealTuple = namedtuple(  # noqa: PYI024
            "DealTuple",
            [
                "ticket",
                "order",
                "time",
                "time_msc",
                "type",
                "entry",
                "magic",
                "position_id",
                "reason",
                "volume",
                "price",
                "commission",
                "swap",
                "profit",
                "fee",
                "symbol",
                "comment",
                "external_id",
            ],
        )
        mt5_deal = DealTuple(
            ticket=tc.TEST_MAGIC_ALT,
            order=tc.TEST_MAGIC_LARGE,
            time=1702000000,
            time_msc=1702000000123,
            type=0,  # BUY
            entry=0,  # IN
            magic=c.Trading.DEFAULT_MAGIC_NUMBER,
            position_id=99999,
            reason=0,  # CLIENT
            volume=0.1,
            price=1.0900,
            commission=-0.50,
            swap=0.0,
            profit=10.0,
            fee=0.0,
            symbol="EURUSD",
            comment="test deal",
            external_id="",
        )

        deal = MT5Models.Deal.from_mt5(mt5_deal)

        assert deal is not None
        assert deal.ticket == tc.TEST_MAGIC_ALT
        assert deal.order == tc.TEST_MAGIC_LARGE
        assert deal.volume == 0.1
        assert deal.profit == 10.0
        assert deal.symbol == "EURUSD"

    def test_from_mt5_none(self) -> None:
        """Test Deal.from_mt5 with None returns None."""
        result = MT5Models.Deal.from_mt5(None)
        assert result is None


class TestBookEntry:
    """Tests for BookEntry model."""

    def test_from_mt5(self) -> None:
        """Test creating BookEntry from MT5 data (using namedtuple)."""
        BookInfoTuple = namedtuple(  # noqa: PYI024
            "BookInfoTuple",
            ["type", "price", "volume", "volume_dbl"],
        )
        mt5_entry = BookInfoTuple(
            type=2,  # BUY
            price=1.0900,
            volume=100.0,
            volume_dbl=100.0,
        )

        entry = MT5Models.BookEntry.from_mt5(mt5_entry)

        assert entry is not None
        assert entry.type == 2
        assert entry.price == 1.0900
        assert entry.volume == 100.0

    def test_from_mt5_none(self) -> None:
        """Test BookEntry.from_mt5 with None returns None."""
        result = MT5Models.BookEntry.from_mt5(None)
        assert result is None
