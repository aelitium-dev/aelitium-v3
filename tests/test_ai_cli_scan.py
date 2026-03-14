"""
Tests for `aelitium scan` — LLM call site coverage detection.
"""
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def _run(args):
    return subprocess.run(
        [sys.executable, "-m", "engine.ai_cli"] + args,
        capture_output=True, text=True, cwd=REPO,
    )


def _write(directory, filename, content):
    p = Path(directory) / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class TestScanEmpty(unittest.TestCase):
    def test_empty_directory_exits_0(self):
        with tempfile.TemporaryDirectory() as d:
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 0)
            self.assertIn("STATUS=OK", r.stdout)

    def test_empty_directory_json(self):
        with tempfile.TemporaryDirectory() as d:
            r = _run(["scan", d, "--json"])
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertEqual(data["total"], 0)
            self.assertEqual(data["status"], "OK")


class TestScanInstrumented(unittest.TestCase):
    def test_file_with_capture_adapter_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                result = capture_chat_completion(client, model, messages, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 0)
            self.assertIn("STATUS=OK", r.stdout)

    def test_instrumented_json_shows_instrumented_count(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                r = capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            r = _run(["scan", d, "--json"])
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertGreater(data["instrumented"], 0)
            self.assertEqual(data["uninstrumented"], 0)

    def test_anthropic_capture_message_is_instrumented(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "agent.py", """
                from engine.capture.anthropic import capture_message
                r = capture_message(client, model, messages, "./out")
                client.messages.create(model=m, messages=msgs, max_tokens=100)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 0)


class TestScanUninstrumented(unittest.TestCase):
    def test_bare_openai_call_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "worker.py", """
                from openai import OpenAI
                client = OpenAI()
                resp = client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 2)
            self.assertIn("STATUS=INCOMPLETE", r.stdout)
            self.assertIn("worker.py", r.stdout)

    def test_bare_anthropic_call_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "agent.py", """
                import anthropic
                client = anthropic.Anthropic()
                resp = client.messages.create(model="claude-3", messages=msgs, max_tokens=1024)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 2)
            self.assertIn("anthropic", r.stdout)
            self.assertIn("agent.py", r.stdout)

    def test_litellm_call_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "router.py", """
                import litellm
                response = litellm.completion(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 2)
            self.assertIn("litellm", r.stdout)

    def test_uninstrumented_json_structure(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "worker.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d, "--json"])
            self.assertEqual(r.returncode, 2)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "INCOMPLETE")
            self.assertEqual(data["uninstrumented"], 1)
            self.assertFalse(data["sites"][0]["instrumented"])
            self.assertEqual(data["sites"][0]["file"], "worker.py")

    def test_shows_line_number(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                # line 1
                # line 2
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertIn("app.py:", r.stdout)


class TestScanMixed(unittest.TestCase):
    def test_mixed_files_reports_both(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "good.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            _write(d, "bad.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertEqual(r.returncode, 2)
            self.assertIn("good.py", r.stdout)
            self.assertIn("bad.py", r.stdout)

    def test_json_mixed_counts(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "good.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            _write(d, "bad.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d, "--json"])
            data = json.loads(r.stdout)
            self.assertGreater(data["instrumented"], 0)
            self.assertGreater(data["uninstrumented"], 0)


class TestScanCoverage(unittest.TestCase):
    def test_coverage_shown_in_normal_output(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            _write(d, "bad.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d])
            self.assertIn("Coverage:", r.stdout)

    def test_coverage_pct_in_json_output(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            _write(d, "bad.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d, "--json"])
            data = json.loads(r.stdout)
            self.assertIn("coverage_pct", data)
            self.assertIsInstance(data["coverage_pct"], int)

    def test_full_coverage_is_100(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            r = _run(["scan", d, "--json"])
            data = json.loads(r.stdout)
            self.assertEqual(data["coverage_pct"], 100)


class TestScanCI(unittest.TestCase):
    def test_ci_flag_outputs_kv_format(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "worker.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d, "--ci"])
            self.assertIn("AELITIUM_SCAN_STATUS=", r.stdout)
            self.assertIn("AELITIUM_SCAN_TOTAL=", r.stdout)
            self.assertIn("AELITIUM_SCAN_MISSING=", r.stdout)
            self.assertIn("AELITIUM_SCAN_COVERAGE=", r.stdout)

    def test_ci_flag_incomplete_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "worker.py", """
                client.chat.completions.create(model="gpt-4o", messages=msgs)
            """)
            r = _run(["scan", d, "--ci"])
            self.assertEqual(r.returncode, 2)
            self.assertIn("AELITIUM_SCAN_STATUS=INCOMPLETE", r.stdout)

    def test_ci_flag_ok_exits_0(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "app.py", """
                from engine.capture.openai import capture_chat_completion
                capture_chat_completion(client, m, msgs, "./out")
                client.chat.completions.create(model=m, messages=msgs)
            """)
            r = _run(["scan", d, "--ci"])
            self.assertEqual(r.returncode, 0)
            self.assertIn("AELITIUM_SCAN_STATUS=OK", r.stdout)


class TestScanErrors(unittest.TestCase):
    def test_nonexistent_path_exits_2(self):
        r = _run(["scan", "/nonexistent/path/aelitium_test_xyz"])
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
