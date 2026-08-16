# AELITIUM AI Integrity — 5-minute demo

> **Verifiable AI evidence infrastructure.**
> Aelitium generates cryptographic evidence for recorded AI outputs so that bundle
> consistency can be verified later — even offline.
>
> Pack → Verify → Detect inconsistent edits. No SaaS. No network required.

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
| `ai_canonical.json` | Deterministic, sorted-key JSON — the recorded bytes that were hashed |
| `ai_manifest.json` | Schema, hash, timestamp, canonicalization method |

---

## Step 3 — Verify offline

```bash
aelitium verify-bundle ./evidence
```

Output:

```
STATUS=VALID rc=0
AI_HASH_SHA256=3a7f9c...
SIGNATURE=NONE
BINDING_HASH=NONE
PAYLOAD_INTEGRITY=VALID
BINDING_FIELD_CONSISTENCY=ABSENT
SIGNATURE_VALIDITY=ABSENT
TRUSTED_SIGNER_IDENTITY=UNESTABLISHED
FRESHNESS=NOT_EVALUATED
AUTHORIZATION=NOT_EVALUATED
```

The payload satisfies `ai_output_v1`; its canonical bytes, manifest identifiers,
and hash are internally consistent. Signature and binding evidence are absent and
accepted by default. Use `--require-signature` or `--require-binding` when that
absence must fail.

---

## Step 4 — Detect an inconsistent edit

Edit one word in `evidence/ai_canonical.json` and verify again:

```bash
# simulate tamper
sed -i 's/Revenue risk/Revenue opportunity/' evidence/ai_canonical.json

aelitium verify-bundle ./evidence
```

Output:

```
STATUS=INVALID rc=2 reason=HASH_MISMATCH
DETAIL=expected=3a7f9c... got=d81b2e...
```

This edit is inconsistent with the recorded manifest hash and is rejected with exit
code `2`. A fully self-consistent replacement requires an independently trusted
external anchor to distinguish it from the expected artifact.

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

- **Deterministic hash** — the same complete validated input object produces the same hash in validated configurations
- **Offline verification** — no network, no third party
- **Evidence consistency** — schema, canonical bytes, and recorded hash are checked
- **Pipeline-friendly** — parse `STATUS=` and exit codes in CI/CD
- **Auditable** — the canonical payload and manifest record model, schema, timestamp fields, and hash

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
```

The maintained claim is that the suite passes; the documentation does not pin a
test count that changes whenever coverage is added.
