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

The conceptual evidence object is a **content-addressed commitment over stored
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
- **Delegation context** — agent identity, delegation chains, and authorisation credentials are agent-receipt-layer concerns. They reference the bundle by `binding_hash` but do not enter its construction.

The conceptual primitive joins supplied request and response hash fields. Temporal
and delegation context belong to external layers; they do not redefine that
conceptual commitment.

> These are architectural observations, not protocol requirements. No runtime support for these reserved extensions is currently implemented. See [EVIDENCE_BUNDLE_SPEC.md](EVIDENCE_BUNDLE_SPEC.md) § Reserved Extensions.

---

## Content-addressability

In this conceptual model, bundle identity is defined as:

```
bundle_id = binding_hash = sha256(canonical({request_hash, response_hash}))
```

and `binding_hash` is derived deterministically from the supplied stored hash pair,
the conceptual evidence object is **content-addressed**. This is not a claim that
current v1 captures a complete provider invocation.

This leads to several emergent properties:

**Reproducible identity**
Independent systems using the same stored `request_hash` and `response_hash` pair
derive the same conceptual `binding_hash` without coordination. That equality does
not establish complete invocation equivalence.

**Natural deduplication**
Bundles can be deduplicated by `binding_hash` without a central registry. If two bundles share a `binding_hash`, they are the same evidence object.

**Offline reconstructibility**
Given the already-derived stored request and response hash values, a party can
derive the conceptual `binding_hash` offline. The current verifier does not
independently derive those fields from source request or response material.

These are consequences of the evidence model — not protocol requirements. Implementations are not required to implement caching or deduplication.

---

## Reconstructible evidence

In this conceptual model, an evidence identifier (`binding_hash`) can be recomputed
from the already-derived stored request and response hash values without access to
the original bundle.

```
binding_hash = sha256(canonical({
  "request_hash": sha256(canonical_request),
  "response_hash": sha256(canonical_response)
}))
```

Any party possessing those stored hash values can independently reconstruct the
conceptual identifier. This does not reproduce or verify the complete current AI
v1 bundle.

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

This enables cross-system evidence correlation without a shared registry.

**Reduced trust requirements**
Deterministic reconstruction can reduce disagreement about the supplied hash pair.
It does not establish that a bundle was historically preserved or that the source
request and response were captured faithfully.

**Long-term audit durability**
The conceptual identifier remains derivable as long as the stored request and
response hash values and the hash algorithm specification are available.

### Boundary

Reconstructibility does not guarantee authenticity or causation. It establishes at
most that the supplied stored hash fields produce the stated commitment. It does
not establish that the model produced the response, that the provider executed a
complete invocation, or that the interaction occurred at a specific time. Those
assurances require independently trusted external mechanisms.

### Why this matters

Most evidence systems are artifact-dependent: if the artifact is lost, the evidence is lost. AELITIUM produces identity-derivable evidence: if the inputs are known, the identity is recoverable. This is the same structural property as Merkle proofs, Git object identity, and content-addressed storage — applied to model interactions.

These properties are emergent consequences of the deterministic evidence model, not protocol requirements.

---

## Cross-institution verifiable evidence anchors

The conceptual model could provide a **cross-institution shared identifier** if
multiple parties possess the same stored request and response hash values and use
the same proposed construction. This is not a current cross-language conformance
claim or proof of a real-world request–response relationship.

This follows directly from deterministic canonicalization, content-addressed identity, and verification determinism.

### Core property

Given two institutions A and B with no shared storage or execution environment: if
both possess the same stored hash pair, both can derive the same conceptual
`binding_hash`. This says nothing about trusted origin or complete invocation
identity.

### Consequences

**Trust decoupling**
Agreement on the conceptual identifier does not require agreement on provider,
transport layer, payment system, or execution environment. Trust in origin,
freshness, and authorization remains separate.

**Neutral reference across boundaries**
Different institutions can reference the same evidence object using the same `binding_hash` without a central registry, shared database, or coordinating authority.

**Dispute minimization**
Disagreements about the conceptual identifier can be reduced to differences in the
supplied stored hash pair. Disputes about source material, execution, or log
history remain outside this model.

**Composability across systems**
Independent agent systems, payment systems, and audit systems can all reference the same `binding_hash` while remaining operationally independent.

### Boundary

This property enables agreement on evidence identity, not agreement on truth of execution. It does not guarantee that the model execution occurred, that the provider is honest, or that the response was generated at a claimed time. Those require external attestations.

### Why this matters

Most interoperability is achieved via shared infrastructure, central authorities, or federated identity. AELITIUM enables a weaker but more scalable primitive: **shared evidence identity without shared trust**. This is a prerequisite for cross-organizational auditing, multi-party workflows, and independent verification ecosystems — without introducing coordination layers.

These properties are emergent consequences of the deterministic evidence model, not protocol requirements.

---

## Layered AI trust stack

The AELITIUM bundle sits as the **evidence primitive** in an emerging trust stack for AI interactions:

```
+---------------------------------------------------+
|                     Agents                        |
|  action receipts, workflow traces                 |
|  evidenceRef → binding_hash                       |
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
|  carries bundle or references binding_hash        |
+------------------------↑--------------------------+
                         |
+------------------------|--------------------------+
|               Payments                            |
|  payment_tx, paid inference records               |
|  references binding_hash                          |
+---------------------------------------------------+
```

Each layer proves something orthogonal:

| Layer | What it proves | What it does not prove |
|-------|---------------|------------------------|
| Payments | A paid inference event occurred | The model output |
| Transport | Message authenticity and integrity in transit | The response semantics |
| **AELITIUM AI v1** | Stored request/response/binding-field consistency | Complete invocation, causation, payment, identity, or execution |
| Agent receipts | A workflow or action occurred | The exact model output |

No layer controls the evidence bundle. Any layer can reference it by `binding_hash`.

---

## Neutrality property

The AELITIUM bundle is neutral between layers because:

- it belongs to no operational layer
- it can be referenced by any layer
- it can be verified independently of all layers
- its identity does not depend on provider, transport, payment, or agent framework

This makes it suitable as the **shared evidence anchor** in multi-layer AI trust stacks.

---

## Relationship to existing standards

| Standard | Relationship |
|----------|-------------|
| SBOM (CycloneDX, SPDX) | Analogous concept applied to AI interactions instead of software components |
| Git commit objects | Similar content-addressed design: `commit_id = sha(content)` |
| IPFS CIDs | Same content-addressability principle |
| Sigstore | Similar trust model; AELITIUM is offline-first and semantics-specific |

The core idea — content-addressed, deterministic, offline-verifiable — is well-established in software infrastructure. AELITIUM applies it to AI interaction evidence.
