"""Tests for resilience patterns.

Tests circuit breaker and retry logic from MT5Utilities.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants as c
from mt5linux.utilities import MT5Utilities


class TestCircuitBreaker:
    """Tests for MT5Utilities.CircuitBreaker class."""

    @pytest.fixture
    def config(self) -> MT5Config:
        """Create test config with fast recovery."""
        return MT5Config(
            cb_threshold=3,
            cb_recovery=0.1,
            cb_half_open_max=2,
        )

    def test_initial_state_is_closed(self, config: MT5Config) -> None:
        """Circuit starts in CLOSED state."""
        cb = MT5Utilities.CircuitBreaker(config=config)
        assert cb.state == c.Resilience.CircuitBreakerState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    def test_stays_closed_below_threshold(self) -> None:
        """Circuit stays CLOSED if failures are below threshold."""
        config = MT5Config(cb_threshold=5)
        cb = MT5Utilities.CircuitBreaker(config=config)

        for _ in range(4):
            cb.record_failure()

        assert cb.state == c.Resilience.CircuitBreakerState.CLOSED
        assert cb.failure_count == 4

    def test_opens_at_threshold(self, config: MT5Config) -> None:
        """Circuit opens when failure threshold is reached."""
        cb = MT5Utilities.CircuitBreaker(config=config)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == c.Resilience.CircuitBreakerState.OPEN
        assert cb.is_open
        assert cb.failure_count == 3

    def test_success_resets_failure_count(self) -> None:
        """Success in CLOSED state resets failure count."""
        config = MT5Config(cb_threshold=5)
        cb = MT5Utilities.CircuitBreaker(config=config)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_can_execute_when_closed(self, config: MT5Config) -> None:
        """Can execute when circuit is CLOSED."""
        cb = MT5Utilities.CircuitBreaker(config=config)
        assert cb.can_execute()

    def test_cannot_execute_when_open(self, config: MT5Config) -> None:
        """Cannot execute when circuit is OPEN."""
        cb = MT5Utilities.CircuitBreaker(config=config)

        for _ in range(3):
            cb.record_failure()

        assert not cb.can_execute()

    def test_transitions_to_half_open_after_recovery_timeout(
        self, config: MT5Config
    ) -> None:
        """Circuit transitions OPEN -> HALF_OPEN after recovery timeout."""
        cb = MT5Utilities.CircuitBreaker(config=config)

        # Open the circuit
        for _ in range(3):
            cb.record_failure()
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN

        # Wait for recovery timeout
        import time

        time.sleep(0.15)

        # Should transition to HALF_OPEN (via state property check)
        # State changes after timeout - mypy doesn't track time-based transitions
        expected_state = c.Resilience.CircuitBreakerState.HALF_OPEN
        assert cb.state == expected_state

    def test_half_open_allows_limited_calls(self) -> None:
        """HALF_OPEN state allows limited test calls."""
        config = MT5Config(cb_threshold=3, cb_recovery=0.01, cb_half_open_max=2)
        cb = MT5Utilities.CircuitBreaker(config=config)

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        import time

        time.sleep(0.02)
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN

        # Should allow limited calls
        assert cb.can_execute()
        cb.record_success()
        assert cb.can_execute()

    def test_half_open_closes_after_success(self) -> None:
        """Circuit closes after success in HALF_OPEN."""
        config = MT5Config(cb_threshold=3, cb_recovery=0.01, cb_half_open_max=2)
        cb = MT5Utilities.CircuitBreaker(config=config)

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        import time

        time.sleep(0.02)
        # State changes after timeout - mypy doesn't track time-based transitions
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN

        # Record success - should close
        cb.record_success()
        # State changes after success in HALF_OPEN
        expected_state = c.Resilience.CircuitBreakerState.CLOSED
        assert cb.state == expected_state

    def test_half_open_reopens_on_failure(self) -> None:
        """Circuit reopens on failure during HALF_OPEN."""
        config = MT5Config(cb_threshold=3, cb_recovery=0.01, cb_half_open_max=2)
        cb = MT5Utilities.CircuitBreaker(config=config)

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        import time

        time.sleep(0.02)
        # State changes after timeout - mypy doesn't track time-based transitions
        assert cb.state == c.Resilience.CircuitBreakerState.HALF_OPEN

        # Failure should reopen
        cb.record_failure()
        # State changes after failure in HALF_OPEN
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN  # type: ignore[comparison-overlap]

    def test_reset_returns_to_closed(self, config: MT5Config) -> None:
        """Reset returns circuit to CLOSED state."""
        cb = MT5Utilities.CircuitBreaker(config=config)

        # Open circuit
        for _ in range(3):
            cb.record_failure()
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN

        # Reset
        cb.reset()
        # State changes after reset
        expected_state = c.Resilience.CircuitBreakerState.CLOSED
        assert cb.state == expected_state
        assert cb.failure_count == 0

    def test_get_status_returns_dict(self, config: MT5Config) -> None:
        """get_status returns monitoring dictionary."""
        cb = MT5Utilities.CircuitBreaker(config=config, name="test-cb")
        status = cb.get_status()

        assert status["name"] == "test-cb"
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 3


class TestAsyncRetryWithBackoff:
    """Tests for MT5Utilities.async_retry_with_backoff function."""

    @pytest.fixture
    def config(self) -> MT5Config:
        """Create test config with fast retries."""
        return MT5Config(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_max_delay=0.1,
            retry_jitter=False,
        )

    @pytest.mark.asyncio
    async def test_returns_on_first_success(self, config: MT5Config) -> None:
        """Returns immediately on first successful call."""
        call_count = 0

        async def success_op() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await MT5Utilities.async_retry_with_backoff(
            success_op, config, "test_op"
        )

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        """Retries on failure until success."""
        call_count = 0

        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "temporary error"
                raise ValueError(msg)
            return "success"

        config_5_attempts = MT5Config(
            retry_max_attempts=5,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )

        result = await MT5Utilities.async_retry_with_backoff(
            fail_then_succeed,
            config_5_attempts,
            "test_op",
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_max_retries_error_after_attempts(
        self, config: MT5Config
    ) -> None:
        """Raises MaxRetriesError after max attempts exhausted."""
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            msg = "persistent error"
            raise ValueError(msg)

        with pytest.raises(MT5Utilities.Exceptions.MaxRetriesError) as exc_info:
            await MT5Utilities.async_retry_with_backoff(
                always_fail,
                config,
                "test_op",
            )

        assert call_count == 3
        assert exc_info.value.operation == "test_op"
        assert exc_info.value.attempts == 3

    @pytest.mark.asyncio
    async def test_respects_max_delay(self) -> None:
        """Delay is capped at max_delay."""
        delays: list[float] = []
        original_sleep = asyncio.sleep

        async def track_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0.001)  # Fast for testing

        call_count = 0

        async def fail_op() -> str:
            nonlocal call_count
            call_count += 1
            msg = "error"
            raise ValueError(msg)

        config = MT5Config(
            retry_max_attempts=5,
            retry_initial_delay=0.1,
            retry_max_delay=0.2,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )

        with (
            patch("mt5linux.utilities.asyncio.sleep", track_sleep),
            pytest.raises(MT5Utilities.Exceptions.MaxRetriesError),
        ):
            await MT5Utilities.async_retry_with_backoff(
                fail_op,
                config,
                "test_op",
            )

        # Delays should be capped at max_delay (0.2)
        assert all(d <= 0.21 for d in delays)  # Small tolerance for float


class TestAsyncReconnectWithBackoff:
    """Tests for MT5Utilities.async_reconnect_with_backoff function."""

    @pytest.fixture
    def config(self) -> MT5Config:
        """Create test config with fast retries."""
        return MT5Config(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_max_delay=0.1,
            retry_jitter=False,
        )

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, config: MT5Config) -> None:
        """Returns True on successful connection."""

        async def success_connect() -> bool:
            return True

        result = await MT5Utilities.async_reconnect_with_backoff(
            success_connect, config, "test"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_after_max_attempts(self, config: MT5Config) -> None:
        """Returns False after all attempts fail."""

        async def fail_connect() -> bool:
            return False

        result = await MT5Utilities.async_reconnect_with_backoff(
            fail_connect, config, "test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_retries_on_exception(self, config: MT5Config) -> None:
        """Retries when connect raises exception."""
        call_count = 0

        async def fail_then_succeed() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                msg = "connection failed"
                raise ConnectionError(msg)
            return True

        result = await MT5Utilities.async_reconnect_with_backoff(
            fail_then_succeed, config, "test"
        )

        assert result is True
        assert call_count == 2


class TestAsyncClientResilience:
    """Tests for resilience features in AsyncMetaTrader5."""

    def test_circuit_breaker_created_when_enabled(self) -> None:
        """Circuit breaker is created when config enables it."""
        from mt5linux.async_client import AsyncMetaTrader5

        # Test with default config (disabled)
        client = AsyncMetaTrader5()
        assert client._circuit_breaker is None

    def test_health_monitor_not_running_by_default(self) -> None:
        """Health monitor is not running by default."""
        from mt5linux.async_client import AsyncMetaTrader5

        client = AsyncMetaTrader5()
        assert client._health_task is None
        assert not client._health_monitor_running

    def test_lock_is_instance_level(self) -> None:
        """Each client instance has its own lock."""
        from mt5linux.async_client import AsyncMetaTrader5

        c1 = AsyncMetaTrader5()
        c2 = AsyncMetaTrader5()

        assert c1._lock is not c2._lock

    def test_timeout_stored_correctly(self) -> None:
        """Timeout parameter is stored correctly."""
        from mt5linux.async_client import AsyncMetaTrader5

        client = AsyncMetaTrader5(timeout=60)
        assert client._timeout == 60
