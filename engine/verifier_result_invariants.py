"""Normative relationships and operation binding for normal output frames.

This validator complements Draft-7. Emergency construction is deliberately
independent of this module and every normal output validation dependency.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from .result_contracts import ResultContractError, VerifierToolResult
from .verifier_invocation_facts import EstablishedOperationalFailure, VerifierInvocationFacts


def validate_verifier_result_invariants(
    value: dict[str, Any],
    *,
    expected_result: VerifierToolResult | None = None,
    process_rc: int | None = None,
    invocation_facts: VerifierInvocationFacts | None = None,
    established_failure: EstablishedOperationalFailure | None = None,
) -> None:
    """Validate normative relationships in an already schema-valid frame.

    Draft-7 establishes closed shapes and supported capability values. This
    complements it with prose invariants and, at the output boundary, binds
    untrusted serializer output to the operation that actually ran. Emergency
    construction must never call this fallible normal-output validator.
    """

    def require(condition: bool) -> None:
        if not condition:
            raise ResultContractError("VERIFIER_TOOL_RESULT_INVARIANT_INVALID")

    def matches_frozen(actual: Any, frozen: Any) -> bool:
        # Compare the projected JSON with immutable semantic data without
        # invoking the projection that produced the untrusted value.
        work = [(actual, frozen)]
        while work:
            member, original = work.pop()
            if isinstance(original, Mapping):
                if type(member) is not dict or member.keys() != original.keys():
                    return False
                work.extend((member[k], v) for k, v in original.items())
            elif type(original) is tuple:
                if type(member) is not list or len(member) != len(original):
                    return False
                work.extend(zip(member, original))
            elif type(member) is not type(original) or member != original:
                return False
        return True

    rc = value["rc"]
    if process_rc is not None:
        require(type(process_rc) is int and rc == process_rc)
    if established_failure is not None:
        require(rc == 3 and value["outcome"] == "OPERATIONAL_OUTCOME"
                and value["verification_result"] is None)
        fact = established_failure.limit
        require(value["operational_result"] == {
            "operational_code": established_failure.code.value,
            "phase": established_failure.phase.value,
            "input_ref": established_failure.input_ref.value if established_failure.input_ref is not None else None,
            "limit": None if fact is None else {
                "name": fact[0].value, "unit": fact[1].value,
                "maximum": fact[2], "observed_at_least": fact[3],
            },
            "detail": None,
        })
    if expected_result is not None:
        require(rc == expected_result.rc)
        metadata = invocation_facts or expected_result
        # Bind metadata directly to immutable primitives, independently of
        # normal projection functions (which are themselves untrusted).
        for name, declaration in (("requested", metadata.requested_capability),
                                  ("effective", metadata.effective_capability)):
            expected = None
            if declaration is not None:
                expected = asdict(declaration)
                expected["dispatch"] = declaration.dispatch.dispatch
                expected["v1"] = {k: v for k, v in expected["v1"].items() if v is not None}
            require(value["capability"][name] == expected)
        require(value["limits"] == asdict(metadata.limits))
        require(value["input_mode"] == metadata.input_mode.value)
        require(value["outcome"] == expected_result.outcome)
        require(matches_frozen(value["verification_result"], expected_result.verification_result))
        failure = expected_result.operational_result
        expected_failure = None
        if failure is not None:
            expected_failure = asdict(failure.failure)
            expected_failure["detail"] = None
        require(value["operational_result"] == expected_failure)

    requested = value["capability"]["requested"]
    effective = value["capability"]["effective"]
    failure = value["operational_result"]
    verification = value["verification_result"]
    limits = value["limits"]
    require(all(v <= limits["advertised"][k] for k, v in limits["effective"].items()))
    if verification is not None:
        require(failure is None and value["outcome"] == "SEMANTIC_RESULT")
        require(rc == verification["rc"] == (0 if verification["status"] == "VALID" else 2))
        require(effective is not None and effective == requested)
        return

    require(failure is not None and value["outcome"] == "OPERATIONAL_OUTCOME" and rc == 3)
    code, phase, ref, fact = (failure[k] for k in ("operational_code", "phase", "input_ref", "limit"))
    if code == "CAPABILITY_PROFILE_UNAVAILABLE":
        require(effective is None)
    elif effective is None:
        require(code in {"INTERNAL_OPERATION_ERROR", "RESOURCE_EXHAUSTED"}
                and phase in {"CAPABILITY_SELECTION", "OUTPUT"})
    else:
        require(effective == requested and phase != "CAPABILITY_SELECTION")

    if phase in {"CAPABILITY_SELECTION", "OUTPUT"}:
        require(ref is None and fact is None)
    role_phases = {
        "TRUST_INPUT": {"TRUST_STORE"},
        "BUNDLE_SNAPSHOT": {"BUNDLE_DIRECTORY", "AI_CANONICAL_JSON", "AI_MANIFEST_JSON", "VERIFICATION_KEYS_JSON"},
        "DISPATCH": {"AI_MANIFEST_JSON"},
        "CANONICAL_PARSE": {"AI_CANONICAL_JSON"},
        "MANIFEST_PARSE": {"AI_MANIFEST_JSON"},
        "SIGNATURE_MATERIAL": {"VERIFICATION_KEYS_JSON", "AI_MANIFEST_JSON"},
    }
    if ref is not None and phase in role_phases:
        require(ref in role_phases[phase])
    if code in {"INPUT_IO_ERROR", "INPUT_NOT_REGULAR_FILE", "INPUT_CHANGED_DURING_SNAPSHOT"}:
        require(phase in {"TRUST_INPUT", "BUNDLE_SNAPSHOT"} and ref is not None and fact is None)
    if code == "OUTPUT_IO_ERROR":
        require(phase == "OUTPUT")
    if code == "CAPABILITY_PROFILE_UNAVAILABLE":
        require((phase == "CAPABILITY_SELECTION" and ref is None)
                or (phase == "DISPATCH" and ref == "AI_MANIFEST_JSON"
                    and requested["v1"]["capability"] == "V1_LEGACY_UNSUPPORTED"))
    if code == "RESOURCE_LIMIT_EXCEEDED":
        require(fact is not None and ref is not None)
        fields = {"FILE_BYTES": "max_file_bytes", "TOTAL_SNAPSHOT_BYTES": "max_total_snapshot_bytes",
                  "STRUCTURAL_DEPTH": "max_structural_depth", "VALUE_OCCURRENCES": "max_value_occurrences"}
        require(fact["name"] in fields)
        require(fact["maximum"] == limits["effective"][fields[fact["name"]]])
        require(fact["observed_at_least"] > fact["maximum"])
        if fact["name"] in {"FILE_BYTES", "TOTAL_SNAPSHOT_BYTES"}:
            require(phase in {"TRUST_INPUT", "BUNDLE_SNAPSHOT"})
            require(ref == "BUNDLE_DIRECTORY" if fact["name"] == "TOTAL_SNAPSHOT_BYTES"
                    else ref not in {"BUNDLE_DIRECTORY", "EXPLICIT_INPUT"})
        else:
            require(phase in {"TRUST_INPUT", "DISPATCH", "CANONICAL_PARSE", "MANIFEST_PARSE", "SIGNATURE_MATERIAL"})
    if code == "INPUT_OUTSIDE_DECLARED_CAPABILITY":
        require(phase in {"TRUST_INPUT", "CANONICAL_PARSE", "MANIFEST_PARSE", "SIGNATURE_MATERIAL"}
                and ref is not None and effective is not None)
        v1 = effective["v1"]
        # V2-only configurations use the specified frozen legacy auxiliary route.
        auxiliary = v1["capability"] == "V1_LEGACY_UNSUPPORTED"
        if fact is None:
            require(v1["capability"] == "V1_RESTRICTED_PORTABLE")
        elif fact["name"] == "INTEGER_DECIMAL_DIGITS":
            maximum = 640 if auxiliary else v1["integer_conversion"]["maximum_decimal_digits"]
            require(type(maximum) is int and fact["maximum"] == maximum
                    and type(fact["observed_at_least"]) is int and fact["observed_at_least"] > maximum)
        elif fact["name"] == "TIMESTAMP_DIGIT_PROFILE":
            profile = "ASCII" if auxiliary else v1["timestamp_digit_profile"]
            require(fact["maximum"] == (profile if type(profile) is str else profile["profile_id"]))
            require(type(fact["observed_at_least"]) is str
                    and re.fullmatch(r"U\+[0-9A-F]{4,6}", fact["observed_at_least"]) is not None)
        else:
            require(False)
