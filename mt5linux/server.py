"""Modern RPyC server for mt5linux.

Production-grade RPyC server with:
- Modern MT5Service (replaces deprecated SlaveService)
- ThreadPoolServer for concurrent request handling
- Circuit breaker for fault tolerance
- Rate limiting (token bucket)
- Health monitoring
- Graceful shutdown handling
- NO STUBS - fails if MT5 unavailable

Compatible with rpyc 6.x.

Usage:
    # Direct mode (Linux):
    python -m mt5linux.server --host 0.0.0.0 --port 18812

    # Wine mode (for mt5docker):
    python -m mt5linux.server --wine wine --python python.exe -p 8001

    # Also supports positional args for Wine (mt5docker compatibility):
    wine python.exe server.py 0.0.0.0 8001
"""

from __future__ import annotations

import argparse
import os
import random
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from pathlib import Path
from types import FrameType
from typing import Any

import rpyc
import structlog
from rpyc.utils.server import ThreadedServer, ThreadPoolServer

# Configure structlog for clean output
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger("mt5linux.server")


# =============================================================================
# Environment Detection
# =============================================================================


class Environment(Enum):
    """Runtime environment type."""

    LINUX = auto()
    WINE = auto()


def detect_environment() -> Environment:
    """Auto-detect runtime environment."""
    if sys.platform == "win32":
        # Wine reports as win32
        wine_indicators = ["WINEPREFIX", "WINELOADER", "WINEDLLPATH"]
        if any(os.environ.get(var) for var in wine_indicators):
            return Environment.WINE
        return Environment.WINE  # Assume Wine in win32 context
    return Environment.LINUX


def is_mt5_available() -> bool:
    """Check if MetaTrader5 module is importable."""
    try:
        import MetaTrader5

    except ImportError:
        return False
    else:
        return True


class MT5NotAvailableError(Exception):
    """Raised when MetaTrader5 module is not available. NO STUBS."""


# =============================================================================
# Resilience Patterns
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    excluded_exceptions: tuple[type[Exception], ...] = ()


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._last_failure_time
                and time.time() - self._last_failure_time >= self.config.timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
            return self._state

    def _record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN or (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.config.failure_threshold
            ):
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.state == CircuitState.OPEN:
                msg = f"Circuit breaker open, call to {func.__name__} blocked"
                raise CircuitBreakerOpenError(msg)
            try:
                result = func(*args, **kwargs)
            except self.config.excluded_exceptions:
                raise
            except Exception:
                self._record_failure()
                raise
            else:
                self._record_success()
                return result

        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""


def exponential_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter_factor: float = 0.1,
) -> float:
    """Calculate delay with exponential backoff and jitter."""
    delay = base_delay * (multiplier**attempt)
    delay = min(delay, max_delay)
    # S311: random is fine for jitter - not cryptographic
    jitter = delay * jitter_factor * (2 * random.random() - 1)  # noqa: S311
    return max(0.0, delay + jitter)


# =============================================================================
# Rate Limiter
# =============================================================================


class TokenBucketRateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_update = now

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


# =============================================================================
# Health Monitoring
# =============================================================================


@dataclass
class HealthStatus:
    """Server health status."""

    healthy: bool
    uptime_seconds: float
    connections_total: int
    connections_active: int
    requests_total: int
    requests_failed: int
    last_error: str | None = None
    environment: str = ""
    mt5_available: bool = False
    circuit_state: str = "closed"


