
"""Real MT5 module validation tests.

These tests validate our protocols and models against the ACTUAL MetaTrader5
PyPI module running on the server. They use the GetMethods and GetModels
gRPC endpoints to introspect the real MT5 module.

Tests:
- Protocol method names match real MT5 module methods
- Model fields match real MT5 namedtuple structures
- Method signatures are compatible

This ensures we stay in sync with the actual MetaTrader5 package.

NOTE: These tests require the bridge server to have GetMethods/GetModels RPCs.
If the server returns UNIMPLEMENTED, tests will be skipped with instructions
to rebuild the container with the updated bridge.py.
"""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING

import grpc
import grpc.aio
import pytest

from mt5linux.models import MT5Models
from mt5linux.protocols import MT5Protocol

if TYPE_CHECKING:
    from mt5linux import MetaTrader5

# Skip message when server doesn't support introspection RPCs
SKIP_UNIMPLEMENTED = (
    "Server doesn't support GetMethods/GetModels. "
    "Rebuild the container with updated bridge.py to enable these tests."
)


def _get_methods_safe(mt5: MetaTrader5) -> list[dict[str, object]] | None:
    """Get methods from server, returning None if not implemented."""
    try:
        return mt5.get_methods()
    except (grpc.RpcError, grpc.aio.AioRpcError) as e:
        if e.code() == grpc.StatusCode.UNIMPLEMENTED:
            return None
        raise


def _get_models_safe(mt5: MetaTrader5) -> list[dict[str, object]] | None:
    """Get models from server, returning None if not implemented."""
    try:
        return mt5.get_models()
    except (grpc.RpcError, grpc.aio.AioRpcError) as e:
        if e.code() == grpc.StatusCode.UNIMPLEMENTED:
            return None
        raise


# Expected MT5 methods (public API from MetaTrader5 PyPI)
# These are the methods we expect in the real MT5 module
MT5_PUBLIC_METHODS = {
    "initialize",
    "login",
    "shutdown",
    "version",
    "last_error",
    "terminal_info",
    "account_info",
    "symbols_total",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "symbol_select",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
    "order_calc_margin",
    "order_calc_profit",
    "order_check",
    "order_send",
    "positions_total",
    "positions_get",
    "orders_total",
    "orders_get",
    "history_orders_total",
    "history_orders_get",
    "history_deals_total",
    "history_deals_get",
    "market_book_add",
    "market_book_get",
    "market_book_release",
}

# Expected MT5 namedtuple models
MT5_MODEL_NAMES = {
    "AccountInfo",
    "SymbolInfo",
    "Tick",
    "TradePosition",
    "TradeOrder",
    "TradeDeal",
    "BookInfo",
    "TerminalInfo",
    "TradeRequest",
    "OrderSendResult",
    "OrderCheckResult",
}


