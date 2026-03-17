# Why AELITIUM

## The problem

You're running an AI pipeline in production. A model generates a response. That response influences a decision — a summary, a recommendation, an automated action.

Later, something goes wrong. Or an auditor asks: *"What exactly did the model say on March 5th at 14:32?"*

You check your logs. The text is there. But you can't prove:

- That the log wasn't modified
- That no one in the pipeline altered the output before it was stored
- That what you are inspecting is identical to what was recorded at capture time

**Logging records what happened. It doesn't prove the record wasn't changed.**

Note: AELITIUM does not solve capture authenticity — it cannot prove that the capture path itself was honest, or that the bundle reflects exactly what the model produced. It provides cryptographic integrity for the evidence bundle you create. See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md).

---

## Why existing tools don't solve this

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| Logging (Datadog, CloudWatch) | Records events | Doesn't prove events weren't modified |
| Observability (Langfuse, Arize) | Traces LLM calls | Doesn't produce cryptographic evidence |
| Audit logs | Records actions | Can be altered by admins |
| Vector stores | Stores embeddings | Not designed for integrity guarantees |

These tools are built for debugging and monitoring. None of them answer: *"Has this recorded output been modified since it was captured?"*

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

Later, anyone can recompute the hash and check:

```bash
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0   ← bundle is intact
# STATUS=INVALID rc=2 reason=HASH_MISMATCH  ← bundle was modified
```

No network required. No AELITIUM server required. Just math.

---

## What this enables

**For developers:**
- Add integrity verification to any LLM pipeline in minutes
- Get machine-readable exit codes (`rc=0` / `rc=2`) for CI/CD
- Use the `--json` flag for structured output in any language

**For compliance:**
- Produce evidence that AI outputs haven't been tampered with
- Attach timestamps and model identifiers to every output
- Enable offline auditing by third parties

**For teams:**
- Establish a chain of custody for AI-generated content
- Detect accidental or intentional modification of stored outputs
- Build audit trails that survive system migrations

---

## What AELITIUM doesn't do

AELITIUM is not:

- A model monitoring tool (use Arize, Langfuse for that)
- A prompt management system
- A content moderation layer
- A guarantee that the model behaved correctly

AELITIUM proves **bundle integrity** (the evidence wasn't changed after packaging), not **capture authenticity** (that the bundle faithfully represents what the model produced) and not **quality** (that the output was correct).

These are separate problems. AELITIUM solves the integrity problem. See [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) for the full boundary.

---

## Design philosophy

**Offline-first.** Verification works without any AELITIUM infrastructure. Anyone with the hash and the evidence bundle can verify, forever.

**Deterministic.** The same AI output always produces the same hash. This is a property, not an accident — it's enforced by the canonicalization algorithm.

**Fail-closed.** If verification fails for any reason, the exit code is `2`. There is no "warning" state. Either the output is intact or it isn't.

**Small surface area.** The core is ~150 lines of Python with no exotic dependencies. It's auditable by any developer in an afternoon.

---

## Who should use this

- Teams running LLM pipelines in regulated industries (healthcare, finance, legal)
- Developers building AI agents that take consequential actions
- Engineers who need audit trails for AI-generated content
- Anyone who wants to detect post-hoc modification of recorded LLM interactions
