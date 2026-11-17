"""
P3 — Release Authority as a Service
Pydantic models for request/response contracts.
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, field_validator

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
TS_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class SignRequest(BaseModel):
    """POST /v1/sign"""
    schema_version: str = "sign_request_v1"
    subject_hash_sha256: str   # 64-hex hash of the content being attested
    subject_type: str          # e.g. "ai_output_v1", "bundle_v1"
    client_id: str             # org / API-key identifier
    meta: Optional[dict] = None  # optional: model name, run_id, ts_utc …

    @field_validator("subject_hash_sha256")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        if not HASH_RE.match(v):
            raise ValueError("subject_hash_sha256 must be 64 lowercase hex chars")
        return v


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class Receipt(BaseModel):
    """receipt_v1 — returned by POST /v1/sign"""
    schema_version: str = "receipt_v1"
    receipt_id: str                 # "rec-<date>-<nonce>"
    ts_signed_utc: str              # ISO-8601 UTC
    subject_hash_sha256: str        # echoed back from request
    subject_type: str
    authority_fingerprint: str      # SHA256 digest of authority public key
    authority_signature: str        # base64 Ed25519 sig over canonical receipt JSON


class AuthorityInfo(BaseModel):
    """GET /v1/authority"""
    schema_version: str = "authority_v1"
    public_key_b64: str             # base64 Ed25519 public key
    fingerprint: str                # SHA256 digest of public key bytes
    valid_from: str                 # ISO-8601 UTC


class VerifyResponse(BaseModel):
    """POST /v1/verify"""
    status: str                     # "VALID" | "INVALID"
    rc: int                         # 0 | 2
    authority_fingerprint: str
    reason: Optional[str] = None    # set when status=INVALID
