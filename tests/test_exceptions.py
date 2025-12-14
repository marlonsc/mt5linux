"""
Tests for mt5linux custom exceptions.
"""

from __future__ import annotations

import pytest

from mt5linux.exceptions import (
    MT5AuthenticationError,
    MT5ConnectionError,
    MT5DataError,
    MT5Error,
    MT5InsufficientFundsError,
    MT5OrderRejectedError,
    MT5ServerUnavailableError,
    MT5SymbolNotFoundError,
    MT5TimeoutError,
    MT5TradeError,
    raise_for_error,
)


class TestMT5Error:
    """Test base MT5Error exception."""

    def test_basic_message(self) -> None:
        """Test exception with basic message."""
        error = MT5Error("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code is None
        assert error.details == {}

    def test_with_error_code(self) -> None:
        """Test exception with error code."""
        error = MT5Error("Test error", error_code=-1)
        assert "[-1]" in str(error)
        assert error.error_code == -1

    def test_with_details(self) -> None:
        """Test exception with details."""
        error = MT5Error("Test error", details={"key": "value"})
        assert "key=value" in str(error)
        assert error.details == {"key": "value"}

    def test_full_format(self) -> None:
        """Test exception with all parameters."""
        error = MT5Error("Test error", error_code=-1, details={"key": "value"})
        msg = str(error)
        assert "[-1]" in msg
        assert "Test error" in msg
        assert "key=value" in msg


class TestMT5ConnectionError:
    """Test connection-related exceptions."""

    def test_connection_error(self) -> None:
        """Test basic connection error."""
        error = MT5ConnectionError("Connection failed", host="localhost", port=8001)
        assert "Connection failed" in str(error)
        assert "localhost" in str(error)
        assert "8001" in str(error)

    def test_timeout_error(self) -> None:
        """Test timeout error."""
        error = MT5TimeoutError("Request timed out", timeout=30.0)
        assert "timed out" in str(error)
        assert "30" in str(error)
        assert isinstance(error, MT5ConnectionError)
        assert isinstance(error, MT5Error)

    def test_server_unavailable_error(self) -> None:
        """Test server unavailable error."""
        error = MT5ServerUnavailableError()
        assert "unavailable" in str(error).lower()
        assert isinstance(error, MT5ConnectionError)


class TestMT5AuthenticationError:
    """Test authentication exception."""

    def test_basic_auth_error(self) -> None:
        """Test basic authentication error."""
        error = MT5AuthenticationError()
        assert "Authentication failed" in str(error)

    def test_auth_error_with_details(self) -> None:
        """Test authentication error with login details."""
        error = MT5AuthenticationError(
            "Invalid credentials",
            login=12345,
            server="Demo-Server",
        )
        assert "Invalid credentials" in str(error)
        assert "12345" in str(error)
        assert "Demo-Server" in str(error)


class TestMT5TradeError:
    """Test trading-related exceptions."""

    def test_basic_trade_error(self) -> None:
        """Test basic trade error."""
        error = MT5TradeError("Trade failed", symbol="EURUSD")
        assert "Trade failed" in str(error)
        assert "EURUSD" in str(error)

    def test_order_rejected_error(self) -> None:
        """Test order rejected error."""
        error = MT5OrderRejectedError("Order rejected", retcode=10006)
        assert "rejected" in str(error).lower()
        assert "10006" in str(error)
        assert isinstance(error, MT5TradeError)

    def test_insufficient_funds_error(self) -> None:
        """Test insufficient funds error."""
        error = MT5InsufficientFundsError(
            "Not enough margin",
            required=1000.0,
            available=500.0,
        )
        assert "margin" in str(error).lower() or "funds" in str(error).lower()
        assert "1000" in str(error)
        assert "500" in str(error)
        assert isinstance(error, MT5TradeError)


class TestMT5DataError:
    """Test data-related exceptions."""

    def test_basic_data_error(self) -> None:
        """Test basic data error."""
        error = MT5DataError("Data retrieval failed")
        assert "Data retrieval failed" in str(error)

    def test_symbol_not_found_error(self) -> None:
        """Test symbol not found error."""
        error = MT5SymbolNotFoundError("Symbol not available", symbol="XYZUSD")
        assert "not" in str(error).lower()
        assert "XYZUSD" in str(error)
        assert isinstance(error, MT5DataError)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_connection_error_is_mt5_error(self) -> None:
        """Test MT5ConnectionError inherits from MT5Error."""
        assert issubclass(MT5ConnectionError, MT5Error)

    def test_timeout_error_is_connection_error(self) -> None:
        """Test MT5TimeoutError inherits from MT5ConnectionError."""
        assert issubclass(MT5TimeoutError, MT5ConnectionError)

    def test_trade_error_is_mt5_error(self) -> None:
        """Test MT5TradeError inherits from MT5Error."""
        assert issubclass(MT5TradeError, MT5Error)

    def test_data_error_is_mt5_error(self) -> None:
        """Test MT5DataError inherits from MT5Error."""
        assert issubclass(MT5DataError, MT5Error)

    def test_auth_error_is_mt5_error(self) -> None:
        """Test MT5AuthenticationError inherits from MT5Error."""
        assert issubclass(MT5AuthenticationError, MT5Error)


class TestRaiseForError:
    """Test raise_for_error helper function."""

    def test_success_code_no_raise(self) -> None:
        """Test that success code doesn't raise."""
        # Should not raise
        raise_for_error(1)

    def test_timeout_error_code(self) -> None:
        """Test timeout error code raises MT5TimeoutError."""
        with pytest.raises(MT5TimeoutError):
            raise_for_error(-10005)

    def test_connection_error_code(self) -> None:
        """Test connection error code raises MT5ConnectionError."""
        with pytest.raises(MT5ConnectionError):
            raise_for_error(-10004)

    def test_auth_error_code(self) -> None:
        """Test auth error code raises MT5AuthenticationError."""
        with pytest.raises(MT5AuthenticationError):
            raise_for_error(-6)

    def test_generic_error_code(self) -> None:
        """Test unknown error code raises MT5Error."""
        with pytest.raises(MT5Error):
            raise_for_error(-999)

    def test_error_with_message(self) -> None:
        """Test error with custom message."""
        with pytest.raises(MT5Error) as exc_info:
            raise_for_error(-1, "Custom error message")
        assert "Custom error message" in str(exc_info.value)
