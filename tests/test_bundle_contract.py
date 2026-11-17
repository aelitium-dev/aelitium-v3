#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "engine" / "cli.py"
OFFLINE_VERIFY = ROOT / "scripts" / "offline_verify.sh"
INPUT = ROOT / "tests" / "fixtures" / "input_min.json"
TEST_KEY = (ROOT / "tests" / "fixtures" / "ed25519_test_private_key.b64").read_text(
    encoding="utf-8"
).strip()

def run_cmd(*args: str, env: dict | None = None):
    return subprocess.run(
        list(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def make_bundle(dest: Path):
    env = os.environ.copy()
    env["AEL_ED25519_PRIVKEY_B64"] = TEST_KEY
    env["AEL_ED25519_KEY_ID"] = "test-key-2026q1"
    cp = run_cmd(
        "python3",
        str(CLI),
        "pack",
        "--input",
        str(INPUT),
        "--out",
        str(dest),
        env=env,
    )
    if cp.returncode != 0:
        raise AssertionError(cp.stdout + cp.stderr)


class TestBundleContract(unittest.TestCase):
    def test_manifest_includes_bundle_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("bundle_schema"), "1.1")

    def test_verify_rejects_unknown_bundle_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["bundle_schema"] = "9.9"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            cp = run_cmd(
                "python3",
                str(CLI),
                "verify",
                "--manifest",
                str(manifest_path),
                "--evidence",
                str(bundle / "evidence_pack.json"),
            )
            self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
            self.assertIn("STATUS=INVALID", cp.stdout)

    def test_verify_rejects_missing_verification_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)
            (bundle / "verification_keys.json").unlink()

            cp = run_cmd(
                "python3",
                str(CLI),
                "verify",
                "--manifest",
                str(bundle / "manifest.json"),
                "--evidence",
                str(bundle / "evidence_pack.json"),
            )
            self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
            self.assertIn("STATUS=INVALID", cp.stdout)

    def test_offline_verify_rejects_extra_root_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)
            (bundle / "extra.txt").write_text("unexpected\n", encoding="utf-8")

            cp = run_cmd("bash", str(OFFLINE_VERIFY), str(bundle))
            self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
            self.assertIn("BUNDLE_LAYOUT_INVALID", cp.stdout)

    def test_offline_verify_rejects_nested_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            nested = bundle / "nested"
            nested.mkdir()
            shutil.move(str(bundle / "manifest.json"), str(nested / "manifest.json"))

            cp = run_cmd("bash", str(OFFLINE_VERIFY), str(bundle))
            self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
            self.assertIn("BUNDLE_LAYOUT_INVALID", cp.stdout)


if __name__ == "__main__":
    unittest.main()
