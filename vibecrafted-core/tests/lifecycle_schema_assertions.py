from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from vibecrafted_core.lifecycle_runner import LIFECYCLE_SCHEMA_ID
from vibecrafted_core.package_resources import resource_path


def packaged_lifecycle_schema() -> dict[str, Any]:
    path = resource_path("schemas", "lifecycle.schema.v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_lifecycle_state_matches_packaged_schema(state: dict[str, Any]) -> None:
    schema = packaged_lifecycle_schema()
    assert schema["$id"] == LIFECYCLE_SCHEMA_ID
    assert schema["properties"]["schema"]["const"] == LIFECYCLE_SCHEMA_ID
    _validate_schema_value(state, schema, schema, "$")


def _validate_schema_value(
    value: Any,
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        _validate_schema_value(
            value,
            _resolve_ref(str(schema["$ref"]), root),
            root,
            path,
        )
        return

    if "oneOf" in schema:
        matches = 0
        errors: list[str] = []
        for option in schema["oneOf"]:
            try:
                _validate_schema_value(value, option, root, path)
            except AssertionError as exc:
                errors.append(str(exc))
            else:
                matches += 1
        assert matches == 1, (
            f"{path}: expected exactly one oneOf match, got {matches}; {errors}"
        )
        return

    if "const" in schema:
        assert value == schema["const"], (
            f"{path}: expected const {schema['const']!r}, got {value!r}"
        )

    expected_types = schema.get("type")
    if expected_types is not None:
        _assert_json_type(value, expected_types, path)

    if "enum" in schema:
        assert value in schema["enum"], (
            f"{path}: expected one of {schema['enum']!r}, got {value!r}"
        )

    if "minimum" in schema and value is not None:
        assert value >= schema["minimum"], (
            f"{path}: expected >= {schema['minimum']}, got {value!r}"
        )

    if isinstance(value, Mapping):
        missing = set(schema.get("required") or []) - set(value)
        assert not missing, f"{path}: missing required keys {sorted(missing)}"
        properties = schema.get("properties") or {}
        for key, property_schema in properties.items():
            if key in value:
                _validate_schema_value(
                    value[key],
                    property_schema,
                    root,
                    f"{path}.{key}",
                )

    if isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(value):
            _validate_schema_value(item, item_schema, root, f"{path}[{index}]")


def _resolve_ref(ref: str, root: Mapping[str, Any]) -> Mapping[str, Any]:
    assert ref.startswith("#/"), f"unsupported schema ref: {ref}"
    current: Any = root
    for part in ref[2:].split("/"):
        assert isinstance(current, Mapping), f"schema ref is not an object: {ref}"
        current = current[part]
    assert isinstance(current, Mapping), (
        f"schema ref does not resolve to an object: {ref}"
    )
    return current


def _assert_json_type(value: Any, raw_types: str | Sequence[str], path: str) -> None:
    expected_types = [raw_types] if isinstance(raw_types, str) else list(raw_types)
    checks = {
        "array": lambda item: isinstance(item, list),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "null": lambda item: item is None,
        "object": lambda item: isinstance(item, Mapping),
        "string": lambda item: isinstance(item, str),
    }
    assert any(checks[item](value) for item in expected_types if item in checks), (
        f"{path}: expected type {expected_types!r}, got {type(value).__name__}"
    )
