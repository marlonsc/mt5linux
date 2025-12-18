"""Tests for MT5 error classification and operation criticality.

Tests the ErrorClassification enum, OperationCriticality enum,
and the CircuitBreaker classification methods.

NO MOCKING - tests use real classification logic.
"""

from __future__ import annotations

from mt5linux.constants import MT5Constants as c
from mt5linux.utilities import MT5Utilities


class TestErrorClassification:
    """Test retcode classification."""

    def test_success_codes_classified_as_success(self) -> None:
        """Success codes should be classified as SUCCESS."""
        success_codes = [10008, 10009]  # PLACED, DONE
        for code in success_codes:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.SUCCESS, (
                f"Code {code} should be SUCCESS, got {classification}"
            )

    def test_partial_code_classified_correctly(self) -> None:
        """DONE_PARTIAL should be classified as PARTIAL."""
        code = 10010  # DONE_PARTIAL
        classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
        assert classification == c.Resilience.ErrorClassification.PARTIAL

    def test_retryable_codes_classified_correctly(self) -> None:
        """Retryable codes (safe to retry - order NOT executed)."""
        # NOTE: 10012 (TIMEOUT) and 10031 (CONNECTION) are now VERIFY_REQUIRED
        # because the order MAY have been executed!
        retryable = [10004, 10020, 10021, 10024]
        # REQUOTE, PRICE_CHANGED, PRICE_OFF, TOO_MANY_REQUESTS
        for code in retryable:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.RETRYABLE, (
                f"Code {code} should be RETRYABLE, got {classification}"
            )

    def test_verify_required_codes_classified_correctly(self) -> None:
        """TIMEOUT and CONNECTION must be VERIFY_REQUIRED, not RETRYABLE.

        These codes mean the order MAY have been executed - we MUST verify
        the state before deciding to retry. Blind retry could cause double
        execution with serious financial consequences.
        """
        verify_required = [10012, 10031]  # TIMEOUT, CONNECTION
        for code in verify_required:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.VERIFY_REQUIRED, (
                f"Code {code} should be VERIFY_REQUIRED, got {classification}"
            )

    def test_conditional_codes_classified_correctly(self) -> None:
        """Conditional codes should be classified as CONDITIONAL."""
        conditional = [10007, 10018, 10023, 10025]
        # CANCEL, MARKET_CLOSED, ORDER_CHANGED, NO_CHANGES
        for code in conditional:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.CONDITIONAL, (
                f"Code {code} should be CONDITIONAL, got {classification}"
            )

    def test_permanent_codes_classified_correctly(self) -> None:
        """Permanent codes should be classified as PERMANENT."""
        permanent = [
            10006,  # REJECT
            10011,  # ERROR
            10013,  # INVALID
            10014,  # INVALID_VOLUME
            10015,  # INVALID_PRICE
            10016,  # INVALID_STOPS
            10017,  # TRADE_DISABLED
            10019,  # NO_MONEY
        ]
        for code in permanent:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.PERMANENT, (
                f"Code {code} should be PERMANENT, got {classification}"
            )

    def test_unknown_code_classified_as_unknown(self) -> None:
        """Unknown codes should be classified as UNKNOWN."""
        unknown_codes = [99999, 0, -1, 10000]
        for code in unknown_codes:
            classification = MT5Utilities.CircuitBreaker.classify_mt5_retcode(code)
            assert classification == c.Resilience.ErrorClassification.UNKNOWN, (
                f"Code {code} should be UNKNOWN, got {classification}"
            )

    def test_is_retryable_mt5_code(self) -> None:
        """is_retryable_mt5_code should return True only for safe retryable codes."""
        # Safe retryable codes (order NOT executed)
        assert MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10004)  # REQUOTE
        assert MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10020)  # PRICE_CHANGED
        assert MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10021)  # PRICE_OFF

        # CRITICAL: TIMEOUT and CONNECTION are NOT retryable - they are VERIFY_REQUIRED
        # because the order MAY have been executed!
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10012)  # TIMEOUT
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10031)  # CONN

        # Other non-retryable codes
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10006)  # REJECT
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10009)  # DONE
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10010)  # PARTIAL
        assert not MT5Utilities.CircuitBreaker.is_retryable_mt5_code(10007)  # CANCEL

    def test_is_permanent_mt5_code(self) -> None:
        """is_permanent_mt5_code should return True only for permanent codes."""
        # Permanent codes
        assert MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10006)  # REJECT
        assert MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10019)  # NO_MONEY
        assert MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10017)  # DISABLED

        # Non-permanent codes
        assert not MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10004)  # REQUOTE
        assert not MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10009)  # DONE
        assert not MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10010)  # PARTIAL
        assert not MT5Utilities.CircuitBreaker.is_permanent_mt5_code(10007)  # CANCEL


