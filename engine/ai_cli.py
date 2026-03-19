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


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    """
    Verify an evidence bundle directory.

    Checks: canonical JSON hash, manifest integrity, Ed25519 signature (if present),
    and binding_hash (if present in manifest).

    Usage: aelitium verify-bundle <bundle_dir>
    """
    import hashlib
    import re

    outdir = Path(args.bundle)
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
        canon_obj = json.loads(canon_text)
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

    # Signature enforcement
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

    # Binding hash: recompute from request_hash + response_hash in canonical metadata
    manifest_binding = manifest.get("binding_hash")
    if manifest_binding:
        meta = canon_obj.get("metadata", {})
        request_hash = meta.get("request_hash")
        response_hash = meta.get("response_hash")
        if not request_hash or not response_hash:
            return fail("BINDING_HASH_MISSING_SOURCES",
                        "manifest has binding_hash but canonical metadata lacks request_hash/response_hash")
        # Recompute using the same algorithm as the capture adapters
        payload = json.dumps(
            {"request_hash": request_hash, "response_hash": response_hash},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if computed != manifest_binding:
            return fail("BINDING_HASH_MISMATCH",
                        f"expected={manifest_binding[:16]}... computed={computed[:16]}...")
        binding = manifest_binding
    else:
        binding = "NONE"

    _out(args,
         ["STATUS=VALID rc=0",
          f"AI_HASH_SHA256={actual_hash}",
          f"SIGNATURE={signature}",
          f"BINDING_HASH={binding}"],
         {"status": "VALID", "rc": 0,
          "ai_hash_sha256": actual_hash,
          "signature": signature,
          "binding_hash": binding})
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """
    Compare two evidence bundles to detect AI model behavior change.

    Given two bundles A and B (both produced by the capture adapter):
    - UNCHANGED:      request_hash same, response_hash same
    - CHANGED:        request_hash same, response_hash different
    - NOT_COMPARABLE: request_hash differs, or bundles lack capture metadata
    - INVALID_BUNDLE: one or both bundles fail bundle verification

    Usage: aelitium compare <bundle_a> <bundle_b>
    """
    import hashlib
    import re

    def _verify_bundle_quiet(path: Path):
        canon_path = path / "ai_canonical.json"
        manifest_path = path / "ai_manifest.json"

        if not canon_path.exists() or not manifest_path.exists():
            return False, "MISSING_BUNDLE_FILES", None, None

        try:
            canon_text = canon_path.read_text(encoding="utf-8")
            canon_obj = json.loads(canon_text)
        except Exception as e:
            return False, "CANONICAL_NOT_JSON", type(e).__name__, None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, "MANIFEST_NOT_JSON", type(e).__name__, None

        for field in ("schema", "ts_utc", "input_schema", "canonicalization", "ai_hash_sha256"):
            if field not in manifest:
                return False, "MANIFEST_MISSING_FIELD", field, None

        if manifest["schema"] != "ai_pack_manifest_v1":
            return False, "MANIFEST_BAD_SCHEMA", manifest["schema"], None

        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", manifest["ts_utc"]):
            return False, "MANIFEST_BAD_TS_UTC", manifest["ts_utc"], None

        actual_hash = hashlib.sha256(canon_text.rstrip("\n").encode("utf-8")).hexdigest()
        if actual_hash != manifest["ai_hash_sha256"]:
            return False, "HASH_MISMATCH", f"expected={manifest['ai_hash_sha256'][:16]}... got={actual_hash[:16]}...", None

        vk_path = path / "verification_keys.json"
        if vk_path.exists():
            try:
                if __package__:
                    from .signing import verify_manifest_signature
                else:
                    from engine.signing import verify_manifest_signature
                vk = json.loads(vk_path.read_text(encoding="utf-8"))
                manifest_bytes = manifest_path.read_bytes()
                verify_manifest_signature(manifest_bytes, vk)
            except Exception as exc:
                return False, "SIGNATURE_INVALID", str(exc), None

        manifest_binding = manifest.get("binding_hash")
        if manifest_binding:
            meta = canon_obj.get("metadata", {})
            request_hash = meta.get("request_hash")
            response_hash = meta.get("response_hash")
            if not request_hash or not response_hash:
                return False, "BINDING_HASH_MISSING_SOURCES", "manifest has binding_hash but canonical metadata lacks request_hash/response_hash", None

            payload = json.dumps(
                {"request_hash": request_hash, "response_hash": response_hash},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
            computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if computed != manifest_binding:
                return False, "BINDING_HASH_MISMATCH", f"expected={manifest_binding[:16]}... computed={computed[:16]}...", None

        return True, "OK", "", {"canon": canon_obj, "manifest": manifest}

    def _hashes(canon, manifest):
        meta = canon.get("metadata", {})
        return {
            "request_hash": meta.get("request_hash"),
            "response_hash": meta.get("response_hash"),
            "binding_hash": manifest.get("binding_hash"),
            "ts_utc": canon.get("ts_utc") or manifest.get("ts_utc"),
        }

    path_a = Path(args.bundle_a)
    path_b = Path(args.bundle_b)

    ok_a, reason_a, detail_a, data_a = _verify_bundle_quiet(path_a)
    ok_b, reason_b, detail_b, data_b = _verify_bundle_quiet(path_b)

    if not ok_a or not ok_b:
        detail_parts = []
        if not ok_a:
            detail_parts.append(f"a={reason_a}")
        if not ok_b:
            detail_parts.append(f"b={reason_b}")
        _out(args,
             ["STATUS=INVALID_BUNDLE rc=2",
              f"DETAIL={' ; '.join(detail_parts)}"],
             {"status": "INVALID_BUNDLE", "rc": 2,
              "detail": " ; ".join(detail_parts)})
        return 2

    canon_a, manifest_a = data_a["canon"], data_a["manifest"]
    canon_b, manifest_b = data_b["canon"], data_b["manifest"]

    h_a = _hashes(canon_a, manifest_a)
    h_b = _hashes(canon_b, manifest_b)

    if not h_a["request_hash"] or not h_b["request_hash"]:
        _out(args,
             ["STATUS=NOT_COMPARABLE rc=1",
              "DETAIL=Bundles do not contain capture metadata (request_hash missing)",
              "HINT=Use the capture adapter (engine.capture.openai / engine.capture.anthropic) instead of aelitium pack"],
             {"status": "NOT_COMPARABLE", "rc": 1,
              "detail": "Bundles do not contain capture metadata (request_hash missing)",
              "hint": "Use the capture adapter instead of aelitium pack"})
        return 1

    req = "SAME" if h_a["request_hash"] == h_b["request_hash"] else "DIFFERENT"
    resp = "SAME" if h_a["response_hash"] == h_b["response_hash"] else "DIFFERENT"
    bind = "SAME" if h_a["binding_hash"] == h_b["binding_hash"] else "DIFFERENT"

    if req == "DIFFERENT":
        status = "NOT_COMPARABLE"
        rc = 1
        interpretation = "Requests differ — bundles are not comparable"
    elif resp == "SAME":
        status = "UNCHANGED"
        rc = 0
        interpretation = "Same request_hash and response_hash observed"
    else:
        status = "CHANGED"
        rc = 2
        interpretation = "Same request_hash with different response_hash observed"

    def _short(h): return h[:16] + "..." if h else "N/A"
    lines = [
        f"STATUS={status} rc={rc}",
        f"REQUEST_HASH={req}  a={_short(h_a['request_hash'])} b={_short(h_b['request_hash'])}",
        f"RESPONSE_HASH={resp}  a={_short(h_a['response_hash'])} b={_short(h_b['response_hash'])}",
        f"BINDING_HASH={bind}",
        f"TS_UTC_A={h_a['ts_utc'] or 'N/A'}",
        f"TS_UTC_B={h_b['ts_utc'] or 'N/A'}",
        f"INTERPRETATION={interpretation}",
    ]

    _out(args, lines,
         {"status": status, "rc": rc,
          "request_hash": req,
          "response_hash": resp,
          "binding_hash": bind,
          "request_hash_a": h_a["request_hash"],
          "request_hash_b": h_b["request_hash"],
          "response_hash_a": h_a["response_hash"],
          "response_hash_b": h_b["response_hash"],
          "ts_utc_a": h_a["ts_utc"],
          "ts_utc_b": h_b["ts_utc"],
          "interpretation": interpretation})
    return rc


def cmd_scan(args: argparse.Namespace) -> int:
    """
    Scan Python files for LLM call sites and check capture adapter coverage.

    Exits 0 if all detected call sites are instrumented.
    Exits 2 if any call sites are missing capture adapters.

    Usage: aelitium scan <path>
    """
    import re
    from pathlib import Path as _Path

    # Patterns that indicate a direct LLM API call (not inside capture adapters)
    LLM_CALL_PATTERNS = [
        (r"\.chat\.completions\.create\s*\(", "openai"),
        (r"ChatCompletion\.create\s*\(", "openai-legacy"),
        (r"\.messages\.create\s*\(", "anthropic"),
        (r"litellm\.completion\s*\(", "litellm"),
        (r"litellm\.acompletion\s*\(", "litellm"),
        (r"\bllm\.predict\s*\(", "langchain"),
        (r"\bllm\.invoke\s*\(", "langchain"),
        (r"\bchain\.run\s*\(", "langchain"),
        (r"\bchain\.invoke\s*\(", "langchain"),
    ]

    # Patterns that indicate AELITIUM capture adapter usage in the same file
    CAPTURE_PATTERNS = [
        r"capture_chat_completion\s*\(",
        r"capture_message\s*\(",
        r"capture_anthropic_message\s*\(",
        r"capture_chat_completion_stream\s*\(",
    ]

    scan_root = _Path(args.path)
    if not scan_root.exists():
        print(f"ERROR: path not found: {args.path}")
        return 2

    instrumented = []
    uninstrumented = []

    for py_file in sorted(scan_root.rglob("*.py")):
        # Skip aelitium's own capture engine and test files
        rel = py_file.relative_to(scan_root)
        parts = rel.parts
        if any(p in ("engine", "aelitium", ".venv", "venv", "__pycache__") for p in parts):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        has_capture = any(re.search(p, content) for p in CAPTURE_PATTERNS)

        for i, line in enumerate(content.splitlines(), 1):
            for pattern, provider in LLM_CALL_PATTERNS:
                if re.search(pattern, line):
                    entry = {
                        "file": str(rel),
                        "line": i,
                        "provider": provider,
                        "instrumented": has_capture,
                    }
                    if has_capture:
                        instrumented.append(entry)
                    else:
                        uninstrumented.append(entry)

    total = len(instrumented) + len(uninstrumented)
    status = "OK" if not uninstrumented else "INCOMPLETE"
    rc = 0 if not uninstrumented else 2
    coverage_pct = int(len(instrumented) * 100 / total) if total > 0 else 100

    if getattr(args, "json", False):
        print(json.dumps({
            "status": status,
            "rc": rc,
            "total": total,
            "instrumented": len(instrumented),
            "uninstrumented": len(uninstrumented),
            "coverage_pct": coverage_pct,
            "sites": instrumented + uninstrumented,
        }, sort_keys=True))
        return rc

    if getattr(args, "ci", False):
        print(f"AELITIUM_SCAN_STATUS={status}")
        print(f"AELITIUM_SCAN_TOTAL={total}")
        print(f"AELITIUM_SCAN_INSTRUMENTED={len(instrumented)}")
        print(f"AELITIUM_SCAN_MISSING={len(uninstrumented)}")
        print(f"AELITIUM_SCAN_COVERAGE={coverage_pct}")
        return rc

    print(f"LLM call sites detected: {total}")
    if total == 0:
        print("No LLM call sites found.")
        print(f"STATUS={status} rc={rc}")
        return rc

    if instrumented:
        print(f"\nInstrumented with capture adapter: {len(instrumented)}")
        for s in instrumented:
            print(f"  \u2713 {s['provider']} \u2014 {s['file']}:{s['line']}")

    if uninstrumented:
        print(f"\nMissing evidence capture: {len(uninstrumented)}")
        for s in uninstrumented:
            print(f"  \u26a0 {s['provider']} \u2014 {s['file']}:{s['line']}")
        print("\nHINT: Wrap uninstrumented calls with the AELITIUM capture adapter.")
        print("  from aelitium import capture_openai")

    print(f"\nCoverage: {len(instrumented)}/{total} ({coverage_pct}%)")
    print(f"STATUS={status} rc={rc}")
    return rc


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

    vb = sub.add_parser("verify-bundle", help="Verify evidence bundle (hash + signature + binding hash)")
    vb.add_argument("bundle", help="Path to evidence bundle directory")
    vb.add_argument("--json", action="store_true", help="Output as JSON")
    vb.set_defaults(fn=cmd_verify_bundle)

    cmp = sub.add_parser("compare", help="Compare two bundles to detect AI model behavior change")
    cmp.add_argument("bundle_a", help="Path to first evidence bundle directory")
    cmp.add_argument("bundle_b", help="Path to second evidence bundle directory")
    cmp.add_argument("--json", action="store_true", help="Output as JSON")
    cmp.set_defaults(fn=cmd_compare)

    sc = sub.add_parser("scan", help="Scan Python files for uninstrumented LLM call sites")
    sc.add_argument("path", help="Directory to scan recursively")
    sc.add_argument("--json", action="store_true", help="Output as JSON")
    sc.add_argument("--ci", action="store_true", help="CI-friendly AELITIUM_SCAN_* key=value output")
    sc.set_defaults(fn=cmd_scan)

    # `aelitium check` — alias for scan, more intuitive for new users
    ck = sub.add_parser("check", help="Alias for scan — check LLM calls for missing evidence capture")
    ck.add_argument("path", help="Directory to scan recursively")
    ck.add_argument("--json", action="store_true", help="Output as JSON")
    ck.add_argument("--ci", action="store_true", help="CI-friendly AELITIUM_SCAN_* key=value output")
    ck.set_defaults(fn=cmd_scan)

    exp = sub.add_parser("export", help="Export bundle in compliance format")
    exp.add_argument("--bundle", required=True, help="Path to evidence bundle dir")
    exp.add_argument("--format", default="eu-ai-act-art12", choices=["eu-ai-act-art12"])
    exp.add_argument("--json", action="store_true")
    exp.set_defaults(fn=cmd_export)

    args = ap.parse_args()
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main())
