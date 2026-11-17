#!/usr/bin/env python3
"""Execute the frozen AELITIUM contract conformance corpus."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
DIMENSIONS = {
    "payload_integrity",
    "binding_field_consistency",
    "invocation_identity_consistency",
    "invocation_binding_consistency",
    "signature_validity",
    "trusted_signer_identity",
    "freshness",
    "authorization",
}


class ConformanceFailure(AssertionError):
    pass


def _load(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _resolved_options(options: list[str]) -> list[str]:
    resolved = []
    for value in options:
        if value.startswith("fixtures/"):
            resolved.append(str(ROOT / value))
        else:
            resolved.append(value)
    return resolved


def _run_cli(arguments: list[str]) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-m", "engine.ai_cli", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ConformanceFailure(
            f"CLI did not emit one JSON document (rc={completed.returncode}): "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        ) from exc
    return completed.returncode, payload


def _states_from_assurance(payload: dict[str, Any]) -> dict[str, str]:
    return {
        item["dimension"]: item["state"]
        for item in payload["assurance"]["dimensions"]
    }


def _all_verification_boundaries(payload: dict[str, Any]) -> set[str]:
    boundaries = set(payload["claim_boundaries"])
    boundaries.update(payload["assurance"]["claim_boundaries"])
    for dimension in payload["assurance"]["dimensions"]:
        boundaries.update(dimension["claim_boundaries"])
    return boundaries


def _equal(case_id: str, name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ConformanceFailure(
            f"{case_id}: {name}: expected {expected!r}, observed {actual!r}"
        )


def _run_verify(
    vector: dict[str, Any],
    verification_validator: Draft7Validator,
    assurance_validator: Draft7Validator,
) -> None:
    case_id = vector["case_id"]
    inputs = vector["input"]
    expected = vector["expected"]
    bundle = ROOT / inputs["bundle"]
    rc, payload = _run_cli(
        [
            "verify-bundle",
            str(bundle),
            *_resolved_options(inputs["options"]),
            "--contract-json",
        ]
    )
    verification_validator.validate(payload)
    assurance_validator.validate(payload["assurance"])
    _equal(case_id, "process rc", rc, expected["rc"])
    _equal(case_id, "contract rc", payload["rc"], expected["rc"])
    _equal(case_id, "status", payload["status"], expected["status"])
    _equal(case_id, "reason", payload["reason"], expected["reason"])
    _equal(
        case_id,
        "assurance states",
        _states_from_assurance(payload),
        expected["assurance_states"],
    )
    emitted = _all_verification_boundaries(payload)
    missing = set(expected["expected_non_claims"]) - emitted
    if missing:
        raise ConformanceFailure(
            f"{case_id}: expected non-claims not emitted: {sorted(missing)}"
        )


def _run_compare(
    vector: dict[str, Any],
    compare_validator: Draft7Validator,
) -> None:
    case_id = vector["case_id"]
    inputs = vector["input"]
    expected = vector["expected"]
    rc, payload = _run_cli(
        [
            "compare",
            str(ROOT / inputs["left"]),
            str(ROOT / inputs["right"]),
            *_resolved_options(inputs["options"]),
            "--json",
        ]
    )
    compare_validator.validate(payload)
    _equal(case_id, "process rc", rc, expected["rc"])
    _equal(case_id, "contract rc", payload["rc"], expected["rc"])
    _equal(case_id, "status", payload["status"], expected["status"])
    _equal(case_id, "reason", payload["comparison_reason"], expected["reason"])
    _equal(
        case_id,
        "comparison basis",
        payload["comparison_basis"],
        expected["comparison_basis"],
    )
    _equal(
        case_id,
        "required comparison basis",
        payload["required_comparison_basis"],
        expected["required_comparison_basis"],
    )
    _equal(
        case_id,
        "response relationship",
        payload["response_relationship"],
        expected["response_relationship"],
    )
    _equal(
        case_id,
        "left assurance states",
        payload["left"]["verification"]["assurance_states"],
        expected["assurance_states"]["left"],
    )
    _equal(
        case_id,
        "right assurance states",
        payload["right"]["verification"]["assurance_states"],
        expected["assurance_states"]["right"],
    )
    missing = set(expected["expected_non_claims"]) - set(
        payload["claim_boundaries"]
    )
    if missing:
        raise ConformanceFailure(
            f"{case_id}: expected non-claims not emitted: {sorted(missing)}"
        )


def run(*, verbose: bool) -> dict[str, Any]:
    manifest = _load("manifest.json")
    verification_schema = _load(manifest["result_schemas"]["verification"])
    assurance_schema = _load(manifest["result_schemas"]["assurance"])
    comparison_schema = _load(manifest["result_schemas"]["comparison"])
    for schema in (verification_schema, assurance_schema, comparison_schema):
        Draft7Validator.check_schema(schema)
    verification_validator = Draft7Validator(verification_schema)
    assurance_validator = Draft7Validator(assurance_schema)
    comparison_validator = Draft7Validator(comparison_schema)

    seen: set[str] = set()
    seen_executions: dict[str, str] = {}
    category_counts: dict[str, int] = {}
    executed = 0
    for vector_file in manifest["vector_files"]:
        document = _load(vector_file)
        category = document["category"]
        vectors = document["vectors"]
        _equal(vector_file, "declared case count", document["case_count"], len(vectors))
        category_counts[category] = len(vectors)
        for vector in vectors:
            case_id = vector["case_id"]
            if case_id in seen:
                raise ConformanceFailure(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            execution_key = json.dumps(
                {
                    "operation": vector["operation"],
                    "input": vector["input"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            if execution_key in seen_executions:
                raise ConformanceFailure(
                    f"{case_id}: duplicates executable input from "
                    f"{seen_executions[execution_key]}"
                )
            seen_executions[execution_key] = case_id
            expected_states = vector["expected"]["assurance_states"]
            state_sets = (
                expected_states.values()
                if vector["operation"] == "verify"
                else [expected_states["left"], expected_states["right"]]
            )
            if vector["operation"] == "verify":
                if set(expected_states) != DIMENSIONS:
                    raise ConformanceFailure(
                        f"{case_id}: expected assurance dimensions are incomplete"
                    )
                _run_verify(vector, verification_validator, assurance_validator)
            elif vector["operation"] == "compare":
                for side_states in state_sets:
                    if set(side_states) != DIMENSIONS:
                        raise ConformanceFailure(
                            f"{case_id}: per-side assurance dimensions are incomplete"
                        )
                _run_compare(vector, comparison_validator)
            else:
                raise ConformanceFailure(
                    f"{case_id}: unsupported operation {vector['operation']!r}"
                )
            executed += 1
            if verbose:
                print(f"[PASS] {case_id}")

    _equal("manifest", "case count", executed, manifest["case_count"])
    return {
        "corpus": manifest["corpus"],
        "status": "PASS",
        "cases": executed,
        "categories": category_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit one JSON summary")
    args = parser.parse_args()
    try:
        result = run(verbose=not args.json)
    except (ConformanceFailure, KeyError, TypeError, SchemaError, ValidationError) as exc:
        # The broad schema-error family is rendered without a traceback for the
        # public runner. Unexpected programming errors still fail normally.
        if args.json:
            print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        else:
            print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"[PASS] CONFORMANCE cases={result['cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
