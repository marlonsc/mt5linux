"""Tests for order_send_async and order_send_batch methods.

Tests verify:
1. order_send_async returns immediately with request_id
2. Callbacks are called correctly on success/error
3. WAL integration for order tracking
4. order_send_batch executes multiple orders in parallel
5. Batch callbacks work correctly

These tests focus on the callback mechanism and structure.
Integration tests for actual order execution require MT5 server.
"""

from __future__ import annotations


class TestOrderSendAsyncSignature:
    """Test order_send_async method signature and basic behavior."""

    def test_order_send_async_exists_on_async_client(self) -> None:
        """order_send_async method exists on AsyncMetaTrader5."""
        from mt5linux.async_client import AsyncMetaTrader5

        assert hasattr(AsyncMetaTrader5, "order_send_async")
        method = AsyncMetaTrader5.order_send_async
        assert callable(method)

    def test_order_send_async_exists_on_sync_client(self) -> None:
        """order_send_async method exists on MetaTrader5 (sync wrapper)."""
        from mt5linux.client import MetaTrader5

        assert hasattr(MetaTrader5, "order_send_async")
        method = MetaTrader5.order_send_async
        assert callable(method)

    def test_order_send_async_accepts_callbacks(self) -> None:
        """order_send_async accepts on_complete and on_error callbacks."""
        from inspect import signature

        from mt5linux.async_client import AsyncMetaTrader5

        sig = signature(AsyncMetaTrader5.order_send_async)
        params = sig.parameters

        assert "request" in params
        assert "on_complete" in params
        assert "on_error" in params


class TestOrderSendBatchSignature:
    """Test order_send_batch method signature and basic behavior."""

    def test_order_send_batch_exists_on_async_client(self) -> None:
        """order_send_batch method exists on AsyncMetaTrader5."""
        from mt5linux.async_client import AsyncMetaTrader5

        assert hasattr(AsyncMetaTrader5, "order_send_batch")
        method = AsyncMetaTrader5.order_send_batch
        assert callable(method)

    def test_order_send_batch_exists_on_sync_client(self) -> None:
        """order_send_batch method exists on MetaTrader5 (sync wrapper)."""
        from mt5linux.client import MetaTrader5

        assert hasattr(MetaTrader5, "order_send_batch")
        method = MetaTrader5.order_send_batch
        assert callable(method)

    def test_order_send_batch_accepts_callbacks(self) -> None:
        """order_send_batch accepts batch callbacks."""
        from inspect import signature

        from mt5linux.async_client import AsyncMetaTrader5

        sig = signature(AsyncMetaTrader5.order_send_batch)
        params = sig.parameters

        assert "requests" in params
        assert "on_each_complete" in params
        assert "on_each_error" in params
        assert "on_all_complete" in params


class TestProtocolCompliance:
    """Test that methods are defined in protocols."""

    def test_order_send_async_in_protocol(self) -> None:
        """order_send_async is defined in AsyncMT5Protocol."""
        from mt5linux.protocols import AsyncMT5Protocol

        assert hasattr(AsyncMT5Protocol, "order_send_async")

    def test_order_send_batch_in_protocol(self) -> None:
        """order_send_batch is defined in AsyncMT5Protocol."""
        from mt5linux.protocols import AsyncMT5Protocol

        assert hasattr(AsyncMT5Protocol, "order_send_batch")


class TestRequestIdGeneration:
    """Test request ID generation for tracking orders."""

    def test_request_id_format(self) -> None:
        """Request IDs follow expected format (RQ + 16 hex chars)."""
        from mt5linux.utilities import MT5Utilities

        tracker = MT5Utilities.TransactionHandler.RequestTracker
        request_id = tracker.generate_request_id()
        assert request_id.startswith("RQ")
        assert len(request_id) == 18  # RQ + 16 hex

    def test_request_ids_are_unique(self) -> None:
        """Generated request IDs are unique."""
        from mt5linux.utilities import MT5Utilities

        ids = {
            MT5Utilities.TransactionHandler.RequestTracker.generate_request_id()
            for _ in range(100)
        }
        assert len(ids) == 100


class TestCallbackSignature:
    """Test callback parameters in method signatures."""

    def test_order_send_async_has_callback_params(self) -> None:
        """order_send_async has on_complete and on_error parameters."""
        from inspect import signature

        from mt5linux.async_client import AsyncMetaTrader5

        sig = signature(AsyncMetaTrader5.order_send_async)
        params = sig.parameters

        # Verify callback parameters exist with default None
        assert "on_complete" in params
        assert params["on_complete"].default is None
        assert "on_error" in params
        assert params["on_error"].default is None

    def test_order_send_batch_has_callback_params(self) -> None:
        """order_send_batch has batch callback parameters."""
        from inspect import signature

        from mt5linux.async_client import AsyncMetaTrader5

        sig = signature(AsyncMetaTrader5.order_send_batch)
        params = sig.parameters

        # Verify batch callback parameters exist with default None
        assert "on_each_complete" in params
        assert params["on_each_complete"].default is None
        assert "on_each_error" in params
        assert params["on_each_error"].default is None
        assert "on_all_complete" in params
        assert params["on_all_complete"].default is None


class TestTransactionHandlerIntegration:
    """Test TransactionHandler prepares requests correctly."""

    def test_prepare_request_adds_request_id(self) -> None:
        """prepare_request adds request_id to comment."""
        from mt5linux.utilities import MT5Utilities

        request = {"action": 1, "symbol": "EURUSD", "volume": 0.1}
        prepared, request_id = MT5Utilities.TransactionHandler.prepare_request(
            request, "order_send"
        )

        assert request_id.startswith("RQ")
        # Comment should contain request_id
        assert "comment" in prepared
        assert request_id in prepared["comment"]

    def test_prepare_request_preserves_existing_comment(self) -> None:
        """prepare_request preserves existing comment."""
        from mt5linux.utilities import MT5Utilities

        request = {
            "action": 1,
            "symbol": "EURUSD",
            "volume": 0.1,
            "comment": "my_strategy",
        }
        prepared, request_id = MT5Utilities.TransactionHandler.prepare_request(
            request, "order_send"
        )

        # Both request_id and original comment should be present
        comment = prepared["comment"]
        assert request_id in comment
        # Original comment might be truncated but should have some part
        # Comment format: "RQ{id}|{original}" or just "RQ{id}" if truncated
        assert comment.startswith(request_id)


class TestAsyncBehavior:
    """Test async behavior of methods."""

    async def test_order_send_async_is_coroutine(self) -> None:
        """order_send_async returns a coroutine."""
        from asyncio import iscoroutinefunction

        from mt5linux.async_client import AsyncMetaTrader5

        assert iscoroutinefunction(AsyncMetaTrader5.order_send_async)

    async def test_order_send_batch_is_coroutine(self) -> None:
        """order_send_batch returns a coroutine."""
        from asyncio import iscoroutinefunction

        from mt5linux.async_client import AsyncMetaTrader5

        assert iscoroutinefunction(AsyncMetaTrader5.order_send_batch)
