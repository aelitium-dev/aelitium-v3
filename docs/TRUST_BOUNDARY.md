# AELITIUM — Trust Boundary

## What AELITIUM proves

AELITIUM provides **tamper-evidence** for AI outputs. When you pack an output and later verify it, a `STATUS=VALID` result means exactly one thing:

> The contents of the evidence bundle have not changed since they were packed.

Specifically:
- `ai_canonical.json` is intact
- The SHA-256 hash in `ai_manifest.json` matches the recomputed hash of the canonical JSON
- No bytes were modified, added, or removed

This is a cryptographic guarantee, not a policy. It holds regardless of who controls the storage system, as long as the stored `ai_hash_sha256` is trusted.

---

## What AELITIUM does not prove

### The model actually produced the output

AELITIUM is not a model output capture system. It packs whatever JSON you give it. If the packing step is in a compromised process, the bundle will faithfully record the compromised output.

**Mitigation:** pack immediately after generation, in the same trust boundary as the model call. See [INTEGRATION_PYTHON.md](INTEGRATION_PYTHON.md) for fail-closed pipeline patterns.

### The output is correct or safe

AELITIUM proves integrity, not quality. A tamper-evident record of a hallucination is still a hallucination.

**Mitigation:** combine AELITIUM with model evaluation and guardrails. These are orthogonal concerns.

### The stored hash hasn't been substituted

If an attacker controls both the evidence bundle and the location where `ai_hash_sha256` is stored, they can substitute a different valid bundle and hash consistently.

**Mitigation:** store hashes in a system the attacker cannot modify — a separate append-only database, an immutable log, or a signed receipt from a P3 authority (see below).

---

## Levels of provenance

| Level | What it provides | How |
|-------|-----------------|-----|
| **Hash only** (P2) | Tamper-evidence, given a trusted stored hash | `aelitium pack` + store hash in separate DB |
| **Authority receipt** (P3) | Tamper-evidence + timestamp attestation by a signing authority | `POST /v1/sign` → `receipt_v1` with Ed25519 signature |
| **Hardware attestation** (future) | Binding to a specific execution environment | TEE / HSM / remote attestation |

Each level answers a stronger question:

- **P2**: *"Has this output been modified since it was packed?"*
- **P3**: *"Did a trusted authority see this hash at this time?"*
- **Hardware**: *"Was this output produced in this specific environment?"*

---

## Integrity vs completeness

These are different properties:

- **Integrity**: packed evidence has not been altered after packing. AELITIUM provides this.
- **Completeness**: all events that should have been captured were captured. AELITIUM does not provide this.

If a logging agent selectively omits events before they reach the capture layer, no cryptographic mechanism can detect the omission — there is nothing to hash. This is a well-known property of tamper-evident logs in distributed systems: proving nothing was omitted is harder than proving nothing was altered.

**Implication for agent systems:** if the agent controls its own logging, it can omit entries without detection. An observer-based capture pattern — where an independent process intercepts LLM calls, rather than the agent calling the capture function — provides stronger completeness guarantees. This is the architectural direction for `aelitium.capture` in multi-agent deployments.

---

## Canonical threat model

| Threat | P2 (hash) | P3 (signed receipt) |
|--------|-----------|---------------------|
| Output tampered in storage | ✅ detected | ✅ detected |
| Manifest hash field altered | ✅ detected | ✅ detected |
| Both bundle and stored hash replaced consistently | ❌ not detected | ✅ detected (signature covers hash) |
| Bundle packed before/after the real generation | ❌ not detected | ✅ timestamp in receipt |
| Manually crafted bundle with valid hashes | ❌ not detected | ✅ requires authority to have seen hash at packing time |
| Packing process compromised | ❌ not detected | ❌ not detected |
| Agent omits events before capture | ❌ not detected | ❌ not detected |
| Model or prompt compromised before generation | ❌ out of scope | ❌ out of scope |

---

## Artifact forgery

Any party with access to the original inputs (the messages and model response) can reconstruct a bundle with valid, matching hashes. This is a known property of hash-based integrity systems, not a bug.

**Why this is expected behavior:**

An evidence bundle proves that a given payload was packed and has not changed since. It does not prove that the packing happened during the original model call or that no other party could have performed it. The hash is deterministic — that is a design goal, not a vulnerability.

**Consequence:** a bundle alone cannot prove that the person who packed it is the same person who made the API call. Anyone who knows the request and response can produce an identical bundle.

**Mitigations, in increasing strength:**

| Mitigation | What it adds |
|-----------|-------------|
| Capture adapter (P2) | `request_hash` ties the bundle to the exact API payload sent, not a reconstruction |
| Operator signing (P2+) | Ed25519 signature in `verification_keys.json` ties the bundle to the operator's private key |
| Authority receipt (P3) | External timestamp and signature prove the authority saw this hash at a specific time — forgery would require the authority's private key |
| Observer-based capture | Independent process intercepts the API call; the agent cannot forge what it did not control |

**Practical implication:** for internal audit trails and model drift detection, P2 hash-only bundles are sufficient — collusion requires controlling both the bundle and the hash store. For third-party audits or regulatory submissions, P3 receipts add non-repudiation.

---

## Practical guidance

### When P2 (hash only) is sufficient

- Internal audit trails where the hash DB is access-controlled separately from the evidence storage
- Pipelines where tamper-detection is needed but non-repudiation is not
- Debugging and reproducibility verification

### When P3 (signed receipt) adds value

- Third-party audits where the auditor needs independent attestation
- Regulatory contexts requiring a trusted timestamp from a named authority
- Dispute resolution where the chain of custody must be externally verifiable

### When neither is sufficient

- Proving that a model with specific parameters generated the output (requires model-level attestation)
- Proving the output is factually correct (requires evaluation, not integrity)
- Preventing adversarial prompt injection before generation

---

## Summary

AELITIUM is best understood as an **evidence preservation layer**, not a trust oracle.

It answers: *"Is what you have now what was recorded then?"*

It does not answer: *"Should you trust what was recorded?"*

For the latter, you need provenance — which is the direction of P3 and beyond.
