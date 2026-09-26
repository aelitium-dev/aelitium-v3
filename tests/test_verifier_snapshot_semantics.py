"""Semantic verification over immutable verifier snapshots."""

from __future__ import annotations

import base64
import builtins
import hashlib
import json
import os
from pathlib import Path
from unittest import mock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import engine.ai_verify as ai_verify_runtime
import engine.signing as signing
import engine.verifier_capabilities as verifier_capability_runtime
from engine.ai_contract import AI_CANONICALIZATION, AI_CANONICALIZATION_V2
from engine.ai_pack import ai_pack_from_obj
from engine.ai_verify import (
    AIVerificationOptions,
    AssuranceState,
    verify_ai_bundle,
    verify_ai_snapshot,
)
from engine.canonicalization import canonical_json_for_identifier
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    SURFACE_OPENAI_CHAT_COMPLETIONS,
    build_invocation_identity,
)
from engine.trust import TRUST_STORE_FORMAT, TrustStoreError, load_trust_store_bytes
from engine.verifier_capabilities import (
    ED25519_PORTABLE_STRICT_1,
    CapabilityProfileUnavailable,
)
from engine.verifier_snapshot import (
    DirectFilesystemInputs,
    ImmutableBytesInputs,
    InputRole,
    OperationalInputFailure,
    acquire_direct_filesystem_snapshot,
    acquire_immutable_bytes_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE2_FIXTURES = ROOT / "conformance" / "verifier_contract_phase2" / "fixtures"
PRIVATE_KEY_BYTES = base64.b64decode(
    (ROOT / "tests" / "fixtures" / "ed25519_test_private_key.b64")
    .read_text(encoding="utf-8")
    .strip(),
    validate=True,
)


def _payload(*, metadata: dict | None = None, ts_utc: str = "2026-03-04T00:00:00Z") -> dict:
    return {
        "metadata": metadata or {},
        "model": "snapshot-test-model",
        "output": "snapshot output",
        "prompt": "snapshot prompt",
        "schema_version": "ai_output_v1",
        "ts_utc": ts_utc,
    }


def _write_bundle(
    bundle: Path,
    *,
    payload: dict | None = None,
    canonicalization: str = AI_CANONICALIZATION,
    manifest_extra: dict | None = None,
) -> bytes:
    bundle.mkdir(parents=True, exist_ok=True)
    packed = ai_pack_from_obj(
        payload or _payload(),
        canonicalization=canonicalization,
    )
    (bundle / "ai_canonical.json").write_bytes(
        packed.canonical_json.encode("utf-8") + b"\n"
    )
    manifest = dict(packed.manifest)
    if manifest_extra:
        manifest.update(manifest_extra)
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    (bundle / "ai_manifest.json").write_bytes(manifest_bytes)
    return manifest_bytes


def _private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY_BYTES)


