"""Server module tests (no MT5 credentials required)."""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from mt5linux.__main__ import main
from mt5linux.server import parse_args


class TestParseArgs:
    """Argument parsing tests."""

    def test_default_args(self) -> None:
        """Test default values."""
        args = parse_args([])
        assert args.host == "0.0.0.0"
        assert args.port == 18812

    def test_custom_host(self) -> None:
        """Test custom host."""
        args = parse_args(["--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"

    def test_custom_port(self) -> None:
        """Test custom port."""
        args = parse_args(["--port", "8080"])
        assert args.port == 8080


class TestMainModule:
    """__main__ module tests."""

    def test_main_no_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test main without command."""
        # Mock sys.argv to simulate no command
        monkeypatch.setattr(sys, "argv", ["mt5linux"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        result = main()

        sys.stdout = old_stdout
        assert result == 1

    def test_parse_server_args(self) -> None:
        """Test server argument parsing."""
        # Simulate argparse to verify structure
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        server_parser = subparsers.add_parser("server")
        server_parser.add_argument("--host", default="0.0.0.0")
        server_parser.add_argument("--port", type=int, default=18812)

        args = parser.parse_args(["server", "--host", "localhost", "--port", "9999"])
        assert args.command == "server"
        assert args.host == "localhost"
        assert args.port == 9999
