# 📜 AELITIUM v3 — ENGINE CONTRACT

## 1. Nature

AELITIUM v3 is a **deterministic evidence engine**.

It performs:

```text
Input → Normalization → Manifest → Evidence Pack → Verification Material
```

No network.
No time dependency.
No hidden state.

---

# 2. CLI Interface (Official v3 Surface)

O engine expõe **3 comandos apenas**:

---

## 🔹 2.1 `aelitium pack`

### Purpose

Generate deterministic evidence artifacts from validated input.

### Syntax

```bash
aelitium pack --input input.json --out ./output/
```

### Behavior

1. Validate schema version (`input_v1`)
2. Normalize input (canonical JSON — sorted keys, no whitespace, UTF-8)
3. Compute SHA256 of normalized payload
4. Sign `manifest.json` bytes with Ed25519 key (loaded from env var)
5. Generate:

   * `manifest.json` — includes `bundle_schema: "1.1"`, input hash, canonicalization spec
   * `evidence_pack.json` — canonical payload + hash
   * `verification_keys.json` — `keyring_format: "ed25519-v1"`, public key, signature

### Signing (required)

`pack` requires a signing key at runtime:

```bash
export AEL_ED25519_PRIVKEY_B64=<base64-encoded 32-byte Ed25519 seed>
# or
export AEL_ED25519_PRIVKEY_PATH=/path/to/key.b64
# optional
export AEL_ED25519_KEY_ID=my-key-id
```

### Determinism Rule

Running twice with same input and same key MUST produce identical hashes.
(Signature bytes vary per run — only hash fields are determinism-checked.)

---

## 🔹 2.2 `aelitium verify`

### Purpose

Verify integrity and authenticity offline.

### Syntax

```bash
aelitium verify-bundle <dir>
```

### Behavior

1. Enforce `manifest.json` and `evidence_pack.json` are in the same directory
2. Enforce `bundle_schema: "1.1"` in manifest
3. Recompute SHA256 of `canonical_payload` — must match `manifest.input_hash` and `evidence.hash`
4. Validate Ed25519 signature of `manifest.json` bytes using public key in `verification_keys.json`
5. Enforce `verification_keys.json` present with `keyring_format: "ed25519-v1"`, 1 key, 1 signature

### Exit Codes

| Code | Meaning               |
| ---- | --------------------- |
| 0    | VALID                 |
| 2    | INVALID (fail-closed) |

No partial success.

---

## 🔹 2.3 `aelitium repro`

### Purpose

Test reproducibility (2-run determinism test).

### Syntax

```bash
aelitium repro --input input.json
```

### Behavior

* Run pack twice
* Compare manifest hashes
* Compare evidence hashes

If mismatch → INVALID (rc=2)

---

# 3. Invariants

The engine MUST:

* Reject placeholders
* Reject missing fields
* Reject schema mismatch
* Reject non-canonical JSON
* Reject environment entropy
* Never depend on system clock
* Never depend on external APIs

---

# 4. Deterministic Boundary

The deterministic boundary includes:

* Canonical JSON encoding
* Stable key ordering
* Fixed hash algorithm (SHA256)
* Defined encoding (UTF-8)

Any deviation → INVALID.

---

# 5. Governance Binding

A release is valid only if:

* `aelitium repro` passes
* `aelitium verify` passes
* All artifacts are committed in Git
* Version tag exists

No exceptions.

---

# 6. Product Definition

AELITIUM v3 product =

> Deterministic Evidence Pack + Offline Verifier

Not a platform.
Not a SaaS.
Not an API-first system.

It is a proof machine.