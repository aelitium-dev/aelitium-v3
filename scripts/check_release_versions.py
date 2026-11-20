#!/usr/bin/env python3
"""Check version agreement and documented publication state without network access."""

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
            f"**{project_version}**, available on "
            f"[PyPI](https://pypi.org/project/aelitium/{project_version}/)",
            "there is no current GitHub release.",
            f'python -m pip install "aelitium=={project_version}"',
        ),
        "README.fr.md": (
            f"**{project_version}**, disponible sur "
            f"[PyPI](https://pypi.org/project/aelitium/{project_version}/)",
            "aucune release GitHub n’est actuellement disponible.",
            f'python -m pip install "aelitium=={project_version}"',
        ),
        "CHANGELOG.md": (
            "## [Unreleased]",
            f"## [{project_version}] — ",
            f"source/package version is `{project_version}`",
        ),
        "SECURITY.md": (
            f"Version `{project_version}` is available on PyPI.",
            "There is no current GitHub release.",
            f"| {major}.{minor}.x   | Current supported line "
            f"(latest PyPI release: `{project_version}`) | ✅ |",
        ),
        "docs/ONE_PAGER.md": (
            f"Package version **{project_version}** is available on PyPI.",
            "There is no current GitHub release.",
            f"Latest PyPI release: **{project_version}**",
        ),
        "docs/RELEASE_PROCESS.md": (
            f"source/package version is `{project_version}`",
            f"Version `{project_version}` is available on PyPI.",
            "There is no current GitHub release.",
            f"workflow accepts only the `v{project_version}` tag",
            f"metadata for `aelitium` `{project_version}`",
        ),
    }
    # Historical changelog entries and future tag-publication instructions are
    # retained. Reject affirmative current-release claims in active documents,
    # even when the required correct publication text is also present.
    version_pattern = r"v?[0-9]+\.[0-9]+\.[0-9]+"
    stale_claim_patterns = (
        rf"\b{version_pattern} is the current (?:published )?"
        r"(?:GitHub(?: and PyPI)? )?release\b",
        rf"\bcurrent published release(?: is|:)\s*{version_pattern}\b",
        rf"\bcurrent (?:published )?GitHub release(?: is|:)\s*{version_pattern}\b",
        rf"\b{version_pattern} est la version actuellement publiée sur GitHub\b",
        r"\bcurrent public release surfaces:\s*annotated\b",
        r"\b(?:a|the) GitHub release is (?:currently )?available\b",
        r"\bune release GitHub (?:est|reste) (?:actuellement )?disponible\b",
    )
    for relative_path, literals in expected_literals.items():
        contents = _read(root, relative_path)
        normalized = " ".join(contents.split())
        if relative_path != "CHANGELOG.md":
            plain_text = normalized.replace("`", "").replace("*", "")
            if any(re.search(pattern, plain_text, flags=re.IGNORECASE)
                   for pattern in stale_claim_patterns):
                raise VersionConsistencyError(
                    f"{relative_path} contains a stale publication claim"
                )
        for literal in literals:
            if " ".join(literal.split()) not in normalized:
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
        f"package={version} pypi={version} github_release=none "
        f"workflow_release_tag=v{version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
