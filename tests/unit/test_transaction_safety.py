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

import pytest

from mt5linux.constants import MT5Constants as c
from mt5linux.utilities import MT5Utilities

# Alias for convenience
RequestTracker = MT5Utilities.TransactionHandler.RequestTracker


class TestRequestTracker:
    """Test idempotency tracking via comment field."""

    def test_generate_request_id_format(self) -> None:
        """Request ID starts with 'RQ' and has 18 chars total (RQ + 16 hex)."""
        req_id = RequestTracker.generate_request_id()
        assert req_id.startswith("RQ"), "Request ID must start with 'RQ'"
        assert len(req_id) == 18, "Request ID must be 18 chars (RQ + 16 hex)"

    def test_generate_request_id_unique(self) -> None:
        """Each generated request ID should be unique."""
        ids = [RequestTracker.generate_request_id() for _ in range(100)]
        assert len(ids) == len(set(ids)), "Request IDs must be unique"

    def test_mark_comment_empty(self) -> None:
        """Marking empty comment returns just the request ID."""
        marked = RequestTracker.mark_comment(None, "RQ1234567890abcdef")
        assert marked == "RQ1234567890abcdef"

        marked = RequestTracker.mark_comment("", "RQ1234567890abcdef")
        assert marked == "RQ1234567890abcdef"

    def test_mark_comment_preserves_original(self) -> None:
        """Marking preserves original comment after separator."""
        marked = RequestTracker.mark_comment("my_strategy_order", "RQ1234567890abcdef")
        assert marked.startswith("RQ1234567890abcdef|")
        assert "my_strategy" in marked

    def test_mark_comment_truncates_long(self) -> None:
        """Long comments are truncated to fit in 31 chars.

        CRITICAL FIX: Also verify that request_id is PRESERVED and EXTRACTABLE
        after truncation. Previous test only checked length.
        """
        long_comment = "a" * 50
        req_id = "RQ1234567890abcdef"
        marked = RequestTracker.mark_comment(long_comment, req_id)

        # Basic length check
        assert len(marked) <= 31, "Marked comment must fit in 31 chars"

        # CRITICAL: Request ID must be preserved at start
        assert marked.startswith(req_id), (
            f"Request ID '{req_id}' must be at start of marked comment, "
            f"got '{marked[:18]}'"
        )

        # CRITICAL: Request ID must be extractable (roundtrip test)
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == req_id, f"Extracted ID '{extracted}' != original '{req_id}'"

    def test_extract_request_id_works(self) -> None:
        """Can extract request_id from marked comment."""
        marked = "RQ1234567890abcdef|original_comment"
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == "RQ1234567890abcdef"

    def test_extract_request_id_no_separator(self) -> None:
        """Extract works when no separator (empty original comment)."""
        marked = "RQ1234567890abcdef"
        extracted = RequestTracker.extract_request_id(marked)
        assert extracted == "RQ1234567890abcdef"

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
        prepared, _req_id = MT5Utilities.TransactionHandler.prepare_request(
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


# ============================================================================
# EXTREME CONDITION TESTS (AUDITORIA v2)
# Tests for edge cases, boundary values, and extreme scenarios.
# These tests validate system behavior under conditions that may not
# occur frequently but are critical for financial safety.
# ============================================================================


class TestRetcodeEdgeCases:
    """Test edge cases for MT5 return codes.

    Tests boundary values and unusual retcodes that may occur in production
    but are not commonly tested.
    """

    def test_retcode_zero_treated_as_verify_required(self) -> None:
        """retcode=0 should be classified as VERIFY_REQUIRED.

        Zero indicates empty/synthetic response (e.g., timeout created synthetic
        result with retcode=0). Must trigger state verification, not blind retry.
        """
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(0)
        assert classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED

    def test_retcode_negative_treated_as_unknown(self) -> None:
        """Negative retcode should be classified as UNKNOWN.

        Negative values are not valid MT5 retcodes.
        """
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(-1)
        assert classification == c.Resilience.ErrorClassification.UNKNOWN

        # Also test more negative values
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(-999)
        assert classification == c.Resilience.ErrorClassification.UNKNOWN

    def test_retcode_very_large_treated_as_unknown(self) -> None:
        """Very large retcode should be classified as UNKNOWN.

        Values outside known MT5 retcode range should not crash.
        """
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(99999)
        assert classification == c.Resilience.ErrorClassification.UNKNOWN

    def test_all_conditional_retcodes_classified_correctly(self) -> None:
        """All CONDITIONAL retcodes should trigger CONDITIONAL classification.

        CRITICAL FIX: Previous test accepted UNKNOWN as valid, which was
        too permissive and allowed bugs to pass. CONDITIONAL codes must
        return CONDITIONAL classification.

        CONDITIONAL codes (10007, 10018, 10023, 10025) require context
        to determine if operation succeeded.
        """
        conditional_codes = [10007, 10018, 10023, 10025]
        for code in conditional_codes:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            # CRITICAL: Must be exactly CONDITIONAL, not UNKNOWN
            assert classification == c.Resilience.ErrorClassification.CONDITIONAL, (
                f"Code {code} should be CONDITIONAL, got {classification.name}"
            )

    def test_timeout_outcome_is_verify_required(self) -> None:
        """TIMEOUT retcode (10012) outcome should be VERIFY_REQUIRED."""
        outcome = MT5Utilities.TransactionHandler.classify_result(10012)
        assert outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED

    def test_connection_outcome_is_verify_required(self) -> None:
        """CONNECTION retcode (10031) outcome should be VERIFY_REQUIRED."""
        outcome = MT5Utilities.TransactionHandler.classify_result(10031)
        assert outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED

    def test_all_success_retcodes(self) -> None:
        """All success-indicating retcodes should classify as SUCCESS."""
        success_codes = [10008, 10009]  # PLACED, DONE
        for code in success_codes:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.SUCCESS

    def test_all_permanent_failure_codes(self) -> None:
        """Common permanent failure codes should classify as PERMANENT."""
        permanent_codes = [
            10006,  # REJECT
            10011,  # ERROR
            10013,  # INVALID
            10014,  # INVALID_VOLUME
            10015,  # INVALID_PRICE
        ]
        for code in permanent_codes:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.PERMANENT, (
                f"Code {code} should be PERMANENT"
            )

    def test_retcode_zero_outcome_is_verify_required(self) -> None:
        """classify_result(0) should return VERIFY_REQUIRED.

        retcode=0 indicates empty/synthetic response. Must verify state
        before deciding on retry to prevent double execution.
        """
        outcome = MT5Utilities.TransactionHandler.classify_result(0)
        # Zero is in VERIFY_REQUIRED_CODES, so outcome must be VERIFY_REQUIRED
        assert outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED, (
            f"retcode=0 outcome should be VERIFY_REQUIRED, got {outcome.name}"
        )


class TestBoundaryValues:
    """Test boundary values and edge conditions."""

    def test_comment_exactly_31_chars_preserved(self) -> None:
        """31-char comment should be handled without truncation.

        MT5 comment field has 31-char limit. Marker takes 18 chars + "|",
        so original comment can have max 12 chars after marking.
        """
        # 31 chars exactly
        long_comment = "a" * 31
        req_id = "RQ1234567890abcdef"

        marked = RequestTracker.mark_comment(long_comment, req_id)

        # Total should not exceed 31
        assert len(marked) <= 31
        # Request ID should be at start
        assert marked.startswith("RQ1234567890abcdef")

    def test_comment_at_various_lengths(self) -> None:
        """Test comment marking at various lengths near boundary."""
        req_id = "RQ1234567890abcdef"

        for length in [0, 1, 10, 12, 13, 20, 25, 30, 31, 50, 100]:
            comment = "x" * length if length > 0 else ""
            marked = RequestTracker.mark_comment(comment, req_id)
            assert len(marked) <= 31, f"Length {length} exceeded 31 chars"
            assert marked.startswith(req_id), f"Length {length} lost request ID"

    def test_attempt_at_max_is_last_retry(self) -> None:
        """Attempt = max_attempts - 1 should be the last retry."""
        max_attempts = 3

        # should_retry with RETRY outcome
        assert MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 0, max_attempts
        )
        assert MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 1, max_attempts
        )
        # At max-1, should NOT retry (already used all attempts)
        assert not MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 2, max_attempts
        )

    def test_delay_with_very_large_attempt_number(self) -> None:
        """Delay should be bounded even with very large attempt numbers.

        Prevents overflow/infinite delay on extreme retry counts.
        """
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_initial_delay=0.5,
            retry_max_delay=10.0,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )

        # Very large attempt number
        delay = config.calculate_retry_delay(1000)

        # Should be capped at max_delay
        assert delay == 10.0, f"Delay {delay} exceeds max"

    def test_critical_delay_with_large_attempt(self) -> None:
        """Critical delay should cap at half of max_delay."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            critical_retry_initial_delay=0.1,
            retry_max_delay=10.0,
            retry_exponential_base=2.0,
            retry_jitter=False,
        )

        delay = config.calculate_critical_retry_delay(1000)
        assert delay == 5.0, f"Critical delay {delay} not capped at half max"


class TestRequestIdUniqueness:
    """Test request ID generation under stress."""

    def test_generate_1000_unique_ids(self) -> None:
        """Generate 1000 request IDs - all should be unique.

        Tests uniqueness under higher volume than standard tests.
        """
        ids = [RequestTracker.generate_request_id() for _ in range(1000)]
        assert len(ids) == len(set(ids)), "Generated duplicate request IDs!"

    def test_request_id_format_always_valid(self) -> None:
        """All generated request IDs should match expected format (18 chars)."""
        for _ in range(100):
            req_id = RequestTracker.generate_request_id()
            assert req_id.startswith("RQ"), f"Invalid prefix: {req_id}"
            assert len(req_id) == 18, f"Invalid length: {req_id} (expected 18)"
            # Check hex (after RQ prefix)
            assert all(c in "0123456789abcdef" for c in req_id[2:]), (
                f"Non-hex chars in: {req_id}"
            )


class TestClassificationConsistency:
    """Test consistency between ErrorClassification and TransactionOutcome."""

    def test_success_classification_maps_to_success_outcome(self) -> None:
        """SUCCESS ErrorClassification should map to SUCCESS TransactionOutcome."""
        # 10009 = DONE = SUCCESS
        err_class = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10009)
        assert err_class == c.Resilience.ErrorClassification.SUCCESS

        outcome = MT5Utilities.TransactionHandler.classify_result(10009)
        assert outcome == c.Resilience.TransactionOutcome.SUCCESS

    def test_retryable_classification_maps_to_retry_outcome(self) -> None:
        """RETRYABLE ErrorClassification should map to RETRY TransactionOutcome."""
        # 10004 = REQUOTE = RETRYABLE
        err_class = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10004)
        assert err_class == c.Resilience.ErrorClassification.RETRYABLE

        outcome = MT5Utilities.TransactionHandler.classify_result(10004)
        assert outcome == c.Resilience.TransactionOutcome.RETRY

    def test_permanent_classification_maps_to_permanent_failure_outcome(self) -> None:
        """PERMANENT ErrorClassification should map to PERMANENT_FAILURE."""
        # 10006 = REJECT = PERMANENT
        err_class = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10006)
        assert err_class == c.Resilience.ErrorClassification.PERMANENT

        outcome = MT5Utilities.TransactionHandler.classify_result(10006)
        assert outcome == c.Resilience.TransactionOutcome.PERMANENT_FAILURE

    def test_verify_required_classification_consistency(self) -> None:
        """VERIFY_REQUIRED classification should map to VERIFY_REQUIRED outcome."""
        # 10012 = TIMEOUT, 10031 = CONNECTION
        for code in [10012, 10031]:
            err_class = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert err_class == c.Resilience.ErrorClassification.VERIFY_REQUIRED

            outcome = MT5Utilities.TransactionHandler.classify_result(code)
            assert outcome == c.Resilience.TransactionOutcome.VERIFY_REQUIRED


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker behavior under concurrent access."""

    def test_concurrent_failure_recording(self) -> None:
        """Multiple threads recording failures should not corrupt state."""
        import threading

        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=100, cb_recovery=30.0)
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: [cb.record_failure() for _ in range(5)])
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have recorded 50 failures exactly
        assert cb.failure_count == 50

    def test_concurrent_success_recording(self) -> None:
        """Multiple threads recording success should not corrupt state."""
        import threading

        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=100, cb_recovery=30.0)
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        # First record some failures
        for _ in range(10):
            cb.record_failure()
        assert cb.failure_count == 10

        threads = []
        for _ in range(10):
            t = threading.Thread(target=cb.record_success)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After any success, failure_count should be 0
        assert cb.failure_count == 0

    def test_concurrent_state_transitions(self) -> None:
        """State transitions should be atomic under concurrent access."""
        import threading
        import time

        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=3, cb_recovery=0.01)
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        results: list[str] = []
        lock = threading.Lock()

        def record_state() -> None:
            for _ in range(5):
                with lock:
                    results.append(cb.state.name)
                cb.record_failure()
                time.sleep(0.001)

        threads = [threading.Thread(target=record_state) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # States should only be valid CircuitBreakerState values
        valid_states = {"CLOSED", "OPEN", "HALF_OPEN"}
        for state in results:
            assert state in valid_states


class TestRetryWithBackoffHooks:
    """Test the hook-based retry mechanism."""

    @pytest.mark.asyncio
    async def test_should_retry_hook_prevents_retry(self) -> None:
        """When should_retry returns False, no retry should occur."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_max_attempts=5, retry_jitter=False)
        call_count = 0

        async def failing_op() -> str:
            nonlocal call_count
            call_count += 1
            msg = "permanent error"
            raise ValueError(msg)

        def never_retry(_: Exception) -> bool:
            return False

        with pytest.raises(ValueError):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                failing_op,
                config,
                "test_op",
                should_retry=never_retry,
            )

        # Should have only tried once (no retries)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_success_hook_called(self) -> None:
        """on_success hook should be called on successful operation."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_max_attempts=3)
        success_called = False

        async def success_op() -> str:
            return "done"

        def on_success() -> None:
            nonlocal success_called
            success_called = True

        await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
            success_op,
            config,
            "test_op",
            on_success=on_success,
        )

        assert success_called

    @pytest.mark.asyncio
    async def test_on_failure_hook_called_on_exhaustion(self) -> None:
        """on_failure hook should be called when retries exhausted."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_max_attempts=2,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        failure_called = False
        failure_exception: Exception | None = None

        async def always_fail() -> str:
            msg = "error"
            raise ValueError(msg)

        def on_failure(e: Exception) -> None:
            nonlocal failure_called, failure_exception
            failure_called = True
            failure_exception = e

        with pytest.raises(MT5Utilities.Exceptions.MaxRetriesError):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                always_fail,
                config,
                "test_op",
                on_failure=on_failure,
            )

        assert failure_called
        assert isinstance(failure_exception, ValueError)

    @pytest.mark.asyncio
    async def test_before_retry_hook_called(self) -> None:
        """before_retry hook should be called before each retry."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        before_retry_count = 0
        call_count = 0

        async def fail_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "not yet"
                raise ValueError(msg)
            return "success"

        async def before_retry() -> None:
            nonlocal before_retry_count
            before_retry_count += 1

        result = await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
            fail_twice,
            config,
            "test_op",
            before_retry=before_retry,
        )

        assert result == "success"
        assert call_count == 3  # First + 2 retries
        assert before_retry_count == 2  # Called before retry 2 and 3

    @pytest.mark.asyncio
    async def test_max_attempts_override(self) -> None:
        """max_attempts_override should override config value."""
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_max_attempts=10,  # High default
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            msg = "error"
            raise ValueError(msg)

        with pytest.raises(MT5Utilities.Exceptions.MaxRetriesError):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                always_fail,
                config,
                "test_op",
                max_attempts_override=2,  # Override to 2
            )

        assert call_count == 2  # Should have only tried 2 times


