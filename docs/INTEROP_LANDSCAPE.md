# Interoperability landscape — NON-NORMATIVE

**Status:** Positioning and research context only. This document does not define
conformance, announce integrations, or add assurance claims to AELITIUM v0.4.0.
The existence of a linked project or specification says nothing about its
adoption.

AELITIUM occupies a deliberately narrow layer: portable recorded evidence and
offline verification of that evidence's internal consistency. Adjacent systems
can supply operational context, issue receipts, expose agent interactions, or
make policy decisions without becoming part of the AELITIUM verification
contract.

| Layer | Primary question | Relationship to AELITIUM | Current AELITIUM status |
|---|---|---|---|
| [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/overview/) | What happened operationally across traces, metrics, logs, and correlated context? | Complementary observability data could be linked to evidence, but telemetry is not evidence verification. | No OpenTelemetry integration implemented. |
| AELITIUM | Is this portable recorded bundle internally consistent under its declared contract when checked offline? | This is the layer implemented by the current verifier. | v0.4.0 verifies the documented bundle surface and compares selected recorded identities and response hashes. |
| [Agent Action Receipt (AAR)](https://github.com/Cyberweasel777/agent-action-receipt-spec) | What action receipt was issued, and what external evidence does it reference? | Upstream naming includes `aelitium/binding-bundle` as an `evidenceRef` type example. AELITIUM's proposed mapping remains separate from the receipt and has unresolved encoding and artifact-hash semantics. | Experimental documentation and an AAR-style example exist; schema-conformant artifact-hash interoperability and AAR verification are not implemented or claimed. |
| [Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/learn/server-concepts) | How do clients and servers expose and use tools, resources, prompts, and related interactions? | MCP is a protocol surface, while AELITIUM verifies recorded evidence artifacts. Either could provide context to a future adapter without changing the other layer's semantics. | No dedicated MCP integration implemented. |
| [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) | How are agents, tools, sessions, and workflows composed and run in that framework? | A framework could produce or consume evidence through separately designed integration code. | No dedicated Microsoft Agent Framework integration implemented. |
| Enforcement and policy engines | Should an action be allowed, denied, or blocked before execution? | Such systems may consume evidence or other inputs, but verification results are not execution decisions. | Outside AELITIUM scope. |

## Boundaries that must remain visible

- Observability does not equal evidence verification. A trace helps investigate
  execution; it does not substitute for checking a portable bundle's declared
  schema, canonical form, and hashes.
- Evidence does not equal enforcement. A verifier reports evidence properties;
  a separate policy authority decides whether an action may execute.
- A receipt does not equal its underlying evidence. A reference can bind a
  receipt field to an artifact identifier without importing that artifact's
  contents or assurance semantics.
- A mathematically valid signature does not establish that the signer identity
  is trusted. Trust requires an independently supplied trust decision or anchor.
- Internal consistency does not establish provider execution or causation. A
  self-consistent record can be checked as a record without proving the
  real-world event asserted around it.

## Practical positioning

OpenTelemetry addresses operational visibility and correlation. MCP and agent
frameworks provide interaction or execution surfaces. Receipt formats can refer
to external supporting artifacts. Enforcement systems make allow/block
decisions. AELITIUM's current role is narrower: retain portable recorded
evidence, verify its documented internal relationships offline, and report the
basis used when comparing bundles.

The existing non-normative AAR work is documented in
[`AAR_EVIDENCE_REF_MAPPING.md`](AAR_EVIDENCE_REF_MAPPING.md) and
[`interop/AAR_EVIDENCE_REF.md`](interop/AAR_EVIDENCE_REF.md), with a frozen
example at
[`examples/aar_evidence_ref_receipt.json`](../examples/aar_evidence_ref_receipt.json).
The upstream
[`receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/schema/receipt.json)
and
[`evidence-ref-receipt.json`](https://github.com/Cyberweasel777/agent-action-receipt-spec/blob/main/examples/evidence-ref-receipt.json)
currently name `aelitium/binding-bundle` as one example `evidenceRef` type, but
that naming does not establish complete interoperability. Upstream describes
the digest as a Base64URL-encoded content hash of the referenced artifact;
AELITIUM exposes `binding_hash` as a 64-hex commitment to selected recorded
request/response hashes, not as a hash of the complete bundle. The linked
materials therefore remain experimental proposals, and the local JSON is an
AAR-style conceptual sketch rather than a schema-conformant receipt.
