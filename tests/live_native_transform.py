"""MCP-only Controller Edit transform regression on the open test file.

The test runs Blender's native transform operator, lets the add-on observer
bridge it to Source, checks an adjacent control remains stationary, exercises
the paired Source undo/redo state, and restores geometry/context in ``finally``.
It never invokes Blender's global undo operator from an area-less MCP context.
"""

from __future__ import annotations

import bmesh
import bpy
import importlib
import sys


def _addon():
    return sys.modules.get("dan_form") or sys.modules.get("bl_ext.user_default.dan_form")


def _max_delta(left, right, ids=None):
    keys = set(left).intersection(right) if ids is None else set(ids).intersection(left).intersection(right)
    return max(((right[key] - left[key]).length for key in keys), default=0.0)


def _restore_controller(controller, positions, addon):
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(addon.PROXY_VID_ATTR)
        if layer is None:
            return
        for vertex in bm.verts:
            vertex_id = int(vertex[layer])
            if vertex_id in positions:
                vertex.co = positions[vertex_id]
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        return
    layer = controller.data.attributes.get(addon.PROXY_VID_ATTR)
    if layer is None:
        return
    for index, item in enumerate(layer.data):
        vertex_id = int(item.value)
        if vertex_id in positions and index < len(controller.data.vertices):
            controller.data.vertices[index].co = positions[vertex_id]
    controller.data.update()


def _finish_native(lifecycle, source):
    """Commit exactly at Blender's modal boundary; no quiet-poll loop."""
    lifecycle._native_transform_timer(source.as_pointer())


