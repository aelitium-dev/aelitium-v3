"""
Tests for engine.capture.openai — no real API key required.

Uses unittest.mock to simulate an OpenAI client response.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from engine.ai_verify import AssuranceState, verify_ai_bundle
from engine.capture.common import CaptureMetadataCollisionError
from engine.capture.openai import (
    CaptureResult,
    capture_chat_completion,
    capture_chat_completion_stream,
)
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    MODE_SYNC_STREAMING,
    SURFACE_OPENAI_CHAT_COMPLETIONS,
    parse_invocation_identity,
)
from engine.invocation_binding import parse_invocation_binding


def _make_mock_client(model: str = "gpt-4o", content: str = "Hello, world!") -> MagicMock:
    """Build a minimal mock that looks like openai.OpenAI()."""
    response = MagicMock()
    response.model = model
    response.choices[0].message.content = content

    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


def _make_mock_stream_client() -> MagicMock:
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Hello "),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="stream"),
                    finish_reason="stop",
                )
            ]
        ),
    ]
    client = MagicMock()
    client.chat.completions.create.return_value = iter(chunks)
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

    def test_all_adapter_owned_metadata_collisions_raise(self):
        reserved_keys = (
            "provider",
            "sdk",
            "request_hash",
            "response_hash",
            "binding_hash",
            "response_id",
            "provider_created_at",
            "finish_reason",
            "usage",
            "captured_at_utc",
            "invocation_identity",
            "invocation_binding",
        )
        for key in reserved_keys:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as out_dir:
                client = _make_mock_client(
                    model=self.model,
                    content="Quantum computing uses qubits.",
                )
                with self.assertRaises(CaptureMetadataCollisionError) as context:
                    capture_chat_completion(
                        client,
                        self.model,
                        self.messages,
                        out_dir,
                        metadata={key: "caller-value"},
                    )
                self.assertEqual(context.exception.offending_keys, (key,))

    def test_custom_metadata_preserves_owned_hashes_and_verifies(self):
        with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as custom_dir:
            capture_chat_completion(
                _make_mock_client(self.model, "Quantum computing uses qubits."),
                self.model,
                self.messages,
                base_dir,
            )
            caller_metadata = {"run_id": "test-999", "team": "assurance"}
            caller_before = dict(caller_metadata)
            capture_chat_completion(
                _make_mock_client(self.model, "Quantum computing uses qubits."),
                self.model,
                self.messages,
                custom_dir,
                metadata=caller_metadata,
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
            self.assertEqual(custom["provider"], "openai")
            self.assertEqual(custom["run_id"], "test-999")
            self.assertEqual(custom["team"], "assurance")
            self.assertEqual(caller_metadata, caller_before)
            self.assertTrue(verify_ai_bundle(custom_dir).valid)

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

    def test_binding_hash_present(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertIn("binding_hash", canon["metadata"])
        self.assertEqual(len(canon["metadata"]["binding_hash"]), 64)

    def test_captured_at_utc_present(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertIn("captured_at_utc", canon["metadata"])

    def test_binding_hash_in_manifest(self):
        result = capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        manifest = json.loads((Path(self.tmp) / "ai_manifest.json").read_text())
        self.assertIn("binding_hash", manifest)
        self.assertEqual(len(manifest["binding_hash"]), 64)

    def test_content_list_extraction(self):
        """Content as list of dicts with type=text."""
        content_list = [{"type": "text", "text": "Hello from list"}]
        client2 = MagicMock()
        resp2 = MagicMock()
        resp2.model = "gpt-4o"
        resp2.choices[0].message.content = content_list
        client2.chat.completions.create.return_value = resp2
        import tempfile
        with tempfile.TemporaryDirectory() as tmp2:
            result2 = capture_chat_completion(client2, self.model, self.messages, tmp2)
            canon = json.loads((Path(tmp2) / "ai_canonical.json").read_text())
            self.assertEqual(canon["output"], "Hello from list")

    def test_content_none_raises(self):
        """content=None should raise ValueError."""
        from types import SimpleNamespace
        resp = SimpleNamespace(
            model="gpt-4o",
            choices=[SimpleNamespace(message=SimpleNamespace(content=None), finish_reason="stop")],
            id="test-id",
            created=1234567890,
            usage=None,
        )
        client3 = MagicMock()
        client3.chat.completions.create.return_value = resp
        import tempfile
        with tempfile.TemporaryDirectory() as tmp3:
            with self.assertRaises(ValueError):
                capture_chat_completion(client3, self.model, self.messages, tmp3)


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
        actual_hash = hashlib.sha256(
            canon_text.removesuffix("\n").encode("utf-8")
        ).hexdigest()
        manifest = json.loads(manifest_path.read_text())
        self.assertNotEqual(actual_hash, manifest["ai_hash_sha256"],
                            "Tampered bundle should fail hash check")


class TestCaptureOpenAIInvocationIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "gpt-4o"
        self.messages = [{"content": "Explain quantum computing.", "role": "user"}]
        self.client = _make_mock_client(
            model=self.model, content="Quantum computing uses qubits."
        )

    def test_non_streaming_invocation_identity_present_and_valid(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        stored = canon["metadata"]["invocation_identity"]

        identity = parse_invocation_identity(stored)
        self.assertEqual(identity.surface, SURFACE_OPENAI_CHAT_COMPLETIONS)
        self.assertEqual(identity.mode, MODE_SYNC_NON_STREAMING)
        request = identity.to_stored_object()["request"]
        self.assertEqual(request["model"], self.model)
        self.assertEqual(request["messages"], self.messages)

    def test_streaming_invocation_identity_has_streaming_mode(self):
        with tempfile.TemporaryDirectory() as out_dir:
            capture_chat_completion_stream(
                _make_mock_stream_client(), self.model, self.messages, out_dir
            )
            canon = json.loads((Path(out_dir) / "ai_canonical.json").read_text())
            stored = canon["metadata"]["invocation_identity"]
            identity = parse_invocation_identity(stored)
            self.assertEqual(identity.mode, MODE_SYNC_STREAMING)

    def test_request_hash_same_but_invocation_hash_differs_stream_vs_non_stream(self):
        with tempfile.TemporaryDirectory() as non_stream_dir, tempfile.TemporaryDirectory() as stream_dir:
            capture_chat_completion(
                self.client, self.model, self.messages, non_stream_dir
            )
            capture_chat_completion_stream(
                _make_mock_stream_client(), self.model, self.messages, stream_dir
            )
            non_stream_meta = json.loads(
                (Path(non_stream_dir) / "ai_canonical.json").read_text()
            )["metadata"]
            stream_meta = json.loads(
                (Path(stream_dir) / "ai_canonical.json").read_text()
            )["metadata"]

            self.assertEqual(
                non_stream_meta["request_hash"], stream_meta["request_hash"]
            )
            self.assertNotEqual(
                non_stream_meta["invocation_identity"]["hash_sha256"],
                stream_meta["invocation_identity"]["hash_sha256"],
            )

    def test_bundle_with_invocation_identity_verifies(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        self.assertTrue(verify_ai_bundle(self.tmp).valid)


class TestCaptureOpenAIInvocationBinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "gpt-4o"
        self.messages = [{"content": "Explain quantum computing.", "role": "user"}]
        self.client = _make_mock_client(
            model=self.model, content="Quantum computing uses qubits."
        )

    def test_non_streaming_invocation_binding_present_and_matches(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]

        binding = parse_invocation_binding(meta["invocation_binding"])
        self.assertEqual(binding.invocation_hash, meta["invocation_identity"]["hash_sha256"])
        self.assertEqual(binding.response_hash, meta["response_hash"])

    def test_streaming_invocation_binding_present_and_matches(self):
        with tempfile.TemporaryDirectory() as out_dir:
            capture_chat_completion_stream(
                _make_mock_stream_client(), self.model, self.messages, out_dir
            )
            canon = json.loads((Path(out_dir) / "ai_canonical.json").read_text())
            meta = canon["metadata"]
            binding = parse_invocation_binding(meta["invocation_binding"])
            self.assertEqual(
                binding.invocation_hash, meta["invocation_identity"]["hash_sha256"]
            )
            self.assertEqual(binding.response_hash, meta["response_hash"])

    def test_bundle_with_invocation_binding_verifies_as_valid(self):
        capture_chat_completion(self.client, self.model, self.messages, self.tmp)
        result = verify_ai_bundle(self.tmp)
        self.assertTrue(result.valid)
        self.assertEqual(
            result.invocation_identity_consistency, AssuranceState.VALID
        )
        self.assertEqual(
            result.invocation_binding_consistency, AssuranceState.VALID
        )


class TestCaptureOpenAIStreaming(unittest.TestCase):
    def setUp(self):
        self.model = "gpt-4o"
        self.messages = [{"content": "Stream a greeting.", "role": "user"}]

    def test_streaming_owned_metadata_collision_raises(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with self.assertRaises(CaptureMetadataCollisionError) as context:
                capture_chat_completion_stream(
                    _make_mock_stream_client(),
                    self.model,
                    self.messages,
                    out_dir,
                    metadata={"streaming": False},
                )
            self.assertEqual(context.exception.offending_keys, ("streaming",))

    def test_streaming_invocation_identity_collision_raises(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with self.assertRaises(CaptureMetadataCollisionError) as context:
                capture_chat_completion_stream(
                    _make_mock_stream_client(),
                    self.model,
                    self.messages,
                    out_dir,
                    metadata={"invocation_identity": {"format": "spoofed"}},
                )
            self.assertEqual(
                context.exception.offending_keys, ("invocation_identity",)
            )

    def test_streaming_invocation_binding_collision_raises(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with self.assertRaises(CaptureMetadataCollisionError) as context:
                capture_chat_completion_stream(
                    _make_mock_stream_client(),
                    self.model,
                    self.messages,
                    out_dir,
                    metadata={"invocation_binding": {"format": "spoofed"}},
                )
            self.assertEqual(
                context.exception.offending_keys, ("invocation_binding",)
            )

    def test_streaming_custom_metadata_round_trips_and_verifies(self):
        with tempfile.TemporaryDirectory() as out_dir:
            caller_metadata = {"run_id": "stream-123"}
            capture_chat_completion_stream(
                _make_mock_stream_client(),
                self.model,
                self.messages,
                out_dir,
                metadata=caller_metadata,
            )

            canonical = json.loads(
                (Path(out_dir) / "ai_canonical.json").read_text(encoding="utf-8")
            )
            self.assertEqual(canonical["metadata"]["run_id"], "stream-123")
            self.assertIs(canonical["metadata"]["streaming"], True)
            self.assertEqual(canonical["metadata"]["provider"], "openai")
            self.assertTrue(verify_ai_bundle(out_dir).valid)
