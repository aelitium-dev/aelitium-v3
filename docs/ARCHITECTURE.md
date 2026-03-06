# AELITIUM — Architecture

## Overview

AELITIUM provides cryptographic integrity for AI outputs and software releases.
The core pipeline is deterministic, offline, and produces machine-verifiable evidence.

---

## AI Output Integrity Pipeline (P2)

```
AI Output (JSON)
      │
      ▼
┌─────────────────────────────────┐
│  Canonicalization               │
│  json.dumps(sort_keys=True,     │
│    separators=(",",":"),        │
│    ensure_ascii=False)          │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  SHA-256 Hash                   │
│  sha256(canonical_utf8)         │
│  → ai_hash_sha256 (64 hex)      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Evidence Bundle (directory)    │
│  ├── ai_canonical.json          │  deterministic, sorted-key JSON
│  └── ai_manifest.json           │  schema, hash, timestamp, method
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Verification                   │
│  recompute hash from canonical  │
│  compare to manifest            │
│  → STATUS=VALID / INVALID       │
└─────────────────────────────────┘
```

---

## Canonicalization

Determinism requires a stable serialization. AELITIUM uses:

```
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

Properties:
- **Stable across Python versions** — no floating-point tricks, no custom codec
- **Unicode-safe** — `ensure_ascii=False` preserves non-ASCII content faithfully
- **No whitespace** — compact form removes formatting ambiguity

The hash is computed over the UTF-8 bytes of this canonical string.

---

## AI Output Schema (`ai_output_v1`)

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | `"ai_output_v1"` | Identifies the schema |
| `ts_utc` | ISO-8601 string | Generation timestamp |
| `model` | string | Model identifier |
| `prompt` | string | Input prompt |
| `output` | string | Model response |
| `metadata` | object | Arbitrary run metadata |

See `engine/schemas/ai_output_v1.json` for the full JSON Schema.

---

## Evidence Bundle

A pack operation writes two files:

### `ai_canonical.json`
The normalized, sorted-key JSON of the original input.
This is the document that is hashed.

### `ai_manifest.json`
```json
{
  "schema": "ai_pack_manifest_v1",
  "ts_utc": "2026-03-05T10:00:00Z",
  "input_schema": "ai_output_v1",
  "canonicalization": "json_sorted_keys_no_whitespace_utf8",
  "ai_hash_sha256": "<64 hex chars>"
}
```

The manifest records what was hashed and how, making verification fully self-describing.

---

## Verification Protocol

1. Read `ai_canonical.json`
2. Recompute `sha256(canonical_text.rstrip("\n").encode("utf-8"))`
3. Compare to `ai_manifest.json["ai_hash_sha256"]`
4. If equal → `STATUS=VALID rc=0`; otherwise → `STATUS=INVALID rc=2 reason=HASH_MISMATCH`

No network access required. No external state.

---

## Authority Signatures (P3 — in development)

P3 adds an optional Ed25519 signature layer:

```
Evidence Bundle
      │
      ▼
POST /v1/sign  { subject_hash_sha256, subject_type }
      │
      ▼
┌──────────────────────────┐
│  Authority Server        │
│  sign(canonical_receipt, │
│       ed25519_private)   │
└──────────┬───────────────┘
           │
           ▼
     receipt_v1 (JSON)
     { subject_hash, ts_signed, authority_fingerprint,
       authority_signature }
```

Receipts are verifiable offline against the authority's public key:

```bash
aelitium-ai verify-receipt --receipt receipt.json --pubkey authority.b64
# STATUS=VALID rc=0
```

---

## Design Principles

| Principle | Consequence |
|-----------|-------------|
| **Deterministic** | Same input → same hash, on any machine |
| **Offline-first** | Verification never requires network access |
| **Fail-closed** | Any error returns `rc=2`; no silent success |
| **Self-describing** | Manifest records schema, method, and timestamp |
| **Pipeline-friendly** | Output parseable (`STATUS=`, `AI_HASH_SHA256=`, `--json`) |

---

## Module Map

```
engine/
├── ai_cli.py          CLI entry point (validate / canonicalize / pack / verify / verify-receipt)
├── ai_canonical.py    Canonicalization + hash for ai_output_v1
├── ai_pack.py         Pure pack function → AIPackResult
├── canonical.py       Generic canonical JSON helper
├── signing.py         Ed25519 sign/verify (P1 release bundles)
├── pack.py            P1 bundle packing
├── verify.py          P1 bundle verification
├── repro.py           Reproducibility check (two-run determinism)
└── schemas/
    └── ai_output_v1.json   JSON Schema for AI output validation

p3/server/
├── app.py             FastAPI application (/v1/authority, /v1/sign, /v1/verify)
├── models.py          Pydantic request/response models
└── signing.py         Authority key management + receipt signing
```