class HealthMonitor:
    """Health monitoring for the server."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._connections_total = 0
        self._connections_active = 0
        self._requests_total = 0
        self._requests_failed = 0
        self._last_error: str | None = None
        self._lock = threading.Lock()
        self._environment = detect_environment()

    def record_connection(self) -> None:
        with self._lock:
            self._connections_total += 1
            self._connections_active += 1

    def record_disconnection(self) -> None:
        with self._lock:
            self._connections_active = max(0, self._connections_active - 1)

    def record_request(self, success: bool = True) -> None:
        with self._lock:
            self._requests_total += 1
            if not success:
                self._requests_failed += 1

    def record_error(self, error: str) -> None:
        with self._lock:
            self._last_error = error
            self._requests_failed += 1

    def clear_error(self) -> None:
        with self._lock:
            self._last_error = None

    def get_status(self, circuit_state: str = "closed") -> HealthStatus:
        with self._lock:
            return HealthStatus(
                healthy=self._last_error is None,
                uptime_seconds=time.time() - self._start_time,
                connections_total=self._connections_total,
                connections_active=self._connections_active,
                requests_total=self._requests_total,
                requests_failed=self._requests_failed,
                last_error=self._last_error,
                environment=self._environment.name,
                mt5_available=is_mt5_available(),
                circuit_state=circuit_state,
            )


# Global instances
_health_monitor = HealthMonitor()
_mt5_circuit_breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=5))


# =============================================================================
# Type Validation Helpers - Convert RPyC's Any to Concrete Types
# =============================================================================

# Constants for tuple length validation
_VERSION_TUPLE_LEN = 3  # (version, build, version_string)
_ERROR_TUPLE_LEN = 2  # (error_code, error_description)


def _validate_bool(value: object) -> bool:
    """Validate and convert Any to bool.

    RPyC returns Any from remote calls. This validates the actual type
    and converts to bool, ensuring type safety without type: ignore.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    msg = f"Expected bool, got {type(value).__name__}"
    raise TypeError(msg)


def _validate_int(value: object) -> int:
    """Validate and convert Any to int."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"Expected int, got {type(value).__name__}"
    raise TypeError(msg)


def _validate_int_optional(value: object) -> int | None:
    """Validate and convert Any to int | None."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"Expected int | None, got {type(value).__name__}"
    raise TypeError(msg)


