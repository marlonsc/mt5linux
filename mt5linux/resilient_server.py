"""
Resilient RPyC server for mt5linux with supervisor, health checks, and auto-recovery.

This module provides a robust server implementation using:
- Pydantic 2 for configuration and state management
- Circuit breaker pattern for failure protection
- Rate limiting with token bucket algorithm
- Process supervision with auto-restart
- HTTP health check endpoints (Kubernetes-compatible)
- Connection watchdog for stale cleanup

Usage:
    python -m mt5linux.resilient_server --host 0.0.0.0 --port 18812 \\
        --wine wine64 --python python.exe
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import PIPE, Popen
from typing import Any, Callable, Protocol

from pydantic import BaseModel, Field, computed_field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5linux.resilient_server")


# =============================================================================
# Enums
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# =============================================================================
# Pydantic Models (Configuration & State)
# =============================================================================


class ServerConfig(BaseModel):
    """Immutable server configuration using Pydantic 2."""

    model_config = {"frozen": True, "extra": "forbid"}

    host: str = "0.0.0.0"
    port: int = Field(default=18812, ge=1, le=65535)
    wine_cmd: str = "wine"
    python_path: str = "python.exe"
    server_dir: str = "/tmp/mt5linux"

    # Resilience
    max_restart_attempts: int = Field(default=10, ge=1)
    restart_cooldown: float = Field(default=5.0, gt=0)
    restart_backoff_multiplier: float = Field(default=2.0, ge=1)
    max_restart_delay: float = Field(default=300.0, gt=0)

    # Health check
    health_check_port: int = Field(default=8002, ge=1, le=65535)
    health_check_interval: float = Field(default=15.0, gt=0)

    # Watchdog
    watchdog_timeout: float = Field(default=60.0, gt=0)
    connection_timeout: float = Field(default=300.0, gt=0)

    # Limits
    max_connections: int = Field(default=10, ge=1)

    # Circuit breaker
    circuit_failure_threshold: int = Field(default=5, ge=1)
    circuit_recovery_timeout: float = Field(default=30.0, gt=0)
    circuit_half_open_max_calls: int = Field(default=3, ge=1)

    # Rate limiting
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: float = Field(default=60.0, gt=0)


class Metrics(BaseModel):
    """Server metrics with Pydantic 2 serialization."""

    model_config = {"extra": "forbid"}

    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    connections_total: int = 0
    connections_active: int = 0
    connections_rejected: int = 0
    restarts_total: int = 0
    uptime_seconds: float = 0.0
    last_request_time: datetime | None = None
    circuit_trips: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to structured dictionary."""
        return {
            "requests": {
                "total": self.requests_total,
                "success": self.requests_success,
                "failed": self.requests_failed,
            },
            "connections": {
                "total": self.connections_total,
                "active": self.connections_active,
                "rejected": self.connections_rejected,
            },
            "restarts_total": self.restarts_total,
            "uptime_seconds": self.uptime_seconds,
            "last_request_time": (
                self.last_request_time.isoformat() if self.last_request_time else None
            ),
            "circuit_trips": self.circuit_trips,
        }


class ServerState(BaseModel):
    """Mutable server state with Pydantic 2."""

    model_config = {"extra": "forbid", "validate_assignment": True}

    status: str = "stopped"
    start_time: datetime | None = None
    restart_count: int = 0
    last_restart_time: datetime | None = None
    last_health_check: datetime | None = None
    active_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    wine_process_pid: int | None = None
    metrics: Metrics = Field(default_factory=Metrics)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_running(self) -> bool:
        """Check if server is in running state."""
        return self.status == "running"


# =============================================================================
# Protocols (Interfaces for DIP/SRP)
# =============================================================================


class Startable(Protocol):
    """Protocol for components that can be started/stopped."""

    def start(self) -> None: ...
    def stop(self) -> None: ...


class HealthProvider(Protocol):
    """Protocol for health check providers."""

    def is_healthy(self) -> bool: ...
    def get_health_status(self) -> dict[str, Any]: ...


# =============================================================================
# Exceptions
# =============================================================================


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# =============================================================================
# Circuit Breaker (Failure Protection)
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascade failures by stopping requests when the system is failing.
    Uses state transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
    """

    __slots__ = (
        "failure_threshold",
        "recovery_timeout",
        "half_open_max_calls",
        "_state",
        "_failure_count",
        "_success_count",
        "_last_failure_time",
        "_half_open_calls",
        "_lock",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, transitioning to HALF_OPEN if ready."""
        with self._lock:
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
            return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if recovery timeout has passed."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._reset()
            else:
                self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._trip()
            elif self._failure_count >= self.failure_threshold:
                self._trip()

    def _trip(self) -> None:
        """Trip the circuit breaker to OPEN state."""
        self._state = CircuitState.OPEN
        logger.warning("Circuit breaker tripped!")

    def _reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info("Circuit breaker reset")

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
            }