def _sign_bundle(bundle: Path) -> bytes:
    private_key = _private_key()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest_bytes = (bundle / "ai_manifest.json").read_bytes()
    keyring = {
        "keyring_format": "ed25519-v1",
        "keys": [
            {
                "key_id": "snapshot-test-key",
                "public_key_b64": base64.b64encode(public_key).decode("ascii"),
            }
        ],
        "signatures": [
            {
                "key_id": "snapshot-test-key",
                "algorithm": "ed25519",
                "scope": "manifest.json",
                "sig_b64": base64.b64encode(
                    private_key.sign(manifest_bytes)
                ).decode("ascii"),
            }
        ],
    }
    (bundle / "verification_keys.json").write_text(
        json.dumps(keyring, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return public_key


def _trust_bytes(public_keys: list[bytes]) -> bytes:
    return (
        json.dumps(
            {
                "trust_store_format": TRUST_STORE_FORMAT,
                "signers": [
                    {
                        "algorithm": "ed25519",
                        "public_key_b64": base64.b64encode(key).decode("ascii"),
                    }
                    for key in public_keys
                ],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_trust(path: Path, public_keys: list[bytes]) -> Path:
    path.write_bytes(_trust_bytes(public_keys))
    return path


def _assert_direct_snapshot_parity(
    bundle: Path,
    *,
    options: AIVerificationOptions | None = None,
):
    direct = verify_ai_bundle(bundle, options=options)
    trust_path = None if options is None else options.trust_store_path
    frozen = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust_path)
    )
    from_snapshot = verify_ai_snapshot(frozen, options=options)
    assert from_snapshot == direct
    return from_snapshot


def _phase2_snapshot(keyring_name: str = "semantic_keyring_valid.json"):
    return acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(
            (PHASE2_FIXTURES / "semantic_ai_canonical.json").read_bytes(),
            (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes(),
            (PHASE2_FIXTURES / keyring_name).read_bytes(),
        )
    )


def _strict_options(**changes) -> AIVerificationOptions:
    return AIVerificationOptions(
        signature_verification_profile=ED25519_PORTABLE_STRICT_1,
        **changes,
    )


def _prepared_frozen_capabilities():
    capability = verifier_capability_runtime
    request = capability.VerifierCapabilityRequest(
        capability.DispatchCapabilityDeclaration(
            capability.AELITIUM_DISPATCH_JSON_1
        ),
        capability.V1CapabilityDeclaration(
            capability.V1_FROZEN_LEGACY_COMPATIBILITY,
            capability.IntegerConversionDeclaration(capability.BOUNDED, 640),
            capability.ASCII_TIMESTAMP_DIGIT_PROFILE,
            capability.ACCEPT_ONE_TIMESTAMP_FINAL_LF,
        ),
        capability.V2CapabilityDeclaration(capability.V2_PORTABLE),
        capability.SignatureVerificationDeclaration(
            capability.ED25519_PORTABLE_STRICT_1
        ),
    )
    return capability.prepare_verifier_capabilities(request)


def test_v1_valid_unsigned_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "v1"
    _write_bundle(bundle)

    result = _assert_direct_snapshot_parity(bundle)

    assert result.valid
    assert result.reason == "OK"
    assert result.manifest["canonicalization"] == AI_CANONICALIZATION
    assert result.signature_validity is AssuranceState.ABSENT


def test_v2_valid_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "v2"
    _write_bundle(bundle, canonicalization=AI_CANONICALIZATION_V2)

    result = _assert_direct_snapshot_parity(bundle)

    assert result.valid
    assert result.reason == "OK"
    assert result.manifest["canonicalization"] == AI_CANONICALIZATION_V2


def test_valid_signed_bundle_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "signed"
    _write_bundle(bundle)
    _sign_bundle(bundle)

    result = _assert_direct_snapshot_parity(bundle)

    assert result.valid
    assert result.signature_validity is AssuranceState.VALID


def test_input_mode_does_not_change_semantic_result(tmp_path: Path) -> None:
    bundle = tmp_path / "mode-equivalence"
    _write_bundle(bundle)
    direct = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    immutable = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(
            direct.bytes_for(InputRole.AI_CANONICAL_JSON),
            direct.bytes_for(InputRole.AI_MANIFEST_JSON),
            direct.bytes_for(InputRole.VERIFICATION_KEYS_JSON),
            trust_store=direct.bytes_for(InputRole.TRUST_STORE),
        )
    )

    assert verify_ai_snapshot(direct) == verify_ai_snapshot(immutable)


def test_payload_tamper_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "tampered"
    _write_bundle(bundle)
    canonical = json.loads((bundle / "ai_canonical.json").read_text(encoding="utf-8"))
    canonical["output"] = "tampered"
    (bundle / "ai_canonical.json").write_text(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    result = _assert_direct_snapshot_parity(bundle)

    assert not result.valid
    assert result.reason == "HASH_MISMATCH"


def test_malformed_manifest_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "malformed-manifest"
    _write_bundle(bundle)
    (bundle / "ai_manifest.json").write_bytes(b'{"schema":')

    result = _assert_direct_snapshot_parity(bundle)

    assert not result.valid
    assert result.reason == "MANIFEST_NOT_JSON"


def test_missing_canonical_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "missing-canonical"
    _write_bundle(bundle)
    (bundle / "ai_canonical.json").unlink()

    result = _assert_direct_snapshot_parity(bundle)

    assert result.reason == "MISSING_CANONICAL"
    assert result.payload_integrity is AssuranceState.ABSENT


def test_missing_manifest_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "missing-manifest"
    _write_bundle(bundle)
    (bundle / "ai_manifest.json").unlink()

    result = _assert_direct_snapshot_parity(bundle)

    assert result.reason == "MISSING_MANIFEST"
    assert result.payload_integrity is AssuranceState.ABSENT


def test_absent_keyring_required_signature_direct_snapshot_parity(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "missing-keyring"
    _write_bundle(bundle)

    result = _assert_direct_snapshot_parity(
        bundle,
        options=AIVerificationOptions(require_signature=True),
    )

    assert result.reason == "SIGNATURE_REQUIRED"
    assert result.signature_validity is AssuranceState.ABSENT


def test_invalid_signature_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "invalid-signature"
    _write_bundle(bundle)
    _sign_bundle(bundle)
    keyring_path = bundle / "verification_keys.json"
    keyring = json.loads(keyring_path.read_text(encoding="utf-8"))
    signature = bytearray(base64.b64decode(keyring["signatures"][0]["sig_b64"]))
    signature[0] ^= 1
    keyring["signatures"][0]["sig_b64"] = base64.b64encode(signature).decode("ascii")
    keyring_path.write_text(json.dumps(keyring), encoding="utf-8")

    result = _assert_direct_snapshot_parity(bundle)

    assert result.reason == "SIGNATURE_INVALID"
    assert result.signature_validity is AssuranceState.INVALID


def test_binding_semantics_direct_snapshot_parity(tmp_path: Path) -> None:
    request_hash = "1" * 64
    response_hash = "2" * 64
    binding_payload = canonical_json_for_identifier(
        {"request_hash": request_hash, "response_hash": response_hash},
        AI_CANONICALIZATION,
    )
    binding_hash = hashlib.sha256(binding_payload.encode("utf-8")).hexdigest()
    metadata = {
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
    }
    bundle = tmp_path / "binding"
    _write_bundle(
        bundle,
        payload=_payload(metadata=metadata),
        manifest_extra={"binding_hash": binding_hash},
    )

    result = _assert_direct_snapshot_parity(bundle)

    assert result.valid
    assert result.binding_field_consistency is AssuranceState.VALID


def test_invocation_semantics_direct_snapshot_parity(tmp_path: Path) -> None:
    identity = build_invocation_identity(
        surface=SURFACE_OPENAI_CHAT_COMPLETIONS,
        mode=MODE_SYNC_NON_STREAMING,
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    ).to_stored_object()
    bundle = tmp_path / "invocation"
    _write_bundle(bundle, payload=_payload(metadata={"invocation_identity": identity}))

    result = _assert_direct_snapshot_parity(bundle)

    assert result.valid
    assert result.invocation_identity_consistency is AssuranceState.VALID


def test_freshness_semantics_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "freshness"
    _write_bundle(bundle, payload=_payload(ts_utc="2026-03-04T00:00:00Z"))
    options = AIVerificationOptions(
        freshness_max_age_seconds=60,
        freshness_reference_time_utc="2026-03-04T00:00:30Z",
    )

    result = _assert_direct_snapshot_parity(bundle, options=options)

    assert result.valid
    assert result.freshness is AssuranceState.VALID


def test_matching_trust_with_strict_signature_direct_snapshot_parity(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "matching-trust"
    _write_bundle(bundle)
    public_key = _sign_bundle(bundle)
    trust_path = _write_trust(tmp_path / "matching-trust.json", [public_key])
    options = _strict_options(
        trust_store_path=trust_path,
        require_trusted_signer=True,
    )

    result = _assert_direct_snapshot_parity(bundle, options=options)

    assert result.valid
    assert result.signature_validity is AssuranceState.VALID
    assert result.trusted_signer_identity is AssuranceState.VALID


def test_nonmatching_trust_direct_snapshot_parity(tmp_path: Path) -> None:
    bundle = tmp_path / "nonmatching-trust"
    _write_bundle(bundle)
    _sign_bundle(bundle)
    other_public_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    trust_path = _write_trust(tmp_path / "other-trust.json", [other_public_key])
    options = _strict_options(
        trust_store_path=trust_path,
        require_trusted_signer=True,
    )

    result = _assert_direct_snapshot_parity(bundle, options=options)

    assert not result.valid
    assert result.reason == "TRUSTED_SIGNER_NOT_FOUND"
    assert result.trusted_signer_identity is AssuranceState.UNESTABLISHED


def test_acquired_malformed_trust_is_semantically_invalid(tmp_path: Path) -> None:
    bundle = tmp_path / "malformed-trust"
    _write_bundle(bundle)
    trust_path = tmp_path / "malformed-trust.json"
    trust_path.write_bytes(b"{not-json")
    options = AIVerificationOptions(trust_store_path=trust_path)

    result = _assert_direct_snapshot_parity(bundle, options=options)

    assert result.reason == "TRUST_STORE_INVALID"
    assert result.detail == "TRUST_STORE_NOT_JSON"
    assert result.trusted_signer_reason == "TRUST_STORE_INVALID"


@pytest.mark.parametrize(
    ("canonical", "manifest"),
    [
        pytest.param(None, b"{}", id="canonical-absent"),
        pytest.param(b"{}", None, id="manifest-absent"),
        pytest.param(b"{", b"{}", id="canonical-malformed"),
        pytest.param(b"{}", b"{", id="manifest-malformed"),
    ],
)
def test_malformed_acquired_trust_precedes_bundle_inspection(
    canonical: bytes | None,
    manifest: bytes | None,
) -> None:
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(canonical, manifest, None, trust_store=b"{")
    )

    result = verify_ai_snapshot(
        frozen,
        capabilities=_prepared_frozen_capabilities(),
    )

    assert not result.valid
    assert result.reason == "TRUST_STORE_INVALID"
    assert result.detail == "TRUST_STORE_NOT_JSON"
    assert result.payload_integrity is AssuranceState.NOT_EVALUATED
    assert result.signature_validity is AssuranceState.NOT_EVALUATED
    assert result.trusted_signer_identity is AssuranceState.UNESTABLISHED
    assert result.trusted_signer_reason == "TRUST_STORE_INVALID"


def test_valid_or_absent_trust_preserves_early_presence_precedence() -> None:
    valid_trust = (PHASE2_FIXTURES / "semantic_trust_empty.json").read_bytes()
    prepared = _prepared_frozen_capabilities()
    missing_canonical = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(None, b"{}", None, trust_store=valid_trust)
    )
    no_trust = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(None, b"{}", None)
    )

    valid = verify_ai_snapshot(missing_canonical, capabilities=prepared)
    optional_absent = verify_ai_snapshot(no_trust, capabilities=prepared)
    required_absent = verify_ai_snapshot(
        no_trust,
        options=AIVerificationOptions(require_trusted_signer=True),
        capabilities=prepared,
    )

    assert valid.reason == "MISSING_CANONICAL"
    assert optional_absent.reason == "MISSING_CANONICAL"
    assert required_absent.reason == "TRUST_INPUT_NOT_PROVIDED"


def test_malformed_trust_missing_canonical_matches_snapshot_input_modes(
    tmp_path: Path,
) -> None:
    manifest = (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes()
    malformed_trust = b"{"
    bundle = tmp_path / "missing-canonical"
    bundle.mkdir()
    (bundle / "ai_manifest.json").write_bytes(manifest)
    trust_path = tmp_path / "malformed-trust.json"
    trust_path.write_bytes(malformed_trust)
    direct = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust_path)
    )
    immutable = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(None, manifest, None, trust_store=malformed_trust)
    )
    prepared = _prepared_frozen_capabilities()

    direct_result = verify_ai_snapshot(direct, capabilities=prepared)
    immutable_result = verify_ai_snapshot(immutable, capabilities=prepared)

    assert direct_result == immutable_result
    assert direct_result.reason == "TRUST_STORE_INVALID"


