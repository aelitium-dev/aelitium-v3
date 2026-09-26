"""F3-01..05: prior invocation/decision and an independent output byte oracle."""
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
import engine.verifier_operation as operation
from engine.verifier_invocation_facts import VerifierInvocationFacts as Facts, VerifierOperationEvidence
from engine.verifier_output_bytes import require_canonical_result_bytes
from engine.verifier_snapshot import DirectFilesystemInputs, InputMode, OperationalCode, OperationalPhase
from test_verifier_operation_cli import ROOT, VALID_BUNDLE, _configuration_json, _validator
from test_verifier_focused_round2_three_major import expected_output_failure, WIRE_MUTATIONS

ERRORS = (RuntimeError, MemoryError, RecursionError)
PRIVATE = 'F3_PRIVATE_SYNTHETIC'


def config_for(state):
    config = json.loads(_configuration_json())
    if state == 'unavailable':
        config['capability']['signature_verification']['profile'] = 'FUTURE'
    if state == 'limit':
        config['limits']['claimed_envelope'] = None
        config['limits']['effective']['max_file_bytes'] = 1
    return config


def run_core(state='valid', tmp_path=None):
    config = cli._parse_operation_config_json(json.dumps(config_for(state)))
    evidence = VerifierOperationEvidence(input_mode=InputMode.DIRECT_FILESYSTEM,
        requested_capability=config.capability_request, limits=config.limits)
    result = operation.verify_bundle_operation(
        DirectFilesystemInputs(tmp_path / 'absent' if state == 'io' else VALID_BUNDLE),
        capability_request=config.capability_request, limits=config.limits, _evidence=evidence)
    return result, evidence


def emit(result, evidence):
    out, err = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, evidence=evidence, stdout=out, stderr=err)
    assert err.getvalue() == b''
    raw = out.getvalue()
    value = json.loads(raw)
    _validator().validate(value)
    assert raw == rfc8785.dumps(value) + b'\n'
    assert rc == value['rc']
    assert PRIVATE.encode() not in raw and b'Traceback' not in raw
    return rc, value, raw


def assert_prior(value, state):
    config = config_for(state)
    assert value['capability']['requested'] == config['capability']
    assert value['capability']['effective'] == (None if state == 'unavailable' else config['capability'])
    assert value['limits'] == config['limits']
    assert value['input_mode'] == 'DIRECT_FILESYSTEM'
    if state != 'valid':
        assert value['verification_result'] is None and value['rc'] == 3
        assert value['operational_result']['operational_code'] == {
            'io': 'INPUT_IO_ERROR', 'unavailable': 'CAPABILITY_PROFILE_UNAVAILABLE',
            'limit': 'RESOURCE_LIMIT_EXCEEDED',
        }[state]


