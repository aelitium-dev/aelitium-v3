# Changelog

All notable changes to AELITIUM are documented here.

Format: `[version] — date — description`

A dated `[version]` heading in this file means that version was released and
tagged. A line under development appears under `[Unreleased]` and is converted to
a dated heading in the release commit that immediately precedes its annotated
tag.

Entries below `[0.2.4]` are historical and are retained as originally written.
Two known artefacts of that history are preserved rather than rewritten: a legacy
`[unreleased] — 2026-03-10` heading whose work shipped in the 0.2.x line, and a
`[0.2.1]` entry recorded after `[0.1.0]`. Neither denotes a currently unreleased
version.

---

## [Unreleased]

### Changed

- **Versioned invocation-first compare contract** — development for v0.4.0
  introduces `aelitium-compare-v1`. The default `compare` mode uses validated
  `aelitium-invocation-v1` hashes when both bundles report
  `invocation_identity_consistency=VALID` and
  `invocation_binding_consistency=VALID`; otherwise valid bundles visibly use
  `REQUEST_HASH_V1_FALLBACK`.
- **Explicit compare modes** — `--require-invocation-evidence` disables the
  request-hash fallback, while `--legacy-request-hash-v1` preserves the v0.3.x
  request-hash decision contract. Comparison output now reports its contract,
  mode, basis, reason, invocation-hash relationship, and per-side invocation
  assurance states.
- Existing exit codes remain unchanged: `0` for `UNCHANGED`, `1` for
  `NOT_COMPARABLE`, and `2` for `CHANGED` or `INVALID_BUNDLE`. Existing bundles
  without invocation evidence remain readable through the visible fallback.

This development work does not change `request_hash` v1, evidence schemas,
capture adapter semantics, or verifier trust boundaries. It is not a v0.4.0
release entry and has no release date.

---

## [0.3.0] — 2026-08-27

**Release status.** The repository and package baseline is `0.3.0`, released
through the annotated `v0.3.0` tag, its GitHub Release, and the `0.3.0` PyPI
publication.

