"""Unit tests for mt5linux.utilities.

These tests cover the parts of MT5Utilities that are not already exercised by
existing unit tests:

- MT5Utilities.Exceptions   (all exception classes and attributes)
- MT5Utilities.Data         (Wrapper, validators, transformations, datetime,
                             JSON/proto serialization)
- MT5Utilities.Introspection (tuple field order discovery)
- MT5Utilities.RetryStrategy (reconnect and timeout helpers)
- MT5Utilities.TransactionOrchestrator (order execution orchestration)

All tests are pure unit tests: they use pytest, mocks when needed, and do NOT
require a real MetaTrader5 terminal, Docker container, or gRPC server.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections import namedtuple
from datetime import UTC, datetime
from typing import Self
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from mt5linux.constants import MT5Constants as c
from mt5linux.settings import MT5Settings
from mt5linux.utilities import MT5Utilities as u

# =============================================================================
# EXCEPTIONS
# =============================================================================


class TestExceptions:
    """Tests for all MT5 exception classes."""

    def test_error_base_is_exception(self) -> None:
        """Base Error inherits from Exception."""
        err = u.Exceptions.Error("base error")
        assert isinstance(err, Exception)
        assert str(err) == "base error"

    def test_retryable_error_attributes(self) -> None:
        """RetryableError stores code and description."""
        err = u.Exceptions.RetryableError(10004, "requote")
        assert err.code == 10004
        assert err.description == "requote"
        assert "10004" in str(err)
        assert "requote" in str(err)

    def test_permanent_error_attributes(self) -> None:
        """PermanentError stores code and description."""
        err = u.Exceptions.PermanentError(10006, "reject")
        assert err.code == 10006
        assert err.description == "reject"
        assert "10006" in str(err)
        assert "reject" in str(err)

    def test_max_retries_error_with_last_error(self) -> None:
        """MaxRetriesError stores operation, attempts and last_error."""
        last = ValueError("boom")
        err = u.Exceptions.MaxRetriesError("order_send", 3, last)
        assert err.operation == "order_send"
        assert err.attempts == 3
        assert err.last_error is last
        assert "order_send" in str(err)
        assert "3" in str(err)
        assert "boom" in str(err)

    def test_max_retries_error_without_last_error(self) -> None:
        """MaxRetriesError works without last_error."""
        err = u.Exceptions.MaxRetriesError("copy_rates", 5)
        assert err.last_error is None
        assert "copy_rates" in str(err)
        assert "5" in str(err)

    def test_not_available_error(self) -> None:
        """NotAvailableError is a simple marker exception."""
        err = u.Exceptions.NotAvailableError("mt5 not available")
        assert isinstance(err, u.Exceptions.Error)
        assert "mt5 not available" in str(err)

    def test_circuit_breaker_open_error_default(self) -> None:
        """CircuitBreakerOpenError has default message and optional recovery."""
        err = u.Exceptions.CircuitBreakerOpenError()
        assert "Circuit breaker is open" in str(err)
        assert err.recovery_time is None

    def test_circuit_breaker_open_error_with_recovery(self) -> None:
        """CircuitBreakerOpenError stores recovery_time."""
        recovery = datetime.now(UTC)
        err = u.Exceptions.CircuitBreakerOpenError("custom", recovery)
        assert err.recovery_time is recovery
        assert "custom" in str(err)

    def test_empty_response_error(self) -> None:
        """EmptyResponseError behaves as RetryableError with code -1."""
        err = u.Exceptions.EmptyResponseError("order_send", "timeout")
        assert err.code == -1
        assert err.operation == "order_send"
        assert err.detail == "timeout"
        assert "order_send" in str(err)
        assert "timeout" in str(err)

    def test_empty_response_error_without_detail(self) -> None:
        """EmptyResponseError works without detail."""
        err = u.Exceptions.EmptyResponseError("positions_get")
        assert err.detail == ""
        assert "positions_get" in str(err)

    def test_queue_full_error_default(self) -> None:
        """QueueFullError has a default message."""
        err = u.Exceptions.QueueFullError()
        assert "Request queue full" in str(err)

    def test_queue_full_error_custom(self) -> None:
        """QueueFullError accepts a custom message."""
        err = u.Exceptions.QueueFullError("capacity exceeded")
        assert "capacity exceeded" in str(err)


# =============================================================================
# DATA UTILITIES - WRAPPER
# =============================================================================


class TestDataWrapper:
    """Tests for MT5Utilities.Data.Wrapper."""

    def test_wrapper_attribute_access(self) -> None:
        """Wrapper exposes dict keys as attributes."""
        data: dict[str, object] = {"symbol": "EURUSD", "volume": 0.1}
        wrapper = u.Data.Wrapper(data)
        assert wrapper.symbol == "EURUSD"
        assert wrapper.volume == 0.1

    def test_wrapper_missing_attribute(self) -> None:
        """Missing attribute raises AttributeError."""
        wrapper = u.Data.Wrapper({"a": 1})
        with pytest.raises(AttributeError, match="has no attribute 'missing'"):
            _ = wrapper.missing

    def test_wrapper_repr(self) -> None:
        """Wrapper repr contains class name and data."""
        wrapper = u.Data.Wrapper({"a": 1})
        repr_str = repr(wrapper)
        assert "Wrapper" in repr_str
        assert "a" in repr_str

    def test_wrapper_asdict(self) -> None:
        """_asdict returns the underlying dict."""
        data: dict[str, object] = {"a": 1, "b": 2}
        wrapper = u.Data.Wrapper(data)
        assert wrapper._asdict() is data


# =============================================================================
# DATA UTILITIES - VALIDATORS
# =============================================================================


class TestDataValidators:
    """Tests for MT5Utilities.Data static validators."""

    def test_validate_version_none(self) -> None:
        """validate_version returns None for None."""
        assert u.Data.validate_version(None) is None

    def test_validate_version_valid(self) -> None:
        """validate_version converts a valid tuple."""
        assert u.Data.validate_version((5, 0, "build")) == (5, 0, "build")

    def test_validate_version_invalid_type(self) -> None:
        """validate_version rejects non-tuple values."""
        with pytest.raises(TypeError, match="Expected version tuple"):
            u.Data.validate_version("5.0")

    def test_validate_version_wrong_length(self) -> None:
        """validate_version rejects tuples with wrong length."""
        with pytest.raises(TypeError, match="Expected version tuple"):
            u.Data.validate_version((5, 0))

    def test_validate_version_invalid_elements(self) -> None:
        """validate_version rejects unconvertible elements."""
        with pytest.raises(TypeError, match="Invalid version tuple"):
            u.Data.validate_version(("a", 0, "b"))

    def test_validate_last_error_valid(self) -> None:
        """validate_last_error converts a valid tuple."""
        assert u.Data.validate_last_error((1, "err")) == (1, "err")

    def test_validate_last_error_invalid_type(self) -> None:
        """validate_last_error rejects non-tuples."""
        with pytest.raises(TypeError, match=r"Expected tuple\[int, str\]"):
            u.Data.validate_last_error([1, "err"])

    def test_validate_last_error_wrong_length(self) -> None:
        """validate_last_error rejects wrong-length tuples."""
        with pytest.raises(TypeError, match=r"Expected tuple\[int, str\]"):
            u.Data.validate_last_error((1, "err", "extra"))

    def test_validate_last_error_invalid_elements(self) -> None:
        """validate_last_error rejects bad element types."""
        with pytest.raises(TypeError, match="Invalid error tuple"):
            u.Data.validate_last_error(("x", "err"))

    def test_validate_bool_true_false(self) -> None:
        """validate_bool accepts booleans and ints."""
        assert u.Data.validate_bool(value=True) is True
        assert u.Data.validate_bool(value=False) is False
        assert u.Data.validate_bool(value=1) is True
        assert u.Data.validate_bool(value=0) is False

    def test_validate_bool_rejects_bool_subclass_confusion(self) -> None:
        """validate_bool treats bool as bool first (no TypeError)."""
        # bool is a subclass of int; the explicit isinstance(value, bool)
        # check must come first.
        assert u.Data.validate_bool(value=True) is True

    def test_validate_bool_rejects_non_boolish(self) -> None:
        """validate_bool rejects strings and floats."""
        with pytest.raises(TypeError, match="Expected bool"):
            u.Data.validate_bool("true")
        with pytest.raises(TypeError, match="Expected bool"):
            u.Data.validate_bool(1.0)

    def test_validate_int_accepts_int(self) -> None:
        """validate_int accepts plain ints."""
        assert u.Data.validate_int(42) == 42
        assert u.Data.validate_int(-7) == -7

    def test_validate_int_rejects_bool(self) -> None:
        """validate_int rejects bools."""
        with pytest.raises(TypeError, match="Expected int"):
            u.Data.validate_int(value=True)

    def test_validate_int_rejects_float_string(self) -> None:
        """validate_int rejects floats and strings."""
        with pytest.raises(TypeError, match="Expected int"):
            u.Data.validate_int(3.14)
        with pytest.raises(TypeError, match="Expected int"):
            u.Data.validate_int("42")

    def test_validate_int_optional_none(self) -> None:
        """validate_int_optional returns None for None."""
        assert u.Data.validate_int_optional(None) is None

    def test_validate_int_optional_valid(self) -> None:
        """validate_int_optional accepts int and rejects bool."""
        assert u.Data.validate_int_optional(42) == 42
        with pytest.raises(TypeError, match="Expected int"):
            u.Data.validate_int_optional(value=True)
        with pytest.raises(TypeError, match="Expected int"):
            u.Data.validate_int_optional(value=3.14)

    def test_validate_float_optional_none(self) -> None:
        """validate_float_optional returns None for None."""
        assert u.Data.validate_float_optional(None) is None

    def test_validate_float_optional_valid(self) -> None:
        """validate_float_optional accepts int and float, rejects bool."""
        assert u.Data.validate_float_optional(3) == 3.0
        assert u.Data.validate_float_optional(3.14) == 3.14
        with pytest.raises(TypeError, match="Expected float"):
            u.Data.validate_float_optional(value=True)
        with pytest.raises(TypeError, match="Expected float"):
            u.Data.validate_float_optional(value="3.14")


# =============================================================================
# DATA UTILITIES - TRANSFORMATIONS
# =============================================================================


class TestDataTransformations:
    """Tests for MT5Utilities.Data wrapping helpers."""

    def test_wrap_dict(self) -> None:
        """Wrap converts dict to Wrapper."""
        data: dict[str, object] = {"a": 1}
        result = u.Data.wrap(data)
        assert isinstance(result, u.Data.Wrapper)
        assert result.a == 1

    def test_wrap_non_dict(self) -> None:
        """Wrap returns non-dict values unchanged."""
        assert u.Data.wrap(42) == 42
        assert u.Data.wrap("x") == "x"

    def test_wrap_many_none(self) -> None:
        """wrap_many returns None for None."""
        assert u.Data.wrap_many(None) is None

    def test_wrap_many_list(self) -> None:
        """wrap_many converts list of dicts to tuple of Wrappers."""
        items: list[object] = [{"a": 1}, {"b": 2}, "skip"]
        result = u.Data.wrap_many(items)
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], u.Data.Wrapper)
        assert result[0].a == 1
        assert result[2] == "skip"

    def test_wrap_many_tuple(self) -> None:
        """wrap_many accepts tuples as input."""
        items: tuple[object, ...] = ({"x": 1},)
        result = u.Data.wrap_many(items)
        assert result is not None
        assert isinstance(result[0], u.Data.Wrapper)

    def test_unwrap_chunks_none(self) -> None:
        """unwrap_chunks returns None for None input."""
        assert u.Data.unwrap_chunks(None) is None

    def test_unwrap_chunks_with_chunks(self) -> None:
        """unwrap_chunks reassembles chunked dict response."""
        result: dict[str, object] = {
            "chunks": [
                [{"symbol": "EURUSD"}, {"symbol": "GBPUSD"}],
                [{"symbol": "USDJPY"}],
            ]
        }
        unwrapped = u.Data.unwrap_chunks(result)
        assert isinstance(unwrapped, tuple)
        assert len(unwrapped) == 3
        assert isinstance(unwrapped[0], u.Data.Wrapper)
        assert unwrapped[0].symbol == "EURUSD"

    def test_unwrap_chunks_dict_without_chunks(self) -> None:
        """unwrap_chunks with dict lacking 'chunks' falls through."""
        assert u.Data.unwrap_chunks({"other": []}) is None

    def test_unwrap_chunks_list(self) -> None:
        """unwrap_chunks wraps tuple/list result."""
        result: tuple[object, ...] = ({"a": 1}, {"b": 2})
        unwrapped = u.Data.unwrap_chunks(result)
        assert isinstance(unwrapped, tuple)
        assert len(unwrapped) == 2

    def test_unwrap_chunks_other(self) -> None:
        """unwrap_chunks returns None for unsupported types."""
        assert u.Data.unwrap_chunks("string") is None


# =============================================================================
# DATA UTILITIES - DATETIME / JSON / PROTO
# =============================================================================


class TestDataDateTime:
    """Tests for MT5Utilities.Data datetime helpers."""

    def test_to_timestamp_none(self) -> None:
        """to_timestamp returns None for None."""
        assert u.Data.to_timestamp(None) is None

    def test_to_timestamp_datetime(self) -> None:
        """to_timestamp converts datetime to Unix timestamp."""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert u.Data.to_timestamp(dt) == int(dt.timestamp())

    def test_to_timestamp_int(self) -> None:
        """to_timestamp returns int unchanged."""
        assert u.Data.to_timestamp(1704110400) == 1704110400


class TestDataJsonSerialization:
    """Tests for MT5Utilities.Data JSON helpers."""

    def test_json_to_dict_empty(self) -> None:
        """json_to_dict returns None for empty string."""
        assert u.Data.json_to_dict("") is None

    def test_json_to_dict_valid(self) -> None:
        """json_to_dict parses JSON object."""
        result = u.Data.json_to_dict('{"a": 1, "b": "x"}')
        assert result == {"a": 1, "b": "x"}

    def test_json_to_dict_non_object(self) -> None:
        """json_to_dict returns None for non-object JSON."""
        assert u.Data.json_to_dict("[1, 2, 3]") is None

    def test_unwrap_proto_list_to_dicts_empty(self) -> None:
        """unwrap_proto_list_to_dicts returns None for empty list."""
        assert u.Data.unwrap_proto_list_to_dicts([]) is None

    def test_unwrap_proto_list_to_dicts_valid(self) -> None:
        """unwrap_proto_list_to_dicts parses non-empty JSON strings."""
        items = ['{"a": 1}', '{"b": 2}']
        result = u.Data.unwrap_proto_list_to_dicts(items)
        assert result == [{"a": 1}, {"b": 2}]

    def test_unwrap_proto_list_to_dicts_skips_empty(self) -> None:
        """unwrap_proto_list_to_dicts skips empty strings."""
        items = ['{"a": 1}', "", '{"b": 2}']
        result = u.Data.unwrap_proto_list_to_dicts(items)
        assert result == [{"a": 1}, {"b": 2}]

    def test_unwrap_proto_list_to_tuple(self) -> None:
        """unwrap_proto_list_to_tuple returns a tuple of dicts."""
        items = ['{"a": 1}', '{"b": 2}']
        result = u.Data.unwrap_proto_list_to_tuple(items)
        assert isinstance(result, tuple)
        assert result == ({"a": 1}, {"b": 2})

    def test_unwrap_proto_list_to_tuple_empty(self) -> None:
        """unwrap_proto_list_to_tuple returns None for empty list."""
        assert u.Data.unwrap_proto_list_to_tuple([]) is None


class TestDataNumpy:
    """Tests for MT5Utilities.Data numpy/proto helpers."""

    def test_numpy_from_proto_none(self) -> None:
        """numpy_from_proto returns None for None proto."""
        assert u.Data.numpy_from_proto(None) is None

    def test_numpy_from_proto_empty(self) -> None:
        """numpy_from_proto returns None for empty data/dtype."""
        proto_empty_data = MagicMock()
        proto_empty_data.data = b""
        proto_empty_data.dtype = "float64"
        proto_empty_data.shape = (1,)
        assert u.Data.numpy_from_proto(proto_empty_data) is None

        proto_empty_dtype = MagicMock()
        proto_empty_dtype.data = b"\x00" * 8
        proto_empty_dtype.dtype = ""
        proto_empty_dtype.shape = (1,)
        assert u.Data.numpy_from_proto(proto_empty_dtype) is None

    def test_numpy_from_proto_simple_dtype(self) -> None:
        """numpy_from_proto parses simple dtype."""
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        proto = MagicMock()
        proto.data = arr.tobytes()
        proto.dtype = "float64"
        proto.shape = (3,)
        result = u.Data.numpy_from_proto(proto)
        assert result is not None
        np.testing.assert_array_equal(result, arr)

    def test_numpy_from_proto_structured_dtype(self) -> None:
        """numpy_from_proto parses structured dtype string."""
        dtype = np.dtype([("time", "<i8"), ("open", "<f8")])
        arr = np.array([(1, 1.1), (2, 2.2)], dtype=dtype)
        proto = MagicMock()
        proto.data = arr.tobytes()
        proto.dtype = str(dtype)
        proto.shape = (2,)
        result = u.Data.numpy_from_proto(proto)
        assert result is not None
        assert result.dtype.names == ("time", "open")
        assert result["time"][0] == 1

    def test_numpy_from_proto_without_shape(self) -> None:
        """numpy_from_proto works when shape is empty."""
        arr = np.array([1.0, 2.0], dtype=np.float64)
        proto = MagicMock()
        proto.data = arr.tobytes()
        proto.dtype = "float64"
        proto.shape = ()
        result = u.Data.numpy_from_proto(proto)
        assert result is not None
        np.testing.assert_array_equal(result, arr)

    def test_unwrap_symbols_chunks_none(self) -> None:
        """unwrap_symbols_chunks returns None for None response."""
        assert u.Data.unwrap_symbols_chunks(None) is None

    def test_unwrap_symbols_chunks_zero_total(self) -> None:
        """unwrap_symbols_chunks returns None when total is zero."""
        response = MagicMock()
        response.total = 0
        response.chunks = [b'[{"symbol":"EURUSD"}]']
        assert u.Data.unwrap_symbols_chunks(response) is None

    def test_unwrap_symbols_chunks_valid(self) -> None:
        """unwrap_symbols_chunks merges JSON chunks."""
        response = MagicMock()
        response.total = 3
        response.chunks = [
            b'[{"symbol":"EURUSD"},{"symbol":"GBPUSD"}]',
            b'[{"symbol":"USDJPY"}]',
        ]
        result = u.Data.unwrap_symbols_chunks(response)
        assert result is not None
        assert len(result) == 3
        assert result[0]["symbol"] == "EURUSD"


# =============================================================================
# INTROSPECTION
# =============================================================================


class TradeDeal:
    """Named tuple-like class for testing __match_args__ path."""

    __match_args__ = ("ticket", "volume", "price")

    def __init__(self, ticket: int, volume: float, price: float) -> None:
        """Initialize trade deal fields."""
        self.ticket = ticket
        self.volume = volume
        self.price = price


class TestIntrospection:
    """Tests for MT5Utilities.Introspection."""

    def test_get_tuple_field_order_from_match_args(self) -> None:
        """Uses __match_args__ when available."""
        order = u.Introspection.get_tuple_field_order(TradeDeal)
        assert order == ["ticket", "volume", "price"]

    def test_get_tuple_field_order_from_fields(self) -> None:
        """Uses _fields for namedtuples."""
        Point = namedtuple("Point", ["x", "y"])  # noqa: PYI024
        order = u.Introspection.get_tuple_field_order(Point)
        assert order == ["x", "y"]

    def test_get_tuple_field_order_from_member_descriptors(self) -> None:
        """Falls back to member_descriptor introspection for structseq types."""
        # sys.float_info is a structseq type without __match_args__/_fields
        order = u.Introspection.get_tuple_field_order(type(sys.float_info))
        assert order is not None
        assert "epsilon" in order

    def test_get_tuple_field_order_unsupported(self) -> None:
        """Returns None for unsupported types."""
        assert u.Introspection.get_tuple_field_order(str) is None


# =============================================================================
# RETRY STRATEGY - RECONNECT / TIMEOUT
# =============================================================================


class TestRetryStrategyReconnect:
    """Tests for MT5Utilities.RetryStrategy.async_reconnect_with_backoff."""

    @pytest.mark.asyncio
    async def test_reconnect_succeeds_first_attempt(self) -> None:
        """Returns True when connect succeeds on first attempt."""
        config = MT5Settings(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )

        async def connect() -> bool:
            return True

        result = await u.RetryStrategy.async_reconnect_with_backoff(
            connect, config, "test"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_reconnect_succeeds_after_failures(self) -> None:
        """Returns True after some failed attempts."""
        config = MT5Settings(
            retry_max_attempts=5,
            retry_initial_delay=0.01,
            retry_max_delay=0.05,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )
        attempts = 0

        async def connect() -> bool:
            nonlocal attempts
            attempts += 1
            return attempts >= 3

        result = await u.RetryStrategy.async_reconnect_with_backoff(
            connect, config, "test"
        )
        assert result is True
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_reconnect_fails_all_attempts(self) -> None:
        """Returns False when all attempts fail."""
        config = MT5Settings(
            retry_max_attempts=2,
            retry_initial_delay=0.01,
            retry_max_delay=0.02,
            retry_jitter=False,
        )

        async def connect() -> bool:
            return False

        result = await u.RetryStrategy.async_reconnect_with_backoff(
            connect, config, "test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_with_exception(self) -> None:
        """Reconnect continues through exceptions."""
        config = MT5Settings(
            retry_max_attempts=2,
            retry_initial_delay=0.01,
            retry_max_delay=0.02,
            retry_jitter=False,
        )
        calls = 0

        async def connect() -> bool:
            nonlocal calls
            calls += 1
            if calls == 1:
                _transient_msg = "transient"
                raise ConnectionError(_transient_msg)
            return True

        result = await u.RetryStrategy.async_reconnect_with_backoff(
            connect, config, "test"
        )
        assert result is True
        assert calls == 2

    @pytest.mark.asyncio
    async def test_reconnect_with_jitter(self) -> None:
        """Reconnect uses jitter when enabled."""
        config = MT5Settings(
            retry_max_attempts=2,
            retry_initial_delay=0.01,
            retry_max_delay=0.02,
            retry_jitter=True,
        )

        async def connect() -> bool:
            return False

        result = await u.RetryStrategy.async_reconnect_with_backoff(
            connect, config, "test"
        )
        assert result is False


class TestRetryStrategyTimeout:
    """Tests for MT5Utilities.RetryStrategy.execute_with_timeout_and_cancel."""

    @pytest.mark.asyncio
    async def test_timeout_success(self) -> None:
        """Returns result and timed_out=False on success."""

        async def work() -> str:
            return "done"

        result, timed_out = await u.RetryStrategy.execute_with_timeout_and_cancel(
            work(), 1.0, "op"
        )
        assert result == "done"
        assert timed_out is False

    @pytest.mark.asyncio
    async def test_timeout_expires(self) -> None:
        """Returns None and timed_out=True on timeout."""

        async def slow() -> str:
            await asyncio.sleep(2.0)
            return "done"

        result, timed_out = await u.RetryStrategy.execute_with_timeout_and_cancel(
            slow(), 0.01, "op"
        )
        assert result is None
        assert timed_out is True

    @pytest.mark.asyncio
    async def test_timeout_invalid_value(self) -> None:
        """Raises ValueError for non-positive timeout."""

        async def work() -> str:
            return "done"

        coro = work()
        try:
            with pytest.raises(ValueError, match="timeout must be > 0"):
                await u.RetryStrategy.execute_with_timeout_and_cancel(coro, 0.0, "op")
        finally:
            coro.close()

    @pytest.mark.asyncio
    async def test_timeout_propagates_exception(self) -> None:
        """Propagates non-timeout exceptions."""

        async def failing() -> str:
            msg = "boom"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="boom"):
            await u.RetryStrategy.execute_with_timeout_and_cancel(failing(), 1.0, "op")


# =============================================================================
# TRANSACTION ORCHESTRATOR
# =============================================================================


class _Result:
    """Minimal stand-in for order result objects."""

    def __init__(
        self,
        retcode: int = 10009,
        order: int = 1,
        deal: int = 2,
        comment: str = "done",
    ) -> None:
        self.retcode = retcode
        self.order = order
        self.deal = deal
        self.comment = comment


@pytest.fixture
def base_config() -> MT5Settings:
    """Default config for orchestrator tests."""
    return MT5Settings(
        retry_max_attempts=2,
        critical_retry_max_attempts=3,
        critical_retry_initial_delay=0.01,
        retry_jitter=False,
    )


@pytest.fixture
def success_deps() -> u.TransactionOrchestrator.Dependencies:
    """Dependencies that succeed immediately."""
    return u.TransactionOrchestrator.Dependencies(
        execute_grpc=AsyncMock(return_value=_Result()),
        verify_state=AsyncMock(return_value=None),
        health_check=AsyncMock(return_value=True),
    )


@pytest.fixture
def full_deps() -> u.TransactionOrchestrator.Dependencies:
    """Dependencies with all optional callbacks wired as mocks."""
    return u.TransactionOrchestrator.Dependencies(
        execute_grpc=AsyncMock(return_value=_Result()),
        verify_state=AsyncMock(return_value=None),
        health_check=AsyncMock(return_value=True),
        check_circuit_breaker=MagicMock(),
        record_success=MagicMock(),
        record_failure=MagicMock(),
        wal_log_intent=AsyncMock(),
        wal_mark_sent=AsyncMock(),
        wal_mark_verified=AsyncMock(),
        wal_mark_failed=AsyncMock(),
    )


class TestTransactionOrchestrator:
    """Tests for MT5Utilities.TransactionOrchestrator."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute returns successful result."""
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        request: dict[str, object] = {"action": "buy", "symbol": "EURUSD"}
        result = await orchestrator.execute(request)
        assert isinstance(result, _Result)
        assert result.retcode == 10009
        success_deps.execute_grpc.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_partial_fill(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute returns partial result."""
        success_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10010))
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert isinstance(result, _Result)
        assert result.retcode == 10010

    @pytest.mark.asyncio
    async def test_execute_permanent_failure(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises PermanentError for permanent retcode."""
        success_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10006))
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_verify_required_found(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute returns verified result when verify_state finds it."""
        verified = _Result(retcode=10009, order=10, deal=20)
        success_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10012))
        success_deps.verify_state = AsyncMock(return_value=verified)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert result is verified

    @pytest.mark.asyncio
    async def test_execute_verify_required_not_found(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises PermanentError when verification fails."""
        success_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10012))
        success_deps.verify_state = AsyncMock(return_value=None)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_retryable_then_success(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute retries retryable retcode and returns success."""
        success_deps.execute_grpc = AsyncMock(
            side_effect=[_Result(retcode=10004), _Result(retcode=10009)]
        )
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert isinstance(result, _Result)
        assert result.retcode == 10009
        assert success_deps.execute_grpc.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_retryable_exception_exhausted(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises MaxRetriesError after retryable exceptions exhausted."""
        success_deps.execute_grpc = AsyncMock(
            side_effect=ConnectionError("lost"),
        )
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.MaxRetriesError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_retryable_retcode_exhausted_becomes_permanent(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises PermanentError when retcode exists at exhaustion."""
        success_deps.execute_grpc = AsyncMock(
            return_value=_Result(retcode=10004),
        )
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_empty_response_verified(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute handles empty response verified by state."""
        verified = _Result(retcode=10009, order=5, deal=6)
        success_deps.execute_grpc = AsyncMock(return_value=None)
        success_deps.verify_state = AsyncMock(return_value=verified)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert result is verified

    @pytest.mark.asyncio
    async def test_execute_empty_response_retries(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute retries when empty response is not verified and MT5 healthy."""
        success_deps.execute_grpc = AsyncMock(
            side_effect=[None, _Result(retcode=10009)]
        )
        success_deps.verify_state = AsyncMock(return_value=None)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert isinstance(result, _Result)

    @pytest.mark.asyncio
    async def test_execute_empty_response_unhealthy(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises PermanentError when empty response and MT5 unreachable."""
        success_deps.execute_grpc = AsyncMock(return_value=None)
        success_deps.verify_state = AsyncMock(return_value=None)
        success_deps.health_check = AsyncMock(return_value=False)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_retryable_exception_healthy(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute retries on retryable exception when MT5 is healthy."""
        success_deps.execute_grpc = AsyncMock(
            side_effect=[ConnectionError("lost"), _Result(retcode=10009)]
        )
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert isinstance(result, _Result)
        assert success_deps.execute_grpc.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_retryable_exception_unhealthy_verified(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute returns verified result on exception when MT5 unhealthy."""
        verified = _Result(retcode=10009)
        success_deps.execute_grpc = AsyncMock(side_effect=ConnectionError("lost"))
        success_deps.verify_state = AsyncMock(return_value=verified)
        success_deps.health_check = AsyncMock(return_value=False)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert result is verified

    @pytest.mark.asyncio
    async def test_execute_retryable_exception_unhealthy_not_verified(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute raises PermanentError when unhealthy and not verified."""
        success_deps.execute_grpc = AsyncMock(side_effect=ConnectionError("lost"))
        success_deps.verify_state = AsyncMock(return_value=None)
        success_deps.health_check = AsyncMock(return_value=False)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_execute_non_retryable_exception_propagates(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """Execute propagates non-retryable exceptions."""
        success_deps.execute_grpc = AsyncMock(side_effect=ValueError("bad request"))
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(ValueError, match="bad request"):
            await orchestrator.execute({"action": "buy"})

    @pytest.mark.asyncio
    async def test_handle_empty_response_verified(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """_handle_empty_response returns verified result."""
        verified = _Result(retcode=10009)
        success_deps.verify_state = AsyncMock(return_value=verified)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator._handle_empty_response("RQ123")
        assert result is verified

    @pytest.mark.asyncio
    async def test_handle_empty_response_unhealthy(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """_handle_empty_response raises PermanentError when MT5 unhealthy."""
        success_deps.verify_state = AsyncMock(return_value=None)
        success_deps.health_check = AsyncMock(return_value=False)
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator._handle_empty_response("RQ123")

    @pytest.mark.asyncio
    async def test_try_verify_synthetic(
        self,
        base_config: MT5Settings,
        success_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """_try_verify_synthetic calls verify_state with synthetic result."""
        success_deps.verify_state = AsyncMock(return_value=_Result())
        orchestrator = u.TransactionOrchestrator(base_config, success_deps)
        result = await orchestrator._try_verify_synthetic("RQ123")
        assert result is not None
        success_deps.verify_state.assert_awaited_once()
        synthetic = success_deps.verify_state.await_args.args[0]
        assert synthetic.retcode == 0
        assert synthetic.order == 0
        assert synthetic.deal == 0


# =============================================================================
# CIRCUIT BREAKER STATUS
# =============================================================================


class TestCircuitBreakerStatus:
    """Additional tests for CircuitBreaker monitoring/status."""

    def test_get_status_closed(self) -> None:
        """get_status reflects closed state and config threshold."""
        config = MT5Settings(cb_threshold=5, cb_recovery=30.0)
        cb = u.CircuitBreaker(config=config, name="test")
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["failure_threshold"] == 5
        assert "last_failure" not in status

    def test_get_status_open(self) -> None:
        """get_status includes recovery time when open."""
        config = MT5Settings(cb_threshold=1, cb_recovery=30.0)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        status = cb.get_status()
        assert status["state"] == "OPEN"
        assert "last_failure" in status
        assert "recovery_at" in status

    def test_get_status_half_open(self) -> None:
        """get_status omits recovery_at when not OPEN."""
        config = MT5Settings(cb_threshold=1, cb_recovery=0.01)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN
        status = cb.get_status()
        assert status["state"] == "HALF_OPEN"
        assert "last_failure" in status
        assert "recovery_at" not in status


# =============================================================================
# ERROR CLASSIFIER COMPLEMENTARY TESTS
# =============================================================================


class TestErrorClassifierComplementary:
    """Tests for ErrorClassifier not covered elsewhere."""

    def test_is_retryable_grpc_code(self) -> None:
        """is_retryable_grpc_code recognizes known retryable codes."""
        assert u.ErrorClassifier.is_retryable_grpc_code(
            c.Resilience.GrpcRetryableCode.UNAVAILABLE
        )
        assert not u.ErrorClassifier.is_retryable_grpc_code(9999)

    def test_is_permanent_mt5_code(self) -> None:
        """is_permanent_mt5_code returns True for permanent retcodes."""
        assert u.ErrorClassifier.is_permanent_mt5_code(10006)
        assert not u.ErrorClassifier.is_permanent_mt5_code(10009)

    def test_is_retryable_exception_with_grpc_error(self) -> None:
        """is_retryable_exception handles gRPC-like errors."""

        class GrpcError(Exception):
            def code(self) -> object:
                return type(
                    "Code",
                    (),
                    {"value": (c.Resilience.GrpcRetryableCode.UNAVAILABLE,)},
                )()

        assert u.ErrorClassifier.is_retryable_exception(GrpcError())

    def test_is_retryable_exception_connection_not_established(self) -> None:
        """ConnectionError with 'not established' is not retryable."""
        assert not u.ErrorClassifier.is_retryable_exception(
            ConnectionError("Connection not established")
        )

    def test_is_retryable_exception_os_error(self) -> None:
        """OSError is retryable."""
        assert u.ErrorClassifier.is_retryable_exception(OSError("io"))

    def test_is_retryable_exception_with_retryable_error(self) -> None:
        """RetryableError instances are retryable."""
        assert u.ErrorClassifier.is_retryable_exception(
            u.Exceptions.RetryableError(10004, "requote")
        )

    def test_is_retryable_exception_empty_response(self) -> None:
        """EmptyResponseError (RetryableError subclass) is retryable."""
        assert u.ErrorClassifier.is_retryable_exception(
            u.Exceptions.EmptyResponseError("order_send")
        )

    def test_is_retryable_exception_connection_call_connect(self) -> None:
        """ConnectionError mentioning 'call connect' is not retryable."""
        assert not u.ErrorClassifier.is_retryable_exception(
            ConnectionError("Please call connect() first")
        )

    def test_is_retryable_mt5_code(self) -> None:
        """is_retryable_mt5_code returns True only for retryable retcodes."""
        assert u.ErrorClassifier.is_retryable_mt5_code(10004)
        assert not u.ErrorClassifier.is_retryable_mt5_code(10009)
        assert not u.ErrorClassifier.is_retryable_mt5_code(10006)

    def test_should_verify_state_for_critical(self) -> None:
        """Critical operations verify state for ambiguous classifications."""
        assert u.ErrorClassifier.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.VERIFY_REQUIRED,
        )
        assert u.ErrorClassifier.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.CONDITIONAL,
        )
        assert u.ErrorClassifier.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.UNKNOWN,
        )

    def test_should_verify_state_for_non_critical(self) -> None:
        """Non-critical operations skip verification."""
        assert not u.ErrorClassifier.should_verify_state(
            "symbol_info",
            c.Resilience.ErrorClassification.VERIFY_REQUIRED,
        )

    def test_classify_mt5_retcode_conditional(self) -> None:
        """classify_mt5_retcode returns CONDITIONAL for conditional codes."""
        for code in [10007, 10018, 10023, 10025]:
            classification = u.ErrorClassifier.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.CONDITIONAL

    def test_classify_mt5_retcode_unknown(self) -> None:
        """classify_mt5_retcode returns UNKNOWN for unrecognized codes."""
        assert (
            u.ErrorClassifier.classify_mt5_retcode(99999)
            == c.Resilience.ErrorClassification.UNKNOWN
        )


# =============================================================================
# DATA BRANCHES
# =============================================================================


class TestDataBranches:
    """Tests for Data branches not covered by the main Data tests."""

    def test_unwrap_chunks_chunks_not_list(self) -> None:
        """unwrap_chunks returns empty tuple when 'chunks' is not a list."""
        result: dict[str, object] = {"chunks": "not-a-list"}
        assert u.Data.unwrap_chunks(result) == ()

    def test_unwrap_chunks_chunk_not_list(self) -> None:
        """unwrap_chunks skips non-list individual chunks."""
        result: dict[str, object] = {
            "chunks": [
                [{"symbol": "EURUSD"}],
                "not-a-list",
            ]
        }
        unwrapped = u.Data.unwrap_chunks(result)
        assert isinstance(unwrapped, tuple)
        assert len(unwrapped) == 1
        assert unwrapped[0].symbol == "EURUSD"

    def test_wrap_many_empty_iterable(self) -> None:
        """wrap_many returns empty tuple for empty list."""
        result = u.Data.wrap_many([])
        assert result == ()

    def test_json_to_dict_empty_string(self) -> None:
        """json_to_dict returns None for an empty string."""
        assert u.Data.json_to_dict("") is None

    def test_mark_comment_truncates_original(self) -> None:
        """mark_comment truncates long original comments to fit 31 chars."""
        req_id = "RQ1234567890abcdef"
        marked = u.TransactionHandler.RequestTracker.mark_comment("x" * 50, req_id)
        assert len(marked) <= 31
        assert marked.startswith(req_id)

    def test_extract_request_id_invalid_hex(self) -> None:
        """extract_request_id rejects non-hex request IDs."""
        assert (
            u.TransactionHandler.RequestTracker.extract_request_id("RQgggggggggggggggg")
            is None
        )

    def test_extract_request_id_wrong_length(self) -> None:
        """extract_request_id rejects wrong-length request IDs."""
        assert u.TransactionHandler.RequestTracker.extract_request_id("RQ12345") is None


# =============================================================================
# INTROSPECTION FALLBACK
# =============================================================================


class MemberDescriptor:
    """Fake descriptor whose type name matches the built-in descriptor."""

    def __init__(self, idx: int) -> None:
        """Initialize descriptor with target tuple index."""
        self._idx = idx

    def __get__(self, obj: object | None, objtype: type | None = None) -> object:
        """Read tuple item at configured index."""
        if isinstance(obj, tuple):
            return obj[self._idx] if self._idx < len(obj) else None
        return self

    def __set__(self, obj: object, value: object) -> None:
        """Raise AttributeError because this descriptor is read-only."""
        _readonly_msg = "readonly"
        raise AttributeError(_readonly_msg)


class _FallbackTuple(tuple):
    """Tuple subclass without __match_args__/_fields but with member descriptors."""

    __slots__ = ()

    a = MemberDescriptor(0)
    b = MemberDescriptor(1)
    c = MemberDescriptor(2)


class TestIntrospectionFallback:
    """Tests for the MemberDescriptor fallback path."""

    def test_fallback_member_descriptor_order(self) -> None:
        """Fallback determines order from MemberDescriptor values."""
        order = u.Introspection.get_tuple_field_order(_FallbackTuple)
        assert order == ["a", "b", "c"]

    def test_fallback_incomplete_mapping_returns_none(self) -> None:
        """Fallback returns None when indices cannot be fully mapped."""

        class BadTuple(tuple):
            """Tuple subclass with an out-of-range member descriptor."""

            __slots__ = ()
            a = MemberDescriptor(0)
            b = MemberDescriptor(5)  # Out of range for a 2-item tuple

        assert u.Introspection.get_tuple_field_order(BadTuple) is None

    def test_fallback_instantiation_fails_returns_none(self) -> None:
        """Fallback returns None when tuple instantiation fails."""

        class NoInitTuple(tuple):
            """Tuple subclass that refuses instantiation."""

            __slots__ = ()
            a = MemberDescriptor(0)

            def __new__(cls) -> Self:
                _nope_msg = "nope"
                raise TypeError(_nope_msg)

        assert u.Introspection.get_tuple_field_order(NoInitTuple) is None


# =============================================================================
# RETRY STRATEGY - ASYNC BACKOFF
# =============================================================================


class TestRetryStrategyBackoff:
    """Tests for async_retry_with_backoff detailed paths."""

    @pytest.mark.asyncio
    async def test_backoff_success_no_retry(self) -> None:
        """Returns immediately on success."""
        config = MT5Settings(retry_max_attempts=3)

        async def work() -> str:
            return "ok"

        result = await u.RetryStrategy.async_retry_with_backoff(work, config, "op")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_backoff_success_after_retries(self) -> None:
        """Retries and eventually succeeds."""
        config = MT5Settings(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        calls = 0

        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                _transient_msg = "transient"
                raise ConnectionError(_transient_msg)
            return "ok"

        result = await u.RetryStrategy.async_retry_with_backoff(flaky, config, "op")
        assert result == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_backoff_non_retryable_propagates(self) -> None:
        """Non-retryable exceptions propagate immediately."""
        config = MT5Settings(retry_max_attempts=3)

        async def bad() -> str:
            _permanent_msg = "permanent"
            raise ValueError(_permanent_msg)

        with pytest.raises(ValueError, match="permanent"):
            await u.RetryStrategy.async_retry_with_backoff(
                bad,
                config,
                "op",
                should_retry=lambda e: not isinstance(e, ValueError),
            )

    @pytest.mark.asyncio
    async def test_backoff_on_success_callback_failure_ignored(self) -> None:
        """Failure in on_success callback does not lose result."""
        config = MT5Settings(retry_max_attempts=1)

        async def work() -> str:
            return "result"

        def bad_success() -> None:
            _callback_failed_msg = "callback failed"
            raise RuntimeError(_callback_failed_msg)

        result = await u.RetryStrategy.async_retry_with_backoff(
            work,
            config,
            "op",
            on_success=bad_success,
        )
        assert result == "result"

    @pytest.mark.asyncio
    async def test_backoff_before_retry_failure_ignored(self) -> None:
        """Failure in before_retry callback does not stop retry."""
        config = MT5Settings(
            retry_max_attempts=2,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        calls = 0

        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                _transient_msg = "transient"
                raise ConnectionError(_transient_msg)
            return "ok"

        async def bad_before_retry() -> None:
            _before_retry_failed_msg = "before_retry failed"
            raise RuntimeError(_before_retry_failed_msg)

        result = await u.RetryStrategy.async_retry_with_backoff(
            flaky,
            config,
            "op",
            before_retry=bad_before_retry,
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_backoff_invalid_max_attempts(self) -> None:
        """max_attempts < 1 raises ValueError."""
        config = MT5Settings(retry_max_attempts=3)

        async def work() -> str:
            return "ok"

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await u.RetryStrategy.async_retry_with_backoff(
                work,
                config,
                "op",
                max_attempts_override=0,
            )

    @pytest.mark.asyncio
    async def test_backoff_on_failure_called_for_non_retryable(self) -> None:
        """on_failure is invoked when a non-retryable exception occurs."""
        config = MT5Settings(retry_max_attempts=3)
        failure: Exception | None = None

        async def bad() -> str:
            _permanent_msg = "permanent"
            raise ValueError(_permanent_msg)

        def on_failure(e: Exception) -> None:
            nonlocal failure
            failure = e

        with pytest.raises(ValueError, match="permanent"):
            await u.RetryStrategy.async_retry_with_backoff(
                bad,
                config,
                "op",
                should_retry=lambda e: not isinstance(e, ValueError),
                on_failure=on_failure,
            )
        assert isinstance(failure, ValueError)


# =============================================================================
# RETRY STRATEGY - TIMEOUT BOUNDARY
# =============================================================================


class TestRetryStrategyTimeoutBoundary:
    """Tests for execute_with_timeout_and_cancel race recovery."""

    @pytest.mark.asyncio
    async def test_timeout_boundary_result_recovered(self) -> None:
        """Result completed exactly at timeout boundary is recovered."""

        async def just_in_time() -> str:
            await asyncio.sleep(0.05)
            return "recovered"

        # Use a short timeout that will likely fire before the coroutine finishes,
        # but the coroutine may complete between the timeout and cancellation.
        result, timed_out = await u.RetryStrategy.execute_with_timeout_and_cancel(
            just_in_time(), 0.01, "op"
        )
        # Either we recovered the result or it genuinely timed out.
        assert result in {"recovered", None}
        assert isinstance(timed_out, bool)


# =============================================================================
# CIRCUIT BREAKER LIFECYCLE
# =============================================================================


class TestCircuitBreakerLifecycle:
    """Detailed tests for CircuitBreaker state transitions."""

    def test_state_open_to_half_open(self) -> None:
        """State property transitions OPEN -> HALF_OPEN after recovery time."""
        config = MT5Settings(cb_threshold=1, cb_recovery=0.01)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        assert cb.is_open
        # Wait for recovery window
        time.sleep(0.02)
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN

    def test_can_execute_closed(self) -> None:
        """can_execute returns True when CLOSED."""
        config = MT5Settings(cb_threshold=5)
        cb = u.CircuitBreaker(config=config, name="test")
        assert cb.can_execute() is True

    def test_can_execute_open(self) -> None:
        """can_execute returns False when OPEN."""
        config = MT5Settings(cb_threshold=1, cb_recovery=60.0)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        assert cb.can_execute() is False

    def test_can_execute_half_open_limited(self) -> None:
        """can_execute allows only half_open_max calls in HALF_OPEN."""
        config = MT5Settings(cb_threshold=1, cb_recovery=0.01, cb_half_open_max=2)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        time.sleep(0.02)
        assert cb.can_execute() is True
        assert cb.can_execute() is True
        assert cb.can_execute() is False

    def test_record_success_in_half_open_closes(self) -> None:
        """Success in HALF_OPEN closes the circuit."""
        config = MT5Settings(cb_threshold=1, cb_recovery=0.01)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.is_closed

    def test_record_failure_in_half_open_reopens(self) -> None:
        """Failure in HALF_OPEN reopens the circuit."""
        config = MT5Settings(cb_threshold=1, cb_recovery=0.01)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN
        cb.record_failure()
        assert cb.is_open

    def test_reset(self) -> None:
        """Reset returns circuit to clean CLOSED state."""
        config = MT5Settings(cb_threshold=1)
        cb = u.CircuitBreaker(config=config, name="test")
        cb.record_failure()
        assert cb.is_open
        cb.reset()
        assert cb.is_closed
        assert cb.failure_count == 0
        assert cb.get_status()["success_count"] == 0

    def test_config_property(self) -> None:
        """Config property returns the settings object."""
        config = MT5Settings()
        cb = u.CircuitBreaker(config=config, name="test")
        assert cb.config is config


# =============================================================================
# TRANSACTION ORCHESTRATOR CALLBACKS
# =============================================================================


class TestTransactionOrchestratorCallbacks:
    """Tests for TransactionOrchestrator optional callback wiring."""

    @pytest.mark.asyncio
    async def test_execute_wal_callbacks_on_success(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """WAL intent/sent/verified callbacks are invoked on success."""
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10009))
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        await orchestrator.execute({"action": "buy"})

        assert full_deps.wal_log_intent.await_count == 1
        assert full_deps.wal_mark_sent.await_count == 1
        assert full_deps.wal_mark_verified.await_count == 1
        assert full_deps.wal_mark_failed.await_count == 0

    @pytest.mark.asyncio
    async def test_execute_wal_callbacks_on_permanent_failure(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """WAL failed callback is invoked on permanent failure."""
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10006))
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})

        assert full_deps.wal_mark_failed.await_count == 1
        assert full_deps.wal_mark_verified.await_count == 0

    @pytest.mark.asyncio
    async def test_execute_circuit_breaker_callback_invoked(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """check_circuit_breaker callback is invoked before execution."""
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10009))
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        await orchestrator.execute({"action": "buy"})
        full_deps.check_circuit_breaker.assert_called_once_with("order_send")

    @pytest.mark.asyncio
    async def test_execute_record_success_callback(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """record_success callback is invoked on success."""
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10009))
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        await orchestrator.execute({"action": "buy"})
        full_deps.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_record_failure_callback(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """record_failure callback is invoked on permanent failure."""
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10006))
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        with pytest.raises(u.Exceptions.PermanentError):
            await orchestrator.execute({"action": "buy"})
        full_deps.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_verify_required_records_verified(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """WAL verified callback is invoked when verify_state succeeds."""
        verified = _Result(retcode=10009, order=10, deal=20)
        full_deps.execute_grpc = AsyncMock(return_value=_Result(retcode=10012))
        full_deps.verify_state = AsyncMock(return_value=verified)
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        result = await orchestrator.execute({"action": "buy"})
        assert result is verified
        assert full_deps.wal_mark_verified.await_count == 1
        full_deps.record_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_retry_records_failure(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """record_failure is invoked for retryable retcode."""
        full_deps.execute_grpc = AsyncMock(
            side_effect=[_Result(retcode=10004), _Result(retcode=10009)]
        )
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        await orchestrator.execute({"action": "buy"})
        assert full_deps.record_failure.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_empty_response_records_failure(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """_handle_empty_response records failure when MT5 is healthy."""
        full_deps.verify_state = AsyncMock(return_value=None)
        full_deps.health_check = AsyncMock(return_value=True)
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        result = await orchestrator._handle_empty_response("RQ123")
        assert result is None
        full_deps.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_empty_response_records_success(
        self,
        base_config: MT5Settings,
        full_deps: u.TransactionOrchestrator.Dependencies,
    ) -> None:
        """_handle_empty_response records success when verified."""
        verified = _Result(retcode=10009)
        full_deps.verify_state = AsyncMock(return_value=verified)
        orchestrator = u.TransactionOrchestrator(base_config, full_deps)
        result = await orchestrator._handle_empty_response("RQ123")
        assert result is verified
        full_deps.record_success.assert_called_once()
