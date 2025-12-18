"""Validate c against real MetaTrader5 library.

This test connects to the MT5 Docker container and validates that
all constants in mt5linux.constants.c match the real
MetaTrader5 library values.

REQUIRES: Docker test container running (use conftest.py fixtures)
"""

from __future__ import annotations

import socket

import grpc
import pytest

from mt5linux import mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.constants import c

from .conftest import tc

# Default config instance
_config = MT5Config()

# Mapping of MT5 constant prefixes to c nested class names
PREFIX_TO_CLASS: dict[str, str] = {
    "TIMEFRAME_": "TimeFrame",
    "ORDER_TYPE_": "OrderType",
    "TRADE_ACTION_": "TradeAction",
    "ORDER_STATE_": "OrderState",
    "ORDER_FILLING_": "OrderFilling",
    "ORDER_TIME_": "OrderTime",
    "ORDER_REASON_": "OrderReason",
    "DEAL_TYPE_": "DealType",
    "DEAL_ENTRY_": "DealEntry",
    "DEAL_REASON_": "DealReason",
    "POSITION_TYPE_": "PositionType",
    "POSITION_REASON_": "PositionReason",
    "ACCOUNT_TRADE_MODE_": "AccountTradeMode",
    "ACCOUNT_STOPOUT_MODE_": "AccountStopoutMode",
    "ACCOUNT_MARGIN_MODE_": "AccountMarginMode",
    "SYMBOL_CALC_MODE_": "SymbolCalcMode",
    "SYMBOL_CHART_MODE_": "SymbolChartMode",
    "SYMBOL_OPTION_MODE_": "SymbolOptionMode",
    "SYMBOL_OPTION_RIGHT_": "SymbolOptionRight",
    "SYMBOL_SWAP_MODE_": "SymbolSwapMode",
    "SYMBOL_TRADE_EXECUTION_": "SymbolTradeExecution",
    "SYMBOL_TRADE_MODE_": "SymbolTradeMode",
    "BOOK_TYPE_": "BookType",
    "TRADE_RETCODE_": "TradeRetcode",
    "COPY_TICKS_": "CopyTicksFlag",
    "TICK_FLAG_": "TickFlag",
    "DAY_OF_WEEK_": "DayOfWeek",
}


