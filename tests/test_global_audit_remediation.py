"""GLOBAL-01 (MAJOR): option-only Freshness policy precedes bundle acquisition.

Expected decisions follow policy §2.2 and explicit-input verification order.
These small real inputs do not depend on producer canonicalization.
"""
from dataclasses import asdict, replace
import io
import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

import engine.ai_cli as cli
import engine.verifier_operation as operation
from engine.ai_verify import AIVerificationOptions, verify_ai_bundle
from engine.result_contracts import VerifierLimitState
from engine.verifier_capabilities import (
    V1_FROZEN_LEGACY_COMPATIBILITY, V1_RESTRICTED_PORTABLE,
    V1_NAMED_RUNTIME_COMPATIBILITY, V1_LEGACY_UNSUPPORTED,
)
from engine.verifier_result_invariants import validate_verifier_result_invariants
from engine.verifier_snapshot import DirectFilesystemInputs, ImmutableBytesInputs, OperationalLimits
from test_verifier_operation import _manifest_source, _payload_source, _request
from test_verifier_operation_cli import ROOT, _configuration, _validator


REFERENCE = '2026-09-09T00:05:00Z'
PARTIAL = (
    AIVerificationOptions(freshness_max_age_seconds=300),
    AIVerificationOptions(freshness_reference_time_utc=REFERENCE),
)
FLAGS = (('--freshness-max-age-seconds', '300'), ('--freshness-reference-time-utc', REFERENCE))
COMPLETE = AIVerificationOptions(freshness_max_age_seconds=300, freshness_reference_time_utc=REFERENCE)
PRIVATE = 'GLOBAL01_SYNTHETIC_PRIVATE'


def _limits(limited=False):
    return VerifierLimitState(None, OperationalLimits(), OperationalLimits(max_file_bytes=1) if limited else OperationalLimits())


def _inputs(tmp_path, mode='direct', condition='normal', trust=None, timestamp=None):
    canonical = _payload_source()
    if timestamp is not None:
        canonical = canonical.replace(b'2026-09-09T00:00:00Z', timestamp.encode())
    manifest = _manifest_source(canonical)
    if mode == 'bytes':
        return ImmutableBytesInputs(None if condition == 'missing' else canonical, manifest, None, trust)
    bundle = tmp_path / 'bundle'
    if condition != 'missing':
        bundle.mkdir(exist_ok=True)
        (bundle / 'ai_canonical.json').write_bytes(canonical)
        (bundle / 'ai_manifest.json').write_bytes(manifest)
    trust_path = None
    if trust is not None:
        trust_path = tmp_path / 'trust.json'
        trust_path.write_bytes(trust)
    return DirectFilesystemInputs(bundle, trust_path)


def _frame(raw, rc, stderr=b''):
    assert stderr == b''
    value = json.loads(raw)
    _validator().validate(value)
    validate_verifier_result_invariants(value, process_rc=rc)
    # Independent byte oracle for these ASCII keys/strings and safe integers.
    # No floats, non-ASCII sorting, or general RFC8785 encoding is needed here.
    assert raw == json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode() + b'\n'
    assert raw.count(b'\n') == 1 and PRIVATE.encode() not in raw
    assert value['rc'] == rc
    return value


def _emit(result):
    out, err = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, stdout=out, stderr=err)
    value = _frame(out.getvalue(), rc, err.getvalue())
    assert value == result.to_json_value()
    return value


def _policy(value, options):
    assert value['rc'] == 2 and value['operational_result'] is None
    inner = value['verification_result']
    assert inner['reason'] == 'FRESHNESS_POLICY_INVALID' and inner['status'] == 'INVALID'
    assert inner['policy_inputs'] == [{
        'ref': 'verification-input:freshness-policy', 'kind': 'declared_time_freshness_v1',
        'maximum_age_seconds': options.freshness_max_age_seconds,
        'reference_time_utc': options.freshness_reference_time_utc,
    }]
    states = {x['dimension']: x['state'] for x in inner['assurance']['dimensions']}
    assert states == {
        'payload_integrity': 'NOT_EVALUATED', 'binding_field_consistency': 'NOT_EVALUATED',
        'invocation_identity_consistency': 'NOT_EVALUATED', 'invocation_binding_consistency': 'NOT_EVALUATED',
        'signature_validity': 'NOT_EVALUATED', 'trusted_signer_identity': 'UNESTABLISHED',
        'freshness': 'UNESTABLISHED', 'authorization': 'NOT_EVALUATED',
    }


