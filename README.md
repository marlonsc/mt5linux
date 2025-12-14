# MetaTrader 5 for linux system

A simple package that uses [wine](https://www.winehq.org), [rpyc](https://github.com/tomerfiliba-org/rpyc) and a Python
Windows version to allow using [MetaTrader5](https://pypi.org/project/MetaTrader5) on Linux.

## Install

1. Install [Wine](https://wiki.winehq.org/Download).

2. Install [Python for Windows](https://www.python.org/downloads/windows/) on Linux with the help of Wine.

3. Find the path to `python.exe`.

   - Mine is installed on
     `/home/user/.wine/drive_c/users/user/Local Settings/Application Data/Programs/Python/Python39`.

4. Install [mt5](https://www.mql5.com/en/docs/integration/python_metatrader5) library on your **Windows** Python
   version.

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
   # import the package
   from mt5linux import MetaTrader5
   # connect to the server
   mt5 = MetaTrader5(
       # host = 'localhost' (default)
       # port = 18812       (default)
   )
   # use as you learned from: https://www.mql5.com/en/docs/integration/python_metatrader5/
   mt5.initialize()
   mt5.terminal_info()
   mt5.copy_rates_from_pos('GOOG',mt5.TIMEFRAME_M1,0,1000)
   # ...
   # don't forget to shutdown
   mt5.shutdown()
   ```

4. Be happy!

On step 2 you can provide the port, host, executable, etc... just type `python -m mt5linux --help`.

## Running Tests

### Prerequisites

1. **Docker** - Required to run the isolated test container.

2. **MT5 Demo Account** - Create a free demo account at [MetaQuotes](https://www.metatrader5.com/).

3. **Configure credentials** - Copy `.env.example` to `.env` and fill in your credentials:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your demo account details:
   ```
   MT5_TEST_LOGIN=your_login_here
   MT5_TEST_PASSWORD=your_password_here
   MT5_TEST_SERVER=MetaQuotes-Demo
   ```

   > **Note**: The `.env` file is gitignored and will not be committed.

### Running Tests

```bash
# Run all tests (auto-starts isolated container on port 38812)
pytest tests/ -v

# Run only unit tests (no MT5 connection required)
pytest tests/test_server.py -v

# Run with coverage
pytest tests/ --cov=mt5linux --cov-report=html
```

### Test Container Isolation

Tests run in a completely isolated Docker container:

| Resource | Production | Tests |
|----------|------------|-------|
| Container | `mt5` | `mt5linux-unit` |
| RPyC Port | 8001 | **38812** |
| VNC Port | 3000 | **33000** |
| Health Port | 8002 | **38002** |

The test container does **not** affect any production MT5 instance.

### Manual Container Management

```bash
# Start test container manually
docker compose -f tests/fixtures/docker-compose.test.yaml up -d

# View container logs
docker logs mt5linux-unit -f

# Stop test container
docker compose -f tests/fixtures/docker-compose.test.yaml down

# Clean up test volumes
docker volume rm mt5linux_unit_config mt5linux_unit_downloads mt5linux_unit_cache
```
