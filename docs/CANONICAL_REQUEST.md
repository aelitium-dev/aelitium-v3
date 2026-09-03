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

Its purpose is to let two bundles be compared for the same selected request
identity within the implemented v1 capture model.

If two bundles have the same `request_hash`, they contain the same selected v1
request fields. A different `response_hash` means their selected recorded
response fields differ.

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

**Comparison basis in v0.3.x: `request_hash` v1.**

Historically, v0.3.x `aelitium compare` determines status from the selected v1
request and response hashes. That behavior remains available explicitly in
v0.4.0 with `--legacy-request-hash-v1`.

**Comparison contract in v0.4.0: `aelitium-compare-v1`.** The default
mode first uses validated `aelitium-invocation-v1` hashes when both bundles have
`invocation_identity_consistency=VALID` and
`invocation_binding_consistency=VALID`. Otherwise, valid inputs use a visible
`REQUEST_HASH_V1_FALLBACK` basis. `--require-invocation-evidence` disables that
fallback.

Fallback or legacy output can report:

```
COMPARISON_MODE=INVOCATION_FIRST
COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK
COMPARISON_REASON=RESPONSE_HASH_DIFFERENT
REQUEST_HASH=SAME       ← same selected v1 model and messages
RESPONSE_HASH=DIFFERENT ← different selected recorded response fields
STATUS=CHANGED
```

- Under fallback or legacy basis, `UNCHANGED` means the selected v1
  `request_hash` and selected `response_hash` values match.
- Under fallback or legacy basis, `CHANGED` means the selected v1
  `request_hash` values match and the selected `response_hash` values differ.
- `NOT_COMPARABLE` means the selected comparison identity hashes differ or the
  mode's required evidence is unavailable. Invalid bundles are reported
  separately as `INVALID_BUNDLE` with basis `NONE`.

`request_hash` is not a complete invocation identity. Its equality does not
establish equality of every invocation parameter, mode, provider route, client
configuration, or execution context. `invocation_identity` is a separate,
broader recorded identity when present. Historical v0.3.x comparison does not
use it; the v0.4 default uses it only under the validated evidence prerequisites
above. Equality under that format remains equality only over its selected
recorded fields. Consequently, `CHANGED` does not establish model drift or
causation, and `UNCHANGED` does not establish unchanged invocation configuration
or unchanged model behavior.

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
