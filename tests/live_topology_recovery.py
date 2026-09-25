"""Blender background fixtures for explicit, fail-closed topology recovery."""

from __future__ import annotations

import bmesh
import bpy
import os
import itertools
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def run():
    addon.register()
    report = {"status": "RUNNING", "checks": []}

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        report["checks"].append(message)

    mesh = bpy.data.meshes.new("H07_SourceMesh")
    mesh.from_pydata(
        [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
        [(0, 1), (1, 2), (2, 3), (3, 0)],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    source = bpy.data.objects.new("H07_Source", mesh)
    bpy.context.scene.collection.objects.link(source)
    source[addon.SOURCE_UUID_KEY] = "h07-source-owner"
    controller_mesh = bpy.data.meshes.new("H07_ControllerMesh")
    controller = bpy.data.objects.new("DANPFORM_CTRL_H07_Source", controller_mesh)
    bpy.context.scene.collection.objects.link(controller)
    controller[addon.CONTROLLER_KEY] = "h07-source-owner"
    controller.parent = source
    controller[addon.PROXY_GENERATION_KEY] = 0
    bpy.context.view_layer.objects.active = source
    source.select_set(True)
    basis = source.shape_key_add(name="Basis")
    smile = source.shape_key_add(name="Smile")
    smile.data[0].co.z += 0.25
    smile.value = 0.7

    addon._ensure_source_ids(source)
    vertex_ids, edge_ids = addon._source_id_maps(source)
    edge = next(iter(edge_ids))
    control = {
        "control_uuid": "h07-control", "name": "Fixture edge", "enabled": True,
        "vertex_ids": [], "edge_ids": [edge], "hidden_vertex_ids": [], "hidden_edge_ids": [],
    }
    addon._json_set(source, addon.CONTROLS_KEY, [control])
    report["source"] = source.name
    report["shape_key_count"] = len(source.data.shape_keys.key_blocks)
    report["original_vertex_ids"] = sorted(vertex_ids)
    smile_before = {index: point.co.copy() for index, point in enumerate(smile.data)}
    basis_before = {index: point.co.copy() for index, point in enumerate(basis.data)}

    initial = addon._topology_repair_analysis(source)
    check(initial["safe"] and initial["protected_faces"] == 1,
          "unchanged Source topology validates against the control patch")

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(source.data)
    new_vertices = [bm.verts.new((3, 0, 0)), bm.verts.new((4, 0, 0)), bm.verts.new((3, 1, 0))]
    bm.faces.new(tuple(new_vertices))
    bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    safe_preview = addon._topology_repair_analysis(source)
    check(safe_preview["safe"] and safe_preview["added_vertices"] == 3
          and safe_preview["added_edges"] == 3,
          "disconnected unassigned geometry previews a safe repair")
    preserved_control = addon._controls(source)[0]
    bpy.ops.ed.undo_push(message="Topology before DANP Repair")
    validation_result = bpy.ops.dan_form.validate_topology()
    check(validation_result == {"FINISHED"}, "Validate action previews a safe repair")
    repair_result = bpy.ops.dan_form.repair_topology()
    check(repair_result == {"FINISHED"}, "Repair action rebuilds the DANP Controller")
    repaired = safe_preview
    report["undo_redo"] = "NOT RUN: Blender disables global undo in background mode"
    check(repaired["added_vertices"] == 3 and repaired["added_edges"] == 3,
          "repair reports exact additions")
    check(addon._topology_state(source)["state"] != "PAUSED",
          "successful repair refreshes topology state")
    check(addon._controls(source)[0] == preserved_control,
          "repair preserves control definition and masks")
    check(len({item.value for item in source.data.attributes[addon.VID_ATTR].data}) == len(source.data.vertices),
          "repair assigns unique persistent IDs to new vertices")
    check(len({item.value for item in source.data.attributes[addon.EID_ATTR].data}) == len(source.data.edges),
          "repair assigns unique persistent IDs to new edges")
    check(all((smile.data[index].co - value).length <= 1e-7 for index, value in smile_before.items()),
          "repair leaves existing Shape Key coordinates unchanged")
    check(all((basis.data[index].co - value).length <= 1e-7 for index, value in basis_before.items()),
          "repair leaves Basis coordinates unchanged")

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(source.data)
    distant = [vertex for vertex in bm.verts if vertex.co.x > 2.0]
    bmesh.ops.delete(bm, geom=distant, context="VERTS")
    bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    delete_preview = addon._topology_repair_analysis(source)
    check(delete_preview["safe"] and delete_preview["removed_vertices"] == 3
          and delete_preview["removed_edges"] == 3,
          "deleting a disconnected component previews a safe repair")
    deleted_repair = addon._repair_source_topology(source)
    check(deleted_repair["removed_vertices"] == 3 and deleted_repair["removed_edges"] == 3,
          "repair accepts deletion outside protected control patches")

    save_path = os.path.join(tempfile.gettempdir(), "danp_h07_topology_recovery.blend")
    bpy.ops.wm.save_as_mainfile(filepath=save_path, check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=save_path, load_ui=False)
    source = bpy.data.objects.get("H07_Source")
    check(source is not None and addon._topology_repair_analysis(source)["safe"],
          "recovery snapshot survives save and reopen")
    try:
        os.remove(save_path)
    except OSError:
        pass

    def create_case(name):
        case_mesh = bpy.data.meshes.new(name + "Mesh")
        case_mesh.from_pydata(
            [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
            [(0, 1), (1, 2), (2, 3), (3, 0)], [(0, 1, 2, 3)],
        )
        case_mesh.update()
        case_source = bpy.data.objects.new(name, case_mesh)
        bpy.context.scene.collection.objects.link(case_source)
        case_source[addon.SOURCE_UUID_KEY] = name + "-owner"
        addon._ensure_source_ids(case_source)
        _vertex_ids, case_edge_ids = addon._source_id_maps(case_source)
        addon._json_set(case_source, addon.CONTROLS_KEY, [{
            "control_uuid": name + "-control", "name": "Fixture edge", "enabled": True,
            "vertex_ids": [], "edge_ids": [next(iter(case_edge_ids))],
            "hidden_vertex_ids": [], "hidden_edge_ids": [],
        }])
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        case_source.select_set(True)
        bpy.context.view_layer.objects.active = case_source
        return case_source

    count_source = create_case("H07_CountPreservingSource")
    control_edge_id = int(addon._controls(count_source)[0]["edge_ids"][0])
    bpy.context.view_layer.objects.active = count_source
    count_source.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(count_source.data)
    edge_layer = bm.edges.layers.int.get(addon.EID_ATTR)
    face = next(face for face in bm.faces if len(face.verts) == 4)
    original_loop = list(face.verts)
    controlled_edge = next(edge for edge in bm.edges if int(edge[edge_layer]) == control_edge_id)
    controlled_pair = frozenset(controlled_edge.verts)
    counts_before = (len(bm.verts), len(bm.edges), len(bm.faces))
    new_loop = next(
        permutation for permutation in itertools.permutations(original_loop)
        if frozenset(permutation[:2]) == controlled_pair
        and {frozenset((permutation[index], permutation[(index + 1) % 4]))
             for index in range(4)} !=
            {frozenset((original_loop[index], original_loop[(index + 1) % 4]))
             for index in range(4)}
    )
    old_edges = list(face.edges)
    new_edge_pairs = {frozenset((new_loop[index], new_loop[(index + 1) % 4]))
                      for index in range(4)}
    bmesh.ops.delete(bm, geom=[face], context="FACES_ONLY")
    for old_edge in old_edges:
        if frozenset(old_edge.verts) not in new_edge_pairs:
            bm.edges.remove(old_edge)
    bm.faces.new(new_loop)
    bmesh.update_edit_mesh(count_source.data, loop_triangles=False, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    counts_after = (len(count_source.data.vertices), len(count_source.data.edges), len(count_source.data.polygons))
    check(counts_before == counts_after,
          "count-preserving connectivity fixture retains vertex/edge/face counts")
    try:
        addon._topology_repair_analysis(count_source)
    except ValueError as exc:
        check(str(exc) == "STALE_MAPPING", "connectivity change with unchanged counts is rejected")
    else:
        raise AssertionError("count-preserving connectivity change was accepted")

    deleted_edge_source = create_case("H07_DeletedControlEdgeSource")
    control_edge_id = int(addon._controls(deleted_edge_source)[0]["edge_ids"][0])
    bpy.context.view_layer.objects.active = deleted_edge_source
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(deleted_edge_source.data)
    edge_layer = bm.edges.layers.int.get(addon.EID_ATTR)
    deleted_edge = next(edge for edge in bm.edges if int(edge[edge_layer]) == control_edge_id)
    bmesh.ops.delete(bm, geom=[deleted_edge], context="EDGES_FACES")
    bmesh.update_edit_mesh(deleted_edge_source.data, loop_triangles=False, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    try:
        addon._topology_repair_analysis(deleted_edge_source)
    except ValueError as exc:
        check(str(exc) == "STALE_MAPPING", "deleting a control edge is rejected")
    else:
        raise AssertionError("deleted control edge was accepted")
    bpy.data.objects.remove(count_source, do_unlink=True)
    bpy.data.objects.remove(deleted_edge_source, do_unlink=True)

    # Retopologize the controlled quad in place. Its original face signature
    # disappears and the new faces touch the protected control patch.
    for selected in bpy.context.selected_objects:
        selected.select_set(False)
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    disabled_control = addon._controls(source)[0]
    disabled_control["enabled"] = False
    addon._json_set(source, addon.CONTROLS_KEY, [disabled_control])
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(source.data)
    id_layer = bm.verts.layers.int.get(addon.VID_ATTR)
    quad = next(face for face in bm.faces if all(int(vertex[id_layer]) in set(report["original_vertex_ids"])
                                                 for vertex in face.verts))
    quad_vertices = list(quad.verts)
    center = bm.verts.new(sum((vertex.co for vertex in quad_vertices), start=quad.verts[0].co.copy()) / 4.0)
    bmesh.ops.delete(bm, geom=[quad], context="FACES_ONLY")
    for index in range(4):
        bm.faces.new((quad_vertices[index], quad_vertices[(index + 1) % 4], center))
    bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    before_failed_repair = [tuple(vertex.co) for vertex in source.data.vertices]
    before_failed_ids = [int(item.value) for item in source.data.attributes[addon.VID_ATTR].data]
    try:
        addon._repair_source_topology(source)
    except ValueError as exc:
        check(str(exc) == "STALE_MAPPING",
              "loop cut in a disabled control patch is still rejected")
    else:
        raise AssertionError("loop cut in a protected control patch was accepted")
    check(before_failed_repair == [tuple(vertex.co) for vertex in source.data.vertices]
          and before_failed_ids == [int(item.value) for item in source.data.attributes[addon.VID_ATTR].data],
          "failed patch repair changes neither Source coordinates nor IDs")

    # A copied persistent ID has no safe winner; validate refuses to guess.
    attr = source.data.attributes[addon.VID_ATTR]
    saved = int(attr.data[0].value)
    attr.data[0].value = int(attr.data[1].value)
    try:
        addon._topology_repair_analysis(source)
    except ValueError as exc:
        check(str(exc) == "STALE_MAPPING", "duplicate persistent ID is rejected as ambiguous")
    else:
        raise AssertionError("duplicate persistent ID was accepted")
    attr.data[0].value = saved

    report["status"] = "PASS"
    report["checks_count"] = len(report["checks"])
    return report


result = run()
