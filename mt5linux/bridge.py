"""RPyC bridge for MetaTrader5 - runs inside Wine.

This module provides the MT5Service RPyC server that runs inside Wine
with Windows Python + MetaTrader5 module.

Features:
- Modern rpyc.Service (NOT deprecated SlaveService/ClassicService)
- ThreadPoolServer for concurrent handling
- Signal handling (SIGTERM/SIGINT) for clean container stops
- Data materialization (_asdict() for NamedTuples)
- Chunked symbols_get for large datasets (9000+)
- NO STUBS - fails if MT5 unavailable

Usage:
    wine python.exe -m mt5linux.bridge --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from types import FrameType
from typing import Any

import rpyc
from rpyc.utils.server import ThreadPoolServer

# Global server reference for signal handler
_server: ThreadPoolServer | None = None


class MT5Service(rpyc.Service):
    """Modern RPyC service for MT5. NO STUBS."""

    _mt5_module: Any = None
    _mt5_lock = threading.RLock()

    def on_connect(self, conn: rpyc.Connection) -> None:  # noqa: ARG002
        with MT5Service._mt5_lock:
            if MT5Service._mt5_module is None:
                import MetaTrader5  # pyright: ignore[reportMissingImports]

                MT5Service._mt5_module = MetaTrader5
                print("[mt5bridge] MT5 module loaded")  # noqa: T201

    def on_disconnect(self, _conn: rpyc.Connection) -> None:
        pass

    def exposed_get_mt5(self) -> Any:
        return MT5Service._mt5_module

    def exposed_health_check(self) -> dict[str, Any]:
        return {"healthy": True, "mt5_available": MT5Service._mt5_module is not None}

    def exposed_reset_circuit_breaker(self) -> bool:
        """Reset circuit breaker (compatibility with client)."""
        return True

    def exposed_initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int | None = None,
        portable: bool = False,
    ) -> bool:
        # Build kwargs, only including non-None values
        # MT5 doesn't accept None for login/password/server
        kwargs: dict[str, Any] = {}
        if path is not None:
            kwargs["path"] = path
        if login is not None:
            kwargs["login"] = login
        if password is not None:
            kwargs["password"] = password
        if server is not None:
            kwargs["server"] = server
        if timeout is not None:
            kwargs["timeout"] = timeout
        if portable:
            kwargs["portable"] = portable
        return MT5Service._mt5_module.initialize(**kwargs)

    def exposed_login(
        self, login: int, password: str, server: str, timeout: int = 60000
    ) -> bool:
        return MT5Service._mt5_module.login(
            login=login, password=password, server=server, timeout=timeout
        )

    def exposed_shutdown(self) -> None:
        return MT5Service._mt5_module.shutdown()

    def exposed_version(self) -> tuple[int, int, str] | None:
        return MT5Service._mt5_module.version()

    def exposed_last_error(self) -> tuple[int, str]:
        return MT5Service._mt5_module.last_error()

    def exposed_terminal_info(self) -> Any:
        """Get terminal info with data materialization."""
        result = MT5Service._mt5_module.terminal_info()
        if result is None:
            return None
        return result._asdict()

    def exposed_account_info(self) -> Any:
        """Get account info with data materialization."""
        result = MT5Service._mt5_module.account_info()
        if result is None:
            return None
        return result._asdict()

    def exposed_symbols_total(self) -> int:
        return MT5Service._mt5_module.symbols_total()

    def exposed_symbols_get(self, group: str | None = None) -> Any:
        """Get symbols with chunked streaming to prevent IPC timeout.

        MT5 returns SymbolInfo named tuples. For large symbol lists (9000+),
        the MT5 IPC connection times out if we don't complete the call quickly.

        Solution:
        1. Get data from MT5 immediately (completes IPC)
        2. Convert to list right away (releases MT5 objects)
        3. Materialize and return in chunks for efficient transfer
        """
        if group:
            result = MT5Service._mt5_module.symbols_get(group=group)
        else:
            result = MT5Service._mt5_module.symbols_get()

        if result is None:
            return None

        # IMMEDIATELY convert to list - this completes the MT5 IPC call
        # After this, we own the data and MT5 IPC is free
        items = list(result)
        total = len(items)

        # For small results, return directly
        chunk_size = 500
        if total <= chunk_size:
            return {"total": total, "chunks": [tuple(s._asdict() for s in items)]}

        # For large results, chunk the materialization
        chunks = []
        for i in range(0, total, chunk_size):
            chunk = tuple(s._asdict() for s in items[i : i + chunk_size])
            chunks.append(chunk)

        return {"total": total, "chunks": chunks}

    def exposed_symbol_info(self, symbol: str) -> Any:
        """Get symbol info with data materialization."""
        result = MT5Service._mt5_module.symbol_info(symbol)
        if result is None:
            return None
        return result._asdict()

    def exposed_symbol_info_tick(self, symbol: str) -> Any:
        """Get symbol tick with data materialization."""
        result = MT5Service._mt5_module.symbol_info_tick(symbol)
        if result is None:
            return None
        return result._asdict()

    def exposed_symbol_select(self, symbol: str, enable: bool = True) -> bool:
        return MT5Service._mt5_module.symbol_select(symbol, enable)

    def exposed_copy_rates_from(
        self, symbol: str, timeframe: int, date_from: Any, count: int
    ) -> Any:
        return MT5Service._mt5_module.copy_rates_from(
            symbol, timeframe, date_from, count
        )

    def exposed_copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        return MT5Service._mt5_module.copy_rates_from_pos(
            symbol, timeframe, start_pos, count
        )

    def exposed_copy_rates_range(
        self, symbol: str, timeframe: int, date_from: Any, date_to: Any
    ) -> Any:
        return MT5Service._mt5_module.copy_rates_range(
            symbol, timeframe, date_from, date_to
        )

    def exposed_copy_ticks_from(
        self, symbol: str, date_from: Any, count: int, flags: int
    ) -> Any:
        return MT5Service._mt5_module.copy_ticks_from(
            symbol, date_from, count, flags
        )

    def exposed_copy_ticks_range(
        self, symbol: str, date_from: Any, date_to: Any, flags: int
    ) -> Any:
        return MT5Service._mt5_module.copy_ticks_range(
            symbol, date_from, date_to, flags
        )

    def exposed_order_calc_margin(
        self, action: int, symbol: str, volume: float, price: float
    ) -> float | None:
        return MT5Service._mt5_module.order_calc_margin(
            action, symbol, volume, price
        )

    def exposed_order_calc_profit(
        self,
        action: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> float | None:
        return MT5Service._mt5_module.order_calc_profit(
            action, symbol, volume, price_open, price_close
        )

    def exposed_order_check(self, request: dict[str, Any]) -> Any:
        """Check order with data materialization."""
        local_request = dict(request)
        result = MT5Service._mt5_module.order_check(local_request)
        if result is None:
            return None
        return result._asdict()

    def exposed_order_send(self, request: dict[str, Any]) -> Any:
        """Send order with data materialization."""
        local_request = dict(request)
        result = MT5Service._mt5_module.order_send(local_request)
        if result is None:
            return None
        return result._asdict()

    def exposed_positions_total(self) -> int:
        return MT5Service._mt5_module.positions_total()

    def exposed_positions_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get positions with data materialization."""
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            result = MT5Service._mt5_module.positions_get(**kwargs)
        else:
            result = MT5Service._mt5_module.positions_get()
        if result is None:
            return None
        return tuple(p._asdict() for p in result)

    def exposed_orders_total(self) -> int:
        return MT5Service._mt5_module.orders_total()

    def exposed_orders_get(
        self,
        symbol: str | None = None,
        group: str | None = None,
        ticket: int | None = None,
    ) -> Any:
        """Get orders with data materialization."""
        kwargs: dict[str, Any] = {}
        if symbol:
            kwargs["symbol"] = symbol
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if kwargs:
            result = MT5Service._mt5_module.orders_get(**kwargs)
        else:
            result = MT5Service._mt5_module.orders_get()
        if result is None:
            return None
        return tuple(o._asdict() for o in result)

    def exposed_history_orders_total(self, date_from: Any, date_to: Any) -> int | None:
        return MT5Service._mt5_module.history_orders_total(date_from, date_to)

    def exposed_history_orders_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get history orders with data materialization."""
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            result = MT5Service._mt5_module.history_orders_get(**kwargs)
        else:
            result = MT5Service._mt5_module.history_orders_get()
        if result is None:
            return None
        return tuple(o._asdict() for o in result)

    def exposed_history_deals_total(self, date_from: Any, date_to: Any) -> int | None:
        return MT5Service._mt5_module.history_deals_total(date_from, date_to)

    def exposed_history_deals_get(
        self,
        date_from: Any = None,
        date_to: Any = None,
        group: str | None = None,
        ticket: int | None = None,
        position: int | None = None,
    ) -> Any:
        """Get history deals with data materialization."""
        kwargs: dict[str, Any] = {}
        if date_from:
            kwargs["date_from"] = date_from
        if date_to:
            kwargs["date_to"] = date_to
        if group:
            kwargs["group"] = group
        if ticket:
            kwargs["ticket"] = ticket
        if position:
            kwargs["position"] = position
        if kwargs:
            result = MT5Service._mt5_module.history_deals_get(**kwargs)
        else:
            result = MT5Service._mt5_module.history_deals_get()
        if result is None:
            return None
        return tuple(d._asdict() for d in result)


def graceful_shutdown(signum: int, frame: FrameType | None) -> None:  # noqa: ARG001
    """Handle shutdown signals for clean container stops."""
    sig_name = signal.Signals(signum).name
    print(f"[mt5bridge] Received {sig_name}, shutting down gracefully...")  # noqa: T201
    if _server is not None:
        _server.close()
    sys.exit(0)


def main() -> int:
    """Run the RPyC bridge server."""
    global _server  # noqa: PLW0603

    parser = argparse.ArgumentParser(description="MT5 RPyC Bridge Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind"  # noqa: S104
    )
    parser.add_argument("-p", "--port", type=int, default=8001, help="Port")
    parser.add_argument("--threads", type=int, default=10, help="Worker threads")
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout")
    args = parser.parse_args()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    print(f"[mt5bridge] Starting MT5Service on {args.host}:{args.port}")  # noqa: T201
    print(f"[mt5bridge] Python {sys.version}")  # noqa: T201
    print("[mt5bridge] Using modern rpyc.Service (NO SlaveService/ClassicService)")  # noqa: T201

    _server = ThreadPoolServer(
        MT5Service,
        hostname=args.host,
        port=args.port,
        reuse_addr=True,
        nbThreads=args.threads,
        protocol_config={
            "allow_public_attrs": True,
            "allow_pickle": True,
            "sync_request_timeout": args.timeout,
        },
    )

    try:
        _server.start()
    except KeyboardInterrupt:
        print("[mt5bridge] Server interrupted")  # noqa: T201
    except Exception as e:  # noqa: BLE001
        print(f"[mt5bridge] Server error: {e}")  # noqa: T201
        return 1
    finally:
        if _server is not None:
            _server.close()
        print("[mt5bridge] Server stopped")  # noqa: T201

    return 0


if __name__ == "__main__":
    sys.exit(main())
