import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "legacy_v1_operational_policy"
SCHEMAS = ROOT / "engine" / "schemas"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestLegacyV1OperationalPolicyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _load(SCHEMAS / "verifier_tool_result_v1.json")
        verification_schema = _load(SCHEMAS / "verification_result_v1.json")
        registry = Registry().with_resource(
            verification_schema["$id"],
            Resource.from_contents(verification_schema),
        )
        cls.validator = Draft7Validator(cls.schema, registry=registry)
        cls.document = _load(CORPUS / "cases.json")
        cls.operational = next(
            vector["expected"]["tool_result"]
            for vector in cls.document["vectors"]
            if vector["expected"]["kind"] == "OPERATIONAL_TOOL_RESULT"
        )

    def test_schema_is_valid_and_accepts_frozen_operational_result(self):
        Draft7Validator.check_schema(self.schema)
        self.validator.validate(self.operational)

    def test_schema_accepts_valid_and_invalid_semantic_wrappers(self):
        # Existing schema-valid inner results exercise only $ref composition
        # and rc/status branching; they are not policy expectations or an
        # oracle for the frozen operational corpus.
        configuration = self.document["vectors"][0]["configuration"]
        for fixture, expected_status, expected_rc in (
            ("full_a", "VALID", 0),
            ("payload_tamper", "INVALID", 2),
        ):
            with self.subTest(status=expected_status):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "engine.ai_cli",
                        "verify-bundle",
                        str(ROOT / "conformance" / "fixtures" / "bundles" / fixture),
                        "--contract-json",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, expected_rc, completed.stderr)
                inner = json.loads(completed.stdout)
                self.assertEqual(inner["status"], expected_status)
                candidate = {
                    "capability": {
                        "effective": configuration["capability"],
                        "requested": configuration["capability"],
                    },
                    "contract": "aelitium-verifier-tool-result-v1",
                    "input_mode": configuration["input_mode"],
                    "limits": configuration["limits"],
                    "operation": "VERIFY_BUNDLE",
                    "operational_result": None,
                    "outcome": "SEMANTIC_RESULT",
                    "rc": expected_rc,
                    "verification_result": inner,
                }
                self.validator.validate(candidate)
                invalid = copy.deepcopy(candidate)
                invalid["rc"] = 2 if expected_rc == 0 else 0
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_operational_outcome_cannot_contain_verification_result(self):
        invalid = copy.deepcopy(self.operational)
        invalid["verification_result"] = {
            "status": "INVALID",
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

    def test_operational_outcome_cannot_contain_assurance_or_comparison(self):
        for field in ("assurance", "comparison_result"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.operational)
                invalid[field] = None
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_operational_outcome_requires_rc_three(self):
        for rc in (0, 1, 2, 64):
            with self.subTest(rc=rc):
                invalid = copy.deepcopy(self.operational)
                invalid["rc"] = rc
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_outer_numbers_remain_in_portable_safe_integer_domain(self):
        invalid = copy.deepcopy(self.operational)
        invalid["limits"]["advertised"]["max_file_bytes"] = 9_007_199_254_740_992
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

    def test_operational_code_relations_are_closed(self):
        examples = {
            vector["expected"]["tool_result"]["operational_result"][
                "operational_code"
            ]: vector["expected"]["tool_result"]
            for vector in self.document["vectors"]
            if vector["expected"]["kind"] == "OPERATIONAL_TOOL_RESULT"
        }

        invalid = copy.deepcopy(examples["CAPABILITY_PROFILE_UNAVAILABLE"])
        invalid["operational_result"]["phase"] = "MANIFEST_PARSE"
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["CAPABILITY_PROFILE_UNAVAILABLE"])
        invalid["capability"]["effective"] = invalid["capability"]["requested"]
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["INPUT_OUTSIDE_DECLARED_CAPABILITY"])
        invalid["operational_result"]["limit"]["name"] = "FILE_BYTES"
        invalid["operational_result"]["limit"]["unit"] = "BYTES"
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["RESOURCE_LIMIT_EXCEEDED"])
        invalid["operational_result"]["limit"]["unit"] = "DIGITS"
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["RESOURCE_LIMIT_EXCEEDED"])
        invalid["operational_result"]["limit"]["name"] = "INTEGER_DECIMAL_DIGITS"
        invalid["operational_result"]["limit"]["unit"] = "DIGITS"
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["INPUT_IO_ERROR"])
        invalid["operational_result"]["limit"] = {
            "name": "FILE_BYTES",
            "unit": "BYTES",
            "maximum": 65536,
            "observed_at_least": 65537,
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["INPUT_IO_ERROR"])
        invalid["capability"]["effective"] = None
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

        invalid = copy.deepcopy(examples["OUTPUT_IO_ERROR"])
        invalid["operational_result"]["input_ref"] = "AI_MANIFEST_JSON"
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

    def test_profile_digest_is_exact(self):
        named = next(
            vector
            for vector in self.document["vectors"]
            if vector["case_id"] == "timestamp.ucd15.accept_15_addition"
        )
        invalid = copy.deepcopy(named["configuration"])
        invalid["capability"]["v1"]["timestamp_digit_profile"][
            "range_file_sha256"
        ] = "0" * 64
        candidate = copy.deepcopy(self.operational)
        candidate["capability"]["requested"] = invalid["capability"]
        candidate["capability"]["effective"] = invalid["capability"]
        with self.assertRaises(ValidationError):
            self.validator.validate(candidate)

    def test_manifest_freezes_94_separate_cases(self):
        manifest = _load(CORPUS / "manifest.json")
        self.assertEqual(manifest["case_count"], 94)
        self.assertEqual(self.document["case_count"], 94)
        self.assertEqual(len(self.document["vectors"]), 94)
        self.assertEqual(
            manifest["existing_corpora_unchanged"],
            {
                "canonicalization_v1_cases": 30,
                "canonicalization_v2_cases": 114,
                "result_contract_cases": 44,
            },
        )
        measurements = manifest["existing_corpus_measurements"]
        self.assertEqual(measurements["maximum_source_bytes"], 10_248)
        self.assertEqual(measurements["maximum_operation_snapshot_bytes"], 2_036)
        self.assertEqual(measurements["maximum_structural_depth"], 521)
        self.assertEqual(measurements["maximum_value_occurrences"], 527)
        self.assertEqual(measurements["measured_source_count"], 194)
        self.assertEqual(measurements["measured_operation_snapshot_count"], 56)

    def test_frozen_corpus_runner(self):
        completed = subprocess.run(
            [sys.executable, "conformance/run_legacy_v1_operational_policy.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("94/94 cases", completed.stdout)

    def test_frozen_corpus_rebuild_check(self):
        completed = subprocess.run(
            [sys.executable, "conformance/build_legacy_v1_operational_policy.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("verified: 94 cases", completed.stdout)

    def test_frozen_unicode_profile_audit(self):
        completed = subprocess.run(
            [sys.executable, "scripts/audit_unicode_nd_profiles.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Unicode Nd profile audit", completed.stdout)
        self.assertIn("13.0.0=bf287074", completed.stdout)
        self.assertIn("14.0.0=5a75c753", completed.stdout)
        self.assertIn("15.0.0=0f10e369", completed.stdout)


if __name__ == "__main__":
    unittest.main()
