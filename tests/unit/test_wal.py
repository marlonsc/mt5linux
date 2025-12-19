"""Tests for u.WAL - Write-Ahead Log for Order Operations.

Tests verify:
1. WAL initialization and schema creation
2. Status transitions (PENDING -> SENT -> VERIFIED/FAILED)
3. Recovery of incomplete entries
4. Cleanup of old entries
5. Concurrent access safety

NO MOCKING - tests use real SQLite database in temp directory.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mt5linux.settings import MT5Settings
from mt5linux.utilities import MT5Utilities as u

# Aliases for convenience
WAL = u.WAL


@pytest.fixture
def temp_db_path() -> str:
    """Return temporary database path for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return f.name


@pytest.fixture
def config(temp_db_path: str) -> MT5Settings:
    """Return config with temp database path."""
    return MT5Settings(wal_path=temp_db_path, wal_retention_days=7)


@pytest.fixture
async def wal(config: MT5Settings) -> WAL:
    """Return initialized WAL for tests."""
    w = WAL(config)
    await w.initialize()
    yield w
    await w.close()
    # Cleanup temp file
    Path(config.wal_path).unlink(missing_ok=True)


class TestWALLifecycle:
    """Test WAL initialization and cleanup."""

    async def test_initialize_creates_database(self, config: MT5Settings) -> None:
        """initialize() creates SQLite database with schema."""
        wal = WAL(config)
        await wal.initialize()

        # Database file should exist
        assert Path(config.wal_path).exists()

        # Should be idempotent
        await wal.initialize()
        await wal.initialize()

        await wal.close()

    async def test_close_is_safe_when_not_initialized(
        self, config: MT5Settings
    ) -> None:
        """close() is safe to call even if not initialized."""
        wal = WAL(config)
        await wal.close()  # Should not raise
        await wal.close()  # Should not raise

    async def test_operations_safe_when_not_initialized(
        self, config: MT5Settings
    ) -> None:
        """Operations return gracefully when not initialized."""
        wal = WAL(config)

        # These should not raise
        await wal.log_intent("test", {"action": 1})
        await wal.mark_sent("test")
        await wal.mark_verified("test", {"result": 1})
        await wal.mark_failed("test", "error")

        incomplete = await wal.get_incomplete()
        assert incomplete == []

        count = await wal.cleanup_old()
        assert count == 0


class TestWALStatusTransitions:
    """Test status transition methods."""

    async def test_log_intent_creates_pending_entry(self, wal: WAL) -> None:
        """log_intent() creates entry with PENDING status."""
        request = {"action": 1, "symbol": "EURUSD", "volume": 0.1}
        await wal.log_intent("RQ001", request)

        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 1
        assert incomplete[0].request_id == "RQ001"
        assert incomplete[0].status == WAL.Status.PENDING

    async def test_mark_sent_updates_status(self, wal: WAL) -> None:
        """mark_sent() updates entry to SENT status."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_sent("RQ001")

        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 1
        assert incomplete[0].status == WAL.Status.SENT

    async def test_mark_verified_removes_from_incomplete(self, wal: WAL) -> None:
        """mark_verified() updates entry and removes from incomplete list."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_sent("RQ001")
        await wal.mark_verified("RQ001", {"retcode": 10009, "order": 12345})

        # Should no longer be incomplete
        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 0

    async def test_mark_failed_removes_from_incomplete(self, wal: WAL) -> None:
        """mark_failed() updates entry and removes from incomplete list."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_sent("RQ001")
        await wal.mark_failed("RQ001", "Order rejected")

        # Should no longer be incomplete
        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 0


class TestWALGetEntry:
    """Test get_entry method."""

    async def test_get_entry_returns_existing(self, wal: WAL) -> None:
        """get_entry() returns entry for existing request_id."""
        await wal.log_intent("RQ001", {"action": 1, "symbol": "EURUSD"})

        entry = await wal.get_entry("RQ001")
        assert entry is not None
        assert entry.request_id == "RQ001"
        assert "EURUSD" in entry.request_json

    async def test_get_entry_returns_none_for_missing(self, wal: WAL) -> None:
        """get_entry() returns None for non-existent request_id."""
        entry = await wal.get_entry("NONEXISTENT")
        assert entry is None

    async def test_get_entry_with_result(self, wal: WAL) -> None:
        """get_entry() includes result_json after verification."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_sent("RQ001")
        await wal.mark_verified("RQ001", {"retcode": 10009, "order": 12345})

        entry = await wal.get_entry("RQ001")
        assert entry is not None
        assert entry.result_json is not None
        assert "12345" in entry.result_json

    async def test_get_entry_with_error(self, wal: WAL) -> None:
        """get_entry() includes error after failure."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_failed("RQ001", "Insufficient margin")

        entry = await wal.get_entry("RQ001")
        assert entry is not None
        assert entry.error == "Insufficient margin"


class TestWALRecovery:
    """Test recovery functionality."""

    async def test_get_incomplete_returns_pending_and_sent(self, wal: WAL) -> None:
        """get_incomplete() returns both PENDING and SENT entries."""
        await wal.log_intent("RQ001", {"action": 1})  # PENDING
        await wal.log_intent("RQ002", {"action": 1})
        await wal.mark_sent("RQ002")  # SENT
        await wal.log_intent("RQ003", {"action": 1})
        await wal.mark_sent("RQ003")
        await wal.mark_verified("RQ003", {})  # VERIFIED - not incomplete

        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 2
        request_ids = {e.request_id for e in incomplete}
        assert request_ids == {"RQ001", "RQ002"}

    async def test_get_incomplete_ordered_by_timestamp(self, wal: WAL) -> None:
        """get_incomplete() returns entries ordered by timestamp (oldest first)."""
        await wal.log_intent("RQ002", {"action": 1})
        await asyncio.sleep(0.01)
        await wal.log_intent("RQ001", {"action": 1})
        await asyncio.sleep(0.01)
        await wal.log_intent("RQ003", {"action": 1})

        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 3
        # First entry should be RQ002 (oldest)
        assert incomplete[0].request_id == "RQ002"


class TestWALCleanup:
    """Test cleanup of old entries."""

    async def test_cleanup_old_removes_verified(self, wal: WAL) -> None:
        """cleanup_old() removes old VERIFIED entries."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_verified("RQ001", {})

        # With 0 days retention, should remove immediately
        removed = await wal.cleanup_old(days=0)
        assert removed == 1

    async def test_cleanup_old_removes_failed(self, wal: WAL) -> None:
        """cleanup_old() removes old FAILED entries."""
        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_failed("RQ001", "error")

        removed = await wal.cleanup_old(days=0)
        assert removed == 1

    async def test_cleanup_old_preserves_incomplete(self, wal: WAL) -> None:
        """cleanup_old() never removes PENDING or SENT entries."""
        await wal.log_intent("RQ001", {"action": 1})  # PENDING
        await wal.log_intent("RQ002", {"action": 1})
        await wal.mark_sent("RQ002")  # SENT

        removed = await wal.cleanup_old(days=0)
        assert removed == 0

        # Both should still be there
        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 2

    async def test_cleanup_respects_retention_period(self, config: MT5Settings) -> None:
        """cleanup_old() respects retention period."""
        wal = WAL(config)
        await wal.initialize()

        await wal.log_intent("RQ001", {"action": 1})
        await wal.mark_verified("RQ001", {})

        # With 7 days retention (default), should not remove recent
        removed = await wal.cleanup_old()
        assert removed == 0

        await wal.close()


