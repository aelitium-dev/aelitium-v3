"""Immutable verifier-input acquisition for the operational contract.

This module establishes bytes and stable absence only.  It deliberately does
not parse JSON or construct semantic verification results.
"""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from enum import Enum
from typing import Callable, ClassVar, Final, Mapping, TypeAlias

from .ai_contract import (
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_FILENAME,
    AI_VERIFICATION_KEYS_FILENAME,
)


class InputMode(str, Enum):
    """Closed verifier input-mode vocabulary."""

    DIRECT_FILESYSTEM = "DIRECT_FILESYSTEM"
    IMMUTABLE_BYTES = "IMMUTABLE_BYTES"


class InputRole(str, Enum):
    """Roles whose presence and bytes are frozen in an operation snapshot."""

    AI_CANONICAL_JSON = "AI_CANONICAL_JSON"
    AI_MANIFEST_JSON = "AI_MANIFEST_JSON"
    VERIFICATION_KEYS_JSON = "VERIFICATION_KEYS_JSON"
    TRUST_STORE = "TRUST_STORE"


class InputRef(str, Enum):
    """Public ``input_ref`` vocabulary from the outer result contract."""

    BUNDLE_DIRECTORY = "BUNDLE_DIRECTORY"
    AI_CANONICAL_JSON = "AI_CANONICAL_JSON"
    AI_MANIFEST_JSON = "AI_MANIFEST_JSON"
    VERIFICATION_KEYS_JSON = "VERIFICATION_KEYS_JSON"
    TRUST_STORE = "TRUST_STORE"
    EXPLICIT_INPUT = "EXPLICIT_INPUT"


