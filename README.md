# MetaTrader 5 for Linux System

A simple package that uses [wine](https://www.winehq.org), [rpyc](https://github.com/tomerfiliba-org/rpyc)
and a Python Windows version to allow using [MetaTrader5](https://pypi.org/project/MetaTrader5) on Linux.

## Install

1. Install [Wine](https://wiki.winehq.org/Download).

2. Install [Python for Windows](https://www.python.org/downloads/windows/) on Linux with the help of Wine.

3. Find the path to `python.exe`.

    - Mine is installed on:
      `/home/user/.wine/drive_c/users/user/Local Settings/Application Data/Programs/Python/Python39`

4. Install [mt5](https://www.mql5.com/en/docs/integration/python_metatrader5) library on your **Windows** Python version.

    ```bash
    pip install MetaTrader5
    pip install --upgrade MetaTrader5
    ```

5. Install this package on both **Windows** and **Linux** Python versions:

    ```bash
    pip install mt5linux
    ```

## How To Use

Follow the steps:

1. Open MetaTrader5.

2. On **Windows** side, start the server on a terminal:

    ```bash
    python -m mt5linux <path/to/python.exe>
    ```

3. On **Linux** side, make your scripts/notebooks as you did with MetaTrader5:

    ```python
    from mt5linux import MetaTrader5
    # Connect to the server
    mt5 = MetaTrader5(
        # host = 'localhost' (default)
        # port = 18812       (default)
    )
    # Initialize connection
    mt5.initialize()
    # Retrieve terminal info
    mt5.terminal_info()
    # Retrieve 1000 bars from GOOG, 1-minute timeframe
    mt5.copy_rates_from_pos('GOOG', mt5.TIMEFRAME_M1, 0, 1000)
    # ...
    # Always shutdown after use
    mt5.shutdown()
    ```

4. For advanced options, use `python -m mt5linux --help` to see all available parameters (port, host, executable, etc).

## API Documentation

### MetaTrader5 Class

Provides a Pythonic interface to interact with MetaTrader 5 running on Windows via Wine, using RPyc for remote
procedure calls. Exposes all major MetaTrader 5 API methods, including account management, market data retrieval,
order management, and historical data access.

#### Example usage

```python
from mt5linux import MetaTrader5
mt5 = MetaTrader5()
mt5.initialize()
info = mt5.terminal_info()
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_M1, 0, 100)
mt5.shutdown()
```

#### copy_rates_from_pos

```python
def copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int):
    """
    Retrieve bars from the MetaTrader 5 terminal starting from a specified index.

    Args:
        symbol (str): Financial instrument name (e.g., "EURUSD").
        timeframe (int): Timeframe, as defined by the TIMEFRAME enumeration.
        start_pos (int): Initial bar index (0 = current bar).
        count (int): Number of bars to retrieve.

    Returns:
        numpy.ndarray or None: Array with columns [time, open, high, low, close, tick_volume, spread,
        real_volume], or None on error.

    Raises:
        Any error from the underlying MetaTrader 5 API is available via last_error().

    Note:
        - Bars are only available within the user's chart history.
        - The number of bars is limited by the "Max. bars in chart" terminal parameter.
        - All times are in UTC.

    Example:
        >>> mt5.copy_rates_from_pos("GBPUSD", mt5.TIMEFRAME_D1, 0, 10)
    """
```
