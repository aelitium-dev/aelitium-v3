# AELITIUM v3 — ENTRYPOINT

## Daily work (Machine A / dev)
- Edit code, run tests, commit, push.
- Do NOT create release tags on A.

## Release (Machine B / authority)
1) Ensure identity context:
   - `echo "DISTRO=$WSL_DISTRO_NAME MACHINE=$AEL_MACHINE"`
   - `AEL_MACHINE` is informational only; authority is enforced by `scripts/authority_status.sh` via `governance/authority/machine_b.identity.json`.
2) Sync and verify repo:
   - `git fetch origin`
   - `git reset --hard origin/main`
   - `git status --porcelain=v1` must be empty
3) Run gate (only authority creates tags):
   - `./scripts/gate_release.sh <tag> tests/fixtures/input_min.json`
4) Gate creates and pushes a signed tag automatically.

## Naming
- Tags: v3.0.0-rcN only. No rcX.


## Offline verification (third-party)
- docs/OFFLINE_VERIFIER.md
- ./scripts/offline_verify.sh <release_output_dir | bundle.zip>
