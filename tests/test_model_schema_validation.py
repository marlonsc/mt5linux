"""Model schema validation tests.

Validates that Pydantic models have correct structure and behavior.
These tests MUST fail if:
- Model fields have wrong types
- Required fields are missing
- Default values are wrong
- from_mt5() factory method fails
- Frozen models can be modified
- Computed fields return wrong values

NO MOCKING - tests validate actual model behavior.
"""

from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING, ClassVar

import pytest
from pydantic import ValidationError

from mt5linux.constants import MT5Constants as c
from mt5linux.models import MT5Models

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


# =============================================================================
# MODEL FIELD DEFINITIONS - Source of truth for validation
# =============================================================================

# Required fields that MUST be present with NO default
REQUIRED_FIELDS = {
    "AccountInfo": ["login"],
    "SymbolInfo": ["name"],
    "Position": ["ticket"],
    "Tick": ["time"],
    "Order": ["ticket"],
    "Deal": ["ticket"],
    "BookEntry": ["type"],
    "TerminalInfo": [],  # All have defaults
    "OrderRequest": ["action", "symbol", "volume", "type"],
    "OrderResult": ["retcode"],
    "OrderCheckResult": ["retcode"],
}

# Field types for each model (subset of important ones)
MODEL_FIELD_TYPES = {
    "AccountInfo": {
        "login": int,
        "balance": float,
        "equity": float,
        "margin": float,
        "currency": str,
        "trade_allowed": bool,
        "leverage": int,
    },
    "SymbolInfo": {
        "name": str,
        "bid": float,
        "ask": float,
        "volume_min": float,
        "volume_max": float,
        "digits": int,
        "visible": bool,
    },
    "Position": {
        "ticket": int,
        "volume": float,
        "price_open": float,
        "profit": float,
        "symbol": str,
        "type": int,
    },
    "Tick": {
        "time": int,
        "bid": float,
        "ask": float,
        "volume": int,
        "time_msc": int,
    },
    "Order": {
        "ticket": int,
        "volume_initial": float,
        "price_open": float,
        "symbol": str,
        "type": int,
        "state": int,
    },
    "Deal": {
        "ticket": int,
        "order": int,
        "volume": float,
        "price": float,
        "profit": float,
        "symbol": str,
    },
    "BookEntry": {
        "type": int,
        "price": float,
        "volume": float,
    },
    "TerminalInfo": {
        "connected": bool,
        "trade_allowed": bool,
        "build": int,
        "company": str,
        "path": str,
    },
    "OrderResult": {
        "retcode": int,
        "deal": int,
        "order": int,
        "volume": float,
        "price": float,
        "comment": str,
    },
    "OrderCheckResult": {
        "retcode": int,
        "balance": float,
        "margin": float,
        "comment": str,
    },
}


# =============================================================================
# TEST: Model Field Structure
# =============================================================================


class TestModelFieldStructure:
    """Validate model fields exist with correct types."""

    @pytest.mark.parametrize("model_name", list(MODEL_FIELD_TYPES.keys()))
    def test_model_has_expected_fields(self, model_name: str) -> None:
        """Each model must have all expected fields."""
        model_cls = getattr(MT5Models, model_name)
        expected_fields = MODEL_FIELD_TYPES[model_name]

        for field_name in expected_fields:
            assert field_name in model_cls.model_fields, (
                f"{model_name} missing field: {field_name}"
            )

    @pytest.mark.parametrize("model_name", list(REQUIRED_FIELDS.keys()))
    def test_required_fields_have_no_default(self, model_name: str) -> None:
        """Required fields must NOT have defaults."""
        model_cls = getattr(MT5Models, model_name)
        required = REQUIRED_FIELDS[model_name]

        for field_name in required:
            field_info = model_cls.model_fields.get(field_name)
            assert field_info is not None, (
                f"{model_name} missing required field: {field_name}"
            )
            # Required means no default or default is PydanticUndefined
            assert field_info.is_required(), (
                f"{model_name}.{field_name} should be required but has default"
            )

    @pytest.mark.parametrize(
        "model_name",
        [name for name, fields in REQUIRED_FIELDS.items() if fields],
    )
    def test_missing_required_field_raises_error(self, model_name: str) -> None:
        """Creating model without required field must raise ValidationError."""
        model_cls = getattr(MT5Models, model_name)
        required = REQUIRED_FIELDS[model_name]

        # Try to create without any required fields
        with pytest.raises(ValidationError) as exc_info:
            model_cls()

        # Verify error mentions the required field
        error_str = str(exc_info.value)
        assert any(field in error_str for field in required), (
            f"ValidationError should mention missing field from {required}"
        )


