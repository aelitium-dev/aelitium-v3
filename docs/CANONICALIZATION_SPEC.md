# Canonicalization Specification

**Version:** 1.0  
**Status:** Draft, implementation-aligned  
**Current manifest identifier:** `json_sorted_keys_no_whitespace_utf8`

---

## Purpose

This document defines the current canonicalization rules used by AELITIUM
when producing canonical JSON for hashing and verification.

It exists to make the implemented behavior explicit and versionable.

This document describes the current implementation. It does **not** claim:

- RFC 8785 compatibility
- cross-language equivalence beyond matching these exact rules
- stability across future canonicalization changes unless a new version is introduced explicitly

---

## Scope

This specification applies to:

- `engine/canonical.py`
- `engine/ai_canonical.py`
- request, response, and binding hash inputs produced by capture adapters
- bundle verification paths that recompute hashes from canonicalized content

It defines canonicalization of data already represented as Python objects in the
current validated implementation.

---

## Canonicalization Rule

Canonical JSON v1 is the UTF-8 encoding of the string returned by:

```python
json.dumps(
    data,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

The hash input is the resulting string encoded as UTF-8 bytes.

No trailing newline is part of the canonical form.

---

## Deterministic Properties

Within the validated implementation surface, canonicalization v1 has these properties:

- object keys are sorted lexicographically
- no insignificant whitespace is emitted
- arrays preserve input order
- strings are preserved as provided by the Python object
- non-ASCII characters are emitted directly, not ASCII-escaped
- hashing always uses UTF-8 encoding of the canonical string

These properties support deterministic hashing in validated configurations.

---

## Value Semantics

### Objects

- Objects are serialized as JSON objects.
- Keys are sorted recursively by the serializer.
- Key order in the original input does not affect canonical output.

### Arrays

- Arrays preserve their original order.
- Reordering array elements changes the canonical form and resulting hash.

### Strings

- Strings are serialized using Python's JSON escaping rules.
- Whitespace inside strings is significant.
- No trimming, normalization, or semantic cleanup is applied.
- Unicode normalization is **not** performed.

Therefore, visually similar strings may produce different canonical forms and hashes.

### Numbers

- Numbers are serialized using the current Python `json.dumps` behavior.
- Integer and finite floating-point values follow the implementation output of the validated runtime.

Non-finite floating-point values such as `NaN`, `Infinity`, and `-Infinity` are outside the intended interoperable surface of this specification and must not be relied upon for cross-implementation compatibility.

### Null vs missing

- `null` and missing fields are distinct.
- Adding or removing a field changes the canonical form and resulting hash.

### Booleans

- Boolean values serialize using standard JSON tokens.

---

## Hash Construction

The following constructions are used in the current implementation:

### Canonical object hash

```text
sha256_hash = SHA256(UTF8(canonical_json(data)))
```

### Request hash

```text
request_hash = SHA256(UTF8(canonical_json(request_payload)))
```

### Response hash

```text
response_hash = SHA256(UTF8(canonical_json(response_payload)))
```

### Binding hash

```text
binding_hash = SHA256(
  UTF8(
    canonical_json({
      "request_hash": request_hash,
      "response_hash": response_hash
    })
  )
)
```

In the current implementation, the binding object itself is canonicalized using the same rule as all other hashed JSON objects.

---

## Manifest Contract

For canonicalization v1 in the current implementation, manifests emitted by the pack path use:

```json
{
  "canonicalization": "json_sorted_keys_no_whitespace_utf8"
}
```

This identifier is the current version anchor for the implemented canonicalization behavior.

Future canonicalization changes must introduce a new identifier rather than silently changing the semantics of the existing one.

---

## Non-Guarantees

This specification does **not** guarantee:

- semantic equivalence detection
- equivalence across different JSON libraries unless they reproduce the same output bytes
- cross-language compatibility by default
- normalization of Unicode-equivalent strings
- stability across future runtime or serializer changes unless revalidated

It also does not imply that two semantically similar objects will canonicalize to the same bytes.

---

## Conformance

A conforming implementation for canonicalization v1 must:

- produce the same canonical string bytes as the current v1 rule
- hash the UTF-8 bytes of that canonical string using SHA-256
- distinguish `null` from missing
- preserve array order
- sort object keys lexicographically
- avoid adding whitespace outside JSON string values

A conforming verifier must make its decision from:

- the canonicalized content
- the hash algorithm
- the verification inputs present in the bundle

It must not depend on:

- network access
- system time
- external services
- hidden runtime state

---

## Reference Implementation

Current reference files:

- `engine/canonical.py`
- `engine/ai_canonical.py`
- `engine/capture/openai.py`
- `engine/capture/anthropic.py`
- `engine/capture/litellm.py`
- `engine/ai_cli.py`

---

## Versioning Rule

Canonicalization is part of the verification contract.

Therefore:

- canonicalization changes must be explicit
- canonicalization identifiers must be versioned
- older bundles must remain interpretable according to the identifier recorded in their manifest

No future change should redefine the meaning of `json_sorted_keys_no_whitespace_utf8`.
