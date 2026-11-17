# RESEARCH CANDIDATES — not committed features

**Status:** Non-normative, non-roadmap research notes. These candidates are not
implementation commitments, schema proposals, or assurance claims.

## A. Trace correlation metadata

**Research question:** Can an AELITIUM evidence bundle be correlated with an
external trace without turning AELITIUM into an observability system?

### Problem

An operator investigating an incident may have a trace and an evidence bundle
but no deliberate join between them. Adding raw telemetry to the evidence would
blur product scope and could collect sensitive prompts or tool arguments.

Candidate correlation fields to research, not implement:

- `trace_id`
- `span_id`
- `agent_id`
- `conversation_id`

### Possible value

Optional identifiers could help an authorized operator navigate from a bundle
to separately retained telemetry, or from a trace to a bundle, while each
system keeps its own storage and verification semantics.

### Trust-boundary risk

An external identifier may be incorrect, reused, disclosed too broadly, or
rewritten with the rest of a self-consistent bundle. Its presence would add no
new guarantee of trace authenticity, provider execution, response causation,
or capture completeness.

Research must retain these principles:

- optional correlation only
- no automatic prompt or tool-argument ingestion
- privacy first
- no new trust guarantee merely because an external trace ID exists

### Interoperability questions

- Which identifier encodings and validation rules are stable across tracing
  systems?
- Can one bundle relate to multiple spans or traces without implying causal
  direction?
- Are agent and conversation identifiers portable, or framework-local?
- How should retention and access controls differ between evidence and
  telemetry?

### Evidence required before implementation

Require documented external workflows, a privacy and linkage threat model,
cross-vendor correlation experiments outside the bundle schema, and evidence
that identifiers round-trip without importing telemetry content.

**Not scheduled for v0.5.0.**

## B. Capture provenance / capture mode

**Research question:** Can a relying party distinguish how evidence entered the
AELITIUM system?

### Problem

Evidence may be observed and packed through different paths, but a relying party
cannot safely infer that path from the bundle's mere existence. Being in the
call path and observing or packing evidence are different conditions.

Possible categories to research include:

- in-call-path adapter capture
- manual pack
- imported or external evidence

These are working descriptions only. This document does not finalize category
names or a schema.

### Possible value

A carefully bounded declaration could help a relying party apply its own policy
to evidence origin without changing the verifier's internal-consistency result.

### Trust-boundary risk

A capture-mode label could be mistaken for an attestation, even when it is
self-declared. Adapter capture must not be described as proof that a provider
received or executed an invocation. Placement in a call path, observation of
values, packaging, and external anchoring are separate properties.

### Interoperability questions

- Which capture distinctions remain meaningful across SDK wrappers, proxies,
  manual tools, and imported archives?
- Who declares the mode, and what independent evidence could support it?
- How should transformations or multi-stage imports be represented without a
  misleading single label?
- Can downstream systems preserve the declaration without treating it as a
  trust decision?

### Evidence required before implementation

Require a topology-based threat model, real capture-path examples from multiple
integrations, terminology review by external relying parties, and tests showing
that each proposed category is both distinguishable and resistant to
overinterpretation.

**Not scheduled for v0.5.0.**

## C. Tool/environment identity

**Research question:** Should a future identity format optionally bind selected
information about the tool or environment against which an invocation occurred?

### Problem

The same model-facing invocation can run alongside different tool declarations,
servers, versions, or environment configuration. Current identity semantics
must not be silently expanded, and this candidate does not design or implement
a hash format.

Research inputs could include:

- tool name
- declared input schema
- selected server identity
- tool or version identity where available

### Possible value

A stable, privacy-conscious selection might let future comparisons distinguish
some materially different declared tool environments, if users demonstrate that
this distinction improves real evidence workflows.

### Trust-boundary risk

Binding a declaration would establish consistency only for selected recorded
fields. It would not establish endpoint control, tool execution, environmental
completeness, or that configuration remained unchanged during a session.

Risks include:

- unstable schemas
- provider and framework differences
- privacy
- huge tool definitions
- endpoint identity ambiguity
- configuration changes during a session

### Interoperability questions

- What is the smallest stable identity shared across frameworks and providers?
- Is a server name meaningful without a trusted endpoint or key identity?
- How should schema evolution, aliases, dynamic tool lists, and per-session
  configuration be handled?
- Can large definitions be referenced without hiding material differences or
  creating an unverifiable dependency?

### Evidence required before implementation

Require a cross-framework fixture corpus, measured size and stability data,
privacy review, adversarial endpoint-identity cases, and independent feedback
showing which fields a relying party actually needs. Any later design would need
its own explicit canonicalization and trust-boundary review.

**Not scheduled for v0.5.0.**
