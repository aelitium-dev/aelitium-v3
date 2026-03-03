# Session State — AELITIUM v3

Este ficheiro permite retomar o trabalho em qualquer sessão nova.

## HEAD actual (Machine A)
`966d6077f3072b03cdce656e162fb526f0919479`

## O que está feito (Foundation SDK)

| # | EPIC | Estado |
|---|------|--------|
| 1 | Commit baseline | ✅ |
| 2 | EPIC-1: fluxo offline (dir+zip+tamper) A+B | ✅ |
| 3 | EPIC-2: ZIP determinístico cross-machine | ✅ |
| 4 | EPIC-3: Bundle Contract 1.1 frozen | ✅ |
| 5 | EPIC-4: CLI instalável (pip install .) | ✅ |
| 6 | EPIC-5: Ed25519 signing | ✅ |
| 7 | EPIC-6: Testes sistémicos 20/20 | ✅ |
| 8 | EPIC-7: Docs alinhadas | ✅ |

## Próximo passo imediato
**Task #9 — Release v0.2.0 formal**

```bash
# Machine A — gate + evidence A
source scripts/use_test_signing_key.sh
./scripts/gate_release.sh v0.2.0 inputs/minimal_input_v1.json
# → escrever evidence A em governance/logs/EVIDENCE_LOG.md
# → commit + push

# Machine B — tag + evidence B
# (sync via tar ou git)
source scripts/use_test_signing_key.sh
./scripts/gate_release.sh v0.2.0 inputs/minimal_input_v1.json
# → criar tag v0.2.0 (Machine B é a authority)
# → escrever evidence B em governance/logs/EVIDENCE_LOG.md
# → git push --tags
```

Checklist completo: `docs/RELEASE_CHECKLIST_v0.2.0.md`

## Roadmap macro (5 produtos)
1. ✅ SDK foundation (fechar com v0.2.0)
2. ⏳ AI Output Integrity Layer
3. ⏳ Release Authority as a Service
4. ⏳ Data Integrity Platform
5. ⏳ Tokenization Trust Fabric
6. ⏳ Market: Phase 4 feedback loop (MARKET_FEEDBACK_LOG.md)
