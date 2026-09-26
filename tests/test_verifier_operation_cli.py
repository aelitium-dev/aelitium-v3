"""Process and stream transport for capability-qualified verification."""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from unittest import mock

import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource

import engine.ai_cli as cli
import engine.signing as signing_runtime
import engine.verifier_capabilities as capability_runtime
import engine.verifier_operation as operation_runtime
from engine.ai_canonical import canonicalize_ai_output
from engine.ai_contract import (
    AI_CANONICALIZATION_V2,
    AI_MANIFEST_SCHEMA,
    AI_OUTPUT_SCHEMA_VERSION,
)
from engine.result_contracts import (
    ResultContractError,
    serialize_verifier_tool_result,
)
from engine.verifier_capabilities import (
    ED25519_PORTABLE_STRICT_1,
    FROZEN_UNICODE_PROFILES,
    V1_FROZEN_LEGACY_COMPATIBILITY,
    V1_LEGACY_UNSUPPORTED,
    V1_NAMED_RUNTIME_COMPATIBILITY,
    V1_RESTRICTED_PORTABLE,
)
from engine.verifier_operation import verify_bundle_operation
from engine.verifier_snapshot import (
    DirectFilesystemInputs,
    InputRef,
    OperationalCode,
    OperationalInputFailure,
    OperationalPhase,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "engine" / "schemas"
VALID_BUNDLE = ROOT / "conformance" / "fixtures" / "bundles" / "full_a"
SIGNED_VALID_BUNDLE = (
    ROOT / "conformance" / "fixtures" / "bundles" / "signed_valid"
)
INVALID_BUNDLE = (
    ROOT / "conformance" / "fixtures" / "bundles" / "payload_tamper"
)
MINIMUM_LIMITS = {
    "max_file_bytes": 65_536,
    "max_total_snapshot_bytes": 262_144,
    "max_structural_depth": 1_024,
    "max_value_occurrences": 65_536,
}


def _capability(v1: str = V1_FROZEN_LEGACY_COMPATIBILITY) -> dict:
    if v1 == V1_LEGACY_UNSUPPORTED:
        v1_value = {"capability": V1_LEGACY_UNSUPPORTED}
    elif v1 == V1_NAMED_RUNTIME_COMPATIBILITY:
        profile = FROZEN_UNICODE_PROFILES[2]
        v1_value = {
            "capability": V1_NAMED_RUNTIME_COMPATIBILITY,
            "integer_conversion": {
                "mode": "BOUNDED",
                "maximum_decimal_digits": 4_300,
            },
            "timestamp_digit_profile": {
                "profile_id": profile.profile_id,
                "range_file_sha256": profile.range_file_sha256,
                "unicode_version": profile.unicode_version,
            },
            "timestamp_final_lf": "ACCEPT_ONE",
        }
    else:
        v1_value = {
            "capability": v1,
            "integer_conversion": {
                "mode": "BOUNDED",
                "maximum_decimal_digits": 640,
            },
            "timestamp_digit_profile": "ASCII",
            "timestamp_final_lf": "ACCEPT_ONE",
        }
    return {
        "dispatch": "AELITIUM-DISPATCH-JSON-1",
        "v1": v1_value,
        "v2": {"capability": "V2_PORTABLE"},
        "signature_verification": {
            "profile": ED25519_PORTABLE_STRICT_1,
        },
    }


def _configuration(
    v1: str = V1_FROZEN_LEGACY_COMPATIBILITY,
    *,
    capability: dict | None = None,
    limits: dict | None = None,
) -> dict:
    return {
        "capability": capability or _capability(v1),
        "limits": limits
        or {
            "claimed_envelope": "AELITIUM_CLEANROOM_MINIMUM_1",
            "advertised": copy.deepcopy(MINIMUM_LIMITS),
            "effective": copy.deepcopy(MINIMUM_LIMITS),
        },
    }


def _configuration_json(**kwargs) -> str:
    return json.dumps(_configuration(**kwargs), separators=(",", ":"))


def _run(bundle: Path | str, config: str, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.ai_cli",
            "verify-bundle",
            str(bundle),
            "--operation-json",
            config,
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
    )


def _run_raw(*arguments: str):
    return subprocess.run(
        [sys.executable, "-m", "engine.ai_cli", *arguments],
        cwd=ROOT,
        capture_output=True,
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


def _expected(bundle: Path, config: str):
    parsed = cli._parse_operation_config_json(config)
    return verify_bundle_operation(
        DirectFilesystemInputs(bundle),
        capability_request=parsed.capability_request,
        limits=parsed.limits,
    )


def _assert_outer(stdout: bytes) -> dict:
    assert stdout.endswith(b"\n")
    assert not stdout.endswith(b"\n\n")
    value = json.loads(stdout)
    _validator().validate(value)
    return value


def _write_v2_bundle(path: Path) -> Path:
    payload, _ = canonicalize_ai_output(
        {
            "metadata": {},
            "model": "o3b-model",
            "output": "o3b-output",
            "prompt": "o3b-prompt",
            "schema_version": AI_OUTPUT_SCHEMA_VERSION,
            "ts_utc": "2026-09-09T00:00:00Z",
        },
        AI_CANONICALIZATION_V2,
    )
    canonical = payload.encode("utf-8")
    import hashlib

    manifest = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": "2026-09-09T00:00:00Z",
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": AI_CANONICALIZATION_V2,
        "ai_hash_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    path.mkdir()
    (path / "ai_canonical.json").write_bytes(canonical)
    (path / "ai_manifest.json").write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        + b"\n"
    )
    return path


def _write_deep_v2_bundle(path: Path, structural_depth: int) -> Path:
    array_depth = structural_depth - 2
    assert array_depth >= 1
    nested = b"[" * array_depth + b"null" + b"]" * array_depth
    canonical = (
        b'{"metadata":{"deep":'
        + nested
        + b'},"model":"cli-model","output":"cli-output",'
        + b'"prompt":"cli-prompt","schema_version":"ai_output_v1",'
        + b'"ts_utc":"2026-09-09T00:00:00Z"}'
    )
    import hashlib

    manifest = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": "2026-09-09T00:00:00Z",
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": AI_CANONICALIZATION_V2,
        "ai_hash_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    path.mkdir()
    (path / "ai_canonical.json").write_bytes(canonical)
    (path / "ai_manifest.json").write_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        + b"\n"
    )
    return path


