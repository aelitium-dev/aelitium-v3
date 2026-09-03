# AELITIUM — Index

<!-- "v3" in the repo name denotes the third-generation product codebase,
     not a package semantic-version major. Current published package: 0.3.0;
     repository development version: 0.4.0. -->

## Entry
- docs/ENTRYPOINT.md

## Threat / Trust
- docs/SYSTEM_MAP.md

## Documentation boundary
- docs/DOCS_SYSTEM.md

## Offline verification
- docs/OFFLINE_VERIFIER.md
- scripts/offline_verify.sh
- scripts/verify_release_zip.sh

## Authority / Release
- docs/RELEASE_PROCESS.md (current release authority)
- scripts/authority_status.sh
- scripts/gate_release.sh
- scripts/release_rc.sh
- scripts/make_release_zip.sh

## Engine
- engine/cli.py (pack, verify, repro)
- engine/pack.py
- engine/verify.py (if present)
- engine/repro.py (if present)

## Governance evidence
- docs/EVIDENCE_LOG.md
