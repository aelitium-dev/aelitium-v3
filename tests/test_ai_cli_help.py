import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

class TestAICLIHelp(unittest.TestCase):
    def test_ai_cli_help_exit_zero(self):
        # correr via python -m engine.ai_cli para evitar depender de instalação
        cp = subprocess.run(
            [sys.executable, "-m", "engine.ai_cli", "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

if __name__ == "__main__":
    unittest.main()
