# AELITIUM — Trust Boundary

## What AELITIUM v1 verification establishes

A `STATUS=VALID` result establishes the internal consistency of the AI evidence
bundle being inspected. Specifically, current v1 verification can establish:

- the payload satisfies `ai_output_v1`
- `ai_canonical.json` uses the governed canonical serialization
- the manifest identifiers and lowercase SHA-256 fields satisfy the v1 contract
- `ai_hash_sha256` matches the independently reconstructed canonical payload
- stored request, response, and binding hash fields are consistent when binding
  evidence is present
- bundled Ed25519 verification material is mathematically valid when present

This result does not, by itself, prove that the inspected artifact is historically
unchanged. A fully self-consistent replacement can verify unless the verifier has
an independently trusted external hash, key identity, receipt, or equivalent
anchor.

The assurance dimensions must be interpreted separately:

| Dimension | Current v1 interpretation |
|---|---|
| `payload_integrity` | Payload/schema/canonical/manifest/hash consistency |
| `binding_field_consistency` | Stored v1 binding fields are `VALID`, `INVALID`, or `ABSENT` |
| `signature_validity` | Mathematical signature result, or `ABSENT` |
| `trusted_signer_identity` | `UNESTABLISHED` |
| `freshness` | `NOT_EVALUATED` |
| `authorization` | `NOT_EVALUATED` |

Unsigned and unbound bundles remain valid by default. `--require-signature` and
`--require-binding` let callers reject absence for their verification context.

---

## What AELITIUM does not prove

### The model actually produced the output

The core pack/verifier accepts the valid `ai_output_v1` object it is given. Native
OpenAI and Anthropic adapters and a LiteLLM adapter can reduce the manual handoff,
but they do not authenticate model execution. If the capture or packing process is
compromised, a bundle can faithfully record compromised input.

**Mitigation:** pack immediately after generation, in the same trust boundary as the model call. See [INTEGRATION_PYTHON.md](INTEGRATION_PYTHON.md) for fail-closed pipeline patterns.

### The output is correct or safe

AELITIUM evaluates evidence consistency, not quality. A consistently represented
record of a hallucination is still a hallucination.

**Mitigation:** combine AELITIUM with model evaluation and guardrails. These are orthogonal concerns.

### The stored hash hasn't been substituted

If an attacker controls both the evidence bundle and the location where `ai_hash_sha256` is stored, they can substitute a different valid bundle and hash consistently.

**Mitigation:** store hashes in a system the attacker cannot modify — a separate append-only database, an immutable log, or a signed receipt from a P3 authority (see below).

---

## Levels of provenance

| Level | What it provides | How |
|-------|-----------------|-----|
| **Hash only** (P2) | Internal consistency; historical tamper-evidence given a trusted stored hash | `aelitium pack` + store hash in separate DB |
| **Authority receipt** (P3) | Tamper-evidence + timestamp attestation by a signing authority | `POST /v1/sign` → `receipt_v1` with Ed25519 signature |
| **Hardware attestation** (future) | Binding to a specific execution environment | TEE / HSM / remote attestation |

Each level answers a stronger question:

- **P2**: *"Is this payload consistent with the independently trusted hash?"*
- **P3**: *"Did a trusted authority see this hash at this time?"*
- **Hardware**: *"Was this output produced in this specific environment?"*

---

## Integrity vs completeness

These are different properties:

- **Integrity**: the inspected payload, contract, and recorded hashes are internally consistent. Historical non-modification additionally requires a trusted anchor.
- **Completeness**: all events that should have been captured were captured. AELITIUM does not provide this.

If a logging agent selectively omits events before they reach the capture layer, no cryptographic mechanism can detect the omission — there is nothing to hash. This is a well-known property of tamper-evident logs in distributed systems: proving nothing was omitted is harder than proving nothing was altered.

**Implication for agent systems:** if the agent controls its own logging, it can omit entries without detection. An observer-based capture pattern — where an independent process intercepts LLM calls, rather than the agent calling the capture function — provides stronger completeness guarantees. This is the architectural direction for `aelitium.capture` in multi-agent deployments.

---

## Canonical threat model

| Threat | P2 with independently trusted hash | P3 (signed receipt) |
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

Any party able to construct a complete valid `ai_output_v1` object can produce a
self-consistent bundle. Selected request and response material is sufficient to
reproduce the v1 binding fields, while timestamps and metadata also contribute to
the complete canonical payload hash. This is a known property of hash-based
consistency systems, not a bug.

**Why this is expected behavior:**

An evidence bundle establishes that its current payload and recorded evidence are
internally consistent. It does not prove that packing happened during the original
model call, that the artifact was never replaced, or that no other party could
have produced a self-consistent bundle. Deterministic hashing is a design goal,
not a producer-authentication mechanism.

**Consequence:** a bundle alone cannot prove that the person who packed it is the
same person who made the API call. A party that knows the selected request and
response material can produce self-consistent v1 hashes and evidence; timestamps
or other metadata may still make the complete bundle bytes differ.

**Mitigations, in increasing strength:**

| Mitigation | What it adds |
|-----------|-------------|
| Capture adapter (P2) | Records selected v1 request and response fields in the adapter-controlled call path; verification checks their stored hash consistency |
| Operator signing (P2+) | Ed25519 material in `verification_keys.json` can establish mathematical signature validity; bundled key material does not establish trusted signer identity |
| Authority receipt (P3) | External timestamp and signature prove the authority saw this hash at a specific time — forgery would require the authority's private key |
| Observer-based capture | Independent process intercepts the API call; the agent cannot forge what it did not control |

**Practical implication:** P2 hash-only bundles can support internal comparison and
audit workflows when the expected hash is independently protected. Bundle-only
verification does not establish origin, freshness, authorization, or historical
non-modification.

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
