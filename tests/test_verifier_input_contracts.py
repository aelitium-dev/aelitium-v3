import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "engine" / "schemas"
CONTRACT_PATH = ROOT / "docs" / "VERIFIER_INPUT_CONTRACTS_V1.md"
PROTOCOL_PATH = ROOT / "docs" / "VERIFIER_PROTOCOL_V1.md"
TOOL_SCHEMA_PATH = SCHEMA_DIR / "verifier_tool_result_v1.json"

SCHEMA_IDS = {
    "ai_manifest_v1.json": "aelitium://schemas/ai_manifest_v1.json",
    "ai_manifest_v2.json": "aelitium://schemas/ai_manifest_v2.json",
    "verification_keys_v1.json": "aelitium://schemas/verification_keys_v1.json",
    "trust_store_v1.json": "aelitium://schemas/trust_store_v1.json",
}
SCHEMA_HASHES = {
    "ai_manifest_v1.json": "f74a42513aa4b0f96bebbc39a40f36dead79dffe8641a5d76142418e6b477b04",
    "ai_manifest_v2.json": "e83d84801b61eff1c20abecefa381f1e79cf8839e6543cd62fc53f4a0e30c12e",
    "verification_keys_v1.json": "be0d9c8db7f4e3ef18484c3c77d98af65e70bc463db50328d5f2caecbbdbf694",
    "trust_store_v1.json": "011b47e789c64dec3ffee2466939dbea3d7637dce5b3d4bfde213c1cb984faf3",
}


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


class TestVerifierInputContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {name: _load_schema(name) for name in SCHEMA_IDS}
        cls.validators = {
            name: Draft7Validator(schema) for name, schema in cls.schemas.items()
        }

    def test_schemas_are_draft7_with_exact_ids(self):
        for name, expected_id in SCHEMA_IDS.items():
            with self.subTest(schema=name):
                schema = self.schemas[name]
                Draft7Validator.check_schema(schema)
                self.assertEqual(
                    schema["$schema"], "http://json-schema.org/draft-07/schema#"
                )
                self.assertEqual(schema["$id"], expected_id)

    def test_four_input_schemas_are_unchanged_by_signature_profile(self):
        for name, expected_hash in SCHEMA_HASHES.items():
            with self.subTest(schema=name):
                self.assertEqual(
                    hashlib.sha256((SCHEMA_DIR / name).read_bytes()).hexdigest(),
                    expected_hash,
                )

    def test_manifest_schemas_preserve_open_and_conditional_fields(self):
        digest = "0" * 64
        routes = {
            "ai_manifest_v1.json": "json_sorted_keys_no_whitespace_utf8",
            "ai_manifest_v2.json": "aelitium_jcs_profile_v2",
        }
        for name, route in routes.items():
            validator = self.validators[name]
            candidate = {
                "schema": "ai_pack_manifest_v1",
                "ts_utc": {"validation": "disabled"},
                "input_schema": "ai_output_v1",
                "canonicalization": route,
                "ai_hash_sha256": digest,
                "unknown_extension": True,
            }
            with self.subTest(schema=name, case="valid-open-disabled-timestamp"):
                validator.validate(candidate)

            bad = copy.deepcopy(candidate)
            bad["ai_hash_sha256"] = "A" * 64
            with self.subTest(schema=name, case="uppercase-digest"):
                with self.assertRaises(ValidationError):
                    validator.validate(bad)

            bad = copy.deepcopy(candidate)
            del bad["ts_utc"]
            with self.subTest(schema=name, case="missing-required"):
                with self.assertRaises(ValidationError):
                    validator.validate(bad)

    def test_keyring_schema_is_open_and_keeps_relations_procedural(self):
        candidate = {
            "keyring_format": "ed25519-v1",
            "keys": [
                {
                    "key_id": "key-a",
                    "public_key_b64": "A" * 42 + "B=",
                    "ignored": {"legacy_extension": True},
                }
            ],
            "signatures": [
                {
                    "key_id": "key-b",
                    "algorithm": "ed25519",
                    "scope": "manifest.json",
                    "sig_b64": "A" * 85 + "B==",
                    "ignored": {"extension": True},
                }
            ],
            "ignored": 1,
        }
        self.validators["verification_keys_v1.json"].validate(candidate)

        bad = copy.deepcopy(candidate)
        bad["keys"].append(copy.deepcopy(bad["keys"][0]))
        with self.assertRaises(ValidationError):
            self.validators["verification_keys_v1.json"].validate(bad)

        bad = copy.deepcopy(candidate)
        bad["signatures"][0]["sig_b64"] = "A" * 86
        with self.assertRaises(ValidationError):
            self.validators["verification_keys_v1.json"].validate(bad)

    def test_trust_schema_closes_objects_but_leaves_fingerprint_uniqueness_procedural(self):
        signer = {
            "algorithm": "ed25519",
            "public_key_b64": "A" * 43 + "=",
            "label": " ",
        }
        validator = self.validators["trust_store_v1.json"]
        validator.validate({"trust_store_format": "aelitium-trust-v1", "signers": []})
        validator.validate(
            {
                "trust_store_format": "aelitium-trust-v1",
                "signers": [signer, copy.deepcopy(signer)],
            }
        )

        bad = {
            "trust_store_format": "aelitium-trust-v1",
            "signers": [dict(signer, unexpected=True)],
        }
        with self.assertRaises(ValidationError):
            validator.validate(bad)

        bad = {
            "trust_store_format": "aelitium-trust-v1",
            "signers": [dict(signer, label="")],
        }
        with self.assertRaises(ValidationError):
            validator.validate(bad)

    def test_public_contract_freezes_authority_and_operational_boundary(self):
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        required_text = (
            "**Status:** NORMATIVE-UNRELEASED",
            "**Contract identifier:** `aelitium-verifier-input-contracts-v1`",
            "Python and every other implementation are non-normative.",
            "the authorized semantic result is `TRUST_INPUT_NOT_PROVIDED`",
            "No `TRUST_STORE_INVALID` or other semantic result",
            "Only after immutable trust bytes have been established",
            "non-zero unused low pad bits are accepted",
            "generic JSON Schema validator",
            "`ED25519_PORTABLE_STRICT_1`",
            "implicit profile and no fallback.",
            "uncofactored",
            "close specification gaps G-04, G-05, and G-06",
            "adoption-time G-05 status as historical metadata",
            "PHASE2_NORMATIVE_INPUT_CONTRACTS_SCHEMAS_AND_CONFORMANCE",
        )
        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, contract)

    def test_signature_profile_capability_is_exact_and_g05_is_closed(self):
        schema = json.loads(TOOL_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        profile = schema["definitions"]["signature_verification_capability"]
        self.assertEqual(
            profile,
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["profile"],
                "properties": {
                    "profile": {"const": "ED25519_PORTABLE_STRICT_1"}
                },
            },
        )
        profile_validator = Draft7Validator(profile)
        profile_validator.validate({"profile": "ED25519_PORTABLE_STRICT_1"})
        for invalid in (
            {},
            {"profile": "ed25519"},
            {"profile": "LEGACY_BACKEND_COMPATIBILITY"},
        ):
            with self.subTest(invalid_profile=invalid):
                with self.assertRaises(ValidationError):
                    profile_validator.validate(invalid)
        current = schema["definitions"]["current_supported_capability_request"]
        self.assertEqual(
            current,
            {"$ref": "#/definitions/supported_capability_request"},
        )
        self.assertIn(
            "signature_verification",
            schema["definitions"]["supported_capability_request"]["required"],
        )
        semantic_branches = json.dumps(schema["oneOf"][:2], sort_keys=True)
        self.assertEqual(
            semantic_branches.count(
                "#/definitions/current_supported_capability_request"
            ),
            4,
        )
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        self.assertIn("| G-04 | **CLOSED** |", protocol)
        self.assertIn("| G-05 | **CLOSED** |", protocol)
        self.assertIn("| G-06 | **CLOSED** |", protocol)
        self.assertNotIn(
            "| G-05 | **OPEN — NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING** |",
            protocol,
        )


if __name__ == "__main__":
    unittest.main()
