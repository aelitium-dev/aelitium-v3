# AELITIUM — Security Model

## What AELITIUM protects against

AELITIUM provides governed **internal-consistency checks** for AI evidence bundles
and supports anchored integrity checks when expected hashes or keys are trusted
independently.

### Threats addressed

| Threat | Protected? | How |
|--------|-----------|-----|
| Bundle content changed without consistently updating governed evidence | ✅ | Schema, canonical-byte, or hash verification fails |
| Payload changed while a separately trusted expected hash is retained | ✅ | Recomputed canonical hash differs from the trusted anchor |
| Manifest hash field altered | ✅ | Detected: recomputed hash won't match |
| Canonical JSON altered | ✅ | Detected: recomputed hash won't match |
| Both files altered consistently | ❌ | See "Limitations" below |
| Replay of an older valid bundle | ❌ | See "Limitations" below |

---

## What AELITIUM does not protect against

AELITIUM provides **no protection** for:

- **Pre-generation attacks**: if the model or prompt is compromised before the output is generated, AELITIUM cannot detect this
- **Collusion**: if an attacker controls both the evidence bundle and the stored hash, they can replace both consistently
- **Model quality**: AELITIUM evaluates evidence consistency, not whether output content is correct or safe
- **Key compromise (P3)**: if the Ed25519 authority private key is leaked, signatures lose their trust property

---

## Threat model

### Integrity (P2 — hash-only)

The hash in `ai_manifest.json` is `sha256(canonical_json)`.

**Assumption**: the stored `ai_hash_sha256` is trusted (e.g., stored in a separate append-only DB, or held by the auditor).

**Guarantee**: given a trusted hash, anyone can verify that `ai_canonical.json` has not been modified.

**Limitation**: if an attacker controls the evidence bundle *and* the stored hash, they can substitute a different valid bundle. Mitigation: store hashes in a system the attacker cannot modify (separate DB, immutable log, receipt from P3 authority).

### Signature layers

Current AI bundles can include Ed25519 signature material in
`verification_keys.json`. Verification establishes mathematical signature
validity under the bundled public key alone; a bundled key is not itself a
trust anchor. By default `trusted_signer_identity` remains `UNESTABLISHED`.

A caller can explicitly supply a local trust store (`--trust-store PATH`) —
a strict `aelitium-trust-v1` JSON file containing trusted Ed25519 public-key
material, independent of the inspected bundle. Each record stores the raw
public key (and an optional, non-authoritative label); the verifier derives
the fingerprint itself, `ed25519:sha256:<64 lowercase hex>`, from the decoded
key bytes — no fingerprint field is stored in the file. Supplying a trust
store alone is sufficient for evaluation: `trusted_signer_identity` becomes
`VALID` only if the verified signing key's derived fingerprint matches a
trust-store entry's derived fingerprint; otherwise it stays `UNESTABLISHED`,
and the bundle still verifies normally. A bundle cannot pass verification
under `--require-trusted-signer` without that match, and cannot pass at all
under that flag without a trust store being supplied
(`TRUST_INPUT_NOT_PROVIDED`) — that flag turns evaluation into an
enforced requirement. See TRUST_BOUNDARY.md for the full contract
and failure-reason vocabulary.

Unsigned bundles remain valid by default. `--require-signature` lets a caller make
absence invalid for a particular verification context. Signature verification does
not evaluate freshness or authorization.

### Authority signatures (P3 — in development)

P3 adds an Ed25519 signature from an authority server.

**Guarantee**: a valid receipt proves that the authority saw the hash at a specific time, and signed it. This makes substitution attacks detectable even if the bundle is replaced.

**Assumption**: the authority's private key is secure and the authority's public key is independently distributed.

---

## Cryptographic primitives

| Primitive | Usage | Library |
|-----------|-------|---------|
| SHA-256 | Content hashing | Python `hashlib` (stdlib) |
| Ed25519 | Bundled operator signatures and authority signatures | `cryptography` ≥ 41 |
| JSON canonicalization | Deterministic serialization | Python `json` (stdlib) |

No custom cryptography. No novel constructions.

---

## Dependency surface

Runtime dependencies:

```
cryptography >= 41    # Ed25519 signature support
jsonschema >= 4.18    # ai_output_v1 validation during pack and verify
```

Current AI pack and verify paths use `jsonschema` to enforce `ai_output_v1`.
Signature verification additionally uses `cryptography` when signature material is
present.

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

Unrelated custom metadata is accepted. If caller metadata collides with a key in
the adapter-owned base metadata for that invocation, capture fails with
`CAPTURE_METADATA_RESERVED_KEY_COLLISION`.

Metadata is preserved in the bundle and included in `ai_canonical.json`, but excluded from `request_hash`. Deletion of the bundle removes all associated metadata.

**Minimum viable bundle (privacy-first):**

If the output itself is sensitive and you only need drift detection signals (not content archival), you can store the hashes extracted from the written bundle and then delete the bundle:

```python
# Store hashes derived from the bundle; delete the bundle file
result = capture_openai(client, model, messages, out_dir=tmp_dir)
manifest = json.loads((result.bundle_dir / "ai_manifest.json").read_text(encoding="utf-8"))
bundle = json.loads((result.bundle_dir / "ai_canonical.json").read_text(encoding="utf-8"))
db.store(
    request_hash=bundle["metadata"]["request_hash"],
    response_hash=bundle["metadata"]["response_hash"],
)
shutil.rmtree(tmp_dir)
```

The `request_hash` and `response_hash` are pseudonymous (SHA-256 of content) — without the original payload, they cannot be used to reconstruct the prompt or response.

---

## Responsible disclosure

Security issues should be reported privately to `secure@aelitium.com`.

See [SECURITY.md](../SECURITY.md) for the full policy.
