"""Background Blender integration gate for Source Shape Key targeting."""

from __future__ import annotations

import sys
import importlib
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


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


def _controller_positions(controller):
    layer = controller.data.attributes.get(addon.PROXY_VID_ATTR)
    if layer is None:
        raise AssertionError("controller proxy ID attribute missing")
    return {int(item.value): controller.data.vertices[index].co.copy()
            for index, item in enumerate(layer.data)}


def run():
    addon.register()
    scene = bpy.context.scene
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def reset_expected_failure():
        try:
            result = bpy.ops.dan_form.reset_source()
        except RuntimeError as exc:
            if "original Shape Key snapshot cannot be verified" not in str(exc):
                raise
            return {"CANCELLED"}
        return result

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

        # Target-aware I/O in Source Edit Mode must address an explicit key,
        # even while Blender's active edit key remains Basis.
        addon._select_only(bpy.context, source)
        bpy.ops.object.mode_set(mode="EDIT")
        source.active_shape_key_index = 0
        basis_edit_before = addon._source_positions(source, basis)
        expression_edit_before = addon._source_positions(source, expression)
        expression_edit_after = {
            vid: co + Vector((0.0, 0.0, 0.11))
            for vid, co in expression_edit_before.items()
        }
        addon._write_source_positions(source, expression_edit_after, shape_key=expression)
        check(all(_near(addon._source_positions(source, expression)[vid], co)
                  for vid, co in expression_edit_after.items()),
              "Source Edit Mode explicitly writes the requested expression key")
        check(all(_near(addon._source_positions(source, basis)[vid], co)
                  for vid, co in basis_edit_before.items()),
              "explicit Edit Mode key write leaves active Basis unchanged")
        addon._write_source_positions(source, expression_edit_before, shape_key=expression)
        bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"}, "control creation with Shape Keys")
        bpy.ops.object.mode_set(mode="OBJECT")

        # Idle Controller coordinates follow Blender's visible evaluated Source,
        # including Shape Key blending, instead of a selected key's stored data.
        lifecycle = importlib.import_module(f"{addon.__name__}.blender.lifecycle")
        runtime_state = importlib.import_module(f"{addon.__name__}.runtime")
        runtime_state.SHAPE_EVAL_SIGNATURES[source.as_pointer()] = addon._shape_key_evaluation_signature(source)
        source.active_shape_key_index = 1
        expression.value = 1.0
        bpy.context.view_layer.update()
        auto_synced = runtime_state.SHAPE_EVAL_SIGNATURES.get(source.as_pointer()) == addon._shape_key_evaluation_signature(source)
        lifecycle._depsgraph_update_post(scene, bpy.context.evaluated_depsgraph_get())
        check(auto_synced, "Blender depsgraph detects Shape Key value changes without an explicit sync action")
        visible_full = addon._evaluated_source_positions(source)
        proxy_full = _controller_positions(controller)
        check(all(_near(proxy_full[vid], co) for vid, co in visible_full.items()),
              "controller follows the visible full Shape Key pose")
        expression.value = 0.5
        bpy.context.view_layer.update()
        lifecycle._depsgraph_update_post(scene, bpy.context.evaluated_depsgraph_get())
        visible_half = addon._evaluated_source_positions(source)
        proxy_half = _controller_positions(controller)
        check(all(_near(proxy_half[vid], co) for vid, co in visible_half.items()),
              "controller follows the visible blended Shape Key pose")
        check(not all(_near(visible_half[vid], visible_full[vid]) for vid in visible_half),
              "partial key value produces an intermediate visible pose")

        # A topology-changing modifier duplicates the persistent Source IDs.
        # The Controller must still follow the evaluated Shape Key pose on the
        # Source cage, rather than fail or adopt the subdivided surface.
        subsurf = source.modifiers.new("DANP Test Subdivision", "SUBSURF")
        subsurf.levels = 2
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_source = source.evaluated_get(depsgraph)
        evaluated_mesh = evaluated_source.to_mesh(
            preserve_all_data_layers=True, depsgraph=depsgraph
        )
        try:
            check(len(evaluated_mesh.vertices) > len(source.data.vertices),
                  "Subdivision creates a topology-changing evaluated surface")
        finally:
            evaluated_source.to_mesh_clear()
        visible_subdivided = addon._evaluated_source_positions(source)
        addon._sync_proxy(source, controller)
        proxy_subdivided = _controller_positions(controller)
        source_vids, _ = addon._source_id_maps(source)
        expected_half = {
            vid: basis.data[index].co + 0.5 *
                 (expression.data[index].co - basis.data[index].co)
            for vid, index in source_vids.items()
        }
        check(len(visible_subdivided) == len(source.data.vertices),
              "topology-changing modifiers retain one coordinate per Source ID")
        check(all(_near(visible_subdivided[vid], expected_half[vid])
                  for vid in expected_half),
              "Subdivision fallback evaluates the real blended Shape Key pose")
        check(all(_near(proxy_subdivided[vid], co)
                  for vid, co in visible_subdivided.items()),
              "controller follows Shape Keys on the Source cage under Subdivision")

        expression.value = 0.0
        bpy.context.view_layer.update()
        lifecycle._depsgraph_update_post(scene, bpy.context.evaluated_depsgraph_get())
        visible_basis = addon._evaluated_source_positions(source)
        proxy_basis = _controller_positions(controller)
        check(all(_near(proxy_basis[vid], co) for vid, co in visible_basis.items()),
              "controller returns to the visible Basis pose when key value reaches zero")
        check(all(_near(visible_basis[vid], basis.data[index].co)
                  for vid, index in source_vids.items()),
              "Subdivision fallback evaluates stored Basis at value zero")
        expression.value = 1.0
        bpy.context.view_layer.update()
        lifecycle._depsgraph_update_post(scene, bpy.context.evaluated_depsgraph_get())
        visible_again = addon._evaluated_source_positions(source)
        proxy_again = _controller_positions(controller)
        check(all(_near(visible_again[vid], expression.data[index].co)
                  for vid, index in source_vids.items()),
              "Subdivision fallback evaluates stored expression after zero-to-one change")
        check(all(_near(proxy_again[vid], expression.data[source_vids[vid]].co)
                  for vid in proxy_again),
              "controller follows a zero-to-one Shape Key change under Subdivision")
        expression.value = 0.0
        bpy.context.view_layer.update()
        lifecycle._depsgraph_update_post(scene, bpy.context.evaluated_depsgraph_get())
        source.modifiers.remove(subsurf)
        source.active_shape_key_index = 0
        bpy.context.view_layer.update()
        addon._sync_proxy(source, controller)

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
        target_record = record.get("shape_key_target")
        check(isinstance(target_record, dict) and target_record.get("kind") == "KEY",
              "Undo history stores stable Shape Key identity instead of a KeyBlock reference")
        invalid_target_record = dict(target_record, pointer=target_record["pointer"] + 1)
        try:
            addon._source_positions(source, invalid_target_record)
            stale_target_rejected = False
        except ValueError as exc:
            stale_target_rejected = str(exc) == "SHAPE_KEY_TARGET_INVALID"
        check(stale_target_rejected,
              "Undo target identity fails closed when the captured key no longer resolves")
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
        # Restore historical key state while Source is in Edit Mode on Basis.
        addon._select_only(bpy.context, source)
        bpy.ops.object.mode_set(mode="EDIT")
        source.active_shape_key_index = 0
        _set_controller_pose(controller, record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")
        check(_near(addon._source_positions(source, expression)[vertex_id], committed_before),
              "Undo bridge writes its historical target while Source edits Basis")
        _set_controller_pose(controller, record["history"][-1]["controller_post"])
        lifecycle._restore_native_undo_records("REDO")
        check(_near(addon._source_positions(source, expression)[vertex_id], committed_after),
              "Redo bridge writes its historical target while Source edits Basis")
        bpy.ops.object.mode_set(mode="OBJECT")
        # Return to pre-edit state before continuing lock and target-switch gates.
        _set_controller_pose(controller, record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")

        # Absolute key stacks use the same explicit coordinate adapter and
        # must preserve key mode/evaluation frame.
        keys = source.data.shape_keys
        keys.use_relative = False
        keys.eval_time = 17.0
        source.active_shape_key_index = 1
        basis.interpolation = "KEY_LINEAR"
        expression.interpolation = "KEY_LINEAR"
        absolute_subsurf = source.modifiers.new("DANP Absolute Subdivision", "SUBSURF")
        absolute_subsurf.levels = 1
        keys.eval_time = 5.0
        bpy.context.view_layer.update()
        absolute_mid = addon._evaluated_source_positions(source)
        source_vids, _ = addon._source_id_maps(source)
        check(all(_near(absolute_mid[vid],
                        0.5 * (basis.data[index].co + expression.data[index].co))
                  for vid, index in source_vids.items()),
              "absolute Shape Key time blends on the Source cage under Subdivision")
        keys.eval_time = 17.0
        source.modifiers.remove(absolute_subsurf)
        absolute_before = addon._source_positions(source, expression)
        absolute_after = {vid: co + Vector((0.0, 0.0, 0.07))
                          for vid, co in absolute_before.items()}
        addon._write_source_positions(source, absolute_after, shape_key=expression)
        check(all(_near(addon._source_positions(source, expression)[vid], co)
                  for vid, co in absolute_after.items()),
              "absolute Shape Key stack writes the explicit key coordinates")
        check(not keys.use_relative and keys.eval_time == 17.0,
              "absolute key mode and evaluation time remain unchanged")
        addon._write_source_positions(source, absolute_before, shape_key=expression)
        addon._sync_proxy(source, controller)
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        addon._select_proxy_ids(controller, {vertex_id}, set())
        absolute_basis_before = basis.data[source_index].co.copy()
        absolute_expression_before = expression.data[source_index].co.copy()
        addon._deform_begin(source, controller)
        addon._deform_update(source, controller, delta=(0.0, 0.0, 0.06), radius=1.0)
        check(not _near(expression.data[source_index].co, absolute_expression_before),
              "controller deformation writes active absolute Shape Key")
        check(_near(basis.data[source_index].co, absolute_basis_before),
              "absolute Shape Key deformation leaves Basis unchanged")
        absolute_expression_after = expression.data[source_index].co.copy()
        addon._deform_commit(source)
        absolute_record = addon._NATIVE_UNDO_RECORDS[source.as_pointer()]
        _set_controller_pose(controller, absolute_record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")
        check(_near(expression.data[source_index].co, absolute_expression_before),
              "Undo bridge restores the stored absolute Shape Key")
        _set_controller_pose(controller, absolute_record["history"][-1]["controller_post"])
        lifecycle._restore_native_undo_records("REDO")
        check(_near(expression.data[source_index].co, absolute_expression_after),
              "Redo bridge reapplies the stored absolute Shape Key")
        _set_controller_pose(controller, absolute_record["history"][-1]["controller_pre"])
        lifecycle._restore_native_undo_records("UNDO")
        bpy.ops.object.mode_set(mode="OBJECT")
        runtime_state = importlib.import_module(f"{addon.__name__}.runtime")
        runtime_state.NATIVE_TRANSFORM_SESSIONS.clear()
        runtime_state.DANP_TRANSACTIONS.clear()
        keys.use_relative = True

        # Reset restores only a key proven in this session; after losing that
        # evidence (as on file reopen), it refuses before touching a replacement.
        source.active_shape_key_index = 0
        basis_reset_before = basis.data[source_index].co.copy()
        basis.data[source_index].co.z += 0.23
        addon._select_only(bpy.context, source)
        check(bpy.ops.dan_form.reset_source() == {"FINISHED"},
              "Reset Model restores the original captured Basis target")
        check(_near(basis.data[source_index].co, basis_reset_before),
              "Reset Model restores original Basis coordinates")
        for property_name in (addon.ORIGINAL_POSITIONS_KEY, addon.ORIGINAL_TOPOLOGY_KEY,
                              addon.ORIGINAL_TARGET_KIND_KEY,
                              addon.ORIGINAL_SHAPE_KEY_NAME_KEY):
            source.pop(property_name, None)
        source.active_shape_key_index = 1
        operators = importlib.import_module(f"{addon.__name__}.operators")
        operators._capture_original_snapshot(source)
        captured_expression = source.data.shape_keys.key_blocks[1]
        captured_expression.data[source_index].co.z += 0.19
        mutated = captured_expression.data[source_index].co.copy()
        # Replacing a captured key with a same-name key cannot inherit its
        # session proof. Simulate deletion/recreation after Init.
        source.shape_key_remove(captured_expression)
        lifecycle._validate_init_target_provenance()
        replacement = source.shape_key_add(name="Expression", from_mix=False)
        replacement.data[source_index].co = mutated.copy()
        expression = replacement
        expression_before = expression.data[source_index].co.copy()
        source.active_shape_key_index = 1
        check(reset_expected_failure() == {"CANCELLED"},
              "Reset Model rejects a same-name replacement Shape Key")
        check(_near(replacement.data[source_index].co, mutated),
              "failed Reset Model leaves replacement key unchanged")
        runtime = importlib.import_module(f"{addon.__name__}.runtime")
        runtime.INIT_TARGET_PROVENANCE.clear()
        replacement.data[source_index].co.z += 0.09
        reopened_state = replacement.data[source_index].co.copy()
        check(reset_expected_failure() == {"CANCELLED"},
              "Reset Model fails closed when saved key provenance is unavailable")
        check(_near(replacement.data[source_index].co, reopened_state),
              "unknown Reset provenance causes no key writes")
        expression_before = replacement.data[source_index].co.copy()

        # A key rename during a preview aborts the transaction; the explicit
        # captured key reference still allows a safe cancel of that preview.
        source.active_shape_key_index = 1
        addon._sync_proxy(source, controller)
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        addon._select_proxy_ids(controller, {vertex_id}, set())
        addon._deform_begin(source, controller)
        replacement.name = "Expression Renamed"
        try:
            addon._deform_update(source, controller, delta=(0.0, 0.0, 0.05))
        except ValueError as exc:
            check(str(exc) == "SHAPE_KEY_TARGET_CHANGED",
                  "renaming the target during preview aborts before another write")
        else:
            raise AssertionError("renamed Shape Key target remained writable")
        addon._deform_cancel(source, controller)
        check(_near(replacement.data[source_index].co, expression_before),
              "cancel restores the captured key after rename")
        replacement.name = "Expression"
        bpy.ops.object.mode_set(mode="OBJECT")

        expression.lock_shape = True
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
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
