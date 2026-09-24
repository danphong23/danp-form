"""Blender Edit Mode selection and Source-position adapters."""

from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from ..constants import *
from .mesh import _source_edge_vids, _source_id_maps, _source_vertices, _validate_source_topology


def _source_selection(source: bpy.types.Object) -> tuple[set[int], set[int]]:
    if source.mode != "EDIT" or bpy.context.view_layer.objects.active != source:
        raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
    _validate_source_topology(source)
    bm = bmesh.from_edit_mesh(source.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    # BMesh lookup indices are transient; persistent DANP layers are canonical.
    # Refresh them before reading selection so agent/API calls never depend on
    # stale positional indices after topology/proxy rebuilds.
    bm.verts.index_update()
    bm.edges.index_update()
    vid_layer = bm.verts.layers.int.get(VID_ATTR)
    eid_layer = bm.edges.layers.int.get(EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("SOURCE_ID_LAYERS_MISSING")
    vertex_ids = {int(vert[vid_layer]) for vert in bm.verts if vert.select}
    edge_ids = {int(edge[eid_layer]) for edge in bm.edges if edge.select}
    for edge_id in edge_ids:
        edge = next(edge for edge in bm.edges if int(edge[eid_layer]) == edge_id)
        vertex_ids.update(int(vert[vid_layer]) for vert in edge.verts)
    if not vertex_ids and not edge_ids:
        raise ValueError("NO_SOURCE_SELECTION")
    return vertex_ids, edge_ids


def source_selection_snapshot(source: bpy.types.Object) -> dict[str, object]:
    """Return an agent-safe snapshot of the current Source selection.

    The public result deliberately exposes persistent DANP IDs, never transient
    ``BMVert.index``/``BMEdge.index`` values as the identity contract.  Raw
    Blender indices are included only as diagnostics so an external caller can
    explain a mismatch without accidentally persisting them.
    """
    vertex_ids, edge_ids = _source_selection(source)
    bm = bmesh.from_edit_mesh(source.data)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    bm.verts.index_update(); bm.edges.index_update()
    vid_layer = bm.verts.layers.int.get(VID_ATTR)
    eid_layer = bm.edges.layers.int.get(EID_ATTR)
    return {
        "source_uuid": str(source.get(SOURCE_UUID_KEY, "")),
        "topology_fingerprint": str(source.get(TOPOLOGY_KEY, "")),
        "persistent_vertex_ids": sorted(vertex_ids),
        "persistent_edge_ids": sorted(edge_ids),
        "mesh_vertex_indices": sorted(v.index for v in bm.verts if v.select),
        "mesh_edge_indices": sorted(e.index for e in bm.edges if e.select),
        "has_persistent_layers": bool(vid_layer and eid_layer),
    }


def _proxy_selection(controller: bpy.types.Object) -> tuple[set[int], set[int]]:
    if controller.mode != "EDIT" or bpy.context.view_layer.objects.active != controller:
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(controller.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    selected_vids = {int(vert[vid_layer]) for vert in bm.verts if vert.select}
    selected_eids = {int(edge[eid_layer]) for edge in bm.edges if edge.select}
    mode = tuple(bpy.context.tool_settings.mesh_select_mode)
    if mode[1]:
        selected_vids = set()
    if not selected_vids and not selected_eids:
        raise ValueError("NO_PROXY_SELECTION")
    return selected_vids, selected_eids


def _source_positions(source: bpy.types.Object, shape_key=None) -> dict[int, Vector]:
    """Return the current Source coordinates keyed by persistent vertex ID."""
    vids, _ = _source_id_maps(source)
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        layer = bm.verts.layers.int.get(VID_ATTR)
        return {int(v[layer]): v.co.copy() for v in bm.verts} if layer else {}
    vertices = _source_vertices(source)
    if source.mode == "OBJECT":
        if isinstance(shape_key, str) and shape_key == BASE_MESH_TARGET:
            vertices = source.data.vertices
        elif shape_key is not None:
            vertices = shape_key.data
    return {int(vid): vertices[index].co.copy() for vid, index in vids.items()}


def _controller_selected_source_ids(controller: bpy.types.Object) -> set[int]:
    """Resolve native controller vertex/edge selection to Source IDs."""
    if controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(controller.data)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
    el = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vl is None or el is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    selected = {int(v[vl]) for v in bm.verts if v.select and not v.hide}
    for edge in bm.edges:
        if edge.select and not edge.hide:
            selected.update(int(v[vl]) for v in edge.verts)
    if not selected:
        raise ValueError("NO_PROXY_SELECTION")
    return selected




def _select_source_ids(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], add: bool = False) -> None:
    if source.mode != "EDIT":
        raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(source.data)
    vid_layer = bm.verts.layers.int.get(VID_ATTR)
    eid_layer = bm.edges.layers.int.get(EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("SOURCE_ID_LAYERS_MISSING")
    if not add:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
    for vert in bm.verts:
        if int(vert[vid_layer]) in vertex_ids:
            vert.select = True
    for edge in bm.edges:
        if int(edge[eid_layer]) in edge_ids:
            edge.select = True
    bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)


def _select_proxy_ids(controller: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], add: bool = False) -> None:
    if controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(controller.data)
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    if not add:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
    for vert in bm.verts:
        if int(vert[vid_layer]) in vertex_ids:
            vert.select = True
    for edge in bm.edges:
        if int(edge[eid_layer]) in edge_ids:
            edge.select = True
    bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
