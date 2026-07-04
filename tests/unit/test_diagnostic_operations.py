"""Unit coverage for diagnostic operations on disconnected terminals."""

from __future__ import annotations

import asyncio

import pytest

from mt5linux import mt5_pb2
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.models import MT5Models


def _client() -> AsyncMetaTrader5:
    return AsyncMetaTrader5(host="testhost", port=12345)


class _DiagnosticStub:
    async def HealthCheck(  # noqa: N802
        self,
        request: object,
        timeout: float,  # noqa: ASYNC109
    ) -> mt5_pb2.HealthStatus:
        del request, timeout
        return mt5_pb2.HealthStatus(
            healthy=False,
            mt5_available=True,
            connected=False,
            trade_allowed=False,
            build=0,
            reason="Terminal not connected",
        )

    async def LastError(  # noqa: N802
        self,
        request: object,
        timeout: float,  # noqa: ASYNC109
    ) -> mt5_pb2.ErrorInfo:
        del request, timeout
        return mt5_pb2.ErrorInfo(code=-1, message="Terminal not connected")

    async def GetProvisionedAccount(  # noqa: N802
        self,
        request: object,
        timeout: float,  # noqa: ASYNC109
    ) -> mt5_pb2.ProvisionedAccount:
        del request, timeout
        return mt5_pb2.ProvisionedAccount(
            login=0,
            server="",
            connected=False,
            source="missing",
        )


@pytest.mark.unit
def test_diagnostics_do_not_require_terminal_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic RPCs must report disconnected state instead of requiring login."""
    client = _client()
    stub = _DiagnosticStub()
    monkeypatch.setattr(client, "_ensure_connected", lambda: stub)

    async def fail_terminal_info() -> None:
        pytest.fail("diagnostic operation called terminal_info guard")

    monkeypatch.setattr(client, "terminal_info", fail_terminal_info)

    health = asyncio.run(client.health_check())
    assert health["connected"] is False
    assert health["reason"] == "Terminal not connected"

    assert asyncio.run(client.last_error()) == (-1, "Terminal not connected")

    provisioned = asyncio.run(client.recover_provisioned_account())
    assert isinstance(provisioned, MT5Models.ProvisionedAccount)
    assert provisioned.connected is False
    assert provisioned.source == "missing"
