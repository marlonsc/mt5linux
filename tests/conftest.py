"""Test configuration and fixtures."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

# Load .env for test credentials
load_dotenv()

# Test container configuration
TEST_RPYC_PORT = int(os.getenv("MT5_RPYC_PORT", "38812"))
TEST_VNC_PORT = int(os.getenv("MT5_VNC_PORT", "33000"))
TEST_CONTAINER_NAME = os.getenv("MT5_CONTAINER_NAME", "mt5linux-unit")

# MT5 credentials for integration tests
MT5_TEST_CONFIG = {
    "host": os.getenv("MT5_HOST", "localhost"),
    "port": TEST_RPYC_PORT,
    "login": int(os.getenv("MT5_LOGIN", "0")),
    "password": os.getenv("MT5_PASSWORD", ""),
    "server": os.getenv("MT5_SERVER", "MetaQuotes-Demo"),
}


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: marks tests requiring MT5 server")
    config.addinivalue_line("markers", "unit: marks pure unit tests")


@pytest.fixture
def mt5_config() -> dict[str, str | int]:
    """Return MT5 test configuration."""
    return MT5_TEST_CONFIG.copy()
