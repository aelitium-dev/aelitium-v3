"""Capability request preparation and post-dispatch route selection."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
from dataclasses import FrozenInstanceError
from importlib import resources
from pathlib import Path
from unittest import mock

import pytest

import engine.verifier_capabilities as capability_runtime
import engine.verifier_snapshot as snapshot_runtime
from engine.ai_contract import AI_CANONICALIZATION, AI_CANONICALIZATION_V2
from engine.ai_pack import ai_pack_from_obj
from engine.ai_verify import AIVerificationResult, verify_ai_snapshot
from engine.verifier_capabilities import (
    ACCEPT_ONE_TIMESTAMP_FINAL_LF,
    AELITIUM_DISPATCH_JSON_1,
    ASCII_TIMESTAMP_DIGIT_PROFILE,
    BOUNDED,
    CapabilityRequestValidationError,
    ED25519_PORTABLE_STRICT_1,
    FROZEN_UNICODE_PROFILES,
    UNLIMITED,
    V1_FROZEN_LEGACY_COMPATIBILITY,
    V1_LEGACY_UNSUPPORTED,
    V1_NAMED_RUNTIME_COMPATIBILITY,
    V1_RESTRICTED_PORTABLE,
    V2_PORTABLE,
    DispatchCapabilityDeclaration,
    IntegerConversionDeclaration,
    PreparedVerifierCapabilities,
    SignatureVerificationDeclaration,
    TimestampDigitProfileDeclaration,
    V1CapabilityDeclaration,
    V2CapabilityDeclaration,
    VerifierCapabilityRequest,
    parse_unicode_nd_ranges,
    prepare_verifier_capabilities,
    select_effective_route,
    validate_verifier_capability_request,
)
from engine.verifier_snapshot import (
    ImmutableBytesInputs,
    InputRef,
    OperationalCode,
    OperationalInputFailure,
    OperationalPhase,
    acquire_immutable_bytes_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
NORMATIVE_UNICODE = (
    ROOT / "conformance" / "legacy_v1_operational_policy" / "unicode"
)


def _portable_v1(
    capability: str = V1_FROZEN_LEGACY_COMPATIBILITY,
    *,
    maximum_decimal_digits: int = 640,
    timestamp_digit_profile: object = ASCII_TIMESTAMP_DIGIT_PROFILE,
    timestamp_final_lf: str = ACCEPT_ONE_TIMESTAMP_FINAL_LF,
) -> V1CapabilityDeclaration:
    return V1CapabilityDeclaration(
        capability=capability,
        integer_conversion=IntegerConversionDeclaration(
            mode=BOUNDED,
            maximum_decimal_digits=maximum_decimal_digits,
        ),
        timestamp_digit_profile=timestamp_digit_profile,  # type: ignore[arg-type]
        timestamp_final_lf=timestamp_final_lf,
    )


def _named_timestamp(index: int = 0) -> TimestampDigitProfileDeclaration:
    profile = FROZEN_UNICODE_PROFILES[index]
    return TimestampDigitProfileDeclaration(
        profile_id=profile.profile_id,
        range_file_sha256=profile.range_file_sha256,
        unicode_version=profile.unicode_version,
    )


def _named_v1(
    *,
    mode: str = BOUNDED,
    maximum_decimal_digits: int | None = 640,
    timestamp_digit_profile: TimestampDigitProfileDeclaration | None = None,
    timestamp_final_lf: str = ACCEPT_ONE_TIMESTAMP_FINAL_LF,
) -> V1CapabilityDeclaration:
    return V1CapabilityDeclaration(
        capability=V1_NAMED_RUNTIME_COMPATIBILITY,
        integer_conversion=IntegerConversionDeclaration(
            mode=mode,
            maximum_decimal_digits=maximum_decimal_digits,
        ),
        timestamp_digit_profile=timestamp_digit_profile or _named_timestamp(),
        timestamp_final_lf=timestamp_final_lf,
    )


def _request(
    *,
    dispatch: str = AELITIUM_DISPATCH_JSON_1,
    v1: V1CapabilityDeclaration | None = None,
    v2: str = V2_PORTABLE,
    signature: str = ED25519_PORTABLE_STRICT_1,
) -> VerifierCapabilityRequest:
    return VerifierCapabilityRequest(
        dispatch=DispatchCapabilityDeclaration(dispatch),
        v1=v1 or _portable_v1(),
        v2=V2CapabilityDeclaration(v2),
        signature_verification=SignatureVerificationDeclaration(signature),
    )


def _assert_unavailable(
    error: OperationalInputFailure,
    *,
    phase: OperationalPhase = OperationalPhase.CAPABILITY_SELECTION,
    input_ref: InputRef | None = None,
) -> None:
    assert error.operational_code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE
    assert error.phase is phase
    assert error.input_ref is input_ref
    assert error.limit is None
    assert error.detail is None


def _capture_unavailable(call) -> OperationalInputFailure:
    with pytest.raises(OperationalInputFailure) as caught:
        call()
    _assert_unavailable(caught.value)
    return caught.value


def _assert_malformed(call) -> None:
    with pytest.raises(CapabilityRequestValidationError):
        call()


def _payload() -> dict:
    return {
        "metadata": {},
        "model": "capability-test-model",
        "output": "capability output",
        "prompt": "capability prompt",
        "schema_version": "ai_output_v1",
        "ts_utc": "2026-09-09T00:00:00Z",
    }


def _snapshot(canonicalization: str):
    packed = ai_pack_from_obj(_payload(), canonicalization=canonicalization)
    return acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(
            packed.canonical_json.encode("utf-8"),
            (json.dumps(packed.manifest, sort_keys=True) + "\n").encode("utf-8"),
            None,
        )
    )


def test_exact_v2_portable_declaration_is_accepted() -> None:
    prepared = prepare_verifier_capabilities(_request())

    assert prepared.requested.v2 == V2CapabilityDeclaration(V2_PORTABLE)
    assert prepared.signature_verification_profile == ED25519_PORTABLE_STRICT_1


@pytest.mark.parametrize(
    "requested",
    ["V2_UNKNOWN", "v2_portable"],
)
def test_unknown_v2_declaration_is_unavailable(requested: str) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(_request(v2=requested))
    )


@pytest.mark.parametrize("requested", ["V2_PORTABLE ", " V2_PORTABLE", "", "V2/X"])
def test_malformed_v2_identifier_is_request_validation_error(requested: str) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(_request(v2=requested))
    )


@pytest.mark.parametrize(
    "capability",
    [V1_RESTRICTED_PORTABLE, V1_FROZEN_LEGACY_COMPATIBILITY],
)
def test_fixed_portable_v1_declaration_is_accepted(capability: str) -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=_portable_v1(capability))
    )

    assert prepared.requested.v1.capability == capability
    assert prepared.named_timestamp_profile is None


@pytest.mark.parametrize("maximum", [639, 641, 4300])
def test_fixed_portable_v1_altered_integer_limit_is_unavailable(
    maximum: int,
) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_portable_v1(maximum_decimal_digits=maximum))
        )
    )


@pytest.mark.parametrize("maximum", [-1, True, 9_007_199_254_740_992, "640"])
def test_fixed_portable_v1_malformed_integer_is_request_validation_error(
    maximum,
) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(v1=_portable_v1(maximum_decimal_digits=maximum))
        )
    )


@pytest.mark.parametrize("profile", ["ascii", "ND"])
def test_fixed_portable_v1_altered_timestamp_profile_is_unavailable(
    profile: object,
) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_portable_v1(timestamp_digit_profile=profile))
        )
    )


@pytest.mark.parametrize("profile", ["ASCII ", None, "", "ASCII/ND"])
def test_fixed_portable_v1_malformed_timestamp_profile_is_request_validation_error(
    profile: object,
) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(v1=_portable_v1(timestamp_digit_profile=profile))
        )
    )


@pytest.mark.parametrize("final_lf", ["REJECT", "accept_one"])
def test_fixed_portable_v1_altered_final_lf_is_unavailable(
    final_lf: str | None,
) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(
                v1=_portable_v1(
                    timestamp_final_lf=final_lf,  # type: ignore[arg-type]
                )
            )
        )
    )


@pytest.mark.parametrize("final_lf", ["ACCEPT_ONE ", None, "", "ACCEPT/ONE"])
def test_fixed_portable_v1_malformed_final_lf_is_request_validation_error(
    final_lf: str | None,
) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(
                v1=_portable_v1(
                    timestamp_final_lf=final_lf,  # type: ignore[arg-type]
                )
            )
        )
    )


def test_legacy_unsupported_exact_declaration_is_prepared() -> None:
    declaration = V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED)

    prepared = prepare_verifier_capabilities(_request(v1=declaration))

    assert prepared.requested.v1 == declaration
    assert prepared.named_timestamp_profile is None


def test_legacy_unsupported_with_extra_fields_is_malformed() -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(v1=_portable_v1(V1_LEGACY_UNSUPPORTED))
        )
    )


def test_legacy_unsupported_selects_v2_after_exact_v2_dispatch() -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED))
    )

    route = select_effective_route(prepared, AI_CANONICALIZATION_V2)

    assert route.capability == V2_PORTABLE
    assert route.canonicalization_identifier == AI_CANONICALIZATION_V2
    assert route.named_timestamp_profile is None


@pytest.mark.parametrize("dispatched", [AI_CANONICALIZATION, None, "unknown"])
def test_legacy_unsupported_refuses_legacy_or_error_dispatch(
    dispatched: str | None,
) -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED))
    )

    with pytest.raises(OperationalInputFailure) as caught:
        select_effective_route(prepared, dispatched)

    _assert_unavailable(
        caught.value,
        phase=OperationalPhase.DISPATCH,
        input_ref=InputRef.AI_MANIFEST_JSON,
    )


@pytest.mark.parametrize("maximum", [640, 4300, 9_007_199_254_740_991])
def test_named_bounded_integer_declaration_is_accepted(maximum: int) -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=_named_v1(maximum_decimal_digits=maximum))
    )

    assert prepared.requested.v1.integer_conversion == IntegerConversionDeclaration(
        BOUNDED,
        maximum,
    )


@pytest.mark.parametrize("maximum", [0, 639])
def test_named_bounded_integer_declaration_below_supported_floor_is_unavailable(
    maximum: int,
) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(maximum_decimal_digits=maximum))
        )
    )


@pytest.mark.parametrize("maximum", [-1, True, 9_007_199_254_740_992, "640"])
def test_named_bounded_malformed_maximum_is_request_validation_error(maximum) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(maximum_decimal_digits=maximum))
        )
    )


def test_named_unlimited_integer_declaration_is_accepted() -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=_named_v1(mode=UNLIMITED, maximum_decimal_digits=None))
    )

    assert prepared.requested.v1.integer_conversion == IntegerConversionDeclaration(
        UNLIMITED,
        None,
    )


@pytest.mark.parametrize("maximum", [640, 4300])
def test_named_unlimited_requires_null_maximum(maximum: int) -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(
                v1=_named_v1(
                    mode=UNLIMITED,
                    maximum_decimal_digits=maximum,
                )
            )
        )
    )


@pytest.mark.parametrize(
    "declaration",
    [
        V1CapabilityDeclaration(
            capability=V1_NAMED_RUNTIME_COMPATIBILITY,
            integer_conversion=None,
            timestamp_digit_profile=_named_timestamp(),
            timestamp_final_lf=ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        ),
        V1CapabilityDeclaration(
            capability=V1_NAMED_RUNTIME_COMPATIBILITY,
            integer_conversion=IntegerConversionDeclaration(BOUNDED, 640),
            timestamp_digit_profile=None,
            timestamp_final_lf=ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        ),
        V1CapabilityDeclaration(
            capability=V1_NAMED_RUNTIME_COMPATIBILITY,
            integer_conversion=IntegerConversionDeclaration(BOUNDED, 640),
            timestamp_digit_profile=_named_timestamp(),
            timestamp_final_lf=None,
        ),
    ],
)
def test_named_runtime_omitted_component_is_malformed(
    declaration: V1CapabilityDeclaration,
) -> None:
    _assert_malformed(
        lambda: prepare_verifier_capabilities(_request(v1=declaration))
    )


def test_unknown_v1_capability_only_is_unavailable_but_subordinates_are_malformed() -> None:
    unknown = V1CapabilityDeclaration("V1_FUTURE")
    validate_verifier_capability_request(_request(v1=unknown))
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(_request(v1=unknown))
    )

    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(
                v1=V1CapabilityDeclaration(
                    "V1_FUTURE",
                    IntegerConversionDeclaration(BOUNDED, 640),
                )
            )
        )
    )


@pytest.mark.parametrize(
    ("version", "digest"),
    [
        ("13.0", FROZEN_UNICODE_PROFILES[0].range_file_sha256),
        ("v13.0.0", FROZEN_UNICODE_PROFILES[0].range_file_sha256),
        ("13.0.0", "A" * 64),
        ("13.0.0", "0" * 63),
    ],
)
def test_named_profile_malformed_metadata_is_request_validation_error(
    version: str,
    digest: str,
) -> None:
    declaration = TimestampDigitProfileDeclaration(
        FROZEN_UNICODE_PROFILES[0].profile_id,
        digest,
        version,
    )
    _assert_malformed(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(timestamp_digit_profile=declaration))
        )
    )


@pytest.mark.parametrize("profile_index", [0, 1, 2])
def test_each_registered_named_timestamp_profile_authenticates(
    profile_index: int,
) -> None:
    metadata = FROZEN_UNICODE_PROFILES[profile_index]

    prepared = prepare_verifier_capabilities(
        _request(v1=_named_v1(timestamp_digit_profile=_named_timestamp(profile_index)))
    )

    authenticated = prepared.named_timestamp_profile
    assert authenticated is not None
    assert authenticated.metadata == metadata
    assert authenticated.actual_range_file_sha256 == metadata.range_file_sha256
    assert len(authenticated.ranges) == metadata.range_count
    assert sum(end - start + 1 for start, end in authenticated.ranges) == (
        metadata.code_point_count
    )


def test_unknown_named_profile_is_unavailable() -> None:
    unknown = TimestampDigitProfileDeclaration(
        profile_id="AELITIUM_UCD_ND_UNKNOWN",
        range_file_sha256=FROZEN_UNICODE_PROFILES[0].range_file_sha256,
        unicode_version="13.0.0",
    )

    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(timestamp_digit_profile=unknown))
        )
    )


def test_named_profile_wrong_unicode_version_is_unavailable() -> None:
    profile = _named_timestamp()
    wrong = TimestampDigitProfileDeclaration(
        profile_id=profile.profile_id,
        range_file_sha256=profile.range_file_sha256,
        unicode_version="13.0.1",
    )

    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(timestamp_digit_profile=wrong))
        )
    )


def test_named_profile_wrong_declared_digest_is_unavailable() -> None:
    profile = _named_timestamp()
    wrong = TimestampDigitProfileDeclaration(
        profile_id=profile.profile_id,
        range_file_sha256="0" * 64,
        unicode_version=profile.unicode_version,
    )

    _capture_unavailable(
        lambda: prepare_verifier_capabilities(
            _request(v1=_named_v1(timestamp_digit_profile=wrong))
        )
    )


def test_corrupted_packaged_profile_bytes_are_unavailable() -> None:
    with mock.patch.object(
        capability_runtime,
        "_read_packaged_profile_bytes",
        return_value=b"000030..000039\ncorrupt\n",
    ):
        _capture_unavailable(
            lambda: prepare_verifier_capabilities(_request(v1=_named_v1()))
        )


def test_missing_packaged_profile_data_is_unavailable() -> None:
    with mock.patch.object(
        capability_runtime,
        "_read_packaged_profile_bytes",
        side_effect=FileNotFoundError("missing profile"),
    ):
        _capture_unavailable(
            lambda: prepare_verifier_capabilities(_request(v1=_named_v1()))
        )


def test_named_profile_preparation_does_not_import_host_unicodedata() -> None:
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "unicodedata":
            raise AssertionError("host unicodedata must not be consulted")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=guarded_import):
        prepared = prepare_verifier_capabilities(_request(v1=_named_v1()))

    assert prepared.named_timestamp_profile is not None


def test_environment_cannot_select_or_replace_a_named_profile() -> None:
    misleading = {
        "AELITIUM_UNICODE_PROFILE": "host",
        "PYTHONINTMAXSTRDIGITS": "0",
        "LC_ALL": "C",
    }
    with mock.patch.dict(os.environ, misleading, clear=False):
        prepared = prepare_verifier_capabilities(
            _request(v1=_named_v1(timestamp_digit_profile=_named_timestamp(1)))
        )

    assert prepared.named_timestamp_profile is not None
    assert prepared.named_timestamp_profile.metadata.profile_id == (
        "AELITIUM_UCD_ND_14_0_0_1"
    )


@pytest.mark.parametrize("metadata", FROZEN_UNICODE_PROFILES)
def test_production_range_bytes_match_normative_bytes_and_published_digest(
    metadata,
) -> None:
    production = (
        resources.files("engine")
        .joinpath("data", "unicode", metadata.range_file)
        .read_bytes()
    )
    normative = (NORMATIVE_UNICODE / metadata.range_file).read_bytes()

    assert production == normative
    assert hashlib.sha256(production).hexdigest() == metadata.range_file_sha256


def test_packaged_profile_loading_is_independent_of_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prepared = prepare_verifier_capabilities(_request(v1=_named_v1()))

    assert prepared.named_timestamp_profile is not None


def test_range_parser_produces_immutable_inclusive_ranges() -> None:
    parsed = parse_unicode_nd_ranges(b"000030..000039\n000660..000669\n")

    assert parsed == ((0x30, 0x39), (0x660, 0x669))
    assert isinstance(parsed, tuple)
    with pytest.raises(TypeError):
        parsed[0] = (0, 0)  # type: ignore[index]


@pytest.mark.parametrize(
    "source",
    [
        b"",
        b"000030..000039",
        b"000030..000039\r\n",
        b"000030..000039\n000039..000040\n",
        b"000030..000039\n00003A..000040\n",
        b"00003a..00003f\n",
    ],
)
def test_range_parser_rejects_inexact_or_noncanonical_bytes(source: bytes) -> None:
    with pytest.raises(ValueError):
        parse_unicode_nd_ranges(source)


def test_prepared_capability_object_is_deeply_immutable() -> None:
    prepared = prepare_verifier_capabilities(_request(v1=_named_v1()))

    assert isinstance(prepared, PreparedVerifierCapabilities)
    assert prepared.named_timestamp_profile is not None
    with pytest.raises(FrozenInstanceError):
        prepared.named_timestamp_profile = None  # type: ignore[misc]
    with pytest.raises(TypeError):
        prepared.named_timestamp_profile.ranges[0] = (0, 0)  # type: ignore[index]


def test_capability_failure_precedes_bundle_io_and_produces_no_semantic_result() -> None:
    unknown = TimestampDigitProfileDeclaration(
        profile_id="AELITIUM_UCD_ND_UNKNOWN",
        range_file_sha256="0" * 64,
        unicode_version="0.0.0",
    )
    unavailable_request = _request(
        v1=_named_v1(timestamp_digit_profile=unknown)
    )

    with (
        mock.patch("builtins.open", side_effect=AssertionError("bundle opened")),
        mock.patch.object(Path, "exists", side_effect=AssertionError("bundle probed")),
        mock.patch.object(Path, "read_bytes", side_effect=AssertionError("bundle read")),
        mock.patch.object(Path, "read_text", side_effect=AssertionError("bundle read")),
        mock.patch.object(
            snapshot_runtime,
            "acquire_verifier_snapshot",
            side_effect=AssertionError("snapshot acquisition invoked"),
        ),
        pytest.raises(OperationalInputFailure) as caught,
    ):
        prepare_verifier_capabilities(unavailable_request)

    _assert_unavailable(caught.value)
    assert not isinstance(caught.value, AIVerificationResult)


def test_snapshot_v2_dispatch_works_with_legacy_unsupported() -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED))
    )

    result = verify_ai_snapshot(
        _snapshot(AI_CANONICALIZATION_V2),
        capabilities=prepared,
    )

    assert result.valid
    assert result.reason == "OK"
    assert result.manifest["canonicalization"] == AI_CANONICALIZATION_V2


def test_snapshot_legacy_dispatch_refusal_produces_no_semantic_result() -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED))
    )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(
            _snapshot(AI_CANONICALIZATION),
            capabilities=prepared,
        )

    _assert_unavailable(
        caught.value,
        phase=OperationalPhase.DISPATCH,
        input_ref=InputRef.AI_MANIFEST_JSON,
    )
    assert not isinstance(caught.value, AIVerificationResult)


def test_snapshot_dispatch_lookahead_error_reaches_legacy_refusal() -> None:
    prepared = prepare_verifier_capabilities(
        _request(v1=V1CapabilityDeclaration(V1_LEGACY_UNSUPPORTED))
    )
    malformed_manifest = b'{"canonicalization":"aelitium_jcs_profile_v2"'
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(b"{}", malformed_manifest, None)
    )

    with pytest.raises(OperationalInputFailure) as caught:
        verify_ai_snapshot(frozen, capabilities=prepared)

    _assert_unavailable(
        caught.value,
        phase=OperationalPhase.DISPATCH,
        input_ref=InputRef.AI_MANIFEST_JSON,
    )


def test_unknown_dispatch_or_signature_profile_is_unavailable_before_content() -> None:
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(_request(dispatch="DISPATCH"))
    )
    _capture_unavailable(
        lambda: prepare_verifier_capabilities(_request(signature="ED25519"))
    )
