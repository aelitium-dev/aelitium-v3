# AELITIUM — Security Model

## What AELITIUM protects against

AELITIUM provides **integrity guarantees** for AI outputs and release artifacts.

### Threats addressed

| Threat | Protected? | How |
|--------|-----------|-----|
| AI output tampered after generation | ✅ | SHA-256 hash mismatch detected on verify |
| Log entry modified in storage | ✅ | Canonical JSON + hash is independent of storage |
| Manifest hash field altered | ✅ | Detected: recomputed hash won't match |
| Canonical JSON altered | ✅ | Detected: recomputed hash won't match |
| Both files altered consistently | ❌ | See "Limitations" below |
| Replay of an older valid bundle | ❌ | See "Limitations" below |

---

## What AELITIUM does not protect against

AELITIUM provides **no protection** for:

- **Pre-generation attacks**: if the model or prompt is compromised before the output is generated, AELITIUM cannot detect this
- **Collusion**: if an attacker controls both the evidence bundle and the stored hash, they can replace both consistently
- **Model quality**: AELITIUM proves the output wasn't changed, not that it was correct or safe
- **Key compromise (P3)**: if the Ed25519 authority private key is leaked, signatures lose their trust property

---

## Threat model

### Integrity (P2 — hash-only)

The hash in `ai_manifest.json` is `sha256(canonical_json)`.

**Assumption**: the stored `ai_hash_sha256` is trusted (e.g., stored in a separate append-only DB, or held by the auditor).

**Guarantee**: given a trusted hash, anyone can verify that `ai_canonical.json` has not been modified.

**Limitation**: if an attacker controls the evidence bundle *and* the stored hash, they can substitute a different valid bundle. Mitigation: store hashes in a system the attacker cannot modify (separate DB, immutable log, receipt from P3 authority).

### Authority signatures (P3 — in development)

P3 adds an Ed25519 signature from an authority server.

**Guarantee**: a valid receipt proves that the authority saw the hash at a specific time, and signed it. This makes substitution attacks detectable even if the bundle is replaced.

**Assumption**: the authority's private key is secure and the authority's public key is independently distributed.

---

## Cryptographic primitives

| Primitive | Usage | Library |
|-----------|-------|---------|
| SHA-256 | Content hashing | Python `hashlib` (stdlib) |
| Ed25519 | Authority signatures (P3) | `cryptography` ≥ 41 |
| JSON canonicalization | Deterministic serialization | Python `json` (stdlib) |

No custom cryptography. No novel constructions.

---

## Dependency surface

Runtime dependencies:

```
cryptography >= 41    # Ed25519 (P3 only; P2 requires only stdlib)
jsonschema >= 4.18    # Schema validation (validate subcommand)
```

P2 (pack + verify) requires only Python stdlib (`json`, `hashlib`, `pathlib`).

---

## Privacy and PII

Evidence bundles contain a verbatim copy of the AI output payload. If the prompt or response contains personal data, the bundle contains personal data.

**AELITIUM does not:**
- Inspect, filter, or redact payload content
- Log payloads to any external service
- Transmit bundle contents anywhere (all operations are local)

**Operator responsibilities:**

| Concern | Guidance |
|---------|---------|
| Bundles stored on disk | Apply filesystem-level access controls; treat bundle directories as you would application logs |
| Bundles containing personal data | GDPR / CCPA: bundles are data records — deletion requests may require deleting the bundle file. The hash stored separately becomes orphaned and can be deleted alongside it |
| Long-term archival | Consider whether the `output` field of the payload needs to be archived, or whether storing the hash reference alone is sufficient for your audit requirements |
| P3 receipts (external signing) | The authority receives only the `ai_hash_sha256` — the payload is never transmitted. Receipt signing is hash-only |

**Using the `metadata` field for PII control:**

If you need to store PII-adjacent context (e.g., a user session ID for correlation) without embedding it in the content hash, store it in the `metadata` field:

```python
result = capture_openai(
    client, model, messages, out_dir="./evidence",
    metadata={"session_id": session_id}  # stored in bundle, not in request_hash
)
```

Metadata is preserved in the bundle and included in `ai_canonical.json`, but excluded from `request_hash`. Deletion of the bundle removes all associated metadata.

**Minimum viable bundle (privacy-first):**

If the output itself is sensitive and you only need drift detection (not content archival), you can store only the hashes:

```python
# Store hashes in your DB; delete the bundle file
result = capture_openai(client, model, messages, out_dir=tmp_dir)
db.store(request_hash=result.request_hash, response_hash=result.response_hash)
shutil.rmtree(tmp_dir)
```

The `request_hash` and `response_hash` are pseudonymous (SHA-256 of content) — without the original payload, they cannot be used to reconstruct the prompt or response.

---

## Responsible disclosure

Security issues should be reported privately to `secure@aelitium.com`.

See [SECURITY.md](../SECURITY.md) for the full policy.
