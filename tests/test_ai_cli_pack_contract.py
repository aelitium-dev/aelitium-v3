import hashlib
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
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _run_pack(outdir: Path):
    return subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


class TestPackContract(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # --- stdout ---

    def test_exit_code_zero(self):
        r = _run_pack(self.outdir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_stdout_exactly_two_lines(self):
        r = _run_pack(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(len(lines), 2, f"Expected 2 lines, got: {lines}")

    def test_stdout_first_line(self):
        r = _run_pack(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[0], "STATUS=OK rc=0")

    def test_stdout_second_line_is_hash(self):
        r = _run_pack(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertRegex(lines[1], HASH_RE)

    def test_hash_deterministic_across_runs(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            r1 = _run_pack(Path(d1))
            r2 = _run_pack(Path(d2))
            h1 = next(l for l in r1.stdout.splitlines() if l.startswith("AI_HASH_SHA256="))
            h2 = next(l for l in r2.stdout.splitlines() if l.startswith("AI_HASH_SHA256="))
            self.assertEqual(h1, h2)

    # --- ai_canonical.json ---

    def test_canonical_file_exists(self):
        _run_pack(self.outdir)
        self.assertTrue((self.outdir / "ai_canonical.json").exists())

    def test_canonical_is_valid_json(self):
        _run_pack(self.outdir)
        content = (self.outdir / "ai_canonical.json").read_text(encoding="utf-8")
        json.loads(content)  # raises if invalid

    def test_canonical_ends_with_newline(self):
        _run_pack(self.outdir)
        raw = (self.outdir / "ai_canonical.json").read_bytes()
        self.assertEqual(raw[-1:], b"\n")

    def test_canonical_keys_sorted(self):
        _run_pack(self.outdir)
        content = (self.outdir / "ai_canonical.json").read_text(encoding="utf-8")
        obj = json.loads(content)
        keys = list(obj.keys())
        self.assertEqual(keys, sorted(keys))

    def test_canonical_hash_matches_stdout(self):
        r = _run_pack(self.outdir)
        stdout_hash = next(
            HASH_RE.match(l).group(1)
            for l in r.stdout.splitlines()
            if HASH_RE.match(l)
        )
        content = (self.outdir / "ai_canonical.json").read_text(encoding="utf-8")
        # hash is over the canonical string (no trailing newline)
        file_hash = hashlib.sha256(content.rstrip("\n").encode("utf-8")).hexdigest()
        self.assertEqual(stdout_hash, file_hash)

    # --- ai_manifest.json ---

    def test_manifest_file_exists(self):
        _run_pack(self.outdir)
        self.assertTrue((self.outdir / "ai_manifest.json").exists())

    def test_manifest_is_valid_json(self):
        _run_pack(self.outdir)
        content = (self.outdir / "ai_manifest.json").read_text(encoding="utf-8")
        json.loads(content)

    def test_manifest_ends_with_newline(self):
        _run_pack(self.outdir)
        raw = (self.outdir / "ai_manifest.json").read_bytes()
        self.assertEqual(raw[-1:], b"\n")

    def test_manifest_keys_sorted(self):
        _run_pack(self.outdir)
        content = (self.outdir / "ai_manifest.json").read_text(encoding="utf-8")
        obj = json.loads(content)
        keys = list(obj.keys())
        self.assertEqual(keys, sorted(keys))

    def test_manifest_required_fields(self):
        _run_pack(self.outdir)
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        for field in ("schema", "ts_utc", "input_schema", "canonicalization", "ai_hash_sha256"):
            self.assertIn(field, m, f"Missing field: {field}")

    def test_manifest_schema_value(self):
        _run_pack(self.outdir)
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["schema"], "ai_pack_manifest_v1")

    def test_manifest_ts_utc_format(self):
        _run_pack(self.outdir)
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        self.assertRegex(m["ts_utc"], TS_RE)

    def test_manifest_input_schema_value(self):
        _run_pack(self.outdir)
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["input_schema"], "ai_output_v1")

    def test_manifest_hash_matches_stdout(self):
        r = _run_pack(self.outdir)
        stdout_hash = next(
            HASH_RE.match(l).group(1)
            for l in r.stdout.splitlines()
            if HASH_RE.match(l)
        )
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["ai_hash_sha256"], stdout_hash)


if __name__ == "__main__":
    unittest.main()
