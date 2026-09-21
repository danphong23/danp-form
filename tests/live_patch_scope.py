"""Live patch-scope checks for loop, edge and single-vertex selections."""

from __future__ import annotations

import bmesh
import bpy
import importlib
import sys


def _addon():
    return sys.modules.get("bl_ext.user_default.dan_form") or sys.modules.get("dan_form")


def _max_delta(left, right, ids=None):
    keys = set(left).intersection(right) if ids is None else set(ids).intersection(left).intersection(right)
    return max(((right[key] - left[key]).length for key in keys), default=0.0)


def run():
    addon = _addon()
    if addon is None:
        raise RuntimeError("DANP Form is not loaded")
    lifecycle = importlib.import_module(f"{addon.__name__}.blender.lifecycle")
    source, controller = addon._context_source(bpy.context)
    if source is None or controller is None or controller.mode != "EDIT":
        raise RuntimeError("Run from Controller Edit Mode")

    old_active = bpy.context.view_layer.objects.active
    old_selected = list(bpy.context.selected_objects)
    old_profile = bpy.context.scene.dan_form_proportional_profile
    old_radius = bpy.context.scene.dan_form_proportional_radius
    source_before = {key: value.copy() for key, value in addon._source_positions(source).items()}
    controller_before = {
        key: value.copy()
        for key, value in addon._transform_session.controller_positions(controller).items()
    }
    bm = bmesh.from_edit_mesh(controller.data)
    vl = bm.verts.layers.int.get(addon.PROXY_VID_ATTR)
    el = bm.edges.layers.int.get(addon.PROXY_EID_ATTR)
    if vl is None or el is None:
        raise RuntimeError("Proxy mapping missing")
    selected_before = ({int(v[vl]) for v in bm.verts if v.select}, {int(e[el]) for e in bm.edges if e.select})
    controls = addon._controls(source)
    selected_control = controls[-1]
    control_vertices, control_edges = addon._control_effective(source, selected_control)
    edge_id = sorted(control_edges)[0]
    edge_vertices = set(addon._source_edge_vids(source)[edge_id])
    cases = (
        ("loop", set(control_vertices), set(control_edges)),
        ("edge", edge_vertices, {edge_id}),
        ("vertex", {min(control_vertices)}, set()),
    )
    partition = addon._patch_partition(source)
    all_enabled = set(addon._effective_proxy_elements(source)[0])
    report = {"file": bpy.data.filepath, "dirty_before": bpy.data.is_dirty, "checks": [], "cases": []}

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        report["checks"].append(message)

    try:
        for label, selected_vertices, selected_edges in cases:
            addon._select_proxy_ids(controller, selected_vertices, selected_edges)
            p0 = {key: value.copy() for key, value in addon._source_positions(source).items()}
            op = bpy.ops.transform.translate("EXEC_DEFAULT", value=(0.01, 0.0, 0.0), orient_type="GLOBAL")
            bpy.context.view_layer.update()
            for _ in range(4):
                lifecycle._native_transform_timer(source.as_pointer())
            current = addon._source_positions(source)
            incident = {
                patch["patch_id"]
                for patch in partition["patches"]
                if selected_vertices.intersection(set(patch["vertex_ids"]))
            }
            rows = []
            changed_patch_ids = set()
            for patch in partition["patches"]:
                ids = set(patch["vertex_ids"])
                delta = _max_delta(p0, current, ids - selected_vertices)
                if delta > 1e-7:
                    changed_patch_ids.add(patch["patch_id"])
                rows.append({
                    "patch_id": patch["patch_id"],
                    "incident": patch["patch_id"] in incident,
                    "max_delta": delta,
                    "changed_vertices": sum(
                        (current[vid] - p0[vid]).length > 1e-7
                        for vid in ids - selected_vertices
                    ),
                })
            stationary_error = _max_delta(p0, current, all_enabled - selected_vertices)
            check(op == {"FINISHED"}, f"{label}: native transform finishes")
            check(changed_patch_ids.issubset(incident), f"{label}: no write outside incident patches")
            check(stationary_error <= 1e-7, f"{label}: unselected controls remain stationary")
            report["cases"].append({
                "name": label,
                "selected_vertices": len(selected_vertices),
                "selected_edges": len(selected_edges),
                "incident_patch_count": len(incident),
                "changed_patch_ids": sorted(changed_patch_ids),
                "stationary_error": stationary_error,
                "patches": rows,
            })

            addon._runtime.SYNC_GUARD = True
            try:
                addon._write_source_positions(source, p0)
                bm = bmesh.from_edit_mesh(controller.data)
                for vertex in bm.verts:
                    vertex_id = int(vertex[vl])
                    if vertex_id in controller_before:
                        vertex.co = controller_before[vertex_id]
                bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
            finally:
                addon._runtime.SYNC_GUARD = False
            addon._DANP_TRANSACTIONS.pop(source.as_pointer(), None)
            addon._NATIVE_TRANSFORM_SESSIONS.pop(source.as_pointer(), None)
            addon._NATIVE_UNDO_RECORDS.pop(source.as_pointer(), None)

        report["status"] = "PASS"
    finally:
        addon._runtime.SYNC_GUARD = True
        try:
            addon._write_source_positions(source, source_before)
            bm = bmesh.from_edit_mesh(controller.data)
            for vertex in bm.verts:
                vertex_id = int(vertex[vl])
                if vertex_id in controller_before:
                    vertex.co = controller_before[vertex_id]
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        finally:
            addon._runtime.SYNC_GUARD = False
        addon._select_proxy_ids(controller, *selected_before)
        addon._DANP_TRANSACTIONS.pop(source.as_pointer(), None)
        addon._NATIVE_TRANSFORM_SESSIONS.pop(source.as_pointer(), None)
        addon._NATIVE_UNDO_RECORDS.pop(source.as_pointer(), None)
        addon._refresh_runtime()
        bpy.context.scene.dan_form_proportional_profile = old_profile
        bpy.context.scene.dan_form_proportional_radius = old_radius
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in old_selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = old_active
        report["dirty_after"] = bpy.data.is_dirty
        report["restore_source_error"] = _max_delta(source_before, addon._source_positions(source))
        report["restore_controller_error"] = _max_delta(
            controller_before, addon._transform_session.controller_positions(controller)
        )
        report["runtime_clean"] = not (
            addon._DANP_TRANSACTIONS
            or addon._NATIVE_TRANSFORM_SESSIONS
            or addon._NATIVE_UNDO_RECORDS
        )
    return report


result = run()
