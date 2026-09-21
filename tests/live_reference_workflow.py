"""Non-destructive front/side/perspective workflow gate on the open character."""

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
    original = context.view_layer.objects.active
    if original is not None and original.mode != "OBJECT":
        raise RuntimeError("Run this gate from Object Mode")
    selected = list(context.selected_objects)
    scene = context.scene
    old_source, old_controller = scene.dan_form_source, scene.dan_form_controller
    old_status = scene.dan_form_status
    view_area = next((area for area in (context.screen.areas if context.screen else ()) if area.type == "VIEW_3D"), None)
    view_state = None
    if view_area is not None:
        region_3d = view_area.spaces.active.region_3d
        view_state = (region_3d.view_perspective, region_3d.view_distance,
                      region_3d.view_location.copy(), region_3d.view_rotation.copy())
    source, controller = addon._context_source(context)
    if source is None or controller is None or not addon._controls(source):
        raise RuntimeError("The open character must already be initialized")
    report = {"file": bpy.data.filepath, "dirty_before": bpy.data.is_dirty, "checks": []}

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        report["checks"].append(name)

    def set_view(view):
        if view_area is None:
            raise AssertionError("VIEW_3D area is required for reference workflow")
        region = next(region for region in view_area.regions if region.type == "WINDOW")
        with context.temp_override(area=view_area, region=region, space_data=view_area.spaces.active):
            bpy.ops.view3d.view_axis(type=view, align_active=False) if view in {"FRONT", "RIGHT"} else bpy.ops.view3d.view_persportho()
        return view_area.spaces.active.region_3d.view_perspective

    try:
        addon._select_only(context, controller)
        bpy.ops.object.mode_set(mode="EDIT")
        control = next((item for item in addon._controls(source)
                        if addon._control_effective(source, item)[0]), None)
        if control is None:
            raise AssertionError("no effective control for reference workflow")
        selected_vids, selected_eids = addon._control_effective(source, control)
        addon._select_proxy_ids(controller, selected_vids, selected_eids)
        check(bool(selected_vids), "reference control selects mapped vertices")
        before = {int(v): source.data.vertices[index].co.copy()
                  for v, index in addon._source_id_maps(source)[0].items()}

        for label, view, delta in (("Front Orthographic", "FRONT", (0.015, 0.0, 0.0)),
                                   ("Side Orthographic", "RIGHT", (0.0, 0.015, 0.0)),
                                   ("Perspective", "PERSP", (0.01, 0.01, 0.01))):
            perspective = set_view(view)
            check((view == "PERSP" and perspective == "PERSP") or
                  (view != "PERSP" and perspective == "ORTHO"), f"{label} viewport state")
            addon._deform_begin(source, controller)
            preview = addon._deform_update(source, controller, delta=delta, profile="SMOOTH", radius=3.0)
            check(preview["selected_vertices"] == len(selected_vids), f"{label} preview resolves selected control")
            addon._deform_cancel(source, controller)
            after = {int(v): source.data.vertices[index].co.copy()
                     for v, index in addon._source_id_maps(source)[0].items()}
            check(all((after[v] - before[v]).length < 1e-7 for v in before), f"{label} cancel restores Source")
            check(all((after[v] - before[v]).length < 1e-7 for v in before), f"{label} cancel restores reference baseline")

        visible_before = tuple(len(item) for item in addon._effective_proxy_elements(source))
        addon._mutate_control_visibility(source, control, False)
        hidden = tuple(len(item) for item in addon._effective_proxy_elements(source))
        check(hidden[0] <= visible_before[0] and hidden[1] <= visible_before[1], "reference hide releases the selected region")
        addon._mutate_control_visibility(source, control, True)
        check(tuple(len(item) for item in addon._effective_proxy_elements(source)) == visible_before,
              "reference reveal restores the selected region")
        report["status"] = "PASS"
    finally:
        if context.object is not None and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = original
        if view_area is not None and view_state is not None:
            region_3d = view_area.spaces.active.region_3d
            region_3d.view_perspective, region_3d.view_distance, region_3d.view_location, region_3d.view_rotation = view_state
        scene.dan_form_source, scene.dan_form_controller = old_source, old_controller
        scene.dan_form_status = old_status
        addon._sync_context_ui_list(context)
        report["restored_active"] = original.name if original else None
        report["dirty_after"] = bpy.data.is_dirty
    return report


result = run()
