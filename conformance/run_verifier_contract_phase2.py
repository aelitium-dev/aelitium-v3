#!/usr/bin/env python3
"""Validate the frozen AELITIUM verifier-input Phase 2 corpus.

This runner is non-normative and deliberately independent of AELITIUM's
production verifier, signing, and trust modules. It checks the committed
source/schema, signature/trust semantic, and cross-contract precedence cases.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
CORPUS = ROOT / "verifier_contract_phase2"
MANIFEST_PATH = CORPUS / "manifest.json"
SOURCE_PATH = CORPUS / "source_vectors.json"
SCHEMA_PATH = CORPUS / "schema_vectors.json"
SEMANTIC_PATH = CORPUS / "semantic_vectors.json"
PRECEDENCE_PATH = CORPUS / "precedence_vectors.json"

EXPECTED_CONTRACT = "aelitium-verifier-contract-phase2-conformance-v1"
EXPECTED_SOURCE_CONTRACT = "aelitium-verifier-contract-phase2-source-vectors-v1"
EXPECTED_SCHEMA_CONTRACT = "aelitium-verifier-contract-phase2-schema-vectors-v1"
EXPECTED_SEMANTIC_CONTRACT = "aelitium-verifier-contract-phase2-semantic-vectors-v1"
EXPECTED_PRECEDENCE_CONTRACT = "aelitium-verifier-contract-phase2-precedence-vectors-v1"
EXPECTED_SUBJECT = "aelitium-verifier-input-contracts-v1"
EXPECTED_TEST_KEY_NOTICE = (
    "PUBLIC TEST-ONLY deterministic Ed25519 seeds for conformance reproduction; "
    "not production secrets and not secure key-generation guidance."
)
BLOCK2A_SOURCE_SHA256 = "2caa5c78cae1c145e1c4630469a49ebf2ebc6ec85df91f90e8628bc1d3b9268e"
BLOCK2A_SCHEMA_SHA256 = "65a99dd490e9710aefb7dbb7547beb07f75bdfb3e6e0d8f292d9cc8a6e295fe4"
BLOCK2B1_SEMANTIC_SHA256 = "b2f6d5c0263c97006bad15af985099869264ac5f4833ef356526a6945909ffd9"
BLOCK2B1_VECTOR_SET_SHA256 = "7260d1216c1fe0b9e340fc4e1a0d1ee075a37c785d486d7370fabf9c73c958f1"
BLOCK2B2_PRECEDENCE_SHA256 = "810b62d3a9d0c311a1bb58c7a361083bb1881a16406c65bcea9d6c76ee3f89c1"
ED25519_PROFILE = "ED25519_PORTABLE_STRICT_1"
ED25519_P = 2**255 - 19
ED25519_L = 2**252 + 27742317777372353535851937790883648493
ED25519_D = (-121665 * pow(121666, ED25519_P - 2, ED25519_P)) % ED25519_P
ED25519_SQRT_M1 = pow(2, (ED25519_P - 1) // 4, ED25519_P)
ED25519_IDENTITY = (0, 1)
EXPECTED_SCHEMA_IDS = {
    "MANIFEST_V1": "aelitium://schemas/ai_manifest_v1.json",
    "MANIFEST_V2": "aelitium://schemas/ai_manifest_v2.json",
    "VERIFICATION_KEYS_V1": "aelitium://schemas/verification_keys_v1.json",
    "TRUST_STORE_V1": "aelitium://schemas/trust_store_v1.json",
}
SCHEMA_FILENAMES = {
    "MANIFEST_V1": "ai_manifest_v1.json",
    "MANIFEST_V2": "ai_manifest_v2.json",
    "VERIFICATION_KEYS_V1": "verification_keys_v1.json",
    "TRUST_STORE_V1": "trust_store_v1.json",
}
SOURCE_FAMILIES = {
    "MANIFEST_SOURCE",
    "MANIFEST_TIMESTAMP_V1",
    "MANIFEST_TIMESTAMP_V2",
    "KEYRING_SOURCE",
    "TRUST_SOURCE",
}
SCHEMA_FAMILIES = {"MANIFEST_SCHEMA", "KEYRING_SCHEMA", "TRUST_SCHEMA"}
INPUT_KINDS = set(EXPECTED_SCHEMA_IDS)
ROUTES = {"LEGACY_V1", "PORTABLE_V2", "LEGACY_ERROR_RESOLUTION", "NOT_APPLICABLE"}
SOURCE_DECISIONS = {"ACCEPT", "REJECT", "OPERATIONAL"}
SCHEMA_DECISIONS = {"VALID", "INVALID", "NOT_REACHED"}
TIMESTAMP_DECISIONS = {"PASS", "FAIL", "BYPASSED", "OPERATIONAL", "NOT_APPLICABLE", "NOT_REACHED"}
COMPATIBILITY = {
    "ALREADY_RELEASED_BEHAVIOR",
    "SAFE_CLARIFICATION",
    "ADOPTED_CAPABILITY_POLICY",
    "UNRELEASED_V2_ONLY",
    "OBSERVED_LEGACY_BACKEND_DIVERGENCE",
}
SEMANTIC_REASONS = {
    None,
    "MANIFEST_NOT_JSON",
    "MANIFEST_NOT_OBJECT",
    "MANIFEST_BAD_SCHEMA",
    "MANIFEST_BAD_INPUT_SCHEMA",
    "MANIFEST_BAD_CANONICALIZATION",
    "MANIFEST_BAD_TS_UTC",
    "MANIFEST_BAD_AI_HASH_SHA256",
    "MANIFEST_MISSING_FIELD",
    "SIGNATURE_INVALID",
    "TRUST_STORE_INVALID",
}
OPERATIONAL_CODES = {None, "INPUT_OUTSIDE_DECLARED_CAPABILITY"}
CAPABILITIES = {
    "V1_FROZEN_LEGACY_COMPATIBILITY",
    "V1_NAMED_RUNTIME_COMPATIBILITY",
    "V2_PORTABLE",
}
PROCEDURAL_REQUIREMENTS = {
    "NONE",
    "ORDERED_MANIFEST_PRESENCE",
    "SOURCE_PROFILE",
    "TIMESTAMP_OPTION",
    "KEY_ID_EQUALITY",
    "BASE64_DECODED_LENGTH",
    "BASE64_PAD_BITS",
    "ED25519_VERIFICATION",
    "FINGERPRINT_UNIQUENESS",
    "SOURCE_COLLAPSE",
}
FOCUS_VALUES = {
    "REQUIRED_MEMBER",
    "MULTIPLE_REQUIRED_MEMBERS",
    "SCHEMA_IDENTIFIER",
    "INPUT_SCHEMA_IDENTIFIER",
    "CANONICALIZATION_IDENTIFIER",
    "AI_HASH_SHA256",
    "OPEN_OBJECT",
    "TIMESTAMP_SCHEMA_NEUTRALITY",
    "STRUCTURE",
    "FORMAT_IDENTIFIER",
    "CARDINALITY",
    "ENTRY_TYPE",
    "KEY_ID",
    "ALGORITHM",
    "SCOPE",
    "BASE64_PUBLIC_KEY",
    "BASE64_SIGNATURE",
    "SIGNATURE_MATHEMATICS",
    "CLOSED_OBJECT",
    "LABEL",
    "FINGERPRINT_UNIQUENESS",
}
CASE_ID = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+")
LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})*")
ASCII_V2_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)
MAX_SAFE_INTEGER = 9_007_199_254_740_991
DIGIT_POSITIONS = (0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18)
SEPARATORS = {4: "-", 7: "-", 10: "T", 13: ":", 16: ":", 19: "Z"}
EXPECTED_BLOCK2A_COUNTS = {
    "total": 210,
    "source_total": 100,
    "schema_total": 110,
    "manifest_source": 69,
    "manifest_schema": 46,
    "keyring_source": 17,
    "keyring_schema": 39,
    "trust_source": 14,
    "trust_schema": 25,
}
EXPECTED_SEMANTIC_COUNTS = {
    "SIGNATURE_SEMANTIC": 17,
    "TRUST_SEMANTIC": 19,
    "ED25519_STRICT_SEMANTIC": 12,
}
EXPECTED_PRECEDENCE_COUNT = 23
EXPECTED_ALL_COUNTS = {
    **EXPECTED_BLOCK2A_COUNTS,
    "total": 281,
    "semantic_total": 48,
    "signature_semantic": 17,
    "trust_semantic": 19,
    "ed25519_strict_semantic": 12,
    "precedence_total": EXPECTED_PRECEDENCE_COUNT,
}
SEMANTIC_FAMILIES = set(EXPECTED_SEMANTIC_COUNTS)
SEMANTIC_OPERATIONS = {
    "DERIVE_FINGERPRINT",
    "EVALUATE_MEMBERSHIP",
    "VALIDATE_TRUST_STORE",
    "VERIFY_SIGNATURE",
}
SEMANTIC_TOP_REASONS = {
    None,
    "SIGNATURE_INVALID",
    "SIGNATURE_REQUIRED",
    "TRUST_INPUT_NOT_PROVIDED",
    "TRUST_STORE_INVALID",
    "TRUSTED_SIGNER_NOT_FOUND",
}
SIGNATURE_STATES = {"ABSENT", "INVALID", "NOT_EVALUATED", "VALID"}
TRUST_STATES = {"NOT_EVALUATED", "UNESTABLISHED", "VALID"}
CRYPTO_DECISIONS = {"INVALID", "NOT_EVALUATED", "VALID"}
STORE_DECISIONS = {"ABSENT", "INVALID", "NOT_EVALUATED", "VALID"}
MEMBERSHIP_DECISIONS = {"MATCH", "NOT_EVALUATED", "NO_MATCH", "NO_STORE"}
PUBLIC_KEY_B64 = re.compile(r"[A-Za-z0-9+/]{43}=")
SIGNATURE_B64 = re.compile(r"[A-Za-z0-9+/]{86}==")
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
CONDITION_REASONS = {
    "REQUIRED_TRUST_INPUT_ABSENT": "TRUST_INPUT_NOT_PROVIDED",
    "ACQUIRED_TRUST_STORE_INVALID": "TRUST_STORE_INVALID",
    "CANONICAL_SOURCE_NOT_JSON": "CANONICAL_NOT_JSON",
    "MANIFEST_SOURCE_NOT_JSON": "MANIFEST_NOT_JSON",
    "MANIFEST_ROOT_NOT_OBJECT": "MANIFEST_NOT_OBJECT",
    "MANIFEST_SCHEMA_BAD": "MANIFEST_BAD_SCHEMA",
    "MANIFEST_INPUT_SCHEMA_BAD": "MANIFEST_BAD_INPUT_SCHEMA",
    "MANIFEST_CANONICALIZATION_BAD": "MANIFEST_BAD_CANONICALIZATION",
    "MANIFEST_TIMESTAMP_BAD_ENABLED": "MANIFEST_BAD_TS_UTC",
    "MANIFEST_DIGEST_SPELLING_BAD": "MANIFEST_BAD_AI_HASH_SHA256",
    "MANIFEST_PAYLOAD_HASH_MISMATCH": "HASH_MISMATCH",
    "PRESENT_SIGNATURE_INVALID": "SIGNATURE_INVALID",
    "SIGNATURE_ENFORCEMENT_REQUESTED": "SIGNATURE_REQUIRED",
    "BINDING_HASH_MISMATCH_PRESENT": "BINDING_HASH_MISMATCH",
    "REQUIRED_BINDING_ABSENT": "BINDING_REQUIRED",
    "REQUIRED_SIGNER_MEMBERSHIP_MISSING": "TRUSTED_SIGNER_NOT_FOUND",
    "AUTHORIZED_INVOCATION_HASH_MISMATCH": "INVOCATION_HASH_MISMATCH",
    "AUTHORIZED_FRESHNESS_TIMESTAMP_MALFORMED": "FRESHNESS_TIMESTAMP_MALFORMED",
}
PRECEDENCE_CHECKS = {
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
}
EXPECTED_SOURCE_DESCRIPTOR_CONTRACT = {
    "FIXTURE": "path is relative to this corpus directory and names exact raw bytes",
    "INLINE_HEX": "hex is an even-length lowercase hexadecimal encoding of exact raw bytes",
    "INLINE_UTF8": "text is encoded once as strict UTF-8 to obtain exact raw bytes",
    "sha256": "lowercase hexadecimal SHA-256 of the exact raw bytes",
}
EXPECTED_INSTANCE_RECIPE_CONTRACT = {
    "contract": "AELITIUM-SCHEMA-INSTANCE-RECIPE-1",
    "initial_value": "deep copy of the named top-level template",
    "mutation_order": "array order, from first to last",
    "pointer": "slash-separated object names or zero-based array indexes; ~0 denotes ~ and ~1 denotes /",
    "REMOVE": "remove the existing value at path",
    "SET": "deep-copy value to path, replacing an existing value or creating the final object member",
}


class CorpusFailure(AssertionError):
    pass


class SourceRejected(ValueError):
    pass


class OutsideCapability(ValueError):
    pass


class LegacyConstant:
    def __init__(self, spelling: str) -> None:
        self.spelling = spelling


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusFailure(message)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def load_canonical(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusFailure(f"cannot load {path.relative_to(REPOSITORY_ROOT)}: {exc}") from exc
    require(raw == canonical_json(value), f"{path.relative_to(REPOSITORY_ROOT)} is not canonical indented JSON")
    return value


def exact_keys(value: Any, keys: set[str], where: str) -> None:
    require(isinstance(value, dict), f"{where} must be an object")
    require(set(value) == keys, f"{where} keys differ: expected {sorted(keys)}, got {sorted(value)}")


def materialize_source(descriptor: Any) -> bytes:
    exact_keys(descriptor, {"kind", "sha256"} | ({"path"} if isinstance(descriptor, dict) and descriptor.get("kind") == "FIXTURE" else {"text"} if isinstance(descriptor, dict) and descriptor.get("kind") == "INLINE_UTF8" else {"hex"}), "source descriptor")
    kind = descriptor["kind"]
    if kind == "FIXTURE":
        path_text = descriptor["path"]
        require(isinstance(path_text, str) and re.fullmatch(r"fixtures/[a-z0-9_]+\.json", path_text) is not None, "invalid fixture path")
        path = CORPUS / path_text
        require(path.is_file(), f"missing fixture: {path_text}")
        raw = path.read_bytes()
    elif kind == "INLINE_UTF8":
        require(isinstance(descriptor["text"], str), "INLINE_UTF8 text must be a string")
        raw = descriptor["text"].encode("utf-8")
    elif kind == "INLINE_HEX":
        value = descriptor["hex"]
        require(isinstance(value, str) and LOWER_HEX.fullmatch(value) is not None, "INLINE_HEX must be lowercase even-length hex")
        raw = bytes.fromhex(value)
    else:
        raise CorpusFailure(f"unknown source descriptor kind: {kind!r}")
    digest = descriptor["sha256"]
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "invalid source SHA-256 spelling")
    require(hashlib.sha256(raw).hexdigest() == digest, "source SHA-256 mismatch")
    return raw


def normalize_v2_string(value: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        codepoint = ord(value[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(value):
                raise SourceRejected("unmatched high surrogate")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise SourceRejected("unmatched high surrogate")
            codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
            index += 2
        elif 0xDC00 <= codepoint <= 0xDFFF:
            raise SourceRejected("unmatched low surrogate")
        else:
            index += 1
        if 0xFDD0 <= codepoint <= 0xFDEF or (codepoint & 0xFFFF) in (0xFFFE, 0xFFFF):
            raise SourceRejected("v2 noncharacter")
        output.append(chr(codepoint))
    return "".join(output)


def normalize_v2_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_v2_string(value)
    if isinstance(value, list):
        return [normalize_v2_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_v2_value(item) for key, item in value.items()}
    return value


def parse_source(raw: bytes, input_kind: str, capability: dict[str, Any]) -> tuple[str, Any | None]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return "REJECT", None
    if text.startswith("\ufeff"):
        return "REJECT", None

    max_digits = capability.get("integer_maximum_decimal_digits")

    def parse_legacy_integer(token: str) -> int:
        digits = token[1:] if token.startswith("-") else token
        if isinstance(max_digits, int) and len(digits) > max_digits:
            raise OutsideCapability("integer digit capability")
        return int(token)

    try:
        if input_kind == "MANIFEST_V2":
            def parse_v2_integer(token: str) -> int:
                value = int(token)
                if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
                    raise SourceRejected("v2 integer outside profile")
                return value

            def parse_v2_float(token: str) -> float:
                value = float(token)
                if not math.isfinite(value) or abs(value) > MAX_SAFE_INTEGER:
                    raise SourceRejected("v2 number outside profile")
                return value

            def reject_constant(token: str) -> Any:
                raise SourceRejected(f"legacy constant {token}")

            def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                value: dict[str, Any] = {}
                for raw_name, member_value in pairs:
                    name = normalize_v2_string(raw_name)
                    if name in value:
                        raise SourceRejected("duplicate decoded name")
                    value[name] = member_value
                return value

            parsed = json.loads(
                text,
                parse_int=parse_v2_integer,
                parse_float=parse_v2_float,
                parse_constant=reject_constant,
                object_pairs_hook=unique_object,
            )
            parsed = normalize_v2_value(parsed)
        else:
            parsed = json.loads(
                text,
                parse_int=parse_legacy_integer,
                parse_constant=LegacyConstant,
            )
    except OutsideCapability:
        return "OPERATIONAL", None
    except (SourceRejected, UnicodeError, json.JSONDecodeError, ValueError, OverflowError):
        return "REJECT", None
    return "ACCEPT", parsed


def profile_ranges(profile: str) -> tuple[tuple[int, int], ...]:
    files = {
        "AELITIUM_UCD_ND_13_0_0_1": "nd-13.0.0.txt",
        "AELITIUM_UCD_ND_15_0_0_1": "nd-15.0.0.txt",
    }
    require(profile in files, f"unsupported timestamp profile in Block 2A: {profile}")
    path = ROOT / "legacy_v1_operational_policy" / "unicode" / files[profile]
    ranges = []
    for line in path.read_text(encoding="ascii").splitlines():
        start, end = line.split("..")
        ranges.append((int(start, 16), int(end, 16)))
    return tuple(ranges)


def in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def evaluate_timestamp(value: Any, input_kind: str, capability: dict[str, Any], enabled: bool) -> str:
    if not enabled:
        return "BYPASSED"
    if not isinstance(value, str):
        return "FAIL"
    if input_kind == "MANIFEST_V2":
        return "PASS" if ASCII_V2_TIMESTAMP.fullmatch(value) is not None else "FAIL"

    core = value[:-1] if value.endswith("\n") else value
    if len(core) != 20 or len(value) not in (20, 21):
        return "FAIL"
    if any(core[index] != expected for index, expected in SEPARATORS.items()):
        return "FAIL"
    profile = capability["timestamp_digit_profile"]
    if profile == "ASCII":
        for index in DIGIT_POSITIONS:
            codepoint = ord(core[index])
            if 0x30 <= codepoint <= 0x39:
                continue
            return "FAIL" if codepoint < 0x80 else "OPERATIONAL"
        return "PASS"
    ranges = profile_ranges(profile)
    return "PASS" if all(in_ranges(ord(core[index]), ranges) for index in DIGIT_POSITIONS) else "FAIL"


def load_schemas(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Draft7Validator]]:
    expected_paths = {
        "MANIFEST_V1": "../../engine/schemas/ai_manifest_v1.json",
        "MANIFEST_V2": "../../engine/schemas/ai_manifest_v2.json",
        "TRUST_STORE_V1": "../../engine/schemas/trust_store_v1.json",
        "VERIFICATION_KEYS_V1": "../../engine/schemas/verification_keys_v1.json",
    }
    require(manifest["schemas"] == expected_paths, "manifest schema registry differs")
    schemas: dict[str, Any] = {}
    validators: dict[str, Draft7Validator] = {}
    for kind, relative in expected_paths.items():
        path = CORPUS / relative
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        require(schema.get("$schema") == "http://json-schema.org/draft-07/schema#", f"{kind} is not Draft 7")
        require(schema.get("$id") == EXPECTED_SCHEMA_IDS[kind], f"{kind} $id differs")
        schemas[kind] = schema
        validators[kind] = Draft7Validator(schema)
    return schemas, validators


def validate_schema_boundaries(schemas: dict[str, Any]) -> None:
    for kind in ("MANIFEST_V1", "MANIFEST_V2"):
        schema = schemas[kind]
        require(schema.get("additionalProperties") is True, f"{kind} root must be open")
        require("type" not in schema["properties"]["ts_utc"], f"{kind} ts_utc must be schema-neutral")
    keyring = schemas["VERIFICATION_KEYS_V1"]
    require(keyring.get("additionalProperties") is True, "keyring root must be open")
    require(keyring["properties"]["keys"]["items"].get("additionalProperties") is True, "key entry must be open")
    require(keyring["properties"]["signatures"]["items"].get("additionalProperties") is True, "signature entry must be open")
    trust = schemas["TRUST_STORE_V1"]
    require(trust.get("additionalProperties") is False, "trust root must be closed")
    require(trust["properties"]["signers"]["items"].get("additionalProperties") is False, "trust signer must be closed")

    def contains_unique_items(value: Any) -> bool:
        if isinstance(value, dict):
            return "uniqueItems" in value or any(contains_unique_items(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_unique_items(item) for item in value)
        return False

    require(not contains_unique_items(trust), "trust schema must not use uniqueItems")


def validate_capability(value: Any, input_kind: str) -> None:
    require(isinstance(value, dict), "capability must be an object")
    identifier = value.get("identifier")
    require(identifier in CAPABILITIES, f"unknown capability: {identifier!r}")
    if identifier == "V2_PORTABLE":
        exact_keys(value, {"identifier"}, "V2 capability")
        require(input_kind == "MANIFEST_V2", "V2 capability used for non-v2 input")
    else:
        exact_keys(value, {"identifier", "integer_maximum_decimal_digits", "timestamp_digit_profile"}, "v1 capability")
        require(isinstance(value["integer_maximum_decimal_digits"], int) and value["integer_maximum_decimal_digits"] >= 640, "invalid integer capability")
        require(isinstance(value["timestamp_digit_profile"], str), "invalid timestamp profile")


def validate_expected(value: Any) -> None:
    exact_keys(value, {"source_profile_decision", "schema_reached", "schema_decision", "semantic_reason", "operational_code", "timestamp_decision"}, "source expected")
    require(value["source_profile_decision"] in SOURCE_DECISIONS, "unknown source decision")
    require(type(value["schema_reached"]) is bool, "schema_reached must be Boolean")
    require(value["schema_decision"] in SCHEMA_DECISIONS, "unknown schema decision")
    require(value["semantic_reason"] in SEMANTIC_REASONS, "unknown semantic reason")
    require(value["operational_code"] in OPERATIONAL_CODES, "unknown operational code")
    require(value["timestamp_decision"] in TIMESTAMP_DECISIONS, "unknown timestamp decision")
    require(value["schema_reached"] == (value["schema_decision"] != "NOT_REACHED"), "schema reach/decision mismatch")
    require(not (value["semantic_reason"] is not None and value["operational_code"] is not None), "semantic and operational outcomes cannot coexist")
    if value["source_profile_decision"] == "REJECT":
        require(value["semantic_reason"] is not None, "rejected stable source must name its authorized semantic reason")
    if value["source_profile_decision"] == "OPERATIONAL":
        require(value["operational_code"] is not None, "operational source must name its operational code")
    if value["timestamp_decision"] == "FAIL":
        require(value["semantic_reason"] == "MANIFEST_BAD_TS_UTC", "failed timestamp must use MANIFEST_BAD_TS_UTC")
    if value["timestamp_decision"] == "OPERATIONAL":
        require(value["operational_code"] is not None, "operational timestamp must name its operational code")


def run_source_cases(document: dict[str, Any], validators: dict[str, Draft7Validator], *, verbose: bool) -> tuple[int, dict[str, int]]:
    exact_keys(document, {"contract", "scope", "source_descriptor_contract", "case_count", "vectors"}, "source vector document")
    require(document["contract"] == EXPECTED_SOURCE_CONTRACT, "source contract identifier differs")
    require(document["scope"] == "SOURCE", "source scope differs")
    require(document["source_descriptor_contract"] == EXPECTED_SOURCE_DESCRIPTOR_CONTRACT, "source descriptor contract differs")
    vectors = document["vectors"]
    require(isinstance(vectors, list) and document["case_count"] == len(vectors), "source case count differs")
    counts: dict[str, int] = {}
    for case in vectors:
        exact_keys(case, {"case_id", "family", "input_kind", "source", "capability", "selected_route", "verifier_options", "expected", "compatibility"}, "source case")
        case_id = case["case_id"]
        require(isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None, f"invalid case ID: {case_id!r}")
        require(case["family"] in SOURCE_FAMILIES, f"{case_id}: unknown source family")
        require(case["input_kind"] in INPUT_KINDS, f"{case_id}: unknown input kind")
        require(case["selected_route"] in ROUTES, f"{case_id}: unknown route")
        if case["input_kind"] == "MANIFEST_V1":
            require(case["selected_route"] in {"LEGACY_V1", "LEGACY_ERROR_RESOLUTION"}, f"{case_id}: invalid v1 route")
        elif case["input_kind"] == "MANIFEST_V2":
            require(case["selected_route"] in {"PORTABLE_V2", "LEGACY_ERROR_RESOLUTION"}, f"{case_id}: invalid v2 route")
        else:
            require(case["selected_route"] == "NOT_APPLICABLE", f"{case_id}: auxiliary input has a dispatch route")
        require(case["compatibility"] in COMPATIBILITY, f"{case_id}: unknown compatibility")
        exact_keys(case["verifier_options"], {"validate_manifest_timestamp"}, f"{case_id} options")
        option = case["verifier_options"]["validate_manifest_timestamp"]
        require(option is None or type(option) is bool, f"{case_id}: invalid timestamp option")
        validate_capability(case["capability"], case["input_kind"])
        validate_expected(case["expected"])
        raw = materialize_source(case["source"])
        observed_source, parsed = parse_source(raw, case["input_kind"], case["capability"])
        expected_value = case["expected"]
        require(observed_source == expected_value["source_profile_decision"], f"{case_id}: source expected {expected_value['source_profile_decision']}, observed {observed_source}")
        if expected_value["schema_reached"]:
            require(observed_source == "ACCEPT", f"{case_id}: schema reached without parsed value")
            errors = list(validators[case["input_kind"]].iter_errors(parsed))
            observed_schema = "INVALID" if errors else "VALID"
            require(observed_schema == expected_value["schema_decision"], f"{case_id}: schema expected {expected_value['schema_decision']}, observed {observed_schema}")
        if case["input_kind"] in {"MANIFEST_V1", "MANIFEST_V2"} and expected_value["timestamp_decision"] not in {"NOT_REACHED", "NOT_APPLICABLE"}:
            require(isinstance(parsed, dict) and "ts_utc" in parsed, f"{case_id}: timestamp cannot be evaluated")
            observed_timestamp = evaluate_timestamp(parsed["ts_utc"], case["input_kind"], case["capability"], bool(option))
            require(observed_timestamp == expected_value["timestamp_decision"], f"{case_id}: timestamp expected {expected_value['timestamp_decision']}, observed {observed_timestamp}")
        counts[case["input_kind"]] = counts.get(case["input_kind"], 0) + 1
        if verbose:
            print(f"PASS {case_id}")
    return len(vectors), counts


def pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    require(isinstance(pointer, str) and pointer.startswith("/") and pointer != "/", f"invalid JSON pointer: {pointer!r}")
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]
    current = document
    for token in tokens[:-1]:
        if isinstance(current, list):
            require(token.isdigit() and int(token) < len(current), f"array pointer out of range: {pointer}")
            current = current[int(token)]
        else:
            require(isinstance(current, dict) and token in current, f"object pointer missing: {pointer}")
            current = current[token]
    return current, tokens[-1]


def apply_recipe(templates: dict[str, Any], recipe: Any) -> Any:
    exact_keys(recipe, {"template", "mutations"}, "instance recipe")
    template = recipe["template"]
    require(isinstance(template, str) and template in templates, f"unknown template: {template!r}")
    require(isinstance(recipe["mutations"], list), "recipe mutations must be an array")
    instance = copy.deepcopy(templates[template])
    for item in recipe["mutations"]:
        require(isinstance(item, dict) and item.get("op") in {"SET", "REMOVE"}, "unknown mutation")
        op = item["op"]
        exact_keys(item, {"op", "path", "value"} if op == "SET" else {"op", "path"}, "mutation")
        parent, token = pointer_parent(instance, item["path"])
        if isinstance(parent, list):
            require(token.isdigit() and int(token) < len(parent), f"array mutation out of range: {item['path']}")
            index = int(token)
            if op == "SET":
                parent[index] = copy.deepcopy(item["value"])
            else:
                del parent[index]
        else:
            require(isinstance(parent, dict), f"mutation parent is not a container: {item['path']}")
            if op == "SET":
                parent[token] = copy.deepcopy(item["value"])
            else:
                require(token in parent, f"REMOVE target missing: {item['path']}")
                del parent[token]
    return instance


def run_schema_cases(document: dict[str, Any], validators: dict[str, Draft7Validator], *, verbose: bool) -> tuple[int, dict[str, int]]:
    exact_keys(document, {"contract", "scope", "instance_recipe_contract", "case_count", "templates", "vectors"}, "schema vector document")
    require(document["contract"] == EXPECTED_SCHEMA_CONTRACT, "schema contract identifier differs")
    require(document["scope"] == "SCHEMA", "schema scope differs")
    require(document["instance_recipe_contract"] == EXPECTED_INSTANCE_RECIPE_CONTRACT, "instance recipe contract differs")
    templates = document["templates"]
    require(isinstance(templates, dict) and set(templates) == {"MANIFEST_V1_VALID", "MANIFEST_V2_VALID", "KEYRING_VALID", "TRUST_EMPTY_VALID", "TRUST_ONE_VALID"}, "schema templates differ")
    vectors = document["vectors"]
    require(isinstance(vectors, list) and document["case_count"] == len(vectors), "schema case count differs")
    counts: dict[str, int] = {}
    for case in vectors:
        exact_keys(case, {"case_id", "family", "input_kind", "schema", "instance_recipe", "focus", "expected"}, "schema case")
        case_id = case["case_id"]
        require(isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None, f"invalid case ID: {case_id!r}")
        require(case["family"] in SCHEMA_FAMILIES, f"{case_id}: unknown schema family")
        kind = case["input_kind"]
        require(kind in INPUT_KINDS, f"{case_id}: unknown input kind")
        require(case["schema"] == SCHEMA_FILENAMES[kind], f"{case_id}: schema/input kind mismatch")
        require(case["focus"] in FOCUS_VALUES, f"{case_id}: unknown focus")
        exp = case["expected"]
        exact_keys(exp, {"schema_decision", "semantic_reason", "first_missing_member", "procedural_requirement"}, f"{case_id} expected")
        require(exp["schema_decision"] in {"VALID", "INVALID"}, f"{case_id}: unknown schema decision")
        require(exp["semantic_reason"] in SEMANTIC_REASONS, f"{case_id}: unknown semantic reason")
        require(exp["first_missing_member"] in {None, "schema", "ts_utc", "input_schema", "canonicalization", "ai_hash_sha256"}, f"{case_id}: invalid first missing member")
        require(exp["procedural_requirement"] in PROCEDURAL_REQUIREMENTS, f"{case_id}: unknown procedural requirement")
        if exp["first_missing_member"] is not None:
            require(exp["procedural_requirement"] == "ORDERED_MANIFEST_PRESENCE", f"{case_id}: missing-member precedence is not procedural")
        instance = apply_recipe(templates, case["instance_recipe"])
        errors = list(validators[kind].iter_errors(instance))
        observed = "INVALID" if errors else "VALID"
        require(observed == exp["schema_decision"], f"{case_id}: schema expected {exp['schema_decision']}, observed {observed}")
        counts[case["family"]] = counts.get(case["family"], 0) + 1
        if verbose:
            print(f"PASS {case_id}")
    return len(vectors), counts


def semantic_fixture(name: str, fixture_hashes: dict[str, str]) -> bytes:
    require(
        isinstance(name, str) and re.fullmatch(r"semantic_[a-z0-9_]+\.json", name) is not None,
        f"invalid semantic fixture name: {name!r}",
    )
    require(name in fixture_hashes, f"semantic fixture is not registered: {name}")
    path = CORPUS / "fixtures" / name
    require(path.is_file(), f"semantic fixture is missing: {name}")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == fixture_hashes[name], f"semantic fixture SHA-256 mismatch: {name}")
    return raw


def strict_json(raw: bytes) -> Any:
    def reject_constant(token: str) -> Any:
        raise ValueError(f"legacy constant {token}")

    text = raw.decode("utf-8", errors="strict")
    if text.startswith("\ufeff"):
        raise ValueError("leading BOM")
    return json.loads(text, parse_constant=reject_constant)


def decode_public_key(spelling: Any) -> bytes:
    if not isinstance(spelling, str) or PUBLIC_KEY_B64.fullmatch(spelling) is None:
        raise ValueError("public-key Base64 spelling")
    raw = base64.b64decode(spelling, validate=True)
    if len(raw) != 32:
        raise ValueError("public-key decoded length")
    return raw


def decode_signature(spelling: Any) -> bytes:
    if not isinstance(spelling, str) or SIGNATURE_B64.fullmatch(spelling) is None:
        raise ValueError("signature Base64 spelling")
    raw = base64.b64decode(spelling, validate=True)
    if len(raw) != 64:
        raise ValueError("signature decoded length")
    return raw


def fingerprint(public_key: bytes) -> str:
    return "ed25519:sha256:" + hashlib.sha256(public_key).hexdigest()


def inspect_trust_store(raw: bytes) -> tuple[str, set[str]]:
    try:
        value = strict_json(raw)
        if not isinstance(value, dict) or set(value) != {"trust_store_format", "signers"}:
            raise ValueError("trust root")
        if value["trust_store_format"] != "aelitium-trust-v1":
            raise ValueError("trust format")
        if not isinstance(value["signers"], list):
            raise ValueError("signers")
        fingerprints: set[str] = set()
        for signer in value["signers"]:
            if not isinstance(signer, dict) or set(signer) not in (
                {"algorithm", "public_key_b64"},
                {"algorithm", "public_key_b64", "label"},
            ):
                raise ValueError("signer structure")
            if signer["algorithm"] != "ed25519":
                raise ValueError("signer algorithm")
            if "label" in signer and (
                not isinstance(signer["label"], str) or len(signer["label"]) == 0
            ):
                raise ValueError("signer label")
            derived = fingerprint(decode_public_key(signer["public_key_b64"]))
            if derived in fingerprints:
                raise ValueError("duplicate derived fingerprint")
            fingerprints.add(derived)
        return "VALID", fingerprints
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, binascii.Error):
        return "INVALID", set()


def inspect_signature(raw_manifest: bytes, raw_keyring: bytes) -> tuple[str, str, bytes | None]:
    try:
        value = strict_json(raw_keyring)
        if not isinstance(value, dict):
            raise ValueError("keyring root")
        if not {"keyring_format", "keys", "signatures"} <= set(value):
            raise ValueError("keyring members")
        if value["keyring_format"] != "ed25519-v1":
            raise ValueError("keyring format")
        if not isinstance(value["keys"], list) or len(value["keys"]) != 1:
            raise ValueError("key cardinality")
        if not isinstance(value["signatures"], list) or len(value["signatures"]) != 1:
            raise ValueError("signature cardinality")
        key_entry = value["keys"][0]
        signature_entry = value["signatures"][0]
        if not isinstance(key_entry, dict) or not {"key_id", "public_key_b64"} <= set(key_entry):
            raise ValueError("key entry")
        if not isinstance(signature_entry, dict) or not {
            "key_id", "algorithm", "scope", "sig_b64"
        } <= set(signature_entry):
            raise ValueError("signature entry")
        key_id = key_entry["key_id"]
        signature_key_id = signature_entry["key_id"]
        if not isinstance(key_id, str) or not key_id or not isinstance(signature_key_id, str) or not signature_key_id:
            raise ValueError("key ID domain")
        if key_id != signature_key_id:
            return "INVALID", "NOT_EVALUATED", None
        if signature_entry["algorithm"] != "ed25519" or signature_entry["scope"] != "manifest.json":
            raise ValueError("signature identifier")
        public_key = decode_public_key(key_entry["public_key_b64"])
        signature = decode_signature(signature_entry["sig_b64"])
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, binascii.Error):
        return "INVALID", "NOT_EVALUATED", None
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, raw_manifest)
    except (InvalidSignature, ValueError):
        return "INVALID", "INVALID", None
    return "VALID", "VALID", public_key


def parse_hex(value: Any, length: int, where: str) -> bytes:
    require(isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length * 2}}}", value) is not None, f"{where} is malformed")
    return bytes.fromhex(value)


def decode_ed25519_portable_point(encoded: bytes) -> tuple[int, int]:
    """Conformance-only strict RFC 8032 section 5.1.3 point decoding."""
    if len(encoded) != 32:
        raise ValueError("point length")
    encoded_integer = int.from_bytes(encoded, "little")
    sign = encoded_integer >> 255
    y = encoded_integer & ((1 << 255) - 1)
    if y >= ED25519_P:
        raise ValueError("non-canonical y")
    y_squared = y * y % ED25519_P
    numerator = (y_squared - 1) % ED25519_P
    denominator = (ED25519_D * y_squared + 1) % ED25519_P
    x_squared = numerator * pow(denominator, ED25519_P - 2, ED25519_P) % ED25519_P
    x = pow(x_squared, (ED25519_P + 3) // 8, ED25519_P)
    if (x * x - x_squared) % ED25519_P != 0:
        x = x * ED25519_SQRT_M1 % ED25519_P
    if (x * x - x_squared) % ED25519_P != 0:
        raise ValueError("square-root recovery")
    if x == 0 and sign == 1:
        raise ValueError("x=0 with sign bit one")
    if (x & 1) != sign:
        x = ED25519_P - x
    return x, y


def ed25519_portable_add(
    left: tuple[int, int], right: tuple[int, int]
) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = ED25519_D * x1 * x2 * y1 * y2 % ED25519_P
    x3 = (x1 * y2 + x2 * y1) * pow(
        (1 + product) % ED25519_P, ED25519_P - 2, ED25519_P
    ) % ED25519_P
    y3 = (y1 * y2 + x1 * x2) * pow(
        (1 - product) % ED25519_P, ED25519_P - 2, ED25519_P
    ) % ED25519_P
    return x3, y3


def ed25519_portable_scalar_multiply(
    scalar: int, point: tuple[int, int]
) -> tuple[int, int]:
    result = ED25519_IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = ed25519_portable_add(result, addend)
        addend = ed25519_portable_add(addend, addend)
        scalar >>= 1
    return result


def ed25519_equation_diagnostics(
    public_key: bytes, signature: bytes, message: bytes
) -> dict[str, str]:
    """Check both RFC-described equations for a decoded discriminator."""
    a_point = decode_ed25519_portable_point(public_key)
    r_point = decode_ed25519_portable_point(signature[:32])
    scalar = int.from_bytes(signature[32:], "little")
    challenge = int.from_bytes(
        hashlib.sha512(signature[:32] + public_key + message).digest(), "little"
    ) % ED25519_L
    base = decode_ed25519_portable_point(bytes.fromhex("58" + "66" * 31))
    left = ed25519_portable_scalar_multiply(scalar, base)
    right = ed25519_portable_add(
        r_point, ed25519_portable_scalar_multiply(challenge, a_point)
    )
    return {
        "cofactored_equation": (
            "PASS"
            if ed25519_portable_scalar_multiply(8, left)
            == ed25519_portable_scalar_multiply(8, right)
            else "FAIL"
        ),
        "uncofactored_equation": "PASS" if left == right else "FAIL",
    }


def ed25519_portable_strict_1_observation(
    public_key: bytes, signature: bytes, message: bytes
) -> dict[str, Any]:
    """Evaluate the Level 1 profile without cryptography/OpenSSL.

    This arithmetic evaluator is non-normative runner machinery. The committed
    expectations and VERIFIER_INPUT_CONTRACTS_V1.md remain authoritative.
    """
    observation = {
        "top_level_reason": "SIGNATURE_INVALID",
        "signature_validity": "INVALID",
        "cryptographic_signature_decision": "INVALID",
        "failure_stage": "A_DECODE",
        "a_decoding": "NOT_REACHED",
        "r_decoding": "NOT_REACHED",
        "a_subgroup": "NOT_REACHED",
        "r_subgroup": "NOT_REACHED",
        "scalar_decision": "NOT_REACHED",
        "equation_decision": "NOT_REACHED",
    }
    try:
        a_point = decode_ed25519_portable_point(public_key)
    except ValueError:
        observation["a_decoding"] = "FAIL"
        return observation
    observation["a_decoding"] = "PASS"

    r_encoded = signature[:32]
    try:
        r_point = decode_ed25519_portable_point(r_encoded)
    except ValueError:
        observation["failure_stage"] = "R_DECODE"
        observation["r_decoding"] = "FAIL"
        return observation
    observation["r_decoding"] = "PASS"

    if a_point == ED25519_IDENTITY:
        observation["failure_stage"] = "A_IDENTITY"
        return observation

    if ed25519_portable_scalar_multiply(ED25519_L, a_point) != ED25519_IDENTITY:
        observation["failure_stage"] = "A_SUBGROUP"
        observation["a_subgroup"] = "FAIL"
        return observation
    observation["a_subgroup"] = "PASS"

    if ed25519_portable_scalar_multiply(ED25519_L, r_point) != ED25519_IDENTITY:
        observation["failure_stage"] = "R_SUBGROUP"
        observation["r_subgroup"] = "FAIL"
        return observation
    observation["r_subgroup"] = "PASS"

    scalar = int.from_bytes(signature[32:], "little")
    if scalar >= ED25519_L:
        observation["failure_stage"] = "S_RANGE"
        observation["scalar_decision"] = "OUT_OF_RANGE"
        return observation
    observation["scalar_decision"] = "IN_RANGE"

    challenge = int.from_bytes(
        hashlib.sha512(r_encoded + public_key + message).digest(), "little"
    ) % ED25519_L
    base = decode_ed25519_portable_point(bytes.fromhex("58" + "66" * 31))
    left = ed25519_portable_scalar_multiply(scalar, base)
    right = ed25519_portable_add(
        r_point, ed25519_portable_scalar_multiply(challenge, a_point)
    )
    observation["failure_stage"] = "EQUATION"
    if left != right:
        observation["equation_decision"] = "FAIL"
        return observation

    observation.update(
        top_level_reason=None,
        signature_validity="VALID",
        cryptographic_signature_decision="VALID",
        failure_stage="NONE",
        equation_decision="PASS",
    )
    return observation


def strict_semantic_message(descriptor: Any) -> bytes:
    raw = materialize_source(descriptor)
    require(
        hashlib.sha256(raw).hexdigest() == descriptor["sha256"],
        "strict semantic raw-message hash mismatch",
    )
    return raw


def validate_semantic_materials(document: dict[str, Any], fixture_hashes: dict[str, str]) -> dict[str, bytes]:
    materials = document["materials"]
    exact_keys(materials, {"primary_key", "secondary_key", "primary_manifest_signature"}, "semantic materials")
    primary = materials["primary_key"]
    secondary = materials["secondary_key"]
    signature_material = materials["primary_manifest_signature"]
    exact_keys(
        primary,
        {"private_seed_hex", "public_key_hex", "public_key_b64", "public_key_pad_bit_alias_b64", "raw_key_sha256", "prefixed_bytes_sha256_not_fingerprint", "fingerprint"},
        "primary key material",
    )
    exact_keys(
        secondary,
        {"private_seed_hex", "public_key_hex", "public_key_b64", "raw_key_sha256", "fingerprint"},
        "secondary key material",
    )
    exact_keys(
        signature_material,
        {"raw_manifest_message_sha256", "signature_hex", "signature_b64", "signature_pad_bit_alias_b64"},
        "signature material",
    )

    derived_public_keys: dict[str, bytes] = {}
    for label, material in (("PRIMARY", primary), ("SECONDARY", secondary)):
        seed = parse_hex(material["private_seed_hex"], 32, f"{label} seed")
        frozen_public = parse_hex(material["public_key_hex"], 32, f"{label} public key")
        derived_public = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        require(derived_public == frozen_public, f"{label} public key does not derive from public test seed")
        require(decode_public_key(material["public_key_b64"]) == frozen_public, f"{label} Base64 differs")
        raw_digest = hashlib.sha256(frozen_public).hexdigest()
        require(material["raw_key_sha256"] == raw_digest, f"{label} raw-key digest differs")
        require(material["fingerprint"] == "ed25519:sha256:" + raw_digest, f"{label} fingerprint differs")
        derived_public_keys[label] = frozen_public

    primary_alias = primary["public_key_pad_bit_alias_b64"]
    require(primary_alias != primary["public_key_b64"], "public-key pad-bit alias is not distinct")
    require(decode_public_key(primary_alias) == derived_public_keys["PRIMARY"], "public-key pad-bit alias changes bytes")
    prefixed_digest = hashlib.sha256(b"ed25519:sha256:" + derived_public_keys["PRIMARY"]).hexdigest()
    require(primary["prefixed_bytes_sha256_not_fingerprint"] == prefixed_digest, "prefixed comparison digest differs")
    require(primary["raw_key_sha256"] != prefixed_digest, "fingerprint test does not distinguish prefix hashing")

    raw_manifest = semantic_fixture("semantic_manifest_valid.json", fixture_hashes)
    signature = parse_hex(signature_material["signature_hex"], 64, "primary signature")
    require(base64.b64decode(signature_material["signature_b64"], validate=True) == signature, "signature Base64 differs")
    alias_signature = decode_signature(signature_material["signature_pad_bit_alias_b64"])
    require(signature_material["signature_pad_bit_alias_b64"] != signature_material["signature_b64"], "signature pad-bit alias is not distinct")
    require(alias_signature == signature, "signature pad-bit alias changes bytes")
    require(hashlib.sha256(raw_manifest).hexdigest() == signature_material["raw_manifest_message_sha256"], "frozen manifest-message hash differs")
    try:
        Ed25519PublicKey.from_public_bytes(derived_public_keys["PRIMARY"]).verify(signature, raw_manifest)
    except InvalidSignature as exc:
        raise CorpusFailure("frozen primary signature is invalid") from exc
    primary_seed = parse_hex(primary["private_seed_hex"], 32, "primary seed")
    require(Ed25519PrivateKey.from_private_bytes(primary_seed).sign(raw_manifest) == signature, "signature is not deterministically reproducible")

    payload = semantic_fixture("semantic_ai_canonical.json", fixture_hashes)
    base_value = strict_json(raw_manifest)
    require(base_value["ai_hash_sha256"] == hashlib.sha256(payload).hexdigest(), "canonical payload hash does not match manifest")
    for name in (
        "semantic_manifest_leading_whitespace.json",
        "semantic_manifest_member_order.json",
        "semantic_manifest_escape_spelling.json",
        "semantic_manifest_terminal_newline.json",
    ):
        changed = semantic_fixture(name, fixture_hashes)
        require(changed != raw_manifest, f"{name} does not change raw bytes")
        require(strict_json(changed) == base_value, f"{name} changes parsed manifest value")
    return derived_public_keys


def semantic_observation(
    case: dict[str, Any], fixture_hashes: dict[str, str], public_keys: dict[str, bytes]
) -> dict[str, Any]:
    inputs = case["inputs"]
    operation = case["operation"]
    empty = {
        "top_level_reason": None,
        "signature_validity": "NOT_EVALUATED",
        "trusted_signer_identity": "NOT_EVALUATED",
        "cryptographic_signature_decision": "NOT_EVALUATED",
        "trust_store_validation": "NOT_EVALUATED",
        "trust_membership_decision": "NOT_EVALUATED",
        "expected_fingerprint": None,
    }
    if operation == "DERIVE_FINGERPRINT":
        empty["expected_fingerprint"] = fingerprint(public_keys[inputs["key_material"]])
        return empty

    trust_ref = inputs["trust_store"]
    if operation == "VALIDATE_TRUST_STORE":
        validation, _ = inspect_trust_store(semantic_fixture(trust_ref, fixture_hashes))
        empty["trust_store_validation"] = validation
        if validation == "INVALID":
            empty["top_level_reason"] = "TRUST_STORE_INVALID"
        return empty

    options = case["verifier_options"]
    if trust_ref is None and options["require_trusted_signer"]:
        empty.update(
            top_level_reason="TRUST_INPUT_NOT_PROVIDED",
            trusted_signer_identity="UNESTABLISHED",
            trust_store_validation="ABSENT",
            trust_membership_decision="NO_STORE",
        )
        return empty

    trust_fingerprints: set[str] = set()
    if trust_ref is None:
        store_validation = "ABSENT"
    else:
        store_validation, trust_fingerprints = inspect_trust_store(
            semantic_fixture(trust_ref, fixture_hashes)
        )
        if store_validation == "INVALID":
            empty.update(
                top_level_reason="TRUST_STORE_INVALID",
                trusted_signer_identity="UNESTABLISHED",
                trust_store_validation="INVALID",
            )
            return empty

    keyring_ref = inputs["verification_keys"]
    if keyring_ref is None:
        empty.update(
            signature_validity="ABSENT",
            trusted_signer_identity="UNESTABLISHED",
            trust_store_validation=store_validation,
        )
        if options["require_signature"] or options["require_trusted_signer"]:
            empty["top_level_reason"] = "SIGNATURE_REQUIRED"
        return empty

    raw_manifest = semantic_fixture(inputs["manifest"], fixture_hashes)
    signature_state, crypto_decision, verified_key = inspect_signature(
        raw_manifest, semantic_fixture(keyring_ref, fixture_hashes)
    )
    empty.update(
        signature_validity=signature_state,
        trusted_signer_identity="UNESTABLISHED",
        cryptographic_signature_decision=crypto_decision,
        trust_store_validation=store_validation,
    )
    if signature_state == "INVALID":
        empty["top_level_reason"] = "SIGNATURE_INVALID"
        return empty
    require(verified_key is not None, "valid signature did not expose its public key")
    if store_validation == "ABSENT":
        empty["trust_membership_decision"] = "NO_STORE"
        return empty
    verified_fingerprint = fingerprint(verified_key)
    empty["expected_fingerprint"] = verified_fingerprint
    if verified_fingerprint in trust_fingerprints:
        empty["trusted_signer_identity"] = "VALID"
        empty["trust_membership_decision"] = "MATCH"
    else:
        empty["trust_membership_decision"] = "NO_MATCH"
        if options["require_trusted_signer"]:
            empty["top_level_reason"] = "TRUSTED_SIGNER_NOT_FOUND"
    return empty


def validate_strict_semantic_case(case: Any) -> str:
    exact_keys(
        case,
        {
            "case_id",
            "family",
            "profile",
            "message",
            "public_key_hex",
            "signature_hex",
            "expected",
            "purpose",
            "compatibility",
            "distinguishing_equations",
        },
        "strict Ed25519 semantic case",
    )
    case_id = case["case_id"]
    require(
        isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None,
        f"invalid strict semantic case ID: {case_id!r}",
    )
    require(case["family"] == "ED25519_STRICT_SEMANTIC", f"{case_id}: family differs")
    require(case["profile"] == ED25519_PROFILE, f"{case_id}: profile differs")
    require(case["compatibility"] in COMPATIBILITY, f"{case_id}: compatibility differs")
    require(isinstance(case["purpose"], str) and case["purpose"], f"{case_id}: purpose is empty")
    message = strict_semantic_message(case["message"])
    public_key = parse_hex(case["public_key_hex"], 32, f"{case_id} public key")
    signature = parse_hex(case["signature_hex"], 64, f"{case_id} signature")
    distinguishing = case["distinguishing_equations"]
    if distinguishing is None:
        require(
            case_id != "signature.strict.cofactored_only_domain_rejected",
            f"{case_id}: distinguishing equation facts are missing",
        )
    else:
        exact_keys(
            distinguishing,
            {"cofactored_equation", "uncofactored_equation"},
            f"{case_id} distinguishing equations",
        )
        require(
            case_id == "signature.strict.cofactored_only_domain_rejected",
            f"{case_id}: unexpected equation discriminator",
        )
        require(
            ed25519_equation_diagnostics(public_key, signature, message)
            == distinguishing,
            f"{case_id}: distinguishing equation facts differ",
        )
    expected = case["expected"]
    exact_keys(
        expected,
        {
            "top_level_reason",
            "signature_validity",
            "cryptographic_signature_decision",
            "failure_stage",
            "a_decoding",
            "r_decoding",
            "a_subgroup",
            "r_subgroup",
            "scalar_decision",
            "equation_decision",
        },
        f"{case_id} expected",
    )
    require(expected["top_level_reason"] in {None, "SIGNATURE_INVALID"}, f"{case_id}: reason differs")
    require(expected["signature_validity"] in {"VALID", "INVALID"}, f"{case_id}: signature state differs")
    require(
        expected["cryptographic_signature_decision"] == expected["signature_validity"],
        f"{case_id}: cryptographic and signature states differ",
    )
    require(
        expected["failure_stage"]
        in {"NONE", "A_DECODE", "R_DECODE", "A_IDENTITY", "A_SUBGROUP", "R_SUBGROUP", "S_RANGE", "EQUATION"},
        f"{case_id}: failure stage differs",
    )
    for field in ("a_decoding", "r_decoding", "a_subgroup", "r_subgroup"):
        require(expected[field] in {"PASS", "FAIL", "NOT_REACHED"}, f"{case_id}: {field} differs")
    require(
        expected["scalar_decision"] in {"IN_RANGE", "OUT_OF_RANGE", "NOT_REACHED"},
        f"{case_id}: scalar decision differs",
    )
    require(
        expected["equation_decision"] in {"PASS", "FAIL", "NOT_REACHED"},
        f"{case_id}: equation decision differs",
    )
    observed = ed25519_portable_strict_1_observation(public_key, signature, message)
    require(observed == expected, f"{case_id}: expected {expected}, observed {observed}")
    return case_id


def run_semantic_cases(document: dict[str, Any], *, verbose: bool) -> tuple[int, dict[str, int], list[str]]:
    exact_keys(
        document,
        {"contract", "scope", "test_material_notice", "claim_boundary", "fixture_hashes", "materials", "ed25519_portable_profile", "state_vocabulary", "case_count", "family_counts", "vectors"},
        "semantic vector document",
    )
    require(document["contract"] == EXPECTED_SEMANTIC_CONTRACT, "semantic contract identifier differs")
    require(
        document["scope"] == "SIGNATURE_TRUST_AND_ED25519_PORTABLE_PROFILE_SEMANTICS",
        "semantic scope differs",
    )
    require(
        document["ed25519_portable_profile"]
        == {
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
        "strict Ed25519 profile metadata differs",
    )
    require(document["test_material_notice"] == EXPECTED_TEST_KEY_NOTICE, "public test-key notice differs")
    require(
        document["claim_boundary"] == [
            "signature_validity=VALID establishes only mathematical validity for the exact raw manifest message under the bundled public key.",
            "Signature validity does not establish trusted organizational identity, authorization, provider execution, historical occurrence, response causation, semantic truth, or legal compliance.",
            "trusted_signer_identity=VALID establishes only exact decoded-key membership in the explicit trust input.",
        ],
        "semantic claim boundary differs",
    )
    expected_vocabulary = {
        "top_level_reason": [None, "SIGNATURE_INVALID", "SIGNATURE_REQUIRED", "TRUST_INPUT_NOT_PROVIDED", "TRUST_STORE_INVALID", "TRUSTED_SIGNER_NOT_FOUND"],
        "signature_validity": ["ABSENT", "INVALID", "NOT_EVALUATED", "VALID"],
        "trusted_signer_identity": ["NOT_EVALUATED", "UNESTABLISHED", "VALID"],
        "cryptographic_signature_decision": ["INVALID", "NOT_EVALUATED", "VALID"],
        "trust_store_validation": ["ABSENT", "INVALID", "NOT_EVALUATED", "VALID"],
        "trust_membership_decision": ["MATCH", "NOT_EVALUATED", "NO_MATCH", "NO_STORE"],
    }
    require(document["state_vocabulary"] == expected_vocabulary, "semantic state vocabulary differs")
    fixture_hashes = document["fixture_hashes"]
    require(isinstance(fixture_hashes, dict) and len(fixture_hashes) == 21, "semantic fixture registry differs")
    semantic_files = {
        path.name
        for path in (CORPUS / "fixtures").iterdir()
        if path.is_file() and path.name.startswith("semantic_")
    }
    require(set(fixture_hashes) == semantic_files, "semantic fixture inventory differs")
    for name, digest in fixture_hashes.items():
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid fixture digest: {name}")
        semantic_fixture(name, fixture_hashes)
    public_keys = validate_semantic_materials(document, fixture_hashes)

    vectors = document["vectors"]
    require(isinstance(vectors, list) and document["case_count"] == len(vectors), "semantic case count differs")
    require(
        hashlib.sha256(canonical_json(vectors[:36])).hexdigest()
        == BLOCK2B1_VECTOR_SET_SHA256,
        "original Block 2B1 semantic vector set changed",
    )
    counts: dict[str, int] = {}
    ids: list[str] = []
    for case in vectors:
        if isinstance(case, dict) and case.get("family") == "ED25519_STRICT_SEMANTIC":
            case_id = validate_strict_semantic_case(case)
            counts["ED25519_STRICT_SEMANTIC"] = (
                counts.get("ED25519_STRICT_SEMANTIC", 0) + 1
            )
            ids.append(case_id)
            if verbose:
                print(f"PASS {case_id}")
            continue
        exact_keys(case, {"case_id", "family", "operation", "inputs", "verifier_options", "raw_manifest_message_sha256", "expected", "compatibility"}, "semantic case")
        case_id = case["case_id"]
        require(isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None, f"invalid semantic case ID: {case_id!r}")
        require(case["family"] in SEMANTIC_FAMILIES, f"{case_id}: unknown semantic family")
        require(case["operation"] in SEMANTIC_OPERATIONS, f"{case_id}: unknown semantic operation")
        if case["family"] == "SIGNATURE_SEMANTIC":
            require(case["operation"] == "VERIFY_SIGNATURE", f"{case_id}: signature family operation differs")
        require(case["compatibility"] in COMPATIBILITY, f"{case_id}: unknown compatibility")
        exact_keys(case["inputs"], {"canonical_payload", "manifest", "verification_keys", "trust_store", "key_material"}, f"{case_id} inputs")
        for input_name in ("canonical_payload", "manifest", "verification_keys", "trust_store"):
            reference = case["inputs"][input_name]
            require(reference is None or reference in fixture_hashes, f"{case_id}: unknown {input_name} fixture")
        key_material = case["inputs"]["key_material"]
        require(key_material in {None, "PRIMARY", "SECONDARY"}, f"{case_id}: invalid key material")
        exact_keys(case["verifier_options"], {"require_signature", "require_trusted_signer"}, f"{case_id} options")
        require(all(type(value) is bool for value in case["verifier_options"].values()), f"{case_id}: option is not Boolean")
        raw_hash = case["raw_manifest_message_sha256"]
        has_signature_material = case["inputs"]["verification_keys"] is not None
        require((raw_hash is not None) == has_signature_material, f"{case_id}: raw-message hash presence differs")
        if raw_hash is not None:
            require(isinstance(raw_hash, str) and re.fullmatch(r"[0-9a-f]{64}", raw_hash) is not None, f"{case_id}: malformed raw-message hash")
            raw_manifest = semantic_fixture(case["inputs"]["manifest"], fixture_hashes)
            require(hashlib.sha256(raw_manifest).hexdigest() == raw_hash, f"{case_id}: raw-message hash mismatch")
        if case["inputs"]["canonical_payload"] is not None:
            require(case["inputs"]["manifest"] is not None, f"{case_id}: payload without manifest")
            payload = semantic_fixture(case["inputs"]["canonical_payload"], fixture_hashes)
            manifest_value = strict_json(semantic_fixture(case["inputs"]["manifest"], fixture_hashes))
            require(manifest_value["ai_hash_sha256"] == hashlib.sha256(payload).hexdigest(), f"{case_id}: payload digest mismatch")
        exp = case["expected"]
        exact_keys(exp, {"top_level_reason", "signature_validity", "trusted_signer_identity", "cryptographic_signature_decision", "trust_store_validation", "trust_membership_decision", "expected_fingerprint"}, f"{case_id} expected")
        require(exp["top_level_reason"] in SEMANTIC_TOP_REASONS, f"{case_id}: unknown reason")
        require(exp["signature_validity"] in SIGNATURE_STATES, f"{case_id}: unknown signature state")
        require(exp["trusted_signer_identity"] in TRUST_STATES, f"{case_id}: unknown trust state")
        require(exp["cryptographic_signature_decision"] in CRYPTO_DECISIONS, f"{case_id}: unknown crypto decision")
        require(exp["trust_store_validation"] in STORE_DECISIONS, f"{case_id}: unknown store decision")
        require(exp["trust_membership_decision"] in MEMBERSHIP_DECISIONS, f"{case_id}: unknown membership decision")
        expected_fingerprint = exp["expected_fingerprint"]
        require(expected_fingerprint is None or re.fullmatch(r"ed25519:sha256:[0-9a-f]{64}", expected_fingerprint) is not None, f"{case_id}: malformed fingerprint")
        observed = semantic_observation(case, fixture_hashes, public_keys)
        require(observed == exp, f"{case_id}: expected {exp}, observed {observed}")
        counts[case["family"]] = counts.get(case["family"], 0) + 1
        ids.append(case_id)
        if verbose:
            print(f"PASS {case_id}")
    require(counts == EXPECTED_SEMANTIC_COUNTS, f"semantic family counts differ: {counts}")
    require(document["family_counts"] == counts, "semantic document family counts differ")
    return len(vectors), counts, ids


def precedence_source_case(source_by_id: dict[str, dict[str, Any]], case_id: str) -> tuple[dict[str, Any], bytes]:
    require(case_id in source_by_id, f"unknown frozen source case: {case_id}")
    case = source_by_id[case_id]
    return case, materialize_source(case["source"])


def precedence_manifest(
    inputs: dict[str, Any], fixture_hashes: dict[str, str], source_by_id: dict[str, dict[str, Any]]
) -> tuple[bytes, Any | None]:
    if inputs["manifest_fixture"] is not None:
        raw = semantic_fixture(inputs["manifest_fixture"], fixture_hashes)
    else:
        _, raw = precedence_source_case(source_by_id, inputs["manifest_source_case"])
    try:
        value = strict_json(raw)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return raw, None
    if inputs["manifest_overrides"]:
        require(isinstance(value, dict), "manifest overrides require an object")
        value = copy.deepcopy(value)
        value.update(copy.deepcopy(inputs["manifest_overrides"]))
    return raw, value


def precedence_keyring(
    inputs: dict[str, Any], fixture_hashes: dict[str, str], source_by_id: dict[str, dict[str, Any]]
) -> bytes | None:
    if inputs["verification_keys_fixture"] is not None:
        return semantic_fixture(inputs["verification_keys_fixture"], fixture_hashes)
    if inputs["verification_keys_source_case"] is not None:
        _, raw = precedence_source_case(source_by_id, inputs["verification_keys_source_case"])
        return raw
    return None


def condition_has_evidence(
    condition: str,
    case: dict[str, Any],
    fixture_hashes: dict[str, str],
    source_by_id: dict[str, dict[str, Any]],
) -> bool:
    inputs = case["inputs"]
    options = case["verifier_options"]
    raw_manifest, manifest_value = precedence_manifest(inputs, fixture_hashes, source_by_id)
    raw_keyring = precedence_keyring(inputs, fixture_hashes, source_by_id)

    if condition == "REQUIRED_TRUST_INPUT_ABSENT":
        return options["require_trusted_signer"] and inputs["trust_store_fixture"] is None
    if condition == "ACQUIRED_TRUST_STORE_INVALID":
        if inputs["trust_store_fixture"] is None:
            return False
        validation, _ = inspect_trust_store(
            semantic_fixture(inputs["trust_store_fixture"], fixture_hashes)
        )
        return validation == "INVALID"
    if condition == "CANONICAL_SOURCE_NOT_JSON":
        if inputs["canonical_inline_hex"] is None:
            return False
        try:
            strict_json(bytes.fromhex(inputs["canonical_inline_hex"]))
        except (UnicodeError, json.JSONDecodeError, ValueError):
            return True
        return False
    if condition == "MANIFEST_SOURCE_NOT_JSON":
        if inputs["manifest_source_case"] is None:
            return False
        source_case, source_raw = precedence_source_case(source_by_id, inputs["manifest_source_case"])
        observed, _ = parse_source(source_raw, source_case["input_kind"], source_case["capability"])
        return observed == "REJECT" and source_case["expected"]["semantic_reason"] == "MANIFEST_NOT_JSON"
    if condition == "MANIFEST_ROOT_NOT_OBJECT":
        return inputs["manifest_source_case"] is not None and manifest_value is not None and not isinstance(manifest_value, dict)
    if condition == "MANIFEST_SCHEMA_BAD":
        return isinstance(manifest_value, dict) and manifest_value.get("schema") != "ai_pack_manifest_v1"
    if condition == "MANIFEST_INPUT_SCHEMA_BAD":
        return isinstance(manifest_value, dict) and manifest_value.get("input_schema") != "ai_output_v1"
    if condition == "MANIFEST_CANONICALIZATION_BAD":
        return isinstance(manifest_value, dict) and manifest_value.get("canonicalization") not in {
            "json_sorted_keys_no_whitespace_utf8", "aelitium_jcs_profile_v2"
        }
    if condition == "MANIFEST_TIMESTAMP_BAD_ENABLED":
        return (
            options["validate_manifest_timestamp"]
            and isinstance(manifest_value, dict)
            and (
                not isinstance(manifest_value.get("ts_utc"), str)
                or ASCII_V2_TIMESTAMP.fullmatch(manifest_value["ts_utc"]) is None
            )
        )
    if condition == "MANIFEST_DIGEST_SPELLING_BAD":
        return (
            isinstance(manifest_value, dict)
            and (
                not isinstance(manifest_value.get("ai_hash_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", manifest_value["ai_hash_sha256"]) is None
            )
        )
    if condition == "MANIFEST_PAYLOAD_HASH_MISMATCH":
        if inputs["payload_hash_comparison"] != "MISMATCH" or not isinstance(manifest_value, dict):
            return False
        payload = semantic_fixture(inputs["canonical_payload_fixture"], fixture_hashes)
        return manifest_value.get("ai_hash_sha256") != hashlib.sha256(payload).hexdigest()
    if condition == "PRESENT_SIGNATURE_INVALID":
        if raw_keyring is None:
            return False
        state, _, _ = inspect_signature(raw_manifest, raw_keyring)
        return state == "INVALID"
    if condition == "SIGNATURE_ENFORCEMENT_REQUESTED":
        return options["require_signature"] or options["require_trusted_signer"]
    if condition == "BINDING_HASH_MISMATCH_PRESENT":
        return inputs["binding_condition"] == "HASH_MISMATCH"
    if condition == "REQUIRED_BINDING_ABSENT":
        return options["require_binding"] and inputs["binding_condition"] == "REQUIRED_ABSENT"
    if condition == "REQUIRED_SIGNER_MEMBERSHIP_MISSING":
        if not options["require_trusted_signer"] or inputs["trust_store_fixture"] is None:
            return False
        validation, trusted = inspect_trust_store(
            semantic_fixture(inputs["trust_store_fixture"], fixture_hashes)
        )
        if validation != "VALID":
            return False
        if not trusted:
            return True
        if raw_keyring is None:
            return False
        try:
            keyring_value = strict_json(raw_keyring)
            public_key = decode_public_key(keyring_value["keys"][0]["public_key_b64"])
        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError, IndexError, binascii.Error):
            return False
        return fingerprint(public_key) not in trusted
    if condition == "AUTHORIZED_INVOCATION_HASH_MISMATCH":
        return inputs["invocation_condition"] == "AUTHORIZED_HASH_MISMATCH"
    if condition == "AUTHORIZED_FRESHNESS_TIMESTAMP_MALFORMED":
        return inputs["freshness_condition"] == "AUTHORIZED_TIMESTAMP_MALFORMED"
    raise CorpusFailure(f"unknown precedence condition: {condition}")


def validate_precedence_binding_materials(materials: Any) -> None:
    exact_keys(materials, {"NONE", "REQUIRED_ABSENT", "VALID", "HASH_MISMATCH"}, "precedence binding materials")
    require(materials["NONE"] == {"fields_present": False}, "NONE binding material differs")
    require(materials["REQUIRED_ABSENT"] == {"fields_present": False}, "required-absent binding material differs")
    material_keys = {
        "fields_present", "request_hash", "response_hash", "canonical_hash_input_hex",
        "expected_binding_hash", "manifest_binding_hash", "payload_binding_hash",
    }
    for state in ("VALID", "HASH_MISMATCH"):
        material = materials[state]
        exact_keys(material, material_keys, f"{state} binding material")
        require(material["fields_present"] is True, f"{state} binding fields are not present")
        request_hash = material["request_hash"]
        response_hash = material["response_hash"]
        require(isinstance(request_hash, str) and re.fullmatch(r"[0-9a-f]{64}", request_hash) is not None, f"{state} request hash differs")
        require(isinstance(response_hash, str) and re.fullmatch(r"[0-9a-f]{64}", response_hash) is not None, f"{state} response hash differs")
        hash_input = json.dumps(
            {"request_hash": request_hash, "response_hash": response_hash},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        require(material["canonical_hash_input_hex"] == hash_input.hex(), f"{state} binding hash input differs")
        expected = hashlib.sha256(hash_input).hexdigest()
        require(material["expected_binding_hash"] == expected, f"{state} derived binding hash differs")
        for field in ("manifest_binding_hash", "payload_binding_hash"):
            require(isinstance(material[field], str) and re.fullmatch(r"[0-9a-f]{64}", material[field]) is not None, f"{state} stored binding hash differs")
        if state == "VALID":
            require(material["manifest_binding_hash"] == expected and material["payload_binding_hash"] == expected, "valid binding material does not match")
        else:
            require(material["manifest_binding_hash"] != expected or material["payload_binding_hash"] != expected, "mismatch binding material is valid")


def run_precedence_cases(
    document: dict[str, Any],
    source_document: dict[str, Any],
    semantic_document: dict[str, Any],
    *,
    verbose: bool,
) -> tuple[int, list[str]]:
    exact_keys(
        document,
        {"contract", "scope", "candidate_failure_contract", "input_recipe_contract", "precedence_relation", "binding_materials", "check_vocabulary", "deliberate_exclusions", "case_count", "vectors"},
        "precedence vector document",
    )
    require(document["contract"] == EXPECTED_PRECEDENCE_CONTRACT, "precedence contract identifier differs")
    require(document["scope"] == "PHASE2_PRECEDENCE_AND_CROSS_CONTRACT", "precedence scope differs")
    require(
        document["candidate_failure_contract"] == {
            "condition": "closed language-neutral condition identifier whose evidence is validated by the runner",
            "reason": "authorized public reason implied by condition",
            "winner": "candidate with the lowest rank in precedence_relation",
            "downstream_candidate": "may describe a failure that would apply only if every earlier check succeeded",
            "not_evaluated_checks": "explicit list of checks blocked by an unmet prerequisite; an empty list preserves independent post-payload dimension evaluation",
        },
        "candidate failure contract differs",
    )
    require(
        document["input_recipe_contract"] == {
            "fixture_reference": "bare fixture name resolved through semantic_vectors.json fixture_hashes",
            "source_case_reference": "case_id resolved to the exact source descriptor and expected source decision in source_vectors.json",
            "canonical_inline_hex": "lowercase hexadecimal encoding of exact canonical-input bytes",
            "manifest_overrides": "replace the named top-level decoded values in the referenced manifest fixture for candidate-condition evaluation; no signature is regenerated",
            "binding_condition": "select the correspondingly named frozen entry in binding_materials",
            "authorized_downstream_condition": "rank-only candidate already named by Level 1; it does not define G-07 invocation grammar or G-11 Freshness policy",
        },
        "precedence input recipe contract differs",
    )
    require(document["precedence_relation"] == PRECEDENCE_RELATION, "precedence relation differs")
    validate_precedence_binding_materials(document["binding_materials"])
    require(document["check_vocabulary"] == sorted(PRECEDENCE_CHECKS), "precedence check vocabulary differs")
    require(
        document["deliberate_exclusions"] == [{
            "case": "TRUSTED_SIGNER_NOT_FOUND_VS_CONCRETE_INVOCATION_OR_FRESHNESS_FAILURE",
            "status": "EXCLUDED_FROM_PHASE2_FIXTURES",
            "reason": "A concrete end-to-end downstream fixture would require completing open G-07 invocation or G-11 Freshness semantics. Level 1 prose already places TRUSTED_SIGNER_NOT_FOUND first; Phase 2 does not invent the missing cross-gap input contract.",
        }],
        "cross-gap exclusion differs",
    )
    serialized = json.dumps(document, sort_keys=True)
    for operational_code in (
        "INPUT_IO_ERROR", "INPUT_NOT_REGULAR_FILE", "INPUT_CHANGED_DURING_SNAPSHOT",
        "RESOURCE_EXHAUSTED", "RESOURCE_LIMIT_EXCEEDED",
    ):
        require(operational_code not in serialized, f"operational code leaked into precedence corpus: {operational_code}")

    ranks = {
        reason: entry["rank"]
        for entry in PRECEDENCE_RELATION
        for reason in entry["reasons"]
    }
    require(len(ranks) == len(CONDITION_REASONS), "precedence reason registry differs")
    source_by_id = {case["case_id"]: case for case in source_document["vectors"]}
    fixture_hashes = semantic_document["fixture_hashes"]
    vectors = document["vectors"]
    require(isinstance(vectors, list) and document["case_count"] == len(vectors), "precedence case count differs")
    require(len(vectors) == EXPECTED_PRECEDENCE_COUNT, "precedence stable count differs")
    ids: list[str] = []
    for case in vectors:
        exact_keys(case, {"case_id", "family", "inputs", "verifier_options", "candidate_failures", "expected", "compatibility"}, "precedence case")
        case_id = case["case_id"]
        require(isinstance(case_id, str) and CASE_ID.fullmatch(case_id) is not None, f"invalid precedence case ID: {case_id!r}")
        require(case["family"] == "PRECEDENCE", f"{case_id}: family differs")
        require(case["compatibility"] in COMPATIBILITY, f"{case_id}: compatibility differs")
        inputs = case["inputs"]
        exact_keys(inputs, {"canonical_payload_fixture", "canonical_inline_hex", "manifest_fixture", "manifest_source_case", "manifest_overrides", "verification_keys_fixture", "verification_keys_source_case", "trust_store_fixture", "binding_condition", "invocation_condition", "freshness_condition", "payload_hash_comparison"}, f"{case_id} inputs")
        require((inputs["canonical_payload_fixture"] is None) != (inputs["canonical_inline_hex"] is None), f"{case_id}: canonical input must have exactly one representation")
        if inputs["canonical_payload_fixture"] is not None:
            require(inputs["canonical_payload_fixture"] in fixture_hashes, f"{case_id}: unknown canonical fixture")
        else:
            require(isinstance(inputs["canonical_inline_hex"], str) and LOWER_HEX.fullmatch(inputs["canonical_inline_hex"]) is not None, f"{case_id}: malformed canonical inline hex")
        require((inputs["manifest_fixture"] is None) != (inputs["manifest_source_case"] is None), f"{case_id}: manifest input must have exactly one representation")
        if inputs["manifest_fixture"] is not None:
            require(inputs["manifest_fixture"] in fixture_hashes, f"{case_id}: unknown manifest fixture")
        else:
            precedence_source_case(source_by_id, inputs["manifest_source_case"])
        require(isinstance(inputs["manifest_overrides"], dict), f"{case_id}: manifest overrides malformed")
        require(not inputs["manifest_overrides"] or inputs["manifest_fixture"] is not None, f"{case_id}: overrides require fixture manifest")
        require(not (inputs["verification_keys_fixture"] is not None and inputs["verification_keys_source_case"] is not None), f"{case_id}: two keyring representations")
        if inputs["verification_keys_fixture"] is not None:
            require(inputs["verification_keys_fixture"] in fixture_hashes, f"{case_id}: unknown keyring fixture")
        if inputs["verification_keys_source_case"] is not None:
            precedence_source_case(source_by_id, inputs["verification_keys_source_case"])
        if inputs["trust_store_fixture"] is not None:
            require(inputs["trust_store_fixture"] in fixture_hashes, f"{case_id}: unknown trust fixture")
        require(inputs["binding_condition"] in {"NONE", "VALID", "HASH_MISMATCH", "REQUIRED_ABSENT"}, f"{case_id}: binding condition differs")
        require(inputs["invocation_condition"] in {"NONE", "AUTHORIZED_HASH_MISMATCH"}, f"{case_id}: invocation condition differs")
        require(inputs["freshness_condition"] in {"NONE", "AUTHORIZED_TIMESTAMP_MALFORMED"}, f"{case_id}: Freshness condition differs")
        require(inputs["payload_hash_comparison"] in {"MATCH", "MISMATCH", "NOT_REACHED"}, f"{case_id}: payload-hash comparison differs")
        exact_keys(case["verifier_options"], {"validate_manifest_timestamp", "require_signature", "require_binding", "require_trusted_signer"}, f"{case_id} options")
        require(all(type(value) is bool for value in case["verifier_options"].values()), f"{case_id}: non-Boolean option")

        candidates = case["candidate_failures"]
        require(isinstance(candidates, list) and candidates, f"{case_id}: candidate set is empty")
        conditions: list[str] = []
        reasons: list[str] = []
        for candidate in candidates:
            exact_keys(candidate, {"condition", "reason"}, f"{case_id} candidate")
            condition = candidate["condition"]
            reason = candidate["reason"]
            require(condition in CONDITION_REASONS, f"{case_id}: unknown candidate condition")
            require(CONDITION_REASONS[condition] == reason, f"{case_id}: condition/reason mismatch")
            require(condition_has_evidence(condition, case, fixture_hashes, source_by_id), f"{case_id}: candidate lacks frozen evidence: {condition}")
            conditions.append(condition)
            reasons.append(reason)
        require(len(conditions) == len(set(conditions)), f"{case_id}: duplicate candidate condition")
        require(len(reasons) == len(set(reasons)), f"{case_id}: duplicate candidate reason")
        expected = case["expected"]
        exact_keys(expected, {"winning_top_level_reason", "signature_validity", "trusted_signer_identity", "timestamp_decision", "not_evaluated_checks", "bypassed_checks"}, f"{case_id} expected")
        winner = expected["winning_top_level_reason"]
        require(reasons.count(winner) == 1, f"{case_id}: winner is not exactly one candidate")
        observed_winner = min(reasons, key=ranks.__getitem__)
        require(winner == observed_winner, f"{case_id}: expected winner {winner}, precedence gives {observed_winner}")
        require(expected["signature_validity"] in SIGNATURE_STATES, f"{case_id}: signature state differs")
        require(expected["trusted_signer_identity"] in TRUST_STATES, f"{case_id}: trust state differs")
        not_evaluated = expected["not_evaluated_checks"]
        bypassed = expected["bypassed_checks"]
        require(isinstance(not_evaluated, list) and len(not_evaluated) == len(set(not_evaluated)), f"{case_id}: excluded checks malformed")
        require(set(not_evaluated) <= PRECEDENCE_CHECKS, f"{case_id}: unknown excluded check")
        require(isinstance(bypassed, list) and len(bypassed) == len(set(bypassed)) and set(bypassed) <= PRECEDENCE_CHECKS, f"{case_id}: bypassed checks malformed")
        rank = ranks[winner]
        if rank <= 20:
            require({"BUNDLE_INSPECTION", "KEYRING_SEMANTICS"} <= set(not_evaluated), f"{case_id}: early trust boundary does not exclude bundle inspection")
        elif rank < ranks["SIGNATURE_INVALID"]:
            require("KEYRING_SEMANTICS" in not_evaluated, f"{case_id}: payload/manifest winner does not exclude keyring")
        elif rank <= ranks["SIGNATURE_REQUIRED"]:
            require("TRUST_MEMBERSHIP" in not_evaluated, f"{case_id}: signature prerequisite does not exclude trust membership")
            require(not ({"BINDING", "INVOCATION", "FRESHNESS"} & set(not_evaluated)), f"{case_id}: independent post-payload dimension was incorrectly excluded")
        else:
            require(not ({"BINDING", "TRUST_MEMBERSHIP", "INVOCATION", "FRESHNESS"} & set(not_evaluated)), f"{case_id}: evaluated post-payload dimension was incorrectly excluded")

        if not case["verifier_options"]["validate_manifest_timestamp"]:
            observed_timestamp = "BYPASSED"
            require(bypassed == ["MANIFEST_TIMESTAMP"], f"{case_id}: disabled timestamp is not explicitly bypassed")
        elif rank < ranks["MANIFEST_BAD_TS_UTC"]:
            observed_timestamp = "NOT_REACHED"
            require(not bypassed, f"{case_id}: enabled timestamp cannot be bypassed")
        elif winner == "MANIFEST_BAD_TS_UTC":
            observed_timestamp = "FAIL"
            require(not bypassed, f"{case_id}: failed timestamp cannot be bypassed")
        else:
            observed_timestamp = "PASS"
            require(not bypassed, f"{case_id}: enabled timestamp cannot be bypassed")
        require(expected["timestamp_decision"] == observed_timestamp, f"{case_id}: timestamp decision differs")

        has_keyring = inputs["verification_keys_fixture"] is not None or inputs["verification_keys_source_case"] is not None
        if rank <= 20:
            require(expected["signature_validity"] == "NOT_EVALUATED", f"{case_id}: early input boundary inspected signature presence")
        elif rank < ranks["SIGNATURE_INVALID"]:
            required_state = "NOT_EVALUATED" if has_keyring else "ABSENT"
            require(expected["signature_validity"] == required_state, f"{case_id}: pre-signature state differs")
        elif winner == "SIGNATURE_INVALID":
            require(expected["signature_validity"] == "INVALID", f"{case_id}: invalid signature state differs")
        elif winner == "SIGNATURE_REQUIRED":
            require(expected["signature_validity"] == "ABSENT", f"{case_id}: required signature state differs")
        else:
            require(expected["signature_validity"] == "VALID", f"{case_id}: downstream winner lacks valid signature")
        require(expected["trusted_signer_identity"] == "UNESTABLISHED", f"{case_id}: trust state must remain UNESTABLISHED")
        ids.append(case_id)
        if verbose:
            print(f"PASS {case_id}")
    return len(vectors), ids


def validate_manifest(manifest: dict[str, Any], source_count: int, source_kinds: dict[str, int], schema_count: int, schema_families: dict[str, int], semantic_count: int, semantic_families: dict[str, int], precedence_count: int, all_ids: list[str]) -> None:
    exact_keys(manifest, {"block_2a_frozen", "block_2b1_frozen", "block_2b2_frozen", "block_3", "byte_source_contract", "case_counts", "case_id_policy", "contract", "ed25519_portable_profile", "fixture_count", "gap_status", "instance_recipe_contract", "notes", "runner", "schemas", "scope", "status", "subject_contract", "vector_files"}, "corpus manifest")
    require(manifest["contract"] == EXPECTED_CONTRACT, "manifest contract differs")
    require(manifest["status"] == "NORMATIVE-UNRELEASED", "manifest status differs")
    require(manifest["scope"] == "SOURCE_SCHEMA_SIGNATURE_TRUST_ED25519_PORTABLE_PROFILE_PRECEDENCE", "manifest scope differs")
    require(manifest["subject_contract"] == EXPECTED_SUBJECT, "subject contract differs")
    require(manifest["vector_files"] == ["source_vectors.json", "schema_vectors.json", "semantic_vectors.json", "precedence_vectors.json"], "vector file order differs")
    require(manifest["case_id_policy"] == "GLOBALLY_UNIQUE_ASCII_LOWERCASE_DOT_SEPARATED", "case ID policy differs")
    require(manifest["byte_source_contract"] == "INLINE_UTF8_OR_INLINE_HEX_OR_FIXTURE_WITH_SHA256", "byte source contract differs")
    require(manifest["instance_recipe_contract"] == "AELITIUM-SCHEMA-INSTANCE-RECIPE-1", "recipe contract differs")
    require(manifest["runner"] == "../run_verifier_contract_phase2.py", "runner path differs")
    require(
        manifest["gap_status"]
        == {
            "G-04": "CLOSED",
            "G-05": "OPEN — NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
            "G-06": "CLOSED",
        },
        "gap status differs",
    )
    require(
        manifest["block_2a_frozen"] == {
            "case_count": 210,
            "source_vectors_sha256": BLOCK2A_SOURCE_SHA256,
            "schema_vectors_sha256": BLOCK2A_SCHEMA_SHA256,
        },
        "Block 2A frozen declaration differs",
    )
    require(hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == BLOCK2A_SOURCE_SHA256, "Block 2A source vectors changed")
    require(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() == BLOCK2A_SCHEMA_SHA256, "Block 2A schema vectors changed")
    require(
        manifest["block_2b1_frozen"] == {
            "case_count": 36,
            "original_semantic_vectors_sha256": BLOCK2B1_SEMANTIC_SHA256,
            "original_vector_set_sha256": BLOCK2B1_VECTOR_SET_SHA256,
        },
        "Block 2B1 frozen declaration differs",
    )
    require(
        manifest["block_2b2_frozen"] == {
            "case_count": 23,
            "precedence_vectors_sha256": BLOCK2B2_PRECEDENCE_SHA256,
        },
        "Block 2B2 frozen declaration differs",
    )
    require(hashlib.sha256(PRECEDENCE_PATH.read_bytes()).hexdigest() == BLOCK2B2_PRECEDENCE_SHA256, "Block 2B2 precedence vectors changed")
    require(
        manifest["block_3"] == {
            "status": "ED25519_RUNTIME_ALIGNMENT_PENDING",
            "closure_claimed": False,
            "closure_mechanism": None,
        },
        "Block 3 declaration differs",
    )
    require(
        manifest["ed25519_portable_profile"]
        == {
            "profile": ED25519_PROFILE,
            "status": "NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
            "case_count": 12,
            "fallback": "NONE",
        },
        "portable Ed25519 manifest declaration differs",
    )
    require(len(all_ids) == len(set(all_ids)), "case IDs are not globally unique")
    require(all(CASE_ID.fullmatch(case_id) is not None for case_id in all_ids), "case ID policy violated")
    actual_block2a_counts = {
        "total": source_count + schema_count,
        "source_total": source_count,
        "schema_total": schema_count,
        "manifest_source": source_kinds.get("MANIFEST_V1", 0) + source_kinds.get("MANIFEST_V2", 0),
        "manifest_schema": schema_families.get("MANIFEST_SCHEMA", 0),
        "keyring_source": source_kinds.get("VERIFICATION_KEYS_V1", 0),
        "keyring_schema": schema_families.get("KEYRING_SCHEMA", 0),
        "trust_source": source_kinds.get("TRUST_STORE_V1", 0),
        "trust_schema": schema_families.get("TRUST_SCHEMA", 0),
    }
    require(actual_block2a_counts == EXPECTED_BLOCK2A_COUNTS, f"Block 2A stable counts differ: {actual_block2a_counts}")
    actual_counts = {
        **actual_block2a_counts,
        "total": source_count + schema_count + semantic_count + precedence_count,
        "semantic_total": semantic_count,
        "signature_semantic": semantic_families.get("SIGNATURE_SEMANTIC", 0),
        "trust_semantic": semantic_families.get("TRUST_SEMANTIC", 0),
        "ed25519_strict_semantic": semantic_families.get("ED25519_STRICT_SEMANTIC", 0),
        "precedence_total": precedence_count,
    }
    require(manifest["case_counts"] == actual_counts, f"manifest counts differ: {actual_counts}")
    require(actual_counts == EXPECTED_ALL_COUNTS, f"Phase 2 corpus counts differ: {actual_counts}")
    fixture_files = sorted(path for path in (CORPUS / "fixtures").iterdir() if path.is_file())
    require(manifest["fixture_count"] == len(fixture_files), "fixture count differs")
    require(manifest["fixture_count"] == 25, "Block 2B1 fixture inventory differs")
    require(isinstance(manifest["notes"], list) and len(manifest["notes"]) == 7 and all(isinstance(note, str) and note for note in manifest["notes"]), "manifest notes malformed")


def run(*, verbose: bool) -> dict[str, Any]:
    manifest = load_canonical(MANIFEST_PATH)
    source_document = load_canonical(SOURCE_PATH)
    schema_document = load_canonical(SCHEMA_PATH)
    semantic_document = load_canonical(SEMANTIC_PATH)
    precedence_document = load_canonical(PRECEDENCE_PATH)
    schemas, validators = load_schemas(manifest)
    validate_schema_boundaries(schemas)
    source_count, source_kinds = run_source_cases(source_document, validators, verbose=verbose)
    schema_count, schema_families = run_schema_cases(schema_document, validators, verbose=verbose)
    semantic_count, semantic_families, semantic_ids = run_semantic_cases(semantic_document, verbose=verbose)
    precedence_count, precedence_ids = run_precedence_cases(
        precedence_document, source_document, semantic_document, verbose=verbose
    )
    all_ids = [case["case_id"] for case in source_document["vectors"]] + [case["case_id"] for case in schema_document["vectors"]] + semantic_ids + precedence_ids
    validate_manifest(manifest, source_count, source_kinds, schema_count, schema_families, semantic_count, semantic_families, precedence_count, all_ids)
    return {
        "passed": source_count + schema_count + semantic_count + precedence_count,
        "total": source_count + schema_count + semantic_count + precedence_count,
        "source": source_count,
        "schema": schema_count,
        "semantic": semantic_count,
        "signature_semantic": semantic_families["SIGNATURE_SEMANTIC"],
        "trust_semantic": semantic_families["TRUST_SEMANTIC"],
        "ed25519_strict_semantic": semantic_families["ED25519_STRICT_SEMANTIC"],
        "precedence": precedence_count,
        "case_counts": manifest["case_counts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        result = run(verbose=args.verbose)
    except (CorpusFailure, OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, binascii.Error) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"SOURCE PASS {result['source']}/{result['source']}")
    print(f"SCHEMA PASS {result['schema']}/{result['schema']}")
    print(f"SIGNATURE_SEMANTIC PASS {result['signature_semantic']}/{result['signature_semantic']}")
    print(f"TRUST_SEMANTIC PASS {result['trust_semantic']}/{result['trust_semantic']}")
    print(f"ED25519_STRICT_SEMANTIC PASS {result['ed25519_strict_semantic']}/{result['ed25519_strict_semantic']}")
    print(f"SEMANTIC PASS {result['semantic']}/{result['semantic']}")
    print(f"PRECEDENCE PASS {result['precedence']}/{result['precedence']}")
    print(f"PASS {result['passed']}/{result['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
