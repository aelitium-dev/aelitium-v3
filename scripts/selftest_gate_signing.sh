#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$ROOT/scripts/gate_release.sh"
INPUT="$ROOT/inputs/minimal_input_v1.json"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
OUT_NO_AGENT="$TMP/out_no_agent.txt"
OUT_OK="$TMP/out_ok.txt"
CALLS="$TMP/git_calls.log"
mkdir -p "$BIN"

TAG1="v9.9.9"
TAG2="v9.9.10"
FULL_SHA="11460945dd86193667560c24190f5b895a8a4593"
KEY_TYPE="ssh-ed25519"
KEY_B64="AAAAC3NzaC1lZDI1NTE5AAAAIMockAelitiumReleaseSigningKeyMaterial12345"
KEY_COMMENT="aelitium-release@machine-b"

SIGNING_PUB="$TMP/aelitium_release_signing.pub"
ALLOWED_SIGNERS="$TMP/allowed_signers"
EVIDENCE_LOG="$TMP/EVIDENCE_LOG.md"

cat > "$SIGNING_PUB" <<EOF_KEY
$KEY_TYPE $KEY_B64 $KEY_COMMENT
EOF_KEY

cat > "$ALLOWED_SIGNERS" <<EOF_SIGNERS
$KEY_COMMENT $KEY_TYPE $KEY_B64
EOF_SIGNERS