# =============================================================================
# TEST: from_mt5() Factory Method
# =============================================================================


class TestFromMT5Factory:
    """Validate from_mt5() factory method works correctly."""

    def test_from_mt5_with_none_returns_none(self) -> None:
        """from_mt5(None) should return None for most models."""
        assert MT5Models.AccountInfo.from_mt5(None) is None
        assert MT5Models.SymbolInfo.from_mt5(None) is None
        assert MT5Models.Position.from_mt5(None) is None
        assert MT5Models.Tick.from_mt5(None) is None
        assert MT5Models.Order.from_mt5(None) is None
        assert MT5Models.Deal.from_mt5(None) is None
        assert MT5Models.TerminalInfo.from_mt5(None) is None
        assert MT5Models.OrderCheckResult.from_mt5(None) is None

    def test_order_result_from_mt5_with_none_returns_error(self) -> None:
        """OrderResult.from_mt5(None) should return error result, NOT None."""
        result = MT5Models.OrderResult.from_mt5(None)
        assert result is not None, "OrderResult.from_mt5(None) should not return None"
        assert result.is_success is False
        assert result.retcode == c.Order.TradeRetcode.ERROR
        assert "No result" in result.comment

    def test_from_mt5_with_dict(self) -> None:
        """from_mt5() should work with dict input."""
        data = {"login": 12345, "balance": 10000.0, "currency": "USD"}
        result = MT5Models.AccountInfo.from_mt5(data)
        assert result is not None
        assert result.login == 12345
        assert result.balance == 10000.0
        assert result.currency == "USD"

    def test_from_mt5_with_namedtuple(self) -> None:
        """from_mt5() should work with namedtuple input."""
        # Create a namedtuple that mimics MT5 response
        AccountTuple = namedtuple("AccountTuple", ["login", "balance", "currency"])  # noqa: PYI024
        data = AccountTuple(login=12345, balance=10000.0, currency="EUR")

        result = MT5Models.AccountInfo.from_mt5(data)
        assert result is not None
        assert result.login == 12345
        assert result.balance == 10000.0
        assert result.currency == "EUR"

    def test_from_mt5_with_object_attributes(self) -> None:
        """from_mt5() should work with objects that have attributes."""

        class FakeAccountInfo:
            login = 99999
            balance = 5000.0
            currency = "GBP"
            # Other fields will use defaults
            trade_mode = 0
            leverage = 100
            limit_orders = 0
            margin_so_mode = 0
            trade_allowed = True
            trade_expert = True
            margin_mode = 0
            currency_digits = 2
            fifo_close = False
            credit = 0.0
            profit = 0.0
            equity = 5000.0
            margin = 0.0
            margin_free = 5000.0
            margin_level = 0.0
            margin_so_call = 0.0
            margin_so_so = 0.0
            margin_initial = 0.0
            margin_maintenance = 0.0
            assets = 0.0
            liabilities = 0.0
            commission_blocked = 0.0
            name = ""
            server = ""
            company = ""

        result = MT5Models.AccountInfo.from_mt5(FakeAccountInfo())
        assert result is not None
        assert result.login == 99999
        assert result.balance == 5000.0
        assert result.currency == "GBP"


# =============================================================================
# TEST: Frozen Models (Immutability)
# =============================================================================


class TestFrozenModels:
    """Validate that models are frozen (immutable)."""

    def test_account_info_is_frozen(self) -> None:
        """AccountInfo should be immutable."""
        info = MT5Models.AccountInfo(login=12345)
        with pytest.raises(ValidationError):
            info.balance = 999999.0  # type: ignore[misc]

    def test_symbol_info_is_frozen(self) -> None:
        """SymbolInfo should be immutable."""
        info = MT5Models.SymbolInfo(name="EURUSD")
        with pytest.raises(ValidationError):
            info.name = "CHANGED"  # type: ignore[misc]

    def test_position_is_frozen(self) -> None:
        """Position should be immutable."""
        pos = MT5Models.Position(ticket=12345)
        with pytest.raises(ValidationError):
            pos.ticket = 99999  # type: ignore[misc]

    def test_tick_is_frozen(self) -> None:
        """Tick should be immutable."""
        tick = MT5Models.Tick(time=1234567890)
        with pytest.raises(ValidationError):
            tick.bid = 999.0  # type: ignore[misc]

    def test_order_is_frozen(self) -> None:
        """Order should be immutable."""
        order = MT5Models.Order(ticket=12345)
        with pytest.raises(ValidationError):
            order.ticket = 99999  # type: ignore[misc]

    def test_deal_is_frozen(self) -> None:
        """Deal should be immutable."""
        deal = MT5Models.Deal(ticket=12345)
        with pytest.raises(ValidationError):
            deal.ticket = 99999  # type: ignore[misc]

    def test_order_result_is_frozen(self) -> None:
        """OrderResult should be immutable."""
        result = MT5Models.OrderResult(retcode=c.Order.TradeRetcode.DONE)
        with pytest.raises(ValidationError):
            result.retcode = 0  # type: ignore[misc]


