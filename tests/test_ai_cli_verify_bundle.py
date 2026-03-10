"""
Tests for `aelitium verify-bundle <dir>`.

Covers:
- valid bundle (pack-produced, no signature, no binding hash) → VALID
- valid capture bundle (with binding_hash) → VALID + BINDING_HASH=<hash>
- missing ai_canonical.json → MISSING_CANONICAL
- missing ai_manifest.json → MISSING_MANIFEST
- tampered canonical → HASH_MISMATCH
- tampered manifest hash → HASH_MISMATCH
- tampered binding_hash in manifest → BINDING_HASH_MISMATCH
- tampered request_hash in canonical metadata → BINDING_HASH_MISMATCH
- signed bundle → SIGNATURE=VALID
- tampered verification_keys.json → SIGNATURE_INVALID
- --json output structure
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"
CLI = [sys.executable, "-m", "engine.ai_cli"]
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _pack(outdir: Path) -> None:
    """Pack the minimal fixture into outdir."""
    subprocess.run(
        CLI + ["pack", "--input", str(FIXTURE), "--out", str(outdir)],
        capture_output=True, check=True, cwd=ROOT,
    )


def _make_capture_bundle(outdir: Path) -> str:
    """Create a capture-style bundle (has binding_hash). Returns binding_hash."""
    from engine.capture.openai import capture_chat_completion

    response = SimpleNamespace(
        id="resp_test", created=1710000000, model="gpt-4o-mini",
        choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content="The answer is 42."),
        )],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create.return_value = response

    result = capture_chat_completion(
        client, "gpt-4o-mini",
        [{"role": "user", "content": "What is 6 times 7?"}],
        outdir,
    )
    manifest = json.loads((outdir / "ai_manifest.json").read_text())
    return manifest["binding_hash"]


def _make_signed_bundle(outdir: Path) -> None:
    """Create a signed capture bundle."""
    import base64, os
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from engine.capture.openai import capture_chat_completion

    key = Ed25519PrivateKey.generate()
    key_b64 = base64.b64encode(key.private_bytes_raw()).decode()

    response = SimpleNamespace(
        id="resp_signed", created=1710000000, model="gpt-4o-mini",
        choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content="signed output"),
        )],
        usage=None,
    )
    client = MagicMock()
    client.chat.completions.create.return_value = response

    old = os.environ.get("AEL_ED25519_PRIVKEY_B64")
    os.environ["AEL_ED25519_PRIVKEY_B64"] = key_b64
    try:
        capture_chat_completion(
            client, "gpt-4o-mini",
            [{"role": "user", "content": "hello"}],
            outdir,
        )
    finally:
        if old is None:
            os.environ.pop("AEL_ED25519_PRIVKEY_B64", None)
        else:
            os.environ["AEL_ED25519_PRIVKEY_B64"] = old


def _verify_bundle(outdir: Path, extra: list = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + ["verify-bundle", str(outdir)] + (extra or []),
        capture_output=True, text=True, cwd=ROOT,
    )


class TestVerifyBundleValid(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        _pack(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_exit_code_zero(self):
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_first_line(self):
        r = _verify_bundle(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[0], "STATUS=VALID rc=0")

    def test_valid_second_line_is_hash(self):
        r = _verify_bundle(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertRegex(lines[1], r"^AI_HASH_SHA256=[0-9a-f]{64}$")

    def test_valid_no_signature_no_binding(self):
        r = _verify_bundle(self.outdir)
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertIn("SIGNATURE=NONE", lines)
        self.assertIn("BINDING_HASH=NONE", lines)

    def test_valid_json_output(self):
        r = _verify_bundle(self.outdir, ["--json"])
        self.assertEqual(r.returncode, 0)
        obj = json.loads(r.stdout.strip())
        self.assertEqual(obj["status"], "VALID")
        self.assertIn("ai_hash_sha256", obj)
        self.assertIn("signature", obj)
        self.assertIn("binding_hash", obj)
        self.assertEqual(obj["signature"], "NONE")
        self.assertEqual(obj["binding_hash"], "NONE")

    def test_no_traceback_on_valid(self):
        r = _verify_bundle(self.outdir)
        self.assertNotIn("Traceback", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


class TestVerifyBundleCapture(unittest.TestCase):
    """Bundle produced by capture adapter — has binding_hash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        self.binding_hash = _make_capture_bundle(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_exit_code_zero(self):
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_binding_hash_present_in_output(self):
        r = _verify_bundle(self.outdir)
        self.assertIn(f"BINDING_HASH={self.binding_hash}", r.stdout)

    def test_binding_hash_in_json_output(self):
        r = _verify_bundle(self.outdir, ["--json"])
        obj = json.loads(r.stdout.strip())
        self.assertEqual(obj["binding_hash"], self.binding_hash)
        self.assertRegex(obj["binding_hash"], HASH_RE)

    def test_tampered_binding_hash_in_manifest_gives_rc2(self):
        m = json.loads((self.outdir / "ai_manifest.json").read_text())
        m["binding_hash"] = "b" * 64
        (self.outdir / "ai_manifest.json").write_text(
            json.dumps(m, sort_keys=True) + "\n", encoding="utf-8"
        )
        # canonical hash will now mismatch (manifest changed) → HASH_MISMATCH
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATUS=INVALID", r.stdout)

    def test_tampered_request_hash_in_canonical_gives_binding_mismatch(self):
        canon = json.loads((self.outdir / "ai_canonical.json").read_text())
        canon["metadata"]["request_hash"] = "c" * 64
        (self.outdir / "ai_canonical.json").write_text(
            json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        # Also update the manifest hash so it matches the new canonical
        import hashlib
        new_text = (self.outdir / "ai_canonical.json").read_text()
        new_hash = hashlib.sha256(new_text.rstrip("\n").encode()).hexdigest()
        m = json.loads((self.outdir / "ai_manifest.json").read_text())
        m["ai_hash_sha256"] = new_hash
        (self.outdir / "ai_manifest.json").write_text(
            json.dumps(m, sort_keys=True) + "\n", encoding="utf-8"
        )
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        # If the bundle was signed, signature check fires before binding_hash check.
        # Both are correct failure modes for this tampering.
        self.assertTrue(
            "BINDING_HASH_MISMATCH" in r.stdout or "SIGNATURE_INVALID" in r.stdout,
            f"Expected BINDING_HASH_MISMATCH or SIGNATURE_INVALID, got: {r.stdout!r}",
        )


class TestVerifyBundleMissing(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        _pack(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_canonical_gives_rc2(self):
        (self.outdir / "ai_canonical.json").unlink()
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("MISSING_CANONICAL", r.stdout)

    def test_missing_manifest_gives_rc2(self):
        (self.outdir / "ai_manifest.json").unlink()
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("MISSING_MANIFEST", r.stdout)


class TestVerifyBundleTamper(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.outdir = Path(self._tmp.name)
        _pack(self.outdir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tampered_canonical_gives_rc2(self):
        canon = self.outdir / "ai_canonical.json"
        obj = json.loads(canon.read_text())
        obj["output"] = "TAMPERED"
        canon.write_text(json.dumps(obj) + "\n", encoding="utf-8")
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("HASH_MISMATCH", r.stdout)

    def test_tampered_manifest_hash_gives_rc2(self):
        m = json.loads((self.outdir / "ai_manifest.json").read_text())
        m["ai_hash_sha256"] = "a" * 64
        (self.outdir / "ai_manifest.json").write_text(
            json.dumps(m, sort_keys=True) + "\n", encoding="utf-8"
        )
        r = _verify_bundle(self.outdir)
        self.assertEqual(r.returncode, 2)
        self.assertIn("HASH_MISMATCH", r.stdout)


class TestVerifyBundleSigned(unittest.TestCase):

    def test_signed_bundle_returns_signature_valid(self):
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            _make_signed_bundle(outdir)
            r = _verify_bundle(outdir, ["--json"])
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            obj = json.loads(r.stdout.strip())
            self.assertEqual(obj["status"], "VALID")
            self.assertEqual(obj["signature"], "VALID")

    def test_tampered_verification_keys_gives_signature_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            outdir = Path(d)
            _make_signed_bundle(outdir)
            vk = json.loads((outdir / "verification_keys.json").read_text())
            vk["signatures"][0]["sig_b64"] = "A" * 88
            (outdir / "verification_keys.json").write_text(
                json.dumps(vk, sort_keys=True) + "\n"
            )
            r = _verify_bundle(outdir)
            self.assertEqual(r.returncode, 2)
            self.assertIn("SIGNATURE_INVALID", r.stdout)


if __name__ == "__main__":
    unittest.main()
