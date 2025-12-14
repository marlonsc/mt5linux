"""MetaTrader5 bridge para Linux via rpyc.

Bridge transparente que conecta ao MetaTrader5 rodando em Windows/Docker
via rpyc. Todos os métodos e constantes são delegados para o MT5 real.

Example:
    >>> from mt5linux import MetaTrader5
    >>> with MetaTrader5(host="localhost", port=8001) as mt5:
    ...     mt5.initialize(login=12345, password="pass", server="Demo")
    ...     account = mt5.account_info()
    ...     print(mt5.ORDER_TYPE_BUY)  # Constante do MT5 real

For MT5 method documentation, see:
    https://www.mql5.com/en/docs/python_metatrader5
"""

from mt5linux.client import MetaTrader5

__all__ = ["MetaTrader5"]
__version__ = "0.2.0"
