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

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine.ai_verify import (
    AIVerificationOptions,
    AssuranceState,
    verify_ai_bundle,
)
from engine.signing import (
    VerifiedManifestSignature,
    build_verification_material,
    verify_manifest_signature,
)
from engine.trust import TRUST_STORE_FORMAT


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


def _write_canonical_bytes_with_raw_hash(bundle: Path, raw: bytes) -> None:
    """Write arbitrary parseable bytes and make the manifest hash those bytes."""

    (bundle / "ai_canonical.json").write_bytes(raw)
    manifest_path = bundle / "ai_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ai_hash_sha256"] = hashlib.sha256(raw).hexdigest()
    _write_manifest(bundle, manifest)


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


def _verification_material_for_key(
    bundle: Path,
    private_key: Ed25519PrivateKey,
) -> dict:
    private_key_b64 = base64.b64encode(private_key.private_bytes_raw()).decode()
    old_key = os.environ.get("AEL_ED25519_PRIVKEY_B64")
    os.environ["AEL_ED25519_PRIVKEY_B64"] = private_key_b64
    try:
        return build_verification_material(
            (bundle / "ai_manifest.json").read_bytes()
        )
    finally:
        if old_key is None:
            os.environ.pop("AEL_ED25519_PRIVKEY_B64", None)
        else:
            os.environ["AEL_ED25519_PRIVKEY_B64"] = old_key


