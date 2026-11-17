# AELITIUM — Evidence Model

**Status:** CONCEPTUAL_MODEL_NON_NORMATIVE
**Current runtime authority:** [Messaging Guardrails](MESSAGING_GUARDRAILS.md), [Trust Boundary](TRUST_BOUNDARY.md)
**Related conceptual draft:** [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md)

This document describes a conceptual evidence model — what it could represent, its
emergent properties, and how it could sit within a layered AI trust stack. It does
not override or define current AELITIUM AI v1 runtime semantics.

These are architectural observations, not protocol requirements.

---

## What an evidence bundle represents

The conceptual evidence object includes a **deterministic commitment over stored
request and response hash fields**.

It records exactly one thing:

> These supplied request and response hash values are joined by this binding commitment.

For current AI v1, `request_hash` is a selected-field request identity and
`binding_hash` is a cryptographic commitment over the stored `request_hash` and
`response_hash`. Verification checks stored binding-field consistency; it does not
establish that a real-world request caused a response.

Nothing else. The bundle does not represent:

- that the model was correct or safe
- that the interaction was authorized or paid for
- that the agent that initiated the call was honest
- that the system that packed the bundle was trustworthy

Those properties belong to other layers.

---

## Adjacent layers: what the primitive is not

Temporal binding and delegation context are **not part of the evidence primitive**. They belong to layers that sit above or adjacent to the AELITIUM bundle:

- **Temporal binding** — when required, belongs to an adjacent attestation or receipt layer. Anchoring an interaction to a specific time is an external attestation concern; the bundle itself makes no claim about when execution occurred.
- **Delegation context** — agent identity, delegation chains, and authorisation credentials are agent-receipt-layer concerns. Any reference from such a layer needs separately defined artifact and encoding semantics; `binding_hash` alone is not a content hash of the complete bundle.

The conceptual primitive joins supplied request and response hash fields. Temporal
and delegation context belong to external layers; they do not redefine that
conceptual commitment.

> These are architectural observations, not protocol requirements. No runtime support for these reserved extensions is currently implemented. See [EVIDENCE_BUNDLE_SPEC.md](EVIDENCE_BUNDLE_SPEC.md) § Reserved Extensions.

---

## Selected-pair commitment

The current AELITIUM v1 construction is:

```
binding_hash = sha256(canonical({request_hash, response_hash}))
```

`binding_hash` deterministically commits to the recorded selected
`request_hash`/`response_hash` pair under the AELITIUM v1 construction. It is not
a content hash or identifier of the complete bundle, and it does not claim that
current v1 captures a complete provider invocation.

This leads to several emergent properties:

**Reproducible pair commitment**
Independent systems using the same stored `request_hash` and `response_hash` pair
derive the same `binding_hash` without coordination. That equality does not
establish bundle equality or complete invocation equivalence.

**Pair-level grouping**
Bundles with the same `binding_hash` can be grouped as carrying the same recorded
selected hash pair under this construction. They are not necessarily the same
artifact or complete evidence object.

**Offline reconstructibility**
Given the already-derived stored request and response hash values, a party can
derive the conceptual `binding_hash` offline. The current verifier does not
independently derive those fields from source request or response material.

These are consequences of the selected-pair construction — not protocol
requirements or complete-artifact addressing semantics.

---

## Reconstructible pair commitment

The `binding_hash` can be recomputed from the already-derived stored request and
response hash values without access to the original bundle.

```
binding_hash = sha256(canonical({
  "request_hash": request_hash,
  "response_hash": response_hash
}))
```

Any party possessing those stored hash values can independently reconstruct the
pair commitment. This does not reproduce, identify, or verify the complete current
AI v1 bundle.

### Consequences

**Independent verification**
An auditor can recompute the conceptual binding commitment from the stored hash
pair. Current AI v1 payload, schema, canonicalization, and manifest verification
still requires the governed bundle artifacts.

**Third-party reproducibility**
Independent systems using the same selected-field hash pair derive the same
conceptual `binding_hash` without coordination:

```
system A capture → binding_hash X
system B capture → binding_hash X
```

This could support cross-system correlation only when the parties separately agree
on the construction and the meaning of the selected hash fields. It is not, by
itself, artifact-level interoperability.

**Reduced trust requirements**
Deterministic reconstruction can reduce disagreement about the supplied hash pair.
It does not establish that a bundle was historically preserved or that the source
request and response were captured faithfully.

**Long-term recomputability**
The pair commitment remains derivable as long as the stored request and response
hash values and the construction are available.

### Boundary

Reconstructibility does not guarantee authenticity or causation. It establishes at
most that the supplied stored hash fields produce the stated commitment. It does
not establish that the model produced the response, that the provider executed a
complete invocation, or that the interaction occurred at a specific time. Those
assurances require independently trusted external mechanisms.

