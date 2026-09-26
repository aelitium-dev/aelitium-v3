import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "legacy_v1_operational_policy"
PHASE2 = ROOT / "conformance" / "verifier_contract_phase2"
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
        cls.vectors = {
            vector["case_id"]: vector for vector in cls.document["vectors"]
        }
        cls.phase2_vectors = {
            vector["case_id"]: vector
            for vector in _load(PHASE2 / "source_vectors.json")["vectors"]
        }
        cls.operational = next(
            vector["expected"]["tool_result"]
            for vector in cls.document["vectors"]
            if vector["expected"]["kind"] == "OPERATIONAL_TOOL_RESULT"
        )

    def _current_semantic_candidate(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "engine.ai_cli",
                "verify-bundle",
                str(ROOT / "conformance" / "fixtures" / "bundles" / "full_a"),
                "--contract-json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        capability = copy.deepcopy(self.document["vectors"][0]["configuration"]["capability"])
        capability["signature_verification"] = {
            "profile": "ED25519_PORTABLE_STRICT_1"
        }
        return {
            "capability": {
                "effective": copy.deepcopy(capability),
                "requested": copy.deepcopy(capability),
            },
            "contract": "aelitium-verifier-tool-result-v1",
            "input_mode": "IMMUTABLE_BYTES",
            "limits": copy.deepcopy(
                self.document["vectors"][0]["configuration"]["limits"]
            ),
            "operation": "VERIFY_BUNDLE",
            "operational_result": None,
            "outcome": "SEMANTIC_RESULT",
            "rc": 0,
            "verification_result": json.loads(completed.stdout),
        }

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
                semantic_capability = copy.deepcopy(configuration["capability"])
                semantic_capability["signature_verification"] = {
                    "profile": "ED25519_PORTABLE_STRICT_1"
                }
                candidate = {
                    "capability": {
                        "effective": copy.deepcopy(semantic_capability),
                        "requested": copy.deepcopy(semantic_capability),
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
                missing_profile = copy.deepcopy(candidate)
                del missing_profile["capability"]["requested"]["signature_verification"]
                del missing_profile["capability"]["effective"]["signature_verification"]
                with self.assertRaises(ValidationError):
                    self.validator.validate(missing_profile)
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

    def test_input_outside_limit_forms_are_closed(self):
        categorical = copy.deepcopy(
            self.vectors["legacy.restricted.nonfinite.ignored_nan"]["expected"][
                "tool_result"
            ]
        )
        integer = copy.deepcopy(
            self.vectors["integer.portable.641"]["expected"]["tool_result"]
        )
        timestamp = copy.deepcopy(
            self.vectors["timestamp.portable.non_ascii_nd"]["expected"][
                "tool_result"
            ]
        )
        resource = copy.deepcopy(
            self.vectors["limit.file_bytes.above"]["expected"]["tool_result"]
        )

        for valid in (categorical, integer, timestamp):
            self.validator.validate(valid)

        missing = copy.deepcopy(categorical)
        del missing["operational_result"]["limit"]
        with self.assertRaises(ValidationError):
            self.validator.validate(missing)

        resource["operational_result"]["limit"] = None
        with self.assertRaises(ValidationError):
            self.validator.validate(resource)

        for name, unit in (
            ("FILE_BYTES", "BYTES"),
            ("STRUCTURAL_DEPTH", "LEVELS"),
        ):
            with self.subTest(unrelated_name=name):
                invalid = copy.deepcopy(integer)
                invalid["operational_result"]["limit"].update(
                    {"name": name, "unit": unit}
                )
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

        for candidate, wrong_unit in ((integer, "BYTES"), (timestamp, "DIGITS")):
            with self.subTest(wrong_unit=wrong_unit):
                invalid = copy.deepcopy(candidate)
                invalid["operational_result"]["limit"]["unit"] = wrong_unit
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

        for candidate in (integer, timestamp):
            for field in ("maximum", "observed_at_least"):
                with self.subTest(
                    name=candidate["operational_result"]["limit"]["name"],
                    field=field,
                ):
                    invalid = copy.deepcopy(candidate)
                    invalid["operational_result"]["limit"][field] = None
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

        invalid = copy.deepcopy(
            self.vectors["integer.portable.641"]["expected"]["tool_result"]
        )
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

    def test_rejected_capability_selection_requests_are_schema_valid_and_retained(self):
        case_ids = (
            "capability.selection.unsupported_v2",
            "capability.selection.unsupported_signature_profile",
            "capability.selection.named_profile_tuple_mismatch",
        )
        for case_id in case_ids:
            with self.subTest(case_id=case_id):
                case = self.vectors[case_id]
                result = case["expected"]["tool_result"]
                self.validator.validate(result)
                self.assertEqual(
                    result["capability"]["requested"],
                    case["configuration"]["capability"],
                )
                self.assertIsNone(result["capability"]["effective"])
                self.assertEqual(
                    result["operational_result"],
                    {
                        "detail": None,
                        "input_ref": None,
                        "limit": None,
                        "operational_code": "CAPABILITY_PROFILE_UNAVAILABLE",
                        "phase": "CAPABILITY_SELECTION",
                    },
                )

    def test_unsupported_requested_values_are_forbidden_in_semantic_results(self):
        candidate = self._current_semantic_candidate()
        for component, value in (
            (("v2", "capability"), "V2_FUTURE"),
            (("signature_verification", "profile"), "ED25519_FUTURE"),
        ):
            with self.subTest(component=component):
                invalid = copy.deepcopy(candidate)
                invalid["capability"]["requested"][component[0]][component[1]] = value
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_broad_requested_syntax_is_limited_to_capability_selection(self):
        unsupported = copy.deepcopy(
            self.vectors["capability.selection.unsupported_v2"]["expected"][
                "tool_result"
            ]
        )

        unrelated = copy.deepcopy(unsupported)
        unrelated["capability"]["effective"] = copy.deepcopy(
            self._current_semantic_candidate()["capability"]["effective"]
        )
        unrelated["operational_result"]["operational_code"] = "INTERNAL_OPERATION_ERROR"
        unrelated["operational_result"]["phase"] = "SEMANTIC_EVALUATION"
        with self.assertRaises(ValidationError):
            self.validator.validate(unrelated)

        dispatch = copy.deepcopy(unsupported)
        dispatch["operational_result"]["phase"] = "DISPATCH"
        dispatch["operational_result"]["input_ref"] = "AI_MANIFEST_JSON"
        with self.assertRaises(ValidationError):
            self.validator.validate(dispatch)

    def test_requested_identifier_grammar_is_closed_ascii(self):
        template = copy.deepcopy(
            self.vectors["capability.selection.unsupported_v2"]["expected"][
                "tool_result"
            ]
        )
        for identifier in ("", " ", "V2 FUTURE", "V2/FUTURE", "V2_FUTURÉ"):
            with self.subTest(identifier=identifier):
                invalid = copy.deepcopy(template)
                invalid["capability"]["requested"]["v2"]["capability"] = identifier
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_unsupported_dispatch_is_representable_only_at_capability_selection(self):
        selection = copy.deepcopy(
            self.vectors["capability.selection.unsupported_v2"]["expected"][
                "tool_result"
            ]
        )
        selection["capability"]["requested"]["dispatch"] = "AELITIUM_DISPATCH_FUTURE"
        selection["capability"]["requested"]["v2"]["capability"] = "V2_PORTABLE"
        self.validator.validate(selection)

        dispatch = copy.deepcopy(selection)
        dispatch["operational_result"]["phase"] = "DISPATCH"
        dispatch["operational_result"]["input_ref"] = "AI_MANIFEST_JSON"
        with self.assertRaises(ValidationError):
            self.validator.validate(dispatch)

    def test_requested_v1_syntax_separates_shape_from_availability(self):
        template = copy.deepcopy(
            self.vectors["capability.selection.unsupported_v2"]["expected"][
                "tool_result"
            ]
        )
        template["capability"]["requested"]["v2"]["capability"] = "V2_PORTABLE"

        unknown = copy.deepcopy(template)
        unknown["capability"]["requested"]["v1"] = {"capability": "V1_FUTURE"}
        self.validator.validate(unknown)

        unknown_extra = copy.deepcopy(unknown)
        unknown_extra["capability"]["requested"]["v1"]["future_parameter"] = "VALUE"
        with self.assertRaises(ValidationError):
            self.validator.validate(unknown_extra)

        missing = copy.deepcopy(template)
        del missing["capability"]["requested"]["v1"]["integer_conversion"]
        with self.assertRaises(ValidationError):
            self.validator.validate(missing)

        named = copy.deepcopy(
            self.vectors["capability.selection.named_profile_tuple_mismatch"][
                "expected"
            ]["tool_result"]
        )
        for maximum in (639, None):
            with self.subTest(maximum=maximum):
                valid = copy.deepcopy(named)
                valid["capability"]["requested"]["v1"]["integer_conversion"] = {
                    "maximum_decimal_digits": maximum,
                    "mode": "BOUNDED",
                }
                self.validator.validate(valid)

        unlimited_integer = copy.deepcopy(named)
        unlimited_integer["capability"]["requested"]["v1"]["integer_conversion"] = {
            "maximum_decimal_digits": 640,
            "mode": "UNLIMITED",
        }
        self.validator.validate(unlimited_integer)

        for maximum in (-1, True, 9_007_199_254_740_992):
            with self.subTest(invalid_maximum=maximum):
                invalid = copy.deepcopy(named)
                invalid["capability"]["requested"]["v1"]["integer_conversion"] = {
                    "maximum_decimal_digits": maximum,
                    "mode": "BOUNDED",
                }
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

        for member, value in (
            ("unicode_version", "15.0"),
            ("unicode_version", "v15.0.0"),
            ("range_file_sha256", "A" * 64),
            ("range_file_sha256", "0" * 63),
        ):
            with self.subTest(invalid_profile_member=member, value=value):
                invalid = copy.deepcopy(named)
                invalid["capability"]["requested"]["v1"][
                    "timestamp_digit_profile"
                ][member] = value
                with self.assertRaises(ValidationError):
                    self.validator.validate(invalid)

    def test_complete_altered_portable_v1_request_is_representable_only_as_unavailable(self):
        template = copy.deepcopy(
            self.vectors["capability.selection.unsupported_v2"]["expected"][
                "tool_result"
            ]
        )
        template["capability"]["requested"]["v2"]["capability"] = "V2_PORTABLE"
        for member, value in (
            (("integer_conversion", "maximum_decimal_digits"), 641),
            (("timestamp_digit_profile",), "ND"),
            (("timestamp_final_lf",), "REJECT"),
        ):
            with self.subTest(member=member):
                valid = copy.deepcopy(template)
                target = valid["capability"]["requested"]["v1"]
                if len(member) == 2:
                    target[member[0]][member[1]] = value
                else:
                    target[member[0]] = value
                self.validator.validate(valid)

    def test_historical_signature_omission_remains_schema_valid(self):
        historical = self.vectors["operation.output_io"]["expected"]["tool_result"]
        self.assertNotIn(
            "signature_verification",
            historical["capability"]["requested"],
        )
        self.validator.validate(historical)

    def test_categorical_cases_match_phase2_sources_and_expected_outcomes(self):
        pairs = (
            (
                "legacy.restricted.nonfinite.ignored_nan",
                "manifest.v1.source.ignored_nan",
                "NONFINITE",
            ),
            (
                "legacy.restricted.surrogate.ignored_opaque_unmatched_high",
                "manifest.v1.source.ignored_opaque_unmatched_surrogate",
                "OPAQUE_SURROGATE",
            ),
        )
        for restricted_id, phase2_id, value_class in pairs:
            with self.subTest(case_id=restricted_id):
                case = self.vectors[restricted_id]
                self.assertEqual(
                    case["configuration"]["capability"]["v1"]["capability"],
                    "V1_RESTRICTED_PORTABLE",
                )
                self.assertEqual(case["input"]["value_class"], value_class)
                source = bytes.fromhex(case["input"]["source"]["recipe"]["hex"])
                phase2_source = self.phase2_vectors[phase2_id]["source"]["text"].encode(
                    "utf-8"
                )
                self.assertEqual(source, phase2_source)
                result = case["expected"]["tool_result"]
                self.assertEqual(result["outcome"], "OPERATIONAL_OUTCOME")
                self.assertIsNone(result["verification_result"])
                self.assertNotIn("assurance", result)
                self.assertEqual(
                    result["operational_result"],
                    {
                        "detail": None,
                        "input_ref": "AI_MANIFEST_JSON",
                        "limit": None,
                        "operational_code": "INPUT_OUTSIDE_DECLARED_CAPABILITY",
                        "phase": "MANIFEST_PARSE",
                    },
                )

    def test_existing_capability_fact_cases_are_byte_preserved(self):
        integer = self.vectors["integer.portable.641"]["expected"]
        self.assertEqual(
            integer["tool_result_sha256"],
            "086d4be55b2f884537c48736a35d52afdf605efc521beee5ae1cbae4e6cf6494",
        )
        self.assertEqual(
            integer["tool_result"]["operational_result"]["limit"],
            {
                "maximum": 640,
                "name": "INTEGER_DECIMAL_DIGITS",
                "observed_at_least": 641,
                "unit": "DIGITS",
            },
        )
        timestamp = self.vectors["timestamp.portable.non_ascii_nd"]["expected"]
        self.assertEqual(
            timestamp["tool_result_sha256"],
            "a95197abc683f09593403f0b1862a7c2bb910000b3eaa91ae9c621c6c2544187",
        )
        self.assertEqual(
            timestamp["tool_result"]["operational_result"]["limit"],
            {
                "maximum": "ASCII",
                "name": "TIMESTAMP_DIGIT_PROFILE",
                "observed_at_least": "U+0661",
                "unit": "PROFILE",
            },
        )

    def test_original_96_are_byte_preserved_and_three_cases_are_appended(self):
        original = self.document["vectors"][:96]
        original_bytes = json.dumps(
            original,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        original_ids = ("\n".join(case["case_id"] for case in original) + "\n").encode()
        self.assertEqual(
            hashlib.sha256(original_bytes).hexdigest(),
            "136e7e2740a11b90de41df414e60dcbe4439e505a1262292603acf75f2f5af4a",
        )
        self.assertEqual(
            hashlib.sha256(original_ids).hexdigest(),
            "06aebcaf038031b006cee5f3289a6133c41d776f8c64396a0233a6d9d082493a",
        )
        self.assertEqual(
            [case["case_id"] for case in self.document["vectors"][96:]],
            [
                "capability.selection.unsupported_v2",
                "capability.selection.unsupported_signature_profile",
                "capability.selection.named_profile_tuple_mismatch",
            ],
        )

    def test_manifest_freezes_99_separate_cases(self):
        manifest = _load(CORPUS / "manifest.json")
        self.assertEqual(manifest["case_count"], 99)
        self.assertEqual(self.document["case_count"], 99)
        self.assertEqual(len(self.document["vectors"]), 99)
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
        self.assertIn("99/99 cases", completed.stdout)

    def test_frozen_corpus_rebuild_check(self):
        completed = subprocess.run(
            [sys.executable, "conformance/build_legacy_v1_operational_policy.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("verified: 99 cases", completed.stdout)

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
