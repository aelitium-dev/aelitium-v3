# AELITIUM Evidence Log

This file records verified milestones in the AELITIUM repository.
Each entry documents what was built, what was tested, and what was validated cross-machine.

---

## 2026-03-10 — OpenAI Capture Adapter EPIC

Status: **COMPLETE**

### Commits

| Hash | Message |
|------|---------|
| `e49c58b` | feat: add minimal OpenAI capture adapter |
| `2d278c2` | test: add capture determinism tests + TEST_MATRIX doc |
| `e90cdab` | docs: record capture layer EPIC in CHANGELOG |

### Artifacts

- `engine/capture/openai.py` — `capture_chat_completion()`: intercepts OpenAI chat calls, packs request+response into tamper-evident bundle automatically
- `engine/capture/__init__.py` — capture layer package
- `examples/capture_openai.py` — end-to-end usage example
- `docs/INTEGRATION_CAPTURE.md` — usage guide and trust boundary
- `docs/EVIDENCE_BUNDLE_SPEC.md` — complete bundle format specification
- `docs/TEST_MATRIX.md` — full test breakdown

### Validation

| Check | Machine A | Machine B |
|-------|-----------|-----------|
| Total test suite (158 tests) | PASS | PASS |
| Capture adapter tests (14/14) | PASS | PASS |
| `verify_repro.sh` | PASS | PASS |
| Working tree clean | ✅ | ✅ |
| HEAD == origin/main | ✅ | ✅ |

### Determinism tests (EPIC: capture determinism)

| Test | Result |
|------|--------|
| Same request → same `request_hash` | PASS |
| Same response → same `response_hash` | PASS |
| Different output → different hash | PASS |
| Tampered canonical → INVALID | PASS |

### Canonical reference hash

```
AI_HASH_SHA256=8b647717b14ad030fe8a641a9dcd63202e70aca170071d96040908e8354ef842
```

Stable across Machine A, Machine B, Python 3.10+, any OS.

### Notes

The capture layer reduces the manual handoff gap present in the original pack-time model.
Instead of the user writing JSON manually, `capture_chat_completion()` intercepts
the API call at runtime, hashing request and response at the moment of the call.

Trust boundary: proves the bundle has not been altered since packing. Does not prove
the model was correct or that the client was not compromised upstream. See
`docs/TRUST_BOUNDARY.md` for full analysis.

---

## 2026-03-04 — P2 AI Output Integrity MVP

Status: **COMPLETE** — published to PyPI as `aelitium` v0.2.0

### Artifacts

- `engine/ai_canonical.py` — canonicalization engine
- `engine/ai_pack.py` — deterministic pack function
- `engine/ai_cli.py` — CLI: validate, canonicalize, pack, verify, verify-receipt
- `engine/schemas/ai_output_v1.json` — input schema

### Validation

| Check | Machine A | Machine B |
|-------|-----------|-----------|
| 86 tests PASS | ✅ | ✅ |
| `verify_repro.sh` PASS | ✅ | ✅ |
| `pip install aelitium` clean install | ✅ | — |

---

## 2026-02-24 — P1 SDK Foundation

Status: **COMPLETE** — v0.1.0 baseline

- Canonical JSON + SHA-256 core
- Ed25519 signing
- Pack/verify/repro pipeline
- A/B authority gate
- Bundle schema 1.1
