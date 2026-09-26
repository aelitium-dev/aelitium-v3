"""Operational input-acquisition and immutable-snapshot tests."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

import pytest

import engine.verifier_snapshot as snapshot_runtime
from engine.ai_contract import (
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_FILENAME,
    AI_VERIFICATION_KEYS_FILENAME,
)
from engine.verifier_snapshot import (
    BUNDLE_ROLE_ORDER,
    DirectFilesystemInputs,
    ImmutableBytesInputs,
    InputMode,
    InputRef,
    InputRole,
    LimitName,
    LimitUnit,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
    StablePresence,
    acquire_direct_filesystem_snapshot,
    acquire_immutable_bytes_snapshot,
    acquire_verifier_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL_RESULT_SCHEMA_PATH = ROOT / "engine" / "schemas" / "verifier_tool_result_v1.json"
FROZEN_CASES_PATH = (
    ROOT / "conformance" / "legacy_v1_operational_policy" / "cases.json"
)
FROZEN_CASES = {
    item["case_id"]: item
    for item in json.loads(FROZEN_CASES_PATH.read_text(encoding="utf-8"))["vectors"]
}


def _bundle(tmp_path: Path, **role_bytes: bytes) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    filenames = {
        "canonical": AI_CANONICAL_FILENAME,
        "manifest": AI_MANIFEST_FILENAME,
        "keyring": AI_VERIFICATION_KEYS_FILENAME,
    }
    for role_name, data in role_bytes.items():
        (bundle / filenames[role_name]).write_bytes(data)
    return bundle


def _frozen_operational(case_id: str) -> dict:
    return FROZEN_CASES[case_id]["expected"]["tool_result"]["operational_result"]


def _assert_frozen_failure(error: OperationalInputFailure, case_id: str) -> None:
    expected = _frozen_operational(case_id)
    actual_limit = None
    if error.limit is not None:
        actual_limit = {
            "name": error.limit.name.value,
            "unit": error.limit.unit.value,
            "maximum": error.limit.maximum,
            "observed_at_least": error.limit.observed_at_least,
        }
    assert {
        "operational_code": error.operational_code.value,
        "phase": error.phase.value,
        "input_ref": None if error.input_ref is None else error.input_ref.value,
        "limit": actual_limit,
        "detail": error.detail,
    } == expected


def _capture_failure(call) -> OperationalInputFailure:
    with pytest.raises(OperationalInputFailure) as caught:
        call()
    return caught.value


def test_operational_phase_registry_matches_schema_and_authored_corpus() -> None:
    schema = json.loads(TOOL_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_phases = tuple(
        schema["definitions"]["operational_result"]["properties"]["phase"][
            "enum"
        ]
    )
    corpus_phases = {
        tool_result["operational_result"]["phase"]
        for case in FROZEN_CASES.values()
        if (
            (tool_result := case.get("expected", {}).get("tool_result"))
            and tool_result.get("operational_result") is not None
        )
    }
    runtime_phases = tuple(phase.value for phase in OperationalPhase)

    assert runtime_phases == schema_phases
    assert set(runtime_phases) == corpus_phases
    assert OperationalPhase("SEMANTIC_EVALUATION") is (
        OperationalPhase.SEMANTIC_EVALUATION
    )
    with pytest.raises(ValueError):
        OperationalPhase("UNKNOWN_OPERATIONAL_PHASE")


def test_immutable_bytes_mode_preserves_exact_bytes_and_absence() -> None:
    canonical = b"\x00not-json\xff"
    manifest = b'{"malformed":'
    with mock.patch.object(
        snapshot_runtime,
        "_os_open",
        side_effect=AssertionError("immutable-byte mode must not access files"),
    ):
        frozen = acquire_verifier_snapshot(
            ImmutableBytesInputs(canonical, manifest, None)
        )

    assert frozen.input_mode is InputMode.IMMUTABLE_BYTES
    assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == canonical
    assert frozen.bytes_for(InputRole.AI_MANIFEST_JSON) == manifest
    assert frozen.input_for(InputRole.VERIFICATION_KEYS_JSON).presence is (
        StablePresence.ABSENT
    )
    assert frozen.bytes_for(InputRole.TRUST_STORE) is None


def test_operation_limits_use_only_the_normative_minimum_envelope_defaults() -> None:
    limits = OperationalLimits()
    assert (
        limits.max_file_bytes,
        limits.max_total_snapshot_bytes,
        limits.max_structural_depth,
        limits.max_value_occurrences,
    ) == (65_536, 262_144, 1_024, 65_536)


def test_direct_filesystem_mode_preserves_exact_bytes(tmp_path: Path) -> None:
    canonical = b"\x00canonical\r\n\xff"
    manifest = b"manifest bytes\n"
    keyring = b"keyring bytes"
    bundle = _bundle(
        tmp_path,
        canonical=canonical,
        manifest=manifest,
        keyring=keyring,
    )

    frozen = acquire_verifier_snapshot(DirectFilesystemInputs(bundle))

    assert frozen.input_mode is InputMode.DIRECT_FILESYSTEM
    assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == canonical
    assert frozen.bytes_for(InputRole.AI_MANIFEST_JSON) == manifest
    assert frozen.bytes_for(InputRole.VERIFICATION_KEYS_JSON) == keyring
    assert frozen.total_bytes == len(canonical) + len(manifest) + len(keyring)


def test_trust_precedes_three_deterministic_bundle_passes(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"c", manifest=b"m", keyring=b"k")
    trust = tmp_path / "trust.json"
    trust.write_bytes(b"t")
    events: list[tuple[str, str]] = []

    with mock.patch.object(
        snapshot_runtime,
        "_snapshot_hook",
        side_effect=lambda point, role: events.append((point, role.value)),
    ):
        acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(bundle, trust_store_path=trust)
        )

    assert events == [
        ("INITIAL_OBSERVATION", "TRUST_STORE"),
        ("BYTE_ACQUISITION", "TRUST_STORE"),
        ("FINAL_OBSERVATION", "TRUST_STORE"),
        *(('INITIAL_OBSERVATION', role.value) for role in BUNDLE_ROLE_ORDER),
        *(("BYTE_ACQUISITION", role.value) for role in BUNDLE_ROLE_ORDER),
        *(("FINAL_OBSERVATION", role.value) for role in BUNDLE_ROLE_ORDER),
    ]


def test_bundle_root_failure_precedes_supplied_trust_failure(tmp_path: Path) -> None:
    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(
                tmp_path / "missing-bundle",
                trust_store_path=tmp_path / "missing-trust.json",
            )
        )
    )
    assert error.operational_code is OperationalCode.INPUT_IO_ERROR
    assert error.phase is OperationalPhase.BUNDLE_SNAPSHOT
    assert error.input_ref is InputRef.BUNDLE_DIRECTORY


def test_supplied_trust_failure_precedes_bundle_role_failure(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / AI_CANONICAL_FILENAME).symlink_to(tmp_path / "target")

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(
                bundle,
                trust_store_path=tmp_path / "missing-trust.json",
            )
        )
    )
    assert error.operational_code is OperationalCode.INPUT_IO_ERROR
    assert error.phase is OperationalPhase.TRUST_INPUT
    assert error.input_ref is InputRef.TRUST_STORE


def test_optional_keyring_has_stable_absence(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}", manifest=b"{}")
    frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))

    keyring = frozen.input_for(InputRole.VERIFICATION_KEYS_JSON)
    assert keyring.presence is StablePresence.ABSENT
    assert keyring.data is None
    assert FROZEN_CASES["snapshot.stable_absence.keyring"]["expected"] == {
        "decision": "SEMANTIC_ABSENCE",
        "kind": "POLICY_CHECKPOINT",
        "semantic_result": "SIGNATURE_ABSENT",
    }


def test_absent_role_appearing_before_final_check_is_unstable(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}", manifest=b"{}")

    def create_keyring(point: str, role: InputRole) -> None:
        if point == "INITIAL_OBSERVATION" and role is InputRole.VERIFICATION_KEYS_JSON:
            (bundle / AI_VERIFICATION_KEYS_FILENAME).write_bytes(b"{}")

    with mock.patch.object(snapshot_runtime, "_snapshot_hook", create_keyring):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )

    assert error.operational_code is OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT
    assert error.input_ref is InputRef.VERIFICATION_KEYS_JSON


def test_symlink_bundle_path_component_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    bundle = _bundle(actual, canonical=b"{}")
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(actual, target_is_directory=True)

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(linked_parent / bundle.name)
        )
    )
    _assert_frozen_failure(error, "snapshot.reject.bundle_root_symlink")


def test_symlink_final_bundle_file_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    target = tmp_path / "canonical-target"
    target.write_bytes(b"{}")
    (bundle / AI_CANONICAL_FILENAME).symlink_to(target)

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    )
    _assert_frozen_failure(error, "snapshot.reject.symlink")


def test_directory_instead_of_file_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / AI_MANIFEST_FILENAME).mkdir()

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    )
    _assert_frozen_failure(error, "snapshot.reject.directory")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO creation is unavailable")
def test_fifo_is_rejected_without_opening_it(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    os.mkfifo(bundle / AI_VERIFICATION_KEYS_FILENAME)

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    )
    _assert_frozen_failure(error, "snapshot.reject.fifo")


def test_file_disappearance_between_read_and_final_observation(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"c", manifest=b"m")
    manifest = bundle / AI_MANIFEST_FILENAME

    def disappear(point: str, role: InputRole) -> None:
        if point == "BYTE_ACQUISITION" and role is InputRole.AI_MANIFEST_JSON:
            manifest.unlink()

    with mock.patch.object(snapshot_runtime, "_snapshot_hook", disappear):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )
    _assert_frozen_failure(error, "snapshot.changed.disappearance")


def test_file_replacement_between_initial_and_final_observation(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b'{"x":1}')
    canonical = bundle / AI_CANONICAL_FILENAME
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b'{"x":2}')

    def replace(point: str, role: InputRole) -> None:
        if point == "INITIAL_OBSERVATION" and role is InputRole.AI_CANONICAL_JSON:
            os.replace(replacement, canonical)

    with mock.patch.object(snapshot_runtime, "_snapshot_hook", replace):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )
    _assert_frozen_failure(error, "snapshot.changed.replacement")


def test_file_growth_after_initial_observation_is_unstable(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, manifest=b"m")
    manifest = bundle / AI_MANIFEST_FILENAME

    def grow(point: str, role: InputRole) -> None:
        if point == "INITIAL_OBSERVATION" and role is InputRole.AI_MANIFEST_JSON:
            with manifest.open("ab") as stream:
                stream.write(b"ore")

    with mock.patch.object(snapshot_runtime, "_snapshot_hook", grow):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )
    _assert_frozen_failure(error, "snapshot.changed.growth")


def test_open_failure_is_input_io_error(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, manifest=b"{}")
    original_open = snapshot_runtime._os_open

    def fail_manifest(path: str, flags: int, *, dir_fd: int | None = None) -> int:
        if path == AI_MANIFEST_FILENAME:
            raise PermissionError(errno.EACCES, "injected open failure")
        return original_open(path, flags, dir_fd=dir_fd)

    with mock.patch.object(snapshot_runtime, "_os_open", fail_manifest):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )
    _assert_frozen_failure(error, "snapshot.io.open_error")


def test_canonical_permission_failure_matches_operational_contract(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}", manifest=b"{}")
    original_open = snapshot_runtime._os_open

    def deny_canonical(path: str, flags: int, *, dir_fd: int | None = None) -> int:
        if path == AI_CANONICAL_FILENAME:
            raise PermissionError(errno.EACCES, "injected permission failure")
        return original_open(path, flags, dir_fd=dir_fd)

    with mock.patch.object(snapshot_runtime, "_os_open", deny_canonical):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(
                DirectFilesystemInputs(bundle)
            )
        )

    _assert_frozen_failure(error, "snapshot.io.permission")


def test_short_reads_are_accumulated_in_one_acquisition(tmp_path: Path) -> None:
    source = b'{"x":1}'
    bundle = _bundle(tmp_path, canonical=source)
    original_read = snapshot_runtime._os_read

    def one_byte(fd: int, length: int) -> bytes:
        return original_read(fd, min(length, 1))

    with mock.patch.object(snapshot_runtime, "_os_read", one_byte):
        frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))

    assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == source
    assert hashlib.sha256(source).hexdigest() == FROZEN_CASES[
        "snapshot.short_reads.accumulated"
    ]["expected"]["captured_sha256"]


def test_memory_error_during_read_is_resource_exhaustion(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}")
    with mock.patch.object(snapshot_runtime, "_os_read", side_effect=MemoryError):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
        )

    assert error.operational_code is OperationalCode.RESOURCE_EXHAUSTED
    assert error.phase is OperationalPhase.BUNDLE_SNAPSHOT
    assert error.input_ref is InputRef.AI_CANONICAL_JSON
    assert error.limit is None


def test_per_file_limit_matches_frozen_above_case() -> None:
    source = b"a" * 65_537
    error = _capture_failure(
        lambda: acquire_immutable_bytes_snapshot(
            ImmutableBytesInputs(source, None, None)
        )
    )

    _assert_frozen_failure(error, "limit.file_bytes.above")
    assert error.limit is not None
    assert error.limit.name is LimitName.FILE_BYTES
    assert error.limit.unit is LimitUnit.BYTES


@pytest.mark.parametrize("size", [65_535, 65_536])
def test_per_file_limit_is_inclusive(size: int) -> None:
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(b"a" * size, None, None)
    )
    assert frozen.total_bytes == size


def test_total_snapshot_limit_matches_frozen_above_case() -> None:
    limits = OperationalLimits(max_file_bytes=131_072)
    source = b"a" * 65_536
    error = _capture_failure(
        lambda: acquire_immutable_bytes_snapshot(
            ImmutableBytesInputs(
                source,
                source,
                source,
                trust_store=source + b"a",
            ),
            limits=limits,
        )
    )

    _assert_frozen_failure(error, "limit.total_snapshot_bytes.above")
    assert error.limit is not None
    assert error.limit.name is LimitName.TOTAL_SNAPSHOT_BYTES


def test_total_limit_waits_for_all_initial_type_checks(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"aaaa", manifest=b"mmmm")
    (bundle / AI_VERIFICATION_KEYS_FILENAME).mkdir()
    limits = OperationalLimits(max_file_bytes=4, max_total_snapshot_bytes=1)

    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(bundle), limits=limits
        )
    )
    assert error.operational_code is OperationalCode.INPUT_NOT_REGULAR_FILE
    assert error.input_ref is InputRef.VERIFICATION_KEYS_JSON
    assert error.limit is None


def test_total_limit_is_checked_after_initial_pass_before_bundle_reads(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, canonical=b"cccc", manifest=b"mmmm", keyring=b"kkkk")
    trust = tmp_path / "trust.json"
    trust.write_bytes(b"tttt")
    limits = OperationalLimits(max_file_bytes=4, max_total_snapshot_bytes=15)
    events: list[tuple[str, InputRole]] = []

    with mock.patch.object(
        snapshot_runtime,
        "_snapshot_hook",
        side_effect=lambda point, role: events.append((point, role)),
    ):
        error = _capture_failure(
            lambda: acquire_direct_filesystem_snapshot(
                DirectFilesystemInputs(bundle, trust_store_path=trust),
                limits=limits,
            )
        )

    assert error.operational_code is OperationalCode.RESOURCE_LIMIT_EXCEEDED
    assert error.input_ref is InputRef.BUNDLE_DIRECTORY
    assert events[:3] == [
        ("INITIAL_OBSERVATION", InputRole.TRUST_STORE),
        ("BYTE_ACQUISITION", InputRole.TRUST_STORE),
        ("FINAL_OBSERVATION", InputRole.TRUST_STORE),
    ]
    assert events[3:] == [
        ("INITIAL_OBSERVATION", role) for role in BUNDLE_ROLE_ORDER
    ]


def test_malformed_stable_bundle_and_trust_bytes_snapshot_successfully(
    tmp_path: Path,
) -> None:
    malformed_bundle = b'{"never": parsed'
    malformed_trust = b"not-json\x00\xff"
    bundle = _bundle(tmp_path, canonical=malformed_bundle, manifest=b"[")
    trust = tmp_path / "trust.json"
    trust.write_bytes(malformed_trust)

    frozen = acquire_direct_filesystem_snapshot(
        DirectFilesystemInputs(bundle, trust_store_path=trust)
    )

    assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == malformed_bundle
    assert frozen.bytes_for(InputRole.TRUST_STORE) == malformed_trust


def test_missing_supplied_trust_is_operational_not_trust_store_invalid(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}", manifest=b"{}")
    error = _capture_failure(
        lambda: acquire_direct_filesystem_snapshot(
            DirectFilesystemInputs(
                bundle,
                trust_store_path=tmp_path / "missing-trust.json",
            )
        )
    )

    assert error.operational_code is OperationalCode.INPUT_IO_ERROR
    assert error.phase is OperationalPhase.TRUST_INPUT
    assert error.input_ref is InputRef.TRUST_STORE
    assert not hasattr(error, "reason")
    assert error.operational_code.value != "TRUST_STORE_INVALID"


def test_no_supplied_trust_performs_no_trust_filesystem_operation(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}")
    observed_names: list[str] = []
    original_stat = snapshot_runtime._os_stat

    def record_stat(
        path: str,
        *,
        dir_fd: int,
        follow_symlinks: bool,
    ):
        observed_names.append(path)
        return original_stat(
            path,
            dir_fd=dir_fd,
            follow_symlinks=follow_symlinks,
        )

    with mock.patch.object(snapshot_runtime, "_os_stat", record_stat):
        frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))

    assert frozen.input_for(InputRole.TRUST_STORE).presence is StablePresence.ABSENT
    assert set(observed_names) <= {
        *{part for part in os.fspath(bundle).split(os.path.sep) if part},
        AI_CANONICAL_FILENAME,
        AI_MANIFEST_FILENAME,
        AI_VERIFICATION_KEYS_FILENAME,
    }


def test_snapshot_and_nested_state_are_immutable() -> None:
    frozen = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(b"canonical", None, None)
    )

    with pytest.raises(FrozenInstanceError):
        frozen.input_mode = InputMode.DIRECT_FILESYSTEM  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        frozen.inputs[1].data = b"changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        frozen.inputs[1] = frozen.inputs[1]  # type: ignore[index]


def test_retrieving_captured_bytes_never_rereads_the_filesystem(tmp_path: Path) -> None:
    source = b'{"x":1}'
    bundle = _bundle(tmp_path, canonical=source)
    frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))

    with mock.patch.object(
        snapshot_runtime,
        "_os_read",
        side_effect=AssertionError("semantic access must use frozen bytes"),
    ):
        assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == source


def test_replacement_after_freeze_does_not_change_snapshot(tmp_path: Path) -> None:
    original = b'{"x":1}'
    bundle = _bundle(tmp_path, manifest=original)
    frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    (bundle / AI_MANIFEST_FILENAME).write_bytes(b'{"x":2}')

    assert frozen.bytes_for(InputRole.AI_MANIFEST_JSON) == original
    assert FROZEN_CASES["snapshot.post_freeze_replacement.ignored"]["expected"][
        "semantic_phase_rereads"
    ] == 0


def test_unknown_files_are_not_enumerated_or_acquired(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, canonical=b"{}")
    os.mkfifo(bundle / "unknown-fifo")

    frozen = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))

    assert frozen.bytes_for(InputRole.AI_CANONICAL_JSON) == b"{}"
    assert len(frozen.inputs) == 4


def test_direct_and_immutable_modes_have_equivalent_role_maps(tmp_path: Path) -> None:
    source = b'{"x":1}'
    bundle = _bundle(tmp_path, canonical=source)
    direct = acquire_direct_filesystem_snapshot(DirectFilesystemInputs(bundle))
    immutable = acquire_immutable_bytes_snapshot(
        ImmutableBytesInputs(source, None, None)
    )

    assert direct.input_mode is InputMode.DIRECT_FILESYSTEM
    assert immutable.input_mode is InputMode.IMMUTABLE_BYTES
    assert direct.inputs == immutable.inputs
    assert FROZEN_CASES["snapshot.immutable_bytes.equivalence"]["expected"][
        "decision"
    ] == "SNAPSHOT_MAP_EQUAL"
