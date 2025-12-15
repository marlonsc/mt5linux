"""Entry point for mt5linux.

Usage:
    # Wine mode (for mt5docker - runs RPyC server via Wine):
    python -m mt5linux --wine wine --python python.exe -p 8001
    python -m mt5linux -w wine python.exe -p 8001

    # Direct server mode (runs RPyC server on Linux):
    python -m mt5linux --port 18812
    python -m mt5linux server --host 0.0.0.0 --port 18812

    # Help:
    python -m mt5linux --help
"""

from __future__ import annotations

import sys

import structlog

from mt5linux.server import (
    Server,
    ServerConfig,
    parse_args,
)

log = structlog.get_logger("mt5linux.main")


def _print_help() -> None:
    """Print usage help."""
    print(  # noqa: T201
        """mt5linux - MetaTrader5 bridge for Linux

Usage:
  Wine mode (for mt5docker - runs RPyC server via Wine):
    python -m mt5linux --wine wine --python python.exe
    python -m mt5linux -w wine python.exe -p 8001
    python -m mt5linux --wine wine --python python.exe -p 8001 --max-restarts 5

  Direct server mode (runs RPyC server on Linux):
    python -m mt5linux
    python -m mt5linux server --host 0.0.0.0 --port 18812

Options:
  --host HOST           Host to bind (default: 0.0.0.0)
  -p, --port PORT       Port to listen on (default: 18812)
  -w, --wine CMD        Wine command (enables Wine mode)
  --python PATH         Python executable for Wine mode (default: python.exe)
  --max-restarts N      Maximum restart attempts (default: 10)
  --server-dir DIR      Directory for generated server script

Features:
  - Automatic restart on failure with exponential backoff
  - Structured logging via structlog
  - Graceful shutdown on SIGTERM/SIGINT
  - Health check support

Examples:
  # Start server for mt5docker container
  python -m mt5linux -w wine python.exe -p 8001

  # Start direct server for local development
  python -m mt5linux --port 18812

  # With custom restart settings
  python -m mt5linux -w wine python.exe --max-restarts 20
""",
    )


def _find_python_exe(argv: list[str]) -> str | None:
    """Find Python executable in legacy argument format."""
    for arg in argv:
        if not arg.startswith("-") and (
            arg.endswith(".exe") or arg in {"python", "python3"}
        ):
            return arg
    return None


def _convert_legacy_wine_args(argv: list[str], python_exe: str) -> list[str]:
    """Convert legacy Wine mode arguments to new format."""
    new_argv = ["--wine", "wine", "--python", python_exe]

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == python_exe:
            i += 1
            continue
        if arg in {"-p", "--port"} and i + 1 < len(argv):
            new_argv.extend(["-p", argv[i + 1]])
            i += 2
            continue
        if arg in {"-w", "--wine"} and i + 1 < len(argv):
            new_argv[1] = argv[i + 1]  # Override wine command
            i += 2
            continue
        if arg == "--host" and i + 1 < len(argv):
            new_argv.extend(["--host", argv[i + 1]])
            i += 2
            continue
        if arg in {"-s", "--server-dir"} and i + 1 < len(argv):
            new_argv.extend(["--server-dir", argv[i + 1]])
            i += 2
            continue
        i += 1

    return new_argv


def _parse_legacy_args(argv: list[str]) -> ServerConfig | None:
    """Parse legacy command line format for backwards compatibility.

    Supports:
        python -m mt5linux python.exe -p 8001 -w wine
        python -m mt5linux server --host 0.0.0.0 --port 18812

    Returns:
        ServerConfig if parsed successfully, None otherwise.
    """
    if not argv:
        return None

    # Check for "server" subcommand (legacy direct mode)
    if argv[0] == "server":
        return parse_args(argv[1:])

    # Check for positional python.exe argument (legacy Wine mode)
    python_exe = _find_python_exe(argv)
    if python_exe:
        new_argv = _convert_legacy_wine_args(argv, python_exe)
        return parse_args(new_argv)

    return None


def main() -> int:
    """Entry point."""
    argv = sys.argv[1:]

    # Check for help flag
    if "-h" in argv or "--help" in argv or not argv:
        _print_help()
        return 0 if argv else 1

    # Try legacy argument format first
    config = _parse_legacy_args(argv)
    arg_format = "legacy"

    # Fall back to new argument format
    if config is None:
        try:
            config = parse_args(argv)
            arg_format = "standard"
        except SystemExit:
            _print_help()
            return 1

    log.info("parsed_arguments", format=arg_format, mode=config.mode.value)

    # Run server
    server = Server(config)

    try:
        server.run(blocking=True)
    except KeyboardInterrupt:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
