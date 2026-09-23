"""DANP Form Source-backed control network and deformation facade."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import uuid
from types import SimpleNamespace

import bmesh
import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Euler, Matrix, Vector

from .constants import *
from . import runtime as _runtime
from .storage import control as _control
from .storage import controls as _controls
from .storage import hidden as _hidden
from .storage import json_set as _json_set
from .storage import migrate_control_schema as _storage_migrate_control_schema
from .storage import source_uuid as _source_uuid
from .core.controls import control_effective as _core_control_effective
from .core.controls import control_intent as _core_control_intent
from .core.controls import effective_elements as _core_effective_elements
from .core.patches import partition_faces as _core_partition_faces
from .core.proportional import alpha as _core_proportional_alpha
from .core.graph import distances as _core_graph_distances
from .core.deformation import compute_preview as _core_compute_preview
from .blender.context import context_source as _context_source
from .blender.context import binding_status as _binding_status
from .blender.context import controller_children as _controller_children
from .blender.context import find_controller as _find_controller
from .blender.context import find_source_by_uuid as _find_source_by_uuid
from .blender.context import source_objects_by_uuid as _source_objects_by_uuid
from .blender.context import source_for_controller as _source_for_controller
from .blender.context import controller_collection as _controller_collection
from .blender.context import select_only as _select_only
from .blender.context import source_controller_pairs as _source_controller_pairs
from .blender.mesh import _ensure_attribute as _ensure_attribute
from .blender.mesh import _ensure_source_ids as _ensure_source_ids
from .blender.mesh import _is_valid_source as _is_valid_source
from .blender.mesh import _source_co as _source_co
from .blender.mesh import _source_edge_vids as _source_edge_vids
from .blender.mesh import _source_id_maps as _source_id_maps
from .blender.mesh import _source_vertices as _source_vertices
from .blender.mesh import _source_vid as _source_vid
from .blender.mesh import _topology_fingerprint as _topology_fingerprint
from .blender.mesh import _validate_source_topology as _validate_source_topology
from .blender.mesh import _topology_state as _topology_state
from .blender.mesh import _modifier_signature as _modifier_signature
from .blender.proxy import ProxyDeps as _ProxyDeps
from .blender.proxy import guard_proxy_topology as _proxy_guard
from .blender.proxy import proxy_state as _proxy_state_impl
from .blender.proxy import rebuild_proxy as _proxy_rebuild
from .blender.proxy import sync_proxy as _proxy_sync
from .blender.selection import _controller_selected_source_ids as _controller_selected_source_ids
from .blender.selection import _proxy_selection as _proxy_selection
from .blender.selection import _select_proxy_ids as _select_proxy_ids
from .blender.selection import _select_source_ids as _select_source_ids
from .blender.selection import _source_positions as _source_positions
from .blender.selection import _source_selection as _source_selection
from .blender.workflows import WorkflowDeps as _WorkflowDeps
from .blender.workflows import deform_begin as _workflow_deform_begin
from .blender.workflows import deform_cancel as _workflow_deform_cancel
from .blender.workflows import deform_commit as _workflow_deform_commit
from .blender.workflows import deform_update as _workflow_deform_update
from .blender.workflows import write_source_positions as _workflow_write_source_positions
from .blender.workflows import mutate_control_visibility as _workflow_mutate_control_visibility
from .blender.workflows import mutate_control_masks as _workflow_mutate_control_masks
from .blender.workflows import mutate_masks as _workflow_mutate_masks
from .blender.workflows import prune_masks_after_remove as _workflow_prune_masks_after_remove
from .blender.workflows import sync_scene as _workflow_sync_scene
from .blender import lifecycle as _lifecycle
from .blender import transform_session as _transform_session
from .registration import register as _register_addon
from .registration import unregister as _unregister_addon
from . import operators as _operators
from .ui import overlay as _overlay

_bind_operators = _operators.bind
for _operator_name in _operators.__all__:
    if _operator_name != "bind":
        globals()[_operator_name] = getattr(_operators, _operator_name)
_bind_overlay = _overlay.bind
for _overlay_name in _overlay.__all__:
    if _overlay_name != "bind":
        globals()[_overlay_name] = getattr(_overlay, _overlay_name)
_bind_lifecycle = _lifecycle.bind
for _lifecycle_name in _lifecycle.__all__:
    if _lifecycle_name != "bind":
        globals()[_lifecycle_name] = getattr(_lifecycle, _lifecycle_name)
_bind_transform_session = _transform_session.bind


def _register_overlay() -> None:
    _overlay._register_overlay()
    globals()["OVERLAY_HANDLE"] = _overlay.OVERLAY_HANDLE


def _unregister_overlay() -> None:
    _overlay._unregister_overlay()
    globals()["OVERLAY_HANDLE"] = _overlay.OVERLAY_HANDLE

# The facade exports the shared runtime containers while the extraction is
# completed.  They are references to one state object, never a second cache or
# geometry store; new modules should access state through ``runtime`` directly.
OVERLAY_HANDLE = _runtime.OVERLAY_HANDLE
_SYNC_GUARD = _runtime.SYNC_GUARD
_UI_SYNC_GUARD = _runtime.UI_SYNC_GUARD
_MAPPING_CACHE = _runtime.MAPPING_CACHE
_UI_SIGNATURES = _runtime.UI_SIGNATURES
_ACTIVE_CONTROL_UUIDS = _runtime.ACTIVE_CONTROL_UUIDS
_RETURN_MODES = _runtime.RETURN_MODES
_PROXY_SNAPSHOTS = _runtime.PROXY_SNAPSHOTS
_TOPOLOGY_KEYMAPS = _runtime.TOPOLOGY_KEYMAPS
_CONTROL_KEYMAPS = _runtime.CONTROL_KEYMAPS
_NETWORK_CACHE = _runtime.NETWORK_CACHE
_PATCH_CACHE = _runtime.PATCH_CACHE
_PATCH_OVERLAY_CACHE = _runtime.PATCH_OVERLAY_CACHE
_FACE_CACHE = _runtime.FACE_CACHE
_OVERLAY_CACHE = _runtime.OVERLAY_CACHE
_XRAY_SHOW_IN_FRONT = _runtime.XRAY_SHOW_IN_FRONT
_PICK_PREVIEW = _runtime.PICK_PREVIEW
_DANP_TRANSACTIONS = _runtime.DANP_TRANSACTIONS
_NATIVE_TRANSFORM_SESSIONS = _runtime.NATIVE_TRANSFORM_SESSIONS
_NATIVE_UNDO_RECORDS = _runtime.NATIVE_UNDO_RECORDS
_TOPOLOGY_STATES = _runtime.TOPOLOGY_STATES
_MODIFIER_SIGNATURES = _runtime.MODIFIER_SIGNATURES

bl_info = {
    "name": "DANP Form",
    "author": "DANP Form",
    "version": (0, 5, 28),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DANP Form",
    "category": "Mesh",
    "description": "Source-backed controller shell for template mesh editing",
}


def _proxy_dependencies() -> _ProxyDeps:
    """Build the adapter bundle lazily after all facade helpers are defined."""
    return _ProxyDeps(
        validate_source_topology=_validate_source_topology,
        effective_proxy_elements=_effective_proxy_elements,
        source_id_maps=_source_id_maps,
        source_edge_vids=_source_edge_vids,
        source_vertices=_source_vertices,
        proxy_selection_snapshot=_proxy_selection_snapshot,
        select_proxy_ids=_select_proxy_ids,
    )


def _workflow_dependencies() -> _WorkflowDeps:
    return _WorkflowDeps(
        transactions=_DANP_TRANSACTIONS,
        overlay_cache=_OVERLAY_CACHE,
        patch_overlay_cache=_PATCH_OVERLAY_CACHE,
        validate_source_topology=_validate_source_topology,
        controller_selected_source_ids=_controller_selected_source_ids,
        source_positions=_source_positions,
        patch_partition=_patch_partition,
        effective_proxy_elements=_effective_proxy_elements,
        source_edge_vids=_source_edge_vids,
        source_id_maps=_source_id_maps,
        sync_proxy=_sync_proxy,
        control_intent=_control_intent,
        control_effective=_control_effective,
        controls=_controls,
        hidden=_hidden,
        json_set=_json_set,
        source_controller_pairs=_source_controller_pairs,
        modifier_signature=_modifier_signature,
    )


def _migrate_control_schema(source: bpy.types.Object) -> list[dict]:
    """Run storage migration with the current Source edge-ID map when available."""
    try:
        edge_vids = _source_edge_vids(source)
    except (KeyError, RuntimeError, ValueError):
        edge_vids = None
    return _storage_migrate_control_schema(source, edge_vids)

def _control_state(source: bpy.types.Object, control: dict) -> tuple[str, int, int]:
    effective_vertices, effective_edges = _control_effective(source, control)
    total = len(control.get("vertex_ids", [])) + len(control.get("edge_ids", []))
    effective = len(effective_vertices) + len(effective_edges)
    state = "On" if effective == total else ("Hidden" if effective == 0 else "Partial")
    return state, effective, total


def _active_control(context: bpy.types.Context, source: bpy.types.Object) -> dict | None:
    scene = context.scene
    items = getattr(scene, "dan_form_control_items", None)
    index = int(getattr(scene, "dan_form_control_index", 0))
    if items is not None and 0 <= index < len(items):
        item = items[index]
        if item.source_uuid == source.get(SOURCE_UUID_KEY):
            return _control(source, item.control_uuid)
    return _control(source, getattr(scene, "dan_form_selected_control", ""))


def _sync_ui_list(scene: bpy.types.Scene, source: bpy.types.Object | None) -> None:
    """Project persistent definitions into a native Blender UIList collection."""
    items = getattr(scene, "dan_form_control_items", None)
    if items is None:
        return
    source_uuid = str(source.get(SOURCE_UUID_KEY, "")) if source is not None else ""
    token = (source_uuid, source.get(CONTROLS_KEY, "") if source is not None else "", source.get(HIDDEN_VIDS_KEY, "") if source is not None else "", source.get(HIDDEN_EIDS_KEY, "") if source is not None else "", source.mode if source is not None else "")
    if _UI_SIGNATURES.get(scene.as_pointer()) == token:
        return
    controls = _controls(source) if source is not None and source_uuid else []
    signature = []
    for control in controls:
        state, effective_count, total_count = _control_state(source, control)
        signature.append((str(control.get("control_uuid", "")), str(control.get("name", "Control")), state, effective_count, total_count))
    current_signature = [
        (item.control_uuid, item.control_name, item.state, item.effective_count, item.total_count)
        for item in items
        if item.source_uuid == source_uuid
    ]
    current_source = getattr(scene, "dan_form_ui_source_uuid", "")
    if current_source == source_uuid and current_signature == signature and len(items) == len(controls):
        _UI_SIGNATURES[scene.as_pointer()] = token
        return
    active_uuid = _ACTIVE_CONTROL_UUIDS.get(source_uuid, "")
    if current_source == source_uuid:
        active_uuid = getattr(scene, "dan_form_selected_control", "") or active_uuid
    _runtime.UI_SYNC_GUARD = True
    try:
        items.clear()
        for control in controls:
            item = items.add()
            item.control_uuid = str(control.get("control_uuid", ""))
            item.source_uuid = source_uuid
            item.control_name = str(control.get("name", "Control"))
            item.state, item.effective_count, item.total_count = _control_state(source, control)
        scene.dan_form_ui_source_uuid = source_uuid
        selected_index = next((i for i, item in enumerate(items) if item.control_uuid == active_uuid), 0)
        scene.dan_form_control_index = selected_index if items else 0
        scene.dan_form_selected_control = items[scene.dan_form_control_index].control_uuid if items else ""
        _ACTIVE_CONTROL_UUIDS[source_uuid] = scene.dan_form_selected_control
        _UI_SIGNATURES[scene.as_pointer()] = token
    finally:
        _runtime.UI_SYNC_GUARD = False


def _sync_context_ui_list(context: bpy.types.Context) -> None:
    source, _ = _context_source(context)
    _sync_ui_list(context.scene, source)
    _activate_ui_control(context.scene, context.scene.dan_form_selected_control)


def _activate_ui_control(scene: bpy.types.Scene, control_uuid: str) -> None:
    """Keep the row and UUID aligned after a rebuild triggers synchronous handlers."""
    for index, item in enumerate(scene.dan_form_control_items):
        if item.control_uuid != control_uuid:
            continue
        previous_guard = _runtime.UI_SYNC_GUARD
        _runtime.UI_SYNC_GUARD = True
        try:
            if scene.dan_form_control_index != index:
                scene.dan_form_control_index = index
            _ACTIVE_CONTROL_UUIDS[item.source_uuid] = control_uuid
        finally:
            _runtime.UI_SYNC_GUARD = previous_guard
        return


def _set_scene_context(context: bpy.types.Context, source: bpy.types.Object | None, controller: bpy.types.Object | None) -> None:
    scene = context.scene
    scene.dan_form_source = source
    scene.dan_form_controller = controller
    _update_overlay_display(scene, context)


def _effective_proxy_elements(source: bpy.types.Object) -> tuple[list[int], list[int]]:
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY)
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY)
    vid_to_index, eid_to_index = _source_id_maps(source)
    cache_key = source.as_pointer()
    mapping = _MAPPING_CACHE[cache_key]
    token = (source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY))
    cached = _NETWORK_CACHE.get(cache_key)
    if cached is not None and cached[0] is mapping and cached[1] == token:
        return list(cached[2]), list(cached[3])
    vertices, edges = _core_effective_elements(
        _controls(source), set(vid_to_index), mapping[4], hidden_vids, hidden_eids
    )
    _NETWORK_CACHE[cache_key] = (mapping, token, vertices, edges)
    return list(vertices), list(edges)


def _control_intent(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    """Return edge and explicit-node intent for whole-definition actions."""
    _, edge_indices = _source_id_maps(source)
    return _core_control_intent(control, _source_edge_vids(source), set(edge_indices))


def _control_effective(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    _, edge_indices = _source_id_maps(source)
    return _core_control_effective(
        control,
        _source_edge_vids(source),
        _hidden(source, HIDDEN_VIDS_KEY),
        _hidden(source, HIDDEN_EIDS_KEY),
        set(edge_indices),
    )


def _source_face_records(source: bpy.types.Object) -> list[dict]:
    """Read Source faces using persistent vertex/edge IDs, never Blender indices."""
    vertex_ids, edge_ids = _source_id_maps(source)
    face_cache_token = (source.data.as_pointer(), source.get(TOPOLOGY_KEY, ""),
                        len(source.data.vertices), len(source.data.edges), len(source.data.polygons))
    cached = _FACE_CACHE.get(source.as_pointer())
    if cached is not None and cached[0] == face_cache_token:
        return cached[1]
    reverse_vertices = {index: vertex_id for vertex_id, index in vertex_ids.items()}
    reverse_edges = {index: edge_id for edge_id, index in edge_ids.items()}
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.faces.ensure_lookup_table()
        records = [
            {
                "face_id": "f:" + ":".join(str(reverse_vertices[v.index]) for v in sorted(face.verts, key=lambda item: reverse_vertices[item.index])),
                "vertex_ids": tuple(reverse_vertices[v.index] for v in face.verts),
                "edge_ids": tuple(reverse_edges[e.index] for e in face.edges),
            }
            for face in bm.faces
        ]
        _FACE_CACHE[source.as_pointer()] = (face_cache_token, records)
        return records
    edge_by_vertices = {
        frozenset(edge.vertices): int(reverse_edges[edge.index])
        for edge in source.data.edges
    }
    records = [
        {
            "face_id": "f:" + ":".join(str(reverse_vertices[index]) for index in sorted(polygon.vertices, key=lambda item: reverse_vertices[item])),
            "vertex_ids": tuple(reverse_vertices[index] for index in polygon.vertices),
            "edge_ids": tuple(edge_by_vertices[frozenset((polygon.vertices[index], polygon.vertices[(index + 1) % len(polygon.vertices)]))]
                               for index in range(len(polygon.vertices))),
        }
        for polygon in source.data.polygons
    ]
    _FACE_CACHE[source.as_pointer()] = (face_cache_token, records)
    return records


def _patch_partition(source: bpy.types.Object) -> dict:
    """Derive connected Source face patches after removing enabled control cuts.

    The result is runtime data. Face/vertex/edge identity comes from Source IDs;
    the partition is never stored as a second geometric truth.
    """
    mapping = _source_id_maps(source)
    mapping_token = (source.data.as_pointer(), source.get(TOPOLOGY_KEY, ""),
                     len(source.data.vertices), len(source.data.edges), len(source.data.polygons))
    faces = _source_face_records(source)
    controls_token = source.get(CONTROLS_KEY, "")
    hidden_vertices = source.get(HIDDEN_VIDS_KEY, "")
    hidden_edges = source.get(HIDDEN_EIDS_KEY, "")
    topology = source.get(TOPOLOGY_KEY, "")
    token = (mapping_token, topology, controls_token, hidden_vertices, hidden_edges,
             tuple((face["face_id"], face["edge_ids"]) for face in faces))
    cached = _PATCH_CACHE.get(source.as_pointer())
    if cached is not None and cached[0] == token:
        return cached[1]

    _, effective_edges = _effective_proxy_elements(source)
    cut_edges = set(effective_edges)
    control_incidence = []
    for control in _controls(source):
        effective_vertices, effective_control_edges = _control_effective(source, control)
        _, explicit_nodes = _control_intent(source, control)
        control_incidence.append((str(control.get("control_uuid")), effective_vertices,
                                  effective_control_edges, explicit_nodes))
    result = _core_partition_faces(
        faces,
        cut_edges,
        _controls(source),
        control_incidence,
        revision=int(source.get(NETWORK_REVISION_KEY, 0)),
    )
    _PATCH_CACHE[source.as_pointer()] = (token, result)
    return result


def _rebuild_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    return _proxy_rebuild(source, controller, _proxy_dependencies())


def _sync_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    return _proxy_sync(source, controller, _proxy_dependencies())


def _proxy_state(controller):
    return _proxy_state_impl(controller)


def _guard_proxy_topology(source, controller) -> bool:
    return _proxy_guard(source, controller, _proxy_dependencies())


def _patches_for_control(source: bpy.types.Object, control_uuid: str) -> list[dict]:
    """Return incident patches for Phase 4 scope capture and diagnostics."""
    partition = _patch_partition(source)
    ids = set(partition["control_patch_ids"].get(str(control_uuid), []))
    return [patch for patch in partition["patches"] if patch["patch_id"] in ids]


def _invalidate_patch_cache(source: bpy.types.Object | None = None) -> None:
    if source is None:
        _PATCH_CACHE.clear()
        _PATCH_OVERLAY_CACHE.clear()
        _FACE_CACHE.clear()
    else:
        _PATCH_CACHE.pop(source.as_pointer(), None)
        _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
        _FACE_CACHE.pop(source.as_pointer(), None)


def _deform_begin(source: bpy.types.Object, controller: bpy.types.Object) -> dict:
    return _workflow_deform_begin(source, controller, _workflow_dependencies())


def _write_source_positions(source: bpy.types.Object, positions: dict[int, Vector]) -> None:
    return _workflow_write_source_positions(source, positions, _workflow_dependencies())


def _deform_update(source: bpy.types.Object, controller: bpy.types.Object,
                   delta=(0.0, 0.0, 0.0), profile="LINEAR", radius=0.0,
                   targets: dict[int, Vector] | None = None,
                   sync_controller: bool = True,
                   operation_transform=None, selection_intent=None) -> dict:
    return _workflow_deform_update(
        source, controller, _workflow_dependencies(), delta, profile, radius, targets,
        sync_controller, operation_transform, selection_intent,
    )


def _deform_commit(source: bpy.types.Object) -> None:
    return _workflow_deform_commit(source, _workflow_dependencies())


def _deform_cancel(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    return _workflow_deform_cancel(source, controller, _workflow_dependencies())


def _mutate_masks(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], reveal: bool) -> bool:
    return _workflow_mutate_masks(source, vertex_ids, edge_ids, reveal, _workflow_dependencies())


def _mutate_control_visibility(source: bpy.types.Object, control: dict, reveal: bool) -> bool:
    return _workflow_mutate_control_visibility(source, control, reveal, _workflow_dependencies())


def _mutate_control_masks(source: bpy.types.Object, control: dict,
                          vertex_ids: set[int], edge_ids: set[int], reveal: bool) -> bool:
    return _workflow_mutate_control_masks(
        source, control, vertex_ids, edge_ids, reveal, _workflow_dependencies()
    )


def _prune_masks_after_remove(source: bpy.types.Object) -> None:
    return _workflow_prune_masks_after_remove(source, _workflow_dependencies())


def _sync_scene(scene: bpy.types.Scene) -> None:
    return _workflow_sync_scene(scene, _workflow_dependencies())


def register() -> None:
    _bind_overlay(sys.modules[__name__])
    _bind_operators(sys.modules[__name__])
    _bind_lifecycle(sys.modules[__name__])
    _bind_transform_session(sys.modules[__name__])
    return _register_addon(sys.modules[__name__])


def unregister() -> None:
    return _unregister_addon(sys.modules[__name__])


if __name__ == "__main__":
    register()
