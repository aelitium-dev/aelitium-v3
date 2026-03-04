"""
P3 — Authority signing helpers.
Wraps engine/signing.py + canonical JSON for receipt signing.
"""
from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone

# Re-use canonical JSON from P1/P2 engine
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.canonical import canonical_json, sha256_hash


def _load_private_key():
    """Load Ed25519 private key from env (same convention as P1)."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    b64 = os.environ.get("AEL_ED25519_PRIVKEY_B64")
    if not b64:
        raise RuntimeError("AEL_ED25519_PRIVKEY_B64 not set")
    raw = base64.b64decode(b64)
    return Ed25519PrivateKey.from_private_bytes(raw)


def authority_public_key_b64() -> str:
    """Return base64-encoded Ed25519 public key."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    priv = _load_private_key()
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(pub_bytes).decode()


def authority_fingerprint() -> str:
    """SHA256 digest of the raw public key bytes (hex)."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    priv = _load_private_key()
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(pub_bytes).hexdigest()


def sign_receipt(subject_hash: str, subject_type: str) -> dict:
    """
    Build and sign a receipt_v1.

    Returns the receipt dict (with authority_signature populated).
    Signature is over canonical JSON of receipt with authority_signature="".
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt_id = f"rec-{ts[:10].replace('-','')}-{uuid.uuid4().hex[:8]}"
    fp = authority_fingerprint()

    # Canonical receipt (signature field = "" for signing)
    unsigned = {
        "schema_version": "receipt_v1",
        "receipt_id": receipt_id,
        "ts_signed_utc": ts,
        "subject_hash_sha256": subject_hash,
        "subject_type": subject_type,
        "authority_fingerprint": fp,
        "authority_signature": "",
    }
    canon = canonical_json(unsigned)

    priv = _load_private_key()
    sig_bytes = priv.sign(canon.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode()

    return {**unsigned, "authority_signature": sig_b64}


def verify_receipt_signature(receipt: dict) -> bool:
    """Verify the Ed25519 signature on a receipt_v1."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    sig_b64 = receipt.get("authority_signature", "")
    if not sig_b64:
        return False

    unsigned = {**receipt, "authority_signature": ""}
    canon = canonical_json(unsigned)

    priv = _load_private_key()
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub = Ed25519PublicKey.from_public_bytes(pub_bytes)

    try:
        pub.verify(base64.b64decode(sig_b64), canon.encode("utf-8"))
        return True
    except InvalidSignature:
        return False
