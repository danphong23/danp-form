"""DANP Form selection operators."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, StringProperty

from .. import runtime
from ..constants import *

def bind(api) -> None:
    """Bind Source/Controller workflow adapters from the compatibility facade."""
    bindings = api.items() if isinstance(api, dict) else (
        (name, getattr(api, name)) for name in dir(api)
    )
    for name, value in bindings:
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = value

class DANFORM_OT_select_control(bpy.types.Operator):
    bl_idname = "dan_form.select_control"
    bl_label = "Select Control"
    bl_description = "Select this control; Shift-click to add or remove it; click it again to deselect"
    # Selection and active-row changes are transient UI state, like Blender's
    # native selection tools, and must not consume a geometry Undo step.
    bl_options = {"REGISTER"}
    control_uuid: StringProperty(default="")
    add_to_selection: BoolProperty(name="Add to Selection", default=False)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        self.add_to_selection = bool(event.shift)
        return self.execute(context)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if not self.control_uuid and source is not None:
            active_control = _active_control(context, source)
            self.control_uuid = active_control.get("control_uuid", "") if active_control else ""
        control = _control(source, self.control_uuid)
        if source is None or control is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        try:
            if controller is not None:
                _transform_session.finalize_active(source, controller, _workflow_dependencies())
            # A row's action button also makes that row active for the shared
            # Rename/Sync/Reorder/Delete controls.  Suppress the index callback
            # here because it would replace selection before a Shift-add.
            scene = context.scene
            for index, item in enumerate(scene.dan_form_control_items):
                if item.control_uuid == self.control_uuid:
                    previous_guard = runtime.UI_SYNC_GUARD
                    runtime.UI_SYNC_GUARD = True
                    try:
                        scene.dan_form_control_index = index
                        scene.dan_form_selected_control = self.control_uuid
                        _ACTIVE_CONTROL_UUIDS[item.source_uuid] = self.control_uuid
                    finally:
                        runtime.UI_SYNC_GUARD = previous_guard
                    break
            vertex_ids = {int(value) for value in control.get("vertex_ids", [])}
            edge_ids = {int(value) for value in control.get("edge_ids", [])}
            scene.dan_form_selected_control = self.control_uuid
            if active == source and source.mode == "EDIT":
                target_vertices, target_edges = vertex_ids, edge_ids
                active_mesh = source
            elif active == controller and controller.mode == "OBJECT":
                _select_only(context, controller)
                bpy.ops.object.mode_set(mode="EDIT")
                target_vertices, target_edges = _control_effective(source, control)
                active_mesh = controller
            elif active == controller and controller.mode == "EDIT":
                target_vertices, target_edges = _control_effective(source, control)
                active_mesh = controller
            elif active == source and source.mode == "OBJECT":
                _select_only(context, source)
                bpy.ops.object.mode_set(mode="EDIT")
                target_vertices, target_edges = vertex_ids, edge_ids
                active_mesh = source
            else:
                raise ValueError("EDIT_SOURCE_OR_CONTROLLER_REQUIRED")
            if not target_vertices and not target_edges:
                raise ValueError("CONTROL_HAS_NO_EFFECTIVE_MEMBERSHIP")
            selected_vertices, selected_edges = _selected_source_elements(active_mesh)
            if self.add_to_selection:
                if target_vertices <= selected_vertices:
                    # Shift-click toggles a fully selected membership off.
                    remaining_vertices = selected_vertices - target_vertices
                    edge_vids = _source_edge_vids(source)
                    remaining_edges = {
                        edge_id for edge_id in selected_edges - target_edges
                        if not set(edge_vids.get(edge_id, ())) & target_vertices
                    }
                    if active_mesh == source:
                        _select_source_ids(source, remaining_vertices, remaining_edges)
                    else:
                        _select_proxy_ids(controller, remaining_vertices, remaining_edges)
                    was_deselected = True
                else:
                    if active_mesh == source:
                        _select_source_ids(source, target_vertices, target_edges, add=True)
                    else:
                        _select_proxy_ids(controller, target_vertices, target_edges, add=True)
                    was_deselected = False
            elif (selected_vertices == target_vertices and selected_edges == target_edges):
                # Clicking the only selected membership again clears it.
                if active_mesh == source:
                    _select_source_ids(source, set(), set())
                else:
                    _select_proxy_ids(controller, set(), set())
                was_deselected = True
            else:
                if active_mesh == source:
                    _select_source_ids(source, target_vertices, target_edges)
                else:
                    _select_proxy_ids(controller, target_vertices, target_edges)
                was_deselected = False
            context.scene.dan_form_status = (
                f"Deselected {control.get('name', 'Control')}"
                if was_deselected else (
                    f"Added {control.get('name', 'Control')} to selection"
                    if self.add_to_selection else f"Selected {control.get('name', 'Control')}"
                )
            )
            _tag_viewport_redraw(context)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

__all__ = ["bind", "DANFORM_OT_select_control"]
