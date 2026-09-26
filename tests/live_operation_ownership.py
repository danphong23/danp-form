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

    def fault_injected_mutation(label, source, controller, action):
        before = {
            "controls": source.get(addon.CONTROLS_KEY),
            "vertices": source.get(addon.HIDDEN_VIDS_KEY),
            "edges": source.get(addon.HIDDEN_EIDS_KEY),
            "revision": source.get(addon.NETWORK_REVISION_KEY),
            "proxy": addon._transform_session.controller_positions(controller),
        }
        rebuild = addon._operators._rebuild_proxy

        def injected_failure(*_args):
            raise ValueError("INJECTED_PROXY_REBUILD_FAILURE")

        addon._operators._rebuild_proxy = injected_failure
        try:
            try:
                result = action()
            except RuntimeError as exc:
                result = {"CANCELLED"} if "INJECTED_PROXY_REBUILD_FAILURE" in str(exc) else set()
        finally:
            addon._operators._rebuild_proxy = rebuild
        after = addon._transform_session.controller_positions(controller)
        check(result == {"CANCELLED"}
              and source.get(addon.CONTROLS_KEY) == before["controls"]
              and source.get(addon.HIDDEN_VIDS_KEY) == before["vertices"]
              and source.get(addon.HIDDEN_EIDS_KEY) == before["edges"]
              and source.get(addon.NETWORK_REVISION_KEY) == before["revision"]
              and set(after) == set(before["proxy"])
              and all((after[vid] - co).length < 1e-7
                      for vid, co in before["proxy"].items()),
              label)

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

        # Inject a rebuild failure in each mutation path after it has changed
        # persistent definitions or masks but before the proxy can be accepted.
        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, source)
        bpy.ops.object.mode_set(mode="EDIT")
        source_vids, _ = addon._source_id_maps(source)
        by_index = {index: vid for vid, index in source_vids.items()}
        source_edges = addon._source_edge_vids(source)
        added_vertices = {by_index[index] for index in (4, 5)}
        addon._select_source_ids(source, added_vertices, {
            eid for eid, endpoints in source_edges.items()
            if set(endpoints) == added_vertices
        })
        fault_injected_mutation(
            "failed Create rolls back definitions, revision and proxy",
            source, controller,
            lambda: bpy.ops.dan_form.create_control(control_name="Injected"),
        )

        addon._activate_ui_control(bpy.context.scene, control["control_uuid"])
        addon._select_source_ids(source, added_vertices, {
            eid for eid, endpoints in source_edges.items()
            if set(endpoints) == added_vertices
        })
        fault_injected_mutation(
            "failed Sync rolls back membership, revision and proxy",
            source, controller, lambda: bpy.ops.dan_form.sync_control(),
        )

        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        control_vertices, control_edges = addon._control_effective(source, control)
        addon._activate_ui_control(bpy.context.scene, control["control_uuid"])
        addon._select_proxy_ids(controller, control_vertices, control_edges)
        fault_injected_mutation(
            "failed Hide rolls back masks, revision and proxy",
            source, controller, lambda: bpy.ops.dan_form.hide_selected(),
        )
        fault_injected_mutation(
            "failed eye action rolls back definition visibility and proxy",
            source, controller,
            lambda: bpy.ops.dan_form.set_control_visibility(
                control_uuid=control["control_uuid"], reveal=False),
        )

        # Establish hidden state normally, then inject Reveal's rebuild failure.
        bpy.ops.dan_form.set_control_visibility(
            control_uuid=control["control_uuid"], reveal=False)
        fault_injected_mutation(
            "failed Reveal rolls back masks, revision and proxy",
            source, controller, lambda: bpy.ops.dan_form.reveal(),
        )

        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, source)
        source_uuid_before_reset = source.get(addon.SOURCE_UUID_KEY)
        fault_injected_mutation(
            "failed Reset restores definitions, masks, revision and proxy",
            source, controller, lambda: bpy.ops.dan_form.reset(),
        )
        check(addon._find_controller(source) is controller
              and source.get(addon.SOURCE_UUID_KEY) == source_uuid_before_reset
              and source.data.attributes.get(addon.VID_ATTR) is not None
              and source.data.attributes.get(addon.EID_ATTR) is not None,
              "failed Reset preserves original binding and Source identity layers")

        addon._select_only(bpy.context, controller)
        bpy.ops.object.mode_set(mode="EDIT")

        fault_injected_mutation(
            "failed Delete rolls back definitions, revision and proxy",
            source, controller,
            lambda: bpy.ops.dan_form.delete_control(
                control_uuid=control["control_uuid"]),
        )
        check(addon._controls(source)[0]["control_uuid"] == control["control_uuid"],
              "Delete rollback preserves the original control identity")

        bpy.ops.dan_form.reveal()
        addon._select_proxy_ids(controller, control_vertices, control_edges)
        handle = agent.begin_operation()
        expected_rest = {vid: co.copy() for vid, co in
                         addon._DANP_TRANSACTIONS[source.as_pointer()]["p0"].items()}
        agent.update_operation(handle["operation_id"], delta=(0, 0, 0.15))
        addon.unregister()
        restored = addon._source_positions(source)
        check(not addon._DANP_TRANSACTIONS
              and max((restored[vid] - co).length for vid, co in expected_rest.items()) < 1e-7,
              "unregister cancels the active preview and clears transaction state")

        addon.register()
        if bpy.context.view_layer.objects.active is not None \
                and bpy.context.view_layer.objects.active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(bpy.context, source)
        old_controller = addon._find_controller(source)
        old_controller_name = old_controller.name
        old_uuid = source.get(addon.SOURCE_UUID_KEY)
        reset_result = bpy.ops.dan_form.reset()
        new_controller = addon._find_controller(source)
        check(reset_result == {"FINISHED"} and new_controller is not None
              and new_controller is not old_controller
              and new_controller.parent == source
              and old_controller_name not in bpy.data.objects
              and source.get(addon.SOURCE_UUID_KEY) != old_uuid
              and not addon._controls(source),
              "successful Reset commits a new bound controller after construction")
        addon.unregister()
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