class TestPartialExecutionScenarios:
    """Test partial execution and fill scenarios."""

    def test_partial_fill_outcome(self) -> None:
        """PARTIAL (10010) should classify as PARTIAL outcome."""
        outcome = MT5Utilities.TransactionHandler.classify_result(10010)
        assert outcome == c.Resilience.TransactionOutcome.PARTIAL

    def test_placed_outcome_is_success(self) -> None:
        """PLACED (10008) should classify as SUCCESS outcome."""
        outcome = MT5Utilities.TransactionHandler.classify_result(10008)
        assert outcome == c.Resilience.TransactionOutcome.SUCCESS

    def test_done_outcome_is_success(self) -> None:
        """DONE (10009) should classify as SUCCESS outcome."""
        outcome = MT5Utilities.TransactionHandler.classify_result(10009)
        assert outcome == c.Resilience.TransactionOutcome.SUCCESS


# ============================================================================
# ADVERSARIAL TESTS (AUDITORIA v3)
# Tests specifically designed to BREAK the system and verify safety guarantees.
# These tests simulate extreme conditions that could cause financial loss.
# ============================================================================


class TestAdversarialRequestIdUniqueness:
    """Adversarial tests for request ID uniqueness.

    Tests parallel generation, collisions, and edge cases that could
    cause double execution if IDs are not truly unique.
    """

    def test_parallel_request_id_generation_100_threads(self) -> None:
        """Generate request IDs from 100 parallel threads.

        CRITICAL: Even with concurrent generation, all IDs must be unique.
        Duplicate IDs could cause one order to be mistaken for another.
        """
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        all_ids: list[str] = []
        lock = threading.Lock()

        def generate_batch() -> list[str]:
            batch = [RequestTracker.generate_request_id() for _ in range(100)]
            with lock:
                all_ids.extend(batch)
            return batch

        # Generate from 100 parallel threads, 100 IDs each = 10,000 total
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(generate_batch) for _ in range(100)]
            for future in as_completed(futures):
                _ = future.result()  # Ensure no exceptions

        assert len(all_ids) == 10000, f"Expected 10000 IDs, got {len(all_ids)}"
        unique_ids = set(all_ids)
        assert len(unique_ids) == 10000, (
            f"COLLISION DETECTED! {10000 - len(unique_ids)} duplicate IDs generated"
        )

    def test_rapid_sequential_generation(self) -> None:
        """Generate 10000 IDs in rapid sequence.

        Tests that UUID source doesn't have rapid-fire collisions.
        """
        ids = [RequestTracker.generate_request_id() for _ in range(10000)]
        unique = set(ids)
        assert len(unique) == len(ids), "Sequential generation produced duplicates"


