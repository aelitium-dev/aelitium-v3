#!/usr/bin/env python3
import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "engine" / "cli.py"
INPUT = ROOT / "tests" / "fixtures" / "input_min.json"
MAKE_ZIP = ROOT / "scripts" / "make_release_zip.sh"
VERIFY_ZIP = ROOT / "scripts" / "verify_release_zip.sh"
TEST_KEY = (ROOT / "tests" / "fixtures" / "ed25519_test_private_key.b64").read_text(
    encoding="utf-8"
).strip()


def signing_env() -> dict:
    env = os.environ.copy()
    env["AEL_ED25519_PRIVKEY_B64"] = TEST_KEY
    env["AEL_ED25519_KEY_ID"] = "test-key-2026q1"
    return env


def run_cmd(*args: str, env: dict | None = None, cwd: Path | None = None):
    return subprocess.run(
        list(args),
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def make_bundle(dest: Path):
    cp = run_cmd(
        "python3",
        str(CLI),
        "pack",
        "--input",
        str(INPUT),
        "--out",
        str(dest),
        env=signing_env(),
    )
    if cp.returncode != 0:
        raise AssertionError(cp.stdout + cp.stderr)


class TestSignature(unittest.TestCase):
    def test_verify_rejects_missing_signature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            vk_path = bundle / "verification_keys.json"
            vk = json.loads(vk_path.read_text(encoding="utf-8"))
            vk["signatures"] = []
            vk_path.write_text(json.dumps(vk, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def test_verify_rejects_bad_signature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["canonicalization"] = "tampered"
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

    def test_verify_rejects_wrong_public_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            make_bundle(bundle)

            vk_path = bundle / "verification_keys.json"
            vk = json.loads(vk_path.read_text(encoding="utf-8"))
            vk["keys"][0]["public_key_b64"] = base64.b64encode(b"\x11" * 32).decode("ascii")
            vk_path.write_text(json.dumps(vk, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def test_offline_verify_zip_signature_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = Path(tmpdir) / "bundle"
            outdir = Path(tmpdir) / "dist"
            make_bundle(bundle)

            env = os.environ.copy()
            env["AEL_ZIP_PAYLOAD_DIR"] = str(bundle)
            env["AEL_ZIP_OUTDIR"] = str(outdir)

            cp_build = run_cmd("bash", str(MAKE_ZIP), env=env)
            self.assertEqual(cp_build.returncode, 0, cp_build.stdout + cp_build.stderr)

            cp_verify = run_cmd(
                "bash",
                str(VERIFY_ZIP),
                str(outdir / "release_output.zip"),
                str(outdir / "release_metadata.json"),
            )
            self.assertEqual(cp_verify.returncode, 0, cp_verify.stdout + cp_verify.stderr)
            self.assertIn("VERIFY_ZIP_STATUS=GO", cp_verify.stdout)


if __name__ == "__main__":
    unittest.main()
