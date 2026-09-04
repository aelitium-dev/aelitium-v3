#!/usr/bin/env python3
"""Build frozen cross-language canonicalization vectors without engine imports.

The byte recipes in this file are deliberately explicit. This maintenance
helper does not call AELITIUM's parser or canonicalizer. The conformance runner
reads the committed JSON output and never invokes this builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CORPUS = "aelitium-canonicalization-conformance-v1"
IDENTIFIER = "json_sorted_keys_no_whitespace_utf8"
STATUS = "IMPLEMENTATION-ALIGNED"

PAYLOAD_PREFIX = b'{"metadata":'
PAYLOAD_SUFFIX = (
    b',"model":"m","output":"o","prompt":"p",'
    b'"schema_version":"ai_output_v1",'
    b'"ts_utc":"2026-01-01T00:00:00Z"}'
)


def _payload(metadata: bytes) -> bytes:
    return PAYLOAD_PREFIX + metadata + PAYLOAD_SUFFIX


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _accept(
    case_id: str,
    description: str,
    canonical: bytes,
    *,
    source: bytes | None = None,
    domain: str = "CROSS_LANGUAGE_SAFE",
) -> dict[str, Any]:
    source_bytes = canonical if source is None else source
    return {
        "case_id": case_id,
        "description": description,
        "source_bytes_hex": source_bytes.hex(),
        "source_sha256": _sha256(source_bytes),
        "expected": {
            "decision": "ACCEPT",
            "reason": "OK",
            "canonical_utf8_hex": canonical.hex(),
            "sha256": _sha256(canonical),
            "domain": domain,
        },
    }


def _reject(
    case_id: str,
    description: str,
    source: bytes,
    reason: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "description": description,
        "source_bytes_hex": source.hex(),
        "source_sha256": _sha256(source),
        "expected": {
            "decision": "REJECT",
            "reason": reason,
            "canonical_utf8_hex": None,
            "sha256": None,
            "domain": "REJECTED",
        },
    }


def build_vectors() -> list[dict[str, Any]]:
    empty = _payload(b"{}")
    non_ascii = _payload('{"text":"café 你好"}'.encode("utf-8"))
    non_bmp = _payload('{"emoji":"😀"}'.encode("utf-8"))
    unicode_order = _payload(
        '{"a":1,"é":2,"é":3,"\ue000":4,"😀":5}'.encode("utf-8")
    )
    controls = _payload(br'{"s":"\u0000\b\t\n\f\r\u001f"}')
    nested = _payload(
        b'{"items":[true,false,null,{"a":1,"b":2}],'
        b'"outer":{"a":[3,2,1],"z":"last"}}'
    )
    digits_640 = b"9" * 640
    integer_640 = _payload(
        b'{"negative":-' + digits_640 + b',"positive":' + digits_640 + b"}"
    )

    vectors = [
        _accept(
            "canonicalization.ascii_baseline_no_lf",
            "Compact ASCII payload without a storage newline.",
            _payload(b'{"a":"x","bool":true,"none":null}'),
        ),
        _reject(
            "canonicalization.multiple_terminal_lf",
            "Two terminal LF bytes are outside the storage allowance.",
            empty + b"\n\n",
            "CANONICAL_BYTES_MISMATCH",
        ),
        _accept(
            "canonicalization.non_ascii_utf8_single_lf",
            "Literal non-ASCII scalars use UTF-8 and one storage LF is allowed.",
            non_ascii,
            source=non_ascii + b"\n",
        ),
        _accept(
            "canonicalization.non_bmp_literal",
            "A non-BMP scalar is emitted as its four-byte UTF-8 sequence.",
            non_bmp,
        ),
        _accept(
            "canonicalization.unicode_key_order",
            "Keys follow scalar-value order, including normalization-sensitive and non-BMP cases.",
            unicode_order,
        ),
        _reject(
            "canonicalization.escaped_non_ascii",
            "A source Unicode escape is not canonical when the scalar must be literal.",
            _payload(br'{"text":"caf\u00e9"}'),
            "CANONICAL_BYTES_MISMATCH",
        ),
        _reject(
            "canonicalization.escaped_non_bmp_pair",
            "A valid surrogate-pair escape decodes correctly but is not canonical source spelling.",
            _payload(br'{"emoji":"\ud83d\ude00"}'),
            "CANONICAL_BYTES_MISMATCH",
        ),
        _accept(
            "canonicalization.control_character_escapes",
            "Control scalars use the exact short-escape and lowercase-u escape table.",
            controls,
        ),
        _accept(
            "canonicalization.nested_arrays_and_objects",
            "Nested object keys sort recursively while array order is preserved.",
            nested,
        ),
        _accept(
            "canonicalization.float_lower_scientific_boundary",
            "Decimal exponent -5 uses scientific notation.",
            _payload(b'{"n":1e-05}'),
        ),
        _accept(
            "canonicalization.float_lower_fixed_boundary",
            "Decimal exponent -4 uses fixed notation.",
            _payload(b'{"n":0.0001}'),
        ),
        _accept(
            "canonicalization.float_upper_fixed_boundary",
            "Decimal exponent 15 remains fixed and an integral float retains .0.",
            _payload(b'{"n":1000000000000000.0}'),
        ),
        _accept(
            "canonicalization.float_upper_scientific_boundary",
            "Decimal exponent 16 uses scientific notation with an explicit sign.",
            _payload(b'{"n":1e+16}'),
        ),
        _accept(
            "canonicalization.float_rounding_sensitive",
            "A rounding-sensitive binary64 value uses its shortest round-trip spelling.",
            _payload(b'{"n":0.30000000000000004}'),
        ),
        _reject(
            "canonicalization.float_rounding_alias",
            "A longer decimal that parses to the same binary64 value is not canonical spelling.",
            _payload(b'{"n":0.30000000000000005}'),
            "CANONICAL_BYTES_MISMATCH",
        ),
        _accept(
            "canonicalization.binary64_finite_extremes",
            "Minimum positive subnormal and maximum finite binary64 values are reproducible.",
            _payload(
                b'{"max":1.7976931348623157e+308,"min_subnormal":5e-324}'
            ),
        ),
        _accept(
            "canonicalization.float_negative_zero",
            "Binary64 negative zero retains its sign and .0 spelling.",
            _payload(b'{"n":-0.0}'),
        ),
        _reject(
            "canonicalization.integer_negative_zero",
            "Integer -0 has value zero and therefore is not canonical spelling.",
            _payload(b'{"n":-0}'),
            "CANONICAL_BYTES_MISMATCH",
        ),
        _accept(
            "canonicalization.integer_common_boundaries",
            "Integers around binary64 and signed-64 boundaries retain exact decimal values.",
            _payload(
                b'{"i53":9007199254740991,"i53_plus_one":9007199254740992,'
                b'"i64_plus_one":9223372036854775808,'
                b'"negative":-9223372036854775808}'
            ),
        ),
        _accept(
            "canonicalization.integer_640_digit_subset_boundary",
            "Positive and negative 640-digit magnitudes are inside the restricted subset.",
            integer_640,
        ),
        _accept(
            "canonicalization.nan_exact_legacy_token",
            "Exact NaN is preserved legacy behavior outside the restricted subset.",
            _payload(b'{"n":NaN}'),
            domain="LEGACY_PRESERVED_OUTSIDE_SUBSET",
        ),
        _reject(
            "canonicalization.nan_lowercase_rejected",
            "Lowercase nan is not an accepted legacy token.",
            _payload(b'{"n":nan}'),
            "CANONICAL_NOT_JSON",
        ),
        _accept(
            "canonicalization.infinity_exact_legacy_token",
            "Exact Infinity is preserved legacy behavior outside the restricted subset.",
            _payload(b'{"n":Infinity}'),
            domain="LEGACY_PRESERVED_OUTSIDE_SUBSET",
        ),
        _reject(
            "canonicalization.infinity_plus_sign_rejected",
            "+Infinity is not an accepted legacy token.",
            _payload(b'{"n":+Infinity}'),
            "CANONICAL_NOT_JSON",
        ),
        _accept(
            "canonicalization.negative_infinity_exact_legacy_token",
            "Exact -Infinity is preserved legacy behavior outside the restricted subset.",
            _payload(b'{"n":-Infinity}'),
            domain="LEGACY_PRESERVED_OUTSIDE_SUBSET",
        ),
        _reject(
            "canonicalization.negative_infinity_lowercase_rejected",
            "Lowercase -infinity is not an accepted legacy token.",
            _payload(b'{"n":-infinity}'),
            "CANONICAL_NOT_JSON",
        ),
        _reject(
            "canonicalization.duplicate_object_name",
            "Duplicate payload names collapse during parsing and cannot match canonical bytes.",
            _payload(b'{"a":1,"a":2}'),
            "CANONICAL_BYTES_MISMATCH",
        ),
        _reject(
            "canonicalization.ill_formed_utf8",
            "A UTF-8 encoding of a surrogate code point is ill-formed.",
            _payload(b'{"s":"' + bytes.fromhex("eda080") + b'"}'),
            "CANONICAL_NOT_JSON",
        ),
        _reject(
            "canonicalization.unpaired_surrogate_escape",
            "An unpaired high-surrogate escape is not a Unicode scalar value.",
            _payload(br'{"s":"\ud800"}'),
            "CANONICAL_NOT_JSON",
        ),
        _reject(
            "canonicalization.insignificant_whitespace",
            "Parser whitespace is not accepted as stored canonical payload bytes.",
            (
                b'{ "metadata": {}, "model": "m", "output": "o", '
                b'"prompt": "p", "schema_version": "ai_output_v1", '
                b'"ts_utc": "2026-01-01T00:00:00Z" }'
            ),
            "CANONICAL_BYTES_MISMATCH",
        ),
    ]
    if len(vectors) != 30:
        raise AssertionError(f"expected 30 vectors, got {len(vectors)}")
    return vectors


def build_files() -> dict[Path, bytes]:
    vectors = build_vectors()
    vector_document = {
        "canonicalization_identifier": IDENTIFIER,
        "case_count": len(vectors),
        "corpus": CORPUS,
        "status": STATUS,
        "vectors": vectors,
    }
    manifest = {
        "canonicalization_identifier": IDENTIFIER,
        "case_count": len(vectors),
        "corpus": CORPUS,
        "open_domain": ["integer_magnitude_more_than_640_decimal_digits"],
        "runner": "../run_canonicalization.py",
        "status": STATUS,
        "vector_files": ["vectors.json"],
    }
    return {
        Path("canonicalization/manifest.json"): (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        Path("canonicalization/vectors.json"): (
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
    for relative, expected in build_files().items():
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
        "CANONICALIZATION_VECTORS="
        f"{'WRITTEN' if args.write else 'MATCH'} files=2 cases=30"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
