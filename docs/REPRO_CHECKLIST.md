# Repro Checklist (Canonical)

This checklist is mandatory for any release.

## Machine A (DEV)

- [ ] Clean tree (git status clean)
- [ ] Pack/build from clean state
- [ ] Determinism check: run1 == run2 (same hash)

## Transfer

- [ ] Bundle transferred to Machine B without modification

## Machine B (AUTHORITY)

- [ ] Verify PASS
- [ ] Repro PASS
- [ ] Tamper test: modified bundle => INVALID (expected)

## Release Discipline

- [ ] Gate executed (fail-closed)
- [ ] Tag created only on PASS
- [ ] Evidence Log entry written
- [ ] Git tree clean at tag time

If any CRITICAL item fails → release blocked.
