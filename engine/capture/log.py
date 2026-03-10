"""
Tamper-evident evidence log — append-only chain of custody.
Each entry references the hash of the previous entry.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..canonical import canonical_json, sha256_hash


class EvidenceLog:
    LOG_FILE = "evidence_log.jsonl"

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _log_path(self) -> Path:
        return self.log_dir / self.LOG_FILE

    def _read_entries(self) -> list:
        if not self._log_path.exists():
            return []
        entries = []
        for line in self._log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def append(self, bundle_dir: Path, ai_hash: str) -> str:
        """Append an entry. Returns the entry_hash."""
        entries = self._read_entries()
        prev_hash = entries[-1]["entry_hash"] if entries else "genesis"
        seq = len(entries) + 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = {
            "seq": seq,
            "ts_utc": ts,
            "bundle_hash": ai_hash,
            "bundle_dir": str(bundle_dir),
            "prev_hash": prev_hash,
            "entry_hash": "",
        }
        entry["entry_hash"] = sha256_hash(canonical_json(entry))
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry["entry_hash"]

    def verify_chain(self) -> bool:
        """Verify the chain is intact."""
        entries = self._read_entries()
        if not entries:
            return True
        for i, entry in enumerate(entries):
            stored_hash = entry["entry_hash"]
            check_entry = {**entry, "entry_hash": ""}
            computed = sha256_hash(canonical_json(check_entry))
            if computed != stored_hash:
                return False
            expected_prev = "genesis" if i == 0 else entries[i - 1]["entry_hash"]
            if entry["prev_hash"] != expected_prev:
                return False
        return True
