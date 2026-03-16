# AELITIUM — Evidence Model

**Status:** Non-normative
**See also:** [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) (normative), [Trust Boundary](TRUST_BOUNDARY.md)

This document describes the conceptual model behind the AELITIUM evidence bundle — what it represents, its emergent properties, and how it sits within a layered AI trust stack.

These are architectural observations, not protocol requirements.

---

## What an evidence bundle represents

An AELITIUM bundle is a **content-addressed record of an LLM interaction boundary**.

It records exactly one thing:

> This canonical request produced this canonical response.

Nothing else. The bundle does not represent:

- that the model was correct or safe
- that the interaction was authorized or paid for
- that the agent that initiated the call was honest
- that the system that packed the bundle was trustworthy

Those properties belong to other layers.

---

## Content-addressability

Because bundle identity is defined as:

```
bundle_id = binding_hash = sha256(canonical({request_hash, response_hash}))
```

and `binding_hash` is derived deterministically from the canonical request and canonical response, an AELITIUM bundle is **content-addressed**.

This leads to several emergent properties:

**Reproducible identity**
Independent systems capturing the same LLM interaction produce the same `binding_hash` without coordination. Two captures of the same request+response are the same evidence object.

**Natural deduplication**
Bundles can be deduplicated by `binding_hash` without a central registry. If two bundles share a `binding_hash`, they are the same evidence object.

**Offline reconstructibility**
Given the original request and response, any party can derive the `binding_hash` offline and compare it against a stored identifier. Evidence identity does not require the original bundle file.

These are consequences of the evidence model — not protocol requirements. Implementations are not required to implement caching or deduplication.

---

## Reconstructible evidence

An AELITIUM evidence object is **reconstructible**: its identifier (`binding_hash`) can be recomputed from the canonical request and canonical response without access to the original bundle.

```
binding_hash = sha256(canonical({
  "request_hash": sha256(canonical_request),
  "response_hash": sha256(canonical_response)
}))
```

Any party possessing the canonical inputs can independently reconstruct the evidence identity. The original bundle file is not required.

### Consequences

**Independent verification**
An auditor can verify an interaction using only `canonical_request`, `canonical_response`, and this specification. Verification remains possible even if the capture system is unavailable, bundle storage is lost, or evidence was transmitted as hashes only.

**Third-party reproducibility**
Independent systems capturing the same model interaction derive the same `binding_hash` without coordination:

```
system A capture → binding_hash X
system B capture → binding_hash X
```

This enables cross-system evidence correlation without a shared registry.

**Reduced trust requirements**
Traditional logging systems require trusting the party that produced the log artifact. With reconstructible evidence, trust shifts from the log producer to the deterministic reconstruction. An auditor does not need to trust that a bundle was faithfully preserved if the canonical inputs are available.

**Long-term audit durability**
Evidence identity remains derivable as long as `canonical_request`, `canonical_response`, and the hash algorithm specification are available — independent of proprietary logging systems, provider APIs, or specific storage formats.

### Boundary

Reconstructibility does not guarantee authenticity. It proves only that this response corresponds to this request. It does not prove that the model actually produced the response, that the provider executed the request, or that the interaction occurred at a specific time. Those assurances require external attestations — signatures, receipts, or transport proofs.

### Why this matters

Most evidence systems are artifact-dependent: if the artifact is lost, the evidence is lost. AELITIUM produces identity-derivable evidence: if the inputs are known, the identity is recoverable. This is the same structural property as Merkle proofs, Git object identity, and content-addressed storage — applied to model interactions.

These properties are emergent consequences of the deterministic evidence model, not protocol requirements.

---

## Cross-institution verifiable evidence anchors

An AELITIUM evidence bundle acts as a **cross-institution verifiable anchor** if multiple independent parties can derive the same `binding_hash`, verify the same request–response relationship, and reach the same verification result — without requiring mutual trust or shared infrastructure.

This follows directly from deterministic canonicalization, content-addressed identity, and verification determinism.

### Core property

Given two institutions A and B with no shared trust, no shared storage, and no shared execution environment: if both possess `canonical_request` and `canonical_response`, both independently derive the same `binding_hash` and the same verification result. No coordination is required.

### Consequences

**Trust decoupling**
Agreement on evidence identity does not require agreement on provider, transport layer, payment system, or execution environment. Evidence verification is decoupled from institutional trust relationships.

**Neutral reference across boundaries**
Different institutions can reference the same evidence object using the same `binding_hash` without a central registry, shared database, or coordinating authority.

**Dispute minimization**
Disagreements can be reduced to `canonical_request` or `canonical_response` mismatches — rather than disputes over log integrity, provider logs, or transport records. The dispute surface narrows to deterministic inputs.

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
| **AELITIUM** | Request ↔ response binding | Payment, identity, or execution |
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
