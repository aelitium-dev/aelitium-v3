[English](README.md) | [Français](README.fr.md)

# AELITIUM

AELITIUM is a Python library and command-line tool for packaging recorded AI
interactions into evidence bundles, checking their consistency offline and
comparing records. Each bundle contains recorded data and a manifest that
describes the checks.

Teams can review a bundle supplied by another team or vendor without access to
the production environment. Verification checks the supplied records, not whether
the interaction actually occurred.

This README covers **0.4.0**, available on [PyPI](https://pypi.org/project/aelitium/0.4.0/).
The historical GitHub tags and releases have been removed; there is no current
GitHub release.

## Features

- Capture supported OpenAI, Anthropic and LiteLLM call paths with optional adapters.
- Pack a recorded interaction into a local evidence bundle.
- Verify supplied evidence offline against its recorded hashes and schema.
- Compare supported bundles with an explicit comparison basis and outcome.
- Find supported large language model (LLM) call patterns through static analysis
  of Python source.

See the [feature matrix on main](https://github.com/aelitium-dev/aelitium-v3/blob/main/FEATURE_MATRIX.md),
sections 1–13, for 0.4.0 support and limits. Later sections cover unpublished work.
Capture and scanning do not cover every LLM call.

## Install

Python 3.10 or newer is required. Core dependencies are `cryptography>=41` and
`jsonschema>=4.18`. Provider SDKs are optional. In a new working directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "aelitium==0.4.0"
```

These commands use Bash. Installation may download dependencies.
Once installed, the example below works offline.

## Example

Create a synthetic recording. No model or provider API is called.
The same recording is used in both language versions.

```bash
cat > recording.json <<'JSON'
{
  "schema_version": "ai_output_v1",
  "ts_utc": "2026-01-01T00:00:00Z",
  "model": "synthetic-example",
  "prompt": "What is the capital of France?",
  "output": "Paris."
}
JSON

aelitium pack --input recording.json --out bundle
aelitium verify-bundle ./bundle
```

A successful verification reports `STATUS=VALID rc=0`.
The example is unsigned and has no recorded request/response binding;
the default verification options allow both.

Use a fresh output directory and one writer per destination.
Bundle files are written sequentially. A failure can leave partial output.
Keep partial output out of reader workflows after a failure.

## Limits

`VALID` means the supplied evidence passed the selected checks.
It does not prove that an interaction occurred, that a provider ran the request,
or that an answer is true, correct or safe. It does not establish complete capture,
what caused the response, the complete identity of the actual call, a trustworthy
historical timestamp, authorization or legal or regulatory compliance.

Comparison does not establish causation, model drift or provider fault.

An internally consistent replacement can also verify.
Keep an independently trusted hash or key when checking an expected record.
Signatures are optional. A public key inside a bundle is not an independent trust anchor.

Bundles retain their recorded content. Review prompts, outputs and metadata
before sharing them. Hashes do not anonymize data.

## Documentation

The links below follow the current `main` branch. Consult each document's stated
version and status when using the PyPI 0.4.0 package.

- [Repository documentation (main)](https://github.com/aelitium-dev/aelitium-v3/tree/main/docs)
- [Capture adapters (main)](https://github.com/aelitium-dev/aelitium-v3/blob/main/docs/INTEGRATION_CAPTURE.md)
- [Comparison rules for 0.4.0 (main)](https://github.com/aelitium-dev/aelitium-v3/blob/main/docs/CANONICAL_REQUEST.md#impact-on-compare)
- [Contributing](CONTRIBUTING.md)

This checkout also contains unpublished work. See the [changelog](CHANGELOG.md)
and [repository documentation](docs/INDEX.md) for its history and version-specific guides.

## License and security

The published 0.4.0 package is distributed under [Apache-2.0](LICENSE).
Retain the [notices](NOTICE). Report vulnerabilities through the [security policy](SECURITY.md).
Any new distribution remains subject to provenance, ownership and release review.
