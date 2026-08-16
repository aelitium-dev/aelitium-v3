# Legacy Generic Offline Verifier

**Status:** LEGACY_GENERIC_OFFLINE_VERIFIER

This document describes `scripts/offline_verify.sh` and the generic compatibility
bundle format built from `manifest.json`, `evidence_pack.json`, and required
verification material. It is not the current AELITIUM AI evidence bundle v1
verifier contract.

For current AI evidence, use `python3 -m engine.ai_cli verify` or
`python3 -m engine.ai_cli verify-bundle` and consult
[MESSAGING_GUARDRAILS.md](MESSAGING_GUARDRAILS.md) and
[TRUST_BOUNDARY.md](TRUST_BOUNDARY.md).

## Input
- A directory containing:
  - manifest.json
  - evidence_pack.json
  - verification_keys.json
- Or a .zip containing the same files at the root.

## Semantics
- No network. No git required.
- Fail-closed: any mismatch -> NO_GO / non-zero exit.

## Run
```bash
./scripts/offline_verify.sh release_output/
# or
./scripts/offline_verify.sh bundle.zip
```