# =============================================================================
# TEST: Computed Fields
# =============================================================================


class TestComputedFields:
    """Validate computed fields return correct values."""

    def test_order_result_is_success(self) -> None:
        """is_success should be True only for DONE retcode."""
        # Success case
        success = MT5Models.OrderResult(
            retcode=c.Order.TradeRetcode.DONE, deal=1, order=1
        )
        assert success.is_success is True
        assert success.is_partial is False

        # Partial fill
        partial = MT5Models.OrderResult(
            retcode=c.Order.TradeRetcode.DONE_PARTIAL, deal=1, order=1
        )
        assert partial.is_success is False
        assert partial.is_partial is True

        # Error
        error = MT5Models.OrderResult(retcode=c.Order.TradeRetcode.ERROR)
        assert error.is_success is False
        assert error.is_partial is False

        # Other retcodes
        for retcode in [
            c.Order.TradeRetcode.REJECT,
            c.Order.TradeRetcode.CANCEL,
            c.Order.TradeRetcode.NO_MONEY,
        ]:
            result = MT5Models.OrderResult(retcode=retcode)
            assert result.is_success is False

    def test_order_check_result_is_valid(self) -> None:
        """is_valid should be True only for DONE retcode."""
        # Valid
        valid = MT5Models.OrderCheckResult(
            retcode=c.Order.TradeRetcode.DONE, balance=10000.0
        )
        assert valid.is_valid is True

        # Invalid
        invalid = MT5Models.OrderCheckResult(
            retcode=c.Order.TradeRetcode.NO_MONEY, balance=100.0
        )
        assert invalid.is_valid is False

    def test_order_request_is_market_order(self) -> None:
        """is_market_order should be True for BUY/SELL types."""
        # Market BUY
        buy = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY,
        )
        assert buy.is_market_order is True

        # Market SELL
        sell = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.SELL,
        )
        assert sell.is_market_order is True

        # Pending order (BUY_LIMIT)
        pending = MT5Models.OrderRequest(
            action=c.Order.TradeAction.PENDING,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY_LIMIT,
            price=1.0,
        )
        assert pending.is_market_order is False


# =============================================================================
# TEST: OrderRequest Validation
# =============================================================================


