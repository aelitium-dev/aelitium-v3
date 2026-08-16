# Canonical Request Format — v1 Selected-Field Identity

**Version:** 1.0
**Status:** Stable

This document defines the selected fields included in the v1 `request_hash`
computed by AELITIUM capture adapters. It does not define a complete provider
invocation identity.

---

## What is the request_hash?

`request_hash` is a SHA-256 hash of the canonical form of the fields selected by
the current v1 capture model.

Its purpose: allow two bundles to be compared and determine whether they came from the same hashed request within the implemented capture model.

If two bundles have the same `request_hash`, the compared bundles contain the same hashed request fields. A different `response_hash` means a different recorded response artifact was observed.

---

## Fields included in request_hash

```json
{
  "messages": [...],
  "model": "gpt-4o"
}
```

| Field      | Type            | Description                             |
|------------|-----------------|-----------------------------------------|
| `messages` | array of objects | The recorded message list selected for v1 identity |
| `model`    | string          | The requested model identifier selected for v1 identity |

These two fields define the frozen v1 request identity. They are not a claim that
all behavior-affecting provider arguments are represented.

---

## Fields excluded from request_hash

| Field | Current v1 treatment |
|---|---|
| `temperature` | Forwarded when supported but excluded from v1 `request_hash` |
| `top_p` | Excluded from v1 `request_hash` |
| `max_tokens` | Forwarded when supported but excluded from v1 `request_hash` |
| `stream` | Excluded from v1 `request_hash` |
| `n` | Excluded from v1 `request_hash` |
| SDK defaults | Excluded from v1 `request_hash` |
| Provider metadata | Excluded from v1 `request_hash` unless represented by a selected field |
| `stop` | Excluded from v1 `request_hash` |

These exclusions are frozen v1 compatibility behavior, not a statement that the
parameters are semantically irrelevant. In particular, behavior-affecting values
can differ while `request_hash` remains the same.

---

## Canonicalization method

Before hashing, the request object is serialized to canonical JSON:

- Keys sorted lexicographically (recursive)
- No insignificant whitespace
- UTF-8 encoding
- No trailing newline

This uses deterministic JSON serialization as implemented in `engine/canonical.py`.

---

## Stability scope

`request_hash` is intended to be stable in validated configurations using the current implementation, including:

- documented Python runtimes in the supported surface
- validated machine/configuration checks recorded in the reproducibility docs

It is **not** stable if:
- The `messages` content changes (including whitespace inside strings)
- The `model` string changes (e.g. `gpt-4o` vs `gpt-4o-2024-11-20`)

---

## Impact on compare

`aelitium compare bundle_a bundle_b` reports:

```
REQUEST_HASH=SAME       ← same model, same messages
RESPONSE_HASH=DIFFERENT ← different recorded response artifact observed
STATUS=CHANGED
INTERPRETATION=Same request_hash with different response_hash observed
```

If `REQUEST_HASH=DIFFERENT`, the selected v1 request identity differs and
comparison is `NOT_COMPARABLE`. Equality or inequality does not establish full
invocation equivalence.

---

## Extending request_hash

If you need to record additional fields (for example `temperature` for a
reproducibility experiment), pass unrelated custom values through the `metadata`
argument. They are stored in the canonical bundle and affect `ai_hash_sha256`, but
they do **not** affect `request_hash`.

```python
result = capture_openai(
    client, model, messages, out_dir="./evidence",
    metadata={"temperature": 0.7}
)
```

Caller metadata cannot overwrite adapter-owned fields. A key collision fails with
`CAPTURE_METADATA_RESERVED_KEY_COLLISION`.

---

## Response hash — field selection and schema drift

`response_hash` is computed from a minimal, stable subset of the provider response:

```python
response_data = {"content": output_text, "model": response.model}
response_hash = sha256_hash(canonical_json(response_data))
```

| Field | Included | Reason |
|-------|----------|--------|
| `content` | ✅ | Recorded response content — core of the selected response identity |
| `model` | ✅ | Provider-confirmed model identifier |
| `id` | ❌ | Response identifier — changes per call, not part of evidence |
| `created` | ❌ | Timestamp — stored separately in metadata |
| `finish_reason` | ❌ | Post-processing signal, not part of output content |
| `usage` | ❌ | Token counts — operational metadata, not evidence |
| `system_fingerprint` | ❌ | Provider-internal, unstable across versions |

**Schema drift rule:** when providers add new response fields, they are excluded from `response_hash` by default. Only fields explicitly listed above are hashed. This is intended to keep `response_hash` stable across validated configurations even when non-hashed provider fields drift.

**Implication:** two recorded responses with identical content and model name will have the same `response_hash`, regardless of when they were generated or what other metadata the provider returned. This is intentional — the hash captures recorded response content, not timing or delivery metadata.

---

## Reference implementation

The capture adapters construct the current v1 request payload equivalently to:

```python
request_payload = {"messages": messages, "model": model}
request_hash = sha256_hash(canonical_json(request_payload))
```
