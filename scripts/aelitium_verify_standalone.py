#!/usr/bin/env python3
"""
AELITIUM standalone verifier.
Verifies an evidence bundle without requiring aelitium to be installed.
Usage: python aelitium_verify_standalone.py --bundle ./evidence
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.ai_verify import AIVerificationOptions, verify_ai_bundle


STANDALONE_REQUIRED_FIELDS = ("schema", "ts_utc", "ai_hash_sha256")


def verify_bundle(
    bundle_dir: Path,
    *,
    require_signature: bool = False,
    require_binding: bool = False,
) -> tuple:
    """Returns (valid, reason, details)."""
    vk_path = bundle_dir / "verification_keys.json"
    options = AIVerificationOptions(
        required_manifest_fields=STANDALONE_REQUIRED_FIELDS,
        validate_manifest_timestamp=False,
        require_signature=require_signature,
        require_binding=require_binding,
    )
    result = verify_ai_bundle(bundle_dir, options=options)
    if not result.valid:
        if result.reason in ("MISSING_CANONICAL", "MISSING_MANIFEST"):
            reason = result.reason
        elif result.reason in ("CANONICAL_NOT_JSON", "MANIFEST_NOT_JSON"):
            reason = f"{result.reason}: {result.error_message}"
        elif result.detail:
            reason = f"{result.reason}: {result.detail}"
        else:
            reason = result.reason
        return False, reason, result.assurance_dict()

    canonical = result.canonical
    manifest = result.manifest

    details = {
        "ai_hash_sha256": result.ai_hash_sha256,
        "model": canonical.get("model"),
        "ts_utc": canonical.get("ts_utc"),
        "has_binding_hash": "binding_hash" in manifest,
        "has_verification_keys": vk_path.exists(),
        **result.assurance_dict(),
    }

    if "binding_hash" in manifest:
        details["binding_hash"] = manifest["binding_hash"]

    return True, "OK", details


def main():
    ap = argparse.ArgumentParser(description="AELITIUM standalone bundle verifier")
    ap.add_argument("--bundle", required=True, help="Path to evidence bundle directory")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    ap.add_argument("--require-signature", action="store_true",
                    help="Reject bundles without signature material")
    ap.add_argument("--require-binding", action="store_true",
                    help="Reject bundles without v1 binding evidence")
    args = ap.parse_args()

    bundle_dir = Path(args.bundle)
    valid, reason, details = verify_bundle(
        bundle_dir,
        require_signature=args.require_signature,
        require_binding=args.require_binding,
    )

    if args.json:
        print(json.dumps({"status": "VALID" if valid else "INVALID", "reason": reason, **details}, sort_keys=True))
    else:
        if valid:
            print(f"STATUS=VALID")
            for k, v in details.items():
                print(f"  {k}={v}")
        else:
            print(f"STATUS=INVALID reason={reason}")
            for k, v in details.items():
                print(f"  {k}={v}")

    sys.exit(0 if valid else 2)


if __name__ == "__main__":
    main()
