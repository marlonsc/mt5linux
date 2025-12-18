"""Tests for transaction safety and double execution prevention.

These tests verify that the MT5 client implements proper safeguards
against double execution of orders, which could cause serious
financial losses.

Key safety guarantees tested:
1. TIMEOUT and CONNECTION are VERIFY_REQUIRED, not RETRYABLE
2. RequestTracker generates and extracts idempotency keys
3. Order state verification before retry decisions

NO MOCKING - tests use real classification and tracking logic.
"""

from __future__ import annotations

from mt5linux.constants import MT5Constants as c
from mt5linux.utilities import MT5Utilities

# Alias for convenience
RequestTracker = MT5Utilities.TransactionHandler.RequestTracker


class TestRequestTracker:
    """Test idempotency tracking via comment field."""

    def test_generate_request_id_format(self) -> None:
        """Request ID starts with 'RQ' and has 12 chars total."""
        req_id = RequestTracker.generate_request_id()
        assert req_id.startswith("RQ"), "Request ID must start with 'RQ'"
        assert len(req_id) == 12, "Request ID must be 12 chars"

    def test_generate_request_id_unique(self) -> None:
        """Each generated request ID should be unique."""
        ids = [RequestTracker.generate_request_id() for _ in range(100)]
        assert len(ids) == len(set(ids)), "Request IDs must be unique"

    def test_mark_comment_empty(self) -> None:
        """Marking empty comment returns just the request ID."""
        marked = RequestTracker.mark_comment(None, "RQ1234567890")
        assert marked == "RQ1234567890"

        marked = RequestTracker.mark_comment("", "RQ1234567890")
        assert marked == "RQ1234567890"

    def test_mark_comment_preserves_original(self) -> None:
        """Marking preserves original comment after separator."""
        marked = RequestTracker.mark_comment("my_strategy_order", "RQ1234567890")
        assert marked.startswith("RQ1234567890|")
        assert "my_strategy" in marked

    def test_mark_comment_truncates_long(self) -> None:
        """Long comments are truncated to fit in 31 chars."""
        long_comment = "a" * 50
        marked = RequestTracker.mark_comment(long_comment, "RQ1234567890")
        assert len(marked) <= 31, "Marked comment must fit in 31 chars"

    def test_extract_request_id_works(self) -> None:
        """Can extract request_id from marked comment."""
        marked = "RQ1234567890|original_comment"
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == "RQ1234567890"

    def test_extract_request_id_no_separator(self) -> None:
        """Extract works when no separator (empty original comment)."""
        marked = "RQ1234567890"
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == "RQ1234567890"

    def test_extract_request_id_none(self) -> None:
        """Extract returns None for None comment."""
        assert RequestTracker.extract_request_id(None) is None

    def test_extract_request_id_no_prefix(self) -> None:
        """Extract returns None for comment without RQ prefix."""
        assert RequestTracker.extract_request_id("not_a_request") is None
        assert RequestTracker.extract_request_id("my_order") is None

    def test_roundtrip(self) -> None:
        """Generate, mark, extract should recover the same ID."""
        req_id = RequestTracker.generate_request_id()
        marked = RequestTracker.mark_comment("my_order", req_id)
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == req_id


class TestVerifyRequiredClassification:
    """Test that TIMEOUT/CONNECTION trigger verification, not blind retry."""

    def test_timeout_not_in_retryable_codes(self) -> None:
        """TIMEOUT (10012) must NOT be in RETRYABLE codes.

        CRITICAL: If TIMEOUT is retryable, blind retry could cause
        double execution when the original order was actually executed.
        """
        assert 10012 not in c.Resilience.MT5_RETRYABLE_CODES

    def test_connection_not_in_retryable_codes(self) -> None:
        """CONNECTION (10031) must NOT be in RETRYABLE codes.

        CRITICAL: If CONNECTION is retryable, blind retry could cause
        double execution when the original order was actually sent.
        """
        assert 10031 not in c.Resilience.MT5_RETRYABLE_CODES

    def test_timeout_in_verify_required_codes(self) -> None:
        """TIMEOUT (10012) must be in VERIFY_REQUIRED codes."""
        assert 10012 in c.Resilience.MT5_VERIFY_REQUIRED_CODES

    def test_connection_in_verify_required_codes(self) -> None:
        """CONNECTION (10031) must be in VERIFY_REQUIRED codes."""
        assert 10031 in c.Resilience.MT5_VERIFY_REQUIRED_CODES

    def test_timeout_classified_as_verify_required(self) -> None:
        """classify_mt5_retcode returns VERIFY_REQUIRED for TIMEOUT."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10012)
        assert classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED

    def test_connection_classified_as_verify_required(self) -> None:
        """classify_mt5_retcode returns VERIFY_REQUIRED for CONNECTION."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10031)
        assert classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED


