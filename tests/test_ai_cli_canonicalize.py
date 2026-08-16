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

HASH_RE = re.compile(r"^AI_CANON_SHA256=([0-9a-f]{64})$")


def _run(*extra_args, input_path=FIXTURE):
    return subprocess.run(
        CLI + ["canonicalize", "--input", str(input_path)] + list(extra_args),
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

    def test_reference_v1_hash_is_unchanged(self):
        r = _run()
        self.assertIn(
            "AI_CANON_SHA256="
            "583eb45e736f16abc077e68ebdd4119d6149d4d7aa5c27a457e7a454c7987f83",
            r.stdout.splitlines(),
        )

    def test_governed_json_golden_vectors(self):
        vectors = (
            (
                "unicode",
                {
                    "schema_version": "ai_output_v1",
                    "ts_utc": "2026-01-02T03:04:05Z",
                    "model": "vector-model",
                    "prompt": "café ☕",
                    "output": "你好, мир",
                    "metadata": {"label": "é"},
                },
                '{"metadata":{"label":"é"},"model":"vector-model",'
                '"output":"你好, мир","prompt":"café ☕",'
                '"schema_version":"ai_output_v1",'
                '"ts_utc":"2026-01-02T03:04:05Z"}',
                "b4df93aba4df44dd6b029107d94866a5072a7828c3fa59aa11b2335d30f4f01d",
            ),
            (
                "escaped_characters",
                {
                    "schema_version": "ai_output_v1",
                    "ts_utc": "2026-01-02T03:04:05Z",
                    "model": "vector-model",
                    "prompt": "line1\nline2\t\"quoted\"\\slash",
                    "output": "carriage\rreturn",
                    "metadata": {},
                },
                r'{"metadata":{},"model":"vector-model",'
                r'"output":"carriage\rreturn",'
                r'"prompt":"line1\nline2\t\"quoted\"\\slash",'
                r'"schema_version":"ai_output_v1",'
                r'"ts_utc":"2026-01-02T03:04:05Z"}',
                "9b20cf8264fb4ae10546295fbe6518a07c1c7ec9f288bc30254a3b2ad8830a1c",
            ),
            (
                "nested_dictionaries",
                {
                    "schema_version": "ai_output_v1",
                    "ts_utc": "2026-01-02T03:04:05Z",
                    "model": "vector-model",
                    "prompt": "nested",
                    "output": "object",
                    "metadata": {
                        "outer": {
                            "z": 1,
                            "a": {"enabled": True, "value": None},
                        }
                    },
                },
                '{"metadata":{"outer":{"a":{"enabled":true,'
                '"value":null},"z":1}},"model":"vector-model",'
                '"output":"object","prompt":"nested",'
                '"schema_version":"ai_output_v1",'
                '"ts_utc":"2026-01-02T03:04:05Z"}',
                "6237010ae049ad45a6d32a52b6c7c1a2ecf931833e3eeeb516a4558c6fcb45fc",
            ),
            (
                "arrays_booleans_and_null",
                {
                    "schema_version": "ai_output_v1",
                    "ts_utc": "2026-01-02T03:04:05Z",
                    "model": "vector-model",
                    "prompt": "array",
                    "output": "values",
                    "metadata": {
                        "items": [True, False, None, {"b": 2, "a": 1}]
                    },
                },
                '{"metadata":{"items":[true,false,null,{"a":1,"b":2}]},'
                '"model":"vector-model","output":"values",'
                '"prompt":"array","schema_version":"ai_output_v1",'
                '"ts_utc":"2026-01-02T03:04:05Z"}',
                "11c6ca4e2f276bf36d2086348a9d3486b14116b3638bda4b5f45cf490c4fe37c",
            ),
        )

        for name, payload, expected_canonical, expected_hash in vectors:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    input_path = Path(directory) / "vector.json"
                    input_path.write_text(
                        json.dumps(payload, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    result = _run("--print", input_path=input_path)

                    self.assertEqual(
                        result.returncode,
                        0,
                        result.stdout + result.stderr,
                    )
                    lines = result.stdout.splitlines()
                    self.assertEqual(lines[-2], expected_canonical)
                    self.assertEqual(
                        lines[-1],
                        f"AI_CANON_SHA256={expected_hash}",
                    )

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