class TestOperationCriticality:
    """Test operation criticality mapping."""

    def test_order_send_is_critical(self) -> None:
        """order_send must be CRITICAL."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "order_send"
        )
        assert criticality == c.Resilience.OperationCriticality.CRITICAL

    def test_order_check_is_critical(self) -> None:
        """order_check must be CRITICAL."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "order_check"
        )
        assert criticality == c.Resilience.OperationCriticality.CRITICAL

    def test_positions_get_is_high(self) -> None:
        """positions_get should be HIGH."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "positions_get"
        )
        assert criticality == c.Resilience.OperationCriticality.HIGH

    def test_account_info_is_high(self) -> None:
        """account_info should be HIGH."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "account_info"
        )
        assert criticality == c.Resilience.OperationCriticality.HIGH

    def test_symbol_info_is_normal(self) -> None:
        """symbol_info should be NORMAL."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "symbol_info"
        )
        assert criticality == c.Resilience.OperationCriticality.NORMAL

    def test_symbols_total_is_low(self) -> None:
        """symbols_total should be LOW."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "symbols_total"
        )
        assert criticality == c.Resilience.OperationCriticality.LOW

    def test_unknown_operation_defaults_to_normal(self) -> None:
        """Unknown operations should default to NORMAL."""
        criticality = MT5Utilities.CircuitBreaker.get_operation_criticality(
            "unknown_op"
        )
        assert criticality == c.Resilience.OperationCriticality.NORMAL


class TestShouldVerifyState:
    """Test should_verify_state logic."""

    def test_should_verify_for_critical_conditional(self) -> None:
        """Should verify state for CRITICAL ops with CONDITIONAL errors."""
        assert MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.CONDITIONAL,
        )

    def test_should_verify_for_critical_unknown(self) -> None:
        """Should verify state for CRITICAL ops with UNKNOWN errors."""
        assert MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.UNKNOWN,
        )

    def test_should_verify_for_critical_verify_required(self) -> None:
        """Should verify state for CRITICAL ops with VERIFY_REQUIRED errors.

        TIMEOUT and CONNECTION errors require verification before retry
        because the order MAY have been executed.
        """
        assert MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.VERIFY_REQUIRED,
        )

    def test_should_not_verify_for_critical_success(self) -> None:
        """Should NOT verify state for SUCCESS (already known)."""
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.SUCCESS,
        )

    def test_should_not_verify_for_critical_permanent(self) -> None:
        """Should NOT verify state for PERMANENT (no point)."""
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.PERMANENT,
        )

    def test_should_not_verify_for_critical_retryable(self) -> None:
        """Should NOT verify state for RETRYABLE (will retry anyway)."""
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "order_send",
            c.Resilience.ErrorClassification.RETRYABLE,
        )

    def test_should_not_verify_for_non_critical_ops(self) -> None:
        """Should NOT verify state for non-CRITICAL operations."""
        # HIGH criticality
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "account_info",
            c.Resilience.ErrorClassification.CONDITIONAL,
        )
        # NORMAL criticality
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "symbol_info",
            c.Resilience.ErrorClassification.CONDITIONAL,
        )
        # LOW criticality
        assert not MT5Utilities.CircuitBreaker.should_verify_state(
            "symbols_total",
            c.Resilience.ErrorClassification.CONDITIONAL,
        )


