# Evidence Log

Each official release must record:

* Input file hash
* Manifest hash
* Git commit hash
* Date
* Machine identifier

No release without log entry.



Evidence Log

============



Release Date (UTC):

2026-02-24T21:15:18Z



Machine Identifier:

Hostname: AELITIUM-DEV

OS: Ubuntu 24.04.4 LTS

Environment: Ubuntu-B (WSL)



Git Commit:

81cb70f2670e48abb3e1c72a92f44befc865671d



Input File:

tests/fixtures/input\_min.json

SHA256:

a2ed6bd84dd218b28fb3b808c6e56c9255872fc1fa1dc1821c78846f57400d6e



Manifest File:

release\_output/manifest.json

SHA256:

60d2f6daf81aa30854182c84a6433a5f6095d63812be3455ab3cbb5df42e0836



Machine B Validation Results:

VERIFY: STATUS=VALID rc=0

REPRO:  PASS hash=59987e2be6fd92e2f9258f315f056ee1161f02a0090433924073d3fd9ab40abd rc=0

TAMPER: STATUS=INVALID rc=2 (pipefail enforced)



Policy:

No release without log entry.


## 2026-02-25T22:06:15Z — RC11 + Deterministic ZIP (Authority B)
- machine: B
- git_commit: ab7eb67
- authority: GO (REMOTE_MAIN == HEAD)
- repro: PASS
- bundle_determinism: PASS (run1 == run2)
- tag: v3.0.0-rc11 (pushed)
- zip_determinism: GO
- zip_sha256: a389d6aa65762ae48889818925ef6b9a95432946c029d46191e1af1565c35060
- offline_verify: GO

## 2026-02-26 23:53:11Z — Governance consolidation (CORE + Reference sealing)

- CORE canonical docs created:
  C:\Users\CATARINA-AELITIUM\AELITIUM_CORE_CLEAN\_CONSOLIDATED\00_CANONICAL\
  (6 files: CANONICAL_INDEX, SYSTEM_MAP, OPERATOR_GUIDE, PHASES_0_to_4, PRODUCTS_3_OPTIONS, GOVERNANCE_MODEL)

- Reference demo sealed (ARCHIVED_REFERENCE) with inventory + SHA256:
  C:\Users\CATARINA-AELITIUM\AELITIUM_CORE_CLEAN\_CONSOLIDATED\20_NOTES_HIGH_SIGNAL\ΛELITIUM_TECH_REF\aelitium-demo\
  Files: ARCHIVE_STAMP.txt, INVENTORY_FILES.csv, INVENTORY_FILES.sha256

- Policy confirmed: official engine = aelitium-v3 only; everything else is reference/archive.


---

# Release Entry Template (Canonical)

## YYYY-MM-DDTHH:MM:SSZ — Release vX.Y.Z

Machine A:
- Determinism: PASS / FAIL
- Hash run1:
- Hash run2:

Machine B:
- Verify: PASS / FAIL
- Repro: PASS / FAIL
- Tamper test (expected INVALID): PASS / FAIL

Gate:
- Result: PASS / FAIL
- Tag created: yes / no

Git:
- Tree clean: yes / no

Notes:
- Any deviation must be documented.
- If any CRITICAL fails → release invalid.

---

## 2026-02-27T00:18:54Z — Gate attempt v0.1.0

- gate_release.sh result: NO_GO
- reason: DIRTY_GIT_TREE
- action: commit canonical docs/inputs and ignore runtime artifacts, then re-run gate.


## 2026-02-27T00:20:21Z — Gate GO v0.1.0 (tag created)

Gate:
- Result: GO
- Tag: v0.1.0

Determinism (bundle script):
- BUNDLE_SHA_RUN1=1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646
- BUNDLE_SHA_RUN2=1daf9b8cc3b9d4700283bf526e4230b53c5899da3036fc6da5e04c36c3978646

Authority checks (Machine B):
- Verify: STATUS=VALID rc=0
- Repro: PASS hash=44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a rc=0
- Tamper: STATUS=INVALID rc=2 (expected)  [validated in this cycle]

Input:
- inputs/minimal_input_v1.json sha256=34d8739e7ba3cd7dab4327a0c48fce70e642b967969cad1a73f2e1713ef3d413

