import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "engine" / "ai_cli.py"
FIX = ROOT / "tests" / "fixtures" / "ai_output_min.json"

def run_cmd(*args: str):
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

class TestAICLI(unittest.TestCase):
    def test_validate_ok(self):
        cp = run_cmd("validate", "--input", str(FIX))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("AI_STATUS=VALID", cp.stdout)

    def test_canonicalize_deterministic(self):
        cp1 = run_cmd("canonicalize", "--input", str(FIX))
        cp2 = run_cmd("canonicalize", "--input", str(FIX))
        self.assertEqual(cp1.returncode, 0, cp1.stdout + cp1.stderr)
        self.assertEqual(cp2.returncode, 0, cp2.stdout + cp2.stderr)
        h1 = [l for l in cp1.stdout.splitlines() if l.startswith("AI_CANON_SHA256=")][0]
        h2 = [l for l in cp2.stdout.splitlines() if l.startswith("AI_CANON_SHA256=")][0]
        self.assertEqual(h1, h2)

if __name__ == "__main__":
    unittest.main()
