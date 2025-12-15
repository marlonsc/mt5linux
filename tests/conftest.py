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


def wait_for_rpyc_service(
    host: str = "localhost", port: int | None = None, timeout: int = 300
) -> bool:
    """Wait for RPyC service to become ready by attempting actual connection.

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

    while time.time() - start < timeout:
        try:
            # Connect same way as MetaTrader5 client (no service specified)
            conn = rpyc.connect(
                host,
                rpyc_port,
                config={
                    "sync_request_timeout": 30,
                    "allow_public_attrs": True,
                },
            )
            # If we can connect successfully, the service is ready
            # The connection establishment itself verifies the service is available
            conn.close()
            return True
        except Exception as e:
            elapsed = int(time.time() - start)
            if elapsed % 30 == 0:  # Log every 30 seconds
                logger.info(
                    "Waiting for RPyC service... (%ds elapsed, error: %s)",
                    elapsed,
                    type(e).__name__,
                )
        time.sleep(5)

    return False


# Load .env for test credentials
load_dotenv()

# Paths
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"
CODEGEN_SCRIPT = PROJECT_ROOT / "scripts" / "codegen_enums.py"

# Test container configuration
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


def _cleanup_test_container_and_volumes() -> None:
    """Clean up test container and volumes for complete isolation."""
    logger = logging.getLogger(__name__)

    # Force remove container if running
    if _is_container_running(TEST_CONTAINER_NAME):
        logger.info("Removing existing test container %s", TEST_CONTAINER_NAME)
        subprocess.run(
            ["docker", "rm", "-f", TEST_CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

    # Clean up test volumes to ensure complete isolation
    # Volumes are parametrized with container name
    test_volumes = [
        f"{TEST_CONTAINER_NAME}_config",
        f"{TEST_CONTAINER_NAME}_downloads",
        f"{TEST_CONTAINER_NAME}_cache",
    ]
    for volume in test_volumes:
        logger.info("Cleaning test volume: %s", volume)
        subprocess.run(
            ["docker", "volume", "rm", volume],
            capture_output=True,
            check=False,
        )


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_and_codegen() -> Generator[None]:
    """Start test Docker container and run codegen before all tests.

    This fixture automatically handles Docker availability:
    - If SKIP_DOCKER=1, skips Docker setup entirely
    - If Docker is not available, skips Docker-dependent setup but allows unit tests
    - If Docker is available, ensures clean container state and runs codegen
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

    logger.info("Ensuring clean Docker test container state...")

    # Always clean up container and volumes for complete test isolation
    try:
        _cleanup_test_container_and_volumes()
        logger.info("Cleaned up existing test containers and volumes")
    except Exception as e:
        logger.warning("Error during cleanup (continuing): %s", e)

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

    # Container started successfully - wait for RPyC service to be ready
    logger.info("Container started successfully")

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

    # Teardown: clean up container and volumes completely
    logger.info("Cleaning up test container and volumes...")
    try:
        _cleanup_test_container_and_volumes()
        logger.info("Test cleanup completed")
    except Exception as e:
        logger.warning("Error during test cleanup: %s", e)


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
