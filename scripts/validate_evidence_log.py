#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

RC_PASS = 0
RC_FAIL = 2

ENTRY_PATTERN = re.compile(
    r"^## EVIDENCE_ENTRY v1 \| tag=(?P<header_tag>\S+)\s*\n```json\s*\n(?P<body>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:-rc[0-9]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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


def _fail(message: str) -> int:
    print(f"EVIDENCE_STATUS=FAIL reason={message}")
    return RC_FAIL


def _parse_entries(log_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for match in ENTRY_PATTERN.finditer(log_text.replace("\r\n", "\n")):
        header_tag = match.group("header_tag")
        body = match.group("body")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"INVALID_JSON_FOR_HEADER_TAG:{header_tag}:{exc.msg}") from exc
        entries.append({"header_tag": header_tag, "payload": payload})
    return entries


def _validate_sha64(value: Any, key: str) -> str | None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        return f"INVALID_{key.upper()}"
    return None


def _validate_entry(requested_tag: str, header_tag: str, payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return "ENTRY_PAYLOAD_NOT_OBJECT"

    missing = REQUIRED_KEYS - set(payload.keys())
    if missing:
        return "MISSING_KEYS:" + ",".join(sorted(missing))

    unknown = set(payload.keys()) - REQUIRED_KEYS
    invalid_unknown = [k for k in unknown if not k.startswith("x_")]
    if invalid_unknown:
        return "UNKNOWN_KEYS:" + ",".join(sorted(invalid_unknown))

    if payload["schema"] != "evidence_entry_v1":
        return "INVALID_SCHEMA"

    tag = payload["tag"]
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
        return "INVALID_TAG_FORMAT"
    if not TAG_RE.fullmatch(requested_tag):
        return "REQUESTED_TAG_FORMAT_INVALID"
    if header_tag != requested_tag:
        return "HEADER_TAG_MISMATCH"
    if tag != requested_tag:
        return "PAYLOAD_TAG_MISMATCH"
    if header_tag != tag:
        return "HEADER_PAYLOAD_TAG_DIVERGENCE"

    ts_utc = payload["ts_utc"]
    if not isinstance(ts_utc, str) or not TS_UTC_RE.fullmatch(ts_utc):
        return "INVALID_TS_UTC"

    for key in sorted(SHA_KEYS):
        error = _validate_sha64(payload[key], key)
        if error:
            return error

    if payload["bundle_sha_run1"] != payload["bundle_sha_run2"]:
        return "BUNDLE_SHA_RUN_MISMATCH"

    if payload["verify_rc"] != 0:
        return "VERIFY_RC_NOT_ZERO"
    if payload["repro_rc"] != 0:
        return "REPRO_RC_NOT_ZERO"
    if payload["tamper_rc"] != 2:
        return "TAMPER_RC_NOT_TWO"

    machine_role = payload["machine_role"]
    if machine_role not in {"A", "B"}:
        return "INVALID_MACHINE_ROLE"

    machine_id = payload["machine_id"]
    if not isinstance(machine_id, str) or not machine_id.strip():
        return "INVALID_MACHINE_ID"

    sync_mode = payload["sync_mode"]
    if sync_mode not in {"remote", "bundle"}:
        return "INVALID_SYNC_MODE"

    bundle_sha256 = payload["bundle_sha256"]
    if sync_mode == "bundle":
        if not isinstance(bundle_sha256, str) or not SHA256_RE.fullmatch(bundle_sha256):
            return "BUNDLE_MODE_REQUIRES_BUNDLE_SHA256"
    else:
        if bundle_sha256 is not None:
            return "REMOTE_MODE_REQUIRES_NULL_BUNDLE_SHA256"

    return None


def validate_evidence_log(log_path: Path, requested_tag: str) -> tuple[bool, str]:
    if not log_path.is_file():
        return False, "LOG_NOT_FOUND"

    text = log_path.read_text(encoding="utf-8")
    try:
        entries = _parse_entries(text)
    except ValueError as exc:
        return False, str(exc)

    matching = [entry for entry in entries if entry["header_tag"] == requested_tag]
    if len(matching) == 0:
        return False, "ENTRY_NOT_FOUND_FOR_TAG"
    if len(matching) > 1:
        return False, "DUPLICATE_ENTRIES_FOR_TAG"

    entry = matching[0]
    error = _validate_entry(requested_tag, entry["header_tag"], entry["payload"])
    if error:
        return False, error

    return True, "OK"


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_evidence_log.py")
    parser.add_argument(
        "--log",
        default="governance/logs/EVIDENCE_LOG.md",
        help="Path to evidence log markdown file",
    )
    parser.add_argument("--tag", required=True, help="Release tag to validate")
    args = parser.parse_args()

    ok, reason = validate_evidence_log(Path(args.log), args.tag)
    if ok:
        print("EVIDENCE_STATUS=PASS")
        return RC_PASS
    return _fail(reason)


if __name__ == "__main__":
    sys.exit(main())