make_entry() {
  local tag="$1"
  cat <<EOF_ENTRY
## EVIDENCE_ENTRY v1 | tag=$tag
\`\`\`json
{
  "schema": "evidence_entry_v1",
  "tag": "$tag",
  "ts_utc": "2026-02-27T00:20:21Z",
  "input_sha256": "34d8739e7ba3cd7dab4327a0c48fce70e642b967969cad1a73f2e1713ef3d413",
  "manifest_sha256": "4ac6d98e5b6c629b042d49b4875d6696081b019c9a929c9f8c985c3b9575984b",
  "evidence_sha256": "237d44c22b8c9b10b19a20c8bccc6808969e994672bcf11d0d0ccf19bf458f4e",
  "verification_keys_sha256": "4096f8f49e938576a5aa15e587b3f56b052b5c4ec60b4c95a745e84f363414e5",
  "bundle_sha_run1": "1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646",
  "bundle_sha_run2": "1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "B",
  "machine_id": "AELITIUM-DEV|6cf43cdaa0784741ae3e87878fe7e009",
  "sync_mode": "remote",
  "bundle_sha256": null
}
\`\`\`
EOF_ENTRY
}

{
  echo "# Evidence Log"
  echo
  make_entry "$TAG1"
  echo
  make_entry "$TAG2"
} > "$EVIDENCE_LOG"

cat > "$BIN/git" <<EOF_GIT
#!/usr/bin/env bash
set -euo pipefail
CALLS="$CALLS"
FULL_SHA="$FULL_SHA"
SIGNING_PUB="$SIGNING_PUB"
ALLOWED_SIGNERS="$ALLOWED_SIGNERS"
echo "git \$*" >> "\$CALLS"

if [[ "\${1:-}" == "status" && "\${2:-}" == "--porcelain=v1" ]]; then
  exit 0
fi
if [[ "\${1:-}" == "rev-parse" && "\${2:-}" == "HEAD" ]]; then
  echo "\$FULL_SHA"
  exit 0
fi
if [[ "\${1:-}" == "config" && "\${2:-}" == "--global" && "\${3:-}" == "--get" ]]; then
  case "\${4:-}" in
    gpg.format) echo "ssh"; exit 0 ;;
    user.signingkey) echo "\$SIGNING_PUB"; exit 0 ;;
    gpg.ssh.allowedSignersFile) echo "\$ALLOWED_SIGNERS"; exit 0 ;;
    *) exit 1 ;;
  esac
fi
if [[ "\${1:-}" == "show-ref" && "\${2:-}" == "--tags" && "\${3:-}" == "--quiet" && "\${4:-}" == "--verify" ]]; then
  exit 1
fi
if [[ "\${1:-}" == "ls-remote" && "\${2:-}" == "--tags" ]]; then
  exit 0
fi
if [[ "\${1:-}" == "tag" && "\${2:-}" == "-s" ]]; then
  exit 0
fi
if [[ "\${1:-}" == "tag" && "\${2:-}" == "-v" ]]; then
  exit 0
fi
if [[ "\${1:-}" == "push" && "\${2:-}" == "origin" ]]; then
  exit 0
fi

echo "unexpected git invocation: \$*" >&2
exit 99
EOF_GIT
chmod +x "$BIN/git"

cat > "$BIN/ssh-add" <<EOF_SSHADD
#!/usr/bin/env bash
set -euo pipefail
if [[ "\${1:-}" == "-l" ]]; then
  if [[ "\${SELFTEST_SSHADD_MODE:-loaded}" == "loaded" ]]; then
    echo "256 SHA256:mock-fingerprint $KEY_COMMENT (ED25519)"
    exit 0
  fi
  exit 1
fi
if [[ "\${1:-}" == "-L" ]]; then
  if [[ "\${SELFTEST_SSHADD_MODE:-loaded}" == "loaded" ]]; then
    echo "$KEY_TYPE $KEY_B64 $KEY_COMMENT"
    exit 0
  fi
  exit 1
fi
echo "unsupported ssh-add args: \$*" >&2
exit 99
EOF_SSHADD
chmod +x "$BIN/ssh-add"

run_gate() {
  local tag="$1"
  local out="$2"
  local ssh_sock="$3"
  local ssh_mode="$4"
  set +e
  (
    cd "$ROOT"
    PATH="$BIN:$PATH" \
    AEL_EVIDENCE_LOG_PATH="$EVIDENCE_LOG" \
    SSH_AUTH_SOCK="$ssh_sock" \
    SELFTEST_SSHADD_MODE="$ssh_mode" \
    "$GATE" "$tag" "$INPUT"
  ) >"$out" 2>&1
  RUN_RC=$?
  set -e
}

# Case 1: no SSH agent => fail-closed before signed tag creation.
: > "$CALLS"
run_gate "$TAG1" "$OUT_NO_AGENT" "" "loaded"
if [[ "${RUN_RC:-}" -ne 2 ]]; then
  echo "SELFTEST=FAIL reason=NO_AGENT_WRONG_RC rc=${RUN_RC:-NA}"
  exit 2
fi
if ! grep -q "reason=SSH_AGENT_NOT_RUNNING" "$OUT_NO_AGENT"; then
  echo "SELFTEST=FAIL reason=MISSING_NO_AGENT_REASON"
  exit 2
fi
if grep -q "git tag -s" "$CALLS"; then
  echo "SELFTEST=FAIL reason=TAG_SIGN_ATTEMPTED_WITHOUT_AGENT"
  exit 2
fi

# Case 2: agent + loaded key => signed tag path executed.
: > "$CALLS"
run_gate "$TAG2" "$OUT_OK" "/tmp/mock-ssh-agent.sock" "loaded"
if [[ "${RUN_RC:-}" -ne 0 ]]; then
  echo "SELFTEST=FAIL reason=SIGNED_PATH_EXPECTED_GO rc=${RUN_RC:-NA}"
  exit 2
fi
if ! grep -q "TAG_SIGN_STATUS=OK tag=$TAG2" "$OUT_OK"; then
  echo "SELFTEST=FAIL reason=MISSING_TAG_SIGN_STATUS"
  exit 2
fi
if ! grep -q "git tag -s" "$CALLS"; then
  echo "SELFTEST=FAIL reason=TAG_SIGN_NOT_CALLED"
  exit 2
fi
if ! grep -q "git tag -v" "$CALLS"; then
  echo "SELFTEST=FAIL reason=TAG_VERIFY_NOT_CALLED"
  exit 2
fi
if ! grep -q "git push origin $TAG2" "$CALLS"; then
  echo "SELFTEST=FAIL reason=TAG_PUSH_NOT_CALLED"
  exit 2
fi

echo "SELFTEST=PASS"
