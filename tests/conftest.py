"""Test configuration and fixtures."""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import rpyc
from dotenv import load_dotenv

from mt5linux import AsyncMetaTrader5, MetaTrader5


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
    return bool(os.getenv("MT5_LOGIN") and os.getenv("MT5_PASSWORD") and MT5_LOGIN != 0)


def is_rpyc_service_ready(host: str = "localhost", port: int | None = None) -> bool:
    """Check if RPyC service is ready (actual handshake + health_check).

    Uses rpyc.connect() and calls health_check() to verify MT5Service is ready.
    Uses a 60 second timeout because Wine/Python RPyC server can be slow.
    """
    rpyc_port = port or TEST_RPYC_PORT
    try:
        conn = rpyc.connect(
            host,
            rpyc_port,
            config={
                "sync_request_timeout": 60,
                "allow_public_attrs": True,
                "allow_pickle": True,
            },
        )
        # Verify connection works by calling health_check
        _ = conn.root.health_check()
        conn.close()
    except (OSError, ConnectionError, TimeoutError, EOFError):
        return False
    else:
        return True


def wait_for_rpyc_service(
    host: str = "localhost", port: int | None = None, timeout: int = 300
) -> bool:
    """Wait for RPyC service to become ready.

    This function waits until the RPyC service is fully ready to handle requests,
    not just when the port is listening. The MT5 container needs time to:
    1. Start the RPyC server (port becomes available)
    2. Initialize Wine and MetaTrader5 (service becomes usable)

    Args:
        host: RPyC server host
        port: RPyC server port (default: TEST_RPYC_PORT)
        timeout: Maximum wait time in seconds (default: 300)

    Returns:
        True if service is ready, False if timeout reached
    """
    rpyc_port = port or TEST_RPYC_PORT
    start = time.time()
    logger = logging.getLogger(__name__)
    check_interval = 3

    while time.time() - start < timeout:
        if is_rpyc_service_ready(host, rpyc_port):
            return True
        elapsed = int(time.time() - start)
        if elapsed % 30 == 0 and elapsed > 0:  # Log every 30 seconds
            logger.info(
                "Waiting for RPyC service... (%ds elapsed)",
                elapsed,
            )
        time.sleep(check_interval)

    return False


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
# Default ports match mt5linux/docker-compose.yaml defaults
TEST_RPYC_HOST = os.getenv("MT5_HOST", "localhost")
TEST_RPYC_PORT = int(os.getenv("MT5_RPYC_PORT", "38812"))
TEST_VNC_PORT = int(os.getenv("MT5_VNC_PORT", "33000"))
TEST_CONTAINER_NAME = os.getenv("MT5_CONTAINER_NAME", "mt5linux-unit")

# MT5 credentials for integration tests (MUST come from .env, no defaults)
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER: str | None = os.getenv("MT5_SERVER")

MT5_CONFIG: dict[str, str | int | None] = {
    "host": TEST_RPYC_HOST,
    "port": TEST_RPYC_PORT,
    "login": MT5_LOGIN,
    "password": MT5_PASSWORD,
    "server": MT5_SERVER,
}


