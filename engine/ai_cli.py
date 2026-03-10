#!/usr/bin/env python3
import argparse
import json
import jsonschema
from pathlib import Path

# Support both:
#  - running as a module (python -m engine.ai_cli)
#  - running as a script   (python engine/ai_cli.py)
if __package__:
    from .ai_canonical import canonicalize_ai_output
else:
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from engine.ai_canonical import canonicalize_ai_output


def _out(args, text_lines: list[str], json_obj: dict) -> None:
    if getattr(args, "json", False):
        print(json.dumps(json_obj, sort_keys=True))
    else:
        for line in text_lines:
            print(line)


def cmd_validate(args: argparse.Namespace) -> int:
    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    try:
        jsonschema.validate(instance=obj, schema=schema)
    except Exception as e:
        _out(args,
             [f"STATUS=INVALID rc=2 reason=SCHEMA_VIOLATION", f"DETAIL={type(e).__name__}"],
             {"status": "INVALID", "rc": 2, "reason": "SCHEMA_VIOLATION",
              "detail": type(e).__name__})
        return 2

    _out(args, ["STATUS=VALID rc=0"], {"status": "VALID", "rc": 0})
    return 0

def cmd_canonicalize(args: argparse.Namespace) -> int:
    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    canonical, h = canonicalize_ai_output(obj)
    if args.print:
        print(canonical)
    print(f"AI_CANON_SHA256={h}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    import hashlib
    import re

    outdir = Path(args.out)
    canon_path = outdir / "ai_canonical.json"
    manifest_path = outdir / "ai_manifest.json"

    def fail(reason: str, detail: str = "") -> int:
        print(f"STATUS=INVALID rc=2 reason={reason}")
        if detail:
            print(f"DETAIL={detail}")
        return 2

    if not canon_path.exists():
        return fail("MISSING_CANONICAL", "ai_canonical.json not found")
    if not manifest_path.exists():
        return fail("MISSING_MANIFEST", "ai_manifest.json not found")

    try:
        canon_text = canon_path.read_text(encoding="utf-8")
        json.loads(canon_text)
    except Exception as e:
        return fail("CANONICAL_NOT_JSON", type(e).__name__)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return fail("MANIFEST_NOT_JSON", type(e).__name__)

    for field in ("schema", "ts_utc", "input_schema", "canonicalization", "ai_hash_sha256"):
        if field not in manifest:
            return fail("MANIFEST_MISSING_FIELD", field)

    if manifest["schema"] != "ai_pack_manifest_v1":
        return fail("MANIFEST_BAD_SCHEMA", manifest["schema"])

    if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", manifest["ts_utc"]):
        return fail("MANIFEST_BAD_TS_UTC", manifest["ts_utc"])

    actual_hash = hashlib.sha256(canon_text.rstrip("\n").encode("utf-8")).hexdigest()
    if actual_hash != manifest["ai_hash_sha256"]:
        return fail("HASH_MISMATCH", f"expected={manifest['ai_hash_sha256'][:16]}... got={actual_hash[:16]}...")

    # Signature enforcement: if verification_keys.json is present, it MUST be valid.
    vk_path = outdir / "verification_keys.json"
    if vk_path.exists():
        try:
            if __package__:
                from .signing import verify_manifest_signature
            else:
                from engine.signing import verify_manifest_signature
            vk = json.loads(vk_path.read_text(encoding="utf-8"))
            manifest_bytes = manifest_path.read_bytes()
            verify_manifest_signature(manifest_bytes, vk)
            signature = "VALID"
        except Exception as exc:
            return fail("SIGNATURE_INVALID", str(exc))
    else:
        signature = "NONE"

    _out(args,
         ["STATUS=VALID rc=0", f"AI_HASH_SHA256={actual_hash}", f"SIGNATURE={signature}"],
         {"status": "VALID", "rc": 0, "ai_hash_sha256": actual_hash, "signature": signature})
    return 0


def cmd_verify_receipt(args: argparse.Namespace) -> int:
    """
    Offline receipt verification.
    Checks: receipt JSON valid, required fields, subject_hash matches --hash,
    Ed25519 signature over canonical receipt (signature="") is valid.
    Authority public key from --pubkey file (base64) or AEL_AUTHORITY_PUBKEY_B64 env.
    """
    import base64
    import hashlib
    import os
    import re

    def fail(reason: str, detail: str = "") -> int:
        print(f"STATUS=INVALID rc=2 reason={reason}")
        if detail:
            print(f"DETAIL={detail}")
        return 2

    # --- load receipt ---
    try:
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    except Exception as e:
        return fail("RECEIPT_NOT_JSON", type(e).__name__)

    for field in ("schema_version", "receipt_id", "ts_signed_utc",
                  "subject_hash_sha256", "subject_type",
                  "authority_fingerprint", "authority_signature"):
        if field not in receipt:
            return fail("RECEIPT_MISSING_FIELD", field)

    # --- hash match ---
    if args.hash and receipt["subject_hash_sha256"] != args.hash:
        return fail("HASH_MISMATCH",
                    f"receipt={receipt['subject_hash_sha256'][:16]}... arg={args.hash[:16]}...")

    # --- load authority public key ---
    pubkey_b64 = None
    if args.pubkey:
        try:
            pubkey_b64 = Path(args.pubkey).read_text(encoding="utf-8").strip()
        except Exception as e:
            return fail("PUBKEY_FILE_ERROR", str(e))
    else:
        pubkey_b64 = os.environ.get("AEL_AUTHORITY_PUBKEY_B64")

    if not pubkey_b64:
        return fail("NO_PUBKEY", "provide --pubkey or AEL_AUTHORITY_PUBKEY_B64")

    # --- verify signature ---
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        if __package__:
            from .canonical import canonical_json
        else:
            from engine.canonical import canonical_json

        pub_bytes = base64.b64decode(pubkey_b64)
        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        sig_bytes = base64.b64decode(receipt["authority_signature"])

        unsigned = {**receipt, "authority_signature": ""}
        canon = canonical_json(unsigned)
        pub.verify(sig_bytes, canon.encode("utf-8"))
    except InvalidSignature:
        return fail("SIGNATURE_INVALID")
    except Exception as e:
        return fail("SIGNATURE_ERROR", type(e).__name__)

    h = receipt["subject_hash_sha256"]
    rid = receipt["receipt_id"]
    _out(args,
         ["STATUS=VALID rc=0", f"SUBJECT_HASH_SHA256={h}", f"RECEIPT_ID={rid}"],
         {"status": "VALID", "rc": 0, "subject_hash_sha256": h, "receipt_id": rid})
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from pathlib import Path
    from engine.compliance import export_eu_ai_act_art12

    bundle_dir = Path(args.bundle)
    if not bundle_dir.exists():
        print(f"ERROR: bundle dir not found: {bundle_dir}")
        return 2

    result = export_eu_ai_act_art12(bundle_dir)

    _out(args,
         [f"STATUS=OK format={args.format} bundle={args.bundle}"],
         result)
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    # import lazy: não rebenta validate/canonicalize se pack tiver bugs
    from engine.ai_pack import ai_pack_from_obj

    obj = json.loads(Path(args.input).read_text(encoding="utf-8"))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    res = ai_pack_from_obj(obj)

    (outdir / "ai_canonical.json").write_text(res.canonical_json + "\n", encoding="utf-8")
    (outdir / "ai_manifest.json").write_text(json.dumps(res.manifest, sort_keys=True) + "\n", encoding="utf-8")

    _out(args,
         ["STATUS=OK rc=0", f"AI_HASH_SHA256={res.ai_hash_sha256}"],
         {"status": "OK", "rc": 0, "ai_hash_sha256": res.ai_hash_sha256})
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(prog="aelitium")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate ai_output_v1 minimal contract")
    v.add_argument("--schema", default="engine/schemas/ai_output_v1.json")
    v.add_argument("--input", required=True)
    v.add_argument("--json", action="store_true", help="Output as JSON")
    v.set_defaults(fn=cmd_validate)

    pck = sub.add_parser("pack", help="Write canonical + manifest artifacts")
    pck.add_argument("--input", required=True)
    pck.add_argument("--out", required=True)
    pck.add_argument("--json", action="store_true", help="Output as JSON")
    pck.set_defaults(fn=cmd_pack)

    ve = sub.add_parser("verify", help="Verify a pack output dir (canonical + manifest)")
    ve.add_argument("--out", required=True)
    ve.add_argument("--json", action="store_true", help="Output as JSON")
    ve.set_defaults(fn=cmd_verify)

    vr = sub.add_parser("verify-receipt", help="Offline verify an authority receipt_v1")
    vr.add_argument("--receipt", required=True, help="Path to receipt_v1 JSON file")
    vr.add_argument("--hash", default=None, help="Expected subject_hash_sha256 (64 hex)")
    vr.add_argument("--pubkey", default=None, help="Path to authority public key (base64)")
    vr.add_argument("--json", action="store_true", help="Output as JSON")
    vr.set_defaults(fn=cmd_verify_receipt)

    c = sub.add_parser("canonicalize", help="Canonicalize AI output and print hash")
    c.add_argument("--input", required=True)
    c.add_argument("--print", action="store_true", help="Print canonical JSON")
    c.set_defaults(fn=cmd_canonicalize)

    exp = sub.add_parser("export", help="Export bundle in compliance format")
    exp.add_argument("--bundle", required=True, help="Path to evidence bundle dir")
    exp.add_argument("--format", default="eu-ai-act-art12", choices=["eu-ai-act-art12"])
    exp.add_argument("--json", action="store_true")
    exp.set_defaults(fn=cmd_export)

    args = ap.parse_args()
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main())
