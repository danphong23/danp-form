"""Run through MCP in the open Blender session to verify Source alignment."""

import bmesh
import sys

import bpy


def run():
    candidates = [module for name, module in sys.modules.items()
                  if (name == "dan_form" or name.endswith(".dan_form"))
                  and hasattr(module, "_overlay_geometry")]
    addon = next((module for name, module in sys.modules.items()
                  if name == "bl_ext.user_default.dan_form"
                  and hasattr(module, "_overlay_geometry")), None)
    if addon is None:
        if len(candidates) != 1:
            raise RuntimeError("DANP Form module is not uniquely loaded")
        addon = candidates[0]

    source, controller = addon._context_source(bpy.context)
    if source is None or controller is None:
        raise RuntimeError("Active Source/controller pair is required")

    effective_vertices, effective_edges = addon._effective_proxy_elements(source)
    geometry = addon._overlay_geometry(bpy.context, "source", source, controller)
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        vid_layer = bm.verts.layers.int.get(addon.VID_ATTR)
        eid_layer = bm.edges.layers.int.get(addon.EID_ATTR)
        positions = {
            int(vertex[vid_layer]): source.matrix_world @ vertex.co
            for vertex in bm.verts
        }
        edge_vids = {
            int(edge[eid_layer]): tuple(int(vertex[vid_layer]) for vertex in edge.verts)
            for edge in bm.edges
        }
    else:
        positions = {
            int(vid): source.matrix_world @ source.data.vertices[index].co
            for vid, index in addon._source_id_maps(source)[0].items()
        }
        edge_vids = addon._source_edge_vids(source)

    expected_segments = {}
    display_modifiers = [modifier for modifier in source.modifiers
                          if modifier.show_viewport and modifier.show_in_editmode
                          and modifier.show_on_cage]
    if display_modifiers:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = source.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            edge_attribute = mesh.attributes.get(addon.EID_ATTR)
            if edge_attribute is None:
                raise AssertionError("Evaluated mesh lost persistent edge IDs")
            for edge, item in zip(mesh.edges, edge_attribute.data):
                edge_id = int(item.value)
                if edge_id in effective_edges:
                    expected_segments.setdefault(edge_id, []).append(tuple(
                        source.matrix_world @ mesh.vertices[index].co
                        for index in edge.vertices
                    ))
        finally:
            evaluated.to_mesh_clear()
    for edge_id in effective_edges:
        expected_segments.setdefault(edge_id, [tuple(positions[vid] for vid in edge_vids[edge_id])])
    expected = [position for edge_id in effective_edges
                for segment in expected_segments[edge_id]
                for position in segment]
    actual = geometry.get("edges", ())
    if len(actual) != len(expected):
        raise AssertionError("Source overlay did not emit one exact segment per base edge")
    if any((actual_position - expected_position).length > 1e-7
           for actual_position, expected_position in zip(actual, expected)):
        raise AssertionError("Source overlay diverges from the selected base Source edges")

    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        selection_snapshot = ([vertex.select for vertex in bm.verts],
                              [edge.select for edge in bm.edges])
        try:
            bpy.ops.mesh.select_all(action="DESELECT")
            cleared = addon._overlay_geometry(bpy.context, "source", source, controller)
            if cleared.get("selected_edges") or cleared.get("selected_points"):
                raise AssertionError("Clearing native Edit selection leaves a stale selected overlay")
        finally:
            bm = bmesh.from_edit_mesh(source.data)
            for vertex, selected in zip(bm.verts, selection_snapshot[0]):
                vertex.select = selected
            for edge, selected in zip(bm.edges, selection_snapshot[1]):
                edge.select = selected
            bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)

    return {
        "status": "PASS",
        "effective_vertices": len(effective_vertices),
        "effective_edges": len(effective_edges),
        "overlay_positions": len(actual),
        "source_mode": source.mode,
        "modifier_stack": [(modifier.name, modifier.type) for modifier in source.modifiers],
    }
