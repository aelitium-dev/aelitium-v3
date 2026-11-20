import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_release_versions.py"
GUARDRAIL_SCRIPT = REPOSITORY_ROOT / "scripts" / "guardrail_public_claims.sh"
CHECKED_FILES = (
    "scripts/check_release_versions.py",
    "pyproject.toml",
    "aelitium/__init__.py",
    ".github/workflows/publish-pypi.yml",
    "README.md",
    "README.fr.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "docs/ONE_PAGER.md",
    "docs/RELEASE_PROCESS.md",
)
PROJECT_VERSION = re.search(
    r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',
    (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    flags=re.MULTILINE,
).group(1)
MISMATCH_VERSION = "9.9.9"


class ReleaseVersionConsistencyTests(unittest.TestCase):
    def _run_check(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )

    def _copy_checked_files(self, root: Path) -> None:
        for relative_path in CHECKED_FILES:
            source = REPOSITORY_ROOT / relative_path
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def test_repository_release_versions_are_consistent(self) -> None:
        result = self._run_check(REPOSITORY_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"package={PROJECT_VERSION} pypi={PROJECT_VERSION} "
            f"github_release=none workflow_release_tag=v{PROJECT_VERSION}",
            result.stdout,
        )

    def test_source_version_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_checked_files(root)
            path = root / "aelitium/__init__.py"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    f'__version__ = "{PROJECT_VERSION}"',
                    f'__version__ = "{MISMATCH_VERSION}"',
                ),
                encoding="utf-8",
            )

            result = self._run_check(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match pyproject.toml", result.stderr)

    def test_workflow_metadata_version_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_checked_files(root)
            path = root / ".github/workflows/publish-pypi.yml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    f'expected = ("aelitium", "{PROJECT_VERSION}")',
                    f'expected = ("aelitium", "{MISMATCH_VERSION}")',
                ),
                encoding="utf-8",
            )

            result = self._run_check(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("expected metadata version", result.stderr)

    def test_active_release_document_version_mismatch_fails(self) -> None:
        publication_text = {
            "README.md": f"**{PROJECT_VERSION}**, available",
            "README.fr.md": f"**{PROJECT_VERSION}**, disponible",
            "SECURITY.md": f"Version `{PROJECT_VERSION}` is available",
            "docs/ONE_PAGER.md": f"Package version **{PROJECT_VERSION}** is available",
            "docs/RELEASE_PROCESS.md": f"Version `{PROJECT_VERSION}` is available",
        }
        for relative_path, original in publication_text.items():
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                text = path.read_text(encoding="utf-8")
                self.assertEqual(text.count(original), 1)
                path.write_text(
                    text.replace(original, original.replace(PROJECT_VERSION, MISMATCH_VERSION)),
                    encoding="utf-8",
                )
                result = self._run_check(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} is missing", result.stderr)

    def test_both_readmes_require_the_published_install_pin(self) -> None:
        for relative_path in ("README.md", "README.fr.md"):
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                text = path.read_text(encoding="utf-8")
                original = f'python -m pip install "aelitium=={PROJECT_VERSION}"'
                self.assertEqual(text.count(original), 1)
                path.write_text(text.replace(original, "python -m pip install aelitium"),
                                encoding="utf-8")
                result = self._run_check(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} is missing release-version text", result.stderr)

    def test_both_readmes_require_the_matching_pypi_url(self) -> None:
        for relative_path in ("README.md", "README.fr.md"):
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                text = path.read_text(encoding="utf-8")
                original = f"https://pypi.org/project/aelitium/{PROJECT_VERSION}/"
                self.assertEqual(text.count(original), 1)
                path.write_text(
                    text.replace(original, original.replace(PROJECT_VERSION, MISMATCH_VERSION)),
                    encoding="utf-8",
                )
                result = self._run_check(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} is missing release-version text", result.stderr)

    def test_workflow_release_tag_version_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_checked_files(root)
            path = root / ".github/workflows/publish-pypi.yml"
            text, count = re.subn(
                r"(github\.event\.release\.tag_name\s*==\s*['\"])v"
                + re.escape(PROJECT_VERSION) + r"(['\"])",
                lambda match: match[1] + "v" + MISMATCH_VERSION + match[2],
                path.read_text(encoding="utf-8"), count=1,
            )
            self.assertEqual(count, 1)
            path.write_text(text, encoding="utf-8")
            result = self._run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("release-tag guards", result.stderr)

    def test_active_documents_require_the_absence_of_a_github_release(self) -> None:
        for relative_path in ("README.md", "README.fr.md", "SECURITY.md",
                              "docs/ONE_PAGER.md", "docs/RELEASE_PROCESS.md"):
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                text = path.read_text(encoding="utf-8")
                pattern = (r"aucune release GitHub\s+n’est actuellement disponible\."
                           if relative_path == "README.fr.md"
                           else r"there is no current\s+GitHub release\.")
                text, count = re.subn(pattern, "[publication status omitted]", text,
                                      flags=re.IGNORECASE)
                self.assertEqual(count, 1)
                path.write_text(text, encoding="utf-8")
                result = self._run_check(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} is missing release-version text", result.stderr)

    def test_stale_claims_fail_even_when_correct_publication_text_remains(self) -> None:
        claims = (
            ("README.md", f"`v{PROJECT_VERSION}` is the current published GitHub and PyPI release."),
            ("README.fr.md", f"`v{PROJECT_VERSION}` est la version actuellement publiée sur GitHub et PyPI."),
            ("SECURITY.md", f"`v{PROJECT_VERSION}` is the current published release."),
            ("docs/ONE_PAGER.md", f"Current published release: **v{PROJECT_VERSION}** on GitHub and **{PROJECT_VERSION}** on PyPI."),
            ("docs/ONE_PAGER.md", f"Current public release surfaces: annotated **v{PROJECT_VERSION}** tag, GitHub Release, and PyPI publication."),
            ("docs/RELEASE_PROCESS.md", f"The current published release is `v{PROJECT_VERSION}`."),
            ("README.md", "A GitHub release is currently available."),
            ("README.fr.md", "Une release GitHub est actuellement disponible."),
            ("README.md", f"Current GitHub release: v{MISMATCH_VERSION}."),
        )
        for relative_path, claim in claims:
            with self.subTest(path=relative_path, claim=claim), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                # Keep the correct status and append a contradictory assertion.
                path.write_text(path.read_text(encoding="utf-8") + "\n" + claim + "\n",
                                encoding="utf-8")
                result = self._run_check(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} contains a stale publication claim", result.stderr)

    def test_public_claims_guardrail_rejects_stale_publication_claims(self) -> None:
        for relative_path, claim in (
            ("README.md", f"`v{PROJECT_VERSION}` is the current published GitHub and PyPI release."),
            ("README.fr.md", f"`v{PROJECT_VERSION}` est la version actuellement publiée sur GitHub et PyPI."),
        ):
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._copy_checked_files(root)
                path = root / relative_path
                path.write_text(path.read_text(encoding="utf-8") + "\n" + claim + "\n",
                                encoding="utf-8")
                result = subprocess.run(["bash", str(GUARDRAIL_SCRIPT)], cwd=root,
                                        check=False, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"{relative_path} contains a stale publication claim", result.stderr)

    def test_missing_french_readme_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_checked_files(root)
            (root / "README.fr.md").unlink()
            result = self._run_check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read README.fr.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
