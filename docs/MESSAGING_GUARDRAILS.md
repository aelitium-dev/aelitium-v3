# AELITIUM — Messaging Guardrails


---

## Canonical claim

> AELITIUM detects post-hoc modification of recorded LLM interactions,
> offline and deterministically.

Longer form:

> If a packed evidence bundle is modified after packing, you can prove it.
> Verification is offline, fail-closed, and requires no AELITIUM server.

---

## What AELITIUM is

A tamper-evidence primitive for LLM outputs.

- Packs a request+response pair into a deterministic evidence bundle
- Computes `binding_hash` — cryptographic link between request and response
- Any modification after packing → `STATUS=INVALID rc=2`
- Verification requires only the bundle and Python stdlib

---

## Threat model (short form)

```
Assumption:  an attacker may modify stored bundles
             the verifier does not trust the runtime that produced the bundle
             the verifier does not trust the LLM provider
             the verifier trusts SHA-256 and the canonicalization rules

Guarantee:   any modification after bundle creation is detectable

Non-goals:   execution authenticity
             origin proof (without P3 authority)
             semantic truth
             model correctness
```

Full version: `docs/TRUST_BOUNDARY.md`, `docs/SECURITY_MODEL.md`

---

## ICP (who this is for)

**Primary:**
- Teams with compliance or audit obligations (EU AI Act Art.12, SOC 2, ISO 42001)
- Pipelines where AI outputs influence regulated decisions
- Forensics / incident response (what exactly did the model say?)
- Enterprise integrations requiring verifiable AI records

**Secondary:**
- Developers building accountability layers over LLM pipelines
- ML teams tracking model behavior changes across versions

**Not the primary audience:**
- General-purpose developers / builders without accountability requirements
- Teams already satisfied with logging + observability

---

## Recommended phrases

| Use this | Instead of |
|----------|-----------|
| tamper-evident evidence bundles | proof of AI outputs |
| detects post-hoc modification | proves the model said this |
| integrity of captured interactions | truth of model outputs |
| offline, fail-closed verification | secure AI / trusted AI |
| binding_hash links request to response | cryptographic proof of LLM call |

---

## Prohibited phrases

These create expectations AELITIUM cannot fulfill:

| Do not say | Why |
|------------|-----|
| "proves the model produced this output" | AELITIUM proves the bundle wasn't modified — not that the packing was honest |
| "trust your AI" / "trustworthy AI" | Conflates integrity with semantic correctness |
| "execution authenticity" | Not provided without hardware attestation (P3+) |
| "detects model hallucinations" | Not in scope — AELITIUM proves tampering, not quality |
| "works for all developers" | Narrow ICP — overclaiming audience creates wrong expectations |

---

## Boundary statement (for README / site)

Use this verbatim when surfacing the trust boundary:

```
What this proves: bundle contents were not modified after packing.
What this does not prove: that the model produced this output,
that the output is correct, or that the capture process was honest.
Verification is offline, deterministic, and fail-closed.
```

---

## Demo framing

- `demo_full.cast` — public/canonical: shows `enable_litellm()` → bundle created → VALID → tamper → INVALID
- `demo_final.cast` — technical: tamper detection only, for audiences already familiar with the primitive

When posting publicly, use `demo_full.cast` and frame as:

> AELITIUM demo — zero-config tamper detection for LiteLLM calls
