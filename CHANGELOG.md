# Changelog

All notable changes to AELITIUM are documented here.

Format: `[version] — date — description`

---

## [0.2.0] — 2026-03-04

### P2 — AI Output Integrity Layer (new)

- `aelitium-ai validate` — JSON Schema validation of `ai_output_v1`
- `aelitium-ai canonicalize` — deterministic canonical JSON + SHA-256 hash
- `aelitium-ai pack` — evidence bundle: `ai_canonical.json` + `ai_manifest.json`
- `aelitium-ai verify` — offline integrity verification with tamper detection
- `engine/ai_canonical.py` — canonicalization engine
- `engine/ai_pack.py` — pack function (deterministic, cross-machine stable)
- `engine/schemas/ai_output_v1.json` — JSON Schema for AI output contract
- 43 contract tests (validate × 8, canonicalize × 7, pack × 19, verify × 10)

### P1 — Deterministic Release SDK

- `aelitium pack | verify | repro` CLI
- Ed25519 signing via `cryptography` library
- Bundle schema `1.1` (enforced)
- A/B authority gate with evidence log
- `governance/` templates (evidence log, release checklist, market feedback)
- 76 total tests — determinism confirmed on Machine A and Machine B

### Infrastructure

- `pyproject.toml` entrypoints: `aelitium`, `aelitium-ai`
- Apache-2.0 license
- `docs/AI_INTEGRITY_DEMO.md` — 5-minute walkthrough
- `docs/RELEASE_AUTHORITY_SERVICE.md` — P3 architecture design

---

## [0.1.0] — 2026-02-24

- Initial engine rebuild after WSL incident
- Canonical JSON + SHA-256 core
- Basic pack/verify/repro pipeline
