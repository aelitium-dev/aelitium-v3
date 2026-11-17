#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# 0) Preflight
echo "== preflight =="
git status --porcelain >/dev/null || true

# 1) Ensure .gitignore has runtime artifacts
if ! grep -q "AELITIUM runtime artifacts" .gitignore 2>/dev/null; then
  cat >> .gitignore <<'EOG'

# AELITIUM runtime artifacts (generated; not source-of-truth)
artifacts/results/
release_output/
output/
EOG
  git add .gitignore
  git commit -m "chore: ignore generated artifacts/results and outputs" || true
fi

# 2) Ensure docs exist
mkdir -p docs governance/dashboard inputs artifacts/results artifacts/real_input

# TEST_MATRIX note (best-effort, no duplicate insertion)
if ! grep -q "verify uses --manifest and --evidence" TEST_MATRIX.md 2>/dev/null; then
  perl -0777 -i -pe 's/(2\) Tamper detection.*?\n)/$1\nNOTE: verify uses --manifest and --evidence (not --input).\n/s' TEST_MATRIX.md || true
  git add TEST_MATRIX.md
  git commit -m "tests: note verify flags in test matrix" || true
fi

# Products options
if [ ! -f docs/PRODUCTS_3_OPTIONS.md ]; then
cat > docs/PRODUCTS_3_OPTIONS.md <<'EOD'
# Products — 3 Options (Canonical)

Format per option:
- ICP
- Moat
- Packaging
- Pricing hypothesis
- 7-day feedback loop
- Kill criteria

## Option 1 — Deterministic Offline Bundle Engine
ICP:
- DevSecOps / Platform / Infra teams
Moat:
- A/B authority model + fail-closed gate + offline verify + determinism
Packaging:
- CLI + scripts + governance templates
Pricing hypothesis:
- per-repo subscription + support tier
7-day feedback loop:
- Day1 install+determinism; Day2 tamper; Day3 MachineB verify; Day7 decision
Kill criteria:
- cannot demo determinism+tamper+verify in 10 min

## Option 2 — Evidence-First Release Governance Layer
ICP:
- teams needing audit hygiene without SaaS
Moat:
- mandatory evidence + minimal governance footprint
Packaging:
- drop-in governance/ + scripts/ + docs
Pricing hypothesis:
- per-repo + setup fee optional
7-day feedback loop:
- first real release with evidence + gate
Kill criteria:
- adds bureaucracy without reducing review/audit time

## Option 3 — AELITIUM Lite (Indie Integrity Kit)
ICP:
- solo devs / OSS maintainers
Moat:
- zero-friction deterministic release habit
Packaging:
- one-command template + local dashboard
Pricing hypothesis:
- one-time license or donationware + paid support
7-day feedback loop:
- ship one tagged release with evidence
Kill criteria:
- setup > 30 min or breaks on Windows+WSL
EOD
  git add docs/PRODUCTS_3_OPTIONS.md
  git commit -m "docs: add canonical products 3 options" || true
fi

# Market feedback log
if [ ! -f docs/MARKET_FEEDBACK_LOG.md ]; then
cat > docs/MARKET_FEEDBACK_LOG.md <<'EOD'
# Market Feedback Log (Canonical)

Template (copy per entry):
- Date (UTC):
- Person/Org:
- Channel:
- ICP fit (Y/N):
- Claim tested:
- Demo shown (Y/N):
- Result (quote or observation):
- Next action:
- Decision (continue/kill/pivot):

Entries:
EOD
  git add docs/MARKET_FEEDBACK_LOG.md
  git commit -m "docs: add market feedback log template" || true
fi

# 7-day loop
if [ ! -f docs/PHASE4_7DAY_LOOP.md ]; then
cat > docs/PHASE4_7DAY_LOOP.md <<'EOD'
# Phase 4 — 7-Day Feedback Loop (Canonical)

Goal: validate product option(s) without governance drift.

Every week:
- 5 conversations (ICP targets)
- 2 demos (determinism + tamper + authority verify)
- 1 decision (continue/kill/pivot) logged in Notion and mirrored here as a short note

Rule:
- No claims are "official" unless mirrored in this repo.
EOD
  git add docs/PHASE4_7DAY_LOOP.md
  git commit -m "docs: add phase4 7-day loop" || true
fi

# Landing mock (non-authoritative)
if [ ! -f governance/dashboard/landing_mock.html ]; then
cat > governance/dashboard/landing_mock.html <<'EOD'
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AELITIUM — Deterministic Releases (Mock)</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 820px; margin: 40px auto; line-height: 1.4; }
    code { background: #f3f3f3; padding: 2px 6px; border-radius: 6px; }
    .box { border: 1px solid #ddd; border-radius: 12px; padding: 16px; margin: 16px 0; }
  </style>
</head>
<body>
  <h1>AELITIUM</h1>
  <p>Deterministic bundle + offline verification + fail-closed release gate.</p>

  <div class="box">
    <h2>What you get</h2>
    <ul>
      <li>2 runs = same hash (determinism)</li>
      <li>Tamper ⇒ INVALID</li>
      <li>Machine B verifies Machine A artifacts</li>
      <li>No release without Evidence Log</li>
    </ul>
  </div>

  <div class="box">
    <h2>Canonical commands</h2>
    <p><code>./scripts/bundle_determinism_check.sh inputs/minimal_input_v1.json</code></p>
    <p><code>python3 engine/cli.py pack --input inputs/minimal_input_v1.json --out artifacts/results/bundle.ael</code></p>
    <p><code>python3 engine/cli.py verify --manifest bundle.ael/manifest.json --evidence bundle.ael/evidence_pack.json</code></p>
    <p><code>./scripts/gate_release.sh vX.Y.Z inputs/minimal_input_v1.json</code></p>
  </div>

  <p><small>This page is a local mock. Source of truth is the repo.</small></p>
</body>
</html>
EOD
  git add governance/dashboard/landing_mock.html
  git commit -m "dashboard: add landing mock (non-authoritative)" || true
fi

echo "== done =="
git status
