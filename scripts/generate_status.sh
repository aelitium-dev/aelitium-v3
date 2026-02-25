#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PHASE="Phase 3 — Enterprise Determinism"
HEAD_COMMIT="$(git rev-parse HEAD)"
LAST_TAG="$(git describe --tags --abbrev=0 2>/dev/null || echo NONE)"
DATE_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

REPRO_HASH="$(python3 engine/cli.py repro --input tests/fixtures/input_min.json 2>/dev/null | grep hash= | sed 's/.*hash=//' | awk '{print $1}' || echo UNKNOWN)"

cat > governance/dashboard/STATUS.md <<EOF
# AELITIUM Governance Dashboard

## 🔒 Current Phase
$PHASE

Last tag: $LAST_TAG
Last commit: $HEAD_COMMIT
Generated at: $DATE_UTC

---

## 🧪 Determinism
Repro hash: $REPRO_HASH

---

## 🚦 Discipline
- Working tree must be clean
- Tag must match HEAD
- Machine B validation required

EOF

echo "STATUS.md updated"
