# Canonical Request Format

**Version:** 1.0
**Status:** Stable

This document defines what fields are included in the `request_hash` computed by AELITIUM capture adapters, and why.

---

## What is the request_hash?

`request_hash` is a SHA-256 hash of the canonical form of the LLM request.

Its purpose: allow two bundles to be compared and determine whether they came from **the same logical request** — regardless of when, where, or with which SDK version the call was made.

If two bundles have the same `request_hash`, any difference in `response_hash` is attributable to the model, not the caller.

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
| `messages` | array of objects | The exact message list sent to the API |
| `model`    | string          | The model identifier as sent            |

These are the only two fields that define **what was asked** and **who was asked**.

---

## Fields excluded from request_hash

| Field         | Reason excluded                                               |
|---------------|---------------------------------------------------------------|
| `temperature` | Sampling parameter — affects randomness, not the request itself |
| `top_p`       | Same as temperature                                           |
| `max_tokens`  | Output budget — doesn't change what was asked                |
| `stream`      | Transport detail, not part of the request semantics           |
| `n`           | Number of completions — not part of the single request        |
| SDK defaults  | Vary across SDK versions; would break hash stability          |
| Provider metadata | Added by the SDK, not by the caller                      |
| `stop`        | Post-processing hint, not part of the request intent          |

**Rule:** if the field controls *how* the model answers but not *what* it was asked, it is excluded.

---

## Canonicalization method

Before hashing, the request object is serialized to canonical JSON:

- Keys sorted lexicographically (recursive)
- No insignificant whitespace
- UTF-8 encoding
- No trailing newline

This matches RFC 8785 (JSON Canonicalization Scheme) and is implemented in `engine/canonical.py`.

---

## Stability guarantee

`request_hash` is stable across:

- Python versions (3.10+)
- Operating systems
- OpenAI SDK versions
- Machines A and B (validated)

It is **not** stable if:
- The `messages` content changes (including whitespace inside strings)
- The `model` string changes (e.g. `gpt-4o` vs `gpt-4o-2024-11-20`)

---

## Impact on compare

`aelitium compare bundle_a bundle_b` reports:

```
REQUEST_HASH=SAME       ← same model, same messages
RESPONSE_HASH=DIFFERENT ← model returned something different
STATUS=CHANGED
INTERPRETATION=Same request produced a different response
```

If `REQUEST_HASH=DIFFERENT`, the requests are not equivalent and comparison is `NOT_COMPARABLE`.

---

## Extending request_hash

If you need to include additional fields (e.g. `temperature` for reproducibility experiments), pass them via the `metadata` argument to the capture adapter. They will be stored in the bundle but will **not** affect `request_hash`.

```python
result = capture_openai(
    client, model, messages, out_dir="./evidence",
    metadata={"temperature": 0.7}
)
```

---

## Reference implementation

`engine/capture/openai.py`, line 107:

```python
request_payload = {"messages": messages, "model": model}
request_hash = sha256_hash(canonical_json(request_payload))
```
