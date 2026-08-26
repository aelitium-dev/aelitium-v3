# AELITIUM — Release Process

**Releases are manual.** There is no automated release, tagging, or publication
workflow in this repository. `.github/workflows/` contains only `tests.yml` and
`release-audit.yml`; neither creates a tag, a GitHub Release, or a PyPI upload.
Every step below that changes a published artefact is performed by a human.

The source/package version is `0.3.0`, but `0.3.0` is unreleased: no `v0.3.0`
tag, GitHub Release, or PyPI publication exists. The latest current-line release
and PyPI publication is `0.2.4`; its historical upload used Twine.

---

## Current release line and tag authority

The current release line uses explicit `v0.x` tags. The latest released version is
`v0.2.4`.

**Do not determine the current AELITIUM release using version-sorted tags.**

The repository also contains a `v3.0.0-rc1` … `v3.0.0-rc11` namespace. Those tags
pre-date the version-line reset and are *older* than every `v0.x` tag, but they
sort **above** all of them under `git tag --sort=-v:refname`. Any tool or command
that picks "the highest version tag" will therefore resolve to `v3.0.0-rc11`,
which is not a release of the current line.

Use one of these instead:

```bash
git describe --tags                                    # nearest tag on this history
git for-each-ref --sort=-creatordate refs/tags/v0.*    # current line, newest first
```

Deletion or rewriting of the legacy `v3.0.0-rc*` tags is **not authorized** by
this document. Removing published tags changes observable history; if it is ever
done, it is a separate governance decision.

---

## Release authority

An actual release is manual. Explicit human approval is required before each of
these actions: creating the `v0.3.0` tag, creating its GitHub Release, and
publishing `0.3.0` to PyPI. Merged documentation, a source-version change, or
green CI must never be interpreted as release authorization.

Once separately authorized, the intended release includes all three publication
surfaces: an annotated git tag, a GitHub Release, and a PyPI publication.

---

## Pre-1.0 stability policy

Within the `0.3.x` line, patch releases must not deliberately introduce breaking
changes to existing public assurance dimension names, assurance states, or
already-versioned public identifiers/contracts. An incompatible public-contract
change requires a future pre-1.0 **minor** release with explicit migration notes.
This is a scoped `0.3.x` rule, not a claim of full 1.0-style backwards
compatibility.

---

## Release steps

### 1. Merge public-contract and release-readiness work

Reconcile the documentation that describes the release before the release exists:

- `CHANGELOG.md` — the `[Unreleased]` section must cover all material work on the
  line, including a `### Breaking` section where the verification or capture
  surface changed.
- `SECURITY.md` — supported-version table, and any support-transition decision for
  the outgoing line.
- `docs/ONE_PAGER.md` — version and release wording.

Review and merge this work to `main`. Do not date the Changelog heading in the
readiness work: that would record a release before one exists.

### 2. Obtain explicit human release authorization

Stop at a human checkpoint. Approval must explicitly cover the tag, GitHub
Release, and PyPI publication; it is not inferred from step 1 or CI. At this
checkpoint, also confirm the release operator's repository/PyPI access and that
PyPI Trusted Publishing is configured and available.

### 3. Create the release commit required by the current Changelog process

On `main`, convert the `[Unreleased]` heading in `CHANGELOG.md` to a dated
`## [X.Y.Z] — <date>` heading. The date is the date intended for the tag. Commit
that change, then record that commit's exact SHA as `release_commit_sha`.

For `v0.3.0`, this dated Changelog commit is required and the tag must target
`release_commit_sha`; it must not target the earlier readiness-PR merge commit or
an ambiguously named “merge SHA.” This is the point at which the repository first
asserts that the version was released, so do not create it without step 2.

### 4. Run required verification on `release_commit_sha`

The readiness pull request workflows must have been green, and the equivalent
gates must be rerun against `release_commit_sha` before tagging:

