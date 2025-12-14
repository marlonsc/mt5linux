"""Entry point para mt5linux.

Usage:
    python -m mt5linux server --host 0.0.0.0 --port 18812
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_PORT = 18812


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="mt5linux - MetaTrader5 bridge para Linux",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando")

    server_parser = subparsers.add_parser(
        "server",
        help="Inicia servidor rpyc",
    )
    server_parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Host para bind",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Porta para listen",
    )

    args = parser.parse_args()

    if args.command == "server":
        from mt5linux.server import run_server

        run_server(host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
