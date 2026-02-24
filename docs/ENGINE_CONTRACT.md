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

1. Validate schema version
2. Normalize input (canonical JSON)
3. Compute SHA256 of normalized payload
4. Generate:

   * `manifest.json`
   * `evidence_pack.json`
   * `verification_keys.json` (public material only)

### Determinism Rule

Running twice with same input MUST produce identical hashes.

---

## 🔹 2.2 `aelitium verify`

### Purpose

Verify integrity and authenticity offline.

### Syntax

```bash
aelitium verify --manifest manifest.json --evidence evidence_pack.json
```

### Behavior

* Recompute hashes
* Validate signatures
* Validate schema version
* Confirm structural invariants

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