#!/usr/bin/env python3
"""Check released-version agreement without duplicating a version constant."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


class VersionConsistencyError(ValueError):
    """Raised when an authoritative release surface disagrees."""


def _read(root: Path, relative_path: str) -> str:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VersionConsistencyError(f"cannot read {relative_path}: {exc}") from exc


def _single_match(pattern: str, text: str, label: str) -> str:
    matches = re.findall(pattern, text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise VersionConsistencyError(
            f"expected exactly one {label}, found {len(matches)}"
        )
    return matches[0]


def check_release_versions(root: Path) -> str:
    pyproject = _read(root, "pyproject.toml")
    source = _read(root, "aelitium/__init__.py")
    workflow = _read(root, ".github/workflows/publish-pypi.yml")

    project_version = _single_match(
        r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',
        pyproject,
        "[project] version declaration",
    )
    source_version = _single_match(
        r'^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',
        source,
        "aelitium.__version__ declaration",
    )
    if source_version != project_version:
        raise VersionConsistencyError(
            "aelitium.__version__ "
            f"({source_version}) does not match pyproject.toml ({project_version})"
        )

    workflow_versions = re.findall(
        r"github\.event\.release\.tag_name\s*==\s*['\"]v([^'\"]+)['\"]",
        workflow,
    )
    if len(workflow_versions) != 2:
        raise VersionConsistencyError(
            "expected exactly two publish-pypi release-tag guards, "
            f"found {len(workflow_versions)}"
        )
    if any(version != project_version for version in workflow_versions):
        raise VersionConsistencyError(
            "publish-pypi release-tag guards "
            f"({workflow_versions}) do not both match pyproject.toml ({project_version})"
        )

    metadata_version = _single_match(
        r'expected\s*=\s*\(\s*["\']aelitium["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
        workflow,
        "publish-pypi expected metadata tuple",
    )
    if metadata_version != project_version:
        raise VersionConsistencyError(
            "publish-pypi expected metadata version "
            f"({metadata_version}) does not match pyproject.toml ({project_version})"
        )

    major, minor, _patch = project_version.split(".")
    expected_literals = {
        "README.md": (
            f"`v{project_version}` is the current published GitHub and PyPI release",
            f"`pip install aelitium` installs AELITIUM {project_version}",
        ),
        "CHANGELOG.md": (
            "## [Unreleased]",
            f"## [{project_version}] — ",
            f"source/package version is `{project_version}`",
        ),
        "SECURITY.md": (
            f"| {major}.{minor}.x   | Current published line (latest release: `v{project_version}`) | ✅ |",
        ),
        "docs/ONE_PAGER.md": (
            f"Current published release: **v{project_version}** on GitHub and **{project_version}** on PyPI",
        ),
        "docs/RELEASE_PROCESS.md": (
            f"source/package version is `{project_version}`",
            f"current published release is `v{project_version}`",
            f"workflow accepts only the `v{project_version}` tag",
            f"metadata for `aelitium` `{project_version}`",
        ),
    }
    for relative_path, literals in expected_literals.items():
        contents = _read(root, relative_path)
        for literal in literals:
            if literal not in contents:
                raise VersionConsistencyError(
                    f"{relative_path} is missing release-version text: {literal}"
                )

    return project_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check package, workflow, and active release-document version agreement."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args(argv)

    try:
        version = check_release_versions(args.root.resolve())
    except VersionConsistencyError as exc:
        print(f"[FAIL] Release version consistency: {exc}", file=sys.stderr)
        return 1

    print(
        "[PASS] Release version consistency: "
        f"package={version} release_tag=v{version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