def test_early_snapshot_trust_validation_uses_frozen_bytes_once(
    tmp_path: Path,
) -> None:
    manifest = (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes()
    malformed_trust = b"{"
    bundle = tmp_path / "frozen-trust"
    bundle.mkdir()
    (bundle / "ai_manifest.json").write_bytes(manifest)
    trust_path = tmp_path / "frozen-malformed-trust.json"
    trust_path.write_bytes(malformed_trust)
    frozen = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust_path)
    )

    forbidden = AssertionError("snapshot semantics must not access the filesystem")
    with mock.patch.object(Path, "exists", side_effect=forbidden), mock.patch.object(
        Path, "read_bytes", side_effect=forbidden
    ), mock.patch.object(Path, "read_text", side_effect=forbidden), mock.patch.object(
        Path, "open", side_effect=forbidden
    ), mock.patch.object(builtins, "open", side_effect=forbidden), mock.patch.object(
        os, "open", side_effect=forbidden
    ), mock.patch.object(os, "read", side_effect=forbidden), mock.patch.object(
        ai_verify_runtime,
        "load_trust_store",
        side_effect=forbidden,
    ), mock.patch.object(
        ai_verify_runtime,
        "parse_v1_json_source",
        wraps=ai_verify_runtime.parse_v1_json_source,
    ) as parser:
        result = verify_ai_snapshot(
            frozen,
            capabilities=_prepared_frozen_capabilities(),
        )

    assert result.reason == "TRUST_STORE_INVALID"
    parser.assert_called_once()
    assert parser.call_args.args == (malformed_trust,)
    assert parser.call_args.kwargs["role"] is InputRole.TRUST_STORE


