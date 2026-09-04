#!/usr/bin/env python3
"""Build the frozen portable-v2 corpus without importing production code.

Every canonical byte string below is an explicit test oracle.  This helper
uses hashlib only to attach corruption checks; it never calls AELITIUM or the
selected RFC 8785 dependency to derive an expected serialization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CORPUS = "aelitium-canonicalization-conformance-v2"
IDENTIFIER = "aelitium_jcs_profile_v2"
V1_IDENTIFIER = "json_sorted_keys_no_whitespace_utf8"
STATUS = "IMPLEMENTATION-ALIGNED-UNRELEASED"

PAYLOAD_PREFIX = b'{"metadata":'
PAYLOAD_SUFFIX = (
    b',"model":"m","output":"o","prompt":"p",'
    b'"schema_version":"ai_output_v1",'
    b'"ts_utc":"2026-01-01T00:00:00Z"}'
)
BASE_CANONICAL = PAYLOAD_PREFIX + b"{}" + PAYLOAD_SUFFIX
BASE_DIGEST = hashlib.sha256(BASE_CANONICAL).hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _expected(
    *,
    decision: str,
    error_category: str | None,
    canonical: bytes | None,
    routing_target: str | None = None,
) -> dict[str, Any]:
    return {
        "canonical_sha256": _sha256(canonical) if canonical is not None else None,
        "canonical_utf8_hex": canonical.hex() if canonical is not None else None,
        "decision": decision,
        "error_category": error_category,
        "routing_target": routing_target,
    }


def _case(
    case_id: str,
    description: str,
    operation: str,
    source_role: str,
    source: bytes,
    expected: dict[str, Any],
    **parameters: Any,
) -> dict[str, Any]:
    result = {
        "case_id": case_id,
        "description": description,
        "operation": operation,
        "source_bytes_hex": source.hex(),
        "source_role": source_role,
        "source_sha256": _sha256(source),
        "expected": expected,
    }
    if parameters:
        result["parameters"] = parameters
    return result


def _accept(
    case_id: str,
    description: str,
    canonical: bytes,
    *,
    source: bytes | None = None,
    operation: str = "canonicalize",
    source_role: str = "generic_value",
    **parameters: Any,
) -> dict[str, Any]:
    return _case(
        case_id,
        description,
        operation,
        source_role,
        canonical if source is None else source,
        _expected(decision="ACCEPT", error_category=None, canonical=canonical),
        **parameters,
    )


def _reject(
    case_id: str,
    description: str,
    source: bytes,
    error_category: str,
    *,
    operation: str = "canonicalize",
    source_role: str = "generic_value",
    canonical: bytes | None = None,
    routing_target: str | None = None,
    **parameters: Any,
) -> dict[str, Any]:
    return _case(
        case_id,
        description,
        operation,
        source_role,
        source,
        _expected(
            decision="REJECT",
            error_category=error_category,
            canonical=canonical,
            routing_target=routing_target,
        ),
        **parameters,
    )


def _payload(metadata: bytes) -> bytes:
    return PAYLOAD_PREFIX + metadata + PAYLOAD_SUFFIX


def _manifest(
    selector: bytes,
    *,
    before_selector: bytes = b"",
    digest: str = BASE_DIGEST,
) -> bytes:
    return (
        b'{"schema":"ai_pack_manifest_v1",'
        b'"ts_utc":"2026-01-01T00:00:00Z",'
        b'"input_schema":"ai_output_v1",'
        + before_selector
        + b'"canonicalization":'
        + selector
        + b',"ai_hash_sha256":"'
        + digest.encode("ascii")
        + b'"}'
    )


def _dispatch(
    case_id: str,
    description: str,
    source: bytes,
    *,
    routing_target: str,
    decision: str,
    reason: str,
    int_digit_limit: int | None = None,
    recursion_limits: tuple[int, ...] | None = None,
    nesting_depth: int | None = None,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {"verifier_reason": reason}
    if int_digit_limit is not None:
        parameters["int_digit_limit"] = int_digit_limit
    if recursion_limits is not None:
        parameters["recursion_limits"] = list(recursion_limits)
    if nesting_depth is not None:
        parameters["nesting_depth"] = nesting_depth
    return _case(
        case_id,
        description,
        "dispatch_verify",
        "manifest",
        source,
        _expected(
            decision=decision,
            error_category=None if decision == "ACCEPT" else reason,
            canonical=None,
            routing_target=routing_target,
        ),
        **parameters,
    )


def build_vectors() -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = [
        _accept("v2.value.null", "Null literal.", b"null"),
        _accept("v2.value.true", "True literal.", b"true"),
        _accept("v2.value.false", "False literal.", b"false"),
        _accept("v2.value.string", "Simple string.", b'"text"'),
        _accept("v2.value.array", "Array order is preserved.", b"[3,2,1]"),
        _accept(
            "v2.value.object",
            "Object names are recursively sorted.",
            b'{"a":2,"b":1}',
            source=b'{"b":1,"a":2}',
        ),
        _accept(
            "v2.unicode.utf8",
            "Multi-byte UTF-8 scalars remain literal.",
            '"café 你好"'.encode("utf-8"),
        ),
        _accept(
            "v2.unicode.non_bmp",
            "A valid non-BMP scalar remains literal UTF-8.",
            '"😀"'.encode("utf-8"),
            source=br'"\ud83d\ude00"',
        ),
        _accept(
            "v2.unicode.nfc",
            "NFC spelling is retained without normalization.",
            '"é"'.encode("utf-8"),
        ),
        _accept(
            "v2.unicode.nfd",
            "NFD spelling is distinct and retained.",
            '"é"'.encode("utf-8"),
        ),
        _accept(
            "v2.unicode.nfc_nfd_names",
            "NFC and NFD names coexist and sort without normalization.",
            '{"é":1,"é":2}'.encode("utf-8"),
            source='{"é":2,"é":1}'.encode("utf-8"),
        ),
        _accept(
            "v2.object.utf16_order",
            "JCS orders a non-BMP name before U+E000 by UTF-16 units.",
            '{"😀":1,"\ue000":2}'.encode("utf-8"),
            source='{"\ue000":2,"😀":1}'.encode("utf-8"),
        ),
        _accept(
            "v2.object.prefix_order",
            "A shorter UTF-16 prefix sorts first.",
            b'{"a":2,"aa":1}',
            source=b'{"aa":1,"a":2}',
        ),
        _accept(
            "v2.string.escaping",
            "JCS uses short controls, lowercase hex, literal solidus, quote, and reverse solidus.",
            br'"\u0000\b\t\n\f\r\u001f\"\\/"',
        ),
        _accept(
            "v2.string.u2028_u2029",
            "U+2028 and U+2029 remain literal.",
            '"\u2028\u2029"'.encode("utf-8"),
            source=br'"\u2028\u2029"',
        ),
        _reject(
            "v2.source.leading_bom",
            "A leading UTF-8 BOM is prohibited.",
            b"\xef\xbb\xbfnull",
            "LEADING_BOM",
        ),
        _reject(
            "v2.source.invalid_continuation",
            "An invalid UTF-8 continuation byte is rejected.",
            b'"\xc3("',
            "INVALID_UTF8",
        ),
        _reject(
            "v2.source.overlong_utf8",
            "An overlong UTF-8 sequence is rejected.",
            b'"\xc0\x80"',
            "INVALID_UTF8",
        ),
        _reject(
            "v2.source.truncated_utf8",
            "A truncated UTF-8 sequence is rejected.",
            b'"\xf0\x9f\x98',
            "INVALID_UTF8",
        ),
        _reject(
            "v2.source.utf8_surrogate",
            "A raw UTF-8 encoding of a surrogate is rejected.",
            b'"\xed\xa0\x80"',
            "INVALID_UTF8",
        ),
        _reject(
            "v2.object.duplicate",
            "Exact duplicate names reject before map collapse.",
            b'{"a":1,"a":2}',
            "DUPLICATE_OBJECT_NAME",
        ),
        _reject(
            "v2.object.escaped_duplicate",
            "Names equal after escape processing are duplicates.",
            br'{"a":1,"\u0061":2}',
            "DUPLICATE_OBJECT_NAME",
        ),
        _reject(
            "v2.object.nested_duplicate",
            "Nested object duplicates are rejected.",
            b'{"outer":{"a":1,"a":2}}',
            "DUPLICATE_OBJECT_NAME",
        ),
        _reject(
            "v2.object.array_nested_duplicate",
            "Duplicates inside an object nested in an array are rejected.",
            b'[{"a":1,"a":2}]',
            "DUPLICATE_OBJECT_NAME",
        ),
        _accept(
            "v2.unicode.surrogate_pair",
            "A valid surrogate-pair escape becomes one scalar.",
            '"𐀀"'.encode("utf-8"),
            source=br'"\ud800\udc00"',
        ),
        _reject(
            "v2.unicode.lone_high_surrogate",
            "A lone high surrogate escape is rejected.",
            br'"\ud800"',
            "INVALID_UNICODE_SCALAR",
        ),
        _reject(
            "v2.unicode.lone_low_surrogate",
            "A lone low surrogate escape is rejected.",
            br'"\udc00"',
            "INVALID_UNICODE_SCALAR",
        ),
        _reject(
            "v2.unicode.reversed_surrogates",
            "A reversed surrogate sequence is rejected.",
            br'"\udc00\ud800"',
            "INVALID_UNICODE_SCALAR",
        ),
        _reject(
            "v2.unicode.noncharacter_fdd0",
            "U+FDD0 is excluded.",
            '"\ufdd0"'.encode("utf-8"),
            "UNICODE_NONCHARACTER",
        ),
        _reject(
            "v2.unicode.noncharacter_fdef",
            "U+FDEF is excluded.",
            '"\ufdef"'.encode("utf-8"),
            "UNICODE_NONCHARACTER",
        ),
        _reject(
            "v2.unicode.noncharacter_fffe",
            "U+FFFE is excluded.",
            br'"\ufffe"',
            "UNICODE_NONCHARACTER",
        ),
        _reject(
            "v2.unicode.noncharacter_ffff",
            "U+FFFF is excluded.",
            br'"\uffff"',
            "UNICODE_NONCHARACTER",
        ),
        _reject(
            "v2.unicode.noncharacter_plane_1",
            "A plane-ending noncharacter above the BMP is excluded.",
            br'"\ud83f\udffe"',
            "UNICODE_NONCHARACTER",
        ),
        _accept(
            "v2.number.max_safe",
            "Positive 2^53 - 1 is accepted.",
            b"9007199254740991",
        ),
        _accept(
            "v2.number.min_safe",
            "Negative 2^53 - 1 is accepted.",
            b"-9007199254740991",
        ),
        _reject(
            "v2.number.positive_2_pow_53",
            "Positive 2^53 integer form is rejected before narrowing.",
            b"9007199254740992",
            "NUMBER_OUT_OF_RANGE",
        ),
        _reject(
            "v2.number.negative_2_pow_53",
            "Negative 2^53 integer form is rejected before narrowing.",
            b"-9007199254740992",
            "NUMBER_OUT_OF_RANGE",
        ),
        _reject(
            "v2.number.extreme_integer",
            "An arbitrary-precision integer token is not coerced.",
            b"9" * 1000,
            "NUMBER_OUT_OF_RANGE",
        ),
        _accept(
            "v2.number.fractions",
            "Current fractional parameter values remain native numbers.",
            b"[0.2,0.75,0.9]",
        ),
        _accept(
            "v2.number.rfc_rounding",
            "The RFC sample rounds to its shortest binary64 spelling.",
            b"333333333.3333333",
            source=b"333333333.33333329",
        ),
        _accept(
            "v2.number.rounding_alias",
            "A longer decimal alias rounds to the same binary64 value.",
            b"0.30000000000000004",
            source=b"0.30000000000000005",
        ),
        _accept(
            "v2.number.scientific",
            "Scientific output uses lowercase e without exponent padding.",
            b"1e-7",
            source=b"1E-07",
        ),
        _accept(
            "v2.number.fixed_threshold",
            "The JCS fixed-notation threshold includes 1e-6.",
            b"0.000001",
            source=b"1e-6",
        ),
        _accept(
            "v2.number.exponent_alias",
            "A positive source exponent serializes to the unique in-range fixed form.",
            b"1000",
            source=b"1E+3",
        ),
        _accept(
            "v2.number.negative_zero_float",
            "Binary64 negative zero serializes as zero.",
            b"0",
            source=b"-0.0",
        ),
        _accept(
            "v2.number.negative_zero_integer",
            "Integer-form negative zero serializes as zero.",
            b"0",
            source=b"-0",
        ),
        _reject(
            "v2.number.nan",
            "NaN is not RFC 8259 JSON.",
            b"NaN",
            "NON_JSON_NUMBER",
        ),
        _reject(
            "v2.number.infinity",
            "Infinity is not RFC 8259 JSON.",
            b"Infinity",
            "NON_JSON_NUMBER",
        ),
        _reject(
            "v2.number.negative_infinity",
            "Negative infinity is not RFC 8259 JSON.",
            b"-Infinity",
            "NON_JSON_NUMBER",
        ),
        _reject(
            "v2.number.decimal_overflow",
            "Decimal overflow to infinity is rejected.",
            b"1e4000",
            "NUMBER_NOT_FINITE",
        ),
        _accept(
            "v2.number.positive_underflow",
            "Correctly rounded positive underflow emits zero.",
            b"0",
            source=b"1e-4000",
        ),
        _accept(
            "v2.number.negative_underflow",
            "Correctly rounded negative underflow emits unsigned zero.",
            b"0",
            source=b"-1e-4000",
        ),
        _accept(
            "v2.number.minimum_subnormal",
            "The smallest positive binary64 value uses the RFC spelling.",
            b"5e-324",
            source=b"4.9406564584124654e-324",
        ),
        _accept(
            "v2.number.round_to_even",
            "The RFC round-to-even sample uses the ECMAScript output.",
            b"1424953923781206.2",
            source=b"1424953923781206.25",
        ),
        _reject(
            "v2.number.rounded_out_of_range",
            "A fractional token whose binary64 result is 2^53 is rejected.",
            b"9007199254740991.9",
            "NUMBER_OUT_OF_RANGE",
        ),
        _accept(
            "v2.source.whitespace",
            "Legal source whitespace is removed by canonicalization.",
            b'{"a":1,"b":2}',
            source=b' \n { "b" : 2, "a" : 1 } \t',
        ),
        _reject(
            "v2.source.multiple_values",
            "Exactly one top-level value is required.",
            b"null true",
            "INVALID_JSON",
        ),
        _reject(
            "v2.source.trailing_comma",
            "Trailing commas are not RFC 8259 syntax.",
            b'{"a":1,}',
            "INVALID_JSON",
        ),
        _reject(
            "v2.source.comment",
            "Comments are not RFC 8259 syntax.",
            b'{"a":1/*x*/}',
            "INVALID_JSON",
        ),
    ]

    # Stored ai_canonical.json envelope and mismatch cases.
    number_canonical = _payload(b'{"n":1}')
    utf16_canonical = _payload('{"😀":1,"\ue000":2}'.encode("utf-8"))
    vectors.extend(
        [
            _accept(
                "v2.storage.c",
                "Stored canonical bytes may be exactly C.",
                BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _accept(
                "v2.storage.c_lf",
                "Stored canonical bytes may be C followed by one LF.",
                BASE_CANONICAL,
                source=BASE_CANONICAL + b"\n",
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.crlf",
                "CRLF is outside the storage envelope.",
                BASE_CANONICAL + b"\r\n",
                "CANONICAL_BYTES_MISMATCH",
                canonical=BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.multiple_lf",
                "More than one terminal LF is rejected.",
                BASE_CANONICAL + b"\n\n",
                "CANONICAL_BYTES_MISMATCH",
                canonical=BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.whitespace",
                "Alternate insignificant whitespace is not canonical storage.",
                BASE_CANONICAL.replace(b'{"metadata":{}', b'{ "metadata" : {}'),
                "CANONICAL_BYTES_MISMATCH",
                canonical=BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.member_order",
                "Alternate member order is not canonical storage.",
                (
                    b'{"model":"m","metadata":{},"output":"o","prompt":"p",'
                    b'"schema_version":"ai_output_v1",'
                    b'"ts_utc":"2026-01-01T00:00:00Z"}'
                ),
                "CANONICAL_BYTES_MISMATCH",
                canonical=BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.escape_spelling",
                "An unnecessary Unicode escape is not canonical storage.",
                BASE_CANONICAL.replace(b'"prompt":"p"', br'"prompt":"\u0070"'),
                "CANONICAL_BYTES_MISMATCH",
                canonical=BASE_CANONICAL,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.number_spelling",
                "An alternate binary64 spelling is not canonical storage.",
                _payload(b'{"n":1.0}'),
                "CANONICAL_BYTES_MISMATCH",
                canonical=number_canonical,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.v1_key_order",
                "V1 scalar order is not accepted where JCS UTF-16 order differs.",
                _payload('{"\ue000":2,"😀":1}'.encode("utf-8")),
                "CANONICAL_BYTES_MISMATCH",
                canonical=utf16_canonical,
                operation="storage_verify",
                source_role="canonical_payload",
            ),
            _reject(
                "v2.storage.duplicate",
                "A duplicate in stored canonical data is profile-invalid JSON.",
                _payload(b'{"a":1,"a":2}'),
                "CANONICAL_NOT_JSON",
                operation="storage_verify",
                source_role="canonical_payload",
            ),
        ]
    )

    # Exact canonical inputs for every governed hash construction.
    request = b'{"messages":[{"content":"p","role":"user"}],"model":"m"}'
    response = b'{"content":"o","model":"m"}'
    request_hash = _sha256(request).encode("ascii")
    response_hash = _sha256(response).encode("ascii")
    binding = (
        b'{"request_hash":"'
        + request_hash
        + b'","response_hash":"'
        + response_hash
        + b'"}'
    )
    invocation = (
        b'{"format":"aelitium-invocation-v1","mode":"sync_non_streaming",'
        b'"request":'
        + request
        + b',"surface":"openai.chat.completions"}'
    )
    invocation_hash = _sha256(invocation).encode("ascii")
    invocation_binding = (
        b'{"format":"aelitium-invocation-binding-v1","invocation_hash":"'
        + invocation_hash
        + b'","response_hash":"'
        + response_hash
        + b'"}'
    )
    for case_id, description, material, construction in (
        ("v2.hash.request", "Frozen byte vector for request_hash.", request, "request_hash"),
        ("v2.hash.response", "Frozen byte vector for response_hash.", response, "response_hash"),
        ("v2.hash.binding", "Frozen byte vector for binding_hash.", binding, "binding_hash"),
        (
            "v2.hash.invocation_identity",
            "Frozen byte vector for invocation_identity.hash_sha256.",
            invocation,
            "invocation_identity.hash_sha256",
        ),
        (
            "v2.hash.invocation_binding",
            "Frozen byte vector for invocation_binding.hash_sha256.",
            invocation_binding,
            "invocation_binding.hash_sha256",
        ),
    ):
        vectors.append(
            _accept(
                case_id,
                description,
                material,
                operation="hash_material",
                source_role="hash_material",
                construction=construction,
            )
        )

    v1 = b'"' + V1_IDENTIFIER.encode("ascii") + b'"'
    v2 = b'"' + IDENTIFIER.encode("ascii") + b'"'
    vectors.extend(
        [
            _dispatch(
                "v2.dispatch.v1",
                "An exact final v1 selector enters the frozen v1 path.",
                _manifest(v1),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.v2",
                "An exact final v2 selector enters the strict v2 path.",
                _manifest(v2),
                routing_target="v2",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.escaped_name_value",
                "Equivalent selector name and value escapes select v2.",
                _manifest(
                    br'"aelitium_jcs_profile_\u00762"'
                ).replace(b'"canonicalization"', br'"\u0063anonicalization"'),
                routing_target="v2",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.legacy_escaped_name_value",
                "Legacy escape processing in the selector name and value still selects v1.",
                _manifest(
                    br'"json_sorted_keys_no_whitespace_utf\u0038"'
                ).replace(b'"canonicalization"', br'"\u0063anonicalization"'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.final_v1_wins",
                "The final duplicate selector chooses v1 and retains last-name-wins.",
                _manifest(
                    v1,
                    before_selector=b'"canonicalization":' + v2 + b',',
                ),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.final_v2_rejects_duplicate",
                "The final duplicate selector chooses v2, whose fresh parse rejects both occurrences.",
                _manifest(
                    v2,
                    before_selector=b'"canonicalization":' + v1 + b',',
                ),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.dispatch.nested_selector_ignored",
                "A nested selector cannot select v2.",
                (
                    b'{"schema":"ai_pack_manifest_v1",'
                    b'"ts_utc":"2026-01-01T00:00:00Z",'
                    b'"input_schema":"ai_output_v1",'
                    b'"extension":{"canonicalization":'
                    + v2
                    + b'},"ai_hash_sha256":"'
                    + BASE_DIGEST.encode("ascii")
                    + b'"}'
                ),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_MISSING_FIELD",
            ),
            _dispatch(
                "v2.dispatch.missing_selector",
                "A missing selector uses legacy required-field precedence.",
                _manifest(v1).replace(b',"canonicalization":' + v1, b""),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_MISSING_FIELD",
            ),
            _dispatch(
                "v2.dispatch.unknown_selector",
                "An unknown selector reaches the legacy identifier check.",
                _manifest(b'"unknown"'),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_BAD_CANONICALIZATION",
            ),
            _dispatch(
                "v2.dispatch.non_string_selector",
                "A non-string selector reaches the legacy identifier check.",
                _manifest(b"2"),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_BAD_CANONICALIZATION",
            ),
            _dispatch(
                "v2.dispatch.malformed_suffix",
                "A partial v2 selector before malformed trailing data cannot dispatch.",
                _manifest(v2) + b" trailing",
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.dispatch.non_object",
                "A non-object root retains legacy MANIFEST_NOT_OBJECT.",
                b"[]",
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_NOT_OBJECT",
            ),
            _dispatch(
                "v2.dispatch.unknown_after_missing_schema",
                "Missing-field precedence remains ahead of an unknown selector.",
                _manifest(b'"unknown"').replace(
                    b'"schema":"ai_pack_manifest_v1",', b""
                ),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_MISSING_FIELD",
            ),
            _dispatch(
                "v2.dispatch.unknown_after_bad_schema",
                "Bad-schema precedence remains ahead of an unknown selector.",
                _manifest(b'"unknown"').replace(
                    b'"schema":"ai_pack_manifest_v1"', b'"schema":"bad"'
                ),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_BAD_SCHEMA",
            ),
            _dispatch(
                "v2.dispatch.legacy_nan",
                "NaN before a final v1 selector reaches unchanged v1 parsing.",
                _manifest(v1, before_selector=b'"extension":NaN,'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.legacy_infinity",
                "Infinity before a final v1 selector reaches unchanged v1 parsing.",
                _manifest(v1, before_selector=b'"extension":Infinity,'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.legacy_negative_infinity",
                "Negative infinity before a final v1 selector reaches unchanged v1 parsing.",
                _manifest(v1, before_selector=b'"extension":-Infinity,'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.legacy_surrogate",
                "An ignored unpaired surrogate reaches unchanged v1 parsing.",
                _manifest(v1, before_selector=br'"extension":"\ud800",'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.legacy_unrelated_duplicate",
                "An unrelated duplicate retains v1 last-name-wins behavior.",
                _manifest(v1, before_selector=b'"extension":1,"extension":2,'),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.dispatch.v2_rejects_legacy_forms",
                "The same legacy forms with a final v2 selector fail the strict fresh parse.",
                _manifest(
                    v2,
                    before_selector=(
                        b'"nan":NaN,"inf":Infinity,"ninf":-Infinity,'
                        br'"surrogate":"\ud800","dup":1,"dup":2,'
                    ),
                ),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.manifest.unknown_valid_extension",
                "A profile-valid unknown extension is ignored under v2.",
                _manifest(v2, before_selector=b'"extension":{"a":[1,true,null]},'),
                routing_target="v2",
                decision="ACCEPT",
                reason="OK",
            ),
            _dispatch(
                "v2.manifest.unknown_invalid_unicode",
                "Invalid Unicode in an ignored extension rejects the v2 manifest.",
                _manifest(v2, before_selector=br'"extension":"\ud800",'),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.manifest.unknown_noncharacter",
                "A noncharacter in an ignored extension rejects the v2 manifest.",
                _manifest(v2, before_selector=br'"extension":"\ufdd0",'),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.manifest.unknown_out_of_range_number",
                "An out-of-range number in an ignored extension rejects the v2 manifest.",
                _manifest(v2, before_selector=b'"extension":9007199254740992,'),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.manifest.nested_duplicate",
                "A nested duplicate in an ignored extension rejects the v2 manifest.",
                _manifest(v2, before_selector=b'"extension":{"a":1,"a":2},'),
                routing_target="v2",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
            _dispatch(
                "v2.manifest.bom_no_partial_dispatch",
                "A BOM prevents partial v2 dispatch and legacy parsing reports malformed JSON.",
                b"\xef\xbb\xbf" + _manifest(v2),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
            ),
        ]
    )

    # Iterative-routing regression vectors.  Depth 520 exceeded the original
    # recursive scanner at recursion_limit=500 and sat across its observed
    # boundary at recursion_limit=1000, while the selected parsers accepted
    # these valid manifests.
    deep_array_520 = b"[" * 520 + b"0" + b"]" * 520
    deep_array_260 = b"[" * 260 + b"0" + b"]" * 260
    deep_object_520 = b'{"x":' * 520 + b"0" + b"}" * 520
    malformed_array_520 = b"[" * 520 + b"0" + b"]" * 519
    malformed_object_520 = b'{"x":' * 520 + b"0" + b"}" * 519
    vectors.extend(
        [
            _dispatch(
                "v2.dispatch.deep_array_before_v2",
                "A deeply nested array before the final v2 selector routes independently of Python recursion limits.",
                _manifest(v2, before_selector=b'"extension":' + deep_array_520 + b","),
                routing_target="v2",
                decision="ACCEPT",
                reason="OK",
                recursion_limits=(500, 1000),
                nesting_depth=520,
            ),
            _dispatch(
                "v2.dispatch.deep_object_after_v2",
                "A deeply nested object after the final v2 selector does not alter v2 routing.",
                _manifest(v2).replace(
                    b',"ai_hash_sha256"',
                    b',"extension":' + deep_object_520 + b',"ai_hash_sha256"',
                ),
                routing_target="v2",
                decision="ACCEPT",
                reason="OK",
                recursion_limits=(500, 1000),
                nesting_depth=520,
            ),
            _dispatch(
                "v2.dispatch.deep_array_before_v1",
                "A deeply nested array before the final v1 selector still enters the legacy parser.",
                _manifest(v1, before_selector=b'"extension":' + deep_array_260 + b","),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
                recursion_limits=(500, 1000),
                nesting_depth=260,
            ),
            _dispatch(
                "v2.dispatch.deep_object_after_v1",
                "A deeply nested object after the final v1 selector still enters the legacy parser.",
                _manifest(v1).replace(
                    b',"ai_hash_sha256"',
                    b',"extension":' + deep_object_520 + b',"ai_hash_sha256"',
                ),
                routing_target="v1",
                decision="ACCEPT",
                reason="OK",
                recursion_limits=(1000,),
                nesting_depth=520,
            ),
            _dispatch(
                "v2.dispatch.deep_malformed_array_before_selector",
                "A malformed deeply nested array cannot partially dispatch on the later v2 text.",
                _manifest(
                    v2,
                    before_selector=b'"extension":' + malformed_array_520 + b",",
                ),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
                recursion_limits=(500, 1000),
                nesting_depth=520,
            ),
            _dispatch(
                "v2.dispatch.deep_malformed_object_after_selector",
                "A malformed deeply nested object after a v2 selector causes complete-scan legacy error resolution.",
                _manifest(v2).replace(
                    b',"ai_hash_sha256"',
                    b',"extension":'
                    + malformed_object_520
                    + b',"ai_hash_sha256"',
                ),
                routing_target="legacy_error_resolution",
                decision="REJECT",
                reason="MANIFEST_NOT_JSON",
                recursion_limits=(500, 1000),
                nesting_depth=520,
            ),
        ]
    )

    # CPython legacy integer-limit isolation.  Each number occurs before the
    # final selector and is retained lexically by the scanner.
    for label, digits, limit, decision, reason in (
        ("640_at_640", 640, 640, "ACCEPT", "OK"),
        ("641_at_640", 641, 640, "REJECT", "MANIFEST_NOT_JSON"),
        ("4300_at_4300", 4300, 4300, "ACCEPT", "OK"),
        ("4301_at_4300", 4301, 4300, "REJECT", "MANIFEST_NOT_JSON"),
        ("10000_disabled", 10000, 0, "ACCEPT", "OK"),
    ):
        vectors.append(
            _dispatch(
                f"v2.dispatch.integer_{label}",
                f"A {digits}-digit legacy extension is routed without scanner conversion.",
                _manifest(v1, before_selector=b'"extension":' + b"9" * digits + b","),
                routing_target="v1",
                decision=decision,
                reason=reason,
                int_digit_limit=limit,
            )
        )
    vectors.append(
        _dispatch(
            "v2.dispatch.integer_10000_final_v2",
            "A 10,000-digit token with final v2 is rejected by the strict profile, even with the legacy limit disabled.",
            _manifest(v2, before_selector=b'"extension":' + b"9" * 10000 + b","),
            routing_target="v2",
            decision="REJECT",
            reason="MANIFEST_NOT_JSON",
            int_digit_limit=0,
        )
    )

    vectors.extend(
        [
            _case(
                "v2.comparison.identifier_mismatch",
                "Verified v1 and v2 bundles have no current comparison basis.",
                "comparison",
                "canonical_payload",
                BASE_CANONICAL,
                _expected(
                    decision="NOT_COMPARABLE",
                    error_category="CANONICALIZATION_IDENTIFIER_MISMATCH",
                    canonical=BASE_CANONICAL,
                    routing_target=None,
                ),
                comparison_basis="NONE",
                response_relationship=None,
            ),
            _case(
                "v2.compatibility.v1_shared_domain_artifact",
                "A frozen v1 artifact retains its exact payload digest and result.",
                "v1_artifact",
                "canonical_payload",
                BASE_CANONICAL,
                _expected(
                    decision="ACCEPT",
                    error_category=None,
                    canonical=BASE_CANONICAL,
                    routing_target="v1",
                ),
                verifier_reason="OK",
            ),
        ]
    )

    return vectors


def build_files() -> dict[Path, bytes]:
    vectors = build_vectors()
    vector_document = {
        "canonicalization_identifier": IDENTIFIER,
        "case_count": len(vectors),
        "corpus": CORPUS,
        "dependency_oracle": {
            "license": "Apache-2.0",
            "name": "rfc8785",
            "version": "0.1.4",
        },
        "status": STATUS,
        "vectors": vectors,
    }
    manifest = {
        "canonicalization_identifier": IDENTIFIER,
        "case_count": len(vectors),
        "corpus": CORPUS,
        "existing_corpora_unchanged": {
            "canonicalization_v1_cases": 30,
            "result_contract_cases": 44,
        },
        "runner": "../run_canonicalization_v2.py",
        "status": STATUS,
        "vector_files": ["vectors.json"],
    }
    return {
        Path("canonicalization_v2/manifest.json"): (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        Path("canonicalization_v2/vectors.json"): (
            json.dumps(vector_document, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args()

    mismatches: list[str] = []
    files = build_files()
    for relative, expected in files.items():
        path = ROOT / relative
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
        elif not path.exists() or path.read_bytes() != expected:
            mismatches.append(str(relative))
    if mismatches:
        for mismatch in mismatches:
            print(f"MISMATCH {mismatch}")
        return 1
    print(
        "CANONICALIZATION_V2_VECTORS="
        f"{'WRITTEN' if args.write else 'MATCH'} files={len(files)} "
        f"cases={len(build_vectors())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