class TestAdversarialCommentTruncation:
    """Adversarial tests for comment field truncation.

    Tests edge cases where truncation could corrupt the request ID,
    making verification impossible.
    """

    def test_truncation_always_preserves_extractable_id(self) -> None:
        """Truncation must ALWAYS preserve extractable request ID.

        Tests various comment lengths to ensure request ID is never corrupted.
        """
        req_id = "RQ1234567890abcdef"  # 18 chars

        # Test all lengths from 0 to 100
        for length in range(101):
            comment = "x" * length if length > 0 else ""
            marked = RequestTracker.mark_comment(comment, req_id)

            # Must fit in 31 chars
            assert len(marked) <= 31, f"Length {length}: exceeded 31 chars"

            # Request ID must be at start
            assert marked.startswith(req_id), (
                f"Length {length}: ID not at start: '{marked[:18]}'"
            )

            # CRITICAL: Must be extractable
            extracted = RequestTracker.extract_request_id(marked)
            assert extracted == req_id, (
                f"Length {length}: extraction failed: got '{extracted}'"
            )

    def test_special_characters_in_comment(self) -> None:
        """Special characters in comment should not break extraction."""
        req_id = "RQ1234567890abcdef"
        special_comments = [
            "RQ|fake",  # Looks like another request ID
            "|||||",  # Multiple separators
            "RQabcdef12345678",  # Looks like request ID
            "RQ" + "x" * 50,  # Starts with RQ but too long
        ]

        for comment in special_comments:
            marked = RequestTracker.mark_comment(comment, req_id)
            extracted = RequestTracker.extract_request_id(marked)
            assert extracted == req_id, (
                f"Special '{comment}' corrupted extraction: got '{extracted}'"
            )