def _validate_float_optional(value: object) -> float | None:
    """Validate and convert Any to float | None."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    msg = f"Expected float | None, got {type(value).__name__}"
    raise TypeError(msg)


def _validate_version(value: object) -> tuple[int, int, str] | None:
    """Validate and convert Any to version tuple."""
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != _VERSION_TUPLE_LEN:
        msg = f"Expected tuple[int, int, str] | None, got {type(value).__name__}"
        raise TypeError(msg)
    try:
        return (int(value[0]), int(value[1]), str(value[2]))
    except (ValueError, IndexError, TypeError) as e:
        msg = f"Invalid version tuple: {e}"
        raise TypeError(msg) from e


def _validate_last_error(value: object) -> tuple[int, str]:
    """Validate and convert Any to last_error tuple."""
    if not isinstance(value, tuple) or len(value) != _ERROR_TUPLE_LEN:
        msg = f"Expected tuple[int, str], got {type(value).__name__}"
        raise TypeError(msg)
    try:
        return (int(value[0]), str(value[1]))
    except (ValueError, IndexError, TypeError) as e:
        msg = f"Invalid error tuple: {e}"
        raise TypeError(msg) from e


def _validate_dict(value: object) -> dict[str, object]:
    """Validate and convert Any to dict."""
    if isinstance(value, dict):
        return value
    msg = f"Expected dict, got {type(value).__name__}"
    raise TypeError(msg)


# =============================================================================
# MT5Service - Modern RPyC Service (NO STUBS)
# =============================================================================


class MT5Service(rpyc.Service):
    """Modern RPyC service for MetaTrader5 access.

    Replaces deprecated SlaveService with explicit method exposure.
    NO STUBS - fails if MT5 module is unavailable.

    rpyc.Service has no type stubs in rpyc library. This is unavoidable
    and doesn't affect our implementation's type safety.
    """

    # Module is dynamically imported - use Any since it's a third-party module
    _mt5_module: Any = None
    _mt5_lock = threading.RLock()
    _rate_limiter = TokenBucketRateLimiter(rate=100, capacity=200)

    def on_connect(self, _conn: rpyc.Connection) -> None:
        """Initialize MT5 module on connection."""
        _health_monitor.record_connection()

        with MT5Service._mt5_lock:
            if MT5Service._mt5_module is None:
                try:
                    import MetaTrader5 as MT5

                    MT5Service._mt5_module = MT5
                    log.info("mt5_module_loaded")
                except ImportError as e:
                    log.exception("mt5_module_not_available", error=str(e))
                    msg = "MetaTrader5 module not available. NO STUBS."
                    raise MT5NotAvailableError(msg) from e

    def on_disconnect(self, _conn: rpyc.Connection) -> None:
        _health_monitor.record_disconnection()
        log.debug("client_disconnected")

    def _call_mt5(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call MT5 function with rate limiting and circuit breaker."""
        if not MT5Service._rate_limiter.acquire():
            time.sleep(0.01)  # Brief wait if rate limited

        @_mt5_circuit_breaker
        def _call() -> Any:
            with MT5Service._mt5_lock:
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    _health_monitor.record_error(str(e))
                    raise
                else:
                    _health_monitor.record_request(success=True)
                    return result

        return _call()

    # =========================================================================
    # Core Access
    # =========================================================================

    def exposed_get_mt5(self) -> Any:
        """Return MT5 module reference."""
        if MT5Service._mt5_module is None:
            msg = "MT5 module not loaded"
            raise MT5NotAvailableError(msg)
        return MT5Service._mt5_module

    def exposed_health_check(self) -> dict[str, Any]:
        """Get server health status."""
        status = _health_monitor.get_status(_mt5_circuit_breaker.state.value)
        return {
            "healthy": status.healthy,
            "uptime_seconds": status.uptime_seconds,
            "connections_total": status.connections_total,
            "connections_active": status.connections_active,
            "requests_total": status.requests_total,
            "requests_failed": status.requests_failed,
            "last_error": status.last_error,
            "environment": status.environment,
            "mt5_available": status.mt5_available,
            "circuit_state": status.circuit_state,
        }

    def exposed_reset_circuit_breaker(self) -> bool:
        _mt5_circuit_breaker.reset()
        _health_monitor.clear_error()
        return True

    # =========================================================================
    # Terminal Operations
    # =========================================================================

    def exposed_initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        result = self._call_mt5(
            MT5Service._mt5_module.initialize,
            path,
            login,
            password,
            server,
            timeout,
            portable,
        )
        return _validate_bool(result)

    def exposed_login(
        self, login: int, password: str, server: str, timeout: int = 60000
    ) -> bool:
        result = self._call_mt5(
            MT5Service._mt5_module.login, login, password, server, timeout
        )
        return _validate_bool(result)

    def exposed_shutdown(self) -> None:
        self._call_mt5(MT5Service._mt5_module.shutdown)

    def exposed_version(self) -> tuple[int, int, str] | None:
        result = self._call_mt5(MT5Service._mt5_module.version)
        return _validate_version(result)

    def exposed_last_error(self) -> tuple[int, str]:
        with MT5Service._mt5_lock:
            result = MT5Service._mt5_module.last_error()
            return _validate_last_error(result)

    def exposed_terminal_info(self) -> Any:
        return self._call_mt5(MT5Service._mt5_module.terminal_info)

    def exposed_account_info(self) -> Any:
        return self._call_mt5(MT5Service._mt5_module.account_info)

    # =========================================================================
    # Symbol Operations
    # =========================================================================

    def exposed_symbols_total(self) -> int:
        result = self._call_mt5(MT5Service._mt5_module.symbols_total)
        return _validate_int(result)

    def exposed_symbols_get(self, group: str | None = None) -> Any:
        if group:
            return self._call_mt5(MT5Service._mt5_module.symbols_get, group=group)
        return self._call_mt5(MT5Service._mt5_module.symbols_get)

    def exposed_symbol_info(self, symbol: str) -> Any:
        return self._call_mt5(MT5Service._mt5_module.symbol_info, symbol)

    def exposed_symbol_info_tick(self, symbol: str) -> Any:
        return self._call_mt5(MT5Service._mt5_module.symbol_info_tick, symbol)

    def exposed_symbol_select(self, symbol: str, enable: bool = True) -> bool:
        result = self._call_mt5(MT5Service._mt5_module.symbol_select, symbol, enable)
        return _validate_bool(result)

    # =========================================================================
    # Market Data Operations
    # =========================================================================

    def exposed_copy_rates_from(
        self, symbol: str, timeframe: int, date_from: Any, count: int
    ) -> Any:
        return self._call_mt5(
            MT5Service._mt5_module.copy_rates_from, symbol, timeframe, date_from, count
        )

    def exposed_copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        return self._call_mt5(
            MT5Service._mt5_module.copy_rates_from_pos,
            symbol,
            timeframe,
            start_pos,
            count,
        )

    def exposed_copy_rates_range(
        self, symbol: str, timeframe: int, date_from: Any, date_to: Any
    ) -> Any:
        return self._call_mt5(
            MT5Service._mt5_module.copy_rates_range,
            symbol,
            timeframe,
            date_from,
            date_to,
        )

    def exposed_copy_ticks_from(
        self, symbol: str, date_from: Any, count: int, flags: int
    ) -> Any:
        return self._call_mt5(
            MT5Service._mt5_module.copy_ticks_from, symbol, date_from, count, flags
        )

    def exposed_copy_ticks_range(
        self, symbol: str, date_from: Any, date_to: Any, flags: int
    ) -> Any:
        return self._call_mt5(
            MT5Service._mt5_module.copy_ticks_range, symbol, date_from, date_to, flags
        )

    # =========================================================================
    # Trading Operations
    # =========================================================================

    def exposed_order_calc_margin(
        self, action: int, symbol: str, volume: float, price: float
    ) -> float | None:
        result = self._call_mt5(
            MT5Service._mt5_module.order_calc_margin, action, symbol, volume, price
        )
        return _validate_float_optional(result)

    def exposed_order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        result = self._call_mt5(
            MT5Service._mt5_module.order_calc_profit,
            action,
            symbol,
            volume,
            price_open,
            price_close,
        )
        return _validate_float_optional(result)

    def exposed_order_check(self, request: dict[str, Any]) -> Any:
        return self._call_mt5(MT5Service._mt5_module.order_check, request)

    def exposed_order_send(self, request: dict[str, Any]) -> Any:
        return self._call_mt5(MT5Service._mt5_module.order_send, request)

    # =========================================================================
    # Position Operations
    # =========================================================================

    def exposed_positions_total(self) -> int:
        result = self._call_mt5(MT5Service._mt5_module.positions_total)
        return _validate_int(result)

    def exposed_positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return self._call_mt5(MT5Service._mt5_module.positions_get, **kwargs)
        return self._call_mt5(MT5Service._mt5_module.positions_get)

    # =========================================================================
    # Order Operations
    # =========================================================================

    def exposed_orders_total(self) -> int:
        result = self._call_mt5(MT5Service._mt5_module.orders_total)
        return _validate_int(result)

    def exposed_orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return self._call_mt5(MT5Service._mt5_module.orders_get, **kwargs)
        return self._call_mt5(MT5Service._mt5_module.orders_get)

    # =========================================================================
    # History Operations
    # =========================================================================

    def exposed_history_orders_total(self, date_from: Any, date_to: Any) -> int | None:
        result = self._call_mt5(
            MT5Service._mt5_module.history_orders_total, date_from, date_to
        )
        return _validate_int_optional(result)

    def exposed_history_orders_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return self._call_mt5(MT5Service._mt5_module.history_orders_get, **kwargs)
        return self._call_mt5(MT5Service._mt5_module.history_orders_get)

    def exposed_history_deals_total(self, date_from: Any, date_to: Any) -> int | None:
        result = self._call_mt5(
            MT5Service._mt5_module.history_deals_total, date_from, date_to
        )
        return _validate_int_optional(result)

    def exposed_history_deals_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return self._call_mt5(MT5Service._mt5_module.history_deals_get, **kwargs)
        return self._call_mt5(MT5Service._mt5_module.history_deals_get)