class StablePresence(str, Enum):
    """Whether one role was stably present or absent during acquisition."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class OperationalCode(str, Enum):
    """Operational codes that can arise at the O1 acquisition boundary."""

    CAPABILITY_PROFILE_UNAVAILABLE = "CAPABILITY_PROFILE_UNAVAILABLE"
    INPUT_OUTSIDE_DECLARED_CAPABILITY = "INPUT_OUTSIDE_DECLARED_CAPABILITY"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    INPUT_IO_ERROR = "INPUT_IO_ERROR"
    INPUT_NOT_REGULAR_FILE = "INPUT_NOT_REGULAR_FILE"
    INPUT_CHANGED_DURING_SNAPSHOT = "INPUT_CHANGED_DURING_SNAPSHOT"
    INTERNAL_OPERATION_ERROR = "INTERNAL_OPERATION_ERROR"
    OUTPUT_IO_ERROR = "OUTPUT_IO_ERROR"


class OperationalPhase(str, Enum):
    """Operational phases relevant to snapshot acquisition and traversal."""

    CAPABILITY_SELECTION = "CAPABILITY_SELECTION"
    TRUST_INPUT = "TRUST_INPUT"
    BUNDLE_SNAPSHOT = "BUNDLE_SNAPSHOT"
    DISPATCH = "DISPATCH"
    CANONICAL_PARSE = "CANONICAL_PARSE"
    MANIFEST_PARSE = "MANIFEST_PARSE"
    SIGNATURE_MATERIAL = "SIGNATURE_MATERIAL"
    SEMANTIC_EVALUATION = "SEMANTIC_EVALUATION"
    OUTPUT = "OUTPUT"


class LimitName(str, Enum):
    """Implemented limit names from the outer result contract."""

    FILE_BYTES = "FILE_BYTES"
    TOTAL_SNAPSHOT_BYTES = "TOTAL_SNAPSHOT_BYTES"
    STRUCTURAL_DEPTH = "STRUCTURAL_DEPTH"
    VALUE_OCCURRENCES = "VALUE_OCCURRENCES"
    INTEGER_DECIMAL_DIGITS = "INTEGER_DECIMAL_DIGITS"
    TIMESTAMP_DIGIT_PROFILE = "TIMESTAMP_DIGIT_PROFILE"


class LimitUnit(str, Enum):
    """Units used by implemented operational limit facts."""

    BYTES = "BYTES"
    LEVELS = "LEVELS"
    OCCURRENCES = "OCCURRENCES"
    DIGITS = "DIGITS"
    PROFILE = "PROFILE"


BUNDLE_ROLE_ORDER: Final[tuple[InputRole, ...]] = (
    InputRole.AI_CANONICAL_JSON,
    InputRole.AI_MANIFEST_JSON,
    InputRole.VERIFICATION_KEYS_JSON,
)
SNAPSHOT_ROLE_ORDER: Final[tuple[InputRole, ...]] = (
    InputRole.TRUST_STORE,
    *BUNDLE_ROLE_ORDER,
)

_ROLE_FILENAMES: Final[Mapping[InputRole, str]] = {
    InputRole.AI_CANONICAL_JSON: AI_CANONICAL_FILENAME,
    InputRole.AI_MANIFEST_JSON: AI_MANIFEST_FILENAME,
    InputRole.VERIFICATION_KEYS_JSON: AI_VERIFICATION_KEYS_FILENAME,
}
_ROLE_INPUT_REFS: Final[Mapping[InputRole, InputRef]] = {
    InputRole.AI_CANONICAL_JSON: InputRef.AI_CANONICAL_JSON,
    InputRole.AI_MANIFEST_JSON: InputRef.AI_MANIFEST_JSON,
    InputRole.VERIFICATION_KEYS_JSON: InputRef.VERIFICATION_KEYS_JSON,
    InputRole.TRUST_STORE: InputRef.TRUST_STORE,
}

AELITIUM_MIN_MAX_FILE_BYTES: Final = 65_536
AELITIUM_MIN_MAX_TOTAL_SNAPSHOT_BYTES: Final = 262_144
AELITIUM_MIN_MAX_STRUCTURAL_DEPTH: Final = 1_024
AELITIUM_MIN_MAX_VALUE_OCCURRENCES: Final = 65_536
_MAX_PORTABLE_INTEGER: Final = 9_007_199_254_740_991


@dataclass(frozen=True, slots=True)
class OperationalLimits:
    """Effective limits frozen for one verifier operation.

    O1 enforces the two byte limits and O2B1 enforces both traversal limits
    from this same operation-wide object.
    """

    max_file_bytes: int = AELITIUM_MIN_MAX_FILE_BYTES
    max_total_snapshot_bytes: int = AELITIUM_MIN_MAX_TOTAL_SNAPSHOT_BYTES
    max_structural_depth: int = AELITIUM_MIN_MAX_STRUCTURAL_DEPTH
    max_value_occurrences: int = AELITIUM_MIN_MAX_VALUE_OCCURRENCES

    def __post_init__(self) -> None:
        for name in (
            "max_file_bytes",
            "max_total_snapshot_bytes",
            "max_structural_depth",
            "max_value_occurrences",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= _MAX_PORTABLE_INTEGER
            ):
                raise ValueError(
                    f"{name} must be an integer from 0 through "
                    f"{_MAX_PORTABLE_INTEGER}"
                )


DEFAULT_OPERATIONAL_LIMITS: Final = OperationalLimits()


@dataclass(frozen=True, slots=True)
class LimitFact:
    """Measured operational-limit fact for later O3 serialization."""

    name: LimitName
    unit: LimitUnit
    maximum: int | str | None
    observed_at_least: int | str | None


@dataclass(frozen=True, slots=True)
class OperationalInputFailure(RuntimeError):
    """Typed operational failure; never an AELITIUM semantic result."""

    operational_code: OperationalCode
    phase: OperationalPhase
    input_ref: InputRef | None
    limit: LimitFact | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.operational_code.value)


PathInput: TypeAlias = str | os.PathLike[str]


@dataclass(frozen=True, slots=True)
class DirectFilesystemInputs:
    """Paths for a direct-filesystem acquisition request."""

    bundle_root: PathInput
    trust_store_path: PathInput | None = None
    input_mode: ClassVar[InputMode] = InputMode.DIRECT_FILESYSTEM


@dataclass(frozen=True, slots=True)
class ImmutableBytesInputs:
    """One already-frozen, complete role map supplied by the caller.

    ``None`` is an explicit stable-absence declaration.  Trust is a separate
    field rather than a bundle-map member.
    """

    ai_canonical_json: bytes | None
    ai_manifest_json: bytes | None
    verification_keys_json: bytes | None
    trust_store: bytes | None = None
    input_mode: ClassVar[InputMode] = InputMode.IMMUTABLE_BYTES

    def __post_init__(self) -> None:
        for name in (
            "ai_canonical_json",
            "ai_manifest_json",
            "verification_keys_json",
            "trust_store",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bytes):
                raise TypeError(f"{name} must be bytes or None")


SnapshotRequest: TypeAlias = DirectFilesystemInputs | ImmutableBytesInputs


@dataclass(frozen=True, slots=True)
class SnapshotInput:
    """Frozen bytes or stable absence for one known input role."""

    role: InputRole
    presence: StablePresence
    data: bytes | None

    def __post_init__(self) -> None:
        if self.presence is StablePresence.PRESENT:
            if not isinstance(self.data, bytes):
                raise TypeError("present snapshot input must contain bytes")
        elif self.data is not None:
            raise ValueError("absent snapshot input cannot contain bytes")


@dataclass(frozen=True, slots=True)
class VerifierSnapshot:
    """Immutable role-to-bytes and role-to-stable-absence operation snapshot."""

    input_mode: InputMode
    inputs: tuple[SnapshotInput, ...]
    effective_limits: OperationalLimits

    def __post_init__(self) -> None:
        if tuple(item.role for item in self.inputs) != SNAPSHOT_ROLE_ORDER:
            raise ValueError("snapshot inputs must use the deterministic role order")

    def input_for(self, role: InputRole | str) -> SnapshotInput:
        """Return the frozen entry for an exact public role."""

        exact_role = role if isinstance(role, InputRole) else InputRole(role)
        for item in self.inputs:
            if item.role is exact_role:
                return item
        raise AssertionError("validated snapshot is missing a role")

    def bytes_for(self, role: InputRole | str) -> bytes | None:
        """Return captured bytes, or ``None`` for stable absence."""

        return self.input_for(role).data

    @property
    def total_bytes(self) -> int:
        """Total byte length of all present known roles."""

        return sum(len(item.data) for item in self.inputs if item.data is not None)


@dataclass(frozen=True, slots=True)
class _HeldInput:
    role: InputRole
    parent_fd: int
    name: str
    fd: int
    initial: os.stat_result


@dataclass(frozen=True, slots=True)
class _AbsentInput:
    role: InputRole
    parent_fd: int
    name: str


_ObservedInput: TypeAlias = _HeldInput | _AbsentInput
_SnapshotHook: TypeAlias = Callable[[str, InputRole], None]


def _noop_snapshot_hook(point: str, role: InputRole) -> None:
    del point, role


# Tests replace this no-op at deterministic synchronization points.  It is not
# part of the verifier's semantic or operational API.
_snapshot_hook: _SnapshotHook = _noop_snapshot_hook

_O_CLOEXEC: Final = getattr(os, "O_CLOEXEC", 0)
_O_NONBLOCK: Final = getattr(os, "O_NONBLOCK", 0)
_READ_CHUNK_BYTES: Final = 64 * 1024
_RESOURCE_ERRNOS: Final = frozenset(
    value
    for value in (
        getattr(errno, "ENOMEM", None),
        getattr(errno, "ENOBUFS", None),
        getattr(errno, "EMFILE", None),
        getattr(errno, "ENFILE", None),
    )
    if value is not None
)


def _os_open(path: str, flags: int, *, dir_fd: int | None = None) -> int:
    if dir_fd is None:
        return os.open(path, flags)
    return os.open(path, flags, dir_fd=dir_fd)


def _os_stat(
    path: str,
    *,
    dir_fd: int,
    follow_symlinks: bool,
) -> os.stat_result:
    return os.stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)


def _os_fstat(fd: int) -> os.stat_result:
    return os.fstat(fd)


def _os_lseek(fd: int, offset: int, whence: int) -> int:
    return os.lseek(fd, offset, whence)


def _os_read(fd: int, length: int) -> bytes:
    return os.read(fd, length)


def _close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        # Closing a held input does not change the already-established outcome.
        pass


def _failure(
    code: OperationalCode,
    phase: OperationalPhase,
    input_ref: InputRef | None,
    *,
    limit: LimitFact | None = None,
) -> OperationalInputFailure:
    return OperationalInputFailure(code, phase, input_ref, limit, None)


def _resource_or_io_failure(
    error: OSError,
    phase: OperationalPhase,
    input_ref: InputRef,
) -> OperationalInputFailure:
    code = (
        OperationalCode.RESOURCE_EXHAUSTED
        if error.errno in _RESOURCE_ERRNOS
        else OperationalCode.INPUT_IO_ERROR
    )
    return _failure(code, phase, input_ref)


def _resource_failure(
    phase: OperationalPhase,
    input_ref: InputRef,
) -> OperationalInputFailure:
    return _failure(OperationalCode.RESOURCE_EXHAUSTED, phase, input_ref)


def _ensure_direct_filesystem_supported() -> None:
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW")
    flags_available = all(hasattr(os, name) for name in required_flags)
    calls_available = (
        os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )
    if not flags_available or not calls_available:
        raise _failure(
            OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE,
            OperationalPhase.CAPABILITY_SELECTION,
            None,
        )


def _path_string(path: PathInput) -> str:
    value = os.fspath(path)
    if not isinstance(value, str):
        raise TypeError("verifier input paths must be text paths")
    return value


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _change_metadata(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
        value.st_mode,
    )


def _same_source(left: os.stat_result, right: os.stat_result) -> bool:
    return _identity(left) == _identity(right) and _change_metadata(
        left
    ) == _change_metadata(right)


def _open_directory_no_follow(
    path: PathInput,
    *,
    phase: OperationalPhase,
    input_ref: InputRef,
) -> int:
    raw_path = _path_string(path)
    if raw_path == "":
        raise _failure(OperationalCode.INPUT_IO_ERROR, phase, input_ref)

    anchor = os.path.sep if os.path.isabs(raw_path) else os.curdir
    components = tuple(
        part
        for part in raw_path.split(os.path.sep)
        if part not in ("", os.curdir)
    )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | _O_CLOEXEC

    try:
        current_fd = _os_open(anchor, directory_flags)
    except OSError as error:
        raise _resource_or_io_failure(error, phase, input_ref) from error

    try:
        for component in components:
            try:
                entry_state = _os_stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise _resource_or_io_failure(error, phase, input_ref) from error

            if stat.S_ISLNK(entry_state.st_mode) or not stat.S_ISDIR(
                entry_state.st_mode
            ):
                raise _failure(
                    OperationalCode.INPUT_NOT_REGULAR_FILE,
                    phase,
                    input_ref,
                )

            try:
                next_fd = _os_open(
                    component,
                    directory_flags,
                    dir_fd=current_fd,
                )
            except OSError as error:
                if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                    raise _failure(
                        OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
                        phase,
                        input_ref,
                    ) from error
                raise _resource_or_io_failure(error, phase, input_ref) from error

            try:
                held_state = _os_fstat(next_fd)
            except OSError as error:
                _close_fd(next_fd)
                raise _resource_or_io_failure(error, phase, input_ref) from error

            if not stat.S_ISDIR(held_state.st_mode) or _identity(
                entry_state
            ) != _identity(held_state):
                _close_fd(next_fd)
                raise _failure(
                    OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
                    phase,
                    input_ref,
                )

            _close_fd(current_fd)
            current_fd = next_fd

        return current_fd
    except BaseException:
        _close_fd(current_fd)
        raise


def _split_parent(path: PathInput) -> tuple[str, str]:
    raw_path = _path_string(path)
    if raw_path == "":
        return os.curdir, ""
    trimmed = raw_path.rstrip(os.path.sep)
    if trimmed == "":
        return os.path.sep, os.curdir
    parent, name = os.path.split(trimmed)
    return parent or os.curdir, name


def _observe_input(
    parent_fd: int,
    name: str,
    role: InputRole,
    *,
    phase: OperationalPhase,
    allow_absent: bool,
    limits: OperationalLimits,
) -> _ObservedInput:
    input_ref = _ROLE_INPUT_REFS[role]
    try:
        entry_state = _os_stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError as error:
        if allow_absent:
            return _AbsentInput(role, parent_fd, name)
        raise _failure(OperationalCode.INPUT_IO_ERROR, phase, input_ref) from error
    except OSError as error:
        raise _resource_or_io_failure(error, phase, input_ref) from error

    if stat.S_ISLNK(entry_state.st_mode) or not stat.S_ISREG(entry_state.st_mode):
        raise _failure(
            OperationalCode.INPUT_NOT_REGULAR_FILE,
            phase,
            input_ref,
        )

    file_flags = os.O_RDONLY | os.O_NOFOLLOW | _O_CLOEXEC | _O_NONBLOCK
    try:
        fd = _os_open(name, file_flags, dir_fd=parent_fd)
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            raise _failure(
                OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
                phase,
                input_ref,
            ) from error
        raise _resource_or_io_failure(error, phase, input_ref) from error

    try:
        held_state = _os_fstat(fd)
    except OSError as error:
        _close_fd(fd)
        raise _resource_or_io_failure(error, phase, input_ref) from error

    if not stat.S_ISREG(held_state.st_mode) or not _same_source(
        entry_state, held_state
    ):
        _close_fd(fd)
        raise _failure(
            OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
            phase,
            input_ref,
        )

    if held_state.st_size > limits.max_file_bytes:
        _close_fd(fd)
        raise _failure(
            OperationalCode.RESOURCE_LIMIT_EXCEEDED,
            phase,
            input_ref,
            limit=LimitFact(
                LimitName.FILE_BYTES,
                LimitUnit.BYTES,
                limits.max_file_bytes,
                held_state.st_size,
            ),
        )

    return _HeldInput(role, parent_fd, name, fd, held_state)


def _read_held_input(
    observed: _HeldInput,
    *,
    phase: OperationalPhase,
) -> bytes:
    input_ref = _ROLE_INPUT_REFS[observed.role]
    expected_size = observed.initial.st_size
    try:
        _os_lseek(observed.fd, 0, os.SEEK_SET)
    except OSError as error:
        raise _resource_or_io_failure(error, phase, input_ref) from error

    try:
        captured = bytearray()
        while len(captured) < expected_size:
            request_size = min(
                _READ_CHUNK_BYTES,
                expected_size - len(captured),
            )
            try:
                chunk = _os_read(observed.fd, request_size)
            except OSError as error:
                raise _resource_or_io_failure(error, phase, input_ref) from error
            if not chunk:
                raise _failure(
                    OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
                    phase,
                    input_ref,
                )
            captured.extend(chunk)

        try:
            extra = _os_read(observed.fd, 1)
        except OSError as error:
            raise _resource_or_io_failure(error, phase, input_ref) from error
        if extra:
            raise _failure(
                OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
                phase,
                input_ref,
            )
        return bytes(captured)
    except (MemoryError, RecursionError) as error:
        raise _resource_failure(phase, input_ref) from error
    except OperationalInputFailure:
        raise
    except Exception as error:
        raise _failure(
            OperationalCode.INTERNAL_OPERATION_ERROR,
            phase,
            input_ref,
        ) from error


def _check_final_observation(
    observed: _ObservedInput,
    *,
    phase: OperationalPhase,
) -> None:
    input_ref = _ROLE_INPUT_REFS[observed.role]
    if isinstance(observed, _AbsentInput):
        try:
            _os_stat(
                observed.name,
                dir_fd=observed.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        except OSError as error:
            raise _resource_or_io_failure(error, phase, input_ref) from error
        raise _failure(
            OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
            phase,
            input_ref,
        )

    try:
        held_state = _os_fstat(observed.fd)
    except OSError as error:
        raise _resource_or_io_failure(error, phase, input_ref) from error
    if not stat.S_ISREG(held_state.st_mode) or not _same_source(
        observed.initial, held_state
    ):
        raise _failure(
            OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
            phase,
            input_ref,
        )

    try:
        entry_state = _os_stat(
            observed.name,
            dir_fd=observed.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError as error:
        raise _failure(
            OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
            phase,
            input_ref,
        ) from error
    except OSError as error:
        raise _resource_or_io_failure(error, phase, input_ref) from error

    if not _same_source(observed.initial, entry_state):
        raise _failure(
            OperationalCode.INPUT_CHANGED_DURING_SNAPSHOT,
            phase,
            input_ref,
        )


def _present(role: InputRole, data: bytes) -> SnapshotInput:
    return SnapshotInput(role, StablePresence.PRESENT, data)


def _absent(role: InputRole) -> SnapshotInput:
    return SnapshotInput(role, StablePresence.ABSENT, None)


def _snapshot(
    input_mode: InputMode,
    entries: tuple[SnapshotInput, ...],
    limits: OperationalLimits,
) -> VerifierSnapshot:
    try:
        return VerifierSnapshot(input_mode, entries, limits)
    except MemoryError as error:
        raise _resource_failure(
            OperationalPhase.BUNDLE_SNAPSHOT,
            InputRef.BUNDLE_DIRECTORY,
        ) from error


def _acquire_trust_path(
    trust_store_path: PathInput | None,
    limits: OperationalLimits,
) -> SnapshotInput:
    if trust_store_path is None:
        return _absent(InputRole.TRUST_STORE)

    parent_path, name = _split_parent(trust_store_path)
    if name == "":
        raise _failure(
            OperationalCode.INPUT_IO_ERROR,
            OperationalPhase.TRUST_INPUT,
            InputRef.TRUST_STORE,
        )
    parent_fd = _open_directory_no_follow(
        parent_path,
        phase=OperationalPhase.TRUST_INPUT,
        input_ref=InputRef.TRUST_STORE,
    )
    observed: _ObservedInput | None = None
    try:
        observed = _observe_input(
            parent_fd,
            name,
            InputRole.TRUST_STORE,
            phase=OperationalPhase.TRUST_INPUT,
            allow_absent=False,
            limits=limits,
        )
        if not isinstance(observed, _HeldInput):
            raise AssertionError("supplied trust input cannot be absent")
        _snapshot_hook("INITIAL_OBSERVATION", InputRole.TRUST_STORE)
        data = _read_held_input(observed, phase=OperationalPhase.TRUST_INPUT)
        _snapshot_hook("BYTE_ACQUISITION", InputRole.TRUST_STORE)
        _check_final_observation(observed, phase=OperationalPhase.TRUST_INPUT)
        _snapshot_hook("FINAL_OBSERVATION", InputRole.TRUST_STORE)
        return _present(InputRole.TRUST_STORE, data)
    finally:
        if isinstance(observed, _HeldInput):
            _close_fd(observed.fd)
        _close_fd(parent_fd)


def _acquire_bundle_roles(
    bundle_fd: int,
    trust_entry: SnapshotInput,
    limits: OperationalLimits,
) -> tuple[SnapshotInput, ...]:
    observed_inputs: list[_ObservedInput] = []
    captured: dict[InputRole, bytes] = {}
    try:
        for role in BUNDLE_ROLE_ORDER:
            observed = _observe_input(
                bundle_fd,
                _ROLE_FILENAMES[role],
                role,
                phase=OperationalPhase.BUNDLE_SNAPSHOT,
                allow_absent=True,
                limits=limits,
            )
            observed_inputs.append(observed)
            _snapshot_hook("INITIAL_OBSERVATION", role)

        total_size = 0 if trust_entry.data is None else len(trust_entry.data)
        total_size += sum(
            observed.initial.st_size
            for observed in observed_inputs
            if isinstance(observed, _HeldInput)
        )
        if total_size > limits.max_total_snapshot_bytes:
            raise _failure(
                OperationalCode.RESOURCE_LIMIT_EXCEEDED,
                OperationalPhase.BUNDLE_SNAPSHOT,
                InputRef.BUNDLE_DIRECTORY,
                limit=LimitFact(
                    LimitName.TOTAL_SNAPSHOT_BYTES,
                    LimitUnit.BYTES,
                    limits.max_total_snapshot_bytes,
                    total_size,
                ),
            )

        for observed in observed_inputs:
            if isinstance(observed, _HeldInput):
                captured[observed.role] = _read_held_input(
                    observed,
                    phase=OperationalPhase.BUNDLE_SNAPSHOT,
                )
                _snapshot_hook("BYTE_ACQUISITION", observed.role)

        for observed in observed_inputs:
            _check_final_observation(
                observed,
                phase=OperationalPhase.BUNDLE_SNAPSHOT,
            )
            _snapshot_hook("FINAL_OBSERVATION", observed.role)

        return tuple(
            _present(role, captured[role])
            if role in captured
            else _absent(role)
            for role in BUNDLE_ROLE_ORDER
        )
    except MemoryError as error:
        raise _resource_failure(
            OperationalPhase.BUNDLE_SNAPSHOT,
            InputRef.BUNDLE_DIRECTORY,
        ) from error
    finally:
        for observed in observed_inputs:
            if isinstance(observed, _HeldInput):
                _close_fd(observed.fd)


def acquire_direct_filesystem_snapshot(
    inputs: DirectFilesystemInputs,
    *,
    limits: OperationalLimits = DEFAULT_OPERATIONAL_LIMITS,
) -> VerifierSnapshot:
    """Acquire one no-follow, regular-file, immutable filesystem snapshot."""

    if not isinstance(inputs, DirectFilesystemInputs):
        raise TypeError("inputs must be DirectFilesystemInputs")
    if not isinstance(limits, OperationalLimits):
        raise TypeError("limits must be OperationalLimits")
    _ensure_direct_filesystem_supported()

    bundle_fd = _open_directory_no_follow(
        inputs.bundle_root,
        phase=OperationalPhase.BUNDLE_SNAPSHOT,
        input_ref=InputRef.BUNDLE_DIRECTORY,
    )
    try:
        trust_entry = _acquire_trust_path(inputs.trust_store_path, limits)
        bundle_entries = _acquire_bundle_roles(bundle_fd, trust_entry, limits)
        return _snapshot(
            InputMode.DIRECT_FILESYSTEM,
            (trust_entry, *bundle_entries),
            limits,
        )
    finally:
        _close_fd(bundle_fd)


def _immutable_entry(role: InputRole, data: bytes | None) -> SnapshotInput:
    return _absent(role) if data is None else _present(role, data)


def acquire_immutable_bytes_snapshot(
    inputs: ImmutableBytesInputs,
    *,
    limits: OperationalLimits = DEFAULT_OPERATIONAL_LIMITS,
) -> VerifierSnapshot:
    """Freeze caller-provided bytes without invoking the filesystem."""

    if not isinstance(inputs, ImmutableBytesInputs):
        raise TypeError("inputs must be ImmutableBytesInputs")
    if not isinstance(limits, OperationalLimits):
        raise TypeError("limits must be OperationalLimits")

    ordered_values = (
        (InputRole.TRUST_STORE, inputs.trust_store),
        (InputRole.AI_CANONICAL_JSON, inputs.ai_canonical_json),
        (InputRole.AI_MANIFEST_JSON, inputs.ai_manifest_json),
        (InputRole.VERIFICATION_KEYS_JSON, inputs.verification_keys_json),
    )
    for role, data in ordered_values:
        if data is not None and len(data) > limits.max_file_bytes:
            phase = (
                OperationalPhase.TRUST_INPUT
                if role is InputRole.TRUST_STORE
                else OperationalPhase.BUNDLE_SNAPSHOT
            )
            raise _failure(
                OperationalCode.RESOURCE_LIMIT_EXCEEDED,
                phase,
                _ROLE_INPUT_REFS[role],
                limit=LimitFact(
                    LimitName.FILE_BYTES,
                    LimitUnit.BYTES,
                    limits.max_file_bytes,
                    len(data),
                ),
            )

    total_size = sum(len(data) for _, data in ordered_values if data is not None)
    if total_size > limits.max_total_snapshot_bytes:
        raise _failure(
            OperationalCode.RESOURCE_LIMIT_EXCEEDED,
            OperationalPhase.BUNDLE_SNAPSHOT,
            InputRef.BUNDLE_DIRECTORY,
            limit=LimitFact(
                LimitName.TOTAL_SNAPSHOT_BYTES,
                LimitUnit.BYTES,
                limits.max_total_snapshot_bytes,
                total_size,
            ),
        )

    entries = tuple(_immutable_entry(role, data) for role, data in ordered_values)
    return _snapshot(InputMode.IMMUTABLE_BYTES, entries, limits)


def acquire_verifier_snapshot(
    inputs: SnapshotRequest,
    *,
    limits: OperationalLimits = DEFAULT_OPERATIONAL_LIMITS,
) -> VerifierSnapshot:
    """Acquire either supported input mode without changing its identity."""

    if isinstance(inputs, DirectFilesystemInputs):
        return acquire_direct_filesystem_snapshot(inputs, limits=limits)
    if isinstance(inputs, ImmutableBytesInputs):
        return acquire_immutable_bytes_snapshot(inputs, limits=limits)
    raise TypeError("unsupported verifier snapshot request")


__all__ = [
    "AELITIUM_MIN_MAX_FILE_BYTES",
    "AELITIUM_MIN_MAX_STRUCTURAL_DEPTH",
    "AELITIUM_MIN_MAX_TOTAL_SNAPSHOT_BYTES",
    "AELITIUM_MIN_MAX_VALUE_OCCURRENCES",
    "BUNDLE_ROLE_ORDER",
    "DEFAULT_OPERATIONAL_LIMITS",
    "DirectFilesystemInputs",
    "ImmutableBytesInputs",
    "InputMode",
    "InputRef",
    "InputRole",
    "LimitFact",
    "LimitName",
    "LimitUnit",
    "OperationalCode",
    "OperationalInputFailure",
    "OperationalLimits",
    "OperationalPhase",
    "SNAPSHOT_ROLE_ORDER",
    "SnapshotInput",
    "StablePresence",
    "VerifierSnapshot",
    "acquire_direct_filesystem_snapshot",
    "acquire_immutable_bytes_snapshot",
    "acquire_verifier_snapshot",
]