# =============================================================================
# Rate Limiter (Token Bucket Algorithm)
# =============================================================================


class RateLimiter:
    """
    Token bucket rate limiter.

    Limits the rate of requests to prevent overload.
    Tokens replenish continuously at a rate of max_requests/window_seconds.
    """

    __slots__ = ("max_requests", "window_seconds", "_tokens", "_last_update", "_lock")

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._tokens = float(max_requests)
        self._last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._last_update = now

            # Replenish tokens based on elapsed time
            self._tokens = min(
                self.max_requests,
                self._tokens + (elapsed * self.max_requests / self.window_seconds),
            )

            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def get_status(self) -> dict[str, Any]:
        """Get rate limiter status."""
        with self._lock:
            return {
                "available_tokens": int(self._tokens),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
            }


# =============================================================================
# Process Supervisor (Auto-restart with Backoff)
# =============================================================================


class ProcessSupervisor:
    """
    Supervises the RPyC server process with auto-restart capability.

    Implements:
    - Exponential backoff on failures
    - Circuit breaker integration
    - Error recording
    - Graceful shutdown
    """

    def __init__(self, config: ServerConfig, state: ServerState) -> None:
        self.config = config
        self.state = state
        self.process: Popen | None = None
        self._stop_event = threading.Event()
        self._restart_delay = config.restart_cooldown
        self._supervisor_thread: threading.Thread | None = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_failure_threshold,
            recovery_timeout=config.circuit_recovery_timeout,
            half_open_max_calls=config.circuit_half_open_max_calls,
        )

    def start(self) -> None:
        """Start the supervisor and managed process."""
        self._stop_event.clear()
        self._supervisor_thread = threading.Thread(
            target=self._supervision_loop,
            name="ProcessSupervisor",
            daemon=True,
        )
        self._supervisor_thread.start()
        logger.info("Process supervisor started")

    def stop(self) -> None:
        """Stop the supervisor and managed process."""
        logger.info("Stopping process supervisor...")
        self._stop_event.set()
        self._kill_process()
        if self._supervisor_thread:
            self._supervisor_thread.join(timeout=10)
        self.state.status = "stopped"
        logger.info("Process supervisor stopped")

    def is_running(self) -> bool:
        """Check if the managed process is running."""
        return self.process is not None and self.process.poll() is None

    def _supervision_loop(self) -> None:
        """Main supervision loop - monitors and restarts process."""
        while not self._stop_event.is_set():
            if not self.is_running():
                exit_code = self.process.poll() if self.process else None
                if exit_code is not None:
                    logger.warning(f"Process exited with code {exit_code}")
                    self._record_error(f"Process exited with code {exit_code}")

                if self._should_restart():
                    try:
                        self.circuit_breaker.call(self._restart_process)
                    except CircuitBreakerOpenError:
                        logger.error("Circuit breaker open, not restarting")
                        self.state.status = "circuit_open"
                        self.state.metrics.circuit_trips += 1
                else:
                    logger.error("Max restart attempts reached, stopping supervisor")
                    self.state.status = "failed"
                    break
            else:
                if self.state.status == "running":
                    self._restart_delay = self.config.restart_cooldown

            self._stop_event.wait(timeout=1.0)

    def _should_restart(self) -> bool:
        """Check if restart is allowed."""
        return self.state.restart_count < self.config.max_restart_attempts

    def _restart_process(self) -> None:
        """Restart the managed process with exponential backoff."""
        self.state.restart_count += 1
        self.state.last_restart_time = datetime.now()
        self.state.status = "restarting"
        self.state.metrics.restarts_total += 1

        logger.info(
            f"Restarting process (attempt {self.state.restart_count}/"
            f"{self.config.max_restart_attempts}), delay: {self._restart_delay:.1f}s"
        )

        self._stop_event.wait(timeout=self._restart_delay)
        if self._stop_event.is_set():
            return

        # Exponential backoff
        self._restart_delay = min(
            self._restart_delay * self.config.restart_backoff_multiplier,
            self.config.max_restart_delay,
        )

        self._kill_process()
        self._start_process()

    def _start_process(self) -> None:
        """Start the RPyC server process."""
        self.state.status = "starting"

        os.makedirs(self.config.server_dir, exist_ok=True)
        server_script = os.path.join(self.config.server_dir, "rpyc_server.py")
        self._generate_server_code(server_script)

        cmd = [
            self.config.wine_cmd,
            self.config.python_path,
            server_script,
            "--host",
            self.config.host,
            "-p",
            str(self.config.port),
            "-q",
        ]

        logger.info(f"Starting process: {' '.join(cmd)}")

        try:
            self.process = Popen(cmd, stdout=PIPE, stderr=PIPE, text=False)
            self.state.wine_process_pid = self.process.pid
            self.state.start_time = datetime.now()

            # Wait briefly to check if process started
            time.sleep(1)
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate(timeout=5)
                stderr_text = stderr.decode(errors="replace")
                logger.error(f"Process failed to start. stderr: {stderr_text}")
                self._record_error(f"Failed to start: {stderr_text[:500]}")
                raise RuntimeError("Process failed to start")

            self.state.status = "running"
            logger.info(f"Process started with PID {self.process.pid}")
        except Exception as e:
            logger.exception(f"Failed to start process: {e}")
            self._record_error(str(e))
            raise

    def _reset_restart_count_if_stable(self) -> None:
        """Reset restart count if process has been stable."""
        if self.state.status == "running" and self.is_running():
            logger.info("Process stable for 30s, resetting restart count")
            self.state.restart_count = 0
            self._restart_delay = self.config.restart_cooldown

    def _kill_process(self) -> None:
        """Kill the managed process."""
        if self.process is not None:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except Exception:
                    self.process.kill()
                    self.process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error killing process: {e}")
            finally:
                self.process = None
                self.state.wine_process_pid = None

    def _record_error(self, message: str) -> None:
        """Record an error in the state (keeps last 10)."""
        self.state.errors.append({
            "time": datetime.now().isoformat(),
            "message": message,
        })
        self.state.errors = self.state.errors[-10:]

    def _generate_server_code(self, path: str) -> None:
        """Generate the RPyC server code."""
        code = '''#!/usr/bin/env python
"""RPyC classic server for mt5linux."""
import rpyc
from plumbum import cli
from rpyc.utils.server import ThreadedServer
from rpyc.utils.classic import DEFAULT_SERVER_PORT
from rpyc.lib import setup_logger
from rpyc.core import SlaveService


class ClassicServer(cli.Application):
    mode = cli.SwitchAttr(
        ["-m", "--mode"],
        cli.Set("threaded", "forking"),
        default="threaded",
        help="The serving mode",
    )
    port = cli.SwitchAttr(
        ["-p", "--port"],
        cli.Range(0, 65535),
        default=DEFAULT_SERVER_PORT,
        help="The TCP listener port",
    )
    host = cli.SwitchAttr(
        ["--host"],
        str,
        default="127.0.0.1",
        help="The host to bind to",
    )
    quiet = cli.Flag(
        ["-q", "--quiet"],
        help="Quiet mode",
    )
    logfile = cli.SwitchAttr(
        "--logfile",
        str,
        default=None,
        help="Log file path",
    )

    def main(self):
        setup_logger(self.quiet, self.logfile)
        t = ThreadedServer(
            SlaveService,
            hostname=self.host,
            port=self.port,
            reuse_addr=True,
        )
        t.start()


if __name__ == "__main__":
    ClassicServer.run()
'''
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)


