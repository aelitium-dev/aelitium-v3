import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "validate_evidence_log.py"
)


def make_entry(tag: str, data_overrides: dict | None = None, header_tag: str | None = None):
    base = {
        "schema": "evidence_entry_v1",
        "tag": tag,
        "ts_utc": "2026-02-27T00:20:21Z",
        "input_sha256": "34d8739e7ba3cd7dab4327a0c48fce70e642b967969cad1a73f2e1713ef3d413",
        "manifest_sha256": "4ac6d98e5b6c629b042d49b4875d6696081b019c9a929c9f8c985c3b9575984b",
        "evidence_sha256": "237d44c22b8c9b10b19a20c8bccc6808969e994672bcf11d0d0ccf19bf458f4e",
        "verification_keys_sha256": "4096f8f49e938576a5aa15e587b3f56b052b5c4ec60b4c95a745e84f363414e5",
        "bundle_sha_run1": "1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646",
        "bundle_sha_run2": "1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646",
        "verify_rc": 0,
        "repro_rc": 0,
        "tamper_rc": 2,
        "machine_role": "B",
        "machine_id": "AELITIUM-DEV|6cf43cdaa0784741ae3e87878fe7e009",
        "sync_mode": "remote",
        "bundle_sha256": None,
    }
    if data_overrides:
        base.update(data_overrides)
    section_tag = header_tag if header_tag is not None else tag
    payload = json.dumps(base, ensure_ascii=False, indent=2)
    return f"## EVIDENCE_ENTRY v1 | tag={section_tag}\n```json\n{payload}\n```\n"


def run_validator(log_text: str, tag: str) -> int:
    with tempfile.TemporaryDirectory() as td:
        log_path = Path(td) / "EVIDENCE_LOG.md"
        log_path.write_text(log_text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--log", str(log_path), "--tag", tag],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode


class ValidateEvidenceLogTests(unittest.TestCase):
    def test_valid_entry_passes(self):
        log = "# Evidence Log\n\n" + make_entry("v0.1.0")
        self.assertEqual(run_validator(log, "v0.1.0"), 0)

    def test_entry_absent_fails(self):
        log = "# Evidence Log\n\n" + make_entry("v0.2.0")
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_tag_mismatch_between_header_and_payload_fails(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0", data_overrides={"tag": "v0.1.1"}, header_tag="v0.1.0"
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_hash_truncated_fails(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0", data_overrides={"manifest_sha256": "abcd"}
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_verify_rc_not_zero_fails(self):
        log = "# Evidence Log\n\n" + make_entry("v0.1.0", data_overrides={"verify_rc": 2})
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_tamper_rc_not_two_fails(self):
        log = "# Evidence Log\n\n" + make_entry("v0.1.0", data_overrides={"tamper_rc": 0})
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_bundle_mode_without_bundle_sha_fails(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0", data_overrides={"sync_mode": "bundle", "bundle_sha256": None}
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_bundle_run_hash_mismatch_fails(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0",
            data_overrides={
                "bundle_sha_run2": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            },
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_duplicate_entries_for_same_tag_fails(self):
        log = (
            "# Evidence Log\n\n"
            + make_entry("v0.1.0")
            + "\n"
            + make_entry("v0.1.0", data_overrides={"x_note": "duplicate"})
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_unknown_key_without_x_prefix_fails(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0", data_overrides={"unexpected": "bad"}
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 2)

    def test_x_prefixed_extension_is_allowed(self):
        log = "# Evidence Log\n\n" + make_entry(
            "v0.1.0", data_overrides={"x_build_env": "authority-b"}
        )
        self.assertEqual(run_validator(log, "v0.1.0"), 0)


if __name__ == "__main__":
    unittest.main()
