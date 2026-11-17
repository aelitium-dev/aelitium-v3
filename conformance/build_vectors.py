#!/usr/bin/env python3
"""Build/check the deterministic machine-readable conformance manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

FULL = {
    "payload_integrity": "VALID",
    "binding_field_consistency": "VALID",
    "invocation_identity_consistency": "VALID",
    "invocation_binding_consistency": "VALID",
    "signature_validity": "ABSENT",
    "trusted_signer_identity": "UNESTABLISHED",
    "freshness": "NOT_EVALUATED",
    "authorization": "NOT_EVALUATED",
}
LEGACY = {
    **FULL,
    "invocation_identity_consistency": "ABSENT",
    "invocation_binding_consistency": "ABSENT",
}
IDENTITY_ONLY = {
    **FULL,
    "invocation_binding_consistency": "ABSENT",
}
UNBOUND = {
    **LEGACY,
    "binding_field_consistency": "ABSENT",
}
UNBOUND_FRESH_VALID = {**UNBOUND, "freshness": "VALID"}
LEGACY_FRESH_VALID = {**LEGACY, "freshness": "VALID"}
EARLY_INVALID = {
    "payload_integrity": "INVALID",
    "binding_field_consistency": "NOT_EVALUATED",
    "invocation_identity_consistency": "NOT_EVALUATED",
    "invocation_binding_consistency": "NOT_EVALUATED",
    "signature_validity": "ABSENT",
    "trusted_signer_identity": "UNESTABLISHED",
    "freshness": "NOT_EVALUATED",
    "authorization": "NOT_EVALUATED",
}
POLICY_INVALID = {
    "payload_integrity": "NOT_EVALUATED",
    "binding_field_consistency": "NOT_EVALUATED",
    "invocation_identity_consistency": "NOT_EVALUATED",
    "invocation_binding_consistency": "NOT_EVALUATED",
    "signature_validity": "NOT_EVALUATED",
    "trusted_signer_identity": "UNESTABLISHED",
    "freshness": "UNESTABLISHED",
    "authorization": "NOT_EVALUATED",
}
SIGNED = {**FULL, "signature_validity": "VALID"}
TRUSTED = {**SIGNED, "trusted_signer_identity": "VALID"}
TRUSTED_FRESH_VALID = {**TRUSTED, "freshness": "VALID"}
SIGNATURE_INVALID = {**FULL, "signature_validity": "INVALID"}
FRESH_VALID = {**FULL, "freshness": "VALID"}
FRESH_INVALID = {**FULL, "freshness": "INVALID"}
BINDING_INVALID = {**FULL, "binding_field_consistency": "INVALID"}
INVOCATION_INVALID = {
    **FULL,
    "invocation_identity_consistency": "INVALID",
    "invocation_binding_consistency": "INVALID",
}
INVOCATION_BINDING_INVALID = {
    **FULL,
    "invocation_binding_consistency": "INVALID",
}


def verify_case(
    case_id: str,
    description: str,
    bundle: str,
    *,
    rc: int,
    status: str,
    reason: str,
    states: dict[str, str],
    non_claims: list[str],
    options: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "description": description,
        "operation": "verify",
        "input": {
            "bundle": f"fixtures/bundles/{bundle}",
            "options": options or [],
        },
        "expected": {
            "rc": rc,
            "status": status,
            "reason": reason,
            "assurance_states": states,
            "expected_non_claims": non_claims,
        },
    }


def compare_case(
    case_id: str,
    description: str,
    left: str,
    right: str,
    *,
    rc: int,
    status: str,
    reason: str,
    basis: str,
    left_states: dict[str, str],
    right_states: dict[str, str],
    response_relationship: str | None,
    options: list[str] | None = None,
    required_basis: str | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "description": description,
        "operation": "compare",
        "input": {
            "left": f"fixtures/bundles/{left}",
            "right": f"fixtures/bundles/{right}",
            "options": options or [],
        },
        "expected": {
            "rc": rc,
            "status": status,
            "reason": reason,
            "comparison_basis": basis,
            "required_comparison_basis": required_basis,
            "response_relationship": response_relationship,
            "assurance_states": {
                "left": left_states,
                "right": right_states,
            },
            "expected_non_claims": [
                "model_drift_not_established",
                "semantic_equivalence_not_established",
                "response_causation_not_established",
            ],
        },
    }


def build_vector_files() -> dict[Path, bytes]:
    verification = [
        verify_case(
            "verification.valid_bundle",
            "This unsigned fixture satisfies the local bundle-consistency checks.",
            "full_a",
            rc=0,
            status="VALID",
            reason="OK",
            states=FULL,
            non_claims=["historical_occurrence_not_established"],
        ),
        verify_case(
            "verification.payload_tamper",
            "A canonical payload edit without a manifest digest update fails.",
            "payload_tamper",
            rc=2,
            status="INVALID",
            reason="HASH_MISMATCH",
            states=EARLY_INVALID,
            non_claims=["historical_occurrence_not_established"],
        ),
        verify_case(
            "verification.manifest_hash_mismatch",
            "A wrong well-formed manifest digest fails payload verification.",
            "manifest_hash_mismatch",
            rc=2,
            status="INVALID",
            reason="HASH_MISMATCH",
            states=EARLY_INVALID,
            non_claims=["semantic_truth_not_established"],
        ),
        verify_case(
            "verification.malformed_schema",
            "A self-consistently hashed payload missing a required field fails schema validation.",
            "malformed_schema",
            rc=2,
            status="INVALID",
            reason="CANONICAL_SCHEMA_INVALID",
            states=EARLY_INVALID,
            non_claims=["semantic_truth_not_established"],
        ),
        verify_case(
            "verification.self_consistent_replacement",
            "A rewritten unsigned artifact with all hashes recomputed remains internally valid.",
            "self_consistent_rewrite",
            rc=0,
            status="VALID",
            reason="OK",
            states=FULL,
            non_claims=[
                "historical_non_modification_not_established",
                "historical_occurrence_not_established",
            ],
        ),
    ]

    assurance = [
        verify_case(
            "assurance.distinct_absent_states",
            "One result keeps valid Freshness, absent optional evidence, unestablished signer trust, and non-evaluated authorization distinct.",
            "unbound",
            rc=0,
            status="VALID",
            reason="OK",
            states=UNBOUND_FRESH_VALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:00Z",
            ],
            non_claims=["capture_completeness_not_established"],
        ),
        verify_case(
            "assurance.binding_invalid_is_not_absent",
            "A present inconsistent v1 binding is INVALID rather than ABSENT.",
            "binding_mismatch",
            rc=2,
            status="INVALID",
            reason="BINDING_HASH_MISMATCH",
            states=BINDING_INVALID,
            non_claims=[
                "response_causation_not_established",
            ],
        ),
        verify_case(
            "assurance.early_failure_not_evaluated",
            "Non-canonical stored bytes fail before downstream dimensions are evaluated.",
            "canonical_bytes_mismatch",
            rc=2,
            status="INVALID",
            reason="CANONICAL_BYTES_MISMATCH",
            states=EARLY_INVALID,
            non_claims=["historical_non_modification_not_established"],
        ),
        verify_case(
            "assurance.authorization_always_not_evaluated",
            "A mathematically valid signature does not activate authorization.",
            "signed_valid",
            rc=0,
            status="VALID",
            reason="OK",
            states=TRUSTED_FRESH_VALID,
            options=[
                "--trust-store",
                "fixtures/trust/legitimate.json",
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:00Z",
            ],
            non_claims=["authorization_not_established"],
        ),
    ]

    trust = [
        verify_case(
            "trust.unsigned",
            "An explicit signature requirement rejects unsigned evidence while preserving ABSENT.",
            "model_changed",
            rc=2,
            status="INVALID",
            reason="SIGNATURE_REQUIRED",
            states=FULL,
            options=["--require-signature"],
            non_claims=["authorization_not_established"],
        ),
        verify_case(
            "trust.valid_signature_required",
            "A valid bundled signature satisfies the explicit signature requirement.",
            "signed_valid",
            rc=0,
            status="VALID",
            reason="OK",
            states=SIGNED,
            options=["--require-signature"],
            non_claims=[
                "trusted_signer_identity_not_established_by_signature"
            ],
        ),
        verify_case(
            "trust.valid_signature_without_trust_store",
            "Signature validity alone leaves signer trust UNESTABLISHED.",
            "signed_valid",
            rc=0,
            status="VALID",
            reason="OK",
            states=SIGNED,
            non_claims=[
                "trusted_signer_identity_not_established_by_signature"
            ],
        ),
        verify_case(
            "trust.valid_signature_with_trusted_key",
            "An explicit matching trust store establishes key-fingerprint membership.",
            "signed_valid",
            rc=0,
            status="VALID",
            reason="OK",
            states=TRUSTED,
            options=[
                "--trust-store",
                "fixtures/trust/legitimate.json",
                "--require-trusted-signer",
            ],
            non_claims=[
                "authorization_not_established",
                "provider_execution_not_established",
            ],
        ),
        verify_case(
            "trust.invalid_signature",
            "Malformed signature value is INVALID, not UNESTABLISHED or ABSENT.",
            "signed_invalid",
            rc=2,
            status="INVALID",
            reason="SIGNATURE_INVALID",
            states=SIGNATURE_INVALID,
            non_claims=["historical_occurrence_not_established"],
        ),
        verify_case(
            "trust.attacker_key_substitution_optional",
            "A substituted key can make a mathematical signature valid but not trusted by the supplied store.",
            "attacker_key_substitution",
            rc=0,
            status="VALID",
            reason="OK",
            states=SIGNED,
            options=["--trust-store", "fixtures/trust/legitimate.json"],
            non_claims=[
                "trusted_signer_identity_not_established_by_signature",
                "historical_occurrence_not_established",
            ],
        ),
        verify_case(
            "trust.attacker_key_substitution_required",
            "Required trust-store membership rejects a substituted signing key.",
            "attacker_key_substitution",
            rc=2,
            status="INVALID",
            reason="TRUSTED_SIGNER_NOT_FOUND",
            states=SIGNED,
            options=[
                "--trust-store",
                "fixtures/trust/legitimate.json",
                "--require-trusted-signer",
            ],
            non_claims=["historical_occurrence_not_established"],
        ),
    ]

    freshness = [
        verify_case(
            "freshness.no_policy",
            "Without a Freshness policy, even a malformed declared evidence time remains NOT_EVALUATED.",
            "malformed_timestamp",
            rc=0,
            status="VALID",
            reason="OK",
            states=FULL,
            non_claims=["trusted_historical_time_not_established"],
        ),
        verify_case(
            "freshness.complete_valid_policy",
            "The declared timestamp is valid at the inclusive age boundary.",
            "full_a",
            rc=0,
            status="VALID",
            reason="OK",
            states=FRESH_VALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:00Z",
            ],
            non_claims=[
                "trusted_historical_time_not_established",
                "historical_occurrence_not_established",
            ],
        ),
        verify_case(
            "freshness.stale_declared_timestamp",
            "One second past the maximum declared-time age is INVALID.",
            "full_a",
            rc=2,
            status="INVALID",
            reason="FRESHNESS_STALE",
            states=FRESH_INVALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:01Z",
            ],
            non_claims=["trusted_historical_time_not_established"],
        ),
        verify_case(
            "freshness.future_declared_timestamp",
            "A declared timestamp after the explicit reference time is INVALID.",
            "full_a",
            rc=2,
            status="INVALID",
            reason="FRESHNESS_TIMESTAMP_IN_FUTURE",
            states=FRESH_INVALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T11:59:59Z",
            ],
            non_claims=["trusted_historical_time_not_established"],
        ),
        verify_case(
            "freshness.malformed_declared_timestamp",
            "A schema-valid but non-time timestamp is INVALID only when policy selects it.",
            "malformed_timestamp",
            rc=2,
            status="INVALID",
            reason="FRESHNESS_TIMESTAMP_MALFORMED",
            states=FRESH_INVALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:00Z",
            ],
            non_claims=["trusted_historical_time_not_established"],
        ),
        verify_case(
            "freshness.incomplete_policy_pair",
            "One policy field alone is UNESTABLISHED and stops before bundle evaluation.",
            "full_a",
            rc=2,
            status="INVALID",
            reason="FRESHNESS_POLICY_INVALID",
            states=POLICY_INVALID,
            options=["--freshness-max-age-seconds", "300"],
            non_claims=["trusted_historical_time_not_established"],
        ),
        verify_case(
            "freshness.malformed_reference_time",
            "A malformed verifier-supplied reference time is a policy failure.",
            "full_a",
            rc=2,
            status="INVALID",
            reason="FRESHNESS_POLICY_INVALID",
            states=POLICY_INVALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "not-a-time",
            ],
            non_claims=["trusted_historical_time_not_established"],
        ),
    ]

    invocation = [
        verify_case(
            "invocation.valid_identity",
            "A stored invocation identity recomputes independently when invocation binding is absent.",
            "identity_only",
            rc=0,
            status="VALID",
            reason="OK",
            states=IDENTITY_ONLY,
            non_claims=[
                "provider_execution_not_established",
                "complete_invocation_identity_not_established",
            ],
        ),
        verify_case(
            "invocation.missing_identity",
            "A valid Freshness result does not upgrade missing invocation identity from ABSENT.",
            "legacy_request_changed",
            rc=0,
            status="VALID",
            reason="OK",
            states=LEGACY_FRESH_VALID,
            options=[
                "--freshness-max-age-seconds",
                "300",
                "--freshness-reference-time-utc",
                "2026-01-15T12:05:00Z",
            ],
            non_claims=["provider_execution_not_established"],
        ),
        verify_case(
            "invocation.malformed_identity",
            "A stale invocation identity hash is INVALID and invalidates its dependent binding.",
            "malformed_invocation",
            rc=2,
            status="INVALID",
            reason="INVOCATION_HASH_MISMATCH",
            states=INVOCATION_INVALID,
            non_claims=["provider_execution_not_established"],
        ),
        verify_case(
            "invocation.valid_binding",
            "A binding that recomputes and matches the local identity and response is VALID.",
            "full_b_changed_response",
            rc=0,
            status="VALID",
            reason="OK",
            states=FULL,
            non_claims=["response_causation_not_established"],
        ),
        verify_case(
            "invocation.binding_cross_field_mismatch",
            "An internally valid binding that references another identity is INVALID.",
            "invocation_binding_mismatch",
            rc=2,
            status="INVALID",
            reason="INVOCATION_BINDING_INPUT_MISMATCH",
            states=INVOCATION_BINDING_INVALID,
            non_claims=["response_causation_not_established"],
        ),
    ]

    comparison = [
        compare_case(
            "comparison.invocation_unchanged",
            "Matching invocation and response hashes are UNCHANGED.",
            "full_a",
            "full_a",
            rc=0,
            status="UNCHANGED",
            reason="RESPONSE_HASH_SAME",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship="SAME",
        ),
        compare_case(
            "comparison.invocation_changed",
            "Matching invocation hashes and different response hashes are CHANGED.",
            "full_a",
            "full_b_changed_response",
            rc=2,
            status="CHANGED",
            reason="RESPONSE_HASH_DIFFERENT",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship="DIFFERENT",
        ),
        compare_case(
            "comparison.same_request_hash_different_sampling",
            "Same request_hash but different represented temperature is NOT_COMPARABLE.",
            "full_a",
            "temperature_changed",
            rc=1,
            status="NOT_COMPARABLE",
            reason="INVOCATION_IDENTITY_HASH_DIFFERENT",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship=None,
        ),
        compare_case(
            "comparison.model_identifier_changed",
            "A selected invocation model change is NOT_COMPARABLE.",
            "full_a",
            "model_changed",
            rc=1,
            status="NOT_COMPARABLE",
            reason="INVOCATION_IDENTITY_HASH_DIFFERENT",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship=None,
        ),
        compare_case(
            "comparison.system_instruction_changed",
            "A system message change is a selected invocation identity change.",
            "full_a",
            "system_instruction_changed",
            rc=1,
            status="NOT_COMPARABLE",
            reason="INVOCATION_IDENTITY_HASH_DIFFERENT",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship=None,
        ),
        compare_case(
            "comparison.adapter_surface_changed",
            "A declared adapter surface change is NOT_COMPARABLE.",
            "full_a",
            "adapter_surface_changed",
            rc=1,
            status="NOT_COMPARABLE",
            reason="INVOCATION_IDENTITY_HASH_DIFFERENT",
            basis="INVOCATION_IDENTITY_V1",
            left_states=FULL,
            right_states=FULL,
            response_relationship=None,
        ),
        compare_case(
            "comparison.fallback_unchanged",
            "Legacy evidence visibly falls back and can be UNCHANGED.",
            "legacy_a",
            "legacy_a",
            rc=0,
            status="UNCHANGED",
            reason="RESPONSE_HASH_SAME",
            basis="REQUEST_HASH_V1_FALLBACK",
            left_states=LEGACY,
            right_states=LEGACY,
            response_relationship="SAME",
        ),
        compare_case(
            "comparison.fallback_changed",
            "Legacy evidence visibly falls back and can be CHANGED.",
            "legacy_a",
            "legacy_b_changed_response",
            rc=2,
            status="CHANGED",
            reason="RESPONSE_HASH_DIFFERENT",
            basis="REQUEST_HASH_V1_FALLBACK",
            left_states=LEGACY,
            right_states=LEGACY,
            response_relationship="DIFFERENT",
        ),
        compare_case(
            "comparison.fallback_request_difference",
            "Different selected request hashes are NOT_COMPARABLE under fallback.",
            "legacy_a",
            "legacy_request_changed",
            rc=1,
            status="NOT_COMPARABLE",
            reason="REQUEST_HASH_DIFFERENT",
            basis="REQUEST_HASH_V1_FALLBACK",
            left_states=LEGACY,
            right_states=LEGACY,
            response_relationship=None,
        ),
        compare_case(
            "comparison.strict_missing_invocation",
            "Strict invocation mode refuses legacy fallback.",
            "legacy_a",
            "legacy_a",
            rc=1,
            status="NOT_COMPARABLE",
            reason="INVOCATION_EVIDENCE_UNAVAILABLE",
            basis="NONE",
            required_basis="INVOCATION_IDENTITY_V1",
            left_states=LEGACY,
            right_states=LEGACY,
            response_relationship=None,
            options=["--require-invocation-evidence"],
        ),
        compare_case(
            "comparison.explicit_legacy_ignores_sampling_difference",
            "Legacy mode can be UNCHANGED despite different invocation identities.",
            "full_a",
            "temperature_changed",
            rc=0,
            status="UNCHANGED",
            reason="RESPONSE_HASH_SAME",
            basis="REQUEST_HASH_V1_LEGACY",
            left_states=FULL,
            right_states=FULL,
            response_relationship="SAME",
            options=["--legacy-request-hash-v1"],
        ),
        compare_case(
            "comparison.invalid_bundle_precedes_basis",
            "A failed bundle is INVALID_BUNDLE and no comparison basis is selected.",
            "payload_tamper",
            "full_a",
            rc=2,
            status="INVALID_BUNDLE",
            reason="BUNDLE_VERIFICATION_FAILED",
            basis="NONE",
            left_states=EARLY_INVALID,
            right_states=FULL,
            response_relationship=None,
        ),
    ]

    compatibility = [
        verify_case(
            "compatibility.legacy_bundle_valid",
            "A pre-invocation-style bundle remains readable and valid.",
            "legacy_a",
            rc=0,
            status="VALID",
            reason="OK",
            states=LEGACY,
            non_claims=["complete_invocation_identity_not_established"],
        ),
        verify_case(
            "compatibility.unsigned_default_valid",
            "Signature absence remains accepted by default.",
            "system_instruction_changed",
            rc=0,
            status="VALID",
            reason="OK",
            states=FULL,
            non_claims=["historical_occurrence_not_established"],
        ),
        verify_case(
            "compatibility.unbound_default_valid",
            "Original binding-field absence remains accepted by default.",
            "unbound",
            rc=0,
            status="VALID",
            reason="OK",
            states=UNBOUND,
            non_claims=["response_causation_not_established"],
        ),
        verify_case(
            "compatibility.require_binding_rejects_absence",
            "The existing explicit binding requirement still rejects absence.",
            "unbound",
            rc=2,
            status="INVALID",
            reason="BINDING_REQUIRED",
            states=UNBOUND,
            options=["--require-binding"],
            non_claims=["response_causation_not_established"],
        ),
    ]

    categories = {
        "verification/vectors.json": verification,
        "assurance/vectors.json": assurance,
        "trust/vectors.json": trust,
        "freshness/vectors.json": freshness,
        "invocation/vectors.json": invocation,
        "comparison/vectors.json": comparison,
        "compatibility/vectors.json": compatibility,
    }
    total = sum(len(vectors) for vectors in categories.values())
    if total != 44:
        raise AssertionError(f"expected 44 executable cases, got {total}")

    files: dict[Path, bytes] = {}
    for filename, vectors in categories.items():
        category = filename.split("/", 1)[0]
        document = {
            "corpus": "aelitium-contract-conformance-v1",
            "status": "IMPLEMENTATION-ALIGNED",
            "category": category,
            "case_count": len(vectors),
            "vectors": vectors,
        }
        files[Path(filename)] = (
            json.dumps(document, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    root_manifest = {
        "corpus": "aelitium-contract-conformance-v1",
        "status": "IMPLEMENTATION-ALIGNED",
        "case_count": total,
        "vector_files": list(categories),
        "research_gaps": "comparison/research_gaps.json",
        "result_schemas": {
            "verification": "../engine/schemas/verification_result_v1.json",
            "assurance": "../engine/schemas/assurance_result_v1.json",
            "comparison": "../engine/schemas/compare_result_v1.json",
        },
    }
    files[Path("manifest.json")] = (
        json.dumps(root_manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args()

    files = build_vector_files()
    mismatches = []
    for relative, content in sorted(files.items(), key=lambda item: str(item[0])):
        path = ROOT / relative
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        elif not path.exists() or path.read_bytes() != content:
            mismatches.append(str(relative))
    if mismatches:
        for mismatch in mismatches:
            print(f"MISMATCH {mismatch}")
        return 1
    print(f"VECTORS={'WRITTEN' if args.write else 'MATCH'} files={len(files)} cases=44")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