# =============================================================================
# Server Configuration
# =============================================================================


class ServerMode(Enum):
    """Server execution mode."""

    DIRECT = "direct"  # Run directly (Linux)
    WINE = "wine"  # Run via Wine subprocess


class ServerState(Enum):
    """Server lifecycle state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "0.0.0.0"  # noqa: S104 - Intentional binding to all interfaces
    port: int = 18812
    mode: ServerMode = ServerMode.DIRECT

    # Wine mode settings
    wine_cmd: str = "wine"
    python_exe: str = "python.exe"
    # S108: /tmp is intentional for server scripts (cross-platform temp location)
    server_dir: Path = field(default_factory=lambda: Path("/tmp/mt5linux"))  # noqa: S108

    # Threading settings
    use_thread_pool: bool = True
    thread_pool_size: int = 10

    # Resilience settings
    max_restarts: int = 10
    restart_delay_base: float = 1.0
    restart_delay_max: float = 60.0
    restart_delay_multiplier: float = 2.0
    jitter_factor: float = 0.1

    # RPyC protocol settings
    sync_request_timeout: int = 300
    allow_pickle: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.server_dir, str):
            self.server_dir = Path(self.server_dir)

    def get_protocol_config(self) -> dict[str, Any]:
        return {
            "allow_public_attrs": True,
            "allow_pickle": self.allow_pickle,
            "sync_request_timeout": self.sync_request_timeout,
        }


# Modern RPyC server script for Wine mode (uses MT5Service)
RPYC_SERVER_SCRIPT = '''\
#!/usr/bin/env python
"""Modern RPyC server with MT5Service (NO STUBS).