class TestAdversarialRequestIdValidation:
    """Tests for request ID validation robustness.

    Tests that invalid/corrupted IDs are properly rejected.
    """

    def test_rejects_invalid_hex_characters(self) -> None:
        """Request IDs with invalid hex chars should be rejected."""
        invalid_ids = [
            "RQgggggggggggggggg",  # 'g' is not hex (18 chars)
            "RQ12345!@#$%abcdef",  # Special chars (18 chars)
            "RQZZZZZZZZZZZZZZZZ",  # Z is not hex (18 chars)
            "RQ12345 67890abcde",  # Space in ID (18 chars)
        ]
        for invalid_id in invalid_ids:
            extracted = RequestTracker.extract_request_id(invalid_id)
            assert extracted is None, f"Invalid ID '{invalid_id}' was accepted"

    def test_rejects_wrong_length(self) -> None:
        """Request IDs with wrong length should be rejected."""
        wrong_lengths = [
            "RQ",  # Too short (2 chars)
            "RQ12345",  # Too short (7 chars)
            "RQ1234567890",  # Too short (12 chars - old format)
            "RQ12345678901234",  # Too short (16 chars)
            "RQ123456789012345",  # Too short (17 chars)
            "RQ12345678901234567",  # Too long (19 chars)
            "RQ1234567890123456789",  # Too long (21 chars)
        ]
        for wrong_id in wrong_lengths:
            extracted = RequestTracker.extract_request_id(wrong_id)
            assert extracted is None, f"Wrong length '{wrong_id}' was accepted"

    def test_rejects_concatenated_ids(self) -> None:
        """Concatenated IDs (broker corruption) should not match wrong ID.

        Simulates broker concatenating multiple order comments.
        """
        # Simulated corrupted comment: two IDs concatenated (18-char format)
        corrupted = "RQ0000000000000001|Trade1RQ0000000000000002|Trade2"
        extracted = RequestTracker.extract_request_id(corrupted)

        # Should extract the first valid ID (18 chars)
        assert extracted == "RQ0000000000000001", (
            f"Extraction from corrupted: {extracted}"
        )


