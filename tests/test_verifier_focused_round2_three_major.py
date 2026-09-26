"""Focused Round 2 R2-01/02/03 (not the older global Round 2 findings)."""
from __future__ import annotations

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
from engine.result_contracts import serialize_verifier_tool_result
from engine.verifier_snapshot import (
    DirectFilesystemInputs, InputMode, OperationalCode, OperationalInputFailure,
    OperationalPhase,
)
from test_verifier_round3_remediation import _operate, _request, _inputs, _VALIDATOR
from test_verifier_operation_cli import ROOT, VALID_BUNDLE, _configuration_json

PRIVATE = 'SYNTHETIC_PRIVATE_FAULT'
ERRORS = (RuntimeError, MemoryError, RecursionError)
# Literal canonical bytes, written from the closed contract rather than obtained
# from either production serializer. These also exercise independent key order.
CAP = (
    b'{"dispatch":"AELITIUM-DISPATCH-JSON-1","signature_verification":'
    b'{"profile":"ED25519_PORTABLE_STRICT_1"},"v1":{"capability":'
    b'"V1_FROZEN_LEGACY_COMPATIBILITY","integer_conversion":'
    b'{"maximum_decimal_digits":640,"mode":"BOUNDED"},"timestamp_digit_profile":'
    b'"ASCII","timestamp_final_lf":"ACCEPT_ONE"},"v2":{"capability":"V2_PORTABLE"}}'
)
LIMITS = (
    b'{"max_file_bytes":65536,"max_structural_depth":1024,'
    b'"max_total_snapshot_bytes":262144,"max_value_occurrences":65536}'
)


def expected_output_failure(code=b'INTERNAL_OPERATION_ERROR'):
    return (
        b'{"capability":{"effective":' + CAP + b',"requested":' + CAP +
        b'},"contract":"aelitium-verifier-tool-result-v1","input_mode":"IMMUTABLE_BYTES",'
        b'"limits":{"advertised":' + LIMITS + b',"claimed_envelope":'
        b'"AELITIUM_CLEANROOM_MINIMUM_1","effective":' + LIMITS +
        b'},"operation":"VERIFY_BUNDLE","operational_result":{"detail":null,'
        b'"input_ref":null,"limit":null,"operational_code":"' + code +
        b'","phase":"OUTPUT"},"outcome":"OPERATIONAL_OUTCOME","rc":3,'
        b'"verification_result":null}\n'
    )


def emit(result):
    out, err = io.BytesIO(), io.BytesIO()
    rc = cli._emit_operation_json(result, stdout=out, stderr=err)
    assert err.getvalue() == b''
    raw = out.getvalue()
    value = json.loads(raw)
    _VALIDATOR.validate(value)
    assert raw == rfc8785.dumps(value) + b'\n'
    assert value['rc'] == rc
    assert PRIVATE.encode() not in raw and b'Traceback' not in raw
    return rc, value, raw