def test_operation_json_valid_is_exact_outer_bytes_and_process_rc_zero() -> None:
    config = _configuration_json()
    expected = _expected(VALID_BUNDLE, config)

    completed = _run(VALID_BUNDLE, config)

    assert completed.returncode == 0
    assert completed.stdout == serialize_verifier_tool_result(expected)
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 0
    assert value["verification_result"]["status"] == "VALID"
    assert value["operational_result"] is None


def test_operation_json_invalid_is_exact_outer_bytes_and_process_rc_two() -> None:
    config = _configuration_json()
    expected = _expected(INVALID_BUNDLE, config)

    completed = _run(INVALID_BUNDLE, config)

    assert completed.returncode == 2
    assert completed.stdout == serialize_verifier_tool_result(expected)
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["verification_result"]["status"] == "INVALID"
    assert value["operational_result"] is None


def test_operation_json_cli_dispatcher_maps_unexpected_semantic_exception(
    monkeypatch,
    capfdbinary,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aelitium",
            "verify-bundle",
            str(VALID_BUNDLE),
            "--operation-json",
            _configuration_json(),
        ],
    )

    with mock.patch.object(
        operation_runtime,
        "verify_ai_snapshot",
        side_effect=RuntimeError("unexpected semantic defect"),
    ):
        rc = cli.main()

    captured = capfdbinary.readouterr()
    assert rc == 3
    assert captured.err == b""
    value = _assert_outer(captured.out)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["capability"]["requested"] == _configuration()["capability"]
    assert value["capability"]["effective"] == value["capability"]["requested"]
    assert value["limits"] == _configuration()["limits"]
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INTERNAL_OPERATION_ERROR",
        "phase": "SEMANTIC_EVALUATION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }
    assert captured.out.count(b"\n") == 1
    assert b"Traceback" not in captured.out
    assert b"RuntimeError" not in captured.out
    assert b"unexpected semantic defect" not in captured.out
    assert b'"status":"INVALID"' not in captured.out


