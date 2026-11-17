"""Direct regressions for the three Round 2 operation-contract failures."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from unittest import mock

import pytest
import rfc8785
from jsonschema import Draft7Validator
from referencing import Registry, Resource

import engine.ai_cli as cli
import engine.verifier_operation as operation
from engine.ai_verify import AIVerificationOptions
from engine.result_contracts import (
    AELITIUM_CLEANROOM_MINIMUM_1,
    VerifierLimitState,
    serialize_verifier_tool_result,
)
from engine.verifier_emergency_output import serialize_emergency_operation_failure
from engine.verifier_capabilities import (
    DispatchCapabilityDeclaration,
    IntegerConversionDeclaration,
    SignatureVerificationDeclaration,
    V1CapabilityDeclaration,
    V2CapabilityDeclaration,
    VerifierCapabilityRequest,
)
from engine.verifier_snapshot import DirectFilesystemInputs, ImmutableBytesInputs, OperationalLimits


_CANONICAL = (
    b'{"model":"m","output":"o","prompt":"p",'
    b'"schema_version":"ai_output_v1","ts_utc":"2026-01-01T00:00:00Z"}'
)
_SHA256 = hashlib.sha256(_CANONICAL).hexdigest().encode("ascii")
_ROOT = Path(__file__).resolve().parents[1]
_SCHEMAS = _ROOT / "engine" / "schemas"
_INNER = json.loads((_SCHEMAS / "verification_result_v1.json").read_text())
_OUTER = json.loads((_SCHEMAS / "verifier_tool_result_v1.json").read_text())
_VALIDATOR = Draft7Validator(
    _OUTER,
    registry=Registry().with_resource(_INNER["$id"], Resource.from_contents(_INNER)),
)
_LIMITS = OperationalLimits()
_LIMIT_STATE = VerifierLimitState(AELITIUM_CLEANROOM_MINIMUM_1, _LIMITS, _LIMITS)


def _request(
    v1: str = "V1_FROZEN_LEGACY_COMPATIBILITY",
    signature: str = "ED25519_PORTABLE_STRICT_1",
) -> VerifierCapabilityRequest:
    if v1 == "V1_LEGACY_UNSUPPORTED":
        legacy = V1CapabilityDeclaration(v1)
    else:
        legacy = V1CapabilityDeclaration(
            v1, IntegerConversionDeclaration("BOUNDED", 640), "ASCII", "ACCEPT_ONE"
        )
    return VerifierCapabilityRequest(
        DispatchCapabilityDeclaration("AELITIUM-DISPATCH-JSON-1"),
        legacy,
        V2CapabilityDeclaration("V2_PORTABLE"),
        SignatureVerificationDeclaration(signature),
    )


def _inputs(
    *,
    timestamp: bytes = b'"2026-01-01T00:00:00Z"',
    route: bytes = b"json_sorted_keys_no_whitespace_utf8",
    extension: bytes = b"",
    trust_store: bytes | None = None,
) -> ImmutableBytesInputs:
    manifest = (
        b'{"schema":"ai_pack_manifest_v1","input_schema":"ai_output_v1",'
        b'"canonicalization":"' + route + b'","ts_utc":' + timestamp
        + b',"ai_hash_sha256":"' + _SHA256 + b'"' + extension + b"}"
    )
    return ImmutableBytesInputs(_CANONICAL, manifest, None, trust_store)


def _result(
    inputs: ImmutableBytesInputs | None = None,
    *,
    request: VerifierCapabilityRequest | None = None,
    options: AIVerificationOptions | None = None,
):
    return operation.verify_bundle_operation(
        inputs or _inputs(),
        capability_request=request or _request(),
        limits=_LIMIT_STATE,
        options=options,
    )


def _schema_value(result):
    value = json.loads(serialize_verifier_tool_result(result))
    _VALIDATOR.validate(value)
    return value


def _assert_machine_bytes(data: bytes, *, code: str, phase: str):
    assert data.endswith(b"\n") and data.count(b"\n") == 1
    value = json.loads(data)
    _VALIDATOR.validate(value)
    assert value["rc"] == 3
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == code
    assert value["operational_result"]["phase"] == phase
    assert b"Traceback" not in data and b"RuntimeError" not in data
    assert b"injected" not in data
    return value


@pytest.mark.parametrize(
    ("signature", "phase"),
    [("FUTURE", "CAPABILITY_SELECTION"), ("ED25519_PORTABLE_STRICT_1", "DISPATCH")],
)
def test_unsupported_capability_survives_result_construction_defect(
    signature: str, phase: str
):
    request = _request("V1_LEGACY_UNSUPPORTED", signature)
    with mock.patch.object(
        operation, "build_verifier_tool_result", side_effect=RuntimeError("injected defect")
    ):
        result = _result(request=request)
    value = _schema_value(result)
    assert value["capability"]["requested"]["signature_verification"] == {
        "profile": signature
    }
    assert value["capability"]["effective"] is None
    assert value["operational_result"]["operational_code"] == "CAPABILITY_PROFILE_UNAVAILABLE"
    assert value["operational_result"]["phase"] == phase
    assert value["rc"] == 3


def test_established_input_failure_survives_later_builder_defect(tmp_path: Path):
    # The fallback must retain the typed failure already selected by the
    # operation, including its phase and role.
    with mock.patch.object(
        operation, "build_verifier_tool_result", side_effect=RuntimeError("injected defect")
    ):
        result = operation.verify_bundle_operation(
            DirectFilesystemInputs(tmp_path / "absent"),
            capability_request=_request(),
            limits=_LIMIT_STATE,
        )
    value = _schema_value(result)
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == "INPUT_IO_ERROR"
    assert value["operational_result"]["phase"] == "BUNDLE_SNAPSHOT"
    assert value["operational_result"]["input_ref"] == "BUNDLE_DIRECTORY"


def test_supported_capability_builder_defect_is_schema_valid_internal():
    with mock.patch.object(
        operation, "build_verifier_tool_result", side_effect=RuntimeError("injected defect")
    ):
        value = _schema_value(_result())
    assert value["capability"]["effective"] == value["capability"]["requested"]
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "SEMANTIC_EVALUATION"


@pytest.mark.parametrize(
    ("signature", "phase"),
    [("FUTURE", "CAPABILITY_SELECTION"), ("ED25519_PORTABLE_STRICT_1", "DISPATCH")],
)
def test_unsupported_capability_and_later_serializer_defect_remain_closed(
    signature: str, phase: str
):
    result = _result(request=_request("V1_LEGACY_UNSUPPORTED", signature))
    stdout, stderr = io.BytesIO(), io.BytesIO()
    with mock.patch.object(
        cli, "serialize_verifier_tool_result", side_effect=RuntimeError("injected defect")
    ):
        rc = cli._emit_operation_json(result, stdout=stdout, stderr=stderr)
    value = _assert_machine_bytes(
        stdout.getvalue(), code="CAPABILITY_PROFILE_UNAVAILABLE", phase=phase
    )
    assert rc == 3 and stderr.getvalue() == b""
    assert value["capability"]["effective"] is None


@pytest.mark.parametrize(
    "stage", ["value", "capability_projection", "limit_projection", "canonical", "framing"]
)
def test_serializer_lifecycle_defects_have_one_closed_internal_result(stage: str):
    result = _result()
    stdout, stderr = io.BytesIO(), io.BytesIO()
    if stage == "value":
        target = "engine.result_contracts.VerifierToolResult.to_json_value"
    elif stage == "capability_projection":
        target = "engine.result_contracts.project_capability_request"
    elif stage == "limit_projection":
        target = "engine.result_contracts.project_verifier_limit_state"
    elif stage == "canonical":
        target = "rfc8785.dumps"
    else:
        target = "engine.ai_cli.serialize_verifier_tool_result"
    with mock.patch(target, side_effect=RuntimeError("injected defect")):
        rc = cli._emit_operation_json(result, stdout=stdout, stderr=stderr)
    assert rc == 3 and stderr.getvalue() == b""
    _assert_machine_bytes(stdout.getvalue(), code="INTERNAL_OPERATION_ERROR", phase="OUTPUT")


def test_emergency_bytes_are_exact_jcs_for_the_narrow_output_shape():
    data = serialize_emergency_operation_failure(_result())
    assert data == rfc8785.dumps(json.loads(data)) + b"\n"


def test_normal_machine_serialization_is_unchanged():
    result = _result()
    expected = serialize_verifier_tool_result(result)
    stdout, stderr = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, stdout=stdout, stderr=stderr)
    assert rc == 0 and stdout.getvalue() == expected and stderr.getvalue() == b""


def test_unexpected_serializer_preflight_defect_has_closed_machine_result(capfd):
    args = Namespace(
        bundle="must-not-be-opened",
        operation_json=cli._parse_operation_config_json(json.dumps({
            "capability": {
                "dispatch": "AELITIUM-DISPATCH-JSON-1",
                "v1": {"capability": "V1_LEGACY_UNSUPPORTED"},
                "v2": {"capability": "V2_PORTABLE"},
                "signature_verification": {"profile": "ED25519_PORTABLE_STRICT_1"},
            },
            "limits": {
                "claimed_envelope": "AELITIUM_CLEANROOM_MINIMUM_1",
                "advertised": dict(max_file_bytes=65536, max_total_snapshot_bytes=262144,
                                   max_structural_depth=1024, max_value_occurrences=65536),
                "effective": dict(max_file_bytes=65536, max_total_snapshot_bytes=262144,
                                  max_structural_depth=1024, max_value_occurrences=65536),
            },
        })),
    )
    with mock.patch.object(
        cli, "_ensure_operation_serializer_available", side_effect=RuntimeError("injected defect")
    ), mock.patch.object(cli, "verify_bundle_operation") as operation_call:
        rc = cli.cmd_verify_bundle(args)
    output = capfd.readouterr()
    assert rc == 3 and operation_call.call_count == 0
    assert output.err == ""
    value = _assert_machine_bytes(
        output.out.encode("ascii"), code="INTERNAL_OPERATION_ERROR", phase="OUTPUT"
    )
    assert value["capability"]["effective"] is None


@pytest.mark.parametrize(
    ("fault_target", "signature", "code", "phase"),
    [
        (
            "engine.verifier_operation.build_verifier_tool_result",
            "FUTURE",
            "CAPABILITY_PROFILE_UNAVAILABLE",
            "CAPABILITY_SELECTION",
        ),
        (
            "rfc8785.dumps",
            "ED25519_PORTABLE_STRICT_1",
            "INTERNAL_OPERATION_ERROR",
            "OUTPUT",
        ),
    ],
)
def test_real_operation_cli_contains_injected_defects(
    tmp_path: Path, fault_target: str, signature: str, code: str, phase: str
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    inputs = _inputs()
    (bundle / "ai_canonical.json").write_bytes(inputs.ai_canonical_json)
    (bundle / "ai_manifest.json").write_bytes(inputs.ai_manifest_json)
    config = {
        "capability": {
            "dispatch": "AELITIUM-DISPATCH-JSON-1",
            "v1": {"capability": "V1_LEGACY_UNSUPPORTED"}
            if signature == "FUTURE"
            else {
                "capability": "V1_FROZEN_LEGACY_COMPATIBILITY",
                "integer_conversion": {"mode": "BOUNDED", "maximum_decimal_digits": 640},
                "timestamp_digit_profile": "ASCII",
                "timestamp_final_lf": "ACCEPT_ONE",
            },
            "v2": {"capability": "V2_PORTABLE"},
            "signature_verification": {"profile": signature},
        },
        "limits": {
            "claimed_envelope": "AELITIUM_CLEANROOM_MINIMUM_1",
            "advertised": dict(max_file_bytes=65536, max_total_snapshot_bytes=262144,
                               max_structural_depth=1024, max_value_occurrences=65536),
            "effective": dict(max_file_bytes=65536, max_total_snapshot_bytes=262144,
                              max_structural_depth=1024, max_value_occurrences=65536),
        },
    }
    script = (
        "import sys\n"
        "from unittest.mock import patch\n"
        "from engine.ai_cli import main\n"
        f"sys.argv = ['aelitium', 'verify-bundle', {str(bundle)!r}, "
        f"'--operation-json', {json.dumps(config)!r}]\n"
        f"with patch({fault_target!r}, side_effect=RuntimeError('injected private defect')):\n"
        "    raise SystemExit(main())\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
    )
    assert completed.returncode == 3 and completed.stderr == b""
    value = _assert_machine_bytes(completed.stdout, code=code, phase=phase)
    if signature == "FUTURE":
        assert value["capability"]["effective"] is None
    else:
        assert value["capability"]["effective"] == value["capability"]["requested"]


@pytest.mark.parametrize(
    ("error", "code"),
    [(OSError("injected"), "OUTPUT_IO_ERROR"), (RuntimeError("injected"), "INTERNAL_OPERATION_ERROR")],
)
def test_unexpected_stdout_write_does_not_retry_or_leak(error: Exception, code: str):
    stdout, stderr = io.BytesIO(), io.BytesIO()
    with mock.patch.object(cli, "_write_stdout", side_effect=error) as writer:
        rc = cli._emit_operation_json(_result(), stdout=stdout, stderr=stderr)
    assert rc == 3 and writer.call_count == 1 and stdout.getvalue() == b""
    assert stderr.getvalue() == f"AELITIUM_OPERATIONAL {code} OUTPUT NONE\n".encode()


@pytest.mark.parametrize(
    ("timestamp", "validate", "expected"),
    [
        (b'"2026-01-01T00:00:00Z"', True, "OK"),
        (b'"2026-01-01T00:00:00Z"', False, "OK"),
        (b'"\\ud800"', True, "MANIFEST_BAD_TS_UTC"),
        (b'"\\ud800"', False, "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
        (b'"\\udc00"', False, "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
        (b'{"nested":["\\ud800"]}', False, "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
        (b'"\\ufdd0"', True, "MANIFEST_BAD_TS_UTC"),
        (b'"\\ufdd0"', False, "OK"),
    ],
)
def test_restricted_manifest_timestamp_source_domain(
    timestamp: bytes, validate: bool, expected: str
):
    value = _schema_value(
        _result(
            _inputs(timestamp=timestamp),
            request=_request("V1_RESTRICTED_PORTABLE"),
            options=AIVerificationOptions(validate_manifest_timestamp=validate),
        )
    )
    if expected == "INPUT_OUTSIDE_DECLARED_CAPABILITY":
        assert value["verification_result"] is None
        assert value["operational_result"]["operational_code"] == expected
        assert value["operational_result"]["phase"] == "MANIFEST_PARSE"
        assert value["operational_result"]["limit"] is None
    else:
        assert value["verification_result"]["reason"] == expected


@pytest.mark.parametrize("validate", [True, False])
def test_restricted_unknown_opaque_surrogate_is_always_refused(validate: bool):
    value = _schema_value(
        _result(
            _inputs(extension=b',"unknown":{"x":"\\ud800"}'),
            request=_request("V1_RESTRICTED_PORTABLE"),
            options=AIVerificationOptions(validate_manifest_timestamp=validate),
        )
    )
    assert value["operational_result"]["operational_code"] == "INPUT_OUTSIDE_DECLARED_CAPABILITY"


@pytest.mark.parametrize("timestamp", [b'"\\ud800"', b'"\\udc00"', b'{"nested":["\\ud800"]}'])
def test_frozen_legacy_timestamp_compatibility_is_preserved(timestamp: bytes):
    value = _schema_value(
        _result(
            _inputs(timestamp=timestamp),
            options=AIVerificationOptions(validate_manifest_timestamp=False),
        )
    )
    assert value["verification_result"]["reason"] == "OK"


@pytest.mark.parametrize("validate", [True, False])
def test_v2_noncharacter_profile_is_independent_of_timestamp_option(validate: bool):
    value = _schema_value(
        _result(
            _inputs(
                timestamp=b'"2026-01-01T00:00:00Z"',
                route=b"aelitium_jcs_profile_v2",
                extension=b',"unknown":"\\ufdd0"',
            ),
            options=AIVerificationOptions(validate_manifest_timestamp=validate),
        )
    )
    assert value["verification_result"]["reason"] == "MANIFEST_NOT_JSON"


@pytest.mark.parametrize(
    "option",
    [
        AIVerificationOptions(validate_manifest_timestamp=False),
        AIVerificationOptions(validate_manifest_timestamp=False, require_signature=True),
        AIVerificationOptions(validate_manifest_timestamp=False, require_binding=True),
        AIVerificationOptions(validate_manifest_timestamp=False, require_trusted_signer=True),
    ],
)
def test_other_requirements_do_not_hide_restricted_source_refusal(option: AIVerificationOptions):
    trust = b'{"signers":[],"trust_store_format":"aelitium-trust-v1"}'
    value = _schema_value(
        _result(
            _inputs(timestamp=b'"\\ud800"', trust_store=trust),
            request=_request("V1_RESTRICTED_PORTABLE"),
            options=option,
        )
    )
    assert value["operational_result"]["operational_code"] == "INPUT_OUTSIDE_DECLARED_CAPABILITY"
