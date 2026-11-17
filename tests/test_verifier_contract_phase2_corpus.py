import ast
import base64
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "verifier_contract_phase2"
RUNNER = ROOT / "conformance" / "run_verifier_contract_phase2.py"
BUILDER = ROOT / "conformance" / "build_verifier_contract_phase2.py"
BLOCK2A_SOURCE_SHA256 = "2caa5c78cae1c145e1c4630469a49ebf2ebc6ec85df91f90e8628bc1d3b9268e"
BLOCK2A_SCHEMA_SHA256 = "65a99dd490e9710aefb7dbb7547beb07f75bdfb3e6e0d8f292d9cc8a6e295fe4"
BLOCK2B1_SEMANTIC_SHA256 = "b2f6d5c0263c97006bad15af985099869264ac5f4833ef356526a6945909ffd9"
BLOCK2B1_VECTOR_SET_SHA256 = "7260d1216c1fe0b9e340fc4e1a0d1ee075a37c785d486d7370fabf9c73c958f1"
BLOCK2B2_PRECEDENCE_SHA256 = "810b62d3a9d0c311a1bb58c7a361083bb1881a16406c65bcea9d6c76ee3f89c1"


def _load(name: str):
    return json.loads((CORPUS / name).read_text(encoding="utf-8"))