def test_operation_json_signed_cli_maps_unexpected_signature_exception(
    monkeypatch,
    capfdbinary,
) -> None:
    message = "unexpected signature verifier defect"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aelitium",
            "verify-bundle",
            str(SIGNED_VALID_BUNDLE),
            "--operation-json",
            _configuration_json(),
        ],
    )

    with mock.patch.object(
        signing_runtime,
        "verify_manifest_signature_portable_strict_1",
        side_effect=RuntimeError(message),
    ):
        rc = cli.main()

    captured = capfdbinary.readouterr()
    assert rc == 3
    assert captured.err == b""
    value = _assert_outer(captured.out)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"] == {
        "operational_code": "INTERNAL_OPERATION_ERROR",
        "phase": "SEMANTIC_EVALUATION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }
    assert captured.out.count(b"\n") == 1
    assert b"Traceback" not in captured.out
    assert b"RuntimeError" not in captured.out
    assert message.encode("ascii") not in captured.out
    assert b'"status":"INVALID"' not in captured.out
    assert b"SIGNATURE_INVALID" not in captured.out


def test_operation_json_malformed_trust_precedes_missing_canonical(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "missing-canonical"
    bundle.mkdir()
    (bundle / "ai_manifest.json").write_bytes(
        (VALID_BUNDLE / "ai_manifest.json").read_bytes()
    )
    trust_path = tmp_path / "malformed-trust.json"
    trust_path.write_bytes(b"{")

    completed = _run(
        bundle,
        _configuration_json(),
        "--trust-store",
        str(trust_path),
    )

    assert completed.returncode == 2
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 2
    assert value["verification_result"]["status"] == "INVALID"
    assert value["verification_result"]["reason"] == "TRUST_STORE_INVALID"
    assert value["operational_result"] is None


def test_operation_json_deep_v2_at_maximum_is_semantic(tmp_path: Path) -> None:
    bundle = _write_deep_v2_bundle(tmp_path / "deep-v2-max", 1_024)

    completed = _run(bundle, _configuration_json())

    assert completed.returncode == 0
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "SEMANTIC_RESULT"
    assert value["rc"] == 0
    assert value["verification_result"]["reason"] == "OK"
    assert value["operational_result"] is None


def test_operation_json_deep_v2_maximum_plus_one_is_limit(
    tmp_path: Path,
) -> None:
    bundle = _write_deep_v2_bundle(tmp_path / "deep-v2-over", 1_025)

    completed = _run(bundle, _configuration_json())

    assert completed.returncode == 3
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
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


def test_operation_json_freshness_maximum_safe_integer_round_trips() -> None:
    maximum_age = 9_007_199_254_740_991
    completed = _run(
        VALID_BUNDLE,
        _configuration_json(),
        "--freshness-max-age-seconds",
        str(maximum_age),
        "--freshness-reference-time-utc",
        "2026-01-15T12:00:00Z",
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["verification_result"]["policy_inputs"][0][
        "maximum_age_seconds"
    ] == maximum_age


@pytest.mark.parametrize(
    "freshness_arguments, expected_fragment",
    (
        (
            (
                "--freshness-max-age-seconds",
                "9007199254740992",
                "--freshness-reference-time-utc",
                "2026-01-15T12:00:00Z",
            ),
            b"freshness_max_age_seconds",
        ),
        (
            (
                "--freshness-max-age-seconds",
                "0",
                "--freshness-reference-time-utc",
                "not-a-time",
            ),
            b"freshness_reference_time_utc",
        ),
    ),
)
def test_operation_json_invalid_outer_freshness_is_rc64_before_bundle_access(
    tmp_path: Path,
    freshness_arguments: tuple[str, ...],
    expected_fragment: bytes,
) -> None:
    missing_bundle = tmp_path / "must-not-be-opened"
    completed = _run(
        missing_bundle,
        _configuration_json(),
        *freshness_arguments,
    )

    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"error:" in completed.stderr
    assert expected_fragment in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_operation_json_operational_is_exact_outer_bytes_and_process_rc_three(
    tmp_path: Path,
) -> None:
    config = _configuration_json()
    missing = tmp_path / "private-host-path" / "missing"
    expected = _expected(missing, config)

    completed = _run(missing, config)

    assert completed.returncode == 3
    assert completed.stdout == serialize_verifier_tool_result(expected)
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["operational_result"]["operational_code"] == "INPUT_IO_ERROR"
    assert str(tmp_path).encode("utf-8") not in completed.stdout


def test_cli_limits_are_both_reported_and_enforced() -> None:
    limits = {
        "claimed_envelope": None,
        "advertised": copy.deepcopy(MINIMUM_LIMITS),
        "effective": {
            **MINIMUM_LIMITS,
            "max_file_bytes": 1,
        },
    }
    completed = _run(VALID_BUNDLE, _configuration_json(limits=limits))
    value = _assert_outer(completed.stdout)

    assert completed.returncode == 3
    assert completed.stderr == b""
    assert value["limits"] == limits
    assert value["operational_result"]["limit"]["maximum"] == 1
    assert value["operational_result"]["limit"]["name"] == "FILE_BYTES"


def test_requested_and_effective_strict_signature_profiles_are_equal() -> None:
    value = _assert_outer(_run(VALID_BUNDLE, _configuration_json()).stdout)

    assert value["capability"]["requested"] == value["capability"]["effective"]
    assert value["capability"]["requested"]["signature_verification"] == {
        "profile": ED25519_PORTABLE_STRICT_1
    }


def test_v1_unsupported_allows_v2_and_refuses_v1(tmp_path: Path) -> None:
    config = _configuration_json(v1=V1_LEGACY_UNSUPPORTED)
    v2_bundle = _write_v2_bundle(tmp_path / "v2")

    v2 = _run(v2_bundle, config)
    v1 = _run(VALID_BUNDLE, config)

    assert v2.returncode == 0
    assert v2.stderr == b""
    v2_value = _assert_outer(v2.stdout)
    assert v2_value["verification_result"]["status"] == "VALID"
    assert v2_value["capability"]["effective"] == (
        v2_value["capability"]["requested"]
    )

    assert v1.returncode == 3
    assert v1.stderr == b""
    v1_value = _assert_outer(v1.stdout)
    assert v1_value["capability"]["effective"] is None
    assert v1_value["operational_result"] == {
        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
        "phase": "DISPATCH",
        "input_ref": "AI_MANIFEST_JSON",
        "limit": None,
        "detail": None,
    }


def test_all_named_integer_forms_are_representable_in_cli_configuration() -> None:
    bounded = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    unlimited = copy.deepcopy(bounded)
    unlimited["capability"]["v1"]["integer_conversion"] = {
        "mode": "UNLIMITED",
        "maximum_decimal_digits": None,
    }

    for value, expected_mode in ((bounded, "BOUNDED"), (unlimited, "UNLIMITED")):
        parsed = cli._parse_operation_config_json(json.dumps(value))
        assert parsed.capability_request.v1.integer_conversion.mode == expected_mode


def _rejected_configuration_cases() -> tuple[tuple[str, dict], ...]:
    unknown_dispatch = _configuration()
    unknown_dispatch["capability"]["dispatch"] = "AELITIUM_DISPATCH_FUTURE"

    unknown_v1 = _configuration()
    unknown_v1["capability"]["v1"] = {"capability": "V1_FUTURE"}

    unknown_v2 = _configuration()
    unknown_v2["capability"]["v2"]["capability"] = "V2_FUTURE"

    unknown_signature = _configuration()
    unknown_signature["capability"]["signature_verification"]["profile"] = (
        "ED25519_FUTURE"
    )

    unknown_named_profile = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    unknown_named_profile["capability"]["v1"]["timestamp_digit_profile"][
        "profile_id"
    ] = "AELITIUM_UCD_ND_FUTURE_1"

    named_metadata_mismatch = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    named_metadata_mismatch["capability"]["v1"]["timestamp_digit_profile"][
        "range_file_sha256"
    ] = "0" * 64

    altered_portable = _configuration()
    altered_portable["capability"]["v1"]["integer_conversion"][
        "maximum_decimal_digits"
    ] = 641

    named_639 = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    named_639["capability"]["v1"]["integer_conversion"][
        "maximum_decimal_digits"
    ] = 639

    bounded_null = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    bounded_null["capability"]["v1"]["integer_conversion"][
        "maximum_decimal_digits"
    ] = None

    unlimited_integer = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    unlimited_integer["capability"]["v1"]["integer_conversion"] = {
        "mode": "UNLIMITED",
        "maximum_decimal_digits": 640,
    }

    return (
        ("unknown_dispatch", unknown_dispatch),
        ("unknown_v1", unknown_v1),
        ("unknown_v2", unknown_v2),
        ("unknown_signature", unknown_signature),
        ("unknown_named_profile", unknown_named_profile),
        ("named_metadata_mismatch", named_metadata_mismatch),
        ("altered_portable", altered_portable),
        ("named_639", named_639),
        ("bounded_null", bounded_null),
        ("unlimited_integer", unlimited_integer),
    )


@pytest.mark.parametrize(("name", "configuration"), _rejected_configuration_cases())
def test_structurally_valid_unsupported_cli_requests_are_pre_io_rc_three(
    name: str,
    configuration: dict,
    tmp_path: Path,
) -> None:
    del name
    missing = tmp_path / "must-not-be-opened"
    completed = _run(missing, json.dumps(configuration))

    assert completed.returncode == 3
    assert completed.stderr == b""
    value = _assert_outer(completed.stdout)
    assert value["outcome"] == "OPERATIONAL_OUTCOME"
    assert value["rc"] == 3
    assert value["verification_result"] is None
    assert value["capability"]["requested"] == configuration["capability"]
    assert value["capability"]["effective"] is None
    assert value["operational_result"] == {
        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
        "phase": "CAPABILITY_SELECTION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }


def _malformed_configuration_values() -> tuple[tuple[str, dict], ...]:
    missing_member = _configuration()
    del missing_member["capability"]["dispatch"]

    extra_member = _configuration()
    extra_member["capability"]["extra"] = "VALUE"

    unknown_v1_subordinate = _configuration()
    unknown_v1_subordinate["capability"]["v1"] = {
        "capability": "V1_FUTURE",
        "future_parameter": "VALUE",
    }

    wrong_primitive = _configuration()
    wrong_primitive["capability"]["v2"]["capability"] = 7

    malformed_identifiers = []
    for index, identifier in enumerate(("", "HAS SPACE", "path/name", "V2_É")):
        value = _configuration()
        value["capability"]["v2"]["capability"] = identifier
        malformed_identifiers.append((f"identifier_{index}", value))

    malformed_signature = _configuration()
    malformed_signature["capability"]["signature_verification"]["profile"] = (
        "ED25519 FUTURE"
    )

    malformed_version = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    malformed_version["capability"]["v1"]["timestamp_digit_profile"][
        "unicode_version"
    ] = "15.0"

    malformed_digest = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    malformed_digest["capability"]["v1"]["timestamp_digit_profile"][
        "range_file_sha256"
    ] = "ABCDEF"

    malformed_integers = []
    for name, maximum in (
        ("negative", -1),
        ("boolean", True),
        ("unsafe", 9_007_199_254_740_992),
    ):
        value = _configuration(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
        value["capability"]["v1"]["integer_conversion"][
            "maximum_decimal_digits"
        ] = maximum
        malformed_integers.append((name, value))

    return (
        ("missing_member", missing_member),
        ("extra_member", extra_member),
        ("unknown_v1_subordinate", unknown_v1_subordinate),
        ("wrong_primitive", wrong_primitive),
        *malformed_identifiers,
        ("malformed_signature", malformed_signature),
        ("malformed_version", malformed_version),
        ("malformed_digest", malformed_digest),
        *malformed_integers,
    )


@pytest.mark.parametrize(("name", "configuration"), _malformed_configuration_values())
def test_malformed_capability_values_are_rc64_without_outer_result(
    name: str,
    configuration: dict,
    tmp_path: Path,
) -> None:
    del name
    completed = _run(tmp_path / "must-not-be-opened", json.dumps(configuration))

    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"error:" in completed.stderr
    assert b"aelitium-verifier-tool-result-v1" not in completed.stderr


def _duplicate_configuration_json(*, nested: bool) -> str:
    source = _configuration_json()
    if nested:
        target = '"v2":{"capability":"V2_PORTABLE"}'
        replacement = (
            '"v2":{"capability":"V2_PORTABLE",'
            '"capability":"V2_FUTURE"}'
        )
    else:
        target = '"dispatch":"AELITIUM-DISPATCH-JSON-1"'
        replacement = (
            '"dispatch":"AELITIUM-DISPATCH-JSON-1",'
            '"dispatch":"AELITIUM_DISPATCH_FUTURE"'
        )
    assert target in source
    return source.replace(target, replacement, 1)


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_capability_members_are_rc64(
    nested: bool,
    tmp_path: Path,
) -> None:
    completed = _run(
        tmp_path / "must-not-be-opened",
        _duplicate_configuration_json(nested=nested),
    )

    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"duplicate member" in completed.stderr


def _deep_malformed_configuration_cases() -> tuple[tuple[str, str], ...]:
    depth = 1_500
    nested_object = '{"x":' * depth + "null" + "}" * depth
    nested_array = "[" * depth + "null" + "]" * depth
    configuration = _configuration_json()

    capability_target = '"v2":{"capability":"V2_PORTABLE"}'
    assert capability_target in configuration
    nested_capability = configuration.replace(
        capability_target,
        '"v2":{"capability":' + nested_object + "}",
        1,
    )

    limit_target = '"max_file_bytes":65536'
    before, after = configuration.rsplit(limit_target, 1)
    nested_limits = before + '"max_file_bytes":' + nested_array + after

    return (
        ("deeply_nested_object", nested_object),
        ("deeply_nested_array", nested_array),
        ("nested_malformed_capability", nested_capability),
        ("nested_malformed_limits", nested_limits),
    )


@pytest.mark.parametrize(("name", "configuration"), _deep_malformed_configuration_cases())
def test_deep_malformed_configuration_is_normal_rc64_diagnostic(
    name: str,
    configuration: str,
    tmp_path: Path,
) -> None:
    del name
    completed = _run(tmp_path / "must-not-be-opened", configuration)

    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"error:" in completed.stderr
    assert b"Traceback" not in completed.stderr
    for exception_name in (
        b"RecursionError",
        b"JSONDecodeError",
        b"ValueError",
        b"TypeError",
    ):
        assert exception_name not in completed.stderr


@pytest.mark.parametrize("depth", [1_000, 2_000, 5_000, 10_000, 20_000])
@pytest.mark.parametrize("shape", ["array", "object", "capability", "limits"])
def test_very_deep_operation_configuration_has_bounded_usage_diagnostic(
    shape: str, depth: int, tmp_path: Path,
) -> None:
    nested_array = "[" * depth + "0" + "]" * depth
    nested_object = '{"x":' * depth + "null" + "}" * depth
    if shape == "array":
        configuration = nested_array
    elif shape == "object":
        configuration = nested_object
    elif shape == "capability":
        configuration = _configuration_json().replace(
            '"v2":{"capability":"V2_PORTABLE"}',
            '"v2":{"capability":' + nested_object + "}",
            1,
        )
    else:
        configuration = _configuration_json().replace(
            '"max_file_bytes":65536',
            '"max_file_bytes":' + nested_array,
            1,
        )
    completed = _run(tmp_path / "not-opened", configuration)
    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"error:" in completed.stderr
    assert b"Traceback" not in completed.stderr
    assert b"RecursionError" not in completed.stderr
    assert b"RuntimeError" not in completed.stderr
    assert b"ValueError" not in completed.stderr


@pytest.mark.parametrize("defect", ["read", "profile"])
def test_machine_cli_pre_semantic_internal_defect_emits_one_result(
    defect: str,
) -> None:
    config = _configuration_json(
        v1=V1_NAMED_RUNTIME_COMPATIBILITY
        if defect == "profile"
        else V1_FROZEN_LEGACY_COMPATIBILITY
    )
    target = (
        "engine.verifier_snapshot._os_read"
        if defect == "read"
        else "engine.verifier_capabilities._read_packaged_profile_bytes"
    )
    program = (
        "import sys\n"
        "from unittest import mock\n"
        "import engine.ai_cli as cli\n"
        "sys.argv = ['aelitium', 'verify-bundle', sys.argv[1], "
        "'--operation-json', sys.argv[2]]\n"
        f"with mock.patch('{target}', side_effect=RuntimeError('private defect text')):\n"
        "    raise SystemExit(cli.main())\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program, str(VALID_BUNDLE), config],
        cwd=ROOT,
        capture_output=True,
    )
    assert completed.returncode == 3
    assert completed.stderr == b""
    assert completed.stdout.count(b"\n") == 1
    assert completed.stdout.endswith(b"\n")
    assert b"private defect text" not in completed.stdout
    assert b"Traceback" not in completed.stdout
    result = json.loads(completed.stdout)
    assert result["verification_result"] is None
    assert result["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert result["operational_result"]["phase"] == (
        "CAPABILITY_SELECTION" if defect == "profile" else "BUNDLE_SNAPSHOT"
    )


def test_operation_configuration_large_integer_diagnostic_is_host_independent() -> None:
    source = _configuration_json().replace(
        '"max_file_bytes":65536', '"max_file_bytes":' + "1" * 4301, 1
    )
    diagnostics = []
    for guard in ("640", "4300", "0"):
        environment = os.environ.copy()
        environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONINTMAXSTRDIGITS=guard)
        completed = subprocess.run(
            [sys.executable, "-m", "engine.ai_cli", "verify-bundle",
             str(VALID_BUNDLE), "--operation-json", source],
            cwd=ROOT,
            env=environment,
            capture_output=True,
        )
        assert completed.returncode == 64
        assert completed.stdout == b""
        assert b"Traceback" not in completed.stderr
        diagnostics.append(completed.stderr)
    assert diagnostics[0] == diagnostics[1] == diagnostics[2]
    assert b"operation configuration integer exceeds portable domain" in diagnostics[0]


def _invalid_configuration_cases() -> tuple[tuple[str, ...], ...]:
    bad_limit = _configuration()
    bad_limit["limits"]["effective"]["max_file_bytes"] = "65536"
    return (
        ("verify-bundle",),
        ("verify-bundle", str(VALID_BUNDLE), "--unknown-flag"),
        ("verify-bundle", str(VALID_BUNDLE), "--operation-json", "{"),
        (
            "verify-bundle",
            str(VALID_BUNDLE),
            "--operation-json",
            json.dumps(bad_limit),
        ),
    )


@pytest.mark.parametrize("arguments", _invalid_configuration_cases())
def test_usage_errors_are_rc64_without_any_result(arguments: tuple[str, ...]) -> None:
    completed = _run_raw(*arguments)

    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"usage: aelitium")
    assert b"error:" in completed.stderr
    assert b"aelitium-verifier-tool-result-v1" not in completed.stderr


def test_known_profile_runtime_unavailability_precedes_bundle_access() -> None:
    parsed = cli._parse_operation_config_json(
        _configuration_json(v1=V1_NAMED_RUNTIME_COMPATIBILITY)
    )
    args = Namespace(
        bundle="/must/not/be-opened",
        operation_json=parsed,
        trust_store=None,
        require_signature=False,
        require_binding=False,
        require_trusted_signer=False,
        freshness_max_age_seconds=None,
        freshness_reference_time_utc=None,
    )
    captured = []

    def emit(result, *, evidence):
        evidence.validate_result(result)
        assert evidence.failure.code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE
        captured.append(result)
        return result.rc

    with (
        mock.patch.object(
            capability_runtime,
            "_read_packaged_profile_bytes",
            side_effect=FileNotFoundError,
        ),
        mock.patch.object(
            operation_runtime,
            "acquire_verifier_snapshot",
            side_effect=AssertionError("bundle acquisition reached"),
        ),
        mock.patch.object(cli, "_emit_operation_json", side_effect=emit),
    ):
        rc = cli.cmd_verify_bundle(args)

    assert rc == 3
    assert len(captured) == 1
    value = captured[0].to_json_value()
    _validator().validate(value)
    assert value["capability"]["effective"] is None
    assert value["operational_result"] == {
        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
        "phase": "CAPABILITY_SELECTION",
        "input_ref": None,
        "limit": None,
        "detail": None,
    }


class _PartialThenBrokenPipe:
    def __init__(self) -> None:
        self.bytes_written = bytearray()
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, data) -> int:
        self.write_calls += 1
        if self.write_calls == 1:
            chunk = bytes(data[:17])
            self.bytes_written.extend(chunk)
            return len(chunk)
        raise BrokenPipeError

    def flush(self) -> None:
        self.flush_calls += 1


class _FlushFailure:
    def __init__(self) -> None:
        self.bytes_written = bytearray()
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, data) -> int:
        self.write_calls += 1
        chunk = bytes(data)
        self.bytes_written.extend(chunk)
        return len(chunk)

    def flush(self) -> None:
        self.flush_calls += 1
        raise OSError


