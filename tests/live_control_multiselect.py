"""Blender regression for sidebar multi-select and derived row selection state."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402
from dan_form import operators  # noqa: E402


def _select_only(obj):
    for candidate in bpy.context.view_layer.objects:
        candidate.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def run():
    addon.register()
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    mesh = bpy.data.meshes.new("Selection Fixture Mesh")
    mesh.from_pydata(
        [(float(i), 0.0, 0.0) for i in range(5)],
        [(0, 1), (1, 2), (2, 3), (3, 4)],
        [],
    )
    source = bpy.data.objects.new("Selection Fixture", mesh)
    bpy.context.scene.collection.objects.link(source)
    _select_only(source)
    try:
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "initialize disposable selection fixture")
        controller = addon._find_controller(source)
        bpy.ops.object.mode_set(mode="EDIT")

        memberships = ((0, 1), (2, 3), (1, 2))
        uuids = []
        vertex_ids_by_index = {
            index: vertex_id for vertex_id, index in addon._source_id_maps(source)[0].items()
        }
        for ordinal, indices in enumerate(memberships, start=1):
            ids = {vertex_ids_by_index[index] for index in indices}
            addon._select_source_ids(source, ids, set())
            check(bpy.ops.dan_form.create_control(control_name=f"Fixture {ordinal}") == {"FINISHED"},
                  f"create definition {ordinal}")
            uuids.append(addon._controls(source)[-1]["control_uuid"])

        controls = addon._controls(source)
        first_ids = set(controls[0]["vertex_ids"])
        second_ids = set(controls[1]["vertex_ids"])
        overlap_ids = set(controls[2]["vertex_ids"])
        addon._select_source_ids(source, first_ids, set())
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[1], add_to_selection=True) == {"FINISHED"},
              "Shift-add operator unions the second control with current selection")
        selected, _edges = addon._source_selection(source)
        check(selected == first_ids | second_ids, "add selection retains earlier vertices")
        check(bpy.context.scene.dan_form_selected_control == uuids[1],
              "row action makes clicked control active for shared row actions")
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[1], add_to_selection=True) == {"FINISHED"},
              "Shift-clicking an already selected control toggles its membership off")
        selected, _edges = addon._source_selection(source)
        check(selected == first_ids, "Shift-deselect preserves the other control membership")
        addon._select_source_ids(source, first_ids, set())
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[0]) == {"FINISHED"},
              "clicking the only selected control toggles it off")
        check(addon._selected_source_vertex_ids(source) == set(),
              "repeat-click leaves mesh selection empty")

        addon._select_source_ids(source, {next(iter(overlap_ids))}, set())
        states = addon._control_selection_states(source, source)
        check(states[uuids[0]] == "PARTIAL" and states[uuids[2]] == "PARTIAL",
              "shared selected point derives partial states for both overlapping controls")
        check(states[uuids[1]] == "NONE", "unrelated control derives unselected state")
        addon._select_source_ids(source, overlap_ids, set())
        states = addon._control_selection_states(source, source)
        check(states[uuids[2]] == "FULL", "all vertices derive full state")
        check(states[uuids[0]] == "PARTIAL" and states[uuids[1]] == "PARTIAL",
              "overlapping controls can report partial while another is full")

        definitions_before = source[addon.CONTROLS_KEY]
        positions_before = [tuple(vertex.co) for vertex in source.data.vertices]
        check("UNDO" not in operators.DANFORM_OT_select_control.bl_options,
              "transient selection does not create a geometry Undo step")
        addon._select_source_ids(source, first_ids, set())
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[2]) == {"FINISHED"},
              "plain selection replaces prior selection")
        selected, _edges = addon._source_selection(source)
        check(selected == overlap_ids, "plain selection leaves only clicked control selected")
        check(source[addon.CONTROLS_KEY] == definitions_before
              and positions_before == [tuple(vertex.co) for vertex in source.data.vertices],
              "select and add operations leave definitions and geometry untouched")

        bpy.ops.object.mode_set(mode="OBJECT")
        hidden_control = controls[1]
        addon._mutate_control_visibility(source, hidden_control, reveal=False)
        addon._rebuild_proxy(source, controller)
        _select_only(controller)
        bpy.ops.object.mode_set(mode="EDIT")
        visible_ids, visible_edges = addon._control_effective(source, controls[0])
        addon._select_proxy_ids(controller, visible_ids, visible_edges)
        controller_states = addon._control_selection_states(source, controller)
        check(controller_states[uuids[1]] == "NONE",
              "fully hidden effective membership is not vacuously selected")
        check(controller_states[uuids[0]] == "FULL",
              "controller selection state resolves persistent proxy IDs to Source membership")
        addon._select_proxy_ids(controller, set(), set())
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[0]) == {"FINISHED"}
              and controller.mode == "EDIT",
              "selecting from Controller Object Mode enters Controller Edit")
        proxy_vertices, proxy_edges = addon._proxy_selection(controller)
        check(proxy_vertices == addon._control_effective(source, controls[0])[0],
              "Controller Object Mode selection selects the effective proxy membership")
        check(bpy.ops.dan_form.select_control(control_uuid=uuids[2], add_to_selection=True) == {"FINISHED"},
              "additive selection also works in Controller Edit")
        proxy_vertices, _proxy_edges = addon._proxy_selection(controller)
        expected_union = (addon._control_effective(source, controls[0])[0]
                          | addon._control_effective(source, controls[2])[0])
        check(proxy_vertices == expected_union, "Controller Shift-add preserves previous proxy vertices")
        return {"status": "PASS", "checks": checks, "blender_version": bpy.app.version_string}
    finally:
        if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in list(bpy.data.objects):
            if obj == source or obj.parent == source:
                mesh_data = getattr(obj, "data", None)
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh_data is not None and mesh_data.users == 0 and bpy.data.meshes.get(mesh_data.name):
                    bpy.data.meshes.remove(mesh_data)


result = run()
