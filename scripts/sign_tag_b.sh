#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: sign_tag_b.sh <vX.Y.Z-rcN>"
  exit 2
fi

TAG="$1"
LOG="${AEL_EVIDENCE_LOG_PATH:-governance/logs/EVIDENCE_LOG.md}"
ALLOW="governance/authority/allowed_signers"

# Validator must exist (fail-closed)
if [[ ! -f "scripts/validate_evidence_log.py" ]]; then
  echo "SIGN_STATUS=NO_GO reason=VALIDATOR_MISSING path=scripts/validate_evidence_log.py"
  exit 2
fi

# Tag format
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$ ]]; then
  echo "SIGN_STATUS=NO_GO reason=INVALID_TAG_FORMAT tag=$TAG"
  exit 2
fi

# Clean tree
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "SIGN_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

# Synced with origin/main
git fetch origin --quiet
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [[ "$LOCAL" != "$REMOTE" ]]; then
  echo "SIGN_STATUS=NO_GO reason=NOT_SYNCED local=$LOCAL remote=$REMOTE"
  exit 2
fi

# Authority material must exist
if [[ ! -f "$ALLOW" ]]; then
  echo "SIGN_STATUS=NO_GO reason=ALLOWLIST_MISSING path=$ALLOW"
  exit 2
fi

# Tag must not exist (local or remote)
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_LOCAL tag=$TAG"
  exit 2
fi
if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_REMOTE tag=$TAG"
  exit 2
fi

# Evidence must exist and validate for TAG (fail-closed)
python3 scripts/validate_evidence_log.py \
  --tag "$TAG" \
  --log "$LOG" \
  --required-machine-role A >/dev/null || {
  RC=$?
  echo "SIGN_STATUS=NO_GO reason=EVIDENCE_INVALID tag=$TAG rc=$RC"
  exit 2
}

# Enforce repo-provided allowed signers for ssh signature verification (Machine B local config)
git config --local gpg.format ssh
git config --local gpg.ssh.allowedSignersFile "$ALLOW"

# Require ssh-agent + key loaded (fail-closed)
ssh-add -l >/dev/null 2>&1 || {
  echo "SIGN_STATUS=NO_GO reason=SSH_AGENT_OR_KEY_MISSING"
  exit 2
}

# Create annotated signed tag (SSH signing via git's ssh signing)
git tag -s -a "$TAG" -m "AELITIUM release $TAG"

# Verify tag signature immediately (offline)
TAG_VERIFY_OUT="$(git tag -v "$TAG" 2>&1)" || {
  echo "SIGN_STATUS=NO_GO reason=TAG_VERIFY_FAILED tag=$TAG"
  exit 2
}
TAG_SIG_FPR="$(printf '%s\n' "$TAG_VERIFY_OUT" | grep -o 'SHA256:[^ ]*' | head -n1 || true)"
if [[ -z "${TAG_SIG_FPR:-}" ]]; then
  echo "SIGN_STATUS=NO_GO reason=TAG_FINGERPRINT_MISSING tag=$TAG"
  exit 2
fi
TAG_COMMIT="$(git rev-parse "$TAG^{commit}")"
TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HN="$(hostname 2>/dev/null || echo unknown)"
MID="$(tr -d '\n' </etc/machine-id 2>/dev/null || echo unknown)"
MACHINE_ID="B|$HN|$MID"

# Append Machine B attestation entry derived from validated A entry.
python3 - "$LOG" "$TAG" "$TS_UTC" "$MACHINE_ID" "$TAG_COMMIT" "$TAG_SIG_FPR" <<'PY'
import json
import re
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
tag = sys.argv[2]
ts_utc = sys.argv[3]
machine_id = sys.argv[4]
tag_commit = sys.argv[5]
tag_sig_fpr = sys.argv[6]

pattern = re.compile(
    r"^## EVIDENCE_ENTRY v1 \| tag=(?P<header_tag>\S+)\s*\n```json\s*\n(?P<body>\{.*?\})\s*\n```",
    flags=re.MULTILINE | re.DOTALL,
)

text = log_path.read_text(encoding="utf-8", errors="replace")
entries = []
for m in pattern.finditer(text.replace("\r\n", "\n")):
    if m.group("header_tag") != tag:
        continue
    obj = json.loads(m.group("body"))
    if obj.get("tag") != tag:
        continue
    entries.append(obj)

a_entries = [e for e in entries if e.get("machine_role") == "A"]
b_entries = [e for e in entries if e.get("machine_role") == "B"]
if len(a_entries) != 1:
    raise SystemExit("A_ENTRY_COUNT_INVALID")
if len(b_entries) != 0:
    raise SystemExit("B_ENTRY_ALREADY_EXISTS")

a = a_entries[0]
required_copy_keys = [
    "schema",
    "tag",
    "input_sha256",
    "manifest_sha256",
    "evidence_sha256",
    "verification_keys_sha256",
    "bundle_sha_run1",
    "bundle_sha_run2",
    "verify_rc",
    "repro_rc",
    "tamper_rc",
    "sync_mode",
    "bundle_sha256",
]
for key in required_copy_keys:
    if key not in a:
        raise SystemExit(f"A_ENTRY_MISSING_KEY:{key}")

b = {
    "schema": a["schema"],
    "tag": a["tag"],
    "ts_utc": ts_utc,
    "input_sha256": a["input_sha256"],
    "manifest_sha256": a["manifest_sha256"],
    "evidence_sha256": a["evidence_sha256"],
    "verification_keys_sha256": a["verification_keys_sha256"],
    "bundle_sha_run1": a["bundle_sha_run1"],
    "bundle_sha_run2": a["bundle_sha_run2"],
    "verify_rc": a["verify_rc"],
    "repro_rc": a["repro_rc"],
    "tamper_rc": a["tamper_rc"],
    "machine_role": "B",
    "machine_id": machine_id,
    "sync_mode": a["sync_mode"],
    "bundle_sha256": a["bundle_sha256"],
    "x_offline_verify_rc": 0,
    "x_git_tag_verify": "GOOD",
    "x_tag_commit": tag_commit,
    "x_tag_sig_fpr": tag_sig_fpr,
}

block = (
    f"\n\n## EVIDENCE_ENTRY v1 | tag={tag}\n"
    f"```json\n{json.dumps(b, ensure_ascii=False, indent=2)}\n```\n"
)
log_path.write_text(text.rstrip() + block, encoding="utf-8")
PY

python3 scripts/validate_evidence_log.py \
  --tag "$TAG" \
  --log "$LOG" \
  --required-machine-role B >/dev/null || {
  RC=$?
  echo "SIGN_STATUS=NO_GO reason=B_ATTESTATION_INVALID tag=$TAG rc=$RC"
  exit 2
}

git add "$LOG"
git commit -m "governance: B attestation for $TAG"
git push origin main

# Push only the tag
git push origin "refs/tags/$TAG"

echo "SIGN_STATUS=GO tag=$TAG"
