# SYSTEM MAP (1 page)

            ┌────────────────────┐
            │  Machine A (DEV)   │
            │  Ubuntu WSL        │
            │  build / pack      │
            └─────────┬──────────┘
                      │ bundle
                      ▼
            ┌────────────────────┐
            │ Artifact Bundle     │
            │ deterministic       │
            └─────────┬──────────┘
                      │ verify/repro
                      ▼
            ┌────────────────────┐
            │ Machine B           │
            │ Ubuntu-B            │
            │ authority verify    │
            └────────────────────┘

Truth chain:
- Git tags via fail-closed gate
- Evidence Log mandatory
- Offline verification supported