def _sign_bundle(bundle: Path) -> None:
    verification_material = _verification_material_for_key(
        bundle,
        Ed25519PrivateKey.generate(),
    )
    (bundle / "verification_keys.json").write_text(
        json.dumps(verification_material, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sign_bundle_with_key(bundle: Path, private_key: Ed25519PrivateKey) -> str:
    """Sign `bundle` with `private_key` and return its public_key_b64."""

    verification_material = _verification_material_for_key(bundle, private_key)
    (bundle / "verification_keys.json").write_text(
        json.dumps(verification_material, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verification_material["keys"][0]["public_key_b64"]


def _write_trust_store(
    directory: Path,
    public_key_b64_values: list[str],
    filename: str = "trust_store.json",
) -> Path:
    path = directory / filename
    path.write_text(
        json.dumps(
            {
                "trust_store_format": TRUST_STORE_FORMAT,
                "signers": [
                    {"algorithm": "ed25519", "public_key_b64": value}
                    for value in public_key_b64_values
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


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


def _public_verifier_outputs(
    bundle: Path,
    *extra: str,
) -> dict[str, subprocess.CompletedProcess]:
    return {
        "verify": _run_cli(
            "verify",
            "--out",
            str(bundle),
            "--json",
            *extra,
        ),
        "verify-bundle": _run_cli(
            "verify-bundle",
            str(bundle),
            "--json",
            *extra,
        ),
        "standalone": _run_standalone(bundle, *extra),
    }


class TestAIVerificationParity(unittest.TestCase):
    def test_malformed_manifest_timestamp_is_rejected_by_public_verifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["ts_utc"] = ""
            _write_manifest(bundle, manifest)

            kernel = verify_ai_bundle(bundle)
            self.assertFalse(kernel.valid)
            self.assertEqual(kernel.reason, "MANIFEST_BAD_TS_UTC")

            verify = _run_cli("verify", "--out", str(bundle), "--json")
            self.assertEqual(verify.returncode, 2, verify.stdout + verify.stderr)
            self.assertIn("reason=MANIFEST_BAD_TS_UTC", verify.stdout)

            verify_bundle = _run_cli(
                "verify-bundle",
                str(bundle),
                "--json",
            )
            self.assertEqual(
                verify_bundle.returncode,
                2,
                verify_bundle.stdout + verify_bundle.stderr,
            )
            self.assertIn(
                "reason=MANIFEST_BAD_TS_UTC",
                verify_bundle.stdout,
            )

            standalone = _run_standalone(bundle)
            self.assertEqual(
                standalone.returncode,
                2,
                standalone.stdout + standalone.stderr,
            )
            self.assertEqual(
                json.loads(standalone.stdout)["reason"],
                "MANIFEST_BAD_TS_UTC",
            )

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


class TestAIV1ManifestContract(unittest.TestCase):
    def test_declared_manifest_identifiers_are_enforced(self):
        cases = (
            ("schema", "ai_pack_manifest_v2", "MANIFEST_BAD_SCHEMA"),
            ("input_schema", "ai_output_v2", "MANIFEST_BAD_INPUT_SCHEMA"),
            (
                "canonicalization",
                "some_other_canonicalization",
                "MANIFEST_BAD_CANONICALIZATION",
            ),
        )
        for field, value, reason in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _pack(bundle)
                    manifest_path = bundle / "ai_manifest.json"
                    manifest = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )
                    manifest[field] = value
                    _write_manifest(bundle, manifest)

                    result = verify_ai_bundle(bundle)

                    self.assertFalse(result.valid)
                    self.assertEqual(result.reason, reason)
                    self.assertEqual(
                        result.payload_integrity,
                        AssuranceState.INVALID,
                    )

    def test_manifest_ai_hash_malformation_matrix_is_rejected(self):
        malformed_values = (
            ("non_hex", "g" * 64),
            ("wrong_length", "a" * 63),
            ("uppercase_hex", "A" * 64),
        )
        for case, value in malformed_values:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _pack(bundle)
                    manifest_path = bundle / "ai_manifest.json"
                    manifest = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )
                    manifest["ai_hash_sha256"] = value
                    _write_manifest(bundle, manifest)

                    result = verify_ai_bundle(bundle)

                    self.assertFalse(result.valid)
                    self.assertEqual(
                        result.reason,
                        "MANIFEST_BAD_AI_HASH_SHA256",
                    )

    def test_binding_field_malformation_matrix_is_rejected(self):
        locations = (
            ("manifest.binding_hash", "manifest", "binding_hash"),
            (
                "canonical.metadata.request_hash",
                "metadata",
                "request_hash",
            ),
            (
                "canonical.metadata.response_hash",
                "metadata",
                "response_hash",
            ),
            (
                "canonical.metadata.binding_hash",
                "metadata",
                "binding_hash",
            ),
        )
        malformed_values = (
            ("non_hex", "g" * 64),
            ("wrong_length", "a" * 63),
            ("uppercase_hex", "A" * 64),
        )
        for location, container, field in locations:
            for case, value in malformed_values:
                with self.subTest(location=location, case=case):
                    with tempfile.TemporaryDirectory() as directory:
                        bundle = Path(directory)
                        _make_bound_bundle(bundle)
                        manifest_path = bundle / "ai_manifest.json"
                        manifest = json.loads(
                            manifest_path.read_text(encoding="utf-8")
                        )

                        if container == "manifest":
                            manifest[field] = value
                        else:
                            canonical_path = bundle / "ai_canonical.json"
                            canonical = json.loads(
                                canonical_path.read_text(encoding="utf-8")
                            )
                            canonical["metadata"][field] = value
                            manifest["ai_hash_sha256"] = _rewrite_canonical(
                                bundle,
                                canonical,
                            )
                        _write_manifest(bundle, manifest)

                        result = verify_ai_bundle(bundle)

                        self.assertFalse(result.valid)
                        self.assertEqual(
                            result.reason,
                            "BINDING_FIELD_MALFORMED",
                        )
                        self.assertEqual(result.detail, location)

    def test_unknown_manifest_metadata_is_accepted_without_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["extension_metadata"] = {
                "canonicalization": "ignored",
                "input_schema": "ignored",
            }
            _write_manifest(bundle, manifest)

            result = verify_ai_bundle(bundle)

            self.assertTrue(result.valid, result)
            self.assertNotIn("extension_metadata", result.assurance_dict())


class TestAIV1CanonicalBytes(unittest.TestCase):
    def test_exact_canonical_bytes_without_terminal_lf_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = canonical_path.read_bytes().removesuffix(b"\n")
            canonical_path.write_bytes(canonical)

            self.assertTrue(verify_ai_bundle(bundle).valid)

    def test_exact_canonical_bytes_with_one_terminal_lf_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)

            self.assertTrue(verify_ai_bundle(bundle).valid)
            self.assertTrue(
                (bundle / "ai_canonical.json").read_bytes().endswith(b"\n")
            )

    def test_noncanonical_byte_representations_are_rejected(self):
        variants = {
            "two_terminal_lfs": lambda canonical, obj: canonical + b"\n\n",
            "crlf": lambda canonical, obj: canonical + b"\r\n",
            "leading_space": lambda canonical, obj: b" " + canonical,
            "trailing_space": lambda canonical, obj: canonical + b" ",
            "pretty_printed": lambda canonical, obj: json.dumps(
                obj,
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8"),
        }
        for name, make_raw in variants.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _pack(bundle)
                    canonical_path = bundle / "ai_canonical.json"
                    canonical = canonical_path.read_bytes().removesuffix(b"\n")
                    obj = json.loads(canonical.decode("utf-8"))
                    raw = make_raw(canonical, obj)
                    _write_canonical_bytes_with_raw_hash(bundle, raw)

                    result = verify_ai_bundle(bundle)

                    self.assertFalse(result.valid)
                    self.assertEqual(result.reason, "CANONICAL_BYTES_MISMATCH")

    def test_alternate_key_order_with_matching_raw_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = canonical_path.read_bytes().removesuffix(b"\n")
            obj = json.loads(canonical.decode("utf-8"))
            reversed_obj = {key: obj[key] for key in reversed(obj)}
            alternate = json.dumps(
                reversed_obj,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            self.assertNotEqual(alternate, canonical)
            _write_canonical_bytes_with_raw_hash(bundle, alternate)

            result = verify_ai_bundle(bundle)

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "CANONICAL_BYTES_MISMATCH")

    def test_schema_invalid_canonical_with_matching_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            canonical_path = bundle / "ai_canonical.json"
            obj = json.loads(canonical_path.read_text(encoding="utf-8"))
            obj.pop("model")
            raw = json.dumps(
                obj,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            _write_canonical_bytes_with_raw_hash(bundle, raw)

            result = verify_ai_bundle(bundle)

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "CANONICAL_SCHEMA_INVALID")

    def test_unsupported_canonical_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _pack(bundle)
            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(
                canonical_path.read_text(encoding="utf-8")
            )
            canonical["schema_version"] = "ai_output_v2"
            canonical_hash = _rewrite_canonical(bundle, canonical)

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["ai_hash_sha256"] = canonical_hash
            _write_manifest(bundle, manifest)

            result = verify_ai_bundle(bundle)

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "CANONICAL_SCHEMA_INVALID")


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

    def test_signature_stripping_requires_caller_declared_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            signed = verify_ai_bundle(bundle)
            self.assertTrue(signed.valid)
            self.assertEqual(
                signed.signature_validity,
                AssuranceState.VALID,
            )

            (bundle / "verification_keys.json").unlink()

            default = verify_ai_bundle(bundle)
            self.assertTrue(default.valid)
            self.assertEqual(
                default.signature_validity,
                AssuranceState.ABSENT,
            )
            self.assertEqual(
                default.trusted_signer_identity,
                AssuranceState.UNESTABLISHED,
            )
            for name, output in _public_verifier_outputs(bundle).items():
                with self.subTest(surface=name, mode="default"):
                    self.assertEqual(
                        output.returncode,
                        0,
                        output.stdout + output.stderr,
                    )
                    payload = json.loads(output.stdout)
                    self.assertEqual(payload["signature_validity"], "ABSENT")
                    self.assertEqual(
                        payload["trusted_signer_identity"],
                        "UNESTABLISHED",
                    )

            required = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(require_signature=True),
            )
            self.assertFalse(required.valid)
            self.assertEqual(required.reason, "SIGNATURE_REQUIRED")
            self.assertEqual(
                required.signature_validity,
                AssuranceState.ABSENT,
            )
            for name, output in _public_verifier_outputs(
                bundle,
                "--require-signature",
            ).items():
                with self.subTest(surface=name, mode="required"):
                    self.assertEqual(output.returncode, 2)
                    if name == "standalone":
                        payload = json.loads(output.stdout)
                        self.assertEqual(
                            payload["reason"],
                            "SIGNATURE_REQUIRED",
                        )
                        self.assertEqual(
                            payload["signature_validity"],
                            "ABSENT",
                        )
                    else:
                        self.assertIn("reason=SIGNATURE_REQUIRED", output.stdout)
                        self.assertIn(
                            "SIGNATURE_VALIDITY=ABSENT",
                            output.stdout,
                        )

    def test_binding_stripping_requires_caller_declared_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            bound = verify_ai_bundle(bundle)
            self.assertTrue(bound.valid)
            self.assertEqual(
                bound.binding_field_consistency,
                AssuranceState.VALID,
            )

            canonical_path = bundle / "ai_canonical.json"
            canonical = json.loads(
                canonical_path.read_text(encoding="utf-8")
            )
            for field in ("request_hash", "response_hash", "binding_hash"):
                canonical["metadata"].pop(field)
            canonical_hash = _rewrite_canonical(bundle, canonical)

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest.pop("binding_hash")
            manifest["ai_hash_sha256"] = canonical_hash
            _write_manifest(bundle, manifest)

            default = verify_ai_bundle(bundle)
            self.assertTrue(default.valid)
            self.assertEqual(
                default.binding_field_consistency,
                AssuranceState.ABSENT,
            )
            for name, output in _public_verifier_outputs(bundle).items():
                with self.subTest(surface=name, mode="default"):
                    self.assertEqual(
                        output.returncode,
                        0,
                        output.stdout + output.stderr,
                    )
                    payload = json.loads(output.stdout)
                    self.assertEqual(
                        payload["binding_field_consistency"],
                        "ABSENT",
                    )

            required = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(require_binding=True),
            )
            self.assertFalse(required.valid)
            self.assertEqual(required.reason, "BINDING_REQUIRED")
            self.assertEqual(
                required.binding_field_consistency,
                AssuranceState.ABSENT,
            )
            for name, output in _public_verifier_outputs(
                bundle,
                "--require-binding",
            ).items():
                with self.subTest(surface=name, mode="required"):
                    self.assertEqual(output.returncode, 2)
                    if name == "standalone":
                        payload = json.loads(output.stdout)
                        self.assertEqual(
                            payload["reason"],
                            "BINDING_REQUIRED",
                        )
                        self.assertEqual(
                            payload["binding_field_consistency"],
                            "ABSENT",
                        )
                    else:
                        self.assertIn("reason=BINDING_REQUIRED", output.stdout)
                        self.assertIn(
                            "BINDING_FIELD_CONSISTENCY=ABSENT",
                            output.stdout,
                        )

    def test_valid_signer_substitution_establishes_no_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            verification_path = bundle / "verification_keys.json"
            original = json.loads(
                verification_path.read_text(encoding="utf-8")
            )

            attacker_material = _verification_material_for_key(
                bundle,
                Ed25519PrivateKey.generate(),
            )
            self.assertNotEqual(
                attacker_material["keys"][0]["public_key_b64"],
                original["keys"][0]["public_key_b64"],
            )
            verification_path.write_text(
                json.dumps(attacker_material, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = verify_ai_bundle(bundle)
            self.assertTrue(result.valid)
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity,
                AssuranceState.UNESTABLISHED,
            )
            self.assertEqual(result.freshness, AssuranceState.NOT_EVALUATED)
            self.assertEqual(
                result.authorization,
                AssuranceState.NOT_EVALUATED,
            )

            for name, output in _public_verifier_outputs(
                bundle,
                "--require-signature",
            ).items():
                with self.subTest(surface=name):
                    self.assertEqual(
                        output.returncode,
                        0,
                        output.stdout + output.stderr,
                    )
                    payload = json.loads(output.stdout)
                    self.assertEqual(payload["signature_validity"], "VALID")
                    self.assertEqual(
                        payload["trusted_signer_identity"],
                        "UNESTABLISHED",
                    )
                    self.assertEqual(payload["freshness"], "NOT_EVALUATED")
                    self.assertEqual(
                        payload["authorization"],
                        "NOT_EVALUATED",
                    )

    def test_unsupported_signing_contract_values_are_rejected(self):
        cases = (
            ("keyring_format", "BAD_KEYRING_FORMAT"),
            ("signature_algorithm", "BAD_SIGNATURE_ALGORITHM"),
        )
        for case, expected_detail in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as directory:
                    bundle = Path(directory)
                    _make_bound_bundle(bundle)
                    _sign_bundle(bundle)
                    verification_path = bundle / "verification_keys.json"
                    verification = json.loads(
                        verification_path.read_text(encoding="utf-8")
                    )
                    if case == "keyring_format":
                        verification["keyring_format"] = "ed25519-v2"
                    else:
                        verification["signatures"][0]["algorithm"] = "ed448"
                    verification_path.write_text(
                        json.dumps(verification, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )

                    result = verify_ai_bundle(bundle)

                    self.assertFalse(result.valid)
                    self.assertEqual(result.reason, "SIGNATURE_INVALID")
                    self.assertEqual(result.detail, expected_detail)
                    self.assertEqual(
                        result.signature_validity,
                        AssuranceState.INVALID,
                    )

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


class TestAITrustedSignerIdentity(unittest.TestCase):
    """P1.1b: trust-store-backed trusted_signer_identity evaluation."""

    def test_verify_manifest_signature_returns_verified_public_key_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            private_key = Ed25519PrivateKey.generate()
            public_key_b64 = _sign_bundle_with_key(bundle, private_key)

            vk = json.loads(
                (bundle / "verification_keys.json").read_text(encoding="utf-8")
            )
            manifest_bytes = (bundle / "ai_manifest.json").read_bytes()

            result = verify_manifest_signature(manifest_bytes, vk)

            self.assertIsInstance(result, VerifiedManifestSignature)
            self.assertEqual(
                result.public_key_bytes,
                base64.b64decode(public_key_b64),
            )
            self.assertEqual(
                result.public_key_bytes,
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                ),
            )

    def test_no_trust_input_preserves_current_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)

            result = verify_ai_bundle(bundle)

            self.assertTrue(result.valid)
            self.assertEqual(result.reason, "OK")
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )
            self.assertEqual(result.trusted_signer_reason, "")

    def test_trust_store_with_signer_key_establishes_valid_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            private_key = Ed25519PrivateKey.generate()
            public_key_b64 = _sign_bundle_with_key(bundle, private_key)
            trust_store_path = _write_trust_store(bundle, [public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertTrue(result.valid)
            self.assertEqual(result.reason, "OK")
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(result.trusted_signer_identity, AssuranceState.VALID)
            self.assertEqual(result.trusted_signer_reason, "")

    def test_trust_store_without_signer_key_stays_unestablished(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle_with_key(bundle, Ed25519PrivateKey.generate())
            other_key = Ed25519PrivateKey.generate()
            other_public_key_b64 = base64.b64encode(
                other_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            trust_store_path = _write_trust_store(bundle, [other_public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertTrue(result.valid)
            self.assertEqual(result.reason, "OK")
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )
            self.assertEqual(
                result.trusted_signer_reason, "TRUSTED_SIGNER_NOT_FOUND"
            )

    def test_require_trusted_signer_with_trusted_key_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            private_key = Ed25519PrivateKey.generate()
            public_key_b64 = _sign_bundle_with_key(bundle, private_key)
            trust_store_path = _write_trust_store(bundle, [public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(
                    trust_store_path=trust_store_path,
                    require_trusted_signer=True,
                ),
            )

            self.assertTrue(result.valid)
            self.assertEqual(result.reason, "OK")
            self.assertEqual(result.trusted_signer_identity, AssuranceState.VALID)

    def test_require_trusted_signer_with_unknown_key_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle_with_key(bundle, Ed25519PrivateKey.generate())
            other_key = Ed25519PrivateKey.generate()
            other_public_key_b64 = base64.b64encode(
                other_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            trust_store_path = _write_trust_store(bundle, [other_public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(
                    trust_store_path=trust_store_path,
                    require_trusted_signer=True,
                ),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "TRUSTED_SIGNER_NOT_FOUND")
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )

    def test_require_trusted_signer_without_trust_store_path_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(require_trusted_signer=True),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "TRUST_INPUT_NOT_PROVIDED")

    def test_malformed_trust_store_is_invalid_without_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            trust_store_path = bundle / "trust_store.json"
            trust_store_path.write_text("{not valid json", encoding="utf-8")

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "TRUST_STORE_INVALID")
            self.assertEqual(result.detail, "TRUST_STORE_NOT_JSON")

    def test_missing_trust_store_path_is_invalid_without_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            _sign_bundle(bundle)
            missing_path = bundle / "does_not_exist_trust_store.json"

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=missing_path),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "TRUST_STORE_INVALID")
            self.assertEqual(result.detail, "TRUST_STORE_IO_ERROR")

    def test_unsigned_bundle_with_trust_store_no_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            other_key = Ed25519PrivateKey.generate()
            other_public_key_b64 = base64.b64encode(
                other_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            trust_store_path = _write_trust_store(bundle, [other_public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertTrue(result.valid)
            self.assertEqual(result.signature_validity, AssuranceState.ABSENT)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )

    def test_unsigned_bundle_with_trust_store_and_requirement_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            other_key = Ed25519PrivateKey.generate()
            other_public_key_b64 = base64.b64encode(
                other_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            trust_store_path = _write_trust_store(bundle, [other_public_key_b64])

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(
                    trust_store_path=trust_store_path,
                    require_trusted_signer=True,
                ),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "SIGNATURE_REQUIRED")

    def test_invalid_signature_from_trusted_key_does_not_establish_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            private_key = Ed25519PrivateKey.generate()
            public_key_b64 = _sign_bundle_with_key(bundle, private_key)
            trust_store_path = _write_trust_store(bundle, [public_key_b64])

            verification_path = bundle / "verification_keys.json"
            verification = json.loads(
                verification_path.read_text(encoding="utf-8")
            )
            sig_bytes = bytearray(
                base64.b64decode(verification["signatures"][0]["sig_b64"])
            )
            sig_bytes[0] ^= 0xFF
            verification["signatures"][0]["sig_b64"] = base64.b64encode(
                bytes(sig_bytes)
            ).decode("ascii")
            verification_path.write_text(
                json.dumps(verification, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "SIGNATURE_INVALID")
            self.assertEqual(result.signature_validity, AssuranceState.INVALID)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )

    def test_attacker_key_substitution_unestablished_without_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            legit_key = Ed25519PrivateKey.generate()
            legit_public_key_b64 = _sign_bundle_with_key(bundle, legit_key)
            trust_store_path = _write_trust_store(bundle, [legit_public_key_b64])

            attacker_key = Ed25519PrivateKey.generate()
            attacker_public_key_b64 = _sign_bundle_with_key(bundle, attacker_key)
            self.assertNotEqual(attacker_public_key_b64, legit_public_key_b64)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertTrue(result.valid)
            self.assertEqual(result.payload_integrity, AssuranceState.VALID)
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(
                result.trusted_signer_identity, AssuranceState.UNESTABLISHED
            )

    def test_attacker_key_substitution_rejected_with_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            legit_key = Ed25519PrivateKey.generate()
            legit_public_key_b64 = _sign_bundle_with_key(bundle, legit_key)
            trust_store_path = _write_trust_store(bundle, [legit_public_key_b64])

            attacker_key = Ed25519PrivateKey.generate()
            _sign_bundle_with_key(bundle, attacker_key)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(
                    trust_store_path=trust_store_path,
                    require_trusted_signer=True,
                ),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "TRUSTED_SIGNER_NOT_FOUND")

    def test_trusted_identity_independent_of_binding_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _make_bound_bundle(bundle)
            private_key = Ed25519PrivateKey.generate()
            public_key_b64 = _sign_bundle_with_key(bundle, private_key)
            trust_store_path = _write_trust_store(bundle, [public_key_b64])

            manifest_path = bundle / "ai_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["binding_hash"] = "b" * 64
            _write_manifest(bundle, manifest)
            # Re-sign over the mutated manifest bytes so signature_validity
            # itself stays VALID and only binding consistency is broken.
            _sign_bundle_with_key(bundle, private_key)

            result = verify_ai_bundle(
                bundle,
                options=AIVerificationOptions(trust_store_path=trust_store_path),
            )

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "BINDING_HASH_MISMATCH")
            self.assertEqual(result.signature_validity, AssuranceState.VALID)
            self.assertEqual(result.trusted_signer_identity, AssuranceState.VALID)


if __name__ == "__main__":
    unittest.main()
