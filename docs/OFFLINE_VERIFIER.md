# Offline Verifier (AELITIUM v3)

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
./scripts/offline_verify.sh release_output/
# or
./scripts/offline_verify.sh bundle.zip
