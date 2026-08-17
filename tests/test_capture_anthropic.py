import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

try:
    from engine.capture.anthropic import capture_message, CaptureResult
    from engine.capture.common import CaptureMetadataCollisionError
    from engine.ai_verify import verify_ai_bundle
    from engine.invocation import (
        MODE_SYNC_NON_STREAMING,
        SURFACE_ANTHROPIC_MESSAGES,
        parse_invocation_identity,
    )
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

anthropic_required = unittest.skipUnless(
    _ANTHROPIC_AVAILABLE,
    "anthropic package not installed — skipping (install with: pip install aelitium[anthropic])"
)


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


@anthropic_required
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

    def test_all_adapter_owned_metadata_collisions_raise(self):
        reserved_keys = (
            "provider",
            "sdk",
            "request_hash",
            "response_hash",
            "binding_hash",
            "response_id",
            "finish_reason",
            "usage",
            "captured_at_utc",
            "invocation_identity",
        )
        for key in reserved_keys:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as out_dir:
                with self.assertRaises(CaptureMetadataCollisionError) as context:
                    capture_message(
                        self.client,
                        self.model,
                        self.messages,
                        out_dir,
                        metadata={key: "caller-value"},
                    )
                self.assertEqual(context.exception.offending_keys, (key,))

    def test_custom_metadata_preserves_owned_hashes_and_verifies(self):
        with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as custom_dir:
            capture_message(
                self.client,
                self.model,
                self.messages,
                base_dir,
            )
            capture_message(
                self.client,
                self.model,
                self.messages,
                custom_dir,
                metadata={"run_id": "anthropic-123"},
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
            self.assertEqual(custom["provider"], "anthropic")
            self.assertEqual(custom["run_id"], "anthropic-123")
            self.assertTrue(verify_ai_bundle(custom_dir).valid)


@anthropic_required
class TestCaptureAnthropicInvocationIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "claude-3-5-sonnet-20241022"
        self.messages = [{"role": "user", "content": "What is 2+2?"}]
        self.client, self.response = _make_mock_anthropic_client(
            self.model, "The answer is 4."
        )

    def test_invocation_identity_present_and_parses(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        stored = canon["metadata"]["invocation_identity"]

        identity = parse_invocation_identity(stored)
        self.assertEqual(identity.surface, SURFACE_ANTHROPIC_MESSAGES)
        self.assertEqual(identity.mode, MODE_SYNC_NON_STREAMING)
        request = identity.to_stored_object()["request"]
        self.assertEqual(request["model"], self.model)
        self.assertEqual(request["messages"], self.messages)

    def test_omitted_max_tokens_records_adapter_default_1024(self):
        # No max_tokens argument supplied by the caller -- the adapter's own
        # default (1024) is what is actually emitted to the SDK call, and
        # must be recorded as such, not treated as absent.
        capture_message(self.client, self.model, self.messages, self.tmp)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        stored = canon["metadata"]["invocation_identity"]
        self.assertEqual(
            stored["request"]["parameters"]["max_tokens"], 1024
        )
        self.client.messages.create.assert_called_once_with(
            model=self.model, messages=self.messages, max_tokens=1024
        )

    def test_explicit_max_tokens_changes_invocation_hash_not_request_hash(self):
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            client_a, _ = _make_mock_anthropic_client(self.model, "The answer is 4.")
            client_b, _ = _make_mock_anthropic_client(self.model, "The answer is 4.")
            capture_message(
                client_a, self.model, self.messages, dir_a, max_tokens=128
            )
            capture_message(
                client_b, self.model, self.messages, dir_b, max_tokens=4096
            )
            client_a.messages.create.assert_called_once_with(
                model=self.model, messages=self.messages, max_tokens=128
            )
            client_b.messages.create.assert_called_once_with(
                model=self.model, messages=self.messages, max_tokens=4096
            )

            meta_a = json.loads(
                (Path(dir_a) / "ai_canonical.json").read_text()
            )["metadata"]
            meta_b = json.loads(
                (Path(dir_b) / "ai_canonical.json").read_text()
            )["metadata"]
            self.assertEqual(meta_a["request_hash"], meta_b["request_hash"])
            self.assertNotEqual(
                meta_a["invocation_identity"]["hash_sha256"],
                meta_b["invocation_identity"]["hash_sha256"],
            )

    def test_bundle_with_invocation_identity_verifies(self):
        capture_message(self.client, self.model, self.messages, self.tmp)
        self.assertTrue(verify_ai_bundle(self.tmp).valid)
