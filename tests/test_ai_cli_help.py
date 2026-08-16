import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

class TestAICLIHelp(unittest.TestCase):
    def _help(self, *args: str) -> str:
        # correr via python -m engine.ai_cli para evitar depender de instalação
        cp = subprocess.run(
            [sys.executable, "-m", "engine.ai_cli", *args, "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        return " ".join(cp.stdout.split())

    def test_ai_cli_help_exit_zero(self):
        self._help()

    def test_root_help_scopes_compare_to_selected_v1_hashes(self):
        help_text = self._help()
        self.assertIn(
            "Compare selected v1 request/response hashes between bundles",
            help_text,
        )
        self.assertNotIn("detect AI model behavior change", help_text)

    def test_verify_help_describes_json_compatibility(self):
        help_text = self._help("verify")
        self.assertIn(
            "Output valid results as JSON; invalid results retain compatibility text",
            help_text,
        )
        self.assertIn(
            "--require-signature Reject bundles without signature material",
            help_text,
        )
        self.assertIn(
            "--require-binding Reject bundles without v1 binding evidence",
            help_text,
        )
        self.assertIn(
            "--trust-store PATH Use an explicit local trusted-signer store "
            "for signer identity evaluation",
            help_text,
        )
        self.assertIn(
            "--require-trusted-signer Reject unless the valid bundle "
            "signature corresponds to a key trusted by the supplied trust "
            "store",
            help_text,
        )

    def test_verify_bundle_help_scopes_present_evidence(self):
        root_help = self._help()
        help_text = self._help("verify-bundle")
        self.assertIn(
            "Verify AI bundle integrity and any present signature/binding evidence",
            root_help,
        )
        self.assertNotIn("hash + signature + binding hash", root_help)
        self.assertIn(
            "Output valid results as JSON; invalid results retain compatibility text",
            help_text,
        )
        self.assertIn(
            "--require-signature Reject bundles without signature material",
            help_text,
        )
        self.assertIn(
            "--require-binding Reject bundles without v1 binding evidence",
            help_text,
        )
        self.assertIn(
            "--trust-store PATH Use an explicit local trusted-signer store "
            "for signer identity evaluation",
            help_text,
        )
        self.assertIn(
            "--require-trusted-signer Reject unless the valid bundle "
            "signature corresponds to a key trusted by the supplied trust "
            "store",
            help_text,
        )

if __name__ == "__main__":
    unittest.main()