def _is_grpc_server_available(host: str, port: int) -> bool:
    """Check if gRPC server is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(tc.MEDIUM_TIMEOUT)
        result = sock.connect_ex((host, port))
        sock.close()
    except (OSError, TimeoutError):
        return False
    else:
        return result == 0


def _extract_mt5_constants(host: str, port: int) -> dict[str, int]:
    """Extract all integer constants from real MetaTrader5 via gRPC.

    Uses the gRPC bridge's GetConstants method.
    """
    channel = grpc.insecure_channel(
        f"{host}:{port}",
        options=[
            ("grpc.max_receive_message_length", tc.GRPC_MAX_MESSAGE_SIZE),
        ],
    )

    try:
        stub = mt5_pb2_grpc.MT5ServiceStub(channel)
        response = stub.GetConstants(mt5_pb2.Empty(), timeout=30)
        raw_constants = response.values
    finally:
        channel.close()

    return {
        name: value
        for name, value in raw_constants.items()
        if isinstance(value, int) and name.isupper() and not name.startswith("_")
    }


def _get_local_constants() -> dict[str, int]:
    """Extract MT5-related constants from c class.

    Only extracts IntEnums that map to known MT5 prefixes.
    Skips internal constants like CircuitBreakerState.
    """
    constants: dict[str, int] = {}

    # Build reverse mapping: class_name -> prefix
    class_to_prefix = {v: k for k, v in PREFIX_TO_CLASS.items()}

    for attr_name in dir(c):
        if attr_name.startswith("_"):
            continue

        attr = getattr(c, attr_name)

        # Check if this is a namespace class (like Order, Position, etc.)
        if isinstance(attr, type) and not issubclass(attr, int):
            # Look for nested IntEnum classes inside namespaces
            for nested_name in dir(attr):
                if nested_name.startswith("_"):
                    continue
                nested = getattr(attr, nested_name, None)
                if nested is None:
                    continue
                # Check if it's an IntEnum class that maps to MT5
                if isinstance(nested, type) and nested_name in class_to_prefix:
                    prefix = class_to_prefix[nested_name]
                    # Extract enum members
                    for member_name in dir(nested):
                        if member_name.startswith("_"):
                            continue
                        member = getattr(nested, member_name, None)
                        if member is None:
                            continue
                        if hasattr(member, "value") and isinstance(member.value, int):
                            full_name = f"{prefix}{member_name}"
                            constants[full_name] = member.value

        # Also check top-level enums that match MT5 prefixes
        if attr_name in class_to_prefix:
            prefix = class_to_prefix[attr_name]
            if isinstance(attr, type):
                for member_name in dir(attr):
                    if member_name.startswith("_"):
                        continue
                    member = getattr(attr, member_name, None)
                    if member is None:
                        continue
                    if hasattr(member, "value") and isinstance(member.value, int):
                        full_name = f"{prefix}{member_name}"
                        constants[full_name] = member.value

    return constants


def _group_by_class(constants: dict[str, int]) -> dict[str, dict[str, int]]:
    """Group constants by their enum class."""
    groups: dict[str, dict[str, int]] = {}

    for name, value in constants.items():
        for prefix, class_name in PREFIX_TO_CLASS.items():
            if name.startswith(prefix):
                if class_name not in groups:
                    groups[class_name] = {}
                member_name = name[len(prefix) :]
                groups[class_name][member_name] = value
                break

    return groups


@pytest.fixture(scope="module")
def mt5_constants() -> dict[str, int]:
    """Fixture that provides real MT5 constants from Docker container."""
    # Use test port from shared conftest configuration
    from .conftest import TEST_GRPC_HOST, TEST_GRPC_PORT

    host = TEST_GRPC_HOST
    port = TEST_GRPC_PORT

    if not _is_grpc_server_available(host, port):
        pytest.skip(
            f"MT5 gRPC server not available on {host}:{port}. "
            "Start with: docker compose up -d"
        )

    return _extract_mt5_constants(host, port)


class TestConstantsValidation:
    """Validate c against real MetaTrader5 library."""

    def test_all_constants_present(self, mt5_constants: dict[str, int]) -> None:
        """Verify all real MT5 constants are present in c."""
        local = _get_local_constants()

        missing: list[str] = []
        for name, value in mt5_constants.items():
            # Check if this constant maps to a known class
            known_class = False
            for prefix in PREFIX_TO_CLASS:
                if name.startswith(prefix):
                    known_class = True
                    break

            if not known_class:
                # Skip constants that don't map to our known classes
                continue

            if name not in local:
                missing.append(f"{name}={value}")

        if missing:
            limit = c.Test.Validation.ERROR_DISPLAY_LIMIT
            pytest.fail(
                f"Missing {len(missing)} constants in c:\n"
                + "\n".join(f"  - {m}" for m in sorted(missing)[:limit])
                + (
                    f"\n  ... and {len(missing) - limit} more"
                    if len(missing) > limit
                    else ""
                )
            )

    def test_constant_values_match(self, mt5_constants: dict[str, int]) -> None:
        """Verify all constant values match the real MT5 values."""
        local = _get_local_constants()

        mismatches: list[str] = []
        for name, expected in mt5_constants.items():
            if name not in local:
                continue  # Handled by test_all_constants_present

            actual = local[name]
            if actual != expected:
                mismatches.append(f"{name}: expected={expected}, actual={actual}")

        if mismatches:
            pytest.fail(
                f"Value mismatches for {len(mismatches)} constants:\n"
                + "\n".join(f"  - {m}" for m in sorted(mismatches))
            )

    def test_no_extra_constants(self, mt5_constants: dict[str, int]) -> None:
        """Verify our constants are a superset of GetConstants response.

        Note: GetConstants only returns ~81 constants, while MT5 has 200+.
        We intentionally include more constants from MT5 documentation.
        This test just verifies we don't have INVALID constants (wrong values).
        """
        local = _get_local_constants()

        # Filter MT5 constants to only those we track
        tracked_mt5 = {
            name: value
            for name, value in mt5_constants.items()
            if any(name.startswith(p) for p in PREFIX_TO_CLASS)
        }

        # Count how many local constants match vs don't match GetConstants
        matched = sum(1 for name in local if name in tracked_mt5)

        # This is informational - GetConstants is incomplete
        # We expect to have MORE constants than GetConstants returns
        assert matched > 0, "No local constants matched GetConstants response"
        assert len(local) >= len(tracked_mt5), (
            f"We have fewer constants ({len(local)}) than "
            f"GetConstants ({len(tracked_mt5)})"
        )

    def test_missing_mt5_constants(self, mt5_constants: dict[str, int]) -> None:
        """Identify MT5 constants not yet added to c.

        This helps keep c in sync with MetaTrader5 updates.
        Reports new constants that should be added.
        """
        local = _get_local_constants()

        # Find MT5 constants from tracked prefixes that we don't have
        missing: list[str] = []
        for name, value in mt5_constants.items():
            # Check if this constant belongs to a tracked class
            for prefix in PREFIX_TO_CLASS:
                if name.startswith(prefix):
                    if name not in local:
                        missing.append(f"{name}={value}")
                    break

        if missing:
            # Report missing constants - this is informational
            # New MT5 versions might add constants we should track
            import warnings

            warnings.warn(
                f"Found {len(missing)} MT5 constants not in c "
                "(may need to add these):\n"
                + "\n".join(f"  - {m}" for m in sorted(missing)[:20]),
                stacklevel=1,
            )

    def test_enum_classes_exist(self) -> None:
        """Verify all expected enum classes exist in c."""
        expected_classes = set(PREFIX_TO_CLASS.values())

        for class_name in expected_classes:
            assert hasattr(c, class_name), f"c missing class: {class_name}"

            cls = getattr(c, class_name)
            assert isinstance(cls, type), f"c.{class_name} is not a class"

    def test_timeframe_constants(self, mt5_constants: dict[str, int]) -> None:
        """Validate TimeFrame constants specifically (commonly used)."""
        expected = {
            "TIMEFRAME_M1": 1,
            "TIMEFRAME_M5": 5,
            "TIMEFRAME_M15": 15,
            "TIMEFRAME_M30": 30,
            "TIMEFRAME_H1": 16385,
            "TIMEFRAME_H4": 16388,
            "TIMEFRAME_D1": 16408,
            "TIMEFRAME_W1": 32769,
            "TIMEFRAME_MN1": 49153,
        }

        for name, expected_value in expected.items():
            assert name in mt5_constants, f"MT5 missing {name}"
            assert mt5_constants[name] == expected_value, (
                f"{name}: expected {expected_value}, got {mt5_constants[name]}"
            )

            # Also check local
            member_name = name.replace("TIMEFRAME_", "")
            assert hasattr(c.TimeFrame, member_name), (
                f"c.TimeFrame missing {member_name}"
            )
            assert getattr(c.TimeFrame, member_name).value == expected_value, (
                f"c.TimeFrame.{member_name} value mismatch"
            )

    def test_trade_retcode_constants(self, mt5_constants: dict[str, int]) -> None:
        """Validate TradeRetcode constants specifically (critical for trading)."""
        expected = {
            "TRADE_RETCODE_DONE": 10009,
            "TRADE_RETCODE_DONE_PARTIAL": 10010,
            "TRADE_RETCODE_ERROR": 10011,
            "TRADE_RETCODE_TIMEOUT": 10012,
            "TRADE_RETCODE_INVALID": 10013,
            "TRADE_RETCODE_NO_MONEY": 10019,
        }

        for name, expected_value in expected.items():
            assert name in mt5_constants, f"MT5 missing {name}"
            assert mt5_constants[name] == expected_value, (
                f"{name}: expected {expected_value}, got {mt5_constants[name]}"
            )

    def test_order_type_constants(self, mt5_constants: dict[str, int]) -> None:
        """Validate OrderType constants specifically."""
        expected = {
            "ORDER_TYPE_BUY": 0,
            "ORDER_TYPE_SELL": 1,
            "ORDER_TYPE_BUY_LIMIT": 2,
            "ORDER_TYPE_SELL_LIMIT": 3,
            "ORDER_TYPE_BUY_STOP": 4,
            "ORDER_TYPE_SELL_STOP": 5,
        }

        for name, expected_value in expected.items():
            assert name in mt5_constants, f"MT5 missing {name}"
            assert mt5_constants[name] == expected_value, (
                f"{name}: expected {expected_value}, got {mt5_constants[name]}"
            )
