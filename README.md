# AELITIUM

> Git-style verification for LLM outputs.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

> AELITIUM is a library/CLI for producing and verifying internally consistent,
> offline-verifiable evidence bundles for recorded LLM interactions under
> deterministic canonicalization.

> **Release status:** `v0.4.0` is the current published GitHub and PyPI release.
> `pip install aelitium` installs AELITIUM 0.4.0.

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
- An explicitly activated Freshness policy can evaluate declared-time recency
  of the canonical timestamp

## What it does not establish

- That the model actually executed
- That the provider was honest
- That the response is correct or truthful
- That capture was complete
- Complete provider invocation identity
- Trusted signer identity, unless an external trust store is explicitly
  supplied for evaluation (see [Trust boundary](#trust-boundary))
- Trusted historical time or authorization
- That semantic equivalence implies hash equivalence

---

## The problem

You run the same prompt text in production. One week later, the output is different.

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

The frozen demo bundles predate invocation evidence, so v0.4.0 output
reports `COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK`. Their selected v1 request
hashes match and their selected response hashes differ.

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
aelitium compare         ← invocation-first comparison with visible basis
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

Verification reports exactly eight separate assurance dimensions:

| Dimension | Reachable states in v0.4.0 |
|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` |
| `authorization` | `NOT_EVALUATED` only |

Unsigned and unbound bundles remain valid by default; `--require-signature` and
`--require-binding` reject the corresponding absence. Bundled key material alone
does not establish trusted signer identity — mathematical signature validity is a
separate property. `trusted_signer_identity` remains `UNESTABLISHED` by default,
and becomes `VALID` only when the caller explicitly supplies a local trust store
(`--trust-store PATH`) containing the verified signing key's fingerprint.
Authorization is not implemented in v0.4.0 and remains `NOT_EVALUATED` in every
case.

Freshness is `NOT_EVALUATED` by default. Activate it on `verify` or
`verify-bundle` only by supplying both policy options:

```bash
aelitium verify-bundle ./evidence \
  --freshness-max-age-seconds 300 \
  --freshness-reference-time-utc 2026-03-04T00:05:00Z
```

The source is `ai_canonical.json.ts_utc`. `freshness = VALID` means only
that this declared strict UTC whole-second timestamp lies within the
inclusive verifier-supplied window. It is declared-time recency, not trusted
historical time, provider execution, response causation, authorization, or
legal/regulatory compliance. Invalid or incomplete policy gives
`freshness = UNESTABLISHED`; stale, future, or malformed selected evidence
time gives `freshness = INVALID`. See the normative
[Freshness trust boundary](docs/TRUST_BOUNDARY.md#freshness-declared-time-recency).

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

### Invocation assurance

Capture bundles also store a versioned **invocation identity**
(`aelitium-invocation-v1`) — the semantic model/messages/parameters emitted
at the provider/SDK call boundary — and an **invocation binding**
(`aelitium-invocation-binding-v1`) linking that identity's hash to the
stored `response_hash`. The verifier reports both as separate,
deterministic consistency dimensions: `invocation_identity_consistency` and
`invocation_binding_consistency`.

These are consistency assurances only — they establish that the stored
fields are internally consistent with each other, not that a provider
received or executed the invocation, nor that the response was historically
caused by it. See [Invocation assurance](docs/INVOCATION_ASSURANCE.md) for
the full claim boundary.

`invocation_identity` is a separate, broader recorded identity when present.
Historical v0.3.x `compare` does not use `invocation_identity` or
`invocation_binding` as its comparison basis. The v0.4.0 contract uses a
validated invocation identity only when validated invocation binding evidence
is also present in both bundles.

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

## Compare validated recorded evidence

```bash
aelitium compare ./bundle_last_week ./bundle_today
# STATUS=CHANGED rc=2
# COMPARISON_CONTRACT=aelitium-compare-v1
# COMPARISON_MODE=INVOCATION_FIRST
# COMPARISON_BASIS=INVOCATION_IDENTITY_V1
# COMPARISON_REASON=RESPONSE_HASH_DIFFERENT
# INVOCATION_IDENTITY_HASH=SAME  a=62a1d3c4... b=62a1d3c4...
# REQUEST_HASH=SAME    a=3f4a8c1d... b=3f4a8c1d...
# RESPONSE_HASH=DIFFERENT  a=9b2e7f1a... b=c41d8e3b...
```

**Comparison basis in v0.3.x: `request_hash` v1.**

That remains the historical v0.3.x contract. It can be selected explicitly in
v0.4.0 with `--legacy-request-hash-v1`.

**Comparison contract in v0.4.0: `aelitium-compare-v1`.** The default
mode is `INVOCATION_FIRST`:

- When both bundles have `invocation_identity_consistency=VALID` and
  `invocation_binding_consistency=VALID`, the basis is
  `INVOCATION_IDENTITY_V1`. Different invocation-identity hashes produce
  `NOT_COMPARABLE`; matching hashes allow the selected response hashes to be
  compared.
- When one or both valid bundles lack that usable invocation evidence, the basis
  is visibly downgraded to `REQUEST_HASH_V1_FALLBACK`, including asymmetric and
  legacy-bundle comparisons.
- `--require-invocation-evidence` selects `STRICT_INVOCATION` and disables the
  fallback. Missing usable evidence produces `NOT_COMPARABLE`, basis `NONE`, and
  required basis `INVOCATION_IDENTITY_V1`.
- `--legacy-request-hash-v1` selects `LEGACY_REQUEST_HASH_V1` and basis
  `REQUEST_HASH_V1_LEGACY`, reproducing the v0.3.x request-hash decisions.

Every result exposes its comparison basis and reason. `UNCHANGED` means that,
under the reported basis, the selected comparison identity hashes and selected
response hashes match. `CHANGED` means the selected comparison identity hashes
match and the selected response hashes differ. `NOT_COMPARABLE` makes no
response-change conclusion because the selected identities differ or required
evidence is unavailable. Invalid inputs report `INVALID_BUNDLE` before basis
selection.

`request_hash` is not a complete invocation identity. Its equality does not
establish equality of every invocation parameter, mode, provider route, client
configuration, or execution context. `CHANGED` does not by itself establish
model drift or explain causation, and `UNCHANGED` does not establish that the
full invocation configuration or model behavior was unchanged. Equality of
validated `aelitium-invocation-v1` hashes applies only to the fields selected by
that recorded identity format; it does not establish a complete real-world
invocation. The displayed request and legacy binding hashes are diagnostic when
the basis is `INVOCATION_IDENTITY_V1`; invocation-binding hashes are never the
comparison identity.

AELITIUM establishes internal consistency of recorded evidence on the validated
surface. It does not establish provider execution, causation, full invocation
completeness, model drift, output truth, authorization, or legal compliance.

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

- Compare selected response hashes across bundles with the same selected v1 request hash
- Detect changes inconsistent with the recorded evidence contract and a trusted external anchor
- Investigate incidents involving AI agents ("what recorded evidence is available for this interaction?")
- Support Article 12-oriented record mapping and other audit evidence workflows;
  AELITIUM does not determine legal or regulatory compliance
- Enforce evidence coverage in CI/CD (`aelitium scan` exits 2 if LLM calls are uninstrumented)

---

## CLI reference

### `aelitium`

| Command | Description |
|---------|-------------|
| `scan <path>` | Scan Python files for uninstrumented LLM call sites |
| `compare <bundle_a> <bundle_b>` | Compare validated recorded hashes using an explicit invocation-first, fallback, strict, or legacy basis |
| `verify-bundle <dir>` | Verify the eight-dimension assurance result, including invocation consistency and optional declared-time Freshness evaluation |
| `pack --input <file> --out <dir>` | Generate canonical JSON + manifest |
| `verify` with `--out=<dir>` | Verify the same eight-dimension assurance result for a pack output directory |
| `validate --input <file>` | Validate against `ai_output_v1` schema |
| `canonicalize --input <file>` | Print deterministic hash |
| `verify-receipt --receipt <file> --pubkey <file>` | Verify Ed25519 authority receipt offline |
| `export --bundle <dir>` | Export a project-defined Article 12-oriented record mapping |

Exit codes are command-specific: verification uses `0` for valid and `2` for
invalid; comparison also uses `1` for not comparable. The CLI is designed for
CI/CD pipelines.

---


## Policy

See [Messaging guardrails](docs/MESSAGING_GUARDRAILS.md) and the normative
[Trust boundary](docs/TRUST_BOUNDARY.md) for the public-claim policy.

## Documentation

- [Why AELITIUM](docs/WHY_AELITIUM.md) — problem statement, positioning, and what this is for
- [Architecture](docs/ARCHITECTURE.md) — canonicalization pipeline, evidence bundle, module map
- [Security model](docs/SECURITY_MODEL.md) — threats addressed, guarantees, limitations
- [Trust boundary](docs/TRUST_BOUNDARY.md) — what AELITIUM establishes and what it does not
- [5-minute demo](docs/AI_INTEGRITY_DEMO.md) — full walkthrough with expected output
- [Python integration](docs/INTEGRATION_PYTHON.md) — drop-in helper + FastAPI example
- [Capture layer](docs/INTEGRATION_CAPTURE.md) — OpenAI adapter, auto-packing, and same-process boundary guidance
- [Invocation assurance](docs/INVOCATION_ASSURANCE.md) — versioned invocation identity/binding, their consistency dimensions, and explicit claim boundaries
- [Engine contract](docs/ENGINE_CONTRACT.md) — legacy generic bundle compatibility contract
- [Evidence Bundle Spec](docs/EVIDENCE_BUNDLE_SPEC.md) — conceptual, non-normative draft; it is not the current AI v1 runtime contract, and AELITIUM does not currently claim conformance or reference-implementation status
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
- stored invocation identity fields and their versioned hash are consistent when
  present
- stored invocation binding fields consistently link the invocation identity hash
  to the recorded response hash when present
- bundled Ed25519 material is mathematically valid when present
- a verified signing key's fingerprint against an explicitly supplied
  external trust store, when one is provided
- declared-time recency of `ai_canonical.json.ts_utc` under an explicitly
  supplied maximum age and UTC reference time

**What current verification does not establish by itself:**
- complete provider invocation identity or independent source reconstruction
- provider execution or response causation from invocation consistency
- historical non-modification without an independently trusted external anchor
- trusted signer identity beyond an explicitly supplied external trust store
- trusted historical time or authorization
- that the output is correct, safe, or actually produced by a claimed model

An explicit trust store makes `trusted_signer_identity` observable instead of
always `UNESTABLISHED`. A caller cannot obtain `trusted_signer_identity=VALID`
without supplying one, and cannot enforce membership without also passing
`--require-trusted-signer`:

```bash
aelitium verify --out ./bundle --trust-store ./trust-store
aelitium verify --out ./bundle \
    --trust-store ./trust-store \
    --require-trusted-signer
```

**Integrity ≠ completeness.** Internal consistency does not guarantee that all
events were captured. Capture completeness depends on the integration layer — SDK
wrapper, proxy, or observer. See [TRUST_BOUNDARY.md](docs/TRUST_BOUNDARY.md) for
the full analysis.

Stronger provenance — signing authorities, hardware-backed keys — is the direction of [P3](docs/RELEASE_AUTHORITY_SERVICE.md).

---

## Record and audit workflow alignment

AELITIUM provides technical evidence artifacts that can support record and audit
workflows when used with appropriate external controls:

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| **EU AI Act — Article 12** | Record-keeping workflows | A project-defined Article 12-oriented mapping exposes selected bundle fields for downstream record workflows |
| **SOC 2 — CC7** | System monitoring and integrity controls | Offline consistency checks can support controls when expected hashes or keys are independently trusted |
| **ISO 42001** | AI management system auditability | Canonical bundles with schema versioning support third-party audits without infrastructure access |
| **NIST AI RMF — MG 2.2** | Traceability of AI decisions and outputs | Each bundle records a validated payload, hash, timestamp fields, and optional signature material within the documented v1 scope |

AELITIUM does not replace logging infrastructure. It adds **cryptographic
evidence-consistency checks** to an existing pipeline — offline, without a server
or blockchain. Its export is not an official regulatory format, a complete
real-world record, a conformity assessment, certification, or a legal compliance
determination.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