def run():
    addon = _addon()
    if addon is None:
        raise RuntimeError("DANP Form is not loaded")
    lifecycle = importlib.import_module(f"{addon.__name__}.blender.lifecycle")
    source, controller = addon._context_source(bpy.context)
    controls = addon._controls(source) if source is not None else []
    if source is None or controller is None or not controls:
        raise RuntimeError("Active Source/controller pair with a control is required")

    old_active = bpy.context.view_layer.objects.active
    old_selected = list(bpy.context.selected_objects)
    old_mode = old_active.mode if old_active else "OBJECT"
    old_select_mode = tuple(bpy.context.tool_settings.mesh_select_mode)
    old_control_uuid = bpy.context.scene.dan_form_selected_control
    old_status = bpy.context.scene.dan_form_status
    old_profile = bpy.context.scene.dan_form_proportional_profile
    old_radius = bpy.context.scene.dan_form_proportional_radius
    source_before = {key: value.copy() for key, value in addon._source_positions(source).items()}
    controller_before = None
    report = {"file": bpy.data.filepath, "dirty_before": bpy.data.is_dirty, "checks": []}

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        report["checks"].append(message)

    try:
        if old_active and old_active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        selected_vids, selected_eids = addon._control_effective(source, controls[0])
        adjacent_vids = set()
        if len(controls) > 1:
            adjacent_vids = set(addon._control_effective(source, controls[1])[0]) - set(selected_vids)
        addon._select_proxy_ids(controller, set(selected_vids), set(selected_eids))
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)
        bpy.context.scene.dan_form_proportional_profile = "SMOOTH"
        bpy.context.scene.dan_form_proportional_radius = 5.0
        controller_before = {
            key: value.copy() for key, value in addon._transform_session.controller_positions(controller).items()
        }

        native_result = bpy.ops.transform.translate(
            "EXEC_DEFAULT", value=(0.01, 0.0, 0.0), orient_type="GLOBAL"
        )
        bpy.context.view_layer.update()
        source_preview = addon._source_positions(source)
        check(native_result == {"FINISHED"}, "native Blender transform finishes")
        check(source.as_pointer() in addon._NATIVE_TRANSFORM_SESSIONS,
              "depsgraph observer starts native transform session")
        check(_max_delta(source_before, source_preview) > 1e-6,
              "native Controller transform deforms Source")
        check(_max_delta(source_before, source_preview, adjacent_vids) <= 1e-7,
              "adjacent unselected control remains stationary")
        nonselected_ids = set(source_before) - set(selected_vids) - set(adjacent_vids)
        check(_max_delta(source_before, source_preview, nonselected_ids) > 1e-6,
              "native proportional radius deforms nearby patch vertices")

        # The native operator has finished, so one timer sample reaches the
        # explicit Confirm boundary deterministically.
        _finish_native(lifecycle, source)
        check(source.as_pointer() not in addon._NATIVE_TRANSFORM_SESSIONS
              and source.as_pointer() not in addon._DANP_TRANSACTIONS,
              "native transform commits and closes runtime transaction")
        record = addon._NATIVE_UNDO_RECORDS.get(source.as_pointer())
        check(record is not None and record.get("state") == "committed",
              "commit records paired Source undo state")
        source_post = {key: value.copy() for key, value in record["source_post"].items()}

        # An unrelated Undo (for example Hide/Reveal) leaves the proxy at its
        # post-transform pose.  The paired restore must not mistake that step
        # for a transform Undo.
        lifecycle._restore_native_undo_records("UNDO")
        check(_max_delta(source_post, addon._source_positions(source)) <= 1e-7,
              "unrelated undo does not rewind the latest transform")

        # A real native transform Undo restores the controller pose first;
        # mirror that state before invoking the deferred Source repair.
        _restore_controller(controller, controller_before, addon)
        lifecycle._restore_native_undo_records("UNDO")
        check(_max_delta(source_before, addon._source_positions(source)) <= 1e-7,
              "paired undo restores Source exactly")
        _restore_controller(controller, record["controller_post"], addon)
        lifecycle._restore_native_undo_records("REDO")
        check(_max_delta(source_post, addon._source_positions(source)) <= 1e-7,
              "paired redo restores Source exactly")

        def native_variant(label, operator):
            variant_source = {key: value.copy() for key, value in addon._source_positions(source).items()}
            variant_controller = {
                key: value.copy()
                for key, value in addon._transform_session.controller_positions(controller).items()
            }
            result = operator()
            bpy.context.view_layer.update()
            preview = addon._source_positions(source)
            check(result == {"FINISHED"}, f"native {label} transform finishes")
            check(source.as_pointer() in addon._NATIVE_TRANSFORM_SESSIONS,
                  f"depsgraph observer starts native {label} session")
            check(_max_delta(variant_source, preview) > 1e-6,
                  f"native {label} transform deforms Source")
            check(_max_delta(variant_source, preview, adjacent_vids) <= 1e-7,
                  f"adjacent control remains stationary during {label}")
            _finish_native(lifecycle, source)
            check(source.as_pointer() not in addon._DANP_TRANSACTIONS,
                  f"native {label} transform commits")
            addon._runtime.SYNC_GUARD = True
            try:
                addon._write_source_positions(source, variant_source)
                _restore_controller(controller, variant_controller, addon)
            finally:
                addon._runtime.SYNC_GUARD = False
            addon._NATIVE_TRANSFORM_SESSIONS.pop(source.as_pointer(), None)
            addon._NATIVE_UNDO_RECORDS.pop(source.as_pointer(), None)
            addon._select_proxy_ids(controller, set(selected_vids), set(selected_eids))

        native_variant(
            "Rotate",
            lambda: bpy.ops.transform.rotate("EXEC_DEFAULT", value=0.05, orient_axis="Z"),
        )
        native_variant(
            "Scale",
            lambda: bpy.ops.transform.resize(
                "EXEC_DEFAULT", value=(1.01, 1.01, 1.01), orient_type="GLOBAL"
            ),
        )

        # Two confirmed Scale operations on the same control must compose from
        # the first committed pose.  The second preview must not rebuild from
        # the original controller rest (the historical scale-reset bug).
        consecutive_source = {
            key: value.copy() for key, value in addon._source_positions(source).items()
        }
        consecutive_controller = {
            key: value.copy()
            for key, value in addon._transform_session.controller_positions(controller).items()
        }
        bpy.ops.transform.resize("EXEC_DEFAULT", value=(1.03, 1.0, 1.0), orient_type="GLOBAL")
        bpy.context.view_layer.update()
        _finish_native(lifecycle, source)
        first_scale = {
            key: value.copy() for key, value in addon._source_positions(source).items()
        }
        bpy.ops.transform.resize("EXEC_DEFAULT", value=(1.04, 1.0, 1.0), orient_type="GLOBAL")
        bpy.context.view_layer.update()
        _finish_native(lifecycle, source)
        second_scale = addon._source_positions(source)
        check(_max_delta(first_scale, second_scale) > 1e-6,
              "consecutive native Scale starts from the committed pose")
        addon._runtime.SYNC_GUARD = True
        try:
            addon._write_source_positions(source, consecutive_source)
            _restore_controller(controller, consecutive_controller, addon)
        finally:
            addon._runtime.SYNC_GUARD = False
        addon._NATIVE_TRANSFORM_SESSIONS.pop(source.as_pointer(), None)
        addon._NATIVE_UNDO_RECORDS.pop(source.as_pointer(), None)
        addon._select_proxy_ids(controller, set(selected_vids), set(selected_eids))

        # Cancellation API: preview a second edit, then ensure both meshes
        # return to the committed pose without leaving a transaction behind.
        committed_controller = {
            key: value.copy() for key, value in addon._transform_session.controller_positions(controller).items()
        }
        deps = addon._workflow_dependencies()
        session = addon._transform_session.begin(source, controller, deps, "CANCEL_TEST")
        bm = bmesh.from_edit_mesh(controller.data)
        addon._runtime.SYNC_GUARD = True
        try:
            for vertex in bm.verts:
                if vertex.select and not vertex.hide:
                    vertex.co.y += 0.005
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        finally:
            addon._runtime.SYNC_GUARD = False
        addon._transform_session.update(source, controller, deps, session)
        check(_max_delta(source_post, addon._source_positions(source)) > 1e-6,
              "cancel test creates a live Source preview")
        addon._transform_session.cancel(source, controller, deps)
        check(_max_delta(source_post, addon._source_positions(source)) <= 1e-7,
              "cancel restores Source exactly")
        check(_max_delta(committed_controller,
                         addon._transform_session.controller_positions(controller)) <= 1e-7,
              "cancel restores Controller exactly")

        report.update({
            "status": "PASS",
            "native_result": sorted(native_result),
            "selected_vertices": len(selected_vids),
            "adjacent_only_vertices": len(adjacent_vids),
            "preview_delta": _max_delta(source_before, source_preview),
            "adjacent_stationary_error": _max_delta(source_before, source_preview, adjacent_vids),
        })
    finally:
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        addon._runtime.SYNC_GUARD = True
        try:
            addon._write_source_positions(source, source_before)
            if controller_before is not None:
                _restore_controller(controller, controller_before, addon)
        finally:
            addon._runtime.SYNC_GUARD = False
        key = source.as_pointer()
        addon._DANP_TRANSACTIONS.pop(key, None)
        addon._NATIVE_TRANSFORM_SESSIONS.pop(key, None)
        addon._NATIVE_UNDO_RECORDS.pop(key, None)
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in old_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if old_active and old_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = old_active
            if old_mode != "OBJECT":
                bpy.ops.object.mode_set(mode=old_mode)
        bpy.context.tool_settings.mesh_select_mode = old_select_mode
        bpy.context.scene.dan_form_selected_control = old_control_uuid
        bpy.context.scene.dan_form_proportional_profile = old_profile
        bpy.context.scene.dan_form_proportional_radius = old_radius
        addon._refresh_runtime()
        bpy.context.scene.dan_form_status = old_status
        report["dirty_after"] = bpy.data.is_dirty
        report["restored_active"] = old_active.name if old_active else None
        report["restored_mode"] = old_active.mode if old_active else None
        report["source_restore_error"] = _max_delta(source_before, addon._source_positions(source))
        report["runtime_clean"] = not (addon._DANP_TRANSACTIONS or addon._NATIVE_TRANSFORM_SESSIONS
                                       or addon._NATIVE_UNDO_RECORDS)
    return report


result = run()
