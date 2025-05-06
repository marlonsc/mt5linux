# MT5Linux - MetaTrader 5 for Linux

[![PyPI version](https://badge.fury.io/py/mt5linux.svg)](https://badge.fury.io/py/mt5linux)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python package that enables using [MetaTrader 5](https://www.metatrader5.com/) on Linux systems through [Wine](https://www.winehq.org) and [RPyC](https://github.com/tomerfiliba-org/rpyc). This package provides a drop-in replacement for the official [MetaTrader5](https://pypi.org/project/MetaTrader5/) Python package.

## Overview

MetaTrader 5 is a popular trading platform that provides a Python API for algorithmic trading, but it's only available for Windows. MT5Linux creates a bridge between Linux and the Windows-only MetaTrader 5 Python API, allowing you to:

- Run MetaTrader 5 trading bots on Linux servers
- Develop trading strategies on Linux using the same API as on Windows
- Access all MetaTrader 5 functionality including market data, order management, and account information

## Features

- **Complete API Compatibility**: All functions and constants from the official MetaTrader 5 Python API are available
- **Easy Setup**: Simple installation process for both the server (Windows/Wine) and client (Linux) components
- **Efficient Communication**: Uses RPyC for fast and reliable remote procedure calls
- **Robust Error Handling**: Proper error propagation from the MetaTrader 5 terminal to your Python code

## Installation

### Prerequisites

1. **Install Wine**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install wine wine64
   
   # Fedora
   sudo dnf install wine
   
   # Arch Linux
   sudo pacman -S wine
   ```

2. **Install Windows Python using Wine**:
   ```bash
   # Create a Wine prefix (optional but recommended)
   export WINEPREFIX=~/.wine_mt5
   
   # Download and install Python for Windows
   wget https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
   wine python-3.9.13-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
   ```

3. **Find your Windows Python path**:
   ```bash
   # Typically located at:
   # ~/.wine/drive_c/users/$USER/Local Settings/Application Data/Programs/Python/Python39/python.exe
   # or
   # ~/.wine/drive_c/Program Files/Python39/python.exe
   
   # You can search for it with:
   find ~/.wine -name python.exe
   ```

4. **Install MetaTrader 5 Terminal**:
   - Download the MetaTrader 5 installer from the [official website](https://www.metatrader5.com/en/download)
   - Install it using Wine:
     ```bash
     wine ~/Downloads/mt5setup.exe
     ```

### Package Installation

1. **Install MetaTrader 5 Python package on Windows Python**:
   ```bash
   wine ~/.wine/drive_c/path/to/python.exe -m pip install --upgrade pip
   wine ~/.wine/drive_c/path/to/python.exe -m pip install MetaTrader5
   ```

2. **Install MT5Linux on both Windows and Linux Python**:
   ```bash
   # On Windows Python (using Wine)
   wine ~/.wine/drive_c/path/to/python.exe -m pip install mt5linux
   
   # On Linux Python
   pip install mt5linux
   ```

## Usage

### Starting the Server

1. **Launch MetaTrader 5 Terminal**:
   ```bash
   wine ~/.wine/drive_c/Program\ Files/MetaTrader\ 5/terminal64.exe
   ```
   
   - Log in to your trading account
   - Enable automated trading (Tools → Options → Expert Advisors → Allow automated trading)
   - Enable DLL imports (Tools → Options → Expert Advisors → Allow DLL imports)

2. **Start the RPyC Server**:
   ```bash
   wine ~/.wine/drive_c/path/to/python.exe -m mt5linux ~/.wine/drive_c/path/to/python.exe
   ```

   With custom options:
   ```bash
   wine ~/.wine/drive_c/path/to/python.exe -m mt5linux ~/.wine/drive_c/path/to/python.exe --host 0.0.0.0 --port 18812
   ```

### Using the Client

On the Linux side, use the MetaTrader 5 API with the same interface as on Windows:

```python
import pandas as pd
from mt5linux import MetaTrader5 as mt5

# Connect to the server (optional, a default instance is created on import)
# mt5 = MetaTrader5(host='localhost', port=18812)

# Initialize connection to the MetaTrader 5 terminal
if not mt5.initialize():
    print(f"Initialize failed, error code = {mt5.last_error()}")
    quit()

# Display MetaTrader 5 terminal info
print(mt5.terminal_info())
print(f"MetaTrader 5 version: {mt5.version()}")

# Get account information
account_info = mt5.account_info()
if account_info is not None:
    print(f"Account: {account_info.login} (Server: {account_info.server})")
    print(f"Balance: {account_info.balance} {account_info.currency}")
    print(f"Equity: {account_info.equity}")

# Get available symbols
symbols = mt5.symbols_get()
print(f"Total symbols: {len(symbols)}")
for i, symbol in enumerate(symbols[:10]):  # Show first 10 symbols
    print(f"{i+1}. {symbol.name}")

# Get historical data
symbol = "EURUSD"
timeframe = mt5.TIMEFRAME_M5
start_pos = 0
num_bars = 100

# Get bars from a position
rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, num_bars)
if rates is not None:
    # Convert to pandas DataFrame
    rates_df = pd.DataFrame(rates)
    rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
    print(rates_df.head())

# Place a market order
symbol = "EURUSD"
lot = 0.01
order_type = mt5.ORDER_TYPE_BUY
price = mt5.symbol_info_tick(symbol).ask
deviation = 20  # Slippage in points

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": symbol,
    "volume": lot,
    "type": order_type,
    "price": price,
    "deviation": deviation,
    "magic": 12345,
    "comment": "Python market order",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}

# Send the order
result = mt5.order_send(request)
if result.retcode == mt5.TRADE_RETCODE_DONE:
    print(f"Order executed: {result.order}")
