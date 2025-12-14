"""
Legacy test file - kept for backwards compatibility.

For proper unit tests, see test_connection.py
For integration tests, see test_integration.py
"""

import pytest


def test_legacy_placeholder() -> None:
    """Placeholder test to ensure test discovery works."""
    # This replaces the old broken test that required a running server
    # See test_connection.py for comprehensive unit tests
    # See test_integration.py for integration tests (requires --run-integration)
    assert True