class TestSafeRetryableCodes:
    """Test that truly retryable codes are still classified correctly."""

    def test_requote_is_retryable(self) -> None:
        """REQUOTE (10004) should be RETRYABLE - order was NOT executed."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10004)
        assert classification == c.Resilience.ErrorClassification.RETRYABLE

    def test_price_changed_is_retryable(self) -> None:
        """PRICE_CHANGED (10020) should be RETRYABLE - order was NOT executed."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10020)
        assert classification == c.Resilience.ErrorClassification.RETRYABLE

    def test_price_off_is_retryable(self) -> None:
        """PRICE_OFF (10021) should be RETRYABLE - order was NOT executed."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10021)
        assert classification == c.Resilience.ErrorClassification.RETRYABLE

    def test_too_many_requests_is_retryable(self) -> None:
        """TOO_MANY_REQUESTS (10024) should be RETRYABLE - rate limited."""
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10024)
        assert classification == c.Resilience.ErrorClassification.RETRYABLE


class TestVerifyRequiredEnumValue:
    """Test VERIFY_REQUIRED enum is correctly positioned."""

    def test_verify_required_value(self) -> None:
        """VERIFY_REQUIRED should have value 3."""
        assert c.Resilience.ErrorClassification.VERIFY_REQUIRED == 3

    def test_verify_required_between_retryable_and_conditional(self) -> None:
        """VERIFY_REQUIRED should be after RETRYABLE, before CONDITIONAL.

        This ordering is important for classification logic.
        """
        assert c.Resilience.ErrorClassification.RETRYABLE == 2
        assert c.Resilience.ErrorClassification.VERIFY_REQUIRED == 3
        assert c.Resilience.ErrorClassification.CONDITIONAL == 4


class TestShouldVerifyForVerifyRequired:
    """Test should_verify_state returns True for VERIFY_REQUIRED."""

    def test_should_verify_for_critical_verify_required(self) -> None:
        """should_verify_state returns True for CRITICAL + VERIFY_REQUIRED."""
        result = MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.VERIFY_REQUIRED,
        )
        assert result is True

    def test_should_verify_for_order_check_verify_required(self) -> None:
        """should_verify_state returns True for order_check + VERIFY_REQUIRED."""
        result = MT5Utilities.CircuitBreaker.should_verify_state(
            "order_check",
            c.Resilience.ErrorClassification.VERIFY_REQUIRED,
        )
        assert result is True

    def test_should_not_verify_for_non_critical_verify_required(self) -> None:
        """Non-critical operations don't need verification even for VERIFY_REQUIRED."""
        # Non-critical operations
        for op in ["account_info", "symbol_info", "symbols_total"]:
            result = MT5Utilities.CircuitBreaker.should_verify_state(
                op,
                c.Resilience.ErrorClassification.VERIFY_REQUIRED,
            )
            assert result is False, f"{op} should not verify for VERIFY_REQUIRED"


# ============================================================================
# INTEGRATION TESTS: Transaction Handler and Config
# ============================================================================


class TestCriticalRetryDelay:
    """Test calculate_critical_retry_delay for CRITICAL operations."""

    def test_critical_delay_is_shorter_than_normal(self) -> None:
        """Critical operations use shorter delay (0.1s vs 0.5s base)."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_jitter=False)

        normal_delay = config.calculate_retry_delay(0)
        critical_delay = config.calculate_critical_retry_delay(0)

        assert critical_delay < normal_delay, (
            f"Critical delay ({critical_delay}) should be < normal ({normal_delay})"
        )

    def test_critical_delay_uses_critical_initial(self) -> None:
        """Critical delay starts from critical_retry_initial_delay (0.1s)."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            critical_retry_initial_delay=0.1,
            retry_jitter=False,
        )
        delay = config.calculate_critical_retry_delay(0)
        assert delay == 0.1, f"Expected 0.1, got {delay}"

    def test_critical_delay_caps_at_half_max(self) -> None:
        """Critical delay caps at half of retry_max_delay."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            critical_retry_initial_delay=0.1,
            retry_max_delay=10.0,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )
        # After many attempts, should cap at 5.0 (half of 10.0)
        delay = config.calculate_critical_retry_delay(10)
        assert delay == 5.0, f"Expected 5.0 (half max), got {delay}"

    def test_critical_delay_exponential_backoff(self) -> None:
        """Critical delay increases exponentially."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            critical_retry_initial_delay=0.1,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )
        d0 = config.calculate_critical_retry_delay(0)
        d1 = config.calculate_critical_retry_delay(1)
        d2 = config.calculate_critical_retry_delay(2)

        assert d0 == 0.1, f"attempt 0: expected 0.1, got {d0}"
        assert d1 == 0.2, f"attempt 1: expected 0.2, got {d1}"
        assert d2 == 0.4, f"attempt 2: expected 0.4, got {d2}"


