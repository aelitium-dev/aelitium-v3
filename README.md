# AELITIUM

> Git-style verification for LLM outputs.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

> AELITIUM is a library/CLI for producing and verifying internally consistent,
> offline-verifiable evidence bundles for recorded LLM interactions under
> deterministic canonicalization.

LLM outputs can change silently. AELITIUM currently enforces fail-closed
verification semantics on the validated surface and checks the internal consistency
of recorded AI evidence under the v1 schema and canonicalization contract.

## Demo

[![asciicast](https://asciinema.org/a/OFLJN0nM5QDk2acz.svg)](https://asciinema.org/a/OFLJN0nM5QDk2acz)

## Quickstart

Find uncaptured LLM call sites:

```bash
aelitium scan .
```

Capture evidence:

```python
from aelitium import enable_litellm
enable_litellm()
```

Verify a bundle offline:

```bash
aelitium verify-bundle ./bundle
```

## What current v1 verification establishes

- Stored v1 request and response hashes can be joined by a deterministic binding commitment
- Modifications inconsistent with the bundle's recorded contract and hashes are detectable
- Verification can be performed offline on the validated surface

## What it does not establish

- That the model actually executed
- That the provider was honest
- That the response is correct or truthful
- That capture was complete
- Complete provider invocation identity
- Trusted signer identity, freshness, or authorization
- That semantic equivalence implies hash equivalence

---

## The problem

You run the same prompt in production. One week later, the output is different.

The recorded response changed — but your logs just show two JSON blobs. It is hard
to check their schema and hash consistency against a separately retained expected
record.

---

## Try it offline

```bash
git clone https://github.com/aelitium-dev/aelitium-v3
cd aelitium-v3 && pip install -e .
bash examples/drift_demo/run_demo.sh  # no API key required
```

Same request hash. Different recorded response hash. That means the recorded response changed for the compared bundles.

```bash
# Scan your codebase for unprotected LLM calls:
aelitium scan ./src
# LLM call sites detected: 4
# Missing evidence capture:
#   ⚠ openai — worker.py:42
#   ⚠ anthropic — agent.py:17
# Coverage: 2/4 (50%)
# STATUS=INCOMPLETE rc=2
```

Commands expose parseable key/value output, and supported successful command paths
offer `--json`. Successful `verify` and `verify-bundle` calls emit JSON when
requested; invalid results currently retain key/value compatibility output. The
standalone verifier emits JSON for invalid verification results.

---

## How it works

```
API call (OpenAI / Anthropic / LiteLLM)
      ↓
capture adapter   ← records request_hash + response_hash in-process
      ↓
evidence bundle   ← canonical JSON + ai_manifest.json + binding_hash
      ↓
aelitium verify-bundle   ← STATUS=VALID / STATUS=INVALID
aelitium compare         ← UNCHANGED / CHANGED / NOT_COMPARABLE
```

Each bundle contains a deterministic SHA-256 hash of its complete canonical
payload and a manifest with timestamp and schema information. Capture bundles can
also contain a `binding_hash`: a cryptographic commitment over the stored v1
`request_hash` and `response_hash` pair. Anyone with the bundle can evaluate its
internal consistency offline.

Current binding construction:

```text
binding_hash = SHA256(
  canonical({
    "request_hash": request_hash,
    "response_hash": response_hash
  })
)
```

Current binding verification checks consistency among stored v1 hash fields. It
does not reconstruct source request or response material or establish that a
real-world provider invocation produced a particular response.

Verification reports separate assurance dimensions: `payload_integrity`,
`binding_field_consistency`, `signature_validity`, `trusted_signer_identity`,
`freshness`, and `authorization`. Unsigned and unbound bundles remain valid by
default; `--require-signature` and `--require-binding` reject the corresponding
absence. Bundled key material can establish mathematical signature validity, but
`trusted_signer_identity` remains `UNESTABLISHED`; freshness and authorization
remain `NOT_EVALUATED`.

---

## Capture adapter (OpenAI / Anthropic / LiteLLM)

No manual JSON. The capture adapter intercepts the API call and writes the bundle automatically.

```python
from openai import OpenAI
from aelitium import capture_openai

client = OpenAI()
result = capture_openai(
    client, "gpt-4o",
    [{"role": "user", "content": "What is the capital of France?"}],
    out_dir="./evidence",
)
print(result.ai_hash_sha256)  # hash of the complete validated canonical object
```

```bash
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0
# AI_HASH_SHA256=...
# BINDING_HASH=...   ← commitment over the stored request/response hash pair
```

LiteLLM capture records calls at the LiteLLM boundary using the same v1 evidence
contract. Repository tests cover the adapter boundary, not every provider route
supported by LiteLLM:

```python
from aelitium import capture_litellm

result = capture_litellm(
    model="openai/gpt-4o",           # or "anthropic/...", "bedrock/...", etc.
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    out_dir="./evidence",
)
print(result.ai_hash_sha256)
```

See [Capture layer](docs/INTEGRATION_CAPTURE.md) for Anthropic, LiteLLM, streaming, and signing.

---

## Zero-config with LiteLLM

Add one line. Keep using LiteLLM normally.

```python
from aelitium import enable_litellm
import litellm

enable_litellm(out_dir="./aelitium/bundles", verbose=True)

response = litellm.completion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)

print(response.choices[0].message.content)
# AELITIUM: bundle → ./aelitium/bundles/<binding_hash>  binding_hash=<hash>
```

Each successfully captured supported non-streaming call writes a bundle
automatically. The LLM response is unchanged.

**What you get:**

- `request_hash` — v1 selected-field identity over recorded model/messages
- `response_hash` — selected-field hash over recorded response content/model
- `binding_hash` — commitment over the two stored hashes

**Failure modes:**

| Mode | Capture fails | Streaming |
|---|---|---|
| `strict=False` (default) | warning, response returned | pass-through |
| `strict=True` | raises | raises |

```python
enable_litellm(strict=True)  # capture failure raises instead of warning
```

**Notes:**
- Streaming calls (`stream=True`) are not captured — they pass through unchanged

See [`examples/litellm_enable.py`](examples/litellm_enable.py) for a runnable example.

---

## Detect when the recorded response changed

```bash
aelitium compare ./bundle_last_week ./bundle_today
# STATUS=CHANGED rc=2
# REQUEST_HASH=SAME    a=3f4a8c1d... b=3f4a8c1d...
# RESPONSE_HASH=DIFFERENT  a=9b2e7f1a... b=c41d8e3b...
# INTERPRETATION=Same request_hash with different response_hash observed
```

If `REQUEST_HASH=SAME` and `RESPONSE_HASH=DIFFERENT`, the compared bundles contain different recorded responses for the same hashed request. AELITIUM does not attribute the cause.

Run offline (no API key):

```bash
bash examples/drift_demo/run_demo.sh
```

Or with a real OpenAI key:

```bash
python examples/model_drift_detector.py
```

---

## Scan for unprotected LLM calls

Find every LLM call in your codebase that isn't wrapped in a capture adapter:

```bash
aelitium scan ./src

# LLM call sites detected: 12
# Instrumented with capture adapter: 9
#   ✓ openai — api/worker.py:14
#   ✓ openai — api/worker.py:38
# Missing evidence capture: 3
#   ⚠ openai — jobs/batch.py:22
#   ⚠ anthropic — agents/classifier.py:11
#   ⚠ litellm — utils/fallback.py:7
# Coverage: 9/12 (75%)
# STATUS=INCOMPLETE rc=2
```

Add to CI/CD to enforce evidence coverage:

```yaml
- name: Check LLM evidence coverage
  run: aelitium scan ./src
```

For CI-friendly key=value output:

```bash
aelitium scan ./src --ci
# AELITIUM_SCAN_STATUS=INCOMPLETE
# AELITIUM_SCAN_TOTAL=12
# AELITIUM_SCAN_INSTRUMENTED=9
# AELITIUM_SCAN_MISSING=3
# AELITIUM_SCAN_COVERAGE=75
```

---

## Reproducibility

The same complete validated input object produces the same hash in validated
configurations:

```bash
bash scripts/verify_repro.sh
# === RESULT: PASS ===
# AI_HASH_SHA256=8b647717...
```

Validated on two independent machines (A + B) with identical hashes.

---

## Why logs are not enough

Tools like Langfuse or Helicone help you **debug LLM calls**.

AELITIUM helps you **verify the internal consistency of recorded evidence** and,
when compared with an independently trusted anchor, detect inconsistent changes.

Logs can be edited. Changes inconsistent with a bundle's governed evidence are
detectable; a self-consistent replacement requires an independently trusted anchor
to distinguish it from the expected artifact.

| Tool | What it does |
|------|-------------|
| Langfuse, Helicone, LangSmith | observability — traces, metrics, dashboards |
| AELITIUM | verification — governed schema, canonicalization, and evidence consistency checks |

These are complementary, not competing. AELITIUM adds governed evidence-consistency
checks and can provide tamper evidence when expected hashes or signer identities
are independently trusted.

---

## When teams use AELITIUM

- Detect when recorded responses differ between runs for the same request hash
- Detect changes inconsistent with the recorded evidence contract and a trusted external anchor
- Investigate incidents involving AI agents ("what recorded evidence is available for this interaction?")
- Produce verifiable records for compliance or audits (EU AI Act Art.12, SOC 2)
- Enforce evidence coverage in CI/CD (`aelitium scan` exits 2 if LLM calls are uninstrumented)

---

## CLI reference

### `aelitium`

| Command | Description |
|---------|-------------|
| `scan <path>` | Scan Python files for uninstrumented LLM call sites |
| `compare <bundle_a> <bundle_b>` | Compare two bundles — detect changed recorded responses |
| `verify-bundle <dir>` | Verify payload integrity and any present signature/binding evidence; optional flags can require them |
| `pack --input <file> --out <dir>` | Generate canonical JSON + manifest |
| `verify` with `--out=<dir>` | Verify integrity of a pack output dir |
| `validate --input <file>` | Validate against `ai_output_v1` schema |
| `canonicalize --input <file>` | Print deterministic hash |
| `verify-receipt --receipt <file> --pubkey <file>` | Verify Ed25519 authority receipt offline |
| `export --bundle <dir>` | Export bundle in compliance format (EU AI Act Art.12) |

Exit codes are command-specific: verification uses `0` for valid and `2` for
invalid; comparison also uses `1` for not comparable. The CLI is designed for
CI/CD pipelines.

---


## Policy

See `docs/policy/AELITIUM_TRUST_BOUNDARY_SPEC.md` for the canonical trust-boundary language policy.

## Documentation

- [Why AELITIUM](docs/WHY_AELITIUM.md) — problem statement, positioning, and what this is for
- [Architecture](docs/ARCHITECTURE.md) — canonicalization pipeline, evidence bundle, module map
- [Security model](docs/SECURITY_MODEL.md) — threats addressed, guarantees, limitations
- [Trust boundary](docs/TRUST_BOUNDARY.md) — what AELITIUM establishes and what it does not
- [5-minute demo](docs/AI_INTEGRITY_DEMO.md) — full walkthrough with expected output
- [Python integration](docs/INTEGRATION_PYTHON.md) — drop-in helper + FastAPI example
- [Capture layer](docs/INTEGRATION_CAPTURE.md) — OpenAI adapter, auto-packing, and same-process boundary guidance
- [Engine contract](docs/ENGINE_CONTRACT.md) — bundle schema and guarantees
- [Evidence Bundle Spec](docs/EVIDENCE_BUNDLE_SPEC.md) — open draft standard for verifiable AI output bundles; AELITIUM is the reference implementation
- [Evidence Model](docs/EVIDENCE_MODEL.md) — conceptual model, emergent properties, and cross-layer positioning
- [AAR evidenceRef mapping](docs/AAR_EVIDENCE_REF_MAPPING.md) — interoperability note: referencing AELITIUM bundles from Agent Action Receipts
- [AAR interop](docs/interop/AAR_EVIDENCE_REF.md) — referencing AELITIUM bundles as `evidenceRef` in Agent Action Receipts (AAR v1.1)

---

## Design principles

- **Deterministic** — the same complete validated input object produces the same hash in validated configurations
- **Offline-first** — verification never requires network access
- **Fail-closed** — any verification error returns `rc=2`; no silent failures
- **Auditable** — every pack includes a manifest with schema, timestamp, and hash
- **Pipeline-friendly** — key/value output is parseable; supported successful paths also offer `--json`

---

## Trust boundary

AELITIUM v1 establishes **internal evidence consistency**, not truth or historical
origin guarantees.

**What current verification can establish:**
- the payload satisfies `ai_output_v1` and the governed canonical byte contract
- manifest identifiers and `ai_hash_sha256` are consistent with the canonical payload
- stored v1 binding fields are consistent when present
- bundled Ed25519 material is mathematically valid when present

**What current verification does not establish by itself:**
- complete provider invocation identity or independent source reconstruction
- historical non-modification without an independently trusted external anchor
- trusted signer identity, freshness, or authorization
- that the output is correct, safe, or actually produced by a claimed model

**Integrity ≠ completeness.** Internal consistency does not guarantee that all
events were captured. Capture completeness depends on the integration layer — SDK
wrapper, proxy, or observer. See [TRUST_BOUNDARY.md](docs/TRUST_BOUNDARY.md) for
the full analysis.

Stronger provenance — signing authorities, hardware-backed keys — is the direction of [P3](docs/RELEASE_AUTHORITY_SERVICE.md).

---

## Compliance alignment

AELITIUM provides governed evidence bundles that can support the following
regulatory and audit requirements when used with appropriate external controls:

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| **EU AI Act — Article 12** | Logging and traceability of high-risk AI system outputs | Evidence bundles provide governed, internally verifiable records with deterministic hashes |
| **SOC 2 — CC7** | System monitoring and integrity controls | Offline consistency checks can support controls when expected hashes or keys are independently trusted |
| **ISO 42001** | AI management system auditability | Canonical bundles with schema versioning support third-party audits without infrastructure access |
| **NIST AI RMF — MG 2.2** | Traceability of AI decisions and outputs | Each bundle records a validated payload, hash, timestamp fields, and optional signature material within the documented v1 scope |

AELITIUM does not replace logging infrastructure. It adds **cryptographic
evidence-consistency checks** to an existing pipeline — offline, without a server
or blockchain.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
