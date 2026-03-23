# Session Handoff — 2026-03-19

> Note: This document is a session-level handoff capturing decisions and state at a specific point in time. It is not a normative specification.

## Summary

This session closed the current consistency cycle across:

- core implementation
- core docs
- public README
- site repo
- site live surface

The result is a materially coherent AELITIUM state for technical exposure, with the core trust boundary preserved and no known remaining protocol-level wording drift in the validated public surface.

---

## Canonical system identity

Use this as the default external description unless explicitly superseded:

> AELITIUM is a library/CLI for producing and verifying tamper-evident, offline-verifiable evidence bundles for recorded LLM interactions under deterministic canonicalization.

Short external line:

> AELITIUM proves integrity of recorded LLM interactions — not correctness.

More precise internal line:

> AELITIUM proves integrity of recorded LLM artifacts — not correctness.

---

## Core decisions reaffirmed

- Do not widen the trust boundary.
- Do not claim authenticity, truth, or provider honesty.
- Do not claim causal attribution from `compare`.
- Keep `verify-bundle` as an integrity verifier with minimum operational structural checks.
- Treat canonicalization as part of the verification contract.
- Do not silently redefine canonicalization identifiers.

---

## Core repository work completed

Repository:

- `/home/catarina-aelitium/aelitium-v3-clean-a`

State reached:

- core `main` aligned with `origin/main`
- fail-closed compare semantics already in place
- trust-boundary docs aligned
- canonicalization formalized
- README credibility pass completed

### Canonicalization

Added:

- [`docs/CANONICALIZATION_SPEC.md`](docs/CANONICALIZATION_SPEC.md)

Purpose:

- make the current canonicalization behavior explicit
- define the current manifest identifier
- document non-guarantees
- establish a versioning rule

Current canonicalization identifier:

- `json_sorted_keys_no_whitespace_utf8`

Canonicalization v1 was treated as frozen in meaning:

> `json_sorted_keys_no_whitespace_utf8` must not change semantics silently.

### Canonicalization identifier alignment

Aligned:

- [`docs/EVIDENCE_BUNDLE_SPEC.md`](docs/EVIDENCE_BUNDLE_SPEC.md)

This removed the conflicting older identifier:

- `json-canonical-v1`

After this session, the canonicalization identifier is consistent across the relevant core surface.

### README credibility close

Updated:

- [`README.md`](README.md)

Main improvements:

- added canonical system identity near the top
- added `What it proves`
- added `What it does not prove`
- added correct `binding_hash` construction
- added `Why logs are not enough`
- kept license aligned with Apache-2.0
- kept wording bounded to the validated surface

### Binding construction fixed in public core docs

The README now reflects the implemented construction:

```text
binding_hash = SHA256(
  canonical({
    "request_hash": request_hash,
    "response_hash": response_hash
  })
)
```

This replaced any risk of ambiguous concat-style wording.

---

## Site repository work completed

Repository:

- `/home/catarina-aelitium/aelitium-site`

State reached:

- site `main` aligned with `origin/main`
- wording hardened
- trust model block present
- binding formula corrected
- messaging guardrails aligned

### Site wording hardening

`index.html` was hardened to align with the implemented protocol and trust boundary.

Stabilized terminology:

- `canonicalized request input`
- `recorded response`
- `tamper-evident evidence bundle`

### Trust model block

The public site now includes an explicit trust model block covering:

- guarantees
- non-guarantees
- offline trust assumptions
- tamper detection vs behavior drift

### Binding formula correction

Critical public wording error fixed:

Old incorrect public wording:

```text
SHA256(request_hash || response_hash)
```

Corrected site wording:

```text
SHA256(canonical({request_hash, response_hash}))
```

### Site messaging guardrail alignment

Updated:

- `MESSAGING_SPEC.md`

Removed residual internal drift such as:

- `canonical request scope`
- `Detect behavior changes between verified captures`

Replaced with the hardened terminology:

- `canonicalized request input`
- `Detect differences between recorded responses for the same canonicalized request input`

### Meta description alignment

The site `<meta name="description">` was updated so that SEO/snippet copy no longer carried older, broader wording.

---

## Live-site validation completed

The public site was checked directly and validated as aligned on the critical protocol wording.

Confirmed live:

```text
binding_hash = SHA256(canonical({request_hash, response_hash}))
```

This closed the most important remaining public inconsistency.

---

## Demo decision

Official onboarding demo:

- [`examples/drift_demo/run_demo.sh`](examples/drift_demo/run_demo.sh)

Reason:

- deterministic
- offline
- reproducible
- no provider dependency
- aligned with the trust boundary

Real-world demos already present:

- [`examples/litellm_enable.py`](examples/litellm_enable.py)
- [`examples/capture_openai.py`](examples/capture_openai.py)
- [`examples/model_drift_detector.py`](examples/model_drift_detector.py)

Current recommendation:

- onboarding/public proof: `drift_demo`
- external validation with live provider: LiteLLM/OpenAI path

---

## Public exposure readiness

The system is now coherent enough for initial technical exposure.

What is coherent:

- implementation
- canonicalization contract
- README
- bundle spec
- site wording
- site messaging guardrail

What remains weak:

- real-world usage validation
- market validation
- one canonical integration story in practice

---

## Key guarantees and non-guarantees

### Guarantees on the validated surface

- tamper-evident evidence bundles
- deterministic binding of canonicalized request/response artifacts
- offline verification
- fail-closed verification semantics
- deterministic comparison outcomes over recorded artifacts

### Non-guarantees

- model execution authenticity
- provider honesty
- semantic correctness
- full provenance
- complete capture
- cross-language equivalence by default
- global chain-of-custody without additional layers

---

## Important wording locked in

Prefer:

- `canonicalized request input`
- `recorded response`
- `offline-verifiable`
- `fail-closed`
- `validated surface`

Avoid:

- `canonical request scope`
- `model changed`
- `what the model actually said`
- `guarantees behavior`
- `any machine` when it exceeds validated scope
- incorrect concat-style `binding_hash` descriptions

---

## Governance / workflow state

Observed and reinforced in this cycle:

- protected `main`
- PR flow required
- merge should remain explicit
- core trust semantics must not change without updating:
  - spec
  - README
  - site
  - messaging guardrails

Working rule:

> Public surface must not describe a different cryptographic construction than the implemented protocol.

---

## Remaining non-blocking gaps

These are not core blockers, but remain open:

1. `aelitium-site` still needs a small README for repository credibility.
2. PyPI short description is coherent enough, but less precise than current institutional wording.
3. Some residual site wording is broader than the strictest standard, but not materially contradictory.
4. Real-world integration/use is still under-validated.
5. Canonicalization v2, normalization changes, or trust-mode expansion should not be opened in the next step.

---

## Recommended next step

Do **not** reopen the core protocol now.

Best next step:

- use the existing offline drift demo as the canonical onboarding demo
- validate one real integration path, preferably LiteLLM/OpenAI
- gather external technical feedback

Only after real usage/feedback:

- refine non-critical public wording
- revisit packaging metadata
- consider broader protocol formalization work

---

## Session close assessment

At the end of this session, AELITIUM is best described as:

- technically strong
- semantically disciplined
- publicly coherent enough for technical exposure
- still commercially unvalidated

This cycle should be treated as:

> core trust-surface consistency freeze

and not as an invitation to add new core features.
