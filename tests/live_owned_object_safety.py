"""Blender background gate: stale DANP markers never auto-delete scene mesh data."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def run():
    addon.register()
    scene = bpy.context.scene
    checks = []
    not_run = []
    created = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def mesh_object(name):
        mesh = bpy.data.meshes.new(name + " | Mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        created.append(obj)
        return obj

    try:
        stale_controller = mesh_object("DANP Stale Controller Fixture")
        stale_controller[addon.CONTROLLER_KEY] = "missing-source-controller-uuid"
        stale_controller["dan_form_source_name"] = "Deleted Source Fixture"
        stale_controller.location = (2.0, 3.0, 4.0)
        stale_controller.data.vertices[0].co.x = 0.25
        controller_mesh = stale_controller.data

        stale_face = mesh_object("DANP Stale Face Fixture")
        stale_face[addon.FACE_SOURCE_UUID_KEY] = "missing-source-face-uuid"
        stale_face.location = (-2.0, 1.0, 0.5)
        face_mesh = stale_face.data

        bpy.context.view_layer.update()
        controller_before = [vertex.co.copy() for vertex in controller_mesh.vertices]
        face_before = [vertex.co.copy() for vertex in face_mesh.vertices]
        controller_world = stale_controller.matrix_world.copy()
        face_world = stale_face.matrix_world.copy()

        lifecycle = __import__(f"{addon.__name__}.blender.lifecycle", fromlist=["x"])
        lifecycle._load_post(None)
        check(stale_controller.name in bpy.data.objects and stale_face.name in bpy.data.objects,
              "load handler keeps stale owned objects")
        check(stale_controller.get(addon.ORPHANED_OWNED_KEY) is True
              and stale_face.get(addon.ORPHANED_OWNED_KEY) is True,
              "load handler marks stale ownership for repair")
        lifecycle._undo_post(None)
        check(stale_controller.name in bpy.data.objects and stale_face.name in bpy.data.objects,
              "undo handler keeps stale owned objects and their mesh data")
        depsgraph = bpy.context.evaluated_depsgraph_get()
        lifecycle._depsgraph_update_post(scene, depsgraph)
        check(stale_controller.name in bpy.data.objects, "depsgraph keeps stale Controller object")
        check(stale_face.name in bpy.data.objects, "depsgraph keeps stale face object")
        check(stale_controller.data is controller_mesh and stale_face.data is face_mesh,
              "depsgraph keeps both mesh datablocks")
        check(stale_controller.get(addon.ORPHANED_OWNED_KEY) is True
              and stale_face.get(addon.ORPHANED_OWNED_KEY) is True,
              "stale objects are marked for recovery")
        check(all((vertex.co - before).length == 0
                  for vertex, before in zip(controller_mesh.vertices, controller_before)),
              "Controller geometry remains unchanged")
        check(all((vertex.co - before).length == 0
                  for vertex, before in zip(face_mesh.vertices, face_before)),
              "face helper geometry remains unchanged")

        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        stale_controller.select_set(True)
        bpy.context.view_layer.objects.active = stale_controller
        check(bpy.ops.dan_form.unbind_stale_object() == {"FINISHED"},
              "explicit unbind recovery is available")
        recovery_class = addon.DANFORM_OT_unbind_orphaned_owned_object
        check("UNDO" in recovery_class.bl_options,
              "explicit unbind operator participates in Blender Undo")
        check(stale_controller.name in bpy.data.objects and stale_controller.data is controller_mesh,
              "explicit recovery preserves Controller mesh data")
        check(stale_controller.get(addon.CONTROLLER_KEY) is None
              and stale_controller.get(addon.ORPHANED_OWNED_KEY) is None
              and stale_controller.get(addon.UNBOUND_COPY_KEY) is True,
              "explicit recovery removes stale owner markers and leaves object unbound")
        check((stale_controller.matrix_world.translation - controller_world.translation).length < 1e-7,
              "explicit recovery preserves world transform")
        check(all((vertex.co - before).length == 0
                  for vertex, before in zip(controller_mesh.vertices, controller_before)),
              "explicit recovery preserves vertex coordinates")
        not_run.append("interactive panel click followed by Ctrl+Z; background fixture has no UI event loop")

        owner = bpy.data.objects.new("DANP Recovery Owner Fixture", bpy.data.meshes.new("DANP Recovery Owner Mesh"))
        scene.collection.objects.link(owner)
        owner[addon.SOURCE_UUID_KEY] = "missing-source-face-uuid"
        created.append(owner)
        lifecycle._cleanup_orphaned_owned_objects()
        check(stale_face.get(addon.ORPHANED_OWNED_KEY) is None,
              "stale warning clears when matching owner returns")
        check(stale_face.name in bpy.data.objects and stale_face.data is face_mesh,
              "reappearing owner does not replace or remove helper mesh")

        return {"status": "PASS", "checks": checks, "not_run": not_run,
                "blender_version": bpy.app.version_string}
    finally:
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in reversed(created):
            if obj.name in bpy.data.objects:
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data is not None and data.users == 0:
                    if data.bl_rna.identifier == "Mesh" and data.name in bpy.data.meshes:
                        bpy.data.meshes.remove(data)
        addon.unregister()


result = run()
print(result)
