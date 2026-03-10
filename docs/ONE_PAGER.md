# AELITIUM — One Pager

## Problem

AI logs are mutable.

When an LLM output influences a real decision — finance, healthcare, legal, compliance — someone eventually asks:

> *"Can you prove what the model actually said?"*

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
canonicalize + hash           ← deterministic, cross-machine stable
    ↓
evidence bundle               ← ai_canonical.json + ai_manifest.json
    ↓
aelitium verify               ← STATUS=VALID / STATUS=INVALID (offline)
```

---

## 3 commands

```bash
pip install aelitium

# Option A: pack a JSON output manually
aelitium pack --input output.json --out ./evidence
aelitium verify --out ./evidence
# STATUS=VALID rc=0
# AI_HASH_SHA256=8b6477...

# Option B: capture directly from OpenAI
from engine.capture.openai import capture_chat_completion
result = capture_chat_completion(client, "gpt-4o", messages, "./evidence")
# result.ai_hash_sha256  →  same hash, every time, any machine
```

Tamper detection:

```bash
# modify the bundle, then verify:
aelitium verify --out ./evidence
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

- `pip install aelitium` — published to PyPI
- OpenAI capture adapter — synchronous, minimal, production-ready happy path
- 100 tests, all passing
- Determinism verified on two independent machines
- Offline verification — no network, no SaaS, no blockchain

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
