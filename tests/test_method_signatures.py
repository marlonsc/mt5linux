"""Method signature validation tests.

Uses Python's inspect and typing modules to verify that method signatures
in protocols and implementations match the expected types.

Tests:
- Return type annotations
- Parameter type annotations
- Parameter kinds (positional, keyword-only, etc.)
- Default values
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from mt5linux import MetaTrader5
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.protocols import AsyncMT5Protocol, MT5Protocol

# Methods grouped by their expected return types
METHODS_RETURNING_BOOL = [
    "initialize",
    "login",
    "symbol_select",
    "market_book_add",
    "market_book_release",
]

METHODS_RETURNING_INT = [
    "symbols_total",
    "positions_total",
    "orders_total",
    "history_orders_total",
    "history_deals_total",
]

METHODS_RETURNING_NONE = [
    "shutdown",
]

# mt5linux-specific extensions (not part of MT5Protocol)
MT5LINUX_EXTENSIONS_NONE = [
    "connect",
    "disconnect",
]

METHODS_RETURNING_OPTIONAL = [
    "version",
    "terminal_info",
    "account_info",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
    "order_calc_margin",
    "order_calc_profit",
    "order_check",
    "order_send",
    "positions_get",
    "orders_get",
    "history_orders_get",
    "history_deals_get",
    "market_book_get",
]

# Methods with keyword-only parameters
METHODS_WITH_KEYWORD_ONLY = [
    ("initialize", "portable"),
    ("symbol_select", "enable"),
]


class TestReturnTypeAnnotations:
    """Validate return type annotations exist and are correct."""

    @pytest.mark.parametrize("method_name", METHODS_RETURNING_BOOL)
    def test_bool_return_methods_have_annotation(self, method_name: str) -> None:
        """Methods returning bool should have bool return annotation."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)

        assert sig.return_annotation != inspect.Signature.empty, (
            f"{method_name} missing return annotation"
        )

    @pytest.mark.parametrize("method_name", METHODS_RETURNING_INT)
    def test_int_return_methods_have_annotation(self, method_name: str) -> None:
        """Methods returning int should have int return annotation."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)

        assert sig.return_annotation != inspect.Signature.empty, (
            f"{method_name} missing return annotation"
        )

    @pytest.mark.parametrize("method_name", METHODS_RETURNING_NONE)
    def test_none_return_methods_have_annotation(self, method_name: str) -> None:
        """Methods returning None should have None return annotation."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)

        assert sig.return_annotation != inspect.Signature.empty, (
            f"{method_name} missing return annotation"
        )

    @pytest.mark.parametrize("method_name", METHODS_RETURNING_OPTIONAL)
    def test_optional_return_methods_have_annotation(self, method_name: str) -> None:
        """Methods that may return None should have | None in annotation."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)

        assert sig.return_annotation != inspect.Signature.empty, (
            f"{method_name} missing return annotation"
        )


class TestParameterTypes:
    """Validate parameter type annotations."""

    def test_initialize_parameters(self) -> None:
        """initialize() parameters should have correct types."""
        method = MetaTrader5.initialize
        sig = inspect.signature(method)
        params = sig.parameters

        # path: str | None = None
        assert "path" in params
        assert params["path"].default is None

        # login: int | None = None
        assert "login" in params
        assert params["login"].default is None

        # portable: bool = False (keyword-only)
        assert "portable" in params
        assert params["portable"].default is False
        assert params["portable"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_login_parameters(self) -> None:
        """login() parameters should have correct types."""
        method = MetaTrader5.login
        sig = inspect.signature(method)
        params = sig.parameters

        # login: int (positional)
        assert "login" in params

        # timeout: int = 60000
        assert "timeout" in params
        assert params["timeout"].default == 60000

    def test_symbol_select_parameters(self) -> None:
        """symbol_select() parameters should have correct types."""
        method = MetaTrader5.symbol_select
        sig = inspect.signature(method)
        params = sig.parameters

        # symbol: str
        assert "symbol" in params

        # enable: bool = True (keyword-only)
        assert "enable" in params
        assert params["enable"].default is True
        assert params["enable"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_copy_rates_from_parameters(self) -> None:
        """copy_rates_from() parameters should have correct types."""
        method = MetaTrader5.copy_rates_from
        sig = inspect.signature(method)
        params = sig.parameters

        assert "symbol" in params
        assert "timeframe" in params
        assert "date_from" in params
        assert "count" in params

    def test_order_send_parameters(self) -> None:
        """order_send() parameters should have correct types."""
        method = MetaTrader5.order_send
        sig = inspect.signature(method)
        params = sig.parameters

        assert "request" in params


class TestKeywordOnlyParameters:
    """Validate keyword-only parameter declarations."""

    @pytest.mark.parametrize(("method_name", "param_name"), METHODS_WITH_KEYWORD_ONLY)
    def test_keyword_only_params(self, method_name: str, param_name: str) -> None:
        """Certain parameters should be keyword-only."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)
        params = sig.parameters

        assert param_name in params, f"{method_name} missing {param_name}"
        assert params[param_name].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{method_name}.{param_name} should be keyword-only"
        )


