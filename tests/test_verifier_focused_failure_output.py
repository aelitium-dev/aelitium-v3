"""Focused audit root-class probes through the real operation and CLI output."""
from __future__ import annotations

import copy
import dataclasses
import io
import json
import os
import subprocess
import sys
from unittest import mock

import pytest
import rfc8785

import engine.ai_cli as cli
import engine.verifier_operation as operation
import engine.verifier_capabilities as capabilities
from engine.result_contracts import (
    ResultContractError, VerifierLimitState, serialize_verifier_tool_result,
)
from engine.verifier_result_invariants import validate_verifier_result_invariants
from engine.verifier_emergency_output import serialize_emergency_operation_failure
from engine.verifier_snapshot import DirectFilesystemInputs, OperationalLimits
from test_verifier_round3_remediation import (
    _operate, _request, _inputs, _machine, _LIMITS, _VALIDATOR,
)
from test_verifier_operation_cli import _configuration_json, VALID_BUNDLE, ROOT

ERRORS = [RuntimeError, MemoryError, RecursionError]
PRIVATE = 'PRIVATE_AUDIT_EXCEPTION'


def emit(result):
    out, err = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, stdout=out, stderr=err)
    assert err.getvalue() == b''
    value = _machine(out.getvalue(), rc=rc)
    validate_verifier_result_invariants(value, process_rc=rc)
    return rc, value, out.getvalue()


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('target', [
    'engine.ai_cli._require_machine_frame',
    'engine.ai_cli.serialize_verifier_tool_result',
    'engine.ai_cli._operation_result_validator',
    'engine.ai_cli.validate_v2_value',
    'engine.ai_cli.validate_verifier_result_invariants',
    'engine.result_contracts.VerifierToolResult.to_json_value',
])
def test_normal_component_fault_cannot_disable_emergency(target, error):
    result = _operate()
    with mock.patch(target, side_effect=error(PRIVATE)):
        rc, value, _ = emit(result)
    assert rc == 3
    assert value['capability']['effective'] == value['capability']['requested']
    assert value['operational_result'] == dict(
        operational_code='INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED',
        phase='OUTPUT', input_ref=None, limit=None, detail=None,
    )


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('kind', ['io', 'limit', 'restricted', 'unavailable', 'exhausted', 'changed', 'type'])
def test_established_failure_precedes_later_frame_fault(error, kind, tmp_path):
    if kind == 'io':
        result = _operate(DirectFilesystemInputs(tmp_path / 'absent'))
    elif kind == 'limit':
        result = _operate(limits=VerifierLimitState(None, _LIMITS, OperationalLimits(max_file_bytes=1)))
    elif kind == 'restricted':
        result = _operate(_inputs(extra=b',"unknown":NaN'), request=_request(v1='V1_RESTRICTED_PORTABLE'))
    elif kind == 'unavailable':
        result = _operate(request=_request(signature='FUTURE'))
    else:
        from engine.verifier_snapshot import OperationalInputFailure, OperationalCode, OperationalPhase, InputRef
        code = {'exhausted':'RESOURCE_EXHAUSTED', 'changed':'INPUT_CHANGED_DURING_SNAPSHOT', 'type':'INPUT_NOT_REGULAR_FILE'}[kind]
        failure = OperationalInputFailure(OperationalCode(code), OperationalPhase.BUNDLE_SNAPSHOT, InputRef.AI_MANIFEST_JSON)
        with mock.patch.object(operation, 'acquire_verifier_snapshot', side_effect=failure):
            result = _operate()
    before = json.loads(serialize_verifier_tool_result(result))
    with mock.patch.object(cli, '_require_machine_frame', side_effect=error(PRIVATE)):
        rc, after, _ = emit(result)
    assert rc == 3 and after == before


@pytest.mark.parametrize('source_rc,frame_rc', [(0, 2), (0, 3), (2, 0), (2, 3), (3, 0), (3, 2)])
def test_schema_valid_rc_substitution_is_never_written(source_rc, frame_rc, tmp_path):
    results = {
        0: _operate(),
        2: _operate(_inputs(timestamp=b'"bad"')),
        3: _operate(DirectFilesystemInputs(tmp_path / 'absent')),
    }
    source, substitute = results[source_rc], results[frame_rc]
    assert source.rc == source_rc and substitute.rc == frame_rc
    frame = serialize_verifier_tool_result(substitute)
    _VALIDATOR.validate(json.loads(frame))
    with mock.patch.object(cli, 'serialize_verifier_tool_result', return_value=frame):
        rc, value, written = emit(source)
    assert rc == 3 and written != frame
    assert value['operational_result']['operational_code'] == ('INPUT_IO_ERROR' if source_rc == 3 else 'INTERNAL_OPERATION_ERROR')


