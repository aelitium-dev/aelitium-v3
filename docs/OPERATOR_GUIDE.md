# OPERATOR GUIDE

Golden rule:
Run the gate. If it fails, you do not release.

Common flow:
1) Build/Pack (Machine A)
2) Determinism check (Machine A)
3) Verify/Repro (Machine B)
4) Gate release (Machine B or controlled context)
5) Evidence Log entry
6) Tag created only on PASS

Commands:
- Gate:
  ./scripts/gate_release.sh <tag> <input_json>

- Determinism:
  ./scripts/bundle_determinism_check.sh

- Evidence:
  governance/logs/EVIDENCE_LOG.md

Dashboard:
- governance/dashboard/index.html (local UI, non-authoritative)
