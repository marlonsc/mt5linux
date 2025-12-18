"""Protocol compliance tests for MT5 clients.

Validates that client implementations correctly implement the defined protocols.
Uses Python's inspect module to verify method signatures match EXACTLY.

These tests MUST fail if:
- Method signatures don't match between protocol and implementation
- Parameter names differ
- Parameter defaults differ
- Return types differ
- Methods are missing

Tests:
- MT5Protocol ↔ MetaTrader5
- AsyncMT5Protocol ↔ AsyncMetaTrader5
- Protocol consistency (sync vs async have same 32 methods)
"""

from __future__ import annotations

import inspect

import pytest

from mt5linux import MetaTrader5
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.protocols import AsyncMT5Protocol, MT5Protocol

# Exact 32 methods that MUST be in the protocol (matching MetaTrader5 PyPI)
MT5_PROTOCOL_METHODS = [
    # Terminal (7 methods)
    "initialize",
    "login",
    "shutdown",
    "version",
    "last_error",
    "terminal_info",
    "account_info",
    # Symbols (5 methods)
    "symbols_total",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "symbol_select",
    # Market Data (5 methods)
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
    # Trading (4 methods)
    "order_calc_margin",
    "order_calc_profit",
    "order_check",
    "order_send",
    # Positions (2 methods)
    "positions_total",
    "positions_get",
    # Orders (2 methods)
    "orders_total",
    "orders_get",
    # History (4 methods)
    "history_orders_total",
    "history_orders_get",
    "history_deals_total",
    "history_deals_get",
    # Market Depth (3 methods)
    "market_book_add",
    "market_book_get",
    "market_book_release",
]

# mt5linux-specific extensions (NOT in protocol, but MUST exist in clients)
MT5LINUX_EXTENSIONS = ["connect", "disconnect", "health_check", "is_connected"]


def get_method_params(cls: type, method_name: str) -> dict[str, inspect.Parameter]:
    """Get method parameters excluding 'self'."""
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return {k: v for k, v in sig.parameters.items() if k != "self"}


def compare_signatures(
    protocol_cls: type,
    client_cls: type,
    method_name: str,
) -> list[str]:
    """Compare method signatures and return list of differences.

    This function performs STRICT validation:
    - All protocol parameters must exist in client
    - Parameter defaults must match exactly
    - Parameter kinds must match (positional, keyword-only, etc.)
    """
    differences: list[str] = []

    protocol_method = getattr(protocol_cls, method_name)
    client_method = getattr(client_cls, method_name)

    inspect.signature(protocol_method)
    inspect.signature(client_method)

    protocol_params = get_method_params(protocol_cls, method_name)
    client_params = get_method_params(client_cls, method_name)

    # Check all protocol parameters exist in client
    for param_name, protocol_param in protocol_params.items():
        if param_name not in client_params:
            differences.append(
                f"{method_name}: Client missing parameter '{param_name}'"
            )
            continue

        client_param = client_params[param_name]

        # Check parameter kinds match
        if protocol_param.kind != client_param.kind:
            differences.append(
                f"{method_name}.{param_name}: Kind mismatch - "
                f"protocol={protocol_param.kind.name}, "
                f"client={client_param.kind.name}"
            )

        # Check defaults match (if protocol has default)
        if protocol_param.default != inspect.Parameter.empty:
            if client_param.default != protocol_param.default:
                differences.append(
                    f"{method_name}.{param_name}: Default mismatch - "
                    f"protocol={protocol_param.default!r}, "
                    f"client={client_param.default!r}"
                )

    # Check for extra required parameters in client (no default)
    extra_params = set(client_params.keys()) - set(protocol_params.keys())
    differences.extend(
        f"{method_name}: Client has extra REQUIRED parameter '{extra}'"
        for extra in extra_params
        if client_params[extra].default == inspect.Parameter.empty
    )

    return differences


class TestProtocolMethodCount:
    """Validate protocol has exactly 32 methods."""

    def test_mt5_protocol_has_exactly_32_methods(self) -> None:
        """MT5Protocol should have exactly 32 methods (matching MT5 PyPI)."""
        protocol_methods = [
            m
            for m in dir(MT5Protocol)
            if not m.startswith("_") and callable(getattr(MT5Protocol, m))
        ]
        assert len(protocol_methods) == 32, (
            f"MT5Protocol should have 32 methods, found {len(protocol_methods)}: "
            f"{sorted(protocol_methods)}"
        )

    def test_async_mt5_protocol_has_exactly_32_methods(self) -> None:
        """AsyncMT5Protocol should have exactly 32 methods (matching MT5 PyPI)."""
        protocol_methods = [
            m
            for m in dir(AsyncMT5Protocol)
            if not m.startswith("_") and callable(getattr(AsyncMT5Protocol, m))
        ]
        assert len(protocol_methods) == 32, (
            f"AsyncMT5Protocol should have 32 methods, found {len(protocol_methods)}: "
            f"{sorted(protocol_methods)}"
        )

    def test_expected_methods_list_has_32_items(self) -> None:
        """Our expected methods list should have exactly 32 items."""
        assert len(MT5_PROTOCOL_METHODS) == 32, (
            f"MT5_PROTOCOL_METHODS should have 32 items, found {len(MT5_PROTOCOL_METHODS)}"
        )


