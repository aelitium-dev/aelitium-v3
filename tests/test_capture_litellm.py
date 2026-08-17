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
from engine.invocation import (  # noqa: E402
    MODE_SYNC_NON_STREAMING,
    SURFACE_LITELLM_COMPLETION,
    parse_invocation_identity,
)


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

    def _call(
        self,
        model=None,
        messages=None,
        out_dir=None,
        metadata=None,
        **litellm_kwargs,
    ):
        return capture_completion(
            model=model or self.model,
            messages=messages or self.messages,
            out_dir=out_dir or self.tmp,
            metadata=metadata,
            **litellm_kwargs,
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

    def test_v1_request_hash_excludes_forwarded_behavior_parameters(self):
        """Characterize frozen v1 identity, not desired future semantics."""
        _litellm_stub.completion.reset_mock()
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            self._call(
                out_dir=first_dir,
                temperature=0.0,
                max_tokens=32,
            )
            self._call(
                out_dir=second_dir,
                temperature=1.0,
                max_tokens=128,
            )

            calls = _litellm_stub.completion.call_args_list
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].kwargs["temperature"], 0.0)
            self.assertEqual(calls[0].kwargs["max_tokens"], 32)
            self.assertEqual(calls[1].kwargs["temperature"], 1.0)
            self.assertEqual(calls[1].kwargs["max_tokens"], 128)

            first_metadata = json.loads(
                (Path(first_dir) / "ai_canonical.json").read_text(
                    encoding="utf-8"
                )
            )["metadata"]
            second_metadata = json.loads(
                (Path(second_dir) / "ai_canonical.json").read_text(
                    encoding="utf-8"
                )
            )["metadata"]
            self.assertEqual(
                first_metadata["request_hash"],
                second_metadata["request_hash"],
            )
            self.assertTrue(verify_ai_bundle(first_dir).valid)
            self.assertTrue(verify_ai_bundle(second_dir).valid)

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
            "invocation_identity",
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


class TestCaptureLiteLLMInvocationIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.model = "openai/gpt-4o"
        self.messages = [{"role": "user", "content": "What is 2+2?"}]
        self.mock_response = _make_mock_response(self.model, "The answer is 4.")
        _litellm_stub.completion.reset_mock(return_value=True, side_effect=True)
        _litellm_stub.completion.return_value = self.mock_response

    def _call(self, out_dir=None, **litellm_kwargs):
        return capture_completion(
            model=self.model,
            messages=self.messages,
            out_dir=out_dir or self.tmp,
            **litellm_kwargs,
        )

    def test_allowed_parameters_stored_exactly(self):
        self._call(
            temperature=0.2,
            max_tokens=64,
            top_p=0.9,
            seed=7,
            stop=["\n"],
        )
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        stored = canon["metadata"]["invocation_identity"]
        identity = parse_invocation_identity(stored)
        self.assertEqual(identity.surface, SURFACE_LITELLM_COMPLETION)
        self.assertEqual(identity.mode, MODE_SYNC_NON_STREAMING)
        params = identity.to_stored_object()["request"]["parameters"]
        self.assertEqual(
            params,
            {
                "temperature": 0.2,
                "max_tokens": 64,
                "top_p": 0.9,
                "seed": 7,
                "stop": ["\n"],
            },
        )

    def test_changing_allowed_parameter_changes_invocation_hash_not_request_hash(
        self,
    ):
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            self._call(out_dir=dir_a, temperature=0.0)
            self._call(out_dir=dir_b, temperature=1.0)
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

    def test_explicit_null_parameter_preserved(self):
        self._call(seed=None)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        params = canon["metadata"]["invocation_identity"]["request"]["parameters"]
        self.assertIn("seed", params)
        self.assertIsNone(params["seed"])

    def test_no_parameters_invocation_identity_still_valid(self):
        self._call()
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        stored = canon["metadata"]["invocation_identity"]
        identity = parse_invocation_identity(stored)
        self.assertNotIn(
            "parameters", identity.to_stored_object()["request"]
        )

    def test_stream_false_does_not_disqualify_identity(self):
        self._call(temperature=0.5, stream=False)
        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertIn("invocation_identity", meta)
        params = meta["invocation_identity"]["request"].get("parameters", {})
        self.assertNotIn("stream", params)
        self.assertEqual(params.get("temperature"), 0.5)

    def test_unsupported_kwarg_provider_receives_it_bundle_succeeds_no_identity(
        self,
    ):
        self._call(custom_llm_provider="azure")

        call_kwargs = _litellm_stub.completion.call_args.kwargs
        self.assertEqual(call_kwargs.get("custom_llm_provider"), "azure")

        canon = json.loads((Path(self.tmp) / "ai_canonical.json").read_text())
        self.assertNotIn("invocation_identity", canon["metadata"])
        self.assertTrue(verify_ai_bundle(self.tmp).valid)

    def test_secret_like_unknown_kwarg_not_written_to_evidence(self):
        fake_token = "sk-test-DETERMINISTIC-FAKE-TOKEN-0000000000"
        self._call(api_key=fake_token)

        call_kwargs = _litellm_stub.completion.call_args.kwargs
        self.assertEqual(call_kwargs.get("api_key"), fake_token)

        canon_text = (Path(self.tmp) / "ai_canonical.json").read_text()
        manifest_text = (Path(self.tmp) / "ai_manifest.json").read_text()
        self.assertNotIn(fake_token, canon_text)
        self.assertNotIn(fake_token, manifest_text)
        vk_path = Path(self.tmp) / "verification_keys.json"
        if vk_path.exists():
            self.assertNotIn(fake_token, vk_path.read_text())

        canon = json.loads(canon_text)
        self.assertNotIn("invocation_identity", canon["metadata"])

    def test_bundle_with_invocation_identity_verifies(self):
        self._call(temperature=0.3, max_tokens=100)
        self.assertTrue(verify_ai_bundle(self.tmp).valid)


