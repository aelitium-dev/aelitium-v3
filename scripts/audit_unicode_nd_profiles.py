#!/usr/bin/env python3
"""Build or audit the frozen Unicode Nd compatibility profiles.

The frozen range files and their public digests are normative.  This script is
only a deterministic maintenance and audit aid; it is not protocol authority
and it does not consult the host Unicode database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UNICODE_DIR = ROOT / "conformance" / "legacy_v1_operational_policy" / "unicode"
REGISTRY_PATH = UNICODE_DIR / "profiles.json"

PROFILE_SOURCES = {
    "13.0.0": {
        "profile_id": "AELITIUM_UCD_ND_13_0_0_1",
        "archive_sha256": "2f76973b4d36ae45584f5a45ec65b47138932d777dd23a5669c89535ef3da951",
        "source_sha256": "4502f0969e4e6558c4b4c6ca4c23dad70b863d61dd3d5eed1a62a6c3c99fd570",
    },
    "14.0.0": {
        "profile_id": "AELITIUM_UCD_ND_14_0_0_1",
        "archive_sha256": "033a5276b5d7af8844589f8e3482f3977a8385e71d107d375055465178c23600",
        "source_sha256": "cde679c8461976ed40d7edf61ae98cbb947540831f06f5bc7da7decbf91a1420",
    },
    "15.0.0": {
        "profile_id": "AELITIUM_UCD_ND_15_0_0_1",
        "archive_sha256": "5fbde400f3e687d25cc9b0a8d30d7619e76cb2f4c3e85ba9df8ec1312cb6718c",
        "source_sha256": "fe29a45c0882500e591140aaa5c4f5067e6a5d746806148af34400c48b9c06f9",
    },
}

SOURCE_MEMBER = "extracted/DerivedGeneralCategory.txt"
RANGE_LINE = re.compile(rb"[0-9A-F]{6}\.\.[0-9A-F]{6}\n")


class AuditError(ValueError):
    """Raised when frozen data or supplied provenance disagrees."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_zip_args(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        version, separator, raw_path = value.partition("=")
        if not separator or version not in PROFILE_SOURCES or not raw_path:
            raise AuditError(
                "--ucd-zip must be one of "
                "13.0.0=PATH, 14.0.0=PATH, or 15.0.0=PATH"
            )
        if version in result:
            raise AuditError(f"duplicate --ucd-zip version: {version}")
        result[version] = Path(raw_path)
    return result


def _nd_ranges(source: bytes, version: str) -> list[tuple[int, int]]:
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"Unicode {version} source is not UTF-8") from exc
    marker = f"# DerivedGeneralCategory-{version}.txt"
    if not text.startswith(marker + "\n"):
        raise AuditError(f"Unicode {version} source has the wrong version marker")

    points: list[tuple[int, int]] = []
    for raw_line in text.splitlines():
        data = raw_line.partition("#")[0].strip()
        if not data:
            continue
        left, separator, category = data.partition(";")
        if not separator or category.strip() != "Nd":
            continue
        value = left.strip()
        if ".." in value:
            first_text, last_text = value.split("..", 1)
        else:
            first_text = last_text = value
        first = int(first_text, 16)
        last = int(last_text, 16)
        if first > last:
            raise AuditError(f"Unicode {version} contains a reversed Nd range")
        points.append((first, last))

    points.sort()
    merged: list[tuple[int, int]] = []
    for first, last in points:
        if merged and first <= merged[-1][1]:
            raise AuditError(f"Unicode {version} contains overlapping Nd ranges")
        if merged and first == merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], last)
        else:
            merged.append((first, last))
    return merged


def _range_bytes(ranges: list[tuple[int, int]]) -> bytes:
    return "".join(
        f"{first:06X}..{last:06X}\n" for first, last in ranges
    ).encode("ascii")


def _profile_from_zip(version: str, path: Path) -> tuple[dict[str, Any], bytes]:
    archive = path.read_bytes()
    expected = PROFILE_SOURCES[version]
    if _sha256(archive) != expected["archive_sha256"]:
        raise AuditError(f"Unicode {version} archive SHA-256 mismatch")
    try:
        with zipfile.ZipFile(path) as archive_file:
            source = archive_file.read(SOURCE_MEMBER)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise AuditError(f"cannot read Unicode {version} archive: {exc}") from exc
    if _sha256(source) != expected["source_sha256"]:
        raise AuditError(f"Unicode {version} source SHA-256 mismatch")

    ranges = _nd_ranges(source, version)
    frozen = _range_bytes(ranges)
    profile = {
        "archive_sha256": expected["archive_sha256"],
        "code_point_count": sum(last - first + 1 for first, last in ranges),
        "profile_id": expected["profile_id"],
        "range_count": len(ranges),
        "range_file": f"nd-{version}.txt",
        "range_file_sha256": _sha256(frozen),
        "source_file": SOURCE_MEMBER,
        "source_file_sha256": expected["source_sha256"],
        "source_url": f"https://www.unicode.org/Public/{version}/ucd/UCD.zip",
        "unicode_version": version,
    }
    return profile, frozen


def _registry(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "canonical_range_format": "AELITIUM-UNICODE-ND-RANGES-1",
        "contract": "aelitium-unicode-nd-profiles-v1",
        "license": "Unicode License v3",
        "profiles": profiles,
        "status": "NORMATIVE-UNRELEASED",
    }


