# AELITIUM — One Pager

## Problem

AI logs are mutable.

When an LLM output influences a real decision — finance, healthcare, legal, compliance — someone eventually asks:

> *"Can you prove that the recorded evidence was not modified after packing?"*

Standard logging (databases, S3, observability tools) cannot answer this. An admin with access can edit records. A bucket can be overwritten. A breach can go undetected.

---

## Approach

AELITIUM turns LLM outputs into **tamper-evident evidence bundles**.

The bundle contains a canonical payload, a deterministic SHA-256 hash, and an optional Ed25519 signature. Anyone with the bundle can verify its integrity — no network, no server, no trust in the original infrastructure required.

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

# Option A: capture directly from OpenAI (strongest — trust chain starts at call time)
from engine.capture.openai import capture_chat_completion
result = capture_chat_completion(client, "gpt-4o", messages, "./evidence")
# result.ai_hash_sha256  →  same hash for the same input in validated configurations

# Option B: pack a JSON output manually
aelitium pack --input output.json --out ./evidence

# Verify bundle integrity (offline)
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0 | BINDING_HASH=<hash> | SIGNATURE=NONE

# Detect if model behavior changed between two captures
aelitium compare ./evidence_run1 ./evidence_run2
# STATUS=UNCHANGED rc=0   (same request_hash and response_hash observed)
# STATUS=CHANGED   rc=2   (same request_hash, different response_hash observed)
```

Tamper detection:

```bash
# modify the bundle, then verify:
aelitium verify-bundle ./evidence
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
```

---

## What it proves

| ✅ Proves | ❌ Does not prove |
|-----------|-----------------|
| Bundle has not been altered since packing | Model output was correct or safe |
| Hash matches the canonical payload | Model actually produced the output (without capture layer) |
| (With receipt) Authority signed this hash | Client was not compromised upstream |

---

## Trust boundary

The trust chain starts at **capture time** — when `capture_chat_completion()` intercepts the API call. From that point forward, any alteration is detectable.

Without the capture adapter, the chain starts at **pack time** — when the user runs `aelitium pack`. This is weaker but still useful: it proves the JSON has not changed since packing.

---

## Compliance alignment

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| EU AI Act — Article 12 | Tamper-resistant logs for high-risk AI | Evidence bundles with verifiable hashes |
| SOC 2 — CC7 | Integrity monitoring | Independent offline verification |
| ISO 42001 | AI auditability | Third-party verifiable bundles |

---

## Current state

- `pip install aelitium` — published to PyPI (v0.2.4)
- OpenAI + Anthropic capture adapters — synchronous, minimal, production-ready
- 206 tests passing in the current suite
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
