"""F4-01/F4-02 (MAJOR), F4-03 (MEDIUM): origin, decision and leaf types."""
import dataclasses
import io
import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
import rfc8785

import engine.ai_cli as cli
import engine.verifier_invocation_facts as facts
import engine.verifier_operation as operation
from engine.result_contracts import ResultContractError, VerifierLimitState
from engine.verifier_capabilities import VerifierCapabilityRequest
from engine.verifier_snapshot import (
    DirectFilesystemInputs, InputMode, InputRef, LimitFact, LimitName, LimitUnit, OperationalCode,
    OperationalInputFailure, OperationalPhase,
)
from test_verifier_operation_cli import ROOT, VALID_BUNDLE, _validator
from test_verifier_focused_round3_five_major import config_for, run_core, assert_prior

ERRORS = (RuntimeError, MemoryError, RecursionError)
PRIVATE = 'F4_PRIVATE_SYNTHETIC'


def emit(result, evidence=None):
    stdout, stderr = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, evidence=evidence, stdout=stdout, stderr=stderr)
    raw = stdout.getvalue()
    assert stderr.getvalue() == b''
    value = json.loads(raw)
    _validator().validate(value)
    assert raw == rfc8785.dumps(value) + b'\n' and raw.count(b'\n') == 1
    assert rc == value['rc'] and PRIVATE.encode() not in raw
    return value


def assert_leaf_types(left, right):
    """Test oracle: exact scalar types, independently of production comparison."""
    assert type(left) is type(right)
    if type(left) is dict:
        assert left.keys() == right.keys()
        for key in left:
            assert_leaf_types(left[key], right[key])
    elif type(left) in (list, tuple):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_leaf_types(a, b)
    else:
        assert left == right


