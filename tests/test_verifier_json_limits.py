"""Operational structural-depth and value-occurrence limit tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

import engine.ai_verify as ai_verify_runtime
from engine.ai_verify import verify_ai_bundle, verify_ai_snapshot
from engine.verifier_json_limits import (
    JsonTraversalLimitExceeded,
    enforce_json_traversal_limits,
    scan_json_limits,
)
from engine.verifier_snapshot import (
    InputRef,
    ImmutableBytesInputs,
    LimitName,
    LimitUnit,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
    acquire_immutable_bytes_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE2_FIXTURES = ROOT / "conformance" / "verifier_contract_phase2" / "fixtures"
OPERATIONAL_CASES = (
    ROOT / "conformance" / "legacy_v1_operational_policy" / "cases.json"
)

CANONICAL = (PHASE2_FIXTURES / "semantic_ai_canonical.json").read_bytes()
MANIFEST = (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes()
KEYRING = (PHASE2_FIXTURES / "semantic_keyring_valid.json").read_bytes()
TRUST = (PHASE2_FIXTURES / "semantic_trust_matching.json").read_bytes()


def _nested_array(depth: int) -> bytes:
    return b"[" * depth + b"null" + b"]" * depth


def _null_array(value_occurrences: int) -> bytes:
    assert value_occurrences >= 1
    if value_occurrences == 1:
        return b"[]"
    return b"[" + b"null," * (value_occurrences - 2) + b"null]"


def _limits(
    *,
    max_structural_depth: int = 1_024,
    max_value_occurrences: int = 65_536,
) -> OperationalLimits:
    return OperationalLimits(
        max_structural_depth=max_structural_depth,
        max_value_occurrences=max_value_occurrences,
    )


def _snapshot(
    *,
    canonical: bytes = CANONICAL,
    manifest: bytes = MANIFEST,
    keyring: bytes | None = None,
    trust: bytes | None = None,
    limits: OperationalLimits,
):
    return acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(canonical, manifest, keyring, trust_store=trust),
        limits=limits,
    )


def _assert_limit_failure(
    failure: OperationalInputFailure,
    *,
    phase: OperationalPhase,
    input_ref: InputRef,
    name: LimitName,
    unit: LimitUnit,
    maximum: int,
    observed_at_least: int,
) -> None:
    assert failure.operational_code is OperationalCode.RESOURCE_LIMIT_EXCEEDED
    assert failure.phase is phase
    assert failure.input_ref is input_ref
    assert failure.detail is None
    assert failure.limit is not None
    assert failure.limit.name is name
    assert failure.limit.unit is unit
    assert failure.limit.maximum == maximum
    assert failure.limit.observed_at_least == observed_at_least


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(3, 3), (4, 4)],
    ids=["maximum-minus-one", "maximum"],
)
def test_small_structural_depth_inclusive_boundary(depth: int, expected: int) -> None:
    result = scan_json_limits(
        _nested_array(depth),
        limits=_limits(max_structural_depth=4),
        allow_legacy_constants=True,
    )

    assert result.source_was_lexically_complete
    assert result.maximum_structural_depth == expected
    assert result.value_occurrences == depth + 1


def test_small_structural_depth_maximum_plus_one() -> None:
    with pytest.raises(JsonTraversalLimitExceeded) as caught:
        scan_json_limits(
            _nested_array(5),
            limits=_limits(max_structural_depth=4),
            allow_legacy_constants=True,
        )

    assert caught.value.name is LimitName.STRUCTURAL_DEPTH
    assert caught.value.unit is LimitUnit.LEVELS
    assert caught.value.maximum == 4
    assert caught.value.observed_at_least == 5


@pytest.mark.parametrize(
    ("occurrences", "expected"),
    [(3, 3), (4, 4)],
    ids=["maximum-minus-one", "maximum"],
)
def test_small_value_occurrence_inclusive_boundary(
    occurrences: int,
    expected: int,
) -> None:
    result = scan_json_limits(
        _null_array(occurrences),
        limits=_limits(max_value_occurrences=4),
        allow_legacy_constants=True,
    )

    assert result.source_was_lexically_complete
    assert result.maximum_structural_depth == 1
    assert result.value_occurrences == expected


def test_small_value_occurrence_maximum_plus_one() -> None:
    with pytest.raises(JsonTraversalLimitExceeded) as caught:
        scan_json_limits(
            _null_array(5),
            limits=_limits(max_value_occurrences=4),
            allow_legacy_constants=True,
        )

    assert caught.value.name is LimitName.VALUE_OCCURRENCES
    assert caught.value.unit is LimitUnit.OCCURRENCES
    assert caught.value.maximum == 4
    assert caught.value.observed_at_least == 5


@pytest.mark.parametrize("depth", [1_023, 1_024])
def test_normative_minimum_depth_boundary_is_inclusive(depth: int) -> None:
    result = scan_json_limits(
        _nested_array(depth),
        limits=OperationalLimits(),
        allow_legacy_constants=True,
    )

    assert result.source_was_lexically_complete
    assert result.maximum_structural_depth == depth


def test_normative_minimum_depth_maximum_plus_one() -> None:
    with pytest.raises(JsonTraversalLimitExceeded) as caught:
        scan_json_limits(
            _nested_array(1_025),
            limits=OperationalLimits(),
            allow_legacy_constants=True,
        )

    assert caught.value.name is LimitName.STRUCTURAL_DEPTH
    assert caught.value.maximum == 1_024
    assert caught.value.observed_at_least == 1_025


@pytest.mark.parametrize("occurrences", [65_535, 65_536])
def test_normative_minimum_occurrence_boundary_is_inclusive(
    occurrences: int,
) -> None:
    result = scan_json_limits(
        _null_array(occurrences),
        limits=OperationalLimits(
            max_file_bytes=524_288,
            max_total_snapshot_bytes=524_288,
        ),
        allow_legacy_constants=True,
    )

    assert result.source_was_lexically_complete
    assert result.value_occurrences == occurrences


def test_normative_minimum_occurrence_maximum_plus_one() -> None:
    with pytest.raises(JsonTraversalLimitExceeded) as caught:
        scan_json_limits(
            _null_array(65_537),
            limits=OperationalLimits(
                max_file_bytes=524_288,
                max_total_snapshot_bytes=524_288,
            ),
            allow_legacy_constants=True,
        )

    assert caught.value.name is LimitName.VALUE_OCCURRENCES
    assert caught.value.maximum == 65_536
    assert caught.value.observed_at_least == 65_537


def test_duplicate_decoded_names_do_not_collapse_source_occurrences() -> None:
    source = b'{"a":0,"\\u0061":1}'
    assert json.loads(source) == {"a": 1}

    result = scan_json_limits(
        source,
        limits=_limits(max_value_occurrences=3),
        allow_legacy_constants=True,
    )
    assert result.value_occurrences == 3

    with pytest.raises(JsonTraversalLimitExceeded) as caught:
        scan_json_limits(
            source,
            limits=_limits(max_value_occurrences=2),
            allow_legacy_constants=True,
        )
    assert caught.value.name is LimitName.VALUE_OCCURRENCES
    assert caught.value.observed_at_least == 3


def test_member_names_are_excluded_from_occurrence_count() -> None:
    result = scan_json_limits(
        b'{"first":null,"second":[true,false]}',
        limits=OperationalLimits(),
        allow_legacy_constants=True,
    )

    assert result.value_occurrences == 5
    assert result.maximum_structural_depth == 2


def test_syntax_before_next_excess_is_left_to_semantic_parser() -> None:
    result = scan_json_limits(
        b"[null,x,[[[]]]]",
        limits=_limits(max_structural_depth=2, max_value_occurrences=2),
        allow_legacy_constants=True,
    )

    assert not result.source_was_lexically_complete
    assert result.maximum_structural_depth == 1
    assert result.value_occurrences == 2


def test_depth_proved_before_later_malformed_content_is_operational() -> None:
    with pytest.raises(OperationalInputFailure) as caught:
        enforce_json_traversal_limits(
            b"[[x",
            limits=_limits(max_structural_depth=1),
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
            allow_legacy_constants=True,
        )

    _assert_limit_failure(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
        name=LimitName.STRUCTURAL_DEPTH,
        unit=LimitUnit.LEVELS,
        maximum=1,
        observed_at_least=2,
    )


def test_occurrence_proved_before_later_malformed_content_is_operational() -> None:
    with pytest.raises(OperationalInputFailure) as caught:
        enforce_json_traversal_limits(
            b"[null,x",
            limits=_limits(max_value_occurrences=1),
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
            allow_legacy_constants=True,
        )

    _assert_limit_failure(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
        name=LimitName.VALUE_OCCURRENCES,
        unit=LimitUnit.OCCURRENCES,
        maximum=1,
        observed_at_least=2,
    )


def test_scanner_depth_is_independent_of_python_recursion_limit() -> None:
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        result = scan_json_limits(
            _nested_array(1_024),
            limits=OperationalLimits(),
            allow_legacy_constants=True,
        )
    finally:
        sys.setrecursionlimit(previous)

    assert result.maximum_structural_depth == 1_024
    assert result.source_was_lexically_complete


def test_deep_snapshot_rejection_is_typed_before_host_json_parser() -> None:
    frozen = _snapshot(
        canonical=_nested_array(1_200),
        limits=OperationalLimits(),
    )

    with mock.patch.object(
        ai_verify_runtime.json,
        "loads",
        side_effect=AssertionError("recursive semantic parser must not be reached"),
    ):
        with pytest.raises(OperationalInputFailure) as caught:
            verify_ai_snapshot(frozen)

    _assert_limit_failure(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
        name=LimitName.STRUCTURAL_DEPTH,
        unit=LimitUnit.LEVELS,
        maximum=1_024,
        observed_at_least=1_025,
    )


def test_snapshot_parser_recursion_is_not_semanticized() -> None:
    frozen = _snapshot(limits=OperationalLimits())

    with mock.patch.object(
        ai_verify_runtime.json,
        "loads",
        side_effect=RecursionError("injected host parser restriction"),
    ):
        with pytest.raises(OperationalInputFailure) as caught:
            verify_ai_snapshot(frozen)

    assert caught.value.operational_code is OperationalCode.RESOURCE_EXHAUSTED
    assert caught.value.phase is OperationalPhase.CANONICAL_PARSE
    assert caught.value.input_ref is InputRef.AI_CANONICAL_JSON
    assert caught.value.limit is None


def _manifest_with_nested_extension() -> bytes:
    value = json.loads(MANIFEST)
    value["extension"] = [[None]]
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


@pytest.mark.parametrize(
    ("role", "phase", "input_ref"),
    [
        (
            "canonical",
            OperationalPhase.CANONICAL_PARSE,
            InputRef.AI_CANONICAL_JSON,
        ),
        (
            "manifest",
            OperationalPhase.MANIFEST_PARSE,
            InputRef.AI_MANIFEST_JSON,
        ),
        (
            "keyring",
            OperationalPhase.SIGNATURE_MATERIAL,
            InputRef.VERIFICATION_KEYS_JSON,
        ),
        ("trust", OperationalPhase.TRUST_INPUT, InputRef.TRUST_STORE),
    ],
)
def test_snapshot_depth_limit_metadata_for_each_reached_source(
    role: str,
    phase: OperationalPhase,
    input_ref: InputRef,
) -> None:
    inputs: dict[str, bytes | None] = {
        "canonical": CANONICAL,
        "manifest": MANIFEST,
        "keyring": None,
        "trust": None,
    }
    inputs[role] = {
        "canonical": _nested_array(3),
        "manifest": _manifest_with_nested_extension(),
        "keyring": KEYRING,
        "trust": TRUST,
    }[role]
    frozen = _snapshot(
        canonical=inputs["canonical"],
        manifest=inputs["manifest"],
        keyring=inputs["keyring"],
        trust=inputs["trust"],
        limits=_limits(max_structural_depth=2),
    )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(frozen)

    _assert_limit_failure(
        caught.value,
        phase=phase,
        input_ref=input_ref,
        name=LimitName.STRUCTURAL_DEPTH,
        unit=LimitUnit.LEVELS,
        maximum=2,
        observed_at_least=3,
    )


@pytest.mark.parametrize(
    ("role", "maximum", "phase", "input_ref"),
    [
        (
            "canonical",
            5,
            OperationalPhase.CANONICAL_PARSE,
            InputRef.AI_CANONICAL_JSON,
        ),
        (
            "manifest",
            6,
            OperationalPhase.MANIFEST_PARSE,
            InputRef.AI_MANIFEST_JSON,
        ),
        (
            "keyring",
            7,
            OperationalPhase.SIGNATURE_MATERIAL,
            InputRef.VERIFICATION_KEYS_JSON,
        ),
        ("trust", 6, OperationalPhase.TRUST_INPUT, InputRef.TRUST_STORE),
    ],
)
def test_snapshot_occurrence_limit_metadata_for_each_reached_source(
    role: str,
    maximum: int,
    phase: OperationalPhase,
    input_ref: InputRef,
) -> None:
    frozen = _snapshot(
        keyring=KEYRING if role == "keyring" else None,
        trust=TRUST if role == "trust" else None,
        limits=_limits(max_value_occurrences=maximum),
    )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(frozen)

    _assert_limit_failure(
        caught.value,
        phase=phase,
        input_ref=input_ref,
        name=LimitName.VALUE_OCCURRENCES,
        unit=LimitUnit.OCCURRENCES,
        maximum=maximum,
        observed_at_least=maximum + 1,
    )


def test_canonical_semantic_failure_precedes_unreached_manifest_limit() -> None:
    frozen = _snapshot(
        canonical=b"not-json",
        manifest=_nested_array(3),
        limits=_limits(max_structural_depth=2),
    )

    result = verify_ai_snapshot(frozen)

    assert not result.valid
    assert result.reason == "CANONICAL_NOT_JSON"


def test_malformed_trust_before_any_limit_remains_semantic() -> None:
    frozen = _snapshot(
        trust=b"x[[[",
        limits=_limits(max_structural_depth=2),
    )

    result = verify_ai_snapshot(frozen)

    assert not result.valid
    assert result.reason == "TRUST_STORE_INVALID"


def test_trust_limit_proved_before_later_malformed_content_is_operational() -> None:
    frozen = _snapshot(
        trust=b"[[[x",
        limits=_limits(max_structural_depth=2),
    )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(frozen)

    _assert_limit_failure(
        caught.value,
        phase=OperationalPhase.TRUST_INPUT,
        input_ref=InputRef.TRUST_STORE,
        name=LimitName.STRUCTURAL_DEPTH,
        unit=LimitUnit.LEVELS,
        maximum=2,
        observed_at_least=3,
    )


def test_absent_required_trust_retains_existing_semantic_boundary() -> None:
    from engine.ai_verify import AIVerificationOptions

    frozen = _snapshot(limits=OperationalLimits())
    result = verify_ai_snapshot(
        frozen,
        options=AIVerificationOptions(require_trusted_signer=True),
    )

    assert not result.valid
    assert result.reason == "TRUST_INPUT_NOT_PROVIDED"


def test_legacy_direct_api_does_not_apply_snapshot_traversal_limits(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "ai_canonical.json").write_bytes(CANONICAL)
    (bundle / "ai_manifest.json").write_bytes(MANIFEST)

    with mock.patch.object(
        ai_verify_runtime,
        "enforce_json_traversal_limits",
        side_effect=AssertionError("snapshot-only scanner must not run"),
    ):
        result = verify_ai_bundle(bundle)

    assert result.valid


@pytest.mark.parametrize(
    ("case_id", "source"),
    [
        ("limit.structural_depth.above", _nested_array(1_025)),
        ("limit.value_occurrences.above", _null_array(65_537)),
    ],
)
def test_operational_failure_matches_frozen_policy_case(
    case_id: str,
    source: bytes,
) -> None:
    corpus = json.loads(OPERATIONAL_CASES.read_text(encoding="utf-8"))
    case = next(vector for vector in corpus["vectors"] if vector["case_id"] == case_id)
    configured = case["configuration"]["limits"]["effective"]
    limits = OperationalLimits(**configured)

    with pytest.raises(OperationalInputFailure) as caught:
        enforce_json_traversal_limits(
            source,
            limits=limits,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
            allow_legacy_constants=True,
        )

    expected = case["expected"]["tool_result"]["operational_result"]
    actual = {
        "operational_code": caught.value.operational_code.value,
        "phase": caught.value.phase.value,
        "input_ref": caught.value.input_ref.value,
        "limit": {
            "name": caught.value.limit.name.value,
            "unit": caught.value.limit.unit.value,
            "maximum": caught.value.limit.maximum,
            "observed_at_least": caught.value.limit.observed_at_least,
        },
        "detail": caught.value.detail,
    }
    assert actual == expected