def _is_container_running(container_name: str) -> bool:
    """Check if container is running."""
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _is_container_healthy(container_name: str) -> bool:
    """Check if container is running and healthy."""
    result = subprocess.run(
        [
            "docker", "inspect", "--format",
            "{{.State.Health.Status}}",
            container_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "healthy"


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_and_codegen() -> Generator[None]:  # noqa: C901
    """Start test Docker container and run codegen before all tests.

    This fixture automatically handles Docker availability:
    - If SKIP_DOCKER=1, skips Docker setup entirely
    - If Docker is not available, skips Docker-dependent setup but allows unit tests
    - If container is already running and healthy, reuses it (no restart)
    - If container not running, starts it and waits for RPyC service
    - Container is kept running after tests end (no cleanup)
    """
    logger = logging.getLogger(__name__)

    # Check if Docker tests should be skipped
    if os.getenv("SKIP_DOCKER", "0") == "1":
        logger.info("SKIP_DOCKER=1 - skipping Docker setup, running unit tests only")
        yield
        return

    # Check if Docker is available
    if not is_docker_available():
        logger.info(
            "Docker not available - skipping Docker setup, running unit tests only"
        )
        yield
        return

    # Check if container is already running and healthy - reuse it
    if _is_container_running(TEST_CONTAINER_NAME):
        if _is_container_healthy(TEST_CONTAINER_NAME):
            logger.info(
                "Container %s already running and healthy - reusing",
                TEST_CONTAINER_NAME,
            )
            # Still verify RPyC is ready
            if wait_for_rpyc_service(TEST_RPYC_HOST, TEST_RPYC_PORT, timeout=30):
                logger.info("RPyC service confirmed ready")
                yield
                return
            else:
                logger.warning(
                    "Container healthy but RPyC not responding - will restart"
                )
        else:
            logger.info(
                "Container %s running but not healthy - will restart",
                TEST_CONTAINER_NAME,
            )

    # Start fresh test container with parametrized environment
    logger.info("Starting test Docker container with configuration...")
    logger.info("Container: %s", TEST_CONTAINER_NAME)
    logger.info("RPyC Port: %s", TEST_RPYC_PORT)
    logger.info("VNC Port: %s", TEST_VNC_PORT)
    logger.info("Server: %s", MT5_SERVER)

    try:
        # Set environment for docker compose
        env = os.environ.copy()
        env_file = os.getenv("ENV_FILE", str(PROJECT_ROOT / ".env"))
        env.update(
            {
                "MT5_CONTAINER_NAME": TEST_CONTAINER_NAME,
                "MT5_RPYC_PORT": str(TEST_RPYC_PORT),
                "MT5_VNC_PORT": str(TEST_VNC_PORT),
                "MT5_LOGIN": str(MT5_LOGIN),
                "MT5_PASSWORD": MT5_PASSWORD,
                "MT5_SERVER": MT5_SERVER or "",
                "ENV_FILE": env_file,
            }
        )

        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
            ],
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=60,
            env=env,
        )
        logger.info("Test container started successfully")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to start test container:\n{e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        pytest.fail("Timeout waiting for test container to start")

    # Wait for RPyC service to be ready before running tests/codegen
    logger.info("Waiting for RPyC service to be ready (up to 300s)...")
    if not wait_for_rpyc_service(TEST_RPYC_HOST, TEST_RPYC_PORT, timeout=300):
        pytest.fail(
            f"RPyC service not available on {TEST_RPYC_HOST}:{TEST_RPYC_PORT} "
            "after 300 seconds"
        )
    logger.info("RPyC service is ready")

    # Run codegen only if Docker is available and RPyC service is ready
    logger.info("Running codegen_enums.py...")
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
            logger.warning(
                "codegen_enums.py failed (continuing):\n%s\n%s",
                result.stdout,
                result.stderr,
            )
    except subprocess.TimeoutExpired:
        logger.warning("Timeout running codegen_enums.py (continuing)")

    logger.info("Codegen complete (or skipped)")

    yield

    # No cleanup - container kept running for subsequent test runs
    logger.info("Tests complete - container %s kept running", TEST_CONTAINER_NAME)


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


@pytest.fixture
def mt5_raw() -> Generator[MetaTrader5]:
    """Return raw MT5 connection (no initialize).

    This fixture creates a connection to the rpyc server but does NOT
    call initialize(). Use for testing connection lifecycle.
    Skips if connection fails.
    """
    try:
        mt5 = MetaTrader5(host=TEST_RPYC_HOST, port=TEST_RPYC_PORT)
    except Exception as e:
        pytest.skip(f"MT5 connection failed: {e}")
    yield mt5
    with contextlib.suppress(Exception):
        mt5.close()


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
    except Exception:
        pass  # Best effort cleanup


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
        pytest.skip(f"Could not open position: {result.retcode} - {result.comment}")

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

    This fixture creates an async connection to the rpyc server but does NOT
    call initialize(). Use for testing connection lifecycle.
    Skips if connection fails.
    """
    client = AsyncMetaTrader5(host=TEST_RPYC_HOST, port=TEST_RPYC_PORT)
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
    "TEST_RPYC_HOST",
    "TEST_RPYC_PORT",
    "TEST_CONTAINER_NAME",
    "MT5_CONFIG",
]
