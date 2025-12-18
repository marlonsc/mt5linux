"""Proto definition validation tests.

Validates that the gRPC protocol buffer definitions are correct and complete.
These tests ensure:
- All introspection messages exist (ParameterInfo, MethodInfo, etc.)
- All service RPCs are defined
- Message fields are correctly typed

NO MOCKING - tests validate actual proto definitions.
"""

from __future__ import annotations

import math

import pytest

from mt5linux import mt5_pb2, mt5_pb2_grpc


class TestProtoIntrospectionMessages:
    """Validate introspection message definitions in proto."""

    def test_parameter_info_message_exists(self) -> None:
        """ParameterInfo message must exist with correct fields."""
        # Create instance to verify structure
        param = mt5_pb2.ParameterInfo(
            name="test",
            type_hint="int",
            kind="POSITIONAL_OR_KEYWORD",
            has_default=True,
            default_value="0",
        )
        assert param.name == "test"
        assert param.type_hint == "int"
        assert param.kind == "POSITIONAL_OR_KEYWORD"
        assert param.has_default is True
        assert param.default_value == "0"

    def test_method_info_message_exists(self) -> None:
        """MethodInfo message must exist with correct fields."""
        param = mt5_pb2.ParameterInfo(name="arg1", has_default=False)
        method = mt5_pb2.MethodInfo(
            name="test_method",
            parameters=[param],
            return_type="bool",
            is_callable=True,
        )
        assert method.name == "test_method"
        assert len(method.parameters) == 1
        assert method.return_type == "bool"
        assert method.is_callable is True

    def test_methods_response_message_exists(self) -> None:
        """MethodsResponse message must exist with correct fields."""
        method = mt5_pb2.MethodInfo(name="test", is_callable=True)
        response = mt5_pb2.MethodsResponse(
            methods=[method],
            total=1,
        )
        assert len(response.methods) == 1
        assert response.total == 1

    def test_field_info_message_exists(self) -> None:
        """FieldInfo message must exist with correct fields."""
        field = mt5_pb2.FieldInfo(
            name="balance",
            type_hint="float",
            index=0,
        )
        assert field.name == "balance"
        assert field.type_hint == "float"
        assert field.index == 0

    def test_model_info_message_exists(self) -> None:
        """ModelInfo message must exist with correct fields."""
        field = mt5_pb2.FieldInfo(name="field1", index=0)
        model = mt5_pb2.ModelInfo(
            name="AccountInfo",
            fields=[field],
            is_namedtuple=True,
        )
        assert model.name == "AccountInfo"
        assert len(model.fields) == 1
        assert model.is_namedtuple is True

    def test_models_response_message_exists(self) -> None:
        """ModelsResponse message must exist with correct fields."""
        model = mt5_pb2.ModelInfo(name="Test", is_namedtuple=True)
        response = mt5_pb2.ModelsResponse(
            models=[model],
            total=1,
        )
        assert len(response.models) == 1
        assert response.total == 1


class TestProtoBasicMessages:
    """Validate basic proto message definitions."""

    def test_empty_message_exists(self) -> None:
        """Empty message must exist."""
        empty = mt5_pb2.Empty()
        assert empty is not None

    def test_bool_response_exists(self) -> None:
        """BoolResponse message must exist."""
        response = mt5_pb2.BoolResponse(result=True)
        assert response.result is True

    def test_int_response_exists(self) -> None:
        """IntResponse message must exist."""
        response = mt5_pb2.IntResponse(value=42)
        assert response.value == 42

    def test_float_response_exists(self) -> None:
        """FloatResponse message must exist."""
        response = mt5_pb2.FloatResponse(value=math.pi)
        assert response.value == pytest.approx(math.pi)

    def test_error_info_exists(self) -> None:
        """ErrorInfo message must exist."""
        error = mt5_pb2.ErrorInfo(code=1, message="Test error")
        assert error.code == 1
        assert error.message == "Test error"

    def test_mt5_version_exists(self) -> None:
        """MT5Version message must exist."""
        version = mt5_pb2.MT5Version(major=5, minor=0, build="3500")
        assert version.major == 5
        assert version.minor == 0
        assert version.build == "3500"

    def test_constants_exists(self) -> None:
        """Constants message must exist."""
        constants = mt5_pb2.Constants(values={"TRADE_ACTION_DEAL": 1})
        assert constants.values["TRADE_ACTION_DEAL"] == 1


class TestProtoDataMessages:
    """Validate data-related proto message definitions."""

    def test_dict_data_exists(self) -> None:
        """DictData message must exist."""
        data = mt5_pb2.DictData(json_data='{"key": "value"}')
        assert data.json_data == '{"key": "value"}'

    def test_dict_list_exists(self) -> None:
        """DictList message must exist."""
        data = mt5_pb2.DictList(json_items=['{"a": 1}', '{"b": 2}'])
        assert len(data.json_items) == 2

    def test_numpy_array_exists(self) -> None:
        """NumpyArray message must exist."""
        data = mt5_pb2.NumpyArray(
            data=b"test",
            dtype="float64",
            shape=[10, 5],
        )
        assert data.data == b"test"
        assert data.dtype == "float64"
        assert list(data.shape) == [10, 5]

    def test_symbols_response_exists(self) -> None:
        """SymbolsResponse message must exist."""
        response = mt5_pb2.SymbolsResponse(
            total=100,
            chunks=['["EURUSD", "GBPUSD"]'],
        )
        assert response.total == 100
        assert len(response.chunks) == 1

    def test_health_status_exists(self) -> None:
        """HealthStatus message must exist."""
        status = mt5_pb2.HealthStatus(
            healthy=True,
            mt5_available=True,
            connected=True,
            trade_allowed=True,
            build=3500,
            reason="",
        )
        assert status.healthy is True
        assert status.mt5_available is True
        assert status.connected is True
        assert status.trade_allowed is True
        assert status.build == 3500


