"""Small, stable facade for external agents.

This module intentionally delegates selection capture to the same primitive used
by the Sidebar ``+`` button.  Callers must never persist Blender mesh indices.
"""

from __future__ import annotations

import json
import hashlib
import math
import uuid
import bpy
from mathutils import Vector

from .blender.context import context_source
from .blender.selection import source_selection_snapshot
from .blender.mesh import (
    _active_shape_key,
    _shape_key_target_record,
    _source_id_maps,
    _validate_source_topology,
)
from .constants import (
    BASE_MESH_TARGET,
    CONTROLS_KEY,
    NETWORK_REVISION_KEY,
    PROXY_GENERATION_KEY,
    SOURCE_UUID_KEY,
    TOPOLOGY_KEY,
)
from . import _runtime


def inspect_source_selection(context: bpy.types.Context | None = None) -> dict[str, object]:
    """Return the current Source selection using persistent DANP IDs."""
    context = context or bpy.context
    source, _ = context_source(context)
    if source is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    return source_selection_snapshot(source)


def list_controls(source: bpy.types.Object) -> list[dict[str, object]]:
    """Return a defensive copy of canonical control definitions."""
    return json.loads(source.get(CONTROLS_KEY, "[]"))


def validate_control(source: bpy.types.Object, control: dict[str, object]) -> dict[str, object]:
    """Validate a definition against the current Source persistent-ID map."""
    _validate_source_topology(source)
    vertex_map, edge_map = _source_id_maps(source)
    vertex_ids = {int(value) for value in control.get("vertex_ids", [])}
    edge_ids = {int(value) for value in control.get("edge_ids", [])}
    missing_vertices = sorted(vertex_ids - set(vertex_map))
    missing_edges = sorted(edge_ids - set(edge_map))
    return {
        "valid": not missing_vertices and not missing_edges,
        "control_uuid": str(control.get("control_uuid", "")),
        "missing_vertex_ids": missing_vertices,
        "missing_edge_ids": missing_edges,
        "topology_fingerprint": str(source.get(TOPOLOGY_KEY, "")),
    }


def create_control_from_current_selection(
    context: bpy.types.Context | None = None,
    *,
    name: str = "",
    side: str = "",
    region: str = "",
) -> dict[str, object]:
    """Create through the registered operator, exactly like the UI ``+`` button.

    The returned payload is safe for an external agent: identity is expressed by
    the control UUID and persistent IDs, while Blender indices remain diagnostic
    only.  No caller should write the control JSON directly.
    """
    context = context or bpy.context
    source, _ = context_source(context)
    if source is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    before = {str(item.get("control_uuid", "")) for item in list_controls(source)}
    result = bpy.ops.dan_form.create_control(control_name=name, side=side, region=region)
    if "FINISHED" not in result:
        raise ValueError("CONTROL_CREATE_FAILED")
    created = next((item for item in list_controls(source) if str(item.get("control_uuid", "")) not in before), None)
    if created is None:
        raise ValueError("CONTROL_CREATE_RESULT_MISSING")
    selection = inspect_source_selection(context)
    validation = validate_control(source, created)
    if not validation["valid"]:
        raise ValueError("CONTROL_PERSISTENT_ID_INVALID")
    return {"status": "OK", "control": created, "selection": selection, "validation": validation}


