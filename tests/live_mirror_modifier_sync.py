"""Run with Blender in the background to check Mirror sync during Edit Mode."""

from pathlib import Path
import sys

import bpy
import bmesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dan_form.blender.modifiers import sync_controller_modifiers


def mesh_object(name, vertices, edges=(), faces=()):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


source = mesh_object(
    "Source",
    [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)],
    faces=[(0, 1, 3, 2)],
)
controller = mesh_object(
    "Controller",
    [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)],
    edges=[(0, 1), (1, 3), (3, 2), (2, 0)],
)
mirror = source.modifiers.new("Mirror", "MIRROR")
mirror.use_clip = True
mirror.use_mirror_merge = True
mirror.merge_threshold = 0.002
source.modifiers.new("Subdivision", "SUBSURF")

first = sync_controller_modifiers(source, controller)
assert first["changed"]
assert first["copied"] == ("Mirror",)
assert first["skipped"] == ("Subdivision",)
assert len(controller.modifiers) == 1
assert not mirror.is_active and controller.modifiers[0].is_active

bpy.ops.object.select_all(action="DESELECT")
controller.select_set(True)
bpy.context.view_layer.objects.active = controller
bpy.ops.object.mode_set(mode="EDIT")

original_modifier = controller.modifiers[0].as_pointer()
second = sync_controller_modifiers(source, controller)
assert not second["changed"], "UI-active modifier state triggered a rebuild"
assert controller.modifiers[0].as_pointer() == original_modifier
assert controller.mode == "EDIT"

mirror.merge_threshold = 0.004
third = sync_controller_modifiers(source, controller)
assert third["changed"]
assert controller.mode == "EDIT"
assert abs(controller.modifiers[0].merge_threshold - 0.004) < 1e-6

fourth = sync_controller_modifiers(source, controller)
assert not fourth["changed"]
assert controller.mode == "EDIT"

# A native Controller transform must keep a selected seam vertex clipped.
bpy.ops.mesh.select_all(action="DESELECT")
bm = bmesh.from_edit_mesh(controller.data)
seam = next(vertex for vertex in bm.verts if abs(vertex.co.x) < 1e-7)
seam.select = True
bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
bpy.ops.transform.translate(value=(0.2, 0, 0))
assert abs(seam.co.x) < 1e-6, "native Mirror clipping released the seam"

print("MIRROR_SYNC_IDEMPOTENT_PASS")