## EVIDENCE_ENTRY v1 | tag=v0.1.0
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v0.1.0",
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
  "bundle_sha256": null,
  "x_legacy_source": "2026-02-27 Gate GO section"
}
```

## EVIDENCE_ENTRY v1 | tag=v0.1.1-rc1
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v0.1.1-rc1",
  "ts_utc": "2026-02-27T16:21:51Z",
  "input_sha256": "a2ed6bd84dd218b28fb3b808c6e56c9255872fc1fa1dc1821c78846f57400d6e",
  "manifest_sha256": "4ac6d98e5b6c629b042d49b4875d6696081b019c9a929c9f8c985c3b9575984b",
  "evidence_sha256": "237d44c22b8c9b10b19a20c8bccc6808969e994672bcf11d0d0ccf19bf458f4e",
  "verification_keys_sha256": "4096f8f49e938576a5aa15e587b3f56b052b5c4ec60b4c95a745e84f363414e5",
  "bundle_sha_run1": "f1b0ab2f28dd32b94f8074ae6a4f1fd4311dcd35321786693cf2e0698723689f",
  "bundle_sha_run2": "f1b0ab2f28dd32b94f8074ae6a4f1fd4311dcd35321786693cf2e0698723689f",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "B",
  "machine_id": "AELITIUM-DEV|6cf43cdaa0784741ae3e87878fe7e009",
  "sync_mode": "remote",
  "bundle_sha256": null,
  "x_tag_sig_fpr": "SHA256:/28eDKiHP8hmW/TEyTO9aacmw+7p11pOB3sF09EVuwo"
}
```

## EVIDENCE_ENTRY v1 | tag=v0.1.2-rc1
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v0.1.2-rc1",
  "ts_utc": "2026-02-27T17:39:36Z",
  "input_sha256": "34d8739e7ba3cd7dab4327a0c48fce70e642b967969cad1a73f2e1713ef3d413",
  "manifest_sha256": "4ac6d98e5b6c629b042d49b4875d6696081b019c9a929c9f8c985c3b9575984b",
  "evidence_sha256": "237d44c22b8c9b10b19a20c8bccc6808969e994672bcf11d0d0ccf19bf458f4e",
  "verification_keys_sha256": "4096f8f49e938576a5aa15e587b3f56b052b5c4ec60b4c95a745e84f363414e5",
  "bundle_sha_run1": "ce3093f1344e25a4e36f389e8817393c52674ef8f1abda692f10997eab3580ea",
  "bundle_sha_run2": "ce3093f1344e25a4e36f389e8817393c52674ef8f1abda692f10997eab3580ea",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "A",
  "machine_id": "A|AELITIUM-DEV|6cf43cdaa0784741ae3e87878fe7e009",
  "sync_mode": "remote",
  "bundle_sha256": null,
  "x_tag_sig_fpr": null
}
```

## EVIDENCE_ENTRY v1 | tag=v0.1.2-rc1
```json
{
  "schema": "evidence_entry_v1",
  "tag": "v0.1.2-rc1",
  "ts_utc": "2026-02-27T17:57:40Z",
  "input_sha256": "34d8739e7ba3cd7dab4327a0c48fce70e642b967969cad1a73f2e1713ef3d413",
  "manifest_sha256": "4ac6d98e5b6c629b042d49b4875d6696081b019c9a929c9f8c985c3b9575984b",
  "evidence_sha256": "237d44c22b8c9b10b19a20c8bccc6808969e994672bcf11d0d0ccf19bf458f4e",
  "verification_keys_sha256": "4096f8f49e938576a5aa15e587b3f56b052b5c4ec60b4c95a745e84f363414e5",
  "bundle_sha_run1": "ce3093f1344e25a4e36f389e8817393c52674ef8f1abda692f10997eab3580ea",
  "bundle_sha_run2": "ce3093f1344e25a4e36f389e8817393c52674ef8f1abda692f10997eab3580ea",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "B",
  "machine_id": "B|AELITIUM-DEV|6cf43cdaa0784741ae3e87878fe7e009",
  "sync_mode": "remote",
  "bundle_sha256": null,
  "x_offline_verify_rc": 0,
  "x_git_tag_verify": "GOOD",
  "x_tag_commit": "505c2562bd1559e0a7b23f56c47945ed6fd6f502",
  "x_tag_sig_fpr": "SHA256:/28eDKiHP8hmW/TEyTO9aacmw+7p11pOB3sF09EVuwo"
}
```
