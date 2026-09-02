"""Contract tests for ``aelitium compare``.

The v0.4 contract is invocation-first, exposes every basis downgrade, retains
the v0.3 request-hash decisions behind an explicit legacy mode, and preserves
the established exit codes.
"""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from engine.ai_cli import cmd_compare
from engine.ai_pack import ai_pack_from_obj
from engine.ai_verify import AIVerificationResult, AssuranceState
from engine.canonical import canonical_json, sha256_hash
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    MODE_SYNC_STREAMING,
    SURFACE_ANTHROPIC_MESSAGES,
    SURFACE_LITELLM_COMPLETION,
    SURFACE_OPENAI_CHAT_COMPLETIONS,
    build_invocation_identity,
)
from engine.invocation_binding import build_invocation_binding


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
FROZEN_PRE_INVOCATION_A = ROOT / "examples" / "drift_demo" / "bundle_a"
FROZEN_PRE_INVOCATION_B = ROOT / "examples" / "drift_demo" / "bundle_b"
FROZEN_V030_INVOCATION_A = (
    ROOT / "tests" / "fixtures" / "compare" / "v030_invocation_a"
)
FROZEN_V030_INVOCATION_B = (
    ROOT / "tests" / "fixtures" / "compare" / "v030_invocation_b"
)
CLI = [sys.executable, "-m", "engine.ai_cli"]


def _make_openai_capture_bundle(
    outdir: Path,
    request_content: str,
    response_content: str,
) -> Path:
    """Create a bundle through the actual OpenAI non-streaming adapter."""

    from engine.capture.openai import capture_chat_completion

    response = SimpleNamespace(
        id="resp_test",
        created=1710000000,
        model="gpt-4o-mini",
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=response_content),
            )
        ],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create.return_value = response

    capture_chat_completion(
        client,
        "gpt-4o-mini",
        [{"role": "user", "content": request_content}],
        outdir,
    )
    return outdir


def _make_bundle(
    outdir: Path,
    *,
    request_content: str = "question",
    response_content: str = "answer",
    model: str = "shared-model",
    response_model: str | None = None,
    surface: str = SURFACE_OPENAI_CHAT_COMPLETIONS,
    mode: str = MODE_SYNC_NON_STREAMING,
    parameters: dict | None = None,
    include_invocation_identity: bool = True,
    include_invocation_binding: bool | None = None,
    malformed_invocation_identity: bool = False,
    malformed_invocation_binding: bool = False,
) -> Path:
    """Write a deterministic, verifier-valid bundle or a targeted malformed one."""

    messages = [{"role": "user", "content": request_content}]
    request_hash = sha256_hash(
        canonical_json({"messages": messages, "model": model})
    )
    response_hash = sha256_hash(
        canonical_json(
            {"content": response_content, "model": response_model or model}
        )
    )
    binding_hash = sha256_hash(
        canonical_json(
            {"request_hash": request_hash, "response_hash": response_hash}
        )
    )

    metadata = {
        "provider": "compare-test",
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
    }

    if include_invocation_binding is None:
        include_invocation_binding = include_invocation_identity

    if include_invocation_identity:
        identity = build_invocation_identity(
            surface=surface,
            mode=mode,
            model=model,
            messages=messages,
            parameters=parameters,
        ).to_stored_object()
        if malformed_invocation_identity:
            identity["hash_sha256"] = "f" * 64
        metadata["invocation_identity"] = identity

        if include_invocation_binding:
            invocation_binding = build_invocation_binding(
                invocation_hash=identity["hash_sha256"],
                response_hash=response_hash,
            ).to_stored_object()
            if malformed_invocation_binding:
                invocation_binding["hash_sha256"] = "f" * 64
            metadata["invocation_binding"] = invocation_binding

    payload = {
        "metadata": metadata,
        "model": model,
        "output": response_content,
        "prompt": canonical_json(messages),
        "schema_version": "ai_output_v1",
        "ts_utc": "2026-08-27T00:00:00Z",
    }
    result = ai_pack_from_obj(payload)
    manifest = {**result.manifest, "binding_hash": binding_hash}
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ai_canonical.json").write_text(
        result.canonical_json + "\n", encoding="utf-8"
    )
    (outdir / "ai_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    return outdir


def _pack(outdir: Path) -> None:
    """Pack the minimal fixture, which has no comparison capture metadata."""

    subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True,
        check=True,
        cwd=ROOT,
    )


