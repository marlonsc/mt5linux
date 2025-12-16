"""Centralized utilities for mt5linux.

All shared utilities, validators, and transformers are organized here.

Usage:
    from mt5linux.utilities import Validators, DataTransformer, RetryHelper
"""

from __future__ import annotations

import random
from datetime import datetime
from functools import cache
from typing import Any

# =============================================================================
# Constants
# =============================================================================

VERSION_TUPLE_LEN = 3  # (version, build, version_string)
ERROR_TUPLE_LEN = 2  # (error_code, error_description)


# =============================================================================
# Type Validators
# =============================================================================


class Validators:
    """Type validators for MT5 data.

    Convert rpyc's 'Any' return types to proper Python types,
    ensuring type safety without 'type: ignore' comments.
    """

    @staticmethod
    def version(value: object) -> tuple[int, int, str] | None:
        """Validate and convert Any to version tuple."""
        if value is None:
            return None
        if not isinstance(value, tuple) or len(value) != VERSION_TUPLE_LEN:
            msg = f"Expected tuple[int, int, str] | None, got {type(value).__name__}"
            raise TypeError(msg)
        try:
            return (int(value[0]), int(value[1]), str(value[2]))
        except (ValueError, IndexError, TypeError) as e:
            msg = f"Invalid version tuple: {e}"
            raise TypeError(msg) from e

    @staticmethod
    def last_error(value: object) -> tuple[int, str]:
        """Validate and convert Any to last_error tuple."""
        if not isinstance(value, tuple) or len(value) != ERROR_TUPLE_LEN:
            msg = f"Expected tuple[int, str], got {type(value).__name__}"
            raise TypeError(msg)
        try:
            return (int(value[0]), str(value[1]))
        except (ValueError, IndexError, TypeError) as e:
            msg = f"Invalid error tuple: {e}"
            raise TypeError(msg) from e

    @staticmethod
    def bool_value(value: object) -> bool:
        """Validate and convert Any to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        msg = f"Expected bool, got {type(value).__name__}"
        raise TypeError(msg)

    @staticmethod
    def int_value(value: object) -> int:
        """Validate and convert Any to int."""
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        msg = f"Expected int, got {type(value).__name__}"
        raise TypeError(msg)

    @staticmethod
    def int_optional(value: object) -> int | None:
        """Validate and convert Any to int | None."""
        if value is None:
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        msg = f"Expected int | None, got {type(value).__name__}"
        raise TypeError(msg)

    @staticmethod
    def float_optional(value: object) -> float | None:
        """Validate and convert Any to float | None."""
        if value is None:
            return None
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        msg = f"Expected float | None, got {type(value).__name__}"
        raise TypeError(msg)


# =============================================================================
# Data Transformers
# =============================================================================


class DataWrapper:
    """Wrapper for MT5 data dict with attribute access."""

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            msg = f"'{type(self).__name__}' has no attribute '{name}'"
            raise AttributeError(msg) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._data})"

    def _asdict(self) -> dict[str, Any]:
        """Return underlying dict (compatibility with named tuples)."""
        return self._data


class DataTransformer:
    """Transform MT5 data between formats."""

    @staticmethod
    def wrap_dict(d: dict[str, Any] | Any) -> DataWrapper | Any:
        """Convert dict to object with attribute access."""
        if isinstance(d, dict):
            return DataWrapper(d)
        return d

    @staticmethod
    def wrap_dicts(items: tuple | list | None) -> tuple | None:
        """Convert tuple/list of dicts to tuple of objects."""
        if items is None:
            return None
        return tuple(DataTransformer.wrap_dict(d) for d in items)

    @staticmethod
    def unwrap_chunks(result: dict[str, Any] | None) -> tuple | None:
        """Reassemble chunked response from server into tuple of objects."""
        if result is None:
            return None

        if isinstance(result, dict) and "chunks" in result:
            all_items: list[DataWrapper] = []
            for chunk in result["chunks"]:
                all_items.extend(DataWrapper(d) for d in chunk)
            return tuple(all_items)

        if isinstance(result, tuple | list):
            return DataTransformer.wrap_dicts(result)

        return None


# =============================================================================
# Retry Helper
# =============================================================================


class RetryHelper:
    """Retry and backoff utilities."""

    @staticmethod
    @cache
    def calculate_delay(
        attempt: int,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
    ) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = min(initial_delay * (exponential_base**attempt), max_delay)
        delay *= 0.5 + random.random()  # noqa: S311
        return delay

    @staticmethod
    def backoff_with_jitter(
        attempt: int,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter_factor: float = 0.1,
    ) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = base_delay * (multiplier**attempt)
        delay = min(delay, max_delay)
        # S311: random is fine for jitter - not cryptographic
        jitter = delay * jitter_factor * (2 * random.random() - 1)  # noqa: S311
        return max(0, delay + jitter)


# =============================================================================
# DateTime Utilities
# =============================================================================


class DateTimeUtils:
    """DateTime conversion utilities."""

    @staticmethod
    def to_timestamp(dt: datetime | int | None) -> int | None:
        """Convert datetime to Unix timestamp for MT5 API."""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return int(dt.timestamp())
        return dt
