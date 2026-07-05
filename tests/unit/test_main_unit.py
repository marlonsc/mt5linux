"""Unit tests for mt5linux.__main__.

These tests exercise the CLI entry point without starting a real gRPC server or
importing the bridge machinery.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from mt5linux import __main__ as main_module

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.fixture
def reset_argv() -> None:
    """Restore sys.argv after each test."""
    original = sys.argv[:]
    yield
    sys.argv = original


class TestMainInfo:
    """Default and help invocations show usage info."""

    def test_main_no_args_prints_info(self, reset_argv: None) -> None:
        """Running without arguments prints package info and returns 0."""
        with patch.object(main_module, "_print_info") as print_mock:
            result = main_module.main()
        print_mock.assert_called_once()
        assert result == 0

    def test_main_help_flag_prints_info(self, reset_argv: None) -> None:
        """--help prints info and returns 0."""
        with (
            patch("sys.argv", ["mt5linux", "--help"]),
            patch.object(main_module, "_print_info") as print_mock,
        ):
            result = main_module.main()
        print_mock.assert_called_once()
        assert result == 0

    def test_main_short_help_flag_prints_info(self, reset_argv: None) -> None:
        """-h prints info and returns 0."""
        with (
            patch("sys.argv", ["mt5linux", "-h"]),
            patch.object(main_module, "_print_info") as print_mock,
        ):
            result = main_module.main()
        print_mock.assert_called_once()
        assert result == 0


class TestMainServer:
    """--server mode forwards arguments to the bridge."""

    def test_main_server_flag_runs_bridge(self, reset_argv: None) -> None:
        """--server removes the flag and calls _bridge_main with remaining args."""
        with (
            patch("sys.argv", ["mt5linux", "--server", "--port", "8080"]),
            patch.object(main_module, "_bridge_main", return_value=42) as bridge_mock,
        ):
            result = main_module.main()
        bridge_mock.assert_called_once_with(["--port", "8080"])
        assert result == 42

    def test_main_short_server_flag_runs_bridge(self, reset_argv: None) -> None:
        """-s removes the flag and calls _bridge_main with remaining args."""
        with (
            patch("sys.argv", ["mt5linux", "-s", "--host", "example.com"]),
            patch.object(main_module, "_bridge_main", return_value=0) as bridge_mock,
        ):
            result = main_module.main()
        bridge_mock.assert_called_once_with(["--host", "example.com"])
        assert result == 0

    def test_main_server_no_extra_args(self, reset_argv: None) -> None:
        """--server alone passes an empty argument list to _bridge_main."""
        with (
            patch("sys.argv", ["mt5linux", "--server"]),
            patch.object(main_module, "_bridge_main", return_value=0) as bridge_mock,
        ):
            result = main_module.main()
        bridge_mock.assert_called_once_with([])
        assert result == 0

    def test_main_server_and_help_together_prefers_server(
        self, reset_argv: None
    ) -> None:
        """If --server is present it takes precedence over --help."""
        with (
            patch("sys.argv", ["mt5linux", "--server", "--help"]),
            patch.object(main_module, "_bridge_main", return_value=0) as bridge_mock,
            patch.object(main_module, "_print_info") as print_mock,
        ):
            result = main_module.main()
        bridge_mock.assert_called_once_with(["--help"])
        print_mock.assert_not_called()
        assert result == 0


class TestPrintInfo:
    """Info text covers the expected topics."""

    def test_print_info_contains_version(self, reset_argv: None) -> None:
        """_print_info() includes the package version."""
        with patch.object(main_module.logger, "info") as log_mock:
            main_module._print_info()
        message = log_mock.call_args[0][0]
        assert main_module.__version__ in message
        assert "mt5linux" in message.lower()

    def test_print_info_contains_usage(self, reset_argv: None) -> None:
        """_print_info() includes usage examples."""
        with patch.object(main_module.logger, "info") as log_mock:
            main_module._print_info()
        message = log_mock.call_args[0][0]
        assert "python -m mt5linux" in message


@pytest.mark.parametrize(
    ("argv", "expected_calls"),
    [
        (["mt5linux"], {"print": 1, "bridge": 0}),
        (["mt5linux", "--help"], {"print": 1, "bridge": 0}),
        (["mt5linux", "-h"], {"print": 1, "bridge": 0}),
        (["mt5linux", "--server"], {"print": 0, "bridge": 1}),
        (["mt5linux", "-s"], {"print": 0, "bridge": 1}),
    ],
)
def test_main_routing_table(
    reset_argv: None,
    argv: Sequence[str],
    expected_calls: dict[str, int],
) -> None:
    """Parameterized routing check for all CLI modes."""
    with (
        patch("sys.argv", argv),
        patch.object(main_module, "_print_info") as print_mock,
        patch.object(main_module, "_bridge_main", return_value=0) as bridge_mock,
    ):
        main_module.main()
    assert print_mock.call_count == expected_calls["print"]
    assert bridge_mock.call_count == expected_calls["bridge"]
