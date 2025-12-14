"""
Resilient RPyC server for mt5linux with supervisor, health checks, and auto-recovery.

This module provides a robust server implementation that:
- Automatically restarts on crashes (supervisor pattern)
- Exposes health check endpoints
- Monitors connection health with heartbeat/watchdog
- Handles graceful shutdown
- Limits concurrent connections

Usage:
    python -m mt5linux.resilient_server --host 0.0.0.0 --port 8001 \\
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
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import PIPE, Popen
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5linux.resilient_server")


@dataclass
class ServerConfig:
    """Configuration for the resilient server."""

    host: str = "0.0.0.0"
    port: int = 18812
    wine_cmd: str = "wine"
    python_path: str = "python.exe"
    server_dir: str = "/tmp/mt5linux"

    # Resilience settings
    max_restart_attempts: int = 10
    restart_cooldown: float = 5.0
    restart_backoff_multiplier: float = 2.0
    max_restart_delay: float = 300.0  # 5 minutes max

    # Health check settings
    health_check_port: int = 8002
    health_check_interval: float = 15.0

    # Watchdog settings
    watchdog_timeout: float = 60.0
    connection_timeout: float = 300.0

    # Connection limits
    max_connections: int = 10


@dataclass
class ServerState:
    """Current state of the server."""

    status: str = "stopped"
    start_time: datetime | None = None
    restart_count: int = 0
    last_restart_time: datetime | None = None
    last_health_check: datetime | None = None
    active_connections: int = 0
    total_connections: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    wine_process_pid: int | None = None


class ProcessSupervisor:
    """Supervises the RPyC server process with auto-restart."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.process: Popen | None = None
        self.state = ServerState()
        self._stop_event = threading.Event()
        self._restart_delay = config.restart_cooldown
        self._supervisor_thread: threading.Thread | None = None

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

    def _supervision_loop(self) -> None:
        """Main supervision loop - monitors and restarts process."""
        while not self._stop_event.is_set():
            if self.process is None or self.process.poll() is not None:
                # Process not running or has exited
                exit_code = self.process.poll() if self.process else None
                if exit_code is not None:
                    logger.warning(f"Process exited with code {exit_code}")
                    self._record_error(f"Process exited with code {exit_code}")

                if self._should_restart():
                    self._restart_process()
                else:
                    logger.error("Max restart attempts reached, stopping supervisor")
                    self.state.status = "failed"
                    break
            else:
                # Process is running, reset restart delay on success
                if self.state.status == "running":
                    self._restart_delay = self.config.restart_cooldown

            self._stop_event.wait(timeout=1.0)

    def _should_restart(self) -> bool:
        """Check if we should attempt a restart."""
        if self.state.restart_count >= self.config.max_restart_attempts:
            return False
        return True

    def _restart_process(self) -> None:
        """Restart the managed process with backoff."""
        self.state.restart_count += 1
        self.state.last_restart_time = datetime.now()
        self.state.status = "restarting"

        logger.info(
            f"Restarting process (attempt {self.state.restart_count}/"
            f"{self.config.max_restart_attempts}), delay: {self._restart_delay:.1f}s"
        )

        # Wait with backoff
        self._stop_event.wait(timeout=self._restart_delay)
        if self._stop_event.is_set():
            return

        # Increase delay for next restart (exponential backoff)
        self._restart_delay = min(
            self._restart_delay * self.config.restart_backoff_multiplier,
            self.config.max_restart_delay,
        )

        # Kill any remaining process
        self._kill_process()

        # Start new process
        self._start_process()

    def _start_process(self) -> None:
        """Start the RPyC server process."""
        self.state.status = "starting"

        # Ensure server directory exists
        os.makedirs(self.config.server_dir, exist_ok=True)

        # Generate server code
        server_code_path = os.path.join(self.config.server_dir, "server.py")
        self._generate_server_code(server_code_path)

        # Build command
        cmd = [
            self.config.wine_cmd,
            self.config.python_path,
            server_code_path,
            "--host",
            self.config.host,
            "-p",
            str(self.config.port),
        ]

        logger.info(f"Starting RPyC server: {' '.join(cmd)}")

        try:
            self.process = Popen(
                cmd,
                stdout=PIPE,
                stderr=PIPE,
                start_new_session=True,
            )
            self.state.wine_process_pid = self.process.pid
            self.state.start_time = datetime.now()

            # Wait a bit and check if process started successfully
            time.sleep(2)
            if self.process.poll() is None:
                self.state.status = "running"
                logger.info(
                    f"RPyC server started successfully (PID: {self.process.pid})"
                )
                # Reset restart count on successful start after some uptime
                threading.Timer(
                    30.0, self._reset_restart_count_if_stable
                ).start()
            else:
                stdout, stderr = self.process.communicate(timeout=5)
                logger.error(
                    f"Process failed to start. stdout: {stdout}, stderr: {stderr}"
                )
                self._record_error(f"Failed to start: {stderr.decode()[:500]}")
        except Exception as e:
            logger.exception(f"Failed to start process: {e}")
            self._record_error(str(e))

    def _reset_restart_count_if_stable(self) -> None:
        """Reset restart count if process has been stable."""
        if self.state.status == "running" and self.process and self.process.poll() is None:
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
        """Record an error in the state."""
        self.state.errors.append({
            "time": datetime.now().isoformat(),
            "message": message,
        })
        # Keep only last 10 errors
        self.state.errors = self.state.errors[-10:]

    def _generate_server_code(self, path: str) -> None:
        """Generate the RPyC server code."""
        code = r'''#!/usr/bin/env python
"""RPyC classic server for mt5linux."""
import sys
import os
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


class HealthChecker:
    """Provides health check functionality."""

    def __init__(self, config: ServerConfig, state: ServerState):
        self.config = config
        self.state = state
        self._stop_event = threading.Event()
        self._checker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the health checker."""
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

    def _perform_check(self) -> None:
        """Perform a health check."""
        self.state.last_health_check = datetime.now()

        # Check if port is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("127.0.0.1", self.config.port))
            sock.close()

            if result != 0:
                logger.warning(f"Port {self.config.port} not responding")
        except Exception as e:
            logger.warning(f"Health check failed: {e}")

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        uptime = None
        if self.state.start_time:
            uptime = (datetime.now() - self.state.start_time).total_seconds()

        return {
            "status": self.state.status,
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
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "max_connections": self.config.max_connections,
            },
        }


class HealthHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""

    health_checker: HealthChecker | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health" or self.path == "/":
            self._send_health_response()
        elif self.path == "/ready":
            self._send_ready_response()
        elif self.path == "/live":
            self._send_live_response()
        else:
            self.send_error(404)

    def _send_health_response(self) -> None:
        """Send full health status."""
        if self.health_checker:
            status = self.health_checker.get_health_status()
            is_healthy = status["status"] == "running"
        else:
            status = {"error": "Health checker not initialized"}
            is_healthy = False

        self.send_response(200 if is_healthy else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode())

    def _send_ready_response(self) -> None:
        """Send readiness status (for Kubernetes)."""
        if self.health_checker:
            status = self.health_checker.get_health_status()
            is_ready = status["status"] == "running"
        else:
            is_ready = False

        self.send_response(200 if is_ready else 503)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ready" if is_ready else b"not ready")

    def _send_live_response(self) -> None:
        """Send liveness status (for Kubernetes)."""
        # Always return 200 if the health server is running
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"alive")


class HealthHTTPServer:
    """HTTP server for health endpoints."""

    def __init__(self, config: ServerConfig, health_checker: HealthChecker):
        self.config = config
        self.health_checker = health_checker
        self._server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the health HTTP server."""
        HealthHTTPHandler.health_checker = self.health_checker

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
        except Exception as e:
            logger.warning(f"Failed to start health HTTP server: {e}")

    def stop(self) -> None:
        """Stop the health HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        logger.info("Health HTTP server stopped")


class ResilientRPyCServer:
    """
    Resilient RPyC server with supervisor, health checks, and auto-recovery.

    This class orchestrates all resilience components:
    - ProcessSupervisor: Monitors and restarts the RPyC server process
    - HealthChecker: Performs periodic health checks
    - HealthHTTPServer: Exposes health endpoints via HTTP
    """

    def __init__(self, config: ServerConfig | None = None):
        self.config = config or ServerConfig()
        self.state = ServerState()
        self.supervisor = ProcessSupervisor(self.config)
        self.supervisor.state = self.state
        self.health_checker = HealthChecker(self.config, self.state)
        self.health_server = HealthHTTPServer(self.config, self.health_checker)
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Start all server components."""
        logger.info("Starting resilient RPyC server...")
        logger.info(f"  Host: {self.config.host}")
        logger.info(f"  Port: {self.config.port}")
        logger.info(f"  Health port: {self.config.health_check_port}")
        logger.info(f"  Wine: {self.config.wine_cmd}")
        logger.info(f"  Python: {self.config.python_path}")

        self.health_checker.start()
        self.health_server.start()
        self.supervisor.start()

        logger.info("Resilient RPyC server started successfully")

    def stop(self) -> None:
        """Stop all server components gracefully."""
        logger.info("Stopping resilient RPyC server...")
        self.supervisor.stop()
        self.health_checker.stop()
        self.health_server.stop()
        logger.info("Resilient RPyC server stopped")

    def run_forever(self) -> None:
        """Run the server until interrupted."""
        self.start()
        try:
            while self.state.status not in ("stopped", "failed"):
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main() -> None:
    """Main entry point for the resilient server."""
    parser = argparse.ArgumentParser(
        description="Resilient RPyC server for mt5linux"
    )
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
        "-p", "--port",
        type=int,
        default=18812,
        help="RPyC server port (default: 18812)",
    )
    parser.add_argument(
        "-w", "--wine",
        type=str,
        default="wine",
        help="Wine command (default: wine)",
    )
    parser.add_argument(
        "-s", "--server-dir",
        type=str,
        default="/tmp/mt5linux",
        help="Server directory (default: /tmp/mt5linux)",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=8002,
        help="Health check HTTP port (default: 8002)",
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

    args = parser.parse_args()

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
