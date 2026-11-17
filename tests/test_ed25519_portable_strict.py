"""Focused production tests for ``ED25519_PORTABLE_STRICT_1``."""

import ast
import base64
import hashlib
import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from engine import ed25519_portable
from engine.ed25519_portable import verify_ed25519_portable_strict_1
from engine.signing import (
    VerifiedManifestSignature,
    verify_manifest_signature_portable_strict_1,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "verifier_contract_phase2"
SEMANTIC_VECTORS = CORPUS / "semantic_vectors.json"
STRICT_FAMILY = "ED25519_STRICT_SEMANTIC"


def _strict_cases() -> list[dict]:
    document = json.loads(SEMANTIC_VECTORS.read_text(encoding="utf-8"))
    return [case for case in document["vectors"] if case["family"] == STRICT_FAMILY]


def _message_bytes(case: dict) -> bytes:
    source = case["message"]
    if source["kind"] == "INLINE_HEX":
        message = bytes.fromhex(source["hex"])
    elif source["kind"] == "FIXTURE":
        message = (CORPUS / source["path"]).read_bytes()
    else:  # pragma: no cover - corpus shape is checked by its focused suite
        raise AssertionError(f"unexpected strict-vector message source: {source!r}")
    if hashlib.sha256(message).hexdigest() != source["sha256"]:
        raise AssertionError(f"strict-vector message hash differs: {case['case_id']}")
    return message


def _strict_case(case_id: str) -> dict:
    return next(case for case in _strict_cases() if case["case_id"] == case_id)


class TestEd25519PortableStrict1(unittest.TestCase):
    def test_all_frozen_strict_semantic_vectors(self):
        cases = _strict_cases()
        self.assertEqual(len(cases), 12)

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                observed = verify_ed25519_portable_strict_1(
                    bytes.fromhex(case["public_key_hex"]),
                    bytes.fromhex(case["signature_hex"]),
                    _message_bytes(case),
                )
                expected = case["expected"]["signature_validity"] == "VALID"
                self.assertEqual(observed, expected)

    def test_rfc_8032_test_vector_1_and_tampering(self):
        public_key = bytes.fromhex(
            "d75a980182b10ab7d54bfed3c964073a"
            "0ee172f3daa62325af021a68f707511a"
        )
        signature = bytes.fromhex(
            "e5564300c360ac729086e2cc806e828a"
            "84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46b"
            "d25bf5f0595bbe24655141438e7a100b"
        )

        self.assertTrue(verify_ed25519_portable_strict_1(public_key, signature, b""))

        tampered_signature = bytearray(signature)
        tampered_signature[0] ^= 1
        self.assertFalse(
            verify_ed25519_portable_strict_1(
                public_key,
                bytes(tampered_signature),
                b"",
            )
        )
        self.assertFalse(
            verify_ed25519_portable_strict_1(public_key, signature, b"\x00")
        )

    def test_scalar_l_minus_one_and_identity_r_reach_equation(self):
        for case_id in (
            "signature.strict.scalar_l_minus_one_reaches_equation",
            "signature.strict.identity_r_reaches_equation",
        ):
            case = _strict_case(case_id)
            with self.subTest(case_id=case_id):
                with mock.patch.object(
                    ed25519_portable,
                    "_verify_equation",
                    wraps=ed25519_portable._verify_equation,
                ) as equation:
                    self.assertFalse(
                        verify_ed25519_portable_strict_1(
                            bytes.fromhex(case["public_key_hex"]),
                            bytes.fromhex(case["signature_hex"]),
                            _message_bytes(case),
                        )
                    )
                equation.assert_called_once()

    def test_scalar_l_is_rejected_before_equation(self):
        case = _strict_case("signature.strict.scalar_l_rejected")
        with mock.patch.object(
            ed25519_portable,
            "_verify_equation",
            wraps=ed25519_portable._verify_equation,
        ) as equation:
            self.assertFalse(
                verify_ed25519_portable_strict_1(
                    bytes.fromhex(case["public_key_hex"]),
                    bytes.fromhex(case["signature_hex"]),
                    _message_bytes(case),
                )
            )
        equation.assert_not_called()

    def test_strict_module_has_no_backend_or_production_oracle(self):
        source = inspect.getsource(ed25519_portable)
        tree = ast.parse(source)
        imported_modules = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

        forbidden_prefixes = ("cryptography", "engine.signing", "conformance", "tests")
        self.assertFalse(
            any(
                module == prefix or module.startswith(prefix + ".")
                for module in imported_modules
                for prefix in forbidden_prefixes
            )
        )
        self.assertNotIn("Ed25519PublicKey", source)

    def test_explicit_signing_helper_uses_strict_kernel_and_preserves_aliases(self):
        manifest = (CORPUS / "fixtures" / "semantic_manifest_valid.json").read_bytes()
        for fixture in (
            "semantic_keyring_valid.json",
            "semantic_keyring_public_key_alias.json",
            "semantic_keyring_signature_alias.json",
        ):
            with self.subTest(fixture=fixture):
                keyring = json.loads((CORPUS / "fixtures" / fixture).read_text())
                verified = verify_manifest_signature_portable_strict_1(
                    manifest,
                    keyring,
                )
                self.assertIsInstance(verified, VerifiedManifestSignature)
                self.assertEqual(
                    verified.public_key_bytes,
                    base64.b64decode(keyring["keys"][0]["public_key_b64"]),
                )

        bad_keyring = json.loads(
            (CORPUS / "fixtures" / "semantic_keyring_modified_signature.json").read_text()
        )
        with self.assertRaisesRegex(ValueError, "^SIGNATURE_INVALID$"):
            verify_manifest_signature_portable_strict_1(manifest, bad_keyring)


if __name__ == "__main__":
    unittest.main()