class TestErrorClassificationEnum:
    """Test ErrorClassification enum values."""

    def test_enum_values(self) -> None:
        """Verify enum values are correctly defined."""
        assert c.Resilience.ErrorClassification.SUCCESS == 0
        assert c.Resilience.ErrorClassification.PARTIAL == 1
        assert c.Resilience.ErrorClassification.RETRYABLE == 2
        assert c.Resilience.ErrorClassification.VERIFY_REQUIRED == 3
        assert c.Resilience.ErrorClassification.CONDITIONAL == 4
        assert c.Resilience.ErrorClassification.PERMANENT == 5
        assert c.Resilience.ErrorClassification.UNKNOWN == 6

    def test_enum_has_all_members(self) -> None:
        """Verify enum has all expected members."""
        members = [
            "SUCCESS",
            "PARTIAL",
            "RETRYABLE",
            "VERIFY_REQUIRED",
            "CONDITIONAL",
            "PERMANENT",
            "UNKNOWN",
        ]
        for member in members:
            assert hasattr(c.Resilience.ErrorClassification, member)


class TestOperationCriticalityEnum:
    """Test OperationCriticality enum values."""

    def test_enum_values(self) -> None:
        """Verify enum values are correctly defined."""
        assert c.Resilience.OperationCriticality.LOW == 0
        assert c.Resilience.OperationCriticality.NORMAL == 1
        assert c.Resilience.OperationCriticality.HIGH == 2
        assert c.Resilience.OperationCriticality.CRITICAL == 3

    def test_enum_has_all_members(self) -> None:
        """Verify enum has all expected members."""
        members = ["LOW", "NORMAL", "HIGH", "CRITICAL"]
        for member in members:
            assert hasattr(c.Resilience.OperationCriticality, member)


class TestRetcodeSetsCompleteness:
    """Test that retcode sets cover all TradeRetcode values."""

    def test_all_trade_retcodes_are_classified(self) -> None:
        """Every TradeRetcode should fall into exactly one classification set."""
        all_codes = set()
        all_codes.update(c.Resilience.MT5_SUCCESS_CODES)
        all_codes.update(c.Resilience.MT5_PARTIAL_CODES)
        all_codes.update(c.Resilience.MT5_VERIFY_REQUIRED_CODES)
        all_codes.update(c.Resilience.MT5_RETRYABLE_CODES)
        all_codes.update(c.Resilience.MT5_CONDITIONAL_CODES)
        all_codes.update(c.Resilience.MT5_PERMANENT_CODES)

        # Get all TradeRetcode values
        trade_retcodes = {member.value for member in c.Order.TradeRetcode}

        # All retcodes should be classified
        for code in trade_retcodes:
            assert code in all_codes, f"TradeRetcode {code} is not classified"

    def test_sets_are_disjoint(self) -> None:
        """Classification sets should not overlap."""
        sets = [
            c.Resilience.MT5_SUCCESS_CODES,
            c.Resilience.MT5_PARTIAL_CODES,
            c.Resilience.MT5_VERIFY_REQUIRED_CODES,
            c.Resilience.MT5_RETRYABLE_CODES,
            c.Resilience.MT5_CONDITIONAL_CODES,
            c.Resilience.MT5_PERMANENT_CODES,
        ]

        for i, s1 in enumerate(sets):
            for s2 in sets[i + 1 :]:
                intersection = s1 & s2
                assert not intersection, f"Sets overlap with codes: {intersection}"

    def test_timeout_and_connection_not_in_retryable(self) -> None:
        """CRITICAL: TIMEOUT and CONNECTION must NOT be in retryable codes.

        These codes were moved to VERIFY_REQUIRED because blind retry
        could cause double execution with serious financial consequences.
        """
        assert 10012 not in c.Resilience.MT5_RETRYABLE_CODES, (
            "TIMEOUT (10012) must NOT be in RETRYABLE - use VERIFY_REQUIRED"
        )
        assert 10031 not in c.Resilience.MT5_RETRYABLE_CODES, (
            "CONNECTION (10031) must NOT be in RETRYABLE - use VERIFY_REQUIRED"
        )

    def test_timeout_and_connection_in_verify_required(self) -> None:
        """TIMEOUT and CONNECTION must be in VERIFY_REQUIRED codes."""
        assert 10012 in c.Resilience.MT5_VERIFY_REQUIRED_CODES, (
            "TIMEOUT (10012) must be in VERIFY_REQUIRED"
        )
        assert 10031 in c.Resilience.MT5_VERIFY_REQUIRED_CODES, (
            "CONNECTION (10031) must be in VERIFY_REQUIRED"
        )