class TestCaptureLiteLLMEnableInvocationIdentity(unittest.TestCase):
    """P1.2b enable() parity: extra provider-call kwargs must reach
    capture_completion() so a representable invocation identity is recorded,
    without triggering a second LLM call. Uses its own fresh litellm stub
    (mirroring tests/test_enable_litellm.py's pattern) and restores the
    shared module-level stub afterward so other classes in this file are
    unaffected regardless of test execution order.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._enable_stub = MagicMock()
        self._enable_stub.__name__ = "litellm"
        self._enable_stub.completion = MagicMock(
            return_value=_make_mock_response()
        )
        sys.modules["litellm"] = self._enable_stub

        import importlib

        import engine.capture.litellm as _mod

        importlib.reload(_mod)
        self._mod = _mod

    def tearDown(self):
        sys.modules["litellm"] = _litellm_stub
        import importlib

        import engine.capture.litellm as _mod

        importlib.reload(_mod)

    def _enable(self, **kwargs):
        self._mod.enable(out_dir=self.tmp, **kwargs)

    def _bundle_dir(self) -> Path:
        subdirs = [
            p
            for p in self.tmp.iterdir()
            if p.is_dir() and not p.name.startswith("_tmp_")
        ]
        self.assertEqual(len(subdirs), 1, subdirs)
        return subdirs[0]

    def test_enable_forwards_extra_kwargs_into_invocation_identity(self):
        expected_response = _make_mock_response(content="exact content")
        # Capture the original mock reference before enable() replaces
        # `.completion` with its own wrapper -- enable() calls this
        # captured `original`, not the post-enable `.completion` attribute.
        original = self._enable_stub.completion
        original.return_value = expected_response
        self._enable()

        response = self._enable_stub.completion(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
            max_tokens=64,
        )

        # original called exactly once
        self.assertEqual(original.call_count, 1)
        call_kwargs = original.call_args.kwargs
        self.assertEqual(call_kwargs["temperature"], 0.7)
        self.assertEqual(call_kwargs["max_tokens"], 64)
        # response returned to caller unchanged
        self.assertIs(response, expected_response)

        bundle_dir = self._bundle_dir()
        canon = json.loads((bundle_dir / "ai_canonical.json").read_text())
        meta = canon["metadata"]
        self.assertIn("invocation_identity", meta)
        identity = parse_invocation_identity(meta["invocation_identity"])
        self.assertEqual(identity.surface, SURFACE_LITELLM_COMPLETION)
        self.assertEqual(identity.mode, MODE_SYNC_NON_STREAMING)
        params = identity.to_stored_object()["request"]["parameters"]
        self.assertEqual(params["temperature"], 0.7)
        self.assertEqual(params["max_tokens"], 64)

        # request_hash keeps frozen v1 model+messages-only semantics
        self.assertEqual(len(meta["request_hash"]), 64)

    def test_enable_unsupported_kwarg_still_succeeds_without_identity(self):
        original = self._enable_stub.completion
        self._enable()

        response = self._enable_stub.completion(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": "hi"}],
            custom_llm_provider="azure",
        )

        self.assertEqual(original.call_count, 1)
        call_kwargs = original.call_args.kwargs
        self.assertEqual(call_kwargs.get("custom_llm_provider"), "azure")
        self.assertIsNotNone(response)

        bundle_dir = self._bundle_dir()
        canon = json.loads((bundle_dir / "ai_canonical.json").read_text())
        self.assertNotIn("invocation_identity", canon["metadata"])
