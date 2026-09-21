"""Run in Blender on a disposable copy of a file with DANP controls."""

import bmesh
import bpy
import dan_form as addon


source, controller = addon._context_source(bpy.context)
assert source is not None and controller is not None
if controller.mode != "EDIT":
    addon._select_only(bpy.context, controller)
    bpy.ops.object.mode_set(mode="EDIT")

before = addon._source_positions(source)
selection_before = addon._proxy_selection_snapshot(controller)
layer_name = addon.PROXY_VID_ATTR
bm = bmesh.from_edit_mesh(controller.data)
bm.verts.ensure_lookup_table()
layer = bm.verts.layers.int.get(layer_name)
assert layer is not None and len(bm.verts) > 0
vertex_id = int(bm.verts[0][layer])
addon._runtime.SYNC_GUARD = True
try:
    bm.verts[0].co.x += 0.125
    bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
finally:
    addon._runtime.SYNC_GUARD = False

addon._rebuild_proxy(source, controller)
after = addon._transform_session.controller_positions(controller)
assert (after[vertex_id] - before[vertex_id]).length < 1e-7
assert all((after[key] - before[key]).length < 1e-7 for key in after)
assert all((addon._source_positions(source)[key] - before[key]).length < 1e-7 for key in before)
assert addon._proxy_selection_snapshot(controller) == selection_before
result = {"status": "PASS", "vertex_id": vertex_id, "controller_vertices": len(after)}
