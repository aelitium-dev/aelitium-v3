import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestAICLIValidate(unittest.TestCase):
    def test_validate_ok(self):
        cp = subprocess.run(
            [sys.executable, "-m", "engine.ai_cli", "validate",
             "--schema", str(ROOT / "engine/schemas/ai_output_v1.json"),
             "--input", str(ROOT / "tests/fixtures/ai_output_min.json")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("STATUS=VALID", cp.stdout)

    def test_validate_rejects_missing_field(self):
        bad = (ROOT / "tests/fixtures/ai_output_min.json").read_text(encoding="utf-8").replace('"ts_utc": "2026-03-04T00:00:00Z",\n', "")
        tmp = ROOT / "artifacts" / "results" / "tmp_bad_ai_output.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(bad, encoding="utf-8")

        cp = subprocess.run(
            [sys.executable, "-m", "engine.ai_cli", "validate",
             "--schema", str(ROOT / "engine/schemas/ai_output_v1.json"),
             "--input", str(tmp)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
        self.assertIn("STATUS=INVALID", cp.stdout)