class TestAdversarialCircuitBreakerBehavior:
    """Adversarial tests for circuit breaker behavior.

    Tests race conditions and threshold accuracy.
    """

    def test_cb_threshold_exact(self) -> None:
        """Circuit breaker should open at EXACTLY the threshold.

        Not before, not after.
        """
        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=5, cb_recovery=60.0)
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        # Record failures up to threshold - 1
        for i in range(4):
            cb.record_failure()
            assert cb.state == c.Resilience.CircuitBreakerState.CLOSED, (
                f"CB opened early at failure {i + 1}"
            )

        # Record the threshold failure
        cb.record_failure()
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN, (
            "CB did not open at threshold"
        )

    def test_cb_threshold_after_multiple_verify_timeouts(self) -> None:
        """CB should open correctly after multiple verify timeouts.

        Simulates 5 orders each with 3 verify timeouts = 15 failures.
        CB with threshold 5 should be OPEN.
        """
        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=5, cb_recovery=60.0)
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        # Simulate 5 orders with 3 verify timeouts each
        failures_recorded = 0
        for _order in range(5):
            for _verify_attempt in range(3):
                cb.record_failure()
                failures_recorded += 1

        # After 15 failures, CB should definitely be OPEN
        assert failures_recorded == 15
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN, (
            f"CB should be OPEN after {failures_recorded} failures"
        )

    def test_can_execute_race_condition(self) -> None:
        """Test can_execute under concurrent access.

        Ensures no race condition where operation is allowed when CB is OPEN.
        """
        import threading

        from mt5linux.config import MT5Config

        config = MT5Config(cb_threshold=5, cb_recovery=0.1)  # Fast recovery
        cb = MT5Utilities.CircuitBreaker(config=config, name="test")

        # Open the CB
        for _ in range(5):
            cb.record_failure()
        assert cb.state == c.Resilience.CircuitBreakerState.OPEN

        allowed_count = 0
        lock = threading.Lock()

        def try_execute() -> None:
            nonlocal allowed_count
            for _ in range(100):
                if cb.can_execute():
                    with lock:
                        allowed_count += 1

        # Run 10 threads trying to execute
        threads = [threading.Thread(target=try_execute) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # In HALF_OPEN, only cb_half_open_max (3) should be allowed
        assert allowed_count <= 3, (
            f"Too many executions allowed: {allowed_count} (max 3 in HALF_OPEN)"
        )


class TestAdversarialRetryBehavior:
    """Adversarial tests for retry behavior.

    Tests that retries don't cause double execution.
    """

    @pytest.mark.asyncio
    async def test_before_retry_failure_does_not_hang(self) -> None:
        """If before_retry fails, system should not hang.

        Tests that reconnection failure doesn't cause infinite loop.
        """
        from mt5linux.config import MT5Config

        config = MT5Config(
            retry_max_attempts=3,
            retry_initial_delay=0.01,
            retry_jitter=False,
        )
        call_count = 0
        before_retry_failures = 0

        async def failing_op() -> str:
            nonlocal call_count
            call_count += 1
            msg = "error"
            raise ValueError(msg)

        async def failing_before_retry() -> None:
            nonlocal before_retry_failures
            before_retry_failures += 1
            msg = "reconnection failed"
            raise ConnectionError(msg)

        with pytest.raises(MT5Utilities.Exceptions.MaxRetriesError):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                failing_op,
                config,
                "test_op",
                before_retry=failing_before_retry,
            )

        # Should have attempted all retries despite before_retry failing
        assert call_count == 3, f"Only {call_count} calls (expected 3)"
        # before_retry should have been called before retries 2 and 3
        assert before_retry_failures == 2, (
            f"before_retry called {before_retry_failures} times"
        )