def _target_revision(source: bpy.types.Object) -> str:
    shape_keys = source.data.shape_keys
    blocks = shape_keys.key_blocks if shape_keys else ()
    payload = {
        "source_uuid": str(source.get(SOURCE_UUID_KEY, "")),
        "source_data": int(source.data.as_pointer()),
        "topology": str(source.get(TOPOLOGY_KEY, "")),
        "network": int(source.get(NETWORK_REVISION_KEY, 0)),
        "active_index": int(source.active_shape_key_index),
        "use_relative": bool(shape_keys.use_relative) if shape_keys else None,
        "eval_time": float(shape_keys.eval_time) if shape_keys else None,
        "keys": [
            (int(key.as_pointer()), str(key.name), index,
             bool(key.lock_shape), len(key.data), float(key.frame))
            for index, key in enumerate(blocks)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def list_deformation_targets(source: bpy.types.Object) -> dict[str, object]:
    """List supported targets with a revision guard for later selection."""
    if source is None or source.type != "MESH" or source.data is None:
        raise ValueError("INVALID_SOURCE")
    from .blender.context import READY, binding_status
    binding = binding_status(source)
    if binding != READY:
        raise ValueError(f"SOURCE_BINDING_{binding}")
    revision = _target_revision(source)
    try:
        _validate_source_topology(source)
    except (RuntimeError, ValueError) as exc:
        return {"status": "STALE", "target_revision": revision,
                "error": str(exc), "targets": []}

    shape_keys = source.data.shape_keys
    blocks = shape_keys.key_blocks if shape_keys else ()
    if not blocks:
        target = {"target_id": "BASE", "kind": "BASE", "name": "Base",
                  "index": None, "locked": False, "active": True,
                  "supported": True}
        return {"status": "OK", "target_revision": revision, "targets": [target]}

    targets = []
    active_index = int(source.active_shape_key_index)
    for index, key in enumerate(blocks):
        pointer = int(key.as_pointer())
        targets.append({
            "target_id": f"KEY:{pointer}",
            "kind": "KEY",
            "name": str(key.name),
            "index": index,
            "locked": bool(key.lock_shape),
            "active": index == active_index,
            "supported": True,
        })
    return {"status": "OK", "target_revision": revision, "targets": targets}


def select_deformation_target(
    source: bpy.types.Object,
    target_id: str,
    *,
    expected_revision: str,
    context: bpy.types.Context | None = None,
) -> dict[str, object]:
    """Select a listed target through the same operator used by the sidebar."""
    context = context or bpy.context
    if source is None or source.type != "MESH" or source.data is None:
        raise ValueError("INVALID_SOURCE")
    if not isinstance(target_id, str):
        raise ValueError("SHAPE_KEY_TARGET_INVALID")
    if _target_revision(source) != str(expected_revision):
        raise ValueError("TARGET_REVISION_MISMATCH")
    active_source, _controller = context_source(context)
    if active_source != source:
        raise ValueError("SOURCE_NOT_ACTIVE")

    shape_keys = source.data.shape_keys
    blocks = shape_keys.key_blocks if shape_keys else ()
    if not blocks:
        if target_id != "BASE":
            raise ValueError("SHAPE_KEY_TARGET_INVALID")
        return {"status": "OK", "target": {"target_id": "BASE", "kind": "BASE",
                "name": "Base", "index": None, "locked": False},
                "target_revision": _target_revision(source)}

    key = next((item for item in blocks
                if target_id == f"KEY:{int(item.as_pointer())}"), None)
    if key is None:
        raise ValueError("SHAPE_KEY_TARGET_INVALID")
    index = next(index for index, item in enumerate(blocks) if item == key)
    result = bpy.ops.dan_form.select_shape_key(key_index=index)
    if "FINISHED" not in result:
        raise ValueError("SHAPE_KEY_SELECT_FAILED")
    record = _shape_key_target_record(source, _active_shape_key(source))
    return {"status": "OK", "target": {**record, "target_id": target_id,
            "locked": bool(key.lock_shape)}, "target_revision": _target_revision(source)}


def _find_agent_operation(operation_id: str):
    if not isinstance(operation_id, str) or not operation_id:
        raise ValueError("OPERATION_HANDLE_INVALID")
    tx = next((item for item in _runtime.DANP_TRANSACTIONS.values()
               if item.get("agent_operation_id") == operation_id and not item.get("closed")), None)
    if tx is None:
        raise ValueError("OPERATION_HANDLE_INVALID")
    source = next((obj for obj in bpy.data.objects
                   if obj.as_pointer() == tx.get("source")), None)
    controller = next((obj for obj in bpy.data.objects
                       if obj.as_pointer() == tx.get("controller")), None)
    from .blender.context import find_controller
    if (source is None or controller is None or controller.parent != source
            or find_controller(source) != controller):
        raise ValueError("OPERATION_STALE")
    return source, controller, tx


def _validate_agent_operation(source, controller, tx) -> None:
    from . import _modifier_signature, _shape_key_signature
    if _shape_key_signature(source) != tx.get("shape_key_signature"):
        raise ValueError("SHAPE_KEY_TARGET_CHANGED")
    if (source.get(TOPOLOGY_KEY) != tx.get("topology")
            or int(source.get(NETWORK_REVISION_KEY, 0)) != tx.get("network")
            or int(controller.get(PROXY_GENERATION_KEY, 0)) != tx.get("proxy_generation")
            or _modifier_signature(source) != tx.get("modifier_signature")):
        raise ValueError("OPERATION_STALE")


def _operation_reply(source, tx) -> dict[str, object]:
    target_record = _shape_key_target_record(source, tx.get("shape_key_target"))
    target_id = ("BASE" if target_record.get("kind") == "BASE"
                 else f"KEY:{target_record['pointer']}")
    return {"target": {**target_record, "target_id": target_id},
            "target_revision": _target_revision(source),
            "network_revision": int(source.get(NETWORK_REVISION_KEY, 0))}


def begin_operation(context: bpy.types.Context | None = None) -> dict[str, object]:
    """Begin a target-captured transaction and return its opaque handle."""
    context = context or bpy.context
    source, controller = context_source(context)
    if source is None or controller is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    if context.view_layer.objects.active != controller or controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    from . import _deform_begin
    tx = _deform_begin(source, controller)
    operation_id = uuid.uuid4().hex
    tx["agent_operation_id"] = operation_id
    return {"status": "OK", "operation_id": operation_id,
            "source_uuid": str(tx.get("source_uuid", "")),
            "topology": str(tx.get("topology", "")),
            "network": int(tx.get("network", 0)),
            "selected_vertex_ids": sorted(int(v) for v in tx.get("selected", set())),
            "scope_vertex_ids": sorted(int(v) for v in tx.get("scope", set())),
            "changed_count": 0, **_operation_reply(source, tx)}


def update_operation(operation_id: str, delta=(0.0, 0.0, 0.0), *,
                     profile: str = "LINEAR", radius: float = 0.0) -> dict[str, object]:
    """Apply an absolute-from-rest translation preview for one handle."""
    source, controller, tx = _find_agent_operation(operation_id)
    _validate_agent_operation(source, controller, tx)
    from . import _deform_update
    result = _deform_update(source, controller, delta=tuple(Vector(delta)),
                            profile=profile, radius=float(radius))
    return {"status": "OK", "operation_id": operation_id,
            **_operation_reply(source, tx), "changed_count": result["changed_vertices"],
            **result}


def set_knot_targets(operation_id: str, targets: dict, *,
                     profile: str = "LINEAR", radius: float = 0.0) -> dict[str, object]:
    """Set absolute Source-local coordinates for every selected knot ID."""
    source, controller, tx = _find_agent_operation(operation_id)
    _validate_agent_operation(source, controller, tx)
    if not isinstance(targets, dict):
        raise ValueError("TARGETS_MUST_BE_MAPPING")
    normalized = {}
    try:
        for raw_id, raw_coordinate in targets.items():
            if isinstance(raw_id, bool):
                raise ValueError("TARGET_ID_INVALID")
            if isinstance(raw_id, int):
                vertex_id = raw_id
            elif isinstance(raw_id, str) and raw_id.strip().lstrip("-").isdigit():
                vertex_id = int(raw_id)
            else:
                raise ValueError("TARGET_ID_INVALID")
            if vertex_id in normalized:
                raise ValueError("TARGET_ID_DUPLICATE")
            coordinate = tuple(float(value) for value in raw_coordinate)
            if len(coordinate) != 3 or not all(math.isfinite(value) for value in coordinate):
                raise ValueError("NON_FINITE_RESULT")
            normalized[vertex_id] = Vector(coordinate)
    except (TypeError, ValueError, OverflowError) as exc:
        if str(exc) in {"TARGET_ID_INVALID", "TARGET_ID_DUPLICATE", "NON_FINITE_RESULT"}:
            raise
        raise ValueError("TARGET_INVALID") from exc
    selected = {int(value) for value in tx.get("selected", set())}
    if set(normalized) != selected:
        raise ValueError("TARGET_SET_MISMATCH")
    from . import _deform_update
    result = _deform_update(source, controller, targets=normalized,
                            selection_intent=selected, profile=profile,
                            radius=float(radius))
    return {"status": "OK", "operation_id": operation_id,
            **_operation_reply(source, tx), "changed_count": result["changed_vertices"],
            **result}


def commit_operation(operation_id: str) -> dict[str, object]:
    source, _controller, tx = _find_agent_operation(operation_id)
    _validate_agent_operation(source, _controller, tx)
    from . import _source_positions, _deform_commit
    target_before = tx.get("p0", {})
    target_after = _source_positions(source, tx.get("shape_key_target"))
    changed_count = sum(
        1 for vertex_id, before in target_before.items()
        if vertex_id in target_after
        and (target_after[vertex_id] - before).length_squared > 1e-14
    )
    reply = _operation_reply(source, tx)
    _deform_commit(source)
    return {"status": "OK", "operation_id": operation_id,
            "changed_count": changed_count, **reply}


def cancel_operation(operation_id: str) -> dict[str, object]:
    source, controller, tx = _find_agent_operation(operation_id)
    reply = _operation_reply(source, tx)
    from . import _source_positions, _deform_cancel
    before = _source_positions(source, tx.get("shape_key_target"))
    rest = tx.get("p0", {})
    changed_count = sum(
        1 for vertex_id, position in before.items()
        if vertex_id in rest and (position - rest[vertex_id]).length_squared > 1e-14
    )
    _deform_cancel(source, controller)
    return {"status": "CANCELLED", "operation_id": operation_id,
            "changed_count": changed_count, **reply}