else:
    print(f"Order failed: {result.retcode}")

# Shutdown connection to the MetaTrader 5 terminal
mt5.shutdown()
```

## Advanced Usage

### Automated Server Startup

You can create a shell script to automate the server startup:

```bash
#!/bin/bash
# start_mt5_server.sh

# Path to Windows Python
WINE_PYTHON="$HOME/.wine/drive_c/path/to/python.exe"

# Start MetaTrader 5 terminal
wine "$HOME/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe" &
sleep 10  # Wait for terminal to start

# Start MT5Linux server
wine "$WINE_PYTHON" -m mt5linux "$WINE_PYTHON" --host 0.0.0.0 --port 18812
```

Make it executable:
```bash
chmod +x start_mt5_server.sh
```

### Running as a Service

You can create a systemd service to run the MT5Linux server:

```ini
[Unit]
Description=MT5Linux Server
After=network.target

[Service]
Type=simple
User=your_username
ExecStart=/bin/bash /path/to/start_mt5_server.sh
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Save this to `/etc/systemd/system/mt5linux.service` and enable it:
```bash
sudo systemctl enable mt5linux.service
sudo systemctl start mt5linux.service
```

## API Reference

MT5Linux provides a complete implementation of the MetaTrader 5 Python API. All functions and constants from the original API are available with the same signatures and behavior.

### Main Functions

| Function | Description |
|----------|-------------|
| `initialize()` | Establishes a connection with the MetaTrader 5 terminal |
| `login(account, password, server)` | Connects to a trading account |
| `shutdown()` | Closes the connection to the MetaTrader 5 terminal |
| `version()` | Returns the MetaTrader 5 terminal version |
| `last_error()` | Returns information about the last error |
| `account_info()` | Gets information about the current trading account |
| `terminal_info()` | Gets the connected MetaTrader 5 terminal status and settings |
| `symbols_total()` | Gets the number of all financial instruments |
| `symbols_get(group=None)` | Gets all financial instruments |
| `symbol_info(symbol)` | Gets information about a specified financial instrument |
| `symbol_info_tick(symbol)` | Gets the last tick for a specified financial instrument |
| `symbol_select(symbol, enable)` | Selects a symbol in the Market Watch window |
| `market_book_add(symbol)` | Subscribes to market depth (DOM) for a specified symbol |
| `market_book_get(symbol)` | Gets the market depth (DOM) for a specified symbol |
| `market_book_release(symbol)` | Cancels subscription to market depth (DOM) for a specified symbol |
| `copy_rates_from(symbol, timeframe, date_from, count)` | Gets bars from a specified financial instrument and period starting from the specified date |
| `copy_rates_from_pos(symbol, timeframe, start_pos, count)` | Gets bars from a specified financial instrument and period starting from the specified index |
| `copy_rates_range(symbol, timeframe, date_from, date_to)` | Gets bars from a specified financial instrument and period within the specified date range |
| `copy_ticks_from(symbol, date_from, count, flags)` | Gets ticks from a specified financial instrument starting from the specified date |
| `copy_ticks_range(symbol, date_from, date_to, flags)` | Gets ticks from a specified financial instrument within the specified date range |
| `orders_total()` | Gets the number of active orders |
| `orders_get(symbol=None, group=None, ticket=None)` | Gets active orders with the ability to filter by symbol or ticket |
| `order_calc_margin(action, symbol, volume, price)` | Calculates the margin required for the specified order type |
| `order_calc_profit(action, symbol, volume, price_open, price_close)` | Calculates the profit for the specified order |
| `order_check(request)` | Checks if there are enough funds to execute a trading operation |
| `order_send(request)` | Sends a trade request to the server |
| `positions_total()` | Gets the number of open positions |
| `positions_get(symbol=None, group=None, ticket=None)` | Gets open positions with the ability to filter by symbol or ticket |
| `history_orders_total(date_from, date_to)` | Gets the number of orders in the trading history within the specified period |
| `history_orders_get(date_from, date_to, group=None)` | Gets orders from the trading history with the ability to filter by ticket or position |
| `history_deals_total(date_from, date_to)` | Gets the number of deals in the trading history within the specified period |
| `history_deals_get(date_from, date_to, group=None)` | Gets deals from the trading history with the ability to filter by ticket or position |

For detailed API documentation, refer to the [official MetaTrader 5 Python documentation](https://www.mql5.com/en/docs/integration/python_metatrader5/).

## Troubleshooting

### Connection Issues

- **Server Not Starting**: 
  - Ensure Wine is properly installed and configured
  - Check that the path to Windows Python is correct
  - Verify that MetaTrader 5 terminal is running
  - Check if the port is already in use by another application

- **Client Cannot Connect**:
  - Verify the server is running with `netstat -tuln | grep 18812`
  - Check firewall settings if connecting from a different machine
  - Ensure the host and port settings match between server and client

### Common Errors

- **"Cannot connect to server"**: The server is not running or is using a different host/port
- **"Initialize failed"**: The MetaTrader 5 terminal is not running or is not properly configured
- **"DLL imports not allowed"**: Enable DLL imports in the MetaTrader 5 terminal settings
- **"Automated trading disabled"**: Enable automated trading in the MetaTrader 5 terminal settings

### Performance Optimization

- Use a dedicated Wine prefix for MetaTrader 5 to avoid conflicts
- Increase the RPyC timeout if working with large datasets
- For high-frequency trading, consider running the client on the same machine as the server

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [MetaTrader 5](https://www.metatrader5.com/) for providing the trading platform
- [RPyC](https://github.com/tomerfiliba-org/rpyc) for the remote procedure call framework
- [Wine](https://www.winehq.org) for making it possible to run Windows applications on Linux