class TestTransactionHandlerIntegration:
    """Integration tests for TransactionHandler."""

    def test_prepare_request_adds_request_id(self) -> None:
        """prepare_request adds request_id to comment field."""
        request: dict[str, object] = {"action": 1, "symbol": "EURUSD"}
        prepared, req_id = MT5Utilities.TransactionHandler.prepare_request(
            request, "order_send"
        )

        assert req_id.startswith("RQ"), "request_id must start with RQ"
        comment = prepared.get("comment", "")
        assert isinstance(comment, str)
        assert req_id in comment, "request_id must be in comment"

    def test_prepare_request_preserves_original_comment(self) -> None:
        """prepare_request preserves original comment after marker."""
        request: dict[str, object] = {
            "action": 1,
            "symbol": "EURUSD",
            "comment": "my_strategy",
        }
        prepared, req_id = MT5Utilities.TransactionHandler.prepare_request(
            request, "order_send"
        )

        comment = prepared.get("comment", "")
        assert isinstance(comment, str)
        assert "my_strat" in comment, "Original comment should be preserved"

    def test_classify_result_for_common_retcodes(self) -> None:
        """classify_result maps retcodes to correct outcomes."""
        # SUCCESS codes
        success_outcome = MT5Utilities.TransactionHandler.classify_result(10009)
        assert success_outcome == c.Resilience.TransactionOutcome.SUCCESS

        # PARTIAL
        partial_outcome = MT5Utilities.TransactionHandler.classify_result(10010)
        assert partial_outcome == c.Resilience.TransactionOutcome.PARTIAL

        # RETRYABLE
        retry_outcome = MT5Utilities.TransactionHandler.classify_result(10004)
        assert retry_outcome == c.Resilience.TransactionOutcome.RETRY

        # VERIFY_REQUIRED
        verify_outcome = MT5Utilities.TransactionHandler.classify_result(10012)
        assert verify_outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED

        # PERMANENT
        perm_outcome = MT5Utilities.TransactionHandler.classify_result(10006)
        assert perm_outcome == c.Resilience.TransactionOutcome.PERMANENT_FAILURE

    def test_get_retry_config_critical_vs_normal(self) -> None:
        """get_retry_config returns more attempts for CRITICAL ops."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_max_attempts=3,
            critical_retry_max_attempts=5,
        )

        # CRITICAL operation
        th = MT5Utilities.TransactionHandler
        critical_attempts, is_critical = th.get_retry_config(config, "order_send")
        assert critical_attempts == 5, "CRITICAL should use critical_retry_max_attempts"
        assert is_critical is True

        # NON-CRITICAL operation
        normal_attempts, is_normal_critical = th.get_retry_config(config, "symbol_info")
        assert normal_attempts == 3, "NORMAL should use retry_max_attempts"
        assert is_normal_critical is False

    def test_should_retry_logic(self) -> None:
        """should_retry returns True only for RETRY outcome with attempts left."""
        # RETRY with attempts left
        assert (
            MT5Utilities.TransactionHandler.should_retry(
                c.Resilience.TransactionOutcome.RETRY, 0, 3
            )
            is True
        )

        # RETRY but no attempts left
        assert (
            MT5Utilities.TransactionHandler.should_retry(
                c.Resilience.TransactionOutcome.RETRY, 2, 3
            )
            is False
        )

        # Non-retry outcome
        assert (
            MT5Utilities.TransactionHandler.should_retry(
                c.Resilience.TransactionOutcome.SUCCESS, 0, 3
            )
            is False
        )

        assert (
            MT5Utilities.TransactionHandler.should_retry(
                c.Resilience.TransactionOutcome.VERIFY_REQUIRED, 0, 3
            )
            is False
        )


class TestCircuitBreakerRetryMethods:
    """Test async_retry_with_backoff in CircuitBreaker."""

    def test_method_exists_in_circuit_breaker(self) -> None:
        """async_retry_with_backoff should be in CircuitBreaker class."""
        assert hasattr(MT5Utilities.CircuitBreaker, "async_retry_with_backoff")
        assert callable(MT5Utilities.CircuitBreaker.async_retry_with_backoff)

    def test_reconnect_method_exists_in_circuit_breaker(self) -> None:
        """async_reconnect_with_backoff should be in CircuitBreaker class."""
        assert hasattr(MT5Utilities.CircuitBreaker, "async_reconnect_with_backoff")
        assert callable(MT5Utilities.CircuitBreaker.async_reconnect_with_backoff)


class TestRequestTrackerInTransactionHandler:
    """Test that RequestTracker is nested inside TransactionHandler."""

    def test_request_tracker_is_nested(self) -> None:
        """RequestTracker should be a nested class of TransactionHandler."""
        assert hasattr(MT5Utilities.TransactionHandler, "RequestTracker")
        tracker = MT5Utilities.TransactionHandler.RequestTracker
        assert hasattr(tracker, "generate_request_id")
        assert hasattr(tracker, "mark_comment")
        assert hasattr(tracker, "extract_request_id")

    def test_no_standalone_request_tracker(self) -> None:
        """There should be no standalone RequestTracker in MT5Utilities."""
        # RequestTracker should ONLY be accessible via TransactionHandler
        # If someone tries MT5Utilities.RequestTracker, it should fail
        # OR be the same as MT5Utilities.TransactionHandler.RequestTracker
        if hasattr(MT5Utilities, "RequestTracker"):
            # If it exists, it should be the same object
            assert (
                MT5Utilities.RequestTracker
                is MT5Utilities.TransactionHandler.RequestTracker
            ), "RequestTracker should be nested, not standalone"
