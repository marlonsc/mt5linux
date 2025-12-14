"""
Resilient RPyC server for mt5linux with supervisor, health checks, and auto-recovery.

This module provides a robust server implementation using:
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
from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import PIPE, Popen
from typing import Any, Callable

from mt5linux.enums import CircuitState
from mt5linux.exceptions import CircuitBreakerOpenError
from mt5linux.models import ServerConfig, ServerState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5linux.resilient_server")


# =============================================================================
# RPyC Server Template
# =============================================================================

RPYC_SERVER_CODE = '''#!/usr/bin/env python
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


def _write_server_script(path: str) -> None:
    """Write the RPyC server script to the specified path."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(RPYC_SERVER_CODE)


# =============================================================================
# Circuit Breaker (Failure Protection)
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker pattern for failure protection.

    Prevents cascade failures by stopping requests when the system is failing.
    State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
    """

    __slots__ = (
        "failure_threshold",
        "recovery_timeout",
        "half_open_max_calls",
        "_state",
        "_failure_count",
        "_success_count",
        "_last_failure_time",
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
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state, transitioning to HALF_OPEN if ready."""
        with self._lock:
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
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
        logger.info("Circuit breaker reset")

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status for monitoring."""
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
    Token bucket rate limiter for request throttling.

    Limits request rate to prevent overload. Tokens replenish continuously
    at a rate of max_requests/window_seconds.
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
        """Get rate limiter status for monitoring."""
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
    Supervises RPyC server process with auto-restart capability.

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
                # Reset delay when running stable
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
        _write_server_script(server_script)

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
        """Record an error in state (keeps last 10)."""
        self.state.errors.append(
            {
                "time": datetime.now().isoformat(),
                "message": message,
            }
        )
        self.state.errors = self.state.errors[-10:]


# =============================================================================
# Health Checker (Monitoring)
# =============================================================================


class HealthChecker:
    """
    Health check functionality for the server.

    Periodically checks server health by testing port connectivity
    and provides status reporting.
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
            self._update_metrics()
            self.state.total_connections += 1
            self.state.metrics.connections_total += 1

    def unregister_connection(self, conn_id: int) -> None:
        """Unregister a connection."""
        with self._lock:
            self._connections.pop(conn_id, None)
            self._update_metrics()

    def update_connection(self, conn_id: int) -> None:
        """Update last activity time for a connection."""
        with self._lock:
            if conn_id in self._connections:
                self._connections[conn_id] = time.time()

    def _update_metrics(self) -> None:
        """Update connection metrics in state."""
        active = len(self._connections)
        self.state.active_connections = active
        self.state.metrics.connections_active = active

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
                self._update_metrics()


# =============================================================================
# HTTP Health Server (Kubernetes-compatible Endpoints)
# =============================================================================


class HealthHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints with DRY response helpers."""

    health_checker: HealthChecker | None = None
    rate_limiter: RateLimiter | None = None
    circuit_breaker: CircuitBreaker | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """DRY helper: Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _send_text(self, text: str, status: int = 200) -> None:
        """DRY helper: Send plain text response."""
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode())

    def do_GET(self) -> None:
        """Handle GET requests using pattern matching."""
        if self.rate_limiter and not self.rate_limiter.acquire():
            self.send_error(429, "Too Many Requests")
            return

        match self.path:
            case "/" | "/health":
                self._handle_health()
            case "/ready":
                self._handle_ready()
            case "/live":
                self._handle_live()
            case "/metrics":
                self._handle_metrics()
            case "/circuit":
                self._handle_circuit()
            case _:
                self.send_error(404)

    def _handle_health(self) -> None:
        """Send full health status."""
        if self.health_checker:
            status = self.health_checker.get_health_status()
            is_healthy = status.get("healthy", False)
        else:
            status = {"error": "Health checker not initialized"}
            is_healthy = False

        self._send_json(status, 200 if is_healthy else 503)

    def _handle_ready(self) -> None:
        """Send readiness status (Kubernetes readiness probe)."""
        is_ready = self.health_checker.is_healthy() if self.health_checker else False
        self._send_text("ready" if is_ready else "not ready", 200 if is_ready else 503)

    def _handle_live(self) -> None:
        """Send liveness status (Kubernetes liveness probe)."""
        self._send_text("alive", 200)

    def _handle_metrics(self) -> None:
        """Send metrics as JSON."""
        metrics = (
            self.health_checker.state.metrics.to_dict()
            if self.health_checker
            else {}
        )
        self._send_json(metrics)

    def _handle_circuit(self) -> None:
        """Send circuit breaker status."""
        status = self.circuit_breaker.get_status() if self.circuit_breaker else {}
        self._send_json(status)


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
            logger.info(
                f"Health HTTP server started on port {self.config.health_check_port}"
            )
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
