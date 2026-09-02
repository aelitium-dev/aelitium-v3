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
capture_openai()              ← intercepts at call time
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
# Install the current 0.3.0 release
pip install aelitium
# with provider extras: pip install "aelitium[all]"

# Option A: capture through the native OpenAI adapter
from aelitium import capture_openai
result = capture_openai(client, "gpt-4o", messages, "./evidence")
# result.ai_hash_sha256  →  hash of the complete validated canonical object

# Option B: pack a JSON output manually
aelitium pack --input output.json --out ./evidence

# Verify bundle integrity (offline)
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0 | BINDING_HASH=<hash> | SIGNATURE=NONE

# Compare selected request and response hashes between two captures
aelitium compare ./evidence_run1 ./evidence_run2
# STATUS=UNCHANGED rc=0   (same selected v1 request_hash and selected response_hash)
# STATUS=CHANGED   rc=2   (same selected v1 request_hash, different selected response_hash)
```

**Comparison basis in v0.3.x: `request_hash` v1.** `request_hash` is not a
complete invocation identity. Equality does not establish equality of every
invocation parameter, mode, provider route, client configuration, or execution
context. The separate, broader recorded `invocation_identity`, when present, is
not used by current 0.3.x comparison. `CHANGED` does not by itself establish
model drift or explain causation; `UNCHANGED` does not establish that the full
invocation configuration was unchanged. Different selected v1 request hashes or
missing required `request_hash` capture metadata produce `NOT_COMPARABLE`;
invalid bundles are reported separately as `INVALID_BUNDLE`.

Unsigned and unbound bundles remain valid by default. `--require-signature` and
`--require-binding` reject the corresponding absence. A mathematically valid
signature under key material bundled with the artifact does not establish signer
identity: `trusted_signer_identity` remains `UNESTABLISHED` unless an explicitly
supplied external trust store contains the verified key. In v0.3.0, Freshness is
`NOT_EVALUATED` without an explicit complete policy pair; when activated it
evaluates declared-time recency of
`ai_canonical.json.ts_utc`, not trusted historical time. Authorization is not
implemented and remains `NOT_EVALUATED` in every v0.3.0 case.

Detect an inconsistent edit:

```bash
# modify the bundle, then verify:
aelitium verify-bundle ./evidence
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
```

---

## The eight assurance dimensions

| Dimension | Reachable states in v0.3.0 | Bounded meaning |
|---|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Payload/schema/canonical/manifest/hash consistency |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored v1 request/response/binding field consistency |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored versioned invocation identity consistency; not provider execution |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored invocation-to-response binding consistency; not causation |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Mathematical validity of present Ed25519 material |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | Match against an explicitly supplied external trust store |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | Declared-time recency under an explicit maximum age and reference time |
| `authorization` | `NOT_EVALUATED` only | No authorization decision is implemented in v0.3.0 |

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

## Record and audit workflow alignment

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| EU AI Act — Article 12 | Record-keeping workflows | Project-defined Article 12-oriented mapping of selected evidence fields |
| SOC 2 — CC7 | Integrity monitoring | Independent offline verification |
| ISO 42001 | AI auditability | Offline bundle-consistency checks for third-party review |

These are technical workflow mappings, not an official regulatory format, a
complete real-world record, certification, conformity assessment, or a legal
compliance determination.

---

## Current state

- Current repository/package release: **0.3.0**
- Release surfaces: annotated **v0.3.0** tag, GitHub Release, and PyPI publication
- Release process: human-authorized, as documented in
  [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
- Latest PyPI release: **0.3.0**
- Native OpenAI and Anthropic capture adapters, plus LiteLLM capture
- OpenAI streaming capture; Anthropic and LiteLLM capture are synchronous and non-streaming
- Determinism validated on two independent machines in the documented repro flow
- Offline verification — no network, no SaaS, no blockchain
- `compare` command for selected v1 request/response hash comparison across bundles

---

## What it is not

- Not an observability tool (use Langfuse, Arize, W&B for that)
- Not a blockchain (verification is local and instant)
- Not a compliance product (it is a building block, not a SaaS)

---

## Repo

GitHub: https://github.com/aelitium-dev/aelitium-v3
Install the current release: `pip install aelitium`
Spec: [docs/EVIDENCE_BUNDLE_SPEC.md](EVIDENCE_BUNDLE_SPEC.md)
