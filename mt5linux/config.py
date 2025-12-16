"""Centralized configuration for mt5linux.

All runtime defaults are defined here. Environment variables override defaults.

Usage:
    >>> from mt5linux.config import MT5Config
    >>> print(MT5Config.Defaults.PORT_RPYC)  # 18812
    >>> config = MT5Config.get_config()
    >>> print(config.PORT_RPYC)  # 18812 or env override
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class MT5Config:
    """Centralized configuration for mt5linux.

    All configuration organized in nested classes:
    - Defaults: Default configuration values (frozen dataclass)
    - get_config(): Factory to get config with env overrides
    """

    @dataclass(frozen=True)
    class Defaults:
        """Runtime defaults for mt5linux.

        All configuration values with their defaults. Use environment variables
        to override at runtime.

        Port Guide:
            PORT_RPYC (18812): Default for Linux native client connections
            PORT_BRIDGE (8001): Wine bridge inside Docker container
            PORT_DOCKER_MAPPED (38812): Default host port when using Docker
        """

        # Network
        HOST: str = "localhost"
        PORT_RPYC: int = 18812
        PORT_BRIDGE: int = 8001
        PORT_DOCKER_MAPPED: int = 38812
        PORT_VNC: int = 3000
        PORT_HEALTH: int = 8002

        # Timeouts in seconds
        TIMEOUT_CONNECTION: int = 300
        TIMEOUT_HEALTH_CHECK: int = 60
        TIMEOUT_SYNC_REQUEST: int = 300

        # Retry settings
        RETRY_MAX_ATTEMPTS: int = 3
        RETRY_INITIAL_DELAY: float = 0.5
        RETRY_MAX_DELAY: float = 10.0
        RETRY_EXPONENTIAL_BASE: float = 2.0
        RETRY_JITTER: bool = True

        # Circuit Breaker settings
        CIRCUIT_BREAKER_THRESHOLD: int = 5
        CIRCUIT_BREAKER_RECOVERY: float = 30.0
        CIRCUIT_BREAKER_HALF_OPEN_MAX: int = 3

        # Server settings
        THREAD_POOL_SIZE: int = 10
        MAX_RESTARTS: int = 10
        RESTART_DELAY_BASE: float = 1.0
        RESTART_DELAY_MAX: float = 60.0
        RESTART_DELAY_MULTIPLIER: float = 2.0
        JITTER_FACTOR: float = 0.1

        # RPyC Protocol settings
        RPYC_MAX_IO_CHUNK: int = 65355 * 10
        RPYC_COMPRESSION_LEVEL: int = 0

    @staticmethod
    def _get_int(key: str, default: int) -> int:
        """Get integer from environment variable."""
        val = os.getenv(key)
        return int(val) if val else default

    @staticmethod
    def _get_float(key: str, default: float) -> float:
        """Get float from environment variable."""
        val = os.getenv(key)
        return float(val) if val else default

    @staticmethod
    def _get_bool(key: str, default: bool) -> bool:
        """Get boolean from environment variable."""
        val = os.getenv(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    @staticmethod
    def get_config() -> MT5Config.Defaults:
        """Get configuration with environment variable overrides."""
        d = MT5Config.Defaults
        g_int = MT5Config._get_int
        g_float = MT5Config._get_float
        g_bool = MT5Config._get_bool
        return MT5Config.Defaults(
            HOST=os.getenv("MT5_HOST", d.HOST),
            PORT_RPYC=g_int("MT5_RPYC_PORT", d.PORT_RPYC),
            PORT_BRIDGE=g_int("MT5_BRIDGE_PORT", d.PORT_BRIDGE),
            PORT_DOCKER_MAPPED=g_int("MT5_DOCKER_PORT", d.PORT_DOCKER_MAPPED),
            PORT_VNC=g_int("MT5_VNC_PORT", d.PORT_VNC),
            PORT_HEALTH=g_int("MT5_HEALTH_PORT", d.PORT_HEALTH),
            TIMEOUT_CONNECTION=g_int(
                "MT5_TIMEOUT_CONNECTION", d.TIMEOUT_CONNECTION
            ),
            TIMEOUT_HEALTH_CHECK=g_int(
                "MT5_TIMEOUT_HEALTH_CHECK", d.TIMEOUT_HEALTH_CHECK
            ),
            TIMEOUT_SYNC_REQUEST=g_int(
                "MT5_TIMEOUT_SYNC_REQUEST", d.TIMEOUT_SYNC_REQUEST
            ),
            RETRY_MAX_ATTEMPTS=g_int(
                "MT5_RETRY_MAX_ATTEMPTS", d.RETRY_MAX_ATTEMPTS
            ),
            RETRY_INITIAL_DELAY=g_float(
                "MT5_RETRY_INITIAL_DELAY", d.RETRY_INITIAL_DELAY
            ),
            RETRY_MAX_DELAY=g_float("MT5_RETRY_MAX_DELAY", d.RETRY_MAX_DELAY),
            RETRY_EXPONENTIAL_BASE=g_float(
                "MT5_RETRY_EXP_BASE", d.RETRY_EXPONENTIAL_BASE
            ),
            RETRY_JITTER=g_bool("MT5_RETRY_JITTER", d.RETRY_JITTER),
            CIRCUIT_BREAKER_THRESHOLD=g_int(
                "MT5_CB_THRESHOLD", d.CIRCUIT_BREAKER_THRESHOLD
            ),
            CIRCUIT_BREAKER_RECOVERY=g_float(
                "MT5_CB_RECOVERY", d.CIRCUIT_BREAKER_RECOVERY
            ),
            CIRCUIT_BREAKER_HALF_OPEN_MAX=g_int(
                "MT5_CB_HALF_OPEN", d.CIRCUIT_BREAKER_HALF_OPEN_MAX
            ),
            THREAD_POOL_SIZE=g_int("MT5_THREAD_POOL_SIZE", d.THREAD_POOL_SIZE),
            MAX_RESTARTS=g_int("MT5_MAX_RESTARTS", d.MAX_RESTARTS),
            RESTART_DELAY_BASE=g_float(
                "MT5_RESTART_DELAY_BASE", d.RESTART_DELAY_BASE
            ),
            RESTART_DELAY_MAX=g_float(
                "MT5_RESTART_DELAY_MAX", d.RESTART_DELAY_MAX
            ),
            RESTART_DELAY_MULTIPLIER=g_float(
                "MT5_RESTART_MULT", d.RESTART_DELAY_MULTIPLIER
            ),
            JITTER_FACTOR=g_float("MT5_JITTER_FACTOR", d.JITTER_FACTOR),
            RPYC_MAX_IO_CHUNK=g_int(
                "MT5_RPYC_MAX_IO_CHUNK", d.RPYC_MAX_IO_CHUNK
            ),
            RPYC_COMPRESSION_LEVEL=g_int(
                "MT5_RPYC_COMPRESSION", d.RPYC_COMPRESSION_LEVEL
            ),
        )


# Backward compatibility aliases (to be removed in next major version)
Defaults = MT5Config.Defaults
config = MT5Config.get_config()
