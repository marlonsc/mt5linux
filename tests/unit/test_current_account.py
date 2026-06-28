"""Unit tests for AsyncMetaTrader5.current_account() (mt5linux extension).

No live bridge: health_check / account_info are stubbed so the combination logic
(connected -> live account; disconnected -> host/port only) is verified in
isolation.
"""

from __future__ import annotations

import asyncio

import pytest

from mt5linux.async_client import AsyncMetaTrader5
from mt5linux.models import MT5Models


def _client() -> AsyncMetaTrader5:
    return AsyncMetaTrader5(host="testhost", port=12345)


@pytest.mark.unit
def test_current_account_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    """When connected, current_account merges the live account into the view."""
    client = _client()

    async def fake_health() -> dict[str, bool | int | str]:
        return {
            "healthy": True,
            "mt5_available": True,
            "connected": True,
            "trade_allowed": True,
            "build": 5956,
            "reason": "",
        }

    account = MT5Models.AccountInfo(
        login=5052338262,
        server="MetaQuotes-Demo",
        company="MetaQuotes Ltd.",
        name="Auto Trader",
        balance=100000.0,
        currency="USD",
    )

    async def fake_account() -> MT5Models.AccountInfo | None:
        return account

    monkeypatch.setattr(client, "health_check", fake_health)
    monkeypatch.setattr(client, "account_info", fake_account)

    result = asyncio.run(client.current_account())
    assert result.host == "testhost"
    assert result.port == 12345
    assert result.connected is True
    assert result.trade_allowed is True
    assert result.build == 5956
    assert result.login == 5052338262
    assert result.server == "MetaQuotes-Demo"
    assert result.company == "MetaQuotes Ltd."
    assert result.balance == 100000.0
    assert result.currency == "USD"


@pytest.mark.unit
def test_current_account_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    """When not connected, current_account reports host/port + connected=False.

    account_info is NOT called (would fail); the account fields stay None.
    """
    client = _client()
    called = {"account_info": False}

    async def fake_health() -> dict[str, bool | int | str]:
        return {
            "healthy": False,
            "mt5_available": True,
            "connected": False,
            "trade_allowed": False,
            "build": 0,
            "reason": "Terminal not connected",
        }

    async def fake_account() -> MT5Models.AccountInfo | None:
        called["account_info"] = True
        return None

    monkeypatch.setattr(client, "health_check", fake_health)
    monkeypatch.setattr(client, "account_info", fake_account)

    result = asyncio.run(client.current_account())
    assert result.host == "testhost"
    assert result.port == 12345
    assert result.connected is False
    assert result.login is None
    assert result.server is None
    assert result.build is None
    assert called["account_info"] is False
