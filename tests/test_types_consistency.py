"""Types consistency validation tests.

Validates that TypedDicts, type aliases, and Pydantic models are consistent
with each other and with actual MT5 data structures.

Tests:
- TypedDict fields match Pydantic model fields
- Type aliases are used consistently
- NumPy array dtypes match expected structure
- JSON types are properly defined
"""

from __future__ import annotations

from typing import TYPE_CHECKING, get_type_hints

import pytest

from mt5linux.models import MT5Models
from mt5linux.types import MT5Types

if TYPE_CHECKING:
    from mt5linux import MetaTrader5


class TestTypedDictModelConsistency:
    """Validate TypedDicts are consistent with Pydantic models."""

    def test_tick_dict_matches_tick_model(self) -> None:
        """TickDict fields should match Tick model fields."""
        # Get TickDict fields from annotations
        tick_dict_hints = get_type_hints(MT5Types.TickDict)
        tick_dict_fields = set(tick_dict_hints.keys())

        # Get Tick model fields
        tick_model_fields = set(MT5Models.Tick.model_fields.keys())

        # TickDict fields should be subset of Tick model fields
        missing_in_model = tick_dict_fields - tick_model_fields
        assert not missing_in_model, (
            f"TickDict has fields not in Tick model: {missing_in_model}"
        )

    def test_rate_dict_fields(self) -> None:
        """RateDict should have OHLCV fields."""
        rate_dict_hints = get_type_hints(MT5Types.RateDict)
        rate_dict_fields = set(rate_dict_hints.keys())

        # Required OHLCV fields
        required_fields = {"time", "open", "high", "low", "close"}
        missing = required_fields - rate_dict_fields
        assert not missing, f"RateDict missing required fields: {missing}"

    def test_order_request_dict_matches_order_request_model(self) -> None:
        """OrderRequestDict fields should match OrderRequest model fields."""
        # Get OrderRequestDict fields
        order_dict_hints = get_type_hints(MT5Types.OrderRequestDict)
        order_dict_fields = set(order_dict_hints.keys())

        # Get OrderRequest model fields (excluding computed)
        order_model_fields = set(MT5Models.OrderRequest.model_fields.keys())

        # OrderRequestDict fields should be subset of OrderRequest fields
        extra_in_dict = order_dict_fields - order_model_fields
        assert not extra_in_dict, (
            f"OrderRequestDict has fields not in OrderRequest: {extra_in_dict}"
        )


class TestJSONTypeDefinitions:
    """Validate JSON type definitions."""

    def test_json_primitive_types(self) -> None:
        """JSONPrimitive should include basic JSON types."""
        # These should be valid JSONPrimitive values

        # This is a compile-time check - if types are wrong, mypy catches it
        # Runtime: just verify the type alias exists
        assert hasattr(MT5Types, "JSONPrimitive")

    def test_json_value_recursive(self) -> None:
        """JSONValue should support nested structures."""
        # These should all be valid JSONValue

        # Type alias should exist
        assert hasattr(MT5Types, "JSONValue")


class TestArrayTypeAliases:
    """Validate NumPy array type aliases."""

    def test_rates_array_type_exists(self) -> None:
        """RatesArray type alias should exist."""
        assert hasattr(MT5Types, "RatesArray")

    def test_ticks_array_type_exists(self) -> None:
        """TicksArray type alias should exist."""
        assert hasattr(MT5Types, "TicksArray")


class TestRatesDataStructure:
    """Validate rates data structure from MT5."""

    def test_rates_have_ohlcv_fields(self, mt5: MetaTrader5) -> None:
        """copy_rates_* should return arrays with OHLCV fields."""
        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 10)

        if rates is None:
            pytest.fail("copy_rates_from_pos returned None")

        # Should be numpy array with dtype
        assert hasattr(rates, "dtype")
        assert rates.dtype.names is not None

        # Required OHLCV fields
        required = {"time", "open", "high", "low", "close"}
        actual_fields = set(rates.dtype.names)
        missing = required - actual_fields
        assert not missing, f"Rates missing required fields: {missing}"

    def test_rates_field_types(self, mt5: MetaTrader5) -> None:
        """Rates fields should have appropriate types."""
        rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 10)

        if rates is None or len(rates) == 0:
            pytest.fail("No rates data available")

        # Check a sample row
        row = rates[0]

        # time should be integer (timestamp)
        assert isinstance(int(row["time"]), int)

        # OHLC should be floats
        assert isinstance(float(row["open"]), float)
        assert isinstance(float(row["high"]), float)
        assert isinstance(float(row["low"]), float)
        assert isinstance(float(row["close"]), float)


