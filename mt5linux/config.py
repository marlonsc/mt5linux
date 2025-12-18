"""MT5 configuration using Pydantic Settings.

Automatic environment variable loading with MT5_ prefix.
Single source of truth for all configuration across the project.

Hierarchy Level: 1
- Imports: MT5Constants (Level 0)
- Used by: MT5Models, MT5Utilities, client.py, bridge.py, conftest.py

Configuration Sources (precedence high to low):
1. Environment variables (MT5_*)
2. .env file
3. Defaults defined here

Usage:
    >>> from mt5linux.config import MT5Config
    >>> config = MT5Config()  # loads from env
    >>> print(config.grpc_port)  # 8001 or env override
    >>> delay = config.calculate_retry_delay(attempt=2)
"""

import random

from pydantic_settings import BaseSettings, SettingsConfigDict

from mt5linux.constants import MT5Constants


class MT5Config(BaseSettings):
    """MetaTrader5 configuration with automatic env loading.

    Single source of truth for all MT5 configuration across the project.
    All fields auto-load from environment variables with MT5_ prefix.

    Port Configuration Strategy:
    - grpc_port/vnc_port/health_port: Container INTERNAL ports (8001/3000/8002)
    - docker_*_port: Host-mapped ports for direct Docker access (38812/33000/38002)
    - test_*_port: Isolated ports for pytest (28812/23000/28002)

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

    # =========================================================================
    # NETWORK - Production (Container Internal Ports)
    # =========================================================================
    host: str = "localhost"
    grpc_port: int = 8001  # Container internal gRPC port
    bridge_port: int = 8001  # Alias for grpc_port (legacy)
    vnc_port: int = 3000  # Container internal VNC port
    health_port: int = 8002  # Container internal health port

    # =========================================================================
    # DOCKER - Host-Mapped Ports (for direct Docker access)
    # =========================================================================
    docker_grpc_port: int = 38812  # Host port mapped to container 8001
    docker_vnc_port: int = 33000  # Host port mapped to container 3000
    docker_health_port: int = 38002  # Host port mapped to container 8002

    # =========================================================================
    # TEST ENVIRONMENT - Isolated Ports (avoid conflicts with other projects)
    # =========================================================================
    # Isolated from: production (8001), neptor (18812), mt5docker (48812)
    test_grpc_port: int = 28812  # Isolated test gRPC port
    test_vnc_port: int = 23000  # Isolated test VNC port
    test_health_port: int = 28002  # Isolated test health port
    test_container_name: str = "mt5linux-test"  # Isolated container name
    test_startup_timeout: int = 420  # Container startup timeout (7 min)
    test_grpc_timeout: int = 60  # gRPC health check timeout

    # =========================================================================
    # TIMEOUTS (in seconds)
    # =========================================================================
    timeout_connection: int = 300
    timeout_health_check: int = 60
    startup_health_timeout: float = 30.0  # Health check during startup
    connection_cooldown: float = 0.1  # Cooldown after disconnect (prevent rapid reconnect)

    # =========================================================================
    # RETRY SETTINGS
    # =========================================================================
    retry_max_attempts: int = 3
    retry_initial_delay: float = 0.5
    retry_max_delay: float = 10.0
    retry_exponential_base: float = 2.0
    retry_jitter: bool = True
    retry_min_interval: float = 0.5  # Min backoff interval for startup
    retry_max_interval: float = 5.0  # Max backoff interval for startup

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================
    cb_threshold: int = 5
    cb_recovery: float = 30.0
    cb_half_open_max: int = 3

    # =========================================================================
    # RESILIENCE FEATURE FLAGS (opt-in for backward compatibility)
    # =========================================================================
    enable_auto_reconnect: bool = False
    """Enable automatic reconnection with exponential backoff."""

    enable_health_monitor: bool = False
    """Enable background health monitoring task."""

    enable_circuit_breaker: bool = False
    """Enable circuit breaker pattern for cascading failure prevention."""

    # =========================================================================
    # SERVER (bridge.py)  # noqa: ERA001
    # =========================================================================
    server_host: str = "0.0.0.0"  # Server bind address
    server_port: int = 8001  # Server listen port (aligned with grpc_port)
    server_grace_period: int = 5  # Graceful shutdown timeout
    thread_pool_size: int = 10
    max_restarts: int = 10
    restart_delay_base: float = 1.0
    restart_delay_max: float = 60.0
    restart_delay_multiplier: float = 2.0
    jitter_factor: float = 0.1

    # =========================================================================
    # gRPC PROTOCOL
    # =========================================================================
    grpc_max_message_size: int = 50 * 1024 * 1024  # 50MB
    grpc_keepalive_time_ms: int = 30000  # 30 seconds
    grpc_keepalive_timeout_ms: int = 10000  # 10 seconds

    # =========================================================================
    # ORDER DEFAULTS (from MT5Constants)
    # =========================================================================
    order_filling: int = MT5Constants.Order.OrderFilling.FOK
    order_time: int = MT5Constants.Order.OrderTime.GTC
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
            delay *= 0.5 + random.random()
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
        jitter = delay * self.jitter_factor * (2 * random.random() - 1)
        return max(0, delay + jitter)

    def get_grpc_channel_options(self) -> list[tuple[str, int]]:
        """Get gRPC channel options from configuration.

        Returns:
            List of (option_name, value) tuples for gRPC channel creation.

        """
        return [
            ("grpc.max_send_message_length", self.grpc_max_message_size),
            ("grpc.max_receive_message_length", self.grpc_max_message_size),
            ("grpc.keepalive_time_ms", self.grpc_keepalive_time_ms),
            ("grpc.keepalive_timeout_ms", self.grpc_keepalive_timeout_ms),
        ]
