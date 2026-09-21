"""Small, stable facade for external agents.

This module intentionally delegates selection capture to the same primitive used
by the Sidebar ``+`` button.  Callers must never persist Blender mesh indices.
"""

from __future__ import annotations

import json
import bpy
from mathutils import Vector

from .blender.context import context_source
from .blender.selection import source_selection_snapshot
from .blender.mesh import _source_id_maps, _validate_source_topology
from .constants import CONTROLS_KEY, TOPOLOGY_KEY


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


def begin_operation(context: bpy.types.Context | None = None) -> dict[str, object]:
    """Begin the same immutable-rest transaction used by Controller Edit."""
    context = context or bpy.context
    source, controller = context_source(context)
    if source is None or controller is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    if context.view_layer.objects.active != controller or controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    from . import _deform_begin
    tx = _deform_begin(source, controller)
    return {"status": "OK", "source_uuid": str(tx.get("source_uuid", "")),
            "topology": str(tx.get("topology", "")),
            "network": int(tx.get("network", 0)),
            "selected_vertex_ids": sorted(int(v) for v in tx.get("selected", set())),
            "scope_vertex_ids": sorted(int(v) for v in tx.get("scope", set()))}


def update_operation(delta=(0.0, 0.0, 0.0), *, context: bpy.types.Context | None = None,
                     profile: str = "LINEAR", radius: float = 0.0) -> dict[str, object]:
    """Apply an absolute-from-rest preview update and return its counts."""
    context = context or bpy.context
    source, controller = context_source(context)
    if source is None or controller is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    from . import _deform_update
    result = _deform_update(source, controller, delta=tuple(Vector(delta)),
                                     profile=profile, radius=float(radius))
    return {"status": "OK", **result}


def commit_operation(context: bpy.types.Context | None = None) -> dict[str, str]:
    context = context or bpy.context
    source, _ = context_source(context)
    if source is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    from . import _deform_commit
    _deform_commit(source)
    return {"status": "OK"}


def cancel_operation(context: bpy.types.Context | None = None) -> dict[str, str]:
    context = context or bpy.context
    source, controller = context_source(context)
    if source is None or controller is None:
        raise ValueError("NO_ACTIVE_SOURCE")
    from . import _deform_cancel
    _deform_cancel(source, controller)
    return {"status": "OK"}
