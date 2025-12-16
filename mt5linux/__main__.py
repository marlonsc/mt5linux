"""Entry point for mt5linux.

mt5linux provides both client and server components for MetaTrader5 via RPyC.

Usage:
    # Show info (default)
    python -m mt5linux

    # Run server (on Windows with MT5)
    python -m mt5linux --server
    python -m mt5linux --server --host 0.0.0.0 --port 18812 --debug

    # Client usage (in Python code)
    from mt5linux import MetaTrader5
    with MetaTrader5(host="windows-ip", port=18812) as mt5:
        mt5.initialize(login=12345)
        account = mt5.account_info()
"""

from __future__ import annotations

import sys

from mt5linux import __version__


def _print_info() -> None:
    """Print package info and usage."""
    info = f"""\
mt5linux v{__version__} - MetaTrader5 Client/Server for Linux

Usage:
    python -m mt5linux              # Show this info
    python -m mt5linux --server     # Run RPyC server (Windows with MT5)

Server Options:
    --server              Start RPyC bridge server
    --host HOST           Bind address (default: 0.0.0.0)
    -p, --port PORT       Listen port (default: 18812)
    --threads N           Worker threads (default: 10)
    --timeout SECS        Request timeout (default: 300)
    -d, --debug           Enable debug logging

Client Usage (Python):
    from mt5linux import MetaTrader5, MT5Constants

    with MetaTrader5(host="windows-ip", port=18812) as mt5:
        mt5.initialize(login=12345, password="pass", server="Demo")
        account = mt5.account_info()
        rates = mt5.copy_rates_from_pos("EURUSD", MT5Constants.TimeFrame.H1, 0, 100)

Configuration:
    MT5_HOST          - Server host (default: localhost)
    MT5_RPYC_PORT     - Server port (default: 18812)

Documentation:
    https://www.mql5.com/en/docs/python_metatrader5
"""
    print(info)  # noqa: T201


def main() -> int:
    """Entry point."""
    args = sys.argv[1:]

    # Check for --server flag
    if "--server" in args or "-s" in args:
        # Remove --server/-s flag and pass remaining args to bridge
        server_args = [a for a in args if a not in ("--server", "-s")]
        from mt5linux.bridge import main as bridge_main

        return bridge_main(server_args)

    # Check for help
    if "-h" in args or "--help" in args:
        _print_info()
        return 0

    # Default: show info
    _print_info()
    return 0


if __name__ == "__main__":
    sys.exit(main())
