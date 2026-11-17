import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError

from engine import freshness as freshness_module
from engine.freshness import (
    FRESHNESS_POLICY_INVALID,
    FRESHNESS_STALE,
    FRESHNESS_TIMESTAMP_IN_FUTURE,
    FRESHNESS_TIMESTAMP_MALFORMED,
    FreshnessError,
    FreshnessOutcome,
    FreshnessResult,
    evaluate_freshness,
)


_EVIDENCE = "2026-08-22T10:00:00Z"
_REFERENCE = "2026-08-22T10:01:00Z"

_MALFORMED_TIMESTAMPS = (
    "2026-99-99T99:99:99Z",
    "0000-00-00T00:00:00Z",
    "2026-08-22T10:00:00+00:00",
    "2026-08-22t10:00:00z",
    "2026-08-22T10:00:00.000Z",
    "٢٠٢٦-٠٨-٢٢T١٠:٠٠:٠٠Z",
    "2026-08-22T10:00:00Z\n",
    "2026-08-22T10:00:00Z ",
    "",
)


def _assert_freshness_error(
    test_case: unittest.TestCase,
    expected_reason: str,
    **kwargs,
) -> FreshnessError:
    with test_case.assertRaises(FreshnessError) as context:
        evaluate_freshness(**kwargs)
    test_case.assertEqual(context.exception.reason, expected_reason)
    return context.exception


class TestFreshnessBoundaries(unittest.TestCase):
    def test_age_exactly_zero_is_valid(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_EVIDENCE,
            maximum_age_seconds=60,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.VALID)
        self.assertIsNone(result.reason)
        self.assertEqual(result.age_seconds, 0)

    def test_age_exactly_equal_to_maximum_is_valid(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.VALID)
        self.assertIsNone(result.reason)
        self.assertEqual(result.age_seconds, 60)

    def test_age_one_second_above_maximum_is_stale(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-08-22T10:01:01Z",
            maximum_age_seconds=60,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.STALE)
        self.assertEqual(result.reason, FRESHNESS_STALE)
        self.assertEqual(result.age_seconds, 61)

    def test_evidence_one_second_in_future_is_future(self):
        result = evaluate_freshness(
            evidence_timestamp="2026-08-22T10:00:01Z",
            reference_timestamp=_EVIDENCE,
            maximum_age_seconds=60,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.FUTURE)
        self.assertEqual(result.reason, FRESHNESS_TIMESTAMP_IN_FUTURE)
        self.assertEqual(result.age_seconds, -1)

    def test_maximum_age_zero_accepts_equal_timestamps(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_EVIDENCE,
            maximum_age_seconds=0,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.VALID)

    def test_maximum_age_zero_rejects_one_second_older_as_stale(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-08-22T10:00:01Z",
            maximum_age_seconds=0,
        )
        self.assertEqual(result.outcome, FreshnessOutcome.STALE)
        self.assertEqual(result.reason, FRESHNESS_STALE)
        self.assertEqual(result.age_seconds, 1)


class TestFreshnessDeterminism(unittest.TestCase):
    def test_repeated_evaluation_is_deterministic(self):
        arguments = {
            "evidence_timestamp": _EVIDENCE,
            "reference_timestamp": _REFERENCE,
            "maximum_age_seconds": 60,
        }
        first = evaluate_freshness(**arguments)
        second = evaluate_freshness(**arguments)
        self.assertEqual(first, second)

    def test_changing_only_reference_time_changes_boundary_result(self):
        valid = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        stale = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-08-22T10:01:01Z",
            maximum_age_seconds=60,
        )
        self.assertEqual(valid.outcome, FreshnessOutcome.VALID)
        self.assertEqual(stale.outcome, FreshnessOutcome.STALE)

    def test_changing_only_maximum_age_changes_boundary_result(self):
        stale = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-08-22T10:01:01Z",
            maximum_age_seconds=60,
        )
        valid = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-08-22T10:01:01Z",
            maximum_age_seconds=61,
        )
        self.assertEqual(stale.outcome, FreshnessOutcome.STALE)
        self.assertEqual(valid.outcome, FreshnessOutcome.VALID)

    def test_result_preserves_exact_inputs(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        self.assertEqual(result.evidence_timestamp, _EVIDENCE)
        self.assertEqual(result.reference_timestamp, _REFERENCE)
        self.assertEqual(result.maximum_age_seconds, 60)


class TestTimestampValidation(unittest.TestCase):
    def test_malformed_evidence_timestamp_matrix(self):
        for malformed in _MALFORMED_TIMESTAMPS:
            with self.subTest(timestamp=repr(malformed)):
                error = _assert_freshness_error(
                    self,
                    FRESHNESS_TIMESTAMP_MALFORMED,
                    evidence_timestamp=malformed,
                    reference_timestamp=_REFERENCE,
                    maximum_age_seconds=60,
                )
                self.assertIn("evidence_timestamp", error.detail)

    def test_malformed_reference_timestamp_matrix(self):
        for malformed in _MALFORMED_TIMESTAMPS:
            with self.subTest(timestamp=repr(malformed)):
                error = _assert_freshness_error(
                    self,
                    FRESHNESS_POLICY_INVALID,
                    evidence_timestamp=_EVIDENCE,
                    reference_timestamp=malformed,
                    maximum_age_seconds=60,
                )
                self.assertIn("reference_timestamp", error.detail)

    def test_impossible_calendar_evidence_timestamp_is_malformed(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-02-29T10:00:00Z",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_impossible_calendar_reference_timestamp_is_policy_invalid(self):
        _assert_freshness_error(
            self,
            FRESHNESS_POLICY_INVALID,
            evidence_timestamp=_EVIDENCE,
            reference_timestamp="2026-02-29T10:00:00Z",
            maximum_age_seconds=60,
        )

    def test_unicode_decimal_digits_are_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="٢٠٢٦-٠٨-٢٢T١٠:٠٠:٠٠Z",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_terminal_newline_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-08-22T10:00:00Z\n",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_fractional_seconds_are_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-08-22T10:00:00.000Z",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_utc_offset_form_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-08-22T10:00:00+00:00",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_lowercase_t_and_z_are_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-08-22t10:00:00z",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_empty_timestamp_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )

    def test_non_string_evidence_timestamps_are_malformed(self):
        values = (None, 0, b"2026-08-22T10:00:00Z", [], object())
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                _assert_freshness_error(
                    self,
                    FRESHNESS_TIMESTAMP_MALFORMED,
                    evidence_timestamp=value,
                    reference_timestamp=_REFERENCE,
                    maximum_age_seconds=60,
                )

    def test_non_string_reference_timestamps_are_policy_invalid(self):
        values = (None, 0, b"2026-08-22T10:00:00Z", [], object())
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                _assert_freshness_error(
                    self,
                    FRESHNESS_POLICY_INVALID,
                    evidence_timestamp=_EVIDENCE,
                    reference_timestamp=value,
                    maximum_age_seconds=60,
                )

    def test_leap_second_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="2026-08-22T10:00:60Z",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )


