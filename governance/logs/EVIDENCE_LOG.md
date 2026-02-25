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
