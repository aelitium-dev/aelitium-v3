#!/usr/bin/env python3
"""Execute the frozen portable canonicalization-v2 corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from engine.ai_contract import (  # noqa: E402
    AI_CANONICALIZATION_IDENTIFIERS,
    AI_CANONICALIZATION_V1,
    AI_CANONICALIZATION_V2,
)
from engine.ai_verify import verify_ai_bundle  # noqa: E402
from engine.canonical_v2 import (  # noqa: E402
    V2CanonicalizationError,
    canonical_json_v2_bytes,
    parse_json_v2,
)
from engine.manifest_dispatch import (  # noqa: E402
    DispatchScanError,
    scan_manifest_selector,
)


class V2ConformanceFailure(AssertionError):
    pass


def _load(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _equal(case_id: str, name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise V2ConformanceFailure(
            f"{case_id}: {name}: expected {expected!r}, observed {actual!r}"
        )


def _manifest_bytes(identifier: str, digest: str) -> bytes:
    return (
        b'{"schema":"ai_pack_manifest_v1",'
        b'"ts_utc":"2026-01-01T00:00:00Z",'
        b'"input_schema":"ai_output_v1",'
        b'"canonicalization":"'
        + identifier.encode("ascii")
        + b'","ai_hash_sha256":"'
        + digest.encode("ascii")
        + b'"}'
    )


def _route(manifest_bytes: bytes) -> str:
    try:
        selected = scan_manifest_selector(
            manifest_bytes,
            registered_identifiers=AI_CANONICALIZATION_IDENTIFIERS,
        )
    except DispatchScanError:
        return "legacy_error_resolution"
    if selected == AI_CANONICALIZATION_V2:
        return "v2"
    if selected == AI_CANONICALIZATION_V1:
        return "v1"
    return "legacy_error_resolution"


def _run_canonicalize(vector: dict[str, Any], source: bytes) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    try:
        value = parse_json_v2(source)
        canonical = canonical_json_v2_bytes(value)
    except V2CanonicalizationError as exc:
        _equal(case_id, "decision", "REJECT", expected["decision"])
        _equal(case_id, "error category", exc.reason, expected["error_category"])
        _equal(case_id, "canonical bytes", None, expected["canonical_utf8_hex"])
        return

    _equal(case_id, "decision", "ACCEPT", expected["decision"])
    _equal(case_id, "error category", None, expected["error_category"])
    expected_bytes = bytes.fromhex(expected["canonical_utf8_hex"])
    _equal(case_id, "canonical bytes", canonical, expected_bytes)
    _equal(
        case_id,
        "canonical digest",
        hashlib.sha256(canonical).hexdigest(),
        expected["canonical_sha256"],
    )
    # Fixed point is part of the canonical-byte contract.
    reparsed = parse_json_v2(canonical)
    _equal(
        case_id,
        "fixed point",
        canonical_json_v2_bytes(reparsed),
        canonical,
    )


def _run_storage(vector: dict[str, Any], source: bytes) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    digest = expected["canonical_sha256"] or ("0" * 64)
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory)
        (bundle / "ai_canonical.json").write_bytes(source)
        (bundle / "ai_manifest.json").write_bytes(
            _manifest_bytes(AI_CANONICALIZATION_V2, digest)
        )
        result = verify_ai_bundle(bundle)
    decision = "ACCEPT" if result.valid else "REJECT"
    _equal(case_id, "decision", decision, expected["decision"])
    _equal(
        case_id,
        "verifier category",
        None if result.valid else result.reason,
        expected["error_category"],
    )
    if expected["canonical_utf8_hex"] is not None:
        canonical = bytes.fromhex(expected["canonical_utf8_hex"])
        _equal(
            case_id,
            "frozen canonical digest",
            hashlib.sha256(canonical).hexdigest(),
            expected["canonical_sha256"],
        )


def _run_dispatch(vector: dict[str, Any], source: bytes) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    parameters = vector.get("parameters", {})
    old_int_limit = sys.get_int_max_str_digits()
    old_recursion_limit = sys.getrecursionlimit()
    requested_int_limit = parameters.get("int_digit_limit")
    recursion_limits = parameters.get("recursion_limits", [old_recursion_limit])
    try:
        if requested_int_limit is not None:
            sys.set_int_max_str_digits(requested_int_limit)
        for recursion_limit in recursion_limits:
            sys.setrecursionlimit(recursion_limit)
            suffix = f" at recursion_limit={recursion_limit}"
            _equal(
                case_id,
                "routing target" + suffix,
                _route(source),
                expected["routing_target"],
            )
            with tempfile.TemporaryDirectory() as directory:
                bundle = Path(directory)
                (bundle / "ai_canonical.json").write_bytes(_base_canonical())
                (bundle / "ai_manifest.json").write_bytes(source)
                result = verify_ai_bundle(bundle)

            decision = "ACCEPT" if result.valid else "REJECT"
            _equal(
                case_id,
                "decision" + suffix,
                decision,
                expected["decision"],
            )
            _equal(
                case_id,
                "verifier reason" + suffix,
                result.reason,
                parameters["verifier_reason"],
            )
    finally:
        sys.setrecursionlimit(old_recursion_limit)
        sys.set_int_max_str_digits(old_int_limit)

    # The selected parser consumes the same immutable file bytes whose digest
    # is frozen on the vector; no scanner-normalized representation is written.
    _equal(
        case_id,
        "parser input digest",
        hashlib.sha256(source).hexdigest(),
        vector["source_sha256"],
    )


def _base_canonical() -> bytes:
    return (
        b'{"metadata":{},"model":"m","output":"o","prompt":"p",'
        b'"schema_version":"ai_output_v1",'
        b'"ts_utc":"2026-01-01T00:00:00Z"}'
    )


def _run_comparison(vector: dict[str, Any], source: bytes) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    digest = hashlib.sha256(source).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, identifier in (
            ("left", AI_CANONICALIZATION_V1),
            ("right", AI_CANONICALIZATION_V2),
        ):
            bundle = root / name
            bundle.mkdir()
            (bundle / "ai_canonical.json").write_bytes(source)
            (bundle / "ai_manifest.json").write_bytes(
                _manifest_bytes(identifier, digest)
            )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "engine.ai_cli",
                "compare",
                str(root / "left"),
                str(root / "right"),
                "--json",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise V2ConformanceFailure(
            f"{case_id}: compare did not emit JSON: {completed.stdout!r}"
        ) from exc
    _equal(case_id, "process rc", completed.returncode, 1)
    _equal(case_id, "status", payload["status"], expected["decision"])
    _equal(
        case_id,
        "reason",
        payload["comparison_reason"],
        expected["error_category"],
    )
    _equal(
        case_id,
        "basis",
        payload["comparison_basis"],
        vector["parameters"]["comparison_basis"],
    )
    _equal(
        case_id,
        "response relationship",
        payload["response_relationship"],
        vector["parameters"]["response_relationship"],
    )


def _run_v1_artifact(vector: dict[str, Any], source: bytes) -> None:
    case_id = vector["case_id"]
    expected = vector["expected"]
    digest = hashlib.sha256(source).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory)
        (bundle / "ai_canonical.json").write_bytes(source)
        (bundle / "ai_manifest.json").write_bytes(
            _manifest_bytes(AI_CANONICALIZATION_V1, digest)
        )
        result = verify_ai_bundle(bundle)
    _equal(case_id, "routing target", "v1", expected["routing_target"])
    _equal(case_id, "decision", result.valid, True)
    _equal(
        case_id,
        "verifier reason",
        result.reason,
        vector["parameters"]["verifier_reason"],
    )
    _equal(case_id, "v1 digest", result.ai_hash_sha256, digest)
    _equal(case_id, "frozen digest", digest, expected["canonical_sha256"])


def _run_vector(vector: dict[str, Any]) -> None:
    case_id = vector["case_id"]
    source = bytes.fromhex(vector["source_bytes_hex"])
    _equal(
        case_id,
        "source digest",
        hashlib.sha256(source).hexdigest(),
        vector["source_sha256"],
    )
    operation = vector["operation"]
    if operation in {"canonicalize", "hash_material"}:
        _run_canonicalize(vector, source)
    elif operation == "storage_verify":
        _run_storage(vector, source)
    elif operation == "dispatch_verify":
        _run_dispatch(vector, source)
    elif operation == "comparison":
        _run_comparison(vector, source)
    elif operation == "v1_artifact":
        _run_v1_artifact(vector, source)
    else:
        raise V2ConformanceFailure(f"{case_id}: unknown operation {operation!r}")


def run(*, verbose: bool) -> dict[str, Any]:
    manifest = _load("canonicalization_v2/manifest.json")
    _equal(
        "manifest",
        "identifier",
        manifest["canonicalization_identifier"],
        AI_CANONICALIZATION_V2,
    )
    _equal(
        "manifest",
        "existing corpus counts",
        manifest["existing_corpora_unchanged"],
        {"canonicalization_v1_cases": 30, "result_contract_cases": 44},
    )

    seen_ids: set[str] = set()
    operation_counts: dict[str, int] = {}
    executed = 0
    for relative in manifest["vector_files"]:
        document = _load(f"canonicalization_v2/{relative}")
        _equal(relative, "corpus", document["corpus"], manifest["corpus"])
        _equal(relative, "status", document["status"], manifest["status"])
        _equal(
            relative,
            "identifier",
            document["canonicalization_identifier"],
            AI_CANONICALIZATION_V2,
        )
        _equal(relative, "case count", document["case_count"], len(document["vectors"]))
        for vector in document["vectors"]:
            case_id = vector["case_id"]
            if case_id in seen_ids:
                raise V2ConformanceFailure(f"duplicate case_id: {case_id}")
            seen_ids.add(case_id)
            _run_vector(vector)
            operation = vector["operation"]
            operation_counts[operation] = operation_counts.get(operation, 0) + 1
            executed += 1
            if verbose:
                print(f"[PASS] {case_id}")

    _equal("manifest", "case count", executed, manifest["case_count"])
    return {
        "canonicalization_identifier": AI_CANONICALIZATION_V2,
        "cases": executed,
        "corpus": manifest["corpus"],
        "operations": operation_counts,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit one JSON summary")
    args = parser.parse_args()
    try:
        result = run(verbose=not args.json)
    except (V2ConformanceFailure, KeyError, TypeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        else:
            print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"[PASS] CANONICALIZATION_V2_CONFORMANCE cases={result['cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
