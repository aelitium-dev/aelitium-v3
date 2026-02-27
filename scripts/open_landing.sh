#!/usr/bin/env bash
set -euo pipefail
p="$(wslpath -w ~/aelitium-v3/governance/dashboard/landing_mock.html)"
cmd.exe /c start "" "$p" >/dev/null 2>&1 || {
  echo "Open manually: $p"
}
