import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]
HASH_RE = re.compile(r"^AI_HASH_SHA256=([0-9a-f]{64})$")


def _pack(outdir: Path):
    subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True, check=True, cwd=ROOT,
    )


def _verify(outdir: Path):
    return subprocess.run(
        CLI + ["verify", "--out", str(outdir)],
        capture_output=True, text=True, cwd=ROOT,
    )


class TestVerifyContract(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        _pack(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    # --- VALID path ---

    def test_valid_exit_code_zero(self):
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_stdout_exactly_two_lines(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(len(lines), 2, f"Expected 2 lines, got: {lines}")

    def test_valid_first_line(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[0], "STATUS=VALID rc=0")

    def test_valid_second_line_is_hash(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertRegex(lines[1], HASH_RE)

    def test_valid_hash_matches_pack_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            pack_r = subprocess.run(
                CLI + ["pack", "--input", str(FIXTURE), "--out", str(p)],
                capture_output=True, text=True, cwd=ROOT,
            )
            pack_hash = next(
                l for l in pack_r.stdout.splitlines() if l.startswith("AI_HASH_SHA256=")
            )
            verify_r = _verify(p)
            verify_hash = next(
                l for l in verify_r.stdout.splitlines() if l.startswith("AI_HASH_SHA256=")
            )
            self.assertEqual(pack_hash, verify_hash)

    # --- INVALID: missing files ---

    def test_missing_canonical_gives_rc2(self):
        (self.outdir / "ai_canonical.json").unlink()
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATUS=INVALID", r.stdout)
        self.assertIn("reason=MISSING_CANONICAL", r.stdout)

    def test_missing_manifest_gives_rc2(self):
        (self.outdir / "ai_manifest.json").unlink()
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATUS=INVALID", r.stdout)
        self.assertIn("reason=MISSING_MANIFEST", r.stdout)

    # --- INVALID: tampered canonical ---

    def test_tampered_canonical_gives_rc2(self):
        # Tamper preserving valid JSON but changing content → HASH_MISMATCH
        canon = self.outdir / "ai_canonical.json"
        obj = json.loads(canon.read_text(encoding="utf-8"))
        obj["output"] = "TAMPERED"
        canon.write_text(json.dumps(obj) + "\n", encoding="utf-8")
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=HASH_MISMATCH", r.stdout)
        self.assertIn("DETAIL=", r.stdout)

    # --- INVALID: tampered manifest hash ---

    def test_tampered_manifest_hash_gives_rc2(self):
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        m["ai_hash_sha256"] = "a" * 64
        (self.outdir / "ai_manifest.json").write_text(
            json.dumps(m, sort_keys=True) + "\n", encoding="utf-8"
        )
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=HASH_MISMATCH", r.stdout)

    # --- no traceback ---

    def test_no_traceback_on_valid(self):
        r = _verify(self.outdir)
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
