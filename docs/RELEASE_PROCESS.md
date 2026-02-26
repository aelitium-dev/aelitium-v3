# Official Release Process (Machine B Only)

1. Validate authority

./scripts/authority_status.sh

Expected:
AUTHORITY_STATUS=GO

2. Execute release

./scripts/release_rc.sh vX.Y.Z-rcN tests/fixtures/input_min.json

Expected:
STATUS=VALID
REPRO=PASS
RELEASE_STATUS=GO

3. Evidence

Append entry to governance/logs/EVIDENCE_LOG.md

4. Push

git push origin main --tags