"""Background Blender regressions for operation ownership and target scope."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402
from dan_form import agent  # noqa: E402


def run():
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    addon.register()
    addon._runtime.SYNC_GUARD = True
    mesh = bpy.data.meshes.new("Operation ownership fixture")
    mesh.from_pydata(
        [(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (2, 0, 0), (2, 1, 0)],
        [], [(0, 2, 3, 1), (2, 4, 5, 3)],
    )
    source = bpy.data.objects.new("Operation ownership Source", mesh)
    bpy.context.scene.collection.objects.link(source)
    try:
        addon._select_only(bpy.context, source)
        assert bpy.ops.dan_form.initialize() == {"FINISHED"}
        bpy.ops.object.mode_set(mode="EDIT")
        vids, _ = addon._source_id_maps(source)
        by_index = {index: vid for vid, index in vids.items()}
        edge_vids = addon._source_edge_vids(source)
        vertices = {by_index[index] for index in (0, 1)}
        edges = {eid for eid, endpoints in edge_vids.items()
                 if set(endpoints) == vertices}
        addon._select_source_ids(source, vertices, edges)
        assert bpy.ops.dan_form.create_control(control_name="Owner") == {"FINISHED"}
        bpy.ops.object.mode_set(mode="OBJECT")
        controller = addon._find_controller(source)
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)
        control = addon._controls(source)[0]
        addon._activate_ui_control(bpy.context.scene, control["control_uuid"])
        addon._select_proxy_ids(controller, *addon._control_effective(source, control))

        handle = agent.begin_operation()
        agent.update_operation(handle["operation_id"], delta=(0, 0, 0.2))
        key = source.as_pointer()
        owner_tx = addon._DANP_TRANSACTIONS[key]
        preview = addon._source_positions(source)
        try:
            addon._deform_begin(source, controller)
        except ValueError as exc:
            busy_rejected = str(exc) == "OPERATION_BUSY"
        else:
            busy_rejected = False
        after = addon._source_positions(source)
        preview_delta = max((after[vid] - co).length for vid, co in preview.items())
        check(busy_rejected and addon._DANP_TRANSACTIONS.get(key) is owner_tx
              and preview_delta < 1e-7,
              "second caller is rejected without changing the agent preview")

        try:
            addon._transform_session.begin(source, controller,
                                           addon._workflow_dependencies(), "NATIVE")
        except ValueError as exc:
            native_rejected = str(exc) == "OPERATION_BUSY"
        else:
            native_rejected = False
        check(native_rejected and addon._DANP_TRANSACTIONS.get(key) is owner_tx,
              "native bridge rejects another caller's transaction")

        unmapped = next(vid for vid in addon._source_positions(source)
                        if vid not in addon._transform_session.controller_positions(controller))
        tx_preview = max((addon._source_positions(source)[vid] - owner_tx["p0"][vid]).length
                         for vid in owner_tx["p0"])
        try:
            addon._deform_update(source, controller,
                                 targets={unmapped: addon._source_positions(source)[unmapped]
                                          + Vector((0, 0, 0.3))})
        except ValueError as exc:
            target_rejected = str(exc) == "TARGET_OUTSIDE_CONTROLLER_MAPPING"
        else:
            target_rejected = False
        check(target_rejected and addon._DANP_TRANSACTIONS.get(key) is owner_tx
              and max((addon._source_positions(source)[vid] - owner_tx["p0"][vid]).length
                      for vid in owner_tx["p0"]) >= tx_preview - 1e-7,
              "unmapped target is rejected before touching the current preview")
        agent.cancel_operation(handle["operation_id"])

        definitions_before = source.get(addon.CONTROLS_KEY)
        revision_before = source.get(addon.NETWORK_REVISION_KEY)
        proxy_before = addon._transform_session.controller_positions(controller)
        rebuild = addon._operators._rebuild_proxy

        def injected_failure(*_args):
            raise ValueError("INJECTED_PROXY_REBUILD_FAILURE")

        addon._operators._rebuild_proxy = injected_failure
        try:
            try:
                delete_result = bpy.ops.dan_form.delete_control(
                    control_uuid=control["control_uuid"])
            except RuntimeError as exc:
                delete_result = {"CANCELLED"} if "INJECTED_PROXY_REBUILD_FAILURE" in str(exc) else set()
        finally:
            addon._operators._rebuild_proxy = rebuild
        proxy_after = addon._transform_session.controller_positions(controller)
        check(delete_result == {"CANCELLED"}
              and source.get(addon.CONTROLS_KEY) == definitions_before
              and source.get(addon.NETWORK_REVISION_KEY) == revision_before
              and addon._controls(source)[0]["control_uuid"] == control["control_uuid"]
              and set(proxy_after) == set(proxy_before)
              and all((proxy_after[vid] - co).length < 1e-7
                      for vid, co in proxy_before.items()),
              "failed Delete rolls back definitions, revision and proxy data")

        handle = agent.begin_operation()
        expected_rest = {vid: co.copy() for vid, co in
                         addon._DANP_TRANSACTIONS[source.as_pointer()]["p0"].items()}
        agent.update_operation(handle["operation_id"], delta=(0, 0, 0.15))
        addon.unregister()
        restored = addon._source_positions(source)
        check(not addon._DANP_TRANSACTIONS
              and max((restored[vid] - co).length for vid, co in expected_rest.items()) < 1e-7,
              "unregister cancels the active preview and clears transaction state")
        result = {"status": "PASS", "checks": checks,
                  "blender_version": bpy.app.version_string}
    finally:
        addon._runtime.SYNC_GUARD = False
        if addon._DANP_TRANSACTIONS or getattr(addon, "CLASSES", None):
            try:
                addon.unregister()
            except Exception:
                pass
    return result


result = run()
print("DANP_RESULT_JSON=" + __import__("json").dumps(result))