@pytest.mark.parametrize("sink_type", [_PartialThenBrokenPipe, _FlushFailure])
def test_output_failure_has_stable_diagnostic_and_no_second_json(sink_type) -> None:
    result = _expected(VALID_BUNDLE, _configuration_json())
    sink = sink_type()
    stderr = io.BytesIO()

    with mock.patch.object(
        cli,
        "serialize_verifier_tool_result",
        wraps=serialize_verifier_tool_result,
    ) as serializer:
        rc = cli._emit_operation_json(result, stdout=sink, stderr=stderr)

    assert rc == 3
    assert serializer.call_count == 1
    assert sink.write_calls >= 1
    assert stderr.getvalue() == (
        b"AELITIUM_OPERATIONAL OUTPUT_IO_ERROR OUTPUT NONE\n"
    )
    assert sink.bytes_written != serialize_verifier_tool_result(result) * 2
    assert b"Traceback" not in stderr.getvalue()


def test_broken_pipe_before_any_byte_is_output_io_error() -> None:
    class BrokenImmediately:
        def write(self, data) -> int:
            del data
            raise BrokenPipeError

        def flush(self) -> None:
            raise AssertionError("flush cannot follow failed write")

    stderr = io.BytesIO()
    rc = cli._emit_operation_json(
        _expected(VALID_BUNDLE, _configuration_json()),
        stdout=BrokenImmediately(),
        stderr=stderr,
    )

    assert rc == 3
    assert stderr.getvalue() == (
        b"AELITIUM_OPERATIONAL OUTPUT_IO_ERROR OUTPUT NONE\n"
    )


