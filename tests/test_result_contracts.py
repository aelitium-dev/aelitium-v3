import json
import subprocess
import sys
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError

from engine.ai_verify import AIVerificationOptions, AIVerificationResult, AssuranceState
from engine.result_contracts import (
    ASSURANCE_DIMENSIONS,
    ASSURANCE_REACHABLE_STATES,
    CLAIM_BOUNDARY_VOCABULARY,
    ClaimBoundary,
    ResultContractError,
    build_assurance_result,
    build_comparison_contract_fields,
    build_verification_result,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "engine.ai_cli"]
LEGACY_A = ROOT / "examples" / "drift_demo" / "bundle_a"
LEGACY_B = ROOT / "examples" / "drift_demo" / "bundle_b"
RICH_A = ROOT / "tests" / "fixtures" / "compare" / "v030_invocation_a"
SCHEMA_DIR = ROOT / "engine" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + list(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _successful_result(**changes) -> AIVerificationResult:
    result = AIVerificationResult(
        valid=True,
        reason="OK",
        ai_hash_sha256="a" * 64,
        canonical={},
        manifest={},
        payload_integrity=AssuranceState.VALID,
        binding_field_consistency=AssuranceState.ABSENT,
        invocation_identity_consistency=AssuranceState.ABSENT,
        invocation_binding_consistency=AssuranceState.ABSENT,
        signature_validity=AssuranceState.ABSENT,
        trusted_signer_identity=AssuranceState.UNESTABLISHED,
        freshness=AssuranceState.NOT_EVALUATED,
        authorization=AssuranceState.NOT_EVALUATED,
    )
    return replace(result, **changes)


class TestAssuranceResultV1(unittest.TestCase):
    def test_exact_dimension_order_and_count(self):
        contract = build_assurance_result(_successful_result())
        self.assertEqual(contract["contract"], "aelitium-assurance-result-v1")
        self.assertEqual(
            tuple(item["dimension"] for item in contract["dimensions"]),
            ASSURANCE_DIMENSIONS,
        )
        self.assertEqual(len(contract["dimensions"]), 8)

    def test_reachable_state_sets_are_not_flattened(self):
        self.assertEqual(
            set(ASSURANCE_REACHABLE_STATES["payload_integrity"]),
            {"VALID", "INVALID", "ABSENT", "NOT_EVALUATED"},
        )
        self.assertEqual(
            set(ASSURANCE_REACHABLE_STATES["trusted_signer_identity"]),
            {"VALID", "UNESTABLISHED"},
        )
        self.assertEqual(
            set(ASSURANCE_REACHABLE_STATES["freshness"]),
            {"VALID", "INVALID", "UNESTABLISHED", "NOT_EVALUATED"},
        )
        self.assertEqual(
            ASSURANCE_REACHABLE_STATES["authorization"],
            ("NOT_EVALUATED",),
        )

    def test_structure_matches_packaged_schema(self):
        contract = build_assurance_result(_successful_result())
        Draft7Validator(_schema("assurance_result_v1.json")).validate(contract)

    def test_schema_rejects_wrong_order_and_unreachable_dimension_state(self):
        validator = Draft7Validator(_schema("assurance_result_v1.json"))
        contract = build_assurance_result(_successful_result())

        wrong_order = deepcopy(contract)
        wrong_order["dimensions"][0], wrong_order["dimensions"][1] = (
            wrong_order["dimensions"][1],
            wrong_order["dimensions"][0],
        )
        with self.assertRaises(ValidationError):
            validator.validate(wrong_order)

        unreachable = deepcopy(contract)
        unreachable["dimensions"][0]["state"] = "UNESTABLISHED"
        with self.assertRaises(ValidationError):
            validator.validate(unreachable)

    def test_schema_rejects_changed_basis_references_and_boundary_profiles(self):
        validator = Draft7Validator(_schema("assurance_result_v1.json"))
        contract = build_assurance_result(_successful_result())

        mutations = []
        wrong_basis = deepcopy(contract)
        wrong_basis["dimensions"][0]["basis"] = "different_basis"
        mutations.append(wrong_basis)
        wrong_input_ref = deepcopy(contract)
        wrong_input_ref["dimensions"][0]["trust_input_refs"] = [
            "verification-input:trust-store"
        ]
        mutations.append(wrong_input_ref)
        missing_boundary = deepcopy(contract)
        missing_boundary["claim_boundaries"].pop()
        mutations.append(missing_boundary)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValidationError):
                    validator.validate(mutation)

    def test_no_aggregate_score_or_ninth_dimension(self):
        contract = build_assurance_result(_successful_result())
        encoded = json.dumps(contract)
        self.assertNotIn("score", encoded.lower())
        self.assertEqual(len(contract["dimensions"]), 8)

    def test_claim_codes_are_closed_and_embedded(self):
        contract = build_assurance_result(_successful_result())
        emitted = set(contract["claim_boundaries"])
        for dimension in contract["dimensions"]:
            emitted.update(dimension["claim_boundaries"])
        self.assertTrue(emitted <= CLAIM_BOUNDARY_VOCABULARY)
        self.assertIn(
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            emitted,
        )
        self.assertIn(
            ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
            emitted,
        )

    def test_trust_and_policy_references_are_explicit_only_when_supplied(self):
        options = AIVerificationOptions(
            trust_store_path="explicit-trust.json",
            freshness_max_age_seconds=30,
            freshness_reference_time_utc="2026-03-01T10:00:30Z",
        )
        contract = build_assurance_result(_successful_result(), options=options)
        by_name = {item["dimension"]: item for item in contract["dimensions"]}
        self.assertEqual(
            by_name["trusted_signer_identity"]["trust_input_refs"],
            ["verification-input:trust-store"],
        )
        self.assertEqual(
            by_name["freshness"]["policy_ref"],
            "verification-input:freshness-policy",
        )
        self.assertEqual(by_name["payload_integrity"]["trust_input_refs"], [])

    def test_impossible_state_combinations_are_rejected(self):
        cases = (
            (
                _successful_result(
                    trusted_signer_identity=AssuranceState.VALID,
                ),
                AIVerificationOptions(trust_store_path="trust.json"),
            ),
            (
                _successful_result(
                    signature_validity=AssuranceState.VALID,
                    trusted_signer_identity=AssuranceState.VALID,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(
                    invocation_binding_consistency=AssuranceState.VALID,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(authorization=AssuranceState.VALID),
                AIVerificationOptions(),
            ),
            (
                _successful_result(freshness=AssuranceState.UNESTABLISHED),
                AIVerificationOptions(),
            ),
            (
                _successful_result(
                    valid=False,
                    reason="SYNTHETIC_FAILURE",
                    signature_validity=AssuranceState.NOT_EVALUATED,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(
                    valid=False,
                    reason="SYNTHETIC_FAILURE",
                    ai_hash_sha256=None,
                    payload_integrity=AssuranceState.INVALID,
                    binding_field_consistency=AssuranceState.ABSENT,
                    invocation_identity_consistency=AssuranceState.NOT_EVALUATED,
                    invocation_binding_consistency=AssuranceState.NOT_EVALUATED,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(
                    valid=False,
                    reason="SYNTHETIC_FAILURE",
                    ai_hash_sha256=None,
                    payload_integrity=AssuranceState.NOT_EVALUATED,
                    binding_field_consistency=AssuranceState.NOT_EVALUATED,
                    invocation_identity_consistency=AssuranceState.NOT_EVALUATED,
                    invocation_binding_consistency=AssuranceState.NOT_EVALUATED,
                    signature_validity=AssuranceState.ABSENT,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(
                    valid=False,
                    reason="SYNTHETIC_FAILURE",
                    payload_integrity=AssuranceState.INVALID,
                    binding_field_consistency=AssuranceState.NOT_EVALUATED,
                    invocation_identity_consistency=AssuranceState.NOT_EVALUATED,
                    invocation_binding_consistency=AssuranceState.NOT_EVALUATED,
                ),
                AIVerificationOptions(),
            ),
            (
                _successful_result(ai_hash_sha256=None),
                AIVerificationOptions(),
            ),
        )
        for result, options in cases:
            with self.subTest(result=result, options=options):
                with self.assertRaises(ResultContractError):
                    build_assurance_result(result, options=options)


class TestVerificationResultV1(unittest.TestCase):
    def test_valid_contract_matches_both_schemas(self):
        result = _run(
            "verify-bundle",
            str(LEGACY_A),
            "--contract-json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        Draft7Validator(_schema("verification_result_v1.json")).validate(payload)
        Draft7Validator(_schema("assurance_result_v1.json")).validate(
            payload["assurance"]
        )
        self.assertEqual(payload["contract"], "aelitium-verification-result-v1")
        self.assertEqual(payload["status"], "VALID")
        self.assertEqual(payload["reason"], "OK")

    def test_verify_command_exposes_the_same_opt_in_contract(self):
        result = _run(
            "verify",
            "--out",
            str(LEGACY_A),
            "--contract-json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["contract"], "aelitium-verification-result-v1")
        self.assertEqual(payload["status"], "VALID")
        Draft7Validator(_schema("verification_result_v1.json")).validate(payload)

    def test_invalid_contract_is_json_and_preserves_exit_code(self):
        missing = ROOT / "conformance-path-that-does-not-exist"
        result = _run(
            "verify-bundle",
            str(missing),
            "--contract-json",
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "INVALID")
        self.assertEqual(payload["rc"], 2)
        self.assertEqual(payload["reason"], "MISSING_CANONICAL")
        self.assertIsNone(payload["artifact"]["canonical_payload_digest"])
        Draft7Validator(_schema("verification_result_v1.json")).validate(payload)
        Draft7Validator(_schema("assurance_result_v1.json")).validate(
            payload["assurance"]
        )

    def test_verification_schema_binds_status_reason_and_exit_code(self):
        payload = json.loads(
            _run("verify-bundle", str(LEGACY_A), "--contract-json").stdout
        )
        validator = Draft7Validator(_schema("verification_result_v1.json"))
        payload["rc"] = 2
        with self.assertRaises(ValidationError):
            validator.validate(payload)

        wrong_basis = json.loads(
            _run("verify-bundle", str(LEGACY_A), "--contract-json").stdout
        )
        wrong_basis["assurance"]["dimensions"][0]["basis"] = "different_basis"
        with self.assertRaises(ValidationError):
            validator.validate(wrong_basis)

    def test_artifact_digest_scope_is_canonical_payload_not_directory(self):
        payload = json.loads(
            _run("verify-bundle", str(LEGACY_A), "--contract-json").stdout
        )
        digest = payload["artifact"]["canonical_payload_digest"]
        self.assertEqual(digest["scope"], "canonical_payload")
        self.assertEqual(len(digest["value"]), 64)
        self.assertNotIn(str(LEGACY_A), json.dumps(payload))

    def test_explicit_inputs_are_represented_without_trust_store_path(self):
        payload = build_verification_result(
            _successful_result(),
            options=AIVerificationOptions(
                trust_store_path="/secret/operator/path/trust.json",
                freshness_max_age_seconds=30,
                freshness_reference_time_utc="2026-03-01T10:00:30Z",
            ),
        )
        self.assertEqual(payload["trust_inputs"][0]["ref"], "verification-input:trust-store")
        self.assertNotIn("/secret/operator/path", json.dumps(payload))
        self.assertEqual(
            payload["policy_inputs"][0]["maximum_age_seconds"],
            30,
        )

    def test_repeated_serialization_is_deterministic(self):
        result = _successful_result()
        first = json.dumps(build_verification_result(result), sort_keys=True)
        second = json.dumps(build_verification_result(result), sort_keys=True)
        self.assertEqual(first, second)

    def test_legacy_json_invalid_behavior_is_unchanged(self):
        missing = ROOT / "conformance-path-that-does-not-exist"
        result = _run("verify-bundle", str(missing), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.startswith("STATUS=INVALID rc=2"))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(result.stdout)

    def test_normal_text_output_is_unchanged(self):
        result = _run("verify-bundle", str(LEGACY_A))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines()[0], "STATUS=VALID rc=0")
        self.assertNotIn("aelitium-verification-result-v1", result.stdout)

    def test_legacy_json_and_contract_json_are_mutually_exclusive(self):
        result = _run(
            "verify-bundle",
            str(LEGACY_A),
            "--json",
            "--contract-json",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowed with argument", result.stderr)
        self.assertEqual(result.stdout, "")


class TestCompareV1HardenedJson(unittest.TestCase):
    def _assert_schema(self, result: subprocess.CompletedProcess) -> dict:
        payload = json.loads(result.stdout)
        Draft7Validator(_schema("compare_result_v1.json")).validate(payload)
        self.assertEqual(payload["comparison_contract"], "aelitium-compare-v1")
        self.assertEqual(
            payload["claim_boundary_contract"],
            "aelitium-claim-boundary-v1",
        )
        for side in ("left", "right"):
            self.assertEqual(
                set(payload[side]["verification"]["assurance_states"]),
                set(ASSURANCE_DIMENSIONS),
            )
        return payload

    def test_unchanged_exposes_response_relationship(self):
        result = _run("compare", str(RICH_A), str(RICH_A), "--json")
        self.assertEqual(result.returncode, 0)
        payload = self._assert_schema(result)
        self.assertEqual(payload["comparability_result"], "UNCHANGED")
        self.assertEqual(payload["response_relationship"], "SAME")

    def test_changed_exposes_response_relationship_and_non_claims(self):
        result = _run("compare", str(LEGACY_A), str(LEGACY_B), "--json")
        self.assertEqual(result.returncode, 2)
        payload = self._assert_schema(result)
        self.assertEqual(payload["comparability_result"], "CHANGED")
        self.assertEqual(payload["response_relationship"], "DIFFERENT")
        self.assertIn(
            ClaimBoundary.MODEL_DRIFT_NOT_ESTABLISHED,
            payload["claim_boundaries"],
        )

    def test_compare_schema_binds_outcome_and_dimension_reachability(self):
        result = _run("compare", str(LEGACY_A), str(LEGACY_B), "--json")
        payload = self._assert_schema(result)
        validator = Draft7Validator(_schema("compare_result_v1.json"))

        wrong_exit = deepcopy(payload)
        wrong_exit["rc"] = 0
        with self.assertRaises(ValidationError):
            validator.validate(wrong_exit)

        unreachable = deepcopy(payload)
        unreachable["left"]["verification"]["assurance_states"][
            "trusted_signer_identity"
        ] = "INVALID"
        with self.assertRaises(ValidationError):
            validator.validate(unreachable)

        missing_boundary = deepcopy(payload)
        missing_boundary["claim_boundaries"].pop()
        with self.assertRaises(ValidationError):
            validator.validate(missing_boundary)

    def test_comparison_serializer_rejects_status_relationship_mismatches(self):
        result = _successful_result()
        cases = (
            ("UNCHANGED", "DIFFERENT"),
            ("CHANGED", "SAME"),
            ("NOT_COMPARABLE", "SAME"),
            ("INVALID_BUNDLE", "DIFFERENT"),
        )
        for status, relationship in cases:
            with self.subTest(status=status, relationship=relationship):
                with self.assertRaises(ResultContractError):
                    build_comparison_contract_fields(
                        result_a=result,
                        result_b=result,
                        status=status,
                        response_relationship=relationship,
                    )

    def test_not_comparable_withholds_response_relationship(self):
        result = _run(
            "compare",
            str(LEGACY_A),
            str(LEGACY_A),
            "--require-invocation-evidence",
            "--json",
        )
        self.assertEqual(result.returncode, 1)
        payload = self._assert_schema(result)
        self.assertEqual(payload["comparability_result"], "NOT_COMPARABLE")
        self.assertIsNone(payload["response_relationship"])
        self.assertEqual(payload["response_hash"], "SAME")
        self.assertEqual(
            payload["required_comparison_basis"],
            "INVOCATION_IDENTITY_V1",
        )

    def test_invalid_bundle_is_not_a_comparability_result(self):
        missing = ROOT / "conformance-path-that-does-not-exist"
        result = _run("compare", str(missing), str(LEGACY_A), "--json")
        self.assertEqual(result.returncode, 2)
        payload = self._assert_schema(result)
        self.assertEqual(payload["status"], "INVALID_BUNDLE")
        self.assertIsNone(payload["comparability_result"])
        self.assertIsNone(payload["response_relationship"])
        self.assertEqual(payload["left"]["verification"]["status"], "INVALID")
        self.assertEqual(payload["right"]["verification"]["status"], "VALID")


if __name__ == "__main__":
    unittest.main()
