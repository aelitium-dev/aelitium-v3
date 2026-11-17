#!/usr/bin/env python3
"""Execute frozen canonical-payload byte vectors against the current verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from engine.ai_canonical import canonicalize_ai_output
from engine.ai_verify import verify_ai_bundle


class CanonicalizationConformanceFailure(AssertionError):
    pass


def _load(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _equal(case_id: str, name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise CanonicalizationConformanceFailure(
            f"{case_id}: {name}: expected {expected!r}, observed {actual!r}"
        )


def _manifest_bytes(digest: str) -> bytes:
    manifest = {
        "ai_hash_sha256": digest,
        "canonicalization": "json_sorted_keys_no_whitespace_utf8",
        "input_schema": "ai_output_v1",
        "schema": "ai_pack_manifest_v1",
        "ts_utc": "2026-01-01T00:00:00Z",
    }
    return (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")


def _run_vector(vector: dict[str, Any]) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    source = bytes.fromhex(vector["source_bytes_hex"])

    _equal(
        case_id,
        "frozen source digest",
        hashlib.sha256(source).hexdigest(),
        vector["source_sha256"],
    )

    manifest_digest = expected["sha256"] or ("0" * 64)
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory)
        (bundle / "ai_canonical.json").write_bytes(source)
        (bundle / "ai_manifest.json").write_bytes(
            _manifest_bytes(manifest_digest)
        )
        result = verify_ai_bundle(bundle)

    decision = "ACCEPT" if result.valid else "REJECT"
    _equal(case_id, "decision", decision, expected["decision"])
    _equal(case_id, "verifier reason", result.reason, expected["reason"])

    if expected["decision"] == "ACCEPT":
        expected_canonical = bytes.fromhex(expected["canonical_utf8_hex"])
        _equal(
            case_id,
            "frozen canonical digest",
            hashlib.sha256(expected_canonical).hexdigest(),
            expected["sha256"],
        )
        actual_canonical, actual_digest = canonicalize_ai_output(result.canonical)
        _equal(
            case_id,
            "canonical UTF-8 bytes",
            actual_canonical.encode("utf-8"),
            expected_canonical,
        )
        _equal(case_id, "canonical digest", actual_digest, expected["sha256"])
        _equal(case_id, "verifier digest", result.ai_hash_sha256, expected["sha256"])
        if source not in (expected_canonical, expected_canonical + b"\n"):
            raise CanonicalizationConformanceFailure(
                f"{case_id}: accepted source is outside the terminal-LF envelope"
            )
    else:
        _equal(case_id, "rejected canonical bytes", expected["canonical_utf8_hex"], None)
        _equal(case_id, "rejected canonical digest", expected["sha256"], None)


def run(*, verbose: bool) -> dict[str, Any]:
    manifest = _load("canonicalization/manifest.json")
    if manifest["canonicalization_identifier"] != (
        "json_sorted_keys_no_whitespace_utf8"
    ):
        raise CanonicalizationConformanceFailure(
            "manifest changes the existing canonicalization identifier"
        )

    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    counts = {
        "CROSS_LANGUAGE_SAFE": 0,
        "LEGACY_PRESERVED_OUTSIDE_SUBSET": 0,
        "REJECTED": 0,
    }
    executed = 0
    for relative in manifest["vector_files"]:
        document = _load(f"canonicalization/{relative}")
        _equal(relative, "corpus", document["corpus"], manifest["corpus"])
        _equal(relative, "status", document["status"], manifest["status"])
        _equal(
            relative,
            "canonicalization identifier",
            document["canonicalization_identifier"],
            manifest["canonicalization_identifier"],
        )
        _equal(relative, "case count", document["case_count"], len(document["vectors"]))
        for vector in document["vectors"]:
            case_id = vector["case_id"]
            if case_id in seen_ids:
                raise CanonicalizationConformanceFailure(
                    f"duplicate case_id: {case_id}"
                )
            if vector["source_sha256"] in seen_sources:
                raise CanonicalizationConformanceFailure(
                    f"{case_id}: duplicate source-byte vector"
                )
            seen_ids.add(case_id)
            seen_sources.add(vector["source_sha256"])

            domain = vector["expected"]["domain"]
            if domain not in counts:
                raise CanonicalizationConformanceFailure(
                    f"{case_id}: unknown domain {domain!r}"
                )
            counts[domain] += 1
            _run_vector(vector)
            executed += 1
            if verbose:
                print(f"[PASS] {case_id}")

    _equal("manifest", "case count", executed, manifest["case_count"])
    _equal("manifest", "open domain", manifest["open_domain"], [
        "integer_magnitude_more_than_640_decimal_digits"
    ])
    return {
        "canonicalization_identifier": manifest["canonicalization_identifier"],
        "cases": executed,
        "corpus": manifest["corpus"],
        "domains": counts,
        "open_domain": manifest["open_domain"],
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit one JSON summary")
    args = parser.parse_args()
    try:
        result = run(verbose=not args.json)
    except (CanonicalizationConformanceFailure, KeyError, TypeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        else:
            print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"[PASS] CANONICALIZATION_CONFORMANCE cases={result['cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
