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
# Install the current published release (v0.4.0)
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

# Compare validated recorded evidence between two captures
aelitium compare ./evidence_run1 ./evidence_run2
# COMPARISON_CONTRACT=aelitium-compare-v1
# COMPARISON_MODE=INVOCATION_FIRST
# COMPARISON_BASIS=INVOCATION_IDENTITY_V1 or REQUEST_HASH_V1_FALLBACK
```

**Comparison basis in v0.3.x: `request_hash` v1.** `request_hash` is not a
complete invocation identity. Equality does not establish equality of every
invocation parameter, mode, provider route, client configuration, or execution
context. The separate, broader recorded `invocation_identity`, when present, is
not used by historical v0.3.x comparison.

**Comparison contract in v0.4.0: `aelitium-compare-v1`.** The default
uses `INVOCATION_IDENTITY_V1` only when both identity and binding consistency are
`VALID` in both bundles. Otherwise valid inputs visibly use
`REQUEST_HASH_V1_FALLBACK`. `--require-invocation-evidence` disables fallback;
`--legacy-request-hash-v1` selects the v0.3.x decision contract explicitly.
Every result reports its mode, basis, reason, invocation-hash relationship, and
per-side invocation assurance states.

`CHANGED` means selected comparison identity hashes match and selected response
hashes differ under the reported basis; it does not identify a cause.
`UNCHANGED` means those selected hashes match; it does not establish unchanged
invocation configuration or unchanged model behavior. `NOT_COMPARABLE` makes no
response-change conclusion. Equality of validated invocation-identity hashes is
limited to fields selected by that recorded format and does not establish a
complete real-world invocation.

Unsigned and unbound bundles remain valid by default. `--require-signature` and
`--require-binding` reject the corresponding absence. A mathematically valid
signature under key material bundled with the artifact does not establish signer
identity: `trusted_signer_identity` remains `UNESTABLISHED` unless an explicitly
supplied external trust store contains the verified key. In v0.4.0, Freshness is
`NOT_EVALUATED` without an explicit complete policy pair; when activated it
evaluates declared-time recency of
`ai_canonical.json.ts_utc`, not trusted historical time. Authorization is not
implemented and remains `NOT_EVALUATED` in every v0.4.0 case.

Detect an inconsistent edit:

```bash
# modify the bundle, then verify:
aelitium verify-bundle ./evidence
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
```

---

## The eight assurance dimensions

| Dimension | Reachable states in v0.4.0 | Bounded meaning |
|---|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Payload/schema/canonical/manifest/hash consistency |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored v1 request/response/binding field consistency |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored versioned invocation identity consistency; not provider execution |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored invocation-to-response binding consistency; not causation |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Mathematical validity of present Ed25519 material |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | Match against an explicitly supplied external trust store |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | Declared-time recency under an explicit maximum age and reference time |
| `authorization` | `NOT_EVALUATED` only | No authorization decision is implemented in v0.4.0 |

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

AELITIUM establishes internal consistency of recorded evidence on the validated
surface. It does not establish provider execution, causation, full invocation
completeness, model drift, output truth, authorization, or legal compliance.

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

- Current published release: **v0.4.0** on GitHub and **0.4.0** on PyPI
- Current public release surfaces: annotated **v0.4.0** tag, GitHub Release, and
  PyPI publication
- Release process: human-authorized, as documented in
  [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
- Latest PyPI release: **0.4.0**
- Native OpenAI and Anthropic capture adapters, plus LiteLLM capture
- OpenAI streaming capture; Anthropic and LiteLLM capture are synchronous and non-streaming
- Determinism validated on two independent machines in the documented repro flow
- Offline verification — no network, no SaaS, no blockchain
- Released v0.4.0 comparison: versioned invocation-first `compare` contract with visible request-hash fallback, strict mode, and explicit v0.3 legacy mode

---

## What it is not

- Not an observability tool (use Langfuse, Arize, W&B for that)
- Not a blockchain (verification is local and instant)
- Not a compliance product (it is a building block, not a SaaS)

---

## Repo

GitHub: https://github.com/aelitium-dev/aelitium-v3
Install the current published release: `pip install aelitium`
Spec: [docs/EVIDENCE_BUNDLE_SPEC.md](EVIDENCE_BUNDLE_SPEC.md)