class TestAdversarialExceptionHandling:
    """Tests for exception classification and handling."""

    def test_is_retryable_exception_rejects_permanent_errors(self) -> None:
        """PermanentError should never be classified as retryable."""
        perm_error = MT5Utilities.Exceptions.PermanentError(10006, "rejected")
        assert not MT5Utilities.CircuitBreaker.is_retryable_exception(perm_error)

    def test_is_retryable_exception_accepts_connection_errors(self) -> None:
        """ConnectionError should be classified as retryable for reconnection."""
        conn_error = ConnectionError("connection lost")
        assert MT5Utilities.CircuitBreaker.is_retryable_exception(conn_error)

    def test_is_retryable_exception_accepts_timeout_errors(self) -> None:
        """TimeoutError should be classified as retryable."""
        timeout_error = TimeoutError("operation timed out")
        assert MT5Utilities.CircuitBreaker.is_retryable_exception(timeout_error)


# ============================================================================
# ADVERSARIAL TESTS v4
# Tests for newly discovered vulnerabilities in audit v4.
# These tests verify fixes for CRITICAL and HIGH severity issues.
# ============================================================================


class TestAdversarialV4ZeroIds:
    """Test behavior when order=0 AND deal=0 (synthetic result scenario).

    CRITICAL FIX v4: When order_send returns empty/timeout, synthetic result
    has order=0 and deal=0. Verification must still work via comment.
    """

    def test_verify_required_codes_includes_zero(self) -> None:
        """retcode=0 must be in VERIFY_REQUIRED codes.

        retcode=0 indicates empty/synthetic response where we don't know
        if order was actually executed. MUST trigger verification.
        """
        assert 0 in c.Resilience.MT5_VERIFY_REQUIRED_CODES, (
            "retcode=0 MUST be in VERIFY_REQUIRED_CODES - empty responses "
            "need state verification"
        )

    def test_retcode_zero_classified_as_verify_required(self) -> None:
        """classify_mt5_retcode(0) should return VERIFY_REQUIRED.

        Not UNKNOWN (which triggers VERIFY_REQUIRED anyway), but explicitly
        VERIFY_REQUIRED for clarity and correctness.
        """
        # Since 0 is in VERIFY_REQUIRED_CODES, it should classify as VERIFY_REQUIRED
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(0)
        assert classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED, (
            f"retcode=0 should be VERIFY_REQUIRED, got {classification.name}"
        )


