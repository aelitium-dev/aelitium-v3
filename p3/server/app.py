"""
P3 — Release Authority as a Service
FastAPI application skeleton.

Start with:
    pip install fastapi uvicorn
    AEL_ED25519_PRIVKEY_B64=<key> uvicorn p3.server.app:app --reload

Endpoints:
    GET  /v1/authority   → authority public key + fingerprint
    POST /v1/sign        → sign a subject hash, return receipt_v1
    POST /v1/verify      → verify a receipt signature
"""
from __future__ import annotations

# NOTE: fastapi is not in pyproject.toml yet — add before running.
# pip install fastapi uvicorn
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    raise ImportError("Install FastAPI: pip install fastapi uvicorn")

from .models import SignRequest, Receipt, AuthorityInfo, VerifyResponse
from .signing import (
    authority_public_key_b64,
    authority_fingerprint,
    sign_receipt,
    verify_receipt_signature,
)

app = FastAPI(
    title="AELITIUM Release Authority",
    description="Cryptographic signing node for AI outputs and release bundles.",
    version="0.1.0",
)


@app.get("/v1/authority", response_model=AuthorityInfo)
def get_authority() -> AuthorityInfo:
    """Return the authority's current public key and fingerprint."""
    return AuthorityInfo(
        public_key_b64=authority_public_key_b64(),
        fingerprint=authority_fingerprint(),
        valid_from="2026-03-04T00:00:00Z",
    )


@app.post("/v1/sign", response_model=Receipt)
def sign(req: SignRequest) -> Receipt:
    """
    Sign a subject hash. Returns a receipt_v1 with Ed25519 signature.

    The authority never receives the original content — only the hash.
    """
    receipt_dict = sign_receipt(
        subject_hash=req.subject_hash_sha256,
        subject_type=req.subject_type,
    )
    return Receipt(**receipt_dict)


@app.post("/v1/verify", response_model=VerifyResponse)
def verify(receipt: Receipt) -> VerifyResponse:
    """Verify an existing receipt's Ed25519 signature."""
    fp = authority_fingerprint()
    valid = verify_receipt_signature(receipt.model_dump())

    if valid:
        return VerifyResponse(status="VALID", rc=0, authority_fingerprint=fp)
    else:
        return VerifyResponse(
            status="INVALID",
            rc=2,
            authority_fingerprint=fp,
            reason="SIGNATURE_MISMATCH",
        )
