#!/usr/bin/env python3
"""Build the frozen legacy-v1 capability and operational-policy corpus.

This maintenance helper imports no AELITIUM runtime module.  It materializes a
small closed byte-recipe language, attaches corruption hashes, and writes
explicit policy expectations.  Committed data, not this script, are normative.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT / "legacy_v1_operational_policy"
CASES_PATH = CORPUS_DIR / "cases.json"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

CONTRACT = "aelitium-legacy-v1-operational-policy-conformance-v1"
STATUS = "NORMATIVE-UNRELEASED"
OPERATION_CONTRACT = "AELITIUM-LEGACY-V1-POLICY-OPERATION-1"
V1_IDENTIFIER = "json_sorted_keys_no_whitespace_utf8"
V2_IDENTIFIER = "aelitium_jcs_profile_v2"

UCD = {
    "13.0.0": {
        "profile_id": "AELITIUM_UCD_ND_13_0_0_1",
        "range_file_sha256": "bf287074b61dbb4a03a10645580b5ae0d1e106d75aa6c26881a7a277712c4f8b",
        "unicode_version": "13.0.0",
    },
    "14.0.0": {
        "profile_id": "AELITIUM_UCD_ND_14_0_0_1",
        "range_file_sha256": "5a75c753790a222c430dbfc95adaa2c3ec6701862d1728eae92d9ed0e2df59c8",
        "unicode_version": "14.0.0",
    },
    "15.0.0": {
        "profile_id": "AELITIUM_UCD_ND_15_0_0_1",
        "range_file_sha256": "0f10e369beb834ccee109f3ccc8d75f6ff8067871baf7109a106f1dac7430222",
        "unicode_version": "15.0.0",
    },
}

MINIMUM_LIMITS = {
    "max_file_bytes": 65_536,
    "max_structural_depth": 1_024,
    "max_total_snapshot_bytes": 262_144,
    "max_value_occurrences": 65_536,
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _literal(value: bytes) -> dict[str, Any]:
    return {"op": "LITERAL_HEX", "hex": value.hex()}


def _repeat(value: bytes, count: int) -> dict[str, Any]:
    if len(value) != 1:
        raise ValueError("REPEAT_BYTE requires exactly one byte")
    return {"op": "REPEAT_BYTE", "byte_hex": value.hex(), "count": count}


def _concat(*parts: dict[str, Any]) -> dict[str, Any]:
    return {"op": "CONCAT", "parts": list(parts)}


def _integer_recipe(digits: int, *, negative: bool = False) -> dict[str, Any]:
    parts = []
    if negative:
        parts.append(_literal(b"-"))
    parts.append(_repeat(b"7", digits))
    return _concat(*parts)


def _json_integer_member(
    digits: int,
    *,
    member: bytes = b"value",
    negative: bool = False,
    suffix: bytes = b"}",
) -> dict[str, Any]:
    return _concat(
        _literal(b'{"' + member + b'":'),
        _integer_recipe(digits, negative=negative),
        _literal(suffix),
    )


def _materialize(recipe: dict[str, Any]) -> bytes:
    op = recipe["op"]
    if op == "LITERAL_HEX":
        return bytes.fromhex(recipe["hex"])
    if op == "REPEAT_BYTE":
        value = bytes.fromhex(recipe["byte_hex"])
        if len(value) != 1 or recipe["count"] < 0:
            raise ValueError("invalid REPEAT_BYTE recipe")
        return value * recipe["count"]
    if op == "CONCAT":
        return b"".join(_materialize(part) for part in recipe["parts"])
    if op == "JSON_STRING_OF_SIZE":
        size = recipe["byte_length"]
        fill = bytes.fromhex(recipe["fill_byte_hex"])
        if size < 2 or len(fill) != 1 or fill in b'"\\' or fill[0] < 0x20:
            raise ValueError("invalid JSON_STRING_OF_SIZE recipe")
        return b'"' + fill * (size - 2) + b'"'
    if op == "NESTED_ARRAY":
        depth = recipe["depth"]
        scalar = bytes.fromhex(recipe["scalar_hex"])
        if depth < 0:
            raise ValueError("invalid NESTED_ARRAY recipe")
        return b"[" * depth + scalar + b"]" * depth
    if op == "NULL_ARRAY":
        occurrences = recipe["value_occurrences"]
        if occurrences < 1:
            raise ValueError("invalid NULL_ARRAY recipe")
        elements = occurrences - 1
        return b"[" + b",".join([b"null"] * elements) + b"]"
    raise ValueError(f"unknown recipe operation: {op}")


def _source(recipe: dict[str, Any]) -> dict[str, Any]:
    data = _materialize(recipe)
    return {
        "byte_length": len(data),
        "recipe": recipe,
        "sha256": _sha256(data),
    }


def _integer_source(
    digits: int,
    *,
    negative: bool = False,
    source_role: str = "AI_CANONICAL_JSON",
    position: str = "GOVERNED",
    recipe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "integer_magnitude_digits": digits,
        "negative": negative,
        "position": position,
        "source": _source(recipe or _json_integer_member(digits, negative=negative)),
        "source_role": source_role,
    }


def _v1_fixed(capability: str = "V1_FROZEN_LEGACY_COMPATIBILITY") -> dict[str, Any]:
    return {
        "capability": capability,
        "integer_conversion": {
            "maximum_decimal_digits": 640,
            "mode": "BOUNDED",
        },
        "timestamp_digit_profile": "ASCII",
        "timestamp_final_lf": "ACCEPT_ONE",
    }


def _v1_named(limit: int | None, unicode_version: str = "15.0.0") -> dict[str, Any]:
    conversion = (
        {"maximum_decimal_digits": None, "mode": "UNLIMITED"}
        if limit is None
        else {"maximum_decimal_digits": limit, "mode": "BOUNDED"}
    )
    return {
        "capability": "V1_NAMED_RUNTIME_COMPATIBILITY",
        "integer_conversion": conversion,
        "timestamp_digit_profile": copy.deepcopy(UCD[unicode_version]),
        "timestamp_final_lf": "ACCEPT_ONE",
    }


def _capability_request(v1: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "dispatch": "AELITIUM-DISPATCH-JSON-1",
        "v1": copy.deepcopy(v1 or _v1_fixed()),
        "v2": {"capability": "V2_PORTABLE"},
    }


def _limit_state(
    values: dict[str, int] | None = None,
    *,
    claimed: str | None = "AELITIUM_CLEANROOM_MINIMUM_1",
) -> dict[str, Any]:
    chosen = copy.deepcopy(values or MINIMUM_LIMITS)
    return {
        "advertised": copy.deepcopy(chosen),
        "claimed_envelope": claimed,
        "effective": chosen,
    }


def _configuration(
    *,
    v1: dict[str, Any] | None = None,
    input_mode: str = "IMMUTABLE_BYTES",
    limits: dict[str, int] | None = None,
    claimed: str | None = "AELITIUM_CLEANROOM_MINIMUM_1",
) -> dict[str, Any]:
    return {
        "capability": _capability_request(v1),
        "input_mode": input_mode,
        "limits": _limit_state(limits, claimed=claimed),
    }


def _limit_fact(
    name: str,
    unit: str,
    maximum: int | str | None,
    observed: int | str | None,
) -> dict[str, Any]:
    return {
        "maximum": maximum,
        "name": name,
        "observed_at_least": observed,
        "unit": unit,
    }


def _tool_bytes(value: dict[str, Any]) -> bytes:
    # Corpus strings are ASCII and numbers are safe integers, so this explicit
    # compact, sorted encoding is byte-identical to RFC 8785 for this schema.
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _operational_expected(
    configuration: dict[str, Any],
    *,
    code: str,
    phase: str,
    input_ref: str | None,
    limit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested = copy.deepcopy(configuration["capability"])
    result = {
        "capability": {
            "effective": None if code == "CAPABILITY_PROFILE_UNAVAILABLE" else copy.deepcopy(requested),
            "requested": requested,
        },
        "contract": "aelitium-verifier-tool-result-v1",
        "input_mode": configuration["input_mode"],
        "limits": copy.deepcopy(configuration["limits"]),
        "operation": "VERIFY_BUNDLE",
        "operational_result": {
            "detail": None,
            "input_ref": input_ref,
            "limit": limit,
            "operational_code": code,
            "phase": phase,
        },
        "outcome": "OPERATIONAL_OUTCOME",
        "rc": 3,
        "verification_result": None,
    }
    encoded = _tool_bytes(result)
    return {
        "kind": "OPERATIONAL_TOOL_RESULT",
        "tool_result": result,
        "tool_result_sha256": _sha256(encoded),
        "tool_result_utf8_hex": encoded.hex(),
    }


def _checkpoint(decision: str, **facts: Any) -> dict[str, Any]:
    return {"decision": decision, "kind": "POLICY_CHECKPOINT", **facts}


def _case(
    case_id: str,
    category: str,
    operation: str,
    description: str,
    input_value: dict[str, Any],
    expected: dict[str, Any],
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "category": category,
        "configuration": copy.deepcopy(configuration or _configuration()),
        "description": description,
        "expected": expected,
        "input": input_value,
        "operation": operation,
    }


def _operational_case(
    case_id: str,
    category: str,
    operation: str,
    description: str,
    input_value: dict[str, Any],
    *,
    code: str,
    phase: str,
    input_ref: str | None,
    limit: dict[str, Any] | None = None,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chosen = copy.deepcopy(configuration or _configuration())
    return _case(
        case_id,
        category,
        operation,
        description,
        input_value,
        _operational_expected(
            chosen,
            code=code,
            phase=phase,
            input_ref=input_ref,
            limit=limit,
        ),
        chosen,
    )


def _timestamp_source(value: str) -> dict[str, Any]:
    source = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "decoded_code_points": [f"U+{ord(character):04X}" for character in value],
        "json_string_source": _source(_literal(source)),
    }


def _role_sources(sizes: dict[str, int]) -> dict[str, Any]:
    return {
        role: _source(
            {
                "op": "JSON_STRING_OF_SIZE",
                "byte_length": size,
                "fill_byte_hex": "61",
            }
        )
        for role, size in sizes.items()
    }


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    portable_config = _configuration(v1=_v1_fixed("V1_RESTRICTED_PORTABLE"))

    # Integer and capability boundaries.
    for case_id, digits, negative, decision in (
        ("integer.portable.positive_640", 640, False, "EVALUATE_SEMANTICALLY"),
        ("integer.portable.negative_640", 640, True, "EVALUATE_SEMANTICALLY"),
    ):
        cases.append(
            _case(
                case_id,
                "INTEGER_CAPABILITY",
                "CLASSIFY_INTEGER_SOURCE",
                f"A {digits}-digit {'negative' if negative else 'positive'} integer is portable.",
                _integer_source(digits, negative=negative),
                _checkpoint(decision, maximum_decimal_digits=640),
                portable_config,
            )
        )

    for digits, negative in ((641, False), (641, True), (4300, False), (4301, False), (10000, False)):
        config = portable_config
        cases.append(
            _operational_case(
                f"integer.portable.{'negative_' if negative else ''}{digits}",
                "INTEGER_CAPABILITY",
                "CLASSIFY_INTEGER_SOURCE",
                f"A reached {digits}-digit integer is outside the portable v1 capability.",
                _integer_source(digits, negative=negative),
                code="INPUT_OUTSIDE_DECLARED_CAPABILITY",
                phase="CANONICAL_PARSE",
                input_ref="AI_CANONICAL_JSON",
                limit=_limit_fact("INTEGER_DECIMAL_DIGITS", "DIGITS", 640, digits),
                configuration=config,
            )
        )

    named_integer_cases = (
        ("integer.named_640.at_limit", 640, 640, "AI_CANONICAL_JSON", "EVALUATE_SEMANTICALLY", None),
        ("integer.named_640.above_limit", 640, 641, "AI_CANONICAL_JSON", "PROFILE_RELATIVE_SEMANTIC_FAILURE", "CANONICAL_NOT_JSON"),
        ("integer.named_4300.at_limit", 4300, 4300, "AI_MANIFEST_JSON", "EVALUATE_SEMANTICALLY", None),
        ("integer.named_4300.above_limit", 4300, 4301, "AI_MANIFEST_JSON", "PROFILE_RELATIVE_SEMANTIC_FAILURE", "MANIFEST_NOT_JSON"),
        ("integer.named_4300.keyring_10000", 4300, 10000, "VERIFICATION_KEYS_JSON", "PROFILE_RELATIVE_SEMANTIC_FAILURE", "SIGNATURE_INVALID"),
        ("integer.named_777.trust_at_limit", 777, 777, "TRUST_STORE", "EVALUATE_SEMANTICALLY", None),
        ("integer.named_777.trust_above_limit", 777, 778, "TRUST_STORE", "PROFILE_RELATIVE_SEMANTIC_FAILURE", "TRUST_STORE_INVALID"),
    )
    for case_id, limit, digits, role, decision, reason in named_integer_cases:
        cases.append(
            _case(
                case_id,
                "INTEGER_CAPABILITY",
                "CLASSIFY_INTEGER_SOURCE",
                f"Named bounded profile {limit} classifies a {digits}-digit token at {role}.",
                _integer_source(digits, source_role=role),
                _checkpoint(
                    decision,
                    integer_decimal_digit_limit=limit,
                    semantic_reason=reason,
                ),
                _configuration(v1=_v1_named(limit)),
            )
        )

    cases.append(
        _case(
            "integer.named_unlimited.10000",
            "INTEGER_CAPABILITY",
            "CLASSIFY_INTEGER_SOURCE",
            "The explicit unlimited conversion profile evaluates a 10,000-digit token subject to resources.",
            _integer_source(10000),
            _checkpoint("EVALUATE_SEMANTICALLY", integer_decimal_digit_limit="UNLIMITED"),
            _configuration(v1=_v1_named(None)),
        )
    )
    cases.append(
        _case(
            "integer.programmatic.640",
            "INTEGER_CAPABILITY",
            "CLASSIFY_PROGRAMMATIC_INTEGER",
            "A programmatic 640-digit exact integer is portable.",
            {"integer": _source(_integer_recipe(640)), "integer_magnitude_digits": 640},
            _checkpoint("EVALUATE_SEMANTICALLY", maximum_decimal_digits=640),
            portable_config,
        )
    )
    cases.append(
        _operational_case(
            "integer.programmatic.641",
            "INTEGER_CAPABILITY",
            "CLASSIFY_PROGRAMMATIC_INTEGER",
            "A programmatic 641-digit integer is outside portable capability, not malformed JSON.",
            {"integer": _source(_integer_recipe(641)), "integer_magnitude_digits": 641},
            code="INPUT_OUTSIDE_DECLARED_CAPABILITY",
            phase="SEMANTIC_EVALUATION",
            input_ref="EXPLICIT_INPUT",
            limit=_limit_fact("INTEGER_DECIMAL_DIGITS", "DIGITS", 640, 641),
            configuration=portable_config,
        )
    )

    for case_id, position, source_role, recipe in (
        (
            "integer.occurrence.governed_641",
            "GOVERNED",
            "AI_CANONICAL_JSON",
            _json_integer_member(641, member=b"governed"),
        ),
        (
            "integer.occurrence.ignored_641",
            "IGNORED_EXTENSION",
            "AI_MANIFEST_JSON",
            _concat(
                _literal(b'{"ignored":'),
                _integer_recipe(641),
                _literal(b',"canonicalization":"' + V1_IDENTIFIER.encode() + b'"}'),
            ),
        ),
        (
            "integer.occurrence.overwritten_641",
            "OVERWRITTEN_DUPLICATE",
            "AI_MANIFEST_JSON",
            _concat(
                _literal(b'{"ignored":'),
                _integer_recipe(641),
                _literal(b',"ignored":0,"canonicalization":"' + V1_IDENTIFIER.encode() + b'"}'),
            ),
        ),
    ):
        cases.append(
            _operational_case(
                case_id,
                "INTEGER_CAPABILITY",
                "CLASSIFY_INTEGER_SOURCE",
                "Every reached integer occurrence is subject to portable capability before field use or collapse.",
                _integer_source(
                    641,
                    source_role=source_role,
                    position=position,
                    recipe=recipe,
                ),
                code="INPUT_OUTSIDE_DECLARED_CAPABILITY",
                phase="CANONICAL_PARSE" if source_role == "AI_CANONICAL_JSON" else "MANIFEST_PARSE",
                input_ref=source_role,
                limit=_limit_fact("INTEGER_DECIMAL_DIGITS", "DIGITS", 640, 641),
                configuration=portable_config,
            )
        )

    for case_id, before in (
        ("integer.dispatch.final_v2_huge_before", True),
        ("integer.dispatch.final_v2_huge_after", False),
    ):
        parts = [_literal(b"{")]
        if before:
            parts.extend(
                [
                    _literal(b'"ignored":'),
                    _integer_recipe(10000),
                    _literal(b',"canonicalization":"' + V2_IDENTIFIER.encode() + b'"'),
                ]
            )
        else:
            parts.extend(
                [
                    _literal(b'"canonicalization":"' + V2_IDENTIFIER.encode() + b'","ignored":'),
                    _integer_recipe(10000),
                ]
            )
        parts.append(_literal(b"}"))
        cases.append(
            _case(
                case_id,
                "INTEGER_CAPABILITY",
                "DISPATCH_MANIFEST",
                "A huge token is skipped without conversion and exact final v2 still selects v2.",
                {"source": _source(_concat(*parts)), "source_role": "AI_MANIFEST_JSON"},
                _checkpoint(
                    "ROUTE_V2",
                    routing_target="v2",
                    subsequent_semantic_reason="MANIFEST_NOT_JSON",
                    v1_integer_guard_consulted=False,
                ),
                portable_config,
            )
        )

    final_v1_recipe = _concat(
        _literal(b'{"ignored":'),
        _integer_recipe(10000),
        _literal(b',"canonicalization":"' + V1_IDENTIFIER.encode() + b'"}'),
    )
    cases.append(
        _operational_case(
            "integer.dispatch.final_v1_huge",
            "INTEGER_CAPABILITY",
            "DISPATCH_MANIFEST",
            "Dispatch reaches v1 before the portable parser refuses the huge token operationally.",
            {
                "routing_target": "v1",
                "source": _source(final_v1_recipe),
                "source_role": "AI_MANIFEST_JSON",
            },
            code="INPUT_OUTSIDE_DECLARED_CAPABILITY",
            phase="MANIFEST_PARSE",
            input_ref="AI_MANIFEST_JSON",
            limit=_limit_fact("INTEGER_DECIMAL_DIGITS", "DIGITS", 640, 10000),
            configuration=portable_config,
        )
    )

    # Timestamp profiles and legacy suffix behavior.
    timestamp_cases = (
        ("timestamp.ascii.valid", "2026-09-05T12:34:56Z", "TIMESTAMP_ACCEPT", None, None),
        ("timestamp.ascii.lexical_zeroes", "0000-00-00T00:00:00Z", "TIMESTAMP_ACCEPT", None, None),
        ("timestamp.final_lf.one", "2026-09-05T12:34:56Z\n", "TIMESTAMP_ACCEPT", None, None),
        ("timestamp.final_lf.two", "2026-09-05T12:34:56Z\n\n", "TIMESTAMP_REJECT", "MANIFEST_BAD_TS_UTC", None),
        ("timestamp.final_lf.embedded", "2026-09-05\n12:34:56Z", "TIMESTAMP_REJECT", "MANIFEST_BAD_TS_UTC", None),
        ("timestamp.final_lf.crlf", "2026-09-05T12:34:56Z\r\n", "TIMESTAMP_REJECT", "MANIFEST_BAD_TS_UTC", None),
        ("timestamp.separator.bad", "2026/09-05T12:34:56Z", "TIMESTAMP_REJECT", "MANIFEST_BAD_TS_UTC", None),
        ("timestamp.ascii_letter.bad", "202X-09-05T12:34:56Z", "TIMESTAMP_REJECT", "MANIFEST_BAD_TS_UTC", None),
    )
    for case_id, value, decision, reason, _unused in timestamp_cases:
        cases.append(
            _case(
                case_id,
                "TIMESTAMP_COMPATIBILITY",
                "VALIDATE_MANIFEST_TIMESTAMP",
                "The portable timestamp profile applies exact structure and final-LF behavior.",
                _timestamp_source(value),
                _checkpoint(decision, semantic_reason=reason),
                portable_config,
            )
        )

    arabic = "١026-09-05T12:34:56Z"
    cases.append(
        _operational_case(
            "timestamp.portable.non_ascii_nd",
            "TIMESTAMP_COMPATIBILITY",
            "VALIDATE_MANIFEST_TIMESTAMP",
            "A non-ASCII Nd digit is outside the portable ASCII profile.",
            _timestamp_source(arabic),
            code="INPUT_OUTSIDE_DECLARED_CAPABILITY",
            phase="MANIFEST_PARSE",
            input_ref="AI_MANIFEST_JSON",
            limit=_limit_fact("TIMESTAMP_DIGIT_PROFILE", "PROFILE", "ASCII", "U+0661"),
            configuration=portable_config,
        )
    )
    cases.append(
        _case(
            "timestamp.ucd13.non_ascii_nd",
            "TIMESTAMP_COMPATIBILITY",
            "VALIDATE_MANIFEST_TIMESTAMP",
            "U+0661 is accepted by the frozen Unicode 13.0.0 Nd profile.",
            _timestamp_source(arabic),
            _checkpoint("TIMESTAMP_ACCEPT", profile_id=UCD["13.0.0"]["profile_id"]),
            _configuration(v1=_v1_named(4300, "13.0.0")),
        )
    )
    for case_id, character, version, decision in (
        ("timestamp.ucd13.outside_14_addition", "𖫀", "13.0.0", "TIMESTAMP_REJECT"),
        ("timestamp.ucd14.accept_14_addition", "𖫀", "14.0.0", "TIMESTAMP_ACCEPT"),
        ("timestamp.ucd14.outside_15_addition", "𞓰", "14.0.0", "TIMESTAMP_REJECT"),
        ("timestamp.ucd15.accept_15_addition", "𞓰", "15.0.0", "TIMESTAMP_ACCEPT"),
    ):
        value = character + "026-09-05T12:34:56Z"
        cases.append(
            _case(
                case_id,
                "TIMESTAMP_COMPATIBILITY",
                "VALIDATE_MANIFEST_TIMESTAMP",
                "Frozen Nd membership changes only with the explicitly selected table.",
                _timestamp_source(value),
                _checkpoint(
                    decision,
                    profile_id=UCD[version]["profile_id"],
                    semantic_reason=None if decision == "TIMESTAMP_ACCEPT" else "MANIFEST_BAD_TS_UTC",
                ),
                _configuration(v1=_v1_named(4300, version)),
            )
        )

    for case_id, event in (
        ("timestamp.profile_data.missing", "FROZEN_PROFILE_FILE_MISSING"),
        ("timestamp.profile_data.digest_mismatch", "FROZEN_PROFILE_DIGEST_MISMATCH"),
    ):
        config = _configuration(v1=_v1_named(4300, "15.0.0"))
        cases.append(
            _operational_case(
                case_id,
                "TIMESTAMP_COMPATIBILITY",
                "SELECT_CAPABILITY",
                "Unavailable or unauthenticated frozen data makes the requested capability unavailable.",
                {"adapter_event": event, "profile": copy.deepcopy(UCD["15.0.0"])},
                code="CAPABILITY_PROFILE_UNAVAILABLE",
                phase="CAPABILITY_SELECTION",
                input_ref=None,
                configuration=config,
            )
        )

    # Deterministic legacy behavior.
    deterministic = [
        (
            "legacy.duplicate.exact_last_wins",
            _literal(b'{"x":1,"x":2}'),
            _checkpoint("LEGACY_ACCEPT", collapsed_member="x", retained_json="2"),
        ),
        (
            "legacy.duplicate.escaped_equivalent_last_wins",
            _literal(br'{"x":1,"\u0078":2}'),
            _checkpoint("LEGACY_ACCEPT", collapsed_member="x", retained_json="2"),
        ),
        (
            "legacy.nonfinite.nan",
            _literal(b"NaN"),
            _checkpoint("LEGACY_ACCEPT", token="NaN", value_class="NONFINITE"),
        ),
        (
            "legacy.nonfinite.infinity",
            _literal(b"Infinity"),
            _checkpoint("LEGACY_ACCEPT", token="Infinity", value_class="NONFINITE"),
        ),
        (
            "legacy.nonfinite.negative_infinity",
            _literal(b"-Infinity"),
            _checkpoint("LEGACY_ACCEPT", token="-Infinity", value_class="NONFINITE"),
        ),
        (
            "legacy.nonfinite.near_miss",
            _literal(b"nan"),
            _checkpoint("LEGACY_SYNTAX_REJECT", token="nan"),
        ),
        (
            "legacy.surrogate.unmatched_high",
            _literal(br'{"ignored":"\ud800"}'),
            _checkpoint("LEGACY_ACCEPT_OPAQUE", retained_utf16_code_units=["D800"]),
        ),
        (
            "legacy.surrogate.unmatched_low",
            _literal(br'{"ignored":"\udc00"}'),
            _checkpoint("LEGACY_ACCEPT_OPAQUE", retained_utf16_code_units=["DC00"]),
        ),
        (
            "legacy.open_member.accepted",
            _literal(b'{"known":1,"future_extension":{"x":true}}'),
            _checkpoint("LEGACY_ACCEPT_OPEN_MEMBER", member="future_extension", semantic_meaning=False),
        ),
        (
            "legacy.trust.empty_signers",
            _literal(b'{"trust_store_format":"aelitium-trust-v1","signers":[]}'),
            _checkpoint("LEGACY_ACCEPT", trust_membership_count=0),
        ),
    ]
    for case_id, recipe, expected in deterministic:
        cases.append(
            _case(
                case_id,
                "DETERMINISTIC_LEGACY",
                "APPLY_LEGACY_RULE",
                "A deterministic released legacy rule is reproducible without a runtime profile.",
                {"source": _source(recipe)},
                expected,
            )
        )

    key_canonical = base64.b64encode(bytes(32)).decode("ascii")
    key_alias = key_canonical[:-2] + "B="
    signature_canonical = base64.b64encode(bytes(64)).decode("ascii")
    signature_alias = signature_canonical[:-3] + "B=="
    for case_id, role, canonical, alias, decoded_length in (
        ("legacy.base64.public_key_pad_bits", "PUBLIC_KEY", key_canonical, key_alias, 32),
        ("legacy.base64.signature_pad_bits", "SIGNATURE", signature_canonical, signature_alias, 64),
    ):
        cases.append(
            _case(
                case_id,
                "DETERMINISTIC_LEGACY",
                "DECODE_LEGACY_BASE64",
                "A standard-alphabet legacy alias with non-zero unused pad bits decodes to the same fixed bytes.",
                {
                    "canonical": canonical,
                    "encoded": alias,
                    "role": role,
                },
                _checkpoint(
                    "LEGACY_ACCEPT",
                    canonical_encoding=canonical,
                    decoded_hex=(bytes(decoded_length)).hex(),
                    decoded_length=decoded_length,
                    encode_after_decode_equality=False,
                ),
            )
        )

    # Resource floors: exact byte recipes at and around each boundary.
    for label, size, decision in (
        ("below", 65_535, "WITHIN_EFFECTIVE_LIMIT"),
        ("at", 65_536, "WITHIN_EFFECTIVE_LIMIT"),
    ):
        cases.append(
            _case(
                f"limit.file_bytes.{label}",
                "OPERATIONAL_LIMIT",
                "MEASURE_SOURCE_LIMIT",
                f"A source {label} the file-byte floor remains within the effective limit.",
                {
                    "source": _source(
                        {"op": "JSON_STRING_OF_SIZE", "byte_length": size, "fill_byte_hex": "61"}
                    ),
                    "source_role": "AI_CANONICAL_JSON",
                },
                _checkpoint(decision, limit="FILE_BYTES", maximum=65_536, observed=size),
            )
        )
    cases.append(
        _operational_case(
            "limit.file_bytes.above",
            "OPERATIONAL_LIMIT",
            "MEASURE_SOURCE_LIMIT",
            "The first byte above the effective file limit is operational.",
            {
                "source": _source(
                    {"op": "JSON_STRING_OF_SIZE", "byte_length": 65_537, "fill_byte_hex": "61"}
                ),
                "source_role": "AI_CANONICAL_JSON",
            },
            code="RESOURCE_LIMIT_EXCEEDED",
            phase="BUNDLE_SNAPSHOT",
            input_ref="AI_CANONICAL_JSON",
            limit=_limit_fact("FILE_BYTES", "BYTES", 65_536, 65_537),
        )
    )

    aggregate_sets = {
        "below": {"AI_CANONICAL_JSON": 65_536, "AI_MANIFEST_JSON": 65_536, "VERIFICATION_KEYS_JSON": 65_536, "TRUST_STORE": 65_535},
        "at": {"AI_CANONICAL_JSON": 65_536, "AI_MANIFEST_JSON": 65_536, "VERIFICATION_KEYS_JSON": 65_536, "TRUST_STORE": 65_536},
        "above": {"AI_CANONICAL_JSON": 65_537, "AI_MANIFEST_JSON": 65_536, "VERIFICATION_KEYS_JSON": 65_536, "TRUST_STORE": 65_536},
    }
    for label in ("below", "at"):
        sizes = aggregate_sets[label]
        observed = sum(sizes.values())
        cases.append(
            _case(
                f"limit.total_snapshot_bytes.{label}",
                "OPERATIONAL_LIMIT",
                "MEASURE_SNAPSHOT_LIMIT",
                f"An aggregate snapshot {label} the floor remains within the effective limit.",
                {"roles": _role_sources(sizes), "total_bytes": observed},
                _checkpoint("WITHIN_EFFECTIVE_LIMIT", limit="TOTAL_SNAPSHOT_BYTES", maximum=262_144, observed=observed),
            )
        )
    aggregate_limits = {**MINIMUM_LIMITS, "max_file_bytes": 131_072}
    aggregate_config = _configuration(limits=aggregate_limits)
    cases.append(
        _operational_case(
            "limit.total_snapshot_bytes.above",
            "OPERATIONAL_LIMIT",
            "MEASURE_SNAPSHOT_LIMIT",
            "Aggregate size can exceed its limit while every role is within a higher file limit.",
            {"roles": _role_sources(aggregate_sets["above"]), "total_bytes": 262_145},
            code="RESOURCE_LIMIT_EXCEEDED",
            phase="BUNDLE_SNAPSHOT",
            input_ref="BUNDLE_DIRECTORY",
            limit=_limit_fact("TOTAL_SNAPSHOT_BYTES", "BYTES", 262_144, 262_145),
            configuration=aggregate_config,
        )
    )

    for label, depth, decision in (
        ("below", 1023, "WITHIN_EFFECTIVE_LIMIT"),
        ("at", 1024, "WITHIN_EFFECTIVE_LIMIT"),
    ):
        cases.append(
            _case(
                f"limit.structural_depth.{label}",
                "OPERATIONAL_LIMIT",
                "MEASURE_TRAVERSAL_LIMIT",
                f"Container depth {depth} is within the effective limit.",
                {"source": _source({"op": "NESTED_ARRAY", "depth": depth, "scalar_hex": "6e756c6c"})},
                _checkpoint(decision, limit="STRUCTURAL_DEPTH", maximum=1024, observed=depth),
            )
        )
    cases.append(
        _operational_case(
            "limit.structural_depth.above",
            "OPERATIONAL_LIMIT",
            "MEASURE_TRAVERSAL_LIMIT",
            "Opening container level 1025 exceeds the effective depth limit.",
            {"source": _source({"op": "NESTED_ARRAY", "depth": 1025, "scalar_hex": "6e756c6c"})},
            code="RESOURCE_LIMIT_EXCEEDED",
            phase="CANONICAL_PARSE",
            input_ref="AI_CANONICAL_JSON",
            limit=_limit_fact("STRUCTURAL_DEPTH", "LEVELS", 1024, 1025),
        )
    )

    occurrence_limits = {
        **MINIMUM_LIMITS,
        "max_file_bytes": 524_288,
        "max_total_snapshot_bytes": 524_288,
    }
    occurrence_config = _configuration(limits=occurrence_limits)
    for label, occurrences, decision in (
        ("below", 65_535, "WITHIN_EFFECTIVE_LIMIT"),
        ("at", 65_536, "WITHIN_EFFECTIVE_LIMIT"),
    ):
        cases.append(
            _case(
                f"limit.value_occurrences.{label}",
                "OPERATIONAL_LIMIT",
                "MEASURE_TRAVERSAL_LIMIT",
                f"Value occurrence count {occurrences} is within the effective limit.",
                {"source": _source({"op": "NULL_ARRAY", "value_occurrences": occurrences})},
                _checkpoint(decision, limit="VALUE_OCCURRENCES", maximum=65_536, observed=occurrences),
                occurrence_config,
            )
        )
    cases.append(
        _operational_case(
            "limit.value_occurrences.above",
            "OPERATIONAL_LIMIT",
            "MEASURE_TRAVERSAL_LIMIT",
            "Value occurrence 65,537 exceeds the effective occurrence limit.",
            {"source": _source({"op": "NULL_ARRAY", "value_occurrences": 65_537})},
            code="RESOURCE_LIMIT_EXCEEDED",
            phase="CANONICAL_PARSE",
            input_ref="AI_CANONICAL_JSON",
            limit=_limit_fact("VALUE_OCCURRENCES", "OCCURRENCES", 65_536, 65_537),
            configuration=occurrence_config,
        )
    )

    for case_id, phase, input_ref in (
        ("resource.exhausted.dispatch", "DISPATCH", "AI_MANIFEST_JSON"),
        ("resource.exhausted.canonical_parse", "CANONICAL_PARSE", "AI_CANONICAL_JSON"),
        ("resource.exhausted.manifest_parse", "MANIFEST_PARSE", "AI_MANIFEST_JSON"),
        ("resource.exhausted.signature_material", "SIGNATURE_MATERIAL", "VERIFICATION_KEYS_JSON"),
    ):
        input_value = {"adapter_event": "FAIL_NEXT_ALLOCATION", "at_phase": phase}
        if phase == "DISPATCH":
            input_value["source"] = _source(
                _literal(b'{"canonicalization":"' + V2_IDENTIFIER.encode() + b'"}')
            )
            input_value["assert_no_v1_fallback"] = True
        cases.append(
            _operational_case(
                case_id,
                "OPERATIONAL_RESOURCE",
                "INJECT_RESOURCE_FAILURE",
                "Injected resource exhaustion never becomes semantic invalidity.",
                input_value,
                code="RESOURCE_EXHAUSTED",
                phase=phase,
                input_ref=input_ref,
            )
        )

    # Direct filesystem and immutable-snapshot behavior.
    regular_source = _source(_literal(b'{"x":1}'))
    cases.append(
        _case(
            "snapshot.regular_file.success",
            "FILESYSTEM_SNAPSHOT",
            "ACQUIRE_SNAPSHOT",
            "An unchanged no-follow regular file is captured into immutable bytes.",
            {
                "filesystem_recipe": [
                    {"op": "CREATE_REGULAR", "role": "AI_CANONICAL_JSON", "source": regular_source},
                    {"op": "ACQUIRE_AND_FREEZE"},
                ]
            },
            _checkpoint("SNAPSHOT_ACQUIRED", captured_sha256=regular_source["sha256"], read_acquisitions=1),
            _configuration(input_mode="DIRECT_FILESYSTEM"),
        )
    )

    for case_id, object_kind, role, input_ref in (
        ("snapshot.reject.symlink", "SYMLINK", "AI_CANONICAL_JSON", "AI_CANONICAL_JSON"),
        ("snapshot.reject.directory", "DIRECTORY", "AI_MANIFEST_JSON", "AI_MANIFEST_JSON"),
        ("snapshot.reject.fifo", "FIFO", "VERIFICATION_KEYS_JSON", "VERIFICATION_KEYS_JSON"),
        ("snapshot.reject.device", "DEVICE", "TRUST_STORE", "TRUST_STORE"),
        ("snapshot.reject.socket", "SOCKET", "AI_CANONICAL_JSON", "AI_CANONICAL_JSON"),
        ("snapshot.reject.bundle_root_symlink", "SYMLINK", "BUNDLE_DIRECTORY", "BUNDLE_DIRECTORY"),
    ):
        cases.append(
            _operational_case(
                case_id,
                "FILESYSTEM_SNAPSHOT",
                "ACQUIRE_SNAPSHOT",
                "A direct input that is a symlink or non-regular role is rejected before reading content.",
                {"filesystem_recipe": [{"object_kind": object_kind, "op": "CREATE_OBJECT", "role": role}]},
                code="INPUT_NOT_REGULAR_FILE",
                phase="TRUST_INPUT" if role == "TRUST_STORE" else "BUNDLE_SNAPSHOT",
                input_ref=input_ref,
                configuration=_configuration(input_mode="DIRECT_FILESYSTEM"),
            )
        )

    for case_id, event, role in (
        ("snapshot.io.permission", "DENY_PERMISSION", "AI_CANONICAL_JSON"),
        ("snapshot.io.open_error", "FAIL_OPEN", "AI_MANIFEST_JSON"),
        ("snapshot.io.read_error", "FAIL_READ", "VERIFICATION_KEYS_JSON"),
    ):
        cases.append(
            _operational_case(
                case_id,
                "FILESYSTEM_SNAPSHOT",
                "ACQUIRE_SNAPSHOT",
                "A metadata/open/read failure is operational input I/O.",
                {"filesystem_recipe": [{"event": event, "op": "INJECT_FAILURE", "role": role}]},
                code="INPUT_IO_ERROR",
                phase="BUNDLE_SNAPSHOT",
                input_ref=role,
                configuration=_configuration(input_mode="DIRECT_FILESYSTEM"),
            )
        )

    for case_id, event, role in (
        ("snapshot.changed.disappearance", "REMOVE_REACHED_ENTRY", "AI_MANIFEST_JSON"),
        ("snapshot.changed.replacement", "REPLACE_REACHED_ENTRY", "AI_CANONICAL_JSON"),
        ("snapshot.changed.premature_eof", "INJECT_PREMATURE_EOF", "AI_CANONICAL_JSON"),
        ("snapshot.changed.truncation", "TRUNCATE_OPEN_FILE", "AI_CANONICAL_JSON"),
        ("snapshot.changed.growth", "APPEND_OPEN_FILE", "AI_MANIFEST_JSON"),
        ("snapshot.changed.in_place_mutation", "MUTATE_OPEN_FILE", "VERIFICATION_KEYS_JSON"),
        ("snapshot.changed.trust_disappearance", "REMOVE_REACHED_ENTRY", "TRUST_STORE"),
    ):
        cases.append(
            _operational_case(
                case_id,
                "FILESYSTEM_SNAPSHOT",
                "ACQUIRE_SNAPSHOT",
                "Observable instability during synchronized acquisition is operational.",
                {
                    "filesystem_recipe": [
                        {"op": "CREATE_REGULAR", "role": role, "source": regular_source},
                        {"op": "WAIT_AT", "point": "SOURCE_OPENED", "role": role},
                        {"event": event, "op": "MUTATE_AT_POINT", "role": role},
                        {"op": "CONTINUE"},
                    ]
                },
                code="INPUT_CHANGED_DURING_SNAPSHOT",
                phase="TRUST_INPUT" if role == "TRUST_STORE" else "BUNDLE_SNAPSHOT",
                input_ref=role,
                configuration=_configuration(input_mode="DIRECT_FILESYSTEM"),
            )
        )

    cases.append(
        _case(
            "snapshot.short_reads.accumulated",
            "FILESYSTEM_SNAPSHOT",
            "ACQUIRE_SNAPSHOT",
            "Short successful reads are accumulated until EOF.",
            {
                "filesystem_recipe": [
                    {"op": "CREATE_REGULAR", "role": "AI_CANONICAL_JSON", "source": regular_source},
                    {"chunk_bytes": 1, "op": "LIMIT_READ_CHUNK"},
                    {"op": "ACQUIRE_AND_FREEZE"},
                ]
            },
            _checkpoint("SNAPSHOT_ACQUIRED", captured_sha256=regular_source["sha256"], read_acquisitions=1),
            _configuration(input_mode="DIRECT_FILESYSTEM"),
        )
    )
    cases.append(
        _case(
            "snapshot.post_freeze_replacement.ignored",
            "FILESYSTEM_SNAPSHOT",
            "ACQUIRE_SNAPSHOT",
            "Replacing a path after freeze cannot change captured semantic bytes.",
            {
                "filesystem_recipe": [
                    {"op": "CREATE_REGULAR", "role": "AI_MANIFEST_JSON", "source": regular_source},
                    {"op": "ACQUIRE_AND_FREEZE"},
                    {"op": "REPLACE_AFTER_FREEZE", "role": "AI_MANIFEST_JSON", "source": _source(_literal(b'{"x":2}'))},
                ]
            },
            _checkpoint("USE_FROZEN_BYTES", captured_sha256=regular_source["sha256"], semantic_phase_rereads=0),
            _configuration(input_mode="DIRECT_FILESYSTEM"),
        )
    )
    cases.append(
        _case(
            "snapshot.immutable_bytes.equivalence",
            "FILESYSTEM_SNAPSHOT",
            "COMPARE_INPUT_MODES",
            "Eligible filesystem capture and caller-provided immutable bytes expose the same role map.",
            {
                "direct_filesystem": {"AI_CANONICAL_JSON": regular_source},
                "immutable_bytes": {"AI_CANONICAL_JSON": regular_source},
            },
            _checkpoint("SNAPSHOT_MAP_EQUAL", role_map_sha256=regular_source["sha256"]),
        )
    )

    for case_id, role, semantic in (
        ("snapshot.stable_absence.canonical", "AI_CANONICAL_JSON", "MISSING_CANONICAL"),
        ("snapshot.stable_absence.manifest", "AI_MANIFEST_JSON", "MISSING_MANIFEST"),
        ("snapshot.stable_absence.keyring", "VERIFICATION_KEYS_JSON", "SIGNATURE_ABSENT"),
        ("snapshot.stable_absence.trust_option", "TRUST_STORE", "TRUST_INPUT_NOT_PROVIDED"),
    ):
        cases.append(
            _case(
                case_id,
                "FILESYSTEM_SNAPSHOT",
                "CLASSIFY_STABLE_ABSENCE",
                "Stable absence retains only its already-authorized semantic meaning.",
                {
                    "filesystem_recipe": [
                        {"op": "OBSERVE_ABSENT", "role": role},
                        {"op": "RECHECK_ABSENT", "role": role},
                    ]
                },
                _checkpoint("SEMANTIC_ABSENCE", semantic_result=semantic),
                _configuration(input_mode="DIRECT_FILESYSTEM"),
            )
        )

    for case_id, code, phase, input_ref, event in (
        ("operation.output_io", "OUTPUT_IO_ERROR", "OUTPUT", None, "FAIL_OUTPUT_WRITE"),
        ("operation.internal_failure", "INTERNAL_OPERATION_ERROR", "SEMANTIC_EVALUATION", None, "INJECT_INTERNAL_DEFECT"),
    ):
        cases.append(
            _operational_case(
                case_id,
                "OPERATIONAL_TRANSPORT",
                "INJECT_OPERATIONAL_FAILURE",
                "A tool/output defect is operational and cannot fabricate a semantic result.",
                {"adapter_event": event},
                code=code,
                phase=phase,
                input_ref=input_ref,
            )
        )

    unsupported_config = _configuration(v1={"capability": "V1_LEGACY_UNSUPPORTED"})
    cases.append(
        _operational_case(
            "capability.v1_unsupported.after_dispatch",
            "OPERATIONAL_TRANSPORT",
            "DISPATCH_MANIFEST",
            "An explicitly unsupported v1 route refuses after dispatch without invalidating evidence.",
            {
                "routing_target": "v1",
                "source": _source(_literal(b'{"canonicalization":"' + V1_IDENTIFIER.encode() + b'"}')),
            },
            code="CAPABILITY_PROFILE_UNAVAILABLE",
            phase="DISPATCH",
            input_ref="AI_MANIFEST_JSON",
            configuration=unsupported_config,
        )
    )

    return cases


def _document(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(cases),
        "contract": CONTRACT,
        "operation_contract": OPERATION_CONTRACT,
        "recipe_contract": "AELITIUM-BYTES-RECIPE-1",
        "status": STATUS,
        "vectors": cases,
    }


def _lexical_metrics(source: bytes) -> tuple[int, int]:
    """Measure container depth/value starts without converting any number."""

    index = 0
    depth = 0
    maximum_depth = 0
    value_occurrences = 0
    root_state = "VALUE"
    stack: list[dict[str, str]] = []

    def expecting_value() -> bool:
        if not stack:
            return root_state == "VALUE"
        frame = stack[-1]
        return frame["state"] in {"VALUE", "VALUE_OR_END"}

    def complete_value() -> None:
        nonlocal root_state
        if stack:
            stack[-1]["state"] = "COMMA_OR_END"
        else:
            root_state = "DONE"

    while index < len(source):
        byte = source[index]
        if byte in b" \t\r\n":
            index += 1
            continue
        if byte == 0x22:
            index += 1
            while index < len(source):
                if source[index] == 0x5C:
                    index += 2
                    continue
                if source[index] == 0x22:
                    index += 1
                    break
                index += 1
            if stack and stack[-1]["kind"] == "OBJECT" and stack[-1]["state"] == "KEY_OR_END":
                stack[-1]["state"] = "COLON"
            elif expecting_value():
                value_occurrences += 1
                complete_value()
            continue
        if byte in (0x7B, 0x5B):
            if expecting_value():
                value_occurrences += 1
            stack.append(
                {
                    "kind": "OBJECT" if byte == 0x7B else "ARRAY",
                    "state": "KEY_OR_END" if byte == 0x7B else "VALUE_OR_END",
                }
            )
            depth += 1
            maximum_depth = max(maximum_depth, depth)
            index += 1
            continue
        if byte in (0x7D, 0x5D):
            if stack:
                stack.pop()
                depth -= 1
            complete_value()
            index += 1
            continue
        if byte == 0x3A:
            if stack and stack[-1]["kind"] == "OBJECT":
                stack[-1]["state"] = "VALUE"
            index += 1
            continue
        if byte == 0x2C:
            if stack:
                stack[-1]["state"] = (
                    "KEY_OR_END" if stack[-1]["kind"] == "OBJECT" else "VALUE_OR_END"
                )
            index += 1
            continue
        end = index + 1
        while end < len(source) and source[end] not in b" \t\r\n,]}":
            end += 1
        if expecting_value():
            value_occurrences += 1
            complete_value()
        index = end
    return maximum_depth, value_occurrences


def _existing_corpus_measurements() -> dict[str, Any]:
    sources: list[tuple[str, bytes]] = []
    for relative in (
        "canonicalization/vectors.json",
        "canonicalization_v2/vectors.json",
    ):
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for vector in document["vectors"]:
            if "source_bytes_hex" in vector:
                sources.append(
                    (
                        f"{relative}:{vector['case_id']}",
                        bytes.fromhex(vector["source_bytes_hex"]),
                    )
                )
    for path in sorted((ROOT / "fixtures").rglob("*.json")):
        sources.append((str(path.relative_to(ROOT)), path.read_bytes()))

    measured = [
        (len(source), *_lexical_metrics(source), label)
        for label, source in sources
    ]
    by_bytes = max(measured, key=lambda item: item[0])
    by_depth = max(measured, key=lambda item: item[1])
    by_values = max(measured, key=lambda item: item[2])

    operation_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    snapshots: list[tuple[int, str]] = []
    for relative in operation_manifest["vector_files"]:
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for vector in document["vectors"]:
            inputs = vector["input"]
            if vector["operation"] == "verify":
                bundles = [inputs["bundle"]]
            elif vector["operation"] == "compare":
                bundles = [inputs["left"], inputs["right"]]
            else:
                raise ValueError(f"unknown result-contract operation: {vector['operation']}")
            options = inputs.get("options", [])
            trust_relative = None
            if "--trust-store" in options:
                trust_relative = options[options.index("--trust-store") + 1]
            for bundle_relative in bundles:
                bundle = ROOT / bundle_relative
                total = sum(
                    (bundle / name).stat().st_size
                    for name in (
                        "ai_canonical.json",
                        "ai_manifest.json",
                        "verification_keys.json",
                    )
                    if (bundle / name).is_file()
                )
                label = f"{relative}:{vector['case_id']}:{bundle_relative}"
                if trust_relative is not None:
                    total += (ROOT / trust_relative).stat().st_size
                    label += f"+{trust_relative}"
                snapshots.append((total, label))
    by_snapshot = max(snapshots, key=lambda item: item[0])
    return {
        "maximum_operation_snapshot_bytes": by_snapshot[0],
        "maximum_operation_snapshot_bytes_ref": by_snapshot[1],
        "maximum_source_bytes": by_bytes[0],
        "maximum_source_bytes_ref": by_bytes[3],
        "maximum_structural_depth": by_depth[1],
        "maximum_structural_depth_ref": by_depth[3],
        "maximum_value_occurrences": by_values[2],
        "maximum_value_occurrences_ref": by_values[3],
        "measured_operation_snapshot_count": len(snapshots),
        "measured_source_count": len(measured),
        "scope": [
            "canonicalization/vectors.json source_bytes_hex",
            "canonicalization_v2/vectors.json source_bytes_hex",
            "fixtures/**/*.json exact bytes",
            "result-contract vector bundle/trust operation snapshots",
        ],
    }


def _manifest(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for case in cases:
        counts[case["category"]] = counts.get(case["category"], 0) + 1
    return {
        "case_count": len(cases),
        "categories": counts,
        "contract": CONTRACT,
        "existing_corpora_unchanged": {
            "canonicalization_v1_cases": 30,
            "canonicalization_v2_cases": 114,
            "result_contract_cases": 44,
        },
        "existing_corpus_measurements": _existing_corpus_measurements(),
        "operational_result_schema": "../../engine/schemas/verifier_tool_result_v1.json",
        "operation_contract": OPERATION_CONTRACT,
        "policy": "../../docs/LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md",
        "recipe_contract": "AELITIUM-BYTES-RECIPE-1",
        "runner": "../run_legacy_v1_operational_policy.py",
        "status": STATUS,
        "unicode_profiles": "unicode/profiles.json",
        "vector_files": ["cases.json"],
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _check_or_write(path: Path, expected: bytes, *, write: bool) -> None:
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        return
    try:
        observed = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT.parent)}: {exc}") from exc
    if observed != expected:
        raise ValueError(f"frozen file differs: {path.relative_to(ROOT.parent)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write frozen corpus files")
    args = parser.parse_args(argv)
    try:
        cases = build_cases()
        _check_or_write(CASES_PATH, _json_bytes(_document(cases)), write=args.write)
        _check_or_write(MANIFEST_PATH, _json_bytes(_manifest(cases)), write=args.write)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"[FAIL] Legacy-v1 operational-policy corpus build: {exc}", file=sys.stderr)
        return 1
    action = "wrote" if args.write else "verified"
    print(f"[PASS] Legacy-v1 operational-policy corpus {action}: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