@pytest.mark.parametrize('helper', ['capture', '__init__'])
@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('persistent', [False, True])
@pytest.mark.parametrize('state', ['io', 'limit', 'unavailable'])
def test_failure_record_preserves_decision_and_selection(helper, error, persistent, state, tmp_path):
    expected, _ = run_core(state, tmp_path)
    expected = expected.to_json_value()
    original = getattr(facts.EstablishedOperationalFailure, helper)
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        if persistent or len(calls) == 1:
            raise error(PRIVATE)
        return original(*args, **kwargs)
    replacement = classmethod(lambda cls, *a, **kw: broken(*a, **kw)) if helper == 'capture' else broken
    with patch.object(facts.EstablishedOperationalFailure, helper, replacement):
        result, evidence = run_core(state, tmp_path)
        assert_leaf_types(result.to_json_value(), expected)
        evidence.validate_result(result)
        # Even a subsequent output defect uses the retained decision directly.
        with patch.object(cli, 'serialize_verifier_tool_result', side_effect=error(PRIVATE)):
            value = emit(result, evidence)
        assert len(calls) == 1
    assert_leaf_types(value, expected)
    assert_prior(value, state)


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('persistent', [False, True])
@pytest.mark.parametrize('state', ['io', 'limit', 'unavailable'])
def test_failure_record_fault_real_cli(error, persistent, state, tmp_path):
    config = config_for(state)
    bundle = tmp_path / 'absent' if state == 'io' else VALID_BUNDLE
    body = f'''
import sys
from unittest.mock import patch
import engine.ai_cli as cli
from engine.verifier_invocation_facts import EstablishedOperationalFailure as Failure
original=Failure.capture
calls=0
@classmethod
def broken(cls,failure):
 global calls
 calls+=1
 if {persistent!r} or calls==1:raise {error.__name__}({PRIVATE!r})
 return original(failure)
sys.argv=['aelitium','verify-bundle',{str(bundle)!r},'--operation-json',{json.dumps(config)!r}]
with patch.object(Failure,'capture',broken):
 rc=cli.main()
 assert calls==1
 raise SystemExit(rc)
'''
    p = subprocess.run([sys.executable, '-B', '-c', body], cwd=ROOT, capture_output=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert p.returncode == 3 and p.stderr == b''
    value = json.loads(p.stdout)
    _validator().validate(value)
    assert p.stdout == rfc8785.dumps(value) + b'\n'
    assert_prior(value, state)


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('state', ['io', 'limit', 'unavailable'])
def test_standalone_emitter_authenticated_api_precondition(error, state, tmp_path):
    result, _ = run_core(state, tmp_path)
    expected = result.to_json_value()
    with patch.object(facts.EstablishedOperationalFailure, 'capture', side_effect=error(PRIVATE)) as capture:
        with patch.object(cli, 'serialize_verifier_tool_result', side_effect=error(PRIVATE)):
            value = emit(result)
        assert capture.call_count == 0  # No normal capture needed for an authenticated API result.
    assert_leaf_types(value, expected)


@pytest.mark.parametrize('error', ERRORS)
def test_api_then_standalone_does_not_retry_capture(error, tmp_path):
    with patch.object(facts.EstablishedOperationalFailure, 'capture', side_effect=error(PRIVATE)) as capture:
        result, _ = run_core('io', tmp_path)
        value = emit(result)
        assert capture.call_count == 1
    assert_prior(value, 'io')


@pytest.mark.parametrize('mutation', ['code', 'phase', 'input_ref', 'limit', 'limit_type'])
def test_false_failure_capture_is_not_the_decision(mutation, tmp_path):
    expected, _ = run_core('limit', tmp_path)
    original = facts.EstablishedOperationalFailure.capture
    def broken(failure):
        value = original(failure)
        changes = {
            'code': {'code': OperationalCode.INPUT_IO_ERROR},
            'phase': {'phase': OperationalPhase.OUTPUT},
            'input_ref': {'input_ref': None},
            'limit': {'limit': None},
            'limit_type': {'limit': (*value.limit[:2], True, value.limit[3])},
        }
        return dataclasses.replace(value, **changes[mutation])
    with patch.object(facts.EstablishedOperationalFailure, 'capture', side_effect=broken):
        result, evidence = run_core('limit', tmp_path)
        value = emit(result, evidence)
    assert_leaf_types(value, expected.to_json_value())


def altered_copy(value, mutation, original):
    copied = original(value)
    if type(copied) is VerifierCapabilityRequest and mutation in ('supported', 'unsupported', 'combined'):
        if mutation == 'unsupported':
            return dataclasses.replace(copied, signature_verification=dataclasses.replace(
                copied.signature_verification,
                profile='FUTURE' if copied.signature_verification.profile != 'FUTURE' else 'FUTURE_OTHER'))
        return dataclasses.replace(copied, v1=dataclasses.replace(copied.v1, capability='V1_RESTRICTED_PORTABLE'))
    if type(copied) is VerifierLimitState and mutation in ('limits', 'combined', 'type'):
        maximum = True if mutation == 'type' else 131072
        # Bypass only the normal constructor in the test: a typed bad return.
        object.__setattr__(copied.effective, 'max_file_bytes', maximum)
        if mutation != 'type':
            object.__setattr__(copied.advertised, 'max_file_bytes', maximum)
        return copied
    return copied


@pytest.mark.parametrize('mutation', ['supported', 'unsupported', 'limits', 'combined', 'type'])
@pytest.mark.parametrize('persistent', [False, True])
@pytest.mark.parametrize('state', ['valid', 'io', 'limit', 'unavailable'])
def test_bad_copy_never_becomes_api_reference(mutation, persistent, state, tmp_path):
    config = config_for(state)
    cfg = cli._parse_operation_config_json(json.dumps(config))
    original = facts.deepcopy
    changed = []
    def broken(value):
        if changed and not persistent:
            return original(value)
        copied = altered_copy(value, mutation, original)
        if copied != value or mutation == 'type' and type(value) is VerifierLimitState:
            changed.append(1)
        return copied
    with patch.object(facts, 'deepcopy', side_effect=broken):
        result = operation.verify_bundle_operation(
            DirectFilesystemInputs(tmp_path / 'absent' if state == 'io' else VALID_BUNDLE),
            capability_request=cfg.capability_request, limits=cfg.limits)
        value = emit(result)
    assert changed
    assert_leaf_types(value['capability']['requested'], config['capability'])
    assert_leaf_types(value['limits'], config['limits'])
    assert value['capability']['effective'] is None
    assert value['rc'] == 3
    assert value['operational_result']['operational_code'] == 'INTERNAL_OPERATION_ERROR'
    assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'
    assert result.input_mode is InputMode.DIRECT_FILESYSTEM


@pytest.mark.parametrize('mutation', ['supported', 'unsupported', 'limits', 'combined', 'type'])
@pytest.mark.parametrize('state', ['io', 'limit', 'unavailable'])
def test_bad_copy_after_established_failure_cannot_reauthenticate(mutation, state, tmp_path):
    expected, _ = run_core(state, tmp_path)
    original_arguments = facts.VerifierInvocationFacts.arguments
    original_copy = facts.deepcopy
    def broken_arguments(reference):
        # Initial metadata witness already exists; corrupt only the builder's copies.
        with patch.object(facts, 'deepcopy', side_effect=lambda v: altered_copy(v, mutation, original_copy)):
            return original_arguments(reference)
    with patch.object(facts.VerifierInvocationFacts, 'arguments', broken_arguments):
        result, evidence = run_core(state, tmp_path)
        value = emit(result, evidence)
    assert_leaf_types(value, expected.to_json_value())


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('state', ['valid', 'io'])
def test_copy_exception_is_contained_before_selection(error, state, tmp_path):
    cfg = cli._parse_operation_config_json(json.dumps(config_for(state)))
    with patch.object(facts, 'deepcopy', side_effect=error(PRIVATE)) as broken:
        result = operation.verify_bundle_operation(
            DirectFilesystemInputs(tmp_path / 'absent' if state == 'io' else VALID_BUNDLE),
            capability_request=cfg.capability_request, limits=cfg.limits)
        value = emit(result)
        assert broken.call_count == 1
    assert value['capability']['effective'] is None
    assert value['operational_result']['operational_code'] == (
        'INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')
    assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'


@pytest.mark.parametrize('field', ['requested_capability', 'limits'])
def test_faithful_alias_is_still_rejected(field):
    cfg = cli._parse_operation_config_json(json.dumps(config_for('valid')))
    origin = cfg.capability_request if field == 'requested_capability' else cfg.limits
    original = facts.deepcopy
    with patch.object(facts, 'deepcopy', side_effect=lambda v: v if v is origin else original(v)):
        with pytest.raises(RuntimeError, match='COPY_MISMATCH'):
            facts.VerifierOperationEvidence(input_mode=InputMode.DIRECT_FILESYSTEM,
                requested_capability=cfg.capability_request, limits=cfg.limits)


@pytest.mark.parametrize('field,before,after,code', [
    ('maximum', 1, True, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('maximum', 0, False, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('maximum', 1, 1.0, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('maximum', 0, 0.0, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('observed_at_least', 1, True, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('observed_at_least', 1, 1.0, OperationalCode.RESOURCE_LIMIT_EXCEEDED),
    ('observed_at_least', 0, False, OperationalCode.RESOURCE_EXHAUSTED),
    ('observed_at_least', 0, 0.0, OperationalCode.RESOURCE_EXHAUSTED),
])
@pytest.mark.parametrize('explicit', [False, True])
def test_api_rejects_coercively_equal_limit_leaves(field, before, after, code, explicit):
    # A measured ceiling is strictly exceeded. Exhaustion may report zero
    # bytes acquired, without claiming that a ceiling was exceeded (§9.3).
    values = {'maximum': 0, 'observed_at_least': before + 1}
    values[field] = before
    config = config_for('limit')
    config['limits']['effective']['max_file_bytes'] = values['maximum']
    cfg = cli._parse_operation_config_json(json.dumps(config))
    prior = OperationalInputFailure(code, OperationalPhase.BUNDLE_SNAPSHOT,
        InputRef.AI_CANONICAL_JSON, limit=LimitFact(LimitName.FILE_BYTES, LimitUnit.BYTES, **values))
    evidence = facts.VerifierOperationEvidence(input_mode=InputMode.DIRECT_FILESYSTEM,
        requested_capability=cfg.capability_request, limits=cfg.limits)
    original = operation.build_verifier_tool_result
    def broken(**kwargs):
        result = original(**kwargs)
        object.__setattr__(result.operational_result.failure.limit, field, after)
        return result
    with patch.object(operation, 'acquire_verifier_snapshot', side_effect=prior), \
            patch.object(operation, 'build_verifier_tool_result', side_effect=broken):
        result = operation.verify_bundle_operation(DirectFilesystemInputs(VALID_BUNDLE),
            capability_request=cfg.capability_request, limits=cfg.limits, _evidence=evidence)
    actual = getattr(result.operational_result.failure.limit, field)
    assert type(actual) is int and actual == before
    evidence.validate_result(result)
    _validator().validate(result.to_json_value())
    value = emit(result, evidence if explicit else None)
    assert type(value['operational_result']['limit'][field]) is int
    assert value['operational_result']['limit'][field] == before


def test_limit_fidelity_does_not_require_effective_equal_advertised():
    config = config_for('limit')
    cfg = cli._parse_operation_config_json(json.dumps(config))
    result = operation.verify_bundle_operation(DirectFilesystemInputs(VALID_BUNDLE),
        capability_request=cfg.capability_request, limits=cfg.limits)
    value = emit(result)
    assert_leaf_types(value['limits'], config['limits'])
    assert value['limits']['advertised']['max_file_bytes'] == 65536
    assert value['limits']['effective']['max_file_bytes'] == 1
    assert type(result.operational_result.failure.limit.maximum) is int
    assert result.operational_result.failure.limit.maximum == 1
    assert type(result.operational_result.failure.limit.observed_at_least) is int


def test_failure_validator_detects_tuple_type_mismatch_directly(tmp_path):
    result, evidence = run_core('limit', tmp_path)
    object.__setattr__(result.operational_result.failure.limit, 'maximum', True)
    with pytest.raises(ResultContractError, match='FAILURE_MISMATCH'):
        evidence.validate_result(result)
    # An explicit historical reference can contain even a post-API mutation.
    value = emit(result, evidence)
    assert value['operational_result']['limit']['maximum'] == 1
    assert type(value['operational_result']['limit']['maximum']) is int
