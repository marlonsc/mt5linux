"""Test configuration and fixtures.

This module provides fixtures that automatically start and validate
the ISOLATED test container (mt5linux-test on port 28812).

The container is completely isolated from:
- Production (mt5, port 8001)
- tests.(neptor-mt5-test, port 18812)
- mt5docker tests (mt5docker-test, port 48812)

Configuration Source: MT5Config (mt5linux/config.py) - Single Source of Truth
All test_* fields in MT5Config define isolated test environment defaults.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import grpc
import pytest
from dotenv import load_dotenv

from mt5linux import AsyncMetaTrader5, MetaTrader5, mt5_pb2, mt5_pb2_grpc
from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants as c
from tests.constants import TestConstants as tc

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# =============================================================================
# CONFIGURATION - Single Source of Truth: MT5Config
# =============================================================================
# IMPORTANT: Configuration must be loaded BEFORE any functions that use it

# Paths
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
CODEGEN_SCRIPT = PROJECT_ROOT / "scripts" / "codegen_enums.py"

# Load .env.test first (test settings), then .env (credentials override)
# MT5Config will pick up these values via Pydantic Settings env loading
# NOTE: .env.test includes resilience settings (MT5_ENABLE_CIRCUIT_BREAKER=true, etc.)
load_dotenv(PROJECT_ROOT / ".env.test")
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Create single config instance - all values come from here
_config = MT5Config()

# Test container configuration from MT5Config.test_* fields
# These are isolated from production (8001), neptor (18812), mt5docker (48812)
TEST_GRPC_HOST = _config.host
TEST_GRPC_PORT = _config.test_grpc_port
TEST_VNC_PORT = _config.test_vnc_port
TEST_HEALTH_PORT = _config.test_health_port
TEST_CONTAINER_NAME = _config.test_container_name

# Timeouts from MT5Config
STARTUP_TIMEOUT = _config.test_startup_timeout
GRPC_TIMEOUT = _config.test_grpc_timeout

# MT5 credentials (loaded via env vars - no defaults in config)
MT5_LOGIN = int(os.getenv("MT5_LOGIN", tc.DEFAULT_MT5_LOGIN))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str | None = os.getenv("MT5_SERVER")

# Skip message for tests requiring credentials
SKIP_NO_CREDENTIALS = (
    "MT5 credentials not configured. "
    "To run container tests, create .env file with MT5_LOGIN and MT5_PASSWORD."
)

MT5_CONFIG: dict[str, str | int | None] = {
    "host": TEST_GRPC_HOST,
    "port": TEST_GRPC_PORT,
    "login": MT5_LOGIN,
    "password": MT5_PASSWORD,
    "server": MT5_SERVER,
}


# =============================================================================
# TIMING INSTRUMENTATION (matches mt5docker pattern)
# =============================================================================


class _Timer:
    """Simple timer for logging."""

    def __init__(self) -> None:
        """Initialize timer."""
        self.start_time: float = time.time()

    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time


_timer = _Timer()


def _log(message: str, *, phase: bool = False) -> None:
    """Log message to stderr (always visible in pytest)."""
    elapsed = _timer.elapsed()
    if phase:
        sys.stderr.write(f"\n{'=' * 60}\n")
        sys.stderr.write(f"[{elapsed:5.1f}s] PHASE: {message}\n")
        sys.stderr.write(f"{'=' * 60}\n")
    else:
        sys.stderr.write(f"[{elapsed:5.1f}s] {message}\n")
    sys.stderr.flush()


# =============================================================================
# DOCKER AND GRPC HELPERS
# =============================================================================


def _run_command(  # noqa: PLR0913
    cmd: list[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    timeout: int | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with full path resolution.

    Args:
        cmd: Command and arguments. First element is resolved to full path.
        capture_output: If True, capture stdout and stderr.
        text: If True, return output as strings instead of bytes.
        timeout: Timeout in seconds.
        check: If True, raise CalledProcessError on non-zero exit.
        cwd: Working directory.
        env: Environment variables.

    Returns:
        CompletedProcess instance

    Raises:
        FileNotFoundError: If command not found

    """
    cmd_path = shutil.which(cmd[0])
    if cmd_path is None:
        msg = f"Command not found: {cmd[0]}"
        raise FileNotFoundError(msg)
    return subprocess.run(  # noqa: S603
        [cmd_path, *cmd[1:]],
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        check=check,
        cwd=cwd,
        env=env,
    )


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = _run_command(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=tc.SLOW_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def has_mt5_credentials() -> bool:
    """Check if MT5 credentials are configured for integration tests."""
    return bool(
        os.getenv("MT5_LOGIN")
        and os.getenv("MT5_PASSWORD")
        and int(tc.DEFAULT_MT5_LOGIN) != MT5_LOGIN
    )


def is_grpc_service_ready(
    host: str = "localhost",
    port: int | None = None,
    timeout: float = 10.0,
) -> bool:
    """Check if gRPC service is ready (actual MT5 operation, not just HealthCheck).

    The HealthCheck endpoint may return healthy=False even when MT5 is fully
    operational. This function performs an actual MT5 operation (GetConstants)
    to verify true service readiness.

    Args:
        host: gRPC server host.
        port: gRPC server port.
        timeout: Timeout for the GetConstants call.

    Returns:
        True if service responds to GetConstants, False otherwise.

    """
    grpc_port = port or TEST_GRPC_PORT
    _log(f"gRPC check: {host}:{grpc_port} (timeout={timeout:.1f}s)...")
    try:
        channel = grpc.insecure_channel(f"{host}:{grpc_port}")
        stub = mt5_pb2_grpc.MT5ServiceStub(channel)
        # Use GetConstants instead of HealthCheck - more reliable indicator
        # that MT5 is actually ready to handle requests
        response = stub.GetConstants(mt5_pb2.Empty(), timeout=timeout)
        channel.close()
        # Constants response has 'values' field (a map of constant name -> value)
        num_constants = len(response.values)
        _log(f"gRPC check: ready (got {num_constants} constants)")
    except grpc.RpcError as e:
        _log(f"gRPC check: FAILED - {type(e).__name__}")
        return False

    # Service is ready if we got any constants
    return num_constants > 0


def wait_for_grpc_service(
    host: str = "localhost",
    port: int | None = None,
    timeout: int | None = None,
) -> bool:
    """Wait for gRPC service to become ready using progressive backoff.

    This function waits until the gRPC service is fully ready to handle requests,
    not just when the port is listening. The MT5 container needs time to:
    1. Start the gRPC server (port becomes available)
    2. Initialize Wine and MetaTrader5 (service becomes usable)

    Args:
        host: gRPC server host
        port: gRPC server port (default: TEST_GRPC_PORT)
        timeout: Maximum wait time in seconds (default: STARTUP_TIMEOUT)

    Returns:
        True if service is ready, False if timeout reached

    """
    grpc_port = port or TEST_GRPC_PORT
    wait_timeout = timeout or STARTUP_TIMEOUT

    _log(f"WAIT FOR GRPC: max {wait_timeout}s, port {grpc_port}", phase=True)

    start = time.time()
    # Use config values instead of hardcoded defaults
    min_interval = _config.retry_min_interval
    max_interval = _config.retry_max_interval
    current_interval = min_interval
    startup_health_timeout = _config.startup_health_timeout

    attempt = 0
    while time.time() - start < wait_timeout:
        attempt += 1
        remaining = wait_timeout - (time.time() - start)

        _log(f"Attempt {attempt}: checking gRPC (remaining: {remaining:.0f}s)...")

        if is_grpc_service_ready(host, grpc_port, timeout=startup_health_timeout):
            elapsed = time.time() - start
            _log(f"SUCCESS: gRPC ready after {elapsed:.1f}s ({attempt} attempts)")
            return True

        _log(f"Not ready. Waiting {current_interval:.1f}s before retry...")
        time.sleep(current_interval)
        current_interval = min(current_interval * 1.5, max_interval)

    elapsed = time.time() - start
    _log(f"TIMEOUT: gRPC not ready after {elapsed:.1f}s ({attempt} attempts)")
    return False


# =============================================================================
# CONTAINER LIFECYCLE
# =============================================================================


def _is_container_running(name: str | None = None) -> bool:
    """Check if container is running."""
    container_name = name or TEST_CONTAINER_NAME
    _log(f"Checking if container '{container_name}' is running...")
    try:
        result = _run_command(
            ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
            capture_output=True,
            text=True,
            check=False,
        )
        running = bool(result.stdout.strip())
    except FileNotFoundError:
        running = False
    _log(f"Container running: {running}")
    return running


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_and_codegen() -> Generator[None]:  # noqa: C901, PLR0915
    """Start test Docker container and run codegen before all tests.

    This fixture automatically handles Docker availability:
    - If SKIP_DOCKER=1, skips Docker setup entirely
    - If Docker is not available, skips Docker-dependent setup but allows unit tests
    - If container is already running, uses fast-path validation (2s timeout)
    - If container not running, starts it and waits for gRPC service
    - Container is kept running after tests end (no cleanup)

    Uses same patterns as mt5docker:
    - Fast-path validation for already-ready containers
    - Progressive backoff for service readiness
    - Detailed timing instrumentation
    """
    _timer.start_time = time.time()

    _log("CONTAINER VALIDATION START", phase=True)
    _log(f"Container: {TEST_CONTAINER_NAME}")
    _log(f"gRPC port: {TEST_GRPC_PORT}")
    _log(f"Startup timeout: {STARTUP_TIMEOUT}s")

    timing_start = time.time()

    # Check if Docker tests should be skipped
    if os.getenv("SKIP_DOCKER", tc.DEFAULT_SKIP_DOCKER) == "1":
        _log("SKIP_DOCKER=1 - skipping Docker setup")
        yield
        return

    # Check if Docker is available
    if not is_docker_available():
        _log("Docker not available - skipping Docker setup")
        yield
        return

    # PHASE 1: Check if container is running
    _log("PHASE 1: Check container status", phase=True)
    if _is_container_running():
        _log(f"Container '{TEST_CONTAINER_NAME}' is running - will reuse")

        # PHASE 2: Fast-path gRPC check (2s timeout)
        _log("PHASE 2: Fast-path gRPC check (2s timeout)", phase=True)
        if is_grpc_service_ready(
            TEST_GRPC_HOST, TEST_GRPC_PORT, timeout=tc.FAST_TIMEOUT
        ):
            _log("FAST-PATH SUCCESS: gRPC already ready!")
            _log(f"Total validation time: {time.time() - timing_start:.1f}s")
            _run_codegen()
            yield
            return

        # PHASE 3: Wait for gRPC with progressive backoff
        _log("PHASE 3: Wait for gRPC (service not immediately ready)", phase=True)
        if wait_for_grpc_service(TEST_GRPC_HOST, TEST_GRPC_PORT):
            _log(f"Total validation time: {time.time() - timing_start:.1f}s")
            _run_codegen()
            yield
            return

        _log("WARNING: gRPC not ready - will try to restart container")

    # Container not running or not responding - need to start it
    _log("Container NOT running or NOT responding - need to start")

    # Check credentials
    _log("PHASE 2: Check credentials", phase=True)
    if not has_mt5_credentials():
        _log("SKIP: No MT5 credentials configured")
        pytest.fail(
            "MT5 credentials not configured - set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER in .env"
        )

    # Check compose file
    if not COMPOSE_FILE.exists():
        _log(f"SKIP: compose file not found at {COMPOSE_FILE}")
        pytest.fail(f"Compose file not found at {COMPOSE_FILE}")

    # Build environment
    test_env = os.environ.copy()
    test_env.update(
        {
            "MT5_CONTAINER_NAME": TEST_CONTAINER_NAME,
            "MT5_GRPC_PORT": str(TEST_GRPC_PORT),
            "MT5_VNC_PORT": str(TEST_VNC_PORT),
            "MT5_HEALTH_PORT": str(TEST_HEALTH_PORT),
            "MT5_LOGIN": str(MT5_LOGIN),
            "MT5_PASSWORD": MT5_PASSWORD,
            "MT5_SERVER": MT5_SERVER or "",
        },
    )

    # Start container
    _log("PHASE 3: Start container with docker-compose", phase=True)
    _log("Running: docker compose up -d...")

    try:
        _run_command(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env=test_env,
            timeout=tc.CONTAINER_TIMEOUT,
        )
        _log("Container started successfully")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        _log(f"FAILED: docker compose error: {e}")
        pytest.fail(f"Failed to start container: {e}")
    except subprocess.TimeoutExpired:
        pytest.fail("Timeout waiting for docker compose up")

    _log("Container started, now waiting for gRPC...")

    # Wait for gRPC
    _log("PHASE 4: Wait for gRPC service", phase=True)

    if not wait_for_grpc_service(TEST_GRPC_HOST, TEST_GRPC_PORT):
        try:
            logs = _run_command(
                [
                    "docker",
                    "logs",
                    TEST_CONTAINER_NAME,
                    "--tail",
                    str(tc.LOG_TAIL_LINES),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            log_output = (
                logs.stdout[-500:] if logs.stdout else logs.stderr[-500:]
            )  # 500 chars for readability
        except FileNotFoundError:
            log_output = "Could not retrieve logs (docker not found)"
        msg = f"gRPC service not ready after {STARTUP_TIMEOUT}s. Logs: {log_output}"
        raise RuntimeError(msg)

    _log(f"Test container {TEST_CONTAINER_NAME} ready on port {TEST_GRPC_PORT}")

    # Run codegen
    _run_codegen()

    yield

    # No cleanup - container kept running for subsequent test runs
    _log(f"Tests complete - container {TEST_CONTAINER_NAME} kept running")


def _run_codegen() -> None:
    """Run codegen_enums.py if available."""
    if not CODEGEN_SCRIPT.exists():
        _log("Codegen script not found, skipping")
        return

    _log("Running codegen_enums.py...")
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(CODEGEN_SCRIPT), "--check"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            _log(f"codegen_enums.py returned {result.returncode} (continuing)")
    except subprocess.TimeoutExpired:
        _log("Timeout running codegen_enums.py (continuing)")

    _log("Codegen complete (or skipped)")


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: marks tests requiring MT5 server")
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "trading: marks tests that place real orders")
    config.addinivalue_line(
        "markers", "market_depth: marks tests requiring market depth"
    )


@pytest.fixture
def mt5_config() -> dict[str, str | int | None]:
    """Return MT5 test configuration."""
    return MT5_CONFIG.copy()


# =============================================================================
# SESSION-SCOPED FIXTURES (reduce connection overhead by ~99%)
# =============================================================================


@pytest.fixture(scope="session")
def _mt5_session_raw() -> Generator[MetaTrader5]:
    """Session-scoped raw MT5 connection - shared across ALL tests.

    Creates a single connection to the gRPC server that's reused by all tests.
    This dramatically reduces connection overhead (from ~584 cycles to 1).
    """
    _log("SESSION FIXTURE: Creating session-scoped MT5 connection")
    mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
    try:
        mt5.connect()
    except (grpc.RpcError, ConnectionError, OSError) as e:
        pytest.fail(f"MT5 connection failed: {e}")
    yield mt5
    _log("SESSION FIXTURE: Disconnecting session-scoped MT5 connection")
    with contextlib.suppress(grpc.RpcError, ConnectionError):
        mt5.disconnect()


@pytest.fixture(scope="session")
def _mt5_session_initialized(
    _mt5_session_raw: MetaTrader5,
) -> Generator[MetaTrader5]:
    """Session-scoped initialized MT5 - shared across ALL tests.

    Initializes the MT5 terminal once and reuses it for all tests.
    Returns uninitialized session if no credentials (handled by mt5 fixture).
    """
    if not has_mt5_credentials():
        _log("SESSION FIXTURE: No MT5 credentials - returning uninitialized session")
        yield _mt5_session_raw
        return

    _log("SESSION FIXTURE: Initializing session-scoped MT5 terminal")
    try:
        result = _mt5_session_raw.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
    except (grpc.RpcError, RuntimeError, OSError, ConnectionError) as e:
        pytest.fail(f"MT5 connection failed: {e}")

    if not result:
        error = _mt5_session_raw.last_error()
        pytest.fail(f"MT5 initialize failed: {error}")

    yield _mt5_session_raw

    _log("SESSION FIXTURE: Shutting down session-scoped MT5 terminal")
    with contextlib.suppress(Exception):
        _mt5_session_raw.shutdown()


# =============================================================================
# FUNCTION-SCOPED ALIASES (use session-scoped connections)
# =============================================================================


@pytest.fixture
def mt5_raw(_mt5_session_raw: MetaTrader5) -> MetaTrader5:
    """Return raw MT5 connection (no initialize).

    This fixture returns the session-scoped connection without initialize.
    Use for testing connection lifecycle.
    """
    # Resilience: reconnect if connection was lost (e.g., by other tests)
    if not _mt5_session_raw.is_connected:
        _log("RESILIENCE: Reconnecting raw MT5 connection")
        _mt5_session_raw.connect()
    return _mt5_session_raw


@pytest.fixture
def mt5(_mt5_session_initialized: MetaTrader5) -> MetaTrader5:
    """Return fully initialized MT5 client with auto-reconnect.

    This fixture returns the session-scoped initialized connection.
    Includes resilience: auto-reconnects if connection was lost by other tests.
    Skips test if MT5_LOGIN is not configured (=0), credentials missing,
    or if initialization fails.
    """
    # Skip test if no MT5 credentials configured
    if not has_mt5_credentials():
        pytest.skip(SKIP_NO_CREDENTIALS)

    # Resilience: reconnect if connection was lost
    if not _mt5_session_initialized.is_connected:
        _log("RESILIENCE: Reconnecting MT5 connection")
        try:
            _mt5_session_initialized.connect()
        except (grpc.RpcError, ConnectionError, OSError) as e:
            pytest.fail(f"MT5 reconnection failed: {e}")

    # Resilience: re-initialize if terminal state lost
    try:
        info = _mt5_session_initialized.terminal_info()
        if info is None:
            msg = "Terminal not initialized"
            raise RuntimeError(msg)

        # Verify terminal is ready for trading
        if not info.trade_allowed:
            pytest.fail("MT5 terminal reports trade_allowed=False")

        if not info.connected:
            pytest.fail("MT5 terminal reports connected=False")

        # Verify account is accessible
        account = _mt5_session_initialized.account_info()
        if account is None:
            pytest.fail("Cannot get account info - MT5 not ready")

        if not account.trade_allowed:
            pytest.fail("MT5 account reports trade_allowed=False")

        _log(
            f"MT5 ready: connected={info.connected}, trade_allowed={info.trade_allowed}, account_trade_allowed={account.trade_allowed}"
        )

    except Exception:  # noqa: BLE001 - catch all for resilience handling
        _log("RESILIENCE: Re-initializing MT5 terminal")
        try:
            result = _mt5_session_initialized.initialize(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER,
            )
            if not result:
                error = _mt5_session_initialized.last_error()
                pytest.fail(f"MT5 re-initialize failed: {error}")

            # Wait a bit for MT5 to be fully ready
            time.sleep(2)

            # Verify after re-initialization
            info = _mt5_session_initialized.terminal_info()
            if info is None or not info.trade_allowed or not info.connected:
                pytest.fail("MT5 not ready for trading after re-initialization")

            account = _mt5_session_initialized.account_info()
            if account is None or not account.trade_allowed:
                pytest.fail("MT5 account not ready for trading after re-initialization")

        except (grpc.RpcError, RuntimeError, OSError, ConnectionError) as e:
            pytest.fail(f"MT5 re-initialize failed: {e}")

    return _mt5_session_initialized


@pytest.fixture
def buy_order_request() -> dict[str, Any]:
    """Return sample buy order request dict.

    Returns a minimal buy market order for EURUSD with 0.01 lot.
    """
    return {
        "action": c.Order.TradeAction.DEAL,
        "symbol": "EURUSD",
        "volume": tc.MICRO_LOT,
        "type": c.Order.OrderType.BUY,
        "deviation": tc.DEFAULT_DEVIATION,
        "magic": tc.TEST_ORDER_MAGIC,
        "comment": "pytest buy order",
    }


@pytest.fixture
def sell_order_request() -> dict[str, Any]:
    """Return sample sell order request dict.

    Returns a minimal sell market order for EURUSD with 0.01 lot.
    """
    return {
        "action": c.Order.TradeAction.DEAL,
        "symbol": "EURUSD",
        "volume": tc.MICRO_LOT,
        "type": c.Order.OrderType.SELL,
        "deviation": tc.DEFAULT_DEVIATION,
        "magic": tc.TEST_ORDER_MAGIC,
        "comment": "pytest sell order",
    }


@pytest.fixture
def date_range_month() -> tuple[datetime, datetime]:
    """Return date range for last 30 days.

    Returns (start_date, end_date) tuple for historical data queries.
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=tc.ONE_MONTH)
    return (start, end)


@pytest.fixture
def date_range_week() -> tuple[datetime, datetime]:
    """Return date range for last 7 days."""
    end = datetime.now(UTC)
    start = end - timedelta(days=tc.ONE_WEEK)
    return (start, end)


@pytest.fixture
def market_book_symbol(mt5: MetaTrader5) -> Generator[str]:
    """Subscribe to EURUSD market depth for test.

    Adds market book subscription and cleans up after test.
    """
    symbol = "EURUSD"
    mt5.market_book_add(symbol)
    yield symbol
    with contextlib.suppress(Exception):
        mt5.market_book_release(symbol)


@pytest.fixture
def cleanup_test_positions(mt5: MetaTrader5) -> Generator[None]:
    """Cleanup any test positions after test.

    Closes all positions with magic=123456 (test magic number).
    """
    yield
    # Close any positions opened by test
    try:
        all_positions = mt5.positions_get()
        positions = [
            pos
            for pos in (all_positions or [])
            if getattr(pos, "magic", None) == tc.TEST_ORDER_MAGIC
        ]
        if positions:
            for pos in positions:
                # Build close request - opposite direction
                close_type = (
                    c.Order.OrderType.SELL
                    if pos.type == c.Order.OrderType.BUY
                    else c.Order.OrderType.BUY
                )
                request = {
                    "action": c.Order.TradeAction.DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "deviation": tc.DEFAULT_DEVIATION,
                    "magic": tc.TEST_ORDER_MAGIC,
                    "comment": "pytest cleanup",
                }
                mt5.order_send(request)
    except (grpc.RpcError, RuntimeError, OSError, ConnectionError) as e:
        _log(f"Warning: Failed to cleanup test positions: {e}")


# =============================================================================
# HISTORY TEST FIXTURES - Create orders to populate history
# =============================================================================


def _get_filling_mode(mt5: MetaTrader5, filling_mode_mask: int) -> int:
    """Get supported filling mode from symbol's filling_mode bitmask."""
    if filling_mode_mask & c.Symbol.FillingMode.FOK:
        return mt5.ORDER_FILLING_FOK
    if filling_mode_mask & c.Symbol.FillingMode.IOC:
        return mt5.ORDER_FILLING_IOC
    # RETURN mode bitmask = 4 (not in FillingMode enum, used for pending orders)
    if filling_mode_mask & 4:
        return mt5.ORDER_FILLING_RETURN
    return mt5.ORDER_FILLING_FOK  # Default


@pytest.fixture
def create_test_history(mt5: MetaTrader5) -> Generator[dict[str, Any]]:  # noqa: C901
    """Create a test order and close it to populate history.

    This fixture places a buy order, immediately closes it, creating
    historical deals and orders that can be queried in history tests.

    Returns dict with 'deal_ticket', 'order_ticket', 'position_id'.
    Returns empty dict if trading is not available (tests should handle this).
    """
    from mt5linux.utilities import MT5Utilities

    symbol = "EURUSD"
    mt5.symbol_select(symbol, enable=True)
    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        pytest.skip(f"Cannot get tick for {symbol} - market may be closed")

    # Get symbol filling mode to use correct one
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        pytest.skip(f"Cannot get symbol_info for {symbol}")
    filling_mode = _get_filling_mode(mt5, symbol_info.filling_mode)

    # Place buy order
    buy_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": tc.MICRO_LOT,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "deviation": tc.HIGH_DEVIATION,
        "magic": c.Test.Order.HISTORY_MAGIC,
        "comment": "pytest history test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }

    try:
        result = mt5.order_send(buy_request)
    except MT5Utilities.Exceptions.Error as e:
        pytest.skip(f"order_send failed with error: {e}")

    if result is None:
        pytest.skip("order_send returned None")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        pytest.skip(f"order_send returned retcode {result.retcode}, expected DONE")

    order_ticket = result.order
    deal_ticket = result.deal

    # Get position to close
    positions = mt5.positions_get(symbol=symbol)
    position = None
    if positions:
        for pos in positions:
            if pos.magic == c.Test.Order.HISTORY_MAGIC:
                position = pos
                break

    if position is None:
        pytest.skip("Position not found after order_send - position tracking issue")

    position_id = position.ticket

    # Close the position immediately
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        pytest.skip(f"Cannot get tick for {symbol} to close position")

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position.volume,
        "type": mt5.ORDER_TYPE_SELL,
        "position": position.ticket,
        "price": tick.bid,
        "deviation": 50,
        "magic": c.Test.Order.HISTORY_MAGIC,
        "comment": "pytest history close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,  # Use same filling mode as open
    }

    try:
        close_result = mt5.order_send(close_request)
    except MT5Utilities.Exceptions.Error as e:
        pytest.skip(f"Failed to close position: {e}")

    if close_result is None:
        pytest.skip("order_send for close returned None")

    return {
        "deal_ticket": deal_ticket,
        "order_ticket": order_ticket,
        "position_id": position_id,
        "close_deal_ticket": close_result.deal,
        "close_order_ticket": close_result.order,
    }


# =============================================================================
# ASYNC SESSION-SCOPED FIXTURES (reduce connection overhead by ~99%)
# =============================================================================


@pytest.fixture(scope="session")
async def _async_mt5_session_raw() -> AsyncGenerator[AsyncMetaTrader5]:
    """Session-scoped raw async MT5 connection - shared across ALL tests.

    Creates a single async connection to the gRPC server that's reused by all tests.
    """
    _log("SESSION FIXTURE: Creating session-scoped async MT5 connection")
    client = AsyncMetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
    try:
        await client.connect()
    except (grpc.RpcError, RuntimeError, OSError, ConnectionError) as e:
        pytest.fail(f"Async MT5 connection failed: {e}")
    yield client
    _log("SESSION FIXTURE: Disconnecting session-scoped async MT5 connection")
    await client.disconnect()


@pytest.fixture(scope="session")
async def _async_mt5_session_initialized(
    _async_mt5_session_raw: AsyncMetaTrader5,
) -> AsyncGenerator[AsyncMetaTrader5]:
    """Session-scoped initialized async MT5 - shared across ALL tests.

    Initializes the async MT5 terminal once and reuses it for all tests.
    """
    if not has_mt5_credentials():
        msg = "MT5 credentials not configured - set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER"
        raise RuntimeError(msg)

    _log("SESSION FIXTURE: Initializing session-scoped async MT5 terminal")
    try:
        result = await _async_mt5_session_raw.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
    except (grpc.RpcError, RuntimeError, OSError, ConnectionError) as e:
        pytest.fail(f"Async MT5 connection failed: {e}")

    if not result:
        error = await _async_mt5_session_raw.last_error()
        pytest.fail(f"Async MT5 initialize failed: {error}")

    yield _async_mt5_session_raw

    _log("SESSION FIXTURE: Shutting down session-scoped async MT5 terminal")
    with contextlib.suppress(Exception):
        await _async_mt5_session_raw.shutdown()


# =============================================================================
# ASYNC FUNCTION-SCOPED ALIASES (use session-scoped connections)
# =============================================================================


@pytest.fixture
async def async_mt5_raw(
    _async_mt5_session_raw: AsyncMetaTrader5,
) -> AsyncMetaTrader5:
    """Return raw async MT5 connection (no initialize).

    This fixture returns the session-scoped async connection without initialize.
    Use for testing connection lifecycle.
    """
    return _async_mt5_session_raw


@pytest.fixture
async def async_mt5(
    _async_mt5_session_initialized: AsyncMetaTrader5,
) -> AsyncMetaTrader5:
    """Return fully initialized async MT5 client.

    This fixture returns the session-scoped async initialized connection.
    Skips test if MT5_LOGIN is not configured (=0), credentials missing,
    or if initialization fails.
    """
    return _async_mt5_session_initialized


# Export symbols for type checking
__all__ = [
    "MT5_CONFIG",
    "TEST_CONTAINER_NAME",
    "TEST_GRPC_HOST",
    "TEST_GRPC_PORT",
    "c",  # MT5Constants from mt5linux.constants
    "tc",  # TestConstants from tests.constants
]