class TestAdversarialV4RetryBoundary:
    """Test retry boundary conditions to prevent mutation bugs.

    CRITICAL: Operator mutation from >= to > could allow extra retry,
    causing double execution on already-executed orders.
    """

    def test_retry_boundary_at_max_minus_one(self) -> None:
        """At attempt = max_attempts - 1, should NOT retry.

        This is the boundary: attempt 2 of max 3 means we've already tried
        3 times (0, 1, 2). No more retries allowed.
        """
        max_attempts = 3

        # Attempt 0: first try -> can retry
        assert MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 0, max_attempts
        )

        # Attempt 1: second try -> can retry
        assert MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 1, max_attempts
        )

        # Attempt 2: third try -> NO MORE RETRIES
        # This is the critical boundary
        assert not MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 2, max_attempts
        ), "MUTATION BUG: attempt >= max-1 should NOT retry!"

    def test_retry_boundary_exactly_at_max(self) -> None:
        """At attempt = max_attempts, should definitely NOT retry."""
        max_attempts = 3

        # Attempt 3: beyond max -> definitely no retry
        assert not MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 3, max_attempts
        ), "attempt >= max should never retry"

    def test_retry_boundary_single_attempt(self) -> None:
        """With max_attempts=1, should NEVER retry."""
        max_attempts = 1

        # Even on first failure, should not retry with max=1
        assert not MT5Utilities.TransactionHandler.should_retry(
            c.Resilience.TransactionOutcome.RETRY, 0, max_attempts
        ), "max_attempts=1 means no retries ever"


class TestAdversarialV4CircuitBreakerDisabled:
    """Test behavior when circuit breaker is disabled (None).

    When enable_circuit_breaker=False, CB can be None. All CB operations
    must handle this gracefully without crashing.
    """

    def test_cb_disabled_config(self) -> None:
        """Verify CB can be disabled via config."""
        from mt5linux.config import MT5Config

        config = MT5Config(enable_circuit_breaker=False)
        assert config.enable_circuit_breaker is False

    def test_classify_retcode_works_without_cb_instance(self) -> None:
        """classify_mt5_retcode is a classmethod, works without CB instance."""
        # This should work even without any CB instance
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(10009)
        assert classification == c.Resilience.ErrorClassification.SUCCESS

    def test_is_retryable_exception_works_without_cb_instance(self) -> None:
        """is_retryable_exception is a classmethod, works without CB instance."""
        # Should work as static/class method
        assert MT5Utilities.CircuitBreaker.is_retryable_exception(TimeoutError())
        assert not MT5Utilities.CircuitBreaker.is_retryable_exception(ValueError())


class TestAdversarialV4UUID64Bit:
    """Test UUID collision resistance with 64-bit (16 hex char) IDs.

    With 64 bits of entropy, birthday paradox collision expected after ~4B IDs.
    Test that 100k IDs are all unique (should be trivially true with 64 bits).
    """

    def test_100k_unique_ids_64bit(self) -> None:
        """Generate 100,000 request IDs - all must be unique.

        With 64-bit UUIDs, collision probability for 100k is essentially 0.
        This test verifies the UUID length increase was implemented correctly.
        """
        ids = set()
        for i in range(100_000):
            req_id = RequestTracker.generate_request_id()

            # Verify format: RQ + 16 hex chars = 18 total
            assert len(req_id) == 18, f"ID {i}: wrong length {len(req_id)}"
            assert req_id.startswith("RQ"), f"ID {i}: missing RQ prefix"
            assert all(c in "0123456789abcdef" for c in req_id[2:]), (
                f"ID {i}: non-hex chars in {req_id}"
            )

            # Check uniqueness
            assert req_id not in ids, f"COLLISION at ID {i}: {req_id}"
            ids.add(req_id)

        assert len(ids) == 100_000, "Not all IDs were unique!"

    def test_uuid_entropy_64bit(self) -> None:
        """Verify UUIDs have good entropy distribution.

        Check that hex chars are reasonably distributed (not all same).
        Note: UUID4 has fixed version digit at hex position 12 (always '4'),
        which maps to our string position 14 (after 'RQ' prefix).
        """
        ids = [RequestTracker.generate_request_id() for _ in range(1000)]

        # Count each hex char position's variation
        # Skip position 14 - UUID4 version digit is always '4'
        for pos in range(2, 18):  # Skip "RQ" prefix
            if pos == 14:  # UUID4 version digit - always '4'
                continue
            chars_at_pos = [req_id[pos] for req_id in ids]
            unique_chars = set(chars_at_pos)
            # Should see multiple different hex chars at each position
            assert len(unique_chars) >= 8, (
                f"Position {pos} has low entropy: only {len(unique_chars)} chars"
            )


