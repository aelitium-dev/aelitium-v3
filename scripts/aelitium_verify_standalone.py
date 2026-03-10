#!/usr/bin/env python3
"""
AELITIUM standalone verifier.
Verifies an evidence bundle without requiring aelitium to be installed.
Usage: python aelitium_verify_standalone.py --bundle ./evidence
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def verify_bundle(bundle_dir: Path) -> tuple:
    """Returns (valid, reason, details)."""
    canon_path = bundle_dir / "ai_canonical.json"
    manifest_path = bundle_dir / "ai_manifest.json"
    vk_path = bundle_dir / "verification_keys.json"

    # 1. Files exist
    if not canon_path.exists():
        return False, "MISSING_CANONICAL", {}
    if not manifest_path.exists():
        return False, "MISSING_MANIFEST", {}

    # 2. Valid JSON
    try:
        canon_text = canon_path.read_text(encoding="utf-8")
        canonical = json.loads(canon_text)
    except Exception as e:
        return False, f"CANONICAL_NOT_JSON: {e}", {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"MANIFEST_NOT_JSON: {e}", {}

    # 3. Manifest required fields
    for field in ("schema", "ts_utc", "ai_hash_sha256"):
        if field not in manifest:
            return False, f"MANIFEST_MISSING_FIELD: {field}", {}

    if manifest["schema"] != "ai_pack_manifest_v1":
        return False, f"MANIFEST_BAD_SCHEMA: {manifest['schema']}", {}

    # 4. Hash verification
    actual_hash = hashlib.sha256(canon_text.rstrip("\n").encode("utf-8")).hexdigest()
    expected_hash = manifest["ai_hash_sha256"]
    if actual_hash != expected_hash:
        return False, f"HASH_MISMATCH: expected={expected_hash[:16]}... got={actual_hash[:16]}...", {}

    details = {
        "ai_hash_sha256": actual_hash,
        "model": canonical.get("model"),
        "ts_utc": canonical.get("ts_utc"),
        "has_binding_hash": "binding_hash" in manifest,
        "has_verification_keys": vk_path.exists(),
    }

    if "binding_hash" in manifest:
        details["binding_hash"] = manifest["binding_hash"]

    return True, "OK", details


def main():
    ap = argparse.ArgumentParser(description="AELITIUM standalone bundle verifier")
    ap.add_argument("--bundle", required=True, help="Path to evidence bundle directory")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    args = ap.parse_args()

    bundle_dir = Path(args.bundle)
    valid, reason, details = verify_bundle(bundle_dir)

    if args.json:
        print(json.dumps({"status": "VALID" if valid else "INVALID", "reason": reason, **details}, sort_keys=True))
    else:
        if valid:
            print(f"STATUS=VALID")
            for k, v in details.items():
                print(f"  {k}={v}")
        else:
            print(f"STATUS=INVALID reason={reason}")

    sys.exit(0 if valid else 2)


if __name__ == "__main__":
    main()
