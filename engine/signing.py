import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

KEYRING_FORMAT = "ed25519-v1"
SIGNATURE_ALGORITHM = "ed25519"
SIGNATURE_SCOPE = "manifest.json"
DEFAULT_KEY_ID = "local-ed25519"


class SigningConfigError(ValueError):
    pass


def _decode_b64(value: str, reason: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise SigningConfigError(reason) from exc


def _load_private_key_bytes() -> bytes:
    key_b64 = os.environ.get("AEL_ED25519_PRIVKEY_B64")
    key_path = os.environ.get("AEL_ED25519_PRIVKEY_PATH")

    if key_b64:
        raw = _decode_b64(key_b64.strip(), "SIGNING_KEY_B64_INVALID")
    elif key_path:
        raw = _decode_b64(
            Path(key_path).read_text(encoding="utf-8").strip(),
            "SIGNING_KEY_FILE_INVALID",
        )
    else:
        raise SigningConfigError("SIGNING_KEY_NOT_CONFIGURED")

    if len(raw) != 32:
        raise SigningConfigError("SIGNING_KEY_LENGTH_INVALID")
    return raw


def load_private_key() -> Ed25519PrivateKey:
    try:
        return Ed25519PrivateKey.from_private_bytes(_load_private_key_bytes())
    except ValueError as exc:
        raise SigningConfigError("SIGNING_KEY_INVALID") from exc


def build_verification_material(manifest_bytes: bytes) -> dict:
    private_key = load_private_key()
    key_id = os.environ.get("AEL_ED25519_KEY_ID", DEFAULT_KEY_ID).strip() or DEFAULT_KEY_ID
    public_key = private_key.public_key()
    public_key_b64 = base64.b64encode(
        public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    signature_b64 = base64.b64encode(private_key.sign(manifest_bytes)).decode("ascii")

    return {
        "keyring_format": KEYRING_FORMAT,
        "keys": [
            {
                "key_id": key_id,
                "public_key_b64": public_key_b64,
            }
        ],
        "signatures": [
            {
                "key_id": key_id,
                "algorithm": SIGNATURE_ALGORITHM,
                "scope": SIGNATURE_SCOPE,
                "sig_b64": signature_b64,
            }
        ],
    }


def verify_manifest_signature(manifest_bytes: bytes, vk_obj: dict) -> None:
    if vk_obj.get("keyring_format") != KEYRING_FORMAT:
        raise ValueError("BAD_KEYRING_FORMAT")

    keys = vk_obj.get("keys")
    signatures = vk_obj.get("signatures")
    if not isinstance(keys, list) or len(keys) != 1:
        raise ValueError("BAD_KEYS")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise ValueError("BAD_SIGNATURES")

    key_entry = keys[0]
    sig_entry = signatures[0]
    if not isinstance(key_entry, dict) or not isinstance(sig_entry, dict):
        raise ValueError("BAD_KEY_OR_SIGNATURE_ENTRY")

    key_id = key_entry.get("key_id")
    public_key_b64 = key_entry.get("public_key_b64")
    if not isinstance(key_id, str) or not key_id:
        raise ValueError("BAD_KEY_ID")
    if not isinstance(public_key_b64, str) or not public_key_b64:
        raise ValueError("BAD_PUBLIC_KEY")

    if sig_entry.get("key_id") != key_id:
        raise ValueError("SIGNATURE_KEY_ID_MISMATCH")
    if sig_entry.get("algorithm") != SIGNATURE_ALGORITHM:
        raise ValueError("BAD_SIGNATURE_ALGORITHM")
    if sig_entry.get("scope") != SIGNATURE_SCOPE:
        raise ValueError("BAD_SIGNATURE_SCOPE")

    sig_b64 = sig_entry.get("sig_b64")
    if not isinstance(sig_b64, str) or not sig_b64:
        raise ValueError("BAD_SIGNATURE")

    public_key_bytes = _decode_b64(public_key_b64, "PUBLIC_KEY_B64_INVALID")
    signature_bytes = _decode_b64(sig_b64, "SIGNATURE_B64_INVALID")
    if len(public_key_bytes) != 32:
        raise ValueError("PUBLIC_KEY_LENGTH_INVALID")
    if len(signature_bytes) != 64:
        raise ValueError("SIGNATURE_LENGTH_INVALID")

    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, manifest_bytes)
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("SIGNATURE_INVALID") from exc