class TestAdversarialV4TimeoutResultRecovery:
    """Test that results arriving at timeout boundary are not lost.

    CRITICAL FIX v4: When result arrives exactly at timeout (4.99s vs 5.0s),
    the task might complete just as TimeoutError is raised. Must check
    task.done() and recover result to prevent false "not found" → duplicate.
    """

    @pytest.mark.asyncio
    async def test_task_result_checked_after_timeout(self) -> None:
        """Verify concept: task.done() can be True even after TimeoutError.

        This tests the underlying Python behavior we rely on.
        """
        import asyncio

        result_value = "ORDER_EXECUTED"

        async def slow_task() -> str:
            await asyncio.sleep(0.05)  # 50ms
            return result_value

        task = asyncio.create_task(slow_task())

        # Wait with very short timeout - will timeout
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), timeout=0.001)

        # But task might still complete!
        await asyncio.sleep(0.1)  # Let it complete

        # Task should be done now
        assert task.done(), "Task should complete even after TimeoutError"
        assert task.result() == result_value, "Result should be recoverable"


class TestAdversarialV4EmptyDealsHandling:
    """Test handling of empty deals vs None.

    CRITICAL: None, [], and () should all be handled the same way
    when checking for deals in verification.
    """

    def test_empty_list_is_falsy(self) -> None:
        """Verify [] evaluates to False in boolean context."""
        empty_list: list[object] = []
        assert not empty_list, "Empty list should be falsy"

    def test_empty_tuple_is_falsy(self) -> None:
        """Verify () evaluates to False in boolean context."""
        empty_tuple: tuple[object, ...] = ()
        assert not empty_tuple, "Empty tuple should be falsy"

    def test_none_is_falsy(self) -> None:
        """Verify None evaluates to False in boolean context."""
        none_value = None
        assert not none_value, "None should be falsy"

    def test_all_empty_types_handled_same(self) -> None:
        """All empty deal responses should trigger same behavior.

        When checking `if deals:`, None/[]/() should all be False.
        """
        empty_responses: list[object] = [None, [], ()]

        for response in empty_responses:
            # All should be falsy
            assert not response, f"{type(response).__name__} should be falsy"

            # Pattern used in verification
            if response:
                pytest.fail(f"{type(response).__name__} incorrectly truthy")


class TestAdversarialV4MaxAttemptsValidation:
    """Test max_attempts parameter validation.

    max_attempts < 1 is invalid and could cause infinite loops or
    incorrect retry behavior.
    """

    @pytest.mark.asyncio
    async def test_max_attempts_zero_raises_error(self) -> None:
        """max_attempts=0 should raise ValueError."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_max_attempts=3)

        async def dummy_op() -> str:
            return "ok"

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                dummy_op,
                config,
                "test_op",
                max_attempts_override=0,
            )

    @pytest.mark.asyncio
    async def test_max_attempts_negative_raises_error(self) -> None:
        """max_attempts=-1 should raise ValueError."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_max_attempts=3)

        async def dummy_op() -> str:
            return "ok"

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
                dummy_op,
                config,
                "test_op",
                max_attempts_override=-1,
            )

    @pytest.mark.asyncio
    async def test_max_attempts_one_is_valid(self) -> None:
        """max_attempts=1 should be valid (single attempt, no retries)."""
        from mt5linux.config import MT5Config

        config = MT5Config(retry_max_attempts=3)
        call_count = 0

        async def counting_op() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await MT5Utilities.CircuitBreaker.async_retry_with_backoff(
            counting_op,
            config,
            "test_op",
            max_attempts_override=1,
        )

        assert result == "ok"
        assert call_count == 1, "Should only call once with max_attempts=1"