def test_serialization_dependency_failure_uses_narrow_internal_mapping(
    capfd,
) -> None:
    error = ResultContractError(
        "VERIFIER_TOOL_RESULT_SERIALIZATION_UNAVAILABLE",
        "rfc8785 dependency is unavailable",
    )
    configuration = cli._parse_operation_config_json(_configuration_json())
    args = Namespace(
        bundle="must-not-be-opened",
        operation_json=configuration,
        trust_store=None,
        require_signature=False,
        require_binding=False,
        require_trusted_signer=False,
        freshness_max_age_seconds=None,
        freshness_reference_time_utc=None,
    )

    with mock.patch.object(
        cli,
        "_ensure_operation_serializer_available",
        side_effect=error,
    ), mock.patch.object(
        cli,
        "verify_bundle_operation",
        side_effect=AssertionError("bundle acquisition must not start"),
    ) as operation:
        rc = cli.cmd_verify_bundle(args)

    captured = capfd.readouterr()
    assert rc == 3
    assert operation.call_count == 0
    assert captured.err == ""
    assert captured.out.endswith("\n") and captured.out.count("\n") == 1
    result = json.loads(captured.out)
    _validator().validate(result)
    assert result["capability"]["effective"] is None
    assert result["verification_result"] is None
    assert result["operational_result"]["operational_code"] == "INTERNAL_OPERATION_ERROR"
    assert result["operational_result"]["phase"] == "OUTPUT"


