#!/usr/bin/env python3
"""Validate the frozen legacy-v1 compatibility and operational-policy corpus.

This runner validates committed recipes, hashes, operational outputs, schemas,
coverage, and invariants.  It intentionally does not invoke the current Python
verifier, which does not implement this unreleased operational transport.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
import rfc8785


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
CORPUS_DIR = ROOT / "legacy_v1_operational_policy"
CASES_PATH = CORPUS_DIR / "cases.json"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
TOOL_SCHEMA_PATH = REPOSITORY_ROOT / "engine" / "schemas" / "verifier_tool_result_v1.json"
VERIFY_SCHEMA_PATH = REPOSITORY_ROOT / "engine" / "schemas" / "verification_result_v1.json"

EXPECTED_EXISTING_COUNTS = {
    "canonicalization_v1_cases": 30,
    "canonicalization_v2_cases": 114,
    "result_contract_cases": 44,
}
EXPECTED_OPERATIONAL_CODES = {
    "CAPABILITY_PROFILE_UNAVAILABLE",
    "INPUT_CHANGED_DURING_SNAPSHOT",
    "INPUT_IO_ERROR",
    "INPUT_NOT_REGULAR_FILE",
    "INPUT_OUTSIDE_DECLARED_CAPABILITY",
    "INTERNAL_OPERATION_ERROR",
    "OUTPUT_IO_ERROR",
    "RESOURCE_EXHAUSTED",
    "RESOURCE_LIMIT_EXCEEDED",
}
EXPECTED_PHASES = {
    "BUNDLE_SNAPSHOT",
    "CANONICAL_PARSE",
    "CAPABILITY_SELECTION",
    "DISPATCH",
    "MANIFEST_PARSE",
    "OUTPUT",
    "SEMANTIC_EVALUATION",
    "SIGNATURE_MATERIAL",
    "TRUST_INPUT",
}
EXPECTED_CASE_OPERATIONS = {
    "ACQUIRE_SNAPSHOT",
    "APPLY_LEGACY_RULE",
    "CLASSIFY_INTEGER_SOURCE",
    "CLASSIFY_PROGRAMMATIC_INTEGER",
    "CLASSIFY_STABLE_ABSENCE",
    "COMPARE_INPUT_MODES",
    "DECODE_LEGACY_BASE64",
    "DISPATCH_MANIFEST",
    "INJECT_OPERATIONAL_FAILURE",
    "INJECT_RESOURCE_FAILURE",
    "MEASURE_SNAPSHOT_LIMIT",
    "MEASURE_SOURCE_LIMIT",
    "MEASURE_TRAVERSAL_LIMIT",
    "SELECT_CAPABILITY",
    "VALIDATE_MANIFEST_TIMESTAMP",
}
EXPECTED_CHECKPOINT_DECISIONS = {
    "EVALUATE_SEMANTICALLY",
    "LEGACY_ACCEPT",
    "LEGACY_ACCEPT_OPAQUE",
    "LEGACY_ACCEPT_OPEN_MEMBER",
    "LEGACY_SYNTAX_REJECT",
    "PROFILE_RELATIVE_SEMANTIC_FAILURE",
    "ROUTE_V2",
    "SEMANTIC_ABSENCE",
    "SNAPSHOT_ACQUIRED",
    "SNAPSHOT_MAP_EQUAL",
    "TIMESTAMP_ACCEPT",
    "TIMESTAMP_REJECT",
    "USE_FROZEN_BYTES",
    "WITHIN_EFFECTIVE_LIMIT",
}
REQUIRED_CASE_IDS = {
    "integer.portable.positive_640",
    "integer.portable.641",
    "integer.portable.4300",
    "integer.portable.4301",
    "integer.portable.10000",
    "integer.named_640.at_limit",
    "integer.named_640.above_limit",
    "integer.named_4300.at_limit",
    "integer.named_4300.above_limit",
    "integer.named_unlimited.10000",
    "integer.named_777.trust_at_limit",
    "integer.named_777.trust_above_limit",
    "integer.occurrence.governed_641",
    "integer.occurrence.ignored_641",
    "integer.occurrence.overwritten_641",
    "integer.dispatch.final_v2_huge_before",
    "integer.dispatch.final_v2_huge_after",
    "integer.dispatch.final_v1_huge",
    "timestamp.ascii.valid",
    "timestamp.portable.non_ascii_nd",
    "timestamp.ucd13.non_ascii_nd",
    "timestamp.ucd13.outside_14_addition",
    "timestamp.ucd14.accept_14_addition",
    "timestamp.ucd14.outside_15_addition",
    "timestamp.ucd15.accept_15_addition",
    "timestamp.final_lf.one",
    "timestamp.final_lf.two",
    "timestamp.final_lf.embedded",
    "timestamp.separator.bad",
    "legacy.duplicate.exact_last_wins",
    "legacy.duplicate.escaped_equivalent_last_wins",
    "legacy.nonfinite.nan",
    "legacy.nonfinite.infinity",
    "legacy.nonfinite.negative_infinity",
    "legacy.surrogate.unmatched_high",
    "legacy.base64.public_key_pad_bits",
    "legacy.base64.signature_pad_bits",
    "legacy.open_member.accepted",
    "legacy.trust.empty_signers",
    "limit.file_bytes.below",
    "limit.file_bytes.at",
    "limit.file_bytes.above",
    "limit.total_snapshot_bytes.below",
    "limit.total_snapshot_bytes.at",
    "limit.total_snapshot_bytes.above",
    "limit.structural_depth.below",
    "limit.structural_depth.at",
    "limit.structural_depth.above",
    "limit.value_occurrences.below",
    "limit.value_occurrences.at",
    "limit.value_occurrences.above",
    "resource.exhausted.dispatch",
    "resource.exhausted.canonical_parse",
    "resource.exhausted.manifest_parse",
    "resource.exhausted.signature_material",
    "snapshot.regular_file.success",
    "snapshot.reject.symlink",
    "snapshot.reject.directory",
    "snapshot.reject.fifo",
    "snapshot.reject.device",
    "snapshot.reject.socket",
    "snapshot.io.permission",
    "snapshot.io.open_error",
    "snapshot.io.read_error",
    "snapshot.changed.disappearance",
    "snapshot.changed.replacement",
    "snapshot.changed.premature_eof",
    "snapshot.changed.truncation",
    "snapshot.changed.growth",
    "snapshot.changed.in_place_mutation",
    "snapshot.short_reads.accumulated",
    "snapshot.post_freeze_replacement.ignored",
    "snapshot.immutable_bytes.equivalence",
    "snapshot.stable_absence.canonical",
    "snapshot.stable_absence.manifest",
    "snapshot.stable_absence.keyring",
    "snapshot.stable_absence.trust_option",
    "operation.output_io",
    "operation.internal_failure",
    "capability.v1_unsupported.after_dispatch",
}


class CorpusFailure(AssertionError):
    """Raised when committed conformance data are inconsistent."""


LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})*")


def _load(path: Path, *, canonical: bool = True) -> Any:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusFailure(f"cannot load {path.relative_to(REPOSITORY_ROOT)}: {exc}") from exc
    expected = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if canonical and raw != expected:
        raise CorpusFailure(f"{path.relative_to(REPOSITORY_ROOT)} is not canonical indented JSON")
    return value


def _materialize(recipe: dict[str, Any]) -> bytes:
    if not isinstance(recipe, dict) or not isinstance(recipe.get("op"), str):
        raise CorpusFailure("invalid byte recipe object")
    op = recipe["op"]
    try:
        if op == "LITERAL_HEX" and set(recipe) == {"op", "hex"}:
            if not isinstance(recipe["hex"], str) or LOWER_HEX.fullmatch(recipe["hex"]) is None:
                raise CorpusFailure("LITERAL_HEX must use even-length lowercase hexadecimal")
            return bytes.fromhex(recipe["hex"])
        if op == "REPEAT_BYTE" and set(recipe) == {"op", "byte_hex", "count"}:
            if (
                not isinstance(recipe["byte_hex"], str)
                or re.fullmatch(r"[0-9a-f]{2}", recipe["byte_hex"]) is None
            ):
                raise CorpusFailure("REPEAT_BYTE byte must be lowercase hexadecimal")
            value = bytes.fromhex(recipe["byte_hex"])
            if (
                len(value) != 1
                or not isinstance(recipe["count"], int)
                or isinstance(recipe["count"], bool)
                or recipe["count"] < 0
            ):
                raise CorpusFailure("invalid REPEAT_BYTE parameters")
            return value * recipe["count"]
        if op == "CONCAT" and set(recipe) == {"op", "parts"}:
            if not isinstance(recipe["parts"], list):
                raise CorpusFailure("CONCAT parts must be an array")
            return b"".join(_materialize(part) for part in recipe["parts"])
        if op == "JSON_STRING_OF_SIZE" and set(recipe) == {
            "op",
            "byte_length",
            "fill_byte_hex",
        }:
            size = recipe["byte_length"]
            fill_hex = recipe["fill_byte_hex"]
            if not isinstance(fill_hex, str) or re.fullmatch(r"[0-9a-f]{2}", fill_hex) is None:
                raise CorpusFailure("JSON_STRING_OF_SIZE fill must be lowercase hexadecimal")
            fill = bytes.fromhex(fill_hex)
            if not isinstance(size, int) or isinstance(size, bool) or size < 2 or len(fill) != 1:
                raise CorpusFailure("invalid JSON_STRING_OF_SIZE parameters")
            if fill in b'"\\' or fill[0] < 0x20 or fill[0] > 0x7E:
                raise CorpusFailure("JSON_STRING_OF_SIZE fill must be safe ASCII")
            return b'"' + fill * (size - 2) + b'"'
        if op == "NESTED_ARRAY" and set(recipe) == {"op", "depth", "scalar_hex"}:
            depth = recipe["depth"]
            scalar_hex = recipe["scalar_hex"]
            if not isinstance(scalar_hex, str) or LOWER_HEX.fullmatch(scalar_hex) is None:
                raise CorpusFailure("NESTED_ARRAY scalar must be lowercase hexadecimal")
            scalar = bytes.fromhex(scalar_hex)
            if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0 or not scalar:
                raise CorpusFailure("invalid NESTED_ARRAY parameters")
            return b"[" * depth + scalar + b"]" * depth
        if op == "NULL_ARRAY" and set(recipe) == {"op", "value_occurrences"}:
            occurrences = recipe["value_occurrences"]
            if (
                not isinstance(occurrences, int)
                or isinstance(occurrences, bool)
                or occurrences < 1
            ):
                raise CorpusFailure("invalid NULL_ARRAY parameters")
            return b"[" + b",".join([b"null"] * (occurrences - 1)) + b"]"
    except (TypeError, ValueError) as exc:
        raise CorpusFailure(f"bad {op} byte recipe: {exc}") from exc
    raise CorpusFailure(f"unknown or malformed byte recipe: {op}")


def _validate_sources(value: Any, case_id: str) -> int:
    count = 0
    if isinstance(value, dict):
        if set(value) == {"byte_length", "recipe", "sha256"}:
            if (
                not isinstance(value["byte_length"], int)
                or isinstance(value["byte_length"], bool)
                or value["byte_length"] < 0
                or not isinstance(value["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
            ):
                raise CorpusFailure(f"{case_id}: malformed source descriptor")
            data = _materialize(value["recipe"])
            if len(data) != value["byte_length"]:
                raise CorpusFailure(f"{case_id}: source byte length mismatch")
            if hashlib.sha256(data).hexdigest() != value["sha256"]:
                raise CorpusFailure(f"{case_id}: source SHA-256 mismatch")
            return 1
        for nested in value.values():
            count += _validate_sources(nested, case_id)
    elif isinstance(value, list):
        for nested in value:
            count += _validate_sources(nested, case_id)
    return count


def _validate_filesystem_recipe(case: dict[str, Any]) -> None:
    recipe = case["input"].get("filesystem_recipe")
    if recipe is None:
        return
    if not isinstance(recipe, list) or not recipe:
        raise CorpusFailure(f"{case['case_id']}: filesystem recipe must be a nonempty array")
    field_sets = {
        "CREATE_REGULAR": {"op", "role", "source"},
        "CREATE_OBJECT": {"op", "role", "object_kind"},
        "INJECT_FAILURE": {"op", "role", "event"},
        "WAIT_AT": {"op", "role", "point"},
        "MUTATE_AT_POINT": {"op", "role", "event"},
        "CONTINUE": {"op"},
        "LIMIT_READ_CHUNK": {"op", "chunk_bytes"},
        "ACQUIRE_AND_FREEZE": {"op"},
        "OBSERVE_ABSENT": {"op", "role"},
        "RECHECK_ABSENT": {"op", "role"},
        "REPLACE_AFTER_FREEZE": {"op", "role", "source"},
    }
    roles = {
        "AI_CANONICAL_JSON",
        "AI_MANIFEST_JSON",
        "BUNDLE_DIRECTORY",
        "TRUST_STORE",
        "VERIFICATION_KEYS_JSON",
    }
    events = {
        "APPEND_OPEN_FILE",
        "DENY_PERMISSION",
        "FAIL_OPEN",
        "FAIL_READ",
        "INJECT_PREMATURE_EOF",
        "MUTATE_OPEN_FILE",
        "REMOVE_REACHED_ENTRY",
        "REPLACE_REACHED_ENTRY",
        "TRUNCATE_OPEN_FILE",
    }
    object_kinds = {"DEVICE", "DIRECTORY", "FIFO", "SOCKET", "SYMLINK"}
    for step in recipe:
        if not isinstance(step, dict) or step.get("op") not in field_sets:
            raise CorpusFailure(f"{case['case_id']}: unknown filesystem operation")
        op = step["op"]
        if set(step) != field_sets[op]:
            raise CorpusFailure(f"{case['case_id']}: malformed filesystem operation {op}")
        if "role" in step and step["role"] not in roles:
            raise CorpusFailure(f"{case['case_id']}: unknown filesystem role")
        if "event" in step and step["event"] not in events:
            raise CorpusFailure(f"{case['case_id']}: unknown filesystem event")
        if "object_kind" in step and step["object_kind"] not in object_kinds:
            raise CorpusFailure(f"{case['case_id']}: unknown filesystem object kind")
        if "point" in step and step["point"] != "SOURCE_OPENED":
            raise CorpusFailure(f"{case['case_id']}: unknown synchronization point")
        if "chunk_bytes" in step and (
            not isinstance(step["chunk_bytes"], int)
            or isinstance(step["chunk_bytes"], bool)
            or step["chunk_bytes"] < 1
        ):
            raise CorpusFailure(f"{case['case_id']}: invalid read chunk size")


def _tool_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _walk_keys_and_values(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _walk_keys_and_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys_and_values(nested)
    else:
        yield value


def _validate_operational(
    case: dict[str, Any],
    validator: Draft7Validator,
) -> tuple[str, str]:
    case_id = case["case_id"]
    expected = case["expected"]
    result = expected["tool_result"]
    try:
        validator.validate(result)
    except ValidationError as exc:
        raise CorpusFailure(f"{case_id}: outer result schema failure: {exc.message}") from exc

    if result["outcome"] != "OPERATIONAL_OUTCOME" or result["rc"] != 3:
        raise CorpusFailure(f"{case_id}: operational discriminator/rc mismatch")
    if result["verification_result"] is not None:
        raise CorpusFailure(f"{case_id}: operational result contains verification result")
    forbidden_keys = {"assurance", "comparison_result", "reason", "status"}
    flattened = list(_walk_keys_and_values(result))
    if any(item in forbidden_keys for item in flattened if isinstance(item, str)):
        raise CorpusFailure(f"{case_id}: operational result contains semantic fields")
    if "INVALID" in flattened:
        raise CorpusFailure(f"{case_id}: operational result contains semantic INVALID")

    code = result["operational_result"]["operational_code"]
    phase = result["operational_result"]["phase"]
    effective = result["capability"]["effective"]
    requested = result["capability"]["requested"]
    if code == "CAPABILITY_PROFILE_UNAVAILABLE":
        if effective is not None:
            raise CorpusFailure(f"{case_id}: unavailable capability has effective declaration")
    elif effective != requested:
        raise CorpusFailure(f"{case_id}: requested/effective capability differs")

    encoded = _tool_bytes(result)
    if rfc8785.dumps(result) + b"\n" != encoded:
        raise CorpusFailure(f"{case_id}: explicit outer encoding is not RFC 8785 plus LF")
    if encoded.hex() != expected["tool_result_utf8_hex"]:
        raise CorpusFailure(f"{case_id}: frozen outer-result bytes mismatch")
    if hashlib.sha256(encoded).hexdigest() != expected["tool_result_sha256"]:
        raise CorpusFailure(f"{case_id}: frozen outer-result SHA-256 mismatch")
    if json.loads(bytes.fromhex(expected["tool_result_utf8_hex"])) != result:
        raise CorpusFailure(f"{case_id}: frozen bytes do not decode to expected object")
    return code, phase


def _validate_base64_case(case: dict[str, Any]) -> None:
    encoded = case["input"]["encoded"]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise CorpusFailure(f"{case['case_id']}: Base64 source does not decode: {exc}") from exc
    expected = case["expected"]
    if decoded.hex() != expected["decoded_hex"]:
        raise CorpusFailure(f"{case['case_id']}: Base64 decoded bytes mismatch")
    canonical = base64.b64encode(decoded).decode("ascii")
    if canonical != expected["canonical_encoding"] or canonical == encoded:
        raise CorpusFailure(f"{case['case_id']}: Base64 pad-bit alias is not noncanonical")


def _validate_configuration(case: dict[str, Any], validator: Draft7Validator) -> None:
    configuration = case["configuration"]
    candidate = {
        "capability": {
            "effective": configuration["capability"],
            "requested": configuration["capability"],
        },
        "contract": "aelitium-verifier-tool-result-v1",
        "input_mode": configuration["input_mode"],
        "limits": configuration["limits"],
        "operation": "VERIFY_BUNDLE",
        "operational_result": {
            "detail": None,
            "input_ref": None,
            "limit": None,
            "operational_code": "INTERNAL_OPERATION_ERROR",
            "phase": "SEMANTIC_EVALUATION",
        },
        "outcome": "OPERATIONAL_OUTCOME",
        "rc": 3,
        "verification_result": None,
    }
    validator.validate(candidate)


def _lexical_metrics(source: bytes) -> tuple[int, int]:
    index = 0
    depth = 0
    maximum_depth = 0
    value_occurrences = 0
    root_state = "VALUE"
    stack: list[dict[str, str]] = []

    def expects_value() -> bool:
        if not stack:
            return root_state == "VALUE"
        return stack[-1]["state"] in {"VALUE", "VALUE_OR_END"}

    def finish_value() -> None:
        nonlocal root_state
        if stack:
            stack[-1]["state"] = "COMMA_OR_END"
        else:
            root_state = "DONE"

    while index < len(source):
        byte = source[index]
        if byte in b" \t\r\n":
            index += 1
        elif byte == 0x22:
            index += 1
            while index < len(source):
                if source[index] == 0x5C:
                    index += 2
                elif source[index] == 0x22:
                    index += 1
                    break
                else:
                    index += 1
            if stack and stack[-1] == {"kind": "OBJECT", "state": "KEY_OR_END"}:
                stack[-1]["state"] = "COLON"
            elif expects_value():
                value_occurrences += 1
                finish_value()
        elif byte in (0x7B, 0x5B):
            if expects_value():
                value_occurrences += 1
            stack.append(
                {
                    "kind": "OBJECT" if byte == 0x7B else "ARRAY",
                    "state": "KEY_OR_END" if byte == 0x7B else "VALUE_OR_END",
                }
            )
            depth += 1
            maximum_depth = max(maximum_depth, depth)
            index += 1
        elif byte in (0x7D, 0x5D):
            if stack:
                stack.pop()
                depth -= 1
            finish_value()
            index += 1
        elif byte == 0x3A:
            if stack and stack[-1]["kind"] == "OBJECT":
                stack[-1]["state"] = "VALUE"
            index += 1
        elif byte == 0x2C:
            if stack:
                stack[-1]["state"] = (
                    "KEY_OR_END" if stack[-1]["kind"] == "OBJECT" else "VALUE_OR_END"
                )
            index += 1
        else:
            end = index + 1
            while end < len(source) and source[end] not in b" \t\r\n,]}":
                end += 1
            if expects_value():
                value_occurrences += 1
                finish_value()
            index = end
    return maximum_depth, value_occurrences


def _measure_existing_corpora() -> dict[str, Any]:
    measured: list[tuple[int, int, int, str]] = []
    for relative in (
        "canonicalization/vectors.json",
        "canonicalization_v2/vectors.json",
    ):
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for vector in document["vectors"]:
            if "source_bytes_hex" not in vector:
                continue
            source = bytes.fromhex(vector["source_bytes_hex"])
            depth, values = _lexical_metrics(source)
            measured.append((len(source), depth, values, f"{relative}:{vector['case_id']}"))
    for path in sorted((ROOT / "fixtures").rglob("*.json")):
        source = path.read_bytes()
        depth, values = _lexical_metrics(source)
        measured.append((len(source), depth, values, str(path.relative_to(ROOT))))
    by_bytes = max(measured, key=lambda item: item[0])
    by_depth = max(measured, key=lambda item: item[1])
    by_values = max(measured, key=lambda item: item[2])

    operation_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    snapshots: list[tuple[int, str]] = []
    for relative in operation_manifest["vector_files"]:
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for vector in document["vectors"]:
            inputs = vector["input"]
            if vector["operation"] == "verify":
                bundles = [inputs["bundle"]]
            elif vector["operation"] == "compare":
                bundles = [inputs["left"], inputs["right"]]
            else:
                raise CorpusFailure(
                    f"unknown result-contract operation: {vector['operation']}"
                )
            options = inputs.get("options", [])
            trust_relative = None
            if "--trust-store" in options:
                trust_relative = options[options.index("--trust-store") + 1]
            for bundle_relative in bundles:
                bundle = ROOT / bundle_relative
                total = sum(
                    (bundle / name).stat().st_size
                    for name in (
                        "ai_canonical.json",
                        "ai_manifest.json",
                        "verification_keys.json",
                    )
                    if (bundle / name).is_file()
                )
                label = f"{relative}:{vector['case_id']}:{bundle_relative}"
                if trust_relative is not None:
                    total += (ROOT / trust_relative).stat().st_size
                    label += f"+{trust_relative}"
                snapshots.append((total, label))
    by_snapshot = max(snapshots, key=lambda item: item[0])
    return {
        "maximum_operation_snapshot_bytes": by_snapshot[0],
        "maximum_operation_snapshot_bytes_ref": by_snapshot[1],
        "maximum_source_bytes": by_bytes[0],
        "maximum_source_bytes_ref": by_bytes[3],
        "maximum_structural_depth": by_depth[1],
        "maximum_structural_depth_ref": by_depth[3],
        "maximum_value_occurrences": by_values[2],
        "maximum_value_occurrences_ref": by_values[3],
        "measured_operation_snapshot_count": len(snapshots),
        "measured_source_count": len(measured),
        "scope": [
            "canonicalization/vectors.json source_bytes_hex",
            "canonicalization_v2/vectors.json source_bytes_hex",
            "fixtures/**/*.json exact bytes",
            "result-contract vector bundle/trust operation snapshots",
        ],
    }


def run() -> dict[str, Any]:
    manifest = _load(MANIFEST_PATH)
    document = _load(CASES_PATH)
    tool_schema = _load(TOOL_SCHEMA_PATH, canonical=False)
    verify_schema = _load(VERIFY_SCHEMA_PATH, canonical=False)
    try:
        Draft7Validator.check_schema(tool_schema)
        registry = Registry().with_resource(
            verify_schema["$id"],
            Resource.from_contents(verify_schema),
        )
        validator = Draft7Validator(tool_schema, registry=registry)
    except SchemaError as exc:
        raise CorpusFailure(f"outer result schema is invalid: {exc.message}") from exc

    if manifest["contract"] != "aelitium-legacy-v1-operational-policy-conformance-v1":
        raise CorpusFailure("manifest contract mismatch")
    if document["contract"] != manifest["contract"]:
        raise CorpusFailure("vector document contract mismatch")
    if (
        manifest.get("operation_contract") != "AELITIUM-LEGACY-V1-POLICY-OPERATION-1"
        or document.get("operation_contract") != manifest["operation_contract"]
    ):
        raise CorpusFailure("operation contract mismatch")
    if manifest["status"] != "NORMATIVE-UNRELEASED" or document["status"] != manifest["status"]:
        raise CorpusFailure("corpus status mismatch")
    if manifest["existing_corpora_unchanged"] != EXPECTED_EXISTING_COUNTS:
        raise CorpusFailure("existing corpus count declaration changed")
    if manifest["existing_corpus_measurements"] != _measure_existing_corpora():
        raise CorpusFailure("frozen existing-corpus measurements changed")
    if manifest["case_count"] != len(document["vectors"]) or document["case_count"] != len(document["vectors"]):
        raise CorpusFailure("case count mismatch")

    case_ids: set[str] = set()
    categories: dict[str, int] = {}
    operational_codes: set[str] = set()
    phases: set[str] = set()
    case_operations: set[str] = set()
    checkpoint_decisions: set[str] = set()
    source_count = 0
    for case in document["vectors"]:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise CorpusFailure(f"duplicate or malformed case identifier: {case_id!r}")
        case_ids.add(case_id)
        category = case.get("category")
        categories[category] = categories.get(category, 0) + 1
        case_operations.add(case.get("operation"))
        try:
            _validate_configuration(case, validator)
        except ValidationError as exc:
            raise CorpusFailure(f"{case_id}: configuration schema failure: {exc.message}") from exc
        source_count += _validate_sources(case["input"], case_id)
        _validate_filesystem_recipe(case)
        expected = case.get("expected")
        if expected.get("kind") == "OPERATIONAL_TOOL_RESULT":
            code, phase = _validate_operational(case, validator)
            operational_codes.add(code)
            phases.add(phase)
        elif expected.get("kind") != "POLICY_CHECKPOINT":
            raise CorpusFailure(f"{case_id}: unknown expected-result kind")
        else:
            decision = expected.get("decision")
            if decision not in EXPECTED_CHECKPOINT_DECISIONS:
                raise CorpusFailure(f"{case_id}: unknown policy checkpoint decision")
            checkpoint_decisions.add(decision)
        if case["operation"] == "DECODE_LEGACY_BASE64":
            _validate_base64_case(case)

    missing = REQUIRED_CASE_IDS - case_ids
    if missing:
        raise CorpusFailure(f"required cases missing: {sorted(missing)}")
    if operational_codes != EXPECTED_OPERATIONAL_CODES:
        raise CorpusFailure(
            f"operational code coverage mismatch: {sorted(operational_codes)}"
        )
    if phases != EXPECTED_PHASES:
        raise CorpusFailure(f"operational phase coverage mismatch: {sorted(phases)}")
    if case_operations != EXPECTED_CASE_OPERATIONS:
        raise CorpusFailure(f"case operation coverage mismatch: {sorted(case_operations)}")
    if checkpoint_decisions != EXPECTED_CHECKPOINT_DECISIONS:
        raise CorpusFailure(
            f"checkpoint decision coverage mismatch: {sorted(checkpoint_decisions)}"
        )
    if categories != manifest["categories"]:
        raise CorpusFailure("category counts disagree with manifest")
    if source_count == 0:
        raise CorpusFailure("no exact source recipes were checked")

    return {
        "case_count": len(case_ids),
        "operational_codes": len(operational_codes),
        "phases": len(phases),
        "source_descriptors": source_count,
        "existing_sources_measured": manifest["existing_corpus_measurements"]["measured_source_count"],
        "existing_snapshots_measured": manifest["existing_corpus_measurements"]["measured_operation_snapshot_count"],
        "status": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a JSON summary")
    args = parser.parse_args(argv)
    try:
        result = run()
    except (CorpusFailure, KeyError, TypeError, ValidationError) as exc:
        print(f"[FAIL] Legacy-v1 operational-policy corpus: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    else:
        print(
            "[PASS] Legacy-v1 operational-policy corpus: "
            f"{result['case_count']}/{result['case_count']} cases; "
            f"{result['operational_codes']} codes; {result['phases']} phases; "
            f"{result['source_descriptors']} source descriptors; "
            f"{result['existing_sources_measured']} existing sources and "
            f"{result['existing_snapshots_measured']} operation snapshots remeasured"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
