# AAR evidenceRef mapping

AELITIUM bundles can be referenced from AAR-style receipts using a minimal evidenceRef mapping.

This document defines a minimal reference shape only. It does not define a complete interoperability verification procedure, and it does not add trust semantics beyond normal AELITIUM bundle verification.

## Minimal mapping

```json
{
  "type": "aelitium/binding-bundle",
  "hash": {
    "alg": "sha256",
    "digest": "<binding_hash>"
  }
}
```

## Offline verification

```bash
aelitium verify-bundle ./bundle
```
