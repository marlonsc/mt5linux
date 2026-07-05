"""Unit tests for MT5Settings calculation methods.

Covers remaining branches in:
- calculate_backoff_delay (restart backoff with jitter)
- calculate_critical_retry_delay (jitter path)
"""

from __future__ import annotations

from mt5linux.settings import MT5Settings


class TestBackoffCalculations:
    """Cover delay calculation helpers."""

    def test_calculate_backoff_delay_without_jitter(self) -> None:
        """Backoff delay respects base, multiplier and max without jitter."""
        config = MT5Settings(
            restart_delay_base=1.0,
            restart_delay_multiplier=2.0,
            restart_delay_max=10.0,
            jitter_factor=0.0,
        )
        assert config.calculate_backoff_delay(0) == 1.0
        assert config.calculate_backoff_delay(1) == 2.0
        assert config.calculate_backoff_delay(10) == 10.0

    def test_calculate_backoff_delay_with_jitter(self) -> None:
        """Backoff delay with non-zero jitter stays within bounds."""
        config = MT5Settings(
            restart_delay_base=1.0,
            restart_delay_multiplier=2.0,
            restart_delay_max=10.0,
            jitter_factor=0.5,
        )
        delay = config.calculate_backoff_delay(0)
        assert 0.0 <= delay <= 1.5

    def test_calculate_critical_retry_delay_with_jitter(self) -> None:
        """Critical retry delay applies jitter when enabled."""
        config = MT5Settings(
            critical_retry_initial_delay=0.1,
            retry_exponential_base=2.0,
            critical_retry_max_delay=None,
            retry_max_delay=1.0,
            retry_jitter=True,
        )
        delay = config.calculate_critical_retry_delay(0)
        assert delay > 0.0