@pytest.mark.parametrize('error', ERRORS)
@pytest.mark.parametrize('stage', ['entry', 'selection', 'acquisition', 'output', 'established'])
def test_persistent_failure_constructor_cli(stage, error, tmp_path):
    config = json.loads(_configuration_json())
    if stage == 'selection':
        config['capability']['signature_verification']['profile'] = 'FUTURE'
    target = str(tmp_path / 'missing') if stage == 'acquisition' else str(VALID_BUNDLE)
    # The typed failure in the last variant is established *before* the fault.
    body = f'''
import sys
from contextlib import ExitStack
from unittest.mock import patch
import engine.ai_cli as cli
import engine.verifier_operation as operation
from engine.verifier_snapshot import *
prior = OperationalInputFailure(OperationalCode.INPUT_IO_ERROR, OperationalPhase.BUNDLE_SNAPSHOT, InputRef.BUNDLE_DIRECTORY)
sys.argv = ['aelitium','verify-bundle',{target!r},'--operation-json',{json.dumps(config)!r}]
with ExitStack() as stack:
    constructor = stack.enter_context(patch.object(OperationalInputFailure,'__post_init__',side_effect={error.__name__}({PRIVATE!r})))
'''
    if stage == 'entry':
        body += f"    stack.enter_context(patch.object(cli,'Path',side_effect={error.__name__}({PRIVATE!r})))\n"
    if stage == 'output':
        body += f"    stack.enter_context(patch.object(cli,'serialize_verifier_tool_result',side_effect={error.__name__}({PRIVATE!r})))\n"
    if stage == 'established':
        body += "    stack.enter_context(patch.object(operation,'acquire_verifier_snapshot',side_effect=prior))\n"
        body += f"    stack.enter_context(patch.object(cli,'serialize_verifier_tool_result',side_effect={error.__name__}({PRIVATE!r})))\n"
    body += f"    rc = cli.main()\n    assert constructor.call_count == {1 if stage in ('selection','acquisition') else 0}\n    raise SystemExit(rc)\n"
    p = subprocess.run([sys.executable, '-B', '-c', body], cwd=ROOT, capture_output=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert p.returncode == 3 and p.stderr == b''
    value = json.loads(p.stdout)
    _VALIDATOR.validate(value)
    assert p.stdout == rfc8785.dumps(value) + b'\n'
    assert value['capability']['requested'] == config['capability']
    assert (value['capability']['effective'] is None) == (stage in ('entry', 'selection'))
    code = 'INTERNAL_OPERATION_ERROR' if error is RuntimeError else 'RESOURCE_EXHAUSTED'
    assert value['operational_result']['operational_code'] == ('INPUT_IO_ERROR' if stage == 'established' else code)
    phase = {'entry':'CAPABILITY_SELECTION', 'selection':'CAPABILITY_SELECTION',
             'acquisition':'BUNDLE_SNAPSHOT', 'output':'OUTPUT', 'established':'BUNDLE_SNAPSHOT'}[stage]
    assert value['operational_result']['phase'] == phase
    assert value['operational_result']['input_ref'] == ('BUNDLE_DIRECTORY' if stage == 'established' else None)


@pytest.mark.parametrize('stage', ['selected', 'unselected', 'typed_failure'])
@pytest.mark.parametrize('mutation', ['requested', 'effective', 'both', 'future', 'input_mode', 'limits', 'aliased_capability', 'aliased_limits', 'float_limit'])
def test_builder_metadata_cannot_be_its_own_reference(stage, mutation, tmp_path):
    request = _request(signature='FUTURE') if stage == 'unselected' else _request()
    original = operation.build_verifier_tool_result
    def altered(**kw):
        if mutation in ('aliased_capability', 'aliased_limits'):
            # Mutate the actual argument's nested dataclass, not just a copy.
            # The independently retained invocation must remain unchanged.
            if mutation == 'aliased_capability':
                for key in ('requested_capability', 'effective_capability'):
                    if kw[key] is not None:
                        object.__setattr__(kw[key].v1, 'capability', 'V1_RESTRICTED_PORTABLE')
            else:
                for key in ('advertised', 'effective'):
                    object.__setattr__(getattr(kw['limits'], key), 'max_file_bytes', 131072)
            return original(**kw)
        result = original(**kw)
        if mutation in ('requested', 'effective', 'both', 'future'):
            changed = dataclasses.replace(request, v1=dataclasses.replace(request.v1, capability='V1_RESTRICTED_PORTABLE'))
            if mutation == 'future':
                changed = dataclasses.replace(request, signature_verification=dataclasses.replace(request.signature_verification, profile='FUTURE'))
            for key in ('requested_capability', 'effective_capability'):
                if mutation in ('both', 'future') or key.startswith(mutation):
                    object.__setattr__(result, key, changed)
        elif mutation == 'input_mode':
            object.__setattr__(result, 'input_mode', InputMode.DIRECT_FILESYSTEM if stage != 'typed_failure' else InputMode.IMMUTABLE_BYTES)
        else:
            for key in ('advertised', 'effective'):
                object.__setattr__(getattr(result.limits, key), 'max_file_bytes', 65536.0 if mutation == 'float_limit' else 131072)
        return result
    inputs = DirectFilesystemInputs(tmp_path / 'missing') if stage == 'typed_failure' else None
    with patch.object(operation, 'build_verifier_tool_result', side_effect=altered):
        result = _operate(inputs, request=request)
    rc, value, _ = emit(result)
    assert rc == 3
    # The caller's own frozen values also must not have been mutated by builder.
    assert request == (_request(signature='FUTURE') if stage == 'unselected' else _request())
    expected_request = json.loads(CAP)
    if stage == 'unselected': expected_request['signature_verification']['profile'] = 'FUTURE'
    assert value['capability']['requested'] == expected_request
    assert value['capability']['effective'] == (None if stage == 'unselected' else expected_request)
    assert value['limits']['advertised'] == value['limits']['effective'] == json.loads(LIMITS)
    assert value['input_mode'] == ('DIRECT_FILESYSTEM' if stage == 'typed_failure' else 'IMMUTABLE_BYTES')
    assert value['operational_result']['operational_code'] == {
        'selected':'INTERNAL_OPERATION_ERROR', 'unselected':'CAPABILITY_PROFILE_UNAVAILABLE', 'typed_failure':'INPUT_IO_ERROR',
    }[stage]


@pytest.mark.parametrize('mutation', ['both', 'limits', 'input_mode'])
def test_output_mutation_cannot_change_recovery_metadata(mutation):
    result = _operate()
    original = cli.serialize_verifier_tool_result
    def altered(record):
        if mutation == 'both':
            for key in ('requested_capability', 'effective_capability'):
                object.__setattr__(getattr(record, key).signature_verification, 'profile', 'FUTURE')
        elif mutation == 'limits':
            for key in ('advertised', 'effective'):
                object.__setattr__(getattr(record.limits, key), 'max_file_bytes', 131072)
        else:
            object.__setattr__(record, 'input_mode', InputMode.DIRECT_FILESYSTEM)
        return original(record)
    with patch.object(cli, 'serialize_verifier_tool_result', side_effect=altered):
        rc, _, raw = emit(result)
    assert rc == 3 and raw == expected_output_failure()


WIRE_MUTATIONS = {
    'rounded_fraction': lambda b: b.replace(b'"max_file_bytes":65536', b'"max_file_bytes":65536.000000000001', 1),
    'rc_float': lambda b: b.replace(b'"rc":0,', b'"rc":0.0,', 1),
    'negative_zero': lambda b: b.replace(b'"rc":0,', b'"rc":-0,', 1),
    'exponent': lambda b: b.replace(b'"max_file_bytes":65536', b'"max_file_bytes":6.5536e4', 1),
    'negative_exponent': lambda b: b.replace(b'"rc":0,', b'"rc":1e-1000,', 1),
    'fraction': lambda b: b.replace(b'"max_file_bytes":65536', b'"max_file_bytes":65536.5', 1),
    'leading_space': lambda b: b' ' + b,
    'tab': lambda b: b.replace(b':', b':\t', 1),
    'trailing_space': lambda b: b[:-1] + b' \n',
    'key_order': lambda b: (json.dumps(dict(reversed(list(json.loads(b).items()))), separators=(',', ':')) + '\n').encode(),
    'escaped_key': lambda b: b.replace(b'"contract":', b'"\\u0063ontract":', 1),
    'escaped_slash': lambda b: b.replace(b'bundle:ai_canonical.json#/metadata', b'bundle:ai_canonical.json#\\/metadata'),
    'no_lf': lambda b: b[:-1],
    'crlf': lambda b: b[:-1] + b'\r\n',
    'extra_lf': lambda b: b + b'\n',
    'second_value': lambda b: b[:-1] + b' {}\n',
    'bom': lambda b: b'\xef\xbb\xbf' + b,
}


@pytest.mark.parametrize('mutation', WIRE_MUTATIONS)
def test_noncanonical_wire_bytes_never_reach_stdout(mutation):
    # full_a supplies slash-containing refs, unlike a minimal semantic result.
    config = cli._parse_operation_config_json(_configuration_json())
    result = operation.verify_bundle_operation(DirectFilesystemInputs(VALID_BUNDLE), capability_request=config.capability_request, limits=config.limits)
    good = serialize_verifier_tool_result(result)
    bad = WIRE_MUTATIONS[mutation](good)
    assert bad != good
    with patch.object(cli, 'serialize_verifier_tool_result', return_value=bad):
        rc, value, raw = emit(result)
    assert rc == 3 and raw != bad
    assert raw == expected_output_failure().replace(b'IMMUTABLE_BYTES', b'DIRECT_FILESYSTEM')
    assert value['operational_result']['phase'] == 'OUTPUT'


@pytest.mark.parametrize('detail,canonical,noncanonical', [
    ('é', b'"detail":"\xc3\xa9"', b'"detail":"\\u00e9"'),
    ('𝄞', b'"detail":"\xf0\x9d\x84\x9e"', b'"detail":"\\ud834\\udd1e"'),
    ('line\n\t\b\x0f', b'"detail":"line\\n\\t\\b\\u000f"', b'"detail":"line\\u000a\\t\\b\\u000F"'),
    ('/', b'"detail":"/"', b'"detail":"\\/"'),
])
def test_unicode_and_escapes_follow_actual_canonical_contract(detail, canonical, noncanonical):
    # The schema permits a non-null detail only on an INVALID semantic result.
    source = _operate(_inputs(timestamp=b'"bad"'))
    result = dataclasses.replace(source, verification_result={**source.verification_result, 'detail': detail})
    rc, _, good = emit(result)
    assert rc == 2 and canonical in good
    bad = good.replace(canonical, noncanonical)
    with patch.object(cli, 'serialize_verifier_tool_result', return_value=bad):
        rc, _, raw = emit(result)
    assert rc == 3 and raw == expected_output_failure()


@pytest.mark.parametrize('ceiling', [0, 1, 65536, 9007199254740991])
def test_literal_safe_integer_spellings_remain_accepted(ceiling):
    source = _operate()
    from engine.verifier_snapshot import OperationalLimits
    from engine.result_contracts import VerifierLimitState
    limit = OperationalLimits(ceiling, ceiling, ceiling, ceiling)
    result = dataclasses.replace(source, limits=VerifierLimitState(None, limit, limit))
    rc, _, raw = emit(result)
    assert rc == 0
    assert b'"max_file_bytes":' + str(ceiling).encode() + b',' in raw


def test_expected_emergency_bytes_are_independent_of_normal_serializer_and_validator():
    result = _operate()
    with patch.object(cli, 'serialize_verifier_tool_result', side_effect=MemoryError(PRIVATE)), patch.object(cli, '_require_machine_frame', side_effect=RuntimeError(PRIVATE)):
        rc, _, raw = emit(result)
    assert rc == 3 and raw == expected_output_failure(b'RESOURCE_EXHAUSTED')
