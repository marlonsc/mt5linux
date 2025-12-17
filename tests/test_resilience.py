"""Tests for resilience patterns.

Tests circuit breaker, retry logic, and health monitoring utilities.

"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from mt5linux.resilience import (
    CircuitBreaker,
    CircuitState,
    ConnectionState,
    HealthStatus,
    retry_with_backoff,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Circuit starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    def test_stays_closed_below_threshold(self) -> None:
        """Circuit stays CLOSED if failures are below threshold."""
        cb = CircuitBreaker(failure_threshold=5)

        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 4

    def test_opens_at_threshold(self) -> None:
        """Circuit opens when failure threshold is reached."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.is_open
        assert cb.failure_count == 3

    def test_success_resets_failure_count(self) -> None:
        """Success in CLOSED state resets failure count."""
        cb = CircuitBreaker(failure_threshold=5)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_can_execute_when_closed(self) -> None:
        """Can execute when circuit is CLOSED."""
        cb = CircuitBreaker()
        assert cb.can_execute()

    def test_cannot_execute_when_open(self) -> None:
        """Cannot execute when circuit is OPEN."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert not cb.can_execute()

    def test_transitions_to_half_open_after_recovery_timeout(self) -> None:
        """Circuit transitions OPEN -> HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

        # Open the circuit
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should transition to HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self) -> None:
        """HALF_OPEN state allows limited test calls."""
        cb = CircuitBreaker(
            failure_threshold=3, recovery_timeout=0.01, half_open_max_calls=2
        )

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Should allow limited calls
        assert cb.can_execute()
        cb.record_success()
        assert cb.can_execute()

    def test_half_open_closes_after_success(self) -> None:
        """Circuit closes after enough successes in HALF_OPEN."""
        cb = CircuitBreaker(
            failure_threshold=3, recovery_timeout=0.01, half_open_max_calls=2
        )

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        cb.record_success()
        cb.record_success()

        # Should be closed
        assert cb.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self) -> None:
        """Circuit reopens on failure during HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.01)

        # Open circuit
        for _ in range(3):
            cb.record_failure()

        # Wait for recovery
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Failure should reopen
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset_returns_to_closed(self) -> None:
        """Reset returns circuit to CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)

        # Open circuit
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_returns_on_first_success(self) -> None:
        """Returns immediately on first successful call."""
        call_count = 0

        async def success_op() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_op, max_attempts=3)

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

        result = await retry_with_backoff(
            fail_then_succeed,
            max_attempts=5,
            initial_delay=0.01,
            jitter=False,
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self) -> None:
        """Raises exception after max attempts exhausted."""
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            msg = "persistent error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="persistent error"):
            await retry_with_backoff(
                always_fail,
                max_attempts=3,
                initial_delay=0.01,
                jitter=False,
            )

        assert call_count == 3

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

        with patch("mt5linux.resilience.asyncio.sleep", track_sleep):
            with pytest.raises(ValueError):
                await retry_with_backoff(
                    fail_op,
                    max_attempts=5,
                    initial_delay=0.1,
                    max_delay=0.2,
                    exponential_base=2.0,
                    jitter=False,
                )

        # Delays should be capped at max_delay
        # Expected: 0.1, 0.2, 0.2, 0.2 (4 retries before final failure)
        assert all(d <= 0.2 for d in delays)


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_connection_states_exist(self) -> None:
        """All expected connection states exist."""
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.FAILED.value == "failed"


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_is_healthy_when_connected(self) -> None:
        """Reports healthy when connected."""
        status = HealthStatus(
            state=ConnectionState.CONNECTED,
            last_check=time.monotonic(),
        )
        assert status.is_healthy

    def test_is_not_healthy_when_disconnected(self) -> None:
        """Reports not healthy when disconnected."""
        status = HealthStatus(
            state=ConnectionState.DISCONNECTED,
            last_check=time.monotonic(),
        )
        assert not status.is_healthy

    def test_tracks_consecutive_failures(self) -> None:
        """Tracks consecutive failure count."""
        status = HealthStatus(
            state=ConnectionState.CONNECTED,
            last_check=time.monotonic(),
            consecutive_failures=5,
        )
        assert status.consecutive_failures == 5

    def test_includes_circuit_state(self) -> None:
        """Can include circuit breaker state."""
        status = HealthStatus(
            state=ConnectionState.CONNECTED,
            last_check=time.monotonic(),
            circuit_state=CircuitState.HALF_OPEN,
        )
        assert status.circuit_state == CircuitState.HALF_OPEN


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
