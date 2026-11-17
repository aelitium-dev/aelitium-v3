"""
Contract tests for aelitium-ai verify-receipt.

Uses the P3 signing module to generate real receipts (requires
AEL_ED25519_PRIVKEY_B64 env set to the test fixture key).
Falls back to a synthetic receipt signed with the test key.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "engine.ai_cli"]

# Test signing key fixture (same as engine tests)
PRIVKEY_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "ed25519_test_private_key.b64"


def _load_test_privkey_b64() -> str:
    return PRIVKEY_FIXTURE_PATH.read_text(encoding="utf-8").strip()


def _make_receipt(subject_hash: str = "a" * 64, subject_type: str = "ai_output_v1") -> dict:
    """Build and sign a real receipt_v1 using the test key."""
    import sys
    sys.path.insert(0, str(ROOT))
    os.environ["AEL_ED25519_PRIVKEY_B64"] = _load_test_privkey_b64()
    from p3.server.signing import sign_receipt
    return sign_receipt(subject_hash=subject_hash, subject_type=subject_type)


def _pubkey_b64() -> str:
    """Return base64 public key for the test fixture."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    raw = base64.b64decode(_load_test_privkey_b64())
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    return base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()


def _run_vr(receipt_path: str, pubkey_path: str, hash_arg: str = None):
    cmd = CLI + ["verify-receipt", "--receipt", receipt_path, "--pubkey", pubkey_path]
    if hash_arg:
        cmd += ["--hash", hash_arg]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


class TestVerifyReceiptContract(unittest.TestCase):

    def setUp(self):
        os.environ["AEL_ED25519_PRIVKEY_B64"] = _load_test_privkey_b64()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

        self.subject_hash = "b" * 64
        self.receipt = _make_receipt(self.subject_hash)
        self.receipt_path = self.tmp / "receipt.json"
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

        self.pubkey_path = self.tmp / "pubkey.b64"
        self.pubkey_path.write_text(_pubkey_b64(), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    # --- VALID path ---

    def test_valid_exit_code_zero(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_first_line(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path))
        lines = [l for l in r.stdout.strip().splitlines() if l]
        self.assertEqual(lines[0], "STATUS=VALID rc=0")

    def test_valid_has_subject_hash_line(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path))
        self.assertIn(f"SUBJECT_HASH_SHA256={self.subject_hash}", r.stdout)

    def test_valid_has_receipt_id_line(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path))
        self.assertIn("RECEIPT_ID=", r.stdout)

    def test_valid_with_matching_hash_arg(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path), self.subject_hash)
        self.assertEqual(r.returncode, 0, r.stderr)

    # --- INVALID: hash mismatch ---

    def test_wrong_hash_arg_gives_rc2(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path), "c" * 64)
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=HASH_MISMATCH", r.stdout)

    # --- INVALID: tampered receipt ---

    def test_tampered_receipt_gives_rc2(self):
        tampered = {**self.receipt, "subject_hash_sha256": "d" * 64}
        p = self.tmp / "tampered.json"
        p.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        r = _run_vr(str(p), str(self.pubkey_path))
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=SIGNATURE_INVALID", r.stdout)

    # --- INVALID: wrong pubkey ---

    def test_wrong_pubkey_gives_rc2(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        # generate a different key
        other = Ed25519PrivateKey.generate()
        other_pub = base64.b64encode(
            other.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode()
        wrong_pub = self.tmp / "wrong_pubkey.b64"
        wrong_pub.write_text(other_pub, encoding="utf-8")
        r = _run_vr(str(self.receipt_path), str(wrong_pub))
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=SIGNATURE_INVALID", r.stdout)

    # --- INVALID: missing fields ---

    def test_missing_receipt_field_gives_rc2(self):
        incomplete = {k: v for k, v in self.receipt.items() if k != "authority_signature"}
        p = self.tmp / "incomplete.json"
        p.write_text(json.dumps(incomplete) + "\n", encoding="utf-8")
        r = _run_vr(str(p), str(self.pubkey_path))
        self.assertEqual(r.returncode, 2)
        self.assertIn("reason=RECEIPT_MISSING_FIELD", r.stdout)

    # --- no traceback ---

    def test_no_traceback_on_valid(self):
        r = _run_vr(str(self.receipt_path), str(self.pubkey_path))
        self.assertNotIn("Traceback", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
