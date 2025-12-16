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
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from functools import wraps
from types import FrameType
from typing import Any

import rpyc
import structlog
from rpyc.utils.server import ThreadedServer, ThreadPoolServer

from mt5linux.config import config
from mt5linux.utilities import MT5Utilities

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
    """Check if MetaTrader5 module is importable.

    MetaTrader5 is only available in Wine environments, not in Linux.
    This function is used to detect the runtime environment and determine
    if MT5 API access is available.

    Returns:
        bool: True if MetaTrader5 can be imported, False otherwise.
    """
    try:
        import MetaTrader5  # pyright: ignore[reportUnusedImport, reportMissingImports]

    except ImportError:
        return False
    else:
        return True


class MT5NotAvailableError(Exception):
    """Raised when MetaTrader5 module is not available. NO STUBS."""


# =============================================================================
# Server Class with All Nested Components
# =============================================================================


class MT5Server:
    """Production-grade RPyC server with automatic recovery.

    Contains all server-related nested classes:
    - Mode: Server execution mode (DIRECT, WINE)
    - State: Server lifecycle state (STOPPED, STARTING, RUNNING, etc.)
    - Config: Server configuration dataclass
    - CircuitBreaker: Server-side circuit breaker for fault tolerance
    - RateLimiter: Token bucket rate limiter
    - HealthMonitor: Health monitoring with status tracking
    """

    # =========================================================================
    # NESTED ENUMS
    # =========================================================================

    class Mode(Enum):
        """Server execution mode."""

        DIRECT = "direct"  # Run directly (Linux)
        WINE = "wine"  # Run via Wine subprocess

    class State(Enum):
        """Server lifecycle state."""

        STOPPED = "stopped"
        STARTING = "starting"
        RUNNING = "running"
        RESTARTING = "restarting"
        STOPPING = "stopping"
        FAILED = "failed"

    # =========================================================================
    # NESTED CONFIG
    # =========================================================================

    @dataclass
    class Config:
        """Server configuration."""

        host: str = "0.0.0.0"  # noqa: S104 - Intentional binding to all interfaces
        port: int = 18812
        mode: MT5Server.Mode = field(default_factory=lambda: MT5Server.Mode.DIRECT)

        # Wine mode settings
        wine_cmd: str = "wine"
        python_exe: str = "python.exe"

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

        def get_protocol_config(self) -> dict[str, Any]:
            return {
                "allow_public_attrs": True,
                "allow_pickle": self.allow_pickle,
                "sync_request_timeout": self.sync_request_timeout,
            }

    # =========================================================================
    # NESTED CIRCUIT BREAKER (Server-side)
    # =========================================================================

    class CircuitBreaker:
        """Server-side circuit breaker for fault tolerance."""

        class State(IntEnum):
            """Circuit breaker states."""

            CLOSED = 0
            OPEN = 1
            HALF_OPEN = 2

        @dataclass
        class Config:
            """Circuit breaker configuration."""

            failure_threshold: int = 5
            success_threshold: int = 2
            timeout: float = 30.0
            excluded_exceptions: tuple[type[Exception], ...] = ()

        class OpenError(Exception):
            """Raised when circuit breaker is open."""

        def __init__(
            self, config: MT5Server.CircuitBreaker.Config | None = None
        ) -> None:
            self.config = config or MT5Server.CircuitBreaker.Config()
            self._state = MT5Server.CircuitBreaker.State.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time: float | None = None
            self._lock = threading.RLock()

        @property
        def state(self) -> MT5Server.CircuitBreaker.State:
            """Current circuit state."""
            with self._lock:
                if (
                    self._state == MT5Server.CircuitBreaker.State.OPEN
                    and self._last_failure_time
                    and time.time() - self._last_failure_time >= self.config.timeout
                ):
                    self._state = MT5Server.CircuitBreaker.State.HALF_OPEN
                    self._success_count = 0
                return self._state

        def _record_success(self) -> None:
            with self._lock:
                if self._state == MT5Server.CircuitBreaker.State.HALF_OPEN:
                    self._success_count += 1
                    if self._success_count >= self.config.success_threshold:
                        self._state = MT5Server.CircuitBreaker.State.CLOSED
                        self._failure_count = 0
                elif self._state == MT5Server.CircuitBreaker.State.CLOSED:
                    self._failure_count = 0

        def _record_failure(self) -> None:
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._state == MT5Server.CircuitBreaker.State.HALF_OPEN or (
                    self._state == MT5Server.CircuitBreaker.State.CLOSED
                    and self._failure_count >= self.config.failure_threshold
                ):
                    self._state = MT5Server.CircuitBreaker.State.OPEN

        def reset(self) -> None:
            """Reset circuit breaker."""
            with self._lock:
                self._state = MT5Server.CircuitBreaker.State.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._last_failure_time = None

        def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if self.state == MT5Server.CircuitBreaker.State.OPEN:
                    msg = f"Circuit breaker open, call to {func.__name__} blocked"
                    raise MT5Server.CircuitBreaker.OpenError(msg)
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

    # =========================================================================
    # NESTED RATE LIMITER
    # =========================================================================

    class RateLimiter:
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

    # =========================================================================
    # NESTED HEALTH MONITOR
    # =========================================================================

    class HealthMonitor:
        """Health monitoring for the server."""

        @dataclass
        class Status:
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

        def get_status(
            self, circuit_state: str = "closed"
        ) -> MT5Server.HealthMonitor.Status:
            with self._lock:
                return MT5Server.HealthMonitor.Status(
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

    # =========================================================================
    # MAIN SERVER IMPLEMENTATION
    # =========================================================================

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or MT5Server.Config()
        self._state = MT5Server.State.STOPPED
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
    def state(self) -> State:
        return self._state

    @property
    def restart_count(self) -> int:
        return self._restart_count

    def _set_state(self, state: State) -> None:
        old_state = self._state
        self._state = state
        self._log.debug(
            "state_changed", old_state=old_state.value, new_state=state.value
        )

    def _calculate_restart_delay(self) -> float:
        return MT5Utilities.Retry.backoff_with_jitter(
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

    def _run_wine_server(self) -> int:
        """Run RPyC server via Wine subprocess using mt5linux.bridge module."""
        cmd = [
            self.config.wine_cmd,
            self.config.python_exe,
            "-m",
            "mt5linux.bridge",
            "--host",
            self.config.host,
            "-p",
            str(self.config.port),
        ]

        self._log.info("starting_wine_bridge", command=" ".join(cmd))

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
        self._set_state(MT5Server.State.RUNNING)

        while not self._shutdown_event.is_set():
            self._set_state(MT5Server.State.STARTING)

            try:
                if self.config.mode == MT5Server.Mode.WINE:
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
                    self._set_state(MT5Server.State.FAILED)
                    break

                delay = self._calculate_restart_delay()
                self._log.warning(
                    "server_crashed",
                    exit_code=exit_code,
                    restart_count=self._restart_count,
                    restart_delay=f"{delay:.2f}s",
                )

                self._set_state(MT5Server.State.RESTARTING)

                if self._shutdown_event.wait(delay):
                    break

            except Exception:  # noqa: BLE001 - Server resilience requires broad catch
                self._log.exception("server_error")
                self._restart_count += 1

                if self._restart_count > self.config.max_restarts:
                    self._set_state(MT5Server.State.FAILED)
                    break

                delay = self._calculate_restart_delay()
                self._set_state(MT5Server.State.RESTARTING)

                if self._shutdown_event.wait(delay):
                    break

        self._set_state(MT5Server.State.STOPPED)

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
        self._set_state(MT5Server.State.STOPPING)
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

        self._set_state(MT5Server.State.STOPPED)
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
            return MT5Utilities.Validators.bool_value(healthy_value)
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
# Global Instances (used by MT5Service)
# =============================================================================

_health_monitor = MT5Server.HealthMonitor()
_mt5_circuit_breaker = MT5Server.CircuitBreaker(
    MT5Server.CircuitBreaker.Config(failure_threshold=5)
)


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
    _rate_limiter = MT5Server.RateLimiter(rate=100, capacity=200)

    def on_connect(self, conn: rpyc.Connection) -> None:  # noqa: ARG002
        """Initialize MT5 module on connection.

        MetaTrader5 module is imported lazily when first client connects
        to avoid unnecessary initialization in non-Wine environments.
        Only done once per service instance with thread-safe locking.

        Raises:
            MT5NotAvailableError: If MetaTrader5 cannot be imported
                (typically in non-Wine Linux environments).
        """
        _health_monitor.record_connection()

        with MT5Service._mt5_lock:
            if MT5Service._mt5_module is None:
                try:
                    import MetaTrader5 as MT5  # pyright: ignore[reportMissingImports]

                    MT5Service._mt5_module = MT5
                    log.info("mt5_module_loaded")
                except ImportError as e:
                    log.exception("mt5_module_not_available", error=str(e))
                    msg = "MetaTrader5 module not available. NO STUBS."
                    raise MT5NotAvailableError(msg) from e

    def on_disconnect(self, conn: rpyc.Connection) -> None:  # noqa: ARG002
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
        status = _health_monitor.get_status(str(_mt5_circuit_breaker.state.value))
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
        return MT5Utilities.Validators.bool_value(result)

    def exposed_login(
        self, login: int, password: str, server: str, timeout: int = 60000
    ) -> bool:
        result = self._call_mt5(
            MT5Service._mt5_module.login, login, password, server, timeout
        )
        return MT5Utilities.Validators.bool_value(result)

    def exposed_shutdown(self) -> None:
        self._call_mt5(MT5Service._mt5_module.shutdown)

    def exposed_version(self) -> tuple[int, int, str] | None:
        result = self._call_mt5(MT5Service._mt5_module.version)
        return MT5Utilities.Validators.version(result)

    def exposed_last_error(self) -> tuple[int, str]:
        with MT5Service._mt5_lock:
            result = MT5Service._mt5_module.last_error()
            return MT5Utilities.Validators.last_error(result)

    def exposed_terminal_info(self) -> Any:
        return self._call_mt5(MT5Service._mt5_module.terminal_info)

    def exposed_account_info(self) -> Any:
        return self._call_mt5(MT5Service._mt5_module.account_info)

    # =========================================================================
    # Symbol Operations
    # =========================================================================

    def exposed_symbols_total(self) -> int:
        result = self._call_mt5(MT5Service._mt5_module.symbols_total)
        return MT5Utilities.Validators.int_value(result)

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
        return MT5Utilities.Validators.bool_value(result)

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
        return MT5Utilities.Validators.float_optional(result)

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
        return MT5Utilities.Validators.float_optional(result)

    def exposed_order_check(self, request: dict[str, Any]) -> Any:
        # Convert netref dict to regular dict for MT5 compatibility
        local_request = dict(request)
        return self._call_mt5(MT5Service._mt5_module.order_check, local_request)

    def exposed_order_send(self, request: dict[str, Any]) -> Any:
        # Convert netref dict to regular dict for MT5 compatibility
        local_request = dict(request)
        return self._call_mt5(MT5Service._mt5_module.order_send, local_request)

    # =========================================================================
    # Position Operations
    # =========================================================================

    def exposed_positions_total(self) -> int:
        result = self._call_mt5(MT5Service._mt5_module.positions_total)
        return MT5Utilities.Validators.int_value(result)

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
        return MT5Utilities.Validators.int_value(result)

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
        return MT5Utilities.Validators.int_optional(result)

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
        return MT5Utilities.Validators.int_optional(result)

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
# CLI
# =============================================================================


def parse_args(argv: list[str] | None = None) -> MT5Server.Config:
    parser = argparse.ArgumentParser(
        description="Modern RPyC server for MetaTrader5 (NO STUBS)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # S104: Default binding to all interfaces is intentional for server
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")  # noqa: S104
    parser.add_argument(
        "-p", "--port", type=int, default=config.PORT_RPYC, help="Port to listen on"
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
        "--max-restarts",
        type=int,
        default=config.MAX_RESTARTS,
        help="Maximum restart attempts",
    )
    parser.add_argument(
        "--no-thread-pool", action="store_true", help="Disable ThreadPoolServer"
    )
    parser.add_argument(
        "--threads", type=int, default=config.THREAD_POOL_SIZE, help="Worker threads"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=config.TIMEOUT_SYNC_REQUEST,
        help="Request timeout (seconds)",
    )

    args = parser.parse_args(argv)

    mode = MT5Server.Mode.WINE if args.wine_cmd else MT5Server.Mode.DIRECT

    return MT5Server.Config(
        host=args.host,
        port=args.port,
        mode=mode,
        wine_cmd=args.wine_cmd or "wine",
        python_exe=args.python_exe,
        use_thread_pool=not args.no_thread_pool,
        thread_pool_size=args.threads,
        max_restarts=args.max_restarts,
        sync_request_timeout=args.timeout,
    )


def run_server(
    host: str = "0.0.0.0",  # noqa: S104 - Intentional binding to all interfaces
    port: int = config.PORT_RPYC,
    *,
    wine_cmd: str | None = None,
    python_exe: str = "python.exe",
    max_restarts: int = config.MAX_RESTARTS,
) -> None:
    server_config = MT5Server.Config(
        host=host,
        port=port,
        mode=MT5Server.Mode.WINE if wine_cmd else MT5Server.Mode.DIRECT,
        wine_cmd=wine_cmd or "wine",
        python_exe=python_exe,
        max_restarts=max_restarts,
    )
    Server(server_config).run(blocking=True)


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
        config = MT5Server.Config(host=host, port=port, mode=MT5Server.Mode.DIRECT)
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
        return 0 if server.state != MT5Server.State.FAILED else 1


# Backward compatibility alias (to be removed in next major version)
Server = MT5Server


if __name__ == "__main__":
    sys.exit(main())
