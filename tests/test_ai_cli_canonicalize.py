import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]

HASH_RE = re.compile(r"^AI_CANON_SHA256=([0-9a-f]{64})$")


def _run(*extra_args):
    return subprocess.run(
        CLI + ["canonicalize", "--input", str(FIXTURE)] + list(extra_args),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


class TestCanonicalizeContract(unittest.TestCase):

    def test_exit_code_zero(self):
        r = _run()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_stdout_has_hash_line(self):
        r = _run()
        lines = r.stdout.strip().splitlines()
        self.assertTrue(
            any(HASH_RE.match(l) for l in lines),
            f"No AI_CANON_SHA256 line found in: {r.stdout!r}",
        )

    def test_hash_is_64_hex(self):
        r = _run()
        for line in r.stdout.strip().splitlines():
            m = HASH_RE.match(line)
            if m:
                self.assertEqual(len(m.group(1)), 64)
                return
        self.fail("Hash line not found")

    def test_hash_stable_across_two_runs(self):
        r1 = _run()
        r2 = _run()
        hash1 = next(
            HASH_RE.match(l).group(1)
            for l in r1.stdout.strip().splitlines()
            if HASH_RE.match(l)
        )
        hash2 = next(
            HASH_RE.match(l).group(1)
            for l in r2.stdout.strip().splitlines()
            if HASH_RE.match(l)
        )
        self.assertEqual(hash1, hash2, "Hash must be deterministic")

    def test_print_flag_adds_canonical_json(self):
        r = _run("--print")
        lines = r.stdout.strip().splitlines()
        self.assertRegex(lines[-1], HASH_RE)
        json_line = lines[-2] if len(lines) >= 2 else None
        self.assertIsNotNone(json_line, "Expected JSON line before hash")
        obj = json.loads(json_line)
        self.assertEqual(obj.get("schema_version"), "ai_output_v1")

    def test_print_canonical_has_sorted_keys(self):
        r = _run("--print")
        lines = r.stdout.strip().splitlines()
        json_line = lines[-2]
        obj = json.loads(json_line)
        keys = list(obj.keys())
        self.assertEqual(keys, sorted(keys), "Canonical JSON keys must be sorted")

    def test_no_extra_stdout_without_print(self):
        """Without --print, stdout is exactly one line: the hash."""
        r = _run()
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(len(lines), 1, f"Expected 1 line, got: {lines}")
        self.assertRegex(lines[0], HASH_RE)


if __name__ == "__main__":
    unittest.main()
