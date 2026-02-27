import json
import os
import sys
from canonical import canonicalize_and_hash

RC_VALID = 0
RC_INVALID = 2
EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "input_schema",
    "input_hash",
    "hash_alg",
    "canonicalization",
}
EXPECTED_EVIDENCE_KEYS = {"canonical_payload", "hash"}
EXPECTED_VK_KEYS = {"keyring_format", "keys"}
EXPECTED_CANONICALIZATION = "json.dumps(sort_keys,separators,utf8)"


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify(manifest_path: str, evidence_path: str) -> int:
    try:
        manifest = _read_json(manifest_path)
        evidence = _read_json(evidence_path)

        # Manifest/evidence schema invariants (fail-closed).
        if not isinstance(manifest, dict) or set(manifest.keys()) != EXPECTED_MANIFEST_KEYS:
            return RC_INVALID
        if not isinstance(evidence, dict) or set(evidence.keys()) != EXPECTED_EVIDENCE_KEYS:
            return RC_INVALID

        schema_version = manifest["schema_version"]
        hash_alg = manifest["hash_alg"]
        input_schema = manifest["input_schema"]
        input_hash = manifest["input_hash"]
        canonicalization = manifest["canonicalization"]

        if (
            not isinstance(schema_version, str)
            or not isinstance(hash_alg, str)
            or not isinstance(input_schema, str)
            or not isinstance(input_hash, str)
            or not isinstance(canonicalization, str)
            or not input_hash
        ):
            return RC_INVALID
        if schema_version != "1.0":
            return RC_INVALID
        if hash_alg != "sha256":
            return RC_INVALID
        if input_schema != "input_v1":
            return RC_INVALID
        if canonicalization != EXPECTED_CANONICALIZATION:
            return RC_INVALID

        canonical_payload = evidence["canonical_payload"]
        evidence_hash = evidence["hash"]

        if not isinstance(evidence_hash, str) or not isinstance(canonical_payload, str) or not evidence_hash:
            return RC_INVALID

        payload_obj = json.loads(canonical_payload)
        if not isinstance(payload_obj, dict):
            return RC_INVALID

        _, recomputed = canonicalize_and_hash(payload_obj)
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
            if not isinstance(vk, dict) or set(vk.keys()) != EXPECTED_VK_KEYS:
                return RC_INVALID
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
