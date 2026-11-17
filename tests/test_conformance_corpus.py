import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance"
DIMENSIONS = {
    "payload_integrity",
    "binding_field_consistency",
    "invocation_identity_consistency",
    "invocation_binding_consistency",
    "signature_validity",
    "trusted_signer_identity",
    "freshness",
    "authorization",
}


class TestConformanceCorpus(unittest.TestCase):
    def test_manifest_has_44_complete_unique_vectors(self):
        manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
        case_ids = set()
        execution_keys = set()
        referenced_bundles = set()
        referenced_trust_inputs = set()
        count = 0
        for relative in manifest["vector_files"]:
            document = json.loads((CORPUS / relative).read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "IMPLEMENTATION-ALIGNED")
            self.assertEqual(document["case_count"], len(document["vectors"]))
            for vector in document["vectors"]:
                self.assertNotIn(vector["case_id"], case_ids)
                case_ids.add(vector["case_id"])
                execution_key = json.dumps(
                    {
                        "operation": vector["operation"],
                        "input": vector["input"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                self.assertNotIn(execution_key, execution_keys)
                execution_keys.add(execution_key)
                expected = vector["expected"]
                self.assertTrue(expected["expected_non_claims"])
                if vector["operation"] == "verify":
                    self.assertEqual(set(expected["assurance_states"]), DIMENSIONS)
                    self.assertTrue((CORPUS / vector["input"]["bundle"]).is_dir())
                    referenced_bundles.add(vector["input"]["bundle"])
                else:
                    self.assertEqual(
                        set(expected["assurance_states"]["left"]), DIMENSIONS
                    )
                    self.assertEqual(
                        set(expected["assurance_states"]["right"]), DIMENSIONS
                    )
                    self.assertTrue((CORPUS / vector["input"]["left"]).is_dir())
                    self.assertTrue((CORPUS / vector["input"]["right"]).is_dir())
                    referenced_bundles.update(
                        (vector["input"]["left"], vector["input"]["right"])
                    )
                referenced_trust_inputs.update(
                    option
                    for option in vector["input"]["options"]
                    if option.startswith("fixtures/trust/")
                )
                count += 1
        self.assertEqual(count, 44)
        self.assertEqual(manifest["case_count"], 44)
        self.assertEqual(
            referenced_bundles,
            {
                str(path.relative_to(CORPUS))
                for path in (CORPUS / "fixtures" / "bundles").iterdir()
                if path.is_dir()
            },
        )
        self.assertEqual(
            referenced_trust_inputs,
            {
                str(path.relative_to(CORPUS))
                for path in (CORPUS / "fixtures" / "trust").iterdir()
                if path.is_file()
            },
        )

    def test_builders_match_committed_bytes(self):
        for script in ("build_fixtures.py", "build_vectors.py"):
            result = subprocess.run(
                [sys.executable, str(CORPUS / script), "--check"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_research_gaps_are_explicit_not_executable_claims(self):
        gaps = json.loads(
            (CORPUS / "comparison" / "research_gaps.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(gaps["status"], "RESEARCH")
        self.assertEqual(
            {item["gap_id"] for item in gaps["gaps"]},
            {
                "comparison.tool_declaration_changed",
                "comparison.provider_route_changed",
            },
        )
        self.assertTrue(all(item["status"] == "RESEARCH_GAP" for item in gaps["gaps"]))

    def test_runner_is_deterministic_and_passes_all_vectors(self):
        outputs = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, str(CORPUS / "run.py"), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        summary = json.loads(outputs[0])
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["cases"], 44)


if __name__ == "__main__":
    unittest.main()
