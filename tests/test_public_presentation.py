"""Checks for the public entry guides and their existing claim boundaries."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


class PublicPresentationTests(unittest.TestCase):
    def _fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "source"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".pytest_cache"))
        return root

    def _guard(self, root):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/guardrail_public_claims.sh")],
            cwd=root, capture_output=True, text=True,
        )

    def _remove_and_reject(self, root, name, text):
        path = root / name
        before = path.read_text(encoding="utf-8")
        self.assertIn(text, before)
        try:
            path.write_text(before.replace(text, "removed-check-value"), encoding="utf-8")
            result = self._guard(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("[FAIL]", result.stdout)
        finally:
            path.write_text(before, encoding="utf-8")

    def test_entry_links_and_heading_anchors(self):
        for name in ("README.md", "README.fr.md", "docs/INDEX.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for destination in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", text):
                url = urlparse(destination)
                if url.scheme:
                    continue
                target = (ROOT / name).parent / unquote(url.path)
                self.assertTrue(target.is_file(), (name, destination))
                if url.fragment:
                    headings = re.findall(r"^#+ (.+)$", target.read_text(encoding="utf-8"), re.M)
                    anchors = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-")
                               for h in headings}
                    self.assertIn(unquote(url.fragment), anchors)
        for name, headings in (
            ("README.md", ("Install", "Example", "Limits")),
            ("README.fr.md", ("Installation", "Exemple", "Limites")),
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            for heading in headings:
                self.assertIn("## " + heading + "\n", text)

    def test_shared_pinned_install_and_synthetic_example(self):
        texts = [(ROOT / name).read_text(encoding="utf-8")
                 for name in ("README.md", "README.fr.md")]
        blocks = [re.findall(r"```bash\n(.*?)```", text, re.S) for text in texts]
        self.assertEqual(blocks[0], blocks[1])
        self.assertEqual(len(blocks[0]), 2)
        self.assertIn('python -m pip install "aelitium==0.4.0"', blocks[0][0])
        self.assertIn('"model": "synthetic-example"', blocks[0][1])
        for text in texts:
            self.assertTrue(text.startswith("[English](README.md) | [Français](README.fr.md)\n"))
            self.assertNotIn(chr(0x2014), text)
            self.assertNotIn(chr(0x2013), text)

    def test_public_index_does_not_link_internal_records(self):
        text = (ROOT / "docs/INDEX.md").read_text(encoding="utf-8")
        destinations = re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", text)
        for destination in destinations:
            self.assertNotIn("internal/", destination)
            self.assertNotIn("RC_INSTALLATION", destination)
        self.assertIn("D-066 HOLD", text)

    def test_assurance_dimensions_remain_guarded(self):
        root = self._fixture()
        dimensions = (
            "payload_integrity", "binding_field_consistency",
            "invocation_identity_consistency", "invocation_binding_consistency",
            "signature_validity", "trusted_signer_identity", "freshness", "authorization",
        )
        for dimension in dimensions:
            with self.subTest(dimension=dimension):
                self._remove_and_reject(root, "docs/ASSURANCE_RESULT_V1.md", dimension)

    def test_freshness_options_remain_guarded(self):
        root = self._fixture()
        for option in ("--freshness-max-age-seconds", "--freshness-reference-time-utc"):
            with self.subTest(option=option):
                self._remove_and_reject(root, "docs/TRUST_BOUNDARY.md", option)

    def test_comparison_versions_remain_guarded(self):
        root = self._fixture()
        for text in (
            "Comparison basis in v0.3.x: `request_hash` v1",
            "Comparison contract in v0.4.0: `aelitium-compare-v1`",
        ):
            with self.subTest(text=text):
                self._remove_and_reject(root, "docs/CANONICAL_REQUEST.md", text)

    def test_preservation_and_independence_notes_remain_guarded(self):
        root = self._fixture()
        for name, text in (
            ("docs/CANONICALIZATION_SPEC.md",
             "The released v1 parser behavior remains unchanged."),
            ("docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md",
             "It changes no released v0.4.0 package bytes, evidence"),
            ("docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md",
             "No second verifier is implemented on this branch."),
        ):
            with self.subTest(name=name, text=text):
                self._remove_and_reject(root, name, text)

    def test_both_readmes_require_verification_and_privacy_limits(self):
        root = self._fixture()
        for name, text in (
            ("README.md", "It does not prove that an interaction occurred"),
            ("README.md", "Hashes do not anonymize data."),
            ("README.fr.md", "Ce résultat ne prouve ni que l’interaction a eu lieu"),
            ("README.fr.md", "Les empreintes n’anonymisent pas les données."),
        ):
            with self.subTest(name=name, text=text):
                self._remove_and_reject(root, name, text)

    def test_affirmative_overclaims_are_rejected_in_both_readmes(self):
        root = self._fixture()
        for name in ("README.md", "README.fr.md"):
            with self.subTest(name=name):
                path = root / name
                before = path.read_text(encoding="utf-8")
                try:
                    path.write_text(before + "\n" * 10 + "One adapter supports every provider.\n",
                                    encoding="utf-8")
                    result = self._guard(root)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("affirmative public-claim pattern", result.stdout)
                finally:
                    path.write_text(before, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