Generated by mt5linux.server.
Runs inside Wine with Windows Python + MetaTrader5 module.
"""
import sys
import signal
import threading
import time
from typing import Any

import rpyc
from rpyc.utils.server import ThreadPoolServer

# Global server reference
_server = None


class MT5Service(rpyc.Service):
    """Modern RPyC service for MT5. NO STUBS."""

    _mt5_module = None
    _mt5_lock = threading.RLock()

    def on_connect(self, conn):
        with MT5Service._mt5_lock:
            if MT5Service._mt5_module is None:
                import MetaTrader5 as MT5
                MT5Service._mt5_module = MT5
                print("[mt5linux] MT5 module loaded")

    def on_disconnect(self, conn):
        pass

    def exposed_get_mt5(self):
        return MT5Service._mt5_module

    def exposed_health_check(self):
        return {"healthy": True, "mt5_available": True}

    def exposed_initialize(self, path=None, login=None, password=None,
                          server=None, timeout=None, portable=False):
        return MT5Service._mt5_module.initialize(
            path, login, password, server, timeout, portable
        )

    def exposed_login(self, login, password, server, timeout=60000):
        return MT5Service._mt5_module.login(login, password, server, timeout)

    def exposed_shutdown(self):
        return MT5Service._mt5_module.shutdown()

    def exposed_version(self):
        return MT5Service._mt5_module.version()

    def exposed_last_error(self):
        return MT5Service._mt5_module.last_error()

    def exposed_terminal_info(self):
        return MT5Service._mt5_module.terminal_info()

    def exposed_account_info(self):
        return MT5Service._mt5_module.account_info()

    def exposed_symbols_total(self):
        return MT5Service._mt5_module.symbols_total()

    def exposed_symbols_get(self, group=None):
        if group:
            return MT5Service._mt5_module.symbols_get(group=group)
        return MT5Service._mt5_module.symbols_get()

    def exposed_symbol_info(self, symbol):
        return MT5Service._mt5_module.symbol_info(symbol)

    def exposed_symbol_info_tick(self, symbol):
        return MT5Service._mt5_module.symbol_info_tick(symbol)

    def exposed_symbol_select(self, symbol, enable=True):
        return MT5Service._mt5_module.symbol_select(symbol, enable)

    def exposed_copy_rates_from(self, symbol, timeframe, date_from, count):
        return MT5Service._mt5_module.copy_rates_from(
            symbol, timeframe, date_from, count
        )

    def exposed_copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        return MT5Service._mt5_module.copy_rates_from_pos(
            symbol, timeframe, start_pos, count
        )

    def exposed_copy_rates_range(self, symbol, timeframe, date_from, date_to):
        return MT5Service._mt5_module.copy_rates_range(
            symbol, timeframe, date_from, date_to
        )

    def exposed_copy_ticks_from(self, symbol, date_from, count, flags):
        return MT5Service._mt5_module.copy_ticks_from(
            symbol, date_from, count, flags
        )

    def exposed_copy_ticks_range(self, symbol, date_from, date_to, flags):
        return MT5Service._mt5_module.copy_ticks_range(
            symbol, date_from, date_to, flags
        )

    def exposed_order_calc_margin(self, action, symbol, volume, price):
        return MT5Service._mt5_module.order_calc_margin(
            action, symbol, volume, price
        )

    def exposed_order_calc_profit(
        self, action, symbol, volume, price_open, price_close
    ):
        return MT5Service._mt5_module.order_calc_profit(
            action, symbol, volume, price_open, price_close
        )

    def exposed_order_check(self, request):
        return MT5Service._mt5_module.order_check(request)

    def exposed_order_send(self, request):
        return MT5Service._mt5_module.order_send(request)

    def exposed_positions_total(self):
        return MT5Service._mt5_module.positions_total()

    def exposed_positions_get(self, symbol=None, group=None, ticket=None):
        kwargs = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return MT5Service._mt5_module.positions_get(**kwargs)
        return MT5Service._mt5_module.positions_get()

    def exposed_orders_total(self):
        return MT5Service._mt5_module.orders_total()

    def exposed_orders_get(self, symbol=None, group=None, ticket=None):
        kwargs = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            return MT5Service._mt5_module.orders_get(**kwargs)
        return MT5Service._mt5_module.orders_get()

    def exposed_history_orders_total(self, date_from, date_to):
        return MT5Service._mt5_module.history_orders_total(date_from, date_to)

    def exposed_history_orders_get(self, date_from=None, date_to=None,
                                   group=None, ticket=None, position=None):
        kwargs = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return MT5Service._mt5_module.history_orders_get(**kwargs)
        return MT5Service._mt5_module.history_orders_get()

    def exposed_history_deals_total(self, date_from, date_to):
        return MT5Service._mt5_module.history_deals_total(date_from, date_to)

    def exposed_history_deals_get(self, date_from=None, date_to=None,
                                  group=None, ticket=None, position=None):
        kwargs = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            return MT5Service._mt5_module.history_deals_get(**kwargs)
        return MT5Service._mt5_module.history_deals_get()


def graceful_shutdown(signum, frame):
    sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    print(f"[mt5linux] Received {sig_name}, shutting down...")
    if _server is not None:
        _server.close()
    sys.exit(0)


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 18812

    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    print(f"[mt5linux] Starting MT5Service on {host}:{port}")
    print("[mt5linux] Using modern rpyc.Service (NO SlaveService, NO STUBS)")

    _server = ThreadPoolServer(
        MT5Service,
        hostname=host,
        port=port,
        reuse_addr=True,
        nbThreads=10,
        protocol_config={"allow_public_attrs": True, "sync_request_timeout": 300},
    )

    try:
        _server.start()
    except KeyboardInterrupt:
        print("[mt5linux] Server interrupted")
    except Exception as e:
        print(f"[mt5linux] Server error: {e}")
        sys.exit(1)
    finally:
        if _server is not None:
            _server.close()
        print("[mt5linux] Server stopped")
'''


# =============================================================================
# Server Class
# =============================================================================


class Server:
    """Production-grade RPyC server with automatic recovery."""

    def __init__(self, config: ServerConfig | None = None) -> None:
        self.config = config or ServerConfig()
        self._state = ServerState.STOPPED
        self._restart_count = 0
        self._shutdown_event = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._server: ThreadedServer | ThreadPoolServer | None = None
        self._server_thread: threading.Thread | None = None
        self._log = log.bind(
            host=self.config.host,
            port=self.config.port,
            mode=self.config.mode.value,
        )

    @property
    def state(self) -> ServerState:
        return self._state

    @property
    def restart_count(self) -> int:
        return self._restart_count

    def _set_state(self, state: ServerState) -> None:
        old_state = self._state
        self._state = state
        self._log.debug(
            "state_changed", old_state=old_state.value, new_state=state.value
        )

    def _calculate_restart_delay(self) -> float:
        return exponential_backoff_with_jitter(
            self._restart_count,
            base_delay=self.config.restart_delay_base,
            max_delay=self.config.restart_delay_max,
            multiplier=self.config.restart_delay_multiplier,
            jitter_factor=self.config.jitter_factor,
        )

    def _setup_signal_handlers(self) -> None:
        def signal_handler(signum: int, _frame: FrameType | None) -> None:
            sig_name = signal.Signals(signum).name
            self._log.info("signal_received", signal=sig_name)
            self.stop()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _generate_server_script(self) -> Path:
        self.config.server_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.config.server_dir / "rpyc_server.py"
        script_path.write_text(RPYC_SERVER_SCRIPT)
        self._log.debug("script_generated", path=str(script_path))
        return script_path

    def _run_wine_server(self) -> int:
        """Run RPyC server via Wine subprocess."""
        script_path = self._generate_server_script()

        cmd = [
            self.config.wine_cmd,
            self.config.python_exe,
            str(script_path),
            self.config.host,
            str(self.config.port),
        ]

        self._log.info("starting_wine_server", command=" ".join(cmd))

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if self._process.stdout:
            for raw_line in self._process.stdout:
                output = raw_line.rstrip()
                if output:
                    if "error" in output.lower():
                        self._log.error("wine_output", message=output)
                    elif "warning" in output.lower():
                        self._log.warning("wine_output", message=output)
                    else:
                        self._log.info("wine_output", message=output)

                if self._shutdown_event.is_set():
                    break

        return self._process.wait()

    def _run_direct_server(self) -> int:
        """Run RPyC server directly (Linux mode)."""
        self._log.info(
            "starting_direct_server",
            use_thread_pool=self.config.use_thread_pool,
            mt5_available=is_mt5_available(),
        )

        server_class: type[ThreadedServer | ThreadPoolServer]
        kwargs: dict[str, Any] = {
            "service": MT5Service,
            "hostname": self.config.host,
            "port": self.config.port,
            "reuse_addr": True,
            "protocol_config": self.config.get_protocol_config(),
        }

        if self.config.use_thread_pool:
            server_class = ThreadPoolServer
            kwargs["nbThreads"] = self.config.thread_pool_size
        else:
            server_class = ThreadedServer

        self._server = server_class(**kwargs)

        try:
            self._server.start()
        except KeyboardInterrupt:
            self._log.info("server_interrupted")
        except Exception as e:
            _health_monitor.record_error(str(e))
            raise
        finally:
            if self._server:
                self._server.close()

        return 0

    def _server_loop(self) -> None:
        self._set_state(ServerState.RUNNING)

        while not self._shutdown_event.is_set():
            self._set_state(ServerState.STARTING)

            try:
                if self.config.mode == ServerMode.WINE:
                    exit_code = self._run_wine_server()
                else:
                    exit_code = self._run_direct_server()

                if self._shutdown_event.is_set():
                    self._log.info("server_shutdown_requested")
                    break

                if exit_code == 0:
                    self._log.info("server_exited_normally", exit_code=exit_code)
                    self._restart_count = 0
                    break

                self._restart_count += 1
                if self._restart_count > self.config.max_restarts:
                    self._log.error(
                        "max_restarts_exceeded", max_restarts=self.config.max_restarts
                    )
                    self._set_state(ServerState.FAILED)
                    break

                delay = self._calculate_restart_delay()
                self._log.warning(
                    "server_crashed",
                    exit_code=exit_code,
                    restart_count=self._restart_count,
                    restart_delay=f"{delay:.2f}s",
                )

                self._set_state(ServerState.RESTARTING)

                if self._shutdown_event.wait(delay):
                    break

            except Exception:  # noqa: BLE001 - Server resilience requires broad catch
                self._log.exception("server_error")
                self._restart_count += 1

                if self._restart_count > self.config.max_restarts:
                    self._set_state(ServerState.FAILED)
                    break

                delay = self._calculate_restart_delay()
                self._set_state(ServerState.RESTARTING)

                if self._shutdown_event.wait(delay):
                    break

        self._set_state(ServerState.STOPPED)

    def run(self, *, blocking: bool = True) -> None:
        self._shutdown_event.clear()
        self._setup_signal_handlers()

        self._log.info(
            "server_starting",
            blocking=blocking,
            max_restarts=self.config.max_restarts,
            use_thread_pool=self.config.use_thread_pool,
        )

        if blocking:
            self._server_loop()
        else:
            self._server_thread = threading.Thread(
                target=self._server_loop,
                name="mt5linux-server",
                daemon=True,
            )
            self._server_thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._log.info("stopping_server")
        self._set_state(ServerState.STOPPING)
        self._shutdown_event.set()

        if self._process and self._process.poll() is None:
            self._log.debug("terminating_wine_process")
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._log.warning("killing_wine_process")
                self._process.kill()

        if self._server:
            self._log.debug("closing_rpyc_server")
            self._server.close()

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=timeout)

        self._set_state(ServerState.STOPPED)
        self._log.info("server_stopped")

    def check_health(self) -> bool:
        """Check if server is healthy using modern rpyc.connect()."""
        try:
            # S104: Comparing against 0.0.0.0 to substitute with localhost
            host = "localhost" if self.config.host == "0.0.0.0" else self.config.host  # noqa: S104
            conn = rpyc.connect(
                host, self.config.port, config={"sync_request_timeout": 5}
            )
            status = conn.root.health_check()
            conn.close()
            healthy_value = status.get("healthy", False)
            return _validate_bool(healthy_value)
        except Exception:  # noqa: BLE001 - Catch all for health check resilience
            return False

    @contextmanager
    def managed(self) -> Iterator[Server]:
        self.run(blocking=False)
        try:
            yield self
        finally:
            self.stop()


# =============================================================================
# CLI
# =============================================================================


def parse_args(argv: list[str] | None = None) -> ServerConfig:
    parser = argparse.ArgumentParser(
        description="Modern RPyC server for MetaTrader5 (NO STUBS)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # S104: Default binding to all interfaces is intentional for server
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")  # noqa: S104
    parser.add_argument(
        "-p", "--port", type=int, default=18812, help="Port to listen on"
    )
    parser.add_argument(
        "--wine",
        "-w",
        dest="wine_cmd",
        metavar="CMD",
        help="Wine command (enables Wine mode)",
    )
    parser.add_argument(
        "--python",
        dest="python_exe",
        default="python.exe",
        help="Python executable (Wine mode)",
    )
    parser.add_argument(
        "--max-restarts", type=int, default=10, help="Maximum restart attempts"
    )
    parser.add_argument(
        "--server-dir",
        default=Path("~/.mt5linux").expanduser(),
        help="Server script directory",
    )
    parser.add_argument(
        "--no-thread-pool", action="store_true", help="Disable ThreadPoolServer"
    )
    parser.add_argument("--threads", type=int, default=10, help="Worker threads")
    parser.add_argument(
        "--timeout", type=int, default=300, help="Request timeout (seconds)"
    )

    args = parser.parse_args(argv)

    mode = ServerMode.WINE if args.wine_cmd else ServerMode.DIRECT

    return ServerConfig(
        host=args.host,
        port=args.port,
        mode=mode,
        wine_cmd=args.wine_cmd or "wine",
        python_exe=args.python_exe,
        server_dir=Path(args.server_dir),
        use_thread_pool=not args.no_thread_pool,
        thread_pool_size=args.threads,
        max_restarts=args.max_restarts,
        sync_request_timeout=args.timeout,
    )


def run_server(
    host: str = "0.0.0.0",  # noqa: S104 - Intentional binding to all interfaces
    port: int = 18812,
    *,
    wine_cmd: str | None = None,
    python_exe: str = "python.exe",
    max_restarts: int = 10,
) -> None:
    config = ServerConfig(
        host=host,
        port=port,
        mode=ServerMode.WINE if wine_cmd else ServerMode.DIRECT,
        wine_cmd=wine_cmd or "wine",
        python_exe=python_exe,
        max_restarts=max_restarts,
    )
    Server(config).run(blocking=True)


_MIN_POSITIONAL_ARGS = 3  # wine python.exe server.py HOST PORT
_IPV4_DOT_COUNT = 3  # x.x.x.x has 3 dots


def main() -> int:
    # Support positional args for Wine mode (mt5docker compatibility)
    # wine python.exe server.py 0.0.0.0 8001
    is_positional_mode = (
        len(sys.argv) >= _MIN_POSITIONAL_ARGS
        and sys.argv[1].count(".") == _IPV4_DOT_COUNT
    )
    if is_positional_mode:
        host = sys.argv[1]
        port = int(sys.argv[2])
        config = ServerConfig(host=host, port=port, mode=ServerMode.DIRECT)
    else:
        config = parse_args()

    env = detect_environment()
    mt5_avail = is_mt5_available()

    log.info(
        "server_initializing",
        environment=env.name,
        mt5_available=mt5_avail,
        use_thread_pool=config.use_thread_pool,
    )

    server = Server(config)

    try:
        server.run(blocking=True)
    except KeyboardInterrupt:
        server.stop()
        return 0
    except MT5NotAvailableError as e:
        log.exception("mt5_not_available", error=str(e))
        return 1
    else:
        return 0 if server.state != ServerState.FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