@pytest.mark.parametrize('options', PARTIAL)
@pytest.mark.parametrize('mode,condition', [('direct', 'normal'), ('direct', 'missing'), ('direct', 'limited'), ('bytes', 'normal'), ('bytes', 'missing'), ('bytes', 'limited')])
def test_incomplete_policy_api_before_snapshot(tmp_path, options, mode, condition):
    inputs = _inputs(tmp_path, mode, condition)
    limits, request = _limits(condition == 'limited'), _request()
    with patch.object(operation, 'acquire_verifier_snapshot', wraps=operation.acquire_verifier_snapshot) as acquisition:
        result = operation.verify_bundle_operation(inputs, capability_request=request, limits=limits, options=options)
    assert acquisition.call_count == 0
    assert result.requested_capability == result.effective_capability == request
    assert result.input_mode == inputs.input_mode and result.limits == limits
    value = _emit(result)
    _policy(value, options)
    assert value['verification_result']['trust_inputs'] == []


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('condition', ['normal', 'missing', 'limited'])
def test_incomplete_policy_real_cli(tmp_path, index, condition):
    inputs = _inputs(tmp_path, condition=condition)
    limits = _limits(condition == 'limited')
    config = _configuration(limits=asdict(limits))
    p = subprocess.run([sys.executable, '-B', '-m', 'engine.ai_cli', 'verify-bundle', str(inputs.bundle_root),
                        '--operation-json', json.dumps(config), *FLAGS[index]], cwd=ROOT, capture_output=True)
    value = _frame(p.stdout, p.returncode, p.stderr)
    _policy(value, PARTIAL[index])
    assert value['capability'] == {'requested': config['capability'], 'effective': config['capability']}
    assert value['limits'] == config['limits'] and value['input_mode'] == 'DIRECT_FILESYSTEM'


@pytest.mark.parametrize('profile', [V1_FROZEN_LEGACY_COMPATIBILITY, V1_RESTRICTED_PORTABLE, V1_NAMED_RUNTIME_COMPATIBILITY, V1_LEGACY_UNSUPPORTED])
def test_selected_profiles_do_not_change_option_precedence(tmp_path, profile):
    request = _request(profile)
    result = operation.verify_bundle_operation(_inputs(tmp_path, condition='missing'), capability_request=request,
                                               limits=_limits(), options=PARTIAL[0])
    assert result.requested_capability == result.effective_capability == request
    _policy(_emit(result), PARTIAL[0])


@pytest.mark.parametrize('required,unavailable', [(True, False), (False, True), (True, True)])
def test_required_trust_and_capability_precede_incomplete_policy(tmp_path, required, unavailable):
    request = _request(dispatch='FUTURE') if unavailable else _request()
    with patch.object(operation, 'acquire_verifier_snapshot', wraps=operation.acquire_verifier_snapshot) as acquisition:
        result = operation.verify_bundle_operation(_inputs(tmp_path, condition='missing'), capability_request=request,
                                                   limits=_limits(True), options=replace(PARTIAL[0], require_trusted_signer=required))
    assert acquisition.call_count == 0
    value = _emit(result)
    if unavailable:
        assert value['operational_result']['operational_code'] == 'CAPABILITY_PROFILE_UNAVAILABLE'
        assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'
        assert value['capability']['effective'] is None
    else:
        assert value['verification_result']['reason'] == 'TRUST_INPUT_NOT_PROVIDED'
        assert value['capability']['effective'] == value['capability']['requested']


@pytest.mark.parametrize('mode', ['direct', 'bytes'])
@pytest.mark.parametrize('trust,required,expected', [
    (b'{', False, 'TRUST_STORE_INVALID'), (b'{', True, 'TRUST_STORE_INVALID'),
    (b'{"signers":[],"trust_store_format":"aelitium-trust-v1"}', False, 'FRESHNESS_POLICY_INVALID'),
    (b'{"signers":[],"trust_store_format":"aelitium-trust-v1"}', True, 'FRESHNESS_POLICY_INVALID'),
])
def test_supplied_trust_retains_earlier_precedence(tmp_path, mode, trust, required, expected):
    inputs = _inputs(tmp_path, mode, trust=trust)
    with patch.object(operation, 'acquire_verifier_snapshot', wraps=operation.acquire_verifier_snapshot) as acquisition:
        result = operation.verify_bundle_operation(inputs, capability_request=_request(), limits=_limits(),
                                                   options=replace(PARTIAL[0], require_trusted_signer=required))
    assert acquisition.call_count == 1
    value = _emit(result)
    assert value['verification_result']['reason'] == expected
    assert len(value['verification_result']['trust_inputs']) == 1


def test_supplied_trust_acquisition_failure_is_not_a_policy_decision(tmp_path):
    inputs = _inputs(tmp_path)
    inputs = replace(inputs, trust_store_path=tmp_path / 'absent-trust')
    result = operation.verify_bundle_operation(inputs, capability_request=_request(), limits=_limits(), options=PARTIAL[0])
    value = _emit(result)
    assert value['rc'] == 3 and value['verification_result'] is None
    assert value['operational_result']['operational_code'] == 'INPUT_IO_ERROR'
    assert value['operational_result']['phase'] == 'TRUST_INPUT'


