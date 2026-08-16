"""Tests for the local trusted-signer store primitive (engine/trust.py).

All keys used here are fixed, deterministic byte sequences (not real Ed25519
keypairs) since this module only exercises base64 decoding, length checks,
and SHA-256 fingerprint derivation. Golden fingerprint values were
independently cross-checked with `sha256sum` outside this test suite.
"""

import copy
import unittest

from engine.trust import (
    ED25519_PUBLIC_KEY_LENGTH,
    SUPPORTED_ALGORITHM,
    TRUST_STORE_FORMAT,
    TrustedSigner,
    TrustStore,
    TrustStoreError,
    fingerprint_public_key,
    load_trust_store_text,
    parse_trust_store,
)

# --- fixed deterministic key material -------------------------------------

KEY_A_B64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # 32 zero bytes
KEY_A_FINGERPRINT = (
    "ed25519:sha256:"
    "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"
)

KEY_B_B64 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="  # bytes(range(32))
KEY_B_FINGERPRINT = (
    "ed25519:sha256:"
    "630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd"
)

KEY_C_B64 = "//////////////////////////////////////////8="  # 32 0xFF bytes
KEY_C_FINGERPRINT = (
    "ed25519:sha256:"
    "af9613760f72635fbdb44a5a0a63c39f12af30f950a6ee5c971be188e89c4051"
)

SHORT_KEY_B64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="  # 31 bytes
LONG_KEY_B64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # 33 bytes
BAD_B64 = "not-valid-base64!!"


def _store(signers):
    return {"trust_store_format": TRUST_STORE_FORMAT, "signers": signers}


def _signer(key_b64=KEY_A_B64, label=None, algorithm=SUPPORTED_ALGORITHM):
    entry = {"algorithm": algorithm, "public_key_b64": key_b64}
    if label is not None:
        entry["label"] = label
    return entry


class TestFingerprintPublicKey(unittest.TestCase):
    def test_golden_vector_zero_bytes(self):
        self.assertEqual(fingerprint_public_key(bytes(32)), KEY_A_FINGERPRINT)

    def test_golden_vector_sequential_bytes(self):
        self.assertEqual(fingerprint_public_key(bytes(range(32))), KEY_B_FINGERPRINT)

    def test_golden_vector_ff_bytes(self):
        self.assertEqual(fingerprint_public_key(bytes([0xFF] * 32)), KEY_C_FINGERPRINT)

    def test_deterministic_same_input_same_output(self):
        first = fingerprint_public_key(bytes(range(32)))
        second = fingerprint_public_key(bytes(range(32)))
        self.assertEqual(first, second)

    def test_lowercase_hex(self):
        fp = fingerprint_public_key(bytes([0xFF] * 32))
        hex_part = fp.rsplit(":", 1)[-1]
        self.assertEqual(hex_part, hex_part.lower())
        self.assertEqual(len(hex_part), 64)

    def test_different_key_different_fingerprint(self):
        fp_a = fingerprint_public_key(bytes(32))
        fp_b = fingerprint_public_key(bytes(range(32)))
        self.assertNotEqual(fp_a, fp_b)

    def test_rejects_wrong_length(self):
        with self.assertRaises(TrustStoreError) as ctx:
            fingerprint_public_key(bytes(31))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_PUBLIC_KEY")

    def test_rejects_non_bytes(self):
        with self.assertRaises(TrustStoreError) as ctx:
            fingerprint_public_key("not-bytes")
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_PUBLIC_KEY")


class TestValidStores(unittest.TestCase):
    def test_valid_one_key_store(self):
        store = parse_trust_store(_store([_signer(KEY_A_B64)]))
        self.assertIsInstance(store, TrustStore)
        self.assertEqual(store.format, TRUST_STORE_FORMAT)
        self.assertEqual(len(store.signers), 1)
        signer = store.signers[0]
        self.assertIsInstance(signer, TrustedSigner)
        self.assertEqual(signer.algorithm, SUPPORTED_ALGORITHM)
        self.assertEqual(signer.fingerprint, KEY_A_FINGERPRINT)
        self.assertIsNone(signer.label)
        self.assertEqual(len(signer.public_key_bytes), ED25519_PUBLIC_KEY_LENGTH)

    def test_valid_multiple_key_store(self):
        store = parse_trust_store(
            _store([_signer(KEY_A_B64), _signer(KEY_B_B64), _signer(KEY_C_B64)])
        )
        self.assertEqual(len(store.signers), 3)
        self.assertEqual(
            store.fingerprints(),
            frozenset({KEY_A_FINGERPRINT, KEY_B_FINGERPRINT, KEY_C_FINGERPRINT}),
        )

    def test_order_independence(self):
        store_1 = parse_trust_store(
            _store([_signer(KEY_A_B64), _signer(KEY_B_B64), _signer(KEY_C_B64)])
        )
        store_2 = parse_trust_store(
            _store([_signer(KEY_C_B64), _signer(KEY_A_B64), _signer(KEY_B_B64)])
        )
        self.assertEqual(store_1.fingerprints(), store_2.fingerprints())
        for fp in (KEY_A_FINGERPRINT, KEY_B_FINGERPRINT, KEY_C_FINGERPRINT):
            self.assertIsNotNone(store_1.find_by_fingerprint(fp))
            self.assertIsNotNone(store_2.find_by_fingerprint(fp))

    def test_optional_label_present(self):
        store = parse_trust_store(_store([_signer(KEY_A_B64, label="release-key")]))
        self.assertEqual(store.signers[0].label, "release-key")

    def test_missing_label_is_none(self):
        store = parse_trust_store(_store([_signer(KEY_A_B64)]))
        self.assertIsNone(store.signers[0].label)

    def test_empty_signer_list_is_valid(self):
        # An empty trust store is not malformed: it establishes no trust,
        # which is a legitimate, deterministic (fail-closed-by-absence) state.
        store = parse_trust_store(_store([]))
        self.assertEqual(store.signers, ())
        self.assertEqual(store.fingerprints(), frozenset())
        self.assertIsNone(store.find_by_fingerprint(KEY_A_FINGERPRINT))
        self.assertNotIn(KEY_A_FINGERPRINT, store)

    def test_lookup_contains(self):
        store = parse_trust_store(_store([_signer(KEY_A_B64)]))
        self.assertIn(KEY_A_FINGERPRINT, store)
        self.assertNotIn(KEY_B_FINGERPRINT, store)

    def test_same_key_same_fingerprint_across_records(self):
        # Same key material appearing (hypothetically) is caught by the
        # duplicate-key rule elsewhere; here we confirm two independently
        # parsed single-signer stores built from the same key bytes agree.
        store_1 = parse_trust_store(_store([_signer(KEY_B_B64)]))
        store_2 = parse_trust_store(_store([_signer(KEY_B_B64, label="other-label")]))
        self.assertEqual(
            store_1.signers[0].fingerprint, store_2.signers[0].fingerprint
        )


