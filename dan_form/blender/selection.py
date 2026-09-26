"""Blender Edit Mode selection and Source-position adapters."""

from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from ..constants import *
from .mesh import _resolve_shape_key, _source_edge_vids, _source_id_maps, _source_vertices, _validate_source_topology


def selected_source_elements(obj: bpy.types.Object) -> tuple[set[int], set[int]]:
    """Read selected mesh vertices/endpoints and edges as persistent IDs.

    This is a read-only UI projection helper.  Empty selection is a valid
    result, unlike the operation-oriented selection readers below.
    """
    if obj is None or obj.mode != "EDIT" or bpy.context.view_layer.objects.active != obj:
        return set()
    bm = bmesh.from_edit_mesh(obj.data)
    if obj.get(CONTROLLER_KEY) is not None:
        vertex_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
        edge_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
        if vertex_layer is None or edge_layer is None:
            return set(), set()
        result = {int(vertex[vertex_layer]) for vertex in bm.verts if vertex.select and not vertex.hide}
        selected_edges = set()
        for edge in bm.edges:
            if edge.select and not edge.hide:
                selected_edges.add(int(edge[edge_layer]))
                result.update(int(vertex[vertex_layer]) for vertex in edge.verts if not vertex.hide)
        return result, selected_edges
    vertex_layer = bm.verts.layers.int.get(VID_ATTR)
    edge_layer = bm.edges.layers.int.get(EID_ATTR)
    if vertex_layer is None or edge_layer is None:
        return set(), set()
    result = {int(vertex[vertex_layer]) for vertex in bm.verts if vertex.select and not vertex.hide}
    selected_edges = set()
    for edge in bm.edges:
        if edge.select and not edge.hide:
            selected_edges.add(int(edge[edge_layer]))
            result.update(int(vertex[vertex_layer]) for vertex in edge.verts if not vertex.hide)
    return result, selected_edges


def selected_source_vertex_ids(obj: bpy.types.Object) -> set[int]:
    """Return selected Source IDs, including endpoints of selected edges."""
    return selected_source_elements(obj)[0]


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
    key = _resolve_shape_key(source, shape_key)
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        id_layer = bm.verts.layers.int.get(VID_ATTR)
        if id_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        coordinate_layer = bm.verts.layers.shape.get(key.name) if key is not None else None
        if key is not None and coordinate_layer is None:
            raise ValueError("SHAPE_KEY_TARGET_INVALID")
        return {
            int(vert[id_layer]): (vert[coordinate_layer] if coordinate_layer else vert.co).copy()
            for vert in bm.verts
        }
    vertices = key.data if key is not None else source.data.vertices
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
