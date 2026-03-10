# AELITIUM

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![tests](https://img.shields.io/badge/tests-100%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

```bash
pip install aelitium
```

## Provable AI outputs.

AELITIUM turns AI outputs into **tamper-evident evidence bundles** that can be verified anywhere, on any machine.

It allows engineers to **prove what a model actually said** — even long after the original system is gone.

---

## Why this exists

AI outputs are usually stored in logs or databases.

Those records can be edited, overwritten, selectively deleted, or disputed later.

When AI outputs influence decisions — finance, healthcare, support automation, legal workflows — teams eventually face the question:

> *"Can you prove what the model actually said?"*

AELITIUM provides a deterministic, cryptographic evidence bundle that allows anyone to verify the output independently.

---

## 30-second demo

```bash
pip install aelitium

aelitium pack --input output.json --out ./bundle
# STATUS=OK rc=0
# AI_HASH_SHA256=8b647717...

aelitium verify --out ./bundle
# STATUS=VALID rc=0
```

The hash is deterministic — same input produces the same hash on any machine.

```bash
# Tamper with the bundle, then verify:
aelitium verify --out ./bundle
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
```

All commands accept `--json` for structured output.

---

## How it works

```
AI output (JSON)
      ↓
aelitium pack      ← deterministic SHA-256 hash + manifest
      ↓
evidence bundle    ← canonical JSON + ai_manifest.json
      ↓
aelitium verify   ← STATUS=VALID / STATUS=INVALID
```

The bundle contains a canonicalized payload, a deterministic SHA-256 hash, and a manifest with schema, timestamp, and canonicalization method. Anyone with the bundle can verify its integrity — no network required.

---

## Reproducibility

AELITIUM is designed to be deterministic. The same AI output always produces the same hash, on any machine.

Run the full reproducibility check from a clean environment:

```bash
bash scripts/verify_repro.sh
```

This script creates a fresh virtual environment, installs the project, runs the test suite, packs the example twice, and confirms the resulting hashes match.

```
=== RESULT: PASS ===
AI_HASH_SHA256=8b647717...
```

All tests also pass on two independent machines (A + B) with identical hashes.

---

## CLI reference

### `aelitium`

| Command | Description |
|---------|-------------|
| `validate --input <file>` | Validate against `ai_output_v1` schema |
| `canonicalize --input <file>` | Print deterministic hash |
| `pack --input <file> --out <dir>` | Generate canonical JSON + manifest |
| `verify --out <dir>` | Verify integrity of a pack output dir |
| `verify-receipt --receipt <file> --pubkey <file>` | Verify Ed25519 authority receipt offline |

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

**What AELITIUM does not prove:**
- that the model output was correct or safe
- that the system that packed the bundle was trustworthy
- that the model actually produced the output

Stronger provenance — signing authorities, hardware-backed keys — is the direction of [P3](docs/RELEASE_AUTHORITY_SERVICE.md). See [TRUST_BOUNDARY.md](docs/TRUST_BOUNDARY.md) for the full analysis.

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
