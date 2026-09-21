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
    HIDDEN_EIDS_KEY,
    HIDDEN_VIDS_KEY,
    SCHEMA_KEY,
    SCHEMA_VERSION,
    SOURCE_UUID_KEY,
)


def json_set(obj: bpy.types.ID, key: str, value) -> None:
    obj[key] = json.dumps(value, separators=(",", ":"), sort_keys=True)


def controls(source: bpy.types.Object) -> list[dict]:
    value = _stored_json(source, CONTROLS_KEY)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("CONTROL_DATA_INVALID: definitions must be a list of objects")
    return value


def _stored_json(source: bpy.types.Object, key: str):
    """Read persistent data strictly; a corrupt field is not an empty control set."""
    value = source.get(key)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"CONTROL_DATA_INVALID: {key} is not valid JSON") from exc
    return value


def _stored_ids(source: bpy.types.Object, key: str) -> set[int]:
    value = _stored_json(source, key)
    if value is None:
        return set()
    return _valid_ids(value, key)


def _valid_ids(value, field: str) -> set[int]:
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"CONTROL_DATA_INVALID: {field} must be a list of IDs")
    if any(type(item) is not int or item < 0 for item in value):
        raise ValueError(f"CONTROL_DATA_INVALID: {field} contains an invalid ID")
    return set(value)


def validate_control_storage(source: bpy.types.Object) -> list[dict]:
    """Preflight all persisted control fields before any migration or mesh write."""
    schema = source.get(SCHEMA_KEY)
    if schema is not None and str(schema) not in {"1", "2", SCHEMA_VERSION}:
        raise ValueError(f"CONTROL_DATA_INVALID: unsupported schema {schema}")
    definitions = controls(source)
    _stored_ids(source, HIDDEN_VIDS_KEY)
    _stored_ids(source, HIDDEN_EIDS_KEY)
    seen = set()
    for item in definitions:
        control_uuid = item.get("control_uuid")
        if not isinstance(control_uuid, str) or not control_uuid or control_uuid in seen:
            raise ValueError("CONTROL_DATA_INVALID: missing or duplicate control_uuid")
        seen.add(control_uuid)
        if not isinstance(item.get("name"), str):
            raise ValueError("CONTROL_DATA_INVALID: name must be text")
        if type(item.get("enabled", True)) is not bool:
            raise ValueError("CONTROL_DATA_INVALID: enabled must be boolean")
        for field in ("vertex_ids", "edge_ids", "hidden_vertex_ids", "hidden_edge_ids"):
            _valid_ids(item.get(field, []), field)
    return definitions


def migrate_control_schema(source: bpy.types.Object, edge_vids: dict[int, tuple[int, int]] | None = None) -> list[dict]:
    """Upgrade legacy shared masks to per-definition control state once.

    Version 2 stored hidden vertices/edges globally on Source.  A shared ID can
    belong to several controls, so that representation could hide geometry from
    an unrelated definition.  Version 3 stores ``enabled`` and hidden IDs on
    each definition.  The old global masks are projected onto every definition
    that contains the corresponding ID, preserving the visible result at the
    moment of migration.
    """
    definitions = validate_control_storage(source)
    legacy_vertices = _stored_ids(source, HIDDEN_VIDS_KEY)
    legacy_edges = _stored_ids(source, HIDDEN_EIDS_KEY)
    changed = False
    normalized = []
    for raw in definitions:
        item = dict(raw)
        vertex_ids = _valid_ids(item.get("vertex_ids", []), "vertex_ids")
        edge_ids = _valid_ids(item.get("edge_ids", []), "edge_ids")
        hidden_vertices = _valid_ids(item.get("hidden_vertex_ids", []), "hidden_vertex_ids")
        hidden_edges = _valid_ids(item.get("hidden_edge_ids", []), "hidden_edge_ids")
        hidden_vertices.update(vertex_ids.intersection(legacy_vertices))
        hidden_edges.update(edge_ids.intersection(legacy_edges))
        # Edge endpoints were represented by the old vertex mask as well.
        # Keep those masks on the definition if it owns the edge.
        hidden_vertices.update(
            legacy_vertices.intersection(vertex_ids)
        )
        if edge_vids:
            owned_endpoints = {
                vertex_id
                for edge_id in edge_ids
                for vertex_id in edge_vids.get(edge_id, ())
            }
            hidden_vertices.update(legacy_vertices.intersection(owned_endpoints))
        item["vertex_ids"] = sorted(vertex_ids)
        item["edge_ids"] = sorted(edge_ids)
        # Keep endpoint masks even when a control stores only edge membership;
        # the old global mask hid those endpoints through edge evaluation.
        allowed_vertices = vertex_ids | {
            vertex_id
            for edge_id in edge_ids
            for vertex_id in (edge_vids or {}).get(edge_id, ())
        }
        item["hidden_vertex_ids"] = sorted(hidden_vertices.intersection(allowed_vertices))
        item["hidden_edge_ids"] = sorted(hidden_edges.intersection(edge_ids))
        item["enabled"] = item.get("enabled", True)
        normalized.append(item)
        if item != raw:
            changed = True

    if legacy_vertices or legacy_edges:
        changed = True
    if changed or str(source.get(SCHEMA_KEY, "")) != SCHEMA_VERSION:
        json_set(source, CONTROLS_KEY, normalized)
        # These keys remain understood for old files but are no longer the
        # source of truth after migration.
        json_set(source, HIDDEN_VIDS_KEY, [])
        json_set(source, HIDDEN_EIDS_KEY, [])
        source[SCHEMA_KEY] = SCHEMA_VERSION
    return normalized


def control(source: bpy.types.Object | None, control_uuid: str) -> dict | None:
    if source is None:
        return None
    return next((item for item in controls(source) if item.get("control_uuid") == control_uuid), None)


def hidden(source: bpy.types.Object, key: str) -> set[int]:
    return _stored_ids(source, key)


def source_uuid(source: bpy.types.Object) -> str:
    value = source.get(SOURCE_UUID_KEY)
    if not isinstance(value, str) or not value:
        value = uuid.uuid4().hex
        source[SOURCE_UUID_KEY] = value
    if SCHEMA_KEY not in source:
        source[SCHEMA_KEY] = SCHEMA_VERSION
    return value
