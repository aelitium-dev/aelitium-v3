"""Capability-qualified verifier operation and outer-result contract tests."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

import pytest
import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft7Validator, ValidationError
from referencing import Registry, Resource

import engine.ai_verify as ai_verify_runtime
import engine.signing as signing_runtime
import engine.verifier_capabilities as capability_runtime
import engine.verifier_operation as operation_runtime
import engine.verifier_snapshot as snapshot_runtime
from engine.ai_canonical import canonicalize_ai_output
from engine.ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICALIZATION_V2,
    AI_MANIFEST_SCHEMA,
    AI_OUTPUT_SCHEMA_VERSION,
)
from engine.ai_verify import AIVerificationOptions
from engine.result_contracts import (
    AELITIUM_CLEANROOM_MINIMUM_1,
    MAX_PORTABLE_INTEGER,
    ResultContractError,
    VERIFIER_TOOL_RESULT_CONTRACT,
    VERIFY_BUNDLE_OPERATION,
    VerifierLimitState,
    VerifierToolResult,
    build_verifier_tool_result,
    project_capability_request,
    serialize_verifier_tool_result,
)
from engine.trust import TRUST_STORE_FORMAT
from engine.verifier_capabilities import (
    ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    AELITIUM_DISPATCH_JSON_1,
    ASCII_TIMESTAMP_DIGIT_PROFILE,
    BOUNDED,
    CapabilityRequestValidationError,
    ED25519_PORTABLE_STRICT_1,
    FROZEN_UNICODE_PROFILES,
    V1_FROZEN_LEGACY_COMPATIBILITY,
    V1_LEGACY_UNSUPPORTED,
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
)
from engine.verifier_operation import verify_bundle_operation
from engine.verifier_json_limits import scan_json_limits
from engine.verifier_snapshot import (
    DEFAULT_OPERATIONAL_LIMITS,
    DirectFilesystemInputs,
    ImmutableBytesInputs,
    InputMode,
    InputRef,
    InputRole,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "engine" / "schemas"
FROZEN_CASES = {
    item["case_id"]: item
    for item in json.loads(
        (
            ROOT
            / "conformance"
            / "legacy_v1_operational_policy"
            / "cases.json"
        ).read_text(encoding="utf-8")
    )["vectors"]
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


def _validator() -> Draft7Validator:
    outer = json.loads(
        (SCHEMAS / "verifier_tool_result_v1.json").read_text(encoding="utf-8")
    )
    inner = json.loads(
        (SCHEMAS / "verification_result_v1.json").read_text(encoding="utf-8")
    )
    registry = Registry().with_resource(
        inner["$id"],
        Resource.from_contents(inner),
    )
    return Draft7Validator(outer, registry=registry)


def _request(
    v1_capability: str = V1_RESTRICTED_PORTABLE,
    *,
    named_profile_index: int = 0,
    declaration: V1CapabilityDeclaration | None = None,
    dispatch: str = AELITIUM_DISPATCH_JSON_1,
    v2: str = V2_PORTABLE,
    signature: str = ED25519_PORTABLE_STRICT_1,
) -> VerifierCapabilityRequest:
    if declaration is not None:
        v1 = declaration
    elif v1_capability == V1_LEGACY_UNSUPPORTED:
        v1 = V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED)
    elif v1_capability == V1_NAMED_RUNTIME_COMPATIBILITY:
        profile = FROZEN_UNICODE_PROFILES[named_profile_index]
        v1 = V1CapabilityDeclaration(
            V1_NAMED_RUNTIME_COMPATIBILITY,
            IntegerConversionDeclaration(BOUNDED, 640),
            TimestampDigitProfileDeclaration(
                profile.profile_id,
                profile.range_file_sha256,
                profile.unicode_version,
            ),
            ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        )
    else:
        v1 = V1CapabilityDeclaration(
            v1_capability,
            IntegerConversionDeclaration(BOUNDED, 640),
            ASCII_TIMESTAMP_DIGIT_PROFILE,
            ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        )
    return VerifierCapabilityRequest(
        DispatchCapabilityDeclaration(dispatch),
        v1,
        V2CapabilityDeclaration(v2),
        SignatureVerificationDeclaration(signature),
    )


def _limits(
    *,
    effective: OperationalLimits = DEFAULT_OPERATIONAL_LIMITS,
    advertised: OperationalLimits = DEFAULT_OPERATIONAL_LIMITS,
    claimed_envelope: str | None = AELITIUM_CLEANROOM_MINIMUM_1,
) -> VerifierLimitState:
    return VerifierLimitState(claimed_envelope, advertised, effective)


def _payload_source(
    metadata: bytes = b"{}",
    *,
    output: bytes | None = None,
) -> bytes:
    output_source = output or json.dumps("operation output").encode("utf-8")
    return (
        b'{"metadata":'
        + metadata
        + b',"model":"operation-model","output":'
        + output_source
        + b',"prompt":"operation prompt","schema_version":"ai_output_v1",'
        + b'"ts_utc":"2026-09-09T00:00:00Z"}'
    )


def _v2_payload_source() -> bytes:
    text, _ = canonicalize_ai_output(
        {
            "metadata": {},
            "model": "operation-model",
            "output": "operation output",
            "prompt": "operation prompt",
            "schema_version": AI_OUTPUT_SCHEMA_VERSION,
            "ts_utc": "2026-09-09T00:00:00Z",
        },
        AI_CANONICALIZATION_V2,
    )
    return text.encode("utf-8")


def _manifest_source(
    canonical: bytes,
    *,
    canonicalization: str = AI_CANONICALIZATION,
    timestamp: str = "2026-09-09T00:00:00Z",
    extension: bytes | None = None,
) -> bytes:
    import hashlib

    value = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": timestamp,
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": canonicalization,
        "ai_hash_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    source = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if extension is not None:
        source = source[:-1] + b',"extension":' + extension + b"}"
    return source + b"\n"


def _keyring(manifest: bytes, *, valid: bool = True) -> bytes:
    signature = (
        _PRIVATE_KEY.sign(manifest)
        if valid
        else bytes(64)
    )
    value = {
        "keyring_format": "ed25519-v1",
        "keys": [
            {
                "key_id": "operation-key",
                "public_key_b64": _B64_PUBLIC_KEY,
            }
        ],
        "signatures": [
            {
                "key_id": "operation-key",
                "algorithm": "ed25519",
                "scope": "manifest.json",
                "sig_b64": base64.b64encode(signature).decode("ascii"),
            }
        ],
    }
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _trust_bytes() -> bytes:
    value = {
        "trust_store_format": TRUST_STORE_FORMAT,
        "signers": [
            {
                "algorithm": "ed25519",
                "public_key_b64": _B64_PUBLIC_KEY,
            }
        ],
    }
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _inputs(
    canonical: bytes | None = None,
    manifest: bytes | None = None,
    *,
    keyring: bytes | None = None,
    trust: bytes | None = None,
    canonicalization: str = AI_CANONICALIZATION,
) -> ImmutableBytesInputs:
    payload = canonical if canonical is not None else (
        _v2_payload_source()
        if canonicalization == AI_CANONICALIZATION_V2
        else _payload_source()
    )
    manifest_bytes = manifest or _manifest_source(
        payload,
        canonicalization=canonicalization,
    )
    return ImmutableBytesInputs(payload, manifest_bytes, keyring, trust)


def _deep_v2_inputs(
    structural_depth: int,
) -> tuple[ImmutableBytesInputs, bytes]:
    array_depth = structural_depth - 2
    assert array_depth >= 1
    nested = b"[" * array_depth + b"null" + b"]" * array_depth
    canonical = (
        b'{"metadata":{"deep":'
        + nested
        + b'},"model":"operation-model","output":"operation output",'
        + b'"prompt":"operation prompt","schema_version":"ai_output_v1",'
        + b'"ts_utc":"2026-09-09T00:00:00Z"}'
    )
    manifest = _manifest_source(
        canonical,
        canonicalization=AI_CANONICALIZATION_V2,
    )
    return ImmutableBytesInputs(canonical, manifest, None), canonical


def _deep_v2_manifest_inputs(structural_depth: int) -> ImmutableBytesInputs:
    canonical = _v2_payload_source()
    array_depth = structural_depth - 1
    assert array_depth >= 1
    nested = b"[" * array_depth + b"null" + b"]" * array_depth
    manifest = _manifest_source(
        canonical,
        canonicalization=AI_CANONICALIZATION_V2,
    )
    manifest = manifest[:-2] + b',"extension":' + nested + b"}\n"
    return ImmutableBytesInputs(canonical, manifest, None)


def _operate(
    inputs: ImmutableBytesInputs | DirectFilesystemInputs | None = None,
    *,
    request: VerifierCapabilityRequest | None = None,
    limit_state: VerifierLimitState | None = None,
    options: AIVerificationOptions | None = None,
) -> VerifierToolResult:
    return verify_bundle_operation(
        inputs or _inputs(),
        capability_request=request or _request(),
        limits=limit_state or _limits(),
        options=options,
    )


def _remediation_child(script: str, *, guard: str, recursion: int = 1000) -> dict:
    """Run real operation code with isolated interpreter settings."""

    environment = os.environ.copy()
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONINTMAXSTRDIGITS=guard,
    )
    program = (
        "import sys, json, hashlib\n"
        "sys.path.insert(0, 'tests')\n"
        "import test_verifier_operation as t\n"
        f"sys.setrecursionlimit({recursion})\n"
        + script
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


_AUXILIARY_INTEGER_PROBE = r'''
out = {}
c = t._v2_payload_source()
m = t._manifest_source(c, canonicalization=t.AI_CANONICALIZATION_V2)
for role in ('keyring', 'trust'):
    for digits in (639, 640, 641, 1000, 4300, 4301):
        token = b'1' * digits
        if role == 'keyring':
            source = t._keyring(m)
            k = source[:-1] + b',"ignored":' + token + b'}'
            inputs = t.ImmutableBytesInputs(c, m, k, None)
        else:
            trust = b'{"signers":' + token + b',"signers":[],"trust_store_format":"aelitium-trust-v1"}'
            inputs = t.ImmutableBytesInputs(c, m, None, trust)
        result = t._operate(inputs, request=t._request(t.V1_LEGACY_UNSUPPORTED))
        v = result.to_json_value()
        op = v['operational_result']
        out[f'{role}/{digits}'] = [v['rc'], op['operational_code'] if op else None,
                                  op['limit']['observed_at_least'] if op and op['limit'] else None]
print(json.dumps(out))
'''


@pytest.mark.parametrize("guard", ["640", "4300", "0"])
def test_unsupported_v1_auxiliary_tokens_use_frozen_profile_under_host_settings(
    guard: str,
) -> None:
    observed = _remediation_child(_AUXILIARY_INTEGER_PROBE, guard=guard)
    for role in ("keyring", "trust"):
        for digits in (639, 640, 641, 1000, 4300, 4301):
            expected = (
                [0, None, None]
                if digits <= 640
                else [3, "INPUT_OUTSIDE_DECLARED_CAPABILITY", digits]
            )
            assert observed[f"{role}/{digits}"] == expected


_NAMED_DIAGNOSTIC_PROBE = r'''
out = {}
c = t._payload_source()
m = t._manifest_source(c)
profile = t.FROZEN_UNICODE_PROFILES[0]
declaration = t.V1CapabilityDeclaration(
    t.V1_NAMED_RUNTIME_COMPATIBILITY,
    t.IntegerConversionDeclaration('UNLIMITED', None),
    t.TimestampDigitProfileDeclaration(profile.profile_id, profile.range_file_sha256, profile.unicode_version),
    t.ACCEPT_ONE_TIMESTAMP_FINAL_LF,
)
request = t._request(declaration=declaration)
token = b'1' * 4301
for role in ('manifest_hash', 'trust_format', 'trust_algorithm', 'invocation_format'):
    mm = m
    trust = None
    cc = c
    if role == 'manifest_hash':
        mm = m.replace(json.dumps(hashlib.sha256(c).hexdigest()).encode(), token)
    elif role == 'trust_format':
        trust = b'{"trust_store_format":' + token + b',"signers":[]}'
    elif role == 'trust_algorithm':
        trust = b'{"trust_store_format":"aelitium-trust-v1","signers":[{"algorithm":' + token + b'}]}'
    else:
        cc = t._payload_source(b'{"invocation_identity":{"format":' + token + b'}}')
        mm = t._manifest_source(cc)
    result = t._operate(t.ImmutableBytesInputs(cc, mm, None, trust), request=request)
    v = result.to_json_value()
    out[role] = [v['rc'], v['verification_result']['reason'] if v['verification_result'] else None,
                 v['operational_result']['operational_code'] if v['operational_result'] else None]
print(json.dumps(out))
'''


@pytest.mark.parametrize("guard", ["640", "4300", "0"])
def test_named_unlimited_invalid_fields_have_bounded_host_independent_diagnostics(
    guard: str,
) -> None:
    observed = _remediation_child(_NAMED_DIAGNOSTIC_PROBE, guard=guard)
    assert observed["manifest_hash"] == [2, "MANIFEST_BAD_AI_HASH_SHA256", None]
    assert observed["trust_format"] == [2, "TRUST_STORE_INVALID", None]
    assert observed["trust_algorithm"] == [2, "TRUST_STORE_INVALID", None]
    assert observed["invocation_format"] == [2, "INVOCATION_BAD_STRUCTURE", None]


_INVOCATION_PROBE = r'''
out = {}
from engine.verifier_capabilities import prepare_verifier_capabilities, select_effective_route
from engine.verifier_v1_capability import parse_v1_json_source, canonical_json_v1_profile
from engine.invocation import parse_invocation_identity
profile = t.FROZEN_UNICODE_PROFILES[0]
declaration = t.V1CapabilityDeclaration(
    t.V1_NAMED_RUNTIME_COMPATIBILITY,
    t.IntegerConversionDeclaration('UNLIMITED', None),
    t.TimestampDigitProfileDeclaration(profile.profile_id, profile.range_file_sha256, profile.unicode_version),
    t.ACCEPT_ONE_TIMESTAMP_FINAL_LF,
)
request_capability = t._request(declaration=declaration)
route = select_effective_route(prepare_verifier_capabilities(request_capability), t.AI_CANONICALIZATION)
for digits in (640, 641, 4300, 4301, 4302):
    token = b'1' * digits
    request = b'{"messages":[' + token + b'],"model":"operation-model"}'
    material = b'{"format":"aelitium-invocation-v1","mode":"sync_non_streaming","request":' + request + b',"surface":"openai.chat.completions"}'
    correct = hashlib.sha256(material).hexdigest().encode()
    for variant in ('correct', 'wrong', 'malformed', 'ignored'):
        fmt = b'"aelitium-invocation-v1"' if variant != 'malformed' else token
        digest = correct if variant != 'wrong' else b'0' * 64
        stored = b'{"format":' + fmt + b',"hash_sha256":"' + digest + b'","mode":"sync_non_streaming","request":' + request + b',"surface":"openai.chat.completions"}'
        metadata = (
            b'{"ignored":' + token + b',"invocation_identity":' + stored + b'}'
            if variant == 'ignored'
            else b'{"invocation_identity":' + stored + b'}'
        )
        c = t._payload_source(metadata)
        m = t._manifest_source(c)
        v = t._operate(t.ImmutableBytesInputs(c, m, None), request=request_capability).to_json_value()
        out[f'{digits}/{variant}'] = [v['rc'], v['verification_result']['reason'] if v['verification_result'] else None]
        if variant == 'correct':
            parsed = parse_v1_json_source(c, route=route, role=t.InputRole.AI_CANONICAL_JSON,
                phase=t.OperationalPhase.CANONICAL_PARSE, input_ref=t.InputRef.AI_CANONICAL_JSON)
            identity = parse_invocation_identity(parsed['metadata']['invocation_identity'],
                canonicalizer=canonical_json_v1_profile, source_route=route)
            assert identity.to_stored_object()['request']['messages'][0] == parsed['metadata']['invocation_identity']['request']['messages'][0]
print(json.dumps(out))
'''


@pytest.mark.parametrize("guard", ["640", "4300", "0"])
def test_invocation_large_integer_hash_and_malformed_paths_are_portable(guard: str) -> None:
    observed = _remediation_child(_INVOCATION_PROBE, guard=guard)
    for digits in (640, 641, 4300, 4301, 4302):
        assert observed[f"{digits}/correct"] == [0, "OK"]
        assert observed[f"{digits}/ignored"] == [0, "OK"]
        assert observed[f"{digits}/wrong"] == [2, "INVOCATION_HASH_MISMATCH"]
        assert observed[f"{digits}/malformed"] == [2, "INVOCATION_BAD_FORMAT"]


_INVOCATION_DEPTH_PROBE = r'''
out = {}
for depth in (990, 1000, 1004, 1023, 1024, 1025, 1500):
    array_depth = depth - 4
    messages = b'[' * array_depth + b'0' + b']' * array_depth
    request = b'{"messages":' + messages + b',"model":"operation-model"}'
    material = b'{"format":"aelitium-invocation-v1","mode":"sync_non_streaming","request":' + request + b',"surface":"openai.chat.completions"}'
    digest = hashlib.sha256(material).hexdigest().encode()
    stored = b'{"format":"aelitium-invocation-v1","hash_sha256":"' + digest + b'","mode":"sync_non_streaming","request":' + request + b',"surface":"openai.chat.completions"}'
    c = t._payload_source(b'{"invocation_identity":' + stored + b'}')
    measured = t.scan_json_limits(c, limits=t.OperationalLimits(max_structural_depth=2000), allow_legacy_constants=True).maximum_structural_depth
    m = t._manifest_source(c)
    v = t._operate(t.ImmutableBytesInputs(c, m, None)).to_json_value()
    out[str(depth)] = [measured, v['rc'], v['operational_result']['operational_code'] if v['operational_result'] else None]
print(json.dumps(out))
'''


@pytest.mark.parametrize("recursion", [700, 3000])
def test_invocation_depth_to_advertised_limit_ignores_python_stack(recursion: int) -> None:
    observed = _remediation_child(_INVOCATION_DEPTH_PROBE, guard="4300", recursion=recursion)
    for depth in (990, 1000, 1004, 1023, 1024):
        assert observed[str(depth)] == [depth, 0, None]
    for depth in (1025, 1500):
        assert observed[str(depth)] == [depth, 3, "RESOURCE_LIMIT_EXCEEDED"]


@pytest.mark.parametrize("role", [
    InputRole.AI_CANONICAL_JSON,
    InputRole.AI_MANIFEST_JSON,
    InputRole.VERIFICATION_KEYS_JSON,
    InputRole.TRUST_STORE,
])
def test_unexpected_snapshot_role_read_is_operational_internal(
    role: InputRole, tmp_path: Path,
) -> None:
    canonical = _v2_payload_source()
    manifest = _manifest_source(canonical, canonicalization=AI_CANONICALIZATION_V2)
    bundle = tmp_path / "bundle"
    _write_inputs(bundle, ImmutableBytesInputs(canonical, manifest, _keyring(manifest)))
    trust_path = tmp_path / "trust.json"
    trust_path.write_bytes(_trust_bytes())
    original = snapshot_runtime._read_held_input

    def defective_read(observed, *, phase):
        if observed.role is role:
            raise RuntimeError("private injected read defect")
        return original(observed, phase=phase)

    with mock.patch.object(snapshot_runtime, "_read_held_input", side_effect=defective_read):
        result = _operate(
            DirectFilesystemInputs(bundle, trust_path if role is InputRole.TRUST_STORE else None)
        )
    value = result.to_json_value()
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == (
        "TRUST_INPUT" if role is InputRole.TRUST_STORE else "BUNDLE_SNAPSHOT"
    )
    assert "private injected read defect" not in serialize_verifier_tool_result(result).decode()


def test_unexpected_low_level_canonical_read_is_role_attributed(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_inputs(bundle, _inputs())
    with mock.patch.object(snapshot_runtime, "_os_read", side_effect=RuntimeError("private low read")):
        result = _operate(DirectFilesystemInputs(bundle))
    value = result.to_json_value()
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "BUNDLE_SNAPSHOT"
    assert value["operational_result"]["input_ref"] == "AI_CANONICAL_JSON"


def test_unexpected_profile_resource_read_is_capability_internal() -> None:
    with mock.patch.object(
        capability_runtime,
        "_read_packaged_profile_bytes",
        side_effect=RuntimeError("private profile defect"),
    ):
        result = _operate(request=_request(V1_NAMED_RUNTIME_COMPATIBILITY))
    value = result.to_json_value()
    assert value["rc"] == 3
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "CAPABILITY_SELECTION"
    assert value["verification_result"] is None


def test_unexpected_result_construction_is_operational_internal() -> None:
    with mock.patch.object(
        operation_runtime,
        "build_verifier_tool_result",
        side_effect=RuntimeError("private result defect"),
    ):
        result = _operate()
    value = result.to_json_value()
    assert value["rc"] == 3
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "SEMANTIC_EVALUATION"
    assert value["verification_result"] is None
    assert "private result defect" not in serialize_verifier_tool_result(result).decode()


def _assert_schema(result: VerifierToolResult) -> dict:
    value = result.to_json_value()
    _validator().validate(value)
    return value


def _current_frozen_tool_result(case_id: str) -> dict:
    expected = copy.deepcopy(
        FROZEN_CASES[case_id]["expected"]["tool_result"]
    )
    signature = {"profile": ED25519_PORTABLE_STRICT_1}
    expected["capability"]["requested"]["signature_verification"] = signature
    if expected["capability"]["effective"] is not None:
        expected["capability"]["effective"]["signature_verification"] = copy.deepcopy(
            signature
        )
    return expected


def _write_inputs(bundle: Path, inputs: ImmutableBytesInputs) -> None:
    bundle.mkdir()
    if inputs.ai_canonical_json is not None:
        (bundle / "ai_canonical.json").write_bytes(inputs.ai_canonical_json)
    if inputs.ai_manifest_json is not None:
        (bundle / "ai_manifest.json").write_bytes(inputs.ai_manifest_json)
    if inputs.verification_keys_json is not None:
        (bundle / "verification_keys.json").write_bytes(
            inputs.verification_keys_json
        )


def test_valid_semantic_outer_result_is_schema_valid_rc_zero() -> None:
    result = _operate()
    value = _assert_schema(result)

    assert isinstance(result, VerifierToolResult)
    assert value["contract"] == VERIFIER_TOOL_RESULT_CONTRACT
    assert value["operation"] == VERIFY_BUNDLE_OPERATION
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 0
    assert value["verification_result"]["status"] == "VALID"
    assert value["verification_result"]["reason"] == "OK"
    assert value["operational_result"] is None


def test_invalid_semantic_outer_result_is_schema_valid_rc_two() -> None:
    inputs = _inputs()
    tampered = inputs.ai_canonical_json.replace(b"operation output", b"tampered output")
    result = _operate(
        ImmutableBytesInputs(
            tampered,
            inputs.ai_manifest_json,
            inputs.verification_keys_json,
        )
    )
    value = _assert_schema(result)

    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["verification_result"]["status"] == "INVALID"
    assert value["verification_result"]["reason"] != "OK"
    assert value["operational_result"] is None


@pytest.mark.parametrize(
    ("inputs", "reason"),
    [
        (_inputs(canonical=b"{"), "CANONICAL_NOT_JSON"),
        (_inputs(manifest=b"{"), "MANIFEST_NOT_JSON"),
    ],
)
def test_malformed_json_sources_remain_semantic_invalid(
    inputs: ImmutableBytesInputs,
    reason: str,
) -> None:
    value = _assert_schema(_operate(inputs))

    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["verification_result"]["status"] == "INVALID"
    assert value["verification_result"]["reason"] == reason
    assert value["operational_result"] is None


def test_unexpected_semantic_exception_is_internal_operational_result() -> None:
    request = _request(V1_FROZEN_LEGACY_COMPATIBILITY)
    limits = _limits()

    with mock.patch.object(
        operation_runtime,
        "verify_ai_snapshot",
        side_effect=RuntimeError("unexpected semantic defect"),
    ):
        result = verify_bundle_operation(
            _inputs(),
            capability_request=request,
            limits=limits,
        )

    value = _assert_schema(result)
    assert value == _current_frozen_tool_result("operation.internal_failure")
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["capability"]["requested"] == project_capability_request(request)
    assert value["capability"]["effective"] == value["capability"]["requested"]
    assert value["limits"] == _current_frozen_tool_result(
        "operation.internal_failure"
    )["limits"]
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INTERNAL_OPERATION_ERROR",
        "phase": "SEMANTIC_EVALUATION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }
    serialized = serialize_verifier_tool_result(result)
    assert serialized == serialize_verifier_tool_result(result)
    assert serialized.endswith(b"\n")
    assert b"unexpected semantic defect" not in serialized


def _assert_inner_defect_is_internal_operation(
    result: VerifierToolResult,
    injected_message: bytes,
) -> None:
    value = _assert_schema(result)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["capability"]["requested"] == value["capability"]["effective"]
    assert value["limits"] == {
        "claimed_envelope": AELITIUM_CLEANROOM_MINIMUM_1,
        "advertised": {
            "max_file_bytes": 65_536,
            "max_total_snapshot_bytes": 262_144,
            "max_structural_depth": 1_024,
            "max_value_occurrences": 65_536,
        },
        "effective": {
            "max_file_bytes": 65_536,
            "max_total_snapshot_bytes": 262_144,
            "max_structural_depth": 1_024,
            "max_value_occurrences": 65_536,
        },
    }
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INTERNAL_OPERATION_ERROR",
        "phase": "SEMANTIC_EVALUATION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }
    serialized = serialize_verifier_tool_result(result)
    assert injected_message not in serialized
    assert serialized.count(b"\n") == 1


def test_unexpected_canonical_parser_exception_reaches_operation_boundary() -> None:
    message = "unexpected canonical parser defect"
    with mock.patch.object(
        ai_verify_runtime,
        "parse_v1_json_source",
        side_effect=RuntimeError(message),
    ):
        result = _operate()

    _assert_inner_defect_is_internal_operation(result, message.encode("ascii"))


def test_unexpected_manifest_parser_exception_reaches_operation_boundary() -> None:
    message = "unexpected manifest parser defect"
    original = ai_verify_runtime.parse_v1_json_source

    def parse_with_manifest_defect(*args, **kwargs):
        if kwargs.get("role") is InputRole.AI_MANIFEST_JSON:
            raise RuntimeError(message)
        return original(*args, **kwargs)

    with mock.patch.object(
        ai_verify_runtime,
        "parse_v1_json_source",
        side_effect=parse_with_manifest_defect,
    ):
        result = _operate()

    _assert_inner_defect_is_internal_operation(result, message.encode("ascii"))


def test_unexpected_signature_verifier_exception_reaches_operation_boundary() -> None:
    message = "unexpected signature verifier defect"
    base = _inputs()
    signed = ImmutableBytesInputs(
        base.ai_canonical_json,
        base.ai_manifest_json,
        _keyring(base.ai_manifest_json),
    )

    with mock.patch.object(
        signing_runtime,
        "verify_manifest_signature_portable_strict_1",
        side_effect=RuntimeError(message),
    ):
        result = _operate(signed)

    _assert_inner_defect_is_internal_operation(result, message.encode("ascii"))


def test_unexpected_trust_parser_exception_reaches_operation_boundary() -> None:
    message = "unexpected trust parser defect"
    with mock.patch.object(
        ai_verify_runtime,
        "_parse_acquired_snapshot_trust",
        side_effect=RuntimeError(message),
    ):
        result = _operate(_inputs(trust=_trust_bytes()))

    _assert_inner_defect_is_internal_operation(result, message.encode("ascii"))


@pytest.mark.parametrize("resource_error", [MemoryError, RecursionError])
def test_semantic_resource_exhaustion_is_not_internal_operation_error(
    resource_error: type[BaseException],
) -> None:
    with mock.patch.object(
        operation_runtime,
        "verify_ai_snapshot",
        side_effect=resource_error("injected semantic resource exhaustion"),
    ):
        value = _assert_schema(_operate())

    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "RESOURCE_EXHAUSTED",
        "phase": "SEMANTIC_EVALUATION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }


@pytest.mark.parametrize(
    "case_id",
    (
        "operation.internal_failure",
        "operation.output_io",
        "resource.exhausted.canonical_parse",
        "resource.exhausted.manifest_parse",
        "resource.exhausted.signature_material",
    ),
)
def test_corpus_authorized_phases_have_typed_outer_projection(case_id: str) -> None:
    expected = FROZEN_CASES[case_id]["expected"]["tool_result"][
        "operational_result"
    ]
    assert expected["limit"] is None
    request = _request()
    failure = OperationalInputFailure(
        OperationalCode(expected["operational_code"]),
        OperationalPhase(expected["phase"]),
        (
            InputRef(expected["input_ref"])
            if expected["input_ref"] is not None
            else None
        ),
        None,
        None,
    )

    result = build_verifier_tool_result(
        input_mode=InputMode.IMMUTABLE_BYTES,
        requested_capability=request,
        effective_capability=request,
        limits=_limits(),
        operational_failure=failure,
    )
    value = _assert_schema(result)

    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == expected


@pytest.mark.parametrize("structural_depth", [1_002, 1_023, 1_024])
def test_v2_canonical_source_executes_declared_deep_envelope(
    structural_depth: int,
) -> None:
    inputs, expected_canonical = _deep_v2_inputs(structural_depth)
    measurement = scan_json_limits(
        expected_canonical,
        limits=DEFAULT_OPERATIONAL_LIMITS,
        allow_legacy_constants=False,
    )
    recursion_limit = sys.getrecursionlimit()

    value = _assert_schema(_operate(inputs))

    assert sys.getrecursionlimit() == recursion_limit
    assert measurement.maximum_structural_depth == structural_depth
    assert measurement.value_occurrences == structural_depth + 6
    assert measurement.value_occurrences < (
        DEFAULT_OPERATIONAL_LIMITS.max_value_occurrences
    )
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 0
    assert value["verification_result"]["reason"] == "OK"
    assert value["verification_result"]["artifact"][
        "canonical_payload_digest"
    ]["value"] == hashlib.sha256(expected_canonical).hexdigest()


def test_v2_canonical_source_maximum_plus_one_uses_declared_limit() -> None:
    inputs, _ = _deep_v2_inputs(1_025)

    value = _assert_schema(_operate(inputs))

    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "RESOURCE_LIMIT_EXCEEDED",
        "phase": "CANONICAL_PARSE",
        "input_ref": "AI_CANONICAL_JSON",
        "limit": {
            "name": "STRUCTURAL_DEPTH",
            "unit": "LEVELS",
            "maximum": 1_024,
            "observed_at_least": 1_025,
        },
        "detail": None,
    }


def test_v2_manifest_executes_at_declared_maximum_depth() -> None:
    inputs = _deep_v2_manifest_inputs(1_024)
    measurement = scan_json_limits(
        inputs.ai_manifest_json,
        limits=DEFAULT_OPERATIONAL_LIMITS,
        allow_legacy_constants=False,
    )

    value = _assert_schema(_operate(inputs))

    assert measurement.maximum_structural_depth == 1_024
    assert measurement.value_occurrences == 1_030
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 0
    assert value["verification_result"]["reason"] == "OK"


def test_v2_deep_canonical_direct_and_immutable_modes_are_equivalent(
    tmp_path: Path,
) -> None:
    inputs, _ = _deep_v2_inputs(1_002)
    bundle = tmp_path / "deep-v2"
    _write_inputs(bundle, inputs)

    immutable = _assert_schema(_operate(inputs))
    direct = _assert_schema(_operate(DirectFilesystemInputs(bundle)))

    assert immutable["input_mode"] == "IMMUTABLE_BYTES"
    assert direct["input_mode"] == "DIRECT_FILESYSTEM"
    assert direct["outcome"] == immutable["outcome"] == "SEMANTIC_RESULT"
    assert direct["rc"] == immutable["rc"] == 0
    assert direct["verification_result"] == immutable["verification_result"]


def test_requested_effective_projection_and_signature_are_deeply_equal() -> None:
    request = _request(V1_FROZEN_LEGACY_COMPATIBILITY)
    value = _assert_schema(_operate(request=request))

    assert value["capability"]["requested"] == project_capability_request(request)
    assert value["capability"]["effective"] == value["capability"]["requested"]
    assert value["capability"]["effective"]["signature_verification"] == {
        "profile": ED25519_PORTABLE_STRICT_1
    }
    assert value["verification_result"]["artifact"]["canonical_ref"].endswith(
        "ai_canonical.json"
    )


def test_v1_and_v2_dispatch_keep_exact_requested_effective_state() -> None:
    request = _request(V1_FROZEN_LEGACY_COMPATIBILITY)
    v1 = _assert_schema(_operate(request=request))
    v2 = _assert_schema(
        _operate(
            _inputs(canonicalization=AI_CANONICALIZATION_V2),
            request=request,
        )
    )

    assert v1["verification_result"]["status"] == "VALID"
    assert v2["verification_result"]["status"] == "VALID"
    assert v1["capability"]["effective"] == v1["capability"]["requested"]
    assert v2["capability"]["effective"] == v2["capability"]["requested"]


def test_v1_unsupported_allows_exact_v2_but_refuses_legacy_after_dispatch() -> None:
    request = _request(V1_LEGACY_UNSUPPORTED)
    v2 = _assert_schema(
        _operate(
            _inputs(canonicalization=AI_CANONICALIZATION_V2),
            request=request,
        )
    )
    v1 = _assert_schema(_operate(request=request))

    assert v2["outcome"] == "SEMANTIC_RESULT"
    assert v2["rc"] == 0
    assert v2["capability"]["effective"] == v2["capability"]["requested"]
    assert v1 == _current_frozen_tool_result(
        "capability.v1_unsupported.after_dispatch"
    )
    assert v1["capability"]["effective"] is None


def test_unavailable_profile_is_operational_before_snapshot_acquisition() -> None:
    request = _request(V1_NAMED_RUNTIME_COMPATIBILITY, named_profile_index=2)
    inputs = DirectFilesystemInputs("/must/not/be/opened")

    with (
        mock.patch.object(
            capability_runtime,
            "_read_packaged_profile_bytes",
            side_effect=FileNotFoundError,
        ),
        mock.patch(
            "engine.verifier_operation.acquire_verifier_snapshot",
            side_effect=AssertionError("snapshot acquisition was reached"),
        ),
    ):
        value = _assert_schema(_operate(inputs, request=request))

    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["capability"]["requested"] == project_capability_request(request)
    assert value["capability"]["effective"] is None
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
        "phase": "CAPABILITY_SELECTION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }


def _rejected_request_scenarios() -> tuple[
    tuple[str, VerifierCapabilityRequest], ...
]:
    profile = FROZEN_UNICODE_PROFILES[2]
    named_unknown = V1CapabilityDeclaration(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        IntegerConversionDeclaration(BOUNDED, 4300),
        TimestampDigitProfileDeclaration(
            "AELITIUM_UCD_ND_FUTURE_1",
            profile.range_file_sha256,
            profile.unicode_version,
        ),
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    named_mismatch = V1CapabilityDeclaration(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        IntegerConversionDeclaration(BOUNDED, 4300),
        TimestampDigitProfileDeclaration(
            profile.profile_id,
            "0" * 64,
            profile.unicode_version,
        ),
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    altered_portable = V1CapabilityDeclaration(
        V1_FROZEN_LEGACY_COMPATIBILITY,
        IntegerConversionDeclaration(BOUNDED, 641),
        ASCII_TIMESTAMP_DIGIT_PROFILE,
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    named_639 = V1CapabilityDeclaration(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        IntegerConversionDeclaration(BOUNDED, 639),
        TimestampDigitProfileDeclaration(
            profile.profile_id,
            profile.range_file_sha256,
            profile.unicode_version,
        ),
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    named_bounded_null = V1CapabilityDeclaration(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        IntegerConversionDeclaration(BOUNDED, None),
        named_639.timestamp_digit_profile,
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    named_unlimited_integer = V1CapabilityDeclaration(
        V1_NAMED_RUNTIME_COMPATIBILITY,
        IntegerConversionDeclaration("UNLIMITED", 640),
        named_639.timestamp_digit_profile,
        ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    )
    return (
        (
            "unknown_dispatch",
            _request(V1_FROZEN_LEGACY_COMPATIBILITY, dispatch="AELITIUM_DISPATCH_FUTURE"),
        ),
        (
            "unknown_v1",
            _request(declaration=V1CapabilityDeclaration("V1_FUTURE")),
        ),
        (
            "unknown_v2",
            _request(V1_FROZEN_LEGACY_COMPATIBILITY, v2="V2_FUTURE"),
        ),
        (
            "unknown_signature",
            _request(
                V1_FROZEN_LEGACY_COMPATIBILITY,
                signature="ED25519_FUTURE",
            ),
        ),
        ("unknown_named_profile", _request(declaration=named_unknown)),
        ("named_metadata_mismatch", _request(declaration=named_mismatch)),
        ("altered_portable", _request(declaration=altered_portable)),
        ("named_639", _request(declaration=named_639)),
        ("bounded_null", _request(declaration=named_bounded_null)),
        ("unlimited_integer", _request(declaration=named_unlimited_integer)),
    )


@pytest.mark.parametrize(
    ("name", "capability_request"),
    _rejected_request_scenarios(),
)
def test_structurally_valid_rejected_requests_are_schema_valid_pre_io_rc_three(
    name: str,
    capability_request: VerifierCapabilityRequest,
) -> None:
    del name
    inputs = DirectFilesystemInputs("/must/not/be-opened")
    with mock.patch(
        "engine.verifier_operation.acquire_verifier_snapshot",
        side_effect=AssertionError("snapshot acquisition was reached"),
    ) as acquire:
        value = _assert_schema(_operate(inputs, request=capability_request))

    assert acquire.call_count == 0
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["capability"]["requested"] == project_capability_request(
        capability_request
    )
    assert value["capability"]["effective"] is None
    assert value["operational_result"] == {
        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
        "phase": "CAPABILITY_SELECTION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }


@pytest.mark.parametrize(
    "capability_request",
    [
        _request(signature="ED25519 FUTURE"),
        _request(declaration=V1CapabilityDeclaration("V1_FUTURE", None, "EXTRA")),
        _request(
            declaration=V1CapabilityDeclaration(
                V1_NAMED_RUNTIME_COMPATIBILITY,
                None,
                None,
                None,
            )
        ),
    ],
)
def test_malformed_programmatic_request_raises_before_operation_result(
    capability_request: VerifierCapabilityRequest,
) -> None:
    with mock.patch(
        "engine.verifier_operation.acquire_verifier_snapshot",
        side_effect=AssertionError("snapshot acquisition was reached"),
    ) as acquire, pytest.raises(CapabilityRequestValidationError):
        _operate(
            DirectFilesystemInputs("/must/not/be-opened"),
            request=capability_request,
        )

    assert acquire.call_count == 0


@pytest.mark.parametrize(
    "case_id",
    [
        "capability.selection.unsupported_v2",
        "capability.selection.unsupported_signature_profile",
        "capability.selection.named_profile_tuple_mismatch",
    ],
)
def test_n2_rejected_request_results_equal_frozen_level3(case_id: str) -> None:
    requests = dict(_rejected_request_scenarios())
    request_by_case = {
        "capability.selection.unsupported_v2": requests["unknown_v2"],
        "capability.selection.unsupported_signature_profile": requests[
            "unknown_signature"
        ],
        "capability.selection.named_profile_tuple_mismatch": requests[
            "named_metadata_mismatch"
        ],
    }

    value = _assert_schema(
        _operate(_inputs(), request=request_by_case[case_id])
    )

    assert value == FROZEN_CASES[case_id]["expected"]["tool_result"]


def test_limit_projection_is_exactly_the_enforced_configuration() -> None:
    effective = OperationalLimits(
        max_file_bytes=200,
        max_total_snapshot_bytes=500,
        max_structural_depth=8,
        max_value_occurrences=32,
    )
    state = _limits(effective=effective, claimed_envelope=None)
    value = _assert_schema(_operate(limit_state=state))

    assert value["limits"] == {
        "claimed_envelope": None,
        "advertised": {
            "max_file_bytes": 65_536,
            "max_total_snapshot_bytes": 262_144,
            "max_structural_depth": 1_024,
            "max_value_occurrences": 65_536,
        },
        "effective": {
            "max_file_bytes": 200,
            "max_total_snapshot_bytes": 500,
            "max_structural_depth": 8,
            "max_value_occurrences": 32,
        },
    }
    assert value["operational_result"]["limit"]["maximum"] == 200
    assert value["operational_result"]["limit"]["observed_at_least"] > 200


def test_limit_state_rejects_divergent_claims_and_effective_above_advertised() -> None:
    low = OperationalLimits(1, 1, 1, 1)
    with pytest.raises(ValueError):
        VerifierLimitState(AELITIUM_CLEANROOM_MINIMUM_1, low, low)
    with pytest.raises(ValueError):
        VerifierLimitState(None, low, DEFAULT_OPERATIONAL_LIMITS)


@pytest.mark.parametrize(
    ("case_id", "inputs"),
    [
        (
            "integer.portable.641",
            _inputs(
                _payload_source(b'{"value":' + b"7" * 641 + b"}"),
            ),
        ),
        (
            "timestamp.portable.non_ascii_nd",
            _inputs(
                manifest=_manifest_source(
                    _payload_source(),
                    timestamp="\u0661026-09-09T00:00:00Z",
                ),
            ),
        ),
        (
            "legacy.restricted.nonfinite.ignored_nan",
            _inputs(manifest=_N1_IGNORED_NAN_MANIFEST),
        ),
        (
            "legacy.restricted.surrogate.ignored_opaque_unmatched_high",
            _inputs(manifest=_N1_IGNORED_SURROGATE_MANIFEST),
        ),
    ],
)
def test_content_capability_outer_results_match_frozen_cases(
    case_id: str,
    inputs: ImmutableBytesInputs,
) -> None:
    value = _assert_schema(_operate(inputs))

    assert value == _current_frozen_tool_result(case_id)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["verification_result"] is None


def test_categorical_integer_and_timestamp_limit_forms_remain_distinct() -> None:
    categorical = _operate(_inputs(manifest=_N1_IGNORED_NAN_MANIFEST)).to_json_value()
    integer = _operate(
        _inputs(_payload_source(b'{"value":' + b"7" * 641 + b"}"))
    ).to_json_value()
    timestamp = _operate(
        _inputs(
            manifest=_manifest_source(
                _payload_source(),
                timestamp="\u0661026-09-09T00:00:00Z",
            )
        )
    ).to_json_value()

    assert categorical["operational_result"]["limit"] is None
    assert integer["operational_result"]["limit"] == {
        "name": "INTEGER_DECIMAL_DIGITS",
        "unit": "DIGITS",
        "maximum": 640,
        "observed_at_least": 641,
    }
    assert timestamp["operational_result"]["limit"] == {
        "name": "TIMESTAMP_DIGIT_PROFILE",
        "unit": "PROFILE",
        "maximum": "ASCII",
        "observed_at_least": "U+0661",
    }


def test_trust_boundaries_remain_semantic_after_stable_acquisition() -> None:
    malformed = _assert_schema(_operate(_inputs(trust=b"{")))
    missing = _assert_schema(
        _operate(
            options=AIVerificationOptions(require_trusted_signer=True),
        )
    )

    assert malformed["rc"] == 2
    assert malformed["verification_result"]["reason"] == "TRUST_STORE_INVALID"
    assert malformed["operational_result"] is None
    assert malformed["verification_result"]["trust_inputs"] == [
        {
            "ref": "verification-input:trust-store",
            "format": TRUST_STORE_FORMAT,
            "source": "explicit_local_file",
        }
    ]
    assert missing["rc"] == 2
    assert missing["verification_result"]["reason"] == "TRUST_INPUT_NOT_PROVIDED"
    assert missing["operational_result"] is None


@pytest.mark.parametrize(
    "inputs",
    [
        DirectFilesystemInputs("/must/not/be-opened"),
        ImmutableBytesInputs(None, None, None),
    ],
)
def test_required_absent_trust_performs_zero_snapshot_acquisition(
    inputs: DirectFilesystemInputs | ImmutableBytesInputs,
) -> None:
    with (
        mock.patch.object(
            operation_runtime,
            "acquire_verifier_snapshot",
            side_effect=AssertionError("snapshot acquisition was reached"),
        ) as snapshot_acquisition,
        mock.patch.object(
            snapshot_runtime,
            "_acquire_trust_path",
            side_effect=AssertionError("trust acquisition was reached"),
        ) as trust_acquisition,
    ):
        value = _assert_schema(
            _operate(
                inputs,
                options=AIVerificationOptions(require_trusted_signer=True),
            )
        )

    assert snapshot_acquisition.call_count == 0
    assert trust_acquisition.call_count == 0
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["verification_result"]["reason"] == "TRUST_INPUT_NOT_PROVIDED"
    assert value["operational_result"] is None


def test_surrogate_manifest_schema_remains_semantic_and_portable() -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical).replace(
        b'"schema":"ai_pack_manifest_v1"',
        b'"schema":"\\ud800"',
    )

    result = _operate(_inputs(canonical, manifest))
    value = _assert_schema(result)
    verification = value["verification_result"]

    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["operational_result"] is None
    assert verification["status"] == "INVALID"
    assert verification["reason"] == "MANIFEST_BAD_SCHEMA"
    assert verification["detail"] is None
    assert {
        item["dimension"]: item["state"]
        for item in verification["assurance"]["dimensions"]
    } == {
        "payload_integrity": "INVALID",
        "binding_field_consistency": "NOT_EVALUATED",
        "invocation_identity_consistency": "NOT_EVALUATED",
        "invocation_binding_consistency": "NOT_EVALUATED",
        "signature_validity": "ABSENT",
        "trusted_signer_identity": "UNESTABLISHED",
        "freshness": "NOT_EVALUATED",
        "authorization": "NOT_EVALUATED",
    }
    encoded = serialize_verifier_tool_result(result)
    assert encoded.endswith(b"\n")
    assert not encoded.endswith(b"\n\n")
    assert json.loads(encoded) == value


def test_outer_freshness_safe_integer_boundaries_round_trip_exactly() -> None:
    reference = "2026-09-09T00:00:00Z"
    for maximum_age in (0, MAX_PORTABLE_INTEGER):
        options = AIVerificationOptions(
            freshness_max_age_seconds=maximum_age,
            freshness_reference_time_utc=reference,
        )
        result = _operate(options=options)
        value = _assert_schema(result)

        assert value["outcome"] == "SEMANTIC_RESULT"
        assert value["rc"] == 0
        assert value["verification_result"]["reason"] == "OK"
        assert value["verification_result"]["policy_inputs"] == [
            {
                "ref": "verification-input:freshness-policy",
                "kind": "declared_time_freshness_v1",
                "maximum_age_seconds": maximum_age,
                "reference_time_utc": reference,
            }
        ]
        round_trip = json.loads(serialize_verifier_tool_result(result))
        assert (
            round_trip["verification_result"]["policy_inputs"][0][
                "maximum_age_seconds"
            ]
            == maximum_age
        )


@pytest.mark.parametrize(
    "options",
    (
        AIVerificationOptions(
            freshness_max_age_seconds=MAX_PORTABLE_INTEGER + 1,
            freshness_reference_time_utc="2026-09-09T00:00:00Z",
        ),
        AIVerificationOptions(
            freshness_max_age_seconds=-1,
            freshness_reference_time_utc="2026-09-09T00:00:00Z",
        ),
        AIVerificationOptions(
            freshness_max_age_seconds=True,
            freshness_reference_time_utc="2026-09-09T00:00:00Z",
        ),
        AIVerificationOptions(
            freshness_max_age_seconds=1.0,
            freshness_reference_time_utc="2026-09-09T00:00:00Z",
        ),
        AIVerificationOptions(
            freshness_max_age_seconds=0,
            freshness_reference_time_utc="not-a-time",
        ),
        AIVerificationOptions(
            freshness_max_age_seconds=0,
            freshness_reference_time_utc="2026-09-09T00:00:00Z\ud800",
        ),
        AIVerificationOptions(validate_manifest_timestamp=1),
        AIVerificationOptions(require_signature=1),
        AIVerificationOptions(require_binding=1),
        AIVerificationOptions(require_trusted_signer=1),
    ),
)
def test_outer_option_validation_rejects_before_capability_and_acquisition(
    options: AIVerificationOptions,
) -> None:
    with (
        mock.patch(
            "engine.verifier_operation.prepare_verifier_capabilities",
            side_effect=AssertionError("capability selection was reached"),
        ),
        mock.patch(
            "engine.verifier_operation.acquire_verifier_snapshot",
            side_effect=AssertionError("snapshot acquisition was reached"),
        ),
        pytest.raises(ValueError),
    ):
        _operate(
            DirectFilesystemInputs("/must/not/be-opened"),
            options=options,
        )


def test_outer_schema_refines_only_embedded_freshness_integer_domain() -> None:
    options = AIVerificationOptions(
        freshness_max_age_seconds=MAX_PORTABLE_INTEGER,
        freshness_reference_time_utc="2026-09-09T00:00:00Z",
    )
    valid = _operate(options=options).to_json_value()
    unsafe = copy.deepcopy(valid)
    unsafe["verification_result"]["policy_inputs"][0][
        "maximum_age_seconds"
    ] = MAX_PORTABLE_INTEGER + 1

    with pytest.raises(ValidationError):
        _validator().validate(unsafe)

    inner = json.loads(
        (SCHEMAS / "verification_result_v1.json").read_text(encoding="utf-8")
    )
    Draft7Validator(inner).validate(unsafe["verification_result"])


def test_final_outer_portability_guard_rejects_unprojected_values() -> None:
    result = _operate()
    verification = result.to_json_value()["verification_result"]
    verification["detail"] = "\ud800"

    with pytest.raises(ResultContractError) as captured:
        VerifierToolResult(
            input_mode=result.input_mode,
            requested_capability=result.requested_capability,
            effective_capability=result.effective_capability,
            limits=result.limits,
            verification_result=verification,
            operational_result=None,
        )

    assert captured.value.reason == "VERIFIER_TOOL_RESULT_NOT_PORTABLE"


def test_malformed_trust_precedes_missing_canonical_in_both_input_modes(
    tmp_path: Path,
) -> None:
    complete = _inputs()
    malformed_trust = b"{"
    immutable_inputs = ImmutableBytesInputs(
        None,
        complete.ai_manifest_json,
        None,
        trust_store=malformed_trust,
    )
    bundle = tmp_path / "missing-canonical"
    _write_inputs(bundle, immutable_inputs)
    trust_path = tmp_path / "malformed-trust.json"
    trust_path.write_bytes(malformed_trust)

    immutable = _assert_schema(_operate(immutable_inputs))
    direct = _assert_schema(
        _operate(DirectFilesystemInputs(bundle, trust_store_path=trust_path))
    )

    for value, input_mode in (
        (immutable, "IMMUTABLE_BYTES"),
        (direct, "DIRECT_FILESYSTEM"),
    ):
        assert value["input_mode"] == input_mode
        assert value["outcome"] == "SEMANTIC_RESULT"
        assert value["rc"] == 2
        assert value["verification_result"]["status"] == "INVALID"
        assert value["verification_result"]["reason"] == "TRUST_STORE_INVALID"
        assert value["operational_result"] is None
        assert value["capability"]["requested"] == value["capability"]["effective"]

    assert direct["verification_result"] == immutable["verification_result"]


def test_strict_signature_valid_invalid_and_trust_membership_results() -> None:
    canonical = _payload_source()
    manifest = _manifest_source(canonical)
    options = AIVerificationOptions(
        require_signature=True,
        require_trusted_signer=True,
    )
    valid = _assert_schema(
        _operate(
            _inputs(
                canonical,
                manifest,
                keyring=_keyring(manifest),
                trust=_trust_bytes(),
            ),
            options=options,
        )
    )
    invalid = _assert_schema(
        _operate(
            _inputs(
                canonical,
                manifest,
                keyring=_keyring(manifest, valid=False),
                trust=_trust_bytes(),
            ),
            options=options,
        )
    )

    assert valid["rc"] == 0
    assert valid["verification_result"]["status"] == "VALID"
    assert invalid["rc"] == 2
    assert invalid["verification_result"]["reason"] == "SIGNATURE_INVALID"
    for value in (valid, invalid):
        assert value["capability"]["requested"]["signature_verification"] == (
            value["capability"]["effective"]["signature_verification"]
        )


def test_direct_acquisition_io_and_non_regular_failures_are_outer_rc_three(
    tmp_path: Path,
) -> None:
    missing = _assert_schema(
        _operate(DirectFilesystemInputs(tmp_path / "missing"))
    )
    bundle = tmp_path / "non-regular"
    bundle.mkdir()
    (bundle / "ai_canonical.json").mkdir()
    non_regular = _assert_schema(_operate(DirectFilesystemInputs(bundle)))

    assert missing["rc"] == 3
    assert missing["operational_result"]["operational_code"] == "INPUT_IO_ERROR"
    assert non_regular["rc"] == 3
    assert non_regular["operational_result"]["operational_code"] == (
        "INPUT_NOT_REGULAR_FILE"
    )
    assert str(tmp_path) not in serialize_verifier_tool_result(
        _operate(DirectFilesystemInputs(tmp_path / "another-missing"))
    ).decode("utf-8")


def test_supplied_trust_acquisition_failure_precedes_missing_canonical(
    tmp_path: Path,
) -> None:
    immutable = _inputs()
    bundle = tmp_path / "bundle-with-missing-trust"
    _write_inputs(bundle, immutable)
    (bundle / "ai_canonical.json").unlink()

    value = _assert_schema(
        _operate(
            DirectFilesystemInputs(
                bundle,
                trust_store_path=tmp_path / "missing-trust.json",
            )
        )
    )

    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INPUT_IO_ERROR",
        "phase": "TRUST_INPUT",
        "input_ref": "TRUST_STORE",
        "limit": None,
        "detail": None,
    }


def test_direct_changed_during_snapshot_is_outer_rc_three(tmp_path: Path) -> None:
    inputs = _inputs()
    bundle = tmp_path / "changed"
    _write_inputs(bundle, inputs)
    manifest_path = bundle / "ai_manifest.json"

    changed = False

    def mutate(point: str, role: InputRole) -> None:
        nonlocal changed
        if (
            not changed
            and point == "INITIAL_OBSERVATION"
            and role is InputRole.AI_MANIFEST_JSON
        ):
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            changed = True

    with mock.patch.object(snapshot_runtime, "_snapshot_hook", side_effect=mutate):
        value = _assert_schema(_operate(DirectFilesystemInputs(bundle)))

    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == (
        "INPUT_CHANGED_DURING_SNAPSHOT"
    )


def test_resource_limit_acquisition_is_outer_rc_three() -> None:
    inputs = _inputs()
    effective = OperationalLimits(
        max_file_bytes=len(inputs.ai_canonical_json) - 1,
        max_total_snapshot_bytes=DEFAULT_OPERATIONAL_LIMITS.max_total_snapshot_bytes,
        max_structural_depth=DEFAULT_OPERATIONAL_LIMITS.max_structural_depth,
        max_value_occurrences=DEFAULT_OPERATIONAL_LIMITS.max_value_occurrences,
    )
    value = _assert_schema(
        _operate(
            inputs,
            limit_state=_limits(effective=effective, claimed_envelope=None),
        )
    )

    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == (
        "RESOURCE_LIMIT_EXCEEDED"
    )
    assert value["operational_result"]["limit"]["name"] == "FILE_BYTES"
    assert value["operational_result"]["limit"]["maximum"] == (
        effective.max_file_bytes
    )


def test_traversal_limit_uses_reported_effective_limit() -> None:
    canonical = b"[[[]]]"
    effective = OperationalLimits(
        max_file_bytes=DEFAULT_OPERATIONAL_LIMITS.max_file_bytes,
        max_total_snapshot_bytes=DEFAULT_OPERATIONAL_LIMITS.max_total_snapshot_bytes,
        max_structural_depth=2,
        max_value_occurrences=DEFAULT_OPERATIONAL_LIMITS.max_value_occurrences,
    )
    value = _assert_schema(
        _operate(
            _inputs(canonical),
            limit_state=_limits(effective=effective, claimed_envelope=None),
        )
    )

    assert value["rc"] == 3
    assert value["operational_result"] == {
        "operational_code": "RESOURCE_LIMIT_EXCEEDED",
        "phase": "CANONICAL_PARSE",
        "input_ref": "AI_CANONICAL_JSON",
        "limit": {
            "name": "STRUCTURAL_DEPTH",
            "unit": "LEVELS",
            "maximum": 2,
            "observed_at_least": 3,
        },
        "detail": None,
    }
    assert value["limits"]["effective"]["max_structural_depth"] == 2


def test_acquisition_memory_exhaustion_uses_existing_typed_mapping(
    tmp_path: Path,
) -> None:
    immutable = _inputs()
    bundle = tmp_path / "resource-exhaustion"
    _write_inputs(bundle, immutable)

    with mock.patch.object(snapshot_runtime, "_os_read", side_effect=MemoryError):
        value = _assert_schema(_operate(DirectFilesystemInputs(bundle)))

    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "RESOURCE_EXHAUSTED",
        "phase": "BUNDLE_SNAPSHOT",
        "input_ref": "AI_CANONICAL_JSON",
        "limit": None,
        "detail": None,
    }


def test_deterministic_serializer_is_rfc8785_plus_exactly_one_lf() -> None:
    for result in (
        _operate(),
        _operate(_inputs(manifest=b"{")),
        _operate(_inputs(manifest=_N1_IGNORED_NAN_MANIFEST)),
        _operate(DirectFilesystemInputs("/deterministic-missing")),
    ):
        first = serialize_verifier_tool_result(result)
        second = serialize_verifier_tool_result(result)
        assert first == second
        assert first == rfc8785.dumps(result.to_json_value()) + b"\n"
        assert first.endswith(b"\n")
        assert not first.endswith(b"\n\n")
        assert not first.startswith(b"\xef\xbb\xbf")
        assert json.loads(first) == result.to_json_value()


def test_same_operation_repeats_to_identical_bytes() -> None:
    scenarios = (
        lambda: _operate(),
        lambda: _operate(_inputs(manifest=b"{")),
        lambda: _operate(_inputs(manifest=_N1_IGNORED_SURROGATE_MANIFEST)),
        lambda: _operate(request=_request(V1_LEGACY_UNSUPPORTED)),
        lambda: _operate(DirectFilesystemInputs("/repeatable-missing")),
    )
    for run in scenarios:
        assert serialize_verifier_tool_result(run()) == serialize_verifier_tool_result(
            run()
        )


def test_direct_and_immutable_results_differ_only_by_input_mode(
    tmp_path: Path,
) -> None:
    immutable_inputs = _inputs()
    bundle = tmp_path / "mode"
    _write_inputs(bundle, immutable_inputs)

    immutable = _assert_schema(_operate(immutable_inputs))
    direct = _assert_schema(_operate(DirectFilesystemInputs(bundle)))
    direct["input_mode"] = InputMode.IMMUTABLE_BYTES.value

    assert direct == immutable


def test_tool_result_dataclass_and_projected_values_are_not_aliases() -> None:
    result = _operate()
    with pytest.raises(FrozenInstanceError):
        result.input_mode = InputMode.DIRECT_FILESYSTEM
    with pytest.raises(TypeError):
        result.verification_result["reason"] = "mutated"

    first = result.to_json_value()
    first["capability"]["requested"]["dispatch"] = "mutated"
    first["verification_result"]["reason"] = "mutated"
    second = result.to_json_value()
    assert second["capability"]["requested"]["dispatch"] == (
        AELITIUM_DISPATCH_JSON_1
    )
    assert second["verification_result"]["reason"] == "OK"


def test_operation_core_covers_lifecycle_and_result_construction_without_baseexception() -> None:
    source = (ROOT / "engine" / "verifier_operation.py").read_text(encoding="utf-8")
    assert "verify_ai_bundle" not in source
    assert "ai_cli" not in source
    assert "except BaseException" not in source
    assert source.count("except Exception:") == 2
    assert "phase = OperationalPhase.CAPABILITY_SELECTION" in source
    assert "snapshot = acquire_verifier_snapshot" in source
    assert "return VerifierToolResult.emergency_operational(" in source

    boundary_start = source.index("verification = verify_ai_snapshot(")
    boundary_end = source.index("\n    return finish(failure=", boundary_start)
    boundary = source[boundary_start:boundary_end]
    assert boundary.index("except OperationalInputFailure") < boundary.index(
        "except (MemoryError, RecursionError)"
    ) < boundary.index("except Exception:")
