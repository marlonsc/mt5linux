"""MetaTrader5 client - bridge transparente via rpyc."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Self

import rpyc
from rpyc.utils.classic import obtain

if TYPE_CHECKING:
    from types import TracebackType

    from numpy.typing import NDArray


class MetaTrader5:
    """Proxy transparente para MetaTrader5 via rpyc.

    Todos os atributos e métodos do MT5 são acessados via __getattr__,
    delegando para o módulo MetaTrader5 real no servidor Windows/Docker.

    Example:
        >>> with MetaTrader5(host="localhost", port=18812) as mt5:
        ...     mt5.initialize(login=12345, password="pass", server="Demo")
        ...     account = mt5.account_info()
        ...     print(mt5.ORDER_TYPE_BUY)  # Constante do MT5 real
    """

    _conn: rpyc.Connection | None
    _mt5: Any

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18812,
        timeout: int = 300,
    ) -> None:
        """Conecta ao servidor rpyc.

        Args:
            host: Endereço do servidor rpyc.
            port: Porta do servidor rpyc.
            timeout: Timeout em segundos para operações.
        """
        self._conn = rpyc.classic.connect(host, port)
        self._conn._config["sync_request_timeout"] = timeout  # noqa: SLF001
        self._mt5 = self._conn.modules.MetaTrader5

    def __getattr__(self, name: str) -> Any:
        """Proxy transparente para qualquer atributo do MT5."""
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
        """Fecha conexão rpyc."""
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None

    # Métodos que precisam trazer numpy arrays localmente via obtain()
    # Sem isso, retornaria netref (referência remota) ao invés do array real

    def copy_rates_from(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copia rates a partir de uma data. Traz array localmente."""
        result = self._mt5.copy_rates_from(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_rates_from_pos(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copia rates a partir de uma posição. Traz array localmente."""
        result = self._mt5.copy_rates_from_pos(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_rates_range(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copia rates em um range de datas. Traz array localmente."""
        result = self._mt5.copy_rates_range(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_ticks_from(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copia ticks a partir de uma data. Traz array localmente."""
        result = self._mt5.copy_ticks_from(*args, **kwargs)
        return obtain(result) if result is not None else None

    def copy_ticks_range(self, *args: Any, **kwargs: Any) -> NDArray[Any] | None:
        """Copia ticks em um range de datas. Traz array localmente."""
        result = self._mt5.copy_ticks_range(*args, **kwargs)
        return obtain(result) if result is not None else None
