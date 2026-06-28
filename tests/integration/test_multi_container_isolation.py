"""Multi-container isolation: distinct env -> distinct resources, no collision.

Validates that several mt5 instances can run in parallel without conflict: for N
parameter sets the resolved docker-compose config must have PAIRWISE-DISTINCT
container name, host ports, volume name, and network name. Uses
`docker compose config` only (no container is started), so it is fast +
deterministic and does not depend on a broker connection.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yaml"

# Three parallel instances with fully distinct parameters.
INSTANCES: tuple[dict[str, str], ...] = (
    {
        "MT5_CONTAINER_NAME": "mt5-iso-a",
        "MT5_GRPC_PORT": "18001",
        "MT5_VNC_PORT": "13001",
        "MT5_HEALTH_PORT": "18011",
        "MT5_NETWORK_NAME": "mt5-iso-a-net",
    },
    {
        "MT5_CONTAINER_NAME": "mt5-iso-b",
        "MT5_GRPC_PORT": "18002",
        "MT5_VNC_PORT": "13002",
        "MT5_HEALTH_PORT": "18012",
        "MT5_NETWORK_NAME": "mt5-iso-b-net",
    },
    {
        "MT5_CONTAINER_NAME": "mt5-iso-c",
        "MT5_GRPC_PORT": "18003",
        "MT5_VNC_PORT": "13003",
        "MT5_HEALTH_PORT": "18013",
        "MT5_NETWORK_NAME": "mt5-iso-c-net",
    },
)


def _at(obj: object, *path: str) -> object:
    """Navigate nested dicts from `docker compose config` JSON, type-safely."""
    cur: object = obj
    for key in path:
        if not isinstance(cur, dict):
            msg = f"expected dict at {key!r}, got {type(cur).__name__}"
            raise TypeError(msg)
        cur = cur[key]
    return cur


def _first_name(obj: object) -> str:
    """Return the `name` of the single mapping entry (volumes/networks)."""
    if not isinstance(obj, dict) or not obj:
        msg = f"expected non-empty mapping, got {obj!r}"
        raise TypeError(msg)
    entry = next(iter(obj.values()))
    return str(_at(entry, "name"))


def _resolve(overrides: dict[str, str]) -> dict[str, str]:
    """Resolve one instance's compose config to its collidable resource names."""
    env = {**os.environ, **overrides, "ENV_FILE": "/dev/null"}
    proc = subprocess.run(  # noqa: S603  # fixed argv, no shell
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--format", "json"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    cfg: object = json.loads(proc.stdout)
    svc = _at(cfg, "services", "mt5")
    ports = _at(svc, "ports")
    if not isinstance(ports, list):
        msg = "ports must be a list"
        raise TypeError(msg)
    published = ",".join(sorted(str(_at(p, "published")) for p in ports))
    return {
        "container": str(_at(svc, "container_name")),
        "ports": published,
        "volume": _first_name(_at(cfg, "volumes")),
        "network": _first_name(_at(cfg, "networks")),
    }


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")
def test_parallel_instances_have_no_resource_collision() -> None:
    """N distinct parameter sets -> pairwise-distinct container/ports/volume/network."""
    resolved = [_resolve(inst) for inst in INSTANCES]
    for field in ("container", "ports", "volume", "network"):
        values = [r[field] for r in resolved]
        assert len(set(values)) == len(values), (
            f"{field} collides across parallel instances: {values}"
        )
