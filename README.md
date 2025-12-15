# MetaTrader 5 for Linux

A Python package that uses [rpyc](https://github.com/tomerfiliba-org/rpyc) to bridge [MetaTrader5](https://pypi.org/project/MetaTrader5) to
Linux systems.

## Features

- **Sync Client**: `MetaTrader5` - Traditional blocking client
- **Async Client**: `AsyncMetaTrader5` - Non-blocking client for asyncio
- **Pydantic Models**: Type-safe models for trading data
- **Python 3.13+**: Modern type hints and features
- **rpyc 6.x**: Latest rpyc with security fixes

## Requirements

- Python 3.13+
- rpyc 6.0.2+
- numpy 2.1.0+
- pydantic 2.10.0+

## Installation

```bash
pip install mt5linux
```

Or from source:

```bash
pip install git+https://github.com/marlonsc/mt5linux.git@master
```

## Quick Start

### Sync Client

```python
from mt5linux import MetaTrader5

with MetaTrader5(host="localhost", port=8001) as mt5:
    mt5.initialize(login=12345, password="pass", server="Demo")

    # Account info
    account = mt5.account_info()
    print(f"Balance: {account.balance}")

    # Symbol info
    info = mt5.symbol_info("EURUSD")
    print(f"EURUSD bid: {info.bid}")

    # OHLCV data
    rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)
    print(f"Got {len(rates)} bars")
```

### Async Client

```python
import asyncio
from mt5linux import AsyncMetaTrader5

async def main():
    async with AsyncMetaTrader5(host="localhost", port=8001) as mt5:
        await mt5.initialize(login=12345, password="pass", server="Demo")

        # Parallel data fetching
        account, symbol, tick = await asyncio.gather(
            mt5.account_info(),
            mt5.symbol_info("EURUSD"),
            mt5.symbol_info_tick("EURUSD"),
        )

        print(f"Balance: {account.balance}")
        print(f"Bid: {tick.bid}, Ask: {tick.ask}")

asyncio.run(main())
```

### Pydantic Models

```python
from mt5linux import (
    OrderRequest,
    OrderResult,
    TradeAction,
    OrderType,
    OrderFilling,
)

# Create validated order request
request = OrderRequest(
    action=TradeAction.DEAL,
    symbol="EURUSD",
    volume=0.1,
    type=OrderType.BUY,
    price=0,  # Market order
    deviation=20,
    magic=123456,
    comment="Test order",
    type_filling=OrderFilling.FOK,
)

# Send order
result = mt5.order_send(request.to_dict())

# Parse result with validation
order_result = OrderResult.from_mt5(result)
if order_result.is_success:
    print(f"Order placed: {order_result.order}")
else:
    print(f"Error: {order_result.comment}")
```

## Server Setup

### Option 1: Docker (Recommended)

Use [mt5docker](https://github.com/marlonsc/mt5docker) for a complete containerized setup:

```bash
docker compose up -d
```

The container runs rpyc server on port 8001.

### Option 2: Manual Wine Setup

1. Install Wine and Python for Windows
2. Install MetaTrader5 package in Wine Python:

   ```bash
   wine pip install MetaTrader5
   ```

3. Start rpyc server:

   ```bash
   python -m mt5linux.server --wine wine --python python.exe -p 8001
   ```

## API Reference

### MetaTrader5 (Sync Client)

All [official MT5 Python functions](https://www.mql5.com/en/docs/python_metatrader5) are available:

**Connection**:

- `initialize()`, `login()`, `shutdown()`
- `version()`, `last_error()`
- `terminal_info()`, `account_info()`

**Symbols**:

- `symbols_total()`, `symbols_get()`
- `symbol_info()`, `symbol_info_tick()`
- `symbol_select()`

**Market Data**:

- `copy_rates_from()`, `copy_rates_from_pos()`, `copy_rates_range()`
- `copy_ticks_from()`, `copy_ticks_range()`

**Trading**:

- `order_calc_margin()`, `order_calc_profit()`
- `order_check()`, `order_send()`

**Positions & Orders**:

- `positions_total()`, `positions_get()`
- `orders_total()`, `orders_get()`

**History**:

- `history_orders_total()`, `history_orders_get()`
- `history_deals_total()`, `history_deals_get()`

### AsyncMetaTrader5 (Async Client)

Same API as sync client, but all methods are async:

```python
await mt5.initialize()
await mt5.order_send(request)
rates = await mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 100)
```

### Pydantic Models

- `OrderRequest` - Validated order request
- `OrderResult` - Order execution result
- `AccountInfo` - Account information
- `SymbolInfo` - Symbol metadata
- `Position` - Open position
- `Tick` - Price tick

### Enums

- `TradeAction` - DEAL, PENDING, SLTP, MODIFY, REMOVE, CLOSE_BY
- `OrderType` - BUY, SELL, BUY_LIMIT, SELL_LIMIT, etc.
- `OrderFilling` - FOK, IOC, RETURN
- `OrderTime` - GTC, DAY, SPECIFIED, SPECIFIED_DAY
- `TradeRetcode` - DONE, REQUOTE, ERROR, NO_MONEY, etc.

## Error Handling

The library uses **fail-fast** error handling:

```python
from mt5linux import MetaTrader5

mt5 = MetaTrader5(host="localhost", port=8001)

try:
    result = mt5.order_send(request)
except ConnectionError as e:
    print(f"Not connected: {e}")
```

### Logging

Enable debug logging to see diagnostic information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Running Tests

### Prerequisites

1. Docker for isolated test container
2. MT5 demo account credentials in `.env`:

   ```bash
   MT5_LOGIN=your_login
   MT5_PASSWORD=your_password
   MT5_SERVER=MetaQuotes-Demo
   ```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (no server)
pytest tests/test_models.py tests/test_async_client.py -v

# With coverage
pytest tests/ --cov=mt5linux --cov-report=html
```

### Test Container Isolation

Tests use isolated ports to avoid conflicts:

| Resource | Production | Tests |
|----------|------------|-------|
| Container | `mt5` | `mt5linux-unit` |
| RPyC Port | 8001 | 38812 |
| VNC Port | 3000 | 33000 |

## Version History

- **0.3.0**: Async client, Pydantic models, Python 3.13+, rpyc 6.x
- **0.2.1**: Fail-fast error handling, structlog
- **0.2.0**: Production server with auto-restart
- **0.1.0**: Initial release

## License

MIT
