"""
Tests for `aelitium compare <bundle_a> <bundle_b>`.

Covers:
- same request, same response → UNCHANGED rc=0
- same request, different response → CHANGED rc=2
- different requests → NOT_COMPARABLE rc=1
- bundles without capture metadata (pack-produced) → NOT_COMPARABLE rc=1
- missing/invalid bundle → INVALID_BUNDLE rc=2
- --json output structure
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]


def _make_capture_bundle(outdir: Path, request_content: str, response_content: str) -> Path:
    """Create a capture bundle with given request and response text."""
    from engine.capture.openai import capture_chat_completion

    response = SimpleNamespace(
        id="resp_test", created=1710000000, model="gpt-4o-mini",
        choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content=response_content),
        )],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create.return_value = response

    capture_chat_completion(
        client, "gpt-4o-mini",
        [{"role": "user", "content": request_content}],
        outdir,
    )
    return outdir


def _pack(outdir: Path) -> None:
    """Pack the minimal fixture (no capture metadata)."""
    subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True, check=True, cwd=ROOT,
    )


def _compare(bundle_a: Path, bundle_b: Path, extra: list = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + ["compare", str(bundle_a), str(bundle_b)] + (extra or []),
        capture_output=True, text=True, cwd=ROOT,
    )


class TestCompareUnchanged(unittest.TestCase):
    """Same request, same response → UNCHANGED."""

    def test_same_request_same_response_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "What is 2+2?", "4")
            _make_capture_bundle(Path(d2), "What is 2+2?", "4")
            r = _compare(Path(d1), Path(d2))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("STATUS=UNCHANGED", r.stdout)
            self.assertIn("REQUEST_HASH=SAME", r.stdout)
            self.assertIn("RESPONSE_HASH=SAME", r.stdout)

    def test_unchanged_json_output(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "Hello", "Hi there")
            _make_capture_bundle(Path(d2), "Hello", "Hi there")
            r = _compare(Path(d1), Path(d2), ["--json"])
            self.assertEqual(r.returncode, 0)
            obj = json.loads(r.stdout.strip())
            self.assertEqual(obj["status"], "UNCHANGED")
            self.assertEqual(obj["request_hash"], "SAME")
            self.assertEqual(obj["response_hash"], "SAME")
            self.assertIn("interpretation", obj)


class TestCompareChanged(unittest.TestCase):
    """Same request, different response → CHANGED."""

    def test_same_request_different_response_is_changed(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "What is the capital of France?", "Paris")
            _make_capture_bundle(Path(d2), "What is the capital of France?", "Lyon")
            r = _compare(Path(d1), Path(d2))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("STATUS=CHANGED", r.stdout)
            self.assertIn("REQUEST_HASH=SAME", r.stdout)
            self.assertIn("RESPONSE_HASH=DIFFERENT", r.stdout)
            self.assertIn("BINDING_HASH=DIFFERENT", r.stdout)

    def test_changed_interpretation_present(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "Summarize this.", "Summary A")
            _make_capture_bundle(Path(d2), "Summarize this.", "Summary B")
            r = _compare(Path(d1), Path(d2))
            self.assertIn("Same request produced a different response", r.stdout)

    def test_changed_json_output(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "Q", "Answer A")
            _make_capture_bundle(Path(d2), "Q", "Answer B")
            r = _compare(Path(d1), Path(d2), ["--json"])
            self.assertEqual(r.returncode, 2)
            obj = json.loads(r.stdout.strip())
            self.assertEqual(obj["status"], "CHANGED")
            self.assertEqual(obj["request_hash"], "SAME")
            self.assertEqual(obj["response_hash"], "DIFFERENT")

    def test_changed_is_symmetric(self):
        """CHANGED regardless of which bundle is A or B."""
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "Q", "Answer A")
            _make_capture_bundle(Path(d2), "Q", "Answer B")
            r1 = _compare(Path(d1), Path(d2))
            r2 = _compare(Path(d2), Path(d1))
            self.assertEqual(r1.returncode, 2)
            self.assertEqual(r2.returncode, 2)
            self.assertIn("STATUS=CHANGED", r1.stdout)
            self.assertIn("STATUS=CHANGED", r2.stdout)


class TestCompareNotComparable(unittest.TestCase):
    """Different requests, or no capture metadata → NOT_COMPARABLE."""

    def test_different_requests_not_comparable(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d1), "Request A", "Response A")
            _make_capture_bundle(Path(d2), "Request B", "Response B")
            r = _compare(Path(d1), Path(d2))
            self.assertEqual(r.returncode, 1)
            self.assertIn("STATUS=NOT_COMPARABLE", r.stdout)
            self.assertIn("REQUEST_HASH=DIFFERENT", r.stdout)

    def test_pack_bundles_not_comparable(self):
        """Bundles from `aelitium pack` have no capture metadata."""
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _pack(Path(d1))
            _pack(Path(d2))
            r = _compare(Path(d1), Path(d2))
            self.assertEqual(r.returncode, 1)
            self.assertIn("NOT_COMPARABLE", r.stdout)

    def test_pack_vs_capture_not_comparable(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _pack(Path(d1))
            _make_capture_bundle(Path(d2), "Some question", "Some answer")
            r = _compare(Path(d1), Path(d2))
            self.assertEqual(r.returncode, 1)
            self.assertIn("NOT_COMPARABLE", r.stdout)


class TestCompareInvalid(unittest.TestCase):
    """Missing or invalid bundles → INVALID_BUNDLE."""

    def test_missing_bundle_a(self):
        with tempfile.TemporaryDirectory() as d2:
            _make_capture_bundle(Path(d2), "Q", "A")
            r = _compare(Path("/nonexistent/path"), Path(d2))
            self.assertEqual(r.returncode, 2)
            self.assertIn("INVALID_BUNDLE", r.stdout)

    def test_missing_bundle_b(self):
        with tempfile.TemporaryDirectory() as d1:
            _make_capture_bundle(Path(d1), "Q", "A")
            r = _compare(Path(d1), Path("/nonexistent/path"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("INVALID_BUNDLE", r.stdout)

    def test_no_traceback_on_invalid(self):
        r = _compare(Path("/bad/a"), Path("/bad/b"))
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
