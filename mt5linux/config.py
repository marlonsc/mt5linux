"""MT5 configuration using Pydantic Settings.

Automatic environment variable loading with MT5_ prefix.
No helpers, no factories - pure Pydantic 2 BaseSettings.

Hierarchy Level: 1
- Imports: MT5Constants (Level 0)
- Used by: MT5Models, MT5Utilities, client.py, server.py

Usage:
    >>> from mt5linux.config import MT5Config
    >>> config = MT5Config()  # loads from env
    >>> print(config.rpyc_port)  # 18812 or env override
    >>> delay = config.calculate_retry_delay(attempt=2)
"""

import random

from pydantic_settings import BaseSettings, SettingsConfigDict

from mt5linux.constants import MT5Constants


class MT5Config(BaseSettings):
    """MetaTrader5 configuration with automatic env loading.

    All fields auto-load from environment variables with MT5_ prefix.
    Example: MT5_HOST, MT5_RPYC_PORT, MT5_TIMEOUT_CONNECTION

    Usage:
        config = MT5Config()  # loads from env
        config = MT5Config(host="custom")  # override
    """

    model_config = SettingsConfigDict(
        env_prefix="MT5_",
        frozen=True,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Network
    host: str = "localhost"
    rpyc_port: int = 18812
    bridge_port: int = 8001
    docker_mapped_port: int = 38812
    vnc_port: int = 3000
    health_port: int = 8002

    # Timeout settings (in seconds)
    timeout_connection: int = 300
    timeout_health_check: int = 60
    timeout_sync_request: int = 300

    # Retry settings
    retry_max_attempts: int = 3
    retry_initial_delay: float = 0.5
    retry_max_delay: float = 10.0
    retry_exponential_base: float = 2.0
    retry_jitter: bool = True

    # Circuit Breaker
    cb_threshold: int = 5
    cb_recovery: float = 30.0
    cb_half_open_max: int = 3

    # Server
    thread_pool_size: int = 10
    max_restarts: int = 10
    restart_delay_base: float = 1.0
    restart_delay_max: float = 60.0
    restart_delay_multiplier: float = 2.0
    jitter_factor: float = 0.1

    # RPyC Protocol
    rpyc_max_io_chunk: int = 65355 * 10
    rpyc_compression_level: int = 0

    # Order defaults (from MT5Constants)
    order_filling: int = MT5Constants.OrderFilling.FOK
    order_time: int = MT5Constants.OrderTime.GTC
    order_deviation: int = 20
    order_magic: int = 0

    # =========================================================================
    # CALCULATION METHODS
    # =========================================================================

    def calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with optional jitter.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds before next retry.

        """
        delay = min(
            self.retry_initial_delay * (self.retry_exponential_base**attempt),
            self.retry_max_delay,
        )
        if self.retry_jitter:
            # Add 0-100% jitter (S311: random is fine for jitter - not cryptographic)
            delay *= 0.5 + random.random()  # noqa: S311
        return delay

    def calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate server restart backoff delay with jitter.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds with jitter applied.

        """
        delay = self.restart_delay_base * (self.restart_delay_multiplier**attempt)
        delay = min(delay, self.restart_delay_max)
        # S311: random is fine for jitter - not cryptographic
        jitter = delay * self.jitter_factor * (2 * random.random() - 1)  # noqa: S311
        return max(0, delay + jitter)
