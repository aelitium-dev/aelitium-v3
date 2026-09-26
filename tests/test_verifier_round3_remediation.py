"""Production-path regressions for Round 3 capability and output failures."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
from pathlib import Path
from unittest import mock

import pytest
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
from engine.verifier_capabilities import (
    DispatchCapabilityDeclaration,
    IntegerConversionDeclaration,
    SignatureVerificationDeclaration,
    V1CapabilityDeclaration,
    V2CapabilityDeclaration,
    VerifierCapabilityRequest,
)
from engine.verifier_snapshot import (
    DirectFilesystemInputs,
    ImmutableBytesInputs,
    OperationalLimits,
)


_ROOT = Path(__file__).resolve().parents[1]
_SCHEMAS = _ROOT / "engine" / "schemas"
_INNER = json.loads((_SCHEMAS / "verification_result_v1.json").read_text())
_OUTER = json.loads((_SCHEMAS / "verifier_tool_result_v1.json").read_text())
_VALIDATOR = Draft7Validator(
    _OUTER,
    registry=Registry().with_resource(_INNER["$id"], Resource.from_contents(_INNER)),
)
_CANONICAL = (
    b'{"model":"m","output":"o","prompt":"p",'
    b'"schema_version":"ai_output_v1","ts_utc":"2026-01-01T00:00:00Z"}'
)
_HASH = hashlib.sha256(_CANONICAL).hexdigest().encode("ascii")
_LIMITS = OperationalLimits()
_LIMIT_STATE = VerifierLimitState(AELITIUM_CLEANROOM_MINIMUM_1, _LIMITS, _LIMITS)


def _request(*, v1: str = "V1_FROZEN_LEGACY_COMPATIBILITY", signature: str = "ED25519_PORTABLE_STRICT_1") -> VerifierCapabilityRequest:
    legacy = (
        V1CapabilityDeclaration(v1)
        if v1 == "V1_LEGACY_UNSUPPORTED"
        else V1CapabilityDeclaration(
            v1, IntegerConversionDeclaration("BOUNDED", 640), "ASCII", "ACCEPT_ONE"
        )
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
    extra: bytes = b"",
    route: bytes = b"json_sorted_keys_no_whitespace_utf8",
) -> ImmutableBytesInputs:
    manifest = (
        b'{"schema":"ai_pack_manifest_v1","input_schema":"ai_output_v1",'
        b'"canonicalization":"' + route + b'",'
        b'"ts_utc":' + timestamp + b',"ai_hash_sha256":"' + _HASH + b'"' + extra + b"}"
    )
    return ImmutableBytesInputs(_CANONICAL, manifest, None)


def _operate(inputs=None, *, request=None, options=None, limits=_LIMIT_STATE):
    return operation.verify_bundle_operation(
        inputs if inputs is not None else _inputs(),
        capability_request=request if request is not None else _request(),
        limits=limits,
        options=options,
    )


def _machine(raw: bytes, *, rc: int = 3) -> dict:
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    value = json.loads(raw)
    _VALIDATOR.validate(value)
    assert value["rc"] == rc
    assert b"Traceback" not in raw and b"PRIVATE_AUDIT_EXCEPTION" not in raw
    return value


def _emit(result) -> tuple[int, dict, bytes]:
    stdout, stderr = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, stdout=stdout, stderr=stderr)
    return rc, _machine(stdout.getvalue()), stderr.getvalue()


@pytest.mark.parametrize(
    "timestamp",
    [
        b'{"\\ud800":0}',
        b'{"\\udc00":0}',
        b'[{"nested":{"\\ud800":0}}]',
        b'{"\\ud800":0,"\\ud800":1}',
    ],
)
def test_restricted_timestamp_rejects_reached_surrogate_member_names(timestamp: bytes):
    result = _operate(
        _inputs(timestamp=timestamp),
        request=_request(v1="V1_RESTRICTED_PORTABLE"),
        options=AIVerificationOptions(validate_manifest_timestamp=False),
    )
    value = _machine(serialize_verifier_tool_result(result))
    failure = value["operational_result"]
    assert failure == {
        "operational_code": "INPUT_OUTSIDE_DECLARED_CAPABILITY",
        "phase": "MANIFEST_PARSE",
        "input_ref": "AI_MANIFEST_JSON",
        "limit": None,
        "detail": None,
    }
    assert value["verification_result"] is None


@pytest.mark.parametrize("validate", [True, False])
def test_restricted_unknown_nested_names_are_checked_independently_of_timestamp(validate: bool):
    result = _operate(
        _inputs(extra=b',"unknown":{"nested":[{"\\udc00":0}]}'),
        request=_request(v1="V1_RESTRICTED_PORTABLE"),
        options=AIVerificationOptions(validate_manifest_timestamp=validate),
    )
    value = _machine(serialize_verifier_tool_result(result))
    assert value["operational_result"]["operational_code"] == "INPUT_OUTSIDE_DECLARED_CAPABILITY"


def test_frozen_profile_retains_historical_opaque_timestamp_names():
    result = _operate(
        _inputs(timestamp=b'{"\\ud800":0,"\\udc00":1}'),
        options=AIVerificationOptions(validate_manifest_timestamp=False),
    )
    value = _machine(serialize_verifier_tool_result(result), rc=0)
    assert value["verification_result"]["reason"] == "OK"


@pytest.mark.parametrize("name", [b"\\ud800", b"\\udc00", b"\\ufdd0", b"\\uffff"])
def test_v2_timestamp_option_does_not_hide_prohibited_member_names(name: bytes):
    value = _machine(
        serialize_verifier_tool_result(
            _operate(
                _inputs(
                    route=b"aelitium_jcs_profile_v2",
                    timestamp=b'{"' + name + b'":0}',
                ),
                options=AIVerificationOptions(validate_manifest_timestamp=False),
            )
        ),
        rc=2,
    )
    assert value["verification_result"]["reason"] == "MANIFEST_NOT_JSON"


@pytest.mark.parametrize("signature", ["FUTURE", "ED25519_PORTABLE_STRICT_1"])
def test_preparation_defect_has_no_unprepared_effective_capability(signature: str):
    with mock.patch.object(
        operation, "prepare_verifier_capabilities", side_effect=RuntimeError("PRIVATE_AUDIT_EXCEPTION")
    ):
        value = _machine(serialize_verifier_tool_result(_operate(request=_request(signature=signature))))
    assert value["capability"]["requested"]["signature_verification"]["profile"] == signature
    assert value["capability"]["effective"] is None
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "CAPABILITY_SELECTION"


def test_established_capability_unavailability_keeps_its_code_and_phase():
    value = _machine(serialize_verifier_tool_result(_operate(request=_request(signature="FUTURE"))))
    assert value["capability"]["effective"] is None
    assert value["operational_result"]["operational_code"] == "CAPABILITY_PROFILE_UNAVAILABLE"
    assert value["operational_result"]["phase"] == "CAPABILITY_SELECTION"


def test_invalid_preparation_return_cannot_select_unqualified_parser():
    with mock.patch.object(operation, "prepare_verifier_capabilities", return_value=None), mock.patch.object(operation, "verify_ai_snapshot") as semantic:
        value = _machine(serialize_verifier_tool_result(_operate()))
    assert semantic.call_count == 0
    assert value["capability"]["effective"] is None
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "CAPABILITY_SELECTION"


@pytest.mark.parametrize(
    "target",
    [
        "engine.verifier_operation.build_verifier_tool_result",
        "engine.result_contracts.VerifierToolResult.to_json_value",
        "engine.result_contracts.project_capability_request",
        "engine.result_contracts.project_verifier_limit_state",
    ],
)
def test_result_construction_recovers_without_failed_projection(target: str):
    with mock.patch(target, side_effect=RuntimeError("PRIVATE_AUDIT_EXCEPTION")):
        rc, value, stderr = _emit(_operate())
    assert rc == 3 and stderr == b""
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "SEMANTIC_EVALUATION"
    assert value["capability"]["effective"] == value["capability"]["requested"]


@pytest.mark.parametrize("error", [MemoryError, RecursionError])
def test_result_projection_resource_failure_is_not_internal(error: type[Exception]):
    with mock.patch(
        "engine.result_contracts.VerifierToolResult.to_json_value",
        side_effect=error("PRIVATE_AUDIT_EXCEPTION"),
    ):
        rc, value, stderr = _emit(_operate())
    assert rc == 3 and stderr == b""
    assert value["operational_result"]["operational_code"] == "RESOURCE_EXHAUSTED"
    assert value["operational_result"]["phase"] == "SEMANTIC_EVALUATION"


@pytest.mark.parametrize("target", ["engine.result_contracts.project_operational_result", "engine.result_contracts.VerifierToolResult.to_json_value"])
def test_typed_input_failure_survives_repeated_result_projection_fault(target: str, tmp_path: Path):
    with mock.patch(target, side_effect=RuntimeError("PRIVATE_AUDIT_EXCEPTION")):
        rc, value, stderr = _emit(_operate(DirectFilesystemInputs(tmp_path / "absent")))
    assert rc == 3 and stderr == b""
    assert value["operational_result"]["operational_code"] == "INPUT_IO_ERROR"
    assert value["operational_result"]["phase"] == "BUNDLE_SNAPSHOT"
    assert value["operational_result"]["input_ref"] == "BUNDLE_DIRECTORY"


def test_operational_record_constructor_fault_does_not_repeat_in_fallback(tmp_path: Path):
    with mock.patch(
        "engine.result_contracts.VerifierOperationalResult.__post_init__",
        side_effect=RuntimeError("PRIVATE_AUDIT_EXCEPTION"),
    ):
        rc, value, stderr = _emit(_operate(DirectFilesystemInputs(tmp_path / "absent")))
    assert rc == 3 and stderr == b""
    assert value["operational_result"]["operational_code"] == "INPUT_IO_ERROR"
    assert value["operational_result"]["phase"] == "BUNDLE_SNAPSHOT"


def test_invalid_result_construction_return_is_contained():
    with mock.patch.object(operation, "build_verifier_tool_result", return_value=None):
        rc, value, stderr = _emit(_operate())
    assert rc == 3 and stderr == b""
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"


@pytest.mark.parametrize("kind", ["io", "limit", "restricted", "unavailable"])
@pytest.mark.parametrize("error", [RuntimeError, MemoryError])
def test_late_serializer_fault_keeps_established_typed_failure(kind: str, error: type[Exception], tmp_path: Path):
    if kind == "io":
        result = _operate(DirectFilesystemInputs(tmp_path / "absent"))
    elif kind == "limit":
        limited = VerifierLimitState(None, _LIMITS, OperationalLimits(max_file_bytes=1))
        result = _operate(limits=limited)
    elif kind == "restricted":
        result = _operate(
            _inputs(extra=b',"unknown":NaN'),
            request=_request(v1="V1_RESTRICTED_PORTABLE"),
        )
    else:
        result = _operate(request=_request(signature="FUTURE"))
    original = _machine(serialize_verifier_tool_result(result))
    with mock.patch.object(cli, "serialize_verifier_tool_result", side_effect=error("PRIVATE_AUDIT_EXCEPTION")):
        rc, value, stderr = _emit(result)
    assert rc == 3 and stderr == b""
    assert value["verification_result"] is None
    assert value["operational_result"] == original["operational_result"]
    assert value["capability"] == original["capability"]


@pytest.mark.parametrize("error,code", [(MemoryError, "RESOURCE_EXHAUSTED"), (RecursionError, "RESOURCE_EXHAUSTED"), (RuntimeError, "INTERNAL_OPERATION_ERROR")])
@pytest.mark.parametrize("target", ["engine.result_contracts.VerifierToolResult.to_json_value", "engine.ai_cli.serialize_verifier_tool_result", "rfc8785.dumps"])
def test_output_fault_taxonomy_and_schema(target: str, error: type[Exception], code: str):
    result = _operate()
    with mock.patch(target, side_effect=error("PRIVATE_AUDIT_EXCEPTION")):
        rc, value, stderr = _emit(result)
    assert rc == 3 and stderr == b""
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == code
    assert value["operational_result"]["phase"] == "OUTPUT"
    assert value["operational_result"]["input_ref"] is None
    assert value["operational_result"]["limit"] is None


@pytest.mark.parametrize(
    "malformed_frame",
    [None, b"{}", b"{}\n\n", "{}\n", b"{}\n", b'{"a":1,"a":2}\n', b"NaN\n"],
)
def test_malformed_normal_frame_is_caught_before_stdout_write(malformed_frame):
    with mock.patch.object(cli, "serialize_verifier_tool_result", return_value=malformed_frame):
        rc, value, stderr = _emit(_operate())
    assert rc == 3 and stderr == b""
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert value["operational_result"]["phase"] == "OUTPUT"


def test_nonportable_normal_frame_is_caught_before_stdout_write():
    malformed = serialize_verifier_tool_result(_operate()).replace(
        b'"detail":null', b'"detail":"\\ufdd0"', 1
    )
    assert malformed != serialize_verifier_tool_result(_operate())
    with mock.patch.object(cli, "serialize_verifier_tool_result", return_value=malformed):
        rc, value, stderr = _emit(_operate())
    assert rc == 3 and stderr == b""
    assert value["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"


@pytest.mark.parametrize("error,code", [(RuntimeError, "INTERNAL_OPERATION_ERROR"), (MemoryError, "RESOURCE_EXHAUSTED"), (RecursionError, "RESOURCE_EXHAUSTED")])
def test_preflight_fault_after_machine_mode_has_machine_result(error: type[Exception], code: str, capfd):
    config = cli._parse_operation_config_json(json.dumps({
        "capability": {
            "dispatch": "AELITIUM-DISPATCH-JSON-1",
            "v1": {"capability": "V1_LEGACY_UNSUPPORTED"},
            "v2": {"capability": "V2_PORTABLE"},
            "signature_verification": {"profile": "ED25519_PORTABLE_STRICT_1"},
        },
        "limits": {
            "claimed_envelope": "AELITIUM_CLEANROOM_MINIMUM_1",
            "advertised": dataclasses.asdict(_LIMITS),
            "effective": dataclasses.asdict(_LIMITS),
        },
    }))
    with mock.patch.object(cli, "_ensure_operation_serializer_available", side_effect=error("PRIVATE_AUDIT_EXCEPTION")), mock.patch.object(cli, "verify_bundle_operation") as operation_call:
        rc = cli.cmd_verify_bundle(type("Args", (), {"bundle": "not-opened", "operation_json": config})())
    captured = capfd.readouterr()
    value = _machine(captured.out.encode("ascii"))
    assert rc == 3 and operation_call.call_count == 0 and captured.err == ""
    assert value["capability"]["effective"] is None
    assert value["operational_result"]["operational_code"] == code
    assert value["operational_result"]["phase"] == "OUTPUT"


def test_low_level_read_stack_exhaustion_uses_resource_taxonomy(tmp_path: Path):
    tmp_path.joinpath("ai_canonical.json").write_bytes(_CANONICAL)
    tmp_path.joinpath("ai_manifest.json").write_bytes(_inputs().ai_manifest_json)
    with mock.patch("engine.verifier_snapshot._os_read", side_effect=RecursionError("PRIVATE_AUDIT_EXCEPTION")):
        value = _machine(serialize_verifier_tool_result(_operate(DirectFilesystemInputs(tmp_path))))
    assert value["operational_result"]["operational_code"] == "RESOURCE_EXHAUSTED"
    assert value["operational_result"]["phase"] == "BUNDLE_SNAPSHOT"


def test_emergency_serializer_resource_failure_has_stable_best_effort_diagnostic():
    stdout, stderr = io.BytesIO(), io.BytesIO()
    with mock.patch.object(cli, "serialize_verifier_tool_result", side_effect=RuntimeError("PRIVATE_AUDIT_EXCEPTION")), mock.patch.object(cli, "serialize_emergency_operation_failure", side_effect=MemoryError("PRIVATE_AUDIT_EXCEPTION")):
        rc = cli._emit_operation_json(_operate(), stdout=stdout, stderr=stderr)
    assert rc == 3 and stdout.getvalue() == b""
    assert stderr.getvalue() == b"AELITIUM_OPERATIONAL RESOURCE_EXHAUSTED OUTPUT NONE\n"


@pytest.mark.parametrize("error", [MemoryError, RecursionError])
def test_stdout_resource_failure_has_stable_best_effort_diagnostic(error: type[Exception]):
    stdout, stderr = io.BytesIO(), io.BytesIO()
    with mock.patch.object(cli, "_write_stdout", side_effect=error("PRIVATE_AUDIT_EXCEPTION")):
        rc = cli._emit_operation_json(_operate(), stdout=stdout, stderr=stderr)
    assert rc == 3 and stdout.getvalue() == b""
    assert stderr.getvalue() == b"AELITIUM_OPERATIONAL RESOURCE_EXHAUSTED OUTPUT NONE\n"


def test_new_null_effective_schema_branch_is_limited_to_preselection_failures():
    source = _machine(serialize_verifier_tool_result(_operate(request=_request(signature="FUTURE"))))
    source["operational_result"]["operational_code"] = "INTERNAL_OPERATION_ERROR"
    source["operational_result"]["phase"] = "SEMANTIC_EVALUATION"
    assert not _VALIDATOR.is_valid(source)
    source["operational_result"]["phase"] = "CAPABILITY_SELECTION"
    assert _VALIDATOR.is_valid(source)
    source["capability"]["effective"] = source["capability"]["requested"]
    assert not _VALIDATOR.is_valid(source)