def test_acquired_non_utf8_trust_is_semantic_not_io() -> None:
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(b"{}", b"{}", None, trust_store=b"\x80")
    )

    result = verify_ai_snapshot(frozen)

    assert result.reason == "TRUST_STORE_INVALID"
    assert result.detail == "TRUST_STORE_NOT_JSON"
    with pytest.raises(TrustStoreError) as caught:
        load_trust_store_bytes(b"\x80")
    assert caught.value.reason == "TRUST_STORE_NOT_JSON"


def test_stable_absent_trust_semantics() -> None:
    bundle_inputs = ImmutableBytesInputs(
        (PHASE2_FIXTURES / "semantic_ai_canonical.json").read_bytes(),
        (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes(),
        None,
    )
    frozen = acquire_immutable_bytes_snapshot(bundle_inputs)

    optional = verify_ai_snapshot(frozen)
    required = verify_ai_snapshot(
        frozen,
        options=AIVerificationOptions(require_trusted_signer=True),
    )

    assert optional.valid
    assert optional.trusted_signer_identity is AssuranceState.UNESTABLISHED
    assert required.reason == "TRUST_INPUT_NOT_PROVIDED"


def test_o1_trust_acquisition_failure_never_enters_semantics(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)

    with mock.patch.object(
        ai_verify_runtime,
        "verify_ai_snapshot",
        side_effect=AssertionError("semantic evaluator must not be entered"),
    ) as semantic:
        with pytest.raises(OperationalInputFailure) as caught:
            acquire_direct_filesystem_snapshot(
                DirectFilesystemInputs(
                    bundle,
                    trust_store_path=tmp_path / "missing-trust.json",
                )
            )
    semantic.assert_not_called()
    assert caught.value.operational_code.value == "INPUT_IO_ERROR"
    assert caught.value.input_ref.value == "TRUST_STORE"
    with pytest.raises(TypeError):
        ImmutableBytesInputs(
            b"{}",
            b"{}",
            None,
            trust_store=caught.value,  # type: ignore[arg-type]
        )


def test_snapshot_semantics_performs_zero_filesystem_access(tmp_path: Path) -> None:
    bundle = tmp_path / "zero-io"
    _write_bundle(bundle)
    public_key = _sign_bundle(bundle)
    trust_path = _write_trust(tmp_path / "zero-io-trust.json", [public_key])
    frozen = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust_path)
    )
    options = _strict_options(
        trust_store_path=Path("/must/not/be/read.json"),
        require_trusted_signer=True,
    )

    forbidden = AssertionError("snapshot semantics must not access the filesystem")
    with mock.patch.object(Path, "exists", side_effect=forbidden), mock.patch.object(
        Path, "is_file", side_effect=forbidden
    ), mock.patch.object(Path, "read_bytes", side_effect=forbidden), mock.patch.object(
        Path, "read_text", side_effect=forbidden
    ), mock.patch.object(Path, "open", side_effect=forbidden), mock.patch.object(
        builtins, "open", side_effect=forbidden
    ), mock.patch.object(os, "open", side_effect=forbidden), mock.patch.object(
        os, "read", side_effect=forbidden
    ), mock.patch.object(
        ai_verify_runtime,
        "load_trust_store",
        side_effect=forbidden,
    ):
        result = verify_ai_snapshot(frozen, options=options)

    assert result.valid
    assert result.signature_validity is AssuranceState.VALID
    assert result.trusted_signer_identity is AssuranceState.VALID


