"""The additive gRPC surface stays importable beside the upstream runtime.

The gRPC transport must not shadow or replace the upstream ``MetaTrader5``
entry point: consumers that opt into ``mt5linux.grpc`` get the bridge client,
models and settings, while the upstream RPyC runtime keeps working unchanged.

Copyright (c) 2026 Marlon Costa. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import mt5linux
from mt5linux.grpc import (
    AsyncGrpcMetaTrader5,
    GrpcMetaTrader5,
    MT5Models,
    MT5Settings,
    MT5Utilities,
)


class TestsGrpcSurface:
    """Prove the additive surface without a live MetaTrader 5 endpoint."""

    @staticmethod
    def test_upstream_entry_point_is_preserved() -> None:
        """Test upstream entry point is preserved."""
        assert mt5linux.MetaTrader5 is not GrpcMetaTrader5

    @staticmethod
    def test_grpc_client_and_models_construct() -> None:
        """Test grpc client and models construct."""
        client = GrpcMetaTrader5(host="127.0.0.1", port=50051)
        assert client is not None
        request = MT5Models.OrderRequest(
            action=1,
            symbol="EURUSD",
            volume=0.01,
            type=0,
            price=1.1,
        )
        wire = request.to_mt5_request()
        assert wire["symbol"] == "EURUSD"
        assert AsyncGrpcMetaTrader5 is not None
        assert MT5Settings is not None
        assert MT5Utilities.Exceptions.MaxRetriesError is not None


import importlib.metadata
import tomllib
from pathlib import Path

import pytest

from packaging.specifiers import SpecifierSet


class TestsProtobufFloor:
    """Prove the protobuf floor declared in pyproject.toml is satisfied at runtime."""

    @staticmethod
    def test_protobuf_floor_matches_declared_specifier() -> None:
        """The installed protobuf version must satisfy the fork's declared floor."""
        pytest.importorskip("google.protobuf")
        pyproject = tomllib.loads(Path("pyproject.toml").read_text())
        grpc_deps = pyproject["project"]["optional-dependencies"]["grpc"]
        protobuf_spec = next(
            dep for dep in grpc_deps if dep.startswith("protobuf")
        )
        # Extract specifier from "protobuf>=6.33.5,<7"
        specifier_str = protobuf_spec.split("protobuf", 1)[1].strip()
        spec = SpecifierSet(specifier_str)
        installed = importlib.metadata.version("protobuf")
        assert installed in spec, (
            f"installed protobuf {installed} does not satisfy {specifier_str}"
        )
