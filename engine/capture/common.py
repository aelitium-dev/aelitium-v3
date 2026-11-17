"""Provider-neutral helpers shared by capture adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class CaptureMetadataCollisionError(ValueError):
    """Caller metadata attempted to overwrite adapter-owned fields."""

    reason = "CAPTURE_METADATA_RESERVED_KEY_COLLISION"

    def __init__(self, offending_keys: Iterable[str]) -> None:
        self.offending_keys = tuple(sorted(offending_keys))
        super().__init__(f"{self.reason}: {','.join(self.offending_keys)}")


def merge_capture_metadata(
    base_metadata: Mapping[str, Any],
    caller_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a merged copy, rejecting caller collisions with base keys."""

    if caller_metadata is None:
        return dict(base_metadata)

    collisions = set(base_metadata).intersection(caller_metadata)
    if collisions:
        raise CaptureMetadataCollisionError(collisions)

    merged = dict(base_metadata)
    merged.update(caller_metadata)
    return merged