class TestProtoRequestMessages:
    """Validate request message definitions."""

    def test_init_request_exists(self) -> None:
        """InitRequest message must exist."""
        request = mt5_pb2.InitRequest(
            path="/path/to/mt5",
            login=12345,
            password="pass",  # noqa: S106
            server="server",
            timeout=60000,
            portable=False,
        )
        assert request.path == "/path/to/mt5"
        assert request.login == 12345

    def test_login_request_exists(self) -> None:
        """LoginRequest message must exist."""
        request = mt5_pb2.LoginRequest(
            login=12345,
            password="pass",  # noqa: S106
            server="server",
            timeout=60000,
        )
        assert request.login == 12345
        assert request.timeout == 60000

    def test_symbol_request_exists(self) -> None:
        """SymbolRequest message must exist."""
        request = mt5_pb2.SymbolRequest(symbol="EURUSD")
        assert request.symbol == "EURUSD"

    def test_copy_rates_request_exists(self) -> None:
        """CopyRatesRequest message must exist."""
        request = mt5_pb2.CopyRatesRequest(
            symbol="EURUSD",
            timeframe=1,
            date_from=1702000000,
            count=100,
        )
        assert request.symbol == "EURUSD"
        assert request.count == 100

    def test_positions_request_exists(self) -> None:
        """PositionsRequest message must exist."""
        request = mt5_pb2.PositionsRequest(
            symbol="EURUSD",
            ticket=12345,
        )
        assert request.symbol == "EURUSD"
        assert request.ticket == 12345

    def test_history_request_exists(self) -> None:
        """HistoryRequest message must exist."""
        request = mt5_pb2.HistoryRequest(
            date_from=1702000000,
            date_to=1702100000,
            ticket=12345,
        )
        assert request.date_from == 1702000000
        assert request.date_to == 1702100000


class TestProtoServiceDefinition:
    """Validate gRPC service definition."""

    def test_mt5_service_stub_exists(self) -> None:
        """MT5ServiceStub must exist in grpc module."""
        assert hasattr(mt5_pb2_grpc, "MT5ServiceStub")

    def test_mt5_service_servicer_exists(self) -> None:
        """MT5ServiceServicer must exist in grpc module."""
        assert hasattr(mt5_pb2_grpc, "MT5ServiceServicer")

    def test_add_servicer_to_server_exists(self) -> None:
        """add_MT5ServiceServicer_to_server must exist."""
        assert hasattr(mt5_pb2_grpc, "add_MT5ServiceServicer_to_server")

    def test_stub_has_introspection_methods(self) -> None:
        """Stub must have GetMethods and GetModels."""
        # Methods are added dynamically, but we can check the servicer base class
        servicer_class = mt5_pb2_grpc.MT5ServiceServicer

        # Servicer should have GetMethods and GetModels
        assert hasattr(servicer_class, "GetMethods")
        assert hasattr(servicer_class, "GetModels")

    def test_servicer_has_all_expected_methods(self) -> None:
        """Servicer must have all expected RPC methods."""
        servicer_class = mt5_pb2_grpc.MT5ServiceServicer
        expected_methods = [
            # Terminal operations
            "HealthCheck",
            "Initialize",
            "Login",
            "Shutdown",
            "Version",
            "LastError",
            "GetConstants",
            # Introspection
            "GetMethods",
            "GetModels",
            # Account/Terminal info
            "TerminalInfo",
            "AccountInfo",
            # Symbol operations
            "SymbolsTotal",
            "SymbolsGet",
            "SymbolInfo",
            "SymbolInfoTick",
            "SymbolSelect",
            # Market data
            "CopyRatesFrom",
            "CopyRatesFromPos",
            "CopyRatesRange",
            "CopyTicksFrom",
            "CopyTicksRange",
            # Trading operations
            "OrderCalcMargin",
            "OrderCalcProfit",
            "OrderCheck",
            "OrderSend",
            # Position operations
            "PositionsTotal",
            "PositionsGet",
            # Order operations
            "OrdersTotal",
            "OrdersGet",
            # History operations
            "HistoryOrdersTotal",
            "HistoryOrdersGet",
            "HistoryDealsTotal",
            "HistoryDealsGet",
            # Market Depth
            "MarketBookAdd",
            "MarketBookGet",
            "MarketBookRelease",
        ]

        for method_name in expected_methods:
            assert hasattr(servicer_class, method_name), (
                f"MT5ServiceServicer missing method: {method_name}"
            )

    def test_servicer_method_count(self) -> None:
        """Servicer should have exactly 36 RPC methods."""
        servicer_class = mt5_pb2_grpc.MT5ServiceServicer
        # Get all methods that don't start with underscore
        methods = [name for name in dir(servicer_class) if not name.startswith("_")]
        # Should have 36 methods (as defined in proto)
        assert len(methods) == 36, f"Expected 36 methods, got {len(methods)}: {methods}"
