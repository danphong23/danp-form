"""Background integration checks for the target-aware agent facade."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402
from dan_form import agent  # noqa: E402


def _make_source(name: str, with_keys: bool = True):
    mesh = bpy.data.meshes.new(f"{name} | Mesh")
    mesh.from_pydata(
        [(-1, 0, 0), (1, 0, 0), (1, 0, 2), (-1, 0, 2)],
        [], [(0, 1, 2, 3)],
    )
    source = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(source)
    if with_keys:
        source.shape_key_add(name="Basis", from_mix=False)
        smile = source.shape_key_add(name="Smile", from_mix=False)
        smile.data[0].co.z += 0.2
        smile.data[1].co.z += 0.2
        blink = source.shape_key_add(name="Blink", from_mix=False)
        blink.data[2].co.z -= 0.1
        blink.lock_shape = True
        source.active_shape_key_index = 1
    _select_only(source)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    assert bpy.ops.dan_form.initialize() == {"FINISHED"}
    assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}
    bpy.ops.mesh.select_all(action="SELECT")
    assert bpy.ops.dan_form.create_control(control_name="Agent Test") == {"FINISHED"}
    assert bpy.ops.object.mode_set(mode="OBJECT") == {"FINISHED"}
    return source, addon._find_controller(source)


def _enter_controller_edit(source, controller):
    _select_only(controller)
    assert bpy.ops.object.mode_set(mode="EDIT") == {"FINISHED"}


def _select_only(obj):
    for candidate in bpy.context.view_layer.objects:
        if candidate is not None:
            candidate.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _close_controller_edit():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _assert_error(code, callback):
    try:
        callback()
    except ValueError as exc:
        assert str(exc) == code, (str(exc), code)
        return
    raise AssertionError(f"expected {code}")


def run():
    addon.register()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    checks = []
    first = second = None
    try:
        source, controller = _make_source("Agent Source A")
        first = (source, controller)
        targets = agent.list_deformation_targets(source)
        assert targets["status"] == "OK"
        assert [item["name"] for item in targets["targets"]] == ["Basis", "Smile", "Blink"]
        assert next(item for item in targets["targets"] if item["name"] == "Blink")["locked"]
        checks.append("list returns Basis and keys with lock/active state and revision")

        basis = targets["targets"][0]
        selected = agent.select_deformation_target(
            source, basis["target_id"], expected_revision=targets["target_revision"]
        )
        assert selected["target"]["name"] == "Basis"
        _assert_error(
            "TARGET_REVISION_MISMATCH",
            lambda: agent.select_deformation_target(
                source, targets["targets"][1]["target_id"],
                expected_revision=targets["target_revision"],
            ),
        )
        checks.append("target selection shares UI operator and stale revisions fail closed")

        refreshed = agent.list_deformation_targets(source)
        blink = next(item for item in refreshed["targets"] if item["name"] == "Blink")
        agent.select_deformation_target(
            source, blink["target_id"], expected_revision=refreshed["target_revision"]
        )
        _enter_controller_edit(source, controller)
        _assert_error("SHAPE_KEY_LOCKED", agent.begin_operation)
        _close_controller_edit()
        checks.append("locked target can be listed/selected but cannot begin deformation")

        refreshed = agent.list_deformation_targets(source)
        smile = next(item for item in refreshed["targets"] if item["name"] == "Smile")
        agent.select_deformation_target(
            source, smile["target_id"], expected_revision=refreshed["target_revision"]
        )
        _enter_controller_edit(source, controller)
        begin = agent.begin_operation()
        assert begin["target"]["name"] == "Smile"
        handle = begin["operation_id"]
        p0 = addon._source_positions(source, source.data.shape_keys.key_blocks[1])
        selected_ids = set(begin["selected_vertex_ids"])
        absolute_targets = {
            vertex_id: tuple(p0[vertex_id] + Vector((0, 0, 0.25)))
            for vertex_id in selected_ids
        }
        before_basis = [point.co.copy() for point in source.data.shape_keys.key_blocks[0].data]
        before_smile = [point.co.copy() for point in source.data.shape_keys.key_blocks[1].data]
        _assert_error(
            "TARGET_SET_MISMATCH",
            lambda: agent.set_knot_targets(handle, {}),
        )
        extra_target = dict(absolute_targets)
        extra_target[999999] = (0.0, 0.0, 0.0)
        _assert_error(
            "TARGET_SET_MISMATCH",
            lambda: agent.set_knot_targets(handle, extra_target),
        )
        nonfinite_target = dict(absolute_targets)
        first_id = next(iter(nonfinite_target))
        nonfinite_target[first_id] = (0.0, 0.0, float("nan"))
        _assert_error(
            "NON_FINITE_RESULT",
            lambda: agent.set_knot_targets(handle, nonfinite_target),
        )
        assert all(
            (point.co - before_basis[index]).length_squared < 1e-12
            for index, point in enumerate(source.data.shape_keys.key_blocks[0].data)
        )
        assert all(
            (point.co - before_smile[index]).length_squared < 1e-12
            for index, point in enumerate(source.data.shape_keys.key_blocks[1].data)
        )
        result = agent.set_knot_targets(handle, absolute_targets)
        assert result["moved_vertices"] == len(selected_ids)
        assert result["target"]["name"] == "Smile"
        assert any(
            (source.data.shape_keys.key_blocks[1].data[index].co - p0[vertex_id]).length_squared > 1e-8
            for vertex_id, index in addon._source_id_maps(source)[0].items()
            if vertex_id in selected_ids
        )
        committed = agent.commit_operation(handle)
        assert committed["changed_count"] > 0
        _assert_error("OPERATION_HANDLE_INVALID", lambda: agent.update_operation(handle))
        checks.append("absolute full selected-ID targets write captured key and commit by handle")

        _close_controller_edit()
        current = agent.list_deformation_targets(source)
        smile = next(item for item in current["targets"] if item["name"] == "Smile")
        agent.select_deformation_target(
            source, smile["target_id"], expected_revision=current["target_revision"]
        )
        _enter_controller_edit(source, controller)
        stale_begin = agent.begin_operation()
        target_before = [point.co.copy() for point in source.data.shape_keys.key_blocks[1].data]
        source.active_shape_key_index = 2
        _assert_error(
            "SHAPE_KEY_TARGET_CHANGED",
            lambda: agent.set_knot_targets(stale_begin["operation_id"], absolute_targets),
        )
        agent.cancel_operation(stale_begin["operation_id"])
        assert all(
            (point.co - target_before[index]).length_squared < 1e-12
            for index, point in enumerate(source.data.shape_keys.key_blocks[1].data)
        )
        checks.append("changing target mid-operation rejects writes and cancel restores captured target")
        _close_controller_edit()

        second_source, second_controller = _make_source("Agent Source B", with_keys=False)
        second = (second_source, second_controller)
        first_committed_coords = [
            point.co.copy() for point in source.data.shape_keys.key_blocks[1].data
        ]
        second_targets = agent.list_deformation_targets(second_source)
        assert len(second_targets["targets"]) == 1
        assert second_targets["targets"][0]["kind"] == "BASE"
        _enter_controller_edit(second_source, second_controller)
        base_before = [vertex.co.copy() for vertex in second_source.data.vertices]
        tx = agent.begin_operation()
        delta_result = agent.update_operation(tx["operation_id"], delta=(0, 0, 0.1))
        assert delta_result["target"]["kind"] == "BASE"
        cancelled = agent.cancel_operation(tx["operation_id"])
        assert cancelled["changed_count"] > 0
        assert all((vertex.co - base_before[index]).length_squared < 1e-12
                   for index, vertex in enumerate(second_source.data.vertices))
        assert all(
            (point.co - first_committed_coords[index]).length_squared < 1e-12
            for index, point in enumerate(source.data.shape_keys.key_blocks[1].data)
        )
        checks.append("Base target cancel restores exact data and operation remains source-local")
        _close_controller_edit()

        result = {"status": "PASS", "checks": checks,
                  "source_count": 2, "blender_version": bpy.app.version_string}
        print("DANP_RESULT_JSON=" + json.dumps(result))
        return result
    finally:
        _close_controller_edit()
        addon.unregister()
        for pair in (first, second):
            if pair:
                source, controller = pair
                for obj in (controller, source):
                    if obj and obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)


result = run()
