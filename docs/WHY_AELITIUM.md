# Why AELITIUM

## The problem

You're running an AI pipeline in production. A model generates a response. That response influences a decision — a summary, a recommendation, an automated action.

Later, something goes wrong. Or an auditor asks: *"What exactly did the model say on March 5th at 14:32?"*

You check your logs. The text is there. But you can't prove:

- That the log wasn't modified
- That no one in the pipeline altered the output before it was stored
- That what you are inspecting is identical to what was recorded at capture time

**Logging records what happened. It doesn't prove the record wasn't changed.**

Note: AELITIUM does not solve capture authenticity — it cannot prove that the
capture path itself was honest, or that the bundle reflects exactly what the model
produced. It provides governed schema, canonicalization, and internal-consistency
checks for the evidence bundle you create. See
[TRUST_BOUNDARY.md](TRUST_BOUNDARY.md).

---

## Why existing tools don't solve this

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| Logging (Datadog, CloudWatch) | Records events | Doesn't prove events weren't modified |
| Observability (Langfuse, Arize) | Traces LLM calls | Doesn't produce cryptographic evidence |
| Audit logs | Records actions | Can be altered by admins |
| Vector stores | Stores embeddings | Not designed for integrity guarantees |

These tools are built for debugging and monitoring. They do not, by themselves,
provide a governed canonical bundle that can be checked against an independently
trusted expected hash.

---

## What AELITIUM does differently

AELITIUM binds a cryptographic fingerprint to the evidence bundle at packaging time.

```
AI response captured
        ↓
AELITIUM packs it into an evidence bundle
        ↓
SHA-256 hash computed from canonical JSON
        ↓
Hash stored alongside the output
```

Later, anyone can recompute the hash and check the inspected bundle's internal
consistency:

```bash
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0   ← payload and recorded evidence are internally consistent
# STATUS=INVALID rc=2 reason=HASH_MISMATCH  ← payload and manifest hash disagree
```

No network or AELITIUM server is required. Historical non-modification additionally
requires an independently trusted external hash, key identity, receipt, or
equivalent anchor.

---

## What this enables

**For developers:**
- Add integrity verification to any LLM pipeline in minutes
- Get machine-readable exit codes (`rc=0` / `rc=2`) for CI/CD
- Parse key/value compatibility output, or JSON from supported successful command paths

**For compliance:**
- Produce governed evidence whose consistency can be checked against trusted anchors
- Attach timestamps and model identifiers to every output
- Enable offline auditing by third parties

**For teams:**
- Add verifiable evidence references to a separately governed chain of custody
- Detect modifications inconsistent with a separately trusted expected record
- Build audit trails that survive system migrations

---

## What AELITIUM doesn't do

AELITIUM is not:

- A model monitoring tool (use Arize, Langfuse for that)
- A prompt management system
- A content moderation layer
- A guarantee that the model behaved correctly

AELITIUM establishes **bundle internal consistency** under the current contract,
not **capture authenticity** (that the bundle faithfully represents what the model
produced), historical non-modification without an external anchor, or **quality**
(that the output was correct).

These are separate problems. AELITIUM addresses governed bundle consistency; an
external anchor is required for historical non-modification claims. See
[TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for the full boundary.

---

## Design philosophy

**Offline-first.** Verification works without any AELITIUM infrastructure. Anyone with the hash and the evidence bundle can verify, forever.

**Deterministic.** The same complete validated `ai_output_v1` object produces the
same hash under the governed canonicalization. Timestamp and metadata are part of
that object; identical output text alone is insufficient.

**Fail-closed.** Invalid evaluated evidence returns exit code `2`. Signature and
binding absence are represented explicitly and remain accepted by default unless
the caller uses `--require-signature` or `--require-binding`.

**Reviewable surface.** The canonical verifier, contract identifiers, schema, and
adversarial tests are repository-visible and can be reviewed together.

---

## Who should use this

- Teams running LLM pipelines in regulated industries (healthcare, finance, legal)
- Developers building AI agents that take consequential actions
- Engineers who need audit trails for AI-generated content
- Anyone who wants to detect post-hoc modification of recorded LLM interactions
