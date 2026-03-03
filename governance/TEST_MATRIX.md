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

---

## Gate Results (Chronological)

### EPIC-1 + EPIC-2 Gate — 2026-03-03

| Test | Machine A | Machine B | Result |
|------|-----------|-----------|--------|
| Determinism (bundle) | PASS | PASS | ✅ |
| Offline verify (dir) | PASS | PASS | ✅ |
| Offline verify (zip) | PASS | PASS | ✅ |
| Tamper detection | PASS (rc=2) | PASS (rc=2) | ✅ |
| ZIP SHA256 cross-machine | `7561e12...` | `7561e12...` | ✅ MATCH |
| Unit tests | 20/20 | 20/20 | ✅ |

- commit: `eeefd1cbebe5be2bc3fb2f2600ebf0eb7755dc3b`
- bundle_schema: `1.1` (ed25519-v1 signatures required)
- evidence: `governance/logs/EVIDENCE_LOG.md` (entries: baseline A + gate B)
- Scripts validated: `test_full_release_flow.sh`, `test_release_zip_determinism.sh`
