#!/usr/bin/env python3
"""Build the frozen Phase 2 verifier-input corpus from explicit case data.

This maintenance helper is non-normative. It does not import or execute the
production verifier, parsers, signing code, or trust code. Expected decisions
below are authored from docs/VERIFIER_INPUT_CONTRACTS_V1.md; this script only
serializes those decisions, deterministic source bytes, hashes, and counts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "verifier_contract_phase2"
FIXTURES = CORPUS / "fixtures"
ZERO_HASH = "0" * 64
KEY_B64 = "A" * 43 + "="
KEY_PAD_ALIAS_B64 = "A" * 42 + "B="
SIG_B64 = "A" * 86 + "=="
SIG_PAD_ALIAS_B64 = "A" * 85 + "B=="
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

PRIMARY_TEST_SEED = bytes(range(32))
SECONDARY_TEST_SEED = bytes(range(32, 64))
PRIMARY_KEY_ID = "phase2-public-test-key"
TEST_KEY_NOTICE = (
    "PUBLIC TEST-ONLY deterministic Ed25519 seeds for conformance reproduction; "
    "not production secrets and not secure key-generation guidance."
)
BLOCK2A_SOURCE_SHA256 = "2caa5c78cae1c145e1c4630469a49ebf2ebc6ec85df91f90e8628bc1d3b9268e"
BLOCK2A_SCHEMA_SHA256 = "65a99dd490e9710aefb7dbb7547beb07f75bdfb3e6e0d8f292d9cc8a6e295fe4"
BLOCK2B1_SEMANTIC_SHA256 = "b2f6d5c0263c97006bad15af985099869264ac5f4833ef356526a6945909ffd9"
BLOCK2B1_VECTOR_SET_SHA256 = "7260d1216c1fe0b9e340fc4e1a0d1ee075a37c785d486d7370fabf9c73c958f1"
BLOCK2B2_PRECEDENCE_SHA256 = "810b62d3a9d0c311a1bb58c7a361083bb1881a16406c65bcea9d6c76ee3f89c1"
ED25519_PROFILE = "ED25519_PORTABLE_STRICT_1"
ED25519_L = 2**252 + 27742317777372353535851937790883648493
IDENTITY_ENCODING = "01" + "00" * 31
IDENTITY_SIGN_ONE_ENCODING = "01" + "00" * 30 + "80"
ORDER_TWO_ENCODING = "ec" + "ff" * 30 + "7f"
Y_P_PLUS_ONE_ENCODING = "ee" + "ff" * 30 + "7f"

V1_ROUTE = "json_sorted_keys_no_whitespace_utf8"
V2_ROUTE = "aelitium_jcs_profile_v2"

CAP_V1 = {
    "identifier": "V1_FROZEN_LEGACY_COMPATIBILITY",
    "integer_maximum_decimal_digits": 640,
    "timestamp_digit_profile": "ASCII",
}
CAP_V1_NAMED_15 = {
    "identifier": "V1_NAMED_RUNTIME_COMPATIBILITY",
    "integer_maximum_decimal_digits": 4300,
    "timestamp_digit_profile": "AELITIUM_UCD_ND_15_0_0_1",
}
CAP_V1_NAMED_13 = {
    "identifier": "V1_NAMED_RUNTIME_COMPATIBILITY",
    "integer_maximum_decimal_digits": 4300,
    "timestamp_digit_profile": "AELITIUM_UCD_ND_13_0_0_1",
}
CAP_V2 = {"identifier": "V2_PORTABLE"}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def manifest_value(route: str, timestamp: Any = "2026-01-01T00:00:00Z", **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "ai_pack_manifest_v1",
        "ts_utc": timestamp,
        "input_schema": "ai_output_v1",
        "canonicalization": route,
        "ai_hash_sha256": ZERO_HASH,
    }
    value.update(extra)
    return value


def keyring_value() -> dict[str, Any]:
    return {
        "keyring_format": "ed25519-v1",
        "keys": [{"key_id": "key-1", "public_key_b64": KEY_B64}],
        "signatures": [
            {
                "key_id": "key-1",
                "algorithm": "ed25519",
                "scope": "manifest.json",
                "sig_b64": SIG_B64,
            }
        ],
    }


def trust_value() -> dict[str, Any]:
    return {
        "trust_store_format": "aelitium-trust-v1",
        "signers": [
            {
                "algorithm": "ed25519",
                "public_key_b64": KEY_B64,
                "label": "fixture signer",
            }
        ],
    }


BLOCK2A_FIXTURE_BYTES = {
    "manifest_v1_valid.json": compact_json(manifest_value(V1_ROUTE)).encode("utf-8"),
    "manifest_v2_valid.json": compact_json(manifest_value(V2_ROUTE)).encode("utf-8"),
    "verification_keys_valid.json": compact_json(keyring_value()).encode("utf-8"),
    "trust_store_valid.json": compact_json(trust_value()).encode("utf-8"),
}


def base64_pad_bit_alias(spelling: str) -> str:
    """Return a same-bytes standard-Base64 spelling with non-zero unused bits."""
    padding = len(spelling) - len(spelling.rstrip("="))
    if padding not in (1, 2):
        raise AssertionError("pad-bit alias requires one or two padding characters")
    index = len(spelling) - padding - 1
    value = BASE64_ALPHABET.index(spelling[index])
    unused_mask = 0x03 if padding == 1 else 0x0F
    if value & unused_mask:
        raise AssertionError("canonical input already has non-zero unused pad bits")
    alias = spelling[:index] + BASE64_ALPHABET[value + 1] + spelling[index + 1 :]
    if base64.b64decode(alias, validate=True) != base64.b64decode(spelling, validate=True):
        raise AssertionError("pad-bit alias changed decoded bytes")
    return alias


def semantic_keyring(
    public_key_b64: str,
    signature_b64: str,
    *,
    key_id: str = PRIMARY_KEY_ID,
    signature_key_id: str | None = None,
) -> dict[str, Any]:
    return {
        "keyring_format": "ed25519-v1",
        "keys": [{"key_id": key_id, "public_key_b64": public_key_b64}],
        "signatures": [
            {
                "key_id": key_id if signature_key_id is None else signature_key_id,
                "algorithm": "ed25519",
                "scope": "manifest.json",
                "sig_b64": signature_b64,
            }
        ],
    }


def semantic_trust(signers: list[dict[str, Any]]) -> dict[str, Any]:
    return {"trust_store_format": "aelitium-trust-v1", "signers": signers}


def semantic_fixture_material() -> tuple[dict[str, bytes], dict[str, Any]]:
    primary_private = Ed25519PrivateKey.from_private_bytes(PRIMARY_TEST_SEED)
    secondary_private = Ed25519PrivateKey.from_private_bytes(SECONDARY_TEST_SEED)
    primary_public = primary_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    secondary_public = secondary_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    primary_b64 = base64.b64encode(primary_public).decode("ascii")
    secondary_b64 = base64.b64encode(secondary_public).decode("ascii")
    primary_alias = base64_pad_bit_alias(primary_b64)

    payload = {
        "schema_version": "ai_output_v1",
        "model": "phase2-test-model",
        "prompt": "deterministic conformance prompt",
        "output": "deterministic conformance output",
        "ts_utc": "2026-01-02T03:04:05Z",
    }
    payload_bytes = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    manifest = {
        "schema": "ai_pack_manifest_v1",
        "ts_utc": "2026-01-02T03:04:05Z",
        "input_schema": "ai_output_v1",
        "canonicalization": V1_ROUTE,
        "ai_hash_sha256": payload_hash,
        "extension": "phase2",
    }
    manifest_bytes = compact_json(manifest).encode("utf-8")
    signature = primary_private.sign(manifest_bytes)
    signature_b64 = base64.b64encode(signature).decode("ascii")
    signature_alias = base64_pad_bit_alias(signature_b64)
    modified_signature = bytes([signature[0] ^ 0x01]) + signature[1:]
    other_signature = primary_private.sign(b"AELITIUM Phase 2 other message")

    primary_signer = {
        "algorithm": "ed25519",
        "public_key_b64": primary_b64,
        "label": "public Phase 2 test key",
    }
    secondary_signer = {
        "algorithm": "ed25519",
        "public_key_b64": secondary_b64,
        "label": "second public Phase 2 test key",
    }

    fixtures = {
        "semantic_ai_canonical.json": payload_bytes,
        "semantic_manifest_valid.json": manifest_bytes,
        "semantic_manifest_leading_whitespace.json": b" " + manifest_bytes,
        "semantic_manifest_member_order.json": json.dumps(
            manifest, separators=(",", ":"), sort_keys=True, ensure_ascii=False
        ).encode("utf-8"),
        "semantic_manifest_escape_spelling.json": manifest_bytes.replace(
            b'"phase2"', b'"phase\\u0032"'
        ),
        "semantic_manifest_terminal_newline.json": manifest_bytes + b"\n",
        "semantic_keyring_valid.json": compact_json(
            semantic_keyring(primary_b64, signature_b64)
        ).encode("utf-8"),
        "semantic_keyring_public_key_alias.json": compact_json(
            semantic_keyring(primary_alias, signature_b64)
        ).encode("utf-8"),
        "semantic_keyring_signature_alias.json": compact_json(
            semantic_keyring(primary_b64, signature_alias)
        ).encode("utf-8"),
        "semantic_keyring_wrong_public_key.json": compact_json(
            semantic_keyring(secondary_b64, signature_b64)
        ).encode("utf-8"),
        "semantic_keyring_modified_signature.json": compact_json(
            semantic_keyring(primary_b64, base64.b64encode(modified_signature).decode("ascii"))
        ).encode("utf-8"),
        "semantic_keyring_other_message_signature.json": compact_json(
            semantic_keyring(primary_b64, base64.b64encode(other_signature).decode("ascii"))
        ).encode("utf-8"),
        "semantic_keyring_key_id_mismatch.json": compact_json(
            semantic_keyring(
                primary_b64,
                signature_b64,
                signature_key_id="different-decoded-key-id",
            )
        ).encode("utf-8"),
        "semantic_trust_matching.json": compact_json(
            semantic_trust([primary_signer])
        ).encode("utf-8"),
        "semantic_trust_nonmatching.json": compact_json(
            semantic_trust([secondary_signer])
        ).encode("utf-8"),
        "semantic_trust_empty.json": compact_json(semantic_trust([])).encode("utf-8"),
        "semantic_trust_two_distinct.json": compact_json(
            semantic_trust([primary_signer, secondary_signer])
        ).encode("utf-8"),
        "semantic_trust_duplicate_exact.json": compact_json(
            semantic_trust([primary_signer, primary_signer])
        ).encode("utf-8"),
        "semantic_trust_duplicate_label.json": compact_json(
            semantic_trust(
                [primary_signer, {**primary_signer, "label": "different display label"}]
            )
        ).encode("utf-8"),
        "semantic_trust_duplicate_alias.json": compact_json(
            semantic_trust(
                [primary_signer, {**primary_signer, "public_key_b64": primary_alias}]
            )
        ).encode("utf-8"),
        "semantic_trust_malformed.json": (
            b'{"trust_store_format":"aelitium-trust-v1","signers":[]} trailing'
        ),
    }
    primary_digest = hashlib.sha256(primary_public).hexdigest()
    secondary_digest = hashlib.sha256(secondary_public).hexdigest()
    materials = {
        "primary_key": {
            "private_seed_hex": PRIMARY_TEST_SEED.hex(),
            "public_key_hex": primary_public.hex(),
            "public_key_b64": primary_b64,
            "public_key_pad_bit_alias_b64": primary_alias,
            "raw_key_sha256": primary_digest,
            "prefixed_bytes_sha256_not_fingerprint": hashlib.sha256(
                b"ed25519:sha256:" + primary_public
            ).hexdigest(),
            "fingerprint": "ed25519:sha256:" + primary_digest,
        },
        "secondary_key": {
            "private_seed_hex": SECONDARY_TEST_SEED.hex(),
            "public_key_hex": secondary_public.hex(),
            "public_key_b64": secondary_b64,
            "raw_key_sha256": secondary_digest,
            "fingerprint": "ed25519:sha256:" + secondary_digest,
        },
        "primary_manifest_signature": {
            "raw_manifest_message_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "signature_hex": signature.hex(),
            "signature_b64": signature_b64,
            "signature_pad_bit_alias_b64": signature_alias,
        },
    }
    return fixtures, materials


SEMANTIC_FIXTURE_BYTES, SEMANTIC_MATERIALS = semantic_fixture_material()
FIXTURE_BYTES = {**BLOCK2A_FIXTURE_BYTES, **SEMANTIC_FIXTURE_BYTES}


def source_fixture(name: str) -> dict[str, Any]:
    raw = FIXTURE_BYTES[name]
    return {
        "kind": "FIXTURE",
        "path": f"fixtures/{name}",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def source_utf8(text: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    return {
        "kind": "INLINE_UTF8",
        "text": text,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def source_bytes(raw: bytes) -> dict[str, Any]:
    return {
        "kind": "INLINE_HEX",
        "hex": raw.hex(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def expected(
    source_decision: str,
    *,
    schema_reached: bool,
    schema_decision: str,
    semantic_reason: str | None = None,
    operational_code: str | None = None,
    timestamp_decision: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    return {
        "source_profile_decision": source_decision,
        "schema_reached": schema_reached,
        "schema_decision": schema_decision,
        "semantic_reason": semantic_reason,
        "operational_code": operational_code,
        "timestamp_decision": timestamp_decision,
    }


def source_case(
    case_id: str,
    family: str,
    input_kind: str,
    source: dict[str, Any],
    capability: dict[str, Any],
    selected_route: str,
    result: dict[str, Any],
    *,
    validate_timestamp: bool | None = None,
    compatibility: str = "SAFE_CLARIFICATION",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": family,
        "input_kind": input_kind,
        "source": source,
        "capability": capability,
        "selected_route": selected_route,
        "verifier_options": {
            "validate_manifest_timestamp": validate_timestamp
        },
        "expected": result,
        "compatibility": compatibility,
    }


def raw_manifest_with_members(route: str, members: str) -> str:
    return (
        "{" + members + f',"ts_utc":"2026-01-01T00:00:00Z",'
        f'"input_schema":"ai_output_v1","canonicalization":"{route}",'
        f'"ai_hash_sha256":"{ZERO_HASH}"' + "}"
    )


def source_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []

    def add(*args: Any, **kwargs: Any) -> None:
        vectors.append(source_case(*args, **kwargs))

    v1 = compact_json(manifest_value(V1_ROUTE))
    v2 = compact_json(manifest_value(V2_ROUTE))

    # Manifest common source boundaries, frozen once for each route family.
    for label, raw, decision, reached, schema_decision, reason, route in (
        ("valid_object", None, "ACCEPT", True, "VALID", None, "LEGACY_V1"),
        ("leading_whitespace", " \t\r\n" + v1, "ACCEPT", True, "VALID", None, "LEGACY_V1"),
        ("trailing_whitespace", v1 + " \t\r\n", "ACCEPT", True, "VALID", None, "LEGACY_V1"),
        ("leading_bom", b"\xef\xbb\xbf" + v1.encode(), "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("malformed_utf8", b"{\"schema\":\"\xff\"}", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("trailing_garbage", v1 + "x", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("second_top_level", v1 + "{}", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("non_object_root", "[]", "ACCEPT", False, "NOT_REACHED", "MANIFEST_NOT_OBJECT", "LEGACY_ERROR_RESOLUTION"),
    ):
        source = source_fixture("manifest_v1_valid.json") if raw is None else (
            source_bytes(raw) if isinstance(raw, bytes) else source_utf8(raw)
        )
        add(
            f"manifest.v1.source.{label}", "MANIFEST_SOURCE", "MANIFEST_V1",
            source, CAP_V1, route,
            expected(decision, schema_reached=reached, schema_decision=schema_decision,
                     semantic_reason=reason, timestamp_decision="PASS" if reached else "NOT_REACHED"),
            validate_timestamp=True,
            compatibility="ALREADY_RELEASED_BEHAVIOR",
        )

    for label, raw, decision, reached, schema_decision, reason, route in (
        ("valid_object", None, "ACCEPT", True, "VALID", None, "PORTABLE_V2"),
        ("leading_whitespace", " \t\r\n" + v2, "ACCEPT", True, "VALID", None, "PORTABLE_V2"),
        ("trailing_whitespace", v2 + " \t\r\n", "ACCEPT", True, "VALID", None, "PORTABLE_V2"),
        ("leading_bom", b"\xef\xbb\xbf" + v2.encode(), "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("malformed_utf8", b"{\"canonicalization\":\"aelitium_jcs_profile_v2\",\"x\":\xff}", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("trailing_garbage", v2 + "x", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("second_top_level", v2 + "{}", "REJECT", False, "NOT_REACHED", "MANIFEST_NOT_JSON", "LEGACY_ERROR_RESOLUTION"),
        ("non_object_root", "[]", "ACCEPT", False, "NOT_REACHED", "MANIFEST_NOT_OBJECT", "LEGACY_ERROR_RESOLUTION"),
    ):
        source = source_fixture("manifest_v2_valid.json") if raw is None else (
            source_bytes(raw) if isinstance(raw, bytes) else source_utf8(raw)
        )
        add(
            f"manifest.v2.source.{label}", "MANIFEST_SOURCE", "MANIFEST_V2",
            source, CAP_V2, route,
            expected(decision, schema_reached=reached, schema_decision=schema_decision,
                     semantic_reason=reason, timestamp_decision="PASS" if reached else "NOT_REACHED"),
            validate_timestamp=True,
            compatibility="UNRELEASED_V2_ONLY",
        )

    # Legacy manifest duplicate, extension, and capability behavior.
    v1_special = [
        (
            "duplicate_required_final_wins",
            raw_manifest_with_members(V1_ROUTE, '"schema":"bad","schema":"ai_pack_manifest_v1"'),
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "escaped_duplicate_final_wins",
            raw_manifest_with_members(V1_ROUTE, '"schema":"bad","schem\\u0061":"ai_pack_manifest_v1"'),
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "invalid_first_valid_final",
            raw_manifest_with_members(V1_ROUTE, '"schema":false,"schema":"ai_pack_manifest_v1"'),
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "valid_first_invalid_final",
            raw_manifest_with_members(V1_ROUTE, '"schema":"ai_pack_manifest_v1","schema":false'),
            expected("ACCEPT", schema_reached=True, schema_decision="INVALID", semantic_reason="MANIFEST_BAD_SCHEMA", timestamp_decision="NOT_REACHED"),
        ),
        (
            "duplicate_inside_unknown_extension",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":{"x":1,"x":2}}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "unknown_ordinary_extension",
            compact_json(manifest_value(V1_ROUTE, extension={"nested": [1, True, None]})),
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_nan",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":NaN}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_infinity",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":Infinity}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_negative_infinity",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":-Infinity}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_opaque_unmatched_surrogate",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":"\\ud800"}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_integer_640_digits",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":' + "9" * 640 + '}',
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", timestamp_decision="PASS"),
        ),
        (
            "ignored_integer_641_digits_outside_capability",
            compact_json(manifest_value(V1_ROUTE))[:-1] + ',"extension":' + "9" * 641 + '}',
            expected("OPERATIONAL", schema_reached=False, schema_decision="NOT_REACHED", operational_code="INPUT_OUTSIDE_DECLARED_CAPABILITY", timestamp_decision="NOT_REACHED"),
        ),
    ]
    for label, raw, result in v1_special:
        add(
            f"manifest.v1.source.{label}", "MANIFEST_SOURCE", "MANIFEST_V1",
            source_utf8(raw), CAP_V1, "LEGACY_V1", result,
            validate_timestamp=True,
            compatibility="ALREADY_RELEASED_BEHAVIOR" if "641" not in label else "ADOPTED_CAPABILITY_POLICY",
        )

    # Portable-v2 manifest profile boundaries needed specifically by this input contract.
    v2_base_prefix = compact_json(manifest_value(V2_ROUTE))[:-1]
    v2_special = [
        ("duplicate_required_rejected", raw_manifest_with_members(V2_ROUTE, '"schema":"ai_pack_manifest_v1","schema":"ai_pack_manifest_v1"')),
        ("escaped_duplicate_rejected", raw_manifest_with_members(V2_ROUTE, '"schema":"ai_pack_manifest_v1","schem\\u0061":"ai_pack_manifest_v1"')),
        ("nested_duplicate_rejected", v2_base_prefix + ',"extension":{"x":1,"x":2}}'),
        ("duplicate_unknown_extension_rejected", v2_base_prefix + ',"extension":1,"extensi\\u006fn":2}'),
    ]
    for label, raw in v2_special:
        add(
            f"manifest.v2.source.{label}", "MANIFEST_SOURCE", "MANIFEST_V2",
            source_utf8(raw), CAP_V2, "PORTABLE_V2",
            expected("REJECT", schema_reached=False, schema_decision="NOT_REACHED", semantic_reason="MANIFEST_NOT_JSON", timestamp_decision="NOT_REACHED"),
            validate_timestamp=True, compatibility="UNRELEASED_V2_ONLY",
        )

    for label, raw, decision in (
        ("valid_unknown_extension", compact_json(manifest_value(V2_ROUTE, extension={"safe": [0, "ok"]})), "ACCEPT"),
        ("legacy_nan_rejected", v2_base_prefix + ',"extension":NaN}', "REJECT"),
        ("legacy_infinity_rejected", v2_base_prefix + ',"extension":Infinity}', "REJECT"),
        ("unmatched_surrogate_rejected", v2_base_prefix + ',"extension":"\\ud800"}', "REJECT"),
        ("noncharacter_rejected", compact_json(manifest_value(V2_ROUTE, extension="\ufdd0")), "REJECT"),
        ("safe_integer_boundary", v2_base_prefix + ',"extension":9007199254740991}', "ACCEPT"),
        ("integer_out_of_profile", v2_base_prefix + ',"extension":9007199254740992}', "REJECT"),
        ("number_overflow_out_of_profile", v2_base_prefix + ',"extension":1e309}', "REJECT"),
    ):
        accepted = decision == "ACCEPT"
        add(
            f"manifest.v2.source.{label}", "MANIFEST_SOURCE", "MANIFEST_V2",
            source_utf8(raw), CAP_V2, "PORTABLE_V2",
            expected(decision, schema_reached=accepted, schema_decision="VALID" if accepted else "NOT_REACHED",
                     semantic_reason=None if accepted else "MANIFEST_NOT_JSON",
                     timestamp_decision="PASS" if accepted else "NOT_REACHED"),
            validate_timestamp=True, compatibility="UNRELEASED_V2_ONLY",
        )

    # Manifest timestamp procedures. Source/schema acceptance is intentionally separate.
    v1_timestamps: list[tuple[str, Any, dict[str, Any], bool, str, str | None, str | None]] = [
        ("ascii_lexical_valid", "2026-01-02T03:04:05Z", CAP_V1, True, "PASS", None, None),
        ("impossible_calendar_lexical_valid", "9999-99-99T99:99:99Z", CAP_V1, True, "PASS", None, None),
        ("zero_final_lf", "0000-00-00T00:00:60Z", CAP_V1, True, "PASS", None, None),
        ("one_final_decoded_lf", "2026-01-02T03:04:05Z\n", CAP_V1, True, "PASS", None, None),
        ("two_final_decoded_lfs", "2026-01-02T03:04:05Z\n\n", CAP_V1, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("final_cr", "2026-01-02T03:04:05Z\r", CAP_V1, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("final_crlf", "2026-01-02T03:04:05Z\r\n", CAP_V1, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("wrong_separator", "2026/01-02T03:04:05Z", CAP_V1, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("embedded_lf", "2026-01-02T03:\n04:05Z", CAP_V1, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("named_profile_matching_nd", "٢٠٢٦-٠١-٠٢T٠٣:٠٤:٠٥Z", CAP_V1_NAMED_15, True, "PASS", None, None),
        ("non_ascii_nd_outside_ascii_capability", "٢٠٢٦-٠١-٠٢T٠٣:٠٤:٠٥Z", CAP_V1, True, "OPERATIONAL", None, "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
        ("outside_selected_frozen_nd_table", chr(0x1E4F0) + "026-01-02T03:04:05Z", CAP_V1_NAMED_13, True, "FAIL", "MANIFEST_BAD_TS_UTC", None),
        ("disabled_non_string", {"not": "a timestamp"}, CAP_V1, False, "BYPASSED", None, None),
    ]
    for label, timestamp, capability, enabled, timestamp_decision, reason, op_code in v1_timestamps:
        raw = compact_json(manifest_value(V1_ROUTE, timestamp))
        add(
            f"manifest.v1.timestamp.{label}", "MANIFEST_TIMESTAMP_V1", "MANIFEST_V1",
            source_utf8(raw), capability, "LEGACY_V1",
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", semantic_reason=reason,
                     operational_code=op_code, timestamp_decision=timestamp_decision),
            validate_timestamp=enabled,
            compatibility="ADOPTED_CAPABILITY_POLICY",
        )

    v2_timestamps: list[tuple[str, Any, bool, str, str | None]] = [
        ("ascii_exact_valid", "2026-01-02T03:04:05Z", True, "PASS", None),
        ("impossible_calendar_lexical_valid", "9999-99-99T99:99:99Z", True, "PASS", None),
        ("arabic_indic_digits", "٢٠٢٦-٠١-٠٢T٠٣:٠٤:٠٥Z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("fullwidth_digits", "２０２６-０１-０２T０３:０４:０５Z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("one_final_decoded_lf", "2026-01-02T03:04:05Z\n", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("two_final_decoded_lfs", "2026-01-02T03:04:05Z\n\n", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("wrong_separator", "2026/01-02T03:04:05Z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("lowercase_t_z", "2026-01-02t03:04:05z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("prefix_whitespace", " 2026-01-02T03:04:05Z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("suffix_whitespace", "2026-01-02T03:04:05Z ", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("utc_offset", "2026-01-02T03:04:05+00:00", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("fractional_seconds", "2026-01-02T03:04:05.000Z", True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("enabled_non_string", {"not": "a timestamp"}, True, "FAIL", "MANIFEST_BAD_TS_UTC"),
        ("disabled_malformed_string", "not-a-timestamp\n", False, "BYPASSED", None),
        ("disabled_object", {"valid": [1, 2, 3]}, False, "BYPASSED", None),
        ("disabled_null", None, False, "BYPASSED", None),
    ]
    for label, timestamp, enabled, timestamp_decision, reason in v2_timestamps:
        raw = compact_json(manifest_value(V2_ROUTE, timestamp))
        add(
            f"manifest.v2.timestamp.{label}", "MANIFEST_TIMESTAMP_V2", "MANIFEST_V2",
            source_utf8(raw), CAP_V2, "PORTABLE_V2",
            expected("ACCEPT", schema_reached=True, schema_decision="VALID", semantic_reason=reason,
                     timestamp_decision=timestamp_decision),
            validate_timestamp=enabled, compatibility="UNRELEASED_V2_ONLY",
        )

    # Legacy auxiliary keyring source cases. Signature mathematics is out of scope.
    keyring = compact_json(keyring_value())
    key_cases: list[tuple[str, str | bytes | None, str, bool, str, str | None, str | None]] = [
        ("valid", None, "ACCEPT", True, "VALID", None, None),
        ("bom", b"\xef\xbb\xbf" + keyring.encode(), "REJECT", False, "NOT_REACHED", "SIGNATURE_INVALID", None),
        ("malformed_utf8", b"{\"keyring_format\":\"\xff\"}", "REJECT", False, "NOT_REACHED", "SIGNATURE_INVALID", None),
        ("surrounding_whitespace", " \t\n" + keyring + "\r ", "ACCEPT", True, "VALID", None, None),
        ("trailing_garbage", keyring + "x", "REJECT", False, "NOT_REACHED", "SIGNATURE_INVALID", None),
        ("second_top_level", keyring + "{}", "REJECT", False, "NOT_REACHED", "SIGNATURE_INVALID", None),
        ("non_object_root", "[]", "ACCEPT", True, "INVALID", "SIGNATURE_INVALID", None),
    ]
    for label, raw, decision, reached, schema_decision, reason, op_code in key_cases:
        source = source_fixture("verification_keys_valid.json") if raw is None else (
            source_bytes(raw) if isinstance(raw, bytes) else source_utf8(raw)
        )
        add(
            f"keyring.source.{label}", "KEYRING_SOURCE", "VERIFICATION_KEYS_V1",
            source, CAP_V1, "NOT_APPLICABLE",
            expected(decision, schema_reached=reached, schema_decision=schema_decision,
                     semantic_reason=reason, operational_code=op_code),
            compatibility="ALREADY_RELEASED_BEHAVIOR",
        )

    key_source_special = [
        ("root_duplicate_last_wins", keyring.replace('"keyring_format":"ed25519-v1"', '"keyring_format":"bad","keyring_format":"ed25519-v1"'), "ACCEPT", "VALID", None),
        ("key_entry_duplicate_last_wins", keyring.replace('"key_id":"key-1","public_key_b64"', '"key_id":false,"key_id":"key-1","public_key_b64"', 1), "ACCEPT", "VALID", None),
        ("signature_entry_duplicate_last_wins", keyring.replace('"algorithm":"ed25519"', '"algorithm":"bad","algorithm":"ed25519"'), "ACCEPT", "VALID", None),
        ("escaped_equivalent_duplicate", keyring.replace('"keyring_format":"ed25519-v1"', '"keyring_format":"bad","keyring_f\\u006frmat":"ed25519-v1"'), "ACCEPT", "VALID", None),
        ("unknown_root_open", keyring[:-1] + ',"extension":true}', "ACCEPT", "VALID", None),
        ("unknown_key_entry_open", keyring.replace('"public_key_b64":"' + KEY_B64 + '"', '"public_key_b64":"' + KEY_B64 + '","extension":true', 1), "ACCEPT", "VALID", None),
        ("unknown_signature_entry_open", keyring.replace('"sig_b64":"' + SIG_B64 + '"', '"sig_b64":"' + SIG_B64 + '","extension":true'), "ACCEPT", "VALID", None),
        ("opaque_ignored_string", keyring[:-1] + ',"extension":"\\ud800"}', "ACCEPT", "VALID", None),
        ("ignored_integer_640_digits", keyring[:-1] + ',"extension":' + "9" * 640 + '}', "ACCEPT", "VALID", None),
        ("overwritten_integer_641_outside_capability", keyring[:-1] + ',"extension":' + "9" * 641 + ',"extension":0}', "OPERATIONAL", "NOT_REACHED", "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
    ]
    for label, raw, decision, schema_decision, outcome in key_source_special:
        operational = outcome if outcome == "INPUT_OUTSIDE_DECLARED_CAPABILITY" else None
        reason = None if operational else outcome
        add(
            f"keyring.source.{label}", "KEYRING_SOURCE", "VERIFICATION_KEYS_V1",
            source_utf8(raw), CAP_V1, "NOT_APPLICABLE",
            expected(decision, schema_reached=decision == "ACCEPT", schema_decision=schema_decision,
                     semantic_reason=reason, operational_code=operational),
            compatibility="ADOPTED_CAPABILITY_POLICY" if operational else "SAFE_CLARIFICATION",
        )

    # Trust source cases start from immutable bytes; no filesystem conditions appear here.
    trust = compact_json(trust_value())
    trust_cases: list[tuple[str, str | bytes | None, str, bool, str, str | None, str | None]] = [
        ("valid", None, "ACCEPT", True, "VALID", None, None),
        ("bom", b"\xef\xbb\xbf" + trust.encode(), "REJECT", False, "NOT_REACHED", "TRUST_STORE_INVALID", None),
        ("malformed_utf8", b"{\"trust_store_format\":\"\xff\"}", "REJECT", False, "NOT_REACHED", "TRUST_STORE_INVALID", None),
        ("surrounding_whitespace", " \t\n" + trust + "\r ", "ACCEPT", True, "VALID", None, None),
        ("trailing_garbage", trust + "x", "REJECT", False, "NOT_REACHED", "TRUST_STORE_INVALID", None),
        ("second_top_level", trust + "{}", "REJECT", False, "NOT_REACHED", "TRUST_STORE_INVALID", None),
        ("wrong_root_type", "[]", "ACCEPT", True, "INVALID", "TRUST_STORE_INVALID", None),
    ]
    for label, raw, decision, reached, schema_decision, reason, op_code in trust_cases:
        source = source_fixture("trust_store_valid.json") if raw is None else (
            source_bytes(raw) if isinstance(raw, bytes) else source_utf8(raw)
        )
        add(
            f"trust.source.{label}", "TRUST_SOURCE", "TRUST_STORE_V1",
            source, CAP_V1, "NOT_APPLICABLE",
            expected(decision, schema_reached=reached, schema_decision=schema_decision,
                     semantic_reason=reason, operational_code=op_code),
            compatibility="ALREADY_RELEASED_BEHAVIOR",
        )

    trust_source_special = [
        ("root_duplicate_last_wins", trust.replace('"trust_store_format":"aelitium-trust-v1"', '"trust_store_format":"bad","trust_store_format":"aelitium-trust-v1"'), "ACCEPT", "VALID", None),
        ("signer_duplicate_last_wins", trust.replace('"algorithm":"ed25519"', '"algorithm":false,"algorithm":"ed25519"'), "ACCEPT", "VALID", None),
        ("escaped_equivalent_duplicate", trust.replace('"trust_store_format":"aelitium-trust-v1"', '"trust_store_format":"bad","trust_store_f\\u006frmat":"aelitium-trust-v1"'), "ACCEPT", "VALID", None),
        ("overwritten_invalid_value_then_valid", trust.replace('"signers":[', '"signers":0,"signers":['), "ACCEPT", "VALID", None),
        ("overwritten_integer_640_digits", trust[:-1] + ',"signers":' + "9" * 640 + ',"signers":[]}', "ACCEPT", "VALID", None),
        ("overwritten_integer_641_outside_capability", trust[:-1] + ',"signers":' + "9" * 641 + ',"signers":[]}', "OPERATIONAL", "NOT_REACHED", "INPUT_OUTSIDE_DECLARED_CAPABILITY"),
        ("opaque_label", trust.replace('"label":"fixture signer"', '"label":"\\ud800"'), "ACCEPT", "VALID", None),
    ]
    for label, raw, decision, schema_decision, outcome in trust_source_special:
        operational = outcome if outcome == "INPUT_OUTSIDE_DECLARED_CAPABILITY" else None
        add(
            f"trust.source.{label}", "TRUST_SOURCE", "TRUST_STORE_V1",
            source_utf8(raw), CAP_V1, "NOT_APPLICABLE",
            expected(decision, schema_reached=decision == "ACCEPT", schema_decision=schema_decision,
                     operational_code=operational),
            compatibility="ADOPTED_CAPABILITY_POLICY" if operational else "SAFE_CLARIFICATION",
        )

    return vectors


SCHEMA_TEMPLATES = {
    "MANIFEST_V1_VALID": manifest_value(V1_ROUTE),
    "MANIFEST_V2_VALID": manifest_value(V2_ROUTE),
    "KEYRING_VALID": keyring_value(),
    "TRUST_EMPTY_VALID": {
        "trust_store_format": "aelitium-trust-v1",
        "signers": [],
    },
    "TRUST_ONE_VALID": trust_value(),
}


def mutation(op: str, path: str, value: Any = None) -> dict[str, Any]:
    result = {"op": op, "path": path}
    if op == "SET":
        result["value"] = value
    return result


def schema_case(
    case_id: str,
    family: str,
    input_kind: str,
    schema: str,
    template: str,
    mutations: list[dict[str, Any]],
    decision: str,
    focus: str,
    *,
    semantic_reason: str | None = None,
    first_missing_member: str | None = None,
    procedural_requirement: str = "NONE",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": family,
        "input_kind": input_kind,
        "schema": schema,
        "instance_recipe": {"template": template, "mutations": mutations},
        "focus": focus,
        "expected": {
            "schema_decision": decision,
            "semantic_reason": semantic_reason,
            "first_missing_member": first_missing_member,
            "procedural_requirement": procedural_requirement,
        },
    }


def schema_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []

    def add(*args: Any, **kwargs: Any) -> None:
        vectors.append(schema_case(*args, **kwargs))

    for version, kind, schema, template, route in (
        ("v1", "MANIFEST_V1", "ai_manifest_v1.json", "MANIFEST_V1_VALID", V1_ROUTE),
        ("v2", "MANIFEST_V2", "ai_manifest_v2.json", "MANIFEST_V2_VALID", V2_ROUTE),
    ):
        for field in ("schema", "ts_utc", "input_schema", "canonicalization", "ai_hash_sha256"):
            add(
                f"manifest.schema.{version}.missing_{field}", "MANIFEST_SCHEMA", kind,
                schema, template, [mutation("REMOVE", f"/{field}")], "INVALID",
                "REQUIRED_MEMBER", semantic_reason="MANIFEST_MISSING_FIELD",
                first_missing_member=field, procedural_requirement="ORDERED_MANIFEST_PRESENCE",
            )
        add(
            f"manifest.schema.{version}.missing_schema_and_ts", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("REMOVE", "/schema"), mutation("REMOVE", "/ts_utc")],
            "INVALID", "MULTIPLE_REQUIRED_MEMBERS", semantic_reason="MANIFEST_MISSING_FIELD",
            first_missing_member="schema", procedural_requirement="ORDERED_MANIFEST_PRESENCE",
        )
        add(
            f"manifest.schema.{version}.missing_ts_and_input_schema", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("REMOVE", "/ts_utc"), mutation("REMOVE", "/input_schema")],
            "INVALID", "MULTIPLE_REQUIRED_MEMBERS", semantic_reason="MANIFEST_MISSING_FIELD",
            first_missing_member="ts_utc", procedural_requirement="ORDERED_MANIFEST_PRESENCE",
        )
        for label, focus in (
            ("valid_schema_identifier", "SCHEMA_IDENTIFIER"),
            ("valid_input_schema_identifier", "INPUT_SCHEMA_IDENTIFIER"),
            ("valid_route_identifier", "CANONICALIZATION_IDENTIFIER"),
        ):
            add(
                f"manifest.schema.{version}.{label}", "MANIFEST_SCHEMA", kind,
                schema, template, [], "VALID", focus,
            )
        add(
            f"manifest.schema.{version}.bad_schema_identifier", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("SET", "/schema", "bad")], "INVALID",
            "SCHEMA_IDENTIFIER", semantic_reason="MANIFEST_BAD_SCHEMA",
        )
        add(
            f"manifest.schema.{version}.bad_input_schema_identifier", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("SET", "/input_schema", "bad")], "INVALID",
            "INPUT_SCHEMA_IDENTIFIER", semantic_reason="MANIFEST_BAD_INPUT_SCHEMA",
        )
        other_route = V2_ROUTE if route == V1_ROUTE else V1_ROUTE
        add(
            f"manifest.schema.{version}.wrong_route_identifier", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("SET", "/canonicalization", other_route)], "INVALID",
            "CANONICALIZATION_IDENTIFIER", semantic_reason="MANIFEST_BAD_CANONICALIZATION",
        )
        digest_cases = (
            ("valid_digest", ZERO_HASH, "VALID", None),
            ("digest_63", "0" * 63, "INVALID", "MANIFEST_BAD_AI_HASH_SHA256"),
            ("digest_65", "0" * 65, "INVALID", "MANIFEST_BAD_AI_HASH_SHA256"),
            ("digest_uppercase", "A" * 64, "INVALID", "MANIFEST_BAD_AI_HASH_SHA256"),
            ("digest_non_hex", "g" * 64, "INVALID", "MANIFEST_BAD_AI_HASH_SHA256"),
            ("digest_non_string", 0, "INVALID", "MANIFEST_BAD_AI_HASH_SHA256"),
        )
        for label, value, decision, reason in digest_cases:
            add(
                f"manifest.schema.{version}.{label}", "MANIFEST_SCHEMA", kind,
                schema, template, [mutation("SET", "/ai_hash_sha256", value)], decision,
                "AI_HASH_SHA256", semantic_reason=reason,
            )
        add(
            f"manifest.schema.{version}.unknown_field_open", "MANIFEST_SCHEMA", kind,
            schema, template, [mutation("SET", "/extension", {"valid": True})], "VALID",
            "OPEN_OBJECT", procedural_requirement="SOURCE_PROFILE",
        )
        for label, value in (
            ("timestamp_string_schema_neutral", "not-a-timestamp"),
            ("timestamp_object_schema_neutral", {"not": "a timestamp"}),
            ("timestamp_null_schema_neutral", None),
        ):
            add(
                f"manifest.schema.{version}.{label}", "MANIFEST_SCHEMA", kind,
                schema, template, [mutation("SET", "/ts_utc", value)], "VALID",
                "TIMESTAMP_SCHEMA_NEUTRALITY", procedural_requirement="TIMESTAMP_OPTION",
            )

    key_schema = "verification_keys_v1.json"
    key_family = "KEYRING_SCHEMA"
    key_kind = "VERIFICATION_KEYS_V1"
    key_template = "KEYRING_VALID"
    key_cases = [
        ("valid_shape", [], "VALID", "STRUCTURE", None, "NONE"),
        ("missing_keyring_format", [mutation("REMOVE", "/keyring_format")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("wrong_keyring_format", [mutation("SET", "/keyring_format", "bad")], "INVALID", "FORMAT_IDENTIFIER", "SIGNATURE_INVALID", "NONE"),
        ("keys_wrong_type", [mutation("SET", "/keys", {})], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("zero_keys", [mutation("SET", "/keys", [])], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("two_keys", [mutation("SET", "/keys", keyring_value()["keys"] * 2)], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("key_entry_wrong_type", [mutation("SET", "/keys/0", "key")], "INVALID", "ENTRY_TYPE", "SIGNATURE_INVALID", "NONE"),
        ("missing_key_id", [mutation("REMOVE", "/keys/0/key_id")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("empty_key_id", [mutation("SET", "/keys/0/key_id", "")], "INVALID", "KEY_ID", "SIGNATURE_INVALID", "NONE"),
        ("whitespace_only_key_id", [mutation("SET", "/keys/0/key_id", " "), mutation("SET", "/signatures/0/key_id", " ")], "VALID", "KEY_ID", None, "KEY_ID_EQUALITY"),
        ("missing_public_key_b64", [mutation("REMOVE", "/keys/0/public_key_b64")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("signatures_wrong_type", [mutation("SET", "/signatures", {})], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("zero_signatures", [mutation("SET", "/signatures", [])], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("two_signatures", [mutation("SET", "/signatures", keyring_value()["signatures"] * 2)], "INVALID", "CARDINALITY", "SIGNATURE_INVALID", "NONE"),
        ("signature_entry_wrong_type", [mutation("SET", "/signatures/0", "signature")], "INVALID", "ENTRY_TYPE", "SIGNATURE_INVALID", "NONE"),
        ("signature_missing_key_id", [mutation("REMOVE", "/signatures/0/key_id")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("signature_missing_algorithm", [mutation("REMOVE", "/signatures/0/algorithm")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("signature_missing_scope", [mutation("REMOVE", "/signatures/0/scope")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("signature_missing_sig_b64", [mutation("REMOVE", "/signatures/0/sig_b64")], "INVALID", "REQUIRED_MEMBER", "SIGNATURE_INVALID", "NONE"),
        ("bad_algorithm", [mutation("SET", "/signatures/0/algorithm", "Ed25519")], "INVALID", "ALGORITHM", "SIGNATURE_INVALID", "NONE"),
        ("bad_scope", [mutation("SET", "/signatures/0/scope", "ai_manifest.json")], "INVALID", "SCOPE", "SIGNATURE_INVALID", "NONE"),
    ]
    for label, mutations, decision, focus, reason, procedure in key_cases:
        add(f"keyring.schema.{label}", key_family, key_kind, key_schema, key_template,
            mutations, decision, focus, semantic_reason=reason,
            procedural_requirement=procedure)

    public_key_cases = (
        ("valid_lexical", KEY_B64, "VALID", "NONE"),
        ("missing_padding", "A" * 43, "INVALID", "NONE"),
        ("extra_padding", "A" * 43 + "==", "INVALID", "NONE"),
        ("url_character", "A" * 42 + "-=", "INVALID", "NONE"),
        ("whitespace", "A" * 41 + " A=", "INVALID", "NONE"),
        ("bad_length", "A" * 42 + "=", "INVALID", "NONE"),
        ("nonzero_pad_bits_schema_valid", KEY_PAD_ALIAS_B64, "VALID", "BASE64_PAD_BITS"),
        ("decoded_length_confirmation_procedural", KEY_B64, "VALID", "BASE64_DECODED_LENGTH"),
    )
    for label, value, decision, procedure in public_key_cases:
        add(
            f"keyring.schema.public_key_b64.{label}", key_family, key_kind, key_schema,
            key_template, [mutation("SET", "/keys/0/public_key_b64", value)], decision,
            "BASE64_PUBLIC_KEY", semantic_reason="SIGNATURE_INVALID" if decision == "INVALID" else None,
            procedural_requirement=procedure,
        )

    signature_cases = (
        ("valid_lexical", SIG_B64, "VALID", "NONE"),
        ("missing_padding", "A" * 86, "INVALID", "NONE"),
        ("extra_padding", "A" * 86 + "===", "INVALID", "NONE"),
        ("url_character", "A" * 85 + "-==", "INVALID", "NONE"),
        ("whitespace", "A" * 84 + " A==", "INVALID", "NONE"),
        ("bad_length", "A" * 85 + "==", "INVALID", "NONE"),
        ("nonzero_pad_bits_schema_valid", SIG_PAD_ALIAS_B64, "VALID", "BASE64_PAD_BITS"),
        ("decoded_length_confirmation_procedural", SIG_B64, "VALID", "BASE64_DECODED_LENGTH"),
    )
    for label, value, decision, procedure in signature_cases:
        add(
            f"keyring.schema.sig_b64.{label}", key_family, key_kind, key_schema,
            key_template, [mutation("SET", "/signatures/0/sig_b64", value)], decision,
            "BASE64_SIGNATURE", semantic_reason="SIGNATURE_INVALID" if decision == "INVALID" else None,
            procedural_requirement=procedure,
        )
    add(
        "keyring.schema.cross_entry_key_id_mismatch_schema_valid", key_family, key_kind,
        key_schema, key_template, [mutation("SET", "/signatures/0/key_id", "other")],
        "VALID", "KEY_ID", procedural_requirement="KEY_ID_EQUALITY",
    )
    add(
        "keyring.schema.arbitrary_signature_math_procedural", key_family, key_kind,
        key_schema, key_template, [], "VALID", "SIGNATURE_MATHEMATICS",
        procedural_requirement="ED25519_VERIFICATION",
    )

    trust_schema = "trust_store_v1.json"
    trust_family = "TRUST_SCHEMA"
    trust_kind = "TRUST_STORE_V1"
    signer = trust_value()["signers"][0]
    distinct_signer = {
        "algorithm": "ed25519",
        "public_key_b64": "B" + "A" * 42 + "=",
        "label": "second",
    }
    trust_cases = [
        ("valid_empty_signers", "TRUST_EMPTY_VALID", [], "VALID", "STRUCTURE", None, "NONE"),
        ("valid_one_signer", "TRUST_ONE_VALID", [], "VALID", "STRUCTURE", None, "NONE"),
        ("valid_multiple_structurally_distinct", "TRUST_ONE_VALID", [mutation("SET", "/signers", [signer, distinct_signer])], "VALID", "STRUCTURE", None, "FINGERPRINT_UNIQUENESS"),
        ("missing_trust_store_format", "TRUST_EMPTY_VALID", [mutation("REMOVE", "/trust_store_format")], "INVALID", "REQUIRED_MEMBER", "TRUST_STORE_INVALID", "NONE"),
        ("bad_trust_store_format", "TRUST_EMPTY_VALID", [mutation("SET", "/trust_store_format", "bad")], "INVALID", "FORMAT_IDENTIFIER", "TRUST_STORE_INVALID", "NONE"),
        ("missing_signers", "TRUST_EMPTY_VALID", [mutation("REMOVE", "/signers")], "INVALID", "REQUIRED_MEMBER", "TRUST_STORE_INVALID", "NONE"),
        ("signers_wrong_type", "TRUST_EMPTY_VALID", [mutation("SET", "/signers", {})], "INVALID", "ENTRY_TYPE", "TRUST_STORE_INVALID", "NONE"),
        ("signer_wrong_type", "TRUST_ONE_VALID", [mutation("SET", "/signers/0", "signer")], "INVALID", "ENTRY_TYPE", "TRUST_STORE_INVALID", "NONE"),
        ("missing_algorithm", "TRUST_ONE_VALID", [mutation("REMOVE", "/signers/0/algorithm")], "INVALID", "REQUIRED_MEMBER", "TRUST_STORE_INVALID", "NONE"),
        ("bad_algorithm", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/algorithm", "Ed25519")], "INVALID", "ALGORITHM", "TRUST_STORE_INVALID", "NONE"),
        ("missing_public_key_b64", "TRUST_ONE_VALID", [mutation("REMOVE", "/signers/0/public_key_b64")], "INVALID", "REQUIRED_MEMBER", "TRUST_STORE_INVALID", "NONE"),
        ("extra_root_member", "TRUST_EMPTY_VALID", [mutation("SET", "/extra", True)], "INVALID", "CLOSED_OBJECT", "TRUST_STORE_INVALID", "SOURCE_COLLAPSE"),
        ("extra_signer_member", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/extra", True)], "INVALID", "CLOSED_OBJECT", "TRUST_STORE_INVALID", "SOURCE_COLLAPSE"),
        ("label_absent", "TRUST_ONE_VALID", [mutation("REMOVE", "/signers/0/label")], "VALID", "LABEL", None, "NONE"),
        ("label_nonempty", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/label", "display")], "VALID", "LABEL", None, "NONE"),
        ("label_whitespace_only", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/label", " ")], "VALID", "LABEL", None, "NONE"),
        ("label_empty", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/label", "")], "INVALID", "LABEL", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_valid_lexical", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", KEY_B64)], "VALID", "BASE64_PUBLIC_KEY", None, "BASE64_DECODED_LENGTH"),
        ("public_key_bad_alphabet", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", "A" * 42 + "-=")], "INVALID", "BASE64_PUBLIC_KEY", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_whitespace", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", "A" * 41 + " A=")], "INVALID", "BASE64_PUBLIC_KEY", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_missing_padding", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", "A" * 43)], "INVALID", "BASE64_PUBLIC_KEY", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_extra_padding", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", "A" * 43 + "==")], "INVALID", "BASE64_PUBLIC_KEY", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_bad_length", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", "A" * 42 + "=")], "INVALID", "BASE64_PUBLIC_KEY", "TRUST_STORE_INVALID", "NONE"),
        ("public_key_nonzero_pad_bits_schema_valid", "TRUST_ONE_VALID", [mutation("SET", "/signers/0/public_key_b64", KEY_PAD_ALIAS_B64)], "VALID", "BASE64_PUBLIC_KEY", None, "BASE64_PAD_BITS"),
        ("structural_duplicate_signers_schema_valid", "TRUST_ONE_VALID", [mutation("SET", "/signers", [signer, signer])], "VALID", "FINGERPRINT_UNIQUENESS", None, "FINGERPRINT_UNIQUENESS"),
    ]
    for label, template, mutations, decision, focus, reason, procedure in trust_cases:
        add(
            f"trust.schema.{label}", trust_family, trust_kind, trust_schema, template,
            mutations, decision, focus, semantic_reason=reason,
            procedural_requirement=procedure,
        )

    return vectors


def semantic_case(
    case_id: str,
    family: str,
    operation: str,
    *,
    manifest: str | None = None,
    verification_keys: str | None = None,
    trust_store: str | None = None,
    key_material: str | None = None,
    require_signature: bool = False,
    require_trusted_signer: bool = False,
    top_level_reason: str | None = None,
    signature_validity: str = "NOT_EVALUATED",
    trusted_signer_identity: str = "NOT_EVALUATED",
    cryptographic_signature_decision: str = "NOT_EVALUATED",
    trust_store_validation: str = "NOT_EVALUATED",
    trust_membership_decision: str = "NOT_EVALUATED",
    expected_fingerprint: str | None = None,
    compatibility: str = "SAFE_CLARIFICATION",
) -> dict[str, Any]:
    message_hash = (
        hashlib.sha256(SEMANTIC_FIXTURE_BYTES[manifest]).hexdigest()
        if manifest is not None and verification_keys is not None
        else None
    )
    return {
        "case_id": case_id,
        "family": family,
        "operation": operation,
        "inputs": {
            "canonical_payload": (
                "semantic_ai_canonical.json" if manifest is not None else None
            ),
            "manifest": manifest,
            "verification_keys": verification_keys,
            "trust_store": trust_store,
            "key_material": key_material,
        },
        "verifier_options": {
            "require_signature": require_signature,
            "require_trusted_signer": require_trusted_signer,
        },
        "raw_manifest_message_sha256": message_hash,
        "expected": {
            "top_level_reason": top_level_reason,
            "signature_validity": signature_validity,
            "trusted_signer_identity": trusted_signer_identity,
            "cryptographic_signature_decision": cryptographic_signature_decision,
            "trust_store_validation": trust_store_validation,
            "trust_membership_decision": trust_membership_decision,
            "expected_fingerprint": expected_fingerprint,
        },
        "compatibility": compatibility,
    }


def strict_ed25519_case(
    case_id: str,
    *,
    message: dict[str, Any],
    public_key_hex: str,
    signature_hex: str,
    signature_validity: str,
    failure_stage: str,
    a_decoding: str,
    r_decoding: str,
    a_subgroup: str,
    r_subgroup: str,
    scalar_decision: str,
    equation_decision: str,
    purpose: str,
    compatibility: str = "SAFE_CLARIFICATION",
    distinguishing_equations: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": "ED25519_STRICT_SEMANTIC",
        "profile": ED25519_PROFILE,
        "message": message,
        "public_key_hex": public_key_hex,
        "signature_hex": signature_hex,
        "expected": {
            "top_level_reason": None if signature_validity == "VALID" else "SIGNATURE_INVALID",
            "signature_validity": signature_validity,
            "cryptographic_signature_decision": signature_validity,
            "failure_stage": failure_stage,
            "a_decoding": a_decoding,
            "r_decoding": r_decoding,
            "a_subgroup": a_subgroup,
            "r_subgroup": r_subgroup,
            "scalar_decision": scalar_decision,
            "equation_decision": equation_decision,
        },
        "purpose": purpose,
        "compatibility": compatibility,
        "distinguishing_equations": distinguishing_equations,
    }


def semantic_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    primary_fingerprint = SEMANTIC_MATERIALS["primary_key"]["fingerprint"]
    secondary_fingerprint = SEMANTIC_MATERIALS["secondary_key"]["fingerprint"]
    manifest = "semantic_manifest_valid.json"
    keyring = "semantic_keyring_valid.json"

    def add(*args: Any, **kwargs: Any) -> None:
        vectors.append(semantic_case(*args, **kwargs))

    # G-05: exact raw-message scope, mathematical verification, key relation,
    # compatible pad-bit aliases, and absent signature material.
    add(
        "signature.semantic.valid_exact_raw_message", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, verification_keys=keyring,
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="VALID", trust_store_validation="ABSENT",
        trust_membership_decision="NO_STORE",
    )
    for label, changed_manifest in (
        ("raw_leading_whitespace", "semantic_manifest_leading_whitespace.json"),
        ("raw_member_order", "semantic_manifest_member_order.json"),
        ("raw_escape_spelling", "semantic_manifest_escape_spelling.json"),
        ("raw_terminal_newline", "semantic_manifest_terminal_newline.json"),
    ):
        add(
            f"signature.semantic.{label}", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
            manifest=changed_manifest, verification_keys=keyring,
            top_level_reason="SIGNATURE_INVALID", signature_validity="INVALID",
            trusted_signer_identity="UNESTABLISHED",
            cryptographic_signature_decision="INVALID",
            trust_store_validation="ABSENT", trust_membership_decision="NOT_EVALUATED",
        )
    for label, changed_keyring in (
        ("wrong_public_key", "semantic_keyring_wrong_public_key.json"),
        ("modified_signature_byte", "semantic_keyring_modified_signature.json"),
        ("signature_from_other_message", "semantic_keyring_other_message_signature.json"),
    ):
        add(
            f"signature.semantic.{label}", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
            manifest=manifest, verification_keys=changed_keyring,
            top_level_reason="SIGNATURE_INVALID", signature_validity="INVALID",
            trusted_signer_identity="UNESTABLISHED",
            cryptographic_signature_decision="INVALID",
            trust_store_validation="ABSENT", trust_membership_decision="NOT_EVALUATED",
        )
    add(
        "signature.semantic.matching_key_id", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, verification_keys=keyring,
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="VALID", trust_store_validation="ABSENT",
        trust_membership_decision="NO_STORE",
    )
    add(
        "signature.semantic.mismatched_decoded_key_id", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, verification_keys="semantic_keyring_key_id_mismatch.json",
        top_level_reason="SIGNATURE_INVALID", signature_validity="INVALID",
        trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="ABSENT", trust_membership_decision="NOT_EVALUATED",
    )
    for label, compatible_keyring in (
        ("canonical_public_key_spelling", keyring),
        ("public_key_nonzero_pad_bits", "semantic_keyring_public_key_alias.json"),
        ("canonical_signature_spelling", keyring),
        ("signature_nonzero_pad_bits", "semantic_keyring_signature_alias.json"),
    ):
        add(
            f"signature.semantic.{label}", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
            manifest=manifest, verification_keys=compatible_keyring,
            signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
            cryptographic_signature_decision="VALID", trust_store_validation="ABSENT",
            trust_membership_decision="NO_STORE",
            compatibility="ALREADY_RELEASED_BEHAVIOR",
        )
    add(
        "signature.semantic.keyring_absent_optional", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, signature_validity="ABSENT",
        trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="ABSENT", trust_membership_decision="NOT_EVALUATED",
    )
    add(
        "signature.semantic.keyring_absent_signature_required", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, require_signature=True, top_level_reason="SIGNATURE_REQUIRED",
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="ABSENT", trust_membership_decision="NOT_EVALUATED",
    )
    add(
        "signature.semantic.keyring_absent_membership_required_with_store", "SIGNATURE_SEMANTIC", "VERIFY_SIGNATURE",
        manifest=manifest, trust_store="semantic_trust_matching.json",
        require_trusted_signer=True, top_level_reason="SIGNATURE_REQUIRED",
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="VALID", trust_membership_decision="NOT_EVALUATED",
    )

    # G-06: fingerprint derivation, decoded-key uniqueness, and explicit-store
    # membership. All trust-store fixtures represent already acquired bytes.
    add(
        "trust.semantic.fingerprint_primary_key", "TRUST_SEMANTIC", "DERIVE_FINGERPRINT",
        key_material="PRIMARY", expected_fingerprint=primary_fingerprint,
    )
    add(
        "trust.semantic.fingerprint_secondary_key", "TRUST_SEMANTIC", "DERIVE_FINGERPRINT",
        key_material="SECONDARY", expected_fingerprint=secondary_fingerprint,
    )
    for label, store, validation, reason in (
        ("one_signer_valid", "semantic_trust_matching.json", "VALID", None),
        ("two_distinct_signers_valid", "semantic_trust_two_distinct.json", "VALID", None),
        ("duplicate_decoded_key_exact", "semantic_trust_duplicate_exact.json", "INVALID", "TRUST_STORE_INVALID"),
        ("duplicate_decoded_key_different_label", "semantic_trust_duplicate_label.json", "INVALID", "TRUST_STORE_INVALID"),
        ("duplicate_decoded_key_pad_bit_alias", "semantic_trust_duplicate_alias.json", "INVALID", "TRUST_STORE_INVALID"),
    ):
        add(
            f"trust.semantic.{label}", "TRUST_SEMANTIC", "VALIDATE_TRUST_STORE",
            trust_store=store, top_level_reason=reason,
            trust_store_validation=validation,
        )
    add(
        "trust.semantic.valid_signature_matching_store", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys=keyring,
        trust_store="semantic_trust_matching.json", require_trusted_signer=True,
        signature_validity="VALID", trusted_signer_identity="VALID",
        cryptographic_signature_decision="VALID", trust_store_validation="VALID",
        trust_membership_decision="MATCH", expected_fingerprint=primary_fingerprint,
    )
    add(
        "trust.semantic.valid_signature_nonmatching_store_optional", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys=keyring,
        trust_store="semantic_trust_nonmatching.json",
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="VALID", trust_store_validation="VALID",
        trust_membership_decision="NO_MATCH", expected_fingerprint=primary_fingerprint,
    )
    add(
        "trust.semantic.valid_signature_nonmatching_store_required", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys=keyring,
        trust_store="semantic_trust_nonmatching.json", require_trusted_signer=True,
        top_level_reason="TRUSTED_SIGNER_NOT_FOUND", signature_validity="VALID",
        trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="VALID", trust_store_validation="VALID",
        trust_membership_decision="NO_MATCH", expected_fingerprint=primary_fingerprint,
    )
    for label, required, reason in (
        ("empty_store_optional", False, None),
        ("empty_store_required", True, "TRUSTED_SIGNER_NOT_FOUND"),
    ):
        add(
            f"trust.semantic.{label}", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
            manifest=manifest, verification_keys=keyring,
            trust_store="semantic_trust_empty.json", require_trusted_signer=required,
            top_level_reason=reason, signature_validity="VALID",
            trusted_signer_identity="UNESTABLISHED",
            cryptographic_signature_decision="VALID", trust_store_validation="VALID",
            trust_membership_decision="NO_MATCH", expected_fingerprint=primary_fingerprint,
        )
    add(
        "trust.semantic.no_store_optional", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys=keyring,
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="VALID", trust_store_validation="ABSENT",
        trust_membership_decision="NO_STORE",
    )
    add(
        "trust.semantic.no_store_required", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys=keyring, require_trusted_signer=True,
        top_level_reason="TRUST_INPUT_NOT_PROVIDED",
        signature_validity="NOT_EVALUATED", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="ABSENT", trust_membership_decision="NO_STORE",
    )
    for label, required in (
        ("malformed_acquired_store_optional", False),
        ("malformed_acquired_store_required", True),
    ):
        add(
            f"trust.semantic.{label}", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
            manifest=manifest, verification_keys=keyring,
            trust_store="semantic_trust_malformed.json",
            require_trusted_signer=required, top_level_reason="TRUST_STORE_INVALID",
            signature_validity="NOT_EVALUATED", trusted_signer_identity="UNESTABLISHED",
            cryptographic_signature_decision="NOT_EVALUATED",
            trust_store_validation="INVALID", trust_membership_decision="NOT_EVALUATED",
        )
    add(
        "trust.semantic.store_present_unsigned_optional", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, trust_store="semantic_trust_matching.json",
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="VALID", trust_membership_decision="NOT_EVALUATED",
    )
    add(
        "trust.semantic.store_present_unsigned_required", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, trust_store="semantic_trust_matching.json",
        require_trusted_signer=True, top_level_reason="SIGNATURE_REQUIRED",
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="NOT_EVALUATED",
        trust_store_validation="VALID", trust_membership_decision="NOT_EVALUATED",
    )
    add(
        "trust.semantic.store_present_invalid_signature", "TRUST_SEMANTIC", "EVALUATE_MEMBERSHIP",
        manifest=manifest, verification_keys="semantic_keyring_modified_signature.json",
        trust_store="semantic_trust_matching.json",
        top_level_reason="SIGNATURE_INVALID", signature_validity="INVALID",
        trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision="INVALID", trust_store_validation="VALID",
        trust_membership_decision="NOT_EVALUATED",
    )

    vectors.extend(strict_ed25519_vectors())
    return vectors


def strict_ed25519_vectors() -> list[dict[str, Any]]:
    """Explicit ED25519_PORTABLE_STRICT_1 decisions; no backend is consulted."""
    vectors: list[dict[str, Any]] = []
    primary_public = SEMANTIC_MATERIALS["primary_key"]["public_key_hex"]
    primary_signature = SEMANTIC_MATERIALS["primary_manifest_signature"]["signature_hex"]
    primary_r = primary_signature[:64]
    frozen_message = source_fixture("semantic_manifest_valid.json")
    empty_message = source_bytes(b"")
    zero_s = "00" * 32

    def add(
        label: str,
        message: dict[str, Any],
        public_key: str,
        r_encoded: str,
        s_encoded: str,
        validity: str,
        stage: str,
        decisions: tuple[str, str, str, str, str, str],
        purpose: str,
        compatibility: str = "SAFE_CLARIFICATION",
        distinguishing_equations: dict[str, str] | None = None,
    ) -> None:
        vectors.append(
            strict_ed25519_case(
                f"signature.strict.{label}",
                message=message,
                public_key_hex=public_key,
                signature_hex=r_encoded + s_encoded,
                signature_validity=validity,
                failure_stage=stage,
                a_decoding=decisions[0],
                r_decoding=decisions[1],
                a_subgroup=decisions[2],
                r_subgroup=decisions[3],
                scalar_decision=decisions[4],
                equation_decision=decisions[5],
                purpose=purpose,
                compatibility=compatibility,
                distinguishing_equations=distinguishing_equations,
            )
        )

    add(
        "canonical_valid",
        frozen_message,
        primary_public,
        primary_r,
        primary_signature[64:],
        "VALID",
        "NONE",
        ("PASS", "PASS", "PASS", "PASS", "IN_RANGE", "PASS"),
        "Ordinary canonical Ed25519 material remains valid under the portable profile.",
    )
    add(
        "cofactored_only_domain_rejected",
        empty_message,
        IDENTITY_ENCODING,
        ORDER_TWO_ENCODING,
        zero_s,
        "INVALID",
        "A_IDENTITY",
        ("PASS", "PASS", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "The historical cofactored-versus-uncofactored discriminator is outside the strict public/subgroup domain and cannot enter a broader cofactored-only acceptance path.",
        "SAFE_CLARIFICATION",
        {
            "cofactored_equation": "PASS",
            "uncofactored_equation": "FAIL",
        },
    )
    add(
        "public_key_x_zero_sign_one",
        empty_message,
        IDENTITY_SIGN_ONE_ENCODING,
        IDENTITY_ENCODING,
        zero_s,
        "INVALID",
        "A_DECODE",
        ("FAIL", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "An x=0 public-key encoding with sign bit one is rejected by strict point decoding.",
        "OBSERVED_LEGACY_BACKEND_DIVERGENCE",
    )
    add(
        "public_key_y_p_plus_one",
        empty_message,
        Y_P_PLUS_ONE_ENCODING,
        IDENTITY_ENCODING,
        zero_s,
        "INVALID",
        "A_DECODE",
        ("FAIL", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "A non-canonical public-key encoding with y=p+1 is rejected before group operations.",
        "OBSERVED_LEGACY_BACKEND_DIVERGENCE",
    )
    add(
        "identity_public_key",
        empty_message,
        IDENTITY_ENCODING,
        IDENTITY_ENCODING,
        zero_s,
        "INVALID",
        "A_IDENTITY",
        ("PASS", "PASS", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "A canonical identity public key is rejected explicitly.",
        "OBSERVED_LEGACY_BACKEND_DIVERGENCE",
    )
    add(
        "nonidentity_small_order_public_key",
        empty_message,
        ORDER_TWO_ENCODING,
        IDENTITY_ENCODING,
        zero_s,
        "INVALID",
        "A_SUBGROUP",
        ("PASS", "PASS", "FAIL", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "The canonical non-identity order-two public key is outside the prime-order subgroup.",
    )
    add(
        "nonidentity_small_order_r",
        empty_message,
        primary_public,
        ORDER_TWO_ENCODING,
        zero_s,
        "INVALID",
        "R_SUBGROUP",
        ("PASS", "PASS", "PASS", "FAIL", "NOT_REACHED", "NOT_REACHED"),
        "A canonical non-identity order-two R is outside the prime-order subgroup.",
    )
    add(
        "noncanonical_r_x_zero_sign_one",
        empty_message,
        primary_public,
        IDENTITY_SIGN_ONE_ENCODING,
        zero_s,
        "INVALID",
        "R_DECODE",
        ("PASS", "FAIL", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "An x=0 R encoding with sign bit one is rejected during strict point decoding.",
    )
    add(
        "noncanonical_r_y_p_plus_one",
        empty_message,
        primary_public,
        Y_P_PLUS_ONE_ENCODING,
        zero_s,
        "INVALID",
        "R_DECODE",
        ("PASS", "FAIL", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED", "NOT_REACHED"),
        "A non-canonical R encoding with y=p+1 is rejected before group operations.",
    )
    add(
        "scalar_l_rejected",
        frozen_message,
        primary_public,
        primary_r,
        ED25519_L.to_bytes(32, "little").hex(),
        "INVALID",
        "S_RANGE",
        ("PASS", "PASS", "PASS", "PASS", "OUT_OF_RANGE", "NOT_REACHED"),
        "S=L is rejected before the verification equation.",
    )
    add(
        "scalar_l_minus_one_reaches_equation",
        frozen_message,
        primary_public,
        primary_r,
        (ED25519_L - 1).to_bytes(32, "little").hex(),
        "INVALID",
        "EQUATION",
        ("PASS", "PASS", "PASS", "PASS", "IN_RANGE", "FAIL"),
        "S=L-1 passes the scalar stage but this constructed signature fails the equation.",
    )
    add(
        "identity_r_reaches_equation",
        empty_message,
        primary_public,
        IDENTITY_ENCODING,
        zero_s,
        "INVALID",
        "EQUATION",
        ("PASS", "PASS", "PASS", "PASS", "IN_RANGE", "FAIL"),
        "Identity R is not rejected solely for identity; it reaches and fails the uncofactored equation.",
    )
    return vectors


PRECEDENCE_RELATION = [
    {"rank": 10, "stage": "EXPLICIT_TRUST_INPUT_PRESENCE", "reasons": ["TRUST_INPUT_NOT_PROVIDED"]},
    {"rank": 20, "stage": "ACQUIRED_TRUST_INPUT_VALIDATION", "reasons": ["TRUST_STORE_INVALID"]},
    {"rank": 30, "stage": "CANONICAL_SOURCE", "reasons": ["CANONICAL_NOT_JSON"]},
    {"rank": 40, "stage": "MANIFEST_SOURCE", "reasons": ["MANIFEST_NOT_JSON"]},
    {"rank": 50, "stage": "MANIFEST_ROOT", "reasons": ["MANIFEST_NOT_OBJECT"]},
    {"rank": 60, "stage": "MANIFEST_SCHEMA_IDENTIFIER", "reasons": ["MANIFEST_BAD_SCHEMA"]},
    {"rank": 70, "stage": "MANIFEST_INPUT_SCHEMA_IDENTIFIER", "reasons": ["MANIFEST_BAD_INPUT_SCHEMA"]},
    {"rank": 80, "stage": "MANIFEST_CANONICALIZATION_IDENTIFIER", "reasons": ["MANIFEST_BAD_CANONICALIZATION"]},
    {"rank": 90, "stage": "MANIFEST_TIMESTAMP_WHEN_ENABLED", "reasons": ["MANIFEST_BAD_TS_UTC"]},
    {"rank": 100, "stage": "MANIFEST_DIGEST_SPELLING", "reasons": ["MANIFEST_BAD_AI_HASH_SHA256"]},
    {"rank": 110, "stage": "PAYLOAD_DIGEST_COMPARISON", "reasons": ["HASH_MISMATCH"]},
    {"rank": 120, "stage": "SIGNATURE_VALIDITY", "reasons": ["SIGNATURE_INVALID"]},
    {"rank": 130, "stage": "SIGNATURE_ENFORCEMENT", "reasons": ["SIGNATURE_REQUIRED"]},
    {"rank": 140, "stage": "BINDING_VALIDITY", "reasons": ["BINDING_HASH_MISMATCH"]},
    {"rank": 150, "stage": "BINDING_ENFORCEMENT", "reasons": ["BINDING_REQUIRED"]},
    {"rank": 160, "stage": "TRUST_MEMBERSHIP_ENFORCEMENT", "reasons": ["TRUSTED_SIGNER_NOT_FOUND"]},
    {"rank": 170, "stage": "INVOCATION_IDENTITY", "reasons": ["INVOCATION_HASH_MISMATCH"]},
    {"rank": 180, "stage": "FRESHNESS", "reasons": ["FRESHNESS_TIMESTAMP_MALFORMED"]},
]


def precedence_binding_materials() -> dict[str, Any]:
    request_hash = hashlib.sha256(b"AELITIUM Phase 2 precedence request").hexdigest()
    response_hash = hashlib.sha256(b"AELITIUM Phase 2 precedence response").hexdigest()
    hash_input = json.dumps(
        {"request_hash": request_hash, "response_hash": response_hash},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    expected_hash = hashlib.sha256(hash_input).hexdigest()
    return {
        "NONE": {"fields_present": False},
        "REQUIRED_ABSENT": {"fields_present": False},
        "VALID": {
            "fields_present": True,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "canonical_hash_input_hex": hash_input.hex(),
            "expected_binding_hash": expected_hash,
            "manifest_binding_hash": expected_hash,
            "payload_binding_hash": expected_hash,
        },
        "HASH_MISMATCH": {
            "fields_present": True,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "canonical_hash_input_hex": hash_input.hex(),
            "expected_binding_hash": expected_hash,
            "manifest_binding_hash": ZERO_HASH,
            "payload_binding_hash": expected_hash,
        },
    }


def precedence_case(
    case_id: str,
    candidates: list[tuple[str, str]],
    winner: str,
    *,
    canonical_payload_fixture: str | None = "semantic_ai_canonical.json",
    canonical_inline_hex: str | None = None,
    manifest_fixture: str | None = "semantic_manifest_valid.json",
    manifest_source_case: str | None = None,
    manifest_overrides: dict[str, Any] | None = None,
    verification_keys_fixture: str | None = None,
    verification_keys_source_case: str | None = None,
    trust_store_fixture: str | None = None,
    binding_condition: str = "NONE",
    invocation_condition: str = "NONE",
    freshness_condition: str = "NONE",
    payload_hash_comparison: str = "MATCH",
    validate_manifest_timestamp: bool = True,
    require_signature: bool = False,
    require_binding: bool = False,
    require_trusted_signer: bool = False,
    signature_validity: str = "NOT_EVALUATED",
    trusted_signer_identity: str = "UNESTABLISHED",
    timestamp_decision: str = "PASS",
    not_evaluated_checks: list[str],
    bypassed_checks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": "PRECEDENCE",
        "inputs": {
            "canonical_payload_fixture": canonical_payload_fixture,
            "canonical_inline_hex": canonical_inline_hex,
            "manifest_fixture": manifest_fixture,
            "manifest_source_case": manifest_source_case,
            "manifest_overrides": {} if manifest_overrides is None else manifest_overrides,
            "verification_keys_fixture": verification_keys_fixture,
            "verification_keys_source_case": verification_keys_source_case,
            "trust_store_fixture": trust_store_fixture,
            "binding_condition": binding_condition,
            "invocation_condition": invocation_condition,
            "freshness_condition": freshness_condition,
            "payload_hash_comparison": payload_hash_comparison,
        },
        "verifier_options": {
            "validate_manifest_timestamp": validate_manifest_timestamp,
            "require_signature": require_signature,
            "require_binding": require_binding,
            "require_trusted_signer": require_trusted_signer,
        },
        "candidate_failures": [
            {"condition": condition, "reason": reason}
            for condition, reason in candidates
        ],
        "expected": {
            "winning_top_level_reason": winner,
            "signature_validity": signature_validity,
            "trusted_signer_identity": trusted_signer_identity,
            "timestamp_decision": timestamp_decision,
            "not_evaluated_checks": not_evaluated_checks,
            "bypassed_checks": [] if bypassed_checks is None else bypassed_checks,
        },
        "compatibility": "SAFE_CLARIFICATION",
    }


def precedence_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []

    def add(*args: Any, **kwargs: Any) -> None:
        vectors.append(precedence_case(*args, **kwargs))

    after_explicit_input = [
        "BUNDLE_INSPECTION", "CANONICAL_SOURCE", "MANIFEST_VALIDATION",
        "PAYLOAD_HASH", "KEYRING_SEMANTICS", "SIGNATURE_MATHEMATICS",
        "BINDING", "TRUST_MEMBERSHIP", "INVOCATION", "FRESHNESS",
    ]
    after_payload = [
        "KEYRING_SEMANTICS", "SIGNATURE_MATHEMATICS", "BINDING",
        "TRUST_MEMBERSHIP", "INVOCATION", "FRESHNESS",
    ]
    after_signature = ["TRUST_MEMBERSHIP"]

    add(
        "precedence.trust_input.required_absent_before_invalid_bundle",
        [
            ("REQUIRED_TRUST_INPUT_ABSENT", "TRUST_INPUT_NOT_PROVIDED"),
            ("CANONICAL_SOURCE_NOT_JSON", "CANONICAL_NOT_JSON"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "TRUST_INPUT_NOT_PROVIDED",
        canonical_payload_fixture=None, canonical_inline_hex="7b",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        payload_hash_comparison="NOT_REACHED",
        require_trusted_signer=True, trusted_signer_identity="UNESTABLISHED",
        timestamp_decision="NOT_REACHED", not_evaluated_checks=after_explicit_input,
    )
    add(
        "precedence.trust_input.malformed_acquired_before_invalid_bundle",
        [
            ("ACQUIRED_TRUST_STORE_INVALID", "TRUST_STORE_INVALID"),
            ("CANONICAL_SOURCE_NOT_JSON", "CANONICAL_NOT_JSON"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "TRUST_STORE_INVALID",
        canonical_payload_fixture=None, canonical_inline_hex="7b",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        trust_store_fixture="semantic_trust_malformed.json",
        payload_hash_comparison="NOT_REACHED",
        trusted_signer_identity="UNESTABLISHED", timestamp_decision="NOT_REACHED",
        not_evaluated_checks=after_explicit_input,
    )

    add(
        "precedence.payload.canonical_not_json_before_malformed_keyring",
        [
            ("CANONICAL_SOURCE_NOT_JSON", "CANONICAL_NOT_JSON"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "CANONICAL_NOT_JSON",
        canonical_payload_fixture=None, canonical_inline_hex="7b",
        verification_keys_source_case="keyring.source.trailing_garbage",
        payload_hash_comparison="NOT_REACHED",
        timestamp_decision="NOT_REACHED",
        not_evaluated_checks=["MANIFEST_VALIDATION", *after_payload],
    )
    add(
        "precedence.payload.manifest_not_json_before_malformed_keyring",
        [
            ("MANIFEST_SOURCE_NOT_JSON", "MANIFEST_NOT_JSON"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "MANIFEST_NOT_JSON",
        manifest_fixture=None, manifest_source_case="manifest.v1.source.trailing_garbage",
        verification_keys_source_case="keyring.source.trailing_garbage",
        payload_hash_comparison="NOT_REACHED",
        timestamp_decision="NOT_REACHED", not_evaluated_checks=after_payload,
    )
    add(
        "precedence.payload.manifest_not_object_before_malformed_keyring",
        [
            ("MANIFEST_ROOT_NOT_OBJECT", "MANIFEST_NOT_OBJECT"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "MANIFEST_NOT_OBJECT",
        manifest_fixture=None, manifest_source_case="manifest.v1.source.non_object_root",
        verification_keys_source_case="keyring.source.trailing_garbage",
        payload_hash_comparison="NOT_REACHED",
        timestamp_decision="NOT_REACHED", not_evaluated_checks=after_payload,
    )
    add(
        "precedence.payload.hash_mismatch_before_malformed_keyring",
        [
            ("MANIFEST_PAYLOAD_HASH_MISMATCH", "HASH_MISMATCH"),
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
        ],
        "HASH_MISMATCH",
        manifest_overrides={"ai_hash_sha256": ZERO_HASH},
        verification_keys_source_case="keyring.source.trailing_garbage",
        payload_hash_comparison="MISMATCH", signature_validity="NOT_EVALUATED",
        not_evaluated_checks=after_payload,
    )

    add(
        "precedence.signature.invalid_before_signature_required",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("SIGNATURE_ENFORCEMENT_REQUESTED", "SIGNATURE_REQUIRED"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        require_signature=True, signature_validity="INVALID",
        trusted_signer_identity="UNESTABLISHED", not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.invalid_before_binding_mismatch",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("BINDING_HASH_MISMATCH_PRESENT", "BINDING_HASH_MISMATCH"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        binding_condition="HASH_MISMATCH", signature_validity="INVALID",
        trusted_signer_identity="UNESTABLISHED", not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.invalid_before_binding_required",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("REQUIRED_BINDING_ABSENT", "BINDING_REQUIRED"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        binding_condition="REQUIRED_ABSENT", require_binding=True,
        signature_validity="INVALID", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.invalid_before_required_membership",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("REQUIRED_SIGNER_MEMBERSHIP_MISSING", "TRUSTED_SIGNER_NOT_FOUND"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        trust_store_fixture="semantic_trust_nonmatching.json",
        require_trusted_signer=True, signature_validity="INVALID",
        trusted_signer_identity="UNESTABLISHED", not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.invalid_before_authorized_invocation_failure",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("AUTHORIZED_INVOCATION_HASH_MISMATCH", "INVOCATION_HASH_MISMATCH"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        invocation_condition="AUTHORIZED_HASH_MISMATCH",
        signature_validity="INVALID", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.invalid_before_authorized_freshness_failure",
        [
            ("PRESENT_SIGNATURE_INVALID", "SIGNATURE_INVALID"),
            ("AUTHORIZED_FRESHNESS_TIMESTAMP_MALFORMED", "FRESHNESS_TIMESTAMP_MALFORMED"),
        ],
        "SIGNATURE_INVALID",
        verification_keys_fixture="semantic_keyring_modified_signature.json",
        freshness_condition="AUTHORIZED_TIMESTAMP_MALFORMED",
        signature_validity="INVALID", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=after_signature,
    )

    add(
        "precedence.signature.required_before_binding_mismatch",
        [
            ("SIGNATURE_ENFORCEMENT_REQUESTED", "SIGNATURE_REQUIRED"),
            ("BINDING_HASH_MISMATCH_PRESENT", "BINDING_HASH_MISMATCH"),
        ],
        "SIGNATURE_REQUIRED",
        require_signature=True, binding_condition="HASH_MISMATCH",
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.required_for_membership_with_valid_store",
        [
            ("SIGNATURE_ENFORCEMENT_REQUESTED", "SIGNATURE_REQUIRED"),
            ("REQUIRED_SIGNER_MEMBERSHIP_MISSING", "TRUSTED_SIGNER_NOT_FOUND"),
        ],
        "SIGNATURE_REQUIRED",
        trust_store_fixture="semantic_trust_empty.json", require_trusted_signer=True,
        signature_validity="ABSENT", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=after_signature,
    )
    add(
        "precedence.signature.no_trust_input_before_unsigned_bundle",
        [
            ("REQUIRED_TRUST_INPUT_ABSENT", "TRUST_INPUT_NOT_PROVIDED"),
            ("SIGNATURE_ENFORCEMENT_REQUESTED", "SIGNATURE_REQUIRED"),
        ],
        "TRUST_INPUT_NOT_PROVIDED",
        require_trusted_signer=True, signature_validity="NOT_EVALUATED",
        trusted_signer_identity="UNESTABLISHED", timestamp_decision="NOT_REACHED",
        not_evaluated_checks=after_explicit_input,
    )

    add(
        "precedence.binding.mismatch_before_required_membership",
        [
            ("BINDING_HASH_MISMATCH_PRESENT", "BINDING_HASH_MISMATCH"),
            ("REQUIRED_SIGNER_MEMBERSHIP_MISSING", "TRUSTED_SIGNER_NOT_FOUND"),
        ],
        "BINDING_HASH_MISMATCH",
        verification_keys_fixture="semantic_keyring_valid.json",
        trust_store_fixture="semantic_trust_nonmatching.json",
        binding_condition="HASH_MISMATCH", require_trusted_signer=True,
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=[],
    )
    add(
        "precedence.binding.valid_then_required_membership_missing",
        [("REQUIRED_SIGNER_MEMBERSHIP_MISSING", "TRUSTED_SIGNER_NOT_FOUND")],
        "TRUSTED_SIGNER_NOT_FOUND",
        verification_keys_fixture="semantic_keyring_valid.json",
        trust_store_fixture="semantic_trust_nonmatching.json",
        binding_condition="VALID", require_trusted_signer=True,
        signature_validity="VALID", trusted_signer_identity="UNESTABLISHED",
        not_evaluated_checks=[],
    )

    add(
        "precedence.manifest.bad_schema_before_bad_input_schema",
        [
            ("MANIFEST_SCHEMA_BAD", "MANIFEST_BAD_SCHEMA"),
            ("MANIFEST_INPUT_SCHEMA_BAD", "MANIFEST_BAD_INPUT_SCHEMA"),
        ],
        "MANIFEST_BAD_SCHEMA",
        manifest_overrides={"schema": "bad", "input_schema": "bad"},
        signature_validity="ABSENT", timestamp_decision="NOT_REACHED",
        not_evaluated_checks=["MANIFEST_LATER_FIELDS", *after_payload],
    )
    add(
        "precedence.manifest.bad_input_schema_before_bad_canonicalization",
        [
            ("MANIFEST_INPUT_SCHEMA_BAD", "MANIFEST_BAD_INPUT_SCHEMA"),
            ("MANIFEST_CANONICALIZATION_BAD", "MANIFEST_BAD_CANONICALIZATION"),
        ],
        "MANIFEST_BAD_INPUT_SCHEMA",
        manifest_overrides={"input_schema": "bad", "canonicalization": "bad"},
        signature_validity="ABSENT", timestamp_decision="NOT_REACHED",
        not_evaluated_checks=["MANIFEST_LATER_FIELDS", *after_payload],
    )
    add(
        "precedence.manifest.bad_canonicalization_before_bad_timestamp",
        [
            ("MANIFEST_CANONICALIZATION_BAD", "MANIFEST_BAD_CANONICALIZATION"),
            ("MANIFEST_TIMESTAMP_BAD_ENABLED", "MANIFEST_BAD_TS_UTC"),
        ],
        "MANIFEST_BAD_CANONICALIZATION",
        manifest_overrides={"canonicalization": "bad", "ts_utc": "not-a-timestamp"},
        signature_validity="ABSENT", timestamp_decision="NOT_REACHED",
        not_evaluated_checks=["MANIFEST_LATER_FIELDS", *after_payload],
    )
    add(
        "precedence.manifest.bad_timestamp_before_bad_digest_spelling",
        [
            ("MANIFEST_TIMESTAMP_BAD_ENABLED", "MANIFEST_BAD_TS_UTC"),
            ("MANIFEST_DIGEST_SPELLING_BAD", "MANIFEST_BAD_AI_HASH_SHA256"),
        ],
        "MANIFEST_BAD_TS_UTC",
        manifest_overrides={"ts_utc": "not-a-timestamp", "ai_hash_sha256": "X" * 64},
        payload_hash_comparison="NOT_REACHED",
        signature_validity="ABSENT", timestamp_decision="FAIL",
        not_evaluated_checks=["MANIFEST_LATER_FIELDS", *after_payload],
    )
    add(
        "precedence.manifest.bad_digest_spelling_before_hash_mismatch",
        [
            ("MANIFEST_DIGEST_SPELLING_BAD", "MANIFEST_BAD_AI_HASH_SHA256"),
            ("MANIFEST_PAYLOAD_HASH_MISMATCH", "HASH_MISMATCH"),
        ],
        "MANIFEST_BAD_AI_HASH_SHA256",
        manifest_overrides={
            "ai_hash_sha256": hashlib.sha256(
                SEMANTIC_FIXTURE_BYTES["semantic_ai_canonical.json"]
            ).hexdigest().upper()
        },
        payload_hash_comparison="MISMATCH",
        signature_validity="ABSENT",
        not_evaluated_checks=["PAYLOAD_HASH", *after_payload],
    )
    add(
        "precedence.manifest.timestamp_disabled_allows_later_digest_failure",
        [("MANIFEST_DIGEST_SPELLING_BAD", "MANIFEST_BAD_AI_HASH_SHA256")],
        "MANIFEST_BAD_AI_HASH_SHA256",
        manifest_overrides={"ts_utc": {"malformed": True}, "ai_hash_sha256": "bad"},
        validate_manifest_timestamp=False, timestamp_decision="BYPASSED",
        payload_hash_comparison="NOT_REACHED",
        signature_validity="ABSENT",
        not_evaluated_checks=["PAYLOAD_HASH", *after_payload],
        bypassed_checks=["MANIFEST_TIMESTAMP"],
    )
    return vectors


def documents() -> dict[Path, bytes]:
    sources = source_vectors()
    schemas = schema_vectors()
    semantics = semantic_vectors()
    precedence = precedence_vectors()
    all_ids = [case["case_id"] for case in sources + schemas + semantics + precedence]
    if len(all_ids) != len(set(all_ids)):
        raise AssertionError("builder contains duplicate case IDs")

    source_document = {
        "contract": "aelitium-verifier-contract-phase2-source-vectors-v1",
        "scope": "SOURCE",
        "source_descriptor_contract": {
            "FIXTURE": "path is relative to this corpus directory and names exact raw bytes",
            "INLINE_HEX": "hex is an even-length lowercase hexadecimal encoding of exact raw bytes",
            "INLINE_UTF8": "text is encoded once as strict UTF-8 to obtain exact raw bytes",
            "sha256": "lowercase hexadecimal SHA-256 of the exact raw bytes",
        },
        "case_count": len(sources),
        "vectors": sources,
    }
    schema_document = {
        "contract": "aelitium-verifier-contract-phase2-schema-vectors-v1",
        "scope": "SCHEMA",
        "instance_recipe_contract": {
            "contract": "AELITIUM-SCHEMA-INSTANCE-RECIPE-1",
            "initial_value": "deep copy of the named top-level template",
            "mutation_order": "array order, from first to last",
            "pointer": "slash-separated object names or zero-based array indexes; ~0 denotes ~ and ~1 denotes /",
            "REMOVE": "remove the existing value at path",
            "SET": "deep-copy value to path, replacing an existing value or creating the final object member",
        },
        "case_count": len(schemas),
        "templates": SCHEMA_TEMPLATES,
        "vectors": schemas,
    }
    semantic_document = {
        "contract": "aelitium-verifier-contract-phase2-semantic-vectors-v1",
        "scope": "SIGNATURE_TRUST_AND_ED25519_PORTABLE_PROFILE_SEMANTICS",
        "test_material_notice": TEST_KEY_NOTICE,
        "claim_boundary": [
            "signature_validity=VALID establishes only mathematical validity for the exact raw manifest message under the bundled public key.",
            "Signature validity does not establish trusted organizational identity, authorization, provider execution, historical occurrence, response causation, semantic truth, or legal compliance.",
            "trusted_signer_identity=VALID establishes only exact decoded-key membership in the explicit trust input.",
        ],
        "fixture_hashes": {
            name: hashlib.sha256(raw).hexdigest()
            for name, raw in sorted(SEMANTIC_FIXTURE_BYTES.items())
        },
        "materials": SEMANTIC_MATERIALS,
        "ed25519_portable_profile": {
            "profile": ED25519_PROFILE,
            "selection": "REQUESTED_EFFECTIVE_EXPLICIT_EQUAL_NO_FALLBACK",
            "applies_to_signature_evaluation_in_all_families": True,
            "point_decoding": "RFC8032_5_1_3_CANONICAL_Y_X0_SIGN_STRICT",
            "public_key_policy": "NON_IDENTITY_PRIME_ORDER_SUBGROUP",
            "r_policy": "PRIME_ORDER_SUBGROUP_IDENTITY_PERMITTED",
            "scalar_policy": "LITTLE_ENDIAN_0_LE_S_LT_L",
            "hash_policy": "SHA512_R_ENCODED_A_ENCODED_RAW_MESSAGE_LITTLE_ENDIAN_MOD_L",
            "equation": "UNCOFACTORED_S_B_EQUALS_R_PLUS_K_A",
            "fallback": "NONE",
        },
        "state_vocabulary": {
            "top_level_reason": [
                None,
                "SIGNATURE_INVALID",
                "SIGNATURE_REQUIRED",
                "TRUST_INPUT_NOT_PROVIDED",
                "TRUST_STORE_INVALID",
                "TRUSTED_SIGNER_NOT_FOUND",
            ],
            "signature_validity": ["ABSENT", "INVALID", "NOT_EVALUATED", "VALID"],
            "trusted_signer_identity": ["NOT_EVALUATED", "UNESTABLISHED", "VALID"],
            "cryptographic_signature_decision": ["INVALID", "NOT_EVALUATED", "VALID"],
            "trust_store_validation": ["ABSENT", "INVALID", "NOT_EVALUATED", "VALID"],
            "trust_membership_decision": ["MATCH", "NOT_EVALUATED", "NO_MATCH", "NO_STORE"],
        },
        "case_count": len(semantics),
        "family_counts": {
            "SIGNATURE_SEMANTIC": sum(
                case["family"] == "SIGNATURE_SEMANTIC" for case in semantics
            ),
            "TRUST_SEMANTIC": sum(
                case["family"] == "TRUST_SEMANTIC" for case in semantics
            ),
            "ED25519_STRICT_SEMANTIC": sum(
                case["family"] == "ED25519_STRICT_SEMANTIC" for case in semantics
            ),
        },
        "vectors": semantics,
    }
    precedence_document = {
        "contract": "aelitium-verifier-contract-phase2-precedence-vectors-v1",
        "scope": "PHASE2_PRECEDENCE_AND_CROSS_CONTRACT",
        "candidate_failure_contract": {
            "condition": "closed language-neutral condition identifier whose evidence is validated by the runner",
            "reason": "authorized public reason implied by condition",
            "winner": "candidate with the lowest rank in precedence_relation",
            "downstream_candidate": "may describe a failure that would apply only if every earlier check succeeded",
            "not_evaluated_checks": "explicit list of checks blocked by an unmet prerequisite; an empty list preserves independent post-payload dimension evaluation",
        },
        "input_recipe_contract": {
            "fixture_reference": "bare fixture name resolved through semantic_vectors.json fixture_hashes",
            "source_case_reference": "case_id resolved to the exact source descriptor and expected source decision in source_vectors.json",
            "canonical_inline_hex": "lowercase hexadecimal encoding of exact canonical-input bytes",
            "manifest_overrides": "replace the named top-level decoded values in the referenced manifest fixture for candidate-condition evaluation; no signature is regenerated",
            "binding_condition": "select the correspondingly named frozen entry in binding_materials",
            "authorized_downstream_condition": "rank-only candidate already named by Level 1; it does not define G-07 invocation grammar or G-11 Freshness policy",
        },
        "precedence_relation": PRECEDENCE_RELATION,
        "binding_materials": precedence_binding_materials(),
        "check_vocabulary": [
            "BINDING",
            "BUNDLE_INSPECTION",
            "CANONICAL_SOURCE",
            "FRESHNESS",
            "INVOCATION",
            "KEYRING_SEMANTICS",
            "MANIFEST_LATER_FIELDS",
            "MANIFEST_TIMESTAMP",
            "MANIFEST_VALIDATION",
            "PAYLOAD_HASH",
            "SIGNATURE_MATHEMATICS",
            "TRUST_MEMBERSHIP",
        ],
        "deliberate_exclusions": [
            {
                "case": "TRUSTED_SIGNER_NOT_FOUND_VS_CONCRETE_INVOCATION_OR_FRESHNESS_FAILURE",
                "status": "EXCLUDED_FROM_PHASE2_FIXTURES",
                "reason": "A concrete end-to-end downstream fixture would require completing open G-07 invocation or G-11 Freshness semantics. Level 1 prose already places TRUSTED_SIGNER_NOT_FOUND first; Phase 2 does not invent the missing cross-gap input contract.",
            }
        ],
        "case_count": len(precedence),
        "vectors": precedence,
    }

    def count_source(kind: str) -> int:
        return sum(case["input_kind"] == kind for case in sources)

    def count_schema(family: str) -> int:
        return sum(case["family"] == family for case in schemas)

    counts = {
        "total": len(sources) + len(schemas) + len(semantics) + len(precedence),
        "source_total": len(sources),
        "schema_total": len(schemas),
        "semantic_total": len(semantics),
        "signature_semantic": semantic_document["family_counts"]["SIGNATURE_SEMANTIC"],
        "trust_semantic": semantic_document["family_counts"]["TRUST_SEMANTIC"],
        "ed25519_strict_semantic": semantic_document["family_counts"]["ED25519_STRICT_SEMANTIC"],
        "precedence_total": len(precedence),
        "manifest_source": count_source("MANIFEST_V1") + count_source("MANIFEST_V2"),
        "manifest_schema": count_schema("MANIFEST_SCHEMA"),
        "keyring_source": count_source("VERIFICATION_KEYS_V1"),
        "keyring_schema": count_schema("KEYRING_SCHEMA"),
        "trust_source": count_source("TRUST_STORE_V1"),
        "trust_schema": count_schema("TRUST_SCHEMA"),
    }
    manifest = {
        "contract": "aelitium-verifier-contract-phase2-conformance-v1",
        "status": "NORMATIVE-UNRELEASED",
        "scope": "SOURCE_SCHEMA_SIGNATURE_TRUST_ED25519_PORTABLE_PROFILE_PRECEDENCE",
        "subject_contract": "aelitium-verifier-input-contracts-v1",
        "vector_files": [
            "source_vectors.json",
            "schema_vectors.json",
            "semantic_vectors.json",
            "precedence_vectors.json",
        ],
        "schemas": {
            "MANIFEST_V1": "../../engine/schemas/ai_manifest_v1.json",
            "MANIFEST_V2": "../../engine/schemas/ai_manifest_v2.json",
            "TRUST_STORE_V1": "../../engine/schemas/trust_store_v1.json",
            "VERIFICATION_KEYS_V1": "../../engine/schemas/verification_keys_v1.json",
        },
        "case_counts": counts,
        "fixture_count": len(FIXTURE_BYTES),
        "case_id_policy": "GLOBALLY_UNIQUE_ASCII_LOWERCASE_DOT_SEPARATED",
        "byte_source_contract": "INLINE_UTF8_OR_INLINE_HEX_OR_FIXTURE_WITH_SHA256",
        "instance_recipe_contract": "AELITIUM-SCHEMA-INSTANCE-RECIPE-1",
        "runner": "../run_verifier_contract_phase2.py",
        "block_2a_frozen": {
            "case_count": 210,
            "source_vectors_sha256": BLOCK2A_SOURCE_SHA256,
            "schema_vectors_sha256": BLOCK2A_SCHEMA_SHA256,
        },
        "block_2b1_frozen": {
            "case_count": 36,
            "original_semantic_vectors_sha256": BLOCK2B1_SEMANTIC_SHA256,
            "original_vector_set_sha256": BLOCK2B1_VECTOR_SET_SHA256,
        },
        "block_2b2_frozen": {
            "case_count": 23,
            "precedence_vectors_sha256": BLOCK2B2_PRECEDENCE_SHA256,
        },
        "block_3": {
            "status": "ED25519_RUNTIME_ALIGNMENT_PENDING",
            "closure_claimed": False,
            "closure_mechanism": None,
        },
        "ed25519_portable_profile": {
            "profile": ED25519_PROFILE,
            "status": "NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
            "case_count": semantic_document["family_counts"]["ED25519_STRICT_SEMANTIC"],
            "fallback": "NONE",
        },
        "gap_status": {
            "G-04": "CLOSED",
            "G-05": "OPEN — NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
            "G-06": "CLOSED",
        },
        "notes": [
            "Expected decisions are authored from Level 1 prose, not generated from Python verifier behavior.",
            "Runner code is non-normative and cannot override frozen expected data or Level 1 prose.",
            "Filesystem acquisition remains in the existing G-09 operational-policy corpus.",
            "The original 269 Phase 2 cases retain their identifiers and expected decisions.",
            "ED25519_PORTABLE_STRICT_1 expectations are evaluated by a conformance-only arithmetic implementation, not the production or cryptography verifier.",
            "G-04 and G-06 are closed by Phase 2 normative input contracts, schemas, and conformance data.",
            "G-05 remains open until production capability selection and ED25519_PORTABLE_STRICT_1 execution align.",
        ],
    }

    result = {
        CORPUS / "source_vectors.json": canonical_json(source_document),
        CORPUS / "schema_vectors.json": canonical_json(schema_document),
        CORPUS / "semantic_vectors.json": canonical_json(semantic_document),
        CORPUS / "precedence_vectors.json": canonical_json(precedence_document),
        CORPUS / "manifest.json": canonical_json(manifest),
    }
    result.update({FIXTURES / name: raw for name, raw in FIXTURE_BYTES.items()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="check that committed data equal deterministic builder output",
    )
    args = parser.parse_args()

    expected_files = documents()
    if args.check:
        mismatches = []
        actual_files = {
            path
            for path in CORPUS.rglob("*")
            if path.is_file()
        }
        unexpected = sorted(actual_files - set(expected_files))
        for path in unexpected:
            mismatches.append(f"unexpected: {path.relative_to(ROOT.parent)}")
        for path, expected_bytes in expected_files.items():
            try:
                observed = path.read_bytes()
            except OSError:
                mismatches.append(f"missing: {path.relative_to(ROOT.parent)}")
                continue
            if observed != expected_bytes:
                mismatches.append(f"differs: {path.relative_to(ROOT.parent)}")
        if mismatches:
            print("\n".join(mismatches), file=sys.stderr)
            return 1
        print(f"PASS deterministic corpus {len(expected_files)}/{len(expected_files)} files")
        return 0

    CORPUS.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for path, contents in expected_files.items():
        path.write_bytes(contents)
    print(f"wrote {len(expected_files)} frozen corpus files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
