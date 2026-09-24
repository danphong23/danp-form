"""Background Blender integration gate for Source Shape Key targeting."""

from __future__ import annotations

import sys
import importlib
from pathlib import Path

import bpy
import bmesh


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import dan_form as addon  # noqa: E402


def _near(left, right, epsilon=1e-7):
    return (left - right).length <= epsilon


def _set_controller_pose(controller, positions):
    """Apply Blender's native Undo/Redo proxy pose to the test controller."""
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(addon.PROXY_VID_ATTR)
        if layer is None:
            raise AssertionError("controller proxy ID layer missing")
        for vertex in bm.verts:
            vertex_id = int(vertex[layer])
            if vertex_id in positions:
                vertex.co = positions[vertex_id]
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        return
    layer = controller.data.attributes.get(addon.PROXY_VID_ATTR)
    if layer is None:
        raise AssertionError("controller proxy ID attribute missing")
    for index, item in enumerate(layer.data):
        vertex_id = int(item.value)
        if vertex_id in positions:
            controller.data.vertices[index].co = positions[vertex_id]


def run():
    addon.register()
    scene = bpy.context.scene
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    mesh = bpy.data.meshes.new("DANP Shape Key Gate Mesh")
    mesh.from_pydata(
        [(-1, 0, 0), (1, 0, 0), (1, 0, 2), (-1, 0, 2)],
        [], [(0, 1, 2, 3)],
    )
    source = bpy.data.objects.new("DANP Shape Key Gate Source", mesh)
    scene.collection.objects.link(source)
    controller = None

    try:
        basis = source.shape_key_add(name="Basis", from_mix=False)
        expression = source.shape_key_add(name="Expression", from_mix=False)
        expression.data[0].co.z += 0.3
        source.active_shape_key_index = 0
        addon._select_only(bpy.context, source)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "Init accepts Basis Shape Key")
        controller = addon._find_controller(source)

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"}, "control creation with Shape Keys")
        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")

        vertex_id = min(addon._source_id_maps(source)[0])
        source_index = addon._source_id_maps(source)[0][vertex_id]
        addon._select_proxy_ids(controller, {vertex_id}, set())
        base_mesh_before = mesh.vertices[source_index].co.copy()
        basis_before = basis.data[source_index].co.copy()
        expression_before = expression.data[source_index].co.copy()

        addon._deform_begin(source, controller)
        addon._deform_update(source, controller, delta=(0.0, 0.0, 0.2), radius=1.0)
        check(not _near(basis.data[source_index].co, basis_before), "Basis receives controller deformation")
        check(_near(expression.data[source_index].co, expression_before), "other Shape Key remains unchanged")
        check(_near(mesh.vertices[source_index].co, base_mesh_before), "Shape Key edit does not write base mesh")
        addon._deform_cancel(source, controller)
        check(_near(basis.data[source_index].co, basis_before), "cancel restores the targeted Basis")

        check(bpy.ops.dan_form.select_shape_key(key_index=1) == {"FINISHED"},
              "sidebar selector switches the Source target key")
        addon._sync_proxy(source, controller)
        expression_before = expression.data[source_index].co.copy()
        basis_before = basis.data[source_index].co.copy()
        addon._deform_begin(source, controller)
        addon._deform_update(source, controller, delta=(0.0, 0.0, 0.15), radius=1.0)
        check(not _near(expression.data[source_index].co, expression_before), "active expression receives controller deformation")
        check(_near(basis.data[source_index].co, basis_before), "editing expression leaves Basis unchanged")
        addon._deform_cancel(source, controller)
        check(_near(expression.data[source_index].co, expression_before), "cancel restores the targeted expression")

        committed_before = expression.data[source_index].co.copy()
        check(bpy.ops.dan_form.deform(delta=(0.0, 0.0, 0.08), radius=1.0) == {"FINISHED"},
              "operator commits deformation into the active expression")
        committed_after = expression.data[source_index].co.copy()
        check(not _near(committed_after, committed_before), "commit changes active key coordinates")
        record = addon._NATIVE_UNDO_RECORDS.get(source.as_pointer())
        check(bool(record), "Shape Key commit records the key-specific undo target")
        lifecycle = importlib.import_module(f"{addon.__name__}.blender.lifecycle")
        # Blender owns native G/R/S undo for the Controller. Reproduce the
        # resulting proxy pose here, then verify DANP repairs the corresponding
        # Shape Key state. Background tests cannot meaningfully undo live UI ops.
        _set_controller_pose(controller, record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")
        check(_near(expression.data[source_index].co, committed_before),
              "Undo bridge restores the edited key after controller undo")
        undone_record = addon._NATIVE_UNDO_RECORDS[source.as_pointer()]
        _set_controller_pose(controller, undone_record["history"][-1]["controller_post"])
        lifecycle._restore_native_undo_records("REDO")
        check(_near(expression.data[source_index].co, committed_after),
              "Redo bridge reapplies the edited key after controller redo")
        # Return to pre-edit state before continuing lock and target-switch gates.
        _set_controller_pose(controller, record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")

        expression.lock_shape = True
        try:
            addon._deform_begin(source, controller)
        except ValueError as exc:
            check(str(exc) == "SHAPE_KEY_LOCKED", "locked active key rejects deformation")
        else:
            raise AssertionError("locked Shape Key accepted deformation")
        check(_near(expression.data[source_index].co, expression_before), "locked key remains unchanged")
        expression.lock_shape = False

        source.active_shape_key_index = 0
        addon._sync_proxy(source, controller)
        p0 = addon._source_positions(source)
        addon._deform_begin(source, controller)
        source.active_shape_key_index = 1
        try:
            addon._deform_update(source, controller, delta=(0.0, 0.0, 0.1))
        except ValueError as exc:
            check(str(exc) == "SHAPE_KEY_TARGET_CHANGED", "mid-operation key switch is rejected")
        else:
            raise AssertionError("mid-operation Shape Key switch was accepted")
        addon._deform_cancel(source, controller)
        check(_near(basis.data[source_index].co, p0[vertex_id]), "cancel after target switch restores original key")

        source.active_shape_key_index = 1
        addon._sync_proxy(source, controller)
        source.show_only_shape_key = False
        addon._select_only(bpy.context, source)
        bpy.ops.object.mode_set(mode="OBJECT")
        check(bpy.ops.dan_form.focus_controller() == {"FINISHED"}, "focus controller with expression key")
        check(source.show_only_shape_key, "controller mode shows selected Shape Key clearly")
        check(bpy.ops.dan_form.focus_source() == {"FINISHED"}, "return to Source")
        check(not source.show_only_shape_key, "return restores prior Shape Key display setting")

        source.shape_key_clear()
        check(addon._active_shape_key(source) is None, "Source can remove all Shape Keys")
        addon._sync_proxy(source, controller)
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        addon._select_proxy_ids(controller, {vertex_id}, set())
        base_before = mesh.vertices[source_index].co.copy()
        addon._deform_begin(source, controller)
        addon._deform_update(source, controller, delta=(0.0, 0.0, 0.12), radius=1.0)
        check(not _near(mesh.vertices[source_index].co, base_before),
              "Controller edits base mesh after all Shape Keys are removed")
        addon._deform_cancel(source, controller)
        check(_near(mesh.vertices[source_index].co, base_before),
              "cancel restores base mesh after Shape Key removal")
        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, source)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"},
              "Create Control works after all Shape Keys are removed")
        check(len(addon._controls(source)) == 2,
              "control list contains the newly created no-key control")

        return {"status": "PASS", "checks": checks, "blender_version": bpy.app.version_string}
    finally:
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if controller is not None and controller.name in bpy.data.objects:
            controller_mesh = controller.data
            bpy.data.objects.remove(controller, do_unlink=True)
            if controller_mesh.users == 0:
                bpy.data.meshes.remove(controller_mesh)
        if source.name in bpy.data.objects:
            bpy.data.objects.remove(source, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        addon.unregister()


result = run()
print(result)
