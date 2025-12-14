"""Pytest fixtures with auto-startup of ISOLATED mt5docker test container.

Test container is completely isolated from production environment:
- Container: mt5linux-test (not mt5)
- RPyC Port: 28812 (not 8001)
- VNC Port: 23000 (not 3000)
- Volumes: separate test volumes (not shared with production)

Workspace Detection:
- If ../mt5docker exists: uses local project with docker-compose.test.yaml
- If not in workspace: skips with instructions to clone from GitHub

The container mounts local mt5linux code instead of cloning from GitHub.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dotenv import load_dotenv

if TYPE_CHECKING:
    from mt5linux import MetaTrader5

# Load .env file from project root
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# =============================================================================
# ISOLATED TEST CONFIGURATION - DOES NOT AFFECT PRODUCTION OR NEPTOR!
# =============================================================================
TEST_CONTAINER_NAME = "mt5linux-unit"
TEST_RPYC_PORT = int(os.environ.get("MT5_TEST_RPYC_PORT", "38812"))
TEST_VNC_PORT = int(os.environ.get("MT5_TEST_VNC_PORT", "33000"))
TEST_HEALTH_PORT = int(os.environ.get("MT5_TEST_HEALTH_PORT", "38002"))
TEST_TIMEOUT = 180  # Timeout for startup (first build takes longer)

# Test credentials from environment (see .env.example)
TEST_MT5_LOGIN = int(os.environ.get("MT5_TEST_LOGIN", "0"))
TEST_MT5_PASSWORD = os.environ.get("MT5_TEST_PASSWORD", "")
TEST_MT5_SERVER = os.environ.get("MT5_TEST_SERVER", "MetaQuotes-Demo")


# =============================================================================
# WORKSPACE DETECTION
# =============================================================================


def _find_workspace_root() -> Path:
    """Find workspace root (parent of mt5linux)."""
    return Path(__file__).resolve().parent.parent.parent


def _find_mt5docker_path() -> Path | None:
    """Find mt5docker project in workspace.

    Detection order:
    1. ../mt5docker (sibling directory in workspace)
    2. None if not found

    Returns:
        Path to mt5docker directory or None if not in workspace.
    """
    workspace = _find_workspace_root()

    # Check sibling directory (../mt5docker relative to mt5linux)
    sibling_path = workspace / "mt5docker"
    if sibling_path.exists() and (sibling_path / "docker-compose.yaml").exists():
        return sibling_path

    return None


def _get_docker_compose_files(mt5docker_path: Path) -> list[Path]:
    """Get docker-compose files for test container.

    Uses overlay: docker-compose.yaml + docker-compose.test.yaml

    Returns:
        List of compose files to use.

    Raises:
        FileNotFoundError: If compose files are missing.
    """
    base = mt5docker_path / "docker-compose.yaml"
    test = mt5docker_path / "docker-compose.test.yaml"

    if not base.exists():
        msg = f"docker-compose.yaml not found in {mt5docker_path}"
        raise FileNotFoundError(msg)

    if not test.exists():
        msg = (
            f"docker-compose.test.yaml not found in {mt5docker_path}. "
            "This file is required for isolated test container."
        )
        raise FileNotFoundError(msg)

    return [base, test]


# =============================================================================
# SERVICE DETECTION
# =============================================================================


def wait_for_port(host: str, port: int, timeout: int = TEST_TIMEOUT) -> bool:
    """Wait for TCP port to become available.

    Args:
        host: Hostname to connect to.
        port: Port number to check.
        timeout: Maximum seconds to wait.

    Returns:
        True if port is available, False if timeout exceeded.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(2)
    return False