The entries below cover all material work on the 0.3.0 line through
`7e007f60ca884a6dc44e63aec1f8f5243ab2ed6e` (merge of PR #23).

### Breaking

These change the verification and capture surface relative to 0.2.4. Bundles and
callers accepted under 0.2.4 may now be rejected.

- **Fail-closed v1 contract enforcement** — bundles missing required v1 fields are
  rejected at verification time rather than silently passing. Bundles that
  verified under 0.2.4 solely because a required field was absent now fail.
- **Fail-closed `compare`** — `compare` no longer reports a comparison result when
  a bundle cannot be established as valid; it fails closed instead.
- **Reserved capture-metadata keys** — adapter-owned metadata keys are reserved.
  A caller supplying a reserved key now raises `CaptureMetadataCollisionError`
  (`CAPTURE_METADATA_RESERVED_KEY_COLLISION`) instead of silently overwriting
  adapter-owned fields. This protects adapter-owned fields from caller metadata
  collisions; it does not address filesystem concurrency.
- **Invocation-evidence migration** — legacy bundles without invocation identity
  and invocation binding evidence remain accepted and report `ABSENT`; malformed
  or incomplete evidence is rejected when those fields are present. Current
  capture adapters add the versioned invocation fields to canonical metadata, so
  the complete `ai_hash_sha256` can differ from an otherwise comparable legacy
  capture. The v1 `request_hash` and `binding_hash` constructions and their public
  identifiers remain unchanged.

### Added

- **Explicit assurance-state model** — verification reports
  `payload_integrity`, `binding_field_consistency`,
  `invocation_identity_consistency`, `invocation_binding_consistency`,
  `signature_validity`, `trusted_signer_identity`, `freshness`, and
  `authorization` separately. States distinguish evaluated results, optional
  absence, unestablished trust or policy, and non-evaluation. Unsigned and unbound
  bundles remain `VALID` by default unless `--require-signature` or
  `--require-binding` is used.
- **Trusted signer store** — a local trusted signer store primitive
  (`engine/trust.py`), with normalized handling of trust store read failures.
- **Trusted signer identity evaluation** — the verifier evaluates trusted signer
  identity against an explicitly supplied external trust store, exposed on
  `verify` and `verify-bundle` as `--trust-store` and `--require-trusted-signer`.
  Without such a store, `trusted_signer_identity` remains `UNESTABLISHED`.
- **Invocation identity** — a versioned invocation-identity primitive
  (`engine/invocation.py`), recorded by the capture adapters and checked for
  consistency by the verifier as `invocation_identity_consistency`. Invocation
  identity is recorded separately from `request_hash`; recording it does not
  change v1 `request_hash` construction.
- **Invocation binding** — a versioned invocation-binding primitive
  (`engine/invocation_binding.py`) binding invocation identity to the response
  hash, consulted by the bundle verifier for parsing and recomputation as
  `invocation_binding_consistency`.
- **Deterministic Freshness** — an explicit maximum age and explicit UTC reference
  time evaluate declared-time recency from `ai_canonical.json.ts_utc`, without an
  implicit system clock. With no policy pair, `freshness` is `NOT_EVALUATED`;
  invalid or incomplete policy is `UNESTABLISHED`; stale, future, or malformed
  selected evidence time is `INVALID`; an in-window timestamp is `VALID`.
  Freshness options are exposed by the public verifier API, `verify`,
  `verify-bundle`, and the standalone verifier.

### Changed

- **Centralized authoritative AI bundle verification** — a single authoritative
  verification code path replaces divergent verification branches across the CLI
  and library entry points.
- Standalone manifest timestamp validation aligned with shared verifier behaviour
  (`scripts/aelitium_verify_standalone.py`).
- Documentation and public-claim guardrails: public-facing docs bound what current
  verification does and does not establish, with an executable public-claims
  guardrail (`scripts/guardrail_public_claims.sh`) gated in CI.

### Capture adapters

- **OpenAI** — native adapter (`engine/capture/openai.py`) covering synchronous and
  streaming chat completions, with optional Ed25519 signing at capture time.
  Records invocation identity and invocation binding.
- **LiteLLM** — capture adapter plus `enable_litellm()` auto-capture, with strict
  and verbose modes; auto-capture bundles are written under `binding_hash`.
  Synchronous and non-streaming.
- **Anthropic** — adapter (`engine/capture/anthropic.py`) is supported and records
  invocation identity and invocation binding. Synchronous and non-streaming. It
  requires the `anthropic` extra; its tests skip when the extra is absent locally
  and are required to execute in CI (see below).

### Tests and CI

- **CI test-suite gate (through PR #23)** — the assurance test suite is gated across
  supported Python versions. `.github/workflows/tests.yml` runs the suite on
  Python 3.10, 3.11 and 3.12 with provider extras installed (`pip install -e
  ".[all]"`), and fails the job if any test is skipped, so provider adapter tests
  cannot silently stop executing. The end-to-end matrix
  (`scripts/run_test_matrix.sh`) runs in the same workflow.
- **529 test cases on each supported interpreter** — CI runs the 529-case suite
  separately on Python 3.10, 3.11, and 3.12 with provider extras. This is a
  per-interpreter count, not one aggregate count across the matrix.
- Expanded adversarial verification coverage: malformed governed hash matrix,
  signature stripping, binding stripping, attacker signer substitution,
  unsupported version and signature algorithm, canonicalization golden vectors,
  LiteLLM excluded behaviour-parameter characterization, and malformed manifest
  timestamp parity.
- `.github/workflows/release-audit.yml` gates `scripts/audit_release.sh` on push
  and pull request.

### Persistent assurance and compatibility boundaries

Verification establishes internal consistency of recorded evidence on the
validated surface. It does not establish:

- **Historical occurrence** — that the model actually executed, or that the
  provider was honest.
- **Causation** — that a real-world request caused the recorded response.
  Verification checks stored binding-field consistency only.
- That the response is correct, truthful, complete, or that capture was complete.

Additional contract and compatibility boundaries:

- The `ai_output_v1` schema identifier is unchanged.
- v1 `request_hash` and `binding_hash` construction is unchanged.
- Request identity remains selected-field identity, not full invocation identity.
- `trusted_signer_identity` remains `UNESTABLISHED` unless an external trust store
  is explicitly supplied for evaluation.
- `freshness` is `NOT_EVALUATED` without the complete explicit policy pair and is
  evaluated only when both policy inputs are supplied.
- `authorization` remains `NOT_EVALUATED`.
- Canonicalization is the deterministic JSON form identified by
  `json_sorted_keys_no_whitespace_utf8`. It is **not** RFC 8785 / JCS and does not
  claim RFC 8785 compatibility or cross-language equivalence beyond matching these
  exact rules. See [docs/CANONICALIZATION_SPEC.md](docs/CANONICALIZATION_SPEC.md).

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
