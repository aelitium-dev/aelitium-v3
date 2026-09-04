#!/usr/bin/env python3
import argparse
import json
import jsonschema
from pathlib import Path

# Support both:
#  - running as a module (python -m engine.ai_cli)
#  - running as a script   (python engine/ai_cli.py)
if __package__:
    from .ai_canonical import AICanonicalError, canonicalize_ai_output
    from .ai_verify import AssuranceState, AIVerificationOptions, verify_ai_bundle
    from .result_contracts import (
        build_comparison_contract_fields,
        build_verification_result,
    )
else:
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from engine.ai_canonical import AICanonicalError, canonicalize_ai_output
    from engine.ai_verify import AssuranceState, AIVerificationOptions, verify_ai_bundle
    from engine.result_contracts import (
        build_comparison_contract_fields,
        build_verification_result,
    )


COMPARISON_CONTRACT = "aelitium-compare-v1"

COMPARISON_MODE_INVOCATION_FIRST = "INVOCATION_FIRST"
COMPARISON_MODE_STRICT_INVOCATION = "STRICT_INVOCATION"
COMPARISON_MODE_LEGACY_REQUEST_HASH_V1 = "LEGACY_REQUEST_HASH_V1"

COMPARISON_BASIS_INVOCATION_IDENTITY_V1 = "INVOCATION_IDENTITY_V1"
COMPARISON_BASIS_REQUEST_HASH_V1_FALLBACK = "REQUEST_HASH_V1_FALLBACK"
COMPARISON_BASIS_REQUEST_HASH_V1_LEGACY = "REQUEST_HASH_V1_LEGACY"
COMPARISON_BASIS_NONE = "NONE"


def _out(args, text_lines: list[str], json_obj: dict) -> None:
    if getattr(args, "json", False):
        print(json.dumps(json_obj, sort_keys=True))
    else:
        for line in text_lines:
            print(line)


def _assurance_lines(result) -> list[str]:
    return [
        f"{name.upper()}={state}"
        for name, state in result.assurance_dict().items()
    ]


def _verification_options(args: argparse.Namespace) -> AIVerificationOptions:
    return AIVerificationOptions(
        require_signature=getattr(args, "require_signature", False),
        require_binding=getattr(args, "require_binding", False),
        trust_store_path=getattr(args, "trust_store", None),
        require_trusted_signer=getattr(args, "require_trusted_signer", False),
        freshness_max_age_seconds=getattr(
            args,
            "freshness_max_age_seconds",
            None,
        ),
        freshness_reference_time_utc=getattr(
            args,
            "freshness_reference_time_utc",
            None,
        ),
    )


def _add_freshness_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--freshness-max-age-seconds",
        type=int,
        metavar="SECONDS",
        default=None,
        help=(
            "Maximum declared-time evidence age in seconds; requires "
            "--freshness-reference-time-utc"
        ),
    )
    parser.add_argument(
        "--freshness-reference-time-utc",
        metavar="UTC_TIME",
        default=None,
        help=(
            "Explicit UTC reference time in YYYY-MM-DDTHH:MM:SSZ form; "
            "requires --freshness-max-age-seconds"
        ),
    )


