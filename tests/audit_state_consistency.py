"""Readiness audit probes, run only in a disposable background Blender process.

These probes report defects rather than certifying a release. Never execute this
script in a user's open scene. Run with --factory-startup --background --python;
an optional path after -- receives the JSON evidence. Convert repaired cases into
normal regression gates when their behavior contracts have been settled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import dan_form as addon
from dan_form import agent
from dan_form.operator_actions import structure as structure_operators
from dan_form.core.operation import OperationTransform, targets_from_transform


def invoke(operator, **kwargs):
    try:
        return {"result": sorted(operator(**kwargs))}
    except Exception as exc:
        return {"error": str(exc)}


def fixture():
    active = bpy.context.view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    addon._runtime.DANP_TRANSACTIONS.clear()
    addon._runtime.NATIVE_TRANSFORM_SESSIONS.clear()
    mesh = bpy.data.meshes.new("Audit disposable mesh")
    mesh.from_pydata(
        [(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (2, 0, 0), (2, 1, 0)],
        [], [(0, 2, 3, 1), (2, 4, 5, 3)],
    )
    source = bpy.data.objects.new("Audit disposable Source", mesh)
    bpy.context.scene.collection.objects.link(source)
    addon._select_only(bpy.context, source)
    assert bpy.ops.dan_form.initialize() == {"FINISHED"}
    # Isolate command semantics from the independent native-transform observer.
    addon._runtime.SYNC_GUARD = True
    bpy.ops.object.mode_set(mode="EDIT")
    vids, _ = addon._source_id_maps(source)
    by_index = {index: vid for vid, index in vids.items()}
    edge_vids = addon._source_edge_vids(source)
    for label, indices in (("A", (0, 1)), ("B", (4, 5))):
        vertices = {by_index[index] for index in indices}
        edges = {eid for eid, endpoints in edge_vids.items() if set(endpoints) == vertices}
        addon._select_source_ids(source, vertices, edges)
        assert bpy.ops.dan_form.create_control(control_name=label) == {"FINISHED"}
    bpy.ops.object.mode_set(mode="OBJECT")
    controller = addon._find_controller(source)
    addon._select_only(bpy.context, controller)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.tool_settings.mesh_select_mode = (True, False, False)
    controls = addon._controls(source)
    addon._activate_ui_control(bpy.context.scene, controls[0]["control_uuid"])
    bpy.context.scene.dan_form_selected_control = controls[0]["control_uuid"]
    return source, controller, controls


def run():
    if not bpy.app.background or bpy.data.filepath:
        raise RuntimeError("Run this audit only in background Blender with an unsaved factory-startup scene")
    observations = []

    def record(identifier, defect, **evidence):
        observations.append({"id": identifier, "status": "FAIL" if defect else "PASS", **evidence})

    addon.register()
    try:
        record("bind_preserves_module_metadata", addon._operators.__name__ != "dan_form.operators",
               expected_name="dan_form.operators", actual_name=addon._operators.__name__,
               actual_spec_name=addon._operators.__spec__.name)
        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        canonical_before = source[addon.CONTROLS_KEY]
        bpy.ops.mesh.hide(unselected=True)
        native_hidden = sum(v.hide for v in bmesh.from_edit_mesh(controller.data).verts)
        eye_before_reveal = addon._control_state(source, controls[1])[0]
        reveal = invoke(bpy.ops.dan_form.reveal)
        hidden_after_reveal = sum(v.hide for v in bmesh.from_edit_mesh(controller.data).verts)
        record("native_hide_reveal_reconciliation", not (
                   native_hidden > 0 and eye_before_reveal == "On"
                   and hidden_after_reveal == 0
                   and source[addon.CONTROLS_KEY] == canonical_before
                   and reveal.get("result") == ["FINISHED"]),
               hidden_before_reveal=native_hidden,
               eye_before_reveal=eye_before_reveal,
               hidden_after_reveal=hidden_after_reveal,
               reveal=reveal)

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        action = invoke(bpy.ops.dan_form.hide_unselected)
        remaining_a, _ = addon._control_effective(source, addon._control(source, controls[0]["control_uuid"]))
        remaining_b, _ = addon._control_effective(source, addon._control(source, controls[1]["control_uuid"]))
        record("shift_h_keeps_selected_control", not (
                   action.get("result") == ["FINISHED"]
                   and remaining_a == av and not remaining_b),
               action=action, selected_control_handles=len(av),
               remaining_a=len(remaining_a), remaining_b=len(remaining_b),
               raw_selection=[sorted(items) for items in addon._proxy_selection_snapshot(controller)],
               hidden_vertices=sorted(addon._hidden(source, addon.HIDDEN_VIDS_KEY)),
               definitions=addon._controls(source))

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        bv, be = addon._control_effective(source, controls[1])
        addon._select_proxy_ids(controller, av | bv, ae | be)
        action = invoke(bpy.ops.dan_form.hide_selected)
        remaining_b, _ = addon._control_effective(source, addon._control(source, controls[1]["control_uuid"]))
        record("hide_multiple_controls", bool(remaining_b), action=action,
               selected_vertices_before=len(av | bv), remaining_b_vertices=len(remaining_b))

        source, controller, controls = fixture()
        bv, be = addon._control_effective(source, controls[1])
        addon._select_proxy_ids(controller, bv, be)
        action = invoke(bpy.ops.dan_form.set_control_visibility,
                        control_uuid=controls[0]["control_uuid"], reveal=False)
        after_v, _ = addon._selected_source_elements(controller)
        record("eye_preserves_unrelated_selection", after_v != bv, action=action,
               selected_before=sorted(bv), selected_after=sorted(after_v))

        source, controller, controls = fixture()
        bpy.ops.object.mode_set(mode="OBJECT")
        actual = addon._selected_source_elements(source)
        record("empty_selection_return_contract", not isinstance(actual, tuple) or len(actual) != 2,
               returned_type=type(actual).__name__, returned_value=repr(actual))

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        operation = agent.begin_operation()
        agent.update_operation(operation["operation_id"], delta=(0, 0, 0.25))
        tx_key = source.as_pointer()
        preview = addon._source_positions(source)
        action = invoke(bpy.ops.dan_form.deform, delta=(0, 0, 0.1))
        after = addon._source_positions(source)
        preview_loss = max((after[vid] - co).length for vid, co in preview.items())
        record("busy_caller_preserves_owner", tx_key not in addon._DANP_TRANSACTIONS or preview_loss > 1e-7,
               second_caller=action, original_transaction_exists=tx_key in addon._DANP_TRANSACTIONS,
               source_preview_loss=preview_loss)

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        operation = agent.begin_operation()
        owner = addon._DANP_TRANSACTIONS[source.as_pointer()]
        try:
            native = addon._transform_session.begin(
                source, controller, addon._workflow_dependencies(), "NATIVE")
            native_rejected = False
            native_reused = native.get("transaction") is owner
        except ValueError as exc:
            native_rejected = str(exc) == "OPERATION_BUSY"
            native_reused = False
        record("native_transaction_owner", not (native_rejected and not native_reused),
               agent_operation_id=operation["operation_id"], native_rejected=native_rejected,
               native_reused_agent_transaction=native_reused)

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        current = addon._source_positions(source)
        effective = set(addon._effective_proxy_elements(source)[0])
        free_vid = next(vid for vid in current if vid not in effective)
        target = current[free_vid] + Vector((0, 0, 0.3))
        action = invoke(bpy.ops.dan_form.deform, targets_json=json.dumps({str(free_vid): list(target)}))
        displacement = (addon._source_positions(source)[free_vid] - current[free_vid]).length
        record("reject_unmapped_target", displacement > 1e-7, action=action,
               vertex_id=free_vid, controller_contains_target=free_vid in effective,
               displacement=displacement)

        source, controller, controls = fixture()
        before = source.get(addon.CONTROLS_KEY)
        # The compatibility facade re-exports registered operators, but the
        # extracted class resolves this helper in its owning domain module.
        rebuild = structure_operators._rebuild_proxy

        def failing_rebuild(*args):
            raise ValueError("AUDIT_INJECTED_REBUILD_FAILURE")

        structure_operators._rebuild_proxy = failing_rebuild
        try:
            action = invoke(bpy.ops.dan_form.delete_control, control_uuid=controls[0]["control_uuid"])
        finally:
            structure_operators._rebuild_proxy = rebuild
        record("delete_failure_atomicity", source.get(addon.CONTROLS_KEY) != before,
               action=action, definitions_before=len(controls), definitions_after=len(addon._controls(source)))

        action = None
        try:
            result = targets_from_transform(
                {1: Vector((1, 2, 3))}, {1}, OperationTransform(space="WORLD"),
                source_to_world=Matrix.Diagonal((0, 1, 1, 1)),
            )
            action = {"accepted": True, "target": list(result[1])}
        except (ValueError, RuntimeError) as exc:
            action = {"accepted": False, "error": str(exc)}
        record("reject_singular_world_frame", action["accepted"], action=action)

        source, controller, controls = fixture()
        av, ae = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, av, ae)
        agent.begin_operation()
    finally:
        addon._runtime.SYNC_GUARD = False
        addon.unregister()
    record("unregister_clears_transactions", bool(addon._runtime.DANP_TRANSACTIONS),
           transactions_after_unregister=len(addon._runtime.DANP_TRANSACTIONS))

    return {"status": "DEFECTS_FOUND" if any(o["status"] == "FAIL" for o in observations) else "PASS",
            "blender_version": bpy.app.version_string, "observations": observations,
            "scope": "disposable background process; no user blend file loaded or saved"}


if __name__ == "__main__":
    result = run()
    if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1:
        Path(sys.argv[sys.argv.index("--") + 1]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("DANP_AUDIT_JSON=" + json.dumps(result))