@pytest.mark.parametrize('helper', ['capture', 'after_selection', 'from_authenticated_result'])
@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('state', ['valid', 'io', 'unavailable'])
def test_removed_transfers_are_not_recovery_dependencies_cli(helper, error, state, tmp_path):
    config = config_for(state)
    bundle = tmp_path / 'absent' if state == 'io' else VALID_BUNDLE
    body = f'''
import sys
from unittest.mock import patch
import engine.ai_cli as cli
from engine.verifier_invocation_facts import VerifierInvocationFacts as Facts
sys.argv=['aelitium','verify-bundle',{str(bundle)!r},'--operation-json',{json.dumps(config)!r}]
with patch.object(Facts,{helper!r},side_effect={error.__name__}({PRIVATE!r})) as faulty:
 rc=cli.main()
 assert faulty.call_count == 0
 raise SystemExit(rc)
'''
    p = subprocess.run([sys.executable, '-B', '-c', body], cwd=ROOT, capture_output=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert p.stderr == b'' and p.returncode == (0 if state == 'valid' else 3)
    value = json.loads(p.stdout)
    _validator().validate(value)
    assert p.stdout == rfc8785.dumps(value) + b'\n'
    assert_prior(value, state)


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('state', ['valid', 'io', 'unavailable', 'limit'])
def test_arguments_failure_is_not_retried_and_prior_decision_survives(error, state, tmp_path):
    with patch.object(Facts, 'arguments', side_effect=error(PRIVATE)) as faulty:
        result, evidence = run_core(state, tmp_path)
        rc, value, _ = emit(result, evidence)
    assert faulty.call_count == 1 and rc == 3
    assert_prior(value, state)
    if state == 'valid':
        assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')
        assert value['operational_result']['phase'] == 'SEMANTIC_EVALUATION'


@pytest.mark.parametrize('mutation', ['requested', 'effective', 'both', 'future', 'limits', 'input_mode'])
@pytest.mark.parametrize('state', ['valid', 'io', 'unavailable'])
def test_rejected_arguments_cannot_reauthenticate(mutation, state, tmp_path):
    original = Facts.arguments
    def faulty(facts):
        kw = original(facts)
        changed = dataclasses.replace(kw['requested_capability'],
            v1=dataclasses.replace(kw['requested_capability'].v1, capability='V1_RESTRICTED_PORTABLE'))
        if mutation == 'future':
            changed = dataclasses.replace(changed, signature_verification=dataclasses.replace(changed.signature_verification, profile='FUTURE'))
        if mutation in ('requested', 'effective', 'both', 'future'):
            for name in ('requested_capability', 'effective_capability'):
                if mutation in ('both', 'future') or name.startswith(mutation): kw[name] = changed
        elif mutation == 'limits':
            altered = dataclasses.replace(kw['limits'].advertised, max_file_bytes=131072)
            kw['limits'] = dataclasses.replace(kw['limits'], advertised=altered, effective=altered)
        else: kw['input_mode'] = InputMode.IMMUTABLE_BYTES
        return kw
    with patch.object(Facts, 'arguments', side_effect=faulty) as injected:
        result, evidence = run_core(state, tmp_path)
        rc, value, _ = emit(result, evidence)
    assert injected.call_count == 1 and rc == 3
    assert_prior(value, state)


@pytest.mark.parametrize('point', ['prepare_verifier_capabilities', 'validate_prepared_verifier_capabilities', '_trust_input_was_supplied'])
@pytest.mark.parametrize('error', ERRORS)
def test_exact_selection_transition(point, error):
    with patch.object(operation, point, side_effect=error(PRIVATE)):
        result, evidence = run_core()
    rc, value, _ = emit(result, evidence)
    selected = point == '_trust_input_was_supplied'
    assert evidence.selected is selected and rc == 3
    assert (value['capability']['effective'] is not None) is selected
    assert value['operational_result']['phase'] == ('TRUST_INPUT' if selected else 'CAPABILITY_SELECTION')
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')


@pytest.mark.parametrize('state', ['io', 'unavailable', 'limit'])
@pytest.mark.parametrize('mutation', ['code', 'phase', 'input_ref', 'limit', 'semantic'])
@pytest.mark.parametrize('output_defect', [False, True])
def test_builder_cannot_replace_established_failure(state, mutation, output_defect, tmp_path):
    good, _ = run_core()
    original = operation.build_verifier_tool_result
    before = []
    def faulty(**kw):
        failure = kw['operational_failure']
        before.append(dataclasses.asdict(failure))
        before[-1]['detail'] = None
        result = original(**kw)
        if mutation == 'semantic':
            object.__setattr__(result, 'operational_result', None)
            object.__setattr__(result, 'verification_result', good.verification_result)
        elif mutation == 'code':
            object.__setattr__(failure, 'operational_code', OperationalCode.INPUT_NOT_REGULAR_FILE)
        elif mutation == 'phase':
            object.__setattr__(failure, 'phase', OperationalPhase.OUTPUT)
        elif mutation == 'input_ref':
            object.__setattr__(failure, 'input_ref', None if failure.input_ref else 'FORGED')
        elif failure.limit is not None:
            object.__setattr__(failure.limit, 'maximum', 1234)
        else:
            object.__setattr__(failure, 'limit', 'FORGED')
        return result
    with patch.object(operation, 'build_verifier_tool_result', side_effect=faulty):
        result, evidence = run_core(state, tmp_path)
    if output_defect:
        with patch.object(cli, 'serialize_verifier_tool_result', side_effect=RuntimeError(PRIVATE)):
            rc, value, _ = emit(result, evidence)
    else:
        rc, value, _ = emit(result, evidence)
    assert rc == 3 and len(before) == 1
    assert value['operational_result'] == before[0]
    assert_prior(value, state)


@pytest.mark.parametrize('mutation', list(WIRE_MUTATIONS))
def test_persistent_shared_canonicalizer_cannot_certify_its_bytes(mutation):
    result, evidence = run_core()
    original = rfc8785.dumps
    def faulty(value):
        # Add/remove transport LF only to reuse the independently specified
        # mutation vectors. The patched producer itself returns JSON bytes.
        return WIRE_MUTATIONS[mutation](original(value) + b'\n')[:-1]
    with patch.object(rfc8785, 'dumps', side_effect=faulty):
        out, err = io.BytesIO(), io.BytesIO()
        rc = cli._emit_operation_json(result, evidence=evidence, stdout=out, stderr=err)
    assert rc == 3 and err.getvalue() == b''
    assert out.getvalue() == expected_output_failure().replace(b'IMMUTABLE_BYTES', b'DIRECT_FILESYSTEM')


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('target', ['serialize_verifier_tool_result', 'require_canonical_result_bytes'])
def test_persistent_normal_byte_dependency_failure_is_independent(error, target):
    result, evidence = run_core()
    with patch.object(cli, target, side_effect=error(PRIVATE)) as faulty:
        rc, _, raw = emit(result, evidence)
    assert faulty.call_count == 1 and rc == 3
    code = b'INTERNAL_OPERATION_ERROR' if error is RuntimeError else b'RESOURCE_EXHAUSTED'
    assert raw == expected_output_failure(code).replace(b'IMMUTABLE_BYTES', b'DIRECT_FILESYSTEM')


def test_independent_literal_byte_domain_vector():
    value = {'z': [True, False, None, -9007199254740991, 0, 9007199254740991],
             'a': '/é𝄞\u2028\u2029\x00\b\t\n\f\r\x0f"\\'}
    expected = (b'{"a":"/\xc3\xa9\xf0\x9d\x84\x9e\xe2\x80\xa8\xe2\x80\xa9'
                b'\\u0000\\b\\t\\n\\f\\r\\u000f\\"\\\\",'
                b'"z":[true,false,null,-9007199254740991,0,9007199254740991]}\n')
    parsed = json.loads(expected)
    assert parsed == value
    with patch.object(rfc8785, 'dumps', side_effect=RuntimeError(PRIVATE)), patch.object(json, 'dumps', side_effect=RuntimeError(PRIVATE)):
        require_canonical_result_bytes(expected, parsed)
        for bad in (b' ' + expected, expected.replace(b'/', b'\\/'),
                    expected.replace(b'\\u000f', b'\\u000F'), expected + b'\n'):
            with pytest.raises(ValueError): require_canonical_result_bytes(bad, parsed)


@pytest.mark.parametrize('value', [{'é': 1}, {'x': 1.0}, {'x': 9007199254740992}])
def test_byte_checker_cannot_silently_expand_its_domain(value):
    with pytest.raises(ValueError): require_canonical_result_bytes(b'{}\n', value)


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('state', ['valid', 'io', 'unavailable'])
def test_normal_validation_fault_keeps_prior_reference(error, state, tmp_path):
    with patch.object(Facts, 'validate_result', side_effect=error(PRIVATE)):
        result, evidence = run_core(state, tmp_path)
        rc, value, _ = emit(result, evidence)
    assert rc == 3
    assert_prior(value, state)


@pytest.mark.parametrize('error', ERRORS)
def test_reference_creation_defect_is_contained_at_valid_entry(error, capfdbinary):
    argv = ['aelitium', 'verify-bundle', str(VALID_BUNDLE), '--operation-json', _configuration_json()]
    with patch.object(sys, 'argv', argv), patch.object(VerifierOperationEvidence, '__init__', side_effect=error(PRIVATE)) as faulty:
        rc = cli.main()
    captured = capfdbinary.readouterr()
    value = json.loads(captured.out)
    assert faulty.call_count == 1 and rc == 3 and captured.err == b''
    _validator().validate(value)
    assert value['capability']['requested'] == config_for('valid')['capability']
    assert value['capability']['effective'] is None
    assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')


@pytest.mark.parametrize('state', ['io', 'limit', 'unavailable'])
def test_serializer_mutation_of_result_cannot_rewrite_prior_failure(state, tmp_path):
    result, evidence = run_core(state, tmp_path)
    expected = dataclasses.asdict(result.operational_result.failure)
    original = cli.serialize_verifier_tool_result
    def faulty(record):
        object.__setattr__(record.operational_result.failure, 'operational_code', OperationalCode.INTERNAL_OPERATION_ERROR)
        object.__setattr__(record.operational_result.failure, 'phase', OperationalPhase.OUTPUT)
        object.__setattr__(record.operational_result.failure, 'input_ref', None)
        object.__setattr__(record.operational_result.failure, 'limit', None)
        return original(record)
    with patch.object(cli, 'serialize_verifier_tool_result', side_effect=faulty):
        rc, value, _ = emit(result, evidence)
    assert rc == 3 and value['operational_result'] == expected
    assert_prior(value, state)


@pytest.mark.parametrize('control', range(32))
def test_all_control_string_spellings_are_recognized(control):
    short = {8:b'\\b', 9:b'\\t', 10:b'\\n', 12:b'\\f', 13:b'\\r'}
    spelling = short.get(control, b'\\u00' + b'0123456789abcdef'[control // 16:control // 16 + 1] + b'0123456789abcdef'[control % 16:control % 16 + 1])
    literal = b'{"detail":"' + spelling + b'"}\n'
    value = json.loads(literal)
    assert value == {'detail': chr(control)}
    require_canonical_result_bytes(literal, value)


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('entry', [False, True])
def test_normal_copy_dependency_is_not_shared_by_recovery(error, entry, capfdbinary):
    import engine.verifier_invocation_facts as facts_module
    config = cli._parse_operation_config_json(_configuration_json())
    if entry:
        with patch.object(sys, 'argv', ['aelitium', 'verify-bundle', str(VALID_BUNDLE), '--operation-json', _configuration_json()]), patch.object(facts_module, 'deepcopy', side_effect=error(PRIVATE)):
            rc = cli.main()
        captured = capfdbinary.readouterr()
        value = json.loads(captured.out)
        assert rc == 3 and captured.err == b''
        _validator().validate(value)
        assert value['capability']['effective'] is None
        assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'
    else:
        evidence = VerifierOperationEvidence(input_mode=InputMode.DIRECT_FILESYSTEM,
            requested_capability=config.capability_request, limits=config.limits)
        with patch.object(facts_module, 'deepcopy', side_effect=error(PRIVATE)):
            result = operation.verify_bundle_operation(DirectFilesystemInputs(VALID_BUNDLE),
                capability_request=config.capability_request, limits=config.limits, _evidence=evidence)
            rc, value, _ = emit(result, evidence)
        assert rc == 3 and value['capability']['effective'] == config_for('valid')['capability']
        assert value['operational_result']['phase'] == 'SEMANTIC_EVALUATION'
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')
