import json
import tempfile
import unittest
from pathlib import Path

from engine.capture.log import EvidenceLog


class TestEvidenceLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_append_creates_file(self):
        log = EvidenceLog(self.tmp)
        log.append(Path(self.tmp) / "bundle1", "a" * 64)
        self.assertTrue((Path(self.tmp) / "evidence_log.jsonl").exists())

    def test_chain_valid_after_multiple_appends(self):
        log = EvidenceLog(self.tmp)
        log.append(Path(self.tmp) / "b1", "a" * 64)
        log.append(Path(self.tmp) / "b2", "b" * 64)
        log.append(Path(self.tmp) / "b3", "c" * 64)
        self.assertTrue(log.verify_chain())

    def test_chain_invalid_after_tamper(self):
        log = EvidenceLog(self.tmp)
        log.append(Path(self.tmp) / "b1", "a" * 64)
        log.append(Path(self.tmp) / "b2", "b" * 64)
        # Tamper: modify an entry
        log_path = Path(self.tmp) / "evidence_log.jsonl"
        lines = log_path.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["bundle_hash"] = "z" * 64
        lines[0] = json.dumps(entry)
        log_path.write_text("\n".join(lines) + "\n")
        self.assertFalse(log.verify_chain())

    def test_entry_hash_references_prev(self):
        log = EvidenceLog(self.tmp)
        h1 = log.append(Path(self.tmp) / "b1", "a" * 64)
        h2 = log.append(Path(self.tmp) / "b2", "b" * 64)
        log_path = Path(self.tmp) / "evidence_log.jsonl"
        entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        self.assertEqual(entries[1]["prev_hash"], entries[0]["entry_hash"])
