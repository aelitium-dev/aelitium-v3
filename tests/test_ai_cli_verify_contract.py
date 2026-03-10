import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]
HASH_RE = re.compile(r"^AI_HASH_SHA256=([0-9a-f]{64})$")


def _pack(outdir: Path):
    subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True, check=True, cwd=ROOT,
    )


def _verify(outdir: Path):
    return subprocess.run(
        CLI + ["verify", "--out", str(outdir)],
        capture_output=True, text=True, cwd=ROOT,
    )


class TestVerifyContract(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        _pack(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    # --- VALID path ---

    def test_valid_exit_code_zero(self):
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_stdout_exactly_three_lines(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(len(lines), 3, f"Expected 3 lines, got: {lines}")

    def test_valid_first_line(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[0], "STATUS=VALID rc=0")

    def test_valid_second_line_is_hash(self):
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertRegex(lines[1], HASH_RE)

    def test_valid_third_line_is_signature_none(self):
        # Bundles produced by `pack` have no signing key → SIGNATURE=NONE
        r = _verify(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[2], "SIGNATURE=NONE")

    def test_valid_hash_matches_pack_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            pack_r = subprocess.run(
                CLI + ["pack", "--input", str(FIXTURE), "--out", str(p)],
                capture_output=True, text=True, cwd=ROOT,
            )
            pack_hash = next(
                l for l in pack_r.stdout.splitlines() if l.startswith("AI_HASH_SHA256=")
            )
            verify_r = _verify(p)
            verify_hash = next(
                l for l in verify_r.stdout.splitlines() if l.startswith("AI_HASH_SHA256=")
            )
            self.assertEqual(pack_hash, verify_hash)

    # --- INVALID: missing files ---

    def test_missing_canonical_gives_rc2(self):
        (self.outdir / "ai_canonical.json").unlink()
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATUS=INVALID", r.stdout)
        self.assertIn("reason=MISSING_CANONICAL", r.stdout)

    def test_missing_manifest_gives_rc2(self):
        (self.outdir / "ai_manifest.json").unlink()
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATUS=INVALID", r.stdout)
        self.assertIn("reason=MISSING_MANIFEST", r.stdout)

    # --- INVALID: tampered canonical ---

    def test_tampered_canonical_gives_rc2(self):
        # Tamper preserving valid JSON but changing content → HASH_MISMATCH
        canon = self.outdir / "ai_canonical.json"
        obj = json.loads(canon.read_text(encoding="utf-8"))
        obj["output"] = "TAMPERED"
        canon.write_text(json.dumps(obj) + "\n", encoding="utf-8")
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=HASH_MISMATCH", r.stdout)
        self.assertIn("DETAIL=", r.stdout)

    # --- INVALID: tampered manifest hash ---

    def test_tampered_manifest_hash_gives_rc2(self):
        m = json.loads((self.outdir / "ai_manifest.json").read_text(encoding="utf-8"))
        m["ai_hash_sha256"] = "a" * 64
        (self.outdir / "ai_manifest.json").write_text(
            json.dumps(m, sort_keys=True) + "\n", encoding="utf-8"
        )
        r = _verify(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=HASH_MISMATCH", r.stdout)

    # --- no traceback ---

    def test_no_traceback_on_valid(self):
        r = _verify(self.outdir)
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    # --- JSON output includes signature field ---

    def test_json_output_includes_signature_none(self):
        r = subprocess.run(
            CLI + ["verify", "--out", str(self.outdir), "--json"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(r.returncode, 0)
        obj = json.loads(r.stdout.strip())
        self.assertIn("signature", obj)
        self.assertEqual(obj["signature"], "NONE")


class TestVerifySignatureEnforcement(unittest.TestCase):
    """Sprint 1.1: signature enforcement in aelitium verify."""

    def _make_signed_bundle(self, outdir: Path) -> str:
        """Create a bundle signed with a fresh Ed25519 key. Returns key b64."""
        import base64
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from types import SimpleNamespace
        from engine.capture.openai import capture_chat_completion

        key = Ed25519PrivateKey.generate()
        key_b64 = base64.b64encode(key.private_bytes_raw()).decode()

        response = SimpleNamespace(
            id="resp_test",
            created=1710000000,
            model="gpt-4o-mini",
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="test output"),
            )],
            usage=None,
        )

        class FakeClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(model, messages, **kwargs):
                        return response

        old_key = os.environ.get("AEL_ED25519_PRIVKEY_B64")
        os.environ["AEL_ED25519_PRIVKEY_B64"] = key_b64
        try:
            capture_chat_completion(
                FakeClient(), "gpt-4o-mini",
                [{"role": "user", "content": "hello"}],
                outdir,
            )
        finally:
            if old_key is None:
                os.environ.pop("AEL_ED25519_PRIVKEY_B64", None)
            else:
                os.environ["AEL_ED25519_PRIVKEY_B64"] = old_key

        return key_b64

    def test_signed_bundle_verify_returns_signature_valid(self):
        """Signed bundle: verify --json returns signature=VALID."""
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            self._make_signed_bundle(outdir)

            r = subprocess.run(
                CLI + ["verify", "--out", str(outdir), "--json"],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            obj = json.loads(r.stdout.strip())
            self.assertEqual(obj["status"], "VALID")
            self.assertEqual(obj["signature"], "VALID")

    def test_unsigned_bundle_verify_returns_signature_none(self):
        """Bundle without verification_keys.json: verify returns signature=NONE."""
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            _pack(outdir)
            self.assertFalse((outdir / "verification_keys.json").exists())

            r = subprocess.run(
                CLI + ["verify", "--out", str(outdir), "--json"],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            obj = json.loads(r.stdout.strip())
            self.assertEqual(obj["signature"], "NONE")

    def test_tampered_verification_keys_gives_signature_invalid(self):
        """Adultered verification_keys.json: verify must return SIGNATURE_INVALID."""
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            self._make_signed_bundle(outdir)

            vk_path = outdir / "verification_keys.json"
            vk = json.loads(vk_path.read_text())
            # Tamper: replace signature with zeros
            vk["signatures"][0]["sig_b64"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            vk_path.write_text(json.dumps(vk, sort_keys=True) + "\n")

            r = subprocess.run(
                CLI + ["verify", "--out", str(outdir)],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(r.returncode, 2)
            self.assertIn("STATUS=INVALID", r.stdout)
            self.assertIn("SIGNATURE_INVALID", r.stdout)

    def test_tampered_manifest_with_valid_keys_gives_signature_invalid(self):
        """Manifest tampered after signing: signature no longer matches bytes."""
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            self._make_signed_bundle(outdir)

            # Tamper manifest (re-write with different ts)
            manifest_path = outdir / "ai_manifest.json"
            m = json.loads(manifest_path.read_text())
            m["ts_utc"] = "2099-01-01T00:00:00Z"
            manifest_path.write_text(json.dumps(m, sort_keys=True) + "\n")

            r = subprocess.run(
                CLI + ["verify", "--out", str(outdir)],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(r.returncode, 2)
            self.assertIn("SIGNATURE_INVALID", r.stdout)


if __name__ == "__main__":
    unittest.main()
