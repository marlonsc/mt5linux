"""Test configuration and fixtures.

This module provides fixtures that automatically start and validate
the ISOLATED test container (mt5linux-test on port 28812).

The container is completely isolated from:
- Production (mt5, port 8001)
- neptor tests (neptor-mt5-test, port 18812)
- mt5docker tests (mt5docker-test, port 48812)

Configuration is loaded from environment variables via .env file.
"""

from __future__ import annotations

import contextlib
import os
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

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# =============================================================================
# TIMING INSTRUMENTATION (matches mt5docker pattern)
# =============================================================================

_timing_start: float = 0.0


def _log(message: str, *, phase: bool = False) -> None:
    """Log message to stderr (always visible in pytest)."""
    elapsed = time.time() - _timing_start
    if phase:
        sys.stderr.write(f"\n{'='*60}\n")
        sys.stderr.write(f"[{elapsed:5.1f}s] PHASE: {message}\n")
        sys.stderr.write(f"{'='*60}\n")
    else:
        sys.stderr.write(f"[{elapsed:5.1f}s] {message}\n")
    sys.stderr.flush()


# =============================================================================
# DOCKER AND GRPC HELPERS
# =============================================================================


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def has_mt5_credentials() -> bool:
    """Check if MT5 credentials are configured for integration tests."""
    return bool(
        os.getenv("MT5_LOGIN") and os.getenv("MT5_PASSWORD") and MT5_LOGIN != 0
    )


def is_grpc_service_ready(
    host: str = "localhost",
    port: int | None = None,
    timeout: float = 10.0,
) -> bool:
    """Check if gRPC service is ready (actual handshake, not just port).

    Args:
        host: gRPC server host.
        port: gRPC server port.
        timeout: Timeout for the HealthCheck call.

    Returns:
        True if service responds to HealthCheck, False otherwise.
    """
    grpc_port = port or TEST_GRPC_PORT
    _log(f"gRPC check: {host}:{grpc_port} (timeout={timeout:.1f}s)...")
    try:
        channel = grpc.insecure_channel(f"{host}:{grpc_port}")
        stub = mt5_pb2_grpc.MT5ServiceStub(channel)
        response = stub.HealthCheck(mt5_pb2.Empty(), timeout=timeout)
        channel.close()
        _log(f"gRPC check: healthy={response.healthy}")
        return response.healthy
    except grpc.RpcError as e:
        _log(f"gRPC check: FAILED - {type(e).__name__}")
        return False


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
    min_interval = 0.5
    max_interval = 5.0
    current_interval = min_interval
    startup_health_timeout = 30.0  # Longer timeout during startup

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
# CONFIGURATION
# =============================================================================

# Paths
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
CODEGEN_SCRIPT = PROJECT_ROOT / "scripts" / "codegen_enums.py"

# Load environment config from .env.test, then credentials from .env
# .env.test has test environment settings (ports, container name)
# .env has credentials (MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
load_dotenv(PROJECT_ROOT / ".env.test")  # Environment config first
load_dotenv(PROJECT_ROOT / ".env", override=True)  # Credentials override

# Test container configuration
# Default ports: mt5linux tests use 28812 (isolated from other projects)
_config = MT5Config()
TEST_GRPC_HOST = os.getenv("MT5_HOST", "localhost")
TEST_GRPC_PORT = int(os.getenv("MT5_GRPC_PORT", "28812"))
TEST_VNC_PORT = int(os.getenv("MT5_VNC_PORT", "23000"))
TEST_HEALTH_PORT = int(os.getenv("MT5_HEALTH_PORT", "28002"))
TEST_CONTAINER_NAME = os.getenv("MT5_CONTAINER_NAME", "mt5linux-test")

# Timeouts (matches mt5docker pattern)
STARTUP_TIMEOUT = int(os.getenv("MT5_STARTUP_TIMEOUT", "420"))
GRPC_TIMEOUT = int(os.getenv("MT5_GRPC_TIMEOUT", "60"))

# MT5 credentials for integration tests (MUST come from .env, no defaults)
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
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
# CONTAINER LIFECYCLE
# =============================================================================


