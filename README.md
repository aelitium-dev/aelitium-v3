# AELITIUM v3

Institutional rebuild after WSL incident (2026-02-24).

## Purpose
Clean consolidation of AELITIUM architecture.

## Structure

- engine/      → Deterministic core (to rebuild)
- artifacts/   → Phase 3 frozen artifacts (recovered)
- governance/  → Incident & environment policy
- scripts/     → Operational tooling
- docs/        → Documentation
- tests/       → Determinism & reproducibility validation

## Status
Foundation complete (v0.2.0 pre-release). Engine implemented, cross-machine validated.

- bundle_schema: `1.1` (ed25519-v1 signatures required)
- CLI: `aelitium pack | verify | repro` (installable via `pip install .`)
- Tests: 20/20 PASS on Machine A and Machine B
- Signing: Ed25519, key via env var `AEL_ED25519_PRIVKEY_B64`

## Entry
- docs/ENTRYPOINT.md
- docs/SYSTEM_MAP.md
- docs/DOCS_SYSTEM.md

## Index (single entry)
- docs/INDEX.md
