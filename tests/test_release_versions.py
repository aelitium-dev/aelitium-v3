import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_release_versions.py"
CHECKED_FILES = (
    "pyproject.toml",
    "aelitium/__init__.py",
    ".github/workflows/publish-pypi.yml",
    "README.md",
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
            f"package={PROJECT_VERSION} release_tag=v{PROJECT_VERSION}",
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_checked_files(root)
            path = root / "docs/ONE_PAGER.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    f"**{PROJECT_VERSION}** on PyPI",
                    f"**{MISMATCH_VERSION}** on PyPI",
                ),
                encoding="utf-8",
            )

            result = self._run_check(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/ONE_PAGER.md is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
