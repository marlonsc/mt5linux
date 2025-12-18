"""Tests for MT5Utilities.RequestQueue - Priority Queue with Parallel Execution.

Tests verify:
1. Priority ordering (CRITICAL > HIGH > NORMAL > LOW)
2. Parallel execution (NOT sequential)
3. Semaphore-controlled concurrency
4. Request coalescing (dedupe identical calls)
5. Backpressure when queue full
6. Graceful shutdown

NO MOCKING - tests use real asyncio primitives.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from mt5linux.config import MT5Config
from mt5linux.constants import MT5Constants as c
from mt5linux.utilities import MT5Utilities

# Aliases for convenience
RequestQueue = MT5Utilities.RequestQueue
QueueFullError = MT5Utilities.Exceptions.QueueFullError


@pytest.fixture
def config() -> MT5Config:
    """Return default config for tests."""
    return MT5Config(queue_max_concurrent=3, queue_max_depth=10)


@pytest.fixture
async def queue(config: MT5Config) -> RequestQueue:
    """Return started request queue for tests."""
    q = RequestQueue(config)
    await q.start()
    yield q
    await q.stop()


class TestRequestQueueLifecycle:
    """Test queue start/stop lifecycle."""

    async def test_start_sets_running(self, config: MT5Config) -> None:
        """start() sets is_running to True."""
        queue = RequestQueue(config)
        assert not queue.is_running

        await queue.start()
        assert queue.is_running

        await queue.stop()
        assert not queue.is_running

    async def test_start_idempotent(self, queue: RequestQueue) -> None:
        """Multiple start() calls are safe (idempotent)."""
        assert queue.is_running
        await queue.start()
        await queue.start()
        assert queue.is_running

    async def test_stop_clears_state(self, config: MT5Config) -> None:
        """stop() clears all internal state."""
        queue = RequestQueue(config)
        await queue.start()

        # Submit something to have state
        async def quick() -> int:
            return 42

        await queue.submit("test", quick)
        await queue.stop()

        assert not queue.is_running
        assert queue.active_count == 0
        assert queue.pending_count == 0


class TestRequestQueueBasicSubmit:
    """Test basic submit functionality."""

    async def test_submit_returns_result(self, queue: RequestQueue) -> None:
        """submit() returns coroutine result."""

        async def compute() -> int:
            return 42

        result = await queue.submit("test", compute)
        assert result == 42

    async def test_submit_propagates_exception(self, queue: RequestQueue) -> None:
        """submit() propagates exceptions from coroutine."""

        async def fail() -> None:
            msg = "test error"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="test error"):
            await queue.submit("test", fail)

    async def test_submit_multiple_sequential(self, queue: RequestQueue) -> None:
        """Multiple sequential submits all return correct results."""
        results = []
        for i in range(5):

            async def compute(val: int = i) -> int:
                return val * 2

            result = await queue.submit("test", compute)
            results.append(result)

        assert results == [0, 2, 4, 6, 8]


class TestRequestQueuePriority:
    """Test priority ordering of requests."""

    async def test_priority_queue_orders_by_priority(self) -> None:
        """Verify PriorityQueue orders items correctly when both queued.

        This tests the internal priority ordering mechanism by directly
        adding items to the queue while dispatcher is paused.
        """
        config = MT5Config(queue_max_concurrent=1, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        execution_order: list[str] = []
        gate = asyncio.Event()

        async def blocking() -> str:
            await gate.wait()
            return "blocking"

        async def record(name: str) -> str:
            execution_order.append(name)
            return name

        # Submit blocker to hold the semaphore
        blocker = asyncio.create_task(queue.submit("test", blocking))
        await asyncio.sleep(0.05)

        # Pause dispatcher to queue items without immediate processing
        queue._running = False
        if queue._dispatcher_task:
            queue._dispatcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await queue._dispatcher_task

        # Directly add items with known priorities to test ordering
        loop = asyncio.get_running_loop()

        # Add LOW priority item first (priority=3)
        low_future: asyncio.Future[str] = loop.create_future()
        low_req = queue._Request(
            priority=3,
            timestamp=loop.time(),
            key="",
            coro_factory=lambda: record("low"),
            future=low_future,
        )
        queue._queue.put_nowait(low_req)

        await asyncio.sleep(0.01)

        # Add CRITICAL priority item second (priority=0)
        critical_future: asyncio.Future[str] = loop.create_future()
        critical_req = queue._Request(
            priority=0,
            timestamp=loop.time() + 0.001,  # Later timestamp
            key="",
            coro_factory=lambda: record("critical"),
            future=critical_future,
        )
        queue._queue.put_nowait(critical_req)

        # Verify queue has both items
        assert queue._queue.qsize() == 2

        # Restart dispatcher
        queue._running = True
        queue._dispatcher_task = asyncio.create_task(queue._dispatcher())

        # Release blocker
        gate.set()
        await blocker

        # Wait for queued items
        await asyncio.gather(low_future, critical_future)
        await queue.stop()

        # CRITICAL (priority 0) should execute before LOW (priority 3)
        # despite LOW being queued first
        assert execution_order[0] == "critical", (
            f"Expected CRITICAL first due to priority, got: {execution_order}"
        )
        assert execution_order[1] == "low"


class TestRequestQueueParallelExecution:
    """Test parallel (NOT sequential) execution."""

    async def test_parallel_execution_not_sequential(self, config: MT5Config) -> None:
        """Multiple requests execute in PARALLEL, not sequentially."""
        config = MT5Config(queue_max_concurrent=5, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        # Track concurrent execution
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def track_concurrent(delay: float) -> int:
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(delay)

            async with lock:
                current_concurrent -= 1

            return 1

        # Submit 5 concurrent requests
        tasks = [
            asyncio.create_task(queue.submit("test", lambda: track_concurrent(0.1)))
            for _ in range(5)
        ]

        await asyncio.gather(*tasks)
        await queue.stop()

        # Should have had multiple concurrent executions
        assert max_concurrent > 1, (
            f"Expected parallel execution, but max concurrent was {max_concurrent}"
        )


class TestRequestQueueSemaphore:
    """Test semaphore-controlled concurrency."""

    async def test_semaphore_limits_concurrency(self) -> None:
        """Semaphore limits concurrent executions to max_concurrent."""
        config = MT5Config(queue_max_concurrent=2, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        # Track max concurrent
        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()

        async def track(delay: float = 0.1) -> int:
            nonlocal max_concurrent, current
            async with lock:
                current += 1
                max_concurrent = max(max_concurrent, current)

            await asyncio.sleep(delay)

            async with lock:
                current -= 1

            return 1

        # Submit more than semaphore allows
        tasks = [asyncio.create_task(queue.submit("test", track)) for _ in range(10)]

        await asyncio.gather(*tasks)
        await queue.stop()

        # Should never exceed semaphore limit
        assert max_concurrent <= 2, (
            f"Exceeded semaphore limit: max={max_concurrent}, limit=2"
        )


class TestRequestQueueCoalescing:
    """Test request coalescing (deduplication)."""

    async def test_coalescing_identical_requests(self, queue: RequestQueue) -> None:
        """Identical coalesce_key requests share the same result."""
        call_count = 0

        async def expensive() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return "result"

        # Submit same key multiple times concurrently
        tasks = [
            asyncio.create_task(
                queue.submit(
                    "symbol_info_tick",
                    expensive,
                    coalesce_key="symbol_info_tick:EURUSD",
                )
            )
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should get same result
        assert all(r == "result" for r in results)
        # But expensive() should only be called once (coalesced)
        assert call_count == 1

    async def test_no_coalescing_without_key(self, queue: RequestQueue) -> None:
        """Requests without coalesce_key are NOT coalesced."""
        call_count = 0

        async def compute() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        # Submit without coalesce_key
        tasks = [asyncio.create_task(queue.submit("test", compute)) for _ in range(3)]

        await asyncio.gather(*tasks)

        # Each should have been called
        assert call_count == 3

    async def test_no_coalescing_for_orders(self, queue: RequestQueue) -> None:
        """order_send requests are NEVER coalesced (each is unique)."""
        call_count = 0

        async def send_order() -> dict:
            nonlocal call_count
            call_count += 1
            return {"order": call_count}

        # Submit order_send WITHOUT coalesce_key (as per design)
        tasks = [
            asyncio.create_task(
                queue.submit("order_send", send_order, coalesce_key=None)
            )
            for _ in range(3)
        ]

        await asyncio.gather(*tasks)

        # Each order should execute separately
        assert call_count == 3


class TestRequestQueueBackpressure:
    """Test backpressure when queue is full."""

    async def test_queue_full_raises_error(self) -> None:
        """QueueFullError raised when queue at max_depth."""
        # Very small queue
        config = MT5Config(queue_max_concurrent=1, queue_max_depth=2)
        queue = RequestQueue(config)
        await queue.start()

        # Block the first request
        gate = asyncio.Event()

        async def blocking() -> None:
            await gate.wait()

        # Fill queue
        task1 = asyncio.create_task(queue.submit("test", blocking))
        await asyncio.sleep(0.02)  # Let it be picked up

        # These fill the queue
        async def noop() -> None:
            pass

        task2 = asyncio.create_task(queue.submit("test", noop))
        task3 = asyncio.create_task(queue.submit("test", noop))

        await asyncio.sleep(0.02)

        # Next should fail with QueueFullError
        with pytest.raises(QueueFullError, match="queue full"):
            await queue.submit("test", noop)

        # Cleanup
        gate.set()
        await asyncio.gather(task1, task2, task3, return_exceptions=True)
        await queue.stop()


class TestRequestQueueCounts:
    """Test active_count and pending_count properties."""

    async def test_active_count_during_execution(self) -> None:
        """active_count reflects running tasks."""
        config = MT5Config(queue_max_concurrent=5, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        gate = asyncio.Event()

        async def wait_for_gate() -> None:
            await gate.wait()

        # Start several tasks
        tasks = [
            asyncio.create_task(queue.submit("test", wait_for_gate)) for _ in range(3)
        ]

        await asyncio.sleep(0.1)  # Let them be picked up

        # Should have active tasks
        assert queue.active_count == 3

        gate.set()
        await asyncio.gather(*tasks)

        # After completion, no active
        await asyncio.sleep(0.05)
        assert queue.active_count == 0

        await queue.stop()

    async def test_pending_count_reflects_queue_size(self) -> None:
        """pending_count reflects items waiting in queue."""
        config = MT5Config(queue_max_concurrent=1, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        gate = asyncio.Event()

        async def wait_for_gate() -> None:
            await gate.wait()

        # Block with one task
        task1 = asyncio.create_task(queue.submit("test", wait_for_gate))
        await asyncio.sleep(0.05)

        # Queue more
        async def noop() -> None:
            pass

        task2 = asyncio.create_task(queue.submit("test", noop))
        task3 = asyncio.create_task(queue.submit("test", noop))

        await asyncio.sleep(0.05)

        # Should have pending items
        assert queue.pending_count >= 1

        gate.set()
        await asyncio.gather(task1, task2, task3)
        await queue.stop()


class TestRequestQueuePriorityMapping:
    """Test priority mapping from OPERATION_CRITICALITY."""

    def test_priority_mapping_for_critical_operations(self) -> None:
        """CRITICAL operations (3) map to priority 0 (highest)."""
        # order_send has criticality 3 (CRITICAL)
        criticality = c.Resilience.OPERATION_CRITICALITY.get("order_send", 1)
        priority = 3 - criticality
        assert priority == 0

    def test_priority_mapping_for_low_operations(self) -> None:
        """LOW priority operations (0) map to priority 3 (lowest)."""
        # symbols_total has criticality 0 (LOW)
        criticality = c.Resilience.OPERATION_CRITICALITY.get("symbols_total", 0)
        priority = 3 - criticality
        assert priority == 3

    def test_priority_mapping_for_unknown_operations(self) -> None:
        """Unknown operations default to priority 2 (NORMAL)."""
        criticality = c.Resilience.OPERATION_CRITICALITY.get("unknown_op", 1)
        priority = 3 - criticality
        assert priority == 2


class TestRequestQueueGracefulShutdown:
    """Test graceful shutdown drains active tasks."""

    async def test_stop_waits_for_active_tasks(self) -> None:
        """stop() waits for active tasks to complete."""
        config = MT5Config(queue_max_concurrent=5, queue_max_depth=20)
        queue = RequestQueue(config)
        await queue.start()

        completed = []

        async def slow(idx: int) -> int:
            await asyncio.sleep(0.2)
            completed.append(idx)
            return idx

        # Start several tasks
        tasks = [
            asyncio.create_task(queue.submit("test", lambda i=i: slow(i)))
            for i in range(3)
        ]

        # Give tasks time to start
        await asyncio.sleep(0.05)

        # Stop should wait for completion
        await queue.stop()

        # All should have completed
        assert len(completed) == 3

        # Cleanup
        await asyncio.gather(*tasks, return_exceptions=True)