# =============================================================================
# Health Checker (Monitoring)
# =============================================================================


class HealthChecker:
    """
    Health check functionality for the server.

    Implements HealthProvider protocol for status reporting.
    """

    def __init__(self, config: ServerConfig, state: ServerState) -> None:
        self.config = config
        self.state = state
        self._stop_event = threading.Event()
        self._checker_thread: threading.Thread | None = None
        self._last_check_success = True

    def start(self) -> None:
        """Start the health checker background thread."""
        self._stop_event.clear()
        self._checker_thread = threading.Thread(
            target=self._check_loop,
            name="HealthChecker",
            daemon=True,
        )
        self._checker_thread.start()
        logger.info("Health checker started")

    def stop(self) -> None:
        """Stop the health checker."""
        self._stop_event.set()
        if self._checker_thread:
            self._checker_thread.join(timeout=5)
        logger.info("Health checker stopped")

    def _check_loop(self) -> None:
        """Periodically check server health."""
        while not self._stop_event.is_set():
            self._perform_check()
            self._stop_event.wait(timeout=self.config.health_check_interval)

    def _perform_check(self) -> bool:
        """Perform a health check by testing port connectivity."""
        self.state.last_health_check = datetime.now()

        if self.state.start_time:
            self.state.metrics.uptime_seconds = (
                datetime.now() - self.state.start_time
            ).total_seconds()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("127.0.0.1", self.config.port))
            sock.close()

            if result != 0:
                logger.warning(f"Port {self.config.port} not responding")
                self._last_check_success = False
                return False

            self._last_check_success = True
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._last_check_success = False
            return False

    def is_healthy(self) -> bool:
        """Check if server is currently healthy."""
        return self._last_check_success and self.state.status == "running"

    def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status."""
        uptime = None
        if self.state.start_time:
            uptime = (datetime.now() - self.state.start_time).total_seconds()

        return {
            "status": self.state.status,
            "healthy": self.is_healthy(),
            "uptime_seconds": uptime,
            "restart_count": self.state.restart_count,
            "last_restart": (
                self.state.last_restart_time.isoformat()
                if self.state.last_restart_time
                else None
            ),
            "last_health_check": (
                self.state.last_health_check.isoformat()
                if self.state.last_health_check
                else None
            ),
            "active_connections": self.state.active_connections,
            "total_connections": self.state.total_connections,
            "wine_pid": self.state.wine_process_pid,
            "recent_errors": self.state.errors[-5:],
            "metrics": self.state.metrics.to_dict(),
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "max_connections": self.config.max_connections,
            },
        }


# =============================================================================
# Connection Watchdog (Stale Connection Cleanup)
# =============================================================================


class ConnectionWatchdog:
    """
    Monitors and cleans up stale connections.

    Tracks connection activity and removes connections that have been
    inactive for longer than the configured timeout.
    """

    def __init__(self, config: ServerConfig, state: ServerState) -> None:
        self.config = config
        self.state = state
        self._connections: dict[int, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._watchdog_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the watchdog background thread."""
        self._stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="ConnectionWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()
        logger.info("Connection watchdog started")

    def stop(self) -> None:
        """Stop the watchdog."""
        self._stop_event.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        logger.info("Connection watchdog stopped")

    def register_connection(self, conn_id: int) -> None:
        """Register a new connection."""
        with self._lock:
            self._connections[conn_id] = time.time()
            self.state.active_connections = len(self._connections)
            self.state.total_connections += 1
            self.state.metrics.connections_total += 1
            self.state.metrics.connections_active = len(self._connections)

    def unregister_connection(self, conn_id: int) -> None:
        """Unregister a connection."""
        with self._lock:
            self._connections.pop(conn_id, None)
            self.state.active_connections = len(self._connections)
            self.state.metrics.connections_active = len(self._connections)

    def update_connection(self, conn_id: int) -> None:
        """Update last activity time for a connection."""
        with self._lock:
            if conn_id in self._connections:
                self._connections[conn_id] = time.time()

    def _watchdog_loop(self) -> None:
        """Periodically check for stale connections."""
        while not self._stop_event.is_set():
            self._cleanup_stale_connections()
            self._stop_event.wait(timeout=self.config.watchdog_timeout)

    def _cleanup_stale_connections(self) -> None:
        """Remove connections that have been inactive."""
        now = time.time()
        with self._lock:
            stale = [
                cid
                for cid, last_active in self._connections.items()
                if now - last_active > self.config.connection_timeout
            ]
            for cid in stale:
                logger.warning(f"Cleaning up stale connection {cid}")
                self._connections.pop(cid, None)
            if stale:
                self.state.active_connections = len(self._connections)
                self.state.metrics.connections_active = len(self._connections)


