import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]

class TestAICLIPack(unittest.TestCase):
    def test_pack_writes_artifacts_and_prints_hash(self):
        outdir = ROOT / "release_output" / "ai_pack_test"
        if outdir.exists():
            for p in outdir.glob("*"):
                p.unlink()
        else:
            outdir.mkdir(parents=True, exist_ok=True)

        cp = subprocess.run(
            CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

        lines = [l.strip() for l in cp.stdout.splitlines() if l.strip()]
        self.assertTrue(any(l == "STATUS=OK rc=0" for l in lines), lines)
        self.assertTrue(any(l.startswith("AI_HASH_SHA256=") for l in lines), lines)

        canon = outdir / "ai_canonical.json"
        manifest = outdir / "ai_manifest.json"
        self.assertTrue(canon.exists())
        self.assertTrue(manifest.exists())

        m = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(m.get("schema"), "ai_pack_manifest_v1")
        self.assertIn("ai_hash_sha256", m)

