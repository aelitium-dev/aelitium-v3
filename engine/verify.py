import json
import os
import sys

if __package__ in (None, ""):
    from canonical import sha256_hash
    from signing import verify_manifest_signature
else:
    from .canonical import sha256_hash
    from .signing import verify_manifest_signature

RC_VALID = 0
RC_INVALID = 2
BUNDLE_SCHEMA = "1.1"


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def verify(manifest_path: str, evidence_path: str) -> int:
    try:
        manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
        evidence_dir = os.path.dirname(os.path.abspath(evidence_path))
        if manifest_dir != evidence_dir:
            return RC_INVALID

        manifest_bytes = _read_bytes(manifest_path)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        evidence = _read_json(evidence_path)

        # Manifest invariants (fail-closed)
        if manifest.get("bundle_schema") != BUNDLE_SCHEMA:
            return RC_INVALID
        if manifest.get("schema_version") != "1.0":
            return RC_INVALID
        if manifest.get("hash_alg") != "sha256":
            return RC_INVALID
        if manifest.get("input_schema") != "input_v1":
            return RC_INVALID

        input_hash = manifest.get("input_hash")
        canonical_payload = evidence.get("canonical_payload")
        evidence_hash = evidence.get("hash")

        if not input_hash or not canonical_payload or not evidence_hash:
            return RC_INVALID

        recomputed = sha256_hash(canonical_payload)
        if recomputed != input_hash:
            return RC_INVALID
        if recomputed != evidence_hash:
            return RC_INVALID

        # verification_keys.json is mandatory and must carry a valid
        # signature over the exact manifest bytes written on disk.
        vk_path = os.path.join(manifest_dir, "verification_keys.json")
        if not os.path.exists(vk_path):
            return RC_INVALID

        vk = _read_json(vk_path)
        try:
            verify_manifest_signature(manifest_bytes, vk)
        except ValueError:
            return RC_INVALID

        return RC_VALID

    except Exception:
        return RC_INVALID


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: verify.py <manifest.json> <evidence_pack.json>")
        sys.exit(RC_INVALID)
    sys.exit(verify(sys.argv[1], sys.argv[2]))
