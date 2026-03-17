# AELITIUM ↔ AAR `evidenceRef` Mapping

**Status:** Non-normative
**Purpose:** Interoperability note between AELITIUM evidence bundles and AAR (Agent Action Receipt)

---

## Overview

AELITIUM and AAR operate at different layers:

- **AELITIUM** → proves the exact **request ↔ response pairing** at the LLM boundary
- **AAR** → proves that an **agent action occurred** and can reference supporting evidence

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
| `request_hash` | identifies the input only |
| `response_hash` | identifies the output only |
| `binding_hash` | identifies the request ↔ response pairing |

The evidence object is the **pairing**, therefore:

```
bundle_id = binding_hash
```

Using `request_hash` or `response_hash` alone would not uniquely identify the interaction.

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

### AAR-only verification

The receipt can be verified independently:

```
- signature valid
- inputHash / outputHash consistent
```

No access to the AELITIUM bundle is required.

### With AELITIUM bundle

If the bundle is available:

```bash
aelitium verify-bundle ./bundle
# STATUS=VALID

aelitium compare bundle_a bundle_b
# REQUEST_HASH=SAME / RESPONSE_HASH=DIFFERENT
```

This enables:

- verification of the exact model output
- drift detection across runs
- offline audit without provider access

---

## Layer separation

### AELITIUM does

- define bundle structure
- define hashing and canonicalization
- provide deterministic, offline verification

### AELITIUM does NOT

- define receipt schemas
- define signatures or identity
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
