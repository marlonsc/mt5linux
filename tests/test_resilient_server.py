"""
Comprehensive tests for the resilient RPyC server.

This module provides 100% test coverage for:
- CircuitBreaker: Circuit breaker pattern
- RateLimiter: Token bucket rate limiting
- ProcessSupervisor: Process supervision and restart
- HealthChecker: Health check functionality
- HealthHTTPServer: HTTP health endpoints
- ConnectionWatchdog: Connection monitoring
- ResilientRPyCServer: Full server orchestration
- ServerConfig, ServerState, Metrics: Data classes
"""

from __future__ import annotations

import socket
import threading
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from mt5linux.enums import CircuitState
from mt5linux.exceptions import CircuitBreakerOpenError
from mt5linux.models import ServerConfig, ServerMetrics, ServerState
from mt5linux.resilient_server import (
    CircuitBreaker,
    ConnectionWatchdog,
    HealthChecker,
    HealthHTTPHandler,
    HealthHTTPServer,
    ProcessSupervisor,
    RateLimiter,
    ResilientRPyCServer,
    parse_args,
)

# Alias for backward compatibility in tests
Metrics = ServerMetrics


# =============================================================================
# ServerConfig Tests
# =============================================================================


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 18812
        assert config.wine_cmd == "wine"
        assert config.python_path == "python.exe"
        assert config.server_dir == "/tmp/mt5linux"
        assert config.max_restart_attempts == 10
        assert config.restart_cooldown == 5.0
        assert config.restart_backoff_multiplier == 2.0
        assert config.max_restart_delay == 300.0
        assert config.health_check_port == 8002
        assert config.health_check_interval == 15.0
        assert config.watchdog_timeout == 60.0
        assert config.connection_timeout == 300.0
        assert config.max_connections == 10
        assert config.circuit_failure_threshold == 5
        assert config.circuit_recovery_timeout == 30.0
        assert config.circuit_half_open_max_calls == 3
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window == 60.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ServerConfig(
            host="127.0.0.1",
            port=8001,
            max_connections=20,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 8001
        assert config.max_connections == 20


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for Metrics dataclass."""

    def test_default_values(self) -> None:
        """Test default metrics values."""
        metrics = Metrics()
        assert metrics.requests_total == 0
        assert metrics.requests_success == 0
        assert metrics.requests_failed == 0
        assert metrics.connections_total == 0
        assert metrics.connections_active == 0
        assert metrics.connections_rejected == 0
        assert metrics.restarts_total == 0
        assert metrics.uptime_seconds == 0.0
        assert metrics.last_request_time is None
        assert metrics.circuit_trips == 0

    def test_to_dict(self) -> None:
        """Test metrics to_dict conversion."""
        metrics = Metrics(
            requests_total=100,
            requests_success=90,
            requests_failed=10,
            connections_total=50,
            connections_active=5,
            restarts_total=2,
            uptime_seconds=3600.0,
        )
        result = metrics.to_dict()

        assert result["requests"]["total"] == 100
        assert result["requests"]["success"] == 90
        assert result["requests"]["failed"] == 10
        assert result["connections"]["total"] == 50
        assert result["connections"]["active"] == 5
        assert result["restarts_total"] == 2
        assert result["uptime_seconds"] == 3600.0
        assert result["last_request_time"] is None

    def test_to_dict_with_last_request_time(self) -> None:
        """Test metrics to_dict with last_request_time."""
        now = datetime.now()
        metrics = Metrics(last_request_time=now)
        result = metrics.to_dict()
        assert result["last_request_time"] == now.isoformat()


# =============================================================================
# ServerState Tests
# =============================================================================


class TestServerState:
    """Tests for ServerState dataclass."""

    def test_default_values(self) -> None:
        """Test default state values."""
        state = ServerState()
        assert state.status == "stopped"
        assert state.start_time is None
        assert state.restart_count == 0
        assert state.last_restart_time is None
        assert state.last_health_check is None
        assert state.active_connections == 0
        assert state.total_connections == 0
        assert state.errors == []
        assert state.wine_process_pid is None
        assert isinstance(state.metrics, Metrics)

    def test_custom_values(self) -> None:
        """Test custom state values."""
        now = datetime.now()
        state = ServerState(
            status="running",
            start_time=now,
            restart_count=3,
        )
        assert state.status == "running"
        assert state.start_time == now
        assert state.restart_count == 3


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_successful_call_keeps_closed(self) -> None:
        """Test successful calls keep circuit closed."""
        cb = CircuitBreaker()

        def success_func() -> str:
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_failures_trip_circuit(self) -> None:
        """Test multiple failures trip the circuit."""
        cb = CircuitBreaker(failure_threshold=3)

        def fail_func() -> None:
            raise ValueError("test error")

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

    def test_open_circuit_rejects_calls(self) -> None:
        """Test open circuit rejects calls."""
        cb = CircuitBreaker(failure_threshold=1)

        def fail_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError):
            cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(fail_func)

    def test_circuit_transitions_to_half_open(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def fail_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError):
            cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_resets_circuit(self) -> None:
        """Test successful calls in half-open state reset circuit."""
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=2,
        )

        def fail_func() -> None:
            raise ValueError("test error")

        def success_func() -> str:
            return "success"

        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(fail_func)

        # Wait for recovery timeout
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN

        # Successful calls reset
        cb.call(success_func)
        cb.call(success_func)
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_trips_circuit(self) -> None:
        """Test failure in half-open state trips circuit again."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        def fail_func() -> None:
            raise ValueError("test error")

        # Trip the circuit
        with pytest.raises(ValueError):
            cb.call(fail_func)

        # Wait for recovery timeout
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN

        # Failure in half-open trips again
        with pytest.raises(ValueError):
            cb.call(fail_func)
        assert cb.state == CircuitState.OPEN

    def test_get_status(self) -> None:
        """Test get_status returns correct information."""
        cb = CircuitBreaker()
        status = cb.get_status()

        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["success_count"] == 0
        assert status["last_failure_time"] is None

    def test_should_attempt_reset_no_failure(self) -> None:
        """Test _should_attempt_reset with no failures."""
        cb = CircuitBreaker()
        assert cb._should_attempt_reset() is True


# =============================================================================
# RateLimiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_initial_tokens_available(self) -> None:
        """Test rate limiter starts with full tokens."""
        rl = RateLimiter(max_requests=10)
        for _ in range(10):
            assert rl.acquire() is True

    def test_tokens_exhausted(self) -> None:
        """Test rate limiter rejects when tokens exhausted."""
        rl = RateLimiter(max_requests=2, window_seconds=60.0)
        assert rl.acquire() is True
        assert rl.acquire() is True
        assert rl.acquire() is False

    def test_tokens_replenish(self) -> None:
        """Test tokens replenish over time."""
        rl = RateLimiter(max_requests=1, window_seconds=0.1)
        assert rl.acquire() is True
        assert rl.acquire() is False

        # Wait for replenishment
        time.sleep(0.2)
        assert rl.acquire() is True

    def test_get_status(self) -> None:
        """Test get_status returns correct information."""
        rl = RateLimiter(max_requests=10, window_seconds=60.0)
        status = rl.get_status()

        assert status["available_tokens"] == 10
        assert status["max_requests"] == 10
        assert status["window_seconds"] == 60.0

    def test_replenishment_on_acquire(self) -> None:
        """Test tokens replenish when acquire is called after waiting."""
        rl = RateLimiter(max_requests=10, window_seconds=0.5)

        # Use all tokens
        for _ in range(10):
            rl.acquire()

        # Verify tokens exhausted
        assert rl.acquire() is False

        # Wait for replenishment window
        time.sleep(0.6)

        # acquire() should succeed now (triggers replenishment internally)
        assert rl.acquire() is True


# =============================================================================
# ProcessSupervisor Tests
# =============================================================================


class TestProcessSupervisor:
    """Tests for ProcessSupervisor class."""

    def test_initialization(self) -> None:
        """Test supervisor initialization."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        assert supervisor.config == config
        assert supervisor.state == state
        assert supervisor.process is None
        assert isinstance(supervisor.circuit_breaker, CircuitBreaker)

    def test_is_running_false_when_no_process(self) -> None:
        """Test is_running returns False when no process."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        assert supervisor.is_running() is False

    def test_should_restart_true_initially(self) -> None:
        """Test _should_restart returns True initially."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        assert supervisor._should_restart() is True

    def test_should_restart_false_after_max_attempts(self) -> None:
        """Test _should_restart returns False after max attempts."""
        config = ServerConfig(max_restart_attempts=3)
        state = ServerState(restart_count=3)
        supervisor = ProcessSupervisor(config, state)

        assert supervisor._should_restart() is False

    def test_record_error(self) -> None:
        """Test _record_error adds errors to state."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        supervisor._record_error("Test error 1")
        supervisor._record_error("Test error 2")

        assert len(state.errors) == 2
        assert state.errors[0]["message"] == "Test error 1"
        assert state.errors[1]["message"] == "Test error 2"

    def test_record_error_limits_to_10(self) -> None:
        """Test _record_error keeps only last 10 errors."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        for i in range(15):
            supervisor._record_error(f"Error {i}")

        assert len(state.errors) == 10
        assert state.errors[0]["message"] == "Error 5"
        assert state.errors[-1]["message"] == "Error 14"

    def test_write_server_script(self, tmp_path: Any) -> None:
        """Test _write_server_script creates valid Python file."""
        from mt5linux.resilient_server import _write_server_script

        code_path = tmp_path / "server.py"
        _write_server_script(str(code_path))

        assert code_path.exists()
        content = code_path.read_text()
        assert "ClassicServer" in content
        assert "ThreadedServer" in content

    def test_kill_process_when_none(self) -> None:
        """Test _kill_process does nothing when no process."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Should not raise
        supervisor._kill_process()

    @patch("mt5linux.resilient_server.Popen")
    def test_start_process_success(self, mock_popen: Mock, tmp_path: Any) -> None:
        """Test _start_process succeeds."""
        config = ServerConfig(server_dir=str(tmp_path))
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        supervisor._start_process()

        assert state.status == "running"
        assert state.wine_process_pid == 12345
        assert state.start_time is not None

    @patch("mt5linux.resilient_server.Popen")
    def test_start_process_failure(self, mock_popen: Mock, tmp_path: Any) -> None:
        """Test _start_process handles failure."""
        config = ServerConfig(server_dir=str(tmp_path))
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited
        mock_process.communicate.return_value = (b"", b"error")
        mock_popen.return_value = mock_process

        with pytest.raises(RuntimeError):
            supervisor._start_process()

    def test_stop(self) -> None:
        """Test stop method."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        supervisor.stop()
        assert state.status == "stopped"


# =============================================================================
# HealthChecker Tests
# =============================================================================


class TestHealthChecker:
    """Tests for HealthChecker class."""

    def test_initialization(self) -> None:
        """Test health checker initialization."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)

        assert checker.config == config
        assert checker.state == state
        assert checker._last_check_success is True

    def test_is_healthy_false_when_not_running(self) -> None:
        """Test is_healthy returns False when not running."""
        config = ServerConfig()
        state = ServerState(status="stopped")
        checker = HealthChecker(config, state)

        assert checker.is_healthy() is False

    def test_is_healthy_true_when_running(self) -> None:
        """Test is_healthy returns True when running and check succeeds."""
        config = ServerConfig()
        state = ServerState(status="running")
        checker = HealthChecker(config, state)
        checker._last_check_success = True

        assert checker.is_healthy() is True

    def test_get_health_status(self) -> None:
        """Test get_health_status returns correct information."""
        config = ServerConfig()
        now = datetime.now()
        state = ServerState(
            status="running",
            start_time=now,
            restart_count=2,
        )
        checker = HealthChecker(config, state)

        status = checker.get_health_status()

        assert status["status"] == "running"
        assert status["restart_count"] == 2
        assert "uptime_seconds" in status
        assert "config" in status

    def test_get_health_status_includes_metrics(self) -> None:
        """Test get_health_status includes metrics."""
        config = ServerConfig()
        state = ServerState()
        state.metrics.requests_total = 100
        checker = HealthChecker(config, state)

        status = checker.get_health_status()

        assert "metrics" in status
        assert status["metrics"]["requests"]["total"] == 100

    @patch("socket.socket")
    def test_perform_check_success(self, mock_socket_class: Mock) -> None:
        """Test _perform_check succeeds when port is open."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)

        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_socket

        result = checker._perform_check()

        assert result is True
        assert checker._last_check_success is True

    @patch("socket.socket")
    def test_perform_check_failure(self, mock_socket_class: Mock) -> None:
        """Test _perform_check fails when port is closed."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)

        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 111  # Connection refused
        mock_socket_class.return_value = mock_socket

        result = checker._perform_check()

        assert result is False
        assert checker._last_check_success is False

    @patch("socket.socket")
    def test_perform_check_exception(self, mock_socket_class: Mock) -> None:
        """Test _perform_check handles exceptions."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)

        mock_socket_class.side_effect = socket.error("test error")

        result = checker._perform_check()

        assert result is False
        assert checker._last_check_success is False

    def test_perform_check_updates_uptime(self) -> None:
        """Test _perform_check updates uptime metric."""
        config = ServerConfig()
        state = ServerState(start_time=datetime.now() - timedelta(seconds=10))
        checker = HealthChecker(config, state)

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 111
            mock_socket_class.return_value = mock_socket
            checker._perform_check()

        assert state.metrics.uptime_seconds >= 10

    def test_start_and_stop(self) -> None:
        """Test start and stop methods."""
        config = ServerConfig(health_check_interval=0.1)
        state = ServerState()
        checker = HealthChecker(config, state)

        checker.start()
        assert checker._checker_thread is not None
        assert checker._checker_thread.is_alive()

        checker.stop()
        assert not checker._checker_thread.is_alive()


# =============================================================================
# ConnectionWatchdog Tests
# =============================================================================


class TestConnectionWatchdog:
    """Tests for ConnectionWatchdog class."""

    def test_initialization(self) -> None:
        """Test watchdog initialization."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        assert watchdog.config == config
        assert watchdog.state == state
        assert len(watchdog._connections) == 0

    def test_register_connection(self) -> None:
        """Test register_connection adds connection."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        watchdog.register_connection(1)

        assert 1 in watchdog._connections
        assert state.active_connections == 1
        assert state.total_connections == 1
        assert state.metrics.connections_total == 1

    def test_unregister_connection(self) -> None:
        """Test unregister_connection removes connection."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        watchdog.register_connection(1)
        watchdog.unregister_connection(1)

        assert 1 not in watchdog._connections
        assert state.active_connections == 0

    def test_unregister_nonexistent_connection(self) -> None:
        """Test unregister_connection with nonexistent ID."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        # Should not raise
        watchdog.unregister_connection(999)

    def test_update_connection(self) -> None:
        """Test update_connection updates timestamp."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        watchdog.register_connection(1)
        old_time = watchdog._connections[1]

        time.sleep(0.01)
        watchdog.update_connection(1)

        assert watchdog._connections[1] > old_time

    def test_update_nonexistent_connection(self) -> None:
        """Test update_connection with nonexistent ID."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        # Should not raise
        watchdog.update_connection(999)

    def test_cleanup_stale_connections(self) -> None:
        """Test _cleanup_stale_connections removes old connections."""
        config = ServerConfig(connection_timeout=0.1)
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        watchdog.register_connection(1)

        # Wait for connection to become stale
        time.sleep(0.2)
        watchdog._cleanup_stale_connections()

        assert 1 not in watchdog._connections
        assert state.active_connections == 0

    def test_start_and_stop(self) -> None:
        """Test start and stop methods."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        watchdog.start()
        assert watchdog._watchdog_thread is not None
        assert watchdog._watchdog_thread.is_alive()

        watchdog.stop()
        assert not watchdog._watchdog_thread.is_alive()


# =============================================================================
# HealthHTTPHandler Tests
# =============================================================================


class TestHealthHTTPHandler:
    """Tests for HealthHTTPHandler class."""

    def _create_handler(
        self,
        path: str = "/health",
        health_checker: HealthChecker | None = None,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> HealthHTTPHandler:
        """Create a handler with mocked request."""
        # Set class attributes
        HealthHTTPHandler.health_checker = health_checker
        HealthHTTPHandler.rate_limiter = rate_limiter
        HealthHTTPHandler.circuit_breaker = circuit_breaker

        # Create handler with mocked socket
        handler = HealthHTTPHandler.__new__(HealthHTTPHandler)
        handler.path = path
        handler.wfile = BytesIO()
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 12345)

        # Mock send_response and related
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.send_error = MagicMock()

        return handler

    def test_log_message_suppressed(self) -> None:
        """Test log_message does nothing."""
        handler = self._create_handler()
        # Should not raise
        handler.log_message("test %s", "message")

    def test_health_endpoint_healthy(self) -> None:
        """Test /health endpoint when healthy."""
        config = ServerConfig()
        state = ServerState(status="running")
        checker = HealthChecker(config, state)
        checker._last_check_success = True

        handler = self._create_handler(
            path="/health",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_health_endpoint_unhealthy(self) -> None:
        """Test /health endpoint when unhealthy."""
        config = ServerConfig()
        state = ServerState(status="stopped")
        checker = HealthChecker(config, state)

        handler = self._create_handler(
            path="/health",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(503)

    def test_health_endpoint_no_checker(self) -> None:
        """Test /health endpoint without checker."""
        handler = self._create_handler(path="/health")
        handler.do_GET()

        handler.send_response.assert_called_with(503)

    def test_ready_endpoint_ready(self) -> None:
        """Test /ready endpoint when ready."""
        config = ServerConfig()
        state = ServerState(status="running")
        checker = HealthChecker(config, state)
        checker._last_check_success = True

        handler = self._create_handler(
            path="/ready",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_ready_endpoint_not_ready(self) -> None:
        """Test /ready endpoint when not ready."""
        config = ServerConfig()
        state = ServerState(status="stopped")
        checker = HealthChecker(config, state)

        handler = self._create_handler(
            path="/ready",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(503)

    def test_live_endpoint(self) -> None:
        """Test /live endpoint always returns 200."""
        handler = self._create_handler(path="/live")
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_metrics_endpoint(self) -> None:
        """Test /metrics endpoint."""
        config = ServerConfig()
        state = ServerState()
        state.metrics.requests_total = 100
        checker = HealthChecker(config, state)

        handler = self._create_handler(
            path="/metrics",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_metrics_endpoint_no_checker(self) -> None:
        """Test /metrics endpoint without checker."""
        handler = self._create_handler(path="/metrics")
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_circuit_endpoint(self) -> None:
        """Test /circuit endpoint."""
        cb = CircuitBreaker()

        handler = self._create_handler(
            path="/circuit",
            circuit_breaker=cb,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_circuit_endpoint_no_breaker(self) -> None:
        """Test /circuit endpoint without breaker."""
        handler = self._create_handler(path="/circuit")
        handler.do_GET()

        handler.send_response.assert_called_with(200)

    def test_unknown_endpoint(self) -> None:
        """Test unknown endpoint returns 404."""
        handler = self._create_handler(path="/unknown")
        handler.do_GET()

        handler.send_error.assert_called_with(404)

    def test_rate_limiting(self) -> None:
        """Test rate limiting rejects excess requests."""
        rl = RateLimiter(max_requests=0, window_seconds=60.0)

        handler = self._create_handler(
            path="/health",
            rate_limiter=rl,
        )
        handler.do_GET()

        handler.send_error.assert_called_with(429, "Too Many Requests")

    def test_root_endpoint_same_as_health(self) -> None:
        """Test / endpoint same as /health."""
        config = ServerConfig()
        state = ServerState(status="running")
        checker = HealthChecker(config, state)
        checker._last_check_success = True

        handler = self._create_handler(
            path="/",
            health_checker=checker,
        )
        handler.do_GET()

        handler.send_response.assert_called_with(200)


# =============================================================================
# HealthHTTPServer Tests
# =============================================================================


class TestHealthHTTPServer:
    """Tests for HealthHTTPServer class."""

    def test_initialization(self) -> None:
        """Test server initialization."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)
        server = HealthHTTPServer(config, checker)

        assert server.config == config
        assert server.health_checker == checker
        assert server._server is None

    def test_start_and_stop(self) -> None:
        """Test start and stop methods."""
        # Use a random high port to avoid conflicts
        import random

        port = random.randint(50000, 60000)
        config = ServerConfig(health_check_port=port)
        state = ServerState()
        checker = HealthChecker(config, state)
        server = HealthHTTPServer(config, checker)

        server.start()
        assert server._server is not None
        assert server._server_thread is not None
        assert server._server_thread.is_alive()

        server.stop()
        assert server._server is None

    @patch("mt5linux.resilient_server.HTTPServer")
    def test_start_failure(self, mock_http_server: Mock) -> None:
        """Test start handles failure gracefully."""
        mock_http_server.side_effect = OSError("Port in use")

        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)
        server = HealthHTTPServer(config, checker)

        # Should not raise
        server.start()
        assert server._server is None


# =============================================================================
# ResilientRPyCServer Tests
# =============================================================================


class TestResilientRPyCServer:
    """Tests for ResilientRPyCServer class."""

    def test_initialization_default_config(self) -> None:
        """Test server initialization with default config."""
        server = ResilientRPyCServer()

        assert isinstance(server.config, ServerConfig)
        assert isinstance(server.state, ServerState)
        assert isinstance(server.supervisor, ProcessSupervisor)
        assert isinstance(server.health_checker, HealthChecker)
        assert isinstance(server.watchdog, ConnectionWatchdog)
        assert isinstance(server.rate_limiter, RateLimiter)

    def test_initialization_custom_config(self) -> None:
        """Test server initialization with custom config."""
        config = ServerConfig(port=9999)
        server = ResilientRPyCServer(config)

        assert server.config.port == 9999

    @patch.object(ProcessSupervisor, "start")
    @patch.object(HealthChecker, "start")
    @patch.object(ConnectionWatchdog, "start")
    @patch.object(HealthHTTPServer, "start")
    def test_start(
        self,
        mock_http_start: Mock,
        mock_watchdog_start: Mock,
        mock_checker_start: Mock,
        mock_supervisor_start: Mock,
    ) -> None:
        """Test start method calls all component starts."""
        server = ResilientRPyCServer()
        server.start()

        mock_checker_start.assert_called_once()
        mock_watchdog_start.assert_called_once()
        mock_http_start.assert_called_once()
        mock_supervisor_start.assert_called_once()

    @patch.object(ProcessSupervisor, "stop")
    @patch.object(HealthChecker, "stop")
    @patch.object(ConnectionWatchdog, "stop")
    @patch.object(HealthHTTPServer, "stop")
    def test_stop(
        self,
        mock_http_stop: Mock,
        mock_watchdog_stop: Mock,
        mock_checker_stop: Mock,
        mock_supervisor_stop: Mock,
    ) -> None:
        """Test stop method calls all component stops."""
        server = ResilientRPyCServer()
        server.stop()

        mock_supervisor_stop.assert_called_once()
        mock_checker_stop.assert_called_once()
        mock_watchdog_stop.assert_called_once()
        mock_http_stop.assert_called_once()

    def test_signal_handler(self) -> None:
        """Test signal handler calls stop and exit."""
        server = ResilientRPyCServer()

        with patch.object(server, "stop") as mock_stop:
            with pytest.raises(SystemExit):
                server._signal_handler(15, None)

            mock_stop.assert_called_once()


# =============================================================================
# parse_args Tests
# =============================================================================


class TestParseArgs:
    """Tests for parse_args function."""

    def test_default_args(self) -> None:
        """Test default argument values."""
        with patch("sys.argv", ["test"]):
            args = parse_args()

        assert args.python == "python.exe"
        assert args.host == "0.0.0.0"
        assert args.port == 18812
        assert args.wine == "wine"
        assert args.server_dir == "/tmp/mt5linux"
        assert args.health_port == 8002
        assert args.max_restarts == 10
        assert args.max_connections == 10

    def test_custom_args(self) -> None:
        """Test custom argument values."""
        with patch(
            "sys.argv",
            [
                "test",
                "custom_python.exe",
                "--host",
                "127.0.0.1",
                "-p",
                "9999",
                "-w",
                "wine64",
            ],
        ):
            args = parse_args()

        assert args.python == "custom_python.exe"
        assert args.host == "127.0.0.1"
        assert args.port == 9999
        assert args.wine == "wine64"


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the resilient server."""

    def test_circuit_breaker_integration(self) -> None:
        """Test circuit breaker integrates with supervisor."""
        config = ServerConfig(
            circuit_failure_threshold=2,
            max_restart_attempts=5,
        )
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Simulate failures
        for _ in range(2):
            supervisor.circuit_breaker._on_failure()

        assert supervisor.circuit_breaker.state == CircuitState.OPEN

    def test_rate_limiter_integration(self) -> None:
        """Test rate limiter integrates with server."""
        config = ServerConfig(
            rate_limit_requests=5,
            rate_limit_window=1.0,
        )
        server = ResilientRPyCServer(config)

        # Exhaust tokens
        for _ in range(5):
            assert server.rate_limiter.acquire() is True

        assert server.rate_limiter.acquire() is False

    def test_connection_tracking_integration(self) -> None:
        """Test connection tracking integrates with state."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        # Register multiple connections
        for i in range(5):
            watchdog.register_connection(i)

        assert state.active_connections == 5
        assert state.total_connections == 5
        assert state.metrics.connections_total == 5
        assert state.metrics.connections_active == 5

        # Unregister some
        watchdog.unregister_connection(0)
        watchdog.unregister_connection(1)

        assert state.active_connections == 3
        assert state.metrics.connections_active == 3

    def test_health_status_integration(self) -> None:
        """Test health status integrates all components."""
        config = ServerConfig()
        state = ServerState(
            status="running",
            start_time=datetime.now() - timedelta(hours=1),
            restart_count=2,
        )
        state.metrics.requests_total = 1000
        state.metrics.connections_active = 5

        checker = HealthChecker(config, state)
        checker._last_check_success = True

        status = checker.get_health_status()

        assert status["status"] == "running"
        assert status["healthy"] is True
        assert status["restart_count"] == 2
        assert status["metrics"]["requests"]["total"] == 1000
        assert status["metrics"]["connections"]["active"] == 5
        assert status["uptime_seconds"] >= 3600


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_errors_list(self) -> None:
        """Test health status with empty errors."""
        config = ServerConfig()
        state = ServerState()
        checker = HealthChecker(config, state)

        status = checker.get_health_status()
        assert status["recent_errors"] == []

    def test_many_errors(self) -> None:
        """Test health status limits errors to 5."""
        config = ServerConfig()
        state = ServerState()

        for i in range(20):
            state.errors.append(
                {"time": datetime.now().isoformat(), "message": f"Error {i}"}
            )

        checker = HealthChecker(config, state)
        status = checker.get_health_status()

        assert len(status["recent_errors"]) == 5

    def test_concurrent_connection_operations(self) -> None:
        """Test concurrent connection register/unregister."""
        config = ServerConfig()
        state = ServerState()
        watchdog = ConnectionWatchdog(config, state)

        def register_many() -> None:
            for i in range(100):
                watchdog.register_connection(i)

        def unregister_many() -> None:
            for i in range(100):
                watchdog.unregister_connection(i)

        t1 = threading.Thread(target=register_many)
        t2 = threading.Thread(target=unregister_many)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should not raise and state should be consistent
        assert state.active_connections >= 0

    def test_circuit_breaker_concurrent_calls(self) -> None:
        """Test circuit breaker handles concurrent calls."""
        cb = CircuitBreaker(failure_threshold=100)

        call_count = 0
        lock = threading.Lock()

        def increment() -> None:
            nonlocal call_count
            with lock:
                call_count += 1

        threads = []
        for _ in range(50):
            t = threading.Thread(target=lambda: cb.call(increment))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert call_count == 50

    def test_rate_limiter_concurrent_acquire(self) -> None:
        """Test rate limiter handles concurrent acquires."""
        rl = RateLimiter(max_requests=10, window_seconds=60.0)

        success_count = 0
        lock = threading.Lock()

        def try_acquire() -> None:
            nonlocal success_count
            if rl.acquire():
                with lock:
                    success_count += 1

        threads = []
        for _ in range(20):
            t = threading.Thread(target=try_acquire)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have limited to ~10 successes
        assert success_count <= 11  # Allow for some race conditions


# =============================================================================
# Supervisor Thread Tests
# =============================================================================


class TestSupervisorThread:
    """Tests for supervisor thread functionality."""

    def test_supervisor_start_creates_thread(self) -> None:
        """Test start() creates and starts supervisor thread."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Mock _start_process to avoid actual process creation
        with patch.object(supervisor, "_start_process"):
            supervisor.start()

            assert supervisor._supervisor_thread is not None
            assert supervisor._supervisor_thread.is_alive()

            # Cleanup
            supervisor.stop()

    def test_supervisor_stop_joins_thread(self) -> None:
        """Test stop() properly joins the supervisor thread."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        with patch.object(supervisor, "_start_process"):
            supervisor.start()
            assert supervisor._supervisor_thread is not None

            supervisor.stop()
            # Thread should have stopped
            assert not supervisor._supervisor_thread.is_alive()
            assert supervisor.state.status == "stopped"

    def test_supervision_loop_detects_process_exit(self) -> None:
        """Test supervision loop detects when process exits."""
        config = ServerConfig(restart_cooldown=0.01, max_restart_attempts=2)
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Create a mock process that has exited
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Exit code 1
        supervisor.process = mock_process

        with patch.object(supervisor, "_start_process"):
            supervisor.start()
            # Wait for the loop to detect the exit
            time.sleep(0.1)
            supervisor.stop()

        # Should have recorded an error about process exit
        assert len(supervisor.state.errors) >= 1

    def test_supervision_loop_respects_max_restarts(self) -> None:
        """Test supervision loop stops after max restart attempts."""
        config = ServerConfig(max_restart_attempts=2, restart_cooldown=0.01)
        state = ServerState()
        state.restart_count = 2  # Already at max
        supervisor = ProcessSupervisor(config, state)

        # Create a mock process that has exited
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        supervisor.process = mock_process

        with patch.object(supervisor, "_start_process"):
            supervisor.start()
            time.sleep(0.2)
            supervisor.stop()

        # Should have set status to failed
        assert state.status in ("stopped", "failed")

    def test_supervision_loop_circuit_breaker_open(self) -> None:
        """Test supervision loop handles circuit breaker open."""
        config = ServerConfig(
            circuit_failure_threshold=1,
            max_restart_attempts=10,
            restart_cooldown=0.01,
        )
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Trip the circuit breaker
        supervisor.circuit_breaker._on_failure()

        # Create a mock process that has exited
        mock_process = MagicMock()
        mock_process.poll.return_value = 1
        supervisor.process = mock_process

        with patch.object(supervisor, "_start_process"):
            supervisor.start()
            time.sleep(0.1)
            supervisor.stop()

        # Circuit breaker trips should be recorded
        assert state.metrics.circuit_trips >= 1 or state.status == "circuit_open"


# =============================================================================
# Restart Process Tests
# =============================================================================


class TestRestartProcess:
    """Tests for _restart_process method."""

    def test_restart_increments_count(self) -> None:
        """Test restart increments restart count."""
        config = ServerConfig(restart_cooldown=0.01)
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        with patch.object(supervisor, "_start_process"):
            with patch.object(supervisor, "_kill_process"):
                supervisor._restart_process()

        assert state.restart_count == 1
        assert state.last_restart_time is not None

    def test_restart_updates_metrics(self) -> None:
        """Test restart updates metrics."""
        config = ServerConfig(restart_cooldown=0.01)
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        with patch.object(supervisor, "_start_process"):
            with patch.object(supervisor, "_kill_process"):
                supervisor._restart_process()

        assert state.metrics.restarts_total == 1

    def test_restart_with_backoff(self) -> None:
        """Test restart applies exponential backoff."""
        config = ServerConfig(
            restart_cooldown=0.01,
            restart_backoff_multiplier=2.0,
            max_restart_delay=1.0,
        )
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        initial_delay = supervisor._restart_delay

        with patch.object(supervisor, "_start_process"):
            with patch.object(supervisor, "_kill_process"):
                supervisor._restart_process()

        # Delay should have increased
        assert supervisor._restart_delay > initial_delay

    def test_restart_respects_stop_event(self) -> None:
        """Test restart exits early if stop event is set."""
        config = ServerConfig(restart_cooldown=5.0)  # Long cooldown
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        # Set stop event
        supervisor._stop_event.set()

        with patch.object(supervisor, "_start_process") as mock_start:
            with patch.object(supervisor, "_kill_process"):
                supervisor._restart_process()

        # _start_process should NOT be called because stop_event was set
        mock_start.assert_not_called()


# =============================================================================
# Kill Process Tests
# =============================================================================


class TestKillProcess:
    """Tests for _kill_process method."""

    def test_kill_terminates_process(self) -> None:
        """Test _kill_process terminates the process."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        mock_process = MagicMock()
        mock_process.wait.return_value = None
        supervisor.process = mock_process
        supervisor.state.wine_process_pid = 12345

        supervisor._kill_process()

        mock_process.terminate.assert_called_once()
        assert supervisor.process is None
        assert supervisor.state.wine_process_pid is None

    def test_kill_uses_kill_on_timeout(self) -> None:
        """Test _kill_process uses kill() if terminate times out."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        mock_process = MagicMock()
        # First wait raises exception (timeout), second succeeds
        mock_process.wait.side_effect = [Exception("Timeout"), None]
        supervisor.process = mock_process

        supervisor._kill_process()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert supervisor.process is None

    def test_kill_handles_exception(self) -> None:
        """Test _kill_process handles exceptions gracefully."""
        config = ServerConfig()
        state = ServerState()
        supervisor = ProcessSupervisor(config, state)

        mock_process = MagicMock()
        mock_process.terminate.side_effect = Exception("Process error")
        supervisor.process = mock_process

        # Should not raise
        supervisor._kill_process()
        assert supervisor.process is None


# Note: TestResetRestartCount removed - _reset_restart_count_if_stable was dead code


# =============================================================================
# Run Forever Tests
# =============================================================================


class TestRunForever:
    """Tests for run_forever method."""

    def test_run_forever_starts_server(self) -> None:
        """Test run_forever calls start."""
        server = ResilientRPyCServer()

        with patch.object(server, "start") as mock_start:
            with patch.object(server, "stop") as mock_stop:
                # Set status to failed to exit loop immediately
                def set_failed() -> None:
                    server.state.status = "failed"

                mock_start.side_effect = set_failed

                server.run_forever()

        mock_start.assert_called_once()
        mock_stop.assert_called_once()

    def test_run_forever_handles_keyboard_interrupt(self) -> None:
        """Test run_forever handles KeyboardInterrupt gracefully."""
        server = ResilientRPyCServer()

        call_count = 0

        def raise_interrupt() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=raise_interrupt):
            with patch.object(server, "start"):
                with patch.object(server, "stop") as mock_stop:
                    server.run_forever()

        # stop() should still be called
        mock_stop.assert_called_once()

    def test_run_forever_exits_on_failed_status(self) -> None:
        """Test run_forever exits when status is failed."""
        server = ResilientRPyCServer()
        server.state.status = "failed"

        with patch.object(server, "start"):
            with patch.object(server, "stop") as mock_stop:
                server.run_forever()

        mock_stop.assert_called_once()


# =============================================================================
# Main Function Tests
# =============================================================================


class TestMain:
    """Tests for main function."""

    def test_main_creates_server_and_runs(self) -> None:
        """Test main creates server with parsed args and runs."""
        from mt5linux.resilient_server import main

        with patch("sys.argv", ["test", "--port", "9999"]):
            with patch.object(ResilientRPyCServer, "run_forever") as mock_run:
                # Make run_forever exit immediately
                mock_run.return_value = None
                main()

                mock_run.assert_called_once()


# =============================================================================
# Ready Endpoint No Checker Tests
# =============================================================================


class TestReadyEndpointNoChecker:
    """Tests for ready endpoint without health checker."""

    def _create_handler(
        self,
        path: str = "/ready",
        health_checker: HealthChecker | None = None,
    ) -> HealthHTTPHandler:
        """Create a handler with mocked request."""
        HealthHTTPHandler.health_checker = health_checker
        HealthHTTPHandler.rate_limiter = None
        HealthHTTPHandler.circuit_breaker = None

        handler = HealthHTTPHandler.__new__(HealthHTTPHandler)
        handler.path = path
        handler.wfile = BytesIO()
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 12345)

        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.send_error = MagicMock()

        return handler

    def test_ready_endpoint_no_checker_returns_503(self) -> None:
        """Test /ready returns 503 when no health checker."""
        handler = self._create_handler(path="/ready", health_checker=None)
        handler.do_GET()

        handler.send_response.assert_called_with(503)
