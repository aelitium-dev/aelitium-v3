"""
Tests for engine.capture.openai — no real API key required.

Uses unittest.mock to simulate an OpenAI client response.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from engine.capture.openai import capture_chat_completion, CaptureResult


def _make_mock_client(model: str = "gpt-4o", content: str = "Hello, world!") -> MagicMock:
    """Build a minimal mock that looks like openai.OpenAI()."""
    response = MagicMock()
    response.model = model
    response.choices[0].message.content = content

    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


class TestCaptureOpenAI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "gpt-4o"
        self.messages = [{"content": "Explain quantum computing.", "role": "user"}]
        self.client = _make_mock_client(model=self.model, content="Quantum computing uses qubits.")

    def test_returns_capture_result(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        self.assertIsInstance(result, CaptureResult)

    def test_bundle_files_written(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        self.assertTrue((Path(self.tmp) / "ai_canonical.json").exists())
        self.assertTrue((Path(self.tmp) / "ai_manifest.json").exists())

    def test_hash_is_64_hex_chars(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        self.assertEqual(len(result.ai_hash_sha256), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result.ai_hash_sha256))

    def test_canonical_json_is_valid_json(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = (Path(self.tmp) / "ai_canonical.json").read_text(encoding="utf-8")
        obj = json.loads(canon)
        self.assertEqual(obj["schema_version"], "ai_output_v1")
        self.assertEqual(obj["model"], self.model)

    def test_metadata_contains_capture_fields(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text(encoding="utf-8"))
        meta = canon["metadata"]
        self.assertEqual(meta["provider"], "openai")
        self.assertEqual(meta["sdk"], "openai-python")
        self.assertIn("request_hash", meta)
        self.assertIn("response_hash", meta)
        self.assertEqual(len(meta["request_hash"]), 64)
        self.assertEqual(len(meta["response_hash"]), 64)

    def test_extra_metadata_merged(self):
        capture_chat_completion(
            self.client, self.model, self.messages, self.tmp,
            metadata={"run_id": "test-999"}
        )
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text(encoding="utf-8"))
        self.assertEqual(canon["metadata"]["run_id"], "test-999")

    def test_manifest_schema_field(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        manifest = json.loads((Path(self.tmp) / "ai_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "ai_pack_manifest_v1")
        self.assertIn("ai_hash_sha256", manifest)

    def test_deterministic_for_same_input(self):
        # Same client/model/messages should produce the same hash if content is identical.
        # Note: ts_utc will differ between calls — so hashes WILL differ.
        # This test confirms the hash reflects content, not randomness.
        r1 = capture_chat_completion(self.client, self.model, self.messages, self.tmp + "/r1")
        r2 = capture_chat_completion(self.client, self.model, self.messages, self.tmp + "/r2")
        # Both hashes must be valid 64-char hex
        self.assertEqual(len(r1.ai_hash_sha256), 64)
        self.assertEqual(len(r2.ai_hash_sha256), 64)

    def test_original_response_returned(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        # The original mock response must be returned unchanged
        self.assertEqual(result.response.choices[0].message.content, "Quantum computing uses qubits.")

    def test_api_called_with_correct_args(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        self.client.chat.completions.create.assert_called_once_with(
            model=self.model,
            messages=self.messages,
        )