### Why this matters

Recomputability lets parties compare the recorded selected hash pair without
requiring a registry. Artifact preservation, complete-bundle identity, provenance,
and trust remain separate concerns.

These properties are emergent consequences of the deterministic evidence model, not protocol requirements.

---

## Potential cross-institution correlation

The conceptual model could provide a **cross-institution shared pair commitment** if
multiple parties possess the same stored request and response hash values and use
the same proposed construction. This is not a current cross-language conformance
claim, a complete-artifact reference, or proof of a real-world request–response
relationship.

This follows from deterministic construction over the recorded selected hash pair.

### Core property

Given two institutions A and B with no shared storage or execution environment: if
both possess the same stored hash pair, both can derive the same conceptual
`binding_hash`. This says nothing about trusted origin or complete invocation
identity.

### Consequences

**Trust decoupling**
Agreement on the pair commitment does not require agreement on provider,
transport layer, payment system, or execution environment. Trust in origin,
freshness, and authorization remains separate.

**Neutral reference across boundaries**
Different institutions can exchange the same `binding_hash` as a correlation value
without a central registry. Treating it as a reference to a particular artifact
requires additional, explicitly agreed reference semantics.

**Dispute minimization**
Disagreements about the pair commitment can be reduced to differences in the
supplied stored hash pair. Disputes about source material, execution, or log
history remain outside this model.

**Composability across systems**
Independent systems could associate records with the same pair commitment while
remaining operationally independent. This does not establish that their referenced
artifacts are byte-for-byte identical.

### Boundary

This property enables agreement on a recorded selected hash pair, not agreement on
complete evidence identity or truth of execution. It does not guarantee that the
model execution occurred, that the provider is honest, or that the response was
generated at a claimed time. Those require independently trusted mechanisms.

### Why this matters

The pair commitment may be one input to a future interoperability design. Artifact
boundaries, encodings, provenance, and relying-party trust still need explicit
agreement; none is supplied merely by exchanging `binding_hash`.

These properties are emergent consequences of the deterministic evidence model, not protocol requirements.

---

## Layered AI trust stack

The AELITIUM bundle sits as the **evidence primitive** in an emerging trust stack for AI interactions:

```
+---------------------------------------------------+
|                     Agents                        |
|  action receipts, workflow traces                 |
|  receipt/reference semantics defined externally  |
+------------------------↑--------------------------+
                         |
+------------------------|--------------------------+
|           Evidence Primitive (AELITIUM)           |
|  request_hash, response_hash, binding_hash        |
|  deterministic · offline · provider-neutral       |
+------------------------↑--------------------------+
                         |
+------------------------|--------------------------+
|           Transport Security                      |
|  signed envelopes, message authentication         |
|  carries artifacts or separately defined refs     |
+------------------------↑--------------------------+
                         |
+------------------------|--------------------------+
|               Payments                            |
|  payment_tx, paid inference records               |
|  association semantics defined externally         |
+---------------------------------------------------+
```

Each layer records or evaluates a different question:

| Layer | What it records or evaluates | What it does not establish by itself |
|-------|---------------|------------------------|
| Payments | A payment record under that layer's rules | Provider execution or the model output |
| Transport | Message integrity or authentication under that transport's trust inputs | The response semantics or causation |
| **AELITIUM AI v1** | Stored request/response/binding-field consistency | Complete invocation, causation, payment, identity, or execution |
| Agent receipts | An action assertion under the receipt layer's schema and trust inputs | The underlying evidence or real-world action by itself |

No layer gains artifact-reference semantics from `binding_hash` alone. A layer may
associate its own record with the selected-pair commitment, but a complete-bundle
reference requires a separately defined artifact hash and encoding.

---

## Neutrality property

The AELITIUM bundle is neutral between layers because:

- it belongs to no operational layer
- it can be referenced by any layer
- it can be verified independently of all layers
- its selected-pair commitment does not depend on provider, transport, payment, or agent framework

This can make the commitment useful as a correlation input in a layered design,
subject to separately defined artifact, provenance, and trust semantics.

---

## Relationship to existing standards

| Standard | Relationship |
|----------|-------------|
| SBOM (CycloneDX, SPDX) | Analogous concept applied to AI interactions instead of software components |
| Git commit objects | No equivalence claimed: Git object IDs hash a defined object serialization, while `binding_hash` commits only to the selected pair |
| IPFS CIDs | No equivalence claimed: a CID includes defined content-addressing semantics that `binding_hash` does not supply for a complete bundle |
| Sigstore | Similar trust model; AELITIUM is offline-first and semantics-specific |

Deterministic commitments and offline verification are established infrastructure
patterns. AELITIUM v1 applies a bounded selected-pair commitment; it does not claim
complete-bundle content addressing.
