"""Narrow independent output path for a failed operation-result serializer."""

from __future__ import annotations

import json

from .result_contracts import (
    VERIFIER_TOOL_RESULT_CONTRACT,
    VERIFY_BUNDLE_OPERATION,
    VerifierToolResult,
)
from .verifier_capabilities import TimestampDigitProfileDeclaration, VerifierCapabilityRequest
from .verifier_snapshot import OperationalCode, OperationalInputFailure, OperationalPhase
from .verifier_invocation_facts import EstablishedOperationalFailure, VerifierInvocationFacts


def recovery_failure(code: OperationalCode, phase: OperationalPhase) -> OperationalInputFailure:
    """Build only a minimal recovery failure without the normal initializer.

    A failed OperationalInputFailure constructor establishes no typed outcome.
    Retrying it can fail persistently. This bounded path sets only internal /
    resource / output-transport facts already established by the boundary.
    """
    if code not in {OperationalCode.INTERNAL_OPERATION_ERROR,
                    OperationalCode.RESOURCE_EXHAUSTED, OperationalCode.OUTPUT_IO_ERROR}:
        raise ValueError("not a recovery code")
    failure = RuntimeError.__new__(OperationalInputFailure)
    for name, value in (("operational_code", code), ("phase", phase),
                        ("input_ref", None), ("limit", None), ("detail", None)):
        object.__setattr__(failure, name, value)
    RuntimeError.__init__(failure, code.value)
    return failure


def _capability_value(request: VerifierCapabilityRequest) -> dict:
    """Copy the small validated capability declaration without result projection."""

    v1 = request.v1
    legacy: dict = {"capability": v1.capability}
    if v1.integer_conversion is not None:
        legacy["integer_conversion"] = {
            "mode": v1.integer_conversion.mode,
            "maximum_decimal_digits": v1.integer_conversion.maximum_decimal_digits,
        }
    timestamp_profile = v1.timestamp_digit_profile
    if type(timestamp_profile) is TimestampDigitProfileDeclaration:
        legacy["timestamp_digit_profile"] = {
            "profile_id": timestamp_profile.profile_id,
            "range_file_sha256": timestamp_profile.range_file_sha256,
            "unicode_version": timestamp_profile.unicode_version,
        }
    elif timestamp_profile is not None:
        legacy["timestamp_digit_profile"] = timestamp_profile
    if v1.timestamp_final_lf is not None:
        legacy["timestamp_final_lf"] = v1.timestamp_final_lf
    return {
        "dispatch": request.dispatch.dispatch,
        "v1": legacy,
        "v2": {"capability": request.v2.capability},
        "signature_verification": {"profile": request.signature_verification.profile},
    }


def _limits_value(limits) -> dict:
    return {
        "max_file_bytes": limits.max_file_bytes,
        "max_total_snapshot_bytes": limits.max_total_snapshot_bytes,
        "max_structural_depth": limits.max_structural_depth,
        "max_value_occurrences": limits.max_value_occurrences,
    }


def _limit_value(fact) -> dict | None:
    if fact is None:
        return None
    return {
        "name": fact.name.value,
        "unit": fact.unit.value,
        "maximum": fact.maximum,
        "observed_at_least": fact.observed_at_least,
    }


def serialize_emergency_operation_failure(
    result: VerifierToolResult,
    *,
    output_failure: OperationalInputFailure | None = None,
    invocation_facts: VerifierInvocationFacts | None = None,
    established_failure: EstablishedOperationalFailure | None = ...,
) -> bytes:
    """Frame one closed failure without calling the normal result serializer.

    The shape contains only fixed ASCII names, validated ASCII capability
    identifiers, portable integers, and nulls. Sorted compact JSON therefore
    has exactly the same bytes as RFC 8785 for this narrow output. Neither
    ``to_json_value`` nor the regular canonical serializer is invoked.
    """

    if type(result) is not VerifierToolResult:
        raise TypeError("result must be VerifierToolResult")
    if output_failure is not None and type(output_failure) is not OperationalInputFailure:
        raise TypeError("output_failure must be OperationalInputFailure")
    if established_failure is not ...:
        # The CLI supplies the decision established before the builder, even
        # when that decision is "no operational failure yet". Rejected or
        # subsequently mutated result fields cannot supply a replacement.
        failure = established_failure.restore() if established_failure is not None else (
            output_failure or recovery_failure(OperationalCode.INTERNAL_OPERATION_ERROR, OperationalPhase.OUTPUT)
        )
    elif result.operational_result is not None:
        # The operation already selected a controlling typed failure. A later
        # serializer defect does not replace its code, phase, role, or limit.
        failure = result.operational_result.failure
    else:
        failure = output_failure or recovery_failure(
            OperationalCode.INTERNAL_OPERATION_ERROR,
            OperationalPhase.OUTPUT,
        )

    # Compatibility for direct callers with an already authenticated result.
    # Production CLI emission always supplies the earlier invocation reference.
    facts = invocation_facts or result

    value = {
        "contract": VERIFIER_TOOL_RESULT_CONTRACT,
        "operation": VERIFY_BUNDLE_OPERATION,
        "outcome": "OPERATIONAL_OUTCOME",
        "rc": 3,
        "input_mode": facts.input_mode.value,
        "capability": {
            "requested": _capability_value(facts.requested_capability),
            "effective": (
                _capability_value(facts.effective_capability)
                if facts.effective_capability is not None
                else None
            ),
        },
        "limits": {
            "claimed_envelope": facts.limits.claimed_envelope,
            "advertised": _limits_value(facts.limits.advertised),
            "effective": _limits_value(facts.limits.effective),
        },
        "verification_result": None,
        "operational_result": {
            "operational_code": failure.operational_code.value,
            "phase": failure.phase.value,
            "input_ref": failure.input_ref.value if failure.input_ref is not None else None,
            "limit": _limit_value(failure.limit),
            "detail": None,
        },
    }
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("ascii")
