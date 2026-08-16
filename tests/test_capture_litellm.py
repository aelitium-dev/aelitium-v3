"""
Tests for engine.capture.litellm — no real API key or litellm install required.

Injects a stub litellm module into sys.modules so the adapter can be imported
and tested without installing the litellm package.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# --- inject stub litellm module before importing the adapter ---
_litellm_stub = MagicMock()
_litellm_stub.__name__ = "litellm"
sys.modules.setdefault("litellm", _litellm_stub)

from engine.ai_verify import verify_ai_bundle  # noqa: E402
from engine.capture.common import CaptureMetadataCollisionError  # noqa: E402
from engine.capture.litellm import capture_completion, CaptureResult  # noqa: E402


def _make_mock_response(model="openai/gpt-4o", content="Hello from LiteLLM"):
    """Build an OpenAI-compatible mock response as LiteLLM would return."""
    message = SimpleNamespace(content=content, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(
        id="chatcmpl-test123",
        model=model,
        choices=[choice],
        usage=usage,
    )


class TestCaptureLiteLLM(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "openai/gpt-4o"
        self.messages = [{"role": "user", "content": "What is 2+2?"}]
        self.mock_response = _make_mock_response(self.model, "The answer is 4.")
        _litellm_stub.completion.return_value = self.mock_response

    def _call(self, model=None, messages=None, out_dir=None, metadata=None):
        return capture_completion(
            model=model or self.model,
            messages=messages or self.messages,
            out_dir=out_dir or self.tmp,
            metadata=metadata,
        )

    def test_returns_capture_result(self):
        result = self._call()
        self.assertIsInstance(result, CaptureResult)

    def test_bundle_files_written(self):
        self._call()
        self.assertTrue((Path(self.tmp) / "ai_canonical.json").exists())
        self.assertTrue((Path(self.tmp) / "ai_manifest.json").exists())

    def test_hash_is_64_hex_chars(self):
        result = self._call()
        self.assertEqual(len(result.ai_hash_sha256), 64)

    def test_metadata_contains_capture_fields(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta["provider"], "litellm")
        self.assertIn("request_hash", meta)
        self.assertIn("response_hash", meta)
        self.assertIn("binding_hash", meta)
        self.assertEqual(len(meta["binding_hash"]), 64)

    def test_model_requested_and_confirmed_recorded(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta["model_requested"], "openai/gpt-4o")
        self.assertEqual(meta["model_confirmed"], "openai/gpt-4o")

    def test_output_extracted_correctly(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertEqual(canon["output"], "The answer is 4.")

    def test_provider_metadata_present(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta.get("response_id"), "chatcmpl-test123")
        self.assertEqual(meta.get("finish_reason"), "stop")

    def test_usage_recorded(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        usage = canon["metadata"]["usage"]
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 15)

    def test_manifest_contains_binding_hash(self):
        self._call()
        manifest = json.loads((Path(self.tmp) / "ai_manifest.json").read_text())
        self.assertIn("binding_hash", manifest)
        self.assertEqual(len(manifest["binding_hash"]), 64)

    def test_binding_hash_deterministic(self):
        """Same request+response always produces same binding_hash."""
        self._call()
        tmp2 = tempfile.mkdtemp()
        self._call(out_dir=tmp2)
        m1 = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        m2 = json.loads((Path(tmp2) / "ai_canonical.json").read_text())
        self.assertEqual(
            m1["metadata"]["binding_hash"],
            m2["metadata"]["binding_hash"],
        )

    def test_extra_metadata_merged(self):
        self._call(metadata={"experiment": "test-run-1"})
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertEqual(canon["metadata"]["experiment"], "test-run-1")

    def test_all_adapter_owned_metadata_collisions_raise(self):
        reserved_keys = (
            "provider",
            "sdk",
            "model_requested",
            "model_confirmed",
            "request_hash",
            "response_hash",
            "binding_hash",
            "response_id",
            "finish_reason",
            "usage",
            "captured_at_utc",
        )
        for key in reserved_keys:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as out_dir:
                with self.assertRaises(CaptureMetadataCollisionError) as context:
                    self._call(
                        out_dir=out_dir,
                        metadata={key: "caller-value"},
                    )
                self.assertEqual(context.exception.offending_keys, (key,))

    def test_custom_metadata_preserves_owned_hashes_and_verifies(self):
        with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as custom_dir:
            self._call(out_dir=base_dir)
            self._call(
                out_dir=custom_dir,
                metadata={"experiment": "test-run-1", "team": "assurance"},
            )

            base = json.loads(
                (Path(base_dir) / "ai_canonical.json").read_text(encoding="utf-8")
            )["metadata"]
            custom = json.loads(
                (Path(custom_dir) / "ai_canonical.json").read_text(
                    encoding="utf-8"
                )
            )["metadata"]
            for key in ("request_hash", "response_hash", "binding_hash"):
                self.assertEqual(custom[key], base[key])
            self.assertEqual(custom["provider"], "litellm")
            self.assertEqual(custom["model_requested"], self.model)
            self.assertEqual(custom["experiment"], "test-run-1")
            self.assertEqual(custom["team"], "assurance")
            self.assertTrue(verify_ai_bundle(custom_dir).valid)

    def test_model_confirmed_differs_when_provider_returns_different(self):
        """Provider may return model name without prefix — both are recorded."""
        _litellm_stub.completion.return_value = _make_mock_response(
            model="gpt-4o", content="Hi"
        )
        tmp = tempfile.mkdtemp()
        capture_completion(model="openai/gpt-4o", messages=self.messages, out_dir=tmp)
        canon = json.loads((Path(tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta["model_requested"], "openai/gpt-4o")
        self.assertEqual(meta["model_confirmed"], "gpt-4o")

    def test_response_is_original_object(self):
        result = self._call()
        self.assertIs(result.response, self.mock_response)
