# Frozen compare compatibility fixtures

- `v030_invocation_a` and `v030_invocation_b` use the invocation identity and
  invocation binding formats present in the v0.3.0 bundle surface. They share a
  validated invocation-identity hash and have different selected response
  hashes.
- The frozen pre-invocation fixtures remain in
  `examples/drift_demo/bundle_a` and `examples/drift_demo/bundle_b`; compare
  tests use them to exercise v0.4 fallback and strict-mode behavior.

These fixtures test bundle readability and comparison selection. They do not
establish provider execution or historical occurrence.
