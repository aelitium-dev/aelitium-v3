import json
import sys
from canonical import sha256_hash

RC_VALID = 0
RC_INVALID = 2


def verify(manifest_path: str, evidence_path: str) -> int:
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(evidence_path, "r", encoding="utf-8") as f:
            evidence = json.load(f)

        # Required fields (fail-closed)
        if manifest.get("schema_version") != "1.0":
            return RC_INVALID

        input_hash = manifest.get("input_hash")
        canonical_payload = evidence.get("canonical_payload")
        evidence_hash = evidence.get("hash")

        if not input_hash or not canonical_payload or not evidence_hash:
            return RC_INVALID

        # Recompute hash
        recomputed = sha256_hash(canonical_payload)

        if recomputed != input_hash:
            return RC_INVALID
        if recomputed != evidence_hash:
            return RC_INVALID

        return RC_VALID

    except Exception:
        return RC_INVALID


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: verify.py <manifest.json> <evidence_pack.json>")
        sys.exit(RC_INVALID)
    sys.exit(verify(sys.argv[1], sys.argv[2]))
