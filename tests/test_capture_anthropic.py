import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from engine.capture.anthropic import capture_message, CaptureResult


def _make_mock_anthropic_client(model="claude-3-5-sonnet-20241022", content="Hello from Claude"):
    response = SimpleNamespace(
        id="msg_test123",
        model=model,
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=content)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    client = MagicMock()
    client.messages.create.return_value = response
    return client, response


class TestCaptureAnthropic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "claude-3-5-sonnet-20241022"
        self.messages = [{"role": "user", "content": "What is 2+2?"}]
        self.client, self.response = _make_mock_anthropic_client(self.model, "The answer is 4.")

    def test_returns_capture_result(self):
        result = capture_message(self.client, self.model, self.messages, self.tmp)
        self.assertIsInstance(result, CaptureResult)

    def test_bundle_files_written(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        self.assertTrue((Path(self.tmp) / "ai_canonical.json").exists())
        self.assertTrue((Path(self.tmp) / "ai_manifest.json").exists())

    def test_hash_is_64_hex_chars(self):
        result = capture_message(self.client, self.model, self.messages, self.tmp)
        self.assertEqual(len(result.ai_hash_sha256), 64)

    def test_metadata_contains_capture_fields(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta["provider"], "anthropic")
        self.assertIn("request_hash", meta)
        self.assertIn("response_hash", meta)
        self.assertIn("binding_hash", meta)
        self.assertEqual(len(meta["binding_hash"]), 64)

    def test_provider_metadata_present(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertEqual(meta.get("response_id"), "msg_test123")
        self.assertEqual(meta.get("finish_reason"), "end_turn")

    def test_output_extracted_correctly(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertEqual(canon["output"], "The answer is 4.")
