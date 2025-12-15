"""MetaTrader5 client - transparent bridge via rpyc.

Fail-fast error handling:
- ConnectionError raised when MT5 connection not established
- Cleanup errors logged at DEBUG level (not suppressed silently)

Compatible with rpyc 6.x.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self

import rpyc
from rpyc.utils.classic import obtain

log = logging.getLogger(__name__)

# Error message constant for fail-fast connection checks
_NOT_CONNECTED_MSG = "MT5 connection not established - call connect first"

if TYPE_CHECKING:
    from datetime import datetime
    from types import TracebackType

    from mt5linux._types import RatesArray, TicksArray


class MetaTrader5:
    """Transparent proxy for MetaTrader5 via rpyc.

    All MT5 attributes and methods are accessed via __getattr__,
    delegating to the real MetaTrader5 module on Windows/Docker server.

    Example:
        >>> with MetaTrader5(host="localhost", port=18812) as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     print(mt5.ORDER_TYPE_BUY)  # Real MT5 constant
    """

    _conn: rpyc.Connection | None
    _mt5: Any

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
    ) -> None:
        """Connect to rpyc server.

        Args:
            host: rpyc server address.
            port: rpyc server port.
            timeout: Timeout in seconds for operations.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._conn = None
        self._mt5 = None
        self.connect()

    def connect(self) -> None:
        """Establish connection to rpyc server."""
        if self._conn is not None:
            return
        # rpyc 6.x: rpyc.classic.connect still works
        self._conn = rpyc.classic.connect(self._host, self._port)
        self._conn._config["sync_request_timeout"] = self._timeout  # noqa: SLF001
        self._mt5 = self._conn.modules.MetaTrader5

    def __getattr__(self, name: str) -> Any:
        """Transparent proxy for any MT5 attribute."""
        if self._mt5 is None:
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)
        return getattr(self._mt5, name)

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - cleanup."""
        try:
            self.shutdown()
        except Exception:  # noqa: BLE001
            log.debug("MT5 shutdown failed during cleanup (connection may be closed)")
        self.close()

    def close(self) -> None:
        """Close rpyc connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                log.debug("RPyC connection close failed (may already be closed)")
            self._conn = None
            self._mt5 = None

    # ========================================
    # Methods that need to fetch numpy arrays locally via obtain()
    # Without this, would return netref (remote reference) instead of real array
    # ========================================

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        count: int,
    ) -> RatesArray | None:
        """Copy rates from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant (TIMEFRAME_M1, etc.).
            date_from: Start datetime.
            count: Number of bars to copy.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
        result = self._mt5.copy_rates_from(symbol, timeframe, date_from, count)
        return obtain(result) if result is not None else None

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> RatesArray | None:
        """Copy rates from a position. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            start_pos: Start position (0 = current bar).
            count: Number of bars to copy.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
        result = self._mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        return obtain(result) if result is not None else None

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> RatesArray | None:
        """Copy rates in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            timeframe: Timeframe constant.
            date_from: Start datetime.
            date_to: End datetime.

        Returns:
            Numpy structured array with OHLCV data or None.
        """
        result = self._mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
        return obtain(result) if result is not None else None

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks from a date. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime.
            count: Number of ticks to copy.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
        result = self._mt5.copy_ticks_from(symbol, date_from, count, flags)
        return obtain(result) if result is not None else None

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        flags: int,
    ) -> TicksArray | None:
        """Copy ticks in a date range. Fetches array locally.

        Args:
            symbol: Symbol name.
            date_from: Start datetime.
            date_to: End datetime.
            flags: COPY_TICKS_ALL, COPY_TICKS_INFO, or COPY_TICKS_TRADE.

        Returns:
            Numpy structured array with tick data or None.
        """
        result = self._mt5.copy_ticks_range(symbol, date_from, date_to, flags)
        return obtain(result) if result is not None else None

    # ========================================
    # Methods that need special handling for RPyC dict serialization
    # MT5's order_send/order_check don't accept RPyC netref dicts,
    # so we serialize the request and recreate it natively on remote side
    # ========================================

    def order_send(self, request: dict[str, Any]) -> Any:
        """Send trading order to MT5.

        Args:
            request: Order request dict with keys like action, symbol, volume, etc.

        Returns:
            OrderSendResult from MT5.

        Raises:
            ConnectionError: If not connected to MT5 server.

        Note:
            Serializes request and recreates it on remote side to avoid RPyC issues.
        """
        if self._conn is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)

        code = self._build_order_code(request, "_order_result", "order_send")
        self._conn.execute(code)
        return self._conn.namespace.get("_order_result")

    def order_check(self, request: dict[str, Any]) -> Any:
        """Check order parameters without sending.

        Args:
            request: Order request dict to validate.

        Returns:
            OrderCheckResult from MT5.

        Raises:
            ConnectionError: If not connected to MT5 server.
        """
        if self._conn is None:
            raise ConnectionError(_NOT_CONNECTED_MSG)

        code = self._build_order_code(request, "_check_result", "order_check")
        self._conn.execute(code)
        return self._conn.namespace.get("_check_result")

    def _build_order_code(
        self, request: dict[str, Any], result_var: str, method: str
    ) -> str:
        """Build Python code to execute order_send/order_check on remote side.

        Creates the request dict natively on Windows to avoid RPyC serialization issues.
        """
        # Map common enum values to MT5 constants
        action_map = {1: "_mt5.TRADE_ACTION_DEAL", 6: "_mt5.TRADE_ACTION_CLOSE_BY"}
        type_map = {
            0: "_mt5.ORDER_TYPE_BUY",
            1: "_mt5.ORDER_TYPE_SELL",
            2: "_mt5.ORDER_TYPE_BUY_LIMIT",
            3: "_mt5.ORDER_TYPE_SELL_LIMIT",
            4: "_mt5.ORDER_TYPE_BUY_STOP",
            5: "_mt5.ORDER_TYPE_SELL_STOP",
        }
        filling_map = {
            0: "_mt5.ORDER_FILLING_FOK",
            1: "_mt5.ORDER_FILLING_IOC",
            2: "_mt5.ORDER_FILLING_RETURN",
        }
        time_map = {
            0: "_mt5.ORDER_TIME_GTC",
            1: "_mt5.ORDER_TIME_DAY",
            2: "_mt5.ORDER_TIME_SPECIFIED",
            3: "_mt5.ORDER_TIME_SPECIFIED_DAY",
        }

        # Build request dict items as Python code
        items = []
        for key, value in request.items():
            if key == "action":
                items.append(f'"action": {action_map.get(value, value)}')
            elif key == "type":
                items.append(f'"type": {type_map.get(value, value)}')
            elif key == "type_filling":
                items.append(f'"type_filling": {filling_map.get(value, value)}')
            elif key == "type_time":
                items.append(f'"type_time": {time_map.get(value, value)}')
            elif isinstance(value, str):
                items.append(f'"{key}": "{value}"')
            else:
                items.append(f'"{key}": {value}')

        request_str = "{" + ", ".join(items) + "}"

        return f"""import MetaTrader5 as _mt5
_request = {request_str}
{result_var} = _mt5.{method}(_request)
"""