class TestWALConcurrency:
    """Test concurrent access to WAL."""

    async def test_concurrent_log_intent(self, wal: WAL) -> None:
        """Multiple concurrent log_intent() calls succeed."""

        async def log_one(i: int) -> None:
            await wal.log_intent(f"RQ{i:03d}", {"action": 1, "index": i})

        # Submit 20 concurrent logs
        await asyncio.gather(*[log_one(i) for i in range(20)])

        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 20

    async def test_concurrent_transitions(self, wal: WAL) -> None:
        """Multiple concurrent status transitions succeed."""
        # Create entries
        for i in range(10):
            await wal.log_intent(f"RQ{i:03d}", {"action": 1})

        # Concurrently transition them
        async def transition(i: int) -> None:
            request_id = f"RQ{i:03d}"
            await wal.mark_sent(request_id)
            if i % 2 == 0:
                await wal.mark_verified(request_id, {"index": i})
            else:
                await wal.mark_failed(request_id, f"error_{i}")

        await asyncio.gather(*[transition(i) for i in range(10)])

        # All should be complete (no incomplete)
        incomplete = await wal.get_incomplete()
        assert len(incomplete) == 0


class TestWALStatusEnum:
    """Test WAL.Status enum values."""

    def test_status_values(self) -> None:
        """Status enum has expected integer values."""
        assert WAL.Status.PENDING == 0
        assert WAL.Status.SENT == 1
        assert WAL.Status.VERIFIED == 2
        assert WAL.Status.FAILED == 3
        assert WAL.Status.RECOVERED == 4

    def test_status_ordering(self) -> None:
        """Status enum values are ordered logically."""
        # PENDING < SENT < VERIFIED/FAILED
        assert WAL.Status.PENDING < WAL.Status.SENT
        assert WAL.Status.SENT < WAL.Status.VERIFIED
        assert WAL.Status.SENT < WAL.Status.FAILED


class TestWALEntry:
    """Test WAL.Entry dataclass."""

    def test_entry_fields(self) -> None:
        """Entry has expected fields."""
        entry = WAL.Entry(
            request_id="RQ001",
            timestamp=datetime.now(UTC),
            request_json='{"action": 1}',
            status=WAL.Status.PENDING,
            result_json=None,
            error=None,
        )

        assert entry.request_id == "RQ001"
        assert entry.request_json == '{"action": 1}'
        assert entry.status == WAL.Status.PENDING
        assert entry.result_json is None
        assert entry.error is None
