"""Deterministic declared-time freshness primitive (P1.3b).

This module evaluates only whether a declared evidence timestamp lies inside
an explicit caller-supplied recency window. Both timestamps must be strict UTC
whole-second strings, and the maximum age must be an explicit non-negative
integer. No system clock, ambient state, bundle I/O, network access, provider
timestamp, manifest timestamp, signature, trust, or authorization input is
consulted.

A valid freshness result does not establish historical occurrence, trusted
time, historical non-modification, provider receipt or execution, response
causation, trusted provider identity, authorization, legal or regulatory
compliance, or semantic truth or correctness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


FRESHNESS_POLICY_INVALID = "FRESHNESS_POLICY_INVALID"
FRESHNESS_TIMESTAMP_MALFORMED = "FRESHNESS_TIMESTAMP_MALFORMED"
FRESHNESS_TIMESTAMP_IN_FUTURE = "FRESHNESS_TIMESTAMP_IN_FUTURE"
FRESHNESS_STALE = "FRESHNESS_STALE"

_UTC_TIMESTAMP_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})-"
    r"(?P<month>[0-9]{2})-"
    r"(?P<day>[0-9]{2})T"
    r"(?P<hour>[0-9]{2}):"
    r"(?P<minute>[0-9]{2}):"
    r"(?P<second>[0-9]{2})Z"
)


class FreshnessError(ValueError):
    """Raised when freshness input cannot be evaluated.

    ``reason`` is one of the stable, machine-readable malformed-input reason
    codes. ``detail`` is human-readable and non-normative; callers must not
    pattern-match it.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


class FreshnessOutcome(str, Enum):
    """Closed vocabulary for an evaluated recency window."""

    VALID = "VALID"
    FUTURE = "FUTURE"
    STALE = "STALE"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class FreshnessResult:
    """Immutable result of evaluating fully validated freshness inputs."""

    evidence_timestamp: str
    reference_timestamp: str
    maximum_age_seconds: int
    age_seconds: int
    outcome: FreshnessOutcome
    reason: str | None


def _parse_utc_timestamp(
    value: Any,
    field_name: str,
    error_reason: str,
) -> datetime:
    if not isinstance(value, str):
        raise FreshnessError(
            error_reason,
            f"{field_name} must be a string in YYYY-MM-DDTHH:MM:SSZ format",
        )

    match = _UTC_TIMESTAMP_PATTERN.fullmatch(value)
    if match is None:
        raise FreshnessError(
            error_reason,
            f"{field_name} must use exact YYYY-MM-DDTHH:MM:SSZ format",
        )

    try:
        return datetime(
            year=int(match.group("year")),
            month=int(match.group("month")),
            day=int(match.group("day")),
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            second=int(match.group("second")),
            tzinfo=timezone.utc,
        )
    except ValueError as exc:
        raise FreshnessError(
            error_reason,
            f"{field_name} is not a calendar-valid UTC instant",
        ) from exc


def _validate_maximum_age(maximum_age_seconds: Any) -> int:
    if type(maximum_age_seconds) is not int or maximum_age_seconds < 0:
        raise FreshnessError(
            FRESHNESS_POLICY_INVALID,
            "maximum_age_seconds must be a non-negative Python int",
        )
    return maximum_age_seconds


def evaluate_freshness(
    *,
    evidence_timestamp: Any,
    reference_timestamp: Any,
    maximum_age_seconds: Any,
) -> FreshnessResult:
    """Evaluate declared-time recency using only explicit caller inputs.

    Timestamps are accepted only in exact ``YYYY-MM-DDTHH:MM:SSZ`` form.
    ``maximum_age_seconds`` must be a non-negative built-in ``int`` (not
    ``bool``). No coercion, trimming, normalization, or implicit current time
    is used.

    The computed age is ``reference_timestamp - evidence_timestamp`` in whole
    seconds. Zero and ``maximum_age_seconds`` are both inclusive valid
    boundaries. A negative age is ``FUTURE``; an age above the maximum is
    ``STALE``.
    """

    maximum_age = _validate_maximum_age(maximum_age_seconds)
    evidence_time = _parse_utc_timestamp(
        evidence_timestamp,
        "evidence_timestamp",
        FRESHNESS_TIMESTAMP_MALFORMED,
    )
    reference_time = _parse_utc_timestamp(
        reference_timestamp,
        "reference_timestamp",
        FRESHNESS_POLICY_INVALID,
    )

    delta = reference_time - evidence_time
    age_seconds = delta.days * 86_400 + delta.seconds

    if age_seconds < 0:
        outcome = FreshnessOutcome.FUTURE
        reason = FRESHNESS_TIMESTAMP_IN_FUTURE
    elif age_seconds > maximum_age:
        outcome = FreshnessOutcome.STALE
        reason = FRESHNESS_STALE
    else:
        outcome = FreshnessOutcome.VALID
        reason = None

    return FreshnessResult(
        evidence_timestamp=evidence_timestamp,
        reference_timestamp=reference_timestamp,
        maximum_age_seconds=maximum_age,
        age_seconds=age_seconds,
        outcome=outcome,
        reason=reason,
    )
