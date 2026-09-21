"""Source-backed persistent values used by DANP Form.

This layer only serializes the model's definitions and masks.  It does not
decide how patches deform and does not access Blender UI state.
"""

from __future__ import annotations

import json
import uuid

import bpy

from .constants import (
    CONTROLS_KEY,
    SCHEMA_KEY,
    SCHEMA_VERSION,
    SOURCE_UUID_KEY,
)


def json_get(obj: bpy.types.ID, key: str, default):
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return default
        return decoded
    return value


def json_set(obj: bpy.types.ID, key: str, value) -> None:
    obj[key] = json.dumps(value, separators=(",", ":"), sort_keys=True)


def controls(source: bpy.types.Object) -> list[dict]:
    value = json_get(source, CONTROLS_KEY, [])
    return value if isinstance(value, list) else []


def control(source: bpy.types.Object | None, control_uuid: str) -> dict | None:
    if source is None:
        return None
    return next((item for item in controls(source) if item.get("control_uuid") == control_uuid), None)


def hidden(source: bpy.types.Object, key: str) -> set[int]:
    value = json_get(source, key, [])
    return {int(item) for item in value if isinstance(item, int) or str(item).isdigit()}


def source_uuid(source: bpy.types.Object) -> str:
    value = source.get(SOURCE_UUID_KEY)
    if not isinstance(value, str) or not value:
        value = uuid.uuid4().hex
        source[SOURCE_UUID_KEY] = value
    source[SCHEMA_KEY] = SCHEMA_VERSION
    return value

