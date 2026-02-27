# AELITIUM Test Matrix (CRITICAL)

These tests are fail-closed.
If any CRITICAL test fails, Phase 4 is blocked.

## CRITICAL

1) Determinism (bundle)
- Run: bundle_determinism_check.sh
- PASS: run1 hash == run2 hash

2) Tamper detection

NOTE: verify uses --manifest and --evidence (not --input).
- Modify bundle bytes
- PASS: verify => INVALID

3) Machine B authority verification
- Build/pack on Machine A
- Verify/repro on Machine B
- PASS: verify PASS, repro PASS

4) Gate fail-closed
- Run gate with invalid input
- PASS: no tag created

5) Evidence mandatory
- Every release/tag MUST have a log entry
- PASS: evidence entry exists before/with tag

6) Clean tree on release
- PASS: git status is clean at tagging time

## ARTIFACTS

- Evidence Log:
  governance/logs/EVIDENCE_LOG.md

- Gate:
  scripts/gate_release.sh <tag> <input_json>

- Determinism:
  scripts/bundle_determinism_check.sh

