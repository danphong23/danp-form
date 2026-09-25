"""Blender background gate for native-style full Controller Scale samples.

Run with Blender 5.2: blender --background --factory-startup --python
tests/live_all_control_scale.py.  This fixture never opens the user's model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def run():
    addon.register()
    scene = bpy.context.scene
    original_active = bpy.context.view_layer.objects.active
    original_selected = list(bpy.context.selected_objects)
    mesh = bpy.data.meshes.new("DANP_ALL_SCALE_MESH")
    vertices = []
    faces = []
    for z in (10.123456, 20.654321):
        start = len(vertices)
        vertices.extend(((-1.4, -1.1, z), (1.3, -1.1, z),
                         (1.3, 1.2, z), (-1.4, 1.2, z), (0.0, 0.0, z + 1.0)))
        faces.extend((start + a, start + b, start + 4)
                     for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)))
    mesh.from_pydata(vertices, [], faces)
    source = bpy.data.objects.new("DANP_ALL_SCALE", mesh)
    scene.collection.objects.link(source)
    controller = None
    try:
        addon._select_only(bpy.context, source)
        assert bpy.ops.dan_form.initialize() == {"FINISHED"}
        controller = addon._find_controller(source)
        vids, _ = addon._source_id_maps(source)
        edge_vids = addon._source_edge_vids(source)
        selected_ids = set()
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        for start in (0, 5):
            ring = {vid for vid, index in vids.items() if index in range(start, start + 4)}
            ring_edges = {eid for eid, ends in edge_vids.items() if set(ends) <= ring}
            assert len(ring) == len(ring_edges) == 4
            addon._select_source_ids(source, ring, ring_edges)
            assert bpy.ops.dan_form.create_control() == {"FINISHED"}
            selected_ids.update(ring)
        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        addon._select_proxy_ids(controller, selected_ids, set())
        rest = {vid: co.copy() for vid, co in addon._source_positions(source).items()}
        assert len(rest) == 10 and len(selected_ids) == 8
        assert len(addon._patch_partition(source)["patches"]) == 2
        transaction = addon._deform_begin(source, controller)
        assert transaction["selected"] == selected_ids
        errors = {}
        for factor in (0.98, 0.7, 0.5, 1.0, 0.9, 0.4):
            # Vector stores each coordinate at Blender's float32 precision.
            targets = {vid: Vector(tuple(component * factor for component in rest[vid]))
                       for vid in selected_ids}
            addon._deform_update(source, controller, targets=targets,
                                 selection_intent=selected_ids, sync_controller=False)
            current = addon._source_positions(source)
            error = max((current[vid] - rest[vid] * factor).length for vid in rest)
            errors[str(factor)] = error
            assert error < 2e-5, (factor, error)
        addon._deform_cancel(source, controller)
        assert max((addon._source_positions(source)[vid] - rest[vid]).length
                   for vid in rest) < 1e-7
        return {"status": "PASS", "samples": errors, "patches": 2, "source_vertices": 10}
    finally:
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if controller is not None and controller.name in bpy.data.objects:
            proxy_mesh = controller.data
            bpy.data.objects.remove(controller, do_unlink=True)
            if proxy_mesh.users == 0:
                bpy.data.meshes.remove(proxy_mesh)
        bpy.data.objects.remove(source, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in original_selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = original_active
        addon.unregister()


print(json.dumps(run(), sort_keys=True))
