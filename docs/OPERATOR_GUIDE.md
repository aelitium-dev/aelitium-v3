# OPERATOR GUIDE

Golden rule:
Run the gate. If it fails, you do not release.

## Signing Key (required for pack + verify)

Set before any `aelitium pack` or gate run:

```bash
export AEL_ED25519_PRIVKEY_B64=<base64-encoded 32-byte Ed25519 seed>
# optional
export AEL_ED25519_KEY_ID=my-key-id-2026
```

For local smoke tests only (NOT for production releases):
```bash
source scripts/use_test_signing_key.sh
```

## Common Flow

1) Set signing key env vars (Machine A)
2) Build/Pack (Machine A): `aelitium pack --input <input.json> --out <dir>`
3) Determinism check (Machine A): `./scripts/test_full_release_flow.sh`
4) Transfer repo to Machine B (tar or git)
5) Set signing key env vars (Machine B) — same key as A
6) Verify/Repro (Machine B): `./scripts/test_full_release_flow.sh`
7) Gate release (Machine B): `./scripts/gate_release.sh <tag> <input_json>`
8) Evidence Log entry: `governance/logs/EVIDENCE_LOG.md`
9) Tag created only on PASS (Machine B authority)

## Commands

- Gate:        `./scripts/gate_release.sh <tag> <input_json>`
- Full flow:   `./scripts/test_full_release_flow.sh`
- ZIP test:    `./scripts/test_release_zip_determinism.sh`
- CLI install: `./scripts/test_cli_install.sh`
- Determinism: `./scripts/bundle_determinism_check.sh`
- Evidence:    `governance/logs/EVIDENCE_LOG.md`

Dashboard:
- governance/dashboard/index.html (local UI, non-authoritative)

---

## A/B Sync (Operational)

Default (Remote):
Machine A:
- git push origin main --tags

Machine B:
- git fetch --all --tags
- git checkout main
- git pull --ff-only

Authority (Offline Bundle):
Machine A:
- ./scripts/make_bundle_a.sh

Machine B:
- ./scripts/apply_bundle_b.sh

Evidence:
If Authority mode is used, record bundle sha256 in EVIDENCE_LOG.md.

