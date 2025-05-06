"""
Main Module Entry Point.

Entrypoint for starting the MetaTrader5 RPyC server under Wine.

Usage:
    python -m mt5linux /path/to/windows/python.exe
    
    # With custom options
    python -m mt5linux /path/to/windows/python.exe --host 0.0.0.0 --port 18812
    
    # For help
    python -m mt5linux --help

This module supports both package and direct script execution.
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
    """
    Parse command-line arguments and start the MetaTrader5 RPyC server under Wine.
    
    This function sets up the argument parser, processes command-line arguments,
    and launches the RPyC server using the specified Windows Python executable
    under Wine.
    
    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Start the MetaTrader5 RPyC server under Wine.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "python",
        type=str,
        help="Path to the Windows Python executable (must be a Windows version!)",
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address to bind the server to",
    )
    
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=(
            f"TCP listener port (default = {DEFAULT_SERVER_PORT}, "
            f"default for SSL = {DEFAULT_SERVER_SSL_PORT})"
        ),
    )
    
    parser.add_argument(
        "-w",
        "--wine",
        type=str,
        default="wine",
        help="Command to call Wine",
    )
    
    parser.add_argument(
        "-s",
        "--server",
        type=str,
        default="/tmp/mt5linux",
        help="Path where the server will be built and run",
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
