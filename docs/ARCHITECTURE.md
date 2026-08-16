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
- **Intended to be stable in validated configurations** — no custom codec or external serializer dependency
- **Unicode-safe** — `ensure_ascii=False` preserves non-ASCII content faithfully
- **No whitespace** — compact form removes formatting ambiguity

The hash is computed over the UTF-8 bytes of this canonical string.

---

## AI Output Schema (`ai_output_v1`)

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | `"ai_output_v1"` | Identifies the schema |
| `ts_utc` | ISO-8601 string | Recorded timestamp; freshness is not evaluated |
| `model` | string | Model identifier |
| `prompt` | string | Input prompt |
| `output` | string | Recorded response content |
| `metadata` | object | Metadata accepted by the schema; capture adapters reserve their owned fields |

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

For the current AI evidence bundle v1 surface, verification:

1. parses `ai_canonical.json` and validates the authoritative `ai_output_v1` schema
2. enforces manifest schema, input-schema, and canonicalization identifiers
3. requires governed SHA-256 fields to be lowercase 64-character hexadecimal strings
4. independently reconstructs canonical JSON with the governed serializer
5. accepts stored canonical bytes only when they equal that serialization exactly,
   optionally followed by one terminal LF
6. hashes the canonical serialization without the optional LF and compares it to
   `ai_manifest.json["ai_hash_sha256"]`
7. evaluates stored v1 binding fields and bundled signature material when present

No network access is required. The result distinguishes payload integrity,
binding-field consistency, signature validity, signer identity, freshness, and
authorization.

Unsigned and unbound bundles remain valid by default. Callers can require those
dimensions with `--require-signature` and `--require-binding`.

### Bundled signature material

A valid Ed25519 signature establishes mathematical validity under the public key
packaged with the artifact. It does not establish an externally trusted signer
identity: `trusted_signer_identity` remains `UNESTABLISHED`. Freshness and
authorization remain `NOT_EVALUATED`.

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
aelitium verify-receipt --receipt receipt.json --pubkey authority.b64
# STATUS=VALID rc=0
```

---

## Design Principles

| Principle | Consequence |
|-----------|-------------|
| **Deterministic** | Same complete validated input object → same hash in validated configurations |
| **Offline-first** | Verification never requires network access |
| **Fail-closed** | Any error returns `rc=2`; no silent success |
| **Self-describing** | Manifest records schema, method, and timestamp |
| **Pipeline-friendly** | Key/value output is parseable; supported successful command paths also offer `--json` |

---

## Module Map

```
engine/
├── ai_cli.py          CLI entry point for the AI evidence surface
├── ai_contract.py     Current AI evidence filenames and contract identifiers
├── ai_canonical.py    ai_output_v1 validation, canonicalization, and hash
├── ai_pack.py         Pure pack function → AIPackResult
├── ai_verify.py       Canonical AI bundle verification kernel
├── canonical.py       Generic canonical JSON helper
├── signing.py         Ed25519 sign/verify support
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
