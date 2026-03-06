# AELITIUM

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![tests](https://img.shields.io/badge/tests-86%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

**Detect tampering in AI outputs. Offline. No SaaS.**

Pack any AI response into a cryptographic evidence bundle.
Verify integrity on any machine, any time — with a single command.
Exit codes `0`/`2` make it CI/CD-friendly.

---

## What it does

```bash
# Pack an AI output into a cryptographic evidence bundle
aelitium-ai pack --input my_output.json --out ./evidence
# STATUS=OK rc=0
# AI_HASH_SHA256=583eb45e...

# Verify integrity (any machine, any time)
aelitium-ai verify --out ./evidence
# STATUS=VALID rc=0

# Tamper with the output — detected immediately
aelitium-ai verify --out ./evidence
# STATUS=INVALID rc=2 reason=HASH_MISMATCH
# DETAIL=expected=583eb45e... got=3a4ac67e...
```

Exit codes `0`/`2` — designed for CI/CD pipelines.

---

## Products

| Product | Status | Description |
|---------|--------|-------------|
| **P1 — Deterministic Release SDK** | ✅ v0.2.0 | Offline bundle engine with Ed25519 signing and A/B authority gate |
| **P2 — AI Output Integrity Layer** | ✅ MVP | Pack/verify/tamper-detect any AI output with deterministic hash |
| **P3 — Release Authority as a Service** | 🚧 design | Hosted signing node — delegate Machine B to AELITIUM |

---

## Quick start

```bash
git clone https://github.com/aelitium-dev/aelitium-v3.git
cd aelitium-v3

python3 -m venv .venv && source .venv/bin/activate
pip install -e .

aelitium-ai pack --input examples/ai_output_min.json --out ./evidence
aelitium-ai verify --out ./evidence
```

**Or run without installing** (from project root):

```bash
python3 -m engine.ai_cli pack --input examples/ai_output_min.json --out ./evidence
python3 -m engine.ai_cli verify --out ./evidence
```

---

## AI output format

Any JSON matching `ai_output_v1`:

```json
{
  "schema_version": "ai_output_v1",
  "ts_utc": "2026-03-04T12:00:00Z",
  "model": "gpt-4o",
  "prompt": "Summarise Q1 risks.",
  "output": "Revenue risk is concentrated in...",
  "metadata": { "run_id": "prod-001" }
}
```

---

## CLI reference

### `aelitium-ai` (P2 — AI integrity)

| Command | Description |
|---------|-------------|
| `validate --input <file>` | Validate against `ai_output_v1` schema |
| `canonicalize --input <file>` | Print deterministic hash |
| `pack --input <file> --out <dir>` | Generate canonical JSON + signed manifest |
| `verify --out <dir>` | Verify integrity of a pack output dir |
| `verify-receipt --receipt <file> --pubkey <file>` | Verify Ed25519 authority receipt offline |

All commands accept `--json` for machine-readable output.

### `aelitium` (P1 — release bundles)

| Command | Description |
|---------|-------------|
| `pack` | Create deterministic evidence bundle |
| `verify` | Verify bundle integrity |
| `repro` | Reproducibility check (two-run determinism) |

---

## Test suite

```bash
python3 -m unittest discover -s tests -q
# Ran 86 tests ... OK
```

All tests pass on two independent machines (A + B) with identical hashes.

---

## Reproducibility

Run the end-to-end reproducibility check from a clean environment:

```bash
bash scripts/verify_repro.sh
```

This script creates a fresh virtual environment, installs the project, runs the test suite, packs the example twice, and confirms the resulting hashes match.

---

## Documentation

- [Why AELITIUM](docs/WHY_AELITIUM.md) — problem statement, positioning, and what this is for
- [Architecture](docs/ARCHITECTURE.md) — canonicalization pipeline, evidence bundle, module map
- [Security model](docs/SECURITY_MODEL.md) — threats addressed, guarantees, limitations
- [5-minute demo](docs/AI_INTEGRITY_DEMO.md) — full walkthrough with expected output
- [Python integration](docs/INTEGRATION_PYTHON.md) — drop-in helper + FastAPI example
- [Engine contract](docs/ENGINE_CONTRACT.md) — bundle schema and guarantees
- [P3 architecture](docs/RELEASE_AUTHORITY_SERVICE.md) — authority-as-a-service design

---

## Design principles

- **Deterministic** — same input always produces the same hash, on any machine
- **Offline-first** — verification never requires network access
- **Fail-closed** — any verification error returns `rc=2`; no silent failures
- **Auditable** — every pack includes a manifest with schema, timestamp, and hash
- **Pipeline-friendly** — all output parseable (`STATUS=`, `AI_HASH_SHA256=`)
