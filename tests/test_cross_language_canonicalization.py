import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.ai_verify import verify_ai_bundle
from engine.canonical import (
    CanonicalizationError,
    canonical_json,
    validate_unicode_scalars,
)
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    SURFACE_LITELLM_COMPLETION,
    InvocationIdentityError,
    build_invocation_identity,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance"
CANONICALIZATION = CORPUS / "canonicalization"


def _load_vectors():
    return json.loads(
        (CANONICALIZATION / "vectors.json").read_text(encoding="utf-8")
    )["vectors"]


class TestFrozenCanonicalizationCorpus(unittest.TestCase):
    def test_manifest_has_30_complete_unique_vectors(self):
        manifest = json.loads(
            (CANONICALIZATION / "manifest.json").read_text(encoding="utf-8")
        )
        vectors = _load_vectors()
        self.assertEqual(manifest["case_count"], 30)
        self.assertEqual(len(vectors), 30)
        self.assertEqual(
            manifest["canonicalization_identifier"],
            "json_sorted_keys_no_whitespace_utf8",
        )
        self.assertEqual(
            manifest["open_domain"],
            ["integer_magnitude_more_than_640_decimal_digits"],
        )
        self.assertEqual(len({item["case_id"] for item in vectors}), 30)
        self.assertEqual(len({item["source_sha256"] for item in vectors}), 30)

        required_expected = {
            "decision",
            "reason",
            "canonical_utf8_hex",
            "sha256",
            "domain",
        }
        for vector in vectors:
            source = bytes.fromhex(vector["source_bytes_hex"])
            self.assertEqual(
                hashlib.sha256(source).hexdigest(), vector["source_sha256"]
            )
            self.assertEqual(set(vector["expected"]), required_expected)
            expected = vector["expected"]
            if expected["decision"] == "ACCEPT":
                canonical = bytes.fromhex(expected["canonical_utf8_hex"])
                self.assertEqual(
                    hashlib.sha256(canonical).hexdigest(), expected["sha256"]
                )
            else:
                self.assertEqual(expected["decision"], "REJECT")
                self.assertIsNone(expected["canonical_utf8_hex"])
                self.assertIsNone(expected["sha256"])

    def test_builder_matches_frozen_bytes_without_engine_imports(self):
        builder = CORPUS / "build_canonicalization_vectors.py"
        text = builder.read_text(encoding="utf-8")
        self.assertNotIn("from engine", text)
        self.assertNotIn("import engine", text)
        result = subprocess.run(
            [sys.executable, str(builder), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runner_is_deterministic_and_passes_all_30_vectors(self):
        outputs = []
        for _ in range(2):
            result = subprocess.run(
                [
                    sys.executable,
                    str(CORPUS / "run_canonicalization.py"),
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        summary = json.loads(outputs[0])
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["cases"], 30)
        self.assertEqual(
            summary["domains"],
            {
                "CROSS_LANGUAGE_SAFE": 15,
                "LEGACY_PRESERVED_OUTSIDE_SUBSET": 3,
                "REJECTED": 12,
            },
        )

    def test_required_cross_language_cases_are_frozen(self):
        cases = {item["case_id"]: item for item in _load_vectors()}
        required = {
            "canonicalization.ascii_baseline_no_lf",
            "canonicalization.multiple_terminal_lf",
            "canonicalization.non_ascii_utf8_single_lf",
            "canonicalization.non_bmp_literal",
            "canonicalization.unicode_key_order",
            "canonicalization.escaped_non_ascii",
            "canonicalization.escaped_non_bmp_pair",
            "canonicalization.control_character_escapes",
            "canonicalization.nested_arrays_and_objects",
            "canonicalization.float_lower_scientific_boundary",
            "canonicalization.float_lower_fixed_boundary",
            "canonicalization.float_upper_fixed_boundary",
            "canonicalization.float_upper_scientific_boundary",
            "canonicalization.float_rounding_sensitive",
            "canonicalization.float_rounding_alias",
            "canonicalization.binary64_finite_extremes",
            "canonicalization.float_negative_zero",
            "canonicalization.integer_negative_zero",
            "canonicalization.integer_common_boundaries",
            "canonicalization.integer_640_digit_subset_boundary",
            "canonicalization.nan_exact_legacy_token",
            "canonicalization.nan_lowercase_rejected",
            "canonicalization.infinity_exact_legacy_token",
            "canonicalization.infinity_plus_sign_rejected",
            "canonicalization.negative_infinity_exact_legacy_token",
            "canonicalization.negative_infinity_lowercase_rejected",
            "canonicalization.duplicate_object_name",
            "canonicalization.ill_formed_utf8",
            "canonicalization.unpaired_surrogate_escape",
            "canonicalization.insignificant_whitespace",
        }
        self.assertEqual(set(cases), required)

        for accepted, rejected in (
            (
                "canonicalization.nan_exact_legacy_token",
                "canonicalization.nan_lowercase_rejected",
            ),
            (
                "canonicalization.infinity_exact_legacy_token",
                "canonicalization.infinity_plus_sign_rejected",
            ),
            (
                "canonicalization.negative_infinity_exact_legacy_token",
                "canonicalization.negative_infinity_lowercase_rejected",
            ),
        ):
            self.assertEqual(cases[accepted]["expected"]["decision"], "ACCEPT")
            self.assertEqual(
                cases[accepted]["expected"]["domain"],
                "LEGACY_PRESERVED_OUTSIDE_SUBSET",
            )
            self.assertEqual(cases[rejected]["expected"]["decision"], "REJECT")
            self.assertEqual(
                cases[rejected]["expected"]["reason"], "CANONICAL_NOT_JSON"
            )

    def test_unicode_order_and_float_spellings_are_explicit(self):
        cases = {item["case_id"]: item for item in _load_vectors()}
        unicode_bytes = bytes.fromhex(
            cases["canonicalization.unicode_key_order"]["expected"][
                "canonical_utf8_hex"
            ]
        )
        ordered_fragments = [
            '"a":1'.encode(),
            '"é":2'.encode("utf-8"),
            '"é":3'.encode("utf-8"),
            '"\ue000":4'.encode("utf-8"),
            '"😀":5'.encode("utf-8"),
        ]
        positions = [unicode_bytes.index(fragment) for fragment in ordered_fragments]
        self.assertEqual(positions, sorted(positions))

        expected_tokens = {
            "canonicalization.float_lower_scientific_boundary": b'"n":1e-05',
            "canonicalization.float_lower_fixed_boundary": b'"n":0.0001',
            "canonicalization.float_upper_fixed_boundary": (
                b'"n":1000000000000000.0'
            ),
            "canonicalization.float_upper_scientific_boundary": b'"n":1e+16',
            "canonicalization.float_rounding_sensitive": (
                b'"n":0.30000000000000004'
            ),
            "canonicalization.float_negative_zero": b'"n":-0.0',
        }
        for case_id, token in expected_tokens.items():
            canonical = bytes.fromhex(
                cases[case_id]["expected"]["canonical_utf8_hex"]
            )
            self.assertIn(token, canonical)


class TestCompatibilityPreservingRestrictions(unittest.TestCase):
    def test_unicode_validation_does_not_narrow_deep_container_domain(self):
        value = "scalar"
        for _ in range(2_000):
            value = [value]

        validate_unicode_scalars(value)

    def test_unpaired_surrogates_are_rejected_before_utf8_hashing(self):
        with self.assertRaises(CanonicalizationError) as raised:
            canonical_json({"value": "\ud800"})
        self.assertEqual(raised.exception.reason, "INVALID_UNICODE_SCALAR")

        with self.assertRaises(CanonicalizationError) as raised_key:
            canonical_json({"\udc00": "value"})
        self.assertEqual(raised_key.exception.reason, "INVALID_UNICODE_SCALAR")

    def test_invocation_surrogate_uses_existing_bad_value_reason(self):
        with self.assertRaises(InvocationIdentityError) as raised:
            build_invocation_identity(
                surface=SURFACE_LITELLM_COMPLETION,
                mode=MODE_SYNC_NON_STREAMING,
                model="model",
                messages=[{"role": "user", "content": "\ud800"}],
            )
        self.assertEqual(raised.exception.reason, "INVOCATION_BAD_VALUE")

    def test_surrogate_rejection_preserves_existing_reason_precedence(self):
        with self.assertRaises(InvocationIdentityError) as raised:
            build_invocation_identity(
                surface=SURFACE_LITELLM_COMPLETION,
                mode=MODE_SYNC_NON_STREAMING,
                model="\ud800",
                messages="not-a-list",
            )
        self.assertEqual(raised.exception.reason, "INVOCATION_BAD_REQUEST")

        canonical = (
            b'{"metadata":{"s":"\\ud800"},"model":"m","output":"o",'
            b'"prompt":"p","schema_version":"ai_output_v1",'
            b'"ts_utc":"2026-01-01T00:00:00Z"}'
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "ai_canonical.json").write_bytes(canonical)
            (bundle / "ai_manifest.json").write_text(
                '{"schema":"ai_pack_manifest_v1"}\n', encoding="utf-8"
            )
            result = verify_ai_bundle(bundle)
        self.assertEqual(result.reason, "MANIFEST_MISSING_FIELD")

        schema_invalid = canonical.replace(b',"output":"o"', b"")
        manifest = (
            '{"schema":"ai_pack_manifest_v1",'
            '"ts_utc":"2026-01-01T00:00:00Z",'
            '"input_schema":"ai_output_v1",'
            '"canonicalization":"json_sorted_keys_no_whitespace_utf8",'
            '"ai_hash_sha256":"'
            + ("0" * 64)
            + '"}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "ai_canonical.json").write_bytes(schema_invalid)
            (bundle / "ai_manifest.json").write_text(manifest, encoding="utf-8")
            result = verify_ai_bundle(bundle)
        self.assertEqual(result.reason, "CANONICAL_SCHEMA_INVALID")

    def test_duplicate_manifest_members_retain_v040_last_value_behavior(self):
        vectors = {item["case_id"]: item for item in _load_vectors()}
        baseline = vectors["canonicalization.ascii_baseline_no_lf"]
        canonical = bytes.fromhex(baseline["source_bytes_hex"])
        digest = baseline["expected"]["sha256"]

        def verify_with_schema_members(first: str, second: str):
            manifest = (
                '{"schema":"'
                + first
                + '","schema":"'
                + second
                + '","ts_utc":"2026-01-01T00:00:00Z",'
                '"input_schema":"ai_output_v1",'
                '"canonicalization":"json_sorted_keys_no_whitespace_utf8",'
                '"ai_hash_sha256":"'
                + digest
                + '"}\n'
            ).encode("utf-8")
            with tempfile.TemporaryDirectory() as directory:
                bundle = Path(directory)
                (bundle / "ai_canonical.json").write_bytes(canonical)
                (bundle / "ai_manifest.json").write_bytes(manifest)
                return verify_ai_bundle(bundle)

        last_valid = verify_with_schema_members("bad", "ai_pack_manifest_v1")
        self.assertTrue(last_valid.valid)
        self.assertEqual(last_valid.reason, "OK")

        last_invalid = verify_with_schema_members("ai_pack_manifest_v1", "bad")
        self.assertFalse(last_invalid.valid)
        self.assertEqual(last_invalid.reason, "MANIFEST_BAD_SCHEMA")

    def test_ignored_manifest_surrogate_retains_v040_behavior(self):
        vectors = {item["case_id"]: item for item in _load_vectors()}
        baseline = vectors["canonicalization.ascii_baseline_no_lf"]
        canonical = bytes.fromhex(baseline["source_bytes_hex"])
        digest = baseline["expected"]["sha256"]
        manifest = (
            '{"schema":"ai_pack_manifest_v1",'
            '"ts_utc":"2026-01-01T00:00:00Z",'
            '"input_schema":"ai_output_v1",'
            '"canonicalization":"json_sorted_keys_no_whitespace_utf8",'
            '"ai_hash_sha256":"'
            + digest
            + '","ignored":"\\ud800"}\n'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "ai_canonical.json").write_bytes(canonical)
            (bundle / "ai_manifest.json").write_bytes(manifest)
            result = verify_ai_bundle(bundle)

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "OK")

    def test_released_v040_fixtures_keep_exact_digests(self):
        fixtures = {
            "examples/drift_demo/bundle_a": (
                "7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63"
            ),
            "examples/drift_demo/bundle_b": (
                "547298ea4f6f7795bf90d7e7196c82841ba50fa385ee7a2a290548c268d845c6"
            ),
            "tests/fixtures/compare/v030_invocation_a": (
                "e6657f38c52ff24ff6d5305caf9d32a7b427cbd0a402c3df75120d50ab36ddf4"
            ),
            "tests/fixtures/compare/v030_invocation_b": (
                "413cc1fbeaaf99417963c2b668c8f312b11c5a9e41b2f3ca7444fbeee00aca53"
            ),
        }
        for relative, digest in fixtures.items():
            with self.subTest(relative=relative):
                result = verify_ai_bundle(ROOT / relative)
                self.assertTrue(result.valid, result)
                self.assertEqual(result.ai_hash_sha256, digest)

    def test_pr33_result_contract_files_are_byte_unchanged(self):
        expected = {
            "engine/result_contracts.py": (
                "74fd01595b710dcaddbc3fb8bac0bb411f34de5c67f22930c790203e18f5c9e9"
            ),
            "engine/schemas/verification_result_v1.json": (
                "6e6f35bcd0e90e51cbf9d5fa25da7453f446c22ae86a2dce3eb75045bc1cddcc"
            ),
            "engine/schemas/assurance_result_v1.json": (
                "0da816736adc24f1a10b13e475ca855a228a2785907075276d48d9e2c3894388"
            ),
            "engine/schemas/compare_result_v1.json": (
                "2aa7a1f9496dc54edebd51c7282e63c88afd421af9b4bc4874b33eecac78a85f"
            ),
            "docs/VERIFICATION_RESULT_V1.md": (
                "00f52794288d95e1454b063771a4e81be4e36fe5f6df70c6c6e671f0b9bcee94"
            ),
            "docs/ASSURANCE_RESULT_V1.md": (
                "7ef1d7097c7cf0aec97348d5ab9e6300b42f943a6b97287ffd3e372b64af283c"
            ),
            "docs/CLAIM_BOUNDARIES_V1.md": (
                "fe3b1c2acaf31b657649f49067387f3d279e43b103a9eebc5884fa9d83ed68d4"
            ),
            "docs/COMPARE_RESULT_V1.md": (
                "5822092129691ccfb7622a7b7bb145c8343209f136dedfaaed8e8d426cde81bb"
            ),
        }
        for relative, digest in expected.items():
            with self.subTest(relative=relative):
                self.assertEqual(
                    hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                    digest,
                )


if __name__ == "__main__":
    unittest.main()