class TestVerifierContractPhase2Corpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = _load("manifest.json")
        cls.sources = _load("source_vectors.json")
        cls.schemas = _load("schema_vectors.json")
        cls.semantics = _load("semantic_vectors.json")
        cls.precedence = _load("precedence_vectors.json")
        cls.semantic_by_id = {
            case["case_id"]: case for case in cls.semantics["vectors"]
        }
        cls.precedence_by_id = {
            case["case_id"]: case for case in cls.precedence["vectors"]
        }

    def test_phase2_manifest_scope_status_and_stable_counts(self):
        self.assertEqual(
            self.manifest["scope"],
            "SOURCE_SCHEMA_SIGNATURE_TRUST_ED25519_PORTABLE_PROFILE_PRECEDENCE",
        )
        self.assertEqual(
            self.manifest["subject_contract"],
            "aelitium-verifier-input-contracts-v1",
        )
        self.assertEqual(
            self.manifest["case_counts"],
            {
                "keyring_schema": 39,
                "keyring_source": 17,
                "manifest_schema": 46,
                "manifest_source": 69,
                "ed25519_strict_semantic": 12,
                "precedence_total": 23,
                "schema_total": 110,
                "semantic_total": 48,
                "signature_semantic": 17,
                "source_total": 100,
                "total": 281,
                "trust_schema": 25,
                "trust_semantic": 19,
                "trust_source": 14,
            },
        )
        self.assertEqual(self.manifest["block_2a_frozen"]["case_count"], 210)
        self.assertEqual(self.manifest["block_2b1_frozen"]["case_count"], 36)
        self.assertEqual(self.manifest["block_2b2_frozen"]["case_count"], 23)
        self.assertEqual(
            self.manifest["block_3"]["status"],
            "ED25519_RUNTIME_ALIGNMENT_PENDING",
        )
        self.assertFalse(self.manifest["block_3"]["closure_claimed"])
        self.assertIsNone(self.manifest["block_3"]["closure_mechanism"])
        self.assertEqual(
            self.manifest["gap_status"],
            {
                "G-04": "CLOSED",
                "G-05": "OPEN — NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
                "G-06": "CLOSED",
            },
        )
        self.assertEqual(
            self.manifest["ed25519_portable_profile"],
            {
                "case_count": 12,
                "fallback": "NONE",
                "profile": "ED25519_PORTABLE_STRICT_1",
                "status": "NORMATIVE_PROFILE_READY_RUNTIME_ALIGNMENT_PENDING",
            },
        )

    def test_block2a_files_and_all_existing_cases_are_byte_frozen(self):
        self.assertEqual(
            hashlib.sha256((CORPUS / "source_vectors.json").read_bytes()).hexdigest(),
            BLOCK2A_SOURCE_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((CORPUS / "schema_vectors.json").read_bytes()).hexdigest(),
            BLOCK2A_SCHEMA_SHA256,
        )
        original_semantics = (
            json.dumps(
                self.semantics["vectors"][:36],
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
            )
            + "\n"
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(original_semantics).hexdigest(),
            BLOCK2B1_VECTOR_SET_SHA256,
        )
        self.assertEqual(
            self.manifest["block_2b1_frozen"]["original_semantic_vectors_sha256"],
            BLOCK2B1_SEMANTIC_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((CORPUS / "precedence_vectors.json").read_bytes()).hexdigest(),
            BLOCK2B2_PRECEDENCE_SHA256,
        )
        self.assertEqual(len(self.sources["vectors"]), 100)
        self.assertEqual(len(self.schemas["vectors"]), 110)
        self.assertEqual(len(self.semantics["vectors"]), 48)

    def test_source_coverage_and_frozen_hashes(self):
        vectors = self.sources["vectors"]
        self.assertEqual(len(vectors), 100)
        self.assertEqual(
            Counter(case["input_kind"] for case in vectors),
            {
                "MANIFEST_V1": 33,
                "MANIFEST_V2": 36,
                "VERIFICATION_KEYS_V1": 17,
                "TRUST_STORE_V1": 14,
            },
        )
        required = {
            "manifest.v1.source.escaped_duplicate_final_wins",
            "manifest.v1.source.ignored_integer_641_digits_outside_capability",
            "manifest.v1.timestamp.named_profile_matching_nd",
            "manifest.v1.timestamp.non_ascii_nd_outside_ascii_capability",
            "manifest.v2.source.duplicate_unknown_extension_rejected",
            "manifest.v2.source.number_overflow_out_of_profile",
            "manifest.v2.timestamp.arabic_indic_digits",
            "manifest.v2.timestamp.disabled_null",
            "keyring.source.overwritten_integer_641_outside_capability",
            "keyring.source.opaque_ignored_string",
            "trust.source.overwritten_integer_641_outside_capability",
            "trust.source.opaque_label",
        }
        ids = {case["case_id"] for case in vectors}
        self.assertTrue(required <= ids)

        for case in vectors:
            with self.subTest(case=case["case_id"]):
                source = case["source"]
                if source["kind"] == "FIXTURE":
                    raw = (CORPUS / source["path"]).read_bytes()
                elif source["kind"] == "INLINE_UTF8":
                    raw = source["text"].encode("utf-8")
                else:
                    raw = bytes.fromhex(source["hex"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), source["sha256"])

    def test_schema_coverage_keeps_procedural_relations_outside_schema(self):
        vectors = self.schemas["vectors"]
        self.assertEqual(len(vectors), 110)
        self.assertEqual(
            Counter(case["family"] for case in vectors),
            {"MANIFEST_SCHEMA": 46, "KEYRING_SCHEMA": 39, "TRUST_SCHEMA": 25},
        )
        by_id = {case["case_id"]: case for case in vectors}
        procedural = {
            "manifest.schema.v1.timestamp_object_schema_neutral": ("TIMESTAMP_OPTION", "VALID"),
            "manifest.schema.v2.missing_schema_and_ts": ("ORDERED_MANIFEST_PRESENCE", "INVALID"),
            "keyring.schema.cross_entry_key_id_mismatch_schema_valid": ("KEY_ID_EQUALITY", "VALID"),
            "keyring.schema.public_key_b64.nonzero_pad_bits_schema_valid": ("BASE64_PAD_BITS", "VALID"),
            "keyring.schema.arbitrary_signature_math_procedural": ("ED25519_VERIFICATION", "VALID"),
            "trust.schema.structural_duplicate_signers_schema_valid": ("FINGERPRINT_UNIQUENESS", "VALID"),
        }
        for case_id, (rule, decision) in procedural.items():
            with self.subTest(case=case_id):
                self.assertEqual(
                    by_id[case_id]["expected"]["schema_decision"], decision
                )
                self.assertEqual(
                    by_id[case_id]["expected"]["procedural_requirement"], rule
                )

    def test_semantic_counts_ids_and_frozen_signed_material(self):
        self.assertEqual(self.semantics["case_count"], 48)
        self.assertEqual(
            self.semantics["family_counts"],
            {
                "ED25519_STRICT_SEMANTIC": 12,
                "SIGNATURE_SEMANTIC": 17,
                "TRUST_SEMANTIC": 19,
            },
        )
        all_ids = [case["case_id"] for case in self.sources["vectors"]]
        all_ids += [case["case_id"] for case in self.schemas["vectors"]]
        all_ids += [case["case_id"] for case in self.semantics["vectors"]]
        self.assertEqual(len(all_ids), len(set(all_ids)))

        material = self.semantics["materials"]["primary_manifest_signature"]
        self.assertEqual(
            material["raw_manifest_message_sha256"],
            "272f733b92560e7213318c0f0dfbee361a4e0b7ba38aef45fa814629deeda6da",
        )
        manifest = (CORPUS / "fixtures" / "semantic_manifest_valid.json").read_bytes()
        self.assertEqual(hashlib.sha256(manifest).hexdigest(), material["raw_manifest_message_sha256"])
        public_key = bytes.fromhex(
            self.semantics["materials"]["primary_key"]["public_key_hex"]
        )
        signature = bytes.fromhex(material["signature_hex"])
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, manifest)

    def test_portable_strict_profile_vectors_freeze_all_edge_decisions(self):
        expected_stages = {
            "signature.strict.canonical_valid": ("VALID", "NONE"),
            "signature.strict.cofactored_only_domain_rejected": ("INVALID", "A_IDENTITY"),
            "signature.strict.public_key_x_zero_sign_one": ("INVALID", "A_DECODE"),
            "signature.strict.public_key_y_p_plus_one": ("INVALID", "A_DECODE"),
            "signature.strict.identity_public_key": ("INVALID", "A_IDENTITY"),
            "signature.strict.nonidentity_small_order_public_key": ("INVALID", "A_SUBGROUP"),
            "signature.strict.nonidentity_small_order_r": ("INVALID", "R_SUBGROUP"),
            "signature.strict.noncanonical_r_x_zero_sign_one": ("INVALID", "R_DECODE"),
            "signature.strict.noncanonical_r_y_p_plus_one": ("INVALID", "R_DECODE"),
            "signature.strict.scalar_l_rejected": ("INVALID", "S_RANGE"),
            "signature.strict.scalar_l_minus_one_reaches_equation": ("INVALID", "EQUATION"),
            "signature.strict.identity_r_reaches_equation": ("INVALID", "EQUATION"),
        }
        strict_ids = {
            case["case_id"]
            for case in self.semantics["vectors"]
            if case["family"] == "ED25519_STRICT_SEMANTIC"
        }
        self.assertEqual(strict_ids, set(expected_stages))
        for case_id, (validity, stage) in expected_stages.items():
            with self.subTest(case=case_id):
                case = self.semantic_by_id[case_id]
                self.assertEqual(case["profile"], "ED25519_PORTABLE_STRICT_1")
                self.assertEqual(case["expected"]["signature_validity"], validity)
                self.assertEqual(case["expected"]["failure_stage"], stage)
        self.assertEqual(
            self.semantic_by_id[
                "signature.strict.scalar_l_minus_one_reaches_equation"
            ]["expected"]["scalar_decision"],
            "IN_RANGE",
        )
        self.assertEqual(
            self.semantic_by_id["signature.strict.scalar_l_rejected"]["expected"][
                "equation_decision"
            ],
            "NOT_REACHED",
        )
        self.assertEqual(
            self.semantic_by_id[
                "signature.strict.cofactored_only_domain_rejected"
            ]["distinguishing_equations"],
            {
                "cofactored_equation": "PASS",
                "uncofactored_equation": "FAIL",
            },
        )

    def test_raw_manifest_mutations_remain_semantically_equal_but_signature_invalid(self):
        base_path = CORPUS / "fixtures" / "semantic_manifest_valid.json"
        base_raw = base_path.read_bytes()
        base_value = json.loads(base_raw)
        case_names = {
            "raw_leading_whitespace": "semantic_manifest_leading_whitespace.json",
            "raw_member_order": "semantic_manifest_member_order.json",
            "raw_escape_spelling": "semantic_manifest_escape_spelling.json",
            "raw_terminal_newline": "semantic_manifest_terminal_newline.json",
        }
        for label, fixture in case_names.items():
            with self.subTest(case=label):
                changed = (CORPUS / "fixtures" / fixture).read_bytes()
                self.assertNotEqual(changed, base_raw)
                self.assertEqual(json.loads(changed), base_value)
                case = self.semantic_by_id[f"signature.semantic.{label}"]
                self.assertEqual(case["expected"]["top_level_reason"], "SIGNATURE_INVALID")
                self.assertEqual(case["expected"]["cryptographic_signature_decision"], "INVALID")
                self.assertEqual(
                    case["raw_manifest_message_sha256"], hashlib.sha256(changed).hexdigest()
                )

    def test_nonzero_pad_bit_aliases_preserve_decoded_material(self):
        materials = self.semantics["materials"]
        key = materials["primary_key"]
        signature = materials["primary_manifest_signature"]
        self.assertNotEqual(key["public_key_b64"], key["public_key_pad_bit_alias_b64"])
        self.assertEqual(
            base64.b64decode(key["public_key_b64"], validate=True),
            base64.b64decode(key["public_key_pad_bit_alias_b64"], validate=True),
        )
        self.assertNotEqual(signature["signature_b64"], signature["signature_pad_bit_alias_b64"])
        self.assertEqual(
            base64.b64decode(signature["signature_b64"], validate=True),
            base64.b64decode(signature["signature_pad_bit_alias_b64"], validate=True),
        )
        for case_id in (
            "signature.semantic.public_key_nonzero_pad_bits",
            "signature.semantic.signature_nonzero_pad_bits",
        ):
            self.assertEqual(
                self.semantic_by_id[case_id]["expected"]["signature_validity"],
                "VALID",
            )

    def test_fingerprint_derivation_and_duplicate_semantics(self):
        primary = self.semantics["materials"]["primary_key"]
        raw = bytes.fromhex(primary["public_key_hex"])
        raw_digest = hashlib.sha256(raw).hexdigest()
        prefixed_digest = hashlib.sha256(b"ed25519:sha256:" + raw).hexdigest()
        self.assertEqual(primary["fingerprint"], "ed25519:sha256:" + raw_digest)
        self.assertNotEqual(raw_digest, prefixed_digest)
        duplicate_ids = (
            "trust.semantic.duplicate_decoded_key_exact",
            "trust.semantic.duplicate_decoded_key_different_label",
            "trust.semantic.duplicate_decoded_key_pad_bit_alias",
        )
        for case_id in duplicate_ids:
            with self.subTest(case=case_id):
                expected = self.semantic_by_id[case_id]["expected"]
                self.assertEqual(expected["trust_store_validation"], "INVALID")
                self.assertEqual(expected["top_level_reason"], "TRUST_STORE_INVALID")

    def test_membership_matrix_and_operational_boundary(self):
        expected = {
            "trust.semantic.valid_signature_matching_store": (None, "VALID", "VALID", "MATCH"),
            "trust.semantic.valid_signature_nonmatching_store_optional": (None, "VALID", "UNESTABLISHED", "NO_MATCH"),
            "trust.semantic.valid_signature_nonmatching_store_required": ("TRUSTED_SIGNER_NOT_FOUND", "VALID", "UNESTABLISHED", "NO_MATCH"),
            "trust.semantic.empty_store_optional": (None, "VALID", "UNESTABLISHED", "NO_MATCH"),
            "trust.semantic.empty_store_required": ("TRUSTED_SIGNER_NOT_FOUND", "VALID", "UNESTABLISHED", "NO_MATCH"),
            "trust.semantic.no_store_optional": (None, "VALID", "UNESTABLISHED", "NO_STORE"),
            "trust.semantic.no_store_required": ("TRUST_INPUT_NOT_PROVIDED", "NOT_EVALUATED", "UNESTABLISHED", "NO_STORE"),
            "trust.semantic.malformed_acquired_store_optional": ("TRUST_STORE_INVALID", "NOT_EVALUATED", "UNESTABLISHED", "NOT_EVALUATED"),
            "trust.semantic.malformed_acquired_store_required": ("TRUST_STORE_INVALID", "NOT_EVALUATED", "UNESTABLISHED", "NOT_EVALUATED"),
            "trust.semantic.store_present_unsigned_optional": (None, "ABSENT", "UNESTABLISHED", "NOT_EVALUATED"),
            "trust.semantic.store_present_unsigned_required": ("SIGNATURE_REQUIRED", "ABSENT", "UNESTABLISHED", "NOT_EVALUATED"),
            "trust.semantic.store_present_invalid_signature": ("SIGNATURE_INVALID", "INVALID", "UNESTABLISHED", "NOT_EVALUATED"),
        }
        for case_id, states in expected.items():
            with self.subTest(case=case_id):
                result = self.semantic_by_id[case_id]["expected"]
                self.assertEqual(
                    (
                        result["top_level_reason"],
                        result["signature_validity"],
                        result["trusted_signer_identity"],
                        result["trust_membership_decision"],
                    ),
                    states,
                )
        serialized = json.dumps(self.semantics, sort_keys=True)
        for acquisition_term in (
            "INPUT_IO_ERROR",
            "INPUT_NOT_REGULAR_FILE",
            "INPUT_CHANGED_DURING_SNAPSHOT",
            "permission failure",
            "unreadable path",
        ):
            self.assertNotIn(acquisition_term, serialized)

    def test_precedence_candidates_have_one_ranked_winner_and_unique_ids(self):
        vectors = self.precedence["vectors"]
        self.assertEqual(self.precedence["case_count"], 23)
        self.assertEqual(Counter(case["family"] for case in vectors), {"PRECEDENCE": 23})
        ranks = {
            reason: entry["rank"]
            for entry in self.precedence["precedence_relation"]
            for reason in entry["reasons"]
        }
        previous_ids = {
            case["case_id"]
            for document in (self.sources, self.schemas, self.semantics)
            for case in document["vectors"]
        }
        precedence_ids = [case["case_id"] for case in vectors]
        self.assertEqual(len(precedence_ids), len(set(precedence_ids)))
        self.assertTrue(previous_ids.isdisjoint(precedence_ids))
        for case in vectors:
            with self.subTest(case=case["case_id"]):
                candidates = case["candidate_failures"]
                self.assertTrue(candidates)
                reasons = [candidate["reason"] for candidate in candidates]
                winner = case["expected"]["winning_top_level_reason"]
                self.assertEqual(reasons.count(winner), 1)
                self.assertEqual(winner, min(reasons, key=ranks.__getitem__))
                self.assertIsInstance(case["expected"]["not_evaluated_checks"], list)

    def test_precedence_coverage_and_timestamp_bypass(self):
        expected_ids = {
            "precedence.trust_input.required_absent_before_invalid_bundle",
            "precedence.trust_input.malformed_acquired_before_invalid_bundle",
            "precedence.payload.canonical_not_json_before_malformed_keyring",
            "precedence.payload.manifest_not_json_before_malformed_keyring",
            "precedence.payload.manifest_not_object_before_malformed_keyring",
            "precedence.payload.hash_mismatch_before_malformed_keyring",
            "precedence.signature.invalid_before_signature_required",
            "precedence.signature.invalid_before_binding_mismatch",
            "precedence.signature.invalid_before_binding_required",
            "precedence.signature.invalid_before_required_membership",
            "precedence.signature.invalid_before_authorized_invocation_failure",
            "precedence.signature.invalid_before_authorized_freshness_failure",
            "precedence.signature.required_before_binding_mismatch",
            "precedence.signature.required_for_membership_with_valid_store",
            "precedence.signature.no_trust_input_before_unsigned_bundle",
            "precedence.binding.mismatch_before_required_membership",
            "precedence.binding.valid_then_required_membership_missing",
            "precedence.manifest.bad_schema_before_bad_input_schema",
            "precedence.manifest.bad_input_schema_before_bad_canonicalization",
            "precedence.manifest.bad_canonicalization_before_bad_timestamp",
            "precedence.manifest.bad_timestamp_before_bad_digest_spelling",
            "precedence.manifest.bad_digest_spelling_before_hash_mismatch",
            "precedence.manifest.timestamp_disabled_allows_later_digest_failure",
        }
        self.assertEqual(set(self.precedence_by_id), expected_ids)
        disabled = self.precedence_by_id[
            "precedence.manifest.timestamp_disabled_allows_later_digest_failure"
        ]
        self.assertFalse(disabled["verifier_options"]["validate_manifest_timestamp"])
        self.assertEqual(disabled["expected"]["timestamp_decision"], "BYPASSED")
        self.assertEqual(disabled["expected"]["bypassed_checks"], ["MANIFEST_TIMESTAMP"])
        self.assertEqual(
            disabled["expected"]["winning_top_level_reason"],
            "MANIFEST_BAD_AI_HASH_SHA256",
        )
        binding = self.precedence["binding_materials"]
        valid = binding["VALID"]
        mismatch = binding["HASH_MISMATCH"]
        self.assertEqual(
            hashlib.sha256(bytes.fromhex(valid["canonical_hash_input_hex"])).hexdigest(),
            valid["expected_binding_hash"],
        )
        self.assertEqual(valid["manifest_binding_hash"], valid["expected_binding_hash"])
        self.assertEqual(valid["payload_binding_hash"], valid["expected_binding_hash"])
        self.assertNotEqual(
            mismatch["manifest_binding_hash"], mismatch["expected_binding_hash"]
        )

    def test_precedence_preserves_pr43_and_excludes_operational_filesystem_cases(self):
        no_input = self.precedence_by_id[
            "precedence.trust_input.required_absent_before_invalid_bundle"
        ]
        malformed = self.precedence_by_id[
            "precedence.trust_input.malformed_acquired_before_invalid_bundle"
        ]
        self.assertEqual(
            no_input["expected"]["winning_top_level_reason"],
            "TRUST_INPUT_NOT_PROVIDED",
        )
        self.assertEqual(
            malformed["expected"]["winning_top_level_reason"],
            "TRUST_STORE_INVALID",
        )
        self.assertEqual(
            malformed["inputs"]["trust_store_fixture"],
            "semantic_trust_malformed.json",
        )
        serialized = json.dumps(self.precedence, sort_keys=True)
        for operational_code in (
            "INPUT_IO_ERROR",
            "INPUT_NOT_REGULAR_FILE",
            "INPUT_CHANGED_DURING_SNAPSHOT",
            "RESOURCE_EXHAUSTED",
            "RESOURCE_LIMIT_EXCEEDED",
        ):
            self.assertNotIn(operational_code, serialized)
        exclusion = self.precedence["deliberate_exclusions"][0]
        self.assertEqual(exclusion["status"], "EXCLUDED_FROM_PHASE2_FIXTURES")
        self.assertIn("G-07", exclusion["reason"])
        self.assertIn("G-11", exclusion["reason"])

    def test_runner_and_builder_check_pass(self):
        runner = subprocess.run(
            [sys.executable, str(RUNNER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(runner.returncode, 0, runner.stderr)
        self.assertIn("SOURCE PASS 100/100", runner.stdout)
        self.assertIn("SCHEMA PASS 110/110", runner.stdout)
        self.assertIn("SIGNATURE_SEMANTIC PASS 17/17", runner.stdout)
        self.assertIn("TRUST_SEMANTIC PASS 19/19", runner.stdout)
        self.assertIn("ED25519_STRICT_SEMANTIC PASS 12/12", runner.stdout)
        self.assertIn("SEMANTIC PASS 48/48", runner.stdout)
        self.assertIn("PRECEDENCE PASS 23/23", runner.stdout)
        self.assertTrue(runner.stdout.rstrip().endswith("PASS 281/281"))

        builder = subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(builder.returncode, 0, builder.stderr)
        self.assertIn("PASS deterministic corpus 30/30 files", builder.stdout)

    def test_maintenance_code_has_no_production_import(self):
        for path in (RUNNER, BUILDER):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            with self.subTest(path=path.name):
                self.assertFalse(
                    any(name == "engine" or name.startswith("engine.") for name in imports),
                    imports,
                )

    def test_strict_reference_path_does_not_delegate_to_backend_verification(self):
        tree = ast.parse(RUNNER.read_text(encoding="utf-8"), filename=str(RUNNER))
        strict_names = {
            "decode_ed25519_portable_point",
            "ed25519_portable_add",
            "ed25519_portable_scalar_multiply",
            "ed25519_equation_diagnostics",
            "ed25519_portable_strict_1_observation",
            "strict_semantic_message",
            "validate_strict_semantic_case",
        }
        nodes = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in strict_names
        ]
        self.assertEqual({node.name for node in nodes}, strict_names)
        referenced = {
            node.id
            for function in nodes
            for node in ast.walk(function)
            if isinstance(node, ast.Name)
        }
        self.assertNotIn("Ed25519PublicKey", referenced)
        self.assertNotIn("Ed25519PrivateKey", referenced)


if __name__ == "__main__":
    unittest.main()
