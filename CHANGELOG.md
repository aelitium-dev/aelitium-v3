# Changelog

All notable changes to AELITIUM are documented here.

Format: `[version] — date — description`

---

## [0.3.0] — 2026-08-17 — repository/package baseline after P0 audit

This is the current repository and package baseline established by the P0 AI
Assurance hardening pass. It is not a PyPI release. No GitHub Release or PyPI
publication exists for this version.

### Changed
- Centralized AI bundle verification into a single authoritative code path,
  eliminating divergent verification branches across CLI and library entry points
- Explicit assurance states replace implicit pass/fail: verification results now
  carry a declared status (`VALID`, `INVALID`, `UNSIGNED`, `UNBOUND`) rather
  than being inferred from exit code alone
- Stricter v1 contract enforcement: bundles missing required v1 fields are
  rejected at verification time rather than silently passing
- Capture metadata collision protection: concurrent captures to the same output
  directory no longer risk partial overwrites
- Expanded adversarial verification coverage: test suite now covers bundle
  substitution, field injection, hash-prefix collision, and timestamp replay
  scenarios
- Documentation and public-claim guardrails: public-facing docs now accurately
  bound what current verification establishes and does not establish
- Standalone verifier timestamp parity: `scripts/offline_verify.sh` now applies
  the same timestamp checks as the in-process verifier

### Boundaries (unchanged from 0.2.4)
- `ai_output_v1` schema identifier is unchanged
- v1 `request_hash` and `binding_hash` construction is unchanged
- Request identity remains selected-field identity, not full invocation identity
- `trusted_signer_identity` remains `UNESTABLISHED`
- Freshness and authorization remain `NOT_EVALUATED`

---

## [0.2.4] — 2026-03-14

### Added
- `aelitium scan --ci` — CI-friendly `AELITIUM_SCAN_*` key=value output
- `aelitium scan` now shows `Coverage: N/M (%)` in normal output
- `scan --json` now includes `coverage_pct` field
- `from aelitium import capture_openai` — short convenience alias for `capture_chat_completion`
- `from aelitium import capture_anthropic` — short alias for `capture_anthropic_message`

### Changed
- README restructured: drift detection demo at the top, scan with coverage metric, simplified capture adapter example using `capture_openai`
- Tagline updated to: "Detect when LLM behavior silently changes — verifiable, offline, no server."

### Tests
- 177 tests, all PASS (added 6 for `--ci` and coverage metric)

---

## [0.2.3] — 2026-03-13

### Added
- `aelitium scan <path>` — scan Python files for uninstrumented LLM call sites
  - Detects OpenAI, Anthropic, LiteLLM, LangChain call patterns
  - Reports instrumented vs missing capture adapter per file:line
  - Exit codes: 0 = all instrumented, 2 = gaps found (CI/CD friendly)
  - `--json` output for pipeline integration

### Fixed
- `engine/capture/anthropic.py` — now imports `anthropic` at module level, so
  `from aelitium import capture_anthropic_message` raises `ImportError` with install
  hint when `anthropic` is not installed (previously raised `TypeError`)
- `tests/test_capture_anthropic.py` — skips gracefully when `anthropic` not installed

### Tests
- 171 tests, all PASS (added 13 for `scan`, skip guard for 6 Anthropic tests)

---

## [0.2.2] — 2026-03-11

### Added
- `aelitium compare <bundle_a> <bundle_b>` — detect AI model behavior change between two capture bundles
  - Returns `UNCHANGED` / `CHANGED` / `NOT_COMPARABLE` / `INVALID_BUNDLE`
  - Exit codes: 0 / 2 / 1 / 2 (CI/CD friendly)
  - `--json` output includes full hash values for both bundles and timestamps
- `aelitium verify-bundle <dir>` — dedicated verify command with binding_hash recompute and signature enforcement
- Optional dependencies: `pip install aelitium[openai]`, `aelitium[anthropic]`, `aelitium[all]`
- `docs/MODEL_BEHAVIOR_CHANGE.md` — guide for detecting AI provider behavior change
- `docs/MARKET_FEEDBACK.md` — market feedback log

### Fixed
- `docs/INTEGRATION_PYTHON.md` — corrected import path (`engine.capture.openai`, not `engine.capture_openai`)
- `aelitium/__init__.py` — `capture_anthropic_message` now raises `ImportError` with install hint if `anthropic` not installed
- Removed duplicate `aelitium-ai` CLI entrypoint from `pyproject.toml`
- `compare` output now shows actual hash values (first 16 chars) and timestamps for debugging

### Tests
- 158 tests, all PASS (added 12 for `compare`, 17 for `verify-bundle`)

---

## [unreleased] — 2026-03-10

### Capture Layer — OpenAI adapter

- `engine/capture/openai.py` — `capture_chat_completion()`: intercepts OpenAI
  chat calls and packs request+response into a tamper-evident bundle automatically.
  Captures `request_hash` and `response_hash` at call time, closing the trust gap.
- `engine/capture/__init__.py` — capture layer package
- 14 tests: happy path (10) + determinism EPIC (4)
  - same request → same request_hash ✅
  - same response → same response_hash ✅
  - different output → different hash ✅
  - tampered canonical → INVALID ✅
- Validated on Machine A and Machine B: 100 tests PASS, repro PASS

### Docs & compliance

- `docs/EVIDENCE_BUNDLE_SPEC.md` — complete bundle format spec (structure,
  verification algorithm, schema evolution, relation to SBOM/OTel/Sigstore)
- `docs/INTEGRATION_CAPTURE.md` — capture adapter usage guide
- `docs/TEST_MATRIX.md` — full breakdown of all 100 tests
- `README.md` — compliance alignment section (EU AI Act Art.12, SOC2 CC7,
  ISO 42001, NIST AI RMF)

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

## [0.2.1] - 2026-03-10
### Added
- OpenAI capture adapter
- Anthropic capture adapter
- Signed binding evidence
- Evidence log support
- Compliance export
- Standalone verifier

### Verified
- 129 tests passing
- reproducibility check passing
- signed release tags on Machine B
- PyPI publication successful
- clean install of aelitium==0.2.1 successful
