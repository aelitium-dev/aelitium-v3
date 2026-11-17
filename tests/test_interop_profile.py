import json
import unittest
from pathlib import Path

from engine.result_contracts import (
    ASSURANCE_DIMENSIONS,
    CLAIM_BOUNDARY_VOCABULARY,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DOC = ROOT / "docs" / "interop" / "SCITT_AI_AGENT_RECEIPT_01.md"
PROFILE_MAPPING = (
    ROOT / "docs" / "interop" / "SCITT_AI_AGENT_RECEIPT_01.mapping.json"
)


def _mapping() -> dict:
    return json.loads(PROFILE_MAPPING.read_text(encoding="utf-8"))


class TestExperimentalScittAiAgentReceiptProfile(unittest.TestCase):
    def test_profile_is_exactly_pinned_and_explicitly_blocked(self):
        mapping = _mapping()
        self.assertEqual(mapping["status"], "EXPERIMENTAL")
        self.assertEqual(mapping["implementation_status"], "BLOCKED")
        self.assertIsNone(mapping["runtime_surface"])
        self.assertEqual(
            mapping["source_specification"]["identifier"],
            "draft-noa-scitt-ai-agent-receipt-01",
        )
        self.assertEqual(
            mapping["source_specification"]["wire_identifier"],
            "noa.receipt/0.1",
        )
        self.assertIn("**Status:** EXPERIMENTAL", PROFILE_DOC.read_text())
        self.assertIn("**Implementation status:** BLOCKED", PROFILE_DOC.read_text())

    def test_source_receipt_cannot_establish_any_native_dimension(self):
        projections = _mapping()["native_assurance_projection"]
        self.assertEqual(
            tuple(item["dimension"] for item in projections),
            ASSURANCE_DIMENSIONS,
        )
        self.assertTrue(
            all(not item["source_receipt_alone_can_establish"] for item in projections)
        )

    def test_external_signature_cannot_create_native_signature_or_trust(self):
        cases = {
            item["case"]: set(item["must_not_emit"])
            for item in _mapping()["prohibited_mappings"]
        }
        self.assertEqual(
            cases["valid_native_or_cose_source_signature"],
            {
                "signature_validity=VALID",
                "trusted_signer_identity=VALID",
            },
        )

    def test_missing_native_invocation_cannot_be_upgraded(self):
        cases = {
            item["case"]: set(item["must_not_emit"])
            for item in _mapping()["prohibited_mappings"]
        }
        self.assertEqual(
            cases["source_receipt_without_aelitium_invocation_material"],
            {
                "invocation_identity_consistency=VALID",
                "invocation_binding_consistency=VALID",
            },
        )

    def test_source_labels_and_time_cannot_create_native_assurance(self):
        cases = {
            item["case"]: set(item["must_not_emit"])
            for item in _mapping()["prohibited_mappings"]
        }
        self.assertEqual(
            cases["source_governance_or_approval_label_present"],
            {"authorization=VALID"},
        )
        self.assertEqual(
            cases["well_formed_or_signed_source_timestamp"],
            {"freshness=VALID"},
        )

    def test_source_hashes_cannot_select_aelitium_comparison_basis(self):
        cases = {
            item["case"]: set(item["must_not_emit"])
            for item in _mapping()["prohibited_mappings"]
        }
        self.assertEqual(
            cases["equal_source_params_hash_or_chain_hash"],
            {
                "comparison_basis=INVOCATION_IDENTITY_V1",
                "comparison_basis=REQUEST_HASH_V1_FALLBACK",
                "comparison_basis=REQUEST_HASH_V1_LEGACY",
            },
        )

    def test_profile_claim_codes_use_the_closed_aelitium_vocabulary(self):
        mapping = _mapping()
        self.assertEqual(
            mapping["claim_boundary_contract"], "aelitium-claim-boundary-v1"
        )
        self.assertTrue(
            set(mapping["claim_boundaries"]) <= CLAIM_BOUNDARY_VOCABULARY
        )


if __name__ == "__main__":
    unittest.main()
