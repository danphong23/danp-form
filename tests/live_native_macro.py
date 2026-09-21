"""Regression for the macro-owned native G/R/S transaction lifecycle.

This test intentionally simulates a long modal pause by polling the managed
timer while the controller remains displaced.  The timer may cancel a restored
rest pose, but it must never commit a non-zero macro preview.
"""

from __future__ import annotations

import bmesh
import bpy
import sys


def run():
    addon = sys.modules.get("bl_ext.user_default.dan_form") or sys.modules.get("dan_form")
    if addon is None:
        raise RuntimeError("DANP Form is not loaded")
    source, controller = addon._context_source(bpy.context)
    if source is None or controller is None or controller.mode != "EDIT":
        raise RuntimeError("Controller Edit context is required")
    bm = bmesh.from_edit_mesh(controller.data)
    controller_before = {v.index: v.co.copy() for v in bm.verts}
    selected_before = {v.index for v in bm.verts if v.select}
    source_before = {v.index: v.co.copy() for v in source.data.vertices}
    runtime = addon._runtime
    key = source.as_pointer()
    report = {"checks": []}

    def check(value, message):
        if not value:
            raise AssertionError(message)
        report["checks"].append(message)

    try:
        check(bpy.ops.dan_form.native_begin_move("EXEC_DEFAULT") == {"FINISHED"}, "macro Begin runs")
        check(bpy.ops.transform.translate("EXEC_DEFAULT", value=(0.01, 0.0, 0.0)) == {"FINISHED"}, "native child transform runs")
        bpy.context.view_layer.update()
        session = runtime.NATIVE_TRANSFORM_SESSIONS.get(key)
        check(session is not None and session.get("managed_by_macro"), "session is macro-managed")
        check(session.get("had_delta"), "session records a real preview delta")
        for _ in range(30):
            addon._lifecycle._native_transform_timer(key)
        check(key in runtime.NATIVE_TRANSFORM_SESSIONS and key in runtime.DANP_TRANSACTIONS,
              "long modal pause never auto-commits the preview")
        check(bpy.ops.dan_form.native_finish("EXEC_DEFAULT") == {"FINISHED"}, "macro Finish commits")
        check(key not in runtime.NATIVE_TRANSFORM_SESSIONS and key not in runtime.DANP_TRANSACTIONS,
              "Finish closes the single transaction")
        check(runtime.NATIVE_UNDO_RECORDS.get(key, {}).get("state") == "committed",
              "Finish records paired undo state")
        report["status"] = "PASS"
        return report
    finally:
        runtime.SYNC_GUARD = True
        try:
            bm = bmesh.from_edit_mesh(controller.data)
            for vertex in bm.verts:
                vertex.co = controller_before[vertex.index]
                vertex.select = vertex.index in selected_before
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
            for vertex in source.data.vertices:
                vertex.co = source_before[vertex.index]
            source.data.update()
        finally:
            runtime.SYNC_GUARD = False
        runtime.DANP_TRANSACTIONS.clear()
        runtime.NATIVE_TRANSFORM_SESSIONS.clear()
        runtime.NATIVE_UNDO_RECORDS.clear()


result = run()
