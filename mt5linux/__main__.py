"""
__main__.py - Entrypoint for MetaTrader5 RPyC Server under Wine

Entrypoint for starting the MetaTrader5 RPyC server under Wine. Supports both module and direct script execution.

Usage:
    python -m mt5linux
"""

import argparse

try:
    from rpyc.utils.classic import DEFAULT_SERVER_PORT, DEFAULT_SERVER_SSL_PORT
except ImportError:
    from rpyc import DEFAULT_SERVER_PORT, DEFAULT_SERVER_SSL_PORT

# Dual import pattern for robust CLI entrypoints
# type: ignore[import]
# pylint: disable=import-error
try:
    from .wine_server_launcher import launch_wine_rpyc_server  # type: ignore
except ImportError:
    from wine_server_launcher import launch_wine_rpyc_server  # type: ignore
# pylint: enable=import-error


def main() -> None:
    """Parse command-line arguments and start the MetaTrader5 RPyC server under Wine.


    :rtype: None

    """
    parser = argparse.ArgumentParser(description="Create Server.")
    parser.add_argument(
        "python",
        type=str,
        help=("Python executable to run the server (must be a Windows version!)"),
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help=("The host to connect to. Default is localhost."),
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=(
            f"TCP listener port (default = {DEFAULT_SERVER_PORT!r}, "
            f"default for SSL = {DEFAULT_SERVER_SSL_PORT!r})"
        ),
    )
    parser.add_argument(
        "-w",
        "--wine",
        type=str,
        default="wine",
        help="Command to call wine (default = wine).",
    )
    parser.add_argument(
        "-s",
        "--server",
        type=str,
        default="/tmp/mt5linux",
        help=("Path where the server will be built and run (default = /tmp/mt5linux)."),
    )
    args = parser.parse_args()
    launch_wine_rpyc_server(
        win_python_path=args.python,
        host=args.host,
        port=args.port,
        wine_cmd=args.wine,
        server_dir=args.server,
    )


if __name__ == "__main__":
    main()
