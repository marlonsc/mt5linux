"""MetaTrader5 client - transparent bridge via rpyc."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Self

import rpyc
from rpyc.utils.classic import obtain

if TYPE_CHECKING:
    from types import TracebackType

    from numpy.typing import NDArray


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
        self._conn = rpyc.classic.connect(host, port)
        self._conn._config["sync_request_timeout"] = timeout  # noqa: SLF001
        self._mt5 = self._conn.modules.MetaTrader5

    def __getattr__(self, name: str) -> Any:
        """Transparent proxy for any MT5 attribute."""
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
        with contextlib.suppress(Exception):
            self.shutdown()
        self.close()

    def close(self) -> None:
        """Close rpyc connection."""
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None

    # Methods that need to fetch numpy arrays locally via obtain()
    # Without this, would return netref (remote reference) instead of real array

    def copy_rates_from(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copy rates from a date. Fetches array locally."""
        result = self._mt5.copy_rates_from(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_rates_from_pos(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copy rates from a position. Fetches array locally."""
        result = self._mt5.copy_rates_from_pos(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_rates_range(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copy rates in a date range. Fetches array locally."""
        result = self._mt5.copy_rates_range(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_ticks_from(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copy ticks from a date. Fetches array locally."""
        result = self._mt5.copy_ticks_from(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_ticks_range(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copy ticks in a date range. Fetches array locally."""
        result = self._mt5.copy_ticks_range(*args, **kwargs)
        return obtain(result) if result is not None else None