def _registry_bytes(registry: dict[str, Any]) -> bytes:
    return (json.dumps(registry, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_frozen_ranges(data: bytes, label: str) -> list[tuple[int, int]]:
    if not data or not data.endswith(b"\n") or b"\r" in data:
        raise AuditError(f"{label} must be nonempty LF-terminated ASCII")
    lines = data.splitlines(keepends=True)
    if any(RANGE_LINE.fullmatch(line) is None for line in lines):
        raise AuditError(f"{label} has a noncanonical range line")
    ranges = [
        (int(line[0:6], 16), int(line[8:14], 16))
        for line in lines
    ]
    previous_last = -2
    for first, last in ranges:
        if first > last or first <= previous_last + 1:
            raise AuditError(f"{label} ranges are overlapping, adjacent, or unsorted")
        previous_last = last
    return ranges


def _audit_frozen() -> dict[str, Any]:
    try:
        registry_bytes = REGISTRY_PATH.read_bytes()
        registry = json.loads(registry_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read frozen Unicode registry: {exc}") from exc
    if registry_bytes != _registry_bytes(registry):
        raise AuditError("Unicode registry is not canonical indented JSON")
    if registry.get("contract") != "aelitium-unicode-nd-profiles-v1":
        raise AuditError("Unicode registry contract mismatch")
    if registry.get("status") != "NORMATIVE-UNRELEASED":
        raise AuditError("Unicode registry status mismatch")
    if registry.get("canonical_range_format") != "AELITIUM-UNICODE-ND-RANGES-1":
        raise AuditError("Unicode registry range format mismatch")
    if registry.get("license") != "Unicode License v3":
        raise AuditError("Unicode registry license mismatch")

    profiles = registry.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != len(PROFILE_SOURCES):
        raise AuditError("Unicode registry profile count mismatch")
    versions = [profile.get("unicode_version") for profile in profiles]
    if versions != list(PROFILE_SOURCES):
        raise AuditError("Unicode registry profiles are not in fixed version order")

    for profile in profiles:
        version = profile["unicode_version"]
        expected = PROFILE_SOURCES[version]
        if profile.get("profile_id") != expected["profile_id"]:
            raise AuditError(f"Unicode {version} profile identifier mismatch")
        if profile.get("archive_sha256") != expected["archive_sha256"]:
            raise AuditError(f"Unicode {version} archive provenance mismatch")
        if profile.get("source_file") != SOURCE_MEMBER:
            raise AuditError(f"Unicode {version} source member mismatch")
        if profile.get("source_file_sha256") != expected["source_sha256"]:
            raise AuditError(f"Unicode {version} source provenance mismatch")
        path = UNICODE_DIR / profile["range_file"]
        data = path.read_bytes()
        ranges = _parse_frozen_ranges(data, path.name)
        if _sha256(data) != profile.get("range_file_sha256"):
            raise AuditError(f"Unicode {version} frozen range digest mismatch")
        if len(ranges) != profile.get("range_count"):
            raise AuditError(f"Unicode {version} frozen range count mismatch")
        count = sum(last - first + 1 for first, last in ranges)
        if count != profile.get("code_point_count"):
            raise AuditError(f"Unicode {version} code-point count mismatch")
        if not any(first <= 0x30 and 0x39 <= last for first, last in ranges):
            raise AuditError(f"Unicode {version} profile omits ASCII digits")
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ucd-zip",
        action="append",
        default=[],
        metavar="VERSION=PATH",
        help="audit or build from an exact Unicode UCD.zip archive",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write frozen profiles; requires all three exact archives",
    )
    args = parser.parse_args(argv)

    try:
        zip_paths = _parse_zip_args(args.ucd_zip)
        if args.write and set(zip_paths) != set(PROFILE_SOURCES):
            raise AuditError("--write requires exact archives for all three versions")

        rebuilt: dict[str, tuple[dict[str, Any], bytes]] = {}
        for version, path in zip_paths.items():
            rebuilt[version] = _profile_from_zip(version, path)

        if args.write:
            UNICODE_DIR.mkdir(parents=True, exist_ok=True)
            ordered_profiles = []
            for version in PROFILE_SOURCES:
                profile, data = rebuilt[version]
                (UNICODE_DIR / profile["range_file"]).write_bytes(data)
                ordered_profiles.append(profile)
            REGISTRY_PATH.write_bytes(_registry_bytes(_registry(ordered_profiles)))

        frozen = _audit_frozen()
        for version, (rebuilt_profile, rebuilt_bytes) in rebuilt.items():
            frozen_profile = next(
                profile
                for profile in frozen["profiles"]
                if profile["unicode_version"] == version
            )
            if rebuilt_profile != frozen_profile:
                raise AuditError(f"Unicode {version} frozen metadata differs from source")
            if rebuilt_bytes != (UNICODE_DIR / frozen_profile["range_file"]).read_bytes():
                raise AuditError(f"Unicode {version} frozen ranges differ from source")
    except (AuditError, OSError, KeyError, TypeError) as exc:
        print(f"[FAIL] Unicode Nd profile audit: {exc}", file=sys.stderr)
        return 1

    print(
        "[PASS] Unicode Nd profile audit: "
        + ", ".join(
            f"{profile['unicode_version']}={profile['range_file_sha256']}"
            for profile in frozen["profiles"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
