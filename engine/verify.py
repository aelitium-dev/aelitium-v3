import json
import os
import sys
from canonical import sha256_hash

RC_VALID = 0
RC_INVALID = 2


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify(manifest_path: str, evidence_path: str) -> int:
    try:
        manifest = _read_json(manifest_path)
        evidence = _read_json(evidence_path)

        # Manifest invariants (fail-closed)
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

        # Optional but expected: verification_keys.json beside manifest/evidence
        # If present, enforce minimal structure.
        base_dir = os.path.dirname(os.path.abspath(manifest_path))
        vk_path = os.path.join(base_dir, "verification_keys.json")
        if os.path.exists(vk_path):
            vk = _read_json(vk_path)
            if vk.get("keyring_format") != "none":
                return RC_INVALID
            keys = vk.get("keys")
            if not isinstance(keys, list) or len(keys) != 0:
                return RC_INVALID

        return RC_VALID

    except Exception:
        return RC_INVALID


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: verify.py <manifest.json> <evidence_pack.json>")
        sys.exit(RC_INVALID)
    sys.exit(verify(sys.argv[1], sys.argv[2]))
