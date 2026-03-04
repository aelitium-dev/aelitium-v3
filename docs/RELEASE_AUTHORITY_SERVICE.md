# Release Authority as a Service — P3 Architecture v0

> Instead of running your own Machine B, you delegate the authority role to AELITIUM.
> Your team packs locally. AELITIUM signs. Anyone can verify offline.

---

## The problem this solves

P1 and P2 require a trusted "Machine B" — an offline authority that signs releases and AI evidence bundles. Setting up and operating that authority is friction for most teams. P3 removes that friction: AELITIUM runs Machine B as a service.

---

## Core model

```
Client (your pipeline)         AELITIUM Authority         Auditor (any machine)
        |                             |                           |
        |  POST /v1/sign              |                           |
        |  { bundle or pack }  -----> |                           |
        |                             |  verify integrity         |
        |                             |  sign with authority key  |
        |  <---- receipt (signed) --- |                           |
        |                             |                           |
        |  store receipt + artifacts  |                           |
                                                                  |
                                      GET /v1/receipt/{id}  ----> |
                                      or offline: verify locally  |
```

**Key properties:**
- Client never gives AELITIUM the raw prompt/output (only the hash + manifest)
- Authority never stores your data — only the receipt
- Verification always works offline (no call-home required)

---

## API (minimum viable)

### `POST /v1/sign`

Submit a pack manifest for signing.

**Request:**
```json
{
  "schema": "sign_request_v1",
  "manifest": {
    "schema": "ai_pack_manifest_v1",
    "ts_utc": "2026-03-04T12:00:00Z",
    "input_schema": "ai_output_v1",
    "canonicalization": "json_sorted_keys_no_whitespace_utf8",
    "ai_hash_sha256": "3a7f9c..."
  },
  "client_id": "org-xyz"
}
```

**Response:**
```json
{
  "schema": "receipt_v1",
  "receipt_id": "rec-20260304-001",
  "ts_signed_utc": "2026-03-04T12:00:05Z",
  "ai_hash_sha256": "3a7f9c...",
  "authority_fingerprint": "SHA256:abc...",
  "authority_signature": "<base64 Ed25519 sig over canonical receipt JSON>"
}
```

**Rules:**
- `ai_hash_sha256` must be 64 hex chars
- Authority signs the canonical JSON of the receipt (same canonicalization as P1/P2)
- Receipt is returned immediately; authority does not store it (client responsibility)

---

### `POST /v1/verify`

Verify that a receipt is valid (authority signature check). Useful for teams without local key setup.

**Request:**
```json
{
  "receipt": { ... receipt_v1 object ... },
  "ai_hash_sha256": "3a7f9c..."
}
```

**Response:**
```json
{
  "status": "VALID",
  "rc": 0,
  "authority_fingerprint": "SHA256:abc..."
}
```

or:

```json
{
  "status": "INVALID",
  "rc": 2,
  "reason": "SIGNATURE_MISMATCH"
}
```

---

### `GET /v1/receipt/{receipt_id}`

Retrieve a receipt by ID (if authority opts to store them — optional feature).

---

### `GET /v1/authority`

Returns the current authority public key and fingerprint.

```json
{
  "schema": "authority_v1",
  "public_key_b64": "<base64 Ed25519 pubkey>",
  "fingerprint": "SHA256:abc...",
  "valid_from": "2026-01-01T00:00:00Z"
}
```

Used for offline verification setup (download once, verify forever).

---

## Receipt format (`receipt_v1`)

```
receipt_v1
├── schema          = "receipt_v1"
├── receipt_id      = "rec-<date>-<nonce>"
├── ts_signed_utc   = ISO-8601 UTC
├── ai_hash_sha256  = 64 hex (the hash being attested)
├── authority_fingerprint = "SHA256:<pubkey digest>"
└── authority_signature   = base64(Ed25519.sign(canonical_receipt_json_without_sig))
```

Canonical receipt = `receipt_v1` object with `authority_signature` field set to `""`, serialized with AELITIUM canonical JSON (sorted keys, no whitespace).

---

## Offline verification flow

```bash
# 1. Download authority public key once
curl https://authority.aelitium.dev/v1/authority > authority.json

# 2. Later, verify any receipt locally
aelitium verify-receipt --receipt receipt.json --pubkey authority.json --hash 3a7f9c...
# STATUS=VALID rc=0
```

No network required after step 1.

---

## Threat model

| Threat | Protected? | How |
|--------|-----------|-----|
| Output tampered after signing | ✅ | hash mismatch on verify |
| Receipt forged | ✅ | Ed25519 signature over receipt |
| Replay (old receipt on new output) | ✅ | hash in receipt must match output hash |
| Authority key compromise | ⚠️ | key rotation + old receipts remain valid for their era |
| Client sends wrong hash | ❌ (by design) | AELITIUM signs what client submits — GIGO |
| AELITIUM downtime | ❌ | signing requires network; verification does not |

---

## Multi-tenant

- API key per organisation (`client_id`)
- Rate limiting per client
- `receipt_id` namespace is per-client
- Authority key is shared (single root of trust) — no per-client keys in v1

---

## What P3 is NOT (scope boundary)

- Not a bundle storage service (P3 only signs hashes)
- Not a content inspection service (never sees your data)
- Not a replacement for P1/P2 (builds on top of them)

---

## Implementation roadmap

| Phase | Scope |
|-------|-------|
| v0.1 | `/v1/sign` + `/v1/authority` endpoints, Ed25519 signing, receipt_v1 |
| v0.2 | `/v1/verify`, CLI `aelitium verify-receipt` |
| v0.3 | API keys + client_id, rate limiting |
| v1.0 | Audit log, receipt storage (optional), key rotation |

---

## Stack (proposed, minimal)

- Python + FastAPI (consistent with existing engine)
- Ed25519 via `cryptography` (already a dependency)
- No database in v0.1 — stateless signing
- Deployed as single process (no K8s required for MVP)