class TestRealMT5Methods:
    """Validate protocol methods against real MT5 module."""

    def test_get_methods_returns_data(self, mt5: MetaTrader5) -> None:
        """get_methods() should return method information."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        assert methods, "get_methods() returned empty list"
        assert len(methods) > 0, "Expected at least one method"

    def test_real_mt5_has_expected_methods(self, mt5: MetaTrader5) -> None:
        """Real MT5 module should have all expected public methods."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        method_names = {m["name"] for m in methods}

        # All expected methods should exist in real MT5
        missing = MT5_PUBLIC_METHODS - method_names
        assert not missing, (
            f"Real MT5 module missing expected methods: {sorted(missing)}"
        )

    def test_protocol_methods_exist_in_real_mt5(self, mt5: MetaTrader5) -> None:
        """All protocol methods should exist in real MT5 module."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_method_names = {m["name"] for m in methods}

        # Get protocol method names (exclude private/magic)
        protocol_methods = {
            m
            for m in dir(MT5Protocol)
            if not m.startswith("_") and callable(getattr(MT5Protocol, m))
        }

        # All protocol methods should exist in real MT5
        missing = protocol_methods - real_method_names
        assert not missing, f"Protocol has methods not in real MT5: {sorted(missing)}"

    def test_real_mt5_method_count(self, mt5: MetaTrader5) -> None:
        """Real MT5 should have at least 32 public methods."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        # Filter to only public methods we care about
        public_methods = [m for m in methods if m["name"] in MT5_PUBLIC_METHODS]
        assert len(public_methods) >= 32, (
            f"Expected at least 32 public methods, found {len(public_methods)}"
        )

    def test_method_signatures_available(self, mt5: MetaTrader5) -> None:
        """Methods should have parameter information."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        # Check some key methods have parameters
        for method in methods:
            if method["name"] == "login":
                params = method["parameters"]
                param_names = {p["name"] for p in params}
                # login should have: login, password, server, timeout
                assert "login" in param_names or len(params) > 0, (
                    "login method should have parameters"
                )
                break


class TestRealMT5Models:
    """Validate our Pydantic models against real MT5 namedtuples."""

    def test_get_models_returns_data(self, mt5: MetaTrader5) -> None:
        """get_models() should return model information."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        assert models, "get_models() returned empty list"
        assert len(models) > 0, "Expected at least one model"

    def test_real_mt5_has_expected_models(self, mt5: MetaTrader5) -> None:
        """Real MT5 module should have expected namedtuple types."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        model_names = {m["name"] for m in models}

        # All expected models should exist in real MT5
        missing = MT5_MODEL_NAMES - model_names
        assert not missing, (
            f"Real MT5 module missing expected models: {sorted(missing)}"
        )

    def test_account_info_fields_match(self, mt5: MetaTrader5) -> None:
        """Our AccountInfo model should have same fields as real MT5."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_account_info = next(
            (m for m in models if m["name"] == "AccountInfo"), None
        )

        if real_account_info is None:
            pytest.fail("AccountInfo not found in real MT5 models")

        real_fields = {f["name"] for f in real_account_info["fields"]}
        our_fields = set(MT5Models.AccountInfo.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"AccountInfo missing fields from real MT5: {sorted(missing)}"
        )

    def test_symbol_info_fields_match(self, mt5: MetaTrader5) -> None:
        """Our SymbolInfo model should have same fields as real MT5."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_symbol_info = next((m for m in models if m["name"] == "SymbolInfo"), None)

        if real_symbol_info is None:
            pytest.fail("SymbolInfo not found in real MT5 models")

        real_fields = {f["name"] for f in real_symbol_info["fields"]}
        our_fields = set(MT5Models.SymbolInfo.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"SymbolInfo missing fields from real MT5: {sorted(missing)}"
        )

    def test_tick_fields_match(self, mt5: MetaTrader5) -> None:
        """Our Tick model should have same fields as real MT5."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_tick = next((m for m in models if m["name"] == "Tick"), None)

        if real_tick is None:
            pytest.fail("Tick not found in real MT5 models")

        real_fields = {f["name"] for f in real_tick["fields"]}
        our_fields = set(MT5Models.Tick.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, f"Tick missing fields from real MT5: {sorted(missing)}"

    def test_position_fields_match(self, mt5: MetaTrader5) -> None:
        """Our Position model should have same fields as real MT5 TradePosition."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_position = next((m for m in models if m["name"] == "TradePosition"), None)

        if real_position is None:
            pytest.fail("TradePosition not found in real MT5 models")

        real_fields = {f["name"] for f in real_position["fields"]}
        our_fields = set(MT5Models.Position.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"Position missing fields from real MT5 TradePosition: {sorted(missing)}"
        )

    def test_order_fields_match(self, mt5: MetaTrader5) -> None:
        """Our Order model should have same fields as real MT5 TradeOrder."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_order = next((m for m in models if m["name"] == "TradeOrder"), None)

        if real_order is None:
            pytest.fail("TradeOrder not found in real MT5 models")

        real_fields = {f["name"] for f in real_order["fields"]}
        our_fields = set(MT5Models.Order.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"Order missing fields from real MT5 TradeOrder: {sorted(missing)}"
        )

    def test_deal_fields_match(self, mt5: MetaTrader5) -> None:
        """Our Deal model should have same fields as real MT5 TradeDeal."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_deal = next((m for m in models if m["name"] == "TradeDeal"), None)

        if real_deal is None:
            pytest.fail("TradeDeal not found in real MT5 models")

        real_fields = {f["name"] for f in real_deal["fields"]}
        our_fields = set(MT5Models.Deal.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"Deal missing fields from real MT5 TradeDeal: {sorted(missing)}"
        )

    def test_terminal_info_fields_match(self, mt5: MetaTrader5) -> None:
        """Our TerminalInfo model should have same fields as real MT5."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_terminal = next((m for m in models if m["name"] == "TerminalInfo"), None)

        if real_terminal is None:
            pytest.fail("TerminalInfo not found in real MT5 models")

        real_fields = {f["name"] for f in real_terminal["fields"]}
        our_fields = set(MT5Models.TerminalInfo.model_fields.keys())

        # Our model should have all fields from real MT5
        missing = real_fields - our_fields
        assert not missing, (
            f"TerminalInfo missing fields from real MT5: {sorted(missing)}"
        )


class TestRealMT5ModelFieldOrder:
    """Validate field order matches real MT5 namedtuples."""

    def test_account_info_field_order(self, mt5: MetaTrader5) -> None:
        """AccountInfo field order should match real MT5."""
        models = _get_models_safe(mt5)
        if models is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_model = next((m for m in models if m["name"] == "AccountInfo"), None)

        if real_model is None:
            pytest.fail("AccountInfo not found in real MT5 models")

        # Get fields in order
        real_fields = sorted(real_model["fields"], key=operator.itemgetter("index"))
        real_field_names = [f["name"] for f in real_fields]

        # Our model field order (Pydantic preserves insertion order)
        our_field_names = list(MT5Models.AccountInfo.model_fields.keys())

        # Compare first N fields (we may have extra computed fields)
        n = min(len(real_field_names), len(our_field_names))
        for i in range(n):
            assert real_field_names[i] == our_field_names[i], (
                f"AccountInfo field order mismatch at index {i}: "
                f"real={real_field_names[i]}, ours={our_field_names[i]}"
            )


class TestMethodParameterValidation:
    """Validate method parameters match real MT5 signatures."""

    def test_login_parameters(self, mt5: MetaTrader5) -> None:
        """login() parameters should match real MT5."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        login_method = next((m for m in methods if m["name"] == "login"), None)

        if login_method is None:
            pytest.fail("login method not found")

        params = login_method["parameters"]
        param_names = [p["name"] for p in params]

        # Real MT5 login docstring exposes: login, password, server
        # Note: timeout exists in the actual function but isn't in the docstring
        expected = {"login", "password", "server"}
        actual = set(param_names)

        # All expected params should exist
        missing = expected - actual
        assert not missing, f"login() missing parameters: {missing}"

    def test_symbol_select_parameters(self, mt5: MetaTrader5) -> None:
        """symbol_select() parameters should match real MT5."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        method = next((m for m in methods if m["name"] == "symbol_select"), None)

        if method is None:
            pytest.fail("symbol_select method not found")

        params = method["parameters"]
        param_names = [p["name"] for p in params]

        # Real MT5 symbol_select has: symbol, enable
        assert "symbol" in param_names, "symbol_select missing 'symbol' param"

    def test_copy_rates_from_parameters(self, mt5: MetaTrader5) -> None:
        """copy_rates_from() parameters should match real MT5."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        method = next((m for m in methods if m["name"] == "copy_rates_from"), None)

        if method is None:
            pytest.fail("copy_rates_from method not found")

        params = method["parameters"]
        param_names = [p["name"] for p in params]

        # Real MT5 copy_rates_from has: symbol, timeframe, date_from, count
        expected = {"symbol", "timeframe", "date_from", "count"}
        actual = set(param_names)

        missing = expected - actual
        assert not missing, f"copy_rates_from() missing parameters: {missing}"


class TestRealVsProtocolConsistency:
    """Cross-validate that real MT5 matches our protocol exactly."""

    def test_method_count_matches(self, mt5: MetaTrader5) -> None:
        """Protocol should have same method count as real MT5 public API."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_public = {m["name"] for m in methods if m["name"] in MT5_PUBLIC_METHODS}

        protocol_methods = {
            m
            for m in dir(MT5Protocol)
            if not m.startswith("_") and callable(getattr(MT5Protocol, m))
        }

        # Both should have exactly 32 methods
        assert len(protocol_methods) == 32, (
            f"Protocol should have 32 methods, has {len(protocol_methods)}"
        )
        assert len(real_public) == 32, (
            f"Real MT5 should have 32 public methods, found {len(real_public)}"
        )

    def test_exact_method_set_match(self, mt5: MetaTrader5) -> None:
        """Protocol methods should exactly match real MT5 public methods."""
        methods = _get_methods_safe(mt5)
        if methods is None:
            pytest.fail("SKIP_UNIMPLEMENTED")
        real_public = {m["name"] for m in methods if m["name"] in MT5_PUBLIC_METHODS}

        protocol_methods = {
            m
            for m in dir(MT5Protocol)
            if not m.startswith("_") and callable(getattr(MT5Protocol, m))
        }

        # Sets should be equal
        only_in_protocol = protocol_methods - real_public
        only_in_real = real_public - protocol_methods

        assert not only_in_protocol, (
            f"Methods only in protocol: {sorted(only_in_protocol)}"
        )
        assert not only_in_real, f"Methods only in real MT5: {sorted(only_in_real)}"