@pytest.mark.parametrize('mutation', ['requested_v1', 'effective_v1', 'both_v1', 'requested_dispatch', 'requested_v2', 'requested_signature', 'effective_null', 'phase', 'maximum', 'observed', 'advertised', 'role'])
def test_schema_valid_normative_mutations_are_rejected(mutation):
    if mutation.startswith('requested_') and mutation != 'requested_v1':
        # Preselection failures permit unsupported request syntax in the schema.
        result = _operate(request=_request(signature='FUTURE'))
    elif mutation in {'phase', 'maximum', 'observed', 'advertised', 'role'}:
        result = _operate(limits=VerifierLimitState(None, _LIMITS, OperationalLimits(max_file_bytes=1)))
    else:
        result = _operate()
    value = json.loads(serialize_verifier_tool_result(result))
    if mutation in {'requested_v1', 'both_v1'}:
        value['capability']['requested']['v1']['capability'] = 'V1_RESTRICTED_PORTABLE'
    if mutation in {'effective_v1', 'both_v1'}:
        value['capability']['effective']['v1']['capability'] = 'V1_RESTRICTED_PORTABLE'
    if mutation == 'requested_dispatch': value['capability']['requested']['dispatch'] = 'FUTURE'
    if mutation == 'requested_v2': value['capability']['requested']['v2']['capability'] = 'FUTURE'
    if mutation == 'requested_signature': value['capability']['requested']['signature_verification']['profile'] = 'OTHER'
    if mutation == 'effective_null':
        # A schema-valid output failure can claim null effective, but the
        # operation actually selected one. Bind to that historical fact.
        result = _operate()
        value = json.loads(serialize_emergency_operation_failure(result))
        value['capability']['effective'] = None
    if mutation == 'phase': value['operational_result']['phase'] = 'OUTPUT'
    if mutation == 'maximum': value['operational_result']['limit']['maximum'] = 2
    if mutation == 'observed': value['operational_result']['limit']['observed_at_least'] = 0
    if mutation == 'advertised': value['limits']['advertised']['max_file_bytes'] = 0
    if mutation == 'role': value['operational_result']['input_ref'] = 'TRUST_STORE'
    _VALIDATOR.validate(value)
    with pytest.raises(ResultContractError):
        validate_verifier_result_invariants(value, expected_result=result, process_rc=result.rc)
    frame = rfc8785.dumps(value) + b'\n'
    with mock.patch.object(cli, 'serialize_verifier_tool_result', return_value=frame):
        rc, _, written = emit(result)
    assert rc == 3 and written != frame


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('target', [
    'engine.verifier_operation._input_mode',
    'engine.verifier_operation.validate_verifier_operation_options',
    'engine.verifier_operation.validate_verifier_capability_request',
    'engine.verifier_operation.AIVerificationOptions',
    'engine.ai_cli._verification_options',
    'engine.ai_cli.validate_verifier_operation_options',
    'engine.ai_cli.DirectFilesystemInputs',
    'engine.ai_cli.verify_bundle_operation',
    'engine.ai_cli._ensure_operation_serializer_available',
])
def test_entry_boundary_child_process(target, error):
    # Default-options constructor is reached only by the direct API, below.
    if target.endswith('.AIVerificationOptions'):
        program = f'''
import runpy
from unittest.mock import patch
h = runpy.run_path('tests/test_verifier_round3_remediation.py')
import engine.ai_cli as cli
with patch({target!r}, side_effect={error.__name__}({PRIVATE!r})):
    raise SystemExit(cli._emit_operation_json(h['_operate']()))
'''
    else:
        program = f'''
import sys
from unittest.mock import patch
import engine.ai_cli as cli
sys.argv = ['aelitium', 'verify-bundle', {str(VALID_BUNDLE)!r}, '--operation-json', {_configuration_json()!r}]
with patch({target!r}, side_effect={error.__name__}({PRIVATE!r})):
    raise SystemExit(cli.main())
'''
    p = subprocess.run([sys.executable, '-B', '-c', program], cwd=ROOT, capture_output=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
    assert p.returncode == 3 and p.stderr == b''
    value = _machine(p.stdout)
    validate_verifier_result_invariants(value, process_rc=p.returncode)
    assert value['capability']['effective'] is None
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')


@pytest.mark.parametrize('field', ['signature', 'v1', 'v2', 'dispatch', 'fixed_v1', 'unexpected_profile', 'requested'])
def test_typed_invalid_preparation_never_reaches_semantics(field):
    request = _request()
    if field == 'signature': request = _request(signature='FUTURE')
    if field == 'v1': request = dataclasses.replace(request, v1=capabilities.V1CapabilityDeclaration('FUTURE'))
    if field == 'v2': request = dataclasses.replace(request, v2=capabilities.V2CapabilityDeclaration('FUTURE'))
    if field == 'dispatch': request = dataclasses.replace(request, dispatch=capabilities.DispatchCapabilityDeclaration('FUTURE'))
    if field == 'fixed_v1': request = dataclasses.replace(request, v1=dataclasses.replace(request.v1, timestamp_final_lf='FUTURE'))
    candidate = capabilities.PreparedVerifierCapabilities(request, object() if field == 'unexpected_profile' else None)
    if field == 'requested': candidate = capabilities.PreparedVerifierCapabilities(_request(v1='V1_RESTRICTED_PORTABLE'), None)
    with mock.patch.object(operation, 'prepare_verifier_capabilities', return_value=candidate), mock.patch.object(operation, 'verify_ai_snapshot') as semantic, mock.patch.object(operation, 'acquire_verifier_snapshot') as snapshot:
        result = _operate(request=request)
    assert not semantic.called and not snapshot.called
    rc, value, _ = emit(result)
    assert rc == 3 and value['capability']['effective'] is None
    assert value['operational_result']['operational_code'] == 'INTERNAL_OPERATION_ERROR'
    assert value['operational_result']['phase'] == 'CAPABILITY_SELECTION'


@pytest.mark.parametrize('field', ['ranges', 'metadata', 'digest', 'missing', 'range_type'])
def test_named_profile_executable_data_is_authenticated(field):
    config = cli._parse_operation_config_json(_configuration_json(v1='V1_NAMED_RUNTIME_COMPATIBILITY'))
    candidate = capabilities.prepare_verifier_capabilities(config.capability_request)
    profile = candidate.named_timestamp_profile
    if field == 'ranges': profile = dataclasses.replace(profile, ranges=profile.ranges[:-1])
    if field == 'metadata': profile = dataclasses.replace(profile, metadata=capabilities.FROZEN_UNICODE_PROFILES[0])
    if field == 'digest': profile = dataclasses.replace(profile, actual_range_file_sha256='0'*64)
    if field == 'missing': profile = None
    if field == 'range_type': profile = dataclasses.replace(profile, ranges=list(profile.ranges))
    candidate = dataclasses.replace(candidate, named_timestamp_profile=profile)
    with mock.patch.object(operation, 'prepare_verifier_capabilities', return_value=candidate), mock.patch.object(operation, 'verify_ai_snapshot') as semantic:
        result = _operate(request=config.capability_request)
    assert not semantic.called
    _, value, _ = emit(result)
    assert value['capability']['effective'] is None
    assert value['operational_result']['operational_code'] == 'INTERNAL_OPERATION_ERROR'


@pytest.mark.parametrize('error', ERRORS)
def test_preparation_postcondition_resource_classification(error):
    with mock.patch.object(operation, 'validate_prepared_verifier_capabilities', side_effect=error(PRIVATE)):
        result = _operate()
    _, value, _ = emit(result)
    assert value['capability']['effective'] is None
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('target', ['engine.ai_cli.serialize_emergency_operation_failure', 'engine.verifier_emergency_output._capability_value'])
def test_emergency_component_failure_is_terminal_and_private(target, error):
    result = _operate()
    out, err = io.BytesIO(), io.BytesIO()
    with mock.patch.object(cli, '_require_machine_frame', side_effect=RuntimeError(PRIVATE)), mock.patch(target, side_effect=error(PRIVATE)):
        rc = cli._emit_operation_json(result, stdout=out, stderr=err)
    assert rc == 3 and out.getvalue() == b''
    code = b'INTERNAL_OPERATION_ERROR' if error is RuntimeError else b'RESOURCE_EXHAUSTED'
    assert err.getvalue() == b'AELITIUM_OPERATIONAL ' + code + b' OUTPUT NONE\n'


def test_normal_bytes_and_independent_emergency_closure():
    result = _operate()
    normal = serialize_verifier_tool_result(result)
    rc, value, emitted = emit(result)
    assert rc == 0 and emitted == normal == rfc8785.dumps(value) + b'\n'
    emergency = serialize_emergency_operation_failure(result)
    value = _machine(emergency)
    validate_verifier_result_invariants(value, process_rc=3)
    assert emergency == rfc8785.dumps(value) + b'\n'


def test_faulty_projection_cannot_rewrite_both_capabilities():
    import engine.result_contracts as contracts
    result = _operate()
    original = contracts.project_capability_request
    def altered(request):
        value = original(request)
        value['v1']['capability'] = 'V1_RESTRICTED_PORTABLE'
        return value
    with mock.patch.object(contracts, 'project_capability_request', side_effect=altered):
        rc, value, _ = emit(result)
    assert rc == 3
    assert value['capability']['effective']['v1']['capability'] == 'V1_FROZEN_LEGACY_COMPATIBILITY'


@pytest.mark.parametrize('error', ERRORS)
def test_emergency_record_constructor_failure_child_process(error):
    program = f'''
import sys
from unittest.mock import patch
import engine.ai_cli as cli
sys.argv=['aelitium','verify-bundle',{str(VALID_BUNDLE)!r},'--operation-json',{_configuration_json()!r}]
with patch.object(cli,'_ensure_operation_serializer_available',side_effect=RuntimeError({PRIVATE!r})), patch.object(cli.VerifierToolResult,'emergency_operational',side_effect={error.__name__}({PRIVATE!r})):
    raise SystemExit(cli.main())
'''
    p = subprocess.run([sys.executable, '-B', '-c', program], cwd=ROOT, capture_output=True)
    assert p.returncode == 3 and p.stdout == b''
    code = b'INTERNAL_OPERATION_ERROR' if error is RuntimeError else b'RESOURCE_EXHAUSTED'
    assert p.stderr == b'AELITIUM_OPERATIONAL ' + code + b' OUTPUT NONE\n'


@pytest.mark.parametrize('mutation', ['effective', 'phase', 'maximum', 'observed', 'advertised', 'role'])
def test_normative_validator_checks_relationships_without_expected_record(mutation):
    result = _operate(limits=VerifierLimitState(None, _LIMITS, OperationalLimits(max_file_bytes=1)))
    value = json.loads(serialize_verifier_tool_result(result))
    if mutation == 'effective': value['capability']['effective']['v1']['capability'] = 'V1_RESTRICTED_PORTABLE'
    if mutation == 'phase': value['operational_result']['phase'] = 'OUTPUT'
    if mutation == 'maximum': value['operational_result']['limit']['maximum'] = 2
    if mutation == 'observed': value['operational_result']['limit']['observed_at_least'] = 0
    if mutation == 'advertised': value['limits']['advertised']['max_file_bytes'] = 0
    if mutation == 'role': value['operational_result']['input_ref'] = 'TRUST_STORE'
    _VALIDATOR.validate(value)
    with pytest.raises(ResultContractError):
        validate_verifier_result_invariants(value)


def test_faulty_projection_cannot_rewrite_established_failure(tmp_path):
    import engine.result_contracts as contracts
    result = _operate(DirectFilesystemInputs(tmp_path / 'absent'))
    original = contracts.project_operational_result
    def altered(failure):
        value = original(failure)
        value['operational_code'] = 'INPUT_NOT_REGULAR_FILE'
        return value
    with mock.patch.object(contracts, 'project_operational_result', side_effect=altered):
        rc, value, _ = emit(result)
    assert rc == 3 and value['operational_result']['operational_code'] == 'INPUT_IO_ERROR'


@pytest.mark.parametrize('error', ERRORS)
def test_postselection_entry_into_trust_stage_retains_effective(error):
    with mock.patch.object(operation, '_trust_input_was_supplied', side_effect=error(PRIVATE)):
        result = _operate()
    _, value, _ = emit(result)
    assert value['capability']['effective'] == value['capability']['requested']
    assert value['operational_result']['phase'] == 'TRUST_INPUT'
    assert value['operational_result']['operational_code'] == ('INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED')
