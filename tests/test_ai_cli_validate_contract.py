import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_OK = ROOT / "tests" / "fixtures" / "ai_output_min.json"
SCHEMA = ROOT / "engine" / "schemas" / "ai_output_v1.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]


def _run_validate(*extra_args):
    return subprocess.run(
        CLI + ["validate", "--input", str(FIXTURE_OK)] + list(extra_args),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _run_validate_bad():
    """Run validate with a fixture missing required field ts_utc."""
    bad = FIXTURE_OK.read_text(encoding="utf-8").replace(
        '"ts_utc": "2026-03-04T00:00:00Z",\n', ""
    )
    tmp = ROOT / "artifacts" / "results" / "tmp_validate_contract_bad.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(bad, encoding="utf-8")
    return subprocess.run(
        CLI + ["validate", "--input", str(tmp), "--schema", str(SCHEMA)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


class TestValidateContract(unittest.TestCase):

    # --- VALID path ---

    def test_valid_exit_code_zero(self):
        r = _run_validate("--schema", str(SCHEMA))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_stdout_exact(self):
        r = _run_validate("--schema", str(SCHEMA))
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines, ["STATUS=VALID rc=0"])

    def test_valid_default_schema(self):
        """--schema must be optional (default points to engine/schemas/ai_output_v1.json)."""
        r = _run_validate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("STATUS=VALID", r.stdout)

    # --- INVALID path ---

    def test_invalid_exit_code_two(self):
        r = _run_validate_bad()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_invalid_status_line(self):
        r = _run_validate_bad()
        self.assertIn("STATUS=INVALID", r.stdout)

    def test_invalid_has_reason_schema_violation(self):
        r = _run_validate_bad()
        self.assertIn("reason=SCHEMA_VIOLATION", r.stdout)

    def test_invalid_has_detail_line(self):
        r = _run_validate_bad()
        detail_lines = [l for l in r.stdout.splitlines() if l.startswith("DETAIL=")]
        self.assertTrue(detail_lines, f"No DETAIL= line in: {r.stdout!r}")

    def test_invalid_no_traceback_in_stdout(self):
        r = _run_validate_bad()
        self.assertNotIn("Traceback", r.stdout)


if __name__ == "__main__":
    unittest.main()
