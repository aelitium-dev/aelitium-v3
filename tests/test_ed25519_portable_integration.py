"""Integration tests for explicit portable Ed25519 bundle verification."""

import base64
import copy
import json
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest import mock

import engine.signing as signing
from engine.ai_verify import AIVerificationOptions, AssuranceState, verify_ai_bundle
from engine.trust import fingerprint_public_key
from engine.verifier_capabilities import (
    ED25519_PORTABLE_STRICT_1,
    CapabilityProfileUnavailable,
    select_signature_verification_profile,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "conformance" / "verifier_contract_phase2" / "fixtures"
VALID_PUBLIC_KEY = bytes.fromhex(
    "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8"
)
IDENTITY_R_ZERO_S = bytes.fromhex("01" + "00" * 63)
BACKEND_SENSITIVE_KEYS = {
    "x_zero_sign_one": bytes.fromhex("01" + "00" * 30 + "0080"),
    "y_p_plus_one": bytes.fromhex("ee" + "ff" * 30 + "ff7f"),
}


def _keyring(name: str = "semantic_keyring_valid.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@contextmanager
def _bundle(
    *,
    keyring: dict | None = None,
    trust_fixture: str | None = None,
) -> Iterator[tuple[Path, Path | None]]:
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / "bundle"
        bundle.mkdir()
        shutil.copyfile(
            FIXTURES / "semantic_ai_canonical.json",
            bundle / "ai_canonical.json",
        )
        shutil.copyfile(
            FIXTURES / "semantic_manifest_valid.json",
            bundle / "ai_manifest.json",
        )
        selected_keyring = _keyring() if keyring is None else keyring
        (bundle / "verification_keys.json").write_text(
            json.dumps(selected_keyring),
            encoding="utf-8",
        )

        trust_path = None
        if trust_fixture is not None:
            trust_path = Path(directory) / "trust.json"
            shutil.copyfile(FIXTURES / trust_fixture, trust_path)
        yield bundle, trust_path


def _strict_options(**changes) -> AIVerificationOptions:
    return AIVerificationOptions(
        signature_verification_profile=ED25519_PORTABLE_STRICT_1,
        **changes,
    )


class TestEd25519PortableBundleIntegration(unittest.TestCase):
    def test_selector_is_exact_and_has_no_default_or_alias(self):
        self.assertIsNone(select_signature_verification_profile(None))
        self.assertEqual(
            select_signature_verification_profile(ED25519_PORTABLE_STRICT_1),
            ED25519_PORTABLE_STRICT_1,
        )
        for requested in (
            "UNKNOWN",
            "ed25519_portable_strict_1",
            " ED25519_PORTABLE_STRICT_1",
            "ED25519_PORTABLE_STRICT_1 ",
        ):
            with self.subTest(requested=requested):
                with self.assertRaises(CapabilityProfileUnavailable):
                    select_signature_verification_profile(requested)

    def test_explicit_strict_profile_accepts_canonical_signed_bundle(self):
        with _bundle() as (bundle, _):
            with mock.patch.object(
                signing,
                "verify_manifest_signature",
                side_effect=AssertionError("generic verifier must not be called"),
            ), mock.patch.object(
                signing,
                "verify_manifest_signature_portable_strict_1",
                wraps=signing.verify_manifest_signature_portable_strict_1,
            ) as strict_verifier:
                result = verify_ai_bundle(bundle, options=_strict_options())

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "OK")
        self.assertIs(result.signature_validity, AssuranceState.VALID)
        strict_verifier.assert_called_once()

    def test_strict_profile_rejects_backend_sensitive_key_encodings(self):
        for name, public_key in BACKEND_SENSITIVE_KEYS.items():
            keyring = copy.deepcopy(_keyring())
            keyring["keys"][0]["public_key_b64"] = base64.b64encode(
                public_key
            ).decode("ascii")
            keyring["signatures"][0]["sig_b64"] = base64.b64encode(
                IDENTITY_R_ZERO_S
            ).decode("ascii")

            with self.subTest(name=name), _bundle(keyring=keyring) as (bundle, _):
                result = verify_ai_bundle(bundle, options=_strict_options())

            self.assertFalse(result.valid)
            self.assertEqual(result.reason, "SIGNATURE_INVALID")
            self.assertIs(result.signature_validity, AssuranceState.INVALID)

    def test_strict_profile_rejects_modified_signature(self):
        with _bundle(
            keyring=_keyring("semantic_keyring_modified_signature.json")
        ) as (bundle, _):
            result = verify_ai_bundle(bundle, options=_strict_options())

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "SIGNATURE_INVALID")
        self.assertIs(result.signature_validity, AssuranceState.INVALID)

    def test_omitted_profile_uses_only_legacy_verifier(self):
        options = AIVerificationOptions()
        self.assertIsNone(options.signature_verification_profile)

        with _bundle() as (bundle, _):
            with mock.patch.object(
                signing,
                "verify_manifest_signature",
                wraps=signing.verify_manifest_signature,
            ) as legacy_verifier, mock.patch.object(
                signing,
                "verify_manifest_signature_portable_strict_1",
                side_effect=AssertionError("strict verifier must not be called"),
            ):
                result = verify_ai_bundle(bundle, options=options)

        self.assertTrue(result.valid)
        self.assertIs(result.signature_validity, AssuranceState.VALID)
        legacy_verifier.assert_called_once()
        self.assertFalse(hasattr(result, "signature_verification_profile"))

    def test_unsupported_profile_is_typed_operational_plumbing_before_io(self):
        options = AIVerificationOptions(
            trust_store_path="/unreadable/trust.json",
            require_trusted_signer=True,
            signature_verification_profile="UNKNOWN",
        )
        with mock.patch(
            "engine.ai_verify.load_trust_store",
            side_effect=AssertionError("trust input must not be accessed"),
        ), mock.patch.object(
            Path,
            "exists",
            side_effect=AssertionError("bundle input must not be inspected"),
        ), mock.patch.object(
            Path,
            "is_file",
            side_effect=AssertionError("bundle input must not be inspected"),
        ), mock.patch.object(
            Path,
            "read_bytes",
            side_effect=AssertionError("bundle input must not be read"),
        ), mock.patch.object(
            Path,
            "read_text",
            side_effect=AssertionError("bundle input must not be read"),
        ):
            with self.assertRaises(CapabilityProfileUnavailable) as caught:
                verify_ai_bundle("/bundle/does/not/exist", options=options)

        error = caught.exception
        self.assertEqual(error.operational_code, "CAPABILITY_PROFILE_UNAVAILABLE")
        self.assertEqual(error.phase, "CAPABILITY_SELECTION")
        self.assertEqual(error.requested_profile, "UNKNOWN")
        self.assertIsNone(error.effective_profile)

    def test_strict_verified_key_bytes_drive_trust_membership(self):
        with _bundle(trust_fixture="semantic_trust_matching.json") as (
            bundle,
            trust_path,
        ):
            with mock.patch(
                "engine.ai_verify.fingerprint_public_key",
                wraps=fingerprint_public_key,
            ) as fingerprint:
                result = verify_ai_bundle(
                    bundle,
                    options=_strict_options(
                        trust_store_path=trust_path,
                        require_trusted_signer=True,
                    ),
                )

        self.assertTrue(result.valid)
        self.assertIs(result.signature_validity, AssuranceState.VALID)
        self.assertIs(result.trusted_signer_identity, AssuranceState.VALID)
        fingerprint.assert_called_once_with(VALID_PUBLIC_KEY)


if __name__ == "__main__":
    unittest.main()
