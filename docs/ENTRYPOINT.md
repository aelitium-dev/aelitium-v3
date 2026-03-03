# AELITIUM v3 — ENTRYPOINT

## Daily work (Machine A / dev)
- Set signing key: `export AEL_ED25519_PRIVKEY_B64=<key>`
- Edit code, run tests, commit, push.
- Do NOT create release tags on A.
- Smoke test: `source scripts/use_test_signing_key.sh && ./scripts/test_full_release_flow.sh`

## Release (Machine B / authority)
1) Set signing key (same key used on A):
   - `export AEL_ED25519_PRIVKEY_B64=<key>`
   - `export AEL_ED25519_KEY_ID=<key-id>`
2) Ensure identity context:
   - `echo "DISTRO=$WSL_DISTRO_NAME MACHINE=$AEL_MACHINE"`
3) Sync repo (remote or tar):
   - Remote: `git fetch origin && git reset --hard origin/main`
   - Offline: extract tar, confirm `HEAD=$(git rev-parse HEAD)`
   - `git status --porcelain=v1` must be empty
4) Run gate (only authority creates tags):
   - `./scripts/gate_release.sh <tag> tests/fixtures/input_min.json`
5) Write evidence B entry: `governance/logs/EVIDENCE_LOG.md`
6) Push tag: `git push --tags`

## Naming
- Tags: `v0.X.Y` (stable) or `v0.X.Y-rcN` (release candidates)
- bundle_schema: `1.1` (ed25519-v1)


## Offline verification (third-party)
- docs/OFFLINE_VERIFIER.md
- ./scripts/offline_verify.sh <release_output_dir | bundle.zip>
