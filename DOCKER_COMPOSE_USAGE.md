# Parametrized Docker Compose Usage

## Overview

`docker-compose.yaml` is the single source of truth for MT5 test container configuration. It supports parametrization via environment variables for flexible test scenarios.

## File Locations

- **Main configuration**: `/home/marlonsc/invest/mt5linux/docker-compose.yaml`
- **Test fixture**: `tests/conftest.py` (auto-parametrizes via environment variables)
- **Environment file**: `.env` (contains MT5_LOGIN, MT5_PASSWORD, MT5_SERVER defaults)

## Parametrizable Options

### Container & Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_CONTAINER_NAME` | `mt5linux-unit` | Container name and volume prefix |
| `MT5_RPYC_PORT` | `38812` | RPyC server port (Wine → host) |
| `MT5_VNC_PORT` | `33000` | VNC GUI port (Wine → host) |
| `MT5_HEALTH_PORT` | `38002` | Health check port (Wine → host) |

### MT5 Credentials

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_LOGIN` | `0` | MT5 account login (from .env) |
| `MT5_PASSWORD` | `` | MT5 account password (from .env) |
| `MT5_SERVER` | `MetaQuotes-Demo` | MT5 server name |

### Environment File

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV_FILE` | `.env` | Path to environment file with credentials |

## Usage Examples

### 1. Default (pytest auto-parametrization)

```bash
cd /home/marlonsc/invest/mt5linux
pytest tests/
```

**What happens**:
- conftest.py reads `.env` for MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
- conftest.py uses defaults for container name and ports
- Docker container starts as `mt5linux-unit` on port 38812
- Tests connect to `localhost:38812`

### 2. Custom Test Scenario (different container name and ports)

```bash
cd /home/marlonsc/invest/mt5linux

# Run tests with custom ports
MT5_CONTAINER_NAME=mt5-test-custom \
MT5_RPYC_PORT=48812 \
MT5_VNC_PORT=43000 \
pytest tests/
```

**What happens**:
- Container starts as `mt5-test-custom` on port 48812
- VNC accessible on port 43000
- Tests connect to `localhost:48812`
- Volumes: `mt5-test-custom_config`, `mt5-test-custom_downloads`, `mt5-test-custom_cache`

### 3. Custom MT5 Credentials

```bash
cd /home/marlonsc/invest/mt5linux

MT5_LOGIN=123456 \
MT5_PASSWORD=mypassword \
MT5_SERVER=MyBroker-Live \
pytest tests/
```

**What happens**:
- Container initializes with custom MT5 credentials
- Uses default container name `mt5linux-unit` and ports

### 4. Custom Environment File

```bash
cd /home/marlonsc/invest/mt5linux

# Use custom .env file
ENV_FILE=/path/to/custom.env \
pytest tests/
```

### 5. Manual Container Management

```bash
# Start with defaults
docker compose up -d

# Start with custom configuration
MT5_CONTAINER_NAME=mt5-custom \
MT5_RPYC_PORT=48812 \
MT5_VNC_PORT=43000 \
docker compose up -d

# View logs
docker compose logs -f

# Stop container
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Volume Names

Volumes are automatically named based on container name:

```
${MT5_CONTAINER_NAME}_config
${MT5_CONTAINER_NAME}_downloads
${MT5_CONTAINER_NAME}_cache
```

**Example with custom container name**:
- `mt5-test-custom_config`
- `mt5-test-custom_downloads`
- `mt5-test-custom_cache`

## Isolation

Each test scenario is completely isolated:

- **Different container names** → Different volumes
- **Different ports** → No port conflicts
- **Clean startup** → conftest.py removes old volumes before starting
- **Clean teardown** → Volumes removed after tests complete

## Advanced: Multiple Parallel Tests

Run multiple test scenarios in parallel:

```bash
# Terminal 1: Default configuration
pytest tests/ -m "not slow"

# Terminal 2: Alternative configuration
MT5_CONTAINER_NAME=mt5-alt \
MT5_RPYC_PORT=48812 \
pytest tests/ -m "not slow"

# Terminal 3: High-security configuration
MT5_CONTAINER_NAME=mt5-secure \
MT5_RPYC_PORT=58812 \
MT5_SERVER=MyBroker-Secure \
pytest tests/ -k "security"
```

All run simultaneously without interference.

## Integration with CI/CD

Set environment variables in CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Run MT5 Tests
  env:
    MT5_LOGIN: ${{ secrets.MT5_LOGIN }}
    MT5_PASSWORD: ${{ secrets.MT5_PASSWORD }}
    MT5_SERVER: MyBroker-CI
    MT5_CONTAINER_NAME: ci-mt5-${{ github.run_id }}
  run: pytest tests/
```

## Troubleshooting

### Container won't start
```bash
# Check if port is in use
lsof -i :38812

# Check logs
docker compose logs

# Force cleanup
docker compose down -v
docker volume prune -f
docker system prune -f
```

### Connection refused
```bash
# Verify container is running
docker ps | grep mt5

# Check RPyC port is exposed
docker inspect mt5linux-unit | grep -A 10 PortBindings

# Test port directly
nc -zv localhost 38812
```

### Volume cleanup issues
```bash
# List all mt5 volumes
docker volume ls | grep mt5

# Remove specific volume
docker volume rm mt5linux-unit_config

# Clean all unused volumes
docker volume prune -f
```
