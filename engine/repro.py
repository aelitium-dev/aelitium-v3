import json
import os
import shutil
import sys
import tempfile
from pack import pack
from verify import verify

RC_VALID = 0
RC_INVALID = 2


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def repro(input_path: str) -> int:
    with tempfile.TemporaryDirectory(prefix="aelitium_repro_") as td:
        out1 = os.path.join(td, "run1")
        out2 = os.path.join(td, "run2")
        os.makedirs(out1, exist_ok=True)
        os.makedirs(out2, exist_ok=True)

        pack(input_path, out1)
        pack(input_path, out2)

        m1 = _read_json(os.path.join(out1, "manifest.json"))
        m2 = _read_json(os.path.join(out2, "manifest.json"))
        e1 = _read_json(os.path.join(out1, "evidence_pack.json"))
        e2 = _read_json(os.path.join(out2, "evidence_pack.json"))

        # Determinism check
        if m1.get("input_hash") != m2.get("input_hash"):
            print("REPRO=FAIL reason=manifest_hash_mismatch rc=2")
            return RC_INVALID
        if e1.get("hash") != e2.get("hash"):
            print("REPRO=FAIL reason=evidence_hash_mismatch rc=2")
            return RC_INVALID
        if e1.get("canonical_payload") != e2.get("canonical_payload"):
            print("REPRO=FAIL reason=canonical_payload_mismatch rc=2")
            return RC_INVALID

        # Verify both runs (belt & suspenders)
        rc1 = verify(os.path.join(out1, "manifest.json"), os.path.join(out1, "evidence_pack.json"))
        rc2 = verify(os.path.join(out2, "manifest.json"), os.path.join(out2, "evidence_pack.json"))
        if rc1 != 0 or rc2 != 0:
            print("REPRO=FAIL reason=verify_failed rc=2")
            return RC_INVALID

        print("REPRO=PASS hash=" + m1["input_hash"] + " rc=0")
        return RC_VALID


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: repro.py <input.json>")
        sys.exit(RC_INVALID)
    sys.exit(repro(sys.argv[1]))
