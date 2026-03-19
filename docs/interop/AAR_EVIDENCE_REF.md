# AAR evidenceRef mapping

AELITIUM bundles can be referenced from AAR-style receipts using a minimal evidenceRef mapping.

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
