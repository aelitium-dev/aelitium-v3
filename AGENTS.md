# AGENTS.md - AELITIUM v3

## Scope
- Applies only to this repository: `aelitium-v3`.
- Canonical engine: `aelitium-v3`.
- `aelitium-v3_bundle` is artifact/export context, not source-of-truth for decisions.

## Global Guardrails
1. Do not run `git` commands unless the user explicitly asks in the current turn.
2. Do not edit files before presenting:
   - `Plan` (max 10 lines)
   - target file list
   - objective PASS/FAIL criteria
3. Every change must include deterministic tests and explicit PASS/FAIL outcomes.
4. Fail-closed by default:
   - if requirement is ambiguous or evidence is insufficient, stop and ask for A/B/C decision.
5. Deterministic boundary must be stable:
   - no clock, random, uuid, network, or hidden environment dependency in hashed artifacts.
6. Keep changes minimal and scoped; no feature work during hardening.

## Determinism Checklist
- Canonical JSON uses a single method across pack/verify.
- Verify re-canonicalizes before hash comparison.
- Schema constraints are enforced end-to-end.
- Timestamped metadata is kept outside deterministic hash boundary.
- Output hash is stable across repeated runs with same input.
- Paths and local machine differences do not change deterministic outputs.

## A/B Sync Rules
- Default mode (remote):
  - Machine A pushes to remote.
  - Machine B fetches/pulls before validation.
- Authority mode (offline bundle):
  - Machine A creates `git bundle` + sha256.
  - Machine B verifies sha256, then applies bundle.
  - Evidence must record sync mode and bundle sha256.
- Machine B never validates manually copied, untracked state as authoritative.

## Agent Roles
### 1) Architect
- Defines invariants, threat/risk map, and change order (P0/P1/P2).
- Produces:
  - `Plan`
  - target files
  - PASS/FAIL criteria
  - minimal test matrix

### 2) Implementer
- Applies smallest possible diff that satisfies Architect criteria.
- No scope creep, no unrelated refactors.
- Produces:
  - `Changes` summary by file
  - exact commands to run tests

### 3) Verifier
- Validates behavior with objective tests (positive and negative cases).
- Produces:
  - `Tests` with expected and actual outcomes
  - PASS/FAIL per criterion

### 4) Auditor
- Checks alignment with:
  - `docs/ENGINE_CONTRACT.md`
  - `governance/policies/DETERMINISM_POLICY.md`
  - evidence/gate rules
- Produces:
  - mismatch list with severity (`P0/P1/P2`)
  - release-readiness decision (`GO/NO_GO`)

## Standard Output Contract
All agents must return sections in this order:
1. `Plan`
2. `Changes`
3. `Tests`
4. `Decision`
5. `Open Questions` (only if blocked)

## Fail-Closed Decision Rule
- If any P0 criterion fails, final decision is `NO_GO`.
- Do not downgrade P0 failures to warnings.