@pytest.mark.parametrize(
    ("json_mode", "contract_mode"),
    [(False, False), (True, False), (False, True)],
)
def test_legacy_surfaces_never_counterfeit_operational_semantics(
    json_mode: bool,
    contract_mode: bool,
    capfd,
) -> None:
    failure = OperationalInputFailure(
        OperationalCode.INPUT_IO_ERROR,
        OperationalPhase.BUNDLE_SNAPSHOT,
        InputRef.AI_CANONICAL_JSON,
        None,
        None,
    )
    args = Namespace(
        bundle="ignored",
        operation_json=None,
        json=json_mode,
        contract_json=contract_mode,
        trust_store=None,
        require_signature=False,
        require_binding=False,
        require_trusted_signer=False,
        freshness_max_age_seconds=None,
        freshness_reference_time_utc=None,
    )

    with mock.patch.object(cli, "verify_ai_bundle", side_effect=failure):
        rc = cli.cmd_verify_bundle(args)

    stdout, stderr = capfd.readouterr()
    assert rc == 3
    assert stdout == ""
    assert stderr == (
        "AELITIUM_OPERATIONAL INPUT_IO_ERROR BUNDLE_SNAPSHOT "
        "AI_CANONICAL_JSON\n"
    )
    assert "INVALID" not in stderr
    assert "Traceback" not in stderr


def test_operation_json_help_is_additive_and_help_remains_rc_zero() -> None:
    completed = _run_raw("verify-bundle", "--help")

    assert completed.returncode == 0
    assert b"--operation-json CONFIG_JSON" in completed.stdout
    assert completed.stderr == b""
