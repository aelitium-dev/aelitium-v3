# Official Release Process (Machine B Only)

1. Validate authority

./scripts/authority_status.sh

Expected:
AUTHORITY_STATUS=GO

Notes:
- Authority identity is bound to `governance/authority/machine_b.identity.json`.
- `AEL_MACHINE` env is informational and not used as the authority decision source.

2. Execute release

./scripts/release_rc.sh vX.Y.Z-rcN tests/fixtures/input_min.json

Expected:
STATUS=VALID
REPRO=PASS
RELEASE_STATUS=GO
TAG_SIGN_STATUS=OK

3. Evidence

Append entry to governance/logs/EVIDENCE_LOG.md

4. Push

No manual tag push is required.
`gate_release.sh` creates and pushes a signed tag (`git tag -s` + verify + `git push origin <tag>`).
