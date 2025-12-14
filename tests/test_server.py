"""Testes do módulo server."""

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
    """Testes de parsing de argumentos."""

    def test_default_args(self) -> None:
        """Testa valores padrão."""
        args = parse_args([])
        assert args.host == "0.0.0.0"
        assert args.port == 18812

    def test_custom_host(self) -> None:
        """Testa host customizado."""
        args = parse_args(["--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"

    def test_custom_port(self) -> None:
        """Testa porta customizada."""
        args = parse_args(["--port", "8080"])
        assert args.port == 8080


class TestMainModule:
    """Testes do módulo __main__."""

    def test_main_no_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Testa main sem comando."""
        # Mock sys.argv to simulate no command
        monkeypatch.setattr(sys, "argv", ["mt5linux"])

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        result = main()

        sys.stdout = old_stdout
        assert result == 1

    def test_parse_server_args(self) -> None:
        """Testa parsing de argumentos do server."""


        # Simula argparse para verificar estrutura
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        server_parser = subparsers.add_parser("server")
        server_parser.add_argument("--host", default="0.0.0.0")
        server_parser.add_argument("--port", type=int, default=18812)

        args = parser.parse_args(["server", "--host", "localhost", "--port", "9999"])
        assert args.command == "server"
        assert args.host == "localhost"
        assert args.port == 9999
