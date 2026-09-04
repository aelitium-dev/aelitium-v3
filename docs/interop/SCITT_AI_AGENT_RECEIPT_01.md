# Experimental SCITT AI-Agent Action Receipt Mapping

**Status:** EXPERIMENTAL
**Implementation status:** BLOCKED
**Reviewed:** 2026-09-04

This document pins one external evidence family and records the mapping that
would be required before an import could be implemented safely. It is not an
executable importer, a claim of conformance, or a modification of AELITIUM's
released assurance semantics.

The companion
[`SCITT_AI_AGENT_RECEIPT_01.mapping.json`](SCITT_AI_AGENT_RECEIPT_01.mapping.json)
is the machine-readable form of the negative mapping and blocker.

## Exact source specification

| Item | Pinned value |
|---|---|
| Document | *A SCITT Profile for AI-Agent Action Receipts* |
| Version | `draft-noa-scitt-ai-agent-receipt-01` |
| Receipt wire identifier | `noa.receipt/0.1` |
| Draft date | 2026-08-15 |
| Draft expiry | 2027-02-16 |
| Authoritative text | [IETF Datatracker version 01](https://datatracker.ietf.org/doc/draft-noa-scitt-ai-agent-receipt/01/) |
| Snapshot used by the draft's non-normative implementation-status section | `NordenSoft/noa` commit `4764cab` |

Version `01` is an active individual Internet-Draft with no RFC stream or
formal standing in the IETF standards process. The Datatracker warns that an
Internet-Draft is work in progress and may be replaced or updated. A later
draft, RFC, repository revision, or similarly named receipt format is not
covered by this profile.

The older Agent Action Receipt documents already discussed in
[`AAR_EVIDENCE_REF.md`](AAR_EVIDENCE_REF.md) and
[`AAR_EVIDENCE_REF_MAPPING.md`](../AAR_EVIDENCE_REF_MAPPING.md) are a different
source family. Their fields and examples must not be substituted for the
`noa.receipt/0.1` construction.

## Candidate source scope

A future implementation would have to treat the following as two distinct
presentations:

- a bare, closed `noa.receipt/0.1` JSON receipt carrying its native Ed25519
  signature; and
- an attached-payload COSE_Sign1 envelope whose payload is the complete receipt,
  including that native signature.

The draft requires the two signatures to be checked independently. The outer
COSE signer may be a relay and cannot substitute for the native receipt signer.
This profile does not cover SCITT Transparency Receipts, transparency-log
consistency monitoring, identity-manifest or checkpoint ingestion, chain-set
completeness, or companion action-digest and settlement-evidence drafts.

## What the source format makes mechanically checkable

This table describes requirements of the pinned draft, not code implemented by
this branch.

| Source material | Mechanically checkable under the pinned draft | Boundary |
|---|---|---|
| Closed JSON receipt | Required members, JSON types, enums, lengths, digest spellings, RFC 3339 timestamp syntax, and cross-field constraints | Structural validity does not make issuer-supplied labels or timestamps true. |
| `chain.hash` | Recompute SHA-256 over the specified JCS projection, excluding exactly `chain.hash` and `sig.value` | This is a source chain-link value, not a digest of the complete receipt or an AELITIUM bundle. |
| `sig.value` | Verify the draft's domain-separated native Ed25519 construction against a caller-resolved key | Key resolution and trust remain external inputs. |
| Attached COSE_Sign1 | Check deterministic CBOR, protected algorithm/key fields, empty external AAD, attached payload, and the outer signature | Outer validity does not establish native signer authority and does not replace native verification. |
| Presented receipt set | Check the draft's sequence and predecessor-link conditions when the required set and inputs are supplied | Absence of a detected gap does not establish that an unpresented head or tail does not exist. |
| `ts` | Parse the accepted RFC 3339 syntax | The value is signer-chosen and is not trusted historical time. |
| `action.paramsHash` and governance commitment hashes | Check only the required lexical form without an external opening construction | The draft does not define their preimages and forbids treating `action.paramsHash` as a shared join key. |
| Governance and approval members | Preserve and report the signed labels | These labels do not establish AELITIUM `authorization=VALID`; that state is unreachable in v0.4-compatible semantics. |

Required canonicalization is RFC 8785 JCS with its specified number, member
ordering, Unicode, and string rules. AELITIUM's current canonicalization uses a
different Python JSON serialization contract. Similar-looking JSON bytes or
SHA-256 labels therefore provide no shared digest basis.

## Safe metadata mapping

Only source-attributed metadata could be carried into a future normalized
interpretation without inventing evidence:

| Source field | Future normalized role | Required qualifier |
|---|---|---|
| Pinned draft identifier plus `spec` | External format identifier | Exact match only; no version negotiation is defined. |
| `id` | Source receipt identifier | Issuer/key scoped; not globally unique. |
| `scope.chain` and `chain.seq` | Source chain coordinates | Source labels only; not AELITIUM invocation identity. |
| `chain.hash` | Source-native chain-link digest | Its projection and algorithm identifier must travel with it; it is not an artifact digest. |
| `sig.kid` and protected COSE `kid` | Opaque source key references | Preserve native and envelope references separately and never resolve through a lossy conversion. |
| `ts` | Source-declared recorded time | No AELITIUM Freshness state follows from syntax or signature alone. |
| `agent.*`, `action.*`, `governance.*` | Source-attributed assertions | Do not copy them into native canonical request, invocation, authorization, or policy-result fields. |

No raw prompt, selected message set, AELITIUM request hash, response hash,
`aelitium-invocation-v1` object, or `aelitium-invocation-binding-v1` object is
present in the receipt format. The issuer-defined `action.canonical` and
`action.paramsHash` fields cannot fill those gaps.

## AELITIUM assurance mapping

There is no safe direct projection from a receipt alone into
`aelitium-assurance-result-v1` under the released semantics:

| AELITIUM dimension | Why the external receipt cannot establish a native state |
|---|---|
| `payload_integrity` | Its `VALID` basis is the AELITIUM `ai_output_v1` canonical payload and manifest contract, neither of which the receipt contains. |
| `binding_field_consistency` | The receipt lacks AELITIUM request, response, and binding fields. |
| `invocation_identity_consistency` | The receipt lacks an `aelitium-invocation-v1` object and its selected fields. |
| `invocation_binding_consistency` | The receipt lacks an `aelitium-invocation-binding-v1` object and AELITIUM response hash. |
| `signature_validity` | Its current `VALID` basis is an AELITIUM manifest signature, not either source-specific receipt signature. |
| `trusted_signer_identity` | Its current `VALID` basis is membership of the verified AELITIUM signing key in an explicitly supplied `aelitium-trust-v1` store. Receipt keyrings and identity manifests are different trust inputs. |
| `freshness` | Its current evaluation uses `ai_canonical.json.ts_utc` plus the complete AELITIUM verifier policy pair. The receipt's `ts` is a different, signer-chosen field. |
| `authorization` | `NOT_EVALUATED` is the only v0.4-compatible state. Receipt governance or approval labels do not add an authorization evaluator. |

In particular, a valid native or COSE receipt signature must not emit
`signature_validity=VALID` or `trusted_signer_identity=VALID` in a native
AELITIUM assurance result. It may be reported only as a source-specific
verification fact in a future external-evidence result contract. Likewise,
missing invocation material must never be upgraded to
`invocation_identity_consistency=VALID` or
`invocation_binding_consistency=VALID`.

The machine-readable mapping therefore sets
`source_receipt_alone_can_establish` to `false` for all eight native dimensions.
This does not mean every dimension is false or invalid. It means this source
does not supply the AELITIUM-native basis needed to evaluate that dimension.

## Comparison boundary

Neither `chain.hash`, `action.paramsHash`, `id`, `action.id`, nor
`action.canonical` is an AELITIUM comparison identity. The pinned draft itself
defines `action.paramsHash` as per-producer and does not define a shared preimage
construction for it. Consequently:

- no receipt field may select `INVOCATION_IDENTITY_V1`;
- no receipt field may select `REQUEST_HASH_V1_FALLBACK` or
  `REQUEST_HASH_V1_LEGACY`;
- two receipts with equal identifiers or hashes do not become comparable under
  `aelitium-compare-v1`; and
- absence of a shared basis must remain `NOT_COMPARABLE`, never be rephrased as
  evidence that two actions differ.

The separate action-digest draft mentioned by the source specification is not
implemented or mapped here. Adding it would exceed the one-profile scope and
would require a separate review of its exact construction and vectors.

## Trust assumptions that remain external

A conforming source verifier would still need independently supplied decisions
for:

- native `sig.kid` resolution and the authority of that key for the claimed
  issuer or agent;
- outer COSE `kid` resolution and the role of an envelope signer or relay;
- key revocation, rotation, validity periods, and compromise handling;
- identity-manifest and checkpoint provenance, scope, and authorization;
- transparency-log policy, log trust, consistency proofs, and monitoring;
- any timestamp authority or caller-supplied maximum-age policy;
- opening rules and secrets for producer-specific commitments; and
- any claim about provider execution, controller outcome, physical effect,
  authorization, completeness, semantic truth, or legal compliance.

Bundling a public key beside a receipt would remain self-asserted key material.
It cannot create an independent trust input.

## BLOCKER

**Evidence**

1. The pinned source requires RFC 8785 JCS, source-specific native signature
   preimages, deterministic CBOR, and an attached COSE_Sign1 profile. AELITIUM
   currently implements a different JSON canonicalization and an Ed25519
   signature over AELITIUM manifest bytes; it has no JCS or COSE verifier.
2. Projecting either receipt signature to native
   `signature_validity=VALID` would change the released meaning of that state.
3. The receipt contains no AELITIUM invocation identity, invocation binding,
   request hash, response hash, or defensible AELITIUM comparison basis.
4. Source governance and approval labels cannot change
   `authorization=NOT_EVALUATED`, and source timestamps cannot create AELITIUM
   Freshness assurance.
5. `action.paramsHash` has no profile-defined preimage and is explicitly not a
   cross-producer join key.

**Affected files if implementation were forced**

- `engine/ai_verify.py` and `engine/result_contracts.py` would need a new source
  type or altered dimension bases;
- `engine/canonical.py` would be unsafe to reuse for JCS;
- `engine/ai_cli.py` would need a new explicit import/appraisal surface;
- packaged schemas and conformance vectors would need source-specific result
  semantics; and
- dependency and security review would be needed for CBOR/COSE or a complete
  local implementation.

**Smallest safe alternative**

Keep the receipt as separately referenced external evidence. Before adding an
importer, define a source-specific external verification result that can report
the two signature results and source trust inputs without populating native
AELITIUM dimensions. Implement the exact `-01` algorithms and official vectors,
then reassess only additive references from an AELITIUM verification result.
Any later draft version requires a new pinned profile and mapping review.

## Claim boundaries retained

The mapping preserves these existing AELITIUM codes:

- `provider_execution_not_established`
- `response_causation_not_established`
- `semantic_truth_not_established`
- `capture_completeness_not_established`
- `historical_occurrence_not_established`
- `historical_non_modification_not_established`
- `authorization_not_established`
- `trusted_historical_time_not_established`
- `legal_compliance_not_established`
- `trusted_signer_identity_not_established_by_signature`
- `complete_invocation_identity_not_established`

These are AELITIUM's bounded non-claim codes, not an external or industry
vocabulary.
