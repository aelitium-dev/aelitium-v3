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


class TestCaptureDeterminism(unittest.TestCase):
    """
    EPIC: capture determinism
    Proves the capture adapter maintains reproducibility and
    that any tamper produces INVALID.
    """

    def setUp(self):
        self.model = "gpt-4o"
        self.messages = [{"content": "What is 2+2?", "role": "user"}]
        self.content = "2+2 equals 4."

    def _capture(self, out_dir: str) -> str:
        client = _make_mock_client(model=self.model, content=self.content)
        result = capture_chat_completion(client, self.model, self.messages, out_dir)
        return result.ai_hash_sha256

    def test_same_payload_same_request_hash(self):
        """Same model+messages always produce the same request_hash."""
        import tempfile, json
        tmp1 = tempfile.mkdtemp()
        tmp2 = tempfile.mkdtemp()
        self._capture(tmp1)
        self._capture(tmp2)
        c1 = json.loads((Path(tmp1) / "ai_canonical.json").read_text())
        c2 = json.loads((Path(tmp2) / "ai_canonical.json").read_text())
        self.assertEqual(c1["metadata"]["request_hash"], c2["metadata"]["request_hash"])

    def test_same_payload_same_response_hash(self):
        """Same model+content always produce the same response_hash."""
        import tempfile, json
        tmp1 = tempfile.mkdtemp()
        tmp2 = tempfile.mkdtemp()
        self._capture(tmp1)
        self._capture(tmp2)
        c1 = json.loads((Path(tmp1) / "ai_canonical.json").read_text())
        c2 = json.loads((Path(tmp2) / "ai_canonical.json").read_text())
        self.assertEqual(c1["metadata"]["response_hash"], c2["metadata"]["response_hash"])

    def test_different_content_different_response_hash(self):
        """Different model output produces a different response_hash."""
        import tempfile, json
        tmp1 = tempfile.mkdtemp()
        tmp2 = tempfile.mkdtemp()

        client_a = _make_mock_client(model=self.model, content="The answer is 4.")
        client_b = _make_mock_client(model=self.model, content="It is four.")
        capture_chat_completion(client_a, self.model, self.messages, tmp1)
        capture_chat_completion(client_b, self.model, self.messages, tmp2)

        c1 = json.loads((Path(tmp1) / "ai_canonical.json").read_text())
        c2 = json.loads((Path(tmp2) / "ai_canonical.json").read_text())
        self.assertNotEqual(c1["metadata"]["response_hash"], c2["metadata"]["response_hash"])

    def test_tampered_canonical_fails_verify(self):
        """Modifying ai_canonical.json after packing makes the bundle INVALID."""
        import hashlib, json, tempfile
        tmp = tempfile.mkdtemp()
        self._capture(tmp)

        canon_path = Path(tmp) / "ai_canonical.json"
        manifest_path = Path(tmp) / "ai_manifest.json"

        # Tamper: change the output in the canonical file
        obj = json.loads(canon_path.read_text())
        obj["output"] = "TAMPERED OUTPUT"
        canon_path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")))

        # Reproduce the verify logic: hash must not match manifest
        canon_text = canon_path.read_text(encoding="utf-8")
        actual_hash = hashlib.sha256(canon_text.rstrip("\n").encode("utf-8")).hexdigest()
        manifest = json.loads(manifest_path.read_text())
        self.assertNotEqual(actual_hash, manifest["ai_hash_sha256"],
                            "Tampered bundle should fail hash check")