class TestTopLevelStructure(unittest.TestCase):
    def test_wrong_format_value(self):
        data = _store([_signer(KEY_A_B64)])
        data["trust_store_format"] = "aelitium-trust-v2"
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_FORMAT")

    def test_missing_top_level_field(self):
        data = {"trust_store_format": TRUST_STORE_FORMAT}
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_STRUCTURE")

    def test_extra_top_level_field(self):
        data = _store([_signer(KEY_A_B64)])
        data["revocation_url"] = "https://example.invalid/revoked"
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_STRUCTURE")

    def test_top_level_not_object(self):
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(["not", "an", "object"])
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_STRUCTURE")

    def test_signers_not_list(self):
        data = _store([_signer(KEY_A_B64)])
        data["signers"] = {"not": "a list"}
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_STRUCTURE")


class TestSignerEntryValidation(unittest.TestCase):
    def test_signer_not_object(self):
        data = _store(["not-an-object"])
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_missing_algorithm(self):
        entry = {"public_key_b64": KEY_A_B64}
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_unsupported_algorithm(self):
        entry = _signer(KEY_A_B64, algorithm="rsa")
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_missing_public_key_b64(self):
        entry = {"algorithm": SUPPORTED_ALGORITHM}
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_bad_base64(self):
        entry = _signer(BAD_B64)
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_PUBLIC_KEY")

    def test_wrong_decoded_key_length_short(self):
        entry = _signer(SHORT_KEY_B64)
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_PUBLIC_KEY")

    def test_wrong_decoded_key_length_long(self):
        entry = _signer(LONG_KEY_B64)
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_PUBLIC_KEY")

    def test_unknown_signer_field(self):
        entry = _signer(KEY_A_B64)
        entry["signer_id"] = "not-allowed-in-this-slice"
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_empty_label_rejected(self):
        entry = _signer(KEY_A_B64, label="")
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")

    def test_non_string_label_rejected(self):
        entry = _signer(KEY_A_B64)
        entry["label"] = 12345
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(_store([entry]))
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_BAD_SIGNER")


class TestDuplicateKeys(unittest.TestCase):
    def test_duplicate_key_rejected(self):
        data = _store([_signer(KEY_A_B64), _signer(KEY_A_B64, label="second-copy")])
        with self.assertRaises(TrustStoreError) as ctx:
            parse_trust_store(data)
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_DUPLICATE_KEY")

    def test_distinct_keys_not_rejected(self):
        data = _store([_signer(KEY_A_B64), _signer(KEY_B_B64)])
        store = parse_trust_store(data)
        self.assertEqual(len(store.signers), 2)


class TestLoadFromText(unittest.TestCase):
    def test_not_json(self):
        with self.assertRaises(TrustStoreError) as ctx:
            load_trust_store_text("{not valid json")
        self.assertEqual(ctx.exception.reason, "TRUST_STORE_NOT_JSON")

    def test_valid_json_text_roundtrip(self):
        import json

        text = json.dumps(_store([_signer(KEY_A_B64, label="ci-release")]))
        store = load_trust_store_text(text)
        self.assertEqual(len(store.signers), 1)
        self.assertEqual(store.signers[0].fingerprint, KEY_A_FINGERPRINT)
        self.assertEqual(store.signers[0].label, "ci-release")


class TestErrorTypeContract(unittest.TestCase):
    def test_trust_store_error_is_value_error(self):
        self.assertTrue(issubclass(TrustStoreError, ValueError))

    def test_deterministic_reason_across_repeated_calls(self):
        data = _store([_signer(BAD_B64)])
        reasons = set()
        for _ in range(3):
            with self.assertRaises(TrustStoreError) as ctx:
                parse_trust_store(copy.deepcopy(data))
            reasons.add(ctx.exception.reason)
        self.assertEqual(reasons, {"TRUST_STORE_BAD_PUBLIC_KEY"})


if __name__ == "__main__":
    unittest.main()
