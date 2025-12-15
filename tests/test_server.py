"""Resilient server module tests (no MT5 credentials required).

Tests for ServerConfig, ResilientServer, and argument parsing.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mt5linux.__main__ import main
from mt5linux.server import (
    Server,
    ServerConfig,
    ServerMode,
    ServerState,
    parse_args,
)

if TYPE_CHECKING:
    import pytest


class TestServerConfig:
    """ServerConfig dataclass tests."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 18812
        assert config.mode == ServerMode.DIRECT
        assert config.wine_cmd == "wine"
        assert config.python_exe == "python.exe"
        assert config.max_restarts == 10
        assert config.restart_delay_base == 1.0
        assert config.restart_delay_max == 60.0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ServerConfig(
            host="127.0.0.1",
            port=8001,
            mode=ServerMode.WINE,
            wine_cmd="wine64",
            python_exe="python3.exe",
            max_restarts=5,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 8001
        assert config.mode == ServerMode.WINE
        assert config.wine_cmd == "wine64"
        assert config.python_exe == "python3.exe"
        assert config.max_restarts == 5

    def test_server_dir_conversion(self) -> None:
        """Test server_dir string to Path conversion."""
        config = ServerConfig(server_dir=Path("/tmp/test"))  # noqa: S108
        assert isinstance(config.server_dir, Path)
        assert config.server_dir == Path("/tmp/test")  # noqa: S108


class TestParseArgs:
    """Argument parsing tests."""

    def test_default_args(self) -> None:
        """Test default values."""
        config = parse_args([])
        assert config.host == "0.0.0.0"
        assert config.port == 18812
        assert config.mode == ServerMode.DIRECT

    def test_custom_host(self) -> None:
        """Test custom host."""
        config = parse_args(["--host", "127.0.0.1"])
        assert config.host == "127.0.0.1"

    def test_custom_port(self) -> None:
        """Test custom port."""
        config = parse_args(["--port", "8080"])
        assert config.port == 8080

    def test_short_port_flag(self) -> None:
        """Test short port flag."""
        config = parse_args(["-p", "9999"])
        assert config.port == 9999

    def test_wine_mode(self) -> None:
        """Test Wine mode activation."""
        config = parse_args(["--wine", "wine64"])
        assert config.mode == ServerMode.WINE
        assert config.wine_cmd == "wine64"

    def test_wine_short_flag(self) -> None:
        """Test short Wine flag."""
        config = parse_args(["-w", "wine"])
        assert config.mode == ServerMode.WINE

    def test_python_exe(self) -> None:
        """Test Python executable option."""
        config = parse_args(["--wine", "wine", "--python", "python3.exe"])
        assert config.python_exe == "python3.exe"

    def test_max_restarts(self) -> None:
        """Test max restarts option."""
        config = parse_args(["--max-restarts", "20"])
        assert config.max_restarts == 20

    def test_server_dir(self) -> None:
        """Test server directory option."""
        config = parse_args(["--wine", "wine", "--server-dir", "/opt/mt5"])
        assert config.server_dir == Path("/opt/mt5")

    def test_full_wine_config(self) -> None:
        """Test full Wine mode configuration."""
        config = parse_args(
            [
                "--host",
                "0.0.0.0",
                "-p",
                "8001",
                "--wine",
                "wine64",
                "--python",
                "python.exe",
                "--max-restarts",
                "15",
                "--server-dir",
                "/tmp/mt5test",  # noqa: S108
            ]
        )
        assert config.host == "0.0.0.0"
        assert config.port == 8001
        assert config.mode == ServerMode.WINE
        assert config.wine_cmd == "wine64"
        assert config.python_exe == "python.exe"
        assert config.max_restarts == 15
        assert config.server_dir == Path("/tmp/mt5test")  # noqa: S108


class TestServer:
    """Server class tests."""

    def test_server_creation(self) -> None:
        """Test server instantiation."""
        server = Server()
        assert server.state == ServerState.STOPPED
        assert server.restart_count == 0

    def test_server_with_config(self) -> None:
        """Test server with custom config."""
        config = ServerConfig(port=9999, max_restarts=3)
        server = Server(config)
        assert server.config.port == 9999
        assert server.config.max_restarts == 3

    def test_restart_delay_calculation(self) -> None:
        """Test exponential backoff calculation."""
        config = ServerConfig(
            restart_delay_base=1.0,
            restart_delay_multiplier=2.0,
            restart_delay_max=60.0,
        )
        server = Server(config)

        # Access private method for testing
        server._restart_count = 0
        assert server._calculate_restart_delay() == 1.0

        server._restart_count = 1
        assert server._calculate_restart_delay() == 2.0

        server._restart_count = 2
        assert server._calculate_restart_delay() == 4.0

        server._restart_count = 3
        assert server._calculate_restart_delay() == 8.0

        # Test max cap
        server._restart_count = 10
        delay = server._calculate_restart_delay()
        assert delay == 60.0  # Capped at max

    def test_health_check_no_server(self) -> None:
        """Test health check when no server is running."""
        server = Server(ServerConfig(port=59999))
        assert server.check_health() is False


class TestServerModes:
    """Server mode enum tests."""

    def test_mode_values(self) -> None:
        """Test mode enum values."""
        assert ServerMode.DIRECT.value == "direct"
        assert ServerMode.WINE.value == "wine"

    def test_mode_from_string(self) -> None:
        """Test mode enum from string."""
        assert ServerMode("direct") == ServerMode.DIRECT
        assert ServerMode("wine") == ServerMode.WINE


class TestServerState:
    """Server state enum tests."""

    def test_state_values(self) -> None:
        """Test state enum values."""
        assert ServerState.STOPPED.value == "stopped"
        assert ServerState.STARTING.value == "starting"
        assert ServerState.RUNNING.value == "running"
        assert ServerState.RESTARTING.value == "restarting"
        assert ServerState.STOPPING.value == "stopping"
        assert ServerState.FAILED.value == "failed"


class TestMainModule:
    """__main__ module tests."""

    def test_main_no_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main without command shows help."""
        monkeypatch.setattr(sys, "argv", ["mt5linux"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        result = main()

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        assert result == 1
        assert "mt5linux" in output

    def test_main_help_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main with help flag."""
        monkeypatch.setattr(sys, "argv", ["mt5linux", "--help"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        result = main()

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        assert result == 0
        assert "Usage" in output
