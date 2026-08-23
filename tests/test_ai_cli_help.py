import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDALONE = REPO_ROOT / "scripts" / "aelitium_verify_standalone.py"


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

    def _standalone_help(self) -> str:
        cp = subprocess.run(
            [sys.executable, str(STANDALONE), "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        return " ".join(cp.stdout.split())

    def _assert_exact_freshness_policy_options(self, help_text: str) -> None:
        self.assertIn("--freshness-max-age-seconds SECONDS", help_text)
        self.assertIn("--freshness-reference-time-utc UTC_TIME", help_text)
        self.assertIn("YYYY-MM-DDTHH:MM:SSZ", help_text)
        normalized_help = " ".join(help_text.split())
        self.assertIn(
            "Explicit UTC reference time in YYYY-MM-DDTHH:MM:SSZ form; "
            "requires --freshness-max-age-seconds",
            normalized_help,
        )
        format_match = re.search(
            r"Explicit UTC reference time in (\S+) form",
            normalized_help,
        )
        self.assertIsNotNone(format_match)
        documented_format = format_match.group(1)
        self.assertEqual(documented_format, "YYYY-MM-DDTHH:MM:SSZ")
        tokens = help_text.split()
        for forbidden in (
            "--require-freshness",
            "--fresh",
            "--now",
            "--clock-skew",
            "--freshness-tolerance",
        ):
            self.assertNotIn(forbidden, tokens)

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
        self._assert_exact_freshness_policy_options(help_text)

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
        self._assert_exact_freshness_policy_options(help_text)

    def test_standalone_help_exposes_exact_freshness_policy_options(self):
        self._assert_exact_freshness_policy_options(self._standalone_help())

    def test_non_freshness_commands_reject_freshness_policy_options(self):
        commands = (
            ("compare", "bundle-a", "bundle-b"),
            ("verify-receipt", "--receipt", "receipt.json"),
        )
        options = (
            ("--freshness-max-age-seconds", "60"),
            ("--freshness-reference-time-utc", "2026-03-04T00:01:00Z"),
        )
        for command in commands:
            help_text = self._help(command[0])
            self.assertNotIn("freshness", help_text.lower())
            for option in options:
                with self.subTest(command=command[0], option=option[0]):
                    cp = subprocess.run(
                        [sys.executable, "-m", "engine.ai_cli", *command, *option],
                        cwd=str(REPO_ROOT),
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
                    self.assertIn("unrecognized arguments", cp.stderr)

if __name__ == "__main__":
    unittest.main()
