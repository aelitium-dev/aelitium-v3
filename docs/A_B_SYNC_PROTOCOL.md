# A/B Sync Protocol (Canonical)

Machine A = DEV
Machine B = AUTHORITY

Rule:
Machine B only verifies code obtained via:
1) Remote sync (git fetch/pull), or
2) Offline bundle sync (git bundle + sha256 recorded)

## Mode 1 — Remote (default)

Machine A:
- git push origin main --tags

Machine B:
- git fetch --all --tags
- git checkout main
- git pull --ff-only

## Mode 2 — Offline Authority (when needed)

Machine A:
- git bundle create <path>/aelitium-v3.bundle --all
- sha256sum <path>/aelitium-v3.bundle > <path>/aelitium-v3.bundle.sha256

Machine B:
- sha256sum -c <path>/aelitium-v3.bundle.sha256
- git fetch <path>/aelitium-v3.bundle --tags
- git checkout main
- git reset --hard FETCH_HEAD

Evidence:
Record which mode was used + bundle sha256 when Mode 2.