def test_snapshot_trust_membership_uses_verified_public_key_bytes(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "verified-key-membership"
    _write_bundle(bundle)
    public_key = _sign_bundle(bundle)
    trust_path = _write_trust(tmp_path / "verified-key-trust.json", [public_key])
    frozen = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust_path)
    )

    with mock.patch.object(
        ai_verify_runtime,
        "fingerprint_public_key",
        wraps=ai_verify_runtime.fingerprint_public_key,
    ) as fingerprint:
        result = verify_ai_snapshot(
            frozen,
            options=_strict_options(require_trusted_signer=True),
        )

    assert result.valid
    assert result.trusted_signer_identity is AssuranceState.VALID
    fingerprint.assert_called_once_with(public_key)


def test_post_acquisition_path_mutation_cannot_change_semantics(tmp_path: Path) -> None:
    bundle = tmp_path / "post-acquisition"
    _write_bundle(bundle)
    frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    expected = verify_ai_snapshot(frozen)

    (bundle / "ai_canonical.json").write_bytes(b"tampered")
    (bundle / "ai_manifest.json").unlink()
    (bundle / "verification_keys.json").write_bytes(b"invalid")
    actual = verify_ai_snapshot(frozen)

    assert actual == expected
    assert actual.valid


def test_exact_snapshot_manifest_bytes_are_the_strict_signature_message() -> None:
    canonical = (PHASE2_FIXTURES / "semantic_ai_canonical.json").read_bytes()
    manifest = (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes()
    keyring = (PHASE2_FIXTURES / "semantic_keyring_valid.json").read_bytes()
    rewritten_manifest = b" " + manifest
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(canonical, rewritten_manifest, keyring)
    )

    with mock.patch.object(
        signing,
        "verify_manifest_signature_portable_strict_1",
        wraps=signing.verify_manifest_signature_portable_strict_1,
    ) as strict_verifier:
        result = verify_ai_snapshot(frozen, options=_strict_options())

    assert not result.valid
    assert result.reason == "SIGNATURE_INVALID"
    strict_verifier.assert_called_once()
    assert strict_verifier.call_args.args[0] == rewritten_manifest


