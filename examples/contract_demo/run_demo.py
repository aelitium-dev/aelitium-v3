#!/usr/bin/env python3
"""Run the frozen verification/assurance/comparability contract demo."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "conformance" / "fixtures" / "bundles"
SCHEMAS = ROOT / "engine" / "schemas"


def _run(command: list[str], expected_rc: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != expected_rc:
        raise RuntimeError(
            f"unexpected rc={completed.returncode}, expected={expected_rc}: "
            f"{' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def _cli_json(arguments: list[str], expected_rc: int) -> dict[str, Any]:
    completed = _run(
        [sys.executable, "-m", "engine.ai_cli", *arguments],
        expected_rc,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI did not emit JSON: {completed.stdout!r}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("CLI result must be a JSON object")
    return value


def _schema(filename: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _assurance_states(assurance: dict[str, Any]) -> dict[str, str]:
    return {
        item["dimension"]: item["state"]
        for item in assurance["dimensions"]
    }


def run_demo(output_dir: Path) -> tuple[str, ...]:
    _run(
        [sys.executable, "conformance/build_fixtures.py", "--check"],
        0,
    )

    left = FIXTURES / "signed_valid"
    changed = FIXTURES / "full_b_changed_response"
    different_invocation = FIXTURES / "model_changed"

    verification = _cli_json(
        ["verify-bundle", str(left), "--contract-json"],
        0,
    )
    assurance = verification["assurance"]
    comparison = _cli_json(
        ["compare", str(left), str(changed), "--json"],
        2,
    )
    not_comparable = _cli_json(
        [
            "compare",
            str(left),
            str(different_invocation),
            "--require-invocation-evidence",
            "--json",
        ],
        1,
    )

    Draft7Validator(_schema("verification_result_v1.json")).validate(verification)
    Draft7Validator(_schema("assurance_result_v1.json")).validate(assurance)
    compare_validator = Draft7Validator(_schema("compare_result_v1.json"))
    compare_validator.validate(comparison)
    compare_validator.validate(not_comparable)

    states = _assurance_states(assurance)
    if verification["status"] != "VALID":
        raise RuntimeError("expected the frozen left bundle to verify")
    if states["signature_validity"] != "VALID":
        raise RuntimeError("expected a mathematically valid bundled signature")
    if states["trusted_signer_identity"] != "UNESTABLISHED":
        raise RuntimeError("expected no ambient signer trust")
    if states["authorization"] != "NOT_EVALUATED":
        raise RuntimeError("authorization must remain NOT_EVALUATED")
    if comparison["comparability_result"] != "CHANGED":
        raise RuntimeError("expected selected response hashes to differ")
    if not_comparable["comparability_result"] != "NOT_COMPARABLE":
        raise RuntimeError("expected strict invocation comparison to refuse")

    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = (
        "verification-result.json",
        "assurance-result.json",
        "comparison-result.json",
        "not-comparable-result.json",
        "interpretation.txt",
    )
    _write_json(output_dir / filenames[0], verification)
    _write_json(output_dir / filenames[1], assurance)
    _write_json(output_dir / filenames[2], comparison)
    _write_json(output_dir / filenames[3], not_comparable)

    interpretation = "\n".join(
        (
            "AELITIUM_CONTRACT_DEMO=PASS",
            f"VERIFICATION_STATUS={verification['status']}",
            f"VERIFICATION_REASON={verification['reason']}",
            f"PAYLOAD_INTEGRITY={states['payload_integrity']}",
            f"SIGNATURE_VALIDITY={states['signature_validity']}",
            f"TRUSTED_SIGNER_IDENTITY={states['trusted_signer_identity']}",
            f"FRESHNESS={states['freshness']}",
            f"AUTHORIZATION={states['authorization']}",
            f"COMPARISON_RESULT={comparison['comparability_result']}",
            f"COMPARISON_BASIS={comparison['comparison_basis']}",
            f"COMPARISON_REASON={comparison['comparison_reason']}",
            "COMPARISON_BOUNDARY=model_drift_not_established",
            f"STRICT_RESULT={not_comparable['comparability_result']}",
            f"STRICT_BASIS={not_comparable['comparison_basis']}",
            f"STRICT_REASON={not_comparable['comparison_reason']}",
            "STRICT_INTERPRETATION=no_response_change_conclusion",
            "SIGNATURE_BOUNDARY=trusted_signer_identity_not_established_by_signature",
            "TIME_BOUNDARY=trusted_historical_time_not_established",
            "EXECUTION_BOUNDARY=provider_execution_not_established",
        )
    ) + "\n"
    (output_dir / filenames[4]).write_text(interpretation, encoding="utf-8")
    return filenames


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit deterministic contract-demo results from frozen fixtures"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for the five generated result artifacts",
    )
    args = parser.parse_args()
    filenames = run_demo(args.output_dir)
    print("STATUS=PASS")
    for filename in filenames:
        print(f"OUTPUT={args.output_dir / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
