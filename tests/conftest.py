"""Pytest fixtures with auto-startup of ISOLATED mt5docker test container.

Test container is completely isolated from production environment:
- Container: mt5linux-test (not mt5)
- RPyC Port: 28812 (not 8001)
- VNC Port: 23000 (not 3000)
- Volumes: separate test volumes (not shared with production)

Workspace Detection:
- If ../mt5docker exists: uses local project with docker-compose.test.yaml
- If not in workspace: skips with instructions to clone from GitHub

The container mounts local mt5linux code instead of cloning from GitHub.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from dotenv import load_dotenv

if TYPE_CHECKING:
    from mt5linux import MetaTrader5

# Load .env file from project root
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# =============================================================================
# ISOLATED TEST CONFIGURATION - DOES NOT AFFECT PRODUCTION OR NEPTOR!
# =============================================================================
TEST_CONTAINER_NAME = "mt5linux-unit"
TEST_RPYC_PORT = int(os.environ.get("MT5_RPYC_PORT", "38812"))
TEST_VNC_PORT = int(os.environ.get("MT5_VNC_PORT", "33000"))
TEST_HEALTH_PORT = int(os.environ.get("MT5_HEALTH_PORT", "38002"))
TEST_TIMEOUT = 180  # Timeout for startup (first build takes longer)

# Test credentials from environment (see .env.example)
# Supports both MT5_* and MT5_* variable names
TEST_MT5_LOGIN = int(os.environ.get("MT5_LOGIN") or "0")
TEST_MT5_PASSWORD = os.environ.get("MT5_PASSWORD") or ""
TEST_MT5_SERVER = os.environ.get("MT5_SERVER") or "MetaQuotes-Demo"


def _mt5_credentials_configured() -> bool:
    """Check if MT5 credentials are configured in .env."""
    return bool(TEST_MT5_PASSWORD)


# Skip message for tests requiring MT5 credentials
_SKIP_NO_CREDENTIALS = (
    "SKIP: MT5_PASSWORD not configured.\n"
    "To run MT5 integration tests:\n"
    "  1. cp .env.example .env\n"
    "  2. Edit .env and set MT5_PASSWORD (and optionally MT5_LOGIN)\n"
    "  3. Run pytest again"
)


# =============================================================================
# WORKSPACE DETECTION
# =============================================================================


def _find_workspace_root() -> Path:
    """Find workspace root (parent of mt5linux)."""
    return Path(__file__).resolve().parent.parent.parent


def _find_mt5docker_path() -> Path | None:
    """Find mt5docker project in workspace.

    Detection order:
    1. ../mt5docker (sibling directory in workspace)
    2. None if not found

    Returns:
        Path to mt5docker directory or None if not in workspace.
    """
    workspace = _find_workspace_root()

    # Check sibling directory (../mt5docker relative to mt5linux)
    sibling_path = workspace / "mt5docker"
    if sibling_path.exists() and (sibling_path / "docker-compose.yaml").exists():
        return sibling_path

    return None


def _get_docker_compose_files(mt5docker_path: Path) -> list[Path]:
    """Get docker-compose files for test container.

    Uses overlay: docker-compose.yaml + docker-compose.test.yaml

    Returns:
        List of compose files to use.

    Raises:
        FileNotFoundError: If compose files are missing.
    """
    base = mt5docker_path / "docker-compose.yaml"
    test = mt5docker_path / "docker-compose.test.yaml"

    if not base.exists():
        msg = f"docker-compose.yaml not found in {mt5docker_path}"
        raise FileNotFoundError(msg)

    if not test.exists():
        msg = (
            f"docker-compose.test.yaml not found in {mt5docker_path}. "
            "This file is required for isolated test container."
        )
        raise FileNotFoundError(msg)

    return [base, test]


# =============================================================================
# SERVICE DETECTION
# =============================================================================


def wait_for_port(host: str, port: int, timeout: int = TEST_TIMEOUT) -> bool:
    """Wait for TCP port to become available.

    Args:
        host: Hostname to connect to.
        port: Port number to check.
        timeout: Maximum seconds to wait.

    Returns:
        True if port is available, False if timeout exceeded.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(2)
    return False


