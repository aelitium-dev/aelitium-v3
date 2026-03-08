# AELITIUM — Python Integration Example

> How to add cryptographic evidence to every AI output in a production pipeline.

---

## Pattern

```
LLM call
  ↓
build ai_output_v1
  ↓
aelitium pack --json      ← fail-closed: exception if rc != 0
  ↓
store (ai_hash_sha256, evidence_uri)
  ↓
downstream processing
```

The hash is the cryptographic ID of the output. Store it anywhere — DB, log, trace.

---

## Drop-in helper

```python
# aelitium_client.py
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


class AelitiumError(RuntimeError):
    """Raised when aelitium returns a non-zero exit code."""


def build_ai_output(model: str, prompt: str, output: str,
                    run_id: str | None = None) -> dict:
    """Construct a valid ai_output_v1 object."""
    return {
        "schema_version": "ai_output_v1",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
        "prompt": prompt,
        "output": output,
        "metadata": {"run_id": run_id or str(uuid.uuid4())},
    }


def pack_ai_output(ai_output: dict, evidence_dir: Path,
                   aelitium_cwd: Path = Path(".")) -> dict:
    """
    Pack an ai_output_v1 into a cryptographic evidence bundle.

    Returns the parsed JSON result: {"status":"OK","rc":0,"ai_hash_sha256":"..."}.
    Raises AelitiumError if packing fails (fail-closed).
    """
    input_path = evidence_dir / "ai_output.json"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(ai_output, sort_keys=True), encoding="utf-8")

    result = subprocess.run(
        ["python3", "-m", "engine.ai_cli", "pack",
         "--input", str(input_path),
         "--out", str(evidence_dir),
         "--json"],
        capture_output=True,
        text=True,
        cwd=aelitium_cwd,
    )

    if result.returncode != 0:
        raise AelitiumError(
            f"aelitium pack failed (rc={result.returncode}): {result.stderr}"
        )

    return json.loads(result.stdout.strip())
```

---

## FastAPI worker example

```python
# worker.py
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aelitium_client import build_ai_output, pack_ai_output, AelitiumError

app = FastAPI()
EVIDENCE_BASE = Path("/var/evidence")        # or s3:// via mounted path
AELITIUM_ROOT = Path("/opt/aelitium-v3")    # project root


class InferenceRequest(BaseModel):
    prompt: str
    model: str = "gpt-4o"


class InferenceResponse(BaseModel):
    run_id: str
    output: str
    ai_hash_sha256: str
    evidence_uri: str


@app.post("/infer", response_model=InferenceResponse)
def infer(req: InferenceRequest) -> InferenceResponse:
    run_id = str(uuid.uuid4())

    # --- 1. call LLM (replace with your client) ---
    raw_output = call_llm(req.model, req.prompt)   # your LLM call here

    # --- 2. build ai_output_v1 ---
    ai_output = build_ai_output(
        model=req.model,
        prompt=req.prompt,
        output=raw_output,
        run_id=run_id,
    )

    # --- 3. pack + fail-closed ---
    evidence_dir = EVIDENCE_BASE / run_id
    try:
        pack_result = pack_ai_output(ai_output, evidence_dir, AELITIUM_ROOT)
    except AelitiumError as e:
        # fail-closed: do NOT return output if evidence cannot be generated
        raise HTTPException(status_code=500, detail=str(e))

    ai_hash = pack_result["ai_hash_sha256"]
    evidence_uri = str(evidence_dir)  # swap for s3:// key in production

    # --- 4. store in your DB / tracing system ---
    store_evidence_record(run_id, ai_hash, evidence_uri)   # your storage here

    return InferenceResponse(
        run_id=run_id,
        output=raw_output,
        ai_hash_sha256=ai_hash,
        evidence_uri=evidence_uri,
    )
```

---

## Verification (audit / debugging)

```python
import subprocess
import json
from pathlib import Path


def verify_evidence(evidence_uri: str, expected_hash: str,
                    aelitium_cwd: Path = Path(".")) -> bool:
    """
    Verify that an evidence bundle is intact.
    Returns True if VALID, False if INVALID or any error.
    """
    result = subprocess.run(
        ["python3", "-m", "engine.ai_cli", "verify",
         "--out", evidence_uri,
         "--json"],
        capture_output=True,
        text=True,
        cwd=aelitium_cwd,
    )

    if result.returncode != 0:
        return False

    data = json.loads(result.stdout.strip())
    return (data.get("status") == "VALID"
            and data.get("ai_hash_sha256") == expected_hash)


# Example: audit endpoint
@app.get("/audit/{run_id}")
def audit(run_id: str):
    record = fetch_evidence_record(run_id)  # your DB lookup
    valid = verify_evidence(
        evidence_uri=record["evidence_uri"],
        expected_hash=record["ai_hash_sha256"],
    )
    return {
        "run_id": run_id,
        "integrity": "VALID" if valid else "INVALID",
        "ai_hash_sha256": record["ai_hash_sha256"],
    }
```

---

## What gets stored per inference

| Field | Where | Purpose |
|-------|-------|---------|
| `run_id` | DB / trace | Link to evidence |
| `ai_hash_sha256` | DB / trace | Cryptographic ID of the output |
| `evidence_uri` | DB | Path/key to `ai_canonical.json` + `ai_manifest.json` |
| `ai_output.json` | Evidence dir | Original output (archived) |
| `ai_canonical.json` | Evidence dir | Deterministic, sorted-key JSON |
| `ai_manifest.json` | Evidence dir | Schema, hash, timestamp |

---

## Key properties

- **Fail-closed**: if `pack` fails, the inference endpoint returns 500 — no output is returned without evidence
- **Offline verification**: `verify` never requires network access
- **Deterministic**: same AI output always produces the same `ai_hash_sha256`
- **Auditable**: `ai_manifest.json` records model, schema, timestamp, canonicalization method
