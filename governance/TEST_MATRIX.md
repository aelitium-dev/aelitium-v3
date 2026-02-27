# AELITIUM - Deterministic Test Matrix

## CRITICAL TESTS (Release Blocking)

| ID | Test | Machine | Expected | Blocking |
|----|------|---------|----------|----------|
| T1 | Clean repo required | A+B | FAIL if dirty | YES |
| T2 | Synced with origin/main | A+B | FAIL if ahead/behind | YES |
| T3 | Evidence validation | A+B | PASS | YES |
| T4 | Double rebuild hash match | A | Identical SHA256 | YES |
| T5 | Tamper detection | A+B | INVALID (rc=2) | YES |
| T6 | Offline tag verification | B | Good signature | YES |
| T7 | Tag nonexistent before signing | B | Must not exist | YES |

---

## NON-BLOCKING TESTS

| ID | Test | Machine | Expected |
|----|------|---------|----------|
| N1 | Authority status check | B | AUTHORITY_STATUS=GO |
| N2 | Validator presence | A+B | `scripts/validate_evidence_log.py` exists |

---

## Determinism Rule

Release is VALID only if:
- All CRITICAL tests PASS
- Evidence contains `machine_role=A` pre-sign evidence and `machine_role=B` authority attestation for the target tag
- Tag signature verifies offline (`git tag -v`)
