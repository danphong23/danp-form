"""MCP-only Phase 4 deformation gate on a temporary two-quad fixture."""

import sys

import bpy
from mathutils import Vector


def _addon_module():
    candidates = [module for name, module in sys.modules.items()
                  if (name == "dan_form" or name.endswith(".dan_form"))
                  and hasattr(module, "_deform_begin")]
    if len(candidates) != 1:
        raise RuntimeError("DANP Form module is not uniquely loaded")
    return candidates[0]


def run():
    addon = _addon_module()
    context = bpy.context
    active = context.view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        raise RuntimeError("Run this gate from Object Mode")
    selected = list(context.selected_objects)
    scene = context.scene
    old_source, old_controller = scene.dan_form_source, scene.dan_form_controller
    old_status = scene.dan_form_status
    report = {"file": bpy.data.filepath, "dirty_before": bpy.data.is_dirty, "checks": []}
    mesh = bpy.data.meshes.new("DANP_DEFORM_GATE_MESH")
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 0, 1), (1, 0, 1), (2, 0, 1)],
        [], ((0, 1, 4, 3), (1, 2, 5, 4)),
    )
    model = bpy.data.objects.new("DANP_DEFORM_GATE", mesh)
    scene.collection.objects.link(model)
    controller = None

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        report["checks"].append(name)

    def positions():
        vids, _ = addon._source_id_maps(model)
        return {vid: mesh.vertices[index].co.copy() for vid, index in vids.items()}

    try:
        addon._select_only(context, model)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "fixture Init")
        controller = addon._find_controller(model)
        addon._select_only(context, model)
        bpy.ops.object.mode_set(mode="EDIT")
        context.tool_settings.mesh_select_mode = (False, True, False)
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"}, "fixture creates editable control")
        bpy.ops.object.mode_set(mode="OBJECT")
        addon._select_only(context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        bm = __import__("bmesh").from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(addon.PROXY_VID_ATTR)
        if layer is None:
            raise AssertionError("proxy vertex IDs missing")
        left = {int(vertex[layer]) for vertex in bm.verts if vertex.co.x < 0.5}
        check(len(left) == 2, f"left boundary selection has two vertices (count={len(left)}, coords={[tuple(vertex.co) for vertex in bm.verts]})")
        addon._select_proxy_ids(controller, left, set())
        before = positions()
        addon._deform_begin(model, controller)
        preview = addon._deform_update(model, controller, delta=(0, 0, 0.5), profile="SMOOTH", radius=2.0)
        preview_positions = positions()
        check(preview["selected_vertices"] == 2, "transaction captures selected controller vertices")
        check(all(abs(preview_positions[vid].z - before[vid].z - 0.5) < 1e-7 for vid in left), "selected targets receive exact delta")
        addon._deform_cancel(model, controller)
        check(all((positions()[vid] - before[vid]).length < 1e-7 for vid in before), "cancel restores Source exactly")
        check(all((controller.data.vertices[index].co - before[vid]).length < 1e-7
                   for vid, index in addon._source_id_maps(model)[0].items() if vid in before), "cancel resyncs Controller")

        addon._select_proxy_ids(controller, left, set())
        before_commit = positions()
        result = bpy.ops.dan_form.deform(delta=(0.25, 0.0, 0.0), profile="LINEAR", radius=0.0)
        check(result == {"FINISHED"}, "deform operator commits through Blender UI API")
        after_commit = positions()
        check(all(abs(after_commit[vid].x - before_commit[vid].x - 0.25) < 1e-7 for vid in left), "committed target reaches Source")
        check(all(abs(after_commit[vid].x - before_commit[vid].x) < 1e-7 for vid in after_commit if vid not in left), "stationary enabled vertices remain fixed")
        report["status"] = "PASS"
    finally:
        if context.object is not None and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if controller is not None and controller.name in bpy.data.objects:
            proxy_mesh = controller.data
            bpy.data.objects.remove(controller, do_unlink=True)
            if proxy_mesh.users == 0:
                bpy.data.meshes.remove(proxy_mesh)
        if model.name in bpy.data.objects:
            bpy.data.objects.remove(model, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = active
        scene.dan_form_source, scene.dan_form_controller = old_source, old_controller
        scene.dan_form_status = old_status
        addon._sync_context_ui_list(context)
        report["restored_active"] = active.name if active else None
        report["dirty_after"] = bpy.data.is_dirty
        report["fixture_removed"] = not any(obj.name.startswith("DANP_DEFORM_GATE") for obj in bpy.data.objects)
    return report


result = run()