def is_container_running(name: str) -> bool:
    """Check if container is running."""
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def is_container_exists(name: str) -> bool:
    """Check if container exists (running or stopped)."""
    result = subprocess.run(
        ["docker", "ps", "-aq", "-f", f"name=^{name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def is_rpyc_service_ready(host: str, port: int) -> bool:
    """Check if RPyC service is ready (actual handshake, not just port).

    Performs real RPyC classic handshake to verify service is operational.
    """
    try:
        from rpyc.utils.classic import connect

        conn = connect(host, port)
        conn._config["sync_request_timeout"] = 5
        # Verify modules are accessible (proves MT5 bridge is working)
        _ = conn.modules
        conn.close()
        return True
    except Exception:
        return False


def wait_for_rpyc_service(
    host: str = "localhost",
    port: int = TEST_RPYC_PORT,
    timeout: int = TEST_TIMEOUT,
) -> bool:
    """Wait for RPyC service to become ready.

    Uses actual RPyC handshake, not just TCP port check.
    """
    start = time.time()
    check_interval = 3  # seconds between checks

    while time.time() - start < timeout:
        if is_rpyc_service_ready(host, port):
            return True
        time.sleep(check_interval)

    return False


def start_test_container() -> None:
    """Start ISOLATED test container using docker-compose.test.yaml."""
    # If container is already running and responding, use it
    if is_container_running(TEST_CONTAINER_NAME):
        if wait_for_port("localhost", TEST_RPYC_PORT, timeout=10):
            return
        # Container running but port not responding - restart
        subprocess.run(
            ["docker", "rm", "-f", TEST_CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

    # Remove existing container if any
    if is_container_exists(TEST_CONTAINER_NAME):
        subprocess.run(
            ["docker", "rm", "-f", TEST_CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

    # Locate docker-compose.test.yaml in tests/fixtures/
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    compose_file = fixtures_dir / "docker-compose.test.yaml"

    if not compose_file.exists():
        pytest.skip(
            f"docker-compose.test.yaml not found in {fixtures_dir}. "
            "Create the file or start the container manually."
        )

    # Start isolated container via docker compose
    # cwd must be mt5linux directory for build context to work
    mt5linux_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=mt5linux_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.skip(
            f"Failed to start test container: {result.stderr}. "
            "Check if ../mt5docker exists and docker is available."
        )

    # Wait for rpyc server to be ready
    if not wait_for_port("localhost", TEST_RPYC_PORT):
        # Get logs for debug
        logs = subprocess.run(
            ["docker", "logs", TEST_CONTAINER_NAME, "--tail", "100"],
            capture_output=True,
            text=True,
            check=False,
        )
        pytest.skip(
            f"Container {TEST_CONTAINER_NAME} did not start in {TEST_TIMEOUT}s. "
            f"Logs: {logs.stdout[-500:] if logs.stdout else logs.stderr[-500:]}"
        )


@pytest.fixture(scope="session", autouse=True)
def docker_container() -> None:
    """Ensure ISOLATED test container is running.

    This fixture is session-scoped and autouse=True, so it runs
    automatically at the start of the test session.

    The container remains active after tests for reuse.
    To stop: docker compose -f tests/fixtures/docker-compose.test.yaml down
    """
    start_test_container()


@pytest.fixture
def mt5() -> Generator[MetaTrader5, None, None]:
    """Fixture with connected and initialized MetaTrader5.

    Connects to isolated test container on port 38812.
    Logs in with credentials from .env (see .env.example).

    Requires MT5_PASSWORD configured in .env.
    MT5_LOGIN is optional (uses demo account if not specified).

    Tests using this fixture will be SKIPPED if credentials are not configured.
    """
    if not _mt5_credentials_configured():
        pytest.skip(_SKIP_NO_CREDENTIALS)

    from mt5linux import MetaTrader5

    client = MetaTrader5(host="localhost", port=TEST_RPYC_PORT)

    result = client.initialize(
        login=TEST_MT5_LOGIN,
        password=TEST_MT5_PASSWORD,
        server=TEST_MT5_SERVER,
    )

    if not result:
        error = client.last_error()
        client.close()
        pytest.skip(f"Could not initialize MT5: {error}")

    yield client

    with contextlib.suppress(Exception):
        client.shutdown()
    client.close()


@pytest.fixture
def mt5_raw() -> Generator[MetaTrader5, None, None]:
    """Fixture with connected MetaTrader5 (without initialize).

    Useful for testing connection and lifecycle without login.
    Does NOT require MT5 credentials.
    """
    from mt5linux import MetaTrader5

    client = MetaTrader5(host="localhost", port=TEST_RPYC_PORT)
    yield client
    client.close()


# =============================================================================
# DATA GENERATION FIXTURES
# =============================================================================


@pytest.fixture
def major_pairs() -> list[str]:
    """Major forex pairs available on most brokers."""
    return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]


@pytest.fixture
def timeframes(mt5: MetaTrader5) -> list[int]:
    """Common timeframes for testing."""
    return [
        mt5.TIMEFRAME_M1,
        mt5.TIMEFRAME_M5,
        mt5.TIMEFRAME_H1,
        mt5.TIMEFRAME_D1,
    ]


@pytest.fixture
def date_range_week() -> tuple[datetime, datetime]:
    """Date range for last 7 days."""
    now = datetime.now(UTC)
    return (now - timedelta(days=7), now)


@pytest.fixture
def date_range_month() -> tuple[datetime, datetime]:
    """Date range for last 30 days."""
    now = datetime.now(UTC)
    return (now - timedelta(days=30), now)


@pytest.fixture
def date_range_year() -> tuple[datetime, datetime]:
    """Date range for last 365 days."""
    now = datetime.now(UTC)
    return (now - timedelta(days=365), now)


# =============================================================================
# TRADING FIXTURES
# =============================================================================

# Test magic number to identify test orders
TEST_MAGIC = 999999
TEST_COMMENT = "mt5linux_test"


@pytest.fixture
def buy_order_request(mt5: MetaTrader5) -> dict[str, Any]:
    """Build a market buy order request for testing.

    Uses minimum volume (0.01 lots) for safety.
    """
    tick = mt5.symbol_info_tick("EURUSD")
    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": "EURUSD",
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask if tick else 0,
        "deviation": 20,
        "magic": TEST_MAGIC,
        "comment": TEST_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }


@pytest.fixture
def sell_order_request(mt5: MetaTrader5) -> dict[str, Any]:
    """Build a market sell order request for testing.

    Uses minimum volume (0.01 lots) for safety.
    """
    tick = mt5.symbol_info_tick("EURUSD")
    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": "EURUSD",
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_SELL,
        "price": tick.bid if tick else 0,
        "deviation": 20,
        "magic": TEST_MAGIC,
        "comment": TEST_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }


@pytest.fixture
def cleanup_test_positions(mt5: MetaTrader5) -> Generator[None, None, None]:
    """Cleanup any test positions after test.

    Closes all positions with TEST_MAGIC number.
    """
    yield

    # Close all positions with test magic number
    positions = mt5.positions_get()
    if positions:
        for pos in positions:
            if pos.magic == TEST_MAGIC:
                # Build close request
                tick = mt5.symbol_info_tick(pos.symbol)
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": (
                        mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                    ),
                    "position": pos.ticket,
                    "price": tick.bid if pos.type == 0 else tick.ask,
                    "deviation": 20,
                    "magic": TEST_MAGIC,
                    "comment": "cleanup",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                mt5.order_send(close_request)


# =============================================================================
# MARKET DEPTH FIXTURES
# =============================================================================


@pytest.fixture
def market_book_symbol(mt5: MetaTrader5) -> Generator[str, None, None]:
    """Subscribe to market book and cleanup after test.

    Returns symbol name after subscribing.
    """
    symbol = "EURUSD"
    mt5.symbol_select(symbol, True)
    mt5.market_book_add(symbol)
    yield symbol
    mt5.market_book_release(symbol)
