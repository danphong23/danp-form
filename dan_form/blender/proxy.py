"""Controller proxy rebuild, coordinate sync and topology recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import bmesh
import bpy
from mathutils import Matrix

from .. import runtime
from ..constants import *


@dataclass(frozen=True)
class ProxyDeps:
    validate_source_topology: Callable
    effective_proxy_elements: Callable
    source_id_maps: Callable
    source_edge_vids: Callable
    source_vertices: Callable
    evaluated_source_positions: Callable
    proxy_selection_snapshot: Callable
    select_proxy_ids: Callable


def rebuild_proxy(source: bpy.types.Object, controller: bpy.types.Object, deps) -> None:
    previous_guard = runtime.SYNC_GUARD
    runtime.SYNC_GUARD = True
    try:
        runtime.OVERLAY_CACHE.clear()
        runtime.PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
        runtime.PICK_PREVIEW.clear()
        rebuild_proxy_impl(source, controller, deps)
        runtime.PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
        guard_proxy_topology(source, controller, deps)
    finally:
        runtime.SYNC_GUARD = previous_guard


def rebuild_proxy_impl(source: bpy.types.Object, controller: bpy.types.Object, deps) -> None:
    deps.validate_source_topology(source)
    vertex_ids, edge_ids = deps.effective_proxy_elements(source)
    deps.source_id_maps(source)
    proxy_mesh = controller.data
    selected_ids = deps.proxy_selection_snapshot(controller) if controller.mode == "EDIT" else (set(), set())
    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active is not None else "OBJECT"
    old_selected = [obj for obj in bpy.context.selected_objects]
    if controller.mode == "EDIT":
        # Blender cannot rebuild a Mesh datablock while its edit BMesh owns it.
        # Temporarily leave only the controller edit context, then restore it.
        bpy.ops.object.mode_set(mode="OBJECT")
    proxy_mesh.clear_geometry()
    source_positions = deps.evaluated_source_positions(source)
    edge_vids = deps.source_edge_vids(source)
    # Source's visible evaluated result owns displayed coordinates. A rebuilt
    # proxy must never revive an older, possibly stale edit pose.
    proxy_vertices = [tuple(source_positions[vid]) for vid in vertex_ids]
    proxy_vertex_index = {vid: index for index, vid in enumerate(vertex_ids)}
    proxy_edges = []
    kept_edge_ids = []
    for edge_id in edge_ids:
        endpoint_ids = edge_vids[edge_id]
        if all(endpoint in proxy_vertex_index for endpoint in endpoint_ids):
            proxy_edges.append(tuple(proxy_vertex_index[endpoint] for endpoint in endpoint_ids))
            kept_edge_ids.append(edge_id)
    proxy_mesh.from_pydata(proxy_vertices, proxy_edges, [])
    proxy_mesh.update()
    for attr_name in (PROXY_VID_ATTR, PROXY_EID_ATTR):
        old_attr = proxy_mesh.attributes.get(attr_name)
        if old_attr is not None:
            proxy_mesh.attributes.remove(old_attr)
    proxy_vid_attr = proxy_mesh.attributes.new(name=PROXY_VID_ATTR, type="INT", domain="POINT")
    for index, vertex_id in enumerate(vertex_ids):
        proxy_vid_attr.data[index].value = vertex_id
    proxy_eid_attr = proxy_mesh.attributes.new(name=PROXY_EID_ATTR, type="INT", domain="EDGE")
    for index, edge_id in enumerate(kept_edge_ids):
        proxy_eid_attr.data[index].value = edge_id
    controller.parent = source
    controller.matrix_parent_inverse = Matrix.Identity(4)
    controller.matrix_basis = Matrix.Identity(4)
    controller.display_type = "WIRE"
    controller.color = (0.05, 0.75, 1.0, 1.0)
    controller.show_wire = True
    controller.show_all_edges = True
    controller.hide_render = True
    controller[PROXY_GENERATION_KEY] = int(controller.get(PROXY_GENERATION_KEY, 0)) + 1
    proxy_mesh.update()
    if old_active is not None and old_active != controller and old_active.name in bpy.data.objects:
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in old_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = old_active
    if old_active == controller and old_mode == "EDIT" and controller.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = controller
        controller.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        deps.select_proxy_ids(controller, *selected_ids)


def sync_proxy(source: bpy.types.Object, controller: bpy.types.Object, deps) -> None:
    if controller is None or controller.data is None:
        return
    proxy_attr = controller.data.attributes.get(PROXY_VID_ATTR)
    if proxy_attr is None:
        return
    source_vids, _ = deps.source_id_maps(source)
    source_positions = deps.evaluated_source_positions(source)
    changed = False
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
        if layer is None:
            return
        for vert in bm.verts:
            vertex_id = int(vert[layer])
            position = source_positions.get(vertex_id)
            if vertex_id in source_vids and position is not None:
                if (vert.co - position).length_squared > 1e-16:
                    vert.co = position
                    changed = True
        if changed:
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
            guard_proxy_topology(source, controller, deps)
        return
    for index, item in enumerate(proxy_attr.data):
        vertex_id = int(item.value)
        position = source_positions.get(vertex_id)
        if vertex_id in source_vids and position is not None and index < len(controller.data.vertices):
            vert = controller.data.vertices[index]
            if (vert.co - position).length_squared > 1e-16:
                vert.co = position
                changed = True
    if changed:
        controller.data.update()
        guard_proxy_topology(source, controller, deps)


def proxy_state(controller):
    """Read ID connectivity and current coordinates; indices are never identity."""
    owned = controller.mode != "EDIT"
    bm = bmesh.new() if owned else bmesh.from_edit_mesh(controller.data)
    try:
        if owned:
            bm.from_mesh(controller.data)
        vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
        el = bm.edges.layers.int.get(PROXY_EID_ATTR)
        if vl is None or el is None or bm.faces:
            return None
        vertices = [(int(v[vl]), tuple(v.co), v.select, v.hide) for v in bm.verts]
        edges = [(int(e[el]), tuple(sorted(int(v[vl]) for v in e.verts)), e.select, e.hide) for e in bm.edges]
        return vertices, edges
    finally:
        if owned:
            bm.free()


def guard_proxy_topology(source, controller, deps) -> bool:
    """Reject native topology edits while preserving the last valid control pose.

    Only Source definitions/masks may rebuild proxy topology. Coordinate-only
    controller edits update a runtime recovery snapshot, never Source geometry.
    """
    key = controller.as_pointer()
    token = (controller.data.as_pointer(), controller.get(PROXY_GENERATION_KEY),
             source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY))
    snapshot = runtime.PROXY_SNAPSHOTS.get(key)
    if snapshot is None or snapshot[0] != token:
        deps.validate_source_topology(source)
        vids, eids = deps.effective_proxy_elements(source)
        vmap, emap = deps.source_id_maps(source)
        edge_vids = deps.source_edge_vids(source)
        source_vertices = deps.source_vertices(source)
        expected_edges = {eid: tuple(sorted(edge_vids[eid])) for eid in eids}
        vertices = [(vid, tuple(source_vertices[vmap[vid]].co), False, False) for vid in vids]
        edges = [(eid, expected_edges[eid], False, False) for eid in eids]
        snapshot = (token, set(vids), expected_edges, (vertices, edges))
    state = proxy_state(controller)
    if state is not None:
        vertices, edges = state
        valid = (len(vertices) == len(snapshot[1]) and len(edges) == len(snapshot[2])
                 and {v[0] for v in vertices} == snapshot[1]
                 and {e[0]: e[1] for e in edges} == snapshot[2])
        if valid:
            runtime.PROXY_SNAPSHOTS[key] = (*snapshot[:3], state)
            return False
    # A menu, tool or MCP call bypassed the shortcut guard. Restore in-place;
    # no mode switch or Source write is allowed inside the depsgraph callback.
    owned = controller.mode != "EDIT"
    bm = bmesh.new() if owned else bmesh.from_edit_mesh(controller.data)
    try:
        bm.clear()
        vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
        if vl is None:
            vl = bm.verts.layers.int.new(PROXY_VID_ATTR)
        el = bm.edges.layers.int.get(PROXY_EID_ATTR)
        if el is None:
            el = bm.edges.layers.int.new(PROXY_EID_ATTR)
        verts = {}
        for vid, co, selected, hidden in snapshot[3][0]:
            vert = bm.verts.new(co)
            vert[vl], vert.select, vert.hide = vid, selected, hidden
            verts[vid] = vert
        for eid, endpoints, selected, hidden in snapshot[3][1]:
            edge = bm.edges.new(tuple(verts[vid] for vid in endpoints))
            edge[el], edge.select, edge.hide = eid, selected, hidden
        if owned:
            bm.to_mesh(controller.data)
            controller.data.update()
        else:
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=True)
    finally:
        if owned:
            bm.free()
    runtime.PROXY_SNAPSHOTS[key] = snapshot
    bpy.context.scene.dan_form_status = "Controller chỉ chỉnh vị trí; tạo/xóa đường trên model"
    return True

