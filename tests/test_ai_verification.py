"""Parity and adversarial tests for the canonical AI verification kernel."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine.ai_verify import (
    AIVerificationOptions,
    AssuranceState,
    verify_ai_bundle,
)
from engine.signing import build_verification_material


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]
STANDALONE = ROOT / "scripts" / "aelitium_verify_standalone.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + list(args),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _run_standalone(
    bundle: Path,
    *extra: str,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(STANDALONE),
            "--bundle",
            str(bundle),
            "--json",
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _pack(bundle: Path) -> None:
    result = _run_cli("pack", "--input", str(FIXTURE), "--out", str(bundle))
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def _rewrite_canonical(bundle: Path, canonical: dict) -> str:
    canonical_text = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    (bundle / "ai_canonical.json").write_text(
        canonical_text + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def _write_manifest(bundle: Path, manifest: dict) -> None:
    (bundle / "ai_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _make_bound_bundle(bundle: Path) -> None:
    """Create a valid unsigned v1 bundle with existing capture hash fields."""
    _pack(bundle)
    canonical_path = bundle / "ai_canonical.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    request_hash = "1" * 64
    response_hash = "2" * 64
    binding_payload = json.dumps(
        {"request_hash": request_hash, "response_hash": response_hash},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    binding_hash = hashlib.sha256(binding_payload.encode("utf-8")).hexdigest()
    canonical.setdefault("metadata", {}).update(
        {
            "request_hash": request_hash,
            "response_hash": response_hash,
            "binding_hash": binding_hash,
        }
    )
    canonical_hash = _rewrite_canonical(bundle, canonical)

    manifest_path = bundle / "ai_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ai_hash_sha256"] = canonical_hash
    manifest["binding_hash"] = binding_hash
    _write_manifest(bundle, manifest)


def _sign_bundle(bundle: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    private_key_b64 = base64.b64encode(private_key.private_bytes_raw()).decode()
    old_key = os.environ.get("AEL_ED25519_PRIVKEY_B64")
    os.environ["AEL_ED25519_PRIVKEY_B64"] = private_key_b64
    try:
        verification_material = build_verification_material(
            (bundle / "ai_manifest.json").read_bytes()
        )
    finally:
        if old_key is None:
            os.environ.pop("AEL_ED25519_PRIVKEY_B64", None)
        else:
            os.environ["AEL_ED25519_PRIVKEY_B64"] = old_key

    (bundle / "verification_keys.json").write_text(
        json.dumps(verification_material, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _entrypoint_acceptance(bundle: Path) -> dict[str, bool]:
    verify = _run_cli("verify", "--out", str(bundle))
    verify_bundle = _run_cli("verify-bundle", str(bundle))
    compare = _run_cli("compare", str(bundle), str(bundle))
    standalone = _run_standalone(bundle)
    return {
        "kernel": verify_ai_bundle(bundle).valid,
        "verify": verify.returncode == 0,
        "verify-bundle": verify_bundle.returncode == 0,
        "compare-prevalidation": "STATUS=INVALID_BUNDLE" not in compare.stdout,
        "standalone": standalone.returncode == 0,
    }


class TestAIVerificationParity(unittest.TestCase):
    def test_valid_unsigned_bundle_is_accepted_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": True,
                    "verify": True,
                    "verify-bundle": True,
                    "compare-prevalidation": True,
                    "standalone": True,
                },
            )

    def test_valid_signed_bundle_is_accepted_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": True,
                    "verify": True,
                    "verify-bundle": True,
                    "compare-prevalidation": True,
                    "standalone": True,
                },
            )

    def test_canonical_payload_tamper_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            canonical["output"] = "TAMPERED"
            _rewrite_canonical(bundle, canonical)
            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            self.assertEqual(verify_ai_bundle(bundle).reason, "HASH_MISMATCH")

    def test_manifest_hash_tamper_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ai_hash_sha256"] = "a" * 64
            _write_manifest(bundle, manifest)
            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            self.assertEqual(verify_ai_bundle(bundle).reason, "HASH_MISMATCH")

    def test_missing_files_are_rejected_by_every_entrypoint(self):
        for filename, expected_reason in (
            ("ai_canonical.json", "MISSING_CANONICAL"),
            ("ai_manifest.json", "MISSING_MANIFEST"),
        ):
            with self.subTest(filename=filename):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _make_bound_bundle(bundle)
                    (bundle / filename).unlink()
                    self.assertEqual(
                        _entrypoint_acceptance(bundle),
                        {
                            "kernel": False,
                            "verify": False,
                            "verify-bundle": False,
                            "compare-prevalidation": False,
                            "standalone": False,
                        },
                    )
                    self.assertEqual(
                        verify_ai_bundle(bundle).reason,
                        expected_reason,
                    )
                    standalone = _run_standalone(bundle)
                    self.assertEqual(
                        json.loads(standalone.stdout)["reason"],
                        expected_reason,
                    )


class TestAIAssuranceResults(unittest.TestCase):
    def test_default_unsigned_unbound_bundle_exposes_absence(self):
        expected = {
            "payload_integrity": "VALID",
            "binding_field_consistency": "ABSENT",
            "signature_validity": "ABSENT",
            "trusted_signer_identity": "UNESTABLISHED",
            "freshness": "NOT_EVALUATED",
            "authorization": "NOT_EVALUATED",
        }
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)

            result = verify_ai_bundle(bundle)
            self.assertTrue(result.valid)
            self.assertEqual(result.assurance_dict(), expected)
            self.assertEqual(result.signature, "NONE")
            self.assertEqual(result.binding_hash, "NONE")

            outputs = (
                _run_cli("verify", "--out", str(bundle), "--json"),
                _run_cli("verify-bundle", str(bundle), "--json"),
                _run_standalone(bundle),
            )
            for output in outputs:
                with self.subTest(args=output.args):
                    self.assertEqual(output.returncode, 0, output.stdout)
                    payload = json.loads(output.stdout)
                    for name, state in expected.items():
                        self.assertEqual(payload[name], state)

    def test_valid_signed_bound_bundle_establishes_no_signer_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)

            result = verify_ai_bundle(bundle)
            self.assertTrue(result.valid)
            self.assertEqual(result.payload_integrity, AssuranceState.VALID)
            self.assertEqual(
                result.binding_field_consistency,
                AssuranceState.VALID,
            )
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity,
                AssuranceState.UNESTABLISHED,
            )

            outputs = (
                _run_cli(
                    "verify",
                    "--out",
                    str(bundle),
                    "--require-signature",
                    "--require-binding",
                ),
                _run_cli(
                    "verify-bundle",
                    str(bundle),
                    "--require-signature",
                    "--require-binding",
                ),
                _run_standalone(
                    bundle,
                    "--require-signature",
                    "--require-binding",
                ),
            )
            for output in outputs:
                with self.subTest(args=output.args):
                    self.assertEqual(
                        output.returncode,
                        0,
                        output.stdout + output.stderr,
                    )

    def test_require_signature_rejects_unsigned_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(require_signature=True),
            )
            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "SIGNATURE_REQUIRED")
            self.assertEqual(result.payload_integrity, AssuranceState.VALID)
            self.assertEqual(result.signature_validity, AssuranceState.ABSENT)
            self.assertEqual(
                result.binding_field_consistency,
                AssuranceState.ABSENT,
            )

            outputs = (
                _run_cli(
                    "verify",
                    "--out",
                    str(bundle),
                    "--require-signature",
                ),
                _run_cli(
                    "verify-bundle",
                    str(bundle),
                    "--require-signature",
                ),
                _run_standalone(bundle, "--require-signature"),
            )
            for output in outputs:
                with self.subTest(args=output.args):
                    self.assertEqual(output.returncode, 2)
                    self.assertIn("SIGNATURE_REQUIRED", output.stdout)
                    self.assertIn("signature_validity", output.stdout.lower())

    def test_require_binding_rejects_unbound_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(require_binding=True),
            )
            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "BINDING_REQUIRED")
            self.assertEqual(result.payload_integrity, AssuranceState.VALID)
            self.assertEqual(
                result.binding_field_consistency,
                AssuranceState.ABSENT,
            )

            outputs = (
                _run_cli(
                    "verify",
                    "--out",
                    str(bundle),
                    "--require-binding",
                ),
                _run_cli(
                    "verify-bundle",
                    str(bundle),
                    "--require-binding",
                ),
                _run_standalone(bundle, "--require-binding"),
            )
            for output in outputs:
                with self.subTest(args=output.args):
                    self.assertEqual(output.returncode, 2)
                    self.assertIn("BINDING_REQUIRED", output.stdout)
                    self.assertIn(
                        "binding_field_consistency",
                        output.stdout.lower(),
                    )

    def test_each_missing_binding_field_is_rejected_by_every_entrypoint(self):
        fields = (
            ("manifest.binding_hash", "manifest", "binding_hash"),
            ("canonical.metadata.request_hash", "metadata", "request_hash"),
            ("canonical.metadata.response_hash", "metadata", "response_hash"),
            ("canonical.metadata.binding_hash", "metadata", "binding_hash"),
        )
        for location, container, field in fields:
            with self.subTest(location=location):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _make_bound_bundle(bundle)
                    manifest_path = bundle / "ai_manifest.json"
                    manifest = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )

                    if container == "manifest":
                        manifest.pop(field)
                    else:
                        canonical_path = bundle / "ai_canonical.json"
                        canonical = json.loads(
                            canonical_path.read_text(encoding="utf-8")
                        )
                        canonical["metadata"].pop(field)
                        manifest["ai_hash_sha256"] = _rewrite_canonical(
                            bundle,
                            canonical,
                        )
                    _write_manifest(bundle, manifest)

                    self.assertEqual(
                        _entrypoint_acceptance(bundle),
                        {
                            "kernel": False,
                            "verify": False,
                            "verify-bundle": False,
                            "compare-prevalidation": False,
                            "standalone": False,
                        },
                    )
                    result = verify_ai_bundle(bundle)
                    self.assertEqual(result.reason, "BINDING_FIELDS_INCOMPLETE")
                    self.assertIn(location, result.detail)
                    self.assertEqual(
                        result.binding_field_consistency,
                        AssuranceState.INVALID,
                    )

    def test_malformed_binding_field_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            canonical["metadata"]["request_hash"] = "not-a-sha256"
            canonical_hash = _rewrite_canonical(bundle, canonical)

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ai_hash_sha256"] = canonical_hash
            _write_manifest(bundle, manifest)

            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            result = verify_ai_bundle(bundle)
            self.assertEqual(result.reason, "BINDING_FIELD_MALFORMED")
            self.assertEqual(
                result.binding_field_consistency,
                AssuranceState.INVALID,
            )

    def test_assurance_fields_are_exposed_when_payload_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            canonical["output"] = "TAMPERED"
            _rewrite_canonical(bundle, canonical)

            result = verify_ai_bundle(bundle)
            self.assertFalse(result.valid)
            self.assertEqual(result.payload_integrity, AssuranceState.INVALID)
            self.assertEqual(
                set(result.assurance_dict()),
                {
                    "payload_integrity",
                    "binding_field_consistency",
                    "signature_validity",
                    "trusted_signer_identity",
                    "freshness",
                    "authorization",
                },
            )

            output = _run_cli("verify", "--out", str(bundle))
            self.assertEqual(output.returncode, 2)
            for name in result.assurance_dict():
                self.assertIn(name.upper(), output.stdout)


class TestAIVerificationDowngradeControls(unittest.TestCase):
    """Evidence that is present cannot be ignored by an entrypoint."""

    def test_malformed_signature_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            verification_path = bundle / "verification_keys.json"
            verification = json.loads(
                verification_path.read_text(encoding="utf-8")
            )
            verification["signatures"] = "malformed"
            verification_path.write_text(
                json.dumps(verification, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            result = verify_ai_bundle(bundle)
            self.assertEqual(result.reason, "SIGNATURE_INVALID")
            self.assertEqual(result.signature_validity, AssuranceState.INVALID)

    def test_manifest_binding_mismatch_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["binding_hash"] = "b" * 64
            _write_manifest(bundle, manifest)

            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            self.assertEqual(
                verify_ai_bundle(bundle).reason,
                "BINDING_HASH_MISMATCH",
            )

    def test_request_hash_mismatch_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            canonical["metadata"]["request_hash"] = "c" * 64
            canonical_hash = _rewrite_canonical(bundle, canonical)

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ai_hash_sha256"] = canonical_hash
            _write_manifest(bundle, manifest)

            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            self.assertEqual(
                verify_ai_bundle(bundle).reason,
                "BINDING_HASH_MISMATCH",
            )

    def test_metadata_binding_mismatch_is_rejected_by_every_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            canonical["metadata"]["binding_hash"] = "d" * 64
            canonical_hash = _rewrite_canonical(bundle, canonical)

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ai_hash_sha256"] = canonical_hash
            _write_manifest(bundle, manifest)

            self.assertEqual(
                _entrypoint_acceptance(bundle),
                {
                    "kernel": False,
                    "verify": False,
                    "verify-bundle": False,
                    "compare-prevalidation": False,
                    "standalone": False,
                },
            )
            result = verify_ai_bundle(bundle)
            self.assertEqual(result.reason, "BINDING_HASH_MISMATCH")
            self.assertEqual(
                result.binding_field_consistency,
                AssuranceState.INVALID,
            )


if __name__ == "__main__":
    unittest.main()
