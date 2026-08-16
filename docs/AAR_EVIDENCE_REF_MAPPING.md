# AELITIUM ↔ AAR `evidenceRef` Mapping

**Status:** Non-normative
**Purpose:** Documentation-only interoperability note between AELITIUM evidence bundles and AAR (Agent Action Receipt)

This mapping does not implement AAR verification or add AAR assurance semantics to
the current AELITIUM runtime.

---

## Overview

AELITIUM and AAR operate at different layers:

- **AELITIUM** → verifies internal consistency of stored v1 evidence fields
- **AAR (conceptual in this repository)** → can represent an agent action and reference supporting evidence

This document defines how an AELITIUM bundle can be referenced from an AAR receipt using the `evidenceRef` field.

---

## Canonical reference

An AELITIUM bundle is referenced using its `binding_hash`.

```json
{
  "evidenceRef": [
    {
      "type": "aelitium/binding-bundle",
      "hash": {
        "alg": "sha256",
        "digest": "<binding_hash>"
      },
      "uri": "optional://location/of/bundle"
    }
  ]
}
```

### Required fields

```
type         = "aelitium/binding-bundle"
hash.alg     = "sha256"
hash.digest  = binding_hash
```

### Optional fields

```
uri = retrieval location (IPFS, HTTPS, local path, etc.)
```

---

## Why `binding_hash`

AELITIUM defines three hashes:

```
request_hash  = sha256(canonical({model, messages}))
response_hash = sha256(canonical({content, model}))
binding_hash  = sha256(canonical({request_hash, response_hash}))
```

Their roles:

| Field | Meaning |
|-------|---------|
| `request_hash` | v1 selected-field request identity |
| `response_hash` | v1 selected-field recorded-response identity |
| `binding_hash` | commitment over the stored request/response hash pair |

For a bound v1 artifact, this mapping uses the binding commitment as its
interoperability reference:

```
bundle_id = binding_hash
```

This is an interop convention for bound artifacts, not proof that a source request
caused a source response. Current AELITIUM verification checks stored-field
consistency and does not independently reconstruct either source artifact.

---

## Minimal example

AAR receipt referencing an AELITIUM bundle:

```json
{
  "agent": "research-crew/analyst",
  "action": "market_scan",
  "inputHash": "sha256:abc...",
  "outputHash": "sha256:def...",
  "evidenceRef": [
    {
      "type": "aelitium/binding-bundle",
      "hash": {
        "alg": "sha256",
        "digest": "sha256:789..."
      },
      "uri": "https://example.com/evidence/789"
    }
  ],
  "signature": "ed25519:..."
}
```

---

## Verification model

### AAR-only verification (conceptual)

An AAR implementation may define independent receipt verification such as:

```
- signature valid
- inputHash / outputHash consistent
```

This repository note does not implement or evaluate that AAR behavior.

### With AELITIUM bundle

If the bundle is available:

```bash
aelitium verify-bundle ./bundle
# STATUS=VALID

aelitium compare bundle_a bundle_b
# REQUEST_HASH=SAME / RESPONSE_HASH=DIFFERENT
```

The AELITIUM commands can provide:

- verification of the recorded v1 bundle's internal consistency
- drift detection across runs
- offline audit without provider access

---

## Layer separation

### AELITIUM does

- define bundle structure
- define hashing and canonicalization
- provide deterministic, offline verification

### AELITIUM does NOT define here

- define receipt schemas
- define AAR signatures or identity semantics
- define transport or storage

---

### AAR does

- define receipt structure
- define signature semantics
- define agent action provenance

### AAR does NOT

- define LLM request/response canonicalization
- define evidence bundle internals

---

## Design principle

```
AELITIUM = evidence primitive
AAR       = receipt layer
```

The integration point is:

```
AAR → references AELITIUM via binding_hash
```

No schema merging is required.

---

## Summary

- `binding_hash` is the canonical identifier of an AELITIUM bundle
- AAR `evidenceRef` can reference it as a typed hash pointer
- Verification remains deterministic, offline, and independent across layers

This enables composability without introducing shared trust or coupling between systems.
