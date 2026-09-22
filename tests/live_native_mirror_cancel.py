"""Run in background Blender to check an Edit Control preview and cancel."""

from pathlib import Path
import sys

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dan_form


mesh = bpy.data.meshes.new("Half grid")
mesh.from_pydata(
    [(x, 0, z) for z in (0, 0.5, 1) for x in (0, 0.5, 1)],
    [],
    [(0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7)],
)
mesh.update()
source = bpy.data.objects.new("Half grid", mesh)
bpy.context.scene.collection.objects.link(source)
source.select_set(True)
bpy.context.view_layer.objects.active = source
mirror = source.modifiers.new("Mirror", "MIRROR")
mirror.use_clip = True
mirror.use_mirror_merge = True
source.modifiers.new("Subdivision", "SUBSURF")

dan_form.register()
assert bpy.ops.dan_form.initialize() == {"FINISHED"}
controller = dan_form._find_controller(source)
assert controller is not None

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
assert bpy.ops.dan_form.create_control() == {"FINISHED"}

bpy.ops.object.mode_set(mode="OBJECT")
source.select_set(False)
controller.select_set(True)
bpy.context.view_layer.objects.active = controller
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bm = bmesh.from_edit_mesh(controller.data)
point = max(bm.verts, key=lambda vertex: vertex.co.x)
point.select = True
bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
dan_form._guard_proxy_topology(source, controller)
snapshot = dan_form._PROXY_SNAPSHOTS[controller.as_pointer()]
source_rest = dan_form._source_positions(source)
controller_rest = dan_form._transform_session.controller_positions(controller)

point.co.y += 0.1
bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
dan_form._lifecycle._observe_native_controller_transform(source, controller, snapshot)
source_preview = dan_form._source_positions(source)
assert any((source_preview[key] - rest).length > 1e-5
           for key, rest in source_rest.items()), "preview did not reach Source"

# Blender's RMB/Esc cancel restores the native proxy pose before the observer
# sees the next update. Simulate that pose restoration, then run the observer.
bm = bmesh.from_edit_mesh(controller.data)
layer = bm.verts.layers.int.get(dan_form.PROXY_VID_ATTR)
for vertex in bm.verts:
    vertex.co = controller_rest[int(vertex[layer])]
bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
dan_form._lifecycle._native_transform_timer(source.as_pointer())

assert source.as_pointer() not in dan_form._NATIVE_TRANSFORM_SESSIONS
assert source.as_pointer() not in dan_form._DANP_TRANSACTIONS
assert all((dan_form._source_positions(source)[key] - rest).length < 1e-6
           for key, rest in source_rest.items()), "cancel left Source deformed"
assert all(abs(position.x) < 1e-6
           for key, position in dan_form._source_positions(source).items()
           if abs(source_rest[key].x) < 1e-6)

print("NATIVE_MIRROR_CANCEL_PASS")