def _verification_fail(result) -> int:
    print(f"STATUS=INVALID rc=2 reason={result.reason}")
    if result.detail:
        print(f"DETAIL={result.detail}")
    for line in _assurance_lines(result):
        print(line)
    return 2


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
    outdir = Path(args.out)

    options = _verification_options(args)
    result = verify_ai_bundle(
        outdir,
        options=options,
    )
    if getattr(args, "contract_json", False):
        print(
            json.dumps(
                build_verification_result(result, options=options),
                sort_keys=True,
            )
        )
        return 0 if result.valid else 2
    if not result.valid:
        return _verification_fail(result)

    _out(args,
         ["STATUS=VALID rc=0",
          f"AI_HASH_SHA256={result.ai_hash_sha256}",
          f"SIGNATURE={result.signature}",
          *_assurance_lines(result)],
         {"status": "VALID", "rc": 0,
          "ai_hash_sha256": result.ai_hash_sha256,
          "signature": result.signature,
          **result.assurance_dict()})
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

    Reports the eight assurance dimensions after schema/canonical/payload,
    binding-field, invocation-identity, invocation-binding, signature/trust, and
    optional Freshness evaluation.

    Usage: aelitium verify-bundle <bundle_dir>
    """
    outdir = Path(args.bundle)

    options = _verification_options(args)
    result = verify_ai_bundle(outdir, options=options)
    if getattr(args, "contract_json", False):
        print(
            json.dumps(
                build_verification_result(result, options=options),
                sort_keys=True,
            )
        )
        return 0 if result.valid else 2
    if not result.valid:
        return _verification_fail(result)

    _out(args,
         ["STATUS=VALID rc=0",
          f"AI_HASH_SHA256={result.ai_hash_sha256}",
          f"SIGNATURE={result.signature}",
          f"BINDING_HASH={result.binding_hash}",
          *_assurance_lines(result)],
         {"status": "VALID", "rc": 0,
          "ai_hash_sha256": result.ai_hash_sha256,
          "signature": result.signature,
          "binding_hash": result.binding_hash,
          **result.assurance_dict()})
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """
    Compare validated invocation evidence, with an explicit request-hash fallback.

    Usage: aelitium compare <bundle_a> <bundle_b>
    """

    def _mode() -> str:
        if getattr(args, "require_invocation_evidence", False):
            return COMPARISON_MODE_STRICT_INVOCATION
        if getattr(args, "legacy_request_hash_v1", False):
            return COMPARISON_MODE_LEGACY_REQUEST_HASH_V1
        return COMPARISON_MODE_INVOCATION_FIRST

    def _state(result, name: str) -> str:
        value = getattr(result, name, AssuranceState.NOT_EVALUATED)
        return value.value if isinstance(value, AssuranceState) else str(value)

    def _assurance_values(result) -> tuple[AssuranceState, AssuranceState] | None:
        identity = getattr(result, "invocation_identity_consistency", None)
        binding = getattr(result, "invocation_binding_consistency", None)
        if not isinstance(identity, AssuranceState) or not isinstance(
            binding, AssuranceState
        ):
            return None
        allowed = {
            (AssuranceState.ABSENT, AssuranceState.ABSENT),
            (AssuranceState.VALID, AssuranceState.ABSENT),
            (AssuranceState.VALID, AssuranceState.VALID),
        }
        return (identity, binding) if (identity, binding) in allowed else None

    def _hashes(result) -> dict:
        canon = result.canonical
        manifest = result.manifest
        meta = canon.get("metadata", {})
        invocation = meta.get("invocation_identity")
        invocation_hash = (
            invocation.get("hash_sha256") if isinstance(invocation, dict) else None
        )
        return {
            "request_hash": meta.get("request_hash"),
            "response_hash": meta.get("response_hash"),
            "binding_hash": manifest.get("binding_hash"),
            "invocation_identity_hash": invocation_hash,
            "ts_utc": canon.get("ts_utc") or manifest.get("ts_utc"),
        }

    def _is_sha256(value) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    def _inputs_are_consistent(result, states) -> bool:
        if states is None:
            return False
        if not isinstance(result.canonical, dict) or not isinstance(
            result.manifest, dict
        ):
            return False
        meta = result.canonical.get("metadata", {})
        if not isinstance(meta, dict):
            return False

        identity_state, binding_state = states
        identity_present = "invocation_identity" in meta
        binding_present = "invocation_binding" in meta
        if identity_present != (identity_state is AssuranceState.VALID):
            return False
        if binding_present != (binding_state is AssuranceState.VALID):
            return False
        if identity_state is AssuranceState.VALID:
            invocation = meta.get("invocation_identity")
            if not isinstance(invocation, dict) or not _is_sha256(
                invocation.get("hash_sha256")
            ):
                return False
        return True

    def _relation(value_a, value_b) -> str:
        if not value_a or not value_b:
            return "UNAVAILABLE"
        return "SAME" if value_a == value_b else "DIFFERENT"

    def _short(value) -> str:
        return value[:16] + "..." if value else "N/A"

    def _interpretation(status: str) -> str:
        if status == "NOT_COMPARABLE":
            return (
                "No response-change conclusion is made because the selected "
                "comparison identity hashes differ or the comparison mode's "
                "required evidence is unavailable."
            )
        if status == "UNCHANGED":
            return (
                "Under the reported comparison basis, the selected comparison "
                "identity hashes and selected response_hash values match. This "
                "does not establish unchanged invocation configuration or "
                "unchanged model behavior."
            )
        return (
            "Under the reported comparison basis, the selected comparison "
            "identity hashes match and selected response_hash values differ. "
            "This does not identify a cause."
        )

    def _emit_invalid(
        mode: str,
        result_a,
        result_b,
        *,
        invariant: bool,
        invariant_sides: tuple[str, ...] = (),
    ) -> int:
        reason = (
            "COMPARISON_INPUT_INVARIANT_FAILED"
            if invariant
            else "BUNDLE_VERIFICATION_FAILED"
        )
        detail_parts = []
        if invariant:
            detail_parts.extend(
                f"{side}=COMPARISON_INPUT_INVARIANT_FAILED"
                for side in invariant_sides
            )
        else:
            for side, result in (("a", result_a), ("b", result_b)):
                if result.valid:
                    continue
                bundle_reason = result.reason
                if bundle_reason in ("MISSING_CANONICAL", "MISSING_MANIFEST"):
                    bundle_reason = "MISSING_BUNDLE_FILES"
                detail_parts.append(f"{side}={bundle_reason}")
        detail = " ; ".join(detail_parts)
        interpretation = (
            "Comparison was not performed because validated comparison inputs "
            "were internally inconsistent"
            if invariant
            else "Comparison was not performed because one or both bundles "
            "failed verification"
        )
        states = {
            "invocation_identity_consistency_a": _state(
                result_a, "invocation_identity_consistency"
            ),
            "invocation_binding_consistency_a": _state(
                result_a, "invocation_binding_consistency"
            ),
            "invocation_identity_consistency_b": _state(
                result_b, "invocation_identity_consistency"
            ),
            "invocation_binding_consistency_b": _state(
                result_b, "invocation_binding_consistency"
            ),
        }
        lines = [
            "STATUS=INVALID_BUNDLE rc=2",
            f"COMPARISON_CONTRACT={COMPARISON_CONTRACT}",
            f"COMPARISON_MODE={mode}",
            f"COMPARISON_BASIS={COMPARISON_BASIS_NONE}",
            f"COMPARISON_REASON={reason}",
            "INVOCATION_IDENTITY_HASH=UNAVAILABLE",
            f"INVOCATION_IDENTITY_CONSISTENCY_A={states['invocation_identity_consistency_a']}",
            f"INVOCATION_BINDING_CONSISTENCY_A={states['invocation_binding_consistency_a']}",
            f"INVOCATION_IDENTITY_CONSISTENCY_B={states['invocation_identity_consistency_b']}",
            f"INVOCATION_BINDING_CONSISTENCY_B={states['invocation_binding_consistency_b']}",
        ]
        if detail:
            lines.append(f"DETAIL={detail}")
        lines.append(f"INTERPRETATION={interpretation}")
        json_result = {
            "status": "INVALID_BUNDLE",
            "rc": 2,
            "comparison_contract": COMPARISON_CONTRACT,
            "comparison_mode": mode,
            "comparison_basis": COMPARISON_BASIS_NONE,
            "required_comparison_basis": None,
            "comparison_reason": reason,
            "invocation_identity_hash": "UNAVAILABLE",
            "invocation_identity_hash_a": None,
            "invocation_identity_hash_b": None,
            **states,
            "detail": detail,
            "interpretation": interpretation,
        }
        json_result.update(
            build_comparison_contract_fields(
                result_a=result_a,
                result_b=result_b,
                status="INVALID_BUNDLE",
                response_relationship=None,
            )
        )
        _out(args, lines, json_result)
        return 2

    path_a = Path(args.bundle_a)
    path_b = Path(args.bundle_b)
    mode = _mode()

    # Verification precedence is deliberate: both inputs are verified before
    # any comparison basis is selected or any stored identity hash is exposed.
    result_a = verify_ai_bundle(path_a)
    result_b = verify_ai_bundle(path_b)

    if not result_a.valid or not result_b.valid:
        return _emit_invalid(mode, result_a, result_b, invariant=False)

    states_a = _assurance_values(result_a)
    states_b = _assurance_values(result_b)
    consistent_a = _inputs_are_consistent(result_a, states_a)
    consistent_b = _inputs_are_consistent(result_b, states_b)
    if not consistent_a or not consistent_b:
        invariant_sides = tuple(
            side
            for side, consistent in (("a", consistent_a), ("b", consistent_b))
            if not consistent
        )
        return _emit_invalid(
            mode,
            result_a,
            result_b,
            invariant=True,
            invariant_sides=invariant_sides,
        )

    h_a = _hashes(result_a)
    h_b = _hashes(result_b)
    identity_a, invocation_binding_a = states_a
    identity_b, invocation_binding_b = states_b
    usable_a = (
        identity_a is AssuranceState.VALID
        and invocation_binding_a is AssuranceState.VALID
    )
    usable_b = (
        identity_b is AssuranceState.VALID
        and invocation_binding_b is AssuranceState.VALID
    )

    required_basis = None
    if mode == COMPARISON_MODE_LEGACY_REQUEST_HASH_V1:
        basis = COMPARISON_BASIS_REQUEST_HASH_V1_LEGACY
    elif usable_a and usable_b:
        basis = COMPARISON_BASIS_INVOCATION_IDENTITY_V1
    elif mode == COMPARISON_MODE_STRICT_INVOCATION:
        basis = COMPARISON_BASIS_NONE
        required_basis = COMPARISON_BASIS_INVOCATION_IDENTITY_V1
    else:
        basis = COMPARISON_BASIS_REQUEST_HASH_V1_FALLBACK

    req = _relation(h_a["request_hash"], h_b["request_hash"])
    resp = _relation(h_a["response_hash"], h_b["response_hash"])
    bind = _relation(h_a["binding_hash"], h_b["binding_hash"])
    invocation = _relation(
        h_a["invocation_identity_hash"], h_b["invocation_identity_hash"]
    )

    if required_basis is not None:
        status = "NOT_COMPARABLE"
        rc = 1
        reason = "INVOCATION_EVIDENCE_UNAVAILABLE"
    elif basis == COMPARISON_BASIS_INVOCATION_IDENTITY_V1:
        bad_response_sides = tuple(
            side
            for side, hashes in (("a", h_a), ("b", h_b))
            if not _is_sha256(hashes["response_hash"])
        )
        if bad_response_sides:
            return _emit_invalid(
                mode,
                result_a,
                result_b,
                invariant=True,
                invariant_sides=bad_response_sides,
            )
        if invocation == "DIFFERENT":
            status = "NOT_COMPARABLE"
            rc = 1
            reason = "INVOCATION_IDENTITY_HASH_DIFFERENT"
        elif invocation != "SAME":
            return _emit_invalid(
                mode,
                result_a,
                result_b,
                invariant=True,
                invariant_sides=("a", "b"),
            )
        elif resp == "SAME":
            status = "UNCHANGED"
            rc = 0
            reason = "RESPONSE_HASH_SAME"
        else:
            status = "CHANGED"
            rc = 2
            reason = "RESPONSE_HASH_DIFFERENT"
    else:
        if req == "UNAVAILABLE":
            status = "NOT_COMPARABLE"
            rc = 1
            reason = "REQUEST_HASH_UNAVAILABLE"
        elif bad_selected_sides := tuple(
            side
            for side, hashes in (("a", h_a), ("b", h_b))
            if not _is_sha256(hashes["request_hash"])
            or not _is_sha256(hashes["response_hash"])
        ):
            return _emit_invalid(
                mode,
                result_a,
                result_b,
                invariant=True,
                invariant_sides=bad_selected_sides,
            )
        elif req == "DIFFERENT":
            status = "NOT_COMPARABLE"
            rc = 1
            reason = "REQUEST_HASH_DIFFERENT"
        elif resp == "SAME":
            status = "UNCHANGED"
            rc = 0
            reason = "RESPONSE_HASH_SAME"
        else:
            status = "CHANGED"
            rc = 2
            reason = "RESPONSE_HASH_DIFFERENT"

    interpretation = _interpretation(status)
    lines = [
        f"STATUS={status} rc={rc}",
        f"COMPARISON_CONTRACT={COMPARISON_CONTRACT}",
        f"COMPARISON_MODE={mode}",
        f"COMPARISON_BASIS={basis}",
        f"COMPARISON_REASON={reason}",
    ]
    if required_basis is not None:
        lines.append(f"REQUIRED_COMPARISON_BASIS={required_basis}")
    lines.extend(
        [
            (
                f"INVOCATION_IDENTITY_HASH={invocation}  "
                f"a={_short(h_a['invocation_identity_hash'])} "
                f"b={_short(h_b['invocation_identity_hash'])}"
            ),
            f"INVOCATION_IDENTITY_CONSISTENCY_A={identity_a.value}",
            f"INVOCATION_BINDING_CONSISTENCY_A={invocation_binding_a.value}",
            f"INVOCATION_IDENTITY_CONSISTENCY_B={identity_b.value}",
            f"INVOCATION_BINDING_CONSISTENCY_B={invocation_binding_b.value}",
            (
                f"REQUEST_HASH={req}  a={_short(h_a['request_hash'])} "
                f"b={_short(h_b['request_hash'])}"
            ),
            (
                f"RESPONSE_HASH={resp}  a={_short(h_a['response_hash'])} "
                f"b={_short(h_b['response_hash'])}"
            ),
            f"BINDING_HASH={bind}",
            f"TS_UTC_A={h_a['ts_utc'] or 'N/A'}",
            f"TS_UTC_B={h_b['ts_utc'] or 'N/A'}",
        ]
    )
    detail = None
    hint = None
    if reason == "REQUEST_HASH_UNAVAILABLE":
        detail = "Bundles do not contain capture metadata (request_hash missing)"
        hint = "Use a supported capture adapter instead of aelitium pack"
        lines.extend([f"DETAIL={detail}", f"HINT={hint}"])
    lines.append(f"INTERPRETATION={interpretation}")

    json_result = {
        "status": status,
        "rc": rc,
        "comparison_contract": COMPARISON_CONTRACT,
        "comparison_mode": mode,
        "comparison_basis": basis,
        "required_comparison_basis": required_basis,
        "comparison_reason": reason,
        "invocation_identity_hash": invocation,
        "invocation_identity_hash_a": h_a["invocation_identity_hash"],
        "invocation_identity_hash_b": h_b["invocation_identity_hash"],
        "invocation_identity_consistency_a": identity_a.value,
        "invocation_binding_consistency_a": invocation_binding_a.value,
        "invocation_identity_consistency_b": identity_b.value,
        "invocation_binding_consistency_b": invocation_binding_b.value,
        "request_hash": req,
        "response_hash": resp,
        "binding_hash": bind,
        "request_hash_a": h_a["request_hash"],
        "request_hash_b": h_b["request_hash"],
        "response_hash_a": h_a["response_hash"],
        "response_hash_b": h_b["response_hash"],
        "ts_utc_a": h_a["ts_utc"],
        "ts_utc_b": h_b["ts_utc"],
        "interpretation": interpretation,
    }
    if detail is not None:
        json_result["detail"] = detail
        json_result["hint"] = hint
    json_result.update(
        build_comparison_contract_fields(
            result_a=result_a,
            result_b=result_b,
            status=status,
            response_relationship=(
                resp if status in {"UNCHANGED", "CHANGED"} else None
            ),
        )
    )
    _out(args, lines, json_result)
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
    try:
        res = ai_pack_from_obj(obj)
    except AICanonicalError as exc:
        reason = str(exc)
        _out(
            args,
            [f"STATUS=INVALID rc=2 reason={reason}"],
            {"status": "INVALID", "rc": 2, "reason": reason},
        )
        return 2

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
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
    verify_output = ve.add_mutually_exclusive_group()
    verify_output.add_argument(
        "--json",
        action="store_true",
        help="Output valid results as JSON; invalid results retain compatibility text",
    )
    verify_output.add_argument(
        "--contract-json",
        action="store_true",
        help=(
            "Output aelitium-verification-result-v1 JSON for valid or invalid "
            "results"
        ),
    )
    ve.add_argument("--require-signature", action="store_true",
                    help="Reject bundles without signature material")
    ve.add_argument("--require-binding", action="store_true",
                    help="Reject bundles without v1 binding evidence")
    ve.add_argument(
        "--trust-store",
        metavar="PATH",
        default=None,
        help="Use an explicit local trusted-signer store for signer identity evaluation",
    )
    ve.add_argument(
        "--require-trusted-signer",
        action="store_true",
        help=(
            "Reject unless the valid bundle signature corresponds to a key "
            "trusted by the supplied trust store"
        ),
    )
    _add_freshness_policy_arguments(ve)
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

    vb = sub.add_parser(
        "verify-bundle",
        help="Verify all eight AI bundle assurance dimensions; optionally evaluate Freshness",
    )
    vb.add_argument("bundle", help="Path to evidence bundle directory")
    verify_bundle_output = vb.add_mutually_exclusive_group()
    verify_bundle_output.add_argument(
        "--json",
        action="store_true",
        help="Output valid results as JSON; invalid results retain compatibility text",
    )
    verify_bundle_output.add_argument(
        "--contract-json",
        action="store_true",
        help=(
            "Output aelitium-verification-result-v1 JSON for valid or invalid "
            "results"
        ),
    )
    vb.add_argument("--require-signature", action="store_true",
                    help="Reject bundles without signature material")
    vb.add_argument("--require-binding", action="store_true",
                    help="Reject bundles without v1 binding evidence")
    vb.add_argument(
        "--trust-store",
        metavar="PATH",
        default=None,
        help="Use an explicit local trusted-signer store for signer identity evaluation",
    )
    vb.add_argument(
        "--require-trusted-signer",
        action="store_true",
        help=(
            "Reject unless the valid bundle signature corresponds to a key "
            "trusted by the supplied trust store"
        ),
    )
    _add_freshness_policy_arguments(vb)
    vb.set_defaults(fn=cmd_verify_bundle)

    cmp = sub.add_parser(
        "compare",
        help="Compare validated bundle hashes using invocation-first semantics",
        description=(
            "Comparison contract: aelitium-compare-v1. The default uses validated "
            "invocation identity and binding evidence from both bundles, with a "
            "visible request_hash v1 fallback when that evidence is unavailable. "
            "UNCHANGED and CHANGED describe selected identity and response-hash "
            "relationships only; they do not establish causation or unchanged "
            "model behavior."
        ),
    )
    cmp.add_argument("bundle_a", help="Path to first evidence bundle directory")
    cmp.add_argument("bundle_b", help="Path to second evidence bundle directory")
    cmp.add_argument("--json", action="store_true", help="Output as JSON")
    compare_mode = cmp.add_mutually_exclusive_group()
    compare_mode.add_argument(
        "--require-invocation-evidence",
        action="store_true",
        help=(
            "Require invocation_identity_consistency=VALID and "
            "invocation_binding_consistency=VALID for both bundles; disable "
            "request_hash v1 fallback."
        ),
    )
    compare_mode.add_argument(
        "--legacy-request-hash-v1",
        action="store_true",
        help=(
            "Use v0.3.x request_hash v1 comparison semantics even when "
            "validated invocation evidence is present."
        ),
    )
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

    exp = sub.add_parser("export", help="Export an Article 12-oriented record mapping")
    exp.add_argument("--bundle", required=True, help="Path to evidence bundle dir")
    exp.add_argument("--format", default="eu-ai-act-art12", choices=["eu-ai-act-art12"])
    exp.add_argument("--json", action="store_true")
    exp.set_defaults(fn=cmd_export)

    args = ap.parse_args()
    return int(args.fn(args))

if __name__ == "__main__":
    raise SystemExit(main())
