# AELITIUM — Release Process

**Releases are manual.** There is no automated release, tagging, or publication
workflow in this repository. `.github/workflows/` contains only `tests.yml` and
`release-audit.yml`; neither creates a tag, a GitHub Release, or a PyPI upload.
Every step below that changes a published artefact is performed by a human.

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

## Release steps

### 1. Release-readiness pull request

Reconcile the documentation that describes the release before the release exists:

- `CHANGELOG.md` — the `[Unreleased]` section must cover all material work on the
  line, including a `### Breaking` section where the verification or capture
  surface changed.
- `SECURITY.md` — supported-version table, and any support-transition decision for
  the outgoing line.
- `docs/ONE_PAGER.md` — version and release wording.

Open this as a pull request against `main`.

### 2. CI green

Both workflows must be green on the pull request:

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
Anthropic adapter tests. CI is the authority for a zero-skip run.

### 3. Merge to main

Merge the release-readiness pull request.

### 4. Release commit

On `main`, convert the `[Unreleased]` heading in `CHANGELOG.md` to a dated
`## [X.Y.Z] — <date>` heading. The date recorded is the date the tag is created.

This is the point at which the repository first asserts that the version was
released, and it must be immediately followed by step 6. Do not date the heading
in the readiness pull request — that would record a release that has not happened.

### 5. Determine the merge SHA

```bash
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
```

Confirm the working tree is clean and that `HEAD` matches `origin/main`.

### 6. Annotated tag

Tags on the current line are annotated:

```bash
git tag -a vX.Y.Z -m "AELITIUM vX.Y.Z" <merge-sha>
git tag -v vX.Y.Z    # or: git show vX.Y.Z
```

### 7. Push the tag

Push the single tag explicitly:

```bash
git push origin vX.Y.Z
```

Do **not** use `git push --tags`. That would push the legacy `v3.0.0-rc*`
namespace along with the release tag.

### 8. GitHub Release

Create the GitHub Release from the pushed tag. The release body is the
corresponding `CHANGELOG.md` entry, including its `### Breaking` section.

### 9. PyPI publication — gated

**Do not publish to PyPI until ownership of the `aelitium` project name is
independently verified.** The repository records the PyPI `v0.2.4` claim as not
externally verified. Publication is a separate, explicitly authorized step and is
not implied by tagging or by creating a GitHub Release.

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