# =============================================================================
# HTTP Health Server (Kubernetes-compatible Endpoints)
# =============================================================================


class HealthHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    health_checker: HealthChecker | None = None
    rate_limiter: RateLimiter | None = None
    circuit_breaker: CircuitBreaker | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests to health endpoints."""
        if self.rate_limiter and not self.rate_limiter.acquire():
            self.send_error(429, "Too Many Requests")
            return

        handlers = {
            "/": self._send_health_response,
            "/health": self._send_health_response,
            "/ready": self._send_ready_response,
            "/live": self._send_live_response,
            "/metrics": self._send_metrics_response,
            "/circuit": self._send_circuit_response,
        }

        handler = handlers.get(self.path)
        if handler:
            handler()
        else:
            self.send_error(404)

    def _send_health_response(self) -> None:
        """Send full health status."""
        if self.health_checker:
            status = self.health_checker.get_health_status()
            is_healthy = status.get("healthy", False)
        else:
            status = {"error": "Health checker not initialized"}
            is_healthy = False

        self.send_response(200 if is_healthy else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode())

    def _send_ready_response(self) -> None:
        """Send readiness status (Kubernetes readiness probe)."""
        is_ready = self.health_checker.is_healthy() if self.health_checker else False

        self.send_response(200 if is_ready else 503)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ready" if is_ready else b"not ready")

    def _send_live_response(self) -> None:
        """Send liveness status (Kubernetes liveness probe)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"alive")

    def _send_metrics_response(self) -> None:
        """Send Prometheus-compatible metrics."""
        if self.health_checker:
            metrics = self.health_checker.state.metrics.to_dict()
        else:
            metrics = {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(metrics, indent=2).encode())

    def _send_circuit_response(self) -> None:
        """Send circuit breaker status."""
        status = self.circuit_breaker.get_status() if self.circuit_breaker else {}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode())