def is_container_running(name: str) -> bool:
    """Check if container is running."""
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def is_container_exists(name: str) -> bool:
    """Check if container exists (running or stopped)."""
    result = subprocess.run(
        ["docker", "ps", "-aq", "-f", f"name=^{name}$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def is_rpyc_service_ready(host: str, port: int) -> bool:
    """Check if RPyC service is ready (actual handshake, not just port).

    Performs real RPyC classic handshake to verify service is operational.
    """
    try:
        from rpyc.utils.classic import connect

        conn = connect(host, port)
        conn._config["sync_request_timeout"] = 5
        # Verify modules are accessible (proves MT5 bridge is working)
        _ = conn.modules
        conn.close()
        return True
    except Exception:
        return False


def wait_for_rpyc_service(
    host: str = "localhost",
    port: int = TEST_RPYC_PORT,
    timeout: int = TEST_TIMEOUT,
) -> bool:
    """Wait for RPyC service to become ready.

    Uses actual RPyC handshake, not just TCP port check.
    """
    start = time.time()
    check_interval = 3  # seconds between checks

    while time.time() - start < timeout:
        if is_rpyc_service_ready(host, port):
            return True
        time.sleep(check_interval)

    return False


def start_test_container() -> None:
    """Inicia container de teste ISOLADO usando docker-compose.test.yaml."""
    # Se container já está rodando e respondendo, usa ele
    if is_container_running(TEST_CONTAINER_NAME):
        if wait_for_port("localhost", TEST_RPYC_PORT, timeout=10):
            return
        # Container rodando mas porta não responde - reinicia
        subprocess.run(
            ["docker", "rm", "-f", TEST_CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

    # Remove container existente se houver
    if is_container_exists(TEST_CONTAINER_NAME):
        subprocess.run(
            ["docker", "rm", "-f", TEST_CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

    # Localiza docker-compose.test.yaml em tests/fixtures/
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    compose_file = fixtures_dir / "docker-compose.test.yaml"

    if not compose_file.exists():
        pytest.skip(
            f"docker-compose.test.yaml não encontrado em {fixtures_dir}. "
            "Crie o arquivo ou inicie o container manualmente."
        )

    # Inicia container isolado via docker compose
    # cwd deve ser o diretório do mt5linux para o build context funcionar
    mt5linux_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=mt5linux_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.skip(
            f"Falha ao iniciar container de teste: {result.stderr}. "
            "Verifique se ../mt5docker existe e docker está disponível."
        )

    # Aguarda servidor rpyc estar pronto
    if not wait_for_port("localhost", TEST_RPYC_PORT):
        # Obtém logs para debug
        logs = subprocess.run(
            ["docker", "logs", TEST_CONTAINER_NAME, "--tail", "100"],
            capture_output=True,
            text=True,
            check=False,
        )
        pytest.skip(
            f"Container {TEST_CONTAINER_NAME} não iniciou em {TEST_TIMEOUT}s. "
            f"Logs: {logs.stdout[-500:] if logs.stdout else logs.stderr[-500:]}"
        )


@pytest.fixture(scope="session", autouse=True)
def docker_container() -> None:
    """Garante container de teste ISOLADO rodando.

    Este fixture é session-scoped e autouse=True, então executa
    automaticamente no início da sessão de testes.

    O container permanece ativo após os testes para reutilização.
    Para parar: docker compose -f docker-compose.test.yaml down
    """
    start_test_container()


@pytest.fixture
def mt5() -> Generator[MetaTrader5, None, None]:
    """Fixture com MetaTrader5 conectado e inicializado.

    Conecta ao container de teste isolado na porta 38812.
    Faz login com credenciais do .env (veja .env.example).
    """
    # Validate credentials are configured
    if TEST_MT5_LOGIN == 0 or not TEST_MT5_PASSWORD:
        pytest.skip(
            "MT5 credentials not configured. "
            "Copy .env.example to .env and set MT5_TEST_LOGIN and MT5_TEST_PASSWORD"
        )

    from mt5linux import MetaTrader5

    client = MetaTrader5(host="localhost", port=TEST_RPYC_PORT)

    result = client.initialize(
        login=TEST_MT5_LOGIN,
        password=TEST_MT5_PASSWORD,
        server=TEST_MT5_SERVER,
    )

    if not result:
        error = client.last_error()
        client.close()
        pytest.skip(f"Não foi possível inicializar MT5: {error}")

    yield client

    with contextlib.suppress(Exception):
        client.shutdown()
    client.close()


@pytest.fixture
def mt5_raw() -> Generator[MetaTrader5, None, None]:
    """Fixture com MetaTrader5 conectado (sem initialize).

    Útil para testar conexão e lifecycle sem fazer login.
    """
    from mt5linux import MetaTrader5

    client = MetaTrader5(host="localhost", port=TEST_RPYC_PORT)
    yield client
    client.close()
