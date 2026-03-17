"""
Tests for engine.capture.litellm.enable() — no real API key or litellm install required.

Injects a stub litellm module into sys.modules so the adapter can be imported
and tested without installing the litellm package.

Invariants under test:
  1. wrapped() returns identical response to original
  2. bundle written to <out_dir>/<ai_hash_sha256>/ (content-addressed)
  3. multiple calls → separate dirs (no overwrite)
  4. streaming → pass-through + warning (fail-open) or raise (strict)
  5. LLM errors always propagate
  6. capture failure → warning (fail-open) or raise (strict), response always returned
  7. original is only called once per wrapped call
"""

import importlib
import json
import sys
import tempfile
import types
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_mock_response(model="openai/gpt-4o", content="Hello"):
    message = SimpleNamespace(content=content, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8)
    return SimpleNamespace(id="chatcmpl-enable-test", model=model, choices=[choice], usage=usage)


def _fresh_litellm_stub():
    stub = MagicMock()
    stub.__name__ = "litellm"
    stub.completion = MagicMock(return_value=_make_mock_response())
    return stub


class TestEnableLiteLLM(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Provide a fresh stub so each test starts with a clean litellm mock
        self._stub = _fresh_litellm_stub()
        sys.modules["litellm"] = self._stub

        # Re-import module to get a clean copy with fresh state
        import engine.capture.litellm as _mod
        importlib.reload(_mod)
        self._mod = _mod

    def _enable(self, **kwargs):
        self._mod.enable(out_dir=self.tmp, **kwargs)

    def _call(self, model="openai/gpt-4o", messages=None, **kwargs):
        if messages is None:
            messages = [{"role": "user", "content": "hi"}]
        return self._stub.completion(model=model, messages=messages, **kwargs)

    # --- transparency ---

    def test_returns_original_response(self):
        expected = _make_mock_response(content="exact content")
        self._stub.completion.return_value = expected
        self._enable()
        result = self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        self.assertIs(result, expected)

    def test_llm_called_exactly_once(self):
        original = MagicMock(return_value=_make_mock_response())
        self._stub.completion = original
        self._enable()
        self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(original.call_count, 1)

    # --- bundle written ---

    def test_bundle_written_to_content_addressed_subdir(self):
        self._enable()
        self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        subdirs = [p for p in self.tmp.iterdir() if p.is_dir() and not p.name.startswith("_tmp_")]
        self.assertEqual(len(subdirs), 1)
        self.assertEqual(len(subdirs[0].name), 64)  # sha256 hex

    def test_bundle_files_present(self):
        self._enable()
        self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        subdirs = [p for p in self.tmp.iterdir() if p.is_dir()]
        bundle_dir = subdirs[0]
        self.assertTrue((bundle_dir / "ai_canonical.json").exists())
        self.assertTrue((bundle_dir / "ai_manifest.json").exists())

    def test_no_tmp_dirs_left_on_success(self):
        self._enable()
        self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        tmp_dirs = [p for p in self.tmp.iterdir() if p.name.startswith("_tmp_")]
        self.assertEqual(tmp_dirs, [])

    def test_multiple_calls_create_separate_dirs(self):
        self._enable()
        msgs1 = [{"role": "user", "content": "question one"}]
        msgs2 = [{"role": "user", "content": "question two"}]
        self._stub.completion.side_effect = [
            _make_mock_response(content="answer one"),
            _make_mock_response(content="answer two"),
        ]
        self._stub.completion(model="openai/gpt-4o", messages=msgs1)
        self._stub.completion(model="openai/gpt-4o", messages=msgs2)
        subdirs = [p for p in self.tmp.iterdir() if p.is_dir()]
        self.assertEqual(len(subdirs), 2)
        self.assertNotEqual(subdirs[0].name, subdirs[1].name)

    # --- streaming pass-through ---

    def test_streaming_passthrough_warns(self):
        self._enable()
        stream_response = object()
        original_mock = MagicMock(return_value=stream_response)
        self._stub.completion = original_mock
        # re-enable so _wrapped references original_mock
        self._mod.enable(out_dir=self.tmp)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = self._stub.completion(model="openai/gpt-4o", messages=[], stream=True)
        self.assertIs(result, stream_response)
        self.assertEqual(len(w), 1)
        self.assertIn("streaming", str(w[0].message).lower())

    def test_streaming_strict_raises(self):
        self._mod.enable(out_dir=self.tmp, strict=True)
        with self.assertRaises(RuntimeError) as ctx:
            self._stub.completion(model="openai/gpt-4o", messages=[], stream=True)
        self.assertIn("stream", str(ctx.exception).lower())

    # --- LLM errors propagate ---

    def test_llm_error_propagates(self):
        # side_effect must be set before enable() — wrapper captures original at that point
        self._stub.completion.side_effect = ConnectionError("API unreachable")
        self._enable()
        with self.assertRaises(ConnectionError):
            self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])

    # --- capture failure modes ---

    def test_capture_failure_failopen_returns_response(self):
        expected = _make_mock_response(content="fail-open test")
        original_mock = MagicMock(return_value=expected)
        self._stub.completion = original_mock
        self._mod.enable(out_dir=self.tmp)

        with patch.object(self._mod, "capture_completion", side_effect=OSError("disk full")):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        self.assertIs(result, expected)
        self.assertEqual(len(w), 1)
        self.assertIn("capture failed", str(w[0].message).lower())

    def test_capture_failure_strict_raises(self):
        original_mock = MagicMock(return_value=_make_mock_response())
        self._stub.completion = original_mock
        self._mod.enable(out_dir=self.tmp, strict=True)

        with patch.object(self._mod, "capture_completion", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])

    def test_capture_failure_no_tmp_dir_left(self):
        original_mock = MagicMock(return_value=_make_mock_response())
        self._stub.completion = original_mock
        self._mod.enable(out_dir=self.tmp)

        with patch.object(self._mod, "capture_completion", side_effect=OSError("disk full")):
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        tmp_dirs = [p for p in self.tmp.iterdir() if p.name.startswith("_tmp_")]
        self.assertEqual(tmp_dirs, [])

    # --- binding_hash in bundle ---

    def test_bundle_contains_binding_hash(self):
        self._enable()
        self._stub.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
        subdirs = [p for p in self.tmp.iterdir() if p.is_dir()]
        manifest = json.loads((subdirs[0] / "ai_manifest.json").read_text())
        self.assertIn("binding_hash", manifest)
        self.assertEqual(len(manifest["binding_hash"]), 64)

    # --- positional args ---

    def test_positional_args_normalised(self):
        """enable() must handle litellm.completion("model", messages) positional style."""
        original_mock = MagicMock(return_value=_make_mock_response())
        self._stub.completion = original_mock
        self._mod.enable(out_dir=self.tmp)
        msgs = [{"role": "user", "content": "positional"}]
        result = self._stub.completion("openai/gpt-4o", msgs)
        self.assertIsNotNone(result)
        subdirs = [p for p in self.tmp.iterdir() if p.is_dir()]
        self.assertEqual(len(subdirs), 1)
