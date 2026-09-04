import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "contract_demo" / "run_demo.py"
SCHEMAS = ROOT / "engine" / "schemas"


class TestContractDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temporary = tempfile.TemporaryDirectory()
        root = Path(cls._temporary.name)
        cls.first = root / "first"
        cls.second = root / "second"
        for output in (cls.first, cls.second):
            result = subprocess.run(
                [sys.executable, str(DEMO), "--output-dir", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise AssertionError(result.stdout + result.stderr)
            if not result.stdout.startswith("STATUS=PASS\n"):
                raise AssertionError(result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    @staticmethod
    def _load(directory: Path, filename: str) -> dict:
        return json.loads((directory / filename).read_text(encoding="utf-8"))

    @staticmethod
    def _schema(filename: str) -> dict:
        return json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))

    def test_output_set_and_bytes_are_deterministic(self):
        expected = {
            "verification-result.json",
            "assurance-result.json",
            "comparison-result.json",
            "not-comparable-result.json",
            "interpretation.txt",
        }
        self.assertEqual({path.name for path in self.first.iterdir()}, expected)
        self.assertEqual({path.name for path in self.second.iterdir()}, expected)
        for filename in expected:
            with self.subTest(filename=filename):
                self.assertEqual(
                    (self.first / filename).read_bytes(),
                    (self.second / filename).read_bytes(),
                )

    def test_generated_json_matches_contract_schemas(self):
        verification = self._load(self.first, "verification-result.json")
        assurance = self._load(self.first, "assurance-result.json")
        changed = self._load(self.first, "comparison-result.json")
        refused = self._load(self.first, "not-comparable-result.json")
        Draft7Validator(self._schema("verification_result_v1.json")).validate(
            verification
        )
        Draft7Validator(self._schema("assurance_result_v1.json")).validate(
            assurance
        )
        compare_validator = Draft7Validator(self._schema("compare_result_v1.json"))
        compare_validator.validate(changed)
        compare_validator.validate(refused)

    def test_required_outcomes_and_boundaries_are_visible(self):
        verification = self._load(self.first, "verification-result.json")
        states = {
            item["dimension"]: item["state"]
            for item in verification["assurance"]["dimensions"]
        }
        self.assertEqual(verification["status"], "VALID")
        self.assertEqual(states["signature_validity"], "VALID")
        self.assertEqual(states["trusted_signer_identity"], "UNESTABLISHED")
        self.assertEqual(states["freshness"], "NOT_EVALUATED")
        self.assertEqual(states["authorization"], "NOT_EVALUATED")
        self.assertEqual(
            self._load(self.first, "comparison-result.json")[
                "comparability_result"
            ],
            "CHANGED",
        )
        refused = self._load(self.first, "not-comparable-result.json")
        self.assertEqual(refused["comparability_result"], "NOT_COMPARABLE")
        self.assertIsNone(refused["response_relationship"])
        text = (self.first / "interpretation.txt").read_text(encoding="utf-8")
        self.assertIn("model_drift_not_established", text)
        self.assertIn("provider_execution_not_established", text)


if __name__ == "__main__":
    unittest.main()
