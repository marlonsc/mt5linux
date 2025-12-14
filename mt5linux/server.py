"""RPyC server for mt5linux.

Classic rpyc server that exposes the MetaTrader5 module.
Runs on Windows/Wine with MetaTrader5 installed.

Usage:
    python -m mt5linux.server --host 0.0.0.0 --port 18812
"""

from __future__ import annotations

import argparse
import logging
from argparse import Namespace

from rpyc.core import SlaveService
from rpyc.utils.server import ThreadedServer

DEFAULT_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_PORT = 18812

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mt5linux.server")


def parse_args(args: list[str] | None = None) -> Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="RPyC server for MetaTrader5",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port to listen on",
    )
    return parser.parse_args(args)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run RPyC classic server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
    """

    logger.info("Starting RPyC server on %s:%d", host, port)

    server = ThreadedServer(
        SlaveService,
        hostname=host,
        port=port,
        reuse_addr=True,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


def main() -> None:
    """Entry point."""
    args = parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