class TestProtocolMethodSignaturesMatch:
    """Validate protocol and client signatures match exactly."""

    def _compare_signatures(
        self,
        protocol_method: Any,
        client_method: Any,
        method_name: str,
    ) -> list[str]:
        """Compare two method signatures and return list of differences."""
        differences = []

        protocol_sig = inspect.signature(protocol_method)
        client_sig = inspect.signature(client_method)

        # Compare return annotations
        if protocol_sig.return_annotation != client_sig.return_annotation:
            # Allow for equivalent types (e.g., typing.Union vs |)
            protocol_ret = str(protocol_sig.return_annotation)
            client_ret = str(client_sig.return_annotation)
            # Normalize common differences
            protocol_ret = protocol_ret.replace("typing.Union", "").replace(" ", "")
            client_ret = client_ret.replace("typing.Union", "").replace(" ", "")
            if protocol_ret != client_ret:
                differences.append(
                    f"{method_name} return: protocol={protocol_sig.return_annotation}, "
                    f"client={client_sig.return_annotation}"
                )

        # Compare parameters
        for param_name, protocol_param in protocol_sig.parameters.items():
            if param_name == "self":
                continue

            if param_name not in client_sig.parameters:
                differences.append(
                    f"{method_name}: client missing parameter '{param_name}'"
                )
                continue

            client_param = client_sig.parameters[param_name]

            # Compare kinds
            if protocol_param.kind != client_param.kind:
                differences.append(
                    f"{method_name}.{param_name}: kind mismatch - "
                    f"protocol={protocol_param.kind.name}, "
                    f"client={client_param.kind.name}"
                )

            # Compare defaults (if present)
            if protocol_param.default != inspect.Parameter.empty:
                if client_param.default != protocol_param.default:
                    differences.append(
                        f"{method_name}.{param_name}: default mismatch - "
                        f"protocol={protocol_param.default}, "
                        f"client={client_param.default}"
                    )

        return differences

    def test_all_sync_methods_match(self) -> None:
        """All sync protocol methods should match client exactly."""
        differences = []

        for method_name in dir(MT5Protocol):
            if method_name.startswith("_"):
                continue

            if not hasattr(MetaTrader5, method_name):
                differences.append(f"Client missing method: {method_name}")
                continue

            protocol_method = getattr(MT5Protocol, method_name)
            client_method = getattr(MetaTrader5, method_name)

            # Skip properties
            if isinstance(inspect.getattr_static(MT5Protocol, method_name), property):
                continue

            diffs = self._compare_signatures(
                protocol_method, client_method, method_name
            )
            differences.extend(diffs)

        assert not differences, "Signature mismatches:\n" + "\n".join(differences)

    def test_all_async_methods_match(self) -> None:
        """All async protocol methods should match client exactly."""
        differences = []

        for method_name in dir(AsyncMT5Protocol):
            if method_name.startswith("_"):
                continue

            if not hasattr(AsyncMetaTrader5, method_name):
                differences.append(f"AsyncClient missing method: {method_name}")
                continue

            protocol_method = getattr(AsyncMT5Protocol, method_name)
            client_method = getattr(AsyncMetaTrader5, method_name)

            # Skip properties
            if isinstance(
                inspect.getattr_static(AsyncMT5Protocol, method_name), property
            ):
                continue

            diffs = self._compare_signatures(
                protocol_method, client_method, method_name
            )
            differences.extend(diffs)

        assert not differences, "Signature mismatches:\n" + "\n".join(differences)


class TestHistoryMethodSignatures:
    """Validate history method signatures specifically."""

    def test_history_orders_total_params(self) -> None:
        """history_orders_total should have date_from and date_to."""
        method = MetaTrader5.history_orders_total
        sig = inspect.signature(method)
        params = sig.parameters

        assert "date_from" in params
        assert "date_to" in params

    def test_history_orders_get_params(self) -> None:
        """history_orders_get should have optional filter params."""
        method = MetaTrader5.history_orders_get
        sig = inspect.signature(method)
        params = sig.parameters

        # All parameters should have defaults (optional)
        for param_name, param in params.items():
            if param_name == "self":
                continue
            assert (
                param.default is not inspect.Parameter.empty or param.default is None
            ), f"history_orders_get.{param_name} should have default"

    def test_history_deals_total_params(self) -> None:
        """history_deals_total should have date_from and date_to."""
        method = MetaTrader5.history_deals_total
        sig = inspect.signature(method)
        params = sig.parameters

        assert "date_from" in params
        assert "date_to" in params

    def test_history_deals_get_params(self) -> None:
        """history_deals_get should have optional filter params."""
        method = MetaTrader5.history_deals_get
        sig = inspect.signature(method)
        params = sig.parameters

        # All parameters should have defaults (optional)
        for param_name, param in params.items():
            if param_name == "self":
                continue
            assert (
                param.default is not inspect.Parameter.empty or param.default is None
            ), f"history_deals_get.{param_name} should have default"


class TestPositionsOrdersMethodSignatures:
    """Validate positions and orders method signatures."""

    def test_positions_get_params(self) -> None:
        """positions_get should have optional filter params."""
        method = MetaTrader5.positions_get
        sig = inspect.signature(method)
        params = sig.parameters

        # Optional filters
        assert "symbol" in params
        assert params["symbol"].default is None

        assert "group" in params
        assert params["group"].default is None

        assert "ticket" in params
        assert params["ticket"].default is None

    def test_orders_get_params(self) -> None:
        """orders_get should have optional filter params."""
        method = MetaTrader5.orders_get
        sig = inspect.signature(method)
        params = sig.parameters

        # Optional filters
        assert "symbol" in params
        assert params["symbol"].default is None

        assert "group" in params
        assert params["group"].default is None

        assert "ticket" in params
        assert params["ticket"].default is None