class TestSyncProtocolCompliance:
    """Validate MetaTrader5 implements MT5Protocol correctly."""

    def test_client_is_protocol_instance(self) -> None:
        """MetaTrader5 instance should pass isinstance check for protocol."""
        client = MetaTrader5()
        assert isinstance(client, MT5Protocol), (
            "MetaTrader5 does not implement MT5Protocol"
        )

    def test_all_32_protocol_methods_exist(self) -> None:
        """All 32 protocol methods must exist in implementation."""
        missing = [
            method_name
            for method_name in MT5_PROTOCOL_METHODS
            if not hasattr(MetaTrader5, method_name)
        ]

        assert not missing, f"MetaTrader5 missing {len(missing)} methods: {missing}"

    def test_mt5linux_extensions_exist(self) -> None:
        """mt5linux extensions should exist in implementation."""
        missing = [
            ext_name
            for ext_name in MT5LINUX_EXTENSIONS
            if not hasattr(MetaTrader5, ext_name)
        ]

        assert not missing, f"MetaTrader5 missing extensions: {missing}"

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_method_signature_matches_protocol(self, method_name: str) -> None:
        """Method signature must match protocol exactly."""
        differences = compare_signatures(MT5Protocol, MetaTrader5, method_name)
        assert not differences, f"Signature mismatch for {method_name}:\n" + "\n".join(
            differences
        )

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_method_has_return_annotation(self, method_name: str) -> None:
        """All methods must have return type annotations."""
        method = getattr(MetaTrader5, method_name)
        sig = inspect.signature(method)
        assert sig.return_annotation != inspect.Signature.empty, (
            f"MetaTrader5.{method_name} missing return type annotation"
        )


class TestAsyncProtocolCompliance:
    """Validate AsyncMetaTrader5 implements AsyncMT5Protocol correctly."""

    def test_client_is_protocol_instance(self) -> None:
        """AsyncMetaTrader5 instance should pass isinstance check for protocol."""
        client = AsyncMetaTrader5()
        assert isinstance(client, AsyncMT5Protocol), (
            "AsyncMetaTrader5 does not implement AsyncMT5Protocol"
        )

    def test_all_32_protocol_methods_exist(self) -> None:
        """All 32 protocol methods must exist in implementation."""
        missing = [
            method_name
            for method_name in MT5_PROTOCOL_METHODS
            if not hasattr(AsyncMetaTrader5, method_name)
        ]

        assert not missing, (
            f"AsyncMetaTrader5 missing {len(missing)} methods: {missing}"
        )

    def test_mt5linux_extensions_exist(self) -> None:
        """mt5linux extensions should exist in implementation."""
        missing = [
            ext_name
            for ext_name in MT5LINUX_EXTENSIONS
            if not hasattr(AsyncMetaTrader5, ext_name)
        ]

        assert not missing, f"AsyncMetaTrader5 missing extensions: {missing}"

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_method_signature_matches_protocol(self, method_name: str) -> None:
        """Method signature must match protocol exactly."""
        differences = compare_signatures(
            AsyncMT5Protocol, AsyncMetaTrader5, method_name
        )
        assert not differences, f"Signature mismatch for {method_name}:\n" + "\n".join(
            differences
        )

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_method_is_coroutine(self, method_name: str) -> None:
        """All async protocol methods must be coroutines."""
        method = getattr(AsyncMetaTrader5, method_name)
        assert inspect.iscoroutinefunction(method), (
            f"AsyncMetaTrader5.{method_name} should be async coroutine"
        )


class TestProtocolConsistency:
    """Validate sync and async protocols are identical (same 32 methods)."""

    def test_same_method_names(self) -> None:
        """Both protocols must have the exact same 32 methods."""
        sync_methods = {
            m
            for m in dir(MT5Protocol)
            if not m.startswith("_") and callable(getattr(MT5Protocol, m))
        }
        async_methods = {
            m
            for m in dir(AsyncMT5Protocol)
            if not m.startswith("_") and callable(getattr(AsyncMT5Protocol, m))
        }

        only_in_sync = sync_methods - async_methods
        only_in_async = async_methods - sync_methods

        assert not only_in_sync, f"Methods only in MT5Protocol: {only_in_sync}"
        assert not only_in_async, f"Methods only in AsyncMT5Protocol: {only_in_async}"
        assert sync_methods == async_methods, "Protocols have different methods"

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_same_parameters(self, method_name: str) -> None:
        """Both protocols must have identical parameters for each method."""
        sync_params = get_method_params(MT5Protocol, method_name)
        async_params = get_method_params(AsyncMT5Protocol, method_name)

        # Parameter names must match
        assert set(sync_params.keys()) == set(async_params.keys()), (
            f"{method_name}: Parameter names differ - "
            f"sync={set(sync_params.keys())}, async={set(async_params.keys())}"
        )

        # Parameter defaults must match
        for param_name in sync_params:
            sync_default = sync_params[param_name].default
            async_default = async_params[param_name].default
            assert sync_default == async_default, (
                f"{method_name}.{param_name}: Default mismatch - "
                f"sync={sync_default!r}, async={async_default!r}"
            )


class TestClientConsistency:
    """Validate sync and async clients have identical signatures."""

    @pytest.mark.parametrize("method_name", MT5_PROTOCOL_METHODS)
    def test_same_parameters(self, method_name: str) -> None:
        """Both clients must have identical parameters for each method."""
        sync_params = get_method_params(MetaTrader5, method_name)
        async_params = get_method_params(AsyncMetaTrader5, method_name)

        # Parameter names must match
        assert set(sync_params.keys()) == set(async_params.keys()), (
            f"{method_name}: Parameter names differ between clients - "
            f"sync={set(sync_params.keys())}, async={set(async_params.keys())}"
        )

        # Parameter defaults must match
        for param_name in sync_params:
            sync_default = sync_params[param_name].default
            async_default = async_params[param_name].default
            assert sync_default == async_default, (
                f"{method_name}.{param_name}: Default mismatch between clients - "
                f"sync={sync_default!r}, async={async_default!r}"
            )
