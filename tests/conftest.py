"""Test configuration and fixtures."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from mt5linux import MetaTrader5

# Load .env for test credentials
load_dotenv()

# Paths
TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
COMPOSE_FILE = FIXTURES_DIR / "docker-compose.test.yaml"
PROJECT_ROOT = TESTS_DIR.parent
CODEGEN_SCRIPT = PROJECT_ROOT / "scripts" / "codegen_enums.py"

# Test container configuration
TEST_RPYC_HOST = os.getenv("MT5_HOST", "localhost")
TEST_RPYC_PORT = int(os.getenv("MT5_RPYC_PORT", "38812"))
TEST_VNC_PORT = int(os.getenv("MT5_VNC_PORT", "33000"))
TEST_CONTAINER_NAME = os.getenv("MT5_CONTAINER_NAME", "mt5linux-unit")

# MT5 credentials for integration tests
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "MetaQuotes-Demo")

MT5_CONFIG: dict[str, str | int] = {
    "host": TEST_RPYC_HOST,
    "port": TEST_RPYC_PORT,
    "login": MT5_LOGIN,
    "password": MT5_PASSWORD,
    "server": MT5_SERVER,
}


@pytest.fixture(scope="session", autouse=True)
def ensure_docker_and_codegen() -> Generator[None, None, None]:
    """Start test Docker container and run codegen before all tests.

    This fixture:
    1. Starts the test container from tests/fixtures/docker-compose.test.yaml
    2. Waits for container to be healthy
    3. Runs codegen_enums.py to regenerate enums
    4. Fails if codegen fails or enums.py has uncommitted changes
    5. Stops container after all tests complete
    """
    # Start test container
    print("\n[conftest] Starting test Docker container...")
    try:
        subprocess.run(
            [  # noqa: S607
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
                "--wait",
            ],
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to start test container:\n{e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        pytest.fail("Timeout waiting for test container to start")

    print("[conftest] Test container started")

    # Run codegen
    print("[conftest] Running codegen_enums.py...")
    try:
        result = subprocess.run(
            [sys.executable, str(CODEGEN_SCRIPT), "--check"],  # noqa: S603
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=60,
        )
        if result.returncode != 0:
            pytest.fail(
                f"codegen_enums.py failed:\n{result.stdout}\n{result.stderr}"
            )
    except subprocess.TimeoutExpired:
        pytest.fail("Timeout running codegen_enums.py")

    print("[conftest] Codegen complete")

    yield

    # Teardown: stop container
    print("\n[conftest] Stopping test container...")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],  # noqa: S607, S603
        cwd=PROJECT_ROOT,
        capture_output=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: marks tests requiring MT5 server")
    config.addinivalue_line("markers", "unit: marks pure unit tests")
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "trading: marks tests that place real orders")
    config.addinivalue_line(
        "markers", "market_depth: marks tests requiring market depth"
    )


@pytest.fixture
def mt5_config() -> dict[str, str | int]:
    """Return MT5 test configuration."""
    return MT5_CONFIG.copy()


@pytest.fixture
def mt5_raw() -> Generator[MetaTrader5]:
    """Return raw MT5 connection (no initialize).

    This fixture creates a connection to the rpyc server but does NOT
    call initialize(). Use for testing connection lifecycle.
    """
    mt5 = MetaTrader5(host=TEST_RPYC_HOST, port=TEST_RPYC_PORT)
    yield mt5
    with contextlib.suppress(Exception):
        mt5.close()


@pytest.fixture
def mt5(mt5_raw: MetaTrader5) -> Generator[MetaTrader5]:
    """Return fully initialized MT5 client.

    This fixture connects AND initializes the MT5 terminal.
    Skips test if MT5_LOGIN is not configured (=0) or if
    initialization fails.
    """
    if MT5_LOGIN == 0:
        pytest.skip("MT5_LOGIN not configured - set MT5_LOGIN env var")

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
        positions = mt5.positions_get(magic=123456)
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
