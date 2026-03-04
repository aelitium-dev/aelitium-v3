# AELITIUM

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Verifiable AI infrastructure.**

Cryptographic integrity for AI outputs and software releases.
Pack, verify, and detect tampering — offline, no SaaS, pipeline-friendly.

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
```

**Or run without installing** (from project root):

```bash
python3 -m engine.ai_cli pack --input my_output.json --out ./evidence
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
# Ran 76 tests ... OK
```

All tests pass on two independent machines (A + B) with identical hashes.

---

## Documentation

- [5-minute demo](docs/AI_INTEGRITY_DEMO.md) — full walkthrough with expected output
- [Engine contract](docs/ENGINE_CONTRACT.md) — bundle schema and guarantees
- [P3 architecture](docs/RELEASE_AUTHORITY_SERVICE.md) — authority-as-a-service design
- [Release process](docs/RELEASE_PROCESS.md)

---

## Design principles

- **Deterministic** — same input always produces the same hash, on any machine
- **Offline-first** — verification never requires network access
- **Fail-closed** — any verification error returns `rc=2`; no silent failures
- **Auditable** — every pack includes a manifest with schema, timestamp, and hash
- **Pipeline-friendly** — all output parseable (`STATUS=`, `AI_HASH_SHA256=`)