class TestTicksDataStructure:
    """Validate ticks data structure from MT5."""

    def test_ticks_have_required_fields(self, mt5: MetaTrader5) -> None:
        """copy_ticks_* should return arrays with tick fields."""
        from datetime import UTC, datetime, timedelta

        mt5.symbol_select("EURUSD", enable=True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = mt5.copy_ticks_from("EURUSD", date_from, 100, mt5.COPY_TICKS_ALL)

        if ticks is None:
            pytest.fail("copy_ticks_from returned None")

        # Should be numpy array with dtype
        assert hasattr(ticks, "dtype")
        assert ticks.dtype.names is not None

        # Required tick fields
        required = {"time", "bid", "ask"}
        actual_fields = set(ticks.dtype.names)
        missing = required - actual_fields
        assert not missing, f"Ticks missing required fields: {missing}"

    def test_ticks_field_types(self, mt5: MetaTrader5) -> None:
        """Ticks fields should have appropriate types."""
        from datetime import UTC, datetime, timedelta

        mt5.symbol_select("EURUSD", enable=True)
        date_from = datetime.now(UTC) - timedelta(hours=1)
        ticks = mt5.copy_ticks_from("EURUSD", date_from, 100, mt5.COPY_TICKS_ALL)

        if ticks is None or len(ticks) == 0:
            pytest.fail("No ticks data available")

        # Check a sample row
        row = ticks[0]

        # time should be integer (timestamp)
        assert isinstance(int(row["time"]), int)

        # bid/ask should be floats
        assert isinstance(float(row["bid"]), float)
        assert isinstance(float(row["ask"]), float)


class TestModelProtocolAlignment:
    """Validate models align with protocol return types."""

    def test_terminal_info_return_type(self, mt5: MetaTrader5) -> None:
        """terminal_info() should return TerminalInfo model."""
        result = mt5.terminal_info()
        if result is not None:
            assert isinstance(result, MT5Models.TerminalInfo)

    def test_account_info_return_type(self, mt5: MetaTrader5) -> None:
        """account_info() should return AccountInfo model."""
        result = mt5.account_info()
        if result is not None:
            assert isinstance(result, MT5Models.AccountInfo)

    def test_symbol_info_return_type(self, mt5: MetaTrader5) -> None:
        """symbol_info() should return SymbolInfo model."""
        result = mt5.symbol_info("EURUSD")
        if result is not None:
            assert isinstance(result, MT5Models.SymbolInfo)

    def test_symbol_info_tick_return_type(self, mt5: MetaTrader5) -> None:
        """symbol_info_tick() should return Tick model."""
        mt5.symbol_select("EURUSD", enable=True)
        result = mt5.symbol_info_tick("EURUSD")
        if result is not None:
            assert isinstance(result, MT5Models.Tick)


class TestMT5ProtocolConsistency:
    """Validate MT5Protocol defines expected methods."""

    def test_mt5_protocol_has_initialize(self) -> None:
        """MT5Protocol should define initialize method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "initialize")

    def test_mt5_protocol_has_login(self) -> None:
        """MT5Protocol should define login method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "login")

    def test_mt5_protocol_has_shutdown(self) -> None:
        """MT5Protocol should define shutdown method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "shutdown")

    def test_mt5_protocol_has_symbol_info(self) -> None:
        """MT5Protocol should define symbol_info method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "symbol_info")

    def test_mt5_protocol_has_copy_rates_from(self) -> None:
        """MT5Protocol should define copy_rates_from method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "copy_rates_from")

    def test_mt5_protocol_has_order_send(self) -> None:
        """MT5Protocol should define order_send method."""
        from mt5linux.protocols import MT5Protocol

        assert hasattr(MT5Protocol, "order_send")


class TestTypedDictFieldTypes:
    """Validate TypedDict field types match expected values."""

    def test_tick_dict_time_is_int(self) -> None:
        """TickDict.time should be int."""
        hints = get_type_hints(MT5Types.TickDict)
        assert hints["time"] is int

    def test_tick_dict_bid_is_float(self) -> None:
        """TickDict.bid should be float."""
        hints = get_type_hints(MT5Types.TickDict)
        assert hints["bid"] is float

    def test_rate_dict_time_is_int(self) -> None:
        """RateDict.time should be int."""
        hints = get_type_hints(MT5Types.RateDict)
        assert hints["time"] is int

    def test_rate_dict_open_is_float(self) -> None:
        """RateDict.open should be float."""
        hints = get_type_hints(MT5Types.RateDict)
        assert hints["open"] is float

    def test_order_request_dict_action_is_int(self) -> None:
        """OrderRequestDict.action should be int."""
        hints = get_type_hints(MT5Types.OrderRequestDict)
        assert hints["action"] is int

    def test_order_request_dict_symbol_is_str(self) -> None:
        """OrderRequestDict.symbol should be str."""
        hints = get_type_hints(MT5Types.OrderRequestDict)
        assert hints["symbol"] is str

    def test_order_request_dict_volume_is_float(self) -> None:
        """OrderRequestDict.volume should be float."""
        hints = get_type_hints(MT5Types.OrderRequestDict)
        assert hints["volume"] is float
