# AELITIUM v3 — Determinism Policy

## Rule 1 — Two Runs
Two consecutive `repro` executions MUST produce identical hashes.

## Rule 2 — Tamper Detection
Any modification of canonical_payload MUST result in rc=2.

## Rule 3 — No Entropy
Engine MUST NOT:
- Use system clock
- Use random()
- Use external network
- Depend on environment variables

## Rule 4 — Canonical Boundary
Only canonical JSON (sorted keys, fixed separators, UTF-8) is valid.

Violation of any rule = INVALID release.