def _compare(
    bundle_a: Path,
    bundle_b: Path,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + ["compare", str(bundle_a), str(bundle_b)] + (extra or []),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _json_result(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout.strip())


class TestCompareInvocationFirst(unittest.TestCase):
    def test_openai_same_identity_same_response_is_unchanged(self):
        """A. Same OpenAI non-streaming identity and response."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_openai_capture_bundle(Path(d1), "What is 2+2?", "4")
            _make_openai_capture_bundle(Path(d2), "What is 2+2?", "4")
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "STATUS=UNCHANGED rc=0")
        self.assertIn("COMPARISON_CONTRACT=aelitium-compare-v1", result.stdout)
        self.assertIn("COMPARISON_MODE=INVOCATION_FIRST", result.stdout)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("COMPARISON_REASON=RESPONSE_HASH_SAME", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=SAME", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=VALID", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_B=VALID", result.stdout)

    def test_openai_same_identity_different_response_is_changed(self):
        """B. Same OpenAI non-streaming identity and different response."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_openai_capture_bundle(Path(d1), "Capital of France?", "Paris")
            _make_openai_capture_bundle(Path(d2), "Capital of France?", "Lyon")
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=CHANGED rc=2", result.stdout)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("COMPARISON_REASON=RESPONSE_HASH_DIFFERENT", result.stdout)
        self.assertIn("REQUEST_HASH=SAME", result.stdout)
        self.assertIn("RESPONSE_HASH=DIFFERENT", result.stdout)
        self.assertIn("BINDING_HASH=DIFFERENT", result.stdout)
        self.assertIn("This does not identify a cause.", result.stdout)

    def test_openai_streaming_and_non_streaming_are_not_comparable(self):
        """C. OpenAI streaming and non-streaming identity modes differ."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), mode=MODE_SYNC_NON_STREAMING)
            _make_bundle(Path(d2), mode=MODE_SYNC_STREAMING)
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("STATUS=NOT_COMPARABLE rc=1", result.stdout)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn(
            "COMPARISON_REASON=INVOCATION_IDENTITY_HASH_DIFFERENT",
            result.stdout,
        )
        self.assertIn("INVOCATION_IDENTITY_HASH=DIFFERENT", result.stdout)
        self.assertIn("REQUEST_HASH=SAME", result.stdout)

    def test_anthropic_max_tokens_difference_is_not_comparable(self):
        """D. Anthropic max_tokens is part of invocation_identity v1."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(
                Path(d1),
                surface=SURFACE_ANTHROPIC_MESSAGES,
                parameters={"max_tokens": 32},
            )
            _make_bundle(
                Path(d2),
                surface=SURFACE_ANTHROPIC_MESSAGES,
                parameters={"max_tokens": 4096},
            )
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=DIFFERENT", result.stdout)
        self.assertIn("REQUEST_HASH=SAME", result.stdout)

    def test_litellm_temperature_difference_is_not_comparable(self):
        """E. LiteLLM representable temperature is part of invocation identity."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(
                Path(d1),
                surface=SURFACE_LITELLM_COMPLETION,
                parameters={"temperature": 0.0},
            )
            _make_bundle(
                Path(d2),
                surface=SURFACE_LITELLM_COMPLETION,
                parameters={"temperature": 1.0},
            )
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=DIFFERENT", result.stdout)

    def test_litellm_same_representable_parameters_follow_response_hash(self):
        """F. Matching representable LiteLLM parameters permit response comparison."""

        for response_b, status, rc in (
            ("answer", "UNCHANGED", 0),
            ("different answer", "CHANGED", 2),
        ):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
                    kwargs = {
                        "surface": SURFACE_LITELLM_COMPLETION,
                        "parameters": {"temperature": 0.2, "seed": 7},
                    }
                    _make_bundle(Path(d1), response_content="answer", **kwargs)
                    _make_bundle(Path(d2), response_content=response_b, **kwargs)
                    result = _compare(Path(d1), Path(d2))

                self.assertEqual(result.returncode, rc)
                self.assertIn(f"STATUS={status}", result.stdout)
                self.assertIn(
                    "COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout
                )

    def test_litellm_unsupported_kwargs_on_both_sides_use_fallback(self):
        """G. Conservative LiteLLM identity absence selects visible fallback."""

        from engine.capture.litellm import _build_litellm_invocation_identity

        messages = [{"role": "user", "content": "question"}]
        self.assertIsNone(
            _build_litellm_invocation_identity(
                "shared-model", messages, {"custom_llm_provider": "azure"}
            )
        )
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), include_invocation_identity=False)
            _make_bundle(Path(d2), include_invocation_identity=False)
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=UNAVAILABLE", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=ABSENT", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_B=ABSENT", result.stdout)

    def test_identity_present_on_one_side_uses_asymmetric_fallback(self):
        """H. One-sided usable invocation evidence permits visible fallback."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2), include_invocation_identity=False)
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=VALID", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_A=VALID", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_B=ABSENT", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_B=ABSENT", result.stdout)

    def test_legacy_bundle_and_current_bundle_use_fallback(self):
        """I. A legacy bundle remains readable alongside current evidence."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), include_invocation_identity=False)
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)

    def test_different_adapter_surfaces_are_not_comparable(self):
        """J. Surface is part of invocation_identity v1."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), surface=SURFACE_OPENAI_CHAT_COMPLETIONS)
            _make_bundle(
                Path(d2),
                surface=SURFACE_ANTHROPIC_MESSAGES,
                parameters={"max_tokens": 32},
            )
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("REQUEST_HASH=SAME", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=DIFFERENT", result.stdout)

    def test_different_request_hash_without_identity_is_not_comparable(self):
        """M. Fallback retains the v1 request-hash prerequisite."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(
                Path(d1),
                request_content="request a",
                include_invocation_identity=False,
            )
            _make_bundle(
                Path(d2),
                request_content="request b",
                include_invocation_identity=False,
            )
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("COMPARISON_REASON=REQUEST_HASH_DIFFERENT", result.stdout)
        self.assertIn("REQUEST_HASH=DIFFERENT", result.stdout)

    def test_identity_valid_but_binding_absent_uses_fallback(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), include_invocation_binding=False)
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=VALID", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_A=ABSENT", result.stdout)

    def test_default_changed_and_not_comparable_are_symmetric(self):
        cases = (
            ({"response_content": "a"}, {"response_content": "b"}, 2, "CHANGED"),
            (
                {"mode": MODE_SYNC_NON_STREAMING},
                {"mode": MODE_SYNC_STREAMING},
                1,
                "NOT_COMPARABLE",
            ),
        )
        for kwargs_a, kwargs_b, rc, status in cases:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
                    _make_bundle(Path(d1), **kwargs_a)
                    _make_bundle(Path(d2), **kwargs_b)
                    forward = _compare(Path(d1), Path(d2))
                    reverse = _compare(Path(d2), Path(d1))
                self.assertEqual(forward.returncode, rc)
                self.assertEqual(reverse.returncode, rc)
                self.assertIn(f"STATUS={status}", forward.stdout)
                self.assertIn(f"STATUS={status}", reverse.stdout)

    def test_request_hash_v1_is_unchanged_by_invocation_parameters(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(
                Path(d1),
                surface=SURFACE_LITELLM_COMPLETION,
                parameters={"temperature": 0.0},
            )
            _make_bundle(
                Path(d2),
                surface=SURFACE_LITELLM_COMPLETION,
                parameters={"temperature": 1.0},
            )
            canon_a = json.loads((Path(d1) / "ai_canonical.json").read_text())
            canon_b = json.loads((Path(d2) / "ai_canonical.json").read_text())

        self.assertEqual(
            canon_a["metadata"]["request_hash"],
            canon_b["metadata"]["request_hash"],
        )
        self.assertNotEqual(
            canon_a["metadata"]["invocation_identity"]["hash_sha256"],
            canon_b["metadata"]["invocation_identity"]["hash_sha256"],
        )


class TestCompareStrictInvocation(unittest.TestCase):
    FLAG = ["--require-invocation-evidence"]

    def test_strict_mode_uses_identity_when_both_sides_are_usable(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2), self.FLAG)

        self.assertEqual(result.returncode, 0)
        self.assertIn("COMPARISON_MODE=STRICT_INVOCATION", result.stdout)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertNotIn("REQUIRED_COMPARISON_BASIS=", result.stdout)

    def test_strict_mode_rejects_missing_evidence(self):
        """N. Strict mode never falls back."""

        for identity_a, binding_a, identity_b, binding_b in (
            (False, False, False, False),
            (True, True, False, False),
            (True, False, True, True),
        ):
            with self.subTest(
                identity_a=identity_a,
                binding_a=binding_a,
                identity_b=identity_b,
                binding_b=binding_b,
            ):
                with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
                    _make_bundle(
                        Path(d1),
                        include_invocation_identity=identity_a,
                        include_invocation_binding=binding_a,
                    )
                    _make_bundle(
                        Path(d2),
                        include_invocation_identity=identity_b,
                        include_invocation_binding=binding_b,
                    )
                    result = _compare(Path(d1), Path(d2), self.FLAG)

                self.assertEqual(result.returncode, 1)
                self.assertIn("STATUS=NOT_COMPARABLE rc=1", result.stdout)
                self.assertIn("COMPARISON_MODE=STRICT_INVOCATION", result.stdout)
                self.assertIn("COMPARISON_BASIS=NONE", result.stdout)
                self.assertIn(
                    "REQUIRED_COMPARISON_BASIS=INVOCATION_IDENTITY_V1",
                    result.stdout,
                )
                self.assertIn(
                    "COMPARISON_REASON=INVOCATION_EVIDENCE_UNAVAILABLE",
                    result.stdout,
                )

    def test_strict_missing_evidence_json_contract(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2), include_invocation_identity=False)
            result = _compare(Path(d1), Path(d2), self.FLAG + ["--json"])
        obj = _json_result(result)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(obj["comparison_mode"], "STRICT_INVOCATION")
        self.assertEqual(obj["comparison_basis"], "NONE")
        self.assertEqual(
            obj["required_comparison_basis"], "INVOCATION_IDENTITY_V1"
        )
        self.assertEqual(obj["comparison_reason"], "INVOCATION_EVIDENCE_UNAVAILABLE")


class TestCompareLegacyRequestHash(unittest.TestCase):
    FLAG = ["--legacy-request-hash-v1"]

    def test_legacy_mode_ignores_different_invocation_identities(self):
        """O. Explicit legacy mode reproduces the v0.3 request-hash decision."""

        for response_b, status, rc in (
            ("answer", "UNCHANGED", 0),
            ("other", "CHANGED", 2),
        ):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
                    _make_bundle(
                        Path(d1),
                        response_content="answer",
                        surface=SURFACE_LITELLM_COMPLETION,
                        parameters={"temperature": 0.0},
                    )
                    _make_bundle(
                        Path(d2),
                        response_content=response_b,
                        surface=SURFACE_LITELLM_COMPLETION,
                        parameters={"temperature": 1.0},
                    )
                    result = _compare(Path(d1), Path(d2), self.FLAG)

                self.assertEqual(result.returncode, rc)
                self.assertIn(f"STATUS={status}", result.stdout)
                self.assertIn(
                    "COMPARISON_MODE=LEGACY_REQUEST_HASH_V1", result.stdout
                )
                self.assertIn(
                    "COMPARISON_BASIS=REQUEST_HASH_V1_LEGACY", result.stdout
                )
                self.assertIn("INVOCATION_IDENTITY_HASH=DIFFERENT", result.stdout)
                self.assertIn("REQUEST_HASH=SAME", result.stdout)

    def test_legacy_mode_different_requests_remain_not_comparable(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), request_content="a")
            _make_bundle(Path(d2), request_content="b")
            result = _compare(Path(d1), Path(d2), self.FLAG)

        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_LEGACY", result.stdout)
        self.assertIn("COMPARISON_REASON=REQUEST_HASH_DIFFERENT", result.stdout)

    def test_legacy_mode_json_contract(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2), self.FLAG + ["--json"])
        obj = _json_result(result)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(obj["comparison_mode"], "LEGACY_REQUEST_HASH_V1")
        self.assertEqual(obj["comparison_basis"], "REQUEST_HASH_V1_LEGACY")
        self.assertIsNone(obj["required_comparison_basis"])


class TestCompareBackwardCompatibility(unittest.TestCase):
    def test_frozen_v030_invocation_bundles_use_preferred_basis(self):
        result = _compare(FROZEN_V030_INVOCATION_A, FROZEN_V030_INVOCATION_B)
        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=CHANGED rc=2", result.stdout)
        self.assertIn("COMPARISON_BASIS=INVOCATION_IDENTITY_V1", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_HASH=SAME", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=VALID", result.stdout)
        self.assertIn("INVOCATION_BINDING_CONSISTENCY_B=VALID", result.stdout)

    def test_frozen_pre_invocation_bundle_uses_fallback_unchanged(self):
        result = _compare(FROZEN_PRE_INVOCATION_A, FROZEN_PRE_INVOCATION_A)
        self.assertEqual(result.returncode, 0)
        self.assertIn("STATUS=UNCHANGED rc=0", result.stdout)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("INVOCATION_IDENTITY_CONSISTENCY_A=ABSENT", result.stdout)

    def test_frozen_pre_invocation_bundles_use_fallback_changed(self):
        result = _compare(FROZEN_PRE_INVOCATION_A, FROZEN_PRE_INVOCATION_B)
        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=CHANGED rc=2", result.stdout)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)

    def test_frozen_pre_invocation_bundle_strict_mode_is_not_comparable(self):
        result = _compare(
            FROZEN_PRE_INVOCATION_A,
            FROZEN_PRE_INVOCATION_A,
            ["--require-invocation-evidence"],
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("COMPARISON_BASIS=NONE", result.stdout)

    def test_frozen_pre_invocation_legacy_decisions_match_v03(self):
        unchanged = _compare(
            FROZEN_PRE_INVOCATION_A,
            FROZEN_PRE_INVOCATION_A,
            ["--legacy-request-hash-v1"],
        )
        changed = _compare(
            FROZEN_PRE_INVOCATION_A,
            FROZEN_PRE_INVOCATION_B,
            ["--legacy-request-hash-v1"],
        )
        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(changed.returncode, 2)
        self.assertIn("STATUS=UNCHANGED", unchanged.stdout)
        self.assertIn("STATUS=CHANGED", changed.stdout)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_LEGACY", changed.stdout)

    def test_pack_bundles_report_request_hash_unavailable(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _pack(Path(d1))
            _pack(Path(d2))
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 1)
        self.assertIn("STATUS=NOT_COMPARABLE rc=1", result.stdout)
        self.assertIn("COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK", result.stdout)
        self.assertIn("COMPARISON_REASON=REQUEST_HASH_UNAVAILABLE", result.stdout)
        self.assertIn("REQUEST_HASH=UNAVAILABLE", result.stdout)


class TestCompareInvalidInputs(unittest.TestCase):
    def test_malformed_invocation_identity_is_invalid_bundle(self):
        """K. Malformed identity fails verification and never falls back."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), malformed_invocation_identity=True)
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.splitlines()[0], "STATUS=INVALID_BUNDLE rc=2")
        self.assertIn("COMPARISON_BASIS=NONE", result.stdout)
        self.assertIn("COMPARISON_REASON=BUNDLE_VERIFICATION_FAILED", result.stdout)
        self.assertNotIn("REQUEST_HASH_V1_FALLBACK", result.stdout)

    def test_malformed_invocation_binding_is_invalid_bundle(self):
        """L. Malformed invocation binding fails verification."""

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), malformed_invocation_binding=True)
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2))

        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=INVALID_BUNDLE rc=2", result.stdout)
        self.assertIn("COMPARISON_BASIS=NONE", result.stdout)
        self.assertIn("COMPARISON_REASON=BUNDLE_VERIFICATION_FAILED", result.stdout)

    def test_invalid_bundle_precedes_strict_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), malformed_invocation_identity=True)
            _make_bundle(Path(d2), include_invocation_identity=False)
            result = _compare(
                Path(d1), Path(d2), ["--require-invocation-evidence"]
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=INVALID_BUNDLE rc=2", result.stdout)
        self.assertIn("COMPARISON_REASON=BUNDLE_VERIFICATION_FAILED", result.stdout)
        self.assertNotIn("REQUIRED_COMPARISON_BASIS=", result.stdout)

    def test_invalid_json_does_not_expose_raw_invocation_hashes(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1), malformed_invocation_identity=True)
            _make_bundle(Path(d2))
            result = _compare(Path(d1), Path(d2), ["--json"])
        obj = _json_result(result)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(obj["status"], "INVALID_BUNDLE")
        self.assertEqual(obj["comparison_basis"], "NONE")
        self.assertIsNone(obj["required_comparison_basis"])
        self.assertEqual(obj["invocation_identity_hash"], "UNAVAILABLE")
        self.assertIsNone(obj["invocation_identity_hash_a"])
        self.assertIsNone(obj["invocation_identity_hash_b"])
        self.assertNotIn("f" * 64, result.stdout)

    def test_missing_bundle_is_invalid(self):
        with tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d2))
            result = _compare(Path("/nonexistent/aelitium-bundle"), Path(d2))

        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=INVALID_BUNDLE rc=2", result.stdout)
        self.assertIn("DETAIL=a=MISSING_BUNDLE_FILES", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_both_bundles_are_verified_before_invalid_result(self):
        invalid = AIVerificationResult(valid=False, reason="MISSING_CANONICAL")
        valid = AIVerificationResult(valid=True, reason="OK")
        args = SimpleNamespace(
            bundle_a="a",
            bundle_b="b",
            json=True,
            require_invocation_evidence=False,
            legacy_request_hash_v1=False,
        )
        output = io.StringIO()
        with patch(
            "engine.ai_cli.verify_ai_bundle", side_effect=[invalid, valid]
        ) as verifier, contextlib.redirect_stdout(output):
            rc = cmd_compare(args)

        self.assertEqual(rc, 2)
        self.assertEqual(verifier.call_count, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "INVALID_BUNDLE")

    def test_impossible_valid_assurance_state_is_input_invariant_failure(self):
        impossible = AIVerificationResult(
            valid=True,
            reason="OK",
            canonical={"metadata": {}},
            manifest={},
            invocation_identity_consistency=AssuranceState.NOT_EVALUATED,
            invocation_binding_consistency=AssuranceState.ABSENT,
        )
        args = SimpleNamespace(
            bundle_a="a",
            bundle_b="b",
            json=True,
            require_invocation_evidence=False,
            legacy_request_hash_v1=False,
        )
        output = io.StringIO()
        with patch(
            "engine.ai_cli.verify_ai_bundle", side_effect=[impossible, impossible]
        ), contextlib.redirect_stdout(output):
            rc = cmd_compare(args)
        obj = json.loads(output.getvalue())

        self.assertEqual(rc, 2)
        self.assertEqual(obj["status"], "INVALID_BUNDLE")
        self.assertEqual(obj["comparison_basis"], "NONE")
        self.assertEqual(
            obj["comparison_reason"], "COMPARISON_INPUT_INVARIANT_FAILED"
        )


class TestCompareOutputContract(unittest.TestCase):
    def test_success_json_retains_old_keys_and_adds_full_hashes(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2))
            expected_a = json.loads(
                (Path(d1) / "ai_canonical.json").read_text()
            )["metadata"]["invocation_identity"]["hash_sha256"]
            expected_b = json.loads(
                (Path(d2) / "ai_canonical.json").read_text()
            )["metadata"]["invocation_identity"]["hash_sha256"]
            result = _compare(Path(d1), Path(d2), ["--json"])
        obj = _json_result(result)

        self.assertEqual(result.returncode, 0)
        for old_key in (
            "status",
            "rc",
            "request_hash",
            "response_hash",
            "binding_hash",
            "request_hash_a",
            "request_hash_b",
            "response_hash_a",
            "response_hash_b",
            "ts_utc_a",
            "ts_utc_b",
            "interpretation",
        ):
            self.assertIn(old_key, obj)
        for new_key in (
            "comparison_contract",
            "comparison_mode",
            "comparison_basis",
            "required_comparison_basis",
            "comparison_reason",
            "invocation_identity_hash",
            "invocation_identity_hash_a",
            "invocation_identity_hash_b",
            "invocation_identity_consistency_a",
            "invocation_binding_consistency_a",
            "invocation_identity_consistency_b",
            "invocation_binding_consistency_b",
        ):
            self.assertIn(new_key, obj)
        self.assertEqual(obj["comparison_contract"], "aelitium-compare-v1")
        self.assertEqual(obj["invocation_identity_hash_a"], expected_a)
        self.assertEqual(obj["invocation_identity_hash_b"], expected_b)
        self.assertEqual(len(obj["invocation_identity_hash_a"]), 64)
        self.assertIsNone(obj["required_comparison_basis"])

    def test_fallback_json_exposes_per_side_assurance(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _make_bundle(Path(d1))
            _make_bundle(Path(d2), include_invocation_identity=False)
            result = _compare(Path(d1), Path(d2), ["--json"])
        obj = _json_result(result)

        self.assertEqual(obj["comparison_basis"], "REQUEST_HASH_V1_FALLBACK")
        self.assertEqual(obj["invocation_identity_consistency_a"], "VALID")
        self.assertEqual(obj["invocation_binding_consistency_a"], "VALID")
        self.assertEqual(obj["invocation_identity_consistency_b"], "ABSENT")
        self.assertEqual(obj["invocation_binding_consistency_b"], "ABSENT")
        self.assertEqual(obj["invocation_identity_hash"], "UNAVAILABLE")
        self.assertEqual(len(obj["invocation_identity_hash_a"]), 64)
        self.assertIsNone(obj["invocation_identity_hash_b"])

    def test_text_output_preserves_status_first_and_diagnostics(self):
        result = _compare(FROZEN_PRE_INVOCATION_A, FROZEN_PRE_INVOCATION_B)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "STATUS=CHANGED rc=2")
        for prefix in (
            "COMPARISON_CONTRACT=",
            "COMPARISON_MODE=",
            "COMPARISON_BASIS=",
            "COMPARISON_REASON=",
            "INVOCATION_IDENTITY_HASH=",
            "INVOCATION_IDENTITY_CONSISTENCY_A=",
            "INVOCATION_BINDING_CONSISTENCY_A=",
            "INVOCATION_IDENTITY_CONSISTENCY_B=",
            "INVOCATION_BINDING_CONSISTENCY_B=",
            "REQUEST_HASH=",
            "RESPONSE_HASH=",
            "BINDING_HASH=",
            "TS_UTC_A=",
            "TS_UTC_B=",
            "INTERPRETATION=",
        ):
            self.assertTrue(any(line.startswith(prefix) for line in lines), prefix)

    def test_mode_flags_are_mutually_exclusive_usage_error(self):
        result = _compare(
            FROZEN_PRE_INVOCATION_A,
            FROZEN_PRE_INVOCATION_A,
            ["--require-invocation-evidence", "--legacy-request-hash-v1"],
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowed with argument", result.stderr)
        self.assertNotIn("STATUS=", result.stdout)


if __name__ == "__main__":
    unittest.main()