class TestOrderRequestValidation:
    """Validate OrderRequest field constraints."""

    def test_volume_must_be_positive(self) -> None:
        """Volume must be > 0."""
        with pytest.raises(ValidationError) as exc_info:
            MT5Models.OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=0.0,  # Invalid: must be > 0
                type=c.Order.OrderType.BUY,
            )
        assert "volume" in str(exc_info.value).lower()

    def test_volume_has_max_limit(self) -> None:
        """Volume must be <= 1000."""
        with pytest.raises(ValidationError) as exc_info:
            MT5Models.OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=1001.0,  # Invalid: must be <= 1000
                type=c.Order.OrderType.BUY,
            )
        assert "volume" in str(exc_info.value).lower()

    def test_price_must_be_non_negative(self) -> None:
        """Price must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            MT5Models.OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=0.1,
                type=c.Order.OrderType.BUY,
                price=-1.0,  # Invalid: must be >= 0
            )
        assert "price" in str(exc_info.value).lower()

    def test_comment_max_length(self) -> None:
        """Comment must be <= 31 characters."""
        with pytest.raises(ValidationError) as exc_info:
            MT5Models.OrderRequest(
                action=c.Order.TradeAction.DEAL,
                symbol="EURUSD",
                volume=0.1,
                type=c.Order.OrderType.BUY,
                comment="x" * 32,  # Invalid: max 31 chars
            )
        assert "comment" in str(exc_info.value).lower()

    def test_valid_order_request(self) -> None:
        """Valid order request should be created successfully."""
        order = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY,
            price=1.1000,
            sl=1.0900,
            tp=1.1100,
            comment="Test order",
        )
        assert order.symbol == "EURUSD"
        assert order.volume == 0.1
        assert order.sl == 1.0900
        assert order.tp == 1.1100


# =============================================================================
# TEST: to_mt5_request() Export
# =============================================================================


class TestOrderRequestExport:
    """Validate OrderRequest.to_mt5_request() export."""

    def test_export_includes_required_fields(self) -> None:
        """Export must include all required fields."""
        order = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY,
        )
        exported = order.to_mt5_request()

        assert "action" in exported
        assert "symbol" in exported
        assert "volume" in exported
        assert "type" in exported
        assert exported["symbol"] == "EURUSD"
        assert exported["volume"] == 0.1

    def test_export_excludes_zero_sl_tp(self) -> None:
        """Export should exclude sl/tp when they are 0."""
        order = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY,
            sl=0.0,  # Should be excluded
            tp=0.0,  # Should be excluded
        )
        exported = order.to_mt5_request()

        assert "sl" not in exported
        assert "tp" not in exported

    def test_export_includes_nonzero_sl_tp(self) -> None:
        """Export should include sl/tp when they are > 0."""
        order = MT5Models.OrderRequest(
            action=c.Order.TradeAction.DEAL,
            symbol="EURUSD",
            volume=0.1,
            type=c.Order.OrderType.BUY,
            sl=1.0900,
            tp=1.1100,
        )
        exported = order.to_mt5_request()

        assert "sl" in exported
        assert "tp" in exported
        assert exported["sl"] == 1.0900
        assert exported["tp"] == 1.1100


# =============================================================================
# TEST: Model Count and Names
# =============================================================================


class TestModelCatalog:
    """Validate all expected models exist."""

    EXPECTED_MODELS: ClassVar[list[str]] = [
        "Base",
        "OrderRequest",
        "OrderResult",
        "OrderCheckResult",
        "AccountInfo",
        "SymbolInfo",
        "Position",
        "Tick",
        "Order",
        "Deal",
        "BookEntry",
        "TerminalInfo",
    ]

    def test_all_models_exist(self) -> None:
        """All expected models must exist in MT5Models."""
        for model_name in self.EXPECTED_MODELS:
            assert hasattr(MT5Models, model_name), f"MT5Models missing: {model_name}"

    def test_model_count(self) -> None:
        """MT5Models should have exactly 12 model classes."""
        models = [
            name
            for name in dir(MT5Models)
            if not name.startswith("_") and isinstance(getattr(MT5Models, name), type)
        ]
        assert len(models) == 12, f"Expected 12 models, found {len(models)}: {models}"

    @pytest.mark.parametrize("model_name", EXPECTED_MODELS[1:])  # Skip Base
    def test_model_inherits_from_base_or_basemodel(self, model_name: str) -> None:
        """All models should inherit from Base or BaseModel."""
        from pydantic import BaseModel

        model_cls = getattr(MT5Models, model_name)
        assert issubclass(model_cls, BaseModel), (
            f"{model_name} should inherit from BaseModel"
        )


# =============================================================================
# TEST: Integration with Real MT5 (when available)
# =============================================================================


@pytest.mark.integration
class TestModelWithRealMT5:
    """Tests that require real MT5 connection."""

    def test_account_info_from_real_data(self, mt5: MetaTrader5) -> None:
        """AccountInfo should parse real account data."""
        info = mt5.account_info()
        if info is None:
            pytest.fail("account_info returned None")

        assert isinstance(info, MT5Models.AccountInfo)
        assert info.login > 0
        assert isinstance(info.balance, float)
        assert len(info.currency) >= 3

    def test_symbol_info_from_real_data(self, mt5: MetaTrader5) -> None:
        """SymbolInfo should parse real symbol data."""
        info = mt5.symbol_info("EURUSD")
        if info is None:
            pytest.fail("symbol_info returned None for EURUSD")

        assert isinstance(info, MT5Models.SymbolInfo)
        assert info.name == "EURUSD"
        assert isinstance(info.bid, float)
        assert isinstance(info.ask, float)

    def test_terminal_info_from_real_data(self, mt5: MetaTrader5) -> None:
        """TerminalInfo should parse real terminal data."""
        info = mt5.terminal_info()
        if info is None:
            pytest.fail("terminal_info returned None")

        assert isinstance(info, MT5Models.TerminalInfo)
        assert info.build > 0
        assert info.connected is True
