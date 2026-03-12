# AELITIUM AI Integrity — 5-minute demo

> **Verifiable AI infrastructure.**
> Aelitium generates cryptographic evidence for AI outputs so that anyone can verify integrity later — even offline.
>
> Pack → Verify → Detect tampering. No SaaS. No network required.

---

## Prerequisites

```bash
git clone https://github.com/aelitium-dev/aelitium-v3.git
cd aelitium-v3

# create and activate a virtual environment (required on Debian/Ubuntu 22.04+)
python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

> **Alternative (no install):** all commands below can also be run as
> `python3 -m engine.ai_cli <subcommand>` from the project root — no venv needed.

---

## Step 1 — Your AI output

Any JSON file with this shape:

```json
{
  "schema_version": "ai_output_v1",
  "ts_utc": "2026-03-04T12:00:00Z",
  "model": "gpt-4o",
  "prompt": "Summarise Q1 revenue risks.",
  "output": "Revenue risk is concentrated in three areas...",
  "metadata": { "run_id": "prod-20260304-001" }
}
```

Save it as `my_output.json`.

---

## Step 2 — Pack (generate evidence)

```bash
aelitium pack --input my_output.json --out ./evidence
```

Output:

```
STATUS=OK rc=0
AI_HASH_SHA256=3a7f9c...
```

Two files are written to `./evidence/`:

| File | Contents |
|------|----------|
| `ai_canonical.json` | Deterministic, sorted-key JSON — the exact bytes that were hashed |
| `ai_manifest.json` | Schema, hash, timestamp, canonicalization method |

---

## Step 3 — Verify (any machine, any time)

```bash
aelitium verify --out ./evidence
```

Output:

```
STATUS=VALID rc=0
AI_HASH_SHA256=3a7f9c...
```

The hash in `ai_manifest.json` matches the canonical content. Integrity confirmed.

---

## Step 4 — Tamper detection

Edit one word in `evidence/ai_canonical.json` and verify again:

```bash
# simulate tamper
sed -i 's/Revenue risk/Revenue opportunity/' evidence/ai_canonical.json

aelitium verify --out ./evidence
```

Output:

```
STATUS=INVALID rc=2 reason=HASH_MISMATCH
DETAIL=expected=3a7f9c... got=d81b2e...
```

Any modification — one character, one word — is caught. Exit code `2` for scripting.

---

## Step 5 — Validate schema

```bash
aelitium validate --input my_output.json
```

Output:

```
STATUS=VALID rc=0
```

Schema violations return `STATUS=INVALID rc=2 reason=SCHEMA_VIOLATION`.

---

## What you get

- **Deterministic hash** — same AI output always produces the same hash
- **Offline verification** — no network, no third party
- **Tamper-evident** — any change detected immediately
- **Pipeline-friendly** — parse `STATUS=` and exit codes in CI/CD
- **Auditable** — `ai_manifest.json` records schema, model, timestamp, hash

---

## Use cases

| Scenario | How AELITIUM helps |
|----------|--------------------|
| AI output audit trail | Pack every response; verify before use |
| Regulatory compliance | Evidence bundle per inference, offline verifiable |
| Multi-team handoff | Producer packs; consumer verifies before processing |
| Red-teaming / eval | Pin expected outputs; detect any drift |

---

## Run the test suite

```bash
python3 -m unittest discover -s tests -q
# Ran 158 tests in ~42s ... OK
```
