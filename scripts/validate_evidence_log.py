#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:-rc[0-9]+)?$")
TS_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_KEYS = {
    "schema",
    "tag",
    "ts_utc",
    "input_sha256",
    "manifest_sha256",
    "evidence_sha256",
    "verification_keys_sha256",
    "bundle_sha_run1",
    "bundle_sha_run2",
    "verify_rc",
    "repro_rc",
    "tamper_rc",
    "machine_role",
    "machine_id",
    "sync_mode",
    "bundle_sha256",
}
SHA_KEYS = {
    "input_sha256",
    "manifest_sha256",
    "evidence_sha256",
    "verification_keys_sha256",
    "bundle_sha_run1",
    "bundle_sha_run2",
}
SYNC_MODES = {"remote", "bundle"}

def fail(reason: str, rc: int = 2):
    print(f"EVIDENCE_STATUS=FAIL reason={reason}")
    sys.exit(rc)

def ok():
    print("EVIDENCE_STATUS=PASS")
    sys.exit(0)

def extract_entries(md: str):
    pattern = re.compile(
        r"^## EVIDENCE_ENTRY v1 \| tag=(?P<header_tag>\S+)\s*\n```json\s*\n(?P<body>\{.*?\})\s*\n```",
        flags=re.MULTILINE | re.DOTALL,
    )
    entries = []
    for m in pattern.finditer(md.replace("\r\n", "\n")):
        entries.append((m.group("header_tag"), m.group("body")))
    return entries


def validate_entry(tag: str, header_tag: str, obj: dict, required_machine_role: str):
    if not isinstance(obj, dict):
        fail("ENTRY_NOT_OBJECT")

    missing = REQUIRED_KEYS - set(obj.keys())
    if missing:
        fail("MISSING_KEYS:" + ",".join(sorted(missing)))

    unknown = set(obj.keys()) - REQUIRED_KEYS
    invalid_unknown = sorted(k for k in unknown if not k.startswith("x_"))
    if invalid_unknown:
        fail("UNKNOWN_KEYS:" + ",".join(invalid_unknown))

    if obj.get("schema") != "evidence_entry_v1":
        fail("SCHEMA_MISMATCH")
    if obj.get("tag") != tag:
        fail("TAG_MISMATCH")
    if header_tag != tag:
        fail("HEADER_TAG_MISMATCH")
    if not TAG_RE.fullmatch(tag):
        fail("INVALID_TAG_FORMAT")

    ts_utc = obj.get("ts_utc")
    if not isinstance(ts_utc, str) or not TS_UTC_RE.fullmatch(ts_utc):
        fail("INVALID_TS_UTC")

    for k in sorted(SHA_KEYS):
        v = obj.get(k)
        if not isinstance(v, str) or not HEX64.fullmatch(v):
            fail(f"BAD_{k.upper()}")

    if obj.get("bundle_sha_run1") != obj.get("bundle_sha_run2"):
        fail("BUNDLE_SHA_MISMATCH")

    if obj.get("verify_rc") != 0:
        fail("VERIFY_RC_NOT_ZERO")
    if obj.get("repro_rc") != 0:
        fail("REPRO_RC_NOT_ZERO")
    if obj.get("tamper_rc") != 2:
        fail("TAMPER_RC_NOT_TWO")

    role = obj.get("machine_role")
    if role not in ("A", "B"):
        fail("BAD_MACHINE_ROLE")
    if required_machine_role != "ANY" and role != required_machine_role:
        fail(f"MACHINE_ROLE_MISMATCH expected={required_machine_role} got={role}")

    machine_id = obj.get("machine_id")
    if not isinstance(machine_id, str) or not machine_id.strip():
        fail("BAD_MACHINE_ID")

    sync_mode = obj.get("sync_mode")
    if sync_mode not in SYNC_MODES:
        fail("BAD_SYNC_MODE")

    bundle_sha = obj.get("bundle_sha256")
    if sync_mode == "bundle":
        if not isinstance(bundle_sha, str) or not HEX64.fullmatch(bundle_sha):
            fail("BAD_BUNDLE_SHA256")
    else:
        if bundle_sha is not None:
            fail("REMOTE_MODE_REQUIRES_NULL_BUNDLE_SHA")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument(
        "--required-machine-role",
        choices=["A", "B", "ANY"],
        default="ANY",
        help="Fail if entry.machine_role does not match this role",
    )
    args = ap.parse_args()

    tag = args.tag.strip()
    log_path = Path(args.log)

    if not tag:
        fail("EMPTY_TAG")
    if not log_path.exists():
        fail("LOG_NOT_FOUND")

    md = log_path.read_text(encoding="utf-8", errors="replace")
    entries = extract_entries(md)
    matching = [(header_tag, blob) for header_tag, blob in entries if header_tag == tag]
    if len(matching) == 0:
        fail("ENTRY_NOT_FOUND_FOR_TAG")

    parsed = []
    for header_tag, blob in matching:
        try:
            obj = json.loads(blob)
        except Exception:
            fail("JSON_PARSE_ERROR")
        parsed.append((header_tag, obj))

    if args.required_machine_role == "ANY":
        if len(parsed) != 1:
            fail("DUPLICATE_ENTRIES_FOR_TAG_REQUIRE_ROLE")
        header_tag, obj = parsed[0]
    else:
        selected = [(h, o) for h, o in parsed if o.get("machine_role") == args.required_machine_role]
        if len(selected) == 0:
            fail(f"ENTRY_NOT_FOUND_FOR_TAG_ROLE role={args.required_machine_role}")
        if len(selected) > 1:
            fail(f"DUPLICATE_ENTRIES_FOR_TAG_ROLE role={args.required_machine_role}")
        header_tag, obj = selected[0]

    validate_entry(tag, header_tag, obj, args.required_machine_role)

    ok()

if __name__ == "__main__":
    main()
