"""Unit tests for recover_provisioned_account() + create_demo_account().

No live bridge: the gRPC stub is replaced so the request mapping (CreateDemoSpec
-> CreateDemoRequest) and the response mapping (proto -> MT5Models.ProvisionedAccount)
are verified in isolation. The proto types are mypy-opaque (replace-imports-with-any),
so request fields are checked via str(request) and stub params are typed `object`.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar

import pytest

from mt5linux import mt5_pb2
from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.models import MT5Models

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_T = TypeVar("_T")


def _client() -> AsyncMetaTrader5:
    return AsyncMetaTrader5(host="testhost", port=12345)


class _RecoverStub:
    # Method name + timeout mirror the generated gRPC stub exactly.
    async def GetProvisionedAccount(  # noqa: N802
        self,
        request: object,
        timeout: float,  # noqa: ASYNC109
    ) -> object:
        del request, timeout
        return mt5_pb2.ProvisionedAccount(
            login=5052338262,
            server="MetaQuotes-Demo",
            email="auto@example.com",
            created_at="2026-06-28T00:00:00Z",
            login_confirmed=True,
            credentials_persisted=True,
            connected=True,
            source="auto_create_demo_account",
        )


class _CreateStub:
    def __init__(self) -> None:
        self.request: object = None
        self.timeout: float = 0.0

    async def CreateDemoAccount(  # noqa: N802
        self,
        request: object,
        timeout: float,  # noqa: ASYNC109
    ) -> object:
        self.request = request
        self.timeout = timeout
        return mt5_pb2.ProvisionedAccount(
            login=777, server="MetaQuotes-Demo", email="x@y.z", connected=True
        )


@pytest.mark.unit
def test_recover_provisioned_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """recover_provisioned_account maps the GetProvisionedAccount proto -> model."""
    client = _client()
    monkeypatch.setattr(client, "_ensure_connected", _RecoverStub)

    async def passthrough(_name: str, call: Callable[[], Awaitable[_T]]) -> _T:
        return await call()

    monkeypatch.setattr(client, "_resilient_call", passthrough)

    result = asyncio.run(client.recover_provisioned_account())
    assert isinstance(result, MT5Models.ProvisionedAccount)
    assert result.login == 5052338262
    assert result.server == "MetaQuotes-Demo"
    assert result.email == "auto@example.com"
    assert result.login_confirmed is True
    assert result.credentials_persisted is True
    assert result.connected is True
    assert result.source == "auto_create_demo_account"


@pytest.mark.unit
def test_create_demo_account_maps_spec_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_demo_account forwards the spec into the request; maps the response."""
    client = _client()
    stub = _CreateStub()
    monkeypatch.setattr(client, "_ensure_connected", lambda: stub)

    spec = MT5Models.CreateDemoSpec(
        server="MetaQuotes-Demo", email="x@y.z", phone="11988887777"
    )
    result = asyncio.run(client.create_demo_account(spec))

    # The spec fields must reach the gRPC request (proto text repr carries them).
    request_text = str(stub.request)
    assert "MetaQuotes-Demo" in request_text
    assert "x@y.z" in request_text
    assert "11988887777" in request_text
    assert stub.timeout >= 300  # create drives a long-running wizard
    assert result.login == 777
    assert result.server == "MetaQuotes-Demo"
    assert result.email == "x@y.z"
