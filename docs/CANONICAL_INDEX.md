
---

## A/B Synchronization Model (Canonical)

Default mode:
- Machine A pushes to remote.
- Machine B fetches/pulls before any verification.
- Fast, daily workflow.

Authority mode (offline / audit / release-critical):
- Machine A creates git bundle + sha256.
- Machine B verifies sha256 and applies bundle.
- Evidence Log must record bundle sha256.
- Used for high-integrity release validation.

Rule:
Machine B never verifies untracked or manually copied state.
Only remote-sync or git-bundle state is considered authoritative.

