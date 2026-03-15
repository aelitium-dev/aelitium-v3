# AELITIUM

> Detect when LLM behavior silently changes — verifiable, offline, no server.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![tests](https://img.shields.io/badge/tests-177%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

```bash
pip install aelitium
aelitium compare ./bundle_last_week ./bundle_today
# STATUS=CHANGED
# REQUEST_HASH=SAME
# RESPONSE_HASH=DIFFERENT
# INTERPRETATION=Same request produced a different response
```

---

## The problem

You run the same prompt in production. One week later, the output is different.

The model changed — but your logs just show two JSON blobs. There's no proof of *when* it changed, or *which* call started returning different results.

AELITIUM gives you cryptographic evidence for every LLM call — request hash, response hash, tamper-evident bundle — so you can prove exactly when behavior changed, and that your records haven't been altered.

---

## 30-second demo

```bash
pip install aelitium
bash examples/drift_demo/run_demo.sh
```

```
STATUS=CHANGED
REQUEST_HASH=SAME
RESPONSE_HASH=DIFFERENT
INTERPRETATION=Same request produced a different response
```

Same request. Different output. That means the change came from the model — not your code.

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

All commands accept `--json` for structured output.

---

## How it works

```
API call (OpenAI / Anthropic)
      ↓
capture adapter   ← records request_hash + response_hash at call time
      ↓
evidence bundle   ← canonical JSON + ai_manifest.json + binding_hash
      ↓
aelitium verify-bundle   ← STATUS=VALID / STATUS=INVALID
aelitium compare         ← UNCHANGED / CHANGED / NOT_COMPARABLE
```

Each bundle contains a deterministic SHA-256 hash of the payload, a manifest with timestamp and schema, and a cryptographic `binding_hash` linking the exact request to the exact response. Anyone with the bundle can verify it — no network required.

---

## Capture adapter (OpenAI / Anthropic)

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
print(result.ai_hash_sha256)  # deterministic proof of this exact call
```

```bash
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0
# AI_HASH_SHA256=...
# BINDING_HASH=...   ← cryptographic link between request and response
```

See [Capture layer](docs/INTEGRATION_CAPTURE.md) for Anthropic, streaming, and signing.

---

## Detect when the model changed

```bash
aelitium compare ./bundle_last_week ./bundle_today
# STATUS=CHANGED rc=2
# REQUEST_HASH=SAME    a=3f4a8c1d... b=3f4a8c1d...
# RESPONSE_HASH=DIFFERENT  a=9b2e7f1a... b=c41d8e3b...
# INTERPRETATION=Same request produced a different response
```

If `REQUEST_HASH=SAME` and `RESPONSE_HASH=DIFFERENT`, the change came from the model — not your code.

Run the full example (requires OpenAI API key):

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

The same AI output always produces the same hash, on any machine:

```bash
bash scripts/verify_repro.sh
# === RESULT: PASS ===
# AI_HASH_SHA256=8b647717...
```

Validated on two independent machines (A + B) with identical hashes.

---

## How this differs from observability tools

Tools like Langfuse or Helicone help you **debug LLM calls**.

AELITIUM helps you **prove what the model actually said**.

Logs can be edited. Evidence bundles cannot.

| Tool | What it does |
|------|-------------|
| Langfuse, Helicone, LangSmith | observability — traces, metrics, dashboards |
| AELITIUM | verification — cryptographic proof the record wasn't altered |

These are complementary, not competing. AELITIUM adds a tamper-evident layer on top of any existing pipeline.

---

## When teams use AELITIUM

- Detect when an LLM provider silently changes behavior between runs
- Prove AI outputs weren't modified after the fact
- Investigate incidents involving AI agents ("what exactly did the model say?")
- Produce verifiable records for compliance or audits (EU AI Act Art.12, SOC 2)
- Enforce evidence coverage in CI/CD (`aelitium scan` exits 2 if LLM calls are uninstrumented)

---

## CLI reference

### `aelitium`

| Command | Description |
|---------|-------------|
| `scan <path>` | Scan Python files for uninstrumented LLM call sites |
| `compare <bundle_a> <bundle_b>` | Compare two bundles — detect model behavior change |
| `verify-bundle <dir>` | Verify bundle: hash + signature + binding hash |
| `pack --input <file> --out <dir>` | Generate canonical JSON + manifest |
| `verify --out <dir>` | Verify integrity of a pack output dir |
| `validate --input <file>` | Validate against `ai_output_v1` schema |
| `canonicalize --input <file>` | Print deterministic hash |
| `verify-receipt --receipt <file> --pubkey <file>` | Verify Ed25519 authority receipt offline |
| `export --bundle <dir>` | Export bundle in compliance format (EU AI Act Art.12) |

Exit codes: `0` = success, `2` = failure. Designed for CI/CD pipelines.

---

## Documentation

- [Why AELITIUM](docs/WHY_AELITIUM.md) — problem statement, positioning, and what this is for
- [Architecture](docs/ARCHITECTURE.md) — canonicalization pipeline, evidence bundle, module map
- [Security model](docs/SECURITY_MODEL.md) — threats addressed, guarantees, limitations
- [Trust boundary](docs/TRUST_BOUNDARY.md) — what AELITIUM proves and what it does not
- [5-minute demo](docs/AI_INTEGRITY_DEMO.md) — full walkthrough with expected output
- [Python integration](docs/INTEGRATION_PYTHON.md) — drop-in helper + FastAPI example
- [Capture layer](docs/INTEGRATION_CAPTURE.md) — OpenAI adapter, auto-packing, trust gap explanation
- [Engine contract](docs/ENGINE_CONTRACT.md) — bundle schema and guarantees
- [Evidence Bundle Spec](docs/EVIDENCE_BUNDLE_SPEC.md) — open draft standard for verifiable AI output bundles; AELITIUM is the reference implementation

---

## Design principles

- **Deterministic** — same input always produces the same hash, on any machine
- **Offline-first** — verification never requires network access
- **Fail-closed** — any verification error returns `rc=2`; no silent failures
- **Auditable** — every pack includes a manifest with schema, timestamp, and hash
- **Pipeline-friendly** — all output parseable (`STATUS=`, `AI_HASH_SHA256=`, `--json`)

---

## Trust boundary

AELITIUM provides **tamper-evidence**, not truth guarantees.

**What AELITIUM proves:**
- the bundle contents have not changed since packing
- the canonicalized payload matches the recorded hash
- (with capture adapter) the request hash matches the exact API payload sent

**What AELITIUM does not prove:**
- that the model output was correct or safe
- that the system that packed the bundle was trustworthy
- that the model actually produced the output (without capture adapter)

**Integrity ≠ completeness.** AELITIUM proves that captured events were not altered. It does not guarantee that all events were captured. Capture completeness depends on the integration layer — SDK wrapper, proxy, or observer. If the agent controls its own logging, an observer-based capture pattern provides stronger guarantees. See [TRUST_BOUNDARY.md](docs/TRUST_BOUNDARY.md) for the full analysis.

Stronger provenance — signing authorities, hardware-backed keys — is the direction of [P3](docs/RELEASE_AUTHORITY_SERVICE.md).

---

## Compliance alignment

AELITIUM provides tamper-evident evidence bundles that support the following regulatory and audit requirements:

| Framework | Requirement | How AELITIUM helps |
|-----------|-------------|-------------------|
| **EU AI Act — Article 12** | Logging and traceability of high-risk AI system outputs | Evidence bundles provide immutable, verifiable records of AI outputs with deterministic hashes |
| **SOC 2 — CC7** | System monitoring and integrity controls | Independent offline verification confirms records have not been altered after creation |
| **ISO 42001** | AI management system auditability | Canonical bundles with schema versioning support third-party audits without infrastructure access |
| **NIST AI RMF — MG 2.2** | Traceability of AI decisions and outputs | Each bundle contains a complete, reproducible record: payload, hash, timestamp, and optional signature |

AELITIUM does not replace logging infrastructure. It adds **cryptographic integrity** on top of any existing pipeline — offline, without a server, without a blockchain.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
