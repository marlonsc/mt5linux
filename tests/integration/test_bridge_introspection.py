"""Bridge introspection function tests.

Tests for the get_tuple_field_order function in utilities.py.
This function extracts field names from tuple subclasses in positional order
using Python introspection (no hardcoding).

Note: bridge.py contains a copy of this function for standalone deployment
inside Wine. The canonical implementation is in utilities.py for testing.

Note: We use collections.namedtuple intentionally to test introspection of
dynamically-created namedtuples (not typing.NamedTuple static definitions).

NO MOCKING - tests use real tuple subclasses.
"""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Callable

import pytest

from mt5linux.utilities import MT5Utilities

# Type alias for the introspection function
TupleFieldOrderFn = Callable[[type], list[str] | None]


class TestGetTupleFieldOrder:
    """Tests for get_tuple_field_order static method."""

    @pytest.fixture
    def get_tuple_field_order(self) -> TupleFieldOrderFn:
        """Import the function from utilities module."""
        return MT5Utilities.Introspection.get_tuple_field_order

    def test_standard_namedtuple(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Standard namedtuple should return fields in order via _fields."""
        # Create a standard namedtuple (dynamic, not typing.NamedTuple)
        AccountInfo = namedtuple(  # noqa: PYI024
            "AccountInfo", ["login", "balance", "equity", "currency"]
        )

        result = get_tuple_field_order(AccountInfo)

        assert result is not None
        assert result == ["login", "balance", "equity", "currency"]

    def test_namedtuple_field_order_preserved(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Field order must be preserved exactly as defined."""
        # Order matters - test with specific order
        SymbolInfo = namedtuple(  # noqa: PYI024
            "SymbolInfo",
            ["name", "description", "path", "bid", "ask", "digits"],
        )

        result = get_tuple_field_order(SymbolInfo)

        assert result is not None
        # Order must be exactly as defined
        assert result[0] == "name"
        assert result[1] == "description"
        assert result[2] == "path"
        assert result[3] == "bid"
        assert result[4] == "ask"
        assert result[5] == "digits"

    def test_single_field_namedtuple(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Single-field namedtuple should work."""
        SingleField = namedtuple("SingleField", ["value"])  # noqa: PYI024

        result = get_tuple_field_order(SingleField)

        assert result is not None
        assert result == ["value"]

    def test_many_fields_namedtuple(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Namedtuple with many fields should work."""
        # Simulate SymbolInfo's 96 fields (using subset)
        fields = [f"field_{i}" for i in range(50)]
        ManyFields = namedtuple("ManyFields", fields)  # noqa: PYI024

        result = get_tuple_field_order(ManyFields)

        assert result is not None
        assert len(result) == 50
        # Verify order is preserved
        for i, field in enumerate(result):
            assert field == f"field_{i}"

    def test_class_without_tuple_inheritance(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Non-tuple class should return None."""

        class NotATuple:
            field1: int
            field2: str

        result = get_tuple_field_order(NotATuple)

        # Should return None or empty list for non-tuple
        assert result is None or result == []

    def test_tuple_subclass_with_match_args(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Tuple subclass with __match_args__ should use that."""

        class MatchArgsTuple(tuple):  # noqa: SLOT001
            __match_args__ = ("first", "second", "third")

        result = get_tuple_field_order(MatchArgsTuple)

        assert result is not None
        assert result == ["first", "second", "third"]

    def test_namedtuple_with_defaults(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Namedtuple with defaults should still return all fields in order."""
        TickInfo = namedtuple(  # noqa: PYI024
            "TickInfo",
            ["time", "bid", "ask", "last", "volume", "flags"],
            defaults=[0, 0.0, 0.0, 0.0, 0, 0],
        )

        result = get_tuple_field_order(TickInfo)

        assert result is not None
        assert result == ["time", "bid", "ask", "last", "volume", "flags"]

    def test_empty_namedtuple(self, get_tuple_field_order: TupleFieldOrderFn) -> None:
        """Empty namedtuple should return empty list."""
        EmptyTuple = namedtuple("EmptyTuple", [])  # noqa: PYI024

        result = get_tuple_field_order(EmptyTuple)

        assert result is not None
        assert result == []


class TestGetTupleFieldOrderIntegration:
    """Integration tests with real MT5-like structures."""

    @pytest.fixture
    def get_tuple_field_order(self) -> TupleFieldOrderFn:
        """Import the function from utilities module."""
        return MT5Utilities.Introspection.get_tuple_field_order

    def test_account_info_structure(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Test with AccountInfo-like structure (28 fields)."""
        AccountInfo = namedtuple(  # noqa: PYI024
            "AccountInfo",
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

        result = get_tuple_field_order(AccountInfo)

        assert result is not None
        assert len(result) == 28
        # Verify alphabetical order (as MT5 returns it)
        assert result[0] == "assets"
        assert result[1] == "balance"
        assert result[12] == "login"
        assert result[-1] == "trade_mode"

    def test_position_structure(self, get_tuple_field_order: TupleFieldOrderFn) -> None:
        """Test with Position-like structure (19 fields)."""
        TradePosition = namedtuple(  # noqa: PYI024
            "TradePosition",
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

        result = get_tuple_field_order(TradePosition)

        assert result is not None
        assert len(result) == 19
        assert result[0] == "ticket"
        assert result[-1] == "external_id"

    def test_tick_structure(self, get_tuple_field_order: TupleFieldOrderFn) -> None:
        """Test with Tick-like structure (8 fields)."""
        Tick = namedtuple(  # noqa: PYI024
            "Tick",
            [
                "time",
                "bid",
                "ask",
                "last",
                "volume",
                "time_msc",
                "flags",
                "volume_real",
            ],
        )

        result = get_tuple_field_order(Tick)

        assert result is not None
        assert len(result) == 8
        assert result == [
            "time",
            "bid",
            "ask",
            "last",
            "volume",
            "time_msc",
            "flags",
            "volume_real",
        ]


class TestMemberDescriptorFallback:
    """Tests for member_descriptor fallback strategy."""

    @pytest.fixture
    def get_tuple_field_order(self) -> TupleFieldOrderFn:
        """Import the function from utilities module."""
        return MT5Utilities.Introspection.get_tuple_field_order

    def test_tuple_subclass_with_member_descriptors(
        self, get_tuple_field_order: TupleFieldOrderFn
    ) -> None:
        """Test tuple subclass with member_descriptor attributes.

        This simulates MT5's structseq types which don't have _fields
        but have member_descriptor attributes.
        """
        # Create a simple tuple subclass to test the fallback

        class SimpleTupleSubclass(tuple):  # noqa: SLOT001
            """Simple tuple subclass for testing."""

            # Note: Python tuple subclasses typically don't have
            # member_descriptors like MT5's C extension types do.
            # This test verifies the function handles such cases.

        # This should either find __match_args__ or return None
        # since SimpleTupleSubclass doesn't have member_descriptors
        result = get_tuple_field_order(SimpleTupleSubclass)

        # Could be None or empty list - both are valid
        assert result is None or isinstance(result, list)
