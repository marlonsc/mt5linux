"""
Pytest configuration and fixtures for mt5linux tests.

This module provides:
- Mock fixtures for rpyc connection (unit tests without MT5 server)
- Integration fixtures for real MT5 connection
- Pytest markers configuration
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# Test credentials (MetaQuotes Demo)
MT5_LOGIN = 10008704586
MT5_PASSWORD = "Lw!8IzEe"
MT5_SERVER = "MetaQuotes-Demo"
MT5_HOST = os.environ.get("MT5_HOST", "localhost")
MT5_PORT = int(os.environ.get("MT5_PORT", "8001"))


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires MT5 server)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require MT5 server",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless --run-integration is passed."""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


class MockRpycConnection:
    """Mock rpyc connection for unit testing."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"sync_request_timeout": 300}
        self._executed_code: list[str] = []
        self._eval_responses: dict[str, Any] = {}

    def execute(self, code: str) -> None:
        """Record executed code."""
        self._executed_code.append(code)

    def eval(self, code: str) -> Any:
        """Return mock response for evaluated code."""
        if code in self._eval_responses:
            return self._eval_responses[code]
        if "mt5.initialize" in code:
            return True
        if "mt5.terminal_info" in code:
            return MockTerminalInfo()
        if "mt5.account_info" in code:
            return MockAccountInfo()
        if "mt5.version" in code:
            return (500, 5430, "13 Dec 2024")
        if "mt5.last_error" in code:
            return (1, "Success")
        if "mt5.shutdown" in code:
            return True
        if "mt5.symbols_total" in code:
            return 100
        return None

    def close(self) -> None:
        """Close mock connection."""
        pass

    def set_response(self, code: str, response: Any) -> None:
        """Set a custom response for specific code."""
        self._eval_responses[code] = response


class MockTerminalInfo:
    """Mock terminal info response."""

    community_account = True
    community_connection = True
    connected = True
    dlls_allowed = True
    trade_allowed = True
    tradeapi_disabled = False
    email_enabled = False
    ftp_enabled = False
    notifications_enabled = False
    mqid = True
    build = 5430
    maxbars = 100000
    codepage = 0
    ping_last = 10
    community_balance = 0.0
    retransmission = 0.0
    company = "MetaQuotes Software Corp."
    name = "MetaTrader 5"
    language = "English"
    path = "C:\\Program Files\\MetaTrader 5"
    data_path = "C:\\Users\\user\\AppData\\Roaming\\MetaQuotes\\Terminal"
    commondata_path = "C:\\Users\\user\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common"


class MockAccountInfo:
    """Mock account info response."""

    login = MT5_LOGIN
    trade_mode = 0  # DEMO
    leverage = 100
    limit_orders = 200
    margin_so_mode = 0
    trade_allowed = True
    trade_expert = True
    margin_mode = 0
    currency_digits = 2
    fifo_close = False
    balance = 10000.0
    credit = 0.0
    profit = 0.0
    equity = 10000.0
    margin = 0.0
    margin_free = 10000.0
    margin_level = 0.0
    margin_so_call = 50.0
    margin_so_so = 30.0
    margin_initial = 0.0
    margin_maintenance = 0.0
    assets = 0.0
    liabilities = 0.0
    commission_blocked = 0.0
    name = "Demo Account"
    server = MT5_SERVER
    currency = "USD"
    company = "MetaQuotes Software Corp."


@pytest.fixture
def mock_rpyc_connection() -> Generator[MockRpycConnection, None, None]:
    """Provide a mock rpyc connection for unit tests."""
    mock_conn = MockRpycConnection()
    with patch("rpyc.classic.connect", return_value=mock_conn):
        yield mock_conn


@pytest.fixture
def mock_mt5(mock_rpyc_connection: MockRpycConnection) -> Generator[Any, None, None]:
    """Provide a MetaTrader5 instance with mocked connection."""
    from mt5linux import MetaTrader5

    mt5 = MetaTrader5(host="localhost", port=18812)
    yield mt5


@pytest.fixture
def mt5_credentials() -> dict[str, Any]:
    """Provide MT5 demo credentials."""
    return {
        "login": MT5_LOGIN,
        "password": MT5_PASSWORD,
        "server": MT5_SERVER,
    }


@pytest.fixture
def mt5_connection_params() -> dict[str, Any]:
    """Provide MT5 connection parameters."""
    return {
        "host": MT5_HOST,
        "port": MT5_PORT,
    }


@pytest.fixture
def real_mt5(mt5_connection_params: dict[str, Any]) -> Generator[Any, None, None]:
    """
    Provide a real MetaTrader5 instance for integration tests.

    This fixture requires MT5 server to be running (mt5docker).
    """
    from mt5linux import MetaTrader5

    mt5 = MetaTrader5(**mt5_connection_params)
    yield mt5
    try:
        mt5.shutdown()
    except Exception:
        pass