def test_explicit_strict_snapshot_uses_no_generic_fallback() -> None:
    frozen = _phase2_snapshot()
    with mock.patch.object(
        signing,
        "verify_manifest_signature",
        side_effect=AssertionError("generic signature verifier must not be called"),
    ), mock.patch.object(
        signing,
        "verify_manifest_signature_portable_strict_1",
        wraps=signing.verify_manifest_signature_portable_strict_1,
    ) as strict_verifier:
        result = verify_ai_snapshot(frozen, options=_strict_options())

    assert result.valid
    assert result.signature_validity is AssuranceState.VALID
    strict_verifier.assert_called_once()


def test_omitted_snapshot_profile_uses_only_legacy_generic_verifier() -> None:
    frozen = _phase2_snapshot()
    with mock.patch.object(
        signing,
        "verify_manifest_signature",
        wraps=signing.verify_manifest_signature,
    ) as generic_verifier, mock.patch.object(
        signing,
        "verify_manifest_signature_portable_strict_1",
        side_effect=AssertionError("strict verifier must not be selected implicitly"),
    ):
        result = verify_ai_snapshot(frozen)

    assert result.valid
    assert result.signature_validity is AssuranceState.VALID
    generic_verifier.assert_called_once()


@pytest.mark.parametrize(
    "public_key",
    [
        bytes.fromhex("01" + "00" * 30 + "0080"),
        bytes.fromhex("ee" + "ff" * 30 + "ff7f"),
    ],
    ids=["x-zero-sign-bit-one", "y-greater-than-or-equal-p"],
)
def test_explicit_strict_snapshot_rejects_noncanonical_keys(public_key: bytes) -> None:
    keyring = json.loads(
        (PHASE2_FIXTURES / "semantic_keyring_valid.json").read_text(encoding="utf-8")
    )
    keyring["keys"][0]["public_key_b64"] = base64.b64encode(public_key).decode("ascii")
    keyring["signatures"][0]["sig_b64"] = base64.b64encode(
        bytes.fromhex("01" + "00" * 63)
    ).decode("ascii")
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(
            (PHASE2_FIXTURES / "semantic_ai_canonical.json").read_bytes(),
            (PHASE2_FIXTURES / "semantic_manifest_valid.json").read_bytes(),
            json.dumps(keyring).encode("utf-8"),
        )
    )

    with mock.patch.object(
        signing,
        "verify_manifest_signature",
        side_effect=AssertionError("strict profile must not fall back"),
    ):
        result = verify_ai_snapshot(frozen, options=_strict_options())

    assert result.reason == "SIGNATURE_INVALID"
    assert result.signature_validity is AssuranceState.INVALID


def test_explicit_strict_snapshot_rejects_modified_signature() -> None:
    result = verify_ai_snapshot(
        _phase2_snapshot("semantic_keyring_modified_signature.json"),
        options=_strict_options(),
    )

    assert result.reason == "SIGNATURE_INVALID"
    assert result.signature_validity is AssuranceState.INVALID


def test_unknown_explicit_profile_remains_typed_operational_plumbing() -> None:
    frozen = acquire_immutable_bytes_snapshot(ImmutableBytesInputs(None, None, None))
    with mock.patch.object(
        ai_verify_runtime,
        "_verify_ai_semantic_source",
        side_effect=AssertionError("semantic evaluation must not start"),
    ):
        with pytest.raises(CapabilityProfileUnavailable):
            verify_ai_snapshot(
                frozen,
                options=AIVerificationOptions(
                    signature_verification_profile="UNKNOWN"
                ),
            )