class TestMaximumAgeValidation(unittest.TestCase):
    def test_negative_maximum_age_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_POLICY_INVALID,
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=-1,
        )

    def test_bool_maximum_age_is_rejected(self):
        for value in (False, True):
            with self.subTest(value=value):
                _assert_freshness_error(
                    self,
                    FRESHNESS_POLICY_INVALID,
                    evidence_timestamp=_EVIDENCE,
                    reference_timestamp=_REFERENCE,
                    maximum_age_seconds=value,
                )

    def test_float_maximum_age_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_POLICY_INVALID,
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60.0,
        )

    def test_string_maximum_age_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_POLICY_INVALID,
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds="60",
        )

    def test_none_maximum_age_is_rejected(self):
        _assert_freshness_error(
            self,
            FRESHNESS_POLICY_INVALID,
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=None,
        )

    def test_other_maximum_age_types_are_rejected(self):
        class IntegerSubclass(int):
            pass

        values = ([], {}, object(), IntegerSubclass(60))
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                _assert_freshness_error(
                    self,
                    FRESHNESS_POLICY_INVALID,
                    evidence_timestamp=_EVIDENCE,
                    reference_timestamp=_REFERENCE,
                    maximum_age_seconds=value,
                )


class TestFreshnessResultContract(unittest.TestCase):
    def test_result_is_frozen(self):
        result = evaluate_freshness(
            evidence_timestamp=_EVIDENCE,
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        self.assertIsInstance(result, FreshnessResult)
        with self.assertRaises(FrozenInstanceError):
            result.age_seconds = 61

    def test_outcome_vocabulary_is_closed(self):
        self.assertEqual(
            {outcome.value for outcome in FreshnessOutcome},
            {"VALID", "FUTURE", "STALE"},
        )

    def test_error_is_value_error_with_stable_reason(self):
        first = _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="bad",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        second = _assert_freshness_error(
            self,
            FRESHNESS_TIMESTAMP_MALFORMED,
            evidence_timestamp="bad",
            reference_timestamp=_REFERENCE,
            maximum_age_seconds=60,
        )
        self.assertIsInstance(first, ValueError)
        self.assertEqual(first.reason, second.reason)


class TestNoAmbientClock(unittest.TestCase):
    def test_primitive_contains_no_system_clock_call(self):
        source = inspect.getsource(freshness_module)
        tree = ast.parse(source)
        forbidden_calls = {
            "now",
            "utcnow",
            "today",
            "time",
            "time_ns",
            "monotonic",
            "monotonic_ns",
            "perf_counter",
            "perf_counter_ns",
            "process_time",
            "process_time_ns",
        }
        observed_calls = []
        time_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    observed_calls.append(node.func.id)
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in forbidden_calls
                ):
                    observed_calls.append(node.func.attr)
            elif isinstance(node, ast.Import):
                time_imports.extend(
                    alias.name for alias in node.names if alias.name == "time"
                )
            elif isinstance(node, ast.ImportFrom) and node.module == "time":
                time_imports.append(node.module)

        self.assertEqual(observed_calls, [])
        self.assertEqual(time_imports, [])

        parameters = inspect.signature(evaluate_freshness).parameters.values()
        self.assertTrue(parameters)
        self.assertTrue(
            all(parameter.default is inspect.Parameter.empty for parameter in parameters)
        )


if __name__ == "__main__":
    unittest.main()
