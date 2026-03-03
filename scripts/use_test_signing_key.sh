#!/usr/bin/env bash
# Test-only signing fixture for local smoke tests.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_KEY_PATH="$ROOT/tests/fixtures/ed25519_test_private_key.b64"

export AEL_ED25519_PRIVKEY_B64="${AEL_ED25519_PRIVKEY_B64:-$(tr -d '\n' < "$TEST_KEY_PATH")}"
export AEL_ED25519_KEY_ID="${AEL_ED25519_KEY_ID:-test-key-2026q1}"
