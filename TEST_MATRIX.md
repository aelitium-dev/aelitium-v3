# TEST_MATRIX.md — AELITIUM Determinism / Offline Verification

## Scope
This matrix defines the minimum acceptance tests for determinism, tamper detection, and cross-machine verification (Machine B).

## Environment
- Machine A: Ubuntu (WSL distro A) — bundle creation
- Bridge: Windows Desktop path `/mnt/c/Users/CATARINA-AELITIUM/Desktop/`
- Machine B: Ubuntu-B (WSL distro B) — verification & repro

## Artifacts
- Bundle: `aelitium-v3_bundle.tar.gz`
- Bundle hash: `aelitium-v3_bundle.tar.gz.sha256`
- Output dir: `release_output/`
- Manifest: `release_output/manifest.json`
- Evidence: `release_output/evidence_pack.json`

---

## T1 — Bundle exists and is transferable (A → Windows)
**Goal:** Ensure bundle + sha256 exist and are copied to Windows Desktop bridge.

**Run on:** Machine A (Ubuntu)

**Commands:**
- `ls -la aelitium-v3_bundle.tar.gz*`
- `cp aelitium-v3_bundle.tar.gz* /mnt/c/Users/CATARINA-AELITIUM/Desktop/`
- `ls -la /mnt/c/Users/CATARINA-AELITIUM/Desktop/aelitium-v3_bundle.tar.gz*`

**PASS criteria:**
- Both files exist on Windows Desktop:
  - `aelitium-v3_bundle.tar.gz`
  - `aelitium-v3_bundle.tar.gz.sha256`

---

## T2 — Bundle integrity on Machine B (sha256)
**Goal:** Verify the transported bundle is intact.

**Run on:** Machine B (Ubuntu-B)

**Commands:**
- `cp /mnt/c/Users/CATARINA-AELITIUM/Desktop/aelitium-v3_bundle.tar.gz* ~/machine_b/`
- `cd ~/machine_b`
- `sha256sum -c aelitium-v3_bundle.tar.gz.sha256`

**PASS criteria:**
- Output contains: `aelitium-v3_bundle.tar.gz: OK`

**FAIL criteria:**
- Any non-OK result → STOP release.

---

## T3 — VERIFY is VALID (offline verification)
**Goal:** Verification succeeds with expected evidence/manifest.

**Run on:** Machine B

**Commands:**
- `python3 engine/cli.py pack --input tests/fixtures/input_min.json --out release_output`
- `python3 engine/cli.py verify --manifest release_output/manifest.json --evidence release_output/evidence_pack.json`

**PASS criteria:**
- `STATUS=VALID rc=0`
- shell rc == 0

---

## T4 — REPRO (2 runs = same hash)
**Goal:** Reproducibility holds with stable hash output.

**Run on:** Machine B

**Commands:**
- `python3 engine/cli.py repro --input tests/fixtures/input_min.json`

**PASS criteria:**
- `REPRO=PASS`
- stable hash reported
- shell rc == 0

---

## T5 — TAMPER detection (must fail)
**Goal:** Any modification to evidence invalidates verification.

**Run on:** Machine B

**Commands:**
- Copy evidence → tampered file
- Modify `canonical_payload` ("42" → "43")
- `set -o pipefail`
- Verify tampered evidence:
  - `python3 engine/cli.py verify --manifest ... --evidence ...tampered... |& tee ...`
  - capture rc (`rc=$?`) and assert rc != 0

**PASS criteria:**
- `STATUS=INVALID rc!=0` (e.g. rc=2)
- captured `RC_TAMPER != 0`

**FAIL criteria:**
- Tampered evidence verifies as VALID OR captured rc == 0 → STOP release.

---

## Release Gate
No release is allowed unless:
- T1–T5 all PASS
- An Evidence Log entry is recorded with:
  - Input file hash
  - Manifest hash
  - Git commit hash
  - Date (UTC)
  - Machine identifier
