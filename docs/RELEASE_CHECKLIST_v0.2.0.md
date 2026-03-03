# Release Checklist — v0.2.0

## Gate Evidence Summary

| Item | Status | Commit |
|------|--------|--------|
| Baseline freeze (A) | ✅ PASS | `0f8d43e` |
| Evidence log baseline (A) | ✅ written | `583f896` |
| Evidence fix bundle_schema 1.1 (A) | ✅ PASS | `eeefd1c` |
| Machine B verification gate (B) | ✅ PASS | `701cfb8` |
| TEST_MATRIX gate results (A) | ✅ written | `b3f4d64` |

## Machine A Results

- HEAD: `b3f4d64a3cf1b3aff20fc41e8d287adfcff714bb`
- `test_full_release_flow.sh`: DETERMINISM=PASS DIR_VERIFY=PASS ZIP_VERIFY=PASS TAMPER=PASS
- `test_release_zip_determinism.sh`: ZIP_DETERMINISM=PASS
- `test_cli_install.sh`: CLI_INSTALL_MODE=venv CLI_TEST_STATUS=PASS
- Unit tests: 20/20 PASS

## Machine B Results

- HEAD: `eeefd1cbebe5be2bc3fb2f2600ebf0eb7755dc3b`
- `test_full_release_flow.sh`: DETERMINISM=PASS DIR_VERIFY=PASS ZIP_VERIFY=PASS TAMPER=PASS
- `test_release_zip_determinism.sh`: ZIP_DETERMINISM=PASS ZIP_SHA256=`7561e122d8d45583682dbdb2d04020f7496d74f6bc09eb803590145d5e8f5f1d`
- `test_cli_install.sh`: CLI_INSTALL_MODE=copy CLI_TEST_STATUS=PASS
- Unit tests: 20/20 PASS

## Cross-Machine Determinism

ZIP SHA256 identical on A and B: `7561e122d8d45583682dbdb2d04020f7496d74f6bc09eb803590145d5e8f5f1d`

## Release Gate Checklist (to complete for v0.2.0 tag)

- [ ] Machine A: git tree CLEAN, HEAD at latest commit
- [ ] Machine A: `source scripts/use_test_signing_key.sh && ./scripts/gate_release.sh v0.2.0 inputs/minimal_input_v1.json` → RELEASE_STATUS=GO
- [ ] Evidence entry A written to EVIDENCE_LOG.md (machine_role=A)
- [ ] Machine B: sync to same HEAD
- [ ] Machine B: `gate_release.sh v0.2.0` → RELEASE_STATUS=GO
- [ ] Machine B: tag `v0.2.0` created and signed
- [ ] Evidence entry B written to EVIDENCE_LOG.md (machine_role=B)
- [ ] `git push --tags`

## Invariants (bundle_schema 1.1)

- `manifest.json`: `bundle_schema=1.1`, `hash_alg=sha256`, `input_schema=input_v1`
- `evidence_pack.json`: `canonical_payload` + `hash`
- `verification_keys.json`: `keyring_format=ed25519-v1`, 1 key, 1 signature
- Signing: `AEL_ED25519_PRIVKEY_B64` or `AEL_ED25519_PRIVKEY_PATH`