class HealthHTTPServer:
    """HTTP server for health check endpoints."""

    def __init__(
        self,
        config: ServerConfig,
        health_checker: HealthChecker,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.config = config
        self.health_checker = health_checker
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self._server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the HTTP server."""
        # Set class attributes for handler
        HealthHTTPHandler.health_checker = self.health_checker
        HealthHTTPHandler.rate_limiter = self.rate_limiter
        HealthHTTPHandler.circuit_breaker = self.circuit_breaker

        try:
            self._server = HTTPServer(
                ("0.0.0.0", self.config.health_check_port),
                HealthHTTPHandler,
            )
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                name="HealthHTTPServer",
                daemon=True,
            )
            self._server_thread.start()
            logger.info(f"Health HTTP server started on port {self.config.health_check_port}")
        except OSError as e:
            logger.error(f"Failed to start health HTTP server: {e}")

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        logger.info("Health HTTP server stopped")


# =============================================================================
# Main Server Orchestrator
# =============================================================================


class ResilientRPyCServer:
    """
    Orchestrates all server components.

    Provides a single entry point to start/stop the resilient server
    with all its features: supervision, health checks, rate limiting, etc.
    """

    def __init__(self, config: ServerConfig | None = None) -> None:
        self.config = config or ServerConfig()
        self.state = ServerState()

        # Initialize components
        self.supervisor = ProcessSupervisor(self.config, self.state)
        self.health_checker = HealthChecker(self.config, self.state)
        self.watchdog = ConnectionWatchdog(self.config, self.state)
        self.rate_limiter = RateLimiter(
            max_requests=self.config.rate_limit_requests,
            window_seconds=self.config.rate_limit_window,
        )
        self.health_server = HealthHTTPServer(
            self.config,
            self.health_checker,
            self.rate_limiter,
            self.supervisor.circuit_breaker,
        )

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Start all server components."""
        logger.info("Starting resilient RPyC server...")
        self.health_checker.start()
        self.watchdog.start()
        self.health_server.start()
        self.supervisor.start()
        logger.info("Resilient RPyC server started successfully")

    def stop(self) -> None:
        """Stop all server components gracefully."""
        logger.info("Stopping resilient RPyC server...")
        self.supervisor.stop()
        self.health_checker.stop()
        self.watchdog.stop()
        self.health_server.stop()
        logger.info("Resilient RPyC server stopped")

    def run_forever(self) -> None:
        """Run the server until interrupted or failed."""
        self.start()
        try:
            while self.state.status not in ("stopped", "failed"):
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


# =============================================================================
# CLI Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Resilient RPyC server for mt5linux")
    parser.add_argument(
        "python",
        type=str,
        nargs="?",
        default="python.exe",
        help="Python executable path (Windows)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=18812,
        help="Port to listen on (default: 18812)",
    )
    parser.add_argument(
        "-w",
        "--wine",
        type=str,
        default="wine",
        help="Wine command (default: wine)",
    )
    parser.add_argument(
        "--server-dir",
        type=str,
        default="/tmp/mt5linux",
        help="Directory for server files (default: /tmp/mt5linux)",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=8002,
        help="Health check port (default: 8002)",
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=10,
        help="Maximum restart attempts (default: 10)",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=10,
        help="Maximum concurrent connections (default: 10)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the resilient server."""
    args = parse_args()

    config = ServerConfig(
        host=args.host,
        port=args.port,
        wine_cmd=args.wine,
        python_path=args.python,
        server_dir=args.server_dir,
        health_check_port=args.health_port,
        max_restart_attempts=args.max_restarts,
        max_connections=args.max_connections,
    )

    server = ResilientRPyCServer(config)
    server.run_forever()


if __name__ == "__main__":
    main()
