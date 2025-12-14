"""
Custom exceptions for mt5linux.

This module provides a hierarchy of exceptions for better error handling
when working with MetaTrader 5 via rpyc.

Exception Hierarchy:
    MT5Error
    ├── MT5ConnectionError
    │   ├── MT5TimeoutError
    │   └── MT5ServerUnavailableError
    ├── MT5AuthenticationError
    ├── MT5TradeError
    │   ├── MT5OrderRejectedError
    │   └── MT5InsufficientFundsError
    └── MT5DataError
        └── MT5SymbolNotFoundError
"""

from __future__ import annotations

from typing import Any


class MT5Error(Exception):
    """
    Base exception for all mt5linux errors.

    Attributes:
        message: Human-readable error description
        error_code: Optional MT5 error code (from last_error())
        details: Optional additional error details
    """

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with code and details."""
        msg = self.message
        if self.error_code is not None:
            msg = f"[{self.error_code}] {msg}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            msg = f"{msg} ({details_str})"
        return msg


class MT5ConnectionError(MT5Error):
    """
    Raised when connection to MT5 rpyc server fails.

    This includes:
    - Server unreachable
    - Connection refused
    - Connection timeout
    - Connection reset
    """

    def __init__(
        self,
        message: str = "Failed to connect to MT5 server",
        host: str | None = None,
        port: int | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if host:
            details["host"] = host
        if port:
            details["port"] = port
        super().__init__(message, details=details, **kwargs)


class MT5TimeoutError(MT5ConnectionError):
    """
    Raised when an operation times out.

    This can occur during:
    - Initial connection
    - Request execution
    - Data retrieval
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if timeout:
            details["timeout_seconds"] = timeout
        super().__init__(message, details=details, **kwargs)


class MT5ServerUnavailableError(MT5ConnectionError):
    """
    Raised when the MT5 rpyc server is unavailable.

    This typically means:
    - Server process not running
    - Wine/MT5 not initialized
    - Network issues
    """

    def __init__(
        self,
        message: str = "MT5 server is unavailable",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class MT5AuthenticationError(MT5Error):
    """
    Raised when authentication to MT5 broker fails.

    This includes:
    - Invalid login credentials
    - Account locked
    - Server authentication issues
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        login: int | None = None,
        server: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if login:
            details["login"] = login
        if server:
            details["server"] = server
        super().__init__(message, details=details, **kwargs)


class MT5TradeError(MT5Error):
    """
    Base exception for trading-related errors.

    This is raised when trade operations fail.
    """

    def __init__(
        self,
        message: str = "Trade operation failed",
        symbol: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if symbol:
            details["symbol"] = symbol
        super().__init__(message, details=details, **kwargs)


class MT5OrderRejectedError(MT5TradeError):
    """
    Raised when an order is rejected by the broker.

    This can happen due to:
    - Invalid parameters
    - Market closed
    - Price changed (requote)
    - Risk management rejection
    """

    def __init__(
        self,
        message: str = "Order rejected",
        retcode: int | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if retcode:
            details["retcode"] = retcode
        super().__init__(message, details=details, **kwargs)


class MT5InsufficientFundsError(MT5TradeError):
    """
    Raised when there are insufficient funds for an operation.

    This includes:
    - Not enough free margin
    - Balance too low
    """

    def __init__(
        self,
        message: str = "Insufficient funds",
        required: float | None = None,
        available: float | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if required:
            details["required"] = required
        if available:
            details["available"] = available
        super().__init__(message, details=details, **kwargs)


class MT5DataError(MT5Error):
    """
    Base exception for data retrieval errors.

    This is raised when data operations fail.
    """

    def __init__(
        self,
        message: str = "Data retrieval failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class MT5SymbolNotFoundError(MT5DataError):
    """
    Raised when a symbol is not found or not available.

    This can happen when:
    - Symbol doesn't exist
    - Symbol not enabled in Market Watch
    - Symbol not available for the account
    """

    def __init__(
        self,
        message: str = "Symbol not found",
        symbol: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if symbol:
            details["symbol"] = symbol
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# RESILIENT SERVER EXCEPTIONS
# =============================================================================


class CircuitBreakerOpenError(Exception):
    """
    Raised when circuit breaker is open and rejecting calls.

    Used by the resilient_server module to indicate that the circuit
    breaker pattern has detected too many failures and is protecting
    the system from cascade failures.
    """


# Mapping of MT5 error codes to exception classes
ERROR_CODE_MAPPING: dict[int, type[MT5Error]] = {
    # Connection errors
    -10005: MT5TimeoutError,  # RES_E_INTERNAL_FAIL_TIMEOUT
    -10004: MT5ConnectionError,  # RES_E_INTERNAL_FAIL_CONNECT
    -10003: MT5ConnectionError,  # RES_E_INTERNAL_FAIL_INIT
    # Authentication errors
    -6: MT5AuthenticationError,  # RES_E_AUTH_FAILED
    # General errors
    -1: MT5Error,  # RES_E_FAIL
    -2: MT5Error,  # RES_E_INVALID_PARAMS
}


def raise_for_error(error_code: int, error_message: str = "") -> None:
    """
    Raise an appropriate exception based on MT5 error code.

    Args:
        error_code: The error code from MT5 last_error()
        error_message: Optional error message

    Raises:
        MT5Error: Appropriate exception subclass based on error code
    """
    if error_code == 1:  # RES_S_OK
        return

    exception_class = ERROR_CODE_MAPPING.get(error_code, MT5Error)
    raise exception_class(
        message=error_message or "MT5 error occurred",
        error_code=error_code,
    )
