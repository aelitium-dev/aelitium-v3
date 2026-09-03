# AELITIUM — Release Process

**Releases are human-authorized.** The test and release-audit workflows do not
create a tag, GitHub Release, or PyPI publication. The tag and GitHub Release are
created manually. `.github/workflows/publish-pypi.yml` handles the separately
authorized PyPI publication for a published, non-draft, non-prerelease `v0.4.0`
GitHub Release.

The source/package version is `0.4.0`. The current published release is `v0.4.0`,
available through an annotated tag, a GitHub Release, and PyPI. The preceding
current-line release is `v0.3.0`. The historical `0.2.4` upload used Twine.

---

## Current release line and tag authority

The current release line uses explicit `v0.x` tags. The latest published version
is `v0.4.0`.

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

An actual release is human-authorized. Explicit human approval is required before each
of these actions: creating its tag, creating its GitHub Release, and authorizing
the corresponding PyPI publication. Merged documentation, a source-version
change, or green CI must never be interpreted as release authorization.

Once separately authorized, the intended release includes all three publication
surfaces: an annotated git tag, a GitHub Release, and a PyPI publication.

---

## Pre-1.0 stability policy

The `0.4.x` line is current and supported. The `0.3.x` line is superseded unless
a separate support decision says otherwise.

Within the current supported pre-1.0 line, patch releases must not deliberately
introduce breaking changes to existing public assurance dimension names,
assurance states, or already-versioned public identifiers/contracts. An
incompatible public-contract change requires a future pre-1.0 **minor** release
with explicit migration notes. This is a scoped pre-1.0 policy, not a claim of
full 1.0-style backwards compatibility.

---

## Release steps

### 1. Merge public-contract and release-readiness work

Reconcile the documentation that describes the release before the release exists:

- `CHANGELOG.md` — the `[Unreleased]` section must cover all material work on the
  line, including a prominent breaking/compatibility section where a public
  decision contract, verification surface, or capture surface changed.
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

### 3. Merge the final release-state pull request and record its main SHA

After step 2, final release-state changes may be prepared on a release branch
and reviewed through a pull request before they reach protected `main`. For
`v0.4.0`, the release branch is `release/v0.4.0-final`. Convert the populated
`[Unreleased]` heading in `CHANGELOG.md` to a dated
`## [0.4.0] — <date>` heading and add a fresh empty `[Unreleased]` section above
it for subsequent development. The date is the date intended for the tag. This
is the point at which the repository first asserts that the version was
released, so do not prepare or merge that final state without step 2.

After the final release-state pull request is merged, switch to `main`, pull the
merged `origin/main`, and record the resulting commit:

```bash
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

`release_commit_sha` is the exact `main` `HEAD` commit that first contains the
final dated `[0.4.0]` release state.
A merge commit, squash merge, or rebased commit may be used. In every case, use
the resulting commit on `main`, not the pre-merge release-branch SHA. The commit
type does not determine release authority.

Do not tag the release-readiness PR SHA.
Do not tag the pre-merge `release/v0.4.0-final` branch SHA.
The annotated `v0.4.0` tag must target exactly `release_commit_sha`.

### 4. Run required verification on the exact `main` release commit

The readiness and final release-state pull request workflows must have been
green. After the final pull request is merged, rerun the full release gates
against the exact `main` `HEAD` recorded as `release_commit_sha` before tagging:

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
git diff --check
```

Running the suite locally without the `anthropic` extra installed will skip the
Anthropic adapter tests. CI is the authority for a zero-skip run. Confirm
`HEAD == release_commit_sha` and that the working tree is clean before tagging.
The pull request's earlier checks do not replace this rerun against the exact
commit that will be tagged.

### 5. Create an annotated tag at `release_commit_sha`

Tags on the current line are annotated:

```bash
git tag -a vX.Y.Z -m "AELITIUM vX.Y.Z" <release_commit_sha>
git cat-file -t vX.Y.Z
git show --no-patch vX.Y.Z
```

An annotated, unsigned tag is sufficient for `v0.4.0`; cryptographic tag signing
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
corresponding `CHANGELOG.md` entry, including its
`### Breaking / Compatibility` section.

### 8. Publish to PyPI through Trusted Publishing

PyPI Trusted Publishing is the preferred publication mechanism. For `v0.4.0`,
publishing the non-draft, non-prerelease GitHub Release triggers
`.github/workflows/publish-pypi.yml`. The workflow accepts only the `v0.4.0` tag,
verifies distribution metadata for `aelitium` `0.4.0`, and uploads through PyPI
Trusted Publishing.

PyPI publication remains a separately approved action: authorization to publish
the GitHub Release must explicitly include the resulting PyPI workflow. Reconfirm
operator access and the configured publisher at the actual release checkpoint.
If Trusted Publishing is not configured or available, **stop for a human
decision**; do not silently fall back to Twine. The fact that the historical
`0.2.4` upload used Twine does not authorize that fallback. A future version must
update and review the workflow's version-specific guards before publication.

### 9. Perform post-publication verification

Confirm that the remote annotated tag resolves to `release_commit_sha`, the
GitHub Release targets that tag, and PyPI serves exactly the intended version's
artifact and metadata. Record any discrepancy and stop instead of attempting an
unapproved replacement release.

For `v0.4.0`, also confirm that the published wheel reports
`aelitium.__version__ == "0.4.0"`, `aelitium compare --help` exposes
`--require-invocation-evidence` and `--legacy-request-hash-v1`, and an offline
comparison reports `COMPARISON_CONTRACT=aelitium-compare-v1`.

---

## Legacy authority scripts

`scripts/authority_status.sh`, `scripts/release_rc.sh` and `scripts/gate_release.sh`
implement an earlier Machine-A / Machine-B release-authority flow. **They cannot
produce a release of the current line as written**, for reasons that are properties
of the scripts themselves:

| Script | Constraint |
|---|---|
| `scripts/authority_status.sh` | Requires `AEL_MACHINE=B` and a live `git ls-remote` probe; otherwise exits `AUTHORITY_STATUS=NO_GO`. |
| `scripts/release_rc.sh` | Accepts only tags matching `^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$`. A final tag such as `v0.4.0` is rejected with `INVALID_TAG_FORMAT`. |
| `scripts/gate_release.sh` | Fail-closed on evidence-log validation against `governance/logs/EVIDENCE_LOG.md` (override: `AEL_EVIDENCE_LOG_PATH`). That path **does not exist** in this repository, so the gate returns `RELEASE_STATUS=NO_GO reason=EVIDENCE_INVALID`. It also drives the legacy `engine/cli.py` rather than `engine.ai_cli`. |
| `scripts/gate_release.sh` | Never creates a tag. It reports `TAG_STATUS=SKIPPED reason=AUTHORITY_ONLY`; tag creation was always manual. |

These scripts are retained as-is. This document does not restore, relocate, or
substitute the missing evidence-log path, and no replacement governance path is
defined here. Reinstating that flow — or retiring it — is a separate decision.