- `tests` — `python -m unittest discover -s tests` on Python 3.10, 3.11 and 3.12
  with provider extras (`pip install -e ".[all]"`). The job **fails if any test is
  skipped**, so provider adapter tests cannot silently stop executing. It then runs
  `./scripts/run_test_matrix.sh`.
- `release-audit` — `./scripts/audit_release.sh`, which runs the public-claims
  guardrail, the capture-adapter call-time claim check, and CLI help validation.

Locally, the same gates are:

```bash
python -m unittest discover -s tests
./scripts/run_test_matrix.sh
./scripts/audit_release.sh
```

Running the suite locally without the `anthropic` extra installed will skip the
Anthropic adapter tests. CI is the authority for a zero-skip run. Confirm the
working tree is clean and `HEAD` equals the recorded `release_commit_sha` before
tagging.

### 5. Create an annotated tag at `release_commit_sha`

Tags on the current line are annotated:

```bash
git tag -a vX.Y.Z -m "AELITIUM vX.Y.Z" <release_commit_sha>
git cat-file -t vX.Y.Z
git show --no-patch vX.Y.Z
```

An annotated, unsigned tag is sufficient for `v0.3.0`; cryptographic tag signing
is not a release blocker. `git tag -v` verifies a cryptographic signature and
must not be used as the expected validation command for an unsigned annotated
tag. Introducing signed tags later requires a separate process and key-management
decision.

### 6. Push the single tag

Push the single tag explicitly:

```bash
git push origin vX.Y.Z
```

Do **not** use `git push --tags`. That would push the legacy `v3.0.0-rc*`
namespace along with the release tag.

### 7. Create the GitHub Release

Create the GitHub Release from the pushed tag. The release body is the
corresponding `CHANGELOG.md` entry, including its `### Breaking` section.

### 8. Publish to PyPI through Trusted Publishing

PyPI Trusted Publishing is the preferred publication mechanism for `0.3.0`.
Reconfirm operator access and the configured publisher at the actual release
checkpoint. If Trusted Publishing is not configured or available, **stop for a
human decision**; do not silently fall back to Twine. The fact that the historical
`0.2.4` upload used Twine does not authorize that fallback.

PyPI publication remains a separately approved action and is not implied by the
tag or GitHub Release.

### 9. Perform post-publication verification

Confirm that the remote annotated tag resolves to `release_commit_sha`, the
GitHub Release targets that tag, and PyPI serves exactly the intended `0.3.0`
artifact and metadata. Record any discrepancy and stop instead of attempting an
unapproved replacement release.

---

## Legacy authority scripts

`scripts/authority_status.sh`, `scripts/release_rc.sh` and `scripts/gate_release.sh`
implement an earlier Machine-A / Machine-B release-authority flow. **They cannot
produce a release of the current line as written**, for reasons that are properties
of the scripts themselves:

| Script | Constraint |
|---|---|
| `scripts/authority_status.sh` | Requires `AEL_MACHINE=B` and a live `git ls-remote` probe; otherwise exits `AUTHORITY_STATUS=NO_GO`. |
| `scripts/release_rc.sh` | Accepts only tags matching `^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$`. A final tag such as `v0.3.0` is rejected with `INVALID_TAG_FORMAT`. |
| `scripts/gate_release.sh` | Fail-closed on evidence-log validation against `governance/logs/EVIDENCE_LOG.md` (override: `AEL_EVIDENCE_LOG_PATH`). That path **does not exist** in this repository, so the gate returns `RELEASE_STATUS=NO_GO reason=EVIDENCE_INVALID`. It also drives the legacy `engine/cli.py` rather than `engine.ai_cli`. |
| `scripts/gate_release.sh` | Never creates a tag. It reports `TAG_STATUS=SKIPPED reason=AUTHORITY_ONLY`; tag creation was always manual. |

These scripts are retained as-is. This document does not restore, relocate, or
substitute the missing evidence-log path, and no replacement governance path is
defined here. Reinstating that flow — or retiring it — is a separate decision.
