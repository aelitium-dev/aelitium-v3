#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_evidence_log.py"
GOOD_SHA = "a" * 64


def make_entry(tag: str = "v9.9.9-rc1", **overrides):
    entry = {
        "schema": "evidence_entry_v1",
        "tag": tag,
        "ts_utc": "2026-02-27T18:00:00Z",
        "input_sha256": GOOD_SHA,
        "manifest_sha256": GOOD_SHA,
        "evidence_sha256": GOOD_SHA,
        "verification_keys_sha256": GOOD_SHA,
        "bundle_sha_run1": GOOD_SHA,
        "bundle_sha_run2": GOOD_SHA,
        "verify_rc": 0,
        "repro_rc": 0,
        "tamper_rc": 2,
        "machine_role": "A",
        "machine_id": "A|test|machine-id",
        "sync_mode": "remote",
        "bundle_sha256": None,
    }
    entry.update(overrides)
    return entry


def render_log(entries):
    blocks = []
    for entry in entries:
        tag = entry["tag"]
        body = json.dumps(entry, ensure_ascii=True, indent=2, sort_keys=True)
        blocks.append(f"## EVIDENCE_ENTRY v1 | tag={tag}\n```json\n{body}\n```\n")
    return "\n".join(blocks)


class TestValidateEvidenceLog(unittest.TestCase):
    def run_validator(self, tag: str, content: str, required_machine_role: str = "ANY"):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "EVIDENCE_LOG.md"
            log.write_text(content, encoding="utf-8")
            cp = subprocess.run(
                [
                    "python3",
                    str(VALIDATOR),
                    "--tag",
                    tag,
                    "--log",
                    str(log),
                    "--required-machine-role",
                    required_machine_role,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            return cp.returncode, cp.stdout + cp.stderr

    def test_valid_entry_passes(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(tag, render_log([make_entry(tag)]))
        self.assertEqual(rc, 0, out)
        self.assertIn("EVIDENCE_STATUS=PASS", out)

    def test_bad_hash_fails(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag, render_log([make_entry(tag, input_sha256="abc")])
        )
        self.assertEqual(rc, 2, out)
        self.assertIn("BAD_INPUT_SHA256", out)

    def test_bad_machine_role_fails(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag, render_log([make_entry(tag, machine_role="C")])
        )
        self.assertEqual(rc, 2, out)
        self.assertIn("BAD_MACHINE_ROLE", out)

    def test_tamper_rc_must_be_two(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(tag, render_log([make_entry(tag, tamper_rc=0)]))
        self.assertEqual(rc, 2, out)
        self.assertIn("TAMPER_RC_NOT_TWO", out)

    def test_duplicate_tag_fails(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(tag, render_log([make_entry(tag), make_entry(tag)]))
        self.assertEqual(rc, 2, out)
        self.assertIn("DUPLICATE_ENTRIES_FOR_TAG_REQUIRE_ROLE", out)

    def test_unknown_key_is_rejected(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag, render_log([make_entry(tag, unexpected_field="value")])
        )
        self.assertEqual(rc, 2, out)
        self.assertIn("UNKNOWN_KEYS:unexpected_field", out)

    def test_x_prefixed_extension_is_allowed(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(tag, render_log([make_entry(tag, x_note="ok")]))
        self.assertEqual(rc, 0, out)
        self.assertIn("EVIDENCE_STATUS=PASS", out)

    def test_bundle_mode_requires_bundle_hash(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag, render_log([make_entry(tag, sync_mode="bundle", bundle_sha256=None)])
        )
        self.assertEqual(rc, 2, out)
        self.assertIn("BAD_BUNDLE_SHA256", out)

    def test_required_machine_role_mismatch_fails(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag,
            render_log([make_entry(tag, machine_role="B")]),
            required_machine_role="A",
        )
        self.assertEqual(rc, 2, out)
        self.assertIn("ENTRY_NOT_FOUND_FOR_TAG_ROLE role=A", out)

    def test_required_machine_role_match_b_passes(self):
        tag = "v9.9.9-rc1"
        rc, out = self.run_validator(
            tag,
            render_log([make_entry(tag, machine_role="B")]),
            required_machine_role="B",
        )
        self.assertEqual(rc, 0, out)
        self.assertIn("EVIDENCE_STATUS=PASS", out)

    def test_dual_entries_select_by_role(self):
        tag = "v9.9.9-rc1"
        content = render_log([make_entry(tag, machine_role="A"), make_entry(tag, machine_role="B")])
        rc_a, out_a = self.run_validator(tag, content, required_machine_role="A")
        rc_b, out_b = self.run_validator(tag, content, required_machine_role="B")
        self.assertEqual(rc_a, 0, out_a)
        self.assertEqual(rc_b, 0, out_b)


if __name__ == "__main__":
    unittest.main()
