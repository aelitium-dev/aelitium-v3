"""Capability-qualified v1 content execution and frozen timestamp profiles."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine.ai_canonical import canonicalize_ai_output
from engine.ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICALIZATION_V2,
    AI_MANIFEST_SCHEMA,
    AI_OUTPUT_SCHEMA_VERSION,
)
from engine.ai_verify import AIVerificationOptions, verify_ai_snapshot
from engine.result_contracts import (
    AELITIUM_CLEANROOM_MINIMUM_1,
    VerifierLimitState,
)
from engine.verifier_capabilities import (
    ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    AELITIUM_DISPATCH_JSON_1,
    ASCII_TIMESTAMP_DIGIT_PROFILE,
    BOUNDED,
    ED25519_PORTABLE_STRICT_1,
    FROZEN_UNICODE_PROFILES,
    UNLIMITED,
    V1_FROZEN_LEGACY_COMPATIBILITY,
    V1_NAMED_RUNTIME_COMPATIBILITY,
    V1_RESTRICTED_PORTABLE,
    V2_PORTABLE,
    DispatchCapabilityDeclaration,
    IntegerConversionDeclaration,
    SignatureVerificationDeclaration,
    TimestampDigitProfileDeclaration,
    V1CapabilityDeclaration,
    V2CapabilityDeclaration,
    VerifierCapabilityRequest,
    prepare_verifier_capabilities,
    select_effective_route,
)
from engine.verifier_operation import verify_bundle_operation
from engine.verifier_snapshot import (
    ImmutableBytesInputs,
    InputRef,
    InputRole,
    LimitName,
    LimitUnit,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
    acquire_immutable_bytes_snapshot,
)
from engine.verifier_v1_capability import (
    LegacyIntegerConversionError,
    LegacyJsonSourceError,
    canonical_json_v1_profile,
    integer_to_decimal,
    parse_v1_json_source,
    validate_v1_manifest_timestamp,
)


_ROLE_BOUNDARIES = {
    InputRole.AI_CANONICAL_JSON: (
        OperationalPhase.CANONICAL_PARSE,
        InputRef.AI_CANONICAL_JSON,
    ),
    InputRole.AI_MANIFEST_JSON: (
        OperationalPhase.MANIFEST_PARSE,
        InputRef.AI_MANIFEST_JSON,
    ),
    InputRole.VERIFICATION_KEYS_JSON: (
        OperationalPhase.SIGNATURE_MATERIAL,
        InputRef.VERIFICATION_KEYS_JSON,
    ),
    InputRole.TRUST_STORE: (
        OperationalPhase.TRUST_INPUT,
        InputRef.TRUST_STORE,
    ),
}
_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
_PUBLIC_KEY = _PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
_B64_PUBLIC_KEY = base64.b64encode(_PUBLIC_KEY).decode("ascii")

_N1_IGNORED_NAN_MANIFEST = bytes.fromhex(
    "7b22736368656d61223a2261695f7061636b5f6d616e69666573745f7631222c"
    "2274735f757463223a22323032362d30312d30315430303a30303a30305a222c"
    "22696e7075745f736368656d61223a2261695f6f75747075745f7631222c2263"
    "616e6f6e6963616c697a6174696f6e223a226a736f6e5f736f727465645f6b65"
    "79735f6e6f5f776869746573706163655f75746638222c2261695f686173685f"
    "736861323536223a223030303030303030303030303030303030303030303030"
    "3030303030303030303030303030303030303030303030303030303030303030"
    "3030303030303030303030303030222c22657874656e73696f6e223a4e614e7d"
)
_N1_IGNORED_SURROGATE_MANIFEST = bytes.fromhex(
    "7b22736368656d61223a2261695f7061636b5f6d616e69666573745f7631222c"
    "2274735f757463223a22323032362d30312d30315430303a30303a30305a222c"
    "22696e7075745f736368656d61223a2261695f6f75747075745f7631222c2263"
    "616e6f6e6963616c697a6174696f6e223a226a736f6e5f736f727465645f6b65"
    "79735f6e6f5f776869746573706163655f75746638222c2261695f686173685f"
    "736861323536223a223030303030303030303030303030303030303030303030"
    "3030303030303030303030303030303030303030303030303030303030303030"
    "3030303030303030303030303030222c22657874656e73696f6e223a225c7564"
    "383030227d"
)


def _profile_declaration(index: int = 0) -> TimestampDigitProfileDeclaration:
    profile = FROZEN_UNICODE_PROFILES[index]
    return TimestampDigitProfileDeclaration(
        profile.profile_id,
        profile.range_file_sha256,
        profile.unicode_version,
    )


def _prepared(
    capability: str = V1_RESTRICTED_PORTABLE,
    *,
    maximum: int | None = 640,
    mode: str = BOUNDED,
    profile_index: int = 0,
):
    if capability == V1_NAMED_RUNTIME_COMPATIBILITY:
        timestamp_profile: str | TimestampDigitProfileDeclaration = (
            _profile_declaration(profile_index)
        )
    else:
        timestamp_profile = ASCII_TIMESTAMP_DIGIT_PROFILE
    request = VerifierCapabilityRequest(
        DispatchCapabilityDeclaration(AELITIUM_DISPATCH_JSON_1),
        V1CapabilityDeclaration(
            capability,
            IntegerConversionDeclaration(mode, maximum),
            timestamp_profile,
            ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        ),
        V2CapabilityDeclaration(V2_PORTABLE),
        SignatureVerificationDeclaration(ED25519_PORTABLE_STRICT_1),
    )
    return prepare_verifier_capabilities(request)


def _route(*args, **kwargs):
    return select_effective_route(_prepared(*args, **kwargs), AI_CANONICALIZATION)


def _payload_source(metadata: bytes = b"{}", *, output: bytes | None = None) -> bytes:
    output_source = output or json.dumps("capability output").encode("utf-8")
    return (
        b'{"metadata":'
        + metadata
        + b',"model":"capability-model","output":'
        + output_source
        + b',"prompt":"capability prompt","schema_version":"ai_output_v1",'
        + b'"ts_utc":"2026-09-09T00:00:00Z"}'
    )


def _manifest_source(
    canonical: bytes,
    *,
    timestamp: str = "2026-09-09T00:00:00Z",
    canonicalization: str = AI_CANONICALIZATION,
    extension: bytes | None = None,
) -> bytes:
    manifest = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": timestamp,
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": canonicalization,
        "ai_hash_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    source = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    if extension is not None:
        source = source[:-1] + b',"extension":' + extension + b"}"
    return source + b"\n"


def _snapshot(
    canonical: bytes,
    manifest: bytes | None = None,
    *,
    keyring: bytes | None = None,
    trust: bytes | None = None,
):
    return acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(
            canonical,
            manifest or _manifest_source(canonical),
            keyring,
            trust_store=trust,
        )
    )


def _signed_keyring(manifest: bytes, *, key_id: str = "capability-key") -> bytes:
    keyring = {
        "keyring_format": "ed25519-v1",
        "keys": [{"key_id": key_id, "public_key_b64": _B64_PUBLIC_KEY}],
        "signatures": [
            {
                "key_id": key_id,
                "algorithm": "ed25519",
                "scope": "manifest.json",
                "sig_b64": base64.b64encode(_PRIVATE_KEY.sign(manifest)).decode(
                    "ascii"
                ),
            }
        ],
    }
    return json.dumps(keyring, ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _source_with_integer(digits: int, *, duplicate_overwrite: bool = False) -> bytes:
    value = b"7" * digits
    suffix = b',"value":0}' if duplicate_overwrite else b"}"
    return b'{"value":' + value + suffix


def _assert_integer_refusal(
    error: OperationalInputFailure,
    *,
    phase: OperationalPhase,
    input_ref: InputRef,
    observed: int = 641,
) -> None:
    assert error.operational_code is (
        OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY
    )
    assert error.phase is phase
    assert error.input_ref is input_ref
    assert error.limit is not None
    assert error.limit.name is LimitName.INTEGER_DECIMAL_DIGITS
    assert error.limit.unit is LimitUnit.DIGITS
    assert error.limit.maximum == 640
    assert error.limit.observed_at_least == observed
    assert error.detail is None


@pytest.mark.parametrize(
    "capability",
    [V1_RESTRICTED_PORTABLE, V1_FROZEN_LEGACY_COMPATIBILITY],
)
@pytest.mark.parametrize("role", list(_ROLE_BOUNDARIES))
@pytest.mark.parametrize("digits", [639, 640])
def test_portable_integer_at_or_below_boundary_converts_exactly(
    capability: str,
    role: InputRole,
    digits: int,
) -> None:
    phase, input_ref = _ROLE_BOUNDARIES[role]

    parsed = parse_v1_json_source(
        _source_with_integer(digits),
        route=_route(capability),
        role=role,
        phase=phase,
        input_ref=input_ref,
    )

    assert integer_to_decimal(parsed["value"]) == "7" * digits


@pytest.mark.parametrize(
    "capability",
    [V1_RESTRICTED_PORTABLE, V1_FROZEN_LEGACY_COMPATIBILITY],
)
@pytest.mark.parametrize("role", list(_ROLE_BOUNDARIES))
def test_portable_integer_641_is_operational_in_every_reached_role(
    capability: str,
    role: InputRole,
) -> None:
    phase, input_ref = _ROLE_BOUNDARIES[role]

    with pytest.raises(OperationalInputFailure) as caught:
        parse_v1_json_source(
            _source_with_integer(641),
            route=_route(capability),
            role=role,
            phase=phase,
            input_ref=input_ref,
        )

    _assert_integer_refusal(caught.value, phase=phase, input_ref=input_ref)


def test_overwritten_portable_integer_occurrence_is_still_reached() -> None:
    with pytest.raises(OperationalInputFailure) as caught:
        parse_v1_json_source(
            _source_with_integer(641, duplicate_overwrite=True),
            route=_route(),
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )

    _assert_integer_refusal(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
    )


def test_integer_magnitude_excludes_leading_minus() -> None:
    route = _route()
    accepted = parse_v1_json_source(
        b'{"value":-' + b"7" * 640 + b"}",
        route=route,
        role=InputRole.AI_CANONICAL_JSON,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
    )
    assert integer_to_decimal(accepted["value"]) == "-" + "7" * 640

    with pytest.raises(OperationalInputFailure) as caught:
        parse_v1_json_source(
            b'{"value":-' + b"7" * 641 + b"}",
            route=route,
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )
    _assert_integer_refusal(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
    )


@pytest.mark.parametrize("digits", [641, 4300, 10_000])
def test_portable_integer_fact_reports_reached_token_magnitude(digits: int) -> None:
    with pytest.raises(OperationalInputFailure) as caught:
        parse_v1_json_source(
            _source_with_integer(digits),
            route=_route(),
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )

    _assert_integer_refusal(
        caught.value,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
        observed=digits,
    )


def test_fraction_and_exponent_tokens_do_not_use_integer_digit_profile() -> None:
    route = _route(V1_NAMED_RUNTIME_COMPATIBILITY, maximum=640)
    for token in (b"7" * 5000 + b".0", b"7e5000"):
        parsed = parse_v1_json_source(
            b'{"value":' + token + b"}",
            route=route,
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )
        assert isinstance(parsed["value"], float)


def test_earlier_malformed_number_precedes_later_portable_integer() -> None:
    source = b'{"bad":1.,"later":' + b"7" * 641 + b"}"

    with pytest.raises(LegacyJsonSourceError):
        parse_v1_json_source(
            source,
            route=_route(),
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )


@pytest.mark.parametrize(
    ("maximum", "accepted", "rejected"),
    [(640, 640, 641), (4300, 4300, 4301)],
)
def test_named_bounded_exact_integer_boundary(
    maximum: int,
    accepted: int,
    rejected: int,
) -> None:
    route = _route(V1_NAMED_RUNTIME_COMPATIBILITY, maximum=maximum)
    parsed = parse_v1_json_source(
        _source_with_integer(accepted),
        route=route,
        role=InputRole.AI_CANONICAL_JSON,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
    )
    assert integer_to_decimal(parsed["value"]) == "7" * accepted

    with pytest.raises(LegacyIntegerConversionError):
        parse_v1_json_source(
            _source_with_integer(rejected),
            route=route,
            role=InputRole.AI_CANONICAL_JSON,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )


@pytest.mark.parametrize("maximum", [640, 4300])
@pytest.mark.parametrize(
    ("role", "expected_reason"),
    [
        (InputRole.AI_CANONICAL_JSON, "CANONICAL_NOT_JSON"),
        (InputRole.AI_MANIFEST_JSON, "MANIFEST_NOT_JSON"),
        (InputRole.VERIFICATION_KEYS_JSON, "SIGNATURE_INVALID"),
        (InputRole.TRUST_STORE, "TRUST_STORE_INVALID"),
    ],
)
def test_named_bounded_above_limit_uses_source_specific_semantic_result(
    maximum: int,
    role: InputRole,
    expected_reason: str,
) -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    huge = b"7" * (maximum + 1)
    keyring = None
    trust = None
    if role is InputRole.AI_CANONICAL_JSON:
        canonical = _payload_source(b'{"large":' + huge + b"}")
        manifest = _manifest_source(canonical)
    elif role is InputRole.AI_MANIFEST_JSON:
        manifest = _manifest_source(canonical, extension=huge)
    elif role is InputRole.VERIFICATION_KEYS_JSON:
        keyring = b'{"extension":' + huge + b"}"
    else:
        trust = (
            b'{"trust_store_format":"aelitium-trust-v1","signers":[],'
            b'"extension":' + huge + b"}"
        )

    result = verify_ai_snapshot(
        _snapshot(canonical, manifest, keyring=keyring, trust=trust),
        capabilities=_prepared(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            maximum=maximum,
        ),
    )

    assert not result.valid
    assert result.reason == expected_reason


@pytest.mark.parametrize(
    "capability",
    [V1_RESTRICTED_PORTABLE, V1_FROZEN_LEGACY_COMPATIBILITY],
)
@pytest.mark.parametrize("role", list(_ROLE_BOUNDARIES))
def test_portable_641_integration_uses_exact_role_mapping(
    capability: str,
    role: InputRole,
) -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    huge = b"7" * 641
    keyring = None
    trust = None
    if role is InputRole.AI_CANONICAL_JSON:
        canonical = _payload_source(b'{"large":' + huge + b"}")
        manifest = _manifest_source(canonical)
    elif role is InputRole.AI_MANIFEST_JSON:
        manifest = _manifest_source(canonical, extension=huge)
    elif role is InputRole.VERIFICATION_KEYS_JSON:
        keyring = b'{"extension":' + huge + b"}"
    else:
        trust = (
            b'{"trust_store_format":"aelitium-trust-v1","signers":[],'
            b'"extension":' + huge + b"}"
        )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            _snapshot(canonical, manifest, keyring=keyring, trust=trust),
            capabilities=_prepared(capability),
        )

    phase, input_ref = _ROLE_BOUNDARIES[role]
    _assert_integer_refusal(caught.value, phase=phase, input_ref=input_ref)


def _operation_limits() -> VerifierLimitState:
    limits = OperationalLimits()
    return VerifierLimitState(
        AELITIUM_CLEANROOM_MINIMUM_1,
        limits,
        limits,
    )


@pytest.mark.parametrize("digits", [640, 641, 1000, 4301])
@pytest.mark.parametrize(
    ("role", "accepted_reason"),
    [
        (InputRole.VERIFICATION_KEYS_JSON, "SIGNATURE_INVALID"),
        (InputRole.TRUST_STORE, "TRUST_STORE_INVALID"),
        (InputRole.AI_MANIFEST_JSON, "OK"),
        (InputRole.AI_CANONICAL_JSON, "OK"),
    ],
)
def test_portable_integer_outer_classification_for_every_source(
    digits: int,
    role: InputRole,
    accepted_reason: str,
) -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    keyring = None
    trust = None
    token = b"7" * digits
    if role is InputRole.AI_CANONICAL_JSON:
        canonical = _payload_source(b'{"large":' + token + b"}")
        manifest = _manifest_source(canonical)
    elif role is InputRole.AI_MANIFEST_JSON:
        manifest = _manifest_source(canonical, extension=token)
    elif role is InputRole.VERIFICATION_KEYS_JSON:
        keyring = b'{"extension":' + token + b"}"
    else:
        trust = (
            b'{"trust_store_format":"aelitium-trust-v1","signers":[],'
            b'"extension":' + token + b"}"
        )

    value = verify_bundle_operation(
        ImmutableBytesInputs(canonical, manifest, keyring, trust_store=trust),
        capability_request=_prepared().requested,
        limits=_operation_limits(),
        options=AIVerificationOptions(),
    ).to_json_value()

    if digits == 640:
        expected_rc = 0 if accepted_reason == "OK" else 2
        assert value["rc"] == expected_rc
        assert value["verification_result"]["reason"] == accepted_reason
        assert value["operational_result"] is None
        return

    phase, input_ref = _ROLE_BOUNDARIES[role]
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INPUT_OUTSIDE_DECLARED_CAPABILITY",
        "phase": phase.value,
        "input_ref": input_ref.value,
        "limit": {
            "name": "INTEGER_DECIMAL_DIGITS",
            "unit": "DIGITS",
            "maximum": 640,
            "observed_at_least": digits,
        },
        "detail": None,
    }


@pytest.mark.parametrize("digits", [640, 641, 1000, 4301])
def test_keyring_legacy_auxiliary_profile_is_manifest_route_independent(
    digits: int,
) -> None:
    payload = {
        "metadata": {},
        "model": "capability-model",
        "output": "capability output",
        "prompt": "capability prompt",
        "schema_version": AI_OUTPUT_SCHEMA_VERSION,
        "ts_utc": "2026-09-09T00:00:00Z",
    }
    canonical_text, _ = canonicalize_ai_output(payload, AI_CANONICALIZATION_V2)
    canonical = canonical_text.encode("utf-8")
    manifest = _manifest_source(
        canonical,
        canonicalization=AI_CANONICALIZATION_V2,
    )
    keyring = b'{"extension":' + b"7" * digits + b"}"

    value = verify_bundle_operation(
        ImmutableBytesInputs(canonical, manifest, keyring),
        capability_request=_prepared().requested,
        limits=_operation_limits(),
        options=AIVerificationOptions(),
    ).to_json_value()

    if digits == 640:
        assert value["rc"] == 2
        assert value["verification_result"]["reason"] == "SIGNATURE_INVALID"
        assert value["operational_result"] is None
        return

    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == (
        "INPUT_OUTSIDE_DECLARED_CAPABILITY"
    )
    assert value["operational_result"]["phase"] == "SIGNATURE_MATERIAL"
    assert value["operational_result"]["input_ref"] == "VERIFICATION_KEYS_JSON"
    assert value["operational_result"]["limit"] == {
        "name": "INTEGER_DECIMAL_DIGITS",
        "unit": "DIGITS",
        "maximum": 640,
        "observed_at_least": digits,
    }


def test_manifest_integer_classification_ignores_ambient_python_guard() -> None:
    child = r'''
import json
import runpy
import sys

from engine.ai_verify import AIVerificationOptions
from engine.result_contracts import VerifierLimitState
from engine.verifier_operation import verify_bundle_operation
from engine.verifier_snapshot import ImmutableBytesInputs, OperationalLimits

sys.set_int_max_str_digits(int(sys.argv[1]))
namespace = runpy.run_path("tests/test_verifier_v1_capability_semantics.py")
prepared = namespace["_prepared"]()
limits = VerifierLimitState(
    "AELITIUM_CLEANROOM_MINIMUM_1",
    OperationalLimits(),
    OperationalLimits(),
)
canonical = namespace["_payload_source"]()
rows = []
for digits in (640, 641, 1000, 4301):
    manifest = namespace["_manifest_source"](
        canonical,
        extension=b"7" * digits,
    )
    value = verify_bundle_operation(
        ImmutableBytesInputs(canonical, manifest, None),
        capability_request=prepared.requested,
        limits=limits,
        options=AIVerificationOptions(),
    ).to_json_value()
    operational = value["operational_result"]
    rows.append({
        "digits": digits,
        "rc": value["rc"],
        "reason": (
            value["verification_result"]["reason"]
            if value["verification_result"] is not None
            else None
        ),
        "operational_code": (
            operational["operational_code"]
            if operational is not None
            else None
        ),
        "limit": operational["limit"] if operational is not None else None,
    })
print(json.dumps(rows, sort_keys=True))
'''
    observed = []
    for setting in (640, 4300):
        completed = subprocess.run(
            [sys.executable, "-c", child, str(setting)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
        )
        assert completed.stderr == ""
        observed.append(json.loads(completed.stdout))

    expected = [
        {
            "digits": 640,
            "rc": 0,
            "reason": "OK",
            "operational_code": None,
            "limit": None,
        },
        *[
            {
                "digits": digits,
                "rc": 3,
                "reason": None,
                "operational_code": "INPUT_OUTSIDE_DECLARED_CAPABILITY",
                "limit": {
                    "name": "INTEGER_DECIMAL_DIGITS",
                    "unit": "DIGITS",
                    "maximum": 640,
                    "observed_at_least": digits,
                },
            }
            for digits in (641, 1000, 4301)
        ],
    ]
    assert observed == [expected, expected]


@pytest.mark.parametrize("maximum", [5000, 10_000])
def test_named_bounded_above_host_default_executes_end_to_end(maximum: int) -> None:
    digits = maximum
    canonical = _payload_source(b'{"large":' + b"7" * digits + b"}")

    result = verify_ai_snapshot(
        _snapshot(canonical),
        capabilities=_prepared(V1_NAMED_RUNTIME_COMPATIBILITY, maximum=maximum),
    )

    assert result.valid
    assert integer_to_decimal(result.canonical["metadata"]["large"]) == "7" * digits


def test_named_unlimited_executes_integer_above_host_default_end_to_end() -> None:
    digits = 12_000
    canonical = _payload_source(b'{"large":-' + b"7" * digits + b"}")

    result = verify_ai_snapshot(
        _snapshot(canonical),
        capabilities=_prepared(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            maximum=None,
            mode=UNLIMITED,
        ),
    )

    assert result.valid
    rendered = integer_to_decimal(result.canonical["metadata"]["large"])
    assert rendered == "-" + "7" * digits


def test_large_integer_canonical_serializer_is_profile_relative() -> None:
    route = _route(V1_NAMED_RUNTIME_COMPATIBILITY, maximum=5000)
    parsed = parse_v1_json_source(
        _source_with_integer(5000),
        route=route,
        role=InputRole.AI_CANONICAL_JSON,
        phase=OperationalPhase.CANONICAL_PARSE,
        input_ref=InputRef.AI_CANONICAL_JSON,
    )

    assert canonical_json_v1_profile(parsed) == (
        '{"value":' + "7" * 5000 + "}"
    )


@pytest.mark.parametrize(
    ("source", "case_id"),
    [
        (_N1_IGNORED_NAN_MANIFEST, "legacy.restricted.nonfinite.ignored_nan"),
        (
            _N1_IGNORED_SURROGATE_MANIFEST,
            "legacy.restricted.surrogate.ignored_opaque_unmatched_high",
        ),
    ],
)
def test_n1_categorical_manifest_cases_raise_null_limit(
    source: bytes,
    case_id: str,
) -> None:
    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            _snapshot(_payload_source(), source),
            capabilities=_prepared(V1_RESTRICTED_PORTABLE),
        )

    error = caught.value
    assert error.operational_code is (
        OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY
    ), case_id
    assert error.phase is OperationalPhase.MANIFEST_PARSE
    assert error.input_ref is InputRef.AI_MANIFEST_JSON
    assert error.limit is None
    assert error.detail is None


@pytest.mark.parametrize(
    "source",
    [_N1_IGNORED_NAN_MANIFEST, _N1_IGNORED_SURROGATE_MANIFEST],
)
def test_n1_categorical_manifest_bytes_keep_frozen_legacy_behavior(
    source: bytes,
) -> None:
    result = verify_ai_snapshot(
        _snapshot(_payload_source(), source),
        capabilities=_prepared(V1_FROZEN_LEGACY_COMPATIBILITY),
    )

    assert not result.valid
    assert result.reason == "MANIFEST_BAD_AI_HASH_SHA256"


def test_restricted_nonfinite_metadata_refuses_but_frozen_legacy_accepts() -> None:
    canonical = _payload_source(b'{"legacy":NaN}')
    snapshot = _snapshot(canonical)

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            snapshot,
            capabilities=_prepared(V1_RESTRICTED_PORTABLE),
        )
    assert caught.value.phase is OperationalPhase.CANONICAL_PARSE
    assert caught.value.limit is None

    frozen = verify_ai_snapshot(
        snapshot,
        capabilities=_prepared(V1_FROZEN_LEGACY_COMPATIBILITY),
    )
    assert frozen.valid


@pytest.mark.parametrize(("role", "source", "phase"), [
    ("trust", b'{"signers":NaN,"signers":[],"trust_store_format":"aelitium-trust-v1"}', OperationalPhase.TRUST_INPUT),
    ("trust", b'{"signers":[],"signers":Infinity,"trust_store_format":"aelitium-trust-v1"}', OperationalPhase.TRUST_INPUT),
    ("trust", b'{"signers":[],"trust_store_format":"aelitium-trust-v1","ignored":{"a":[-Infinity]}}', OperationalPhase.TRUST_INPUT),
    ("manifest", b'NaN', OperationalPhase.MANIFEST_PARSE),
    ("canonical", b'{"x":NaN,"x":null}', OperationalPhase.CANONICAL_PARSE),
    ("keyring", b'{"keyring_format":"ed25519-v1","keys":[],"signatures":[],"ignored":[{"a":NaN}]}', OperationalPhase.SIGNATURE_MATERIAL),
])
def test_restricted_nonfinite_is_refused_before_duplicate_or_unknown_collapse(
    role: str, source: bytes, phase: OperationalPhase,
) -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    if role == "trust":
        snapshot = _snapshot(canonical, manifest, trust=source)
    elif role == "manifest":
        snapshot = _snapshot(canonical, manifest[:-2] + b',"ignored":' + source + b'}\n')
    elif role == "canonical":
        snapshot = _snapshot(_payload_source(b'{"x":NaN,"x":null}'))
    else:
        snapshot = _snapshot(canonical, manifest, keyring=source)
    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(snapshot, capabilities=_prepared(V1_RESTRICTED_PORTABLE))
    assert caught.value.operational_code is OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY
    assert caught.value.phase is phase
    assert caught.value.limit is None


def test_governed_invalid_surrogate_remains_semantic() -> None:
    canonical = _payload_source(output=b'"\\ud800"')

    result = verify_ai_snapshot(
        _snapshot(canonical),
        capabilities=_prepared(V1_RESTRICTED_PORTABLE),
    )

    assert not result.valid
    assert result.reason == "CANONICAL_NOT_JSON"


def test_opaque_trust_label_refuses_only_under_restricted_profile() -> None:
    trust = (
        b'{"trust_store_format":"aelitium-trust-v1","signers":[{'
        b'"algorithm":"ed25519","public_key_b64":"'
        + _B64_PUBLIC_KEY.encode("ascii")
        + b'","label":"\\ud800"}]}'
    )
    snapshot = _snapshot(_payload_source(), trust=trust)

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            snapshot,
            capabilities=_prepared(V1_RESTRICTED_PORTABLE),
        )
    assert caught.value.phase is OperationalPhase.TRUST_INPUT
    assert caught.value.input_ref is InputRef.TRUST_STORE
    assert caught.value.limit is None

    frozen = verify_ai_snapshot(
        snapshot,
        capabilities=_prepared(V1_FROZEN_LEGACY_COMPATIBILITY),
    )
    assert frozen.valid


def test_opaque_key_id_refuses_only_under_restricted_profile() -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    keyring = _signed_keyring(manifest, key_id="\ud800")
    snapshot = _snapshot(canonical, manifest, keyring=keyring)

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            snapshot,
            capabilities=_prepared(V1_RESTRICTED_PORTABLE),
        )
    assert caught.value.phase is OperationalPhase.SIGNATURE_MATERIAL
    assert caught.value.input_ref is InputRef.VERIFICATION_KEYS_JSON
    assert caught.value.limit is None

    frozen = verify_ai_snapshot(
        snapshot,
        capabilities=_prepared(V1_FROZEN_LEGACY_COMPATIBILITY),
    )
    assert frozen.valid


@pytest.mark.parametrize(
    ("timestamp", "expected_valid"),
    [
        ("2026-09-09T00:00:00Z", True),
        ("2026-09-09T00:00:00Z\n", True),
        ("2026-09-09T00:00:00Z\n\n", False),
        ("2026/09-09T00:00:00Z", False),
        ("X026-09-09T00:00:00Z", False),
    ],
)
def test_portable_v1_timestamp_shape_and_final_lf(
    timestamp: str,
    expected_valid: bool,
) -> None:
    canonical = _payload_source()
    result = verify_ai_snapshot(
        _snapshot(canonical, _manifest_source(canonical, timestamp=timestamp)),
        capabilities=_prepared(V1_FROZEN_LEGACY_COMPATIBILITY),
    )

    assert result.valid is expected_valid
    assert result.reason == ("OK" if expected_valid else "MANIFEST_BAD_TS_UTC")


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-09-09T00:00:00Z", True),
        ("2026-09-09T00:00:00Z\n", True),
        ("2026-09-09T00:00:00Z\n\n", False),
    ],
)
def test_named_v1_timestamp_final_lf(timestamp: str, expected: bool) -> None:
    assert validate_v1_manifest_timestamp(
        timestamp,
        route=_route(V1_NAMED_RUNTIME_COMPATIBILITY),
    ) is expected


@pytest.mark.parametrize(
    "capability",
    [V1_RESTRICTED_PORTABLE, V1_FROZEN_LEGACY_COMPATIBILITY],
)
def test_portable_non_ascii_nd_timestamp_is_operational(
    capability: str,
) -> None:
    canonical = _payload_source()
    timestamp = "\u0661026-09-09T00:00:00Z"

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            _snapshot(canonical, _manifest_source(canonical, timestamp=timestamp)),
            capabilities=_prepared(capability),
        )

    error = caught.value
    assert error.operational_code is (
        OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY
    )
    assert error.phase is OperationalPhase.MANIFEST_PARSE
    assert error.input_ref is InputRef.AI_MANIFEST_JSON
    assert error.limit is not None
    assert error.limit.name is LimitName.TIMESTAMP_DIGIT_PROFILE
    assert error.limit.unit is LimitUnit.PROFILE
    assert error.limit.maximum == "ASCII"
    assert error.limit.observed_at_least == "U+0661"


def test_governed_timestamp_surrogate_remains_semantic() -> None:
    canonical = _payload_source()
    manifest = _manifest_source(
        canonical,
        timestamp="\ud800026-09-09T00:00:00Z",
    )

    result = verify_ai_snapshot(
        _snapshot(canonical, manifest),
        capabilities=_prepared(V1_RESTRICTED_PORTABLE),
    )

    assert not result.valid
    assert result.reason == "MANIFEST_BAD_TS_UTC"


def test_disabled_v1_timestamp_validation_skips_digit_capability() -> None:
    canonical = _payload_source()
    manifest = _manifest_source(
        canonical,
        timestamp="\u0661026-09-09T00:00:00Z",
    )

    result = verify_ai_snapshot(
        _snapshot(canonical, manifest),
        options=AIVerificationOptions(validate_manifest_timestamp=False),
        capabilities=_prepared(V1_RESTRICTED_PORTABLE),
    )

    assert result.valid


@pytest.mark.parametrize(
    ("profile_index", "code_point", "expected"),
    [
        (0, 0x0661, True),
        (1, 0x0661, True),
        (2, 0x0661, True),
        (0, 0x16AC0, False),
        (1, 0x16AC0, True),
        (2, 0x16AC0, True),
        (0, 0x1E4F0, False),
        (1, 0x1E4F0, False),
        (2, 0x1E4F0, True),
    ],
)
def test_named_timestamp_membership_uses_selected_frozen_profile(
    profile_index: int,
    code_point: int,
    expected: bool,
) -> None:
    route = _route(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        profile_index=profile_index,
    )
    timestamp = chr(code_point) + "026-09-09T00:00:00Z"

    assert validate_v1_manifest_timestamp(timestamp, route=route) is expected


def test_named_timestamp_version_difference_reaches_snapshot_semantics() -> None:
    canonical = _payload_source()
    timestamp = chr(0x16AC0) + "026-09-09T00:00:00Z"
    snapshot = _snapshot(canonical, _manifest_source(canonical, timestamp=timestamp))

    old = verify_ai_snapshot(
        snapshot,
        capabilities=_prepared(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            profile_index=0,
        ),
    )
    new = verify_ai_snapshot(
        snapshot,
        capabilities=_prepared(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            profile_index=1,
        ),
    )

    assert not old.valid and old.reason == "MANIFEST_BAD_TS_UTC"
    assert new.valid


def test_v2_non_ascii_nd_timestamp_remains_v2_semantic_failure() -> None:
    payload = {
        "metadata": {},
        "model": "capability-model",
        "output": "capability output",
        "prompt": "capability prompt",
        "schema_version": "ai_output_v1",
        "ts_utc": "2026-09-09T00:00:00Z",
    }
    canonical_text, _ = canonicalize_ai_output(payload, AI_CANONICALIZATION_V2)
    canonical = canonical_text.encode("utf-8")
    manifest = _manifest_source(
        canonical,
        timestamp="\u0661026-09-09T00:00:00Z",
        canonicalization=AI_CANONICALIZATION_V2,
    )

    result = verify_ai_snapshot(
        _snapshot(canonical, manifest),
        capabilities=_prepared(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            profile_index=2,
        ),
    )

    assert not result.valid
    assert result.reason == "MANIFEST_BAD_TS_UTC"


def test_capability_execution_reads_only_snapshot_bytes() -> None:
    canonical = _payload_source(b'{"large":' + b"7" * 5000 + b"}")
    snapshot = _snapshot(canonical)
    prepared = _prepared(V1_NAMED_RUNTIME_COMPATIBILITY, maximum=5000)

    with (
        mock.patch("builtins.open", side_effect=AssertionError("filesystem read")),
        mock.patch.object(Path, "read_bytes", side_effect=AssertionError("path read")),
        mock.patch.object(Path, "read_text", side_effect=AssertionError("path read")),
    ):
        result = verify_ai_snapshot(snapshot, capabilities=prepared)

    assert result.valid


def test_production_module_has_no_host_policy_oracle() -> None:
    import engine.verifier_v1_capability as runtime

    source = inspect.getsource(runtime)
    forbidden = (
        "unicodedata",
        ".isdigit(",
        ".isdecimal(",
        "locale",
        "get_int_max_str_digits",
        "set_int_max_str_digits",
        "\\\\d",
        "os.environ",
    )

    assert all(item not in source for item in forbidden)
