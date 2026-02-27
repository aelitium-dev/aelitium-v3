#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")

def fail(reason: str, rc: int = 2):
    print(f"EVIDENCE_STATUS=FAIL reason={reason}")
    sys.exit(rc)

def ok():
    print("EVIDENCE_STATUS=PASS")
    sys.exit(0)

def extract_entry(md: str, tag: str) -> str | None:
    # Header line must match exactly
    header = f"## EVIDENCE_ENTRY v1 | tag={tag}"
    idx = md.find(header)
    if idx < 0:
        return None
    tail = md[idx:]
    # Find the first fenced json block after the header
    m = re.search(r"```json\s*(\{.*?\})\s*```", tail, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()

    tag = args.tag.strip()
    log_path = Path(args.log)

    if not tag:
        fail("EMPTY_TAG")
    if not log_path.exists():
        fail("LOG_NOT_FOUND")

    md = log_path.read_text(encoding="utf-8", errors="replace")
    blob = extract_entry(md, tag)
    if blob is None:
        fail("ENTRY_NOT_FOUND_FOR_TAG")

    try:
        obj = json.loads(blob)
    except Exception:
        fail("JSON_PARSE_ERROR")

    # Required fields
    if obj.get("schema") != "evidence_entry_v1":
        fail("SCHEMA_MISMATCH")
    if obj.get("tag") != tag:
        fail("TAG_MISMATCH")

    for k in ("input_sha256","manifest_sha256","evidence_sha256","verification_keys_sha256"):
        v = obj.get(k)
        if not isinstance(v, str) or not HEX64.match(v):
            fail(f"BAD_{k.upper()}")

    # rc fields
    if obj.get("verify_rc") != 0:
        fail("VERIFY_RC_NOT_ZERO")
    if obj.get("repro_rc") != 0:
        fail("REPRO_RC_NOT_ZERO")

    role = obj.get("machine_role")
    if role not in ("A","B"):
        fail("BAD_MACHINE_ROLE")

    ok()

if __name__ == "__main__":
    main()
