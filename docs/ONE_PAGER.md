# AELITIUM — One Pager

## Problem

AI logs are mutable.

When an LLM output influences a real decision — finance, healthcare, legal, compliance — someone eventually asks:

> *"Can you check this record against a separately retained expected hash?"*

Standard logging (databases, S3, observability tools) cannot answer this. An admin with access can edit records. A bucket can be overwritten. A breach can go undetected.

---

## Approach

AELITIUM turns recorded LLM outputs into **governed, internally verifiable
evidence bundles**.

The bundle contains a canonical payload, a deterministic SHA-256 hash, and
optional Ed25519 verification material. Anyone with the bundle can evaluate its
internal consistency without a network or server. Historical non-modification and
signer identity require independently trusted anchors outside the bundle.

```
LLM call
    ↓
capture_chat_completion()     ← intercepts at call time
    ↓
canonicalize + hash           ← deterministic in validated configurations
    ↓
evidence bundle               ← ai_canonical.json + ai_manifest.json
    ↓
aelitium verify               ← STATUS=VALID / STATUS=INVALID (offline)
```

---

## Key commands

```bash
pip install aelitium

# Option A: capture through the native OpenAI adapter
from engine.capture.openai import capture_chat_completion
result = capture_chat_completion(client, "gpt-4o", messages, "./evidence")
# result.ai_hash_sha256  →  hash of the complete validated canonical object

# Option B: pack a JSON output manually
aelitium pack --input output.json --out ./evidence

# Verify bundle integrity (offline)
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0 | BINDING_HASH=<hash> | SIGNATURE=NONE

# Detect if recorded responses differ between two captures
aelitium compare ./evidence_run1 ./evidence_run2
# STATUS=UNCHANGED rc=0   (same request_hash and response_hash observed)
# STATUS=CHANGED   rc=2   (same request_hash, different response_hash observed)
```

Unsigned and unbound bundles remain valid by default. `--require-signature` and
`--require-binding` reject the corresponding absence. A mathematically valid
signature under key material bundled with the artifact does not establish signer
identity: `trusted_signer_identity` remains `UNESTABLISHED`; freshness and
authorization remain `NOT_EVALUATED`.

Detect an inconsistent edit:

```bash
# modify the bundle, then verify:
aelitium verify-bundle ./evidence
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
```

---

## What current verification establishes

| ✅ Establishes | ❌ Does not establish |
|-----------|-----------------|
| Inspected payload and recorded hash are internally consistent | Model output was correct or safe |
| Stored v1 binding fields are consistent when present | Complete provider invocation identity |
| Bundled Ed25519 material is mathematically valid when present | Trusted signer identity, freshness, or authorization |

---

## Trust boundary

The native capture adapters reduce the manual handoff by recording selected v1
request and response fields in the adapter-controlled call path. They do not
establish every behavior-affecting invocation parameter or an externally trusted
origin.

Bundle verification detects changes that are inconsistent with the recorded
contract, hashes, and any present signature material. A fully self-consistent
replacement can still verify unless the verifier has an independently trusted
external anchor or signer identity.

---

## Compliance alignment

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| EU AI Act — Article 12 | Tamper-resistant logs for high-risk AI | Evidence bundles with verifiable hashes |
| SOC 2 — CC7 | Integrity monitoring | Independent offline verification |
| ISO 42001 | AI auditability | Third-party verifiable bundles |

---

## Current state

- Repository/package version: **0.3.0** (current baseline; not yet published to PyPI)
- Last confirmed PyPI publication: **v0.2.4** (historical; unverified in current repository evidence)
- Native OpenAI and Anthropic capture adapters, plus LiteLLM capture
- OpenAI streaming capture; Anthropic and LiteLLM capture are synchronous and non-streaming
- Determinism validated on two independent machines in the documented repro flow
- Offline verification — no network, no SaaS, no blockchain
- `compare` command for detecting changed recorded responses across bundles

---

## What it is not

- Not an observability tool (use Langfuse, Arize, W&B for that)
- Not a blockchain (verification is local and instant)
- Not a compliance product (it is a building block, not a SaaS)

---

## Repo

`pip install aelitium`
GitHub: https://github.com/aelitium-dev/aelitium-v3
Spec: [docs/EVIDENCE_BUNDLE_SPEC.md](EVIDENCE_BUNDLE_SPEC.md)