def _is_container_running(name: str | None = None) -> bool:
    """Check if container is running."""
    container_name = name or TEST_CONTAINER_NAME
    _log(f"Checking if container '{container_name}' is running...")
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = bool(result.stdout.strip())
    _log(f"Container running: {running}")
    return running


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_and_codegen() -> Generator[None]:  # noqa: C901
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
    global _timing_start  # noqa: PLW0603
    _timing_start = time.time()

    _log("CONTAINER VALIDATION START", phase=True)
    _log(f"Container: {TEST_CONTAINER_NAME}")
    _log(f"gRPC port: {TEST_GRPC_PORT}")
    _log(f"Startup timeout: {STARTUP_TIMEOUT}s")

    # Check if Docker tests should be skipped
    if os.getenv("SKIP_DOCKER", "0") == "1":
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
        if is_grpc_service_ready(TEST_GRPC_HOST, TEST_GRPC_PORT, timeout=2.0):
            _log("FAST-PATH SUCCESS: gRPC already ready!")
            _log(f"Total validation time: {time.time() - _timing_start:.1f}s")
            _run_codegen()
            yield
            return

        # PHASE 3: Wait for gRPC with progressive backoff
        _log("PHASE 3: Wait for gRPC (service not immediately ready)", phase=True)
        if wait_for_grpc_service(TEST_GRPC_HOST, TEST_GRPC_PORT):
            _log(f"Total validation time: {time.time() - _timing_start:.1f}s")
            _run_codegen()
            yield
            return
        else:
            _log("WARNING: gRPC not ready - will try to restart container")

    # Container not running or not responding - need to start it
    _log("Container NOT running or NOT responding - need to start")

    # Check credentials
    _log("PHASE 2: Check credentials", phase=True)
    if not has_mt5_credentials():
        _log("SKIP: No MT5 credentials configured")
        pytest.skip(SKIP_NO_CREDENTIALS)

    # Check compose file
    if not COMPOSE_FILE.exists():
        _log(f"SKIP: compose file not found at {COMPOSE_FILE}")
        pytest.skip(f"Compose file not found at {COMPOSE_FILE}")

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
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env=test_env,
            timeout=60,
        )
        _log("Container started successfully")
    except subprocess.CalledProcessError as e:
        _log(f"FAILED: docker compose error: {e.stderr}")
        pytest.skip(f"Failed to start container: {e.stderr}")
    except subprocess.TimeoutExpired:
        pytest.skip("Timeout waiting for docker compose up")

    _log("Container started, now waiting for gRPC...")

    # Wait for gRPC
    _log("PHASE 4: Wait for gRPC service", phase=True)

    if not wait_for_grpc_service(TEST_GRPC_HOST, TEST_GRPC_PORT):
        logs = subprocess.run(
            ["docker", "logs", TEST_CONTAINER_NAME, "--tail", "50"],
            capture_output=True,
            text=True,
            check=False,
        )
        pytest.skip(
            f"gRPC service not ready after {STARTUP_TIMEOUT}s.\n"
            f"Logs: {logs.stdout[-500:] if logs.stdout else logs.stderr[-500:]}",
        )

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
        result = subprocess.run(
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
    config.addinivalue_line(
        "markers", "integration: marks tests requiring MT5 server"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line(
        "markers", "trading: marks tests that place real orders"
    )
    config.addinivalue_line(
        "markers", "market_depth: marks tests requiring market depth"
    )


@pytest.fixture
def mt5_config() -> dict[str, str | int | None]:
    """Return MT5 test configuration."""
    return MT5_CONFIG.copy()


@pytest.fixture
def mt5_raw() -> Generator[MetaTrader5]:
    """Return raw MT5 connection (no initialize).

    This fixture creates a connection to the gRPC server but does NOT
    call initialize(). Use for testing connection lifecycle.
    Skips if connection fails.
    """
    mt5 = MetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
    try:
        mt5.connect()
    except Exception as e:
        pytest.skip(f"MT5 connection failed: {e}")
    yield mt5
    with contextlib.suppress(Exception):
        mt5.disconnect()


@pytest.fixture
def mt5(mt5_raw: MetaTrader5) -> Generator[MetaTrader5]:
    """Return fully initialized MT5 client.

    This fixture connects AND initializes the MT5 terminal.
    Skips test if MT5_LOGIN is not configured (=0), credentials missing,
    or if initialization fails.
    """
    if not has_mt5_credentials():
        pytest.skip(
            "MT5 credentials not configured - set MT5_LOGIN, MT5_PASSWORD, "
            "and MT5_SERVER in .env file"
        )

    try:
        result = mt5_raw.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
    except Exception as e:
        pytest.skip(f"MT5 connection failed: {e}")

    if not result:
        error = mt5_raw.last_error()
        pytest.skip(f"MT5 initialize failed: {error}")

    yield mt5_raw

    with contextlib.suppress(Exception):
        mt5_raw.shutdown()


@pytest.fixture
def buy_order_request() -> dict[str, Any]:
    """Return sample buy order request dict.

    Returns a minimal buy market order for EURUSD with 0.01 lot.
    """
    return {
        "action": 1,  # TRADE_ACTION_DEAL
        "symbol": "EURUSD",
        "volume": 0.01,
        "type": 0,  # ORDER_TYPE_BUY
        "deviation": 20,
        "magic": 123456,
        "comment": "pytest buy order",
    }


@pytest.fixture
def sell_order_request() -> dict[str, Any]:
    """Return sample sell order request dict.

    Returns a minimal sell market order for EURUSD with 0.01 lot.
    """
    return {
        "action": 1,  # TRADE_ACTION_DEAL
        "symbol": "EURUSD",
        "volume": 0.01,
        "type": 1,  # ORDER_TYPE_SELL
        "deviation": 20,
        "magic": 123456,
        "comment": "pytest sell order",
    }


@pytest.fixture
def date_range_month() -> tuple[datetime, datetime]:
    """Return date range for last 30 days.

    Returns (start_date, end_date) tuple for historical data queries.
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=30)
    return (start, end)


@pytest.fixture
def date_range_week() -> tuple[datetime, datetime]:
    """Return date range for last 7 days."""
    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    return (start, end)


@pytest.fixture
def market_book_symbol(mt5: MetaTrader5) -> Generator[str]:
    """Subscribe to EURUSD market depth for test.

    Adds market book subscription and cleans up after test.
    """
    symbol = "EURUSD"
    try:
        mt5.market_book_add(symbol)
    except Exception as e:
        pytest.skip(f"Market book not available: {e}")
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
            if getattr(pos, "magic", None) == 123456
        ]
        if positions:
            for pos in positions:
                # Build close request
                request = {
                    "action": 1,  # TRADE_ACTION_DEAL
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": 1 if pos.type == 0 else 0,  # Opposite direction
                    "position": pos.ticket,
                    "deviation": 20,
                    "magic": 123456,
                    "comment": "pytest cleanup",
                }
                mt5.order_send(request)
    except Exception as e:
        _log(f"Warning: Failed to cleanup test positions: {e}")


# =============================================================================
# HISTORY TEST FIXTURES - Create orders to populate history
# =============================================================================

# Magic number for history test orders (different from regular test orders)
HISTORY_TEST_MAGIC = 888888


@pytest.fixture
def create_test_history(mt5: MetaTrader5) -> Generator[dict[str, Any]]:
    """Create a test order and close it to populate history.

    This fixture places a buy order, immediately closes it, creating
    historical deals and orders that can be queried in history tests.

    Returns dict with 'deal_ticket', 'order_ticket', 'position_id'.
    Skips if market is closed or trading disabled.
    """
    symbol = "EURUSD"
    mt5.symbol_select(symbol, True)
    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        pytest.skip("Could not get tick data for history test")

    # Place buy order
    buy_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "deviation": 50,
        "magic": HISTORY_TEST_MAGIC,
        "comment": "pytest history test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(buy_request)
    if result is None:
        pytest.skip("order_send returned None (trading not available)")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        # Check for market closed
        if result.retcode == mt5.TRADE_RETCODE_MARKET_CLOSED:
            pytest.skip("Market closed - cannot create history test data")
        pytest.skip(
            f"Could not open position: {result.retcode} - {result.comment}"
        )

    order_ticket = result.order
    deal_ticket = result.deal

    # Get position to close
    positions = mt5.positions_get(symbol=symbol)
    position = None
    if positions:
        for pos in positions:
            if pos.magic == HISTORY_TEST_MAGIC:
                position = pos
                break

    if position is None:
        pytest.skip("Position not found after opening")

    position_id = position.ticket

    # Close the position immediately
    tick = mt5.symbol_info_tick(symbol)
    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position.volume,
        "type": mt5.ORDER_TYPE_SELL,
        "position": position.ticket,
        "price": tick.bid,
        "deviation": 50,
        "magic": HISTORY_TEST_MAGIC,
        "comment": "pytest history close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    close_result = mt5.order_send(close_request)
    if close_result is None or close_result.retcode != mt5.TRADE_RETCODE_DONE:
        # Best effort - still yield what we have
        pass

    return {
        "deal_ticket": deal_ticket,
        "order_ticket": order_ticket,
        "position_id": position_id,
        "close_deal_ticket": close_result.deal if close_result else None,
        "close_order_ticket": close_result.order if close_result else None,
    }


# =============================================================================
# ASYNC FIXTURES
# =============================================================================


@pytest.fixture
async def async_mt5_raw() -> AsyncGenerator[AsyncMetaTrader5]:
    """Return raw async MT5 connection (no initialize).

    This fixture creates an async connection to the gRPC server but does NOT
    call initialize(). Use for testing connection lifecycle.
    Skips if connection fails.
    """
    client = AsyncMetaTrader5(host=TEST_GRPC_HOST, port=TEST_GRPC_PORT)
    try:
        await client.connect()
    except Exception as e:
        pytest.skip(f"Async MT5 connection failed: {e}")
    yield client
    await client.disconnect()


@pytest.fixture
async def async_mt5(
    async_mt5_raw: AsyncMetaTrader5,
) -> AsyncGenerator[AsyncMetaTrader5]:
    """Return fully initialized async MT5 client.

    This fixture connects AND initializes the MT5 terminal.
    Skips test if MT5_LOGIN is not configured (=0), credentials missing,
    or if initialization fails.
    """
    if not has_mt5_credentials():
        pytest.skip(
            "MT5 credentials not configured - set MT5_LOGIN, MT5_PASSWORD, "
            "and MT5_SERVER in .env file"
        )

    try:
        result = await async_mt5_raw.initialize(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
    except Exception as e:
        pytest.skip(f"Async MT5 connection failed: {e}")

    if not result:
        error = await async_mt5_raw.last_error()
        pytest.skip(f"Async MT5 initialize failed: {error}")

    yield async_mt5_raw

    with contextlib.suppress(Exception):
        await async_mt5_raw.shutdown()


# Export symbols for type checking
__all__ = [
    "MT5_CONFIG",
    "TEST_CONTAINER_NAME",
    "TEST_GRPC_HOST",
    "TEST_GRPC_PORT",
]