@pytest.mark.parametrize('options', [AIVerificationOptions(), COMPLETE])
@pytest.mark.parametrize('condition,expected', [('normal', 'OK'), ('missing', 'INPUT_IO_ERROR'), ('limited', 'RESOURCE_LIMIT_EXCEEDED')])
def test_disabled_or_complete_policy_keeps_acquisition(tmp_path, options, condition, expected):
    with patch.object(operation, 'acquire_verifier_snapshot', wraps=operation.acquire_verifier_snapshot) as acquisition:
        result = operation.verify_bundle_operation(_inputs(tmp_path, condition=condition), capability_request=_request(),
                                                   limits=_limits(condition == 'limited'), options=options)
    assert acquisition.call_count == 1
    value = _emit(result)
    if condition == 'normal':
        inner = value['verification_result']
        assert inner['reason'] == expected
        states = {x['dimension']: x['state'] for x in inner['assurance']['dimensions']}
        assert states['freshness'] == ('VALID' if options == COMPLETE else 'NOT_EVALUATED')
    else:
        assert value['operational_result']['operational_code'] == expected


@pytest.mark.parametrize('timestamp,expected', [
    ('not-a-timestamp', 'FRESHNESS_TIMESTAMP_MALFORMED'),
    ('2026-02-30T00:00:00Z', 'FRESHNESS_TIMESTAMP_MALFORMED'),
    ('2026-09-08T23:59:59Z', 'FRESHNESS_STALE'),
    ('2026-09-09T00:05:01Z', 'FRESHNESS_TIMESTAMP_IN_FUTURE'),
])
def test_evidence_timestamp_is_not_policy_validation(tmp_path, timestamp, expected):
    inputs = _inputs(tmp_path, 'bytes', timestamp=timestamp)
    result = operation.verify_bundle_operation(inputs, capability_request=_request(), limits=_limits(), options=COMPLETE)
    value = _emit(result)
    assert value['rc'] == 2 and value['verification_result']['reason'] == expected


@pytest.mark.parametrize('options', [replace(COMPLETE, freshness_max_age_seconds=-1), replace(COMPLETE, freshness_reference_time_utc='bad')])
def test_invalid_complete_outer_policy_is_an_envelope_error(tmp_path, options):
    with patch.object(operation, 'prepare_verifier_capabilities', wraps=operation.prepare_verifier_capabilities) as selection:
        with pytest.raises(ValueError):
            operation.verify_bundle_operation(_inputs(tmp_path, condition='missing'), capability_request=_request(dispatch='FUTURE'),
                                               limits=_limits(), options=options)
    assert selection.call_count == 0
    # Legacy accepts the larger option domain and retains its semantic mapping.
    result = verify_ai_bundle(tmp_path / 'absent', options=options)
    assert result.reason == 'FRESHNESS_POLICY_INVALID'


@pytest.mark.parametrize('error,code', [(RuntimeError, 'INTERNAL_OPERATION_ERROR'), (MemoryError, 'RESOURCE_EXHAUSTED'), (RecursionError, 'RESOURCE_EXHAUSTED')])
def test_policy_helper_failure_retains_selection(tmp_path, error, code):
    with patch.object(operation, '_freshness_policy_failure', side_effect=error(PRIVATE)) as helper:
        result = operation.verify_bundle_operation(_inputs(tmp_path, condition='missing'), capability_request=_request(),
                                                   limits=_limits(), options=PARTIAL[0])
    assert helper.call_count == 1
    value = _emit(result)
    assert value['operational_result']['operational_code'] == code
    assert value['operational_result']['phase'] == 'SEMANTIC_EVALUATION'
    assert value['capability']['effective'] == value['capability']['requested']


@pytest.mark.parametrize('error,code', [(RuntimeError, 'INTERNAL_OPERATION_ERROR'), (MemoryError, 'RESOURCE_EXHAUSTED'), (RecursionError, 'RESOURCE_EXHAUSTED')])
def test_incomplete_policy_later_output_failure_real_cli(tmp_path, error, code):
    config = _configuration(limits=asdict(_limits(True)))
    args = ['aelitium', 'verify-bundle', str(tmp_path / 'absent'), '--operation-json', json.dumps(config), *FLAGS[0]]
    body = f'''
import sys
from unittest.mock import patch
import engine.ai_cli as cli
sys.argv = {args!r}
with patch.object(cli, 'serialize_verifier_tool_result', side_effect={error.__name__}({PRIVATE!r})):
    raise SystemExit(cli.main())
'''
    p = subprocess.run([sys.executable, '-B', '-c', body], cwd=ROOT, capture_output=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    value = _frame(p.stdout, p.returncode, p.stderr)
    assert value['verification_result'] is None and value['rc'] == 3
    assert value['operational_result']['operational_code'] == code
    assert value['operational_result']['phase'] == 'OUTPUT'
    assert value['capability'] == {'requested': config['capability'], 'effective': config['capability']}
    assert value['limits'] == config['limits']
